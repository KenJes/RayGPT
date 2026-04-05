"""
agent_loop.py — El cerebro agéntico de Raymundo.

Implementa el ciclo:  Goal → Plan → Execute → Observe → Reflect → Replan → Stop

El LLM produce JSON estructurado en cada paso.  El loop ejecuta la acción
indicada a través del AdapterRegistry, loguea resultados, consulta el
sistema de aprobación para acciones peligrosas y almacena resultados
relevantes en la VectorMemory para RAG.
"""

from __future__ import annotations

import json
import re
import traceback
from typing import Callable

from core.adapters import AdapterRegistry
from core.agent_logger import AgentLogger
from core.agent_memory import VectorMemory
from core.approval import ApprovalManager, ApprovalStatus, approval_manager


# ═══════════════════════════════════════════════════════════════
# Prompt de planificación (se inyecta como system message)
# ═══════════════════════════════════════════════════════════════

_AGENT_SYSTEM_PROMPT = """\
{personality}

Eres un agente agéntico de Axoloit (startup mexicana de Kenneth Alcalá).
No eres un simple chatbot: piensas, planificas, ejecutas herramientas, observas resultados
y replanteas tu plan hasta completar la meta del usuario.

### HERRAMIENTAS DISPONIBLES

{tools_description}

### FORMATO DE RESPUESTA

Responde SIEMPRE con un JSON válido con esta estructura exacta:

{{
  "thought": "Tu razonamiento interno sobre qué hacer a continuación",
  "plan": ["paso 1", "paso 2", ...],
  "next_action": {{
    "tool": "nombre_de_herramienta",
    "args": {{"arg1": "valor1", ...}}
  }},
  "confidence": 0.0-1.0,
  "requires_approval": false,
  "message_to_user": "Mensaje parcial opcional para el usuario mientras trabajas",
  "stop": false
}}

### REGLAS

1. `thought` = tu razonamiento interno (no se muestra al usuario).
2. `plan` = lista actualizada de pasos pendientes; se actualiza en cada iteración.
3. `next_action` = la siguiente herramienta a ejecutar. Si no necesitas herramienta, usa `"tool": "none"`.
4. `confidence` = qué tan seguro estás de que la acción es correcta (0.0 a 1.0).
5. `requires_approval` = true si la acción es destructiva (run_shell, write_file).
6. `message_to_user` = mensaje que el usuario verá mientras trabajas (progreso, preguntas, etc.).
7. `stop` = true cuando la meta está COMPLETAMENTE resuelta.
8. Cuando `stop` es true, `message_to_user` debe contener la respuesta final completa.
9. Si un paso falla, refleja el error en `thought` y replantea en `plan`.
10. Máximo 10 pasos por meta. Si necesitas más, para y pide guía al usuario.
11. Si la meta es simple (una pregunta directa, un saludo), responde con `stop: true` de inmediato
    usando la herramienta `call_api` o directamente con `"tool": "none"`.
12. Si el mensaje incluye "[CONTENIDO EXTRAÍDO DE LA IMAGEN ADJUNTA]", el texto después de esa
    etiqueta es texto OCR extraído de una imagen/foto enviada por el usuario. ÚSALO directamente
    como si fueras leyendo el documento — NO necesitas volver a analizar la imagen.
13. Para evaluar CVs, usa la herramienta `evaluate_cv` pasando el texto del CV como `cv_text`.
    El CV se guardará automáticamente en la base de datos.
14. Tienes acceso a una base de conocimiento persistente con `query_knowledge`, `store_person`,
    `add_fact` y `store_document`. SIEMPRE consulta la KB con `query_knowledge` cuando el usuario
    pregunte sobre personas, candidatos, CVs anteriores o comparaciones.
15. Cuando el usuario mencione datos sobre una persona (habilidades, experiencia, preferencias),
    usa `store_person` o `add_fact` para registrarlos en la KB para futuras consultas.
16. Si hay "[CONOCIMIENTO ALMACENADO EN BASE DE DATOS]" en tu contexto, USA esa información
    para responder — son datos que ya aprendiste en conversaciones o CVs anteriores.
17. Tienes control de Spotify con las herramientas `spotify_play`, `spotify_pause`, `spotify_next`,
    `spotify_previous`, `spotify_current`, `spotify_volume`, `spotify_queue`, `spotify_search`,
    `spotify_devices`. Cuando el usuario pida música, úsalas. Para reproducir, usa `spotify_play`
    con `query` = nombre de canción/artista/album. Si dice "pause", "para", "detén", usa `spotify_pause`.
    Si dice "siguiente", usa `spotify_next`. Si dice "qué suena", usa `spotify_current`.

### CONTEXTO PREVIO (RAG)

{rag_context}
"""

