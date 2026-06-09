"""
adapters.py — Registro de Tool Adapters para la arquitectura agéntica.

Cada adapter envuelve una capacidad del agente con una interfaz estandarizada:
    execute(args) → {success, output, error}

Los adapters declaran si requieren aprobación humana antes de ejecutarse.
"""

import json
import os
import re
import subprocess
import shlex
import sys
from pathlib import Path
from typing import Any, Callable

from core.config import OUTPUT_DIR


_NOTEBOOK_OUTPUT_DIR = OUTPUT_DIR / "notebooks"
_ARTIFACT_OUTPUT_DIR = OUTPUT_DIR / "files"
_ALLOWED_ARTIFACT_EXTENSIONS = {
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".md",
    ".php",
    ".py",
    ".sql",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
_ARTIFACT_EXTENSION_ALIASES = {
    "css": ".css",
    "csv": ".csv",
    "html": ".html",
    "javascript": ".js",
    "js": ".js",
    "json": ".json",
    "markdown": ".md",
    "md": ".md",
    "php": ".php",
    "py": ".py",
    "python": ".py",
    "sql": ".sql",
    "ts": ".ts",
    "typescript": ".ts",
    "txt": ".txt",
    "text": ".txt",
    "xml": ".xml",
    "yaml": ".yaml",
    "yml": ".yml",
}
_GOOGLE_EXPORT_FORMATS = {
    "documento": "docx",
    "hoja_calculo": "xlsx",
    "presentacion": "pptx",
}
_GOOGLE_ID_KEYS = {
    "documento": "document_id",
    "hoja_calculo": "spreadsheet_id",
    "presentacion": "presentation_id",
}


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


def _normalize_output(result: Any) -> tuple[bool, str]:
    if isinstance(result, dict):
        parts = []
        for key in ("texto", "resultado", "output_text", "output"):
            value = result.get(key)
            if value:
                parts.append(str(value))
        path = result.get("path")
        if path:
            parts.append(f"Archivo generado: {path}")
        if not parts:
            parts.append(json.dumps(result, ensure_ascii=False, default=str))
        output = "\n\n".join(parts)
    else:
        output = str(result or "")
    output = output.strip()
    success = bool(output) and not output.startswith("❌")
    return success, output


def _sanitize_filename(
    filename: str | None,
    *,
    default_stem: str,
    default_suffix: str,
) -> str:
    raw_name = Path(str(filename or "").strip()).name
    stem = Path(raw_name).stem if raw_name else default_stem
    suffix = Path(raw_name).suffix.lower() if raw_name else default_suffix

    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or default_stem
    safe_suffix = re.sub(r"[^A-Za-z0-9.]+", "", suffix).lower()
    if not safe_suffix:
        safe_suffix = default_suffix
    if not safe_suffix.startswith("."):
        safe_suffix = f".{safe_suffix}"
    return f"{safe_stem}{safe_suffix}"


def _sanitize_subdir(subdir: str | None) -> Path:
    if not subdir:
        return Path()
    safe_parts = []
    for part in Path(str(subdir)).parts:
        if part in ("", ".", ".."):
            continue
        safe_part = re.sub(r"[^A-Za-z0-9_-]+", "_", part).strip("._-")
        if safe_part:
            safe_parts.append(safe_part)
    return Path(*safe_parts) if safe_parts else Path()


def _ensure_output_path(base_dir: Path, filename: str) -> Path:
    candidate = (base_dir / filename).resolve()
    output_root = OUTPUT_DIR.resolve()
    if not str(candidate).startswith(str(output_root)):
        raise ValueError(f"Solo se permite escribir bajo {OUTPUT_DIR}")
    return candidate


def _unique_output_path(base_dir: Path, filename: str) -> Path:
    candidate = _ensure_output_path(base_dir, filename)
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 1000):
        alternative = candidate.with_name(f"{stem}_{index}{suffix}")
        if not alternative.exists():
            return alternative
    raise ValueError("No se pudo generar un nombre de archivo único.")


def _coerce_source_lines(content: Any) -> list[str]:
    if content is None:
        return []
    if isinstance(content, list):
        return [str(line) for line in content]
    text = str(content)
    if not text:
        return []
    lines = text.splitlines(keepends=True)
    return lines or [text]


def _build_notebook_cell(cell_type: str, content: Any) -> dict:
    normalized_type = "code" if str(cell_type).lower().strip() == "code" else "markdown"
    source = _coerce_source_lines(content)
    if normalized_type == "code":
        return {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": source,
        }
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source,
    }


def _coerce_notebook_cells(args: dict) -> list[dict]:
    raw_cells = args.get("cells")
    if isinstance(raw_cells, str):
        try:
            raw_cells = json.loads(raw_cells)
        except Exception:
            raw_cells = [{"type": "markdown", "content": raw_cells}]

    if not raw_cells:
        fallback_content = args.get("content") or args.get("texto") or ""
        return [_build_notebook_cell("markdown", fallback_content)] if str(fallback_content).strip() else []

    cells = []
    if not isinstance(raw_cells, list):
        raw_cells = [raw_cells]

    for raw_cell in raw_cells:
        if isinstance(raw_cell, dict):
            cell_type = (
                raw_cell.get("type")
                or raw_cell.get("cell_type")
                or ("code" if raw_cell.get("code") is not None else "markdown")
            )
            content = (
                raw_cell.get("content")
                if raw_cell.get("content") is not None
                else raw_cell.get("source")
            )
            if content is None:
                content = raw_cell.get("markdown")
            if content is None:
                content = raw_cell.get("code")
        else:
            cell_type = "markdown"
            content = raw_cell
        cells.append(_build_notebook_cell(cell_type, content))
    return cells


