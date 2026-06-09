"""
face_recognition.py — Módulo de reconocimiento facial para Raymundo.

Backend: OpenCV (YuNet + SFace) + ONNX Runtime
NO requiere TensorFlow ni DeepFace. Compatible con Python 3.14+.

Funciones:
    - Detección facial (YuNet ONNX)
    - Verificación de identidad (SFace ONNX)
    - Registro de rostros en base de datos local
    - Reconocimiento facial (SFace embeddings)
    - Análisis de emociones (FER+ ONNX)
    - Anti-spoofing (análisis de textura)
    - Extracción de rostros
    - Streaming de webcam (ver face_stream.py)

Los modelos ONNX se descargan automáticamente la primera vez.

Requiere: pip install opencv-python onnxruntime numpy

Uso:
    fm = FaceManager()
    result = fm.analyze("foto.jpg")
    result = fm.verify("foto1.jpg", "foto2.jpg")
    fm.register_face("Kenneth", "foto_kenneth.jpg")
    result = fm.recognize("desconocido.jpg")
"""

from __future__ import annotations

import base64
import logging
import os
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Import condicional de ONNX Runtime ────────────────────────
_ORT_AVAILABLE = False
try:
    import onnxruntime as ort

    _ORT_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ onnxruntime no disponible: pip install onnxruntime")

_DEFAULT_FACE_DB = Path(__file__).resolve().parent.parent / "data" / "face_db"
_DEFAULT_MODELS_DIR = Path(__file__).resolve().parent.parent / "data" / "face_models"

# URLs de modelos ONNX (fuentes estables de OpenCV Zoo y ONNX Model Zoo)
_MODEL_URLS = {
    "yunet": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "sface": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    "emotion": "https://github.com/onnx/models/raw/main/validated/vision/body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx",
}

_EMOTION_LABELS = [
    "neutral", "happiness", "surprise", "sadness",
    "anger", "disgust", "fear", "contempt",
]

# Umbrales por defecto de SFace (OpenCV)
_COSINE_THRESHOLD = 0.363
_L2_THRESHOLD = 1.128

# Configuración por defecto
_DEFAULT_CONFIG = {
    "distance_metric": "cosine",
    "anti_spoofing": True,
    "face_db_path": str(_DEFAULT_FACE_DB),
    "models_path": str(_DEFAULT_MODELS_DIR),
}


