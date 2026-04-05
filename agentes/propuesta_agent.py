"""
📋 PROPUESTA AGENT — Axoloit
Generador de propuestas comerciales para municipios mexicanos.

Habilidades:
  - generar_propuesta      → Genera propuesta completa para un municipio
  - analizar_municipio     → Perfil de un municipio objetivo
  - calcular_roi           → Estimación de ROI de TraceTrash para un municipio
  - redactar_email         → Email de acercamiento a autoridades municipales
  - generar_pitch          → Script de pitch de 2 minutos

Puerto: 8002
"""

from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

from base_agent import (
    log,
    get_groq_client, get_mistral_client, get_ollama_client,
    OUTPUT_DIR, llamar_ia,
)
from datetime import datetime

# ── FastAPI app ────────────────────────────────────────────────
app = FastAPI(title="Propuesta Agent", version="1.0.0")

# ── Modelos de entrada ─────────────────────────────────────────
class MunicipioInput(BaseModel):
    nombre: str
    poblacion: Optional[int] = None
    problema: Optional[str] = None

class RoiInput(BaseModel):
    nombre: str
    num_camiones: int
    costo_combustible_mensual: float
    poblacion: Optional[int] = None

class PropuestaInput(BaseModel):
    municipio: str
    contacto: Optional[str] = None
    cargo: Optional[str] = None
    problema: Optional[str] = None
    num_camiones: Optional[int] = None

class EmailInput(BaseModel):
    municipio: str
    contacto: Optional[str] = None
    cargo: Optional[str] = None
    tipo: str = "acercamiento"

class PitchInput(BaseModel):
    municipio: Optional[str] = None
    duracion_minutos: int = 2

# ── Clientes IA ────────────────────────────────────────────────
groq    = get_groq_client()
mistral = get_mistral_client()
ollama  = get_ollama_client()

# ── Context empresarial Axoloit ────────────────────────────────
AXOLOIT_CONTEXT = """
Axoloit es una consultora de software 100% mexicana fundada por Kenneth Alcalá, CEO.
Especialidad: Diseño e implementación de soluciones de Inteligencia Artificial y Agentes Inteligentes adaptadas a las necesidades de cada cliente.
Región de operación: Sur del Estado de México (con proyección nacional).

QUÉ HACE AXOLOIT:
- Consultoría y desarrollo de software a medida
- Implementación de sistemas ERP (Enterprise Resource Planning)
- Implementación de sistemas CRM (Customer Relationship Management)
- Automatización de procesos empresariales con IA
- Diseño e integración de Agentes Inteligentes para operaciones, ventas, atención y más
- Dashboards de monitoreo y analítica avanzada
- Integración de sistemas legados con tecnología moderna

SOLUCIONES DESTACADAS:
- TraceTrash: Sistema GPS + IA para optimización de rutas de recolección de residuos sólidos (municipios 50K-500K hab.)
- Agentes de IA para gestión comercial, investigación de mercado y generación automatizada de propuestas
- Sistemas de reportería automática y auditoría para gobierno y empresa

PROPUESTA DE VALOR:
- Nos adaptamos al problema del cliente, no al revés
- Reducción de costos operativos mediante automatización con IA (20-40% típico)
- Implementaciones rápidas: 4-12 semanas según alcance
- Acompañamiento continuo: soporte técnico y mejora iterativa
- Soluciones escalables: desde PYME hasta gobierno municipal

MODELO COMERCIAL:
- Consultoría inicial: diagnóstico + propuesta de solución
- Desarrollo a medida o adaptación de plataformas existentes
- Modalidades: proyecto cerrado, suscripción SaaS mensual o contrato de mantenimiento
- Precios desde $15,000 MXN/mes según complejidad y alcance
"""


_SYSTEM_PROPUESTAS = (
    "Eres un experto en propuestas comerciales municipales en México, "
    "especializado en tecnología para gobiernos locales y sustentabilidad. "
    "Redactas propuestas formales, persuasivas y con datos concretos."
)


def _llamar_ia(prompt: str, max_tokens: int = 3000) -> str:
    """Cadena Groq → Mistral → Ollama."""
    return llamar_ia(prompt, groq, mistral, ollama, system=_SYSTEM_PROPUESTAS, max_tokens=max_tokens)


# ════════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {"status": "ok", "agente": "propuestas", "puerto": 8002}