def _build_notebook_metadata(language: str | None) -> dict:
    normalized = str(language or "python").lower().strip()
    kernels = {
        "javascript": ("javascript", "JavaScript", "javascript"),
        "js": ("javascript", "JavaScript", "javascript"),
        "php": ("php", "PHP", "php"),
        "py": ("python3", "Python 3", "python"),
        "python": ("python3", "Python 3", "python"),
    }
    kernel_name, display_name, language_name = kernels.get(normalized, (normalized or "python3", normalized.title() or "Python 3", normalized or "python"))
    return {
        "kernelspec": {
            "display_name": display_name,
            "language": language_name,
            "name": kernel_name,
        },
        "language_info": {
            "name": language_name,
        },
    }


def _normalize_artifact_extension(filename: str | None, artifact_type: str | None) -> str:
    suffix = Path(str(filename or "")).suffix.lower()
    if suffix:
        return suffix
    normalized_type = str(artifact_type or "txt").strip().lower().lstrip(".")
    return _ARTIFACT_EXTENSION_ALIASES.get(normalized_type, f".{normalized_type}" if normalized_type else ".txt")


def _artifact_descriptor(path: Path, *, artifact_type: str, title: str | None = None) -> dict:
    return {
        "path": str(path),
        "filename": path.name,
        "tipo": artifact_type,
        "title": title or path.stem,
    }


def _local_artifacts_from_result(result: Any) -> list[dict]:
    if not isinstance(result, dict):
        return []

    raw_path = result.get("path") or result.get("imagen_path")
    if not raw_path:
        return []

    path = Path(str(raw_path)).resolve()
    if not path.exists() or not path.is_file():
        return []

    artifact_type = path.suffix.lstrip(".") or "file"
    title = result.get("title") or result.get("titulo") or path.stem
    return [_artifact_descriptor(path, artifact_type=artifact_type, title=title)]


def _extract_first_url(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"https?://\S+", str(text))
    if not match:
        return None
    return match.group(0).rstrip(").,;]")


def _google_workspace_artifact(
    *,
    artifact_type: str,
    google_id: str,
    google_url: str | None = None,
    title: str | None = None,
) -> dict:
    export_format = _GOOGLE_EXPORT_FORMATS.get(artifact_type)
    filename = None
    if export_format:
        filename = _sanitize_filename(
            title,
            default_stem=artifact_type,
            default_suffix=f".{export_format}",
        )
    return {
        "provider": "google_workspace",
        "kind": artifact_type,
        "tipo": artifact_type,
        "google_id": google_id,
        "google_url": google_url,
        "title": title or artifact_type,
        "filename": filename,
        "export_format": export_format,
    }


def _google_artifacts_from_result(result: dict, *, fallback_title: str | None = None) -> list[dict]:
    archivo_info = result.get("archivo")
    if not isinstance(archivo_info, dict):
        return []

    artifact_type = str(archivo_info.get("tipo") or "").strip().lower()
    id_key = _GOOGLE_ID_KEYS.get(artifact_type)
    google_id = archivo_info.get(id_key) if id_key else None
    if not artifact_type or not google_id:
        return []

    return [
        _google_workspace_artifact(
            artifact_type=artifact_type,
            google_id=str(google_id),
            google_url=archivo_info.get("url") or _extract_first_url(result.get("texto") or result.get("output")),
            title=archivo_info.get("titulo") or fallback_title,
        )
    ]


def _coerce_artifact_specs(args: dict) -> list[dict]:
    raw_files = args.get("files")
    if isinstance(raw_files, str):
        try:
            raw_files = json.loads(raw_files)
        except Exception:
            raw_files = None

    if not raw_files:
        return [dict(args)]

    if not isinstance(raw_files, list):
        raw_files = [raw_files]

    specs: list[dict] = []
    for raw_spec in raw_files:
        if isinstance(raw_spec, dict):
            spec = dict(raw_spec)
        else:
            spec = {"filename": raw_spec}
        for shared_key in ("artifact_type", "extension", "subdir"):
            if shared_key not in spec and args.get(shared_key) is not None:
                spec[shared_key] = args.get(shared_key)
        specs.append(spec)
    return specs


def _extract_artifact_content(spec: dict) -> str:
    content = spec.get("content")
    if content is None:
        for key in ("code", "html", "css", "javascript", "python", "php", "text"):
            if spec.get(key) is not None:
                content = spec.get(key)
                break
    if isinstance(content, (dict, list)):
        content = json.dumps(content, ensure_ascii=False, indent=2)
    return str(content or "")


def _coerce_open_paths(args: dict) -> list[Path]:
    raw_paths: list[Any] = []

    if args.get("path"):
        raw_paths.append(args.get("path"))

    paths_arg = args.get("paths")
    if isinstance(paths_arg, str):
        try:
            paths_arg = json.loads(paths_arg)
        except Exception:
            paths_arg = [paths_arg]
    if isinstance(paths_arg, list):
        raw_paths.extend(paths_arg)

    artifacts_arg = args.get("artifacts")
    if isinstance(artifacts_arg, str):
        try:
            artifacts_arg = json.loads(artifacts_arg)
        except Exception:
            artifacts_arg = []
    if isinstance(artifacts_arg, list):
        for artifact in artifacts_arg:
            if isinstance(artifact, dict) and artifact.get("path"):
                raw_paths.append(artifact["path"])

    resolved_paths: list[Path] = []
    seen_paths: set[str] = set()
    for raw_path in raw_paths:
        if not raw_path:
            continue
        resolved = Path(str(raw_path)).resolve()
        output_root = OUTPUT_DIR.resolve()
        if not str(resolved).startswith(str(output_root)):
            raise ValueError(f"Solo se permite abrir archivos bajo {OUTPUT_DIR}")
        if not resolved.exists() or not resolved.is_file():
            raise ValueError(f"Archivo no encontrado: {resolved}")
        key = str(resolved)
        if key not in seen_paths:
            resolved_paths.append(resolved)
            seen_paths.add(key)
    return resolved_paths


