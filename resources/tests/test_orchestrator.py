import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

# Añadir el directorio raíz y la carpeta 'agentes' al PATH para resolver imports
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "agentes") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "agentes"))

from agentes.orchestrator import (
    _detectar_intencion_agente,
    _extraer_municipio,
    _extraer_url,
    http_app
)

class OrchestratorUnitTests(unittest.TestCase):
    def test_extraer_municipio(self):
        # Casos comunes
        self.assertEqual(_extraer_municipio("propuesta para Chalco"), "Chalco")
        self.assertEqual(_extraer_municipio("en Monterrey"), "Monterrey")
        self.assertEqual(_extraer_municipio("del municipio de Ecatepec"), "Ecatepec")
        # Casos sin match
        self.assertIsNone(_extraer_municipio("hola mundo como estas"))

    def test_extraer_url(self):
        self.assertEqual(_extraer_url("visita https://google.com ahora"), "https://google.com")
        self.assertEqual(_extraer_url("entra a www.test.com para mas info"), "https://www.test.com")
        self.assertIsNone(_extraer_url("solo un texto sin enlaces"))

    def test_detectar_intencion_propuestas(self):
        # ROI
        agente, skill, params = _detectar_intencion_agente("calcula el roi para Chalco")
        self.assertEqual(agente, "propuestas")
        self.assertEqual(skill, "calcular_roi")
        self.assertEqual(params["nombre"], "Chalco")

        # Email
        agente, skill, params = _detectar_intencion_agente("necesito un email para Ixtapaluca")
        self.assertEqual(agente, "propuestas")
        self.assertEqual(skill, "redactar_email")
        self.assertEqual(params["municipio"], "Ixtapaluca")

        # Pitch
        agente, skill, params = _detectar_intencion_agente("preparame un pitch para el municipio de Toluca")
        self.assertEqual(agente, "propuestas")
        self.assertEqual(skill, "generar_pitch")
        self.assertEqual(params["municipio"], "Toluca")

    def test_detectar_intencion_google(self):
        # Presentaciones
        agente, skill, params = _detectar_intencion_agente("crea una presentación sobre la IA")
        self.assertEqual(agente, "google")
        self.assertEqual(skill, "crear_presentacion")
        self.assertEqual(params["tema"], "crea una presentación sobre la IA")

        # Hojas de calculo / Tracker
        agente, skill, params = _detectar_intencion_agente("haz un excel de datos")
        self.assertEqual(agente, "google")
        self.assertEqual(skill, "crear_tracker")

        # Documentos genéricos
        agente, skill, params = _detectar_intencion_agente("redacta un informe ejecutivo")
        self.assertEqual(agente, "google")
        self.assertEqual(skill, "crear_documento")

    def test_detectar_intencion_research(self):
        # Competencia
        agente, skill, params = _detectar_intencion_agente("analiza a la competencia tesla")
        self.assertEqual(agente, "research")
        self.assertEqual(skill, "analizar_competencia")

        # Resumir URL
        agente, skill, params = _detectar_intencion_agente("resume esta página http://noticias.com")
        self.assertEqual(agente, "research")
        self.assertEqual(skill, "resumir_url")
        self.assertEqual(params["url"], "http://noticias.com")

        # General / Fallback
        agente, skill, params = _detectar_intencion_agente("dime qué es la computación cuántica")
        self.assertEqual(agente, "research")
        self.assertEqual(skill, "investigar")

class OrchestratorIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(http_app)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("agentes", data)

    @patch("agentes.orchestrator._llamar_agente_local", new_callable=AsyncMock)
    def test_procesar_endpoint_exitoso(self, mock_llamar_agente):
        mock_llamar_agente.return_value = {"resultado": {"mensaje": "Todo listo, aquí está la info", "url": "http://ejemplo.com"}}
        
        response = self.client.post("/procesar", json={
            "mensaje": "investiga algo",
            "parametros": {}
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["exito"])
        self.assertEqual(data["resultado"], "Todo listo, aquí está la info")
        self.assertEqual(data["url"], "http://ejemplo.com")
        self.assertEqual(data["agente_usado"], "research")
        
        # Verificar que se llamó correctamente al microservicio
        mock_llamar_agente.assert_called_once_with("research", "investigar", {"tema": "investiga algo"})

    @patch("agentes.orchestrator._llamar_agente_local", new_callable=AsyncMock)
    def test_procesar_endpoint_error_agente(self, mock_llamar_agente):
        # Simula un error devuelto por la llamada al agente local
        mock_llamar_agente.return_value = {"error": "Servicio inactivo"}
        
        response = self.client.post("/procesar", json={
            "mensaje": "crear presentacion"
        })
        
        # FastAPI debería transformar este "error" en un HTTPException 503
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Servicio inactivo")

if __name__ == "__main__":
    unittest.main(verbosity=2)
