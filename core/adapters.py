"""
adapters.py — Registro de Tool Adapters para la arquitectura agéntica.

Cada adapter envuelve una capacidad del agente con una interfaz estandarizada:
    execute(args) → {success, output, error}

Los adapters declaran si requieren aprobación humana antes de ejecutarse.
"""

import os
import re
import subprocess
import shlex
from pathlib import Path
from typing import Any

from core.config import OUTPUT_DIR


# ═══════════════════════════════════════════════════════════════
# Base adapter
# ═══════════════════════════════════════════════════════════════

class ToolAdapter:
    """Interfaz base para todos los tool adapters."""

    name: str = "base"
    description: str = ""
    requires_approval: bool = False

    def execute(self, args: dict) -> dict:
        """
        Ejecuta la herramienta.
        Returns: {"success": bool, "output": Any, "error": str | None}
        """
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════
# Adapters concretos
# ═══════════════════════════════════════════════════════════════

class SearchWebAdapter(ToolAdapter):
    """Busca y analiza una URL."""

    name = "search_web"
    description = "Scrape a URL and optionally answer a question about its content."
    requires_approval = False

    def __init__(self, scraper, ai_query_fn):
        self.scraper = scraper
        self.ai_query_fn = ai_query_fn  # fn(prompt, temp, max_tokens) → str

    def execute(self, args: dict) -> dict:
        url = args.get("url", "")
        pregunta = args.get("pregunta", "Resume el contenido de esta página.")
        if not url:
            return {"success": False, "output": None, "error": "Falta el argumento 'url'."}
        resultado = self.scraper.scrape(url)
        if not resultado["success"]:
            return {"success": False, "output": None, "error": resultado.get("error", "Scrape failed")}
        prompt = (
            f"Analiza esta página web:\nTítulo: {resultado['titulo']}\n"
            f"URL: {resultado['url']}\n\nContenido:\n{resultado['contenido'][:1500]}\n\n"
            f"Pregunta: {pregunta}\n\nResponde claro y conciso."
        )
        respuesta = self.ai_query_fn(prompt, 0.7, 500)
        return {"success": True, "output": respuesta, "error": None}