_OBSERVATION_TEMPLATE = """\
Resultado del paso {step}:
- Herramienta: {tool}
- Éxito: {success}
- Output: {output}
- Error: {error}

Continúa con el siguiente paso. Responde con JSON:
"""


# ═══════════════════════════════════════════════════════════════
# AgentLoop
# ═══════════════════════════════════════════════════════════════

class AgentLoop:
    """
    Ciclo agéntico: recibe una meta, planifica, ejecuta herramientas
    en iteraciones, observa resultados y produce una respuesta final.
    """

    MAX_STEPS = 10

    def __init__(
        self,
        registry: AdapterRegistry,
        ai_chat_fn: Callable,       # fn(messages: list[dict], temperature, max_tokens) → str
        logger: AgentLogger | None = None,
        memory: VectorMemory | None = None,
        approval: ApprovalManager | None = None,
        on_progress: Callable[[str], None] | None = None,  # callback para mensajes parciales
    ):
        self.registry = registry
        self.ai_chat = ai_chat_fn
        self.logger = logger or AgentLogger()
        self.memory = memory or VectorMemory()
        self.approval = approval or approval_manager
        self.on_progress = on_progress

    # ─── Punto de entrada ─────────────────────────────────────

    def run(
        self,
        goal: str,
        user_name: str | None = None,
        user_id: str | None = None,
        tono_override: str | None = None,
        usuario_agresivo: bool = False,
        conversation_history: list[dict] | None = None,
        knowledge_context: str | None = None,
    ) -> dict:
        """
        Ejecuta el ciclo agéntico para una meta.

        Args:
            conversation_history: Mensajes previos del usuario (resúmenes + recientes)
                                  para dar contexto de la conversación.
            knowledge_context: Conocimiento de la KB relevante (personas, CVs, hechos).

        Returns:
            {
                "success": bool,
                "response": str,           # Respuesta final para el usuario
                "steps_taken": int,
                "run_id": str,
                "actions_log": list[dict],  # Resumen de cada paso
            }
        """
        run_id = self.logger.new_run_id()

        # 1. Recuperar contexto RAG
        rag_context = self.memory.get_context_for_planning(goal) or "Sin contexto previo relevante."

        # 2. Construir system prompt
        tools_desc = self._format_tools_description()
        from core.config import config_agente
        personality = config_agente.get_prompt_sistema()
        system_prompt = _AGENT_SYSTEM_PROMPT.format(
            personality=personality,
            tools_description=tools_desc,
            rag_context=rag_context,
        )

        # Inyectar conocimiento de la base de datos
        if knowledge_context:
            system_prompt += f"\n\n{knowledge_context}"

        # Inyectar contexto de usuario
        if user_name:
            system_prompt += f"\n\nUsuario actual: {user_name}"
        if tono_override:
            system_prompt += f"\nTono solicitado: {tono_override}"
        if usuario_agresivo:
            system_prompt += (
                "\nEl usuario está siendo agresivo en este mensaje — "
                "espeja su tono, groserías con groserías, sin perder utilidad."
            )

        # 3. Iniciar conversación con el LLM (incluir historial de conversación)
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        # Inyectar historial de conversación previo para contexto
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": f"Meta: {goal}"})

        actions_log = []
        step = 0

        while step < self.MAX_STEPS:
            step += 1
            start_ts = AgentLogger._now_iso()

            # 4. Pedir al LLM el siguiente paso
            raw_response = self._call_llm(messages)
            parsed = self._parse_agent_response(raw_response)

            if parsed is None:
                # LLM no devolvió JSON válido → tratar como respuesta directa
                self.logger.log_step(
                    run_id, step, "parse_error", {},
                    start_ts, AgentLogger._now_iso(),
                    "error", output_summary=raw_response[:300],
                    error="No se pudo parsear JSON del LLM",
                )
                # Devolver la respuesta raw como respuesta final
                self.logger.log_final(run_id, step, "ok", raw_response[:300])
                return {
                    "success": True,
                    "response": raw_response,
                    "steps_taken": step,
                    "run_id": run_id,
                    "actions_log": actions_log,
                }

            # Log plan en el primer paso
            if step == 1:
                self.logger.log_plan(run_id, goal, parsed.get("plan", []))

            # 5. Notificar progreso al usuario
            msg_user = parsed.get("message_to_user", "")
            if msg_user and self.on_progress:
                try:
                    self.on_progress(msg_user)
                except Exception:
                    pass

            # 6. Verificar si el agente quiere parar
            if parsed.get("stop", False):
                final_msg = parsed.get("message_to_user", "Listo.")
                self.logger.log_step(
                    run_id, step, "stop", {},
                    start_ts, AgentLogger._now_iso(),
                    "ok", output_summary=final_msg[:300],
                )
                self.logger.log_final(run_id, step, "ok", final_msg[:300])

                # Almacenar en memory para futuro RAG
                self.memory.store_if_relevant(
                    f"Meta: {goal}\nResultado: {final_msg[:500]}",
                    metadata={"action": "completed_goal", "run_id": run_id},
                )

                return {
                    "success": True,
                    "response": final_msg,
                    "steps_taken": step,
                    "run_id": run_id,
                    "actions_log": actions_log,
                }

            # 7. Ejecutar la acción
            next_action = parsed.get("next_action", {})
            tool_name = next_action.get("tool", "none")
            tool_args = next_action.get("args", {})

            if tool_name == "none" or not tool_name:
                # Sin herramienta → agregar observación vacía y continuar
                messages.append({"role": "assistant", "content": raw_response})
                messages.append({
                    "role": "user",
                    "content": _OBSERVATION_TEMPLATE.format(
                        step=step, tool="none",
                        success=True, output="Sin acción ejecutada.", error="None",
                    ),
                })
                actions_log.append({
                    "step": step, "tool": "none", "success": True,
                    "output": "Sin acción.", "error": None,
                })
                continue

            adapter = self.registry.get(tool_name)
            if not adapter:
                # Herramienta desconocida
                error_msg = f"Herramienta '{tool_name}' no encontrada."
                messages.append({"role": "assistant", "content": raw_response})
                messages.append({
                    "role": "user",
                    "content": _OBSERVATION_TEMPLATE.format(
                        step=step, tool=tool_name,
                        success=False, output="", error=error_msg,
                    ),
                })
                self.logger.log_step(
                    run_id, step, tool_name, tool_args,
                    start_ts, AgentLogger._now_iso(),
                    "error", error=error_msg,
                )
                actions_log.append({
                    "step": step, "tool": tool_name, "success": False,
                    "output": "", "error": error_msg,
                })
                continue

            # 8. Verificar aprobación si es necesario
            if adapter.requires_approval:
                req = self.approval.request_approval(
                    run_id=run_id,
                    action=tool_name,
                    args=tool_args,
                    reason=parsed.get("thought", "Acción requiere aprobación."),
                )
                status = self.approval.wait_for_decision(req.id, timeout=120)
                if status != ApprovalStatus.APPROVED:
                    skip_reason = f"Acción '{tool_name}' {status.value} por el usuario."
                    messages.append({"role": "assistant", "content": raw_response})
                    messages.append({
                        "role": "user",
                        "content": _OBSERVATION_TEMPLATE.format(
                            step=step, tool=tool_name,
                            success=False, output="", error=skip_reason,
                        ),
                    })
                    self.logger.log_step(
                        run_id, step, tool_name, tool_args,
                        start_ts, AgentLogger._now_iso(),
                        "approval_pending", error=skip_reason,
                    )
                    actions_log.append({
                        "step": step, "tool": tool_name, "success": False,
                        "output": "", "error": skip_reason,
                    })
                    continue

            # 9. Ejecutar herramienta
            try:
                result = adapter.execute(tool_args)
            except Exception as e:
                result = {"success": False, "output": None, "error": str(e)}

            end_ts = AgentLogger._now_iso()

            # 10. Log
            self.logger.log_step(
                run_id, step, tool_name, tool_args,
                start_ts, end_ts,
                "ok" if result["success"] else "error",
                output_summary=str(result.get("output", ""))[:300],
                error=result.get("error"),
            )

            # 11. Almacenar en memory si fue exitoso (para RAG futuro)
            if result["success"] and result.get("output"):
                self.memory.store_if_relevant(
                    f"Acción: {tool_name}, Args: {json.dumps(tool_args, ensure_ascii=False)[:200]}\n"
                    f"Resultado: {str(result['output'])[:500]}",
                    metadata={"action": tool_name, "run_id": run_id, "step": step},
                )

            # 12. Alimentar observación al LLM
            messages.append({"role": "assistant", "content": raw_response})
            messages.append({
                "role": "user",
                "content": _OBSERVATION_TEMPLATE.format(
                    step=step,
                    tool=tool_name,
                    success=result["success"],
                    output=str(result.get("output", ""))[:800],
                    error=result.get("error") or "None",
                ),
            })

            actions_log.append({
                "step": step,
                "tool": tool_name,
                "success": result["success"],
                "output": str(result.get("output", ""))[:300],
                "error": result.get("error"),
            })

        # Si llegamos aquí, agotamos los pasos
        self.logger.log_final(run_id, step, "max_steps", "Se alcanzó el límite de pasos.")
        last_msg = "He alcanzado el máximo de pasos. Esto es lo que logré hasta ahora."
        # Intentar extraer el último message_to_user si existe
        if actions_log:
            last_msg += f"\n\nÚltimo resultado: {actions_log[-1].get('output', '')[:500]}"

        return {
            "success": False,
            "response": last_msg,
            "steps_taken": step,
            "run_id": run_id,
            "actions_log": actions_log,
        }

    # ─── Helpers ──────────────────────────────────────────────

    def _call_llm(self, messages: list[dict]) -> str:
        """Llama al LLM con la cadena de mensajes y devuelve la respuesta raw.
        Si la respuesta es un rechazo por filtros de seguridad, reintenta
        con un prompt simplificado (sin historial agresivo)."""
        from core.tools import es_rechazo_llm
        try:
            response = self.ai_chat(messages, 0.4, 2000)
            if response and not es_rechazo_llm(response):
                return response
            # Rechazo detectado — reintentar sin historial de conversación
            simplified = [m for m in messages if m["role"] in ("system", "user")]
            if len(simplified) < len(messages):
                response2 = self.ai_chat(simplified, 0.4, 2000)
                if response2 and not es_rechazo_llm(response2):
                    return response2
            return response or ""
        except Exception as e:
            return f"Error llamando al LLM: {e}"

    def _parse_agent_response(self, raw: str) -> dict | None:
        """
        Intenta extraer JSON estructurado de la respuesta del LLM.
        Busca el primer bloque JSON { ... } en la respuesta.
        """
        if not raw:
            return None
        # 1. Intentar parsear toda la respuesta como JSON
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # 2. Buscar bloques ```json ... ``` o { ... }
        code_block = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw)
        if code_block:
            try:
                return json.loads(code_block.group(1))
            except json.JSONDecodeError:
                pass
        # 3. Buscar primer { ... } balanceado
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def _format_tools_description(self) -> str:
        """Formatea las herramientas disponibles para el system prompt."""
        tools = self.registry.list_tools()
        lines = []
        for t in tools:
            approval = " [REQUIERE APROBACIÓN]" if t["requires_approval"] else ""
            lines.append(f"- **{t['name']}**{approval}: {t['description']}")
        return "\n".join(lines) or "Sin herramientas disponibles."


