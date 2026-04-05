"""
🔍 RESEARCH AGENT — Axoloit
Especializado en investigación web e inteligencia de mercado.

Habilidades:
  - scrape_url      → Extrae contenido de cualquier URL
  - investigar      → Investiga un tema con scraping + análisis IA
  - analizar_competencia → Analiza competidores de Axoloit / TraceTrash
  - resumir_url     → Resume una página web en puntos clave

Puerto: 8001
"""

from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

from base_agent import (
    log, get_groq_client, get_mistral_client, get_ollama_client,
    BASE_DIR, WebScraper, llamar_ia,
)

# ── FastAPI app ────────────────────────────────────────────────
app = FastAPI(title="Research Agent", version="1.0.0")


# ── Modelos de entrada ─────────────────────────────────────────
class ScrapeUrlInput(BaseModel):
    url: str

class InvestigarInput(BaseModel):
    tema: str
    url: Optional[str] = None

class CompetenciaInput(BaseModel):
    empresa: str

class ResumirInput(BaseModel):
    url: str
    enfoque: str = "general"

# ── Clientes IA ────────────────────────────────────────────────
groq    = get_groq_client()
mistral = get_mistral_client()
ollama  = get_ollama_client()

# ── WebScraper reutilizado de core/ ────────────────────────────
scraper = WebScraper()

_SYSTEM_RESEARCH = "Eres un investigador experto en tecnología y negocios."


def _llamar_ia(prompt: str, max_tokens: int = 2000) -> str:
    """Cadena Groq → Mistral → Ollama."""
    return llamar_ia(prompt, groq, mistral, ollama, system=_SYSTEM_RESEARCH, max_tokens=max_tokens)


# ════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {"status": "ok", "agente": "research", "puerto": 8001}


@app.post("/skills/scrape_url")
def scrape_url(data: ScrapeUrlInput):
    log("research", f"Scrapeando: {data.url}")
    return scraper.scrape(data.url)


@app.post("/skills/investigar")
def investigar(data: InvestigarInput):
    contexto = ""
    if data.url:
        log("research", f"Obteniendo contexto de: {data.url}")
        datos = scraper.scrape(data.url)
        if datos.get("success"):
            contexto = f"\n\n**Contenido de {data.url}:**\n{datos['contenido'][:1500]}"

    prompt = f"""Eres un investigador de negocios experto en tecnología y mercados mexicanos, especializado en Axoloit (consultora de software e Inteligencia Artificial que implementa soluciones de IA, Agentes Inteligentes, ERP, CRM y automatización para empresas y gobiernos).

Investiga el siguiente tema y produce un reporte ejecutivo:

TEMA: {data.tema}{contexto}

REPORTE REQUERIDO:
1. **Resumen ejecutivo** (3-5 líneas)
2. **Hallazgos clave** (viñetas, 5-7 puntos)
3. **Relevancia para Axoloit** (cómo aplica al negocio de consultoría de software e IA: oportunidades de implementación, mercados, tendencias)
4. **Oportunidades detectadas** (2-3 oportunidades accionables para Axoloit como consultora)
5. **Riesgos o consideraciones** (1-2 puntos críticos)

Sé conciso, preciso y orientado a acción. Usa datos específicos cuando sea posible."""

    log("research", f"Analizando tema: {data.tema}")
    return {"resultado": _llamar_ia(prompt, max_tokens=1500)}


@app.post("/skills/analizar_competencia")
def analizar_competencia(data: CompetenciaInput):
    contexto = ""
    empresa = data.empresa
    if empresa.startswith("http") or "." in empresa:
        url = empresa if empresa.startswith("http") else f"https://{empresa}"
        datos = scraper.scrape(url)
        if datos.get("success"):
            empresa = datos.get("titulo", empresa)
            contexto = f"\n\nContenido del sitio:\n{datos['contenido'][:1200]}"

    prompt = f"""Analiza a '{empresa}' como competidor potencial de Axoloit en el mercado de tecnología y consultoría de software en México.

Axoloit es una consultora de software e IA fundada por Kenneth Alcalá, especializada en implementación de Inteligencia Artificial, Agentes Inteligentes, ERP, CRM y automatización de procesos, adaptándose a las necesidades de cada cliente (empresas y gobiernos municipales). Solución destacada: TraceTrash (GPS + IA para residuos municipales).{contexto}

ANÁLISIS REQUERIDO:
1. **¿Qué hace este competidor?** (descripción breve)
2. **Fortalezas** vs Axoloit (2-3 puntos)
3. **Debilidades** vs Axoloit (2-3 puntos)
4. **Mercado objetivo** (¿compite directamente o es segmento diferente?)
5. **Diferenciadores de Axoloit** frente a ellos (consultoría personalizada, IA adaptada, Agentes Inteligentes, enfoque mexicano)
6. **Estrategia recomendada** (cómo posicionarse frente a este competidor)

Responde con análisis objetivo y accionable."""

    log("research", f"Analizando competidor: {empresa}")
    return {"resultado": _llamar_ia(prompt, max_tokens=1200)}


@app.post("/skills/resumir_url")
def resumir_url(data: ResumirInput):
    datos = scraper.scrape(data.url)
    if not datos.get("success"):
        return {"resultado": f"No se pudo acceder a {data.url}: {datos.get('error', 'Error')}"}

    enfoques = {
        "general":    "Resume los puntos más importantes de forma clara y directa.",
        "negocio":    "Enfócate en el modelo de negocio, propuesta de valor y mercado objetivo.",
        "tecnico":    "Destaca los aspectos técnicos, tecnologías usadas y arquitectura.",
        "municipios": "Extrae todo lo relevante para municipios mexicanos y gestión de residuos.",
    }
    instruccion = enfoques.get(data.enfoque, enfoques["general"])

    prompt = f"""Tienes el siguiente contenido de {data.url}:

{datos['contenido'][:2000]}

{instruccion}

Produce un resumen en 5-8 puntos clave con formato de viñetas. Sé conciso y preciso."""

    log("research", f"Resumiendo {data.url}")
    return {"resultado": _llamar_ia(prompt, max_tokens=800)}


# ── Arranque ───────────────────────────────────────────────────
if __name__ == "__main__":
    log("research", "Iniciando Research Agent en puerto 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")
