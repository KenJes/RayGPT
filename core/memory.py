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

    def get_vocabulario_hint(self, top_n: int = 15) -> str:
        """Devuelve un hint con el vocabulario más frecuente del usuario para inyectar en el system prompt."""
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

    def aprender_vocabulario(self, mensaje_usuario):
        palabras_comunes = {
            "que", "para", "con", "por", "una", "los", "las",
            "del", "como", "sobre", "esto", "eso", "hay", "más",
            "cuando", "donde", "quien", "cual", "qué", "cómo",
            "pero", "este", "esta", "tiene", "hacer", "puede",
            "ser", "ver", "dar", "fue", "son", "algo", "todo",
        }
        palabras = mensaje_usuario.lower().split()
        for palabra in palabras:
            limpia = re.sub(r"[^a-záéíóúñ]", "", palabra)
            if len(limpia) >= 3 and limpia not in palabras_comunes:
                self.memory["vocabulario_usuario"][limpia] = (
                    self.memory["vocabulario_usuario"].get(limpia, 0) + 1
                )
        if len(self.memory["vocabulario_usuario"]) > 100:
            sorted_vocab = sorted(
                self.memory["vocabulario_usuario"].items(),
                key=lambda x: x[1],
                reverse=True,
            )[:100]
            self.memory["vocabulario_usuario"] = dict(sorted_vocab)
        self.save_memory()
