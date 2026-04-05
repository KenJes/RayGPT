"""
🧠 ORCHESTRATOR — Axoloit / Raymundo
Punto central de coordinación entre Raymundo (GUI) y los agentes especializados.

Expone un endpoint HTTP local que Raymundo llama cuando los agentes están disponibles.
Si los agentes no están corriendo, Raymundo usa sus herramientas internas normalmente.

Puerto: 8000
Dashboard AgentField: http://localhost:9090
"""

import asyncio
import json
import re
from typing import Optional

from base_agent import (
    log,
    get_groq_client, get_mistral_client, get_ollama_client,
    llamar_ia,
)

# ── FastAPI app ────────────────────────────────────────────────────
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import httpx


# ── FastAPI app ────────────────────────────────────────────────
http_app = FastAPI(
    title="Axoloit Orchestrator",
    description="Puente entre Raymundo y los agentes especializados",
    version="1.0.0",
)

# ── Clientes IA ────────────────────────────────────────────────
groq    = get_groq_client()
mistral = get_mistral_client()
ollama  = get_ollama_client()

# URLs de los agentes (cuando corren localmente fuera de Docker)
AGENT_URLS = {
    "research":   "http://localhost:8001",
    "propuestas": "http://localhost:8002",
    "google":     "http://localhost:8003",
}


# ════════════════════════════════════════════════════════════════
# MODELOS DE DATOS
# ════════════════════════════════════════════════════════════════

class SolicitudOrchestrator(BaseModel):
    mensaje: str
    agente_forzado: Optional[str] = None   # 'research' | 'propuestas' | 'google'
    parametros: Optional[dict] = {}


class RespuestaOrchestrator(BaseModel):
    exito: bool
    agente_usado: str
    skill_usado: str
    resultado: str
    url: Optional[str] = None
    tiempo_ms: Optional[int] = None


# ════════════════════════════════════════════════════════════════
# ROUTER INTELIGENTE
# ════════════════════════════════════════════════════════════════

def _detectar_intencion_agente(mensaje: str) -> tuple[str, str, dict]:
    """
    Decide qué agente y qué skill invocar basándose en el mensaje.

    Returns:
        (agente, skill, parametros)
    """
    msg = mensaje.lower()

    # ─── Agente de Propuestas ─────────────────────────────────
    if any(kw in msg for kw in [
        "propuesta", "municipio", "alcalde", "ayuntamiento",
        "roi", "pitch", "tracetrash", "email para", "mail para",
        "contactar al", "carta para", "licitación", "licitacion",
    ]):
        # Detectar skill específico
        if any(kw in msg for kw in ["calc", "roi", "retorno", "inversión", "cuánto ahorra"]):
            params = {"nombre": _extraer_municipio(mensaje) or "municipio", "num_camiones": 5, "costo_combustible_mensual": 50000}
            return "propuestas", "calcular_roi", params

        if any(kw in msg for kw in ["email", "correo", "mail"]):
            return "propuestas", "redactar_email", {
                "municipio": _extraer_municipio(mensaje) or "municipio",
                "tipo": "acercamiento",
            }

        if any(kw in msg for kw in ["pitch", "presentarte", "discurso", "script"]):
            return "propuestas", "generar_pitch", {
                "municipio": _extraer_municipio(mensaje),
                "duracion_minutos": 2,
            }

        if any(kw in msg for kw in ["analiza", "perfil", "diagnóstico", "oportunidad"]):
            return "propuestas", "analizar_municipio", {
                "nombre": _extraer_municipio(mensaje) or mensaje[:50],
            }

        # Default: propuesta completa
        return "propuestas", "generar_propuesta", {
            "municipio": _extraer_municipio(mensaje) or "Municipio",
        }

    # ─── Agente Google Workspace ──────────────────────────────
    if any(kw in msg for kw in [
        "presentación", "presentacion", "slides", "diapositivas", "ppt",
        "documento", "doc ", "redacta", "informe", "reporte",
        "hoja de cálculo", "spreadsheet", "tracker", "tabla de seguimiento",
        "crea un sheet", "crea una hoja",
    ]):
        if any(kw in msg for kw in ["presentación", "presentacion", "slides", "diapositivas"]):
            return "google", "crear_presentacion", {"tema": mensaje}

        if any(kw in msg for kw in ["hoja", "spreadsheet", "tracker", "sheet"]):
            tipo = "municipios" if "municipio" in msg else "general"
            return "google", "crear_tracker", {"nombre": mensaje[:60], "tipo": tipo}

        return "google", "crear_documento", {"titulo": mensaje[:80], "contenido": mensaje}

    # ─── Agente de Investigación (default) ───────────────────
    if any(kw in msg for kw in [
        "investiga", "busca", "qué es", "que es", "cuéntame", "cuentame",
        "analiza", "competencia", "competidor", "empresa", "http", "www",
        "noticias", "infórmame", "informame", "resume",
    ]):
        if any(kw in msg for kw in ["compet", "rival", "empresa similar"]):
            return "research", "analizar_competencia", {"empresa": _extraer_url_o_empresa(mensaje)}

        if any(kw in msg for kw in ["resume", "resumir", "puntos de"]):
            url = _extraer_url(mensaje)
            if url:
                return "research", "resumir_url", {"url": url}

        url = _extraer_url(mensaje)
        if url:
            return "research", "investigar", {"tema": mensaje, "url": url}

        return "research", "investigar", {"tema": mensaje}

    # Fallback: investigación general
    return "research", "investigar", {"tema": mensaje}


