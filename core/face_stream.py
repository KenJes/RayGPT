"""
face_stream.py — Streaming de webcam con análisis facial en tiempo real.

Captura frames de la webcam, detecta rostros, y ejecuta análisis facial
y reconocimiento usando FaceManager (OpenCV + ONNX Runtime).

Uso:
    from core.face_stream import FaceStream
    stream = FaceStream(face_manager)
    stream.start()          # Abre ventana con feed de cámara
    stream.stop()
    stream.capture_and_analyze()  # Captura un frame y analiza

Requiere: opencv-python
"""

from __future__ import annotations

import logging
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    logger.warning("⚠️ OpenCV no disponible: pip install opencv-python")


class FaceStream:
    """
    Streaming de webcam con análisis facial.

    Puede funcionar en dos modos:
    1. capture_and_analyze() — Captura un frame, analiza y retorna resultado.
    2. start()/stop() — Loop continuo con ventana OpenCV mostrando detecciones.
    """

    def __init__(self, face_manager, camera_index: int = 0):
        self.fm = face_manager
        self.camera_index = camera_index
        self._running = False
        self._thread = None
        self._last_result = None
        self._on_result: Callable | None = None

    @property
    def available(self) -> bool:
        return _CV2_AVAILABLE and self.fm is not None and self.fm.available

    def _check_available(self) -> dict | None:
        if not _CV2_AVAILABLE:
            return {"success": False, "output": None, "error": "OpenCV no disponible: pip install opencv-python"}
        if not self.fm or not self.fm.available:
            return {"success": False, "output": None, "error": "FaceManager no disponible."}
        return None

    # ═══════════════════════════════════════════════════════════
    # Modo 1: Captura única + análisis
    # ═══════════════════════════════════════════════════════════

    def capture_and_analyze(self, actions: list[str] | None = None, recognize: bool = False) -> dict:
        """
        Captura un frame de la webcam y ejecuta análisis facial.

        Args:
            actions: Atributos a analizar ("age", "gender", "emotion", "race").
            recognize: Si True, también intenta identificar en la BD.

        Returns:
            {"success": bool, "output": dict, "error": str|None}
            output contiene "analysis" y opcionalmente "recognition".
        """
        err = self._check_available()
        if err:
            return err

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            return {"success": False, "output": None, "error": f"No se pudo abrir la cámara (index={self.camera_index})."}

        try:
            # Descartar algunos frames para que la cámara se estabilice
            for _ in range(5):
                cap.read()

            ret, frame = cap.read()
            if not ret or frame is None:
                return {"success": False, "output": None, "error": "No se pudo capturar frame de la cámara."}

            # Guardar frame temporal
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            cv2.imwrite(tmp.name, frame)
            tmp.close()

            output = {}

            # Análisis facial
            analysis = self.fm.analyze(path=tmp.name, actions=actions)
            output["analysis"] = analysis

            # Reconocimiento (opcional)
            if recognize:
                recognition = self.fm.recognize(path=tmp.name)
                output["recognition"] = recognition

            # Limpiar
            Path(tmp.name).unlink(missing_ok=True)

            success = analysis.get("success", False)
            return {"success": success, "output": output, "error": None}
        except Exception as e:
            logger.error(f"Error en capture_and_analyze: {e}")
            return {"success": False, "output": None, "error": str(e)}
        finally:
            cap.release()

    # ═══════════════════════════════════════════════════════════
    # Modo 2: Streaming continuo
    # ═══════════════════════════════════════════════════════════

    def start(self, on_result: Callable | None = None, analyze_interval: float = 3.0):
        """
        Inicia streaming de webcam con detección facial en tiempo real.

        Args:
            on_result: Callback que recibe el resultado del análisis cada intervalo.
            analyze_interval: Segundos entre análisis (default 3s para no saturar).
        """
        err = self._check_available()
        if err:
            logger.error(err["error"])
            return err

        if self._running:
            return {"success": False, "output": None, "error": "El stream ya está corriendo."}

        self._on_result = on_result
        self._running = True
        self._thread = threading.Thread(
            target=self._stream_loop,
            args=(analyze_interval,),
            daemon=True,
        )
        self._thread.start()
        logger.info("📹 Webcam stream iniciado")
        return {"success": True, "output": "Stream de webcam iniciado.", "error": None}

    def stop(self):
        """Detiene el streaming de webcam."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("📹 Webcam stream detenido")
        return {"success": True, "output": "Stream detenido.", "error": None}

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_result(self) -> dict | None:
        return self._last_result

    def _stream_loop(self, analyze_interval: float):
        """Loop principal de captura y análisis."""
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            logger.error(f"No se pudo abrir cámara (index={self.camera_index})")
            self._running = False
            return

        last_analysis_time = 0
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    break

                # Detección rápida con OpenCV (para overlay visual)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)

                # Dibujar rectángulos en rostros detectados
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    # Mostrar último resultado si lo hay
                    if self._last_result and self._last_result.get("success"):
                        analysis = self._last_result.get("output", {}).get("analysis", {})
                        if analysis.get("success") and analysis.get("output"):
                            face_info = analysis["output"][0]
                            label_parts = []
                            if "edad" in face_info:
                                label_parts.append(f"~{face_info['edad']}y")
                            if "emocion" in face_info:
                                label_parts.append(face_info["emocion"])
                            if "genero" in face_info:
                                label_parts.append(face_info["genero"])
                            label = " | ".join(label_parts)
                            cv2.putText(frame, label, (x, y - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                # Análisis profundo cada N segundos
                now = time.time()
                if now - last_analysis_time >= analyze_interval and len(faces) > 0:
                    last_analysis_time = now
                    # Guardar frame y analizar
                    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                    cv2.imwrite(tmp.name, frame)
                    tmp.close()

                    try:
                        result = {
                            "analysis": self.fm.analyze(path=tmp.name),
                            "recognition": self.fm.recognize(path=tmp.name),
                        }
                        self._last_result = {"success": True, "output": result, "error": None}

                        if self._on_result:
                            self._on_result(self._last_result)
                    except Exception as e:
                        logger.warning(f"Error en análisis de stream: {e}")
                    finally:
                        Path(tmp.name).unlink(missing_ok=True)

                # Mostrar ventana
                cv2.imshow("Raymundo - Facial Recognition", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        finally:
            cap.release()
            cv2.destroyAllWindows()
            self._running = False
            logger.info("📹 Stream loop terminado")
