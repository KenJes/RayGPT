"""
knowledge_db.py — Base de conocimiento persistente de Raymundo.

Almacena documentos (CVs, archivos), personas y hechos aprendidos
para que Raymundo funcione como asistente de RH con memoria a largo plazo.

Tablas:
    documents   — CVs, imágenes, archivos recibidos (texto extraído + metadata)
    people      — Personas conocidas (candidatos, contactos)
    facts       — Hechos/datos aprendidos en conversaciones sobre personas

Uso:
    kb = KnowledgeBase()
    doc_id = kb.store_document(user_id, "cv", "Alan García", texto_ocr, ...)
    kb.store_person("Alan García", cv_doc_id=doc_id, skills=["Python", "React"])
    kb.add_fact("Alan García", "Tiene 3 años de experiencia en backend", user_id)
    results = kb.search_people(query="Python senior")
    person = kb.get_person("Alan García")
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Callable


_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "conocimiento.db"


class KnowledgeBase:
    """Base de conocimiento persistente para documentos, personas y hechos."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path or _DEFAULT_DB_PATH)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    # ─── Inicialización ───────────────────────────────────────

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      TEXT    NOT NULL,
                    doc_type     TEXT    NOT NULL,
                    person_name  TEXT,
                    title        TEXT,
                    content      TEXT    NOT NULL,
                    evaluation   TEXT,
                    source       TEXT,
                    timestamp    REAL    NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_docs_user ON documents(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_docs_person ON documents(person_name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_docs_type ON documents(doc_type)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS people (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL UNIQUE,
                    role        TEXT,
                    skills      TEXT,
                    experience  TEXT,
                    education   TEXT,
                    contact     TEXT,
                    location    TEXT,
                    salary_range TEXT,
                    level       TEXT,
                    verdict     TEXT,
                    notes       TEXT,
                    added_by    TEXT,
                    updated_at  REAL    NOT NULL
                )
            """)
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_people_name
                ON people(name COLLATE NOCASE)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_name TEXT    NOT NULL,
                    fact        TEXT    NOT NULL,
                    source      TEXT,
                    user_id     TEXT,
                    timestamp   REAL    NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_facts_person
                ON facts(person_name COLLATE NOCASE)
            """)

    # ═══════════════════════════════════════════════════════════
    # Documentos
    # ═══════════════════════════════════════════════════════════

    def store_document(
        self,
        user_id: str,
        doc_type: str,
        content: str,
        person_name: str | None = None,
        title: str | None = None,
        evaluation: str | None = None,
        source: str = "whatsapp",
    ) -> int:
        """
        Guarda un documento (CV, imagen, archivo) con su texto extraído.

        Args:
            doc_type: "cv", "image", "document", "spreadsheet"
            content: Texto extraído (OCR o contenido del doc)
            person_name: Nombre de la persona asociada (si es CV)
            evaluation: Texto de la evaluación de RH (si aplica)
            source: "whatsapp", "gui", "upload"

        Returns:
            ID del documento insertado.
        """
        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO documents
                   (user_id, doc_type, person_name, title, content, evaluation, source, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, doc_type, person_name, title, content, evaluation, source, time.time()),
            )
            return cursor.lastrowid

    def update_document_evaluation(self, doc_id: int, evaluation: str, person_name: str | None = None):
        """Actualiza la evaluación de un documento ya guardado."""
        with self._conn() as conn:
            if person_name:
                conn.execute(
                    "UPDATE documents SET evaluation = ?, person_name = ? WHERE id = ?",
                    (evaluation, person_name, doc_id),
                )
            else:
                conn.execute(
                    "UPDATE documents SET evaluation = ? WHERE id = ?",
                    (evaluation, doc_id),
                )

    def get_document(self, doc_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def get_documents_by_person(self, person_name: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE person_name = ? COLLATE NOCASE ORDER BY timestamp DESC",
                (person_name,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_documents_by_type(self, doc_type: str, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE doc_type = ? ORDER BY timestamp DESC LIMIT ?",
                (doc_type, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_documents(self, user_id: str | None = None, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            if user_id:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM documents ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def search_documents(self, query: str, limit: int = 20) -> list[dict]:
        """Búsqueda de texto en documentos."""
        pattern = f"%{query}%"
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM documents
                   WHERE content LIKE ? OR person_name LIKE ? OR title LIKE ? OR evaluation LIKE ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ═══════════════════════════════════════════════════════════
    # Personas
    # ═══════════════════════════════════════════════════════════

    def store_person(
        self,
        name: str,
        role: str | None = None,
        skills: list[str] | None = None,
        experience: str | None = None,
        education: str | None = None,
        contact: str | None = None,
        location: str | None = None,
        salary_range: str | None = None,
        level: str | None = None,
        verdict: str | None = None,
        notes: str | None = None,
        added_by: str | None = None,
    ) -> int:
        """
        Crea o actualiza una persona en la base.
        Si ya existe (por nombre), actualiza solo los campos proporcionados.
        """
        skills_json = json.dumps(skills, ensure_ascii=False) if skills else None
        existing = self.get_person(name)

        if existing:
            # Actualizar solo campos no-None
            updates = {}
            if role is not None: updates["role"] = role
            if skills_json is not None: updates["skills"] = skills_json
            if experience is not None: updates["experience"] = experience
            if education is not None: updates["education"] = education
            if contact is not None: updates["contact"] = contact
            if location is not None: updates["location"] = location
            if salary_range is not None: updates["salary_range"] = salary_range
            if level is not None: updates["level"] = level
            if verdict is not None: updates["verdict"] = verdict
            if notes is not None: updates["notes"] = notes
            updates["updated_at"] = time.time()

            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                values = list(updates.values())
                values.append(existing["id"])
                with self._conn() as conn:
                    conn.execute(f"UPDATE people SET {set_clause} WHERE id = ?", values)
            return existing["id"]
        else:
            with self._conn() as conn:
                cursor = conn.execute(
                    """INSERT INTO people
                       (name, role, skills, experience, education, contact, location,
                        salary_range, level, verdict, notes, added_by, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name, role, skills_json, experience, education, contact, location,
                     salary_range, level, verdict, notes, added_by, time.time()),
                )
                return cursor.lastrowid

    def get_person(self, name: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM people WHERE name = ? COLLATE NOCASE",
                (name,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("skills"):
            try:
                d["skills"] = json.loads(d["skills"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    def list_people(self, limit: int = 100) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM people ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if d.get("skills"):
                try:
                    d["skills"] = json.loads(d["skills"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results

    def search_people(self, query: str, limit: int = 20) -> list[dict]:
        """Busca personas por nombre, skills, rol, experiencia, etc."""
        pattern = f"%{query}%"
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM people
                   WHERE name LIKE ? OR role LIKE ? OR skills LIKE ?
                         OR experience LIKE ? OR education LIKE ? OR notes LIKE ?
                   ORDER BY updated_at DESC LIMIT ?""",
                (pattern, pattern, pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if d.get("skills"):
                try:
                    d["skills"] = json.loads(d["skills"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results

    def delete_person(self, name: str) -> bool:
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM people WHERE name = ? COLLATE NOCASE", (name,),
            )
            conn.execute(
                "DELETE FROM facts WHERE person_name = ? COLLATE NOCASE", (name,),
            )
        return cursor.rowcount > 0

    # ═══════════════════════════════════════════════════════════
    # Hechos / datos aprendidos
    # ═══════════════════════════════════════════════════════════

    def add_fact(self, person_name: str, fact: str, user_id: str | None = None, source: str = "conversation"):
        """Registra un hecho sobre una persona."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO facts (person_name, fact, source, user_id, timestamp) VALUES (?, ?, ?, ?, ?)",
                (person_name, fact, source, user_id, time.time()),
            )

    def get_facts(self, person_name: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM facts WHERE person_name = ? COLLATE NOCASE ORDER BY timestamp DESC",
                (person_name,),
            ).fetchall()
        return [dict(r) for r in rows]

    def search_facts(self, query: str, limit: int = 30) -> list[dict]:
        pattern = f"%{query}%"
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM facts
                   WHERE fact LIKE ? OR person_name LIKE ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (pattern, pattern, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ═══════════════════════════════════════════════════════════
    # Contexto para LLM — construye resumen de conocimiento
    # ═══════════════════════════════════════════════════════════

    def build_knowledge_context(self, query: str | None = None, person_name: str | None = None) -> str:
        """
        Construye un bloque de texto con conocimiento relevante para inyectar al LLM.
        Se usa como contexto adicional en el system prompt.
        """
        parts = []

        # Si se pregunta por una persona específica
        if person_name:
            person = self.get_person(person_name)
            if person:
                parts.append(self._format_person(person))
                # Agregar hechos
                facts = self.get_facts(person_name)
                if facts:
                    facts_text = "\n".join(f"  - {f['fact']}" for f in facts[:15])
                    parts.append(f"Datos adicionales sobre {person_name}:\n{facts_text}")
                # Agregar documentos/CVs
                docs = self.get_documents_by_person(person_name)
                for doc in docs[:3]:
                    if doc["doc_type"] == "cv" and doc.get("evaluation"):
                        parts.append(f"Evaluación de CV de {person_name}:\n{doc['evaluation'][:1500]}")

        # Búsqueda general
        if query:
            # Buscar personas relevantes
            people = self.search_people(query, limit=5)
            for p in people:
                if not person_name or p["name"].lower() != person_name.lower():
                    parts.append(self._format_person(p))
            # Buscar hechos relevantes
            facts = self.search_facts(query, limit=10)
            if facts:
                seen = set()
                fact_lines = []
                for f in facts:
                    key = (f["person_name"], f["fact"])
                    if key not in seen:
                        seen.add(key)
                        fact_lines.append(f"  - {f['person_name']}: {f['fact']}")
                if fact_lines:
                    parts.append("Datos relevantes:\n" + "\n".join(fact_lines))
            # Buscar documentos relevantes
            docs = self.search_documents(query, limit=5)
            for doc in docs:
                if doc["doc_type"] == "cv":
                    snippet = doc["content"][:500]
                    parts.append(f"CV guardado ({doc.get('person_name', 'sin nombre')}): {snippet}...")

        if not parts:
            return ""

        return "[CONOCIMIENTO ALMACENADO EN BASE DE DATOS]:\n" + "\n---\n".join(parts)

    def _format_person(self, person: dict) -> str:
        lines = [f"Persona: {person['name']}"]
        if person.get("role"): lines.append(f"  Rol: {person['role']}")
        if person.get("level"): lines.append(f"  Nivel: {person['level']}")
        skills = person.get("skills")
        if skills:
            if isinstance(skills, list):
                lines.append(f"  Skills: {', '.join(skills)}")
            else:
                lines.append(f"  Skills: {skills}")
        if person.get("experience"): lines.append(f"  Experiencia: {person['experience']}")
        if person.get("education"): lines.append(f"  Educación: {person['education']}")
        if person.get("contact"): lines.append(f"  Contacto: {person['contact']}")
        if person.get("location"): lines.append(f"  Ubicación: {person['location']}")
        if person.get("salary_range"): lines.append(f"  Rango salarial: {person['salary_range']}")
        if person.get("verdict"): lines.append(f"  Veredicto: {person['verdict']}")
        if person.get("notes"): lines.append(f"  Notas: {person['notes']}")
        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════
    # Stats
    # ═══════════════════════════════════════════════════════════

    def get_stats(self) -> dict:
        with self._conn() as conn:
            docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            cvs = conn.execute("SELECT COUNT(*) FROM documents WHERE doc_type = 'cv'").fetchone()[0]
            people = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
            facts = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        return {"documents": docs, "cvs": cvs, "people": people, "facts": facts}