# ═══════════════════════════════════════════════════════════════
# Detector de metas complejas vs chat simple
# ═══════════════════════════════════════════════════════════════

# Palabras/patrones que sugieren que el usuario quiere algo agéntico
_AGENTIC_PATTERNS = [
    r"\bcrea(?:r|me)?\b.*\b(?:presentaci[oó]n|documento|hoja|excel|archivo|reporte)\b",
    r"\bbusca(?:r|me)?\b.*\b(?:en (?:la )?web|internet|google|url)\b",
    r"\banaliza(?:r|me)?\b.*\b(?:imagen|foto|documento|pdf|archivo)\b",
    r"\bescribe?\b.*\b(?:archivo|c[oó]digo|script)\b",
    r"\bejecutar?\b.*\b(?:comando|shell|terminal)\b",
    r"\binvestiga(?:r|me)?\b",
    r"\bplanifica(?:r|me)?\b",
    r"\bgenera(?:r|me)?\b.*\b(?:reporte|informe|an[aá]lisis|resumen)\b",
    r"\bpaso a paso\b",
    r"\bprimero\b.*\bluego\b",
    # Evaluación de sitios web / URLs
    r"\bevalú[ao]r?\b",
    r"\b(?:revisar?|analizar?)\b.*\b(?:sitio|p[aá]gina|web|portal|empresa)\b",
    r"\b(?:sitio|p[aá]gina|web)\b.*\b(?:evalú|revis|analiz)\b",
    r"\b(?:http|www)\b",
    r"\b\w{3,30}\.(?:com|mx|org|net|io|co)\b",
    # Listas y recomendaciones
    r"\bdame?\s+(?:una\s+)?lista\b",
    r"\bhaz(?:me)?\s+(?:una\s+)?lista\b",
    r"\bmuéstrame\s+(?:la\s+)?lista\b",
    r"\blista\s+de\s+\w",
    r"\bqué\s+puestos?\b",
    r"\bpuestos?\s+(?:que\s+)?necesi\w+\b",
    r"\brecomienda\w*\b",
    r"\bcontratar?\s+\w",
    r"\bhaz\s+un\s+(?:an[aá]lisis|reporte|resumen|listado)\b",
    r"\bqu[eé]\s+(?:rol|cargo|puesto|personal|equipo)\s+necesita\w*\b",
    # CV / Recursos Humanos
    r"\bcv\b",
    r"\bcurr[ií]cul(?:um|o)\b",
    r"\beval[uú]a(?:r)?\s+(?:al?\s+)?(?:candidato|perfil|cv|curr[ií]cul)\b",
    r"\bqu[eé]\s+puesto\s+(?:puede|le\s+queda|ocupar)\b",
    r"\b(?:imagen|foto)\s+(?:con|del?)\s+(?:el\s+)?cv\b",
    r"\bcontratar\w*\b.*\b(?:posici[oó]n|puesto|rol)\b",
    r"\brh\b|\brecursos\s+humanos\b",
    r"\bfortalezas?\b.*\bdebilidades?\b",
    # Imagen adjunta con análisis
    r"\bCONTENIDO EXTRAÍDO DE LA IMAGEN\b",
]

