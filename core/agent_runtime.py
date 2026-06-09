"""Runtime central para solicitudes agénticas.

Normaliza una solicitud de texto, recupera contexto persistente,
inyecta conocimiento relevante y ejecuta el AgentLoop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import re

from core.agent_loop import AgentLoop
from core.config import OUTPUT_DIR
from core.context_manager import ContextManager
from core.conversation_db import ConversationDB
from core.knowledge_db import KnowledgeBase

logger = logging.getLogger(__name__)


_GOOGLE_EXPORTERS = {
    "documento": "exportar_documento_docx",
    "hoja_calculo": "exportar_hoja_calculo_xlsx",
    "presentacion": "exportar_presentacion_pptx",
}


@dataclass(slots=True)
class AgentRequest:
    text: str
    user_id: str = "local_user"
    user_name: str | None = None
    channel: str = "unknown"
    tono_override: str | None = None
    usuario_agresivo: bool = False
    conversation_history: list[dict] | None = None
    knowledge_context: str | None = None


@dataclass(slots=True)
class AgentResponse:
    success: bool
    response: str
    used_agent_loop: bool
    run_id: str | None = None
    steps_taken: int = 0
    actions_log: list[dict] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)


class AgentRuntime:
    """Orquesta el flujo agent-first compartido entre canales."""

    def __init__(
        self,
        gestor,
        agent_loop: AgentLoop,
        conversation_db: ConversationDB | None = None,
        knowledge_base: KnowledgeBase | None = None,
        context_manager: ContextManager | None = None,
    ):
        self.gestor = gestor
        self.agent_loop = agent_loop
        self.conversation_db = conversation_db or ConversationDB()
        self.knowledge_base = knowledge_base
        self.context_manager = context_manager or ContextManager(
            knowledge_base=knowledge_base,
            memory_system=getattr(gestor, "memory", None),
        )

    def handle_text(self, request: AgentRequest) -> AgentResponse:
        text = request.text.strip()
        if not text:
            return AgentResponse(
                success=False,
                response="",
                used_agent_loop=False,
            )

        user_id = request.user_id or "local_user"
        if getattr(self.gestor, "memory", None):
            self.gestor.memory.aprender_vocabulario(text, user_id=user_id)

        conversation_history = request.conversation_history
        if conversation_history is None:
            conversation_history = self.conversation_db.build_context_messages(
                user_id,
                summarize_fn=self._summarize_for_context,
            )

        knowledge_context = request.knowledge_context
        if knowledge_context is None and self.context_manager:
            knowledge_context = self.context_manager.build_knowledge_context(
                query=text,
                user_id=user_id,
            )
        if knowledge_context and len(knowledge_context) > 2500:
            knowledge_context = knowledge_context[:2500]

        result = self.agent_loop.run(
            goal=text,
            user_name=request.user_name,
            user_id=user_id,
            channel=request.channel,
            tono_override=request.tono_override,
            usuario_agresivo=request.usuario_agresivo,
            conversation_history=conversation_history,
            knowledge_context=knowledge_context,
        )

        response_text = (result.get("response") or "").strip()
        if not response_text:
            response_text = "No pude generar una respuesta."

        artifacts = self._materialize_artifacts(self._collect_artifacts(result))

        self._persist_turn(user_id, text, response_text)

        return AgentResponse(
            success=bool(result.get("success", False)),
            response=response_text,
            used_agent_loop=True,
            run_id=result.get("run_id"),
            steps_taken=int(result.get("steps_taken", 0) or 0),
            actions_log=result.get("actions_log", []),
            artifacts=artifacts,
        )

    def clear_user_context(self, user_id: str):
        self.conversation_db.clear_history(user_id)
        if getattr(self.gestor, "memory", None):
            try:
                self.gestor.memory.clear_user_context(user_id)
            except Exception as exc:
                logger.warning("No se pudo limpiar memoria del usuario %s: %s", user_id, exc)

    def _persist_turn(self, user_id: str, user_text: str, assistant_text: str):
        self.conversation_db.add_message(user_id, "user", user_text)
        self.conversation_db.add_message(user_id, "assistant", assistant_text)

    def _summarize_for_context(self, prompt: str) -> str:
        try:
            return self.gestor._consultar_ia(prompt, temperature=0.3, max_tokens=400)
        except Exception as exc:
            logger.warning("No se pudo resumir contexto: %s", exc)
            return ""

    @staticmethod
    def _collect_artifacts(result: dict) -> list[dict]:
        artifacts = []
        seen_ids = set()

        for artifact in result.get("artifacts", []) or []:
            identity = AgentRuntime._artifact_identity(artifact)
            if isinstance(artifact, dict) and identity and identity not in seen_ids:
                artifacts.append(dict(artifact))
                seen_ids.add(identity)

        for action in result.get("actions_log", []) or []:
            for artifact in action.get("artifacts", []) or []:
                identity = AgentRuntime._artifact_identity(artifact)
                if isinstance(artifact, dict) and identity and identity not in seen_ids:
                    artifacts.append(dict(artifact))
                    seen_ids.add(identity)

        return artifacts

    @staticmethod
    def _artifact_identity(artifact: dict) -> str | None:
        if not isinstance(artifact, dict):
            return None
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

    def _materialize_artifacts(self, artifacts: list[dict]) -> list[dict]:
        materialized = []
        for artifact in artifacts:
            if isinstance(artifact, dict):
                materialized.append(self._materialize_google_artifact(dict(artifact)))
        return materialized

    def _materialize_google_artifact(self, artifact: dict) -> dict:
        if artifact.get("path"):
            return artifact
        if artifact.get("provider") != "google_workspace":
            return artifact

        google_client = getattr(self.gestor, "google", None)
        artifact_type = str(artifact.get("tipo") or artifact.get("kind") or "").strip().lower()
        google_id = artifact.get("google_id")
        exporter_name = _GOOGLE_EXPORTERS.get(artifact_type)
        exporter = getattr(google_client, exporter_name, None) if google_client and exporter_name else None
        if not callable(exporter) or not google_id:
            return artifact

        output_path = self._build_export_output_path(artifact)
        try:
            exported_path = exporter(str(google_id), str(output_path))
        except Exception as exc:
            logger.warning("No se pudo exportar artifact Google %s: %s", artifact_type, exc)
            return artifact

        if not exported_path:
            return artifact

        resolved_path = Path(str(exported_path)).resolve()
        materialized = dict(artifact)
        materialized["path"] = str(resolved_path)
        materialized["filename"] = resolved_path.name
        materialized["title"] = materialized.get("title") or resolved_path.stem
        materialized["tipo"] = materialized.get("tipo") or resolved_path.suffix.lstrip(".")
        return materialized

    def _build_export_output_path(self, artifact: dict) -> Path:
        export_dir = OUTPUT_DIR / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        filename = self._sanitize_export_filename(
            artifact.get("filename"),
            default_stem=artifact.get("title") or artifact.get("tipo") or "artifact",
            default_suffix=f".{artifact.get('export_format') or 'bin'}",
        )
        return self._unique_export_path(export_dir, filename)

    @staticmethod
    def _sanitize_export_filename(filename: str | None, *, default_stem: str, default_suffix: str) -> str:
        raw_name = Path(str(filename or "").strip()).name
        stem = Path(raw_name).stem if raw_name else default_stem
        suffix = Path(raw_name).suffix.lower() if raw_name else default_suffix

        safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or default_stem
        safe_suffix = re.sub(r"[^A-Za-z0-9.]+", "", suffix).lower() or default_suffix
        if not safe_suffix.startswith("."):
            safe_suffix = f".{safe_suffix}"
        return f"{safe_stem}{safe_suffix}"

    @staticmethod
    def _unique_export_path(base_dir: Path, filename: str) -> Path:
        candidate = (base_dir / filename).resolve()
        output_root = OUTPUT_DIR.resolve()
        if not str(candidate).startswith(str(output_root)):
            raise ValueError(f"Solo se permite escribir bajo {OUTPUT_DIR}")
        if not candidate.exists():
            return candidate

        stem = candidate.stem
        suffix = candidate.suffix
        for index in range(2, 1000):
            alternative = candidate.with_name(f"{stem}_{index}{suffix}")
            if not alternative.exists():
                return alternative
        raise ValueError("No se pudo generar un nombre de exportación único.")