"""Smoke tests for WhatsApp server routes."""

import io
import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch


BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.agent_runtime import AgentResponse
import whatsapp_server


def _make_wav_file() -> str:
    fd, temp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(temp_path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 1600)
    return temp_path


def _make_text_file(suffix=".html", content="<h1>hola</h1>") -> str:
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    Path(temp_path).write_text(content, encoding="utf-8")
    return temp_path


class WhatsAppServerSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = whatsapp_server.app.test_client()

    def test_health_returns_expected_fields(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["agent"], "rAImundoGPT")
        self.assertIn("personality", data)

    def test_chat_uses_agent_runtime_and_returns_metadata(self):
        temp_artifact = _make_text_file()
        fake_runtime = AgentResponse(
            success=True,
            response="RUNTIME::hola desde whatsapp",
            used_agent_loop=True,
            run_id="wa-smoke-run",
            steps_taken=2,
            actions_log=[],
            artifacts=[
                {
                    "path": temp_artifact,
                    "filename": Path(temp_artifact).name,
                    "tipo": "html",
                    "title": "landing",
                }
            ],
        )

        try:
            with (
                patch.object(
                    whatsapp_server.gestor,
                    "procesar_mensaje",
                    return_value={"ejecuto_herramienta": False},
                ),
                patch.object(
                    whatsapp_server.agent_runtime,
                    "handle_text",
                    return_value=fake_runtime,
                ) as runtime_mock,
                patch.object(whatsapp_server.metrics, "track_request"),
                patch.object(whatsapp_server, "_extraer_y_guardar_conocimiento"),
                patch.object(
                    whatsapp_server,
                    "limpiar_formato_markdown",
                    side_effect=lambda text: text,
                ),
            ):
                response = self.client.post(
                    "/chat",
                    json={
                        "mensaje": "hola desde smoke",
                        "user_id": "smoke_user",
                        "user_name": "Smoke Tester",
                    },
                )
        finally:
            Path(temp_artifact).unlink(missing_ok=True)

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data["respuesta"], "RUNTIME::hola desde whatsapp")
        self.assertEqual(data["user_id"], "smoke_user")
        self.assertTrue(data["agentic"])
        self.assertEqual(data["steps"], 2)
        self.assertEqual(data["run_id"], "wa-smoke-run")
        self.assertEqual(data["archivo"], temp_artifact)
        self.assertEqual(data["tipo_archivo"], "html")
        self.assertEqual(len(data["archivos"]), 1)
        self.assertEqual(data["archivos"][0]["path"], temp_artifact)

        runtime_mock.assert_called_once()
        request_obj = runtime_mock.call_args.args[0]
        self.assertEqual(request_obj.text, "hola desde smoke")
        self.assertEqual(request_obj.user_id, "smoke_user")
        self.assertEqual(request_obj.user_name, "Smoke Tester")
        self.assertEqual(request_obj.channel, "whatsapp")

    def test_chat_direct_image_tool_returns_attachment_metadata(self):
        temp_image = _make_text_file(suffix=".png", content="fake-image")

        try:
            with (
                patch.object(
                    whatsapp_server.gestor,
                    "procesar_mensaje",
                    return_value={
                        "ejecuto_herramienta": True,
                        "tipo": "generar_imagen",
                        "resultado": "Imagen creada",
                        "imagen_path": temp_image,
                    },
                ),
                patch.object(whatsapp_server.metrics, "track_request"),
                patch.object(whatsapp_server, "_extraer_y_guardar_conocimiento"),
                patch.object(
                    whatsapp_server,
                    "limpiar_formato_markdown",
                    side_effect=lambda text: text,
                ),
            ):
                response = self.client.post(
                    "/chat",
                    json={
                        "mensaje": "Genera una imagen de un pato",
                        "user_id": "smoke_user",
                    },
                )
        finally:
            Path(temp_image).unlink(missing_ok=True)

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data["respuesta"], "Imagen creada")
        self.assertEqual(data["archivo"], temp_image)
        self.assertEqual(data["tipo_archivo"], "png")
        self.assertEqual(data["archivos"][0]["path"], temp_image)

    def test_audio_stt_returns_transcribed_text(self):
        with patch.object(
            whatsapp_server.audio_handler,
            "speech_to_text",
            return_value="texto transcrito",
        ):
            response = self.client.post(
                "/audio/stt",
                data={
                    "user_id": "audio_smoke",
                    "audio": (io.BytesIO(b"fake-ogg-data"), "sample.ogg"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data["texto"], "texto transcrito")
        self.assertEqual(data["user_id"], "audio_smoke")

    def test_audio_tts_returns_audio_file(self):
        temp_wav = _make_wav_file()

        with patch.object(
            whatsapp_server.audio_handler,
            "text_to_speech",
            return_value=temp_wav,
        ), patch.object(
            whatsapp_server.detector_idioma,
            "detectar",
            return_value="es",
        ):
            response = self.client.post(
                "/audio/tts",
                json={
                    "texto": "hola audio",
                    "user_id": "audio_smoke",
                },
            )

        try:
            self.assertEqual(response.status_code, 200, response.status)
            self.assertTrue(response.content_type.startswith("audio/"))
        finally:
            response.close()
            Path(temp_wav).unlink(missing_ok=True)

    def test_audio_chat_returns_audio_response(self):
        temp_wav = _make_wav_file()

        fake_runtime = AgentResponse(
            success=True,
            response="RUNTIME::audio response",
            used_agent_loop=True,
            run_id="wa-audio-run",
            steps_taken=1,
            actions_log=[],
        )

        with (
            patch.object(
                whatsapp_server.audio_handler,
                "speech_to_text",
                return_value="audio transcrito",
            ),
            patch.object(
                whatsapp_server.audio_handler,
                "text_to_speech",
                return_value=temp_wav,
            ),
            patch.object(
                whatsapp_server.gestor,
                "procesar_mensaje",
                return_value={"ejecuto_herramienta": False},
            ),
            patch.object(
                whatsapp_server.agent_runtime,
                "handle_text",
                return_value=fake_runtime,
            ) as runtime_mock,
            patch.object(
                whatsapp_server,
                "limpiar_formato_markdown",
                side_effect=lambda text: text,
            ),
            patch.object(
                whatsapp_server.detector_idioma,
                "detectar",
                return_value="es",
            ),
        ):
            response = self.client.post(
                "/audio/chat",
                data={
                    "user_id": "audio_smoke",
                    "audio": (io.BytesIO(b"fake-ogg-data"), "sample.ogg"),
                },
                content_type="multipart/form-data",
            )

        try:
            self.assertEqual(response.status_code, 200, response.status)
            self.assertTrue(response.content_type.startswith("audio/"))
            runtime_mock.assert_called_once()
            request_obj = runtime_mock.call_args.args[0]
            self.assertEqual(request_obj.text, "audio transcrito")
            self.assertEqual(request_obj.user_id, "audio_smoke")
            self.assertEqual(request_obj.channel, "whatsapp")
        finally:
            response.close()
            Path(temp_wav).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)