"""
context_manager.py — Gestor centralizado de contexto para el LLM.

Construye el system prompt enriquecido con RAG automático,
temas del usuario, vocabulario, y capacidades disponibles.
Evita que el usuario tenga que repetirle a Raymundo qué hacer y cómo actuar.

Uso:
    ctx = ContextManager(knowledge_base, memory_system)
    prompt = ctx.build_system_prompt(
        user_id="123", query="crea una presentación", ...
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.config import config_agente, _get_mode

if TYPE_CHECKING:
    from core.knowledge_db import KnowledgeBase
    from core.memory import MemorySystem

logger = logging.getLogger(__name__)


# ── Capacidades disponibles (se inyecta como reminder) ───────────
_CAPABILITIES_ES = """
HERRAMIENTAS DISPONIBLES (úsalas cuando el usuario lo necesite):
• Presentaciones — Crea slides profesionales en Google Slides
• Documentos — Crea documentos en Google Docs
• Hojas de cálculo — Crea hojas en Google Sheets
• Calendario — Agenda eventos, recordatorios y consulta tu agenda en Google Calendar
• YouTube — Busca y recomienda videos de YouTube
• Spotify — Controla la reproducción de música (play, pausa, siguiente, anterior)
• Web — Busca y resume contenido de páginas web
• Imágenes — Analiza imágenes con visión por computadora (OCR)
• Documentos adjuntos — Lee y analiza PDFs, textos y otros archivos
• Comandos rápidos — /resumir, /traducir, /email, /codigo, /reset, /ayuda
""".strip()


class ContextManager:
    """Construye contexto enriquecido para inyectar al LLM."""

    def __init__(
        self,
        knowledge_base: KnowledgeBase | None = None,
        memory_system: MemorySystem | None = None,
    ):
        self.kb = knowledge_base
        self.memory = memory_system

    def build_system_prompt(
        self,
        user_id: str | None = None,
        user_name: str | None = None,
        query: str | None = None,
        tono_override: str | None = None,
        usuario_agresivo: bool = False,
        idioma: str = "es",
        include_capabilities: bool = True,
    ) -> str:
        """
        Construye el system prompt completo con:
        1. Personalidad base (archivo .md)
        2. Capacidades disponibles (herramientas)
        3. Conocimiento RAG relevante al query
        4. Temas frecuentes del usuario
        5. Estilo/vocabulario del usuario
        6. Nombre del interlocutor
        7. Instrucciones de tono
        """
        parts: list[str] = []

        # ── 1. Personalidad base ────────────────────────────────
        if idioma == "en":
            base = config_agente.get_prompt_sistema_en()
        else:
            base = config_agente.get_prompt_sistema()
        parts.append(base)

        # ── 2. Capacidades (recordatorio de herramientas) ───────
        if include_capabilities:
            parts.append(f"\n\n{_CAPABILITIES_ES}")

        # ── 3. Conocimiento RAG relevante ───────────────────────
        if self.kb and query:
            try:
                kb_context = self.kb.build_knowledge_context(
                    query=query, user_id=user_id
                )
                if kb_context:
                    parts.append(f"\n\n{kb_context}")
            except Exception as e:
                logger.warning(f"⚠️ Error obteniendo contexto KB: {e}")

        # ── 4. Temas frecuentes del usuario ─────────────────────
        if self.memory and user_id:
            try:
                temas = self.memory.get_temas_frecuentes(
                    user_id=user_id, top_n=8
                )
                if temas:
                    temas_str = ", ".join(temas)
                    parts.append(
                        f"\n\nTEMAS FRECUENTES DE ESTE USUARIO: "
                        f"Suele hablar de: {temas_str}. "
                        f"Usa este contexto para dar respuestas más relevantes "
                        f"y anticipar sus necesidades."
                    )
            except Exception as e:
                logger.warning(f"⚠️ Error obteniendo temas: {e}")

        # ── 5. Estilo / vocabulario del usuario ─────────────────
        if self.memory:
            try:
                vocab_hint = self.memory.get_vocabulario_hint(
                    user_id=user_id
                )
                if vocab_hint:
                    parts.append(vocab_hint)
            except Exception:
                pass

        # ── 6. Nombre del interlocutor ──────────────────────────
        if user_name and user_name.strip() and user_name != user_id:
            parts.append(
                f"\n\nESTÁS CHATEANDO CON: {user_name}. "
                f"Llámalo/a por su nombre ({user_name}) cuando sea natural."
            )

        # ── 7. Instrucciones de tono ────────────────────────────
        tono_instr = self._build_tone_instruction(
            tono_override, usuario_agresivo
        )
        if tono_instr:
            parts.append(tono_instr)

        return "".join(parts)

    @staticmethod
    def _build_tone_instruction(
        tono_override: str | None, usuario_agresivo: bool
    ) -> str:
        """Genera la instrucción de tono según el override y agresividad."""
        mode = _get_mode()

        # rAI es SIEMPRE agresivo — no necesita instrucción extra
        if mode == "rai":
            return ""

        if tono_override == "amigable":
            if usuario_agresivo:
                return (
                    "\n\nINSTRUCCIÓN DE TONO: Mantén el tono tranquilo y directo. "
                    "Si el usuario está siendo grosero, ignora el tono e identifica qué necesita. "
                    "NUNCA comentes sobre su lenguaje, NUNCA digas 'aunque no comparto', "
                    "'no me gusta cómo te expresas', 'Entendido, a partir de ahora' ni nada similar. "
                    "Solo responde al contenido de forma natural."
                )
            return (
                "\n\nINSTRUCCIÓN DE TONO: El usuario prefiere trato amable. "
                "Sé cordial, profesional y directo. Sin groserías."
            )

        if tono_override == "puteado":
            return (
                "\n\nINSTRUCCIÓN DE TONO: El usuario quiere tu modo directo sin filtros. "
                "Groserías permitidas, sé agresivo y directo."
            )

        if usuario_agresivo:
            return (
                "\n\nTONO DEL USUARIO EN ESTE MENSAJE: Está siendo grosero o agresivo. "
                "Respóndele al mismo nivel o más fuerte — groserías con groserías, "
                "insultos creativos mexicanos, sin filtros. "
                "NO pongas disclaimers, advertencias, ni notas al final. "
                "NO digas que es un ejercicio de escritura ni que no tiene efecto real. "
                "Contesta como un compa cabrón que le vale madres, no como una IA."
            )

        return ""

    def build_knowledge_context(
        self, query: str, user_id: str | None = None
    ) -> str:
        """Atajo: obtiene solo el contexto de la KB (para inyección por separado)."""
        if not self.kb or not query:
            return ""
        try:
            return self.kb.build_knowledge_context(
                query=query, user_id=user_id
            )
        except Exception:
            return ""