def _open_with_default_app(path: Path):
    if hasattr(os, "startfile"):
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    command = ["open", str(path)] if os.name == "posix" and sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.Popen(command)


class MessageToolAdapter(ToolAdapter):
    """Envuelve una capacidad basada en una instrucción en lenguaje natural."""

    def __init__(self, name: str, description: str, handler: Callable[[str], Any]):
        self.name = name
        self.description = description
        self.handler = handler

    def execute(self, args: dict) -> dict:
        message = str(
            args.get("message")
            or args.get("query")
            or args.get("prompt")
            or ""
        ).strip()
        if not message:
            return {
                "success": False,
                "output": None,
                "error": "Falta el argumento 'message'.",
            }
        try:
            result = self.handler(message)
            success, output = _normalize_output(result)
            return {
                "success": success,
                "output": output,
                "error": None if success else output,
                "artifacts": _local_artifacts_from_result(result),
            }
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


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


class CreateNotebookAdapter(ToolAdapter):
    """Crea notebooks Jupyter válidos bajo output/notebooks."""

    name = "create_notebook"
    description = (
        "Create a local Jupyter notebook (.ipynb) under output/notebooks. "
        "Args: optional 'title', optional 'filename', optional 'language', and 'cells' "
        "(list of {'type': 'markdown'|'code', 'content': str})."
    )
    requires_approval = False

    def execute(self, args: dict) -> dict:
        title = str(args.get("title") or args.get("tema") or "Notebook").strip() or "Notebook"
        filename = args.get("filename") or args.get("path") or f"{title}.ipynb"
        language = str(args.get("language") or "python").strip() or "python"
        cells = _coerce_notebook_cells(args)
        if not cells:
            return {
                "success": False,
                "output": None,
                "error": "Falta el contenido del notebook en 'cells' o 'content'.",
            }

        safe_name = _sanitize_filename(filename, default_stem="notebook", default_suffix=".ipynb")
        safe_name = str(Path(safe_name).with_suffix(".ipynb"))
        try:
            output_path = _unique_output_path(_NOTEBOOK_OUTPUT_DIR, safe_name)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            notebook = {
                "cells": cells,
                "metadata": _build_notebook_metadata(language),
                "nbformat": 4,
                "nbformat_minor": 5,
            }
            output_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding="utf-8")
            artifacts = [_artifact_descriptor(output_path, artifact_type="notebook", title=title)]
            return {
                "success": True,
                "output": f"Notebook creado correctamente en: {output_path}",
                "error": None,
                "path": str(output_path),
                "filename": output_path.name,
                "artifacts": artifacts,
            }
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class CreateLocalArtifactAdapter(ToolAdapter):
    """Crea archivos de texto locales bajo output/files."""

    name = "create_local_artifact"
    description = (
        "Create a local text artifact under output/files. Supported extensions: "
        ".html, .css, .js, .ts, .py, .php, .json, .md, .txt, .xml, .yaml, .yml, .sql, .csv. "
        "Args: single-file mode with 'filename' or multi-file mode with 'files' (list of file specs), "
        "plus optional 'artifact_type', optional 'subdir', and 'content'."
    )
    requires_approval = False

    def execute(self, args: dict) -> dict:
        try:
            artifact_specs = _coerce_artifact_specs(args)
            artifacts: list[dict] = []
            created_paths: list[Path] = []

            for spec in artifact_specs:
                filename = spec.get("filename") or spec.get("path") or spec.get("title") or "artifact"
                artifact_type = spec.get("artifact_type") or spec.get("extension")
                extension = _normalize_artifact_extension(filename, artifact_type)
                if extension not in _ALLOWED_ARTIFACT_EXTENSIONS:
                    return {
                        "success": False,
                        "output": None,
                        "error": f"Extensión no soportada: {extension}",
                    }

                content = _extract_artifact_content(spec)
                if not content.strip():
                    return {
                        "success": False,
                        "output": None,
                        "error": "Falta el contenido del archivo en 'content'.",
                    }

                safe_name = _sanitize_filename(filename, default_stem="artifact", default_suffix=extension)
                safe_name = str(Path(safe_name).with_suffix(extension))
                safe_subdir = _sanitize_subdir(spec.get("subdir"))
                target_dir = _ARTIFACT_OUTPUT_DIR / safe_subdir
                output_path = _unique_output_path(target_dir, safe_name)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(content, encoding="utf-8")
                created_paths.append(output_path)
                artifacts.append(
                    _artifact_descriptor(
                        output_path,
                        artifact_type=extension.lstrip("."),
                        title=spec.get("title") or Path(safe_name).stem,
                    )
                )

            first_path = created_paths[0]
            output_lines = ["Archivos creados correctamente:"]
            output_lines.extend(f"- {path}" for path in created_paths)
            return {
                "success": True,
                "output": "\n".join(output_lines),
                "error": None,
                "path": str(first_path),
                "filename": first_path.name,
                "paths": [str(path) for path in created_paths],
                "artifacts": artifacts,
            }
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class OpenLocalArtifactAdapter(ToolAdapter):
    """Abre uno o varios archivos locales creados por el agente."""

    name = "open_local_artifact"
    description = (
        "Open one or more local artifacts under output/. Accepts 'path', 'paths', or 'artifacts'. "
        "Use only on local desktop channels when the user explicitly asks to open the generated file."
    )
    requires_approval = False

    def execute(self, args: dict) -> dict:
        try:
            paths = _coerce_open_paths(args)
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}

        if not paths:
            return {
                "success": False,
                "output": None,
                "error": "Falta 'path', 'paths' o 'artifacts' para abrir el archivo.",
            }

        opened: list[Path] = []
        for path in paths:
            _open_with_default_app(path)
            opened.append(path)

        artifacts = [_artifact_descriptor(path, artifact_type=path.suffix.lstrip(".") or "file") for path in opened]
        output_lines = ["Archivos abiertos correctamente:"]
        output_lines.extend(f"- {path}" for path in opened)
        return {
            "success": True,
            "output": "\n".join(output_lines),
            "error": None,
            "path": str(opened[0]),
            "paths": [str(path) for path in opened],
            "artifacts": artifacts,
        }


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
    description = "Create a Google Slides presentation. Args: 'tema' (required) and optional 'detalles'."
    requires_approval = False

    def __init__(self, gestor):
        self.gestor = gestor

    def execute(self, args: dict) -> dict:
        tema = args.get("tema") or args.get("topic") or args.get("title") or ""
        detalles = args.get("detalles", {})
        if not tema:
            return {"success": False, "output": None, "error": "Falta el argumento 'tema'."}
        if not self.gestor.google:
            return {"success": False, "output": None, "error": "Google Slides no configurado."}
        try:
            res = self.gestor.crear_presentacion(tema, detalles)
            texto = res.get("texto", "")
            return {
                "success": "❌" not in texto,
                "output": texto,
                "error": None,
                "artifacts": _google_artifacts_from_result(res, fallback_title=f"{tema} - Presentacion"),
            }
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class CreateDocumentAdapter(ToolAdapter):
    """Crea un documento en Google Docs."""

    name = "create_document"
    description = "Create a Google Docs document. Args: 'tema' (required), optional 'detalles', optional 'content'."
    requires_approval = False

    def __init__(self, gestor):
        self.gestor = gestor

    def execute(self, args: dict) -> dict:
        tema = args.get("tema") or args.get("topic") or args.get("title") or ""
        detalles = args.get("detalles", {})
        contenido = args.get("content", "")
        if not tema:
            return {"success": False, "output": None, "error": "Falta el argumento 'tema'."}
        if not self.gestor.google:
            return {"success": False, "output": None, "error": "Google Docs no configurado."}
        try:
            if contenido:
                doc = self.gestor.google.crear_documento(f"{tema} - Documento", contenido)
                if doc:
                    return {
                        "success": True,
                        "output": f"✅ Documento creado\n\n🔗 **URL**: {doc['url']}",
                        "error": None,
                        "artifacts": [
                            _google_workspace_artifact(
                                artifact_type="documento",
                                google_id=str(doc["id"]),
                                google_url=doc.get("url"),
                                title=doc.get("titulo") or f"{tema} - Documento",
                            )
                        ],
                    }
                return {"success": False, "output": None, "error": "Error al crear documento"}
            res = self.gestor.crear_documento(tema, detalles)
            texto = res.get("texto", "")
            return {
                "success": "❌" not in texto,
                "output": texto,
                "error": None,
                "artifacts": _google_artifacts_from_result(res, fallback_title=f"{tema} - Documento"),
            }
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class CreateSpreadsheetAdapter(ToolAdapter):
    """Crea una hoja de cálculo en Google Sheets."""

    name = "create_spreadsheet"
    description = "Create a Google Sheets spreadsheet. Args: 'tema' (required) and optional 'detalles'."
    requires_approval = False

    def __init__(self, gestor):
        self.gestor = gestor

    def execute(self, args: dict) -> dict:
        tema = args.get("tema") or args.get("topic") or args.get("title") or ""
        detalles = args.get("detalles", {})
        if not tema:
            return {"success": False, "output": None, "error": "Falta el argumento 'tema'."}
        if not self.gestor.google:
            return {"success": False, "output": None, "error": "Google Sheets no configurado."}
        try:
            res = self.gestor.crear_hoja_calculo(tema, detalles)
            texto = res.get("texto", "")
            return {
                "success": "❌" not in texto,
                "output": texto,
                "error": None,
                "artifacts": _google_artifacts_from_result(res, fallback_title=f"{tema} - Datos"),
            }
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
# DeepFace — Reconocimiento y análisis facial
# ═══════════════════════════════════════════════════════════════

