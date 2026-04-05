"""
📊 GOOGLE AGENT — Axoloit
Crea documentos, presentaciones y hojas de cálculo en Google Workspace.

Habilidades:
  - crear_presentacion   → Presentación en Google Slides
  - crear_documento      → Documento en Google Docs
  - crear_tracker        → Hoja de seguimiento en Google Sheets
  - crear_propuesta_doc  → Propuesta completa en Google Docs (formato oficial)

Puerto: 8003
"""

from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

from base_agent import (
    log,
    get_groq_client, get_mistral_client, get_ollama_client, get_google_client,
    BASE_DIR, llamar_ia,
)

# ── FastAPI app ────────────────────────────────────────────────
app = FastAPI(title="Google Agent", version="1.0.0")

# ── Modelos de entrada ─────────────────────────────────────────
class PresentacionInput(BaseModel):
    tema: str
    num_slides: int = 6
    estilo: str = "profesional"
    publico: str = "municipios mexicanos"

class DocumentoInput(BaseModel):
    titulo: str
    contenido: str
    tipo: str = "general"

class TrackerInput(BaseModel):
    nombre: str
    tipo: str = "municipios"
    columnas: Optional[list] = None

class PropuestaDocInput(BaseModel):
    municipio: str
    contacto: Optional[str] = None
    cargo: Optional[str] = None
    problema: Optional[str] = None

# ── Clientes IA y Google ───────────────────────────────────────
groq    = get_groq_client()
mistral = get_mistral_client()
ollama  = get_ollama_client()
google  = get_google_client()


def _llamar_ia(prompt: str, max_tokens: int = 3000) -> str:
    """Cadena Groq → Mistral → Ollama."""
    return llamar_ia(prompt, groq, mistral, ollama, max_tokens=max_tokens)


def _check_google():
    """Verifica que Google esté disponible."""
    if not google:
        raise RuntimeError(
            "Google Workspace no está configurado. "
            "Verifica resources/data/google-credentials.json y ejecuta autorizar_google.py"
        )


# ════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {"status": "ok", "agente": "google", "puerto": 8003}


@app.post("/skills/crear_presentacion")
def crear_presentacion(inp: PresentacionInput) -> dict:
    _check_google()
    num_slides = min(max(inp.num_slides, 3), 12)

    prompt = f"""Diseña el contenido para una presentación de {num_slides} diapositivas sobre:
Tema: {inp.tema}
Estilo: {inp.estilo}
Público: {inp.publico}

Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura exacta (sin texto extra antes ni después):
{{
    "titulo": "Título de la presentación",
    "subtitulo": "Subtítulo de portada (1 línea)",
    "diapositivas": [
        {{
            "titulo": "Título de la diapositiva (máx 60 caracteres)",
            "subtitulo": "Solo para la portada, dejar vacío en las demás",
            "puntos": [
                "• Punto conciso (máx 70 caracteres)",
                "• Otro punto importante",
                "★ Punto destacado (úsalo 1 vez por slide para el dato clave)"
            ],
            "imagen_clave": "2-3 palabras en inglés para buscar imagen (ej: GPS truck city)"
        }}
    ]
}}

REGLAS ESTRICTAS:
- Primera diapositiva: portada. Solo título y subtítulo, puntos vacíos []
- Diapositivas intermedias: máx 5 puntos cada una, concisos
- Última diapositiva: conclusión/CTA. Sin imagen_clave
- imagen_clave: solo para diapositivas 2 a N-1 (intermedias). Vacío "" para portada y conclusión
- Cada punto máx 70 caracteres para que quepa en la slide
- ★ marca máx 1 punto destacado por diapositiva"""

    log("google", f"Generando contenido para: {inp.tema}")
    contenido_json = _llamar_ia(prompt, max_tokens=3500)

    import json as _json, re as _re
    match = _re.search(r'\{[\s\S]*\}', contenido_json)
    if not match:
        return {"error": "La IA no devolvió JSON válido para la presentación", "url": None}

    try:
        parsed = _json.loads(match.group())
    except _json.JSONDecodeError as e:
        return {"error": f"JSON inválido en respuesta de IA: {e}", "url": None}

    titulo_pres = parsed.get("titulo", inp.tema)
    raw_slides  = parsed.get("diapositivas", [])

    # Construir lista de diapositivas en el formato que espera crear_presentacion
    diapositivas = []
    for idx, slide in enumerate(raw_slides):
        es_portada    = (idx == 0)
        es_conclusion = (idx == len(raw_slides) - 1 and len(raw_slides) > 1)
        tipo = "portada" if es_portada else ("conclusion" if es_conclusion else "contenido")

        # Convertir puntos a texto con viñetas
        puntos = slide.get("puntos", [])
        contenido = "\n".join(puntos) if puntos else slide.get("contenido", "")

        # Buscar imagen para slides intermedias
        imagen_url = None
        clave = slide.get("imagen_clave", "").strip()
        if clave and tipo == "contenido":
            try:
                imagen_url = google.buscar_imagen_web(clave)
            except Exception:
                imagen_url = None

        diapositivas.append({
            "tipo":      tipo,
            "titulo":    slide.get("titulo", ""),
            "subtitulo": slide.get("subtitulo", "") if es_portada else "",
            "contenido": contenido,
            "imagen_url": imagen_url,
        })

    log("google", f"Creando presentación en Google Slides ({len(diapositivas)} slides)...")
    resultado = google.crear_presentacion(titulo=titulo_pres, diapositivas=diapositivas)

    if resultado and resultado.get("url"):
        url = resultado["url"]
        log("google", f"Presentación creada: {url}")
        return {
            "titulo":  titulo_pres,
            "url":     url,
            "mensaje": f"Presentación '{titulo_pres}' creada con {len(diapositivas)} slides.\n{url}",
        }

    if resultado and resultado.get("error"):
        return {"error": resultado.get("message", "Error al crear la presentación"), "url": None}

    return {"error": "Error al crear la presentación en Google Slides", "url": None}


