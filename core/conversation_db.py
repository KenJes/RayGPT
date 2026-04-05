"""
conversation_db.py — Almacenamiento persistente de conversaciones con SQLite.

Reemplaza el diccionario en RAM para que Raymundo recuerde conversaciones
entre reinicios del servidor y a lo largo de días/semanas.

Esquema:
    messages(id, user_id, role, content, timestamp)

Uso:
    db = ConversationDB()                     # Abre/crea data/conversaciones.db
    db.add_message("user123", "user", "Hola")
    history = db.get_history("user123")       # Últimos N mensajes
    summary = db.get_summary("user123")       # Resumen compacto de historial antiguo
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Callable


_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "conversaciones.db"

# Cuántos pares (user+assistant) recientes se envían completos al LLM
RECENT_PAIRS = 8   # 16 mensajes = contexto manejable sin sobrecargar el LLM

# Cuántos mensajes viejos se resumen para dar contexto largo
SUMMARY_WINDOW = 60  # mensajes antiguos a considerar para resumen


class ConversationDB:
    """Capa de persistencia para conversaciones por usuario."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path or _DEFAULT_DB_PATH)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ─── Inicialización ───────────────────────────────────────

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id   TEXT    NOT NULL,
                    role      TEXT    NOT NULL,
                    content   TEXT    NOT NULL,
                    timestamp REAL    NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_user_ts
                ON messages(user_id, timestamp)
            """)
            # Tabla para resúmenes compactados de historial viejo
            conn.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id        TEXT    NOT NULL,
                    summary        TEXT    NOT NULL,
                    messages_from  INTEGER NOT NULL,
                    messages_to    INTEGER NOT NULL,
                    created_at     REAL    NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_summaries_user
                ON summaries(user_id)
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    # ─── Escritura ────────────────────────────────────────────

    def add_message(self, user_id: str, role: str, content: str):
        """Guarda un mensaje en la BD."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, role, content, time.time()),
            )

    # ─── Lectura ──────────────────────────────────────────────

    def get_history(self, user_id: str, limit: int = RECENT_PAIRS * 2) -> list[dict]:
        """
        Devuelve los últimos `limit` mensajes del usuario como lista de dicts
        [{"role": "user"|"assistant", "content": "..."}]
        ordenados cronológicamente (más viejo primero).
        """
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT role, content FROM messages
                   WHERE user_id = ?
                   ORDER BY timestamp DESC, id DESC
                   LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        # Invertir para orden cronológico
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def get_old_messages(self, user_id: str, offset: int, limit: int = SUMMARY_WINDOW) -> list[dict]:
        """Mensajes más antiguos para generar resúmenes."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, role, content FROM messages
                   WHERE user_id = ?
                   ORDER BY timestamp ASC, id ASC
                   LIMIT ? OFFSET ?""",
                (user_id, limit, offset),
            ).fetchall()
        return [{"id": r[0], "role": r[1], "content": r[2]} for r in rows]

    def count_messages(self, user_id: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row[0] if row else 0

    def clear_history(self, user_id: str):
        """Borra todo el historial de un usuario."""
        with self._conn() as conn:
            conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM summaries WHERE user_id = ?", (user_id,))

    # ─── Resúmenes ────────────────────────────────────────────

    def save_summary(self, user_id: str, summary: str, msg_from: int, msg_to: int):
        """Guarda un resumen compactado de un rango de mensajes."""
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO summaries (user_id, summary, messages_from, messages_to, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, summary, msg_from, msg_to, time.time()),
            )

    def get_summaries(self, user_id: str) -> list[str]:
        """Devuelve todos los resúmenes de un usuario, ordenados cronológicamente."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT summary FROM summaries
                   WHERE user_id = ?
                   ORDER BY messages_from ASC""",
                (user_id,),
            ).fetchall()
        return [r[0] for r in rows]

    def get_last_summarized_id(self, user_id: str) -> int:
        """ID del último mensaje ya resumido."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(messages_to) FROM summaries WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row[0] if row and row[0] else 0

    # ─── Contexto para LLM ───────────────────────────────────

    def build_context_messages(
        self,
        user_id: str,
        summarize_fn: Callable[[str], str] | None = None,
    ) -> list[dict]:
        """
        Construye la lista de mensajes de contexto para enviar al LLM:
        1. Resúmenes compactados del historial viejo (si existen)
        2. Últimos RECENT_PAIRS*2 mensajes completos

        Si `summarize_fn` se proporciona y hay mensajes viejos sin resumir,
        los compacta automáticamente.

        Returns:
            [{"role": "system"|"user"|"assistant", "content": "..."}]
        """
        context = []

        # 1. Auto-compactar mensajes viejos si hay función de resumen
        if summarize_fn:
            self._auto_summarize(user_id, summarize_fn)

        # 2. Agregar resúmenes existentes como contexto del sistema
        summaries = self.get_summaries(user_id)
        if summaries:
            combined = "\n---\n".join(summaries)
            context.append({
                "role": "system",
                "content": (
                    f"[RESUMEN DE CONVERSACIONES ANTERIORES CON ESTE USUARIO]:\n{combined}"
                ),
            })

        # 3. Agregar mensajes recientes completos
        recent = self.get_history(user_id, limit=RECENT_PAIRS * 2)
        context.extend(recent)

        return context

    def _auto_summarize(self, user_id: str, summarize_fn: Callable[[str], str]):
        """
        Si hay más de RECENT_PAIRS*2 mensajes sin resumir,
        compacta los bloques viejos en resúmenes.
        """
        total = self.count_messages(user_id)
        recent_count = RECENT_PAIRS * 2
        if total <= recent_count:
            return  # No hay nada viejo que resumir

        last_summarized = self.get_last_summarized_id(user_id)

        # Obtener mensajes no resumidos que ya no están en la ventana reciente
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, role, content FROM messages
                   WHERE user_id = ? AND id > ?
                   ORDER BY timestamp ASC, id ASC""",
                (user_id, last_summarized),
            ).fetchall()

        if len(rows) <= recent_count:
            return

        # Los mensajes a resumir son los que están FUERA de la ventana reciente
        to_summarize = rows[:-recent_count]
        if len(to_summarize) < 6:
            return  # No vale la pena resumir menos de 3 pares

        # Construir texto para resumir
        lines = []
        for row in to_summarize:
            role_label = "Usuario" if row[1] == "user" else "Raymundo"
            lines.append(f"{role_label}: {row[2]}")
        conversation_text = "\n".join(lines)

        # Generar resumen con LLM
        summary = summarize_fn(
            f"Resume esta conversación en máximo 5 oraciones, conservando "
            f"datos clave (nombres, fechas, temas, decisiones, datos importantes mencionados):\n\n"
            f"{conversation_text}"
        )

        if summary and not summary.startswith("❌"):
            msg_from = to_summarize[0][0]
            msg_to = to_summarize[-1][0]
            self.save_summary(user_id, summary, msg_from, msg_to)


# ══════════════════════════════════════════════════════════════
# Singleton + funciones de conveniencia  (módulo-level)
# ══════════════════════════════════════════════════════════════
_db = ConversationDB()


def agregar_mensaje(user_id: str, role: str, content: str):
    """Guarda un mensaje en la BD persistente."""
    _db.add_message(user_id, role, content)


def get_contexto_completo(user_id: str, summarize_fn=None) -> list[dict]:
    """Historial + resúmenes para el LLM."""
    return _db.build_context_messages(user_id, summarize_fn=summarize_fn)


def clear_user(user_id: str):
    """Borra TODO el historial y resúmenes de un usuario."""
    _db.clear_history(user_id)
