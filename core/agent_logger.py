"""
agent_logger.py — Logging JSONL de acciones del agente.

Cada step del agent loop se registra como una línea JSON en data/agent_logs.jsonl
con la estructura:
    {id, step_id, action, args, start_ts, end_ts, status, output_summary, error}
"""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.config import DATA_DIR

LOG_FILE = DATA_DIR / "agent_logs.jsonl"


class AgentLogger:
    """Escribe un log JSONL de cada acción del agente."""

    def __init__(self, log_file: Path | None = None):
        self.log_file = log_file or LOG_FILE
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    # ─── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _short_id() -> str:
        return uuid.uuid4().hex[:12]

    # ─── Logging ───────────────────────────────────────────────

    def log_step(
        self,
        run_id: str,
        step_id: int,
        action: str,
        args: dict,
        start_ts: str,
        end_ts: str,
        status: str,           # "ok" | "error" | "approval_pending" | "skipped"
        output_summary: str = "",
        error: str | None = None,
    ):
        entry = {
            "id": run_id,
            "step_id": step_id,
            "action": action,
            "args": _safe_serialize(args),
            "start_ts": start_ts,
            "end_ts": end_ts,
            "status": status,
            "output_summary": output_summary[:500],
            "error": error,
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # No interrumpir el agente por fallo de logging

    def log_plan(self, run_id: str, goal: str, plan: list[str]):
        entry = {
            "id": run_id,
            "step_id": 0,
            "action": "plan",
            "args": {"goal": goal},
            "start_ts": self._now_iso(),
            "end_ts": self._now_iso(),
            "status": "ok",
            "output_summary": json.dumps(plan, ensure_ascii=False)[:500],
            "error": None,
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def log_final(self, run_id: str, step_count: int, outcome: str, summary: str):
        entry = {
            "id": run_id,
            "step_id": step_count + 1,
            "action": "final",
            "args": {},
            "start_ts": self._now_iso(),
            "end_ts": self._now_iso(),
            "status": outcome,
            "output_summary": summary[:500],
            "error": None,
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def new_run_id(self) -> str:
        return self._short_id()

    # ─── Lectura (para debug) ─────────────────────────────────

    def get_last_runs(self, n: int = 5) -> list[dict]:
        """Lee las últimas n líneas del log."""
        if not self.log_file.exists():
            return []
        try:
            lines = self.log_file.read_text(encoding="utf-8").strip().splitlines()
            return [json.loads(l) for l in lines[-n:]]
        except Exception:
            return []


def _safe_serialize(obj) -> dict:
    """Garantiza que args sea serializable a JSON."""
    if not isinstance(obj, dict):
        return {"raw": str(obj)[:200]}
    sanitized = {}
    for k, v in obj.items():
        try:
            json.dumps(v, ensure_ascii=False)
            sanitized[k] = v
        except (TypeError, ValueError):
            sanitized[k] = str(v)[:200]
    return sanitized
