"""
deepface_stream.py — Cámara en tiempo real con DeepFace + comentarios de voz.

Usa la librería `deepface` (pip) para analizar en tiempo real:
  - Edad estimada
  - Género (Man/Woman)
  - Emoción dominante
  - Raza/etnia dominante

Arquitectura de dos procesos:
  - Proceso principal (Python 3.14): captura de cámara, overlay visual,
    comentarios de voz con el LLM.
  - Subprocess worker (Python 3.12): ejecuta DeepFace.analyze() porque
    TensorFlow no soporta Python 3.14. Se comunica via stdin/stdout JSON.

Muestra ventana de OpenCV con bounding boxes y datos superpuestos.
Un hilo secundario (DeepFaceCommentator) pide al LLM que comente
sobre los datos faciales cada N segundos, y lo reproduce por TTS.

Requiere: pip install opencv-python
Worker requiere (Python 3.12 venv): pip install deepface tf-keras

Uso:
    from core.deepface_stream import DeepFaceStream, DeepFaceCommentator
    stream = DeepFaceStream()
    stream.start()
    # ... integrar con voice assistant ...
    stream.stop()
"""

from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent

# ── Import condicional de OpenCV ──────────────────────────────
_CV2_AVAILABLE = False
try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ OpenCV no disponible: pip install opencv-python")

# ── Buscar Python 3.12 con DeepFace ──────────────────────────
_WORKER_SCRIPT = _ROOT / "core" / "deepface_worker.py"

# Posibles ubicaciones del venv con Python 3.12 + DeepFace
_PYTHON312_CANDIDATES = [
    Path(r"C:\Users\kenne\Visual Studio Code\Python\.venv312\Scripts\python.exe"),
    _ROOT / ".venv312" / "Scripts" / "python.exe",
    _ROOT.parent / ".venv312" / "Scripts" / "python.exe",
]

_PYTHON312_PATH: str | None = None
for _candidate in _PYTHON312_CANDIDATES:
    if _candidate.exists():
        _PYTHON312_PATH = str(_candidate)
        break

_DEEPFACE_AVAILABLE = _PYTHON312_PATH is not None and _WORKER_SCRIPT.exists()

if _DEEPFACE_AVAILABLE:
    logger.info(f"✅ DeepFace worker encontrado: Python 3.12 en {_PYTHON312_PATH}")
else:
    logger.warning(
        "⚠️ DeepFace worker no disponible. Se necesita Python 3.12 con deepface instalado. "
        "Buscado en: " + ", ".join(str(c) for c in _PYTHON312_CANDIDATES)
    )


# ═══════════════════════════════════════════════════════════════
# Traducciones para overlay en español
# ═══════════════════════════════════════════════════════════════
_GENDER_ES = {"Man": "Hombre", "Woman": "Mujer"}
_EMOTION_ES = {
    "angry": "enojado", "disgust": "disgustado", "fear": "miedo",
    "happy": "feliz", "sad": "triste", "surprise": "sorpresa",
    "neutral": "neutral",
}
_RACE_ES = {
    "asian": "asiático", "indian": "indio", "black": "negro",
    "white": "blanco", "middle eastern": "medio oriente",
    "latino hispanic": "latino",
}


def _translate(value: str, table: dict) -> str:
    return table.get(value.lower().strip(), value) if value else value


# ═══════════════════════════════════════════════════════════════
# DeepFaceWorkerProxy — comunicación con el subprocess worker
# ═══════════════════════════════════════════════════════════════

