"""
Configuración del agente Raymundo.
Carga config_agente.json y expone helpers de personalidad.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths del proyecto ──────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
RESOURCES_DIR = BASE_DIR / "resources"

# Selección de personalidad via variable de entorno PERSONALITY_MODE
# "raymundo" (default) = agente profesional de Axoloit
# "rai"                = compa agresivo, déspota y chistoso
_PERSONALITY_MODE = os.environ.get("PERSONALITY_MODE", "raymundo").lower()
if _PERSONALITY_MODE == "rai":
    PERSONALITY_FILE = DATA_DIR / "personalidad_rai.md"
else:
    PERSONALITY_FILE = DATA_DIR / "personalidad_raymundo.md"

# Crear directorios si no existen
for _d in (CONFIG_DIR, DATA_DIR, OUTPUT_DIR):
    _d.mkdir(exist_ok=True)

# Cargar variables de entorno
_dotenv_path = CONFIG_DIR / ".env"
if _dotenv_path.exists():
    load_dotenv(dotenv_path=_dotenv_path)
else:
    load_dotenv()


# ═══════════════════════════════════════════════════════════════
# ConfigAgente
# ═══════════════════════════════════════════════════════════════

def _load_personality_file() -> str | None:
    """Lee el archivo de personalidad según PERSONALITY_MODE (raymundo o rai)."""
    if PERSONALITY_FILE.exists():
        try:
            return PERSONALITY_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return None


class ConfigAgente(dict):
    """Wrapper con helpers para acceder a la configuración del agente."""

    def __init__(self, data):
        super().__init__(data or {})
        self.config = self

    def get_nombre_agente(self):
        if _PERSONALITY_MODE == "rai":
            return "rAI"
        return self.config.get("personalidad", {}).get("nombre", "Raymundo")

    def get_prompt_sistema(self):
        # Prioridad: archivo de personalidad > JSON config
        file_personality = _load_personality_file()
        if file_personality:
            return file_personality
        personalidad = self.config.get("personalidad", {})
        prompt = personalidad.get("prompt_sistema")
        if prompt:
            return prompt
        tono = personalidad.get("tono", "amigable")
        return (
            f"Eres {self.get_nombre_agente()}, un asistente con tono {tono}. "
            "Responde siempre con precisión y mantén ese estilo."
        )

    def get_tono(self):
        return self.config.get("personalidad", {}).get("tono", "amigable")

    def get_prompt_sistema_en(self):
        personalidad_en = self.config.get("personalidad_en", {})
        tono = self.get_tono()
        if tono == "puteado":
            return personalidad_en.get(
                "prompt_sistema_puteado",
                "You are Ray, a helpful assistant. Respond in English.",
            )
        return personalidad_en.get(
            "prompt_sistema_amigable",
            "You are Ray, a friendly assistant. Respond in English.",
        )

    def cambiar_personalidad(self, tono):
        personalidades = self.config.get("personalidades", {})
        if tono in personalidades:
            datos = personalidades[tono]
            self.config["personalidad"]["tono"] = tono
            self.config["personalidad"]["nombre"] = datos.get("nombre", "Raymundo")
            self.config["personalidad"]["prompt_sistema"] = datos.get("prompt_sistema", "")
        else:
            self.config["personalidad"]["tono"] = tono
            if tono == "puteado":
                self.config["personalidad"]["nombre"] = "rAI"
            else:
                self.config["personalidad"]["nombre"] = "Raymundo"
        return f"🔄 Personalidad cambiada a: {tono}"


# ── Singleton: Cargar configuración ────────────────────────────

def _load_config() -> ConfigAgente:
    config_path = BASE_DIR / "config_agente.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return ConfigAgente(json.load(f))


config_agente = _load_config()


# ═══════════════════════════════════════════════════════════════
# AppConfig — credenciales y clientes base
# ═══════════════════════════════════════════════════════════════

class AppConfig:
    """Administra ajustes locales (modelos y credenciales)."""

    def __init__(self):
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
        self.github_token = os.environ.get("GITHUB_TOKEN")

        creds_env = os.environ.get("GOOGLE_CREDENTIALS_FILE")
        default_creds = RESOURCES_DIR / "data" / "google-credentials.json"
        self.google_credentials_file = Path(creds_env) if creds_env else default_creds
        self.google_client = None
        if self.google_credentials_file and self.google_credentials_file.exists():
            try:
                from core.google_workspace_client import GoogleWorkspaceClient

                self.google_client = GoogleWorkspaceClient(str(self.google_credentials_file))
            except Exception as e:
                print(f"⚠️ No se pudo inicializar Google Workspace: {e}")
