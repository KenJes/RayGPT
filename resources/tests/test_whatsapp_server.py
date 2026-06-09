import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Añadir el directorio raíz al PATH para resolver imports
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import whatsapp_server
from core.agent_runtime import AgentResponse

class WhatsAppServerUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Cliente de pruebas de Flask
        cls.client = whatsapp_server.app.test_client()

    def test_limpiar_formato_markdown(self):
        # Negritas
        self.assertEqual(
            whatsapp_server.limpiar_formato_markdown("Hola **mundo**"),
            "Hola mundo"
        )
        self.assertEqual(
            whatsapp_server.limpiar_formato_markdown("Hola __mundo__"),
            "Hola mundo"
        )
        
        # Cursivas
        self.assertEqual(
            whatsapp_server.limpiar_formato_markdown("Hola *mundo*"),
            "Hola mundo"
        )
        
        # Prefijos del modelo
        self.assertEqual(
            whatsapp_server.limpiar_formato_markdown("Raymundo: Hola que tal"),
            "Hola que tal"
        )
        self.assertEqual(
            whatsapp_server.limpiar_formato_markdown("rAI: Que pasa"),
            "Que pasa"
        )
        
        # Disclaimers
        texto_con_disclaimer = "Claro, aquí tienes la info.\nNota: Recuerda que soy una IA."
        self.assertEqual(
            whatsapp_server.limpiar_formato_markdown(texto_con_disclaimer),
            "Claro, aquí tienes la info."
        )

        # Bloques de código
        texto_codigo = "Aquí tienes:\n```python\nprint('hola')\n```"
        self.assertEqual(
            whatsapp_server.limpiar_formato_markdown(texto_codigo),
            "Aquí tienes:\npython\nprint('hola')"
        )

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["agent"], "rAImundoGPT")

    @patch("whatsapp_server.limpiar_historial")
    @patch("whatsapp_server.gestor.memory.clear_user_context")
    @patch("whatsapp_server.agent_memory.clear")
    def test_comando_reset(self, mock_agent_memory, mock_clear_context, mock_limpiar_historial):
        user_id = "test_reset_user"
        
        # Añadir al dict de personalidades para verificar que se limpie
        whatsapp_server.personalidades_por_usuario[user_id] = {"tono": "amigable"}
        
        response = self.client.post("/chat", json={
            "mensaje": "/reset",
            "user_id": user_id
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("borré todo el historial", data["respuesta"].lower() + data["respuesta"])
        
        # Verificar que se limpiaron las memorias
        mock_limpiar_historial.assert_called_once_with(user_id)
        mock_clear_context.assert_called_once_with(user_id)
        mock_agent_memory.assert_called_once()
        
        # Verificar que se quitó la personalidad
        self.assertNotIn(user_id, whatsapp_server.personalidades_por_usuario)

    @patch("whatsapp_server.agent_runtime.handle_text")
    def test_chat_endpoint_regular_message(self, mock_handle_text):
        # Simular una respuesta exitosa del AgentRuntime
        fake_response = AgentResponse(
            success=True,
            response="Esta es una respuesta simulada de Raymundo.",
            used_agent_loop=True,
            run_id="test-run-id",
            steps_taken=1,
            actions_log=[],
            artifacts=[]
        )
        mock_handle_text.return_value = fake_response
        
        response = self.client.post("/chat", json={
            "mensaje": "hola, ¿cómo estás?",
            "user_id": "test_user"
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # La respuesta ya debió pasar por limpiar_formato_markdown, pero nuestro mock 
        # devolvió texto limpio, así que debe ser igual.
        self.assertEqual(data["respuesta"], "Esta es una respuesta simulada de Raymundo.")
        self.assertEqual(data["user_id"], "test_user")
        
        # Verificar que se llamó a handle_text correctamente
        mock_handle_text.assert_called_once()
        request_obj = mock_handle_text.call_args.args[0]
        self.assertEqual(request_obj.text, "hola, ¿cómo estás?")
        self.assertEqual(request_obj.user_id, "test_user")

if __name__ == "__main__":
    unittest.main(verbosity=2)
