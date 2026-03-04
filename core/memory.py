"""
MemorySystem — Memoria contextual del agente.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from core.config import DATA_DIR


class MemorySystem:
    """Sistema de memoria contextual persistente."""

    def __init__(self, memory_file=None):
        default_memory = DATA_DIR / "memoria_agente.json"
        self.memory_file = Path(memory_file) if memory_file else default_memory
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.memory = {
            "documents": [],
            "images": [],
            "vocabulario_usuario": {},
            "max_items": 20,
        }
        self.load_memory()

    def load_memory(self):
        try:
            if self.memory_file.exists():
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.memory = json.load(f)
        except Exception:
            pass

    def save_memory(self):
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def add_document(self, file_path, content, summary=""):
        entry = {
            "filename": Path(file_path).name,
            "content": content[:5000],
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
        }
        self.memory["documents"].append(entry)
        max_items = self.memory.get("max_items", 20)
        if len(self.memory["documents"]) > max_items:
            self.memory["documents"] = self.memory["documents"][-max_items:]
        self.save_memory()

    def add_image(self, file_path, description=""):
        entry = {
            "filename": Path(file_path).name,
            "description": description,
            "timestamp": datetime.now().isoformat(),
        }
        self.memory["images"].append(entry)
        max_items = self.memory.get("max_items", 20)
        if len(self.memory["images"]) > max_items:
            self.memory["images"] = self.memory["images"][-max_items:]
        self.save_memory()

    def get_vocabulario_hint(self, user_id=None, top_n: int = 15) -> str:
        """Devuelve un hint con el vocabulario más frecuente del usuario para inyectar en el system prompt.
        Si se proporciona user_id, usa el vocabulario específico de ese usuario.
        """
        if user_id:
            vocab = self.memory.get("vocabulario_por_usuario", {}).get(user_id, {})
        else:
            vocab = self.memory.get("vocabulario_usuario", {})

        if not vocab:
            return ""
        top = sorted(vocab.items(), key=lambda x: x[1], reverse=True)[:top_n]
        palabras = ", ".join(w for w, _ in top)
        return (
            f"\n\nVOCABULARIO DEL USUARIO: Este usuario usa frecuentemente "
            f"estas palabras y expresiones: {palabras}. "
            f"Incorpóralas naturalmente en tus respuestas según el contexto y tu personalidad."
        )

    def aprender_vocabulario(self, mensaje_usuario, user_id=None):
        """Aprende el vocabulario del usuario.
        Si se proporciona user_id, almacena de forma separada por usuario.
        """
        palabras_comunes = {
            "que", "para", "con", "por", "una", "los", "las",
            "del", "como", "sobre", "esto", "eso", "hay", "más",
            "cuando", "donde", "quien", "cual", "qué", "cómo",
            "pero", "este", "esta", "tiene", "hacer", "puede",
            "ser", "ver", "dar", "fue", "son", "algo", "todo",
        }
        palabras = mensaje_usuario.lower().split()

        # Elegir bucket de vocabulario
        if user_id:
            if "vocabulario_por_usuario" not in self.memory:
                self.memory["vocabulario_por_usuario"] = {}
            if user_id not in self.memory["vocabulario_por_usuario"]:
                self.memory["vocabulario_por_usuario"][user_id] = {}
            vocab_bucket = self.memory["vocabulario_por_usuario"][user_id]
        else:
            vocab_bucket = self.memory["vocabulario_usuario"]

        for palabra in palabras:
            limpia = re.sub(r"[^a-záéíóúñ]", "", palabra)
            if len(limpia) >= 3 and limpia not in palabras_comunes:
                vocab_bucket[limpia] = vocab_bucket.get(limpia, 0) + 1

        # Limitar a 100 palabras por bucket
        if len(vocab_bucket) > 100:
            sorted_vocab = sorted(
                vocab_bucket.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:100]
            if user_id:
                self.memory["vocabulario_por_usuario"][user_id] = dict(sorted_vocab)
            else:
                self.memory["vocabulario_usuario"] = dict(sorted_vocab)
        self.save_memory()