def _extraer_municipio(texto: str) -> Optional[str]:
    """Extrae nombre de municipio del texto."""
    # Patrones comunes: "para Chalco", "del municipio de X", "en Valle de X"
    patrones = [
        r'para ([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
        r'de ([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
        r'en ([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
        r'municipio (?:de )?([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?: [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
    ]
    for patron in patrones:
        m = re.search(patron, texto)
        if m:
            return m.group(1)
    return None


def _extraer_url(texto: str) -> Optional[str]:
    """Extrae primera URL del texto."""
    m = re.search(r'https?://[^\s]+|www\.[^\s]+', texto)
    if m:
        url = m.group()
        return url if url.startswith("http") else f"https://{url}"
    return None


def _extraer_url_o_empresa(texto: str) -> str:
    """Extrae URL o nombre de empresa."""
    url = _extraer_url(texto)
    if url:
        return url
    # Intentar extraer nombre propio
    m = re.search(r'(?:de |sobre |empresa |compet[^\s]+ )([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)', texto)
    return m.group(1) if m else texto[:50]


# ════════════════════════════════════════════════════════════════
# CALLER A AGENTES
# ════════════════════════════════════════════════════════════════

async def _llamar_agente_local(agente: str, skill: str, params: dict) -> dict:
    """Llama a un agente corriendo localmente via HTTP."""
    url = AGENT_URLS.get(agente)
    if not url:
        return {"error": f"Agente '{agente}' no reconocido"}

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{url}/skills/{skill}",
                json=params,
            )
            if response.status_code == 200:
                return {"resultado": response.json()}
            return {"error": f"HTTP {response.status_code}: {response.text[:200]}"}
    except httpx.ConnectError:
        return {"error": f"Agente '{agente}' no está corriendo en {url}"}
    except Exception as e:
        return {"error": str(e)}


# ════════════════════════════════════════════════════════════════
# ENDPOINTS HTTP (Raymundo se conecta aquí)
# ════════════════════════════════════════════════════════════════

@http_app.get("/health")
async def health():
    """Verifica que el orquestador está vivo."""
    return {"status": "ok", "agentes": list(AGENT_URLS.keys())}


@http_app.get("/agentes")
async def listar_agentes():
    """Lista los agentes disponibles y su estado."""
    estados = {}
    async with httpx.AsyncClient(timeout=3) as client:
        for nombre, url in AGENT_URLS.items():
            try:
                r = await client.get(f"{url}/health")
                estados[nombre] = "✅ Activo" if r.status_code == 200 else "⚠️ Error"
            except Exception:
                estados[nombre] = "❌ Inactivo"
    return estados


@http_app.post("/procesar", response_model=RespuestaOrchestrator)
async def procesar(solicitud: SolicitudOrchestrator):
    """
    Recibe un mensaje de Raymundo y lo procesa con el agente adecuado.

    Body:
        {
            "mensaje": "Genera una propuesta para Valle de Chalco",
            "agente_forzado": null,
            "parametros": {}
        }
    """
    import time
    inicio = time.time()

    # Decidir ruta
    if solicitud.agente_forzado:
        agente = solicitud.agente_forzado
        skill  = solicitud.parametros.get("skill", "investigar")
        params = {k: v for k, v in solicitud.parametros.items() if k != "skill"}
    else:
        agente, skill, params = _detectar_intencion_agente(solicitud.mensaje)

    # Sobrescribir parámetros adicionales si se enviaron
    if solicitud.parametros:
        params.update(solicitud.parametros)

    log("orchestrator", f"→ {agente}.{skill}({list(params.keys())})")

    # Llamar al agente
    resultado = await _llamar_agente_local(agente, skill, params)
    tiempo_ms = int((time.time() - inicio) * 1000)

    if "error" in resultado:
        raise HTTPException(status_code=503, detail=resultado["error"])

    # Extraer texto y URL del resultado
    res_data = resultado.get("resultado", {})
    if isinstance(res_data, dict):
        texto = res_data.get("mensaje") or res_data.get("resultado") or str(res_data)
        url   = res_data.get("url")
    else:
        texto = str(res_data)
        url   = None

    return RespuestaOrchestrator(
        exito=True,
        agente_usado=agente,
        skill_usado=skill,
        resultado=texto,
        url=url,
        tiempo_ms=tiempo_ms,
    )


# ── Arranque ─────────────────────────────────────────────────────
if __name__ == "__main__":
    log("orchestrator", "Iniciando Orchestrator en puerto 8000...")
    log("orchestrator", "  Raymundo conecta en http://localhost:8000/procesar")
    uvicorn.run(http_app, host="0.0.0.0", port=8000, log_level="info")