class _DeepFaceWorkerProxy:
    """
    Gestiona un subprocess persistente de deepface_worker.py
    para ejecutar DeepFace.analyze() en Python 3.12.
    """

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._ready = False
        self._start_attempts = 0
        self._max_restarts = 5

    @property
    def available(self) -> bool:
        return _DEEPFACE_AVAILABLE

    def _is_alive(self) -> bool:
        """Verifica si el proceso worker sigue vivo."""
        return (self._process is not None
                and self._process.poll() is None)

    def start(self) -> bool:
        """Inicia el proceso worker."""
        if not _DEEPFACE_AVAILABLE:
            return False

        # Limpiar proceso anterior si existe
        self._kill_if_dead()

        try:
            env = os.environ.copy()
            env["TF_CPP_MIN_LOG_LEVEL"] = "3"
            env["TF_ENABLE_ONEDNN_OPTS"] = "0"
            env["PYTHONUNBUFFERED"] = "1"

            self._process = subprocess.Popen(
                [_PYTHON312_PATH, "-u", str(_WORKER_SCRIPT)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
                cwd=str(_ROOT),
            )

            # Esperar señal "ready" del worker (timeout 60s para carga de modelos)
            import select
            # En Windows no hay select para pipes, usar thread con timeout
            ready_result = [None]
            def _read_ready():
                try:
                    ready_result[0] = self._process.stdout.readline()
                except Exception:
                    pass
            t = threading.Thread(target=_read_ready, daemon=True)
            t.start()
            t.join(timeout=120)  # 120s para primera carga de modelos TF

            ready_line = ready_result[0]
            if ready_line:
                data = json.loads(ready_line.strip())
                if data.get("ok") and data.get("status") == "ready":
                    self._ready = True
                    self._start_attempts = 0
                    logger.info("✅ DeepFace worker listo (Python 3.12)")
                    return True

            # Si no respondió, leer stderr para diagnosticar
            stderr_out = ""
            try:
                stderr_out = self._process.stderr.read(2000) if self._process.stderr else ""
            except Exception:
                pass
            logger.error(f"❌ Worker no respondió con señal ready. stderr: {stderr_out[:500]}")
            self.stop()
            return False

        except Exception as e:
            logger.error(f"❌ Error iniciando DeepFace worker: {e}")
            self.stop()
            return False

    def _kill_if_dead(self):
        """Limpia el proceso si ya murió."""
        if self._process and self._process.poll() is not None:
            self._process = None
            self._ready = False

    def _restart(self) -> bool:
        """Intenta reiniciar el worker si murió."""
        self._start_attempts += 1
        if self._start_attempts > self._max_restarts:
            logger.error(f"❌ Worker superó {self._max_restarts} reinicios. Desactivando.")
            return False
        logger.warning(f"🔄 Reiniciando DeepFace worker (intento {self._start_attempts})...")
        self.stop()
        return self.start()

    def stop(self):
        """Detiene el proceso worker."""
        if self._process:
            try:
                if self._is_alive():
                    self._process.stdin.write("QUIT\n")
                    self._process.stdin.flush()
                    self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
            self._ready = False
            logger.info("🛑 DeepFace worker detenido")

    def _send_command(self, cmd: dict) -> dict | None:
        """Envía un comando JSON al worker y retorna la respuesta (30 s timeout)."""
        if not self._ready and not self._process:
            return None
        if not self._is_alive():
            logger.warning("Worker murió, intentando reiniciar...")
            if not self._restart():
                return None
        with self._lock:
            try:
                payload = json.dumps(cmd) + "\n"
                self._process.stdin.write(payload)
                self._process.stdin.flush()

                response_result = [None]
                def _read_response():
                    try:
                        response_result[0] = self._process.stdout.readline()
                    except Exception:
                        pass
                t = threading.Thread(target=_read_response, daemon=True)
                t.start()
                t.join(timeout=30)

                line = response_result[0]
                if not line:
                    logger.warning("Worker no respondió (timeout o pipe roto)")
                    if not self._is_alive():
                        self._restart()
                    return None

                data = json.loads(line.strip())
                if data.get("ok"):
                    return data
                else:
                    logger.debug(f"Worker error: {data.get('error', 'desconocido')}")
                    return None

            except (OSError, BrokenPipeError) as e:
                logger.warning(f"Pipe roto con worker: {e}. Reiniciando...")
                self._restart()
                return None
            except Exception as e:
                logger.warning(f"Error comunicando con worker: {e}")
                return None

    def verify(self, path1: str, path2: str) -> dict | None:
        """Verifica si dos imágenes son la misma persona."""
        if not self._ready and not self._process:
            if not self.start():
                return None
        return self._send_command({"op": "verify", "path1": path1, "path2": path2})

    def extract_faces(self, path: str) -> dict | None:
        """Extrae y cuenta los rostros en una imagen."""
        if not self._ready and not self._process:
            if not self.start():
                return None
        return self._send_command({"op": "extract", "path": path})

    def find(self, path: str, db_path: str, max_results: int = 5) -> dict | None:
        """Busca coincidencias de un rostro en una carpeta de imágenes."""
        if not self._ready and not self._process:
            if not self.start():
                return None
        return self._send_command({
            "op": "find",
            "path": path,
            "db_path": db_path,
            "max_results": int(max_results),
        })

    def represent(self, path: str, max_values: int = 10) -> dict | None:
        """Genera embedding facial (vector) de una imagen."""
        if not self._ready and not self._process:
            if not self.start():
                return None
        return self._send_command({
            "op": "represent",
            "path": path,
            "max_values": int(max_values),
        })

    def face_swap(self, path1: str, path2: str, out_dir: str = "") -> dict | None:
        """Intercambia rostros entre dos imágenes y guarda los resultados."""
        if not self._ready and not self._process:
            if not self.start():
                return None
        return self._send_command({
            "op": "face_swap",
            "path1": path1,
            "path2": path2,
            "out_dir": out_dir,
        })


    def analyze(self, image_path: str) -> dict | None:
        """Envía una imagen al worker y retorna el resultado."""
        if not self._ready and not self._process:
            if not self.start():
                return None

        # Verificar que el worker sigue vivo
        if not self._is_alive():
            logger.warning("Worker murió, intentando reiniciar...")
            if not self._restart():
                return None

        with self._lock:
            try:
                self._process.stdin.write(image_path + "\n")
                self._process.stdin.flush()

                # Leer respuesta con timeout
                response_result = [None]
                def _read_response():
                    try:
                        response_result[0] = self._process.stdout.readline()
                    except Exception:
                        pass
                t = threading.Thread(target=_read_response, daemon=True)
                t.start()
                t.join(timeout=30)  # 30s timeout por análisis

                line = response_result[0]
                if not line:
                    logger.warning("Worker no respondió (timeout o pipe roto)")
                    if not self._is_alive():
                        self._restart()
                    return None

                data = json.loads(line.strip())
                if data.get("ok"):
                    return data
                else:
                    logger.debug(f"Worker error: {data.get('error', 'desconocido')}")
                    return None

            except (OSError, BrokenPipeError) as e:
                logger.warning(f"Pipe roto con worker: {e}. Reiniciando...")
                self._restart()
                return None
            except Exception as e:
                logger.warning(f"Error comunicando con worker: {e}")
                return None

    def analyze_b64(self, image_base64: str) -> dict | None:
        """Analiza una imagen en base64. Decodifica a temp file, llama analyze(), limpia."""
        if not image_base64:
            return None
        # Lazy-start: iniciar worker en la primera llamada si no está corriendo
        if not self._ready and not self._process:
            if not self.start():
                return None
        tmp_path = None
        try:
            raw = base64.b64decode(image_base64)
            fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="deepface_wa_")
            os.write(fd, raw)
            os.close(fd)
            return self.analyze(tmp_path)
        except Exception as e:
            logger.warning(f"Error en analyze_b64: {e}")
            return None
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