@app.post("/skills/analizar_municipio")
def analizar_municipio(data: MunicipioInput):
    pob_str = f"{data.poblacion:,}" if data.poblacion else "desconocida"
    prob_str = f"\nProblema mencionado: {data.problema}" if data.problema else ""

    prompt = f"""{AXOLOIT_CONTEXT}

Genera un perfil municipal de oportunidad para Axoloit:

MUNICIPIO: {data.nombre}
POBLACIÓN: {pob_str} habitantes{prob_str}

PERFIL REQUERIDO:
1. **Contexto del municipio** (tamaño, región, perfil sociodemográfico estimado)
2. **Problemáticas operativas y tecnológicas** (3-5 áreas de dolor: servicios públicos, gestión interna, atención ciudadana, etc.)
3. **Oportunidades Axoloit** (soluciones de IA, ERP, CRM o Agentes Inteligentes que resolverían esos problemas)
4. **Ahorro o valor potencial** (estimado en MXN o eficiencia operativa)
5. **Perfil del tomador de decisión** (Presidente Municipal, Dirección de Servicios Públicos, Tesorería, etc.)
6. **Nivel de prioridad** (Alto/Medio/Bajo) y justificación
7. **Estrategia de entrada recomendada** (diagnóstico gratuito, demo, piloto, propuesta técnica)

Usa datos y estimaciones realistas para municipios mexicanos de ese tamaño."""

    log("propuestas", f"Analizando municipio: {data.nombre}")
    return {"resultado": _llamar_ia(prompt, max_tokens=1500)}


@app.post("/skills/calcular_roi")
def calcular_roi(data: RoiInput):
    precio_saas = 15000 if (data.poblacion or 0) < 100000 else (
        25000 if (data.poblacion or 0) < 250000 else 45000
    )
    ahorro_estimado = data.costo_combustible_mensual * 0.25

    prompt = f"""{AXOLOIT_CONTEXT}

Calcula el ROI de implementar una solución Axoloit (TraceTrash u otra solución IA) para el siguiente municipio:

DATOS:
- Municipio: {data.nombre}
- Flota: {data.num_camiones} camiones recolectores
- Gasto mensual combustible: ${data.costo_combustible_mensual:,.0f} MXN
- Precio solución Axoloit: ${precio_saas:,} MXN/mes (estimado según tamaño)
- Ahorro combustible estimado: ${ahorro_estimado:,.0f} MXN/mes (25% conservador)
- Población: {data.poblacion:,} hab. si se conoce

ANÁLISIS ROI REQUERIDO:
1. **Inversión total primer año** (consultoría/implementación + suscripción 12 meses)
2. **Ahorros Año 1** (combustible + eficiencia operativa + reducción horas extras + automatización de reportes)
3. **ROI Año 1** (porcentaje y meses para recuperar inversión)
4. **Proyección 3 años** (tabla comparativa)
5. **Beneficios no monetarios** (imagen municipal, cumplimiento normativo, auditorías, transparencia)
6. **Comparativa: Con vs Sin solución Axoloit** (tabla resumen)
7. **Recomendación** (por qué aprobar el proyecto ahora)

Incluye números específicos y citas a regulaciones aplicables."""

    log("propuestas", f"Calculando ROI para: {data.nombre} ({data.num_camiones} camiones)")
    return {"resultado": _llamar_ia(prompt, max_tokens=2000)}


@app.post("/skills/generar_propuesta")
def generar_propuesta(data: PropuestaInput):
    contacto_str = f"Dirigida a: {data.contacto}" if data.contacto else "Dirigida a: Autoridades Municipales"
    cargo_str    = f", {data.cargo}" if data.cargo else ""
    problema_str = f"\nProblema identificado: {data.problema}" if data.problema else ""
    camiones_str = f"\nFlota municipal: {data.num_camiones} camiones" if data.num_camiones else ""
    fecha        = datetime.now().strftime("%d de %B de %Y")

    prompt = f"""{AXOLOIT_CONTEXT}

Redacta una propuesta comercial FORMAL Y COMPLETA para:

MUNICIPIO: {data.municipio}
{contacto_str}{cargo_str}
FECHA: {fecha}{problema_str}{camiones_str}

ESTRUCTURA DE LA PROPUESTA:

# PROPUESTA TÉCNICA Y COMERCIAL
## Solución de Inteligencia Artificial y Automatización para {data.municipio}
### Axoloit — Consultoría de Software e IA | {fecha}

---

**SECCIONES REQUERIDAS:**

1. **Carta de presentación** (3 párrafos formales: presentar Axoloit como consultora de software e IA, identificar el problema o necesidad del municipio, invitar a revisión)

2. **Diagnóstico del problema** (situación actual del área identificada, costos típicos, ineficiencias comunes en municipios similares)

3. **Solución propuesta por Axoloit** (descripción técnica accesible de la solución recomendada — puede incluir ERP, CRM, Agentes IA, TraceTrash según el contexto; módulos incluidos, cómo funciona)

4. **Beneficios específicos para {data.municipio}** (5-7 beneficios medibles con números: ahorro, eficiencia, transparencia, etc.)

5. **Plan de implementación** (cronograma 8-12 semanas con hitos, capacitación incluida)

6. **Inversión** (tabla de precios mensual/anual, incluir lo que está incluido: desarrollo, soporte, actualizaciones)

7. **ROI estimado** (tabla simple con ahorros vs inversión a 12-24 meses)

8. **Casos de uso / Testimonial** (ejemplo de cliente o municipio similar donde Axoloit ya implementó soluciones)

9. **Próximos pasos** (diagnóstico gratuito, demo de 30 minutos, piloto de 30 días, proceso de contratación)

10. **Contacto** (Kenneth Alcalá, CEO Axoloit, datos de contacto genéricos)

---

TONO: Formal, gubernamental mexicano, pero moderno y orientado a resultados.
EXTENSIÓN: Propuesta completa y persuasiva. No escatimes en detalles.
IMPORTANTE: Presenta a Axoloit como una consultora integral de software e IA, no solo como proveedora de un producto; muestra que la solución se adapta a las necesidades del municipio."""

    log("propuestas", f"Generando propuesta para: {data.municipio}")
    propuesta = _llamar_ia(prompt, max_tokens=3000)
    nombre_archivo = f"propuesta_{data.municipio.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.md"
    ruta = OUTPUT_DIR / nombre_archivo
    ruta.write_text(propuesta, encoding="utf-8")
    log("propuestas", f"Guardada en: {ruta}")
    return {"resultado": propuesta, "archivo": str(ruta)}


