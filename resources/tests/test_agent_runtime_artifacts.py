"""Tests for AgentRuntime artifact propagation and channel forwarding."""

import sys
import unittest
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.agent_runtime import AgentRequest, AgentRuntime


class _DummyMemorySystem:
    def aprender_vocabulario(self, text, user_id=None):
        return None


class _DummyGestor:
    def __init__(self, google=None):
        self.memory = _DummyMemorySystem()
        self.google = google

    def _consultar_ia(self, prompt, temperature=0.3, max_tokens=400):
        return "summary"


class _DummyGoogleExporter:
    def exportar_hoja_calculo_xlsx(self, google_id, output_path):
        Path(output_path).write_text(f"sheet:{google_id}", encoding="utf-8")
        return output_path


class _DummyConversationDb:
    def build_context_messages(self, user_id, summarize_fn=None):
        return []

    def add_message(self, user_id, role, content):
        return None

    def clear_history(self, user_id):
        return None


class _DummyContextManager:
    def build_knowledge_context(self, query, user_id):
        return None


class _DummyAgentLoop:
    def __init__(self, result=None):
        self.last_kwargs = None
        self.result = result or {
            "success": True,
            "response": "Listo",
            "run_id": "runtime-artifacts-run",
            "steps_taken": 2,
            "actions_log": [
                {
                    "step": 1,
                    "tool": "create_local_artifact",
                    "success": True,
                    "output": "Archivo creado",
                    "error": None,
                    "artifacts": [
                        {
                            "path": r"C:\\tmp\\index.html",
                            "filename": "index.html",
                            "tipo": "html",
                            "title": "index",
                        }
                    ],
                }
            ],
            "artifacts": [
                {
                    "path": r"C:\\tmp\\index.html",
                    "filename": "index.html",
                    "tipo": "html",
                    "title": "index",
                }
            ],
        }

    def run(self, **kwargs):
        self.last_kwargs = kwargs
        return self.result


class AgentRuntimeArtifactTests(unittest.TestCase):
    def test_handle_text_propagates_artifacts_and_channel(self):
        loop = _DummyAgentLoop()
        runtime = AgentRuntime(
            gestor=_DummyGestor(),
            agent_loop=loop,
            conversation_db=_DummyConversationDb(),
            knowledge_base=None,
            context_manager=_DummyContextManager(),
        )

        result = runtime.handle_text(
            AgentRequest(
                text="Hazme una landing page en html",
                user_id="runtime-user",
                user_name="Kenneth",
                channel="desktop_gui",
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.run_id, "runtime-artifacts-run")
        self.assertEqual(result.artifacts[0]["filename"], "index.html")
        self.assertEqual(loop.last_kwargs["channel"], "desktop_gui")

    def test_handle_text_propagates_google_artifacts_without_local_path(self):
        loop = _DummyAgentLoop(
            result={
                "success": True,
                "response": "Listo",
                "run_id": "runtime-google-run",
                "steps_taken": 1,
                "actions_log": [
                    {
                        "step": 1,
                        "tool": "create_spreadsheet",
                        "success": True,
                        "output": "Hoja creada",
                        "error": None,
                        "artifacts": [
                            {
                                "provider": "google_workspace",
                                "kind": "hoja_calculo",
                                "tipo": "hoja_calculo",
                                "google_id": "sheet-123",
                                "google_url": "https://docs.google.com/spreadsheets/d/sheet-123/edit",
                                "title": "Ventas",
                                "filename": "Ventas.xlsx",
                                "export_format": "xlsx",
                            }
                        ],
                    }
                ],
                "artifacts": [
                    {
                        "provider": "google_workspace",
                        "kind": "hoja_calculo",
                        "tipo": "hoja_calculo",
                        "google_id": "sheet-123",
                        "google_url": "https://docs.google.com/spreadsheets/d/sheet-123/edit",
                        "title": "Ventas",
                        "filename": "Ventas.xlsx",
                        "export_format": "xlsx",
                    }
                ],
            }
        )
        runtime = AgentRuntime(
            gestor=_DummyGestor(),
            agent_loop=loop,
            conversation_db=_DummyConversationDb(),
            knowledge_base=None,
            context_manager=_DummyContextManager(),
        )

        result = runtime.handle_text(
            AgentRequest(
                text="Hazme un excel de ventas",
                user_id="runtime-user",
                channel="desktop_gui",
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.run_id, "runtime-google-run")
        self.assertEqual(result.artifacts[0]["google_id"], "sheet-123")
        self.assertEqual(result.artifacts[0]["export_format"], "xlsx")

    def test_handle_text_exports_google_artifact_to_local_file(self):
        loop = _DummyAgentLoop(
            result={
                "success": True,
                "response": "Listo",
                "run_id": "runtime-google-export-run",
                "steps_taken": 1,
                "actions_log": [
                    {
                        "step": 1,
                        "tool": "create_spreadsheet",
                        "success": True,
                        "output": "Hoja creada",
                        "error": None,
                        "artifacts": [
                            {
                                "provider": "google_workspace",
                                "kind": "hoja_calculo",
                                "tipo": "hoja_calculo",
                                "google_id": "sheet-export-123",
                                "google_url": "https://docs.google.com/spreadsheets/d/sheet-export-123/edit",
                                "title": "Ventas Export",
                                "filename": "Ventas Export.xlsx",
                                "export_format": "xlsx",
                            }
                        ],
                    }
                ],
                "artifacts": [
                    {
                        "provider": "google_workspace",
                        "kind": "hoja_calculo",
                        "tipo": "hoja_calculo",
                        "google_id": "sheet-export-123",
                        "google_url": "https://docs.google.com/spreadsheets/d/sheet-export-123/edit",
                        "title": "Ventas Export",
                        "filename": "Ventas Export.xlsx",
                        "export_format": "xlsx",
                    }
                ],
            }
        )
        runtime = AgentRuntime(
            gestor=_DummyGestor(google=_DummyGoogleExporter()),
            agent_loop=loop,
            conversation_db=_DummyConversationDb(),
            knowledge_base=None,
            context_manager=_DummyContextManager(),
        )

        result = runtime.handle_text(
            AgentRequest(
                text="Hazme un excel de ventas",
                user_id="runtime-user",
                channel="desktop_gui",
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.run_id, "runtime-google-export-run")
        exported_path = Path(result.artifacts[0]["path"])
        self.addCleanup(lambda: exported_path.unlink(missing_ok=True))
        self.assertTrue(exported_path.exists())
        self.assertEqual(exported_path.suffix, ".xlsx")
        self.assertEqual(result.artifacts[0]["filename"], exported_path.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