class CallApiAdapter(ToolAdapter):
    """Llama a la cadena de fallback de IA (Groq → GitHub → Ollama)."""

    name = "call_api"
    description = "Send a prompt to the AI fallback chain and get a response."
    requires_approval = False

    def __init__(self, ai_query_fn):
        self.ai_query_fn = ai_query_fn

    def execute(self, args: dict) -> dict:
        prompt = args.get("prompt", "")
        temperature = args.get("temperature", 0.7)
        max_tokens = args.get("max_tokens", 2000)
        if not prompt:
            return {"success": False, "output": None, "error": "Falta el argumento 'prompt'."}
        try:
            respuesta = self.ai_query_fn(prompt, temperature, max_tokens)
            return {"success": True, "output": respuesta, "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class ReadFileAdapter(ToolAdapter):
    """Lee el contenido de un archivo local."""

    name = "read_file"
    description = "Read the content of a local file."
    requires_approval = False

    def execute(self, args: dict) -> dict:
        file_path = args.get("path", "")
        if not file_path:
            return {"success": False, "output": None, "error": "Falta el argumento 'path'."}
        p = Path(file_path)
        if not p.exists():
            return {"success": False, "output": None, "error": f"Archivo no encontrado: {file_path}"}
        if not p.is_file():
            return {"success": False, "output": None, "error": f"No es un archivo: {file_path}"}
        try:
            contenido = p.read_text(encoding="utf-8", errors="replace")
            # Limitar tamaño para no saturar contexto
            if len(contenido) > 10000:
                contenido = contenido[:10000] + "\n... [truncado]"
            return {"success": True, "output": contenido, "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class WriteFileAdapter(ToolAdapter):
    """Escribe contenido a un archivo local. Requiere aprobación."""

    name = "write_file"
    description = "Write content to a local file. Requires approval for overwrites."
    requires_approval = True

    def execute(self, args: dict) -> dict:
        file_path = args.get("path", "")
        content = args.get("content", "")
        if not file_path:
            return {"success": False, "output": None, "error": "Falta el argumento 'path'."}
        # Seguridad: solo permitir escritura bajo OUTPUT_DIR
        p = Path(file_path).resolve()
        output_resolved = OUTPUT_DIR.resolve()
        if not str(p).startswith(str(output_resolved)):
            return {
                "success": False,
                "output": None,
                "error": f"Solo se permite escribir bajo {OUTPUT_DIR}",
            }
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {"success": True, "output": f"Archivo escrito: {p}", "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class RunShellAdapter(ToolAdapter):
    """Ejecuta un comando de shell. Requiere aprobación siempre."""

    name = "run_shell"
    description = "Execute a shell command. ALWAYS requires human approval."
    requires_approval = True

    # Comandos bloqueados por seguridad
    _BLOCKED_PATTERNS = [
        r"\brm\s+-rf\s+/",       # rm -rf /
        r"\bformat\b",           # format
        r"\bdel\s+/[sf]",        # del /s /f
        r"\bshutdown\b",         # shutdown
        r"\breg\s+delete\b",     # reg delete
    ]

    def execute(self, args: dict) -> dict:
        command = args.get("command", "")
        timeout = args.get("timeout", 30)
        if not command:
            return {"success": False, "output": None, "error": "Falta el argumento 'command'."}
        # Verificar patrones bloqueados
        for pattern in self._BLOCKED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return {
                    "success": False,
                    "output": None,
                    "error": f"Comando bloqueado por seguridad: {command}",
                }
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=min(timeout, 60),  # Max 60s
                cwd=str(OUTPUT_DIR),
            )
            output = result.stdout or ""
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            return {
                "success": result.returncode == 0,
                "output": output[:5000],
                "error": None if result.returncode == 0 else f"Exit code {result.returncode}",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": None, "error": f"Timeout ({timeout}s)"}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class CreatePresentationAdapter(ToolAdapter):
    """Crea una presentación en Google Slides."""

    name = "create_presentation"
    description = "Create a Google Slides presentation on a given topic."
    requires_approval = False

    def __init__(self, gestor):
        self.gestor = gestor

    def execute(self, args: dict) -> dict:
        tema = args.get("tema", "")
        detalles = args.get("detalles", {})
        if not tema:
            return {"success": False, "output": None, "error": "Falta el argumento 'tema'."}
        if not self.gestor.google:
            return {"success": False, "output": None, "error": "Google Slides no configurado."}
        try:
            res = self.gestor.crear_presentacion(tema, detalles)
            texto = res.get("texto", "")
            return {"success": "❌" not in texto, "output": texto, "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class CreateDocumentAdapter(ToolAdapter):
    """Crea un documento en Google Docs."""

    name = "create_document"
    description = "Create a Google Docs document on a given topic."
    requires_approval = False

    def __init__(self, gestor):
        self.gestor = gestor

    def execute(self, args: dict) -> dict:
        tema = args.get("tema", "")
        detalles = args.get("detalles", {})
        if not tema:
            return {"success": False, "output": None, "error": "Falta el argumento 'tema'."}
        if not self.gestor.google:
            return {"success": False, "output": None, "error": "Google Docs no configurado."}
        try:
            res = self.gestor.crear_documento(tema, detalles)
            texto = res.get("texto", "")
            return {"success": "❌" not in texto, "output": texto, "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class CreateSpreadsheetAdapter(ToolAdapter):
    """Crea una hoja de cálculo en Google Sheets."""

    name = "create_spreadsheet"
    description = "Create a Google Sheets spreadsheet."
    requires_approval = False

    def __init__(self, gestor):
        self.gestor = gestor

    def execute(self, args: dict) -> dict:
        tema = args.get("tema", "")
        detalles = args.get("detalles", {})
        if not tema:
            return {"success": False, "output": None, "error": "Falta el argumento 'tema'."}
        if not self.gestor.google:
            return {"success": False, "output": None, "error": "Google Sheets no configurado."}
        try:
            res = self.gestor.crear_hoja_calculo(tema, detalles)
            texto = res.get("texto", "")
            return {"success": "❌" not in texto, "output": texto, "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class AnalyzeImageAdapter(ToolAdapter):
    """Analiza una imagen con GPT-4o Vision (archivo local o base64)."""

    name = "analyze_image"
    description = "Analyze an image using GPT-4o Vision. Accepts 'path' (local file) or 'base64' (image data)."
    requires_approval = False

    def __init__(self, vision_processor):
        self.vision = vision_processor

    def execute(self, args: dict) -> dict:
        path = args.get("path", "")
        b64 = args.get("base64", "")
        prompt = args.get("prompt", "Describe esta imagen en detalle.")
        try:
            if b64:
                resultado = self.vision.analyze_image_base64(b64, prompt)
            elif path:
                if not Path(path).exists():
                    return {"success": False, "output": None, "error": f"Imagen no encontrada: {path}"}
                resultado = self.vision.analyze_image(path, prompt)
            else:
                return {"success": False, "output": None, "error": "Falta 'path' o 'base64'."}
            success = resultado and not str(resultado).startswith("❌")
            return {"success": success, "output": resultado, "error": None if success else resultado}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class AnalyzeDocumentAdapter(ToolAdapter):
    """Procesa un documento (txt, md, pdf)."""

    name = "analyze_document"
    description = "Process and extract content from a document (txt, md, pdf)."
    requires_approval = False

    def __init__(self, doc_processor):
        self.docs = doc_processor

    def execute(self, args: dict) -> dict:
        path = args.get("path", "")
        if not path:
            return {"success": False, "output": None, "error": "Falta el argumento 'path'."}
        if not Path(path).exists():
            return {"success": False, "output": None, "error": f"Documento no encontrado: {path}"}
        try:
            doc = self.docs.process_document(path)
            if doc["success"]:
                return {"success": True, "output": doc["content"][:5000], "error": None}
            return {"success": False, "output": None, "error": "No se pudo procesar el documento."}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# Evaluador de CV / RH
# ═══════════════════════════════════════════════════════════════

class EvaluateCVAdapter(ToolAdapter):
    """Evalúa un CV/currículum y recomienda puestos ideales."""

    name = "evaluate_cv"
    description = (
        "Evaluate a CV/resume text and recommend the best role for the candidate. "
        "Args: 'cv_text' (extracted text from CV), 'context' (optional company context/needs)."
    )
    requires_approval = False

    def __init__(self, ai_query_fn):
        self.ai_query_fn = ai_query_fn

    def execute(self, args: dict) -> dict:
        cv_text = args.get("cv_text", "")
        context = args.get("context", "")
        if not cv_text:
            return {"success": False, "output": None, "error": "Falta el argumento 'cv_text'."}

        prompt = f"""Eres un experto de Recursos Humanos de Axoloit, una startup mexicana de tecnología.

INSTRUCCIONES:
Analiza el siguiente CV/currículum y proporciona una evaluación profesional completa.

CV DEL CANDIDATO:
{cv_text[:3000]}

{f"CONTEXTO DE LA EMPRESA / NECESIDADES:{chr(10)}{context}" if context else ""}

RESPONDE CON:
1. **Datos del candidato**: Nombre, contacto, ubicación
2. **Resumen profesional**: Perfil general en 2-3 líneas
3. **Fortalezas clave**: Las 5 habilidades/experiencias más fuertes
4. **Áreas de oportunidad**: Qué le falta o debería desarrollar
5. **Puestos recomendados**: Los 3 mejores puestos donde este candidato rendiría más, ordenados por fit
6. **Nivel sugerido**: Junior / Mid / Senior / Lead
7. **Rango salarial estimado (MXN)**: Basado en mercado mexicano
8. **Veredicto final**: Contratar / Considerar / Pasar — con justificación

Sé directo, honesto y usa español mexicano natural. Si el CV tiene áreas débiles, dilo sin rodeos."""

        try:
            respuesta = self.ai_query_fn(prompt, 0.5, 2000)
            return {"success": True, "output": respuesta, "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════

class AdapterRegistry:
    """Registro central de tool adapters."""

    def __init__(self):
        self._adapters: dict[str, ToolAdapter] = {}

    def register(self, adapter: ToolAdapter):
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> ToolAdapter | None:
        return self._adapters.get(name)

    def list_tools(self) -> list[dict]:
        """Devuelve la lista de herramientas disponibles para el system prompt."""
        return [
            {
                "name": a.name,
                "description": a.description,
                "requires_approval": a.requires_approval,
            }
            for a in self._adapters.values()
        ]

    def list_names(self) -> list[str]:
        return list(self._adapters.keys())

    def requires_approval(self, name: str) -> bool:
        adapter = self._adapters.get(name)
        return adapter.requires_approval if adapter else True  # unknown → require approval


def build_registry(gestor) -> AdapterRegistry:
    """
    Construye el registry con todos los adapters disponibles,
    reutilizando los componentes que ya tiene GestorHerramientas.
    """
    registry = AdapterRegistry()

    registry.register(SearchWebAdapter(gestor.scraper, gestor._consultar_ia))
    registry.register(CallApiAdapter(gestor._consultar_ia))
    registry.register(ReadFileAdapter())
    registry.register(WriteFileAdapter())
    registry.register(RunShellAdapter())
    registry.register(CreatePresentationAdapter(gestor))
    registry.register(CreateDocumentAdapter(gestor))
    registry.register(CreateSpreadsheetAdapter(gestor))
    registry.register(AnalyzeImageAdapter(gestor.vision))
    registry.register(AnalyzeDocumentAdapter(gestor.docs))
    registry.register(EvaluateCVAdapter(gestor._consultar_ia))

    return registry
