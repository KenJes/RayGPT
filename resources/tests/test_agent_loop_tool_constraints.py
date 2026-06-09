"""Tests for explicit-request constraints on file creation tools."""

import json
import sys
import unittest
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.adapters import AdapterRegistry, ToolAdapter
from core.agent_loop import AgentLoop


class _DummyLogger:
    def new_run_id(self):
        return "test-run"

    def log_plan(self, *args, **kwargs):
        return None

    def log_step(self, *args, **kwargs):
        return None

    def log_final(self, *args, **kwargs):
        return None


class _DummyMemory:
    def get_context_for_planning(self, goal):
        return ""

    def store_if_relevant(self, *args, **kwargs):
        return None


class _DummyAdapter(ToolAdapter):
    requires_approval = False

    def __init__(self, name: str, result: dict | None = None):
        self.name = name
        self.description = f"dummy adapter for {name}"
        self.calls = []
        self.result = result or {"success": True, "output": f"ok:{name}", "error": None}

    def execute(self, args: dict) -> dict:
        self.calls.append(args)
        return dict(self.result)


class _SequentialAiChat:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, messages, temperature=0.4, max_tokens=800):
        if self.calls >= len(self.responses):
            raise AssertionError("AI chat called more times than expected")
        response = self.responses[self.calls]
        self.calls += 1
        return response


def _agent_json(tool_name: str, args: dict | None = None, *, stop: bool = False, message: str = "", plan=None):
    return json.dumps(
        {
            "thought": "test",
            "plan": plan or ["step"],
            "next_action": {"tool": tool_name, "args": args or {}},
            "confidence": 0.9,
            "requires_approval": False,
            "message_to_user": message,
            "stop": stop,
        },
        ensure_ascii=False,
    )