@app.post("/skills/redactar_email")
def redactar_email(data: EmailInput):
    tipos_map = {
        "acercamiento": "primer contacto para presentar Axoloit y solicitar reunión",
        "seguimiento":  "seguimiento 7 días después de enviar la propuesta",
        "demo":         "invitación a demo gratuita de 30 minutos",
        "cierre":       "impulsar la firma del contrato o piloto de 30 días",
    }
    tipo_desc = tipos_map.get(data.tipo, "primer contacto")
    prompt = f"""{AXOLOIT_CONTEXT}

Redacta un email para: {tipo_desc}

DESTINATARIO: {data.contacto or 'Funcionario municipal'}{f', {data.cargo}' if data.cargo else ''}
MUNICIPIO: {data.municipio}

REQUERIMIENTOS:
- Asunto: impactante y profesional (máx 60 caracteres)
- Saludo formal mexicano
- Cuerpo: 3-4 párrafos cortos y directos
- Beneficio principal mencionado en las primeras 2 líneas
- Call to action claro (reunión 30 min, llamada, demo)
- Firma de Kenneth Alcalá, CEO - Axoloit
- Tono: formal pero humano, NO corporativo frío

Formato:
ASUNTO: [asunto aquí]

[cuerpo del email]"""

    log("propuestas", f"Redactando email ({data.tipo}) para: {data.municipio}")
    return {"resultado": _llamar_ia(prompt, max_tokens=800)}


@app.post("/skills/generar_pitch")
def generar_pitch(data: PitchInput):
    palabras = data.duracion_minutos * 130
    mun_str = f" personalizado para {data.municipio}" if data.municipio else ""
    prompt = f"""{AXOLOIT_CONTEXT}

Crea un script de pitch verbal{mun_str} de {data.duracion_minutos} minuto(s) (~{palabras} palabras) para presentar Axoloit.

ESTRUCTURA:
- **[0:00-0:20]** Hook: El problema del cliente (frase impactante sobre ineficiencia, costos altos o falta de tecnología)
- **[0:20-0:50]** Axoloit como solución: consultora de software e IA que se adapta al problema (mencionar ERP, CRM, Agentes IA, automatización)
- **[0:50-1:20]** Resultados concretos (números: ahorro, eficiencia, automatización; ejemplo con TraceTrash u otro caso)
- **[1:20-1:45]** Por qué Axoloit (diferenciador: consultoría mexicana, enfoque en IA y Agentes Inteligentes, acompañamiento real)
- **[1:45-2:00]** Call to action (diagnóstico gratuito, demo de 30 min, siguiente paso claro)

TONO: Confianza, pasión, datos concretos. Hablar como emprendedor mexicano exitoso que resuelve problemas reales, no como vendedor.

Incluye notas de énfasis [PAUSA], [VOZ FIRME], [SONRÍE] en puntos clave."""

    log("propuestas", f"Generando pitch de {data.duracion_minutos} min")
    return {"resultado": _llamar_ia(prompt, max_tokens=1000)}


# ── Arranque ───────────────────────────────────────────────────
if __name__ == "__main__":
    log("propuestas", "Iniciando Propuesta Agent en puerto 8002...")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="warning")
