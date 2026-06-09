"""
test_deepface.py — Tests para la integración de reconocimiento facial con Raymundo.

Backend: OpenCV (YuNet + SFace) + ONNX Runtime

Ejecutar:
    python test_deepface.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import cv2
import numpy as np

# Asegurar que el proyecto está en el path
sys.path.insert(0, str(Path(__file__).resolve().parent))


class TestFaceManagerInit(unittest.TestCase):
    """Tests de inicialización del FaceManager."""

    def test_import_face_recognition_module(self):
        """El módulo face_recognition se importa sin errores."""
        from core.face_recognition import FaceManager
        self.assertIsNotNone(FaceManager)

    def test_face_manager_creates_face_db_dir(self):
        """FaceManager crea el directorio face_db si no existe."""
        from core.face_recognition import FaceManager
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_face_db")
            models_path = os.path.join(tmpdir, "test_models")
            fm = FaceManager(config={"face_db_path": db_path, "models_path": models_path})
            self.assertTrue(Path(db_path).exists())

    def test_face_manager_creates_models_dir(self):
        """FaceManager crea el directorio de modelos si no existe."""
        from core.face_recognition import FaceManager
        with tempfile.TemporaryDirectory() as tmpdir:
            models_path = os.path.join(tmpdir, "test_models")
            fm = FaceManager(config={"models_path": models_path})
            self.assertTrue(Path(models_path).exists())

    def test_face_manager_default_config(self):
        """FaceManager usa configuración por defecto correcta."""
        from core.face_recognition import FaceManager
        fm = FaceManager()
        self.assertEqual(fm.config["distance_metric"], "cosine")
        self.assertTrue(fm.config["anti_spoofing"])

    def test_face_manager_custom_config(self):
        """FaceManager acepta configuración personalizada."""
        from core.face_recognition import FaceManager
        fm = FaceManager(config={"distance_metric": "euclidean_l2"})
        self.assertEqual(fm.config["distance_metric"], "euclidean_l2")

    def test_face_manager_available_property(self):
        """FaceManager reporta disponibilidad según modelos cargados."""
        from core.face_recognition import FaceManager
        fm = FaceManager()
        # available es True si los modelos se descargaron correctamente
        self.assertIsInstance(fm.available, bool)

    def test_face_manager_unavailable_returns_error(self):
        """Si los modelos no están, los métodos retornan error graceful."""
        from core.face_recognition import FaceManager
        fm = FaceManager()
        fm._available = False  # Forzar no disponible
        result = fm.analyze(path="fake.jpg")
        self.assertFalse(result["success"])
        self.assertIn("no disponible", result["error"].lower())

    def test_list_registered_empty(self):
        """list_registered retorna lista vacía en BD nueva."""
        from core.face_recognition import FaceManager
        with tempfile.TemporaryDirectory() as tmpdir:
            fm = FaceManager(config={"face_db_path": tmpdir})
            result = fm.list_registered()
            self.assertTrue(result["success"])
            self.assertEqual(result["output"], [])


class TestFaceManagerFormatters(unittest.TestCase):
    """Tests de los métodos de formato de texto."""

    def test_format_analysis_with_emotion(self):
        """format_analysis genera texto legible con emoción."""
        from core.face_recognition import FaceManager
        result = {
            "success": True,
            "output": [{"emocion": "happiness", "confianza_deteccion": 0.95}],
        }
        text = FaceManager.format_analysis(result)
        self.assertIn("feliz", text)
        self.assertIn("Confianza", text)

    def test_format_analysis_with_age_gender(self):
        """format_analysis genera texto legible con edad y género (extensibilidad)."""
        from core.face_recognition import FaceManager
        result = {
            "success": True,
            "output": [{"edad": 25, "genero": "Man", "emocion": "happiness"}],
        }
        text = FaceManager.format_analysis(result)
        self.assertIn("25 años", text)
        self.assertIn("Hombre", text)
        self.assertIn("feliz", text)

    def test_format_analysis_error(self):
        """format_analysis maneja errores."""
        from core.face_recognition import FaceManager
        result = {"success": False, "error": "No face detected"}
        text = FaceManager.format_analysis(result)
        self.assertIn("❌", text)

    def test_format_analysis_empty(self):
        """format_analysis maneja lista vacía de rostros."""
        from core.face_recognition import FaceManager
        result = {"success": True, "output": []}
        text = FaceManager.format_analysis(result)
        self.assertIn("No se detectaron", text)

    def test_format_verify_same_person(self):
        """format_verify para misma persona."""
        from core.face_recognition import FaceManager
        result = {
            "success": True,
            "output": {"verificado": True, "similitud": 0.95},
        }
        text = FaceManager.format_verify(result)
        self.assertIn("Misma persona", text)

    def test_format_verify_different(self):
        """format_verify para personas diferentes."""
        from core.face_recognition import FaceManager
        result = {
            "success": True,
            "output": {"verificado": False, "similitud": 0.3},
        }
        text = FaceManager.format_verify(result)
        self.assertIn("diferentes", text)

    def test_format_recognize_found(self):
        """format_recognize cuando encuentra coincidencia."""
        from core.face_recognition import FaceManager
        result = {
            "success": True,
            "output": {
                "identificado": True,
                "persona": "Kenneth",
                "distancia": 0.15,
                "coincidencias": [{"identidad": "Kenneth", "distancia": 0.15}],
            },
        }
        text = FaceManager.format_recognize(result)
        self.assertIn("Kenneth", text)
        self.assertIn("Identificado", text)

    def test_format_recognize_not_found(self):
        """format_recognize cuando no hay coincidencia."""
        from core.face_recognition import FaceManager
        result = {
            "success": True,
            "output": {"identificado": False},
        }
        text = FaceManager.format_recognize(result)
        self.assertIn("No se encontraron", text)


class TestAdaptersRegistration(unittest.TestCase):
    """Tests de registro de adapters en el registry."""

    def test_face_adapters_classes_exist(self):
        """Las 5 clases de adapters faciales existen."""
        from core.adapters import (
            FaceAnalyzeAdapter,
            FaceVerifyAdapter,
            FaceRegisterAdapter,
            FaceRecognizeAdapter,
            FaceAntiSpoofAdapter,
        )
        self.assertEqual(FaceAnalyzeAdapter.name, "face_analyze")
        self.assertEqual(FaceVerifyAdapter.name, "face_verify")
        self.assertEqual(FaceRegisterAdapter.name, "face_register")
        self.assertTrue(FaceRegisterAdapter.requires_approval)
        self.assertEqual(FaceRecognizeAdapter.name, "face_recognize")
        self.assertEqual(FaceAntiSpoofAdapter.name, "face_antispoofing")

    def test_build_registry_with_face_manager(self):
        """build_registry registra face adapters cuando hay face_manager disponible."""
        from core.adapters import build_registry, AdapterRegistry
        from core.face_recognition import FaceManager

        mock_gestor = MagicMock()
        mock_gestor._consultar_ia = MagicMock(return_value="test")
        mock_gestor.scraper = MagicMock()
        mock_gestor.vision = MagicMock()
        mock_gestor.docs = MagicMock()

        fm = FaceManager()
        if fm.available:
            registry = build_registry(mock_gestor, face_manager=fm)
            tools = registry.list_names()
            self.assertIn("face_analyze", tools)
            self.assertIn("face_verify", tools)
            self.assertIn("face_register", tools)
            self.assertIn("face_recognize", tools)
            self.assertIn("face_antispoofing", tools)

    def test_build_registry_without_face_manager(self):
        """build_registry no registra face adapters sin face_manager."""
        from core.adapters import build_registry

        mock_gestor = MagicMock()
        mock_gestor._consultar_ia = MagicMock(return_value="test")
        mock_gestor.scraper = MagicMock()
        mock_gestor.vision = MagicMock()
        mock_gestor.docs = MagicMock()

        registry = build_registry(mock_gestor)
        tools = registry.list_names()
        self.assertNotIn("face_analyze", tools)


class TestDetectorIntenciones(unittest.TestCase):
    """Tests de detección de intenciones faciales."""

    def test_detect_facial_intent(self):
        """Detecta intent reconocimiento_facial correctamente."""
        from core.detectors import DetectorIntenciones
        d = DetectorIntenciones()

        result = d.detectar("quién es esta persona, analiza su cara y rostro")
        self.assertEqual(result["intencion"], "reconocimiento_facial")

    def test_detect_age_intent(self):
        """Detecta pregunta de edad como intent facial."""
        from core.detectors import DetectorIntenciones
        d = DetectorIntenciones()

        result = d.detectar("qué edad tiene esta persona en la foto, analiza su rostro")
        self.assertEqual(result["intencion"], "reconocimiento_facial")

    def test_no_false_positive(self):
        """No detecta facial intent en mensajes normales."""
        from core.detectors import DetectorIntenciones
        d = DetectorIntenciones()

        result = d.detectar("cuéntame un chiste sobre gatos")
        self.assertNotEqual(result["intencion"], "reconocimiento_facial")


class TestFaceStream(unittest.TestCase):
    """Tests del módulo de streaming de webcam."""

    def test_import_face_stream(self):
        """El módulo face_stream se importa sin errores."""
        from core.face_stream import FaceStream
        self.assertIsNotNone(FaceStream)

    def test_face_stream_availability(self):
        """FaceStream reporta disponibilidad según FaceManager."""
        from core.face_stream import FaceStream
        from core.face_recognition import FaceManager
        fm = FaceManager()
        stream = FaceStream(fm)
        # available depende de cv2 Y FaceManager
        if not fm.available:
            self.assertFalse(stream.available)
        else:
            self.assertTrue(stream.available)


class TestConfigAgente(unittest.TestCase):
    """Tests de la configuración del agente."""

    def test_deepface_config_exists(self):
        """config_agente.json contiene sección deepface."""
        with open("config_agente.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        self.assertIn("deepface", config)
        self.assertEqual(config["deepface"]["distance_metric"], "cosine")
        self.assertTrue(config["deepface"]["anti_spoofing"])
        self.assertIn("models_path", config["deepface"])
        self.assertIn("face_db_path", config["deepface"])


class TestCoreOpenCVAPIs(unittest.TestCase):
    """Tests de disponibilidad de las APIs de OpenCV usadas."""

    def test_face_detector_yn_exists(self):
        """cv2.FaceDetectorYN está disponible."""
        self.assertTrue(hasattr(cv2, "FaceDetectorYN"))

    def test_face_recognizer_sf_exists(self):
        """cv2.FaceRecognizerSF está disponible."""
        self.assertTrue(hasattr(cv2, "FaceRecognizerSF"))

    def test_onnxruntime_available(self):
        """onnxruntime está disponible."""
        try:
            import onnxruntime as ort
            self.assertIsNotNone(ort.__version__)
        except ImportError:
            self.skipTest("onnxruntime no instalado")

    def test_numpy_available(self):
        """numpy está disponible."""
        self.assertIsNotNone(np.__version__)


class TestFaceManagerWithModels(unittest.TestCase):
    """Tests funcionales (requieren modelos descargados)."""

    @classmethod
    def setUpClass(cls):
        from core.face_recognition import FaceManager
        cls.fm = FaceManager()
        if not cls.fm.available:
            raise unittest.SkipTest("Modelos faciales no disponibles (sin conexión?)")

    def _create_test_face_image(self):
        """Crea una imagen de test con un 'rostro' sintético."""
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        # Óvalo de piel
        cv2.ellipse(img, (150, 150), (80, 100), 0, 0, 360, (200, 180, 160), -1)
        # Ojos
        cv2.circle(img, (120, 130), 10, (255, 255, 255), -1)
        cv2.circle(img, (180, 130), 10, (255, 255, 255), -1)
        cv2.circle(img, (120, 130), 5, (50, 50, 50), -1)
        cv2.circle(img, (180, 130), 5, (50, 50, 50), -1)
        # Boca
        cv2.ellipse(img, (150, 190), (30, 10), 0, 0, 180, (100, 100, 200), 2)
        # Nariz
        cv2.line(img, (150, 140), (150, 170), (180, 160, 140), 2)
        return img

    def test_extract_faces_no_crash(self):
        """extract_faces no crashea con una imagen válida."""
        img = self._create_test_face_image()
        tmp_path = os.path.join(tempfile.gettempdir(), "test_face_extract.jpg")
        cv2.imwrite(tmp_path, img)
        try:
            result = self.fm.extract_faces(path=tmp_path)
        finally:
            os.unlink(tmp_path)
        self.assertTrue(result["success"])
        self.assertIsInstance(result["output"], list)

    def test_analyze_no_crash(self):
        """analyze no crashea con una imagen válida."""
        img = self._create_test_face_image()
        tmp_path = os.path.join(tempfile.gettempdir(), "test_face_analyze.jpg")
        cv2.imwrite(tmp_path, img)
        try:
            result = self.fm.analyze(path=tmp_path)
        finally:
            os.unlink(tmp_path)
        self.assertTrue(result["success"])

    def test_check_spoofing_no_crash(self):
        """check_spoofing no crashea con una imagen válida."""
        img = self._create_test_face_image()
        tmp_path = os.path.join(tempfile.gettempdir(), "test_face_spoof.jpg")
        cv2.imwrite(tmp_path, img)
        try:
            result = self.fm.check_spoofing(path=tmp_path)
        finally:
            os.unlink(tmp_path)
        # Puede no detectar rostro en imagen sintética, pero no debe crashear
        self.assertIn("success", result)


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST SUITE: Face Recognition con Raymundo")
    print("  Backend: OpenCV (YuNet + SFace) + ONNX Runtime")
    print("=" * 60)

    # Verificar disponibilidad
    try:
        from core.face_recognition import FaceManager
        fm = FaceManager()
        print(f"  Modelos faciales:    {'✅ Cargados' if fm.available else '⚠️ No disponibles'}")
        print(f"  Emoción (FER+):      {'✅ Sí' if fm._emotion_available else '⚠️ No'}")
    except Exception as e:
        print(f"  ⚠️ Error: {e}")

    try:
        import onnxruntime as ort
        print(f"  ONNX Runtime:        ✅ {ort.__version__}")
    except ImportError:
        print("  ONNX Runtime:        ⚠️ No instalado")

    print(f"  OpenCV:              ✅ {cv2.__version__}")
    print(f"  FaceDetectorYN:      {'✅' if hasattr(cv2, 'FaceDetectorYN') else '❌'}")
    print(f"  FaceRecognizerSF:    {'✅' if hasattr(cv2, 'FaceRecognizerSF') else '❌'}")
    print("=" * 60)
    print()

    unittest.main(verbosity=2)