class AgentLoopToolConstraintTests(unittest.TestCase):
    def _make_loop(self, adapter: ToolAdapter, responses: list[str]) -> AgentLoop:
        registry = AdapterRegistry()
        registry.register(adapter)
        return AgentLoop(
            registry=registry,
            ai_chat_fn=_SequentialAiChat(responses),
            logger=_DummyLogger(),
            memory=_DummyMemory(),
        )

    def test_rejects_notebook_creation_without_explicit_request(self):
        adapter = _DummyAdapter("create_notebook")
        loop = self._make_loop(
            adapter,
            [
                _agent_json(
                    "create_notebook",
                    {
                        "title": "etl",
                        "filename": "etl.ipynb",
                        "cells": [{"type": "markdown", "content": "# ETL"}],
                    },
                ),
                _agent_json("none", stop=True, message="Aquí tienes la práctica ETL en texto."),
            ],
        )

        result = loop.run(goal="Explícame ETL con pandas paso a paso")

        self.assertTrue(result["success"])
        self.assertEqual(result["response"], "Aquí tienes la práctica ETL en texto.")
        self.assertEqual(adapter.calls, [])
        self.assertEqual(result["actions_log"][0]["tool"], "create_notebook")
        self.assertFalse(result["actions_log"][0]["success"])
        self.assertIn("no pidió explícitamente", result["actions_log"][0]["error"])

    def test_allows_notebook_creation_with_explicit_ipynb_request(self):
        adapter = _DummyAdapter("create_notebook")
        loop = self._make_loop(
            adapter,
            [
                _agent_json(
                    "create_notebook",
                    {
                        "title": "etl",
                        "filename": "etl.ipynb",
                        "cells": [{"type": "markdown", "content": "# ETL"}],
                    },
                ),
                _agent_json("none", stop=True, message="Notebook creado correctamente."),
            ],
        )

        result = loop.run(goal="Haz una práctica de ETL en ipynb")

        self.assertTrue(result["success"])
        self.assertEqual(len(adapter.calls), 1)
        self.assertTrue(result["actions_log"][0]["success"])
        self.assertEqual(result["actions_log"][0]["tool"], "create_notebook")

    def test_allows_local_artifact_with_explicit_html_request(self):
        adapter = _DummyAdapter("create_local_artifact")
        loop = self._make_loop(
            adapter,
            [
                _agent_json(
                    "create_local_artifact",
                    {
                        "filename": "index.html",
                        "content": "<h1>Hola</h1>",
                    },
                ),
                _agent_json("none", stop=True, message="Archivo HTML creado correctamente."),
            ],
        )

        result = loop.run(goal="Hazme una landing page en html")

        self.assertTrue(result["success"])
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(result["actions_log"][0]["tool"], "create_local_artifact")
        self.assertTrue(result["actions_log"][0]["success"])

    def test_blocks_open_local_artifact_on_whatsapp_channel(self):
        adapter = _DummyAdapter("open_local_artifact")
        loop = self._make_loop(
            adapter,
            [
                _agent_json(
                    "open_local_artifact",
                    {"path": r"C:\\temp\\etl.ipynb"},
                ),
                _agent_json("none", stop=True, message="No puedo abrir archivos desde WhatsApp."),
            ],
        )

        result = loop.run(goal="Abre el notebook etl.ipynb", channel="whatsapp")

        self.assertTrue(result["success"])
        self.assertEqual(adapter.calls, [])
        self.assertFalse(result["actions_log"][0]["success"])
        self.assertIn("canales locales de escritorio", result["actions_log"][0]["error"])

    def test_propagates_artifacts_from_successful_tool(self):
        adapter = _DummyAdapter(
            "create_local_artifact",
            result={
                "success": True,
                "output": "Archivo creado correctamente en: C:/tmp/index.html",
                "error": None,
                "artifacts": [
                    {
                        "path": r"C:\\tmp\\index.html",
                        "filename": "index.html",
                        "tipo": "html",
                        "title": "index",
                    }
                ],
            },
        )
        loop = self._make_loop(
            adapter,
            [
                _agent_json(
                    "create_local_artifact",
                    {
                        "filename": "index.html",
                        "content": "<h1>Hola</h1>",
                    },
                ),
                _agent_json("none", stop=True, message="Archivo HTML creado correctamente."),
            ],
        )

        result = loop.run(goal="Hazme una landing page en html")

        self.assertEqual(len(result["artifacts"]), 1)
        self.assertEqual(result["artifacts"][0]["filename"], "index.html")
        self.assertEqual(result["actions_log"][0]["artifacts"][0]["tipo"], "html")

    def test_propagates_google_artifacts_without_local_path(self):
        adapter = _DummyAdapter(
            "create_spreadsheet",
            result={
                "success": True,
                "output": "✅ Hoja creada\n\n🔗 https://docs.google.com/spreadsheets/d/sheet-123/edit",
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
            },
        )
        loop = self._make_loop(
            adapter,
            [
                _agent_json(
                    "create_spreadsheet",
                    {
                        "tema": "Ventas",
                    },
                ),
                _agent_json("none", stop=True, message="Hoja creada correctamente."),
            ],
        )

        result = loop.run(goal="Hazme un excel de ventas")

        self.assertEqual(len(result["artifacts"]), 1)
        self.assertEqual(result["artifacts"][0]["google_id"], "sheet-123")
        self.assertEqual(result["actions_log"][0]["artifacts"][0]["export_format"], "xlsx")

    def test_returns_user_clarification_without_looping(self):
        progress_messages = []
        ai_chat = _SequentialAiChat(
            [
                _agent_json(
                    "none",
                    stop=False,
                    message="¿Qué imagen quieres que genere con ComfyUI?",
                ),
                _agent_json("none", stop=True, message="No debería ejecutarse un segundo paso."),
            ]
        )
        loop = AgentLoop(
            registry=AdapterRegistry(),
            ai_chat_fn=ai_chat,
            logger=_DummyLogger(),
            memory=_DummyMemory(),
            on_progress=progress_messages.append,
        )

        result = loop.run(goal="Genera con ComfyUI")

        self.assertTrue(result["success"])
        self.assertEqual(result["response"], "¿Qué imagen quieres que genere con ComfyUI?")
        self.assertEqual(result["steps_taken"], 1)
        self.assertEqual(ai_chat.calls, 1)
        self.assertEqual(progress_messages, [])
        self.assertEqual(result["actions_log"], [])

    def test_final_stop_message_is_not_sent_as_progress(self):
        progress_messages = []
        ai_chat = _SequentialAiChat(
            [
                _agent_json(
                    "none",
                    stop=True,
                    message="Respuesta final única.",
                )
            ]
        )
        loop = AgentLoop(
            registry=AdapterRegistry(),
            ai_chat_fn=ai_chat,
            logger=_DummyLogger(),
            memory=_DummyMemory(),
            on_progress=progress_messages.append,
        )

        result = loop.run(goal="Hola")

        self.assertTrue(result["success"])
        self.assertEqual(result["response"], "Respuesta final única.")
        self.assertEqual(progress_messages, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)