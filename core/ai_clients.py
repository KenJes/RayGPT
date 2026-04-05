"""
Clientes de IA — Ollama, Mistral, Groq.
También expone ``llamar_ia()`` como helper de fallback chain.
"""

import os
import requests

from groq import Groq


# ═══════════════════════════════════════════════════════════════
# Ollama (local GPU)
# ═══════════════════════════════════════════════════════════════

class OllamaClient:
    """Cliente para Ollama local (GPU)."""

    def __init__(self, url="http://localhost:11434", model="llama3.1:8b"):
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
                text = data.get("response", "")
                import re as _re
                text = _re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", text, flags=_re.DOTALL).strip()
                return text or None
            return None
        except Exception as e:
            print(f"Error Ollama: {e}")
            return None

    def chat(self, messages, temperature=0.7, max_tokens=2000):
        """Chat con formato messages [{role, content}] via /api/chat."""
        try:
            response = requests.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=120,
            )
            if response.status_code == 200:
                data = response.json()
                self.last_tokens_used = data.get("eval_count", 0)
                text = data.get("message", {}).get("content", "")
                import re as _re
                text = _re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", text, flags=_re.DOTALL).strip()
                return text or None
            return None
        except Exception as e:
            print(f"Error Ollama chat: {e}")
            return None

    def is_available(self):
        try:
            r = requests.get(f"{self.url}/api/version", timeout=2)
            return r.status_code == 200
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# Mistral AI (mistral-small-latest — rápido y económico)
# ═══════════════════════════════════════════════════════════════

class MistralClient:
    """Cliente para Mistral AI API."""

    def __init__(self, api_key=None, model="mistral-small-latest"):
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        self.model = model
        self.last_tokens_used = 0
        self.client = None

        if not self.api_key:
            print("⚠️ Mistral API key no encontrada en .env")
            return
        try:
            # mistralai v2+ movió la clase principal a mistralai.client
            try:
                from mistralai.client import Mistral
            except ImportError:
                from mistralai import Mistral  # fallback v0/v1
            self.client = Mistral(api_key=self.api_key)
            print("✅ Mistral client inicializado")
        except Exception as e:
            print(f"⚠️ Error inicializando Mistral: {e}")

    def chat(self, messages, temperature=0.7, max_tokens=4000, model_override=None):
        if not self.client:
            return None
        try:
            # Truncar mensajes si el payload es muy grande
            trimmed = self._trim_messages(messages)
            response = self.client.chat.complete(
                model=model_override or self.model,
                messages=trimmed,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if hasattr(response, "usage") and response.usage:
                self.last_tokens_used = response.usage.total_tokens
            else:
                self.last_tokens_used = 0
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                print("⚠️ Mistral rate limit alcanzado")
                return None
            if "401" in error_msg or "Unauthorized" in error_msg:
                print("⚠️ Mistral API key inválida o expirada")
                return None
            print(f"Error Mistral: {error_msg}")
            return None

    def chat_with_images(self, messages, temperature=0.7, max_tokens=2000):
        """Envía mensajes multimodales (texto + imagen) usando Pixtral."""
        if not self.client:
            return "❌ Mistral no configurado"
        try:
            # Pixtral soporta el mismo formato de mensajes multimodales
            response = self.client.chat.complete(
                model="pixtral-12b-2409",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if hasattr(response, "usage") and response.usage:
                self.last_tokens_used = response.usage.total_tokens
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                return "❌ Rate limit alcanzado. Intenta en unos minutos."
            return f"❌ Error procesando imagen: {e}"

    @staticmethod
    def _trim_messages(messages, max_chars=24000):
        """Recorta historial para no exceder límite de payload."""
        total = sum(len(m.get("content", "") if isinstance(m.get("content", ""), str) else str(m.get("content", ""))) for m in messages)
        if total <= max_chars:
            return messages
        system = [m for m in messages if m["role"] == "system"]
        others = [m for m in messages if m["role"] != "system"]
        while others and sum(len(m.get("content", "") if isinstance(m.get("content", ""), str) else str(m.get("content", ""))) for m in system + others) > max_chars:
            others.pop(0)
        return system + others

    def is_available(self):
        if not self.client:
            return False
        try:
            self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            return True
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# Groq (Llama 3.3 70B — ultra rápido)
# ═══════════════════════════════════════════════════════════════

class GroqClient:
    """Cliente para Groq API."""

    def __init__(self, api_key=None, model="llama-3.1-8b-instant"):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model
        self.last_tokens_used = 0
        self.client = None

        if not self.api_key:
            print("⚠️ Groq API key no encontrada en .env")
            return
        try:
            # max_retries=0: desactiva el backoff automático del SDK.
            # Si hay 429, cae de inmediato a Mistral/Ollama en vez de esperar 30-40s.
            self.client = Groq(api_key=self.api_key, max_retries=0)
            print("✅ Groq client inicializado (14,400 RPD gratis)")
        except Exception as e:
            print(f"⚠️ Error inicializando Groq: {e}")

    def chat(self, messages, temperature=0.7, max_tokens=4000, model_override=None):
        if not self.client:
            return None
        try:
            # Truncar mensajes si el payload es muy grande (evitar 413)
            trimmed = self._trim_messages(messages)
            response = self.client.chat.completions.create(
                model=model_override or self.model,
                messages=trimmed,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if hasattr(response, "usage"):
                self.last_tokens_used = response.usage.total_tokens
            else:
                self.last_tokens_used = 0
            text = response.choices[0].message.content or ""
            # Qwen incluye bloques <think>...</think> — removerlos (incluye bloques sin cerrar)
            import re as _re
            text = _re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", text, flags=_re.DOTALL).strip()
            return text if text else None
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                print("⚠️ Groq rate limit alcanzado (30 RPM)")
                return None
            if "413" in error_msg or "Payload Too Large" in error_msg:
                print("⚠️ Groq payload demasiado grande, saltando")
                return None
            print(f"Error Groq: {error_msg}")
            return None

    @staticmethod
    def _trim_messages(messages, max_chars=24000):
        """Recorta historial para no exceder límite de payload."""
        total = sum(len(m.get("content", "")) for m in messages)
        if total <= max_chars:
            return messages
        # Conservar system + últimos mensajes, recortar historial del medio
        system = [m for m in messages if m["role"] == "system"]
        others = [m for m in messages if m["role"] != "system"]
        while others and sum(len(m.get("content", "")) for m in system + others) > max_chars:
            others.pop(0)  # quitar mensajes más viejos
        return system + others

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
    mistral_client: MistralClient | None = None,
    ollama_client: OllamaClient | None = None,
    system: str | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.7,
) -> str:
    """Cadena Groq → Mistral → Ollama. Usada por todos los agentes."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    if groq_client and groq_client.client:
        r = groq_client.chat(messages, temperature=temperature, max_tokens=max_tokens)
        if r:
            return r

    if mistral_client and mistral_client.client:
        r = mistral_client.chat(messages, temperature=temperature, max_tokens=max_tokens)
        if r:
            return r

    if ollama_client:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        r = ollama_client.generate(full_prompt, temperature=temperature, max_tokens=max_tokens)
        if r:
            return r

    return "❌ No se pudo conectar a ningún modelo de IA."