class FaceAnalyzeAdapter(ToolAdapter):
    """Analiza atributos faciales: edad, género, emoción, raza."""

    name = "face_analyze"
    description = (
        "Analyze facial attributes (age, gender, emotion, race) in an image. "
        "Args: 'path' (local file) or 'base64' (image data), "
        "'actions' (optional list: 'age','gender','emotion','race' — default: all)."
    )
    requires_approval = False

    def __init__(self, face_manager):
        self.fm = face_manager

    def execute(self, args: dict) -> dict:
        from core.face_recognition import FaceManager
        path = args.get("path", "")
        b64 = args.get("base64", "")
        actions = args.get("actions")
        if isinstance(actions, str):
            actions = [a.strip() for a in actions.split(",")]
        result = self.fm.analyze(path=path, b64=b64, actions=actions)
        if result["success"]:
            result["output_text"] = FaceManager.format_analysis(result)
        return result


class FaceVerifyAdapter(ToolAdapter):
    """Verifica si dos imágenes son la misma persona."""

    name = "face_verify"
    description = (
        "Verify whether two facial images belong to the same person. "
        "Args: 'img1_path'/'img1_base64' and 'img2_path'/'img2_base64'."
    )
    requires_approval = False

    def __init__(self, face_manager):
        self.fm = face_manager

    def execute(self, args: dict) -> dict:
        from core.face_recognition import FaceManager
        result = self.fm.verify(
            img1_path=args.get("img1_path", ""),
            img2_path=args.get("img2_path", ""),
            img1_base64=args.get("img1_base64", ""),
            img2_base64=args.get("img2_base64", ""),
        )
        if result["success"]:
            result["output_text"] = FaceManager.format_verify(result)
        return result


