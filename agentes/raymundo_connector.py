"""
🔌 RAYMUNDO ↔ AGENTFIELD CONNECTOR
Módulo que Raymundo importa para delegar tareas a los agentes especializados.

Si el orquestador NO está corriendo → Raymundo usa sus herramientas internas (sin cambios).
Si el orquestador SÍ está corriendo → Raymundo delega al agente correcto automáticamente.

Integración non-invasiva: solo agrega una llamada opcional ANTES del routing interno.
"""

import requests
import json
from typing import Optional

ORCHESTRATOR_URL = "http://localhost:8000"
_agentfield_disponible: Optional[bool] = None  # Cache para no pegar en cada mensaje


def verificar_disponibilidad() -> bool:
    """Verifica si el orquestador está corriendo. Usa cache de 30 segundos."""
    global _agentfield_disponible
    try:
        r = requests.get(f"{ORCHESTRATOR_URL}/health", timeout=1)
        _agentfield_disponible = r.status_code == 200
    except Exception:
        _agentfield_disponible = False
    return _agentfield_disponible


def esta_disponible() -> bool:
    """Retorna si AgentField está disponible (sin llamada HTTP si ya se sabe)."""
    global _agentfield_disponible
    if _agentfield_disponible is None:
        return verificar_disponibilidad()
    return _agentfield_disponible


def resetear_cache():
    """Fuerza re-verificación en el próximo mensaje."""
    global _agentfield_disponible
    _agentfield_disponible = None


def delegar(mensaje: str, agente: Optional[str] = None, parametros: Optional[dict] = None) -> Optional[dict]:
    """
    Delega un mensaje al orquestador AgentField.

    Args:
        mensaje:    Texto del usuario (igual que Raymundo lo recibe)
        agente:     Agente forzado: 'research' | 'propuestas' | 'google' (None = auto-detección)
        parametros: Parámetros adicionales opcionales

    Returns:
        dict con claves: exito, agente_usado, skill_usado, resultado, url
        None si AgentField no está disponible o falló.
    """
    if not esta_disponible():
        return None

    try:
        payload = {
            "mensaje":         mensaje,
            "agente_forzado":  agente,
            "parametros":      parametros or {},
        }
        r = requests.post(
            f"{ORCHESTRATOR_URL}/procesar",
            json=payload,
            timeout=120,
        )
        if r.status_code == 200:
            return r.json()

        # Si el orquestador devuelve error, invalidar caché
        if r.status_code == 503:
            resetear_cache()

        return None

    except requests.exceptions.ConnectionError:
        resetear_cache()
        return None
    except Exception as e:
        print(f"[AgentField] Error: {e}")
        return None


def estado_agentes() -> str:
    """Retorna string con estado de cada agente para mostrar en la GUI."""
    if not esta_disponible():
        return "⚫ AgentField: Inactivo (modo local)"

    try:
        r = requests.get(f"{ORCHESTRATOR_URL}/agentes", timeout=3)
        if r.status_code == 200:
            agentes = r.json()
            lineas = ["🔵 **AgentField Activo** — Agentes:"]
            for nombre, estado in agentes.items():
                lineas.append(f"  {estado} {nombre}")
            return "\n".join(lineas)
    except Exception:
        pass

    return "⚠️ AgentField: Sin respuesta"
