"""
agent_memory.py — Memoria vectorial ligera para RAG del agente.

Implementación TF-IDF local (sin dependencias externas como ChromaDB).
Permite almacenar textos con metadatos y recuperar los k más relevantes
usando similitud coseno sobre vectores TF-IDF.
"""

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import DATA_DIR

MEMORY_STORE_FILE = DATA_DIR / "agent_vector_memory.json"


class VectorMemory:
    """
    Store & retrieve de textos con TF-IDF + cosine similarity.
    Ligero, sin dependencias externas — ideal para el free tier.
    """

    def __init__(self, store_file: Path | None = None, max_entries: int = 200):
        self.store_file = store_file or MEMORY_STORE_FILE
        self.store_file.parent.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries

        # Cada entrada: {"text": str, "metadata": dict, "tokens": list[str], "timestamp": str}
        self._entries: list[dict] = []
        # IDF cache (se recalcula al cargar / insertar)
        self._idf: dict[str, float] = {}
        self._load()

    # ─── Persistencia ──────────────────────────────────────────

    def _load(self):
        if self.store_file.exists():
            try:
                data = json.loads(self.store_file.read_text(encoding="utf-8"))
                self._entries = data.get("entries", [])
                self._rebuild_idf()
            except Exception:
                self._entries = []

    def _save(self):
        try:
            data = {"entries": self._entries}
            self.store_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ─── Tokenización simple ──────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokeniza texto a lista de palabras en minúsculas."""
        return re.findall(r"[a-záéíóúüñ]{2,}", text.lower())

    # ─── TF-IDF ───────────────────────────────────────────────

    def _rebuild_idf(self):
        """Recalcula IDF sobre todos los documentos almacenados."""
        n = len(self._entries)
        if n == 0:
            self._idf = {}
            return
        df: Counter = Counter()
        for entry in self._entries:
            tokens = set(entry.get("tokens", []))
            for t in tokens:
                df[t] += 1
        self._idf = {t: math.log(n / count) for t, count in df.items()}

    def _tfidf_vector(self, tokens: list[str]) -> dict[str, float]:
        """Calcula vector TF-IDF para una lista de tokens."""
        tf = Counter(tokens)
        total = len(tokens) or 1
        vec = {}
        for t, count in tf.items():
            idf = self._idf.get(t, 0.0)
            vec[t] = (count / total) * idf
        return vec

    @staticmethod
    def _cosine_sim(a: dict[str, float], b: dict[str, float]) -> float:
        """Similitud coseno entre dos vectores sparse."""
        common = set(a) & set(b)
        if not common:
            return 0.0
        dot = sum(a[k] * b[k] for k in common)
        mag_a = math.sqrt(sum(v * v for v in a.values()))
        mag_b = math.sqrt(sum(v * v for v in b.values()))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    # ─── API pública ──────────────────────────────────────────

    def store(self, text: str, metadata: dict | None = None):
        """Almacena un texto con metadatos opcionales."""
        tokens = self._tokenize(text)
        if not tokens:
            return
        entry = {
            "text": text[:3000],  # Limitar tamaño
            "metadata": metadata or {},
            "tokens": tokens,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._entries.append(entry)
        # Purgar si excede max
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]
        self._rebuild_idf()
        self._save()

    def retrieve(self, query: str, k: int = 5, min_score: float = 0.05) -> list[dict]:
        """
        Recupera los k documentos más relevantes para la query.
        Retorna lista de {"text", "metadata", "score", "timestamp"}.
        """
        if not self._entries:
            return []
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        query_vec = self._tfidf_vector(query_tokens)

        scored = []
        for entry in self._entries:
            entry_vec = self._tfidf_vector(entry.get("tokens", []))
            score = self._cosine_sim(query_vec, entry_vec)
            if score >= min_score:
                scored.append({
                    "text": entry["text"],
                    "metadata": entry.get("metadata", {}),
                    "score": round(score, 4),
                    "timestamp": entry.get("timestamp", ""),
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def store_if_relevant(self, text: str, metadata: dict | None = None, threshold: float = 0.7):
        """
        Solo almacena si el texto NO es muy similar a algo existente (evita duplicados).
        Si la similitud con el mejor match es < threshold, almacena.
        """
        if not self._entries:
            self.store(text, metadata)
            return
        matches = self.retrieve(text, k=1)
        if not matches or matches[0]["score"] < threshold:
            self.store(text, metadata)

    def get_context_for_planning(self, goal: str, k: int = 5) -> str:
        """
        Recupera contexto relevante formateado para inyectar en el prompt de planning.
        """
        results = self.retrieve(goal, k=k)
        if not results:
            return ""
        lines = ["Contexto de acciones previas relevantes:"]
        for r in results:
            meta = r.get("metadata", {})
            action = meta.get("action", "unknown")
            lines.append(f"- [{action}] (relevancia: {r['score']}) {r['text'][:200]}")
        return "\n".join(lines)

    def count(self) -> int:
        return len(self._entries)

    def clear(self):
        self._entries = []
        self._idf = {}
        self._save()
