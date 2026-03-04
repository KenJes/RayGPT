"""
Clientes de IA — Ollama, GitHub Models (GPT-4o), Groq.
También expone ``llamar_ia()`` como helper de fallback chain.
"""

import os
import requests

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from groq import Groq


# ═══════════════════════════════════════════════════════════════
# Ollama (local GPU)
# ═══════════════════════════════════════════════════════════════

class OllamaClient:
    """Cliente para Ollama local (GPU)."""

    def __init__(self, url="http://localhost:11434", model="qwen2.5:7b"):
        self.url = url
        self.model = model
        self.last_tokens_used = 0

    def generate(self, prompt, temperature=0.7, max_tokens=2000):
        try:
            response = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
                timeout=120,
            )
            if response.status_code == 200:
                data = response.json()
                self.last_tokens_used = data.get("eval_count", 0)
                return data.get("response", "")
            return None
        except Exception as e:
            print(f"Error Ollama: {e}")
            return None

    def is_available(self):
        try:
            r = requests.get(f"{self.url}/api/version", timeout=2)
            return r.status_code == 200
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# GitHub Models (GPT-4o)
# ═══════════════════════════════════════════════════════════════

class GitHubModelsClient:
    """Cliente para GitHub Models (GPT-4o)."""

    def __init__(self, token=None, model="gpt-4o"):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.model = model
        self.endpoint = "https://models.inference.ai.azure.com"
        self.last_tokens_used = 0
        self.client = None

        if self.token:
            try:
                self.client = ChatCompletionsClient(
                    endpoint=self.endpoint,
                    credential=AzureKeyCredential(self.token),
                )
            except Exception as e:
                print(f"Error inicializando GitHub Models: {e}")

    def chat(self, messages, temperature=0.7, max_tokens=4000):
        if not self.client:
            return None
        try:
            formatted = []
            for msg in messages:
                if msg["role"] == "system":
                    formatted.append(SystemMessage(content=msg["content"]))
                elif msg["role"] == "user":
                    formatted.append(UserMessage(content=msg["content"]))

            response = self.client.complete(
                messages=formatted,
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if hasattr(response, "usage"):
                self.last_tokens_used = response.usage.total_tokens
            else:
                self.last_tokens_used = 0
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RateLimitReached" in error_msg:
                print("⚠️ Rate limit alcanzado en GitHub Models (Free Tier)")
                return None
            print(f"Error GitHub Models: {error_msg}")
            return None

    def chat_with_images(self, messages, temperature=0.7, max_tokens=1000):
        if not self.client:
            return "❌ GitHub Models no configurado"
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            }
            payload = {
                "messages": messages,
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            response = requests.post(
                f"{self.endpoint}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            if response.status_code == 429:
                return "❌ Rate limit alcanzado. Intenta en unos minutos."
            return f"❌ Error en API: {response.status_code}"
        except Exception as e:
            return f"❌ Error procesando imagen: {e}"


# ═══════════════════════════════════════════════════════════════
# Groq (Llama 3.3 70B — ultra rápido)
# ═══════════════════════════════════════════════════════════════

class GroqClient:
    """Cliente para Groq API."""

    def __init__(self, api_key=None, model="llama-3.3-70b-versatile"):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model
        self.last_tokens_used = 0
        self.client = None

        if not self.api_key:
            print("⚠️ Groq API key no encontrada en .env")
            return
        try:
            self.client = Groq(api_key=self.api_key)
            print("✅ Groq client inicializado (14,400 RPD gratis)")
        except Exception as e:
            print(f"⚠️ Error inicializando Groq: {e}")

    def chat(self, messages, temperature=0.7, max_tokens=4000):
        if not self.client:
            return None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if hasattr(response, "usage"):
                self.last_tokens_used = response.usage.total_tokens
            else:
                self.last_tokens_used = 0
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                print("⚠️ Groq rate limit alcanzado (30 RPM)")
                return None
            print(f"Error Groq: {error_msg}")
            return None

    def is_available(self):
        if not self.client:
            return False
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            return True
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# Helper: llamar_ia (fallback chain reutilizable)
# ═══════════════════════════════════════════════════════════════

def llamar_ia(
    prompt: str,
    groq_client: GroqClient | None = None,
    github_client: GitHubModelsClient | None = None,
    ollama_client: OllamaClient | None = None,
    system: str | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.7,
) -> str:
    """Cadena Groq → GitHub → Ollama. Usada por todos los agentes."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    if groq_client and groq_client.client:
        r = groq_client.chat(messages, temperature=temperature, max_tokens=max_tokens)
        if r:
            return r

    if github_client and github_client.client:
        r = github_client.chat(messages, temperature=temperature, max_tokens=max_tokens)
        if r:
            return r

    if ollama_client:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        r = ollama_client.generate(full_prompt, temperature=temperature, max_tokens=max_tokens)
        if r:
            return r

    return "❌ No se pudo conectar a ningún modelo de IA."
