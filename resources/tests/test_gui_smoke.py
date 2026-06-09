"""Smoke tests for the desktop GUI send/render flow."""

import sys
import tkinter as tk
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.agent_runtime import AgentResponse
import raymundo


class _ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


class _SilentAudioHandler:
    def is_tts_available(self):
        return False


class _FakeRuntime:
    def __init__(self, response=None):
        self.requests = []
        self.response = response or AgentResponse(
            success=True,
            response="GUI::respuesta de prueba",
            used_agent_loop=True,
            run_id="gui-smoke-run",
            steps_taken=1,
            actions_log=[],
        )

    def handle_text(self, request):
        self.requests.append(request)
        return self.response


class ChatGuiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

        self.gui = object.__new__(raymundo.ChatGUI)
        self.gui.root = self.root
        self.gui.entry_mensaje = tk.Text(self.root)
        self.gui.text_chat = tk.Text(self.root)
        self.gui.label_estado = tk.Label(self.root, text="✅  Listo para ayudarte")
        self.gui.btn_adjuntar = tk.Button(self.root)
        self.gui.btn_reproducir = tk.Button(self.root)
        self.gui._planeacion_wizard = None
        self.gui._placeholder_active = False
        self.gui._image_refs = []
        self.gui.archivo_adjunto = None
        self.gui.procesando = False
        self.gui.audio_handler = _SilentAudioHandler()
        self.gui.agent_runtime = _FakeRuntime()
        self.gui.historial_chat = []
        self.gui.contador_mensajes = 0
        self.gui.agent_memory = type("_Memory", (), {"clear": lambda *args, **kwargs: None})()
        self.gui.herramientas = type(
            "_Herramientas",
            (),
            {
                "memory": type(
                    "_UserMemory",
                    (),
                    {"clear_user_context": lambda *args, **kwargs: None},
                )(),
            },
        )()
        self.gui._user_id = "gui_smoke_user"
        self.gui._set_placeholder = lambda: None

    def tearDown(self):
        try:
            self.root.update_idletasks()
            self.root.update()
        except tk.TclError:
            pass
        self.root.destroy()

    def test_send_message_renders_runtime_response(self):
        self.gui.entry_mensaje.insert("1.0", "Hola desde GUI")

        with patch.object(raymundo.threading, "Thread", _ImmediateThread):
            self.gui._enviar_mensaje()
            self.root.update_idletasks()
            self.root.update()

        rendered = self.gui.text_chat.get("1.0", "end-1c")
        self.assertIn("Tú", rendered)
        self.assertIn("Hola desde GUI", rendered)
        self.assertIn("GUI::respuesta de prueba", rendered)
        self.assertEqual(self.gui.label_estado.cget("text"), "✅  Listo para ayudarte")
        self.assertFalse(self.gui.procesando)

        self.assertEqual(len(self.gui.agent_runtime.requests), 1)
        request_obj = self.gui.agent_runtime.requests[0]
        self.assertEqual(request_obj.text, "Hola desde GUI")
        self.assertEqual(request_obj.user_id, "gui_smoke_user")
        self.assertEqual(request_obj.channel, "desktop_gui")

    def test_send_message_renders_and_opens_generated_artifact(self):
        fd, temp_path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        Path(temp_path).unlink(missing_ok=True)
        Path(temp_path).write_text("excel", encoding="utf-8")
        self.addCleanup(lambda: Path(temp_path).unlink(missing_ok=True))

        self.gui.agent_runtime = _FakeRuntime(
            response=AgentResponse(
                success=True,
                response="GUI::hoja creada",
                used_agent_loop=True,
                run_id="gui-artifact-run",
                steps_taken=1,
                actions_log=[],
                artifacts=[
                    {
                        "path": temp_path,
                        "filename": Path(temp_path).name,
                        "tipo": "hoja_calculo",
                        "title": "Ventas",
                    }
                ],
            )
        )
        self.gui.entry_mensaje.insert("1.0", "Hazme un excel")

        with (
            patch.object(raymundo.threading, "Thread", _ImmediateThread),
            patch.object(raymundo.os, "startfile") as startfile_mock,
        ):
            self.gui._enviar_mensaje()
            self.root.update_idletasks()
            self.root.update()

        rendered = self.gui.text_chat.get("1.0", "end-1c")
        self.assertIn("GUI::hoja creada", rendered)
        self.assertIn("Archivos generados:", rendered)
        self.assertIn(temp_path, rendered)
        startfile_mock.assert_called_once_with(temp_path)

    def test_send_message_renders_image_artifact_inline(self):
        fd, temp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        Path(temp_path).write_text("fake-image", encoding="utf-8")
        self.addCleanup(lambda: Path(temp_path).unlink(missing_ok=True))

        inserted_images = []
        self.gui._insertar_imagen_ui = lambda path: inserted_images.append(path)
        self.gui.agent_runtime = _FakeRuntime(
            response=AgentResponse(
                success=True,
                response="GUI::imagen creada",
                used_agent_loop=True,
                run_id="gui-image-run",
                steps_taken=1,
                actions_log=[],
                artifacts=[
                    {
                        "path": temp_path,
                        "filename": Path(temp_path).name,
                        "tipo": "png",
                        "title": "pato",
                    }
                ],
            )
        )
        self.gui.entry_mensaje.insert("1.0", "Genera una imagen de un pato")

        with (
            patch.object(raymundo.threading, "Thread", _ImmediateThread),
            patch.object(raymundo.os, "startfile") as startfile_mock,
        ):
            self.gui._enviar_mensaje()
            self.root.update_idletasks()
            self.root.update()

        rendered = self.gui.text_chat.get("1.0", "end-1c")
        self.assertIn("GUI::imagen creada", rendered)
        self.assertIn(temp_path, rendered)
        self.assertEqual(inserted_images, [temp_path])
        startfile_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)