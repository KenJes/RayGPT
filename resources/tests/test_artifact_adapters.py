"""Focused tests for artifact adapters."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.adapters import (
    CreateDocumentAdapter,
    CreateLocalArtifactAdapter,
    CreateNotebookAdapter,
    CreatePresentationAdapter,
    CreateSpreadsheetAdapter,
    MessageToolAdapter,
    OpenLocalArtifactAdapter,
)


class _DummyGoogleWorkspace:
    def crear_documento(self, titulo, contenido=""):
        return {
            "id": "doc-123",
            "url": "https://docs.google.com/document/d/doc-123/edit",
            "titulo": titulo,
        }


class _DummyGestorGoogle:
    def __init__(self):
        self.google = _DummyGoogleWorkspace()

    def crear_documento(self, tema, detalles):
        return {
            "texto": "✅ Documento creado\n\n🔗 **URL**: https://docs.google.com/document/d/doc-456/edit",
            "archivo": {
                "document_id": "doc-456",
                "tipo": "documento",
            },
        }

    def crear_hoja_calculo(self, tema, detalles):
        return {
            "texto": "✅ Hoja de cálculo creada\n\n🔗 **URL**: https://docs.google.com/spreadsheets/d/sheet-123/edit",
            "archivo": {
                "spreadsheet_id": "sheet-123",
                "tipo": "hoja_calculo",
            },
        }

    def crear_presentacion(self, tema, detalles):
        return {
            "texto": "✅ Presentación creada\n\n🔗 **URL**: https://docs.google.com/presentation/d/pres-123/edit",
            "archivo": {
                "presentation_id": "pres-123",
                "titulo": "Deck de prueba",
                "tipo": "presentacion",
            },
        }


class ArtifactAdapterTests(unittest.TestCase):
    def test_create_document_adapter_with_content_returns_google_artifact(self):
        adapter = CreateDocumentAdapter(_DummyGestorGoogle())
        result = adapter.execute(
            {
                "tema": "Contrato",
                "content": "# Hola",
            }
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(result["artifacts"][0]["tipo"], "documento")
        self.assertEqual(result["artifacts"][0]["google_id"], "doc-123")
        self.assertEqual(result["artifacts"][0]["export_format"], "docx")

    def test_message_tool_adapter_preserves_local_image_artifact(self):
        fd, temp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        Path(temp_path).write_text("fake-image", encoding="utf-8")
        self.addCleanup(lambda: Path(temp_path).unlink(missing_ok=True))

        adapter = MessageToolAdapter(
            "image_generate",
            "Generate image",
            lambda message: {"path": temp_path, "texto": "Imagen lista"},
        )
        result = adapter.execute({"message": "Genera una imagen de prueba"})

        self.assertTrue(result["success"], result)
        self.assertEqual(result["artifacts"][0]["path"], str(Path(temp_path).resolve()))
        self.assertEqual(result["artifacts"][0]["tipo"], "png")

    def test_create_notebook_writes_valid_ipynb(self):
        adapter = CreateNotebookAdapter()
        result = adapter.execute(
            {
                "title": "practica_etl_smoke",
                "filename": "practica_etl_smoke.ipynb",
                "language": "python",
                "cells": [
                    {"type": "markdown", "content": "# Práctica ETL\n\nObjetivo de la práctica."},
                    {"type": "code", "content": "import pandas as pd\ndf = pd.DataFrame({'a': [1, 2]})\ndf"},
                ],
            }
        )

        self.assertTrue(result["success"], result)
        notebook_path = Path(result["path"])
        self.addCleanup(lambda: notebook_path.unlink(missing_ok=True))
        self.assertEqual(len(result["artifacts"]), 1)
        self.assertEqual(result["artifacts"][0]["path"], str(notebook_path))

        notebook_data = json.loads(notebook_path.read_text(encoding="utf-8"))
        self.assertEqual(notebook_data["nbformat"], 4)
        self.assertEqual(notebook_data["metadata"]["kernelspec"]["name"], "python3")
        self.assertEqual(len(notebook_data["cells"]), 2)
        self.assertEqual(notebook_data["cells"][0]["cell_type"], "markdown")
        self.assertEqual(notebook_data["cells"][1]["cell_type"], "code")

    def test_create_local_artifact_writes_supported_file(self):
        adapter = CreateLocalArtifactAdapter()
        result = adapter.execute(
            {
                "filename": "landing_test.html",
                "content": "<html><body><h1>Hola</h1></body></html>",
            }
        )

        self.assertTrue(result["success"], result)
        artifact_path = Path(result["path"])
        self.addCleanup(lambda: artifact_path.unlink(missing_ok=True))

        self.assertEqual(artifact_path.suffix, ".html")
        self.assertIn("Hola", artifact_path.read_text(encoding="utf-8"))

    def test_create_local_artifact_supports_multiple_related_files(self):
        adapter = CreateLocalArtifactAdapter()
        result = adapter.execute(
            {
                "files": [
                    {"filename": "index.html", "content": "<link rel='stylesheet' href='styles.css'><script src='app.js'></script>"},
                    {"filename": "styles.css", "content": "body { background: #111; }"},
                    {"filename": "app.js", "content": "console.log('hola');"},
                ]
            }
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(len(result["artifacts"]), 3)
        artifact_paths = [Path(item["path"]) for item in result["artifacts"]]
        for artifact_path in artifact_paths:
            self.addCleanup(lambda p=artifact_path: p.unlink(missing_ok=True))
            self.assertTrue(artifact_path.exists())

        self.assertEqual(Path(result["path"]).name, "index.html")
        self.assertEqual([Path(path).name for path in result["paths"]], ["index.html", "styles.css", "app.js"])

    def test_create_local_artifact_rejects_unsupported_extension(self):
        adapter = CreateLocalArtifactAdapter()
        result = adapter.execute(
            {
                "filename": "payload.exe",
                "content": "not allowed",
            }
        )

        self.assertFalse(result["success"])
        self.assertIn("Extensión no soportada", result["error"])

    def test_create_local_artifact_supports_php_alias(self):
        adapter = CreateLocalArtifactAdapter()
        result = adapter.execute(
            {
                "title": "index",
                "artifact_type": "php",
                "content": "<?php echo 'hola'; ?>",
            }
        )

        self.assertTrue(result["success"], result)
        artifact_path = Path(result["path"])
        self.addCleanup(lambda: artifact_path.unlink(missing_ok=True))

        self.assertEqual(artifact_path.suffix, ".php")
        self.assertIn("echo 'hola'", artifact_path.read_text(encoding="utf-8"))

    def test_open_local_artifact_uses_default_app(self):
        create_adapter = CreateLocalArtifactAdapter()
        create_result = create_adapter.execute(
            {
                "filename": "open_me.txt",
                "content": "hola",
            }
        )
        self.assertTrue(create_result["success"], create_result)
        artifact_path = Path(create_result["path"])
        self.addCleanup(lambda: artifact_path.unlink(missing_ok=True))

        open_adapter = OpenLocalArtifactAdapter()
        with patch("core.adapters.os.startfile") as startfile_mock:
            result = open_adapter.execute({"path": str(artifact_path)})

        self.assertTrue(result["success"], result)
        startfile_mock.assert_called_once_with(str(artifact_path))
        self.assertEqual(result["artifacts"][0]["path"], str(artifact_path))

    def test_create_spreadsheet_adapter_returns_google_artifact(self):
        adapter = CreateSpreadsheetAdapter(_DummyGestorGoogle())
        result = adapter.execute({"tema": "Ventas Q4"})

        self.assertTrue(result["success"], result)
        self.assertEqual(result["artifacts"][0]["tipo"], "hoja_calculo")
        self.assertEqual(result["artifacts"][0]["google_id"], "sheet-123")
        self.assertEqual(result["artifacts"][0]["export_format"], "xlsx")
        self.assertEqual(result["artifacts"][0]["filename"], "Ventas_Q4_-_Datos.xlsx")

    def test_create_presentation_adapter_returns_google_artifact(self):
        adapter = CreatePresentationAdapter(_DummyGestorGoogle())
        result = adapter.execute({"tema": "Pitch deck"})

        self.assertTrue(result["success"], result)
        self.assertEqual(result["artifacts"][0]["tipo"], "presentacion")
        self.assertEqual(result["artifacts"][0]["google_id"], "pres-123")
        self.assertEqual(result["artifacts"][0]["title"], "Deck de prueba")
        self.assertEqual(result["artifacts"][0]["export_format"], "pptx")


if __name__ == "__main__":
    unittest.main(verbosity=2)