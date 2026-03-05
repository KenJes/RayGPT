"""
MemorySystem — Memoria contextual del agente.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from core.config import DATA_DIR

# ─── Palabras de argot / estilo informal mexicano ───────────────────────────
# Estas sí deben reflejarse en el tono del agente
SLANG_MEXICANO = {
    "wey", "güey", "buey", "oye", "órale", "ándale", "andale", "chido", "chida",
    "chingon", "chingona", "chingada", "chinga", "chingo", "chingo", "verga",
    "naco", "naca", "puto", "puta", "putos", "putas", "cabron", "cabrón",
    "pendejo", "pendeja", "pendejos", "imbecil", "imbécil", "estupido", "estúpido",
    "pinche", "pinches", "culero", "culera", "mierda", "madres", "madre",
    "osea", "pues", "pos", "aja", "ajá", "alv", "nmms", "jalo",
    "chale", "neta", "neta", "fierro", "cañon", "cañón", "chonchole",
    "putazo", "putiza", "grosero", "insulto", "wtf", "omg", "bruh", "mano",
    "dude", "bro", "bro", "ese", "vato", "wachala", "nel", "chamba",
}

# ─── Stopwords español completo (palabras sin valor de estilo ni tema) ───────
STOPWORDS_ES = {
    # artículos / determinantes
    "el", "la", "los", "las", "un", "una", "unos", "unas", "del", "al",
    # preposiciones
    "a", "ante", "bajo", "con", "contra", "de", "desde", "durante", "en",
    "entre", "hacia", "hasta", "mediante", "para", "por", "según", "sin",
    "sobre", "tras",
    # conjunciones
    "y", "o", "u", "e", "ni", "que", "si", "aunque", "pero", "sino",
    "porque", "pues", "cuando", "donde", "como", "mientras",
    # pronombres
    "yo", "tú", "tu", "él", "ella", "ello", "nos", "vos",
    "nosotros", "vosotros", "ellos", "ellas", "me", "te", "se", "le",
    "lo", "les", "nos", "os", "ello", "esto", "eso", "aquello",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
    "aquel", "aquella", "aquellos", "aquellas",
    "qué", "quién", "cuál", "dónde", "cuándo", "cómo", "cuánto",
    "que", "quien", "cual", "donde", "cuando", "como", "cuanto",
    # verbos auxiliares / ser / estar comunes
    "es", "son", "soy", "somos", "eres", "erais", "era", "eran",
    "fue", "fueron", "ser", "estar", "estoy", "estás", "está", "estamos",
    "están", "estaba", "estaban", "estuvo", "estuvieron",
    "hay", "haber", "has", "ha", "han", "había", "habían", "hubo",
    "hacer", "hago", "hace", "hacen", "hacemos",
    "tener", "tengo", "tienes", "tiene", "tenemos", "tienen",
    "poder", "puedo", "puedes", "puede", "podemos", "pueden",
    "querer", "quiero", "quieres", "quiere", "queremos", "quieren",
    "ir", "voy", "vas", "va", "vamos", "van",
    "ver", "ver", "dar", "saber", "decir", "digo", "dice", "poner",
    "venir", "venir", "salir", "traer", "llevar",
    # adverbios comunes
    "no", "sí", "si", "también", "tampoco", "muy", "más", "menos",
    "bien", "mal", "ya", "aún", "aun", "ahora", "antes", "después",
    "siempre", "nunca", "jamás", "aquí", "allí", "allá", "acá",
    "todo", "todos", "toda", "todas", "nada", "algo", "alguien",
    "nadie", "cada", "mismo", "misma", "otro", "otra", "otros", "otras",
    # palabras cortas sin contenido
    "sus", "mis", "tus", "les", "nos", "les", "les", "sin", "con",
    "por", "para", "ese", "esa", "sus", "hay", "fue", "son",
    # otras frecuentes
    "entonces", "bueno", "claro", "obvio", "igual", "solo", "sólo",
    "así", "tal", "cual", "tanto", "cuanto", "menos", "además",
    "mejor", "peor", "mayor", "menor", "nuevo", "nueva",
    "gran", "grande", "pequeño", "pequeña",
    "hacer", "tener", "poder", "querer",
    "hola", "gracias", "favor", "please", "okay", "vale",
    # anglicismos neutros
    "the", "and", "for", "with", "that", "this", "from",
    # palabras de comando Raymundo
    "raymundo", "dile", "cuál", "dame", "manda", "haz",
    "explica", "explícale", "explícame", "dime",
}


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

def get_vocabulario_hint(self, user_id=None, top_n: int = 8) -> str:
        """
        Genera un hint de ESTILO basado en el argot/slang que usa el usuario.
        Solo incluye palabras de estilo informal — nunca temas ni palabras genéricas.
        Si no hay slang registrado, no inyecta nada (evita ruido).
        """
        if user_id:
            estilo = self.memory.get("estilo_por_usuario", {}).get(user_id, {})
        else:
            estilo = self.memory.get("estilo_usuario", {})

        if not estilo:
            return ""

        top = sorted(estilo.items(), key=lambda x: x[1], reverse=True)[:top_n]
        palabras = [w for w, _ in top]

        if not palabras:
            return ""

        # Hint específico de tono, no de inserción de palabras al azar
        return (
            f"\n\nESTILO DE COMUNICACIÓN DEL USUARIO: Este usuario habla de forma informal "
            f"y usa expresiones como: {', '.join(palabras)}. "
            f"Refleja SU mismo nivel de informalidad en tus respuestas — no insertes estas "
            f"palabras forzadamente, úsalas solo si fluye natural con tu personalidad."
        )

    def get_temas_frecuentes(self, user_id=None, top_n: int = 10) -> list:
        """Devuelve los temas/palabras clave más frecuentes del usuario (para contexto futuro)."""
        if user_id:
            temas = self.memory.get("temas_por_usuario", {}).get(user_id, {})
        else:
            temas = self.memory.get("temas_usuario", {})
        if not temas:
            return []
        top = sorted(temas.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [w for w, _ in top]

    def aprender_vocabulario(self, mensaje_usuario, user_id=None):
        """
        Clasifica cada palabra del mensaje en dos buckets:
        - estilo_usuario / estilo_por_usuario: argot/slang (para hint de tono)
        - temas_usuario / temas_por_usuario: palabras de contenido (temas frecuentes)
        Palabras de la lista de stopwords se descartan.
        """
        palabras = mensaje_usuario.lower().split()

        # Elegir buckets según user_id
        if user_id:
            if "estilo_por_usuario" not in self.memory:
                self.memory["estilo_por_usuario"] = {}
            if "temas_por_usuario" not in self.memory:
                self.memory["temas_por_usuario"] = {}
            if user_id not in self.memory["estilo_por_usuario"]:
                self.memory["estilo_por_usuario"][user_id] = {}
            if user_id not in self.memory["temas_por_usuario"]:
                self.memory["temas_por_usuario"][user_id] = {}
            estilo_bucket = self.memory["estilo_por_usuario"][user_id]
            temas_bucket = self.memory["temas_por_usuario"][user_id]
        else:
            if "estilo_usuario" not in self.memory:
                self.memory["estilo_usuario"] = {}
            if "temas_usuario" not in self.memory:
                self.memory["temas_usuario"] = {}
            estilo_bucket = self.memory["estilo_usuario"]
            temas_bucket = self.memory["temas_usuario"]

        for palabra in palabras:
            limpia = re.sub(r"[^a-záéíóúüñ]", "", palabra)
            if len(limpia) < 3:
                continue
            if limpia in STOPWORDS_ES:
                continue

            if limpia in SLANG_MEXICANO:
                # Palabra de estilo/slang
                estilo_bucket[limpia] = estilo_bucket.get(limpia, 0) + 1
            elif len(limpia) >= 4:
                # Palabra de tema/contenido (mínimo 4 chars para reducir ruido)
                temas_bucket[limpia] = temas_bucket.get(limpia, 0) + 1

        # Limitar tamaño de buckets
        def _trim(bucket, max_size=80):
            if len(bucket) > max_size:
                return dict(
                    sorted(bucket.items(), key=lambda x: x[1], reverse=True)[:max_size]
                )
            return bucket

        if user_id:
            self.memory["estilo_por_usuario"][user_id] = _trim(estilo_bucket, 50)
            self.memory["temas_por_usuario"][user_id] = _trim(temas_bucket, 80)
        else:
            self.memory["estilo_usuario"] = _trim(estilo_bucket, 50)
            self.memory["temas_usuario"] = _trim(temas_bucket, 80)

        self.save_memory()
