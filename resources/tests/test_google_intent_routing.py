"""Focused tests for Google Workspace intent routing semantics."""

import sys
import unittest
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

AGENTES_DIR = BASE_DIR / "agentes"
if str(AGENTES_DIR) not in sys.path:
    sys.path.insert(0, str(AGENTES_DIR))

from agentes.orchestrator import _detectar_intencion_agente
from core.detectors import DetectorIntenciones


class GoogleIntentRoutingTests(unittest.TestCase):
    def test_detector_recognizes_excel_request_as_spreadsheet(self):
        detector = DetectorIntenciones()
        result = detector.detectar("Hazme un excel de ventas mensuales")

        self.assertEqual(result["intencion"], "hoja_calculo")
        self.assertGreaterEqual(result["confianza"], 0.25)

    def test_detector_prioritizes_spreadsheet_over_document_when_excel_is_present(self):
        detector = DetectorIntenciones()
        result = detector.detectar("Hazme un documento en excel con gastos mensuales")

        self.assertEqual(result["intencion"], "hoja_calculo")

    def test_orchestrator_routes_excel_requests_to_google_tracker(self):
        agent, skill, params = _detectar_intencion_agente("Hazme un excel de ventas")

        self.assertEqual(agent, "google")
        self.assertEqual(skill, "crear_tracker")
        self.assertIn("nombre", params)


if __name__ == "__main__":
    unittest.main(verbosity=2)