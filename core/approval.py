"""
approval.py — Sistema de aprobación para acciones destructivas/peligrosas.

Las acciones que requieren aprobación (write_file overwrite, run_shell, etc.)
quedan en estado "pending" hasta que el humano aprueba o rechaza.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"


@dataclass
class ApprovalRequest:
    id: str
    run_id: str
    action: str
    args: dict
    reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str | None = None


class ApprovalManager:
    """
    Gestiona solicitudes de aprobación humana.

    Flujo:
    1. Agent loop llama a request_approval(action, args, reason)
    2. Se crea un ApprovalRequest PENDING
    3. El callback on_approval_needed se dispara (para notificar al frontend)
    4. El frontend llama a approve(id) o deny(id)
    5. Agent loop puede consultar is_approved(id) o wait_for_decision(id)
    """

    def __init__(self):
        self._requests: dict[str, ApprovalRequest] = {}
        self._events: dict[str, threading.Event] = {}
        self.on_approval_needed: Callable[[ApprovalRequest], None] | None = None

    def request_approval(
        self,
        run_id: str,
        action: str,
        args: dict,
        reason: str = "",
    ) -> ApprovalRequest:
        """Crea una solicitud de aprobación y notifica al frontend."""
        req = ApprovalRequest(
            id=uuid.uuid4().hex[:12],
            run_id=run_id,
            action=action,
            args=args,
            reason=reason,
        )
        self._requests[req.id] = req
        self._events[req.id] = threading.Event()

        if self.on_approval_needed:
            try:
                self.on_approval_needed(req)
            except Exception:
                pass

        return req

    def approve(self, request_id: str) -> bool:
        req = self._requests.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False
        req.status = ApprovalStatus.APPROVED
        req.resolved_at = datetime.now(timezone.utc).isoformat()
        event = self._events.get(request_id)
        if event:
            event.set()
        return True

    def deny(self, request_id: str) -> bool:
        req = self._requests.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return False
        req.status = ApprovalStatus.DENIED
        req.resolved_at = datetime.now(timezone.utc).isoformat()
        event = self._events.get(request_id)
        if event:
            event.set()
        return True

    def wait_for_decision(self, request_id: str, timeout: float = 120.0) -> ApprovalStatus:
        """
        Bloquea hasta que el humano decida o se agote el timeout.
        Retorna el status final.
        """
        event = self._events.get(request_id)
        if not event:
            return ApprovalStatus.DENIED

        resolved = event.wait(timeout=timeout)
        req = self._requests.get(request_id)
        if not req:
            return ApprovalStatus.DENIED

        if not resolved:
            req.status = ApprovalStatus.TIMEOUT
            req.resolved_at = datetime.now(timezone.utc).isoformat()

        return req.status

    def is_approved(self, request_id: str) -> bool:
        req = self._requests.get(request_id)
        return req is not None and req.status == ApprovalStatus.APPROVED

    def get_pending(self, run_id: str | None = None) -> list[ApprovalRequest]:
        """Devuelve solicitudes pendientes, opcionalmente filtradas por run_id."""
        return [
            r for r in self._requests.values()
            if r.status == ApprovalStatus.PENDING
            and (run_id is None or r.run_id == run_id)
        ]

    def cleanup(self, run_id: str):
        """Limpia solicitudes de un run terminado."""
        to_remove = [k for k, v in self._requests.items() if v.run_id == run_id]
        for k in to_remove:
            self._requests.pop(k, None)
            self._events.pop(k, None)


# Singleton global para fácil acceso desde whatsapp_server y GUI
approval_manager = ApprovalManager()