@app.post("/skills/crear_documento")
def crear_documento(data: DocumentoInput) -> dict:
    _check_google()

    contenido = data.contenido
    if len(contenido) < 200:
        instrucciones = {
            "propuesta":  "Redacta una propuesta comercial formal completa.",
            "informe":    "Redacta un informe ejecutivo profesional.",
            "minuta":     "Redacta la minuta en formato oficial mexicano.",
            "general":    "Redacta el documento de forma clara y profesional.",
        }
        prompt = f"""Redacta un documento de Google Docs con el siguiente tema/descripción:
Título: {data.titulo}
Descripción: {contenido}
Tipo: {instrucciones.get(data.tipo, instrucciones['general'])}

Entrega el contenido completo listo para pegar en Google Docs."""

        log("google", f"Generando contenido del documento: {data.titulo}")
        contenido = _llamar_ia(prompt, max_tokens=3000)

    resultado = google.crear_documento(titulo=data.titulo, contenido=contenido)

    if resultado and resultado.get("url"):
        url = resultado["url"]
        log("google", f"Documento creado: {url}")
        return {
            "titulo":  resultado.get("titulo", data.titulo),
            "url":     url,
            "mensaje": f"Documento '{data.titulo}' creado.\n{url}",
        }

    return {"error": "Error creando el documento en Google Docs", "url": None}


@app.post("/skills/crear_tracker")
def crear_tracker(data: TrackerInput) -> dict:
    _check_google()

    # Columnas predefinidas por tipo
    columnas_default = {
        "municipios": [
            "Municipio", "Estado", "Población", "Contacto", "Cargo",
            "Email", "Teléfono", "Estatus", "Fecha Contacto",
            "Fecha Siguiente Acción", "Propuesta Enviada", "MRR Potencial", "Notas"
        ],
        "propuestas": [
            "ID Propuesta", "Municipio", "Fecha Envío", "Valor MXN",
            "Estatus", "Respuesta", "Próxima Acción", "Cierre Estimado", "Probabilidad %"
        ],
        "metricas": [
            "Fecha", "Nuevos Contactos", "Demos Realizadas", "Propuestas Enviadas",
            "Contratos Cerrados", "MRR Acumulado", "Churn", "Notas"
        ],
        "general": ["ID", "Descripción", "Responsable", "Fecha Inicio", "Fecha Fin", "Estatus", "Notas"],
    }

    cols = data.columnas or columnas_default.get(data.tipo, columnas_default["general"])

    resultado = google.crear_hoja_calculo(titulo=data.nombre)

    if resultado and resultado.get("url"):
        # Escribir headers como primera fila
        try:
            google.escribir_datos(resultado["id"], "Sheet1!A1", [cols])
        except Exception:
            pass
        url = resultado["url"]
        log("google", f"Spreadsheet creado: {url}")
        return {
            "nombre":  data.nombre,
            "url":     url,
            "mensaje": f"Tracker '{data.nombre}' creado con {len(cols)} columnas.\n{url}",
        }

    return {"error": "Error creando la hoja de cálculo en Google Sheets", "url": None}


@app.post("/skills/crear_propuesta_doc")
def crear_propuesta_doc(data: PropuestaDocInput) -> dict:
    """Genera propuesta TraceTrash con IA y la sube directamente a Google Docs."""
    _check_google()
    from datetime import datetime

    contacto_str = f"Dirigida a: {data.contacto}" if data.contacto else "Dirigida a: Autoridades Municipales"
    cargo_str    = f", {data.cargo}" if data.cargo else ""
    problema_str = f"\nProblema identificado: {data.problema}" if data.problema else ""
    fecha        = datetime.now().strftime("%d de %B de %Y")

    prompt = f"""Eres un experto en ventas B2G para startups de tecnología municipal mexicanas.
Empresa: Axoloit | Producto: TraceTrash (IoT + GPS + IA para residuos sólidos)
Fundador: Kenneth Alcalá

Genera una propuesta comercial completa en Markdown para:
MUNICIPIO: {data.municipio}
{contacto_str}{cargo_str}
FECHA: {fecha}{problema_str}

Incluye: portada, resumen ejecutivo, problema, solución, beneficios, implementación (8 semanas), ROI, precios, próximos pasos.
Tono formal gubernamental mexicano pero moderno. Propuesta completa y persuasiva."""

    log("google", f"Generando propuesta para {data.municipio} → Google Docs...")
    contenido_md = _llamar_ia(prompt, max_tokens=3000)

    titulo = f"Propuesta TraceTrash — {data.municipio} — {datetime.now().strftime('%B %Y')}"
    resultado = google.crear_documento(titulo=titulo, contenido=contenido_md)

    if resultado and resultado.get("url"):
        url = resultado["url"]
        log("google", f"Propuesta creada en Google Docs: {url}")
        return {"titulo": titulo, "url": url, "mensaje": f"Propuesta para {data.municipio} creada.\n{url}"}

    return {"error": "Error creando el documento en Google Docs", "url": None}


# ── Arranque ───────────────────────────────────────────────────
if __name__ == "__main__":
    log("google", "Iniciando Google Agent en puerto 8003...")
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="warning")
