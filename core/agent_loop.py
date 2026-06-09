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
18. Si el usuario pide contenido puramente textual como explicaciones, tutoriales, prácticas guiadas,
    brainstorming, planes, ejemplos o redacción, responde con `call_api` o con `"tool": "none"`.
    NO uses herramientas de creación de archivos salvo que el usuario pida explícitamente crear,
    guardar, exportar o entregar un archivo, notebook o entregable.
19. Cuando uses `create_document`, `create_presentation` o `create_spreadsheet`, el argumento principal
    esperado es `tema` y el opcional es `detalles`.
    Si el usuario pide `excel`, `xlsx`, `sheet` o `google sheet`, usa `create_spreadsheet`.
    Si pide `documento`, `docx`, `word` o `google docs`, usa `create_document`.
    Si pide `slides`, `ppt`, `pptx` o `powerpoint`, usa `create_presentation`.
20. Para notebooks locales usa `create_notebook`. Para archivos locales de texto como html, css,
    js, ts, py, php, json, md, txt, xml, yaml, yml, sql o csv usa `create_local_artifact`.
    `create_local_artifact` también puede crear varios archivos relacionados en una sola llamada con
    `files` = lista de especificaciones de archivo. Usa `open_local_artifact` solo si el usuario pidió
    explícitamente abrir el recurso y solo en canales locales de escritorio.
    Si el usuario pidió un archivo descargable o exportable, no respondas con tablas o instrucciones para
    copiar y pegar manualmente; crea el recurso correspondiente para que el canal pueda exportarlo o adjuntarlo.
    NO uses `write_file` para responder chats, tutoriales, notebooks, prácticas guiadas o ejemplos.
    Solo úsalo como fallback si el usuario pide explícitamente guardar un archivo local y no existe
    una herramienta especializada que aplique.
21. Nunca inventes enlaces, IDs, nombres de archivo, documentos creados ni acciones completadas.
    Solo menciona URLs o recursos externos si una herramienta los devolvió realmente en `Output`.
    Si no se creó ningún recurso, entrega el contenido completo directamente en `message_to_user`.

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

_FILE_REQUEST_INTENT_PATTERNS = (
    r"\b(crea(?:r)?|genera(?:r)?|haz(?:me|lo|la)?|hacer|guarda(?:r)?|exporta(?:r)?|escribe(?:r)?|arma(?:r)?|prepara(?:r)?|construye(?:r)?|dame|entr[eé]ga(?:me|r)?)\b",
)

_FILE_OPEN_INTENT_PATTERNS = (
    r"\b(abre(?:lo|la|me)?|abrir|open|muestra(?:me|r)?|visualiza(?:r)?|lanza(?:r)?)\b",
)

_LOCAL_OPEN_CHANNELS = {"desktop", "desktop_gui", "local"}