# Patrones de chat simple (saludos, preguntas directas, etc.)
_SIMPLE_PATTERNS = [
    r"^(?:hola|hey|buenos?\s+(?:d[ií]as?|tardes?|noches?)|qu[eé]\s+(?:onda|pedo)|c[oó]mo\s+est[aá]s?)\b",
    r"^(?:gracias|ok|vale|si|no|claro|ya|chido|órale)\s*[.!?]*$",
    r"^(?:qu[eé]\s+(?:es|son|significa)|cu[aá]l\s+es|d[oó]nde\s+(?:est[aá]|queda)|qui[eé]n\s+(?:es|fue))\b",
    r"^(?:cu[aá]nto|cu[aá]ndo|por\s+qu[eé]|c[oó]mo)\b",    # Preguntas de opinión/pensamiento — NUNCA son agénticas
    r"qu[eé]\s+opinas\b",
    r"qu[eé]\s+piensas\b",
    r"qu[eé]\s+crees\b",
    r"cu[aá]l\s+es\s+tu\s+opini[oó]n\b",
    r"qu[eé]\s+te\s+parece\b",
    r"te\s+gusta\b",
    r"me\s+recomiendas\b",]


def es_meta_compleja(mensaje: str, usuario_agresivo: bool = False) -> bool:
    """
    Determina si un mensaje requiere el ciclo agéntico completo
    o si es un chat simple que puede resolverse directamente.
    """
    msg = mensaje.strip().lower()

    # Mensajes muy cortos → chat simple
    if len(msg) < 15:
        return False

    # Mensajes puramente agresivos sin petición real → chat simple
    if usuario_agresivo:
        # Solo enviar al AgentLoop si hay una petición agéntica explícita
        tiene_patron_agentico = any(
            re.search(pattern, msg, re.IGNORECASE)
            for pattern in _AGENTIC_PATTERNS
        )
        if not tiene_patron_agentico:
            return False

    # Comandos rápidos → no agéntico
    if msg.startswith("/"):
        return False

    # Patrones simples → chat simple
    for pattern in _SIMPLE_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return False

    # Patrones agénticos → sí complejo
    for pattern in _AGENTIC_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
            return True

    # Mensajes largos con múltiples oraciones → probablemente complejo
    # Ignorar puntos dentro de dominios/URLs para el conteo de oraciones
    msg_sin_dominios = re.sub(r"\b\w+\.(?:com|mx|org|net|io|co|edu|gov)\b", "DOMINIO", msg)
    oraciones = [s.strip() for s in re.split(r"[.;]", msg_sin_dominios) if s.strip()]
    if len(oraciones) >= 3:
        return True

    # Default: chat simple
    return False