class FaceRegisterAdapter(ToolAdapter):
    """Registra un rostro en la base de datos de reconocimiento facial."""

    name = "face_register"
    description = (
        "Register a face in the facial recognition database. "
        "Args: 'name' (person's name, REQUIRED), 'path' (local file) or 'base64' (image data)."
    )
    requires_approval = True  # Dato biométrico — requiere aprobación

    def __init__(self, face_manager):
        self.fm = face_manager

    def execute(self, args: dict) -> dict:
        return self.fm.register_face(
            name=args.get("name", ""),
            path=args.get("path", ""),
            b64=args.get("base64", ""),
        )


class FaceRecognizeAdapter(ToolAdapter):
    """Identifica una persona buscando en la BD de rostros conocidos."""

    name = "face_recognize"
    description = (
        "Identify a person by searching the registered faces database. "
        "Args: 'path' (local file) or 'base64' (image data)."
    )
    requires_approval = False

    def __init__(self, face_manager):
        self.fm = face_manager

    def execute(self, args: dict) -> dict:
        from core.face_recognition import FaceManager
        result = self.fm.recognize(
            path=args.get("path", ""),
            b64=args.get("base64", ""),
        )
        if result["success"]:
            result["output_text"] = FaceManager.format_recognize(result)
        return result


class FaceAntiSpoofAdapter(ToolAdapter):
    """Detecta si una imagen facial es real o falsificada (anti-spoofing)."""

    name = "face_antispoofing"
    description = (
        "Detect whether a facial image is real or a spoof (photo of photo, screen, etc.). "
        "Args: 'path' (local file) or 'base64' (image data)."
    )
    requires_approval = False

    def __init__(self, face_manager):
        self.fm = face_manager

    def execute(self, args: dict) -> dict:
        result = self.fm.check_spoofing(
            path=args.get("path", ""),
            b64=args.get("base64", ""),
        )
        if result["success"]:
            lines = []
            for r in result["output"]:
                status = "✅ Real" if r["es_real"] else "⚠️ Posible falsificación"
                lines.append(f"{status} (confianza: {r['confianza_antispoof']:.2%})")
            result["output_text"] = "\n".join(lines)
        return result


# ═══════════════════════════════════════════════════════════════
# Evaluador de CV / RH
# ═══════════════════════════════════════════════════════════════