class FaceManager:
    """
    Gestor de reconocimiento facial basado en OpenCV + ONNX Runtime.

    Centraliza todas las operaciones faciales:
    - Detección (YuNet)
    - Reconocimiento/verificación (SFace)
    - Análisis de emociones (FER+ ONNX)
    - Anti-spoofing (análisis de textura, sin modelo externo)
    - Conversión base64 ↔ archivo temporal
    - Base de datos de rostros con embeddings cacheados
    """

    def __init__(self, config: dict | None = None, knowledge_base=None):
        self.config = {**_DEFAULT_CONFIG, **(config or {})}
        self.kb = knowledge_base
        self.face_db_path = Path(self.config["face_db_path"])
        self.face_db_path.mkdir(parents=True, exist_ok=True)
        self.models_dir = Path(self.config["models_path"])
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self._detector = None        # cv2.FaceDetectorYN
        self._recognizer = None      # cv2.FaceRecognizerSF
        self._emotion_session = None  # ort.InferenceSession
        self._available = False
        self._emotion_available = False

        self._init_models()

    @property
    def available(self) -> bool:
        return self._available

    # ═══════════════════════════════════════════════════════════
    # Inicialización de modelos
    # ═══════════════════════════════════════════════════════════

    def _download_model(self, name: str, url: str) -> str | None:
        """Descarga un modelo ONNX si no está en caché."""
        filename = url.rsplit("/", 1)[-1]
        path = self.models_dir / filename
        if path.exists():
            return str(path)
        logger.info(f"📥 Descargando modelo {name}: {filename}...")
        try:
            urllib.request.urlretrieve(url, str(path))
            logger.info(f"✅ Modelo {name} descargado: {path}")
            return str(path)
        except Exception as e:
            logger.error(f"❌ Error descargando modelo {name}: {e}")
            if path.exists():
                path.unlink()
            return None

    def _init_models(self):
        """Inicializa modelos de detección y reconocimiento."""
        try:
            # YuNet — detección facial
            yunet_path = self._download_model("yunet", _MODEL_URLS["yunet"])
            if not yunet_path:
                logger.warning("⚠️ No se pudo obtener YuNet. Detección no disponible.")
                return

            self._detector = cv2.FaceDetectorYN.create(yunet_path, "", (320, 320))

            # SFace — reconocimiento facial
            sface_path = self._download_model("sface", _MODEL_URLS["sface"])
            if not sface_path:
                logger.warning("⚠️ No se pudo obtener SFace. Reconocimiento no disponible.")
                return

            self._recognizer = cv2.FaceRecognizerSF.create(sface_path, "")

            self._available = True
            logger.info("✅ Modelos faciales cargados (YuNet + SFace)")

            # FER+ — emociones (opcional)
            if _ORT_AVAILABLE:
                emo_path = self._download_model("emotion", _MODEL_URLS["emotion"])
                if emo_path:
                    try:
                        self._emotion_session = ort.InferenceSession(emo_path)
                        self._emotion_available = True
                        logger.info("✅ Modelo de emociones cargado (FER+)")
                    except Exception as e:
                        logger.warning(f"⚠️ Error cargando modelo de emociones: {e}")

        except Exception as e:
            logger.error(f"❌ Error inicializando modelos faciales: {e}")
            self._available = False

    def _check_available(self) -> dict | None:
        """Retorna error dict si los modelos no están disponibles."""
        if not self._available:
            return {
                "success": False,
                "output": None,
                "error": (
                    "Modelos faciales no disponibles. "
                    "Verifica la conexión a Internet para la descarga automática, "
                    "o coloca los modelos ONNX en: " + str(self.models_dir)
                ),
            }
        return None

    # ═══════════════════════════════════════════════════════════
    # Utilidades de imagen
    # ═══════════════════════════════════════════════════════════

    def _resolve_image(self, path: str = "", b64: str = "") -> tuple[str, bool]:
        """
        Resuelve una imagen desde path o base64.

        Returns:
            (ruta_archivo, es_temporal) — si es_temporal=True, borrar después.
        """
        if path:
            return path, False
        if b64:
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            img_data = base64.b64decode(b64)
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            tmp.write(img_data)
            tmp.close()
            return tmp.name, True
        raise ValueError("Se requiere 'path' o 'base64'.")

    def _cleanup(self, path: str, is_temp: bool):
        """Limpia archivo temporal si aplica."""
        if is_temp:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _load_image(self, path: str) -> np.ndarray:
        """Carga imagen como array BGR de OpenCV."""
        img = cv2.imread(path)
        if img is None:
            raise ValueError(f"No se pudo leer la imagen: {path}")
        return img

    # ═══════════════════════════════════════════════════════════
    # Operaciones internas de detección y reconocimiento
    # ═══════════════════════════════════════════════════════════

    def _detect_faces(self, img: np.ndarray):
        """
        Detecta rostros con YuNet.

        Returns:
            np.ndarray Nx15 (bbox[4] + landmarks[10] + score[1]) o None.
        """
        h, w = img.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(img)
        return faces

    def _get_embedding(self, img: np.ndarray, face) -> np.ndarray:
        """Obtiene embedding 128-d con SFace."""
        aligned = self._recognizer.alignCrop(img, face)
        return self._recognizer.feature(aligned)

    def _predict_emotion(self, face_crop: np.ndarray) -> tuple[str | None, dict]:
        """Predice emoción con FER+ ONNX. Retorna (dominante, probabilidades)."""
        if not self._emotion_available or self._emotion_session is None:
            return None, {}

        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (64, 64))
        input_data = resized.astype(np.float32).reshape(1, 1, 64, 64)

        input_name = self._emotion_session.get_inputs()[0].name
        output = self._emotion_session.run(None, {input_name: input_data})

        logits = output[0][0]
        exp = np.exp(logits - np.max(logits))
        probs = exp / exp.sum()

        idx = int(np.argmax(probs))
        dominant = _EMOTION_LABELS[idx]
        emotions = {
            _EMOTION_LABELS[i]: round(float(probs[i]) * 100, 2)
            for i in range(len(_EMOTION_LABELS))
        }
        return dominant, emotions

    def _crop_face(self, img: np.ndarray, face) -> np.ndarray:
        """Recorta un rostro de la imagen usando las coordenadas de YuNet."""
        x, y, w, h = int(face[0]), int(face[1]), int(face[2]), int(face[3])
        y1 = max(0, y)
        y2 = min(img.shape[0], y + h)
        x1 = max(0, x)
        x2 = min(img.shape[1], x + w)
        return img[y1:y2, x1:x2]

    def _load_db_embeddings(self) -> list[tuple[str, np.ndarray]]:
        """Carga todos los embeddings registrados de la BD."""
        db: list[tuple[str, np.ndarray]] = []
        for person_dir in sorted(self.face_db_path.iterdir()):
            if not person_dir.is_dir():
                continue

            emb_files = list(person_dir.glob("emb_*.npy"))
            if emb_files:
                for emb_file in emb_files:
                    try:
                        emb = np.load(str(emb_file))
                        db.append((person_dir.name, emb))
                    except Exception:
                        continue
            else:
                # Sin embeddings cacheados: computar desde imágenes
                for img_file in list(person_dir.glob("*.jpg")) + list(person_dir.glob("*.png")):
                    try:
                        img = self._load_image(str(img_file))
                        faces = self._detect_faces(img)
                        if faces is not None and len(faces) > 0:
                            emb = self._get_embedding(img, faces[0])
                            ts = img_file.stem.replace("foto_", "")
                            np.save(str(person_dir / f"emb_{ts}.npy"), emb)
                            db.append((person_dir.name, emb))
                    except Exception:
                        continue
        return db

    # ═══════════════════════════════════════════════════════════
    # 1. Análisis facial — emoción + detección
    # ═══════════════════════════════════════════════════════════

    def analyze(
        self,
        path: str = "",
        b64: str = "",
        actions: list[str] | None = None,
    ) -> dict:
        """
        Analiza atributos faciales de una imagen.

        Args:
            path: Ruta a archivo de imagen.
            b64: Imagen codificada en base64.
            actions: Lista de análisis: "emotion".
                     (age/gender requieren modelos adicionales).

        Returns:
            {"success": bool, "output": list[dict], "error": str|None}
        """
        err = self._check_available()
        if err:
            return err

        if actions is None:
            actions = ["emotion"]

        img_path, is_temp = "", False
        try:
            img_path, is_temp = self._resolve_image(path, b64)
            img = self._load_image(img_path)
            faces = self._detect_faces(img)

            if faces is None or len(faces) == 0:
                return {"success": True, "output": [], "error": None}

            summary = []
            for face in faces:
                info: dict[str, Any] = {}
                x, y, w, h = int(face[0]), int(face[1]), int(face[2]), int(face[3])
                confidence = float(face[14])

                info["region"] = {"x": x, "y": y, "w": w, "h": h}
                info["confianza_deteccion"] = round(confidence, 4)

                face_crop = self._crop_face(img, face)
                if face_crop.size == 0:
                    continue

                if "emotion" in actions:
                    dominant, emotions = self._predict_emotion(face_crop)
                    if dominant:
                        info["emocion"] = dominant
                        info["emociones"] = emotions

                summary.append(info)

            return {"success": True, "output": summary, "error": None}
        except Exception as e:
            logger.error(f"Error en face_analyze: {e}")
            return {"success": False, "output": None, "error": str(e)}
        finally:
            self._cleanup(img_path, is_temp)

    # ═══════════════════════════════════════════════════════════
    # 2. Verificación — ¿son la misma persona?
    # ═══════════════════════════════════════════════════════════

    def verify(
        self,
        img1_path: str = "",
        img2_path: str = "",
        img1_base64: str = "",
        img2_base64: str = "",
    ) -> dict:
        """
        Verifica si dos imágenes pertenecen a la misma persona.

        Returns:
            {"success": bool, "output": dict, "error": str|None}
        """
        err = self._check_available()
        if err:
            return err

        path1, temp1 = "", False
        path2, temp2 = "", False
        try:
            path1, temp1 = self._resolve_image(img1_path, img1_base64)
            path2, temp2 = self._resolve_image(img2_path, img2_base64)

            img1 = self._load_image(path1)
            img2 = self._load_image(path2)

            faces1 = self._detect_faces(img1)
            faces2 = self._detect_faces(img2)

            if faces1 is None or len(faces1) == 0:
                return {"success": False, "output": None, "error": "No se detectó rostro en la primera imagen."}
            if faces2 is None or len(faces2) == 0:
                return {"success": False, "output": None, "error": "No se detectó rostro en la segunda imagen."}

            emb1 = self._get_embedding(img1, faces1[0])
            emb2 = self._get_embedding(img2, faces2[0])

            cosine = float(self._recognizer.match(emb1, emb2, cv2.FaceRecognizerSF_FR_COSINE))
            l2 = float(self._recognizer.match(emb1, emb2, cv2.FaceRecognizerSF_FR_NORM_L2))

            output = {
                "verificado": cosine >= _COSINE_THRESHOLD,
                "distancia": round(l2, 4),
                "umbral": _L2_THRESHOLD,
                "modelo": "SFace",
                "similitud": round(cosine, 4),
            }
            return {"success": True, "output": output, "error": None}
        except Exception as e:
            logger.error(f"Error en face_verify: {e}")
            return {"success": False, "output": None, "error": str(e)}
        finally:
            self._cleanup(path1, temp1)
            self._cleanup(path2, temp2)

    # ═══════════════════════════════════════════════════════════
    # 3. Registro de rostro en BD
    # ═══════════════════════════════════════════════════════════

    def register_face(
        self,
        name: str,
        path: str = "",
        b64: str = "",
    ) -> dict:
        """
        Registra un rostro en la base de datos local.
        Guarda la imagen + embedding en data/face_db/{name}/

        Args:
            name: Nombre de la persona.
            path: Ruta a la imagen.
            b64: Imagen en base64.

        Returns:
            {"success": bool, "output": str, "error": str|None}
        """
        err = self._check_available()
        if err:
            return err

        if not name or not name.strip():
            return {"success": False, "output": None, "error": "Se requiere un nombre para registrar el rostro."}

        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in name.strip())
        person_dir = self.face_db_path / safe_name
        person_dir.mkdir(parents=True, exist_ok=True)

        img_path, is_temp = "", False
        try:
            img_path, is_temp = self._resolve_image(path, b64)
            img = self._load_image(img_path)
            faces = self._detect_faces(img)

            if faces is None or len(faces) == 0:
                return {
                    "success": False,
                    "output": None,
                    "error": "No se detectó un rostro en la imagen. Intenta con otra foto.",
                }

            confidence = float(faces[0][14])
            if confidence < 0.5:
                return {
                    "success": False,
                    "output": None,
                    "error": "No se detectó un rostro claro en la imagen. Intenta con otra foto.",
                }

            ts = int(time.time())
            dest = person_dir / f"foto_{ts}.jpg"
            shutil.copy2(img_path, str(dest))

            # Calcular y guardar embedding
            emb = self._get_embedding(img, faces[0])
            np.save(str(person_dir / f"emb_{ts}.npy"), emb)

            # Registrar en KnowledgeBase si disponible
            if self.kb:
                try:
                    self.kb.store_person(
                        name=name.strip(),
                        notes=f"Rostro registrado en face_db ({dest.name})",
                    )
                    self.kb.add_fact(
                        person_name=name.strip(),
                        fact=f"Rostro registrado el {time.strftime('%Y-%m-%d %H:%M')}. Archivo: {dest.name}",
                        source="face_recognition",
                    )
                except Exception as ke:
                    logger.warning(f"⚠️ No se pudo registrar en KB: {ke}")

            count = len(list(person_dir.glob("*.jpg")))
            return {
                "success": True,
                "output": f"✅ Rostro de '{name}' registrado exitosamente ({count} foto(s) en BD).",
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error en face_register: {e}")
            return {"success": False, "output": None, "error": str(e)}
        finally:
            self._cleanup(img_path, is_temp)

    # ═══════════════════════════════════════════════════════════
    # 4. Reconocimiento — ¿quién es?
    # ═══════════════════════════════════════════════════════════

    def recognize(self, path: str = "", b64: str = "") -> dict:
        """
        Busca la identidad de una persona en la BD de rostros conocidos.

        Returns:
            {"success": bool, "output": dict, "error": str|None}
        """
        err = self._check_available()
        if err:
            return err

        subdirs = [
            d for d in self.face_db_path.iterdir()
            if d.is_dir() and (list(d.glob("*.jpg")) or list(d.glob("*.npy")))
        ]
        if not subdirs:
            return {
                "success": False,
                "output": None,
                "error": "No hay rostros registrados en la base de datos. Usa 'face_register' primero.",
            }

        img_path, is_temp = "", False
        try:
            img_path, is_temp = self._resolve_image(path, b64)
            img = self._load_image(img_path)
            faces = self._detect_faces(img)

            if faces is None or len(faces) == 0:
                return {"success": False, "output": None, "error": "No se detectó rostro en la imagen."}

            query_emb = self._get_embedding(img, faces[0])
            db = self._load_db_embeddings()

            matches = []
            for name, ref_emb in db:
                cosine = float(self._recognizer.match(
                    query_emb, ref_emb, cv2.FaceRecognizerSF_FR_COSINE
                ))
                l2 = float(self._recognizer.match(
                    query_emb, ref_emb, cv2.FaceRecognizerSF_FR_NORM_L2
                ))
                matches.append({
                    "identidad": name,
                    "distancia": round(l2, 4),
                    "similitud_coseno": round(cosine, 4),
                })

            # Filtrar por umbral y ordenar
            if self.config["distance_metric"] == "cosine":
                good = [m for m in matches if m["similitud_coseno"] >= _COSINE_THRESHOLD]
                good.sort(key=lambda x: -x["similitud_coseno"])
            else:
                good = [m for m in matches if m["distancia"] <= _L2_THRESHOLD]
                good.sort(key=lambda x: x["distancia"])

            if not good:
                return {
                    "success": True,
                    "output": {"identificado": False, "mensaje": "No se encontraron coincidencias en la base de datos."},
                    "error": None,
                }

            best = good[0]
            return {
                "success": True,
                "output": {
                    "identificado": True,
                    "persona": best["identidad"],
                    "distancia": best["distancia"],
                    "coincidencias": good[:5],
                },
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error en face_recognize: {e}")
            return {"success": False, "output": None, "error": str(e)}
        finally:
            self._cleanup(img_path, is_temp)

    # ═══════════════════════════════════════════════════════════
    # 5. Anti-spoofing — análisis de textura
    # ═══════════════════════════════════════════════════════════

    def check_spoofing(self, path: str = "", b64: str = "") -> dict:
        """
        Detecta si una imagen facial es real o falsificación.

        Usa análisis de textura (Laplacian variance) y distribución de color.
        No requiere modelo externo.

        Returns:
            {"success": bool, "output": list[dict], "error": str|None}
        """
        err = self._check_available()
        if err:
            return err

        img_path, is_temp = "", False
        try:
            img_path, is_temp = self._resolve_image(path, b64)
            img = self._load_image(img_path)
            faces = self._detect_faces(img)

            if faces is None or len(faces) == 0:
                return {"success": False, "output": None, "error": "No se detectaron rostros en la imagen."}

            results = []
            for face in faces:
                face_crop = self._crop_face(img, face)
                if face_crop.size == 0:
                    continue

                # Laplacian variance — rostros reales tienen más variación de textura
                gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
                laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

                # Análisis de saturación (fotos impresas/pantallas tienen distribución diferente)
                hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
                sat_mean = float(hsv[:, :, 1].mean())

                # Scoring heurístico
                score = 0.0
                if laplacian_var > 50:
                    score += 0.5
                if 20 < sat_mean < 200:
                    score += 0.3
                if laplacian_var > 100:
                    score += 0.2

                results.append({
                    "es_real": score >= 0.7,
                    "confianza_antispoof": round(score, 2),
                    "confianza_deteccion": round(float(face[14]), 4),
                    "detalles": {
                        "nitidez_laplacian": round(laplacian_var, 2),
                        "saturacion_media": round(sat_mean, 2),
                    },
                })

            if not results:
                return {"success": False, "output": None, "error": "No se detectaron rostros en la imagen."}

            return {"success": True, "output": results, "error": None}
        except Exception as e:
            logger.error(f"Error en anti-spoofing: {e}")
            return {"success": False, "output": None, "error": str(e)}
        finally:
            self._cleanup(img_path, is_temp)

    # ═══════════════════════════════════════════════════════════
    # 6. Extracción de rostros
    # ═══════════════════════════════════════════════════════════

    def extract_faces(self, path: str = "", b64: str = "") -> dict:
        """
        Detecta y extrae todos los rostros de una imagen.

        Returns:
            {"success": bool, "output": list[dict], "error": str|None}
        """
        err = self._check_available()
        if err:
            return err

        img_path, is_temp = "", False
        try:
            img_path, is_temp = self._resolve_image(path, b64)
            img = self._load_image(img_path)
            faces = self._detect_faces(img)

            output = []
            if faces is not None:
                for i, face in enumerate(faces):
                    output.append({
                        "rostro_num": i + 1,
                        "confianza": round(float(face[14]), 4),
                        "region": {
                            "x": int(face[0]), "y": int(face[1]),
                            "w": int(face[2]), "h": int(face[3]),
                        },
                    })

            return {"success": True, "output": output, "error": None}
        except Exception as e:
            logger.error(f"Error en extract_faces: {e}")
            return {"success": False, "output": None, "error": str(e)}
        finally:
            self._cleanup(img_path, is_temp)

    # ═══════════════════════════════════════════════════════════
    # 7. Listar personas registradas
    # ═══════════════════════════════════════════════════════════

    def list_registered(self) -> dict:
        """Lista todas las personas registradas en la BD de rostros."""
        people = []
        for d in sorted(self.face_db_path.iterdir()):
            if d.is_dir():
                fotos = list(d.glob("*.jpg")) + list(d.glob("*.png"))
                if fotos:
                    people.append({"nombre": d.name, "fotos": len(fotos)})
        return {
            "success": True,
            "output": people,
            "error": None,
        }

    # ═══════════════════════════════════════════════════════════
    # Resumen de texto para respuestas del agente
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def format_analysis(result: dict) -> str:
        """Formatea el resultado de analyze() como texto legible."""
        if not result.get("success"):
            return f"❌ {result.get('error', 'Error desconocido')}"

        output = result["output"]
        if not output:
            return "No se detectaron rostros en la imagen."

        lines = []
        for i, face in enumerate(output, 1):
            prefix = f"👤 Rostro {i}:" if len(output) > 1 else "👤"
            parts = []
            if "edad" in face:
                parts.append(f"~{face['edad']} años")
            if "genero" in face:
                gender_es = {"Man": "Hombre", "Woman": "Mujer"}.get(face["genero"], face["genero"])
                parts.append(gender_es)
            if "emocion" in face:
                emo_map = {
                    "happy": "feliz", "happiness": "feliz",
                    "sad": "triste", "sadness": "triste",
                    "angry": "enojado/a", "anger": "enojado/a",
                    "surprise": "sorprendido/a", "fear": "asustado/a",
                    "disgust": "disgustado/a", "neutral": "neutral",
                    "contempt": "desprecio",
                }
                parts.append(f"Emoción: {emo_map.get(face['emocion'], face['emocion'])}")
            if "confianza_deteccion" in face:
                parts.append(f"Confianza: {face['confianza_deteccion']:.1%}")
            if parts:
                lines.append(f"{prefix} {', '.join(parts)}")

        return "\n".join(lines) if lines else "Rostros detectados pero sin análisis disponible."

    @staticmethod
    def format_verify(result: dict) -> str:
        """Formatea el resultado de verify() como texto legible."""
        if not result.get("success"):
            return f"❌ {result.get('error', 'Error desconocido')}"

        o = result["output"]
        if o["verificado"]:
            return f"✅ **Misma persona** (similitud: {o['similitud']:.1%})"
        else:
            return f"❌ **Personas diferentes** (similitud: {o['similitud']:.1%})"

    @staticmethod
    def format_recognize(result: dict) -> str:
        """Formatea el resultado de recognize() como texto legible."""
        if not result.get("success"):
            return f"❌ {result.get('error', 'Error desconocido')}"

        o = result["output"]
        if not o.get("identificado"):
            return "🔍 No se encontraron coincidencias en la base de datos de rostros."

        lines = [f"🔍 **Identificado: {o['persona']}**"]
        if o.get("coincidencias"):
            for m in o["coincidencias"][:3]:
                dist = f" (distancia: {m['distancia']:.4f})" if m.get("distancia") is not None else ""
                lines.append(f"  • {m['identidad']}{dist}")
        return "\n".join(lines)