# ═══════════════════════════════════════════════════════════════
# DeepFaceStream — cámara + análisis en tiempo real
# ═══════════════════════════════════════════════════════════════

class DeepFaceStream:
    """
    Stream de webcam con análisis DeepFace en tiempo real.

    - Abre ventana OpenCV con feed de cámara (Python 3.14).
    - Cada `analyze_interval` segundos envía un frame al worker
      subprocess (Python 3.12) que ejecuta DeepFace.analyze().
    - Dibuja bounding boxes y texto superpuesto.
    - Almacena el último resultado en `last_result` (thread-safe).
    - Llama `on_result(data)` cada vez que hay nuevos datos.
    """

    def __init__(
        self,
        camera_index: int = 0,
        analyze_interval: float = 2.0,
        on_result: Callable[[dict], None] | None = None,
    ):
        self.camera_index = camera_index
        self.analyze_interval = analyze_interval
        self._on_result = on_result

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_result: dict | None = None
        self._worker = _DeepFaceWorkerProxy()

    @property
    def available(self) -> bool:
        return _CV2_AVAILABLE and self._worker.available

    @property
    def last_result(self) -> dict | None:
        with self._lock:
            return self._last_result

    @property
    def is_running(self) -> bool:
        return self._running

    # ─── Control ──────────────────────────────────────────────

    def start(self) -> dict:
        """Inicia el stream de webcam + DeepFace worker."""
        if not _CV2_AVAILABLE:
            return {"success": False, "error": "OpenCV no disponible: pip install opencv-python"}
        if not self._worker.available:
            return {"success": False, "error": (
                "DeepFace worker no disponible. Se requiere Python 3.12 con deepface instalado. "
                f"Buscado en: {', '.join(str(c) for c in _PYTHON312_CANDIDATES)}"
            )}
        if self._running:
            return {"success": False, "error": "El stream ya está corriendo."}

        # Iniciar worker subprocess
        if not self._worker.start():
            return {"success": False, "error": "No se pudo iniciar el worker de DeepFace."}

        self._running = True
        self._thread = threading.Thread(
            target=self._stream_loop,
            daemon=True,
            name="DeepFaceStream",
        )
        self._thread.start()
        logger.info("📹 DeepFace stream iniciado")
        return {"success": True, "error": None}

    def stop(self):
        """Detiene el stream y el worker."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        self._worker.stop()
        logger.info("📹 DeepFace stream detenido")

    # ─── Loop principal ───────────────────────────────────────

    def _stream_loop(self):
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            logger.error(f"No se pudo abrir cámara (index={self.camera_index})")
            self._running = False
            return

        last_analysis_time = 0.0
        overlay_faces: list[dict] = []
        # Directorio temporal para frames
        tmp_dir = tempfile.mkdtemp(prefix="raymundo_vision_")

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    break

                now = time.time()

                # ── Análisis DeepFace cada N segundos ─────────
                if now - last_analysis_time >= self.analyze_interval:
                    last_analysis_time = now
                    # Guardar frame a archivo temporal para el worker
                    tmp_path = os.path.join(tmp_dir, "frame.jpg")
                    cv2.imwrite(tmp_path, frame)

                    result = self._worker.analyze(tmp_path)
                    if result and result.get("faces"):
                        overlay_faces = result["faces"]

                        with self._lock:
                            self._last_result = {
                                "faces": overlay_faces,
                                "timestamp": now,
                                "num_faces": len(overlay_faces),
                            }

                        if self._on_result and overlay_faces:
                            try:
                                self._on_result(self._last_result)
                            except Exception as e:
                                logger.warning(f"Error en on_result callback: {e}")

                # ── Dibujar overlay ───────────────────────────
                for face in overlay_faces:
                    region = face.get("region", {})
                    x = region.get("x", 0)
                    y = region.get("y", 0)
                    w = region.get("w", 0)
                    h = region.get("h", 0)

                    if w > 0 and h > 0:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                        gender_es = _translate(face.get("gender", ""), _GENDER_ES)
                        emotion_es = _translate(face.get("emotion", ""), _EMOTION_ES)
                        race_es = _translate(face.get("race", ""), _RACE_ES)
                        age = face.get("age", "?")

                        lines = [
                            f"Edad: ~{age}",
                            f"Genero: {gender_es}",
                            f"Emocion: {emotion_es}",
                            f"Raza: {race_es}",
                        ]

                        for i, line in enumerate(lines):
                            ty = y - 10 - (len(lines) - 1 - i) * 22
                            if ty < 15:
                                ty = y + h + 20 + i * 22
                            cv2.putText(frame, line, (x + 1, ty + 1),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
                            cv2.putText(frame, line, (x, ty),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

                cv2.putText(frame, "Raymundo Vision | Q=salir", (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

                cv2.imshow("Raymundo - DeepFace Vision", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    break

        except Exception as e:
            logger.error(f"Error en DeepFace stream loop: {e}")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            self._running = False
            # Limpiar tmp
            try:
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass
            logger.info("📹 DeepFace stream loop terminado")


# ═══════════════════════════════════════════════════════════════
# DeepFaceCommentator — comentarios periódicos del LLM sobre
# los datos faciales detectados
# ═══════════════════════════════════════════════════════════════

class DeepFaceCommentator:
    """
    Genera comentarios de voz periódicos basados en los datos faciales.

    Cada `interval` segundos:
    1. Lee el último resultado del DeepFaceStream.
    2. Si los datos cambiaron significativamente, construye un prompt.
    3. Pide al LLM una reacción breve.
    4. Lo convierte a voz y lo reproduce.

    Respeta un speaking_lock compartido con el VoiceAssistant para
    evitar que ambos hablen al mismo tiempo.
    """

    # Prompt que se inyecta al LLM con los datos faciales
    _FACE_PROMPT_TEMPLATE = (
        "[CONTEXTO VISUAL - CÁMARA EN TIEMPO REAL]\n"
        "Estás viendo a {num_faces} persona(s) por la cámara web en este momento.\n"
        "Datos detectados:\n{face_details}\n\n"
        "Haz UN comentario breve y espontáneo sobre lo que ves. "
        "Máximo 2 oraciones cortas. Puedes comentar sobre la emoción, la edad, "
        "hacer un chiste o una observación ingeniosa. "
        "REGLAS IMPORTANTES:\n"
        "- Varía tu comentario cada vez: NO repitas la misma estructura ni las mismas palabras.\n"
        "- NO uses muletillas repetitivas (nmms, wey, no mames, etc) en cada frase.\n"
        "- Menciona algo ESPECÍFICO de los datos (ej: la emoción o la edad detectada).\n"
        "- Sé conciso: máximo 25 palabras total.\n"
        "- NO uses markdown, asteriscos ni formato especial.\n"
        "- Habla como si le hablaras a la persona directamente, con naturalidad."
    )

    def __init__(
        self,
        ai_chat_fn: Callable,
        tts_fn: Callable[[str], str | None],
        play_fn: Callable[[str], bool],
        stream: DeepFaceStream,
        speaking_lock: threading.Lock,
        is_busy_fn: Callable[[], bool],
        system_prompt: str = "",
        interval: float = 20.0,
    ):
        """
        Args:
            ai_chat_fn:    callable(messages, temperature, max_tokens) → str
            tts_fn:        callable(text) → path_audio | None
            play_fn:       callable(path) → bool
            stream:        DeepFaceStream instance
            speaking_lock: Lock compartido para evitar audio superpuesto
            is_busy_fn:    callable() → bool — True si el asistente está ocupado
            system_prompt: Personalidad del asistente (se usa como system message)
            interval:      Segundos entre comentarios (default 20)
        """
        self.ai_chat_fn = ai_chat_fn
        self.tts_fn = tts_fn
        self.play_fn = play_fn
        self.stream = stream
        self.speaking_lock = speaking_lock
        self.is_busy_fn = is_busy_fn
        self.system_prompt = system_prompt
        self.interval = interval

        self._running = False
        self._thread: threading.Thread | None = None
        self._last_commented_data: str = ""

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._comment_loop,
            daemon=True,
            name="DeepFaceCommentator",
        )
        self._thread.start()
        logger.info(f"💬 Comentarista DeepFace iniciado (cada {self.interval}s)")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("💬 Comentarista DeepFace detenido")

    def _build_face_details(self, faces: list[dict]) -> str:
        """Construye texto descriptivo de los rostros detectados."""
        lines = []
        for i, face in enumerate(faces, 1):
            gender_es = _translate(face.get("gender", ""), _GENDER_ES)
            emotion_es = _translate(face.get("emotion", ""), _EMOTION_ES)
            race_es = _translate(face.get("race", ""), _RACE_ES)
            age = face.get("age", "?")
            lines.append(
                f"  Persona {i}: Edad ~{age} años, "
                f"Género: {gender_es}, "
                f"Emoción: {emotion_es}, "
                f"Raza: {race_es}"
            )
        return "\n".join(lines)

    def _data_changed(self, faces: list[dict]) -> bool:
        """Verifica si los datos cambiaron significativamente desde el último comentario."""
        # Crear firma simple de los datos actuales
        signature = "|".join(
            f"{f.get('age', '?')}-{f.get('gender', '')}-{f.get('emotion', '')}-{f.get('race', '')}"
            for f in faces
        )
        if signature == self._last_commented_data:
            return False
        # Considerar cambio solo si la emoción o número de caras cambió
        old_parts = self._last_commented_data.split("|")
        new_parts = signature.split("|")
        if len(old_parts) != len(new_parts):
            return True
        for old, new in zip(old_parts, new_parts):
            old_fields = old.split("-")
            new_fields = new.split("-")
            if len(old_fields) != 4 or len(new_fields) != 4:
                return True
            # Cambio de emoción o género → nuevo comentario
            if old_fields[2] != new_fields[2]:  # emoción
                return True
            # Cambio de edad > 5 años → nuevo comentario
            try:
                if abs(int(old_fields[0]) - int(new_fields[0])) > 5:
                    return True
            except (ValueError, TypeError):
                return True
        return False

    def _comment_loop(self):
        """Loop que genera comentarios periódicos."""
        # Esperar unos segundos para que el stream se estabilice
        _wait = 0.0
        while self._running and _wait < 8.0:
            time.sleep(0.5)
            _wait += 0.5

        while self._running:
            try:
                # Dormir el intervalo en chunks (para poder parar rápido)
                for _ in range(int(self.interval * 2)):
                    if not self._running:
                        return
                    time.sleep(0.5)

                # No comentar si el asistente está ocupado
                if self.is_busy_fn():
                    continue

                # Leer último resultado
                result = self.stream.last_result
                if not result or not result.get("faces"):
                    continue

                faces = result["faces"]

                # Solo comentar si los datos cambiaron
                if not self._data_changed(faces):
                    continue

                # Construir prompt
                face_details = self._build_face_details(faces)
                user_prompt = self._FACE_PROMPT_TEMPLATE.format(
                    num_faces=len(faces),
                    face_details=face_details,
                )

                messages = []
                if self.system_prompt:
                    messages.append({"role": "system", "content": self.system_prompt})
                messages.append({"role": "user", "content": user_prompt})

                # Pedir comentario al LLM
                logger.info(f"💬 Generando comentario facial para {len(faces)} persona(s)...")
                response = self.ai_chat_fn(
                    messages, temperature=0.55, max_tokens=100,
                )

                if not response or len(response.strip()) < 5:
                    continue

                # Guardar firma actual
                self._last_commented_data = "|".join(
                    f"{f.get('age', '?')}-{f.get('gender', '')}-{f.get('emotion', '')}-{f.get('race', '')}"
                    for f in faces
                )

                # Hablar — respetando el lock
                if self.is_busy_fn():
                    continue

                with self.speaking_lock:
                    logger.info(f"🗣️ Comentario facial: '{response[:80]}...'")
                    audio_file = self.tts_fn(response.strip())
                    if audio_file:
                        self.play_fn(audio_file)

            except Exception as e:
                logger.error(f"Error en comment loop: {e}")
                time.sleep(2)

        logger.info("💬 Comment loop terminado")