_FILE_CREATION_TOOL_PATTERNS = {
    "create_document": (
        r"\b(documento|google docs|doc|docs)\b",
    ),
    "create_presentation": (
        r"\b(presentaci[oó]n|diapositivas|slides|powerpoint|pptx)\b",
    ),
    "create_spreadsheet": (
        r"\b(hoja de c[aá]lculo|spreadsheet|excel|xlsx|sheet)\b",
    ),
    "create_notebook": (
        r"\b(ipynb|jupyter|notebook|colab|cuaderno)\b",
    ),
    "create_local_artifact": (
        r"\b(archivo|fichero|script|plantilla|landing page|p[aá]gina web|sitio web)\b",
        r"\.(?:html|css|js|ts|py|php|json|md|txt|xml|yaml|yml|sql|csv)\b",
        r"\b(html|css|javascript|js|typescript|ts|php|json|markdown|md|xml|yaml|yml|sql|csv)\b",
        r"\b(?:en|como)\s+(?:python|py)\b",
    ),
    "write_file": (
        r"\b(archivo|fichero|script|plantilla|notebook|ipynb|jupyter)\b",
        r"\.(?:html|css|js|ts|py|php|json|md|txt|xml|yaml|yml|sql|csv|ipynb)\b",
    ),
    "open_local_artifact": (
        r"\b(archivo|fichero|script|plantilla|notebook|ipynb|jupyter|landing page|p[aá]gina web|sitio web)\b",
        r"\.(?:html|css|js|ts|py|php|json|md|txt|xml|yaml|yml|sql|csv|ipynb)\b",
        r"\b(html|css|javascript|js|typescript|ts|python|py|php|json|markdown|md|xml|yaml|yml|sql|csv)\b",
    ),
}


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
        channel: str | None = None,
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
        # Inyectar historial de conversación previo: 8 msgs = ~4 turnos de contexto
        if conversation_history:
            messages.extend(conversation_history[-8:])
        messages.append({"role": "user", "content": f"Meta: {goal}"})

        actions_log = []
        artifacts = []
        step = 0

        while step < self.MAX_STEPS:
            step += 1
            start_ts = AgentLogger._now_iso()

            # 4. Pedir al LLM el siguiente paso
            raw_response = self._call_llm(messages)
            parsed = self._parse_agent_response(raw_response)

            if parsed is None:
                # LLM no devolvió JSON válido → rescatar mensaje visible si existe
                recovered_message = self._extract_message_to_user(raw_response)
                final_response = recovered_message or raw_response
                self.logger.log_step(
                    run_id, step, "parse_error", {},
                    start_ts, AgentLogger._now_iso(),
                    "error", output_summary=final_response[:300],
                    error="No se pudo parsear JSON del LLM",
                )
                self.logger.log_final(run_id, step, "ok", final_response[:300])
                return {
                    "success": True,
                    "response": final_response,
                    "steps_taken": step,
                    "run_id": run_id,
                    "actions_log": actions_log,
                    "artifacts": artifacts,
                }

            # Log plan en el primer paso
            if step == 1:
                self.logger.log_plan(run_id, goal, parsed.get("plan", []))

            # 5. Verificar si el agente quiere parar
            msg_user = parsed.get("message_to_user", "")
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
                    "artifacts": artifacts,
                }

            # 6. Preparar la acción
            next_action = parsed.get("next_action", {})
            tool_name = next_action.get("tool", "none")
            tool_args = next_action.get("args", {})

            if (tool_name == "none" or not tool_name) and str(msg_user).strip():
                final_msg = str(msg_user).strip()
                self.logger.log_step(
                    run_id, step, "handoff", {},
                    start_ts, AgentLogger._now_iso(),
                    "ok", output_summary=final_msg[:300],
                )
                self.logger.log_final(run_id, step, "awaiting_user", final_msg[:300])
                return {
                    "success": True,
                    "response": final_msg,
                    "steps_taken": step,
                    "run_id": run_id,
                    "actions_log": actions_log,
                    "artifacts": artifacts,
                }

            # 7. Notificar progreso al usuario solo si el loop seguirá trabajando
            if msg_user and self.on_progress:
                try:
                    self.on_progress(msg_user)
                except Exception:
                    pass

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

            allowed, block_reason = self._can_execute_tool_for_goal(goal, tool_name, channel=channel)
            if not allowed:
                messages.append({"role": "assistant", "content": raw_response})
                messages.append({
                    "role": "user",
                    "content": _OBSERVATION_TEMPLATE.format(
                        step=step,
                        tool=tool_name,
                        success=False,
                        output="",
                        error=block_reason,
                    ),
                })
                self.logger.log_step(
                    run_id, step, tool_name, tool_args,
                    start_ts, AgentLogger._now_iso(),
                    "error", error=block_reason,
                )
                actions_log.append({
                    "step": step, "tool": tool_name, "success": False,
                    "output": "", "error": block_reason,
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

            result_artifacts = [
                dict(item)
                for item in (result.get("artifacts") or [])
                if isinstance(item, dict) and self._artifact_identity(item)
            ]
            artifacts = self._merge_artifacts(artifacts, result_artifacts)

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
                "artifacts": result_artifacts,
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
            "artifacts": artifacts,
        }

    # ─── Helpers ──────────────────────────────────────────────

    def _can_execute_tool_for_goal(self, goal: str, tool_name: str, channel: str | None = None) -> tuple[bool, str | None]:
        if tool_name not in _FILE_CREATION_TOOL_PATTERNS:
            return True, None
        normalized_channel = str(channel or "").strip().lower()
        if tool_name == "open_local_artifact" and normalized_channel not in _LOCAL_OPEN_CHANNELS:
            return False, "La apertura automática de archivos solo se permite en canales locales de escritorio."
        if self._goal_explicitly_requests_tool(goal, tool_name):
            return True, None
        return (
            False,
            (
                f"La meta no pidió explícitamente crear o guardar un recurso con '{tool_name}'. "
                "Entrega el contenido directamente o espera una solicitud explícita de archivo."
            ),
        )

    def _goal_explicitly_requests_tool(self, goal: str, tool_name: str) -> bool:
        normalized_goal = str(goal or "").lower()
        if not normalized_goal:
            return False

        intent_patterns = _FILE_OPEN_INTENT_PATTERNS if tool_name == "open_local_artifact" else _FILE_REQUEST_INTENT_PATTERNS
        has_creation_intent = any(
            re.search(pattern, normalized_goal, re.IGNORECASE)
            for pattern in intent_patterns
        )
        if not has_creation_intent:
            return False

        return any(
            re.search(pattern, normalized_goal, re.IGNORECASE)
            for pattern in _FILE_CREATION_TOOL_PATTERNS.get(tool_name, ())
        )

    def _merge_artifacts(self, current: list[dict], new_items: list[dict]) -> list[dict]:
        merged = [dict(item) for item in current if isinstance(item, dict)]
        seen_ids = {self._artifact_identity(item) for item in merged if self._artifact_identity(item)}
        for artifact in new_items:
            identity = self._artifact_identity(artifact)
            if identity and identity not in seen_ids:
                merged.append(dict(artifact))
                seen_ids.add(identity)
        return merged

    def _artifact_identity(self, artifact: dict) -> str | None:
        for key in ("path", "google_id", "google_url"):
            value = artifact.get(key)
            if value:
                return str(value)
        provider = artifact.get("provider")
        artifact_type = artifact.get("tipo") or artifact.get("kind")
        title = artifact.get("title")
        if provider and artifact_type and title:
            return f"{provider}:{artifact_type}:{title}"
        return None

    def _call_llm(self, messages: list[dict]) -> str:
        """Llama al LLM con la cadena de mensajes y devuelve la respuesta raw.
        Comprime el historial antes de enviar para evitar overflow 413/contexto enorme.
        Si la respuesta es un rechazo por filtros de seguridad, reintenta
        con un prompt simplificado (sin historial agresivo)."""
        from core.tools import es_rechazo_llm
        from core.ai_clients import EdgeRouter
        # Comprimir a 10k chars — suficiente para plan+JSON de cada paso
        # Mantener bajo para no agotar RPM de Groq (30 RPM) ni Mistral (1 RPM free)
        compressed = EdgeRouter.compress_messages(messages, max_chars=10000)
        try:
            # max_tokens=800: el JSON de plan/acción rara vez supera 600 tokens.
            # Bajar este valor reduce consumo de RPM en todos los modelos.
            response = self.ai_chat(compressed, 0.4, 800)
            if response and not es_rechazo_llm(response):
                return response
            # Rechazo detectado — reintentar sin historial de conversación
            simplified = [m for m in compressed if m["role"] in ("system", "user")]
            if len(simplified) < len(compressed):
                response2 = self.ai_chat(simplified, 0.4, 800)
                if response2 and not es_rechazo_llm(response2):
                    return response2
            return response or ""
        except Exception as e:
            return f"Error llamando al LLM: {e}"

    def _parse_agent_response(self, raw: str) -> dict | None:
        """
        Intenta extraer JSON estructurado de la respuesta del LLM.
        Soporta respuestas con uno o varios objetos JSON concatenados.
        """
        if not raw:
            return None

        def _scan_dicts(text: str) -> list[dict]:
            decoder = json.JSONDecoder()
            found: list[dict] = []
            idx = 0
            while idx < len(text):
                start = text.find("{", idx)
                if start == -1:
                    break
                try:
                    parsed, end = decoder.raw_decode(text[start:])
                except json.JSONDecodeError:
                    idx = start + 1
                    continue
                if isinstance(parsed, dict):
                    found.append(parsed)
                idx = start + end
            return found

        # 1. Intentar parsear toda la respuesta como JSON
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 2. Buscar bloques ```json ... ``` y escanear múltiples objetos.
        code_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
        if code_block:
            candidates = _scan_dicts(code_block.group(1))
            if candidates:
                return candidates[-1]

        # 3. Escanear todo el texto y tomar el último objeto válido.
        candidates = _scan_dicts(raw)
        if candidates:
            return candidates[-1]

        return None

    def _extract_message_to_user(self, raw: str) -> str | None:
        """Extrae `message_to_user` incluso si el JSON está malformado."""
        if not raw:
            return None

        match = re.search(
            r'"message_to_user"\s*:\s*"((?:\\.|[^"\\])*)"',
            raw,
            re.DOTALL,
        )
        if not match:
            return None

        encoded = f'"{match.group(1)}"'
        try:
            return json.loads(encoded)
        except json.JSONDecodeError:
            return (
                match.group(1)
                .replace(r'\n', '\n')
                .replace(r'\"', '"')
                .replace(r'\\', '\\')
            )

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