class EvaluateCVAdapter(ToolAdapter):
    """Evalúa un CV/currículum, lo guarda en la base de conocimiento y recomienda puestos."""

    name = "evaluate_cv"
    description = (
        "Evaluate a CV/resume text, STORE it in the knowledge database, and recommend the best role. "
        "Args: 'cv_text' (extracted text from CV), 'context' (optional company context/needs), "
        "'user_id' (who sent it)."
    )
    requires_approval = False

    def __init__(self, ai_query_fn, knowledge_base=None):
        self.ai_query_fn = ai_query_fn
        self.kb = knowledge_base

    def execute(self, args: dict) -> dict:
        cv_text = args.get("cv_text", "")
        context = args.get("context", "")
        user_id = args.get("user_id", "unknown")
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

            # Guardar CV y evaluación en la base de conocimiento
            if self.kb and respuesta:
                self._persist_cv(cv_text, respuesta, user_id)

            return {"success": True, "output": respuesta, "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}

    def _persist_cv(self, cv_text: str, evaluation: str, user_id: str):
        """Extrae nombre del candidato y guarda CV + persona en la KB."""
        try:
            # Intentar extraer nombre del CV o de la evaluación
            name = self._extract_name(cv_text, evaluation)
            doc_id = self.kb.store_document(
                user_id=user_id,
                doc_type="cv",
                content=cv_text,
                person_name=name,
                title=f"CV de {name}" if name else "CV sin nombre",
                evaluation=evaluation,
                source="whatsapp",
            )
            # Extraer datos estructurados y crear/actualizar persona
            if name:
                person_data = self._extract_person_data(evaluation)
                self.kb.store_person(name=name, added_by=user_id, **person_data)
                self.kb.add_fact(name, f"CV recibido y evaluado. Doc ID: {doc_id}", user_id, "cv_eval")
        except Exception:
            pass  # No fallar el flujo principal si la persistencia falla

    def _extract_name(self, cv_text: str, evaluation: str) -> str | None:
        """Intenta extraer el nombre del candidato del CV o evaluación."""
        # Buscar en la evaluación (más confiable porque el LLM ya lo parseó)
        patterns = [
            r'\*\*(?:Nombre|Datos del candidato)\*\*[:\s]*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})',
            r'(?:Nombre|Candidato)[:\s]*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})',
        ]
        for pat in patterns:
            m = re.search(pat, evaluation)
            if m:
                return m.group(1).strip()
        # Buscar en primeras líneas del CV
        for line in cv_text.split('\n')[:5]:
            line = line.strip()
            if line and len(line.split()) <= 5 and not any(c.isdigit() for c in line):
                words = line.split()
                if all(w[0].isupper() for w in words if w):
                    return line
        return None

    def _extract_person_data(self, evaluation: str) -> dict:
        """Extrae campos estructurados de la evaluación de texto."""
        data = {}
        # Nivel
        level_match = re.search(r'(?:Nivel|nivel)\s*(?:sugerido)?[:\s]*(Junior|Mid|Senior|Lead)', evaluation, re.I)
        if level_match:
            data["level"] = level_match.group(1).capitalize()
        # Veredicto
        verdict_match = re.search(r'(?:Veredicto|veredicto)[:\s]*(Contratar|Considerar|Pasar)', evaluation, re.I)
        if verdict_match:
            data["verdict"] = verdict_match.group(1).capitalize()
        # Rango salarial
        salary_match = re.search(r'(?:Rango salarial|salarial)[^:]*[:\s]*([^\n]{5,60})', evaluation, re.I)
        if salary_match:
            data["salary_range"] = salary_match.group(1).strip()
        # Habilidades/fortalezas → skills
        skills_section = re.search(r'(?:Fortalezas|habilidades)[^:]*:(.*?)(?:\n\d+\.|\n\*\*|$)', evaluation, re.I | re.S)
        if skills_section:
            skills_text = skills_section.group(1)
            skills = re.findall(r'[-•*]\s*(.+?)(?:\n|$)', skills_text)
            if skills:
                data["skills"] = [s.strip()[:100] for s in skills[:8]]
        # Puestos recomendados → role
        role_match = re.search(r'(?:Puestos? recomendados?)[^:]*[:\s]*[^a-zA-Z]*([^\n]{5,80})', evaluation, re.I)
        if role_match:
            data["role"] = role_match.group(1).strip()
        return data


class StoreCVAdapter(ToolAdapter):
    """Guarda un CV/documento en la base de conocimiento sin evaluarlo."""

    name = "store_document"
    description = (
        "Store a document/CV text in the knowledge database for future reference. "
        "Args: 'content' (text), 'doc_type' (cv/document/image), "
        "'person_name' (optional), 'title' (optional), 'user_id'."
    )
    requires_approval = False

    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def execute(self, args: dict) -> dict:
        content = args.get("content", "")
        if not content:
            return {"success": False, "output": None, "error": "Falta 'content'."}
        doc_id = self.kb.store_document(
            user_id=args.get("user_id", "unknown"),
            doc_type=args.get("doc_type", "document"),
            content=content,
            person_name=args.get("person_name"),
            title=args.get("title"),
        )
        return {"success": True, "output": f"Documento guardado (ID: {doc_id})", "error": None}


class StorePersonAdapter(ToolAdapter):
    """Crea o actualiza una persona en la base de conocimiento."""

    name = "store_person"
    description = (
        "Create or update a person in the knowledge database. "
        "Args: 'name' (required), 'role', 'skills' (list), 'experience', "
        "'education', 'contact', 'location', 'level', 'notes', 'user_id'."
    )
    requires_approval = False

    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def execute(self, args: dict) -> dict:
        name = args.get("name", "")
        if not name:
            return {"success": False, "output": None, "error": "Falta 'name'."}
        person_id = self.kb.store_person(
            name=name,
            role=args.get("role"),
            skills=args.get("skills"),
            experience=args.get("experience"),
            education=args.get("education"),
            contact=args.get("contact"),
            location=args.get("location"),
            level=args.get("level"),
            notes=args.get("notes"),
            added_by=args.get("user_id"),
        )
        return {"success": True, "output": f"Persona '{name}' guardada (ID: {person_id})", "error": None}


class AddFactAdapter(ToolAdapter):
    """Registra un hecho/dato sobre una persona."""

    name = "add_fact"
    description = (
        "Record a fact or piece of information about a person. "
        "Args: 'person_name' (required), 'fact' (the info to remember), 'user_id'."
    )
    requires_approval = False

    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def execute(self, args: dict) -> dict:
        person = args.get("person_name", "")
        fact = args.get("fact", "")
        if not person or not fact:
            return {"success": False, "output": None, "error": "Faltan 'person_name' y/o 'fact'."}
        self.kb.add_fact(person, fact, args.get("user_id"), "agent")
        return {"success": True, "output": f"Dato sobre '{person}' registrado.", "error": None}


class QueryKnowledgeAdapter(ToolAdapter):
    """Consulta la base de conocimiento: personas, CVs, documentos, hechos."""

    name = "query_knowledge"
    description = (
        "Search the knowledge database for people, CVs, documents, or facts. "
        "Args: 'query' (search text), 'person_name' (optional, for specific person lookup), "
        "'type' (optional: 'people'/'documents'/'facts'/'all', default 'all')."
    )
    requires_approval = False

    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def execute(self, args: dict) -> dict:
        query = args.get("query", "")
        person_name = args.get("person_name")
        search_type = args.get("type", "all")

        results = []

        if person_name:
            # Búsqueda específica de persona
            person = self.kb.get_person(person_name)
            if person:
                results.append(f"=== Persona: {person['name']} ===")
                if person.get("role"): results.append(f"Rol: {person['role']}")
                if person.get("level"): results.append(f"Nivel: {person['level']}")
                if person.get("skills"):
                    skills = person["skills"]
                    if isinstance(skills, list): skills = ", ".join(skills)
                    results.append(f"Skills: {skills}")
                if person.get("experience"): results.append(f"Experiencia: {person['experience']}")
                if person.get("education"): results.append(f"Educación: {person['education']}")
                if person.get("salary_range"): results.append(f"Rango salarial: {person['salary_range']}")
                if person.get("verdict"): results.append(f"Veredicto: {person['verdict']}")
                if person.get("notes"): results.append(f"Notas: {person['notes']}")
                # Hechos
                facts = self.kb.get_facts(person_name)
                if facts:
                    results.append(f"\nDatos sobre {person_name}:")
                    for f in facts[:10]:
                        results.append(f"  - {f['fact']}")
                # Documentos
                docs = self.kb.get_documents_by_person(person_name)
                if docs:
                    results.append(f"\nDocumentos de {person_name}:")
                    for d in docs[:5]:
                        results.append(f"  - [{d['doc_type']}] {d.get('title', 'Sin título')} ({d['content'][:200]}...)")
            else:
                results.append(f"No se encontró información sobre '{person_name}' en la base de datos.")

        if query:
            if search_type in ("people", "all"):
                people = self.kb.search_people(query, limit=10)
                if people:
                    results.append(f"\n=== Personas que coinciden con '{query}' ===")
                    for p in people:
                        skills = p.get("skills", "")
                        if isinstance(skills, list): skills = ", ".join(skills)
                        results.append(f"  • {p['name']} — {p.get('role', 'sin rol')} | {p.get('level', '?')} | Skills: {skills}")

            if search_type in ("documents", "all"):
                docs = self.kb.search_documents(query, limit=5)
                if docs:
                    results.append(f"\n=== Documentos que coinciden con '{query}' ===")
                    for d in docs:
                        results.append(f"  • [{d['doc_type']}] {d.get('person_name', '?')} — {d['content'][:200]}...")

            if search_type in ("facts", "all"):
                facts = self.kb.search_facts(query, limit=10)
                if facts:
                    results.append(f"\n=== Datos relacionados con '{query}' ===")
                    for f in facts:
                        results.append(f"  • {f['person_name']}: {f['fact']}")

        if not results:
            return {"success": True, "output": "No se encontró información relevante en la base de datos.", "error": None}

        return {"success": True, "output": "\n".join(results), "error": None}


# ═══════════════════════════════════════════════════════════════
# Spotify Adapters
# ═══════════════════════════════════════════════════════════════

class SpotifyPlayAdapter(ToolAdapter):
    """Reproduce música en Spotify."""

    name = "spotify_play"
    description = (
        "Play music on Spotify. If 'query' is provided, searches and plays that song/artist/album/playlist. "
        "If no 'query', resumes current playback. "
        "Args: 'query' (optional — song name, artist, album, or playlist to play)."
    )
    requires_approval = False

    def __init__(self, spotify_client):
        self.spotify = spotify_client

    def execute(self, args: dict) -> dict:
        if not self.spotify.is_authenticated:
            return {"success": False, "output": None, "error": "Spotify no está conectado. Dile al usuario que visite /spotify/auth"}
        try:
            query = args.get("query")
            result = self.spotify.play(query)
            return {"success": True, "output": result, "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class SpotifyPauseAdapter(ToolAdapter):
    """Pausa la reproducción de Spotify."""

    name = "spotify_pause"
    description = "Pause Spotify playback. No args needed."
    requires_approval = False

    def __init__(self, spotify_client):
        self.spotify = spotify_client

    def execute(self, args: dict) -> dict:
        if not self.spotify.is_authenticated:
            return {"success": False, "output": None, "error": "Spotify no está conectado."}
        try:
            return {"success": True, "output": self.spotify.pause(), "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class SpotifyNextAdapter(ToolAdapter):
    """Salta a la siguiente canción."""

    name = "spotify_next"
    description = "Skip to the next track on Spotify. No args needed."
    requires_approval = False

    def __init__(self, spotify_client):
        self.spotify = spotify_client

    def execute(self, args: dict) -> dict:
        if not self.spotify.is_authenticated:
            return {"success": False, "output": None, "error": "Spotify no está conectado."}
        try:
            return {"success": True, "output": self.spotify.next_track(), "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class SpotifyPreviousAdapter(ToolAdapter):
    """Regresa a la canción anterior."""

    name = "spotify_previous"
    description = "Go back to the previous track on Spotify. No args needed."
    requires_approval = False

    def __init__(self, spotify_client):
        self.spotify = spotify_client

    def execute(self, args: dict) -> dict:
        if not self.spotify.is_authenticated:
            return {"success": False, "output": None, "error": "Spotify no está conectado."}
        try:
            return {"success": True, "output": self.spotify.previous_track(), "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class SpotifyCurrentAdapter(ToolAdapter):
    """Muestra la canción que está sonando."""

    name = "spotify_current"
    description = "Show what is currently playing on Spotify. No args needed."
    requires_approval = False

    def __init__(self, spotify_client):
        self.spotify = spotify_client

    def execute(self, args: dict) -> dict:
        if not self.spotify.is_authenticated:
            return {"success": False, "output": None, "error": "Spotify no está conectado."}
        try:
            return {"success": True, "output": self.spotify.current_track(), "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class SpotifyVolumeAdapter(ToolAdapter):
    """Ajusta el volumen de Spotify."""

    name = "spotify_volume"
    description = (
        "Set Spotify volume level. Args: 'volume' (integer 0-100)."
    )
    requires_approval = False

    def __init__(self, spotify_client):
        self.spotify = spotify_client

    def execute(self, args: dict) -> dict:
        if not self.spotify.is_authenticated:
            return {"success": False, "output": None, "error": "Spotify no está conectado."}
        try:
            vol = int(args.get("volume", 50))
            return {"success": True, "output": self.spotify.set_volume(vol), "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class SpotifyQueueAdapter(ToolAdapter):
    """Agrega una canción a la cola de reproducción."""

    name = "spotify_queue"
    description = (
        "Add a song to the Spotify playback queue. Args: 'query' (song name to add)."
    )
    requires_approval = False

    def __init__(self, spotify_client):
        self.spotify = spotify_client

    def execute(self, args: dict) -> dict:
        if not self.spotify.is_authenticated:
            return {"success": False, "output": None, "error": "Spotify no está conectado."}
        query = args.get("query", "")
        if not query:
            return {"success": False, "output": None, "error": "Falta el argumento 'query'."}
        try:
            return {"success": True, "output": self.spotify.add_to_queue(query), "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class SpotifySearchAdapter(ToolAdapter):
    """Busca canciones, artistas, albums o playlists en Spotify."""

    name = "spotify_search"
    description = (
        "Search Spotify for songs, artists, albums, or playlists. "
        "Args: 'query' (search text). Returns formatted results."
    )
    requires_approval = False

    def __init__(self, spotify_client):
        self.spotify = spotify_client

    def execute(self, args: dict) -> dict:
        if not self.spotify.is_authenticated:
            return {"success": False, "output": None, "error": "Spotify no está conectado."}
        query = args.get("query", "")
        if not query:
            return {"success": False, "output": None, "error": "Falta el argumento 'query'."}
        try:
            return {"success": True, "output": self.spotify.search(query), "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": str(e)}


class SpotifyDevicesAdapter(ToolAdapter):
    """Lista dispositivos Spotify disponibles."""

    name = "spotify_devices"
    description = "List available Spotify playback devices. No args needed."
    requires_approval = False

    def __init__(self, spotify_client):
        self.spotify = spotify_client

    def execute(self, args: dict) -> dict:
        if not self.spotify.is_authenticated:
            return {"success": False, "output": None, "error": "Spotify no está conectado."}
        try:
            return {"success": True, "output": self.spotify.get_devices(), "error": None}
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


def build_registry(gestor, knowledge_base=None, spotify_client=None, face_manager=None) -> AdapterRegistry:
    """
    Construye el registry con todos los adapters disponibles,
    reutilizando los componentes que ya tiene GestorHerramientas.
    """
    registry = AdapterRegistry()

    registry.register(SearchWebAdapter(gestor.scraper, gestor._consultar_ia))
    registry.register(CallApiAdapter(gestor._consultar_ia))
    registry.register(ReadFileAdapter())
    registry.register(CreateNotebookAdapter())
    registry.register(CreateLocalArtifactAdapter())
    registry.register(OpenLocalArtifactAdapter())
    registry.register(WriteFileAdapter())
    registry.register(RunShellAdapter())
    registry.register(CreatePresentationAdapter(gestor))
    registry.register(CreateDocumentAdapter(gestor))
    registry.register(CreateSpreadsheetAdapter(gestor))
    registry.register(AnalyzeImageAdapter(gestor.vision))
    registry.register(AnalyzeDocumentAdapter(gestor.docs))
    registry.register(EvaluateCVAdapter(gestor._consultar_ia, knowledge_base=knowledge_base))
    registry.register(MessageToolAdapter(
        "calendar_manage",
        "Create or read Google Calendar events from a natural-language instruction. Args: 'message'.",
        gestor.gestionar_calendario,
    ))
    registry.register(MessageToolAdapter(
        "gmail_manage",
        "Read or send Gmail messages from a natural-language instruction. Args: 'message'.",
        gestor.gestionar_correo,
    ))
    registry.register(MessageToolAdapter(
        "youtube_search",
        "Search YouTube and recommend videos from a natural-language request. Args: 'message'.",
        gestor.gestionar_youtube,
    ))
    registry.register(MessageToolAdapter(
        "weather_lookup",
        "Get current weather for a city from a natural-language request. Args: 'message'.",
        gestor.gestionar_clima,
    ))
    registry.register(MessageToolAdapter(
        "crypto_lookup",
        "Get cryptocurrency prices or rankings from a natural-language request. Args: 'message'.",
        gestor.gestionar_crypto,
    ))
    registry.register(MessageToolAdapter(
        "image_generate",
        "Generate an image with Pollinations.ai from a natural-language prompt. Args: 'message'.",
        gestor.generar_imagen_ia,
    ))
    registry.register(MessageToolAdapter(
        "qr_generate",
        "Generate a QR code from a natural-language request. Args: 'message'.",
        gestor.generar_qr,
    ))
    registry.register(MessageToolAdapter(
        "nasa_lookup",
        "Get NASA picture of the day or asteroid information from a natural-language request. Args: 'message'.",
        gestor.gestionar_nasa,
    ))
    registry.register(MessageToolAdapter(
        "comfyui_generate",
        "Generate an image with local ComfyUI or Stable Diffusion from a natural-language prompt. Args: 'message'.",
        gestor.generar_imagen_comfyui,
    ))

    # DeepFace adapters (solo si hay face_manager)
    if face_manager and face_manager.available:
        registry.register(FaceAnalyzeAdapter(face_manager))
        registry.register(FaceVerifyAdapter(face_manager))
        registry.register(FaceRegisterAdapter(face_manager))
        registry.register(FaceRecognizeAdapter(face_manager))
        registry.register(FaceAntiSpoofAdapter(face_manager))

    # Knowledge base adapters (solo si hay KB)
    if knowledge_base:
        registry.register(StoreCVAdapter(knowledge_base))
        registry.register(StorePersonAdapter(knowledge_base))
        registry.register(AddFactAdapter(knowledge_base))
        registry.register(QueryKnowledgeAdapter(knowledge_base))

    # Spotify adapters (solo si hay cliente Spotify)
    if spotify_client:
        registry.register(SpotifyPlayAdapter(spotify_client))
        registry.register(SpotifyPauseAdapter(spotify_client))
        registry.register(SpotifyNextAdapter(spotify_client))
        registry.register(SpotifyPreviousAdapter(spotify_client))
        registry.register(SpotifyCurrentAdapter(spotify_client))
        registry.register(SpotifyVolumeAdapter(spotify_client))
        registry.register(SpotifyQueueAdapter(spotify_client))
        registry.register(SpotifySearchAdapter(spotify_client))
        registry.register(SpotifyDevicesAdapter(spotify_client))

    return registry
