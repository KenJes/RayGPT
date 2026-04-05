"""
Utilidades compartidas para todos los agentes de Axoloit.
Carga variables de entorno, expone fábricas de clientes IA y helpers.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR   = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

# Agregar raíz del proyecto para importar core/
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ── Variables de entorno ───────────────────────────────────────
dotenv_path = CONFIG_DIR / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()

# ── Re-exportar clientes desde core/ ──────────────────────────
from core.ai_clients import OllamaClient, MistralClient, GroqClient, llamar_ia  # noqa: E402
from core.web_scraper import WebScraper  # noqa: E402
from core.config import config_agente  # noqa: E402

# ── URLs / credenciales ───────────────────────────────────────
OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")


def get_ollama_client():
    """Retorna OllamaClient configurado."""
    return OllamaClient(url=OLLAMA_URL, model=OLLAMA_MODEL)


def get_mistral_client():
    """Retorna MistralClient configurado."""
    return MistralClient(api_key=MISTRAL_API_KEY)


def get_groq_client():
    """Retorna GroqClient configurado."""
    return GroqClient(api_key=GROQ_API_KEY)


def get_google_client():
    """Retorna GoogleWorkspaceClient si hay credenciales disponibles."""
    try:
        from core.google_workspace_client import GoogleWorkspaceClient
        creds = BASE_DIR / "resources" / "data" / "google-credentials.json"
        if creds.exists():
            return GoogleWorkspaceClient(str(creds))
    except Exception as e:
        print(f"⚠️ Google Workspace no disponible: {e}")
    return None


def log(agent_name: str, msg: str):
    """Logger simple con timestamp."""
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{agent_name}] {msg}", flush=True)
