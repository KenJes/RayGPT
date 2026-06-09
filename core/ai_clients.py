"""
Clientes de IA — Ollama, Mistral, Groq.
También expone ``llamar_ia()`` como helper de fallback chain.
"""

import os
import re
import shutil
import time
import hashlib
import requests

from groq import Groq


def _extract_retry_after_seconds(error_msg: str) -> float | None:
    patterns = (
        r"try again in\s+([0-9]+(?:\.[0-9]+)?)s",
        r"retry after\s+([0-9]+(?:\.[0-9]+)?)s?",
        r"retry_after\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, error_msg, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (TypeError, ValueError):
                return None
    return None


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
        # Detectar placeholder — no intentar conectar con key falsa
        if self.api_key.startswith("TU_API") or len(self.api_key) < 20:
            print("⚠️ Mistral API key parece ser un placeholder, saltando inicialización")
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

    DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 60.0

    def __init__(self, api_key=None, model="llama-3.1-8b-instant"):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model
        self.last_tokens_used = 0
        self.client = None
        self._rate_limited_until = 0.0

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
        if self._rate_limited_until > time.time():
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
                cooldown = _extract_retry_after_seconds(error_msg) or self.DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS
                self._rate_limited_until = time.time() + max(cooldown, 1.0)
                print(f"⚠️ Groq rate limit alcanzado; enfriamiento temporal de {cooldown:.0f}s")
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
# GitHub Copilot API (requiere gh CLI autenticado)
# ═══════════════════════════════════════════════════════════════

class GitHubCopilotClient:
    """Cliente para GitHub Copilot API. Requiere 'gh' CLI instalado y autenticado."""

    BASE_URL = "https://api.githubcopilot.com"
    MODELS = ["gpt-4o", "gpt-4o-mini", "claude-sonnet-4-5", "o3-mini", "o1-mini"]

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.last_tokens_used = 0
        self._gh_cmd = self._resolve_gh_cmd()
        self._token: str | None = None
        self._try_init()

    @staticmethod
    def _env_token_overrides() -> list[str]:
        return [name for name in ("GH_TOKEN", "GITHUB_TOKEN") if os.environ.get(name)]

    def _resolve_gh_cmd(self) -> list[str] | None:
        gh_on_path = shutil.which("gh")
        if gh_on_path:
            return [gh_on_path]

        candidate_paths = [
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "GitHub CLI", "gh.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "GitHub CLI", "gh.exe"),
        ]
        for candidate in candidate_paths:
            if candidate and os.path.isfile(candidate):
                return [candidate]
        return None

    @staticmethod
    def _gh_env() -> dict[str, str]:
        env = os.environ.copy()
        env.pop("GITHUB_TOKEN", None)
        env.pop("GH_TOKEN", None)
        return env

    def _read_token(self) -> str | None:
        if not self._gh_cmd:
            return None
        import subprocess
        result = subprocess.run(
            [*self._gh_cmd, "auth", "token"],
            capture_output=True, text=True, timeout=5,
            env=self._gh_env(),
        )
        token = result.stdout.strip()
        return token or None

    def _try_init(self):
        try:
            self._refresh_token()
            if self._token:
                print(f"✅ GitHub Copilot client inicializado (modelo: {self.model})")
            elif self._gh_cmd:
                overrides = self._env_token_overrides()
                if overrides:
                    joined = ", ".join(overrides)
                    print(
                        "⚠️ GitHub Copilot: gh no tiene sesión guardada. "
                        f"Hay {joined} en el entorno; si es inválido, `gh auth status` o `gh auth login` puede usarlo y confundirte. "
                        "Abre una terminal sin esas variables o corrige ese token."
                    )
                else:
                    print("⚠️ GitHub Copilot: no hay token activo. Ejecuta 'gh auth login'")
            else:
                print("⚠️ GitHub Copilot: gh CLI no encontrado. Instala desde https://cli.github.com o reinicia VS Code para recargar PATH")
        except FileNotFoundError:
            print("⚠️ GitHub Copilot: gh CLI no encontrado. Instala desde https://cli.github.com")
        except Exception as e:
            print(f"⚠️ GitHub Copilot init error: {e}")

    def _refresh_token(self):
        try:
            token = self._read_token()
            self._token = token if token and len(token) > 10 else None
            return self._token
        except Exception:
            self._token = None
            return None

    @property
    def available(self) -> bool:
        if not self._token:
            self._refresh_token()
        return bool(self._token)

    def set_model(self, model: str):
        self.model = model
        print(f"🤖 Copilot modelo cambiado a: {model}")

    def chat(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        model_override: str | None = None,
    ) -> str | None:
        if not self._token:
            self._refresh_token()
        if not self._token:
            return None
        model = model_override or self.model
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "editor-version": "vscode/1.95.0",
            "editor-plugin-version": "GitHub.copilot-chat/0.22.4",
            "Copilot-Integration-Id": "vscode-chat",
            "User-Agent": "GitHubCopilot/1.0",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = requests.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload, headers=headers, timeout=60,
            )
            if resp.status_code == 401:
                self._refresh_token()
                if self._token:
                    headers["Authorization"] = f"Bearer {self._token}"
                    resp = requests.post(
                        f"{self.BASE_URL}/chat/completions",
                        json=payload, headers=headers, timeout=60,
                    )
            resp.raise_for_status()
            data = resp.json()
            self.last_tokens_used = data.get("usage", {}).get("total_tokens", 0)
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            print("⚠️ GitHub Copilot: timeout")
            return None
        except Exception as e:
            print(f"Error GitHub Copilot ({model}): {e}")
            return None

    def is_available(self) -> bool:
        return self.available


# ═══════════════════════════════════════════════════════════════
# EdgeRouter — clasificador de complejidad + caché + compresor
# ═══════════════════════════════════════════════════════════════

class EdgeRouter:
    """
    Router Edge-first para minimizar tokens en nube y maximizar velocidad.

    Estrategia:
      SIMPLE  → Ollama local (0 tokens cloud, respuesta ~200ms)
      MEDIUM  → Groq cloud (gratis, ~400ms)
      COMPLEX → Groq → Mistral → Ollama fallback
    """

    # Patrones que indican tarea simple (el modelo local puede manejar bien)
    _SIMPLE_PATTERNS = [
        r"^\s*(hola|hi|hey|buenos días|buenas tardes|buenas noches|qué tal|cómo estás|como estas)",
        r"^\s*(gracias|thanks|ok|okay|entendido|perfecto|listo|de nada|con gusto)",
        r"^\s*(sí|si|no|claro|por supuesto|desde luego|exacto|correcto)",
        r"^\s*(adiós|bye|hasta luego|nos vemos|chao|chau)",
        r"^.{1,60}$",  # mensajes muy cortos (menos de 60 caracteres)
    ]

    # Patrones que indican tarea compleja (requiere nube o modelo grande)
    _COMPLEX_PATTERNS = [
        r"(código|code|programa|script|función|función|class|implementa|desarrolla|refactori)",
        r"(analiza|análisis|presenta|presentación|informe|reporte|documento largo)",
        r"(busca en internet|investiga|research|web scraping|search online)",
        r"(google|drive|sheets|slides|gmail|calendar|spotify|whatsapp)",
        r"(imagen|foto|pdf|archivo adjunto|\[CONTENIDO EXTRAÍDO)",
        r"(escribe un ensayo|redacta|elabora un plan|estrategia completa|propuesta detallada)",
        r"(compara .{10,} con .{10,}|diferencias entre .{10,} y .{10,})",
    ]

    _cache: dict[str, str] = {}
    _cache_ttl: dict[str, float] = {}
    CACHE_TTL_SECONDS = 300  # 5 minutos

    @classmethod
    def classify(cls, messages: list[dict]) -> str:
        """Clasifica la complejidad de la consulta: 'simple', 'medium' o 'complex'."""
        user_msgs = [m for m in messages if m.get("role") == "user"]
        if not user_msgs:
            return "medium"

        last = user_msgs[-1].get("content", "")
        # Contenido multimodal (lista con imágenes) = siempre complex
        if isinstance(last, list):
            return "complex"

        text = str(last).strip()

        # Patrones de complejidad alta
        for p in cls._COMPLEX_PATTERNS:
            if re.search(p, text, re.IGNORECASE):
                return "complex"

        # Historial largo indica sesión activa con contexto acumulado
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        if total_chars > 10000:
            return "complex"
        if total_chars > 4000:
            return "medium"

        # Patrones de consulta simple
        for p in cls._SIMPLE_PATTERNS:
            if re.search(p, text, re.IGNORECASE):
                return "simple"

        # Longitud del mensaje como señal de complejidad
        if len(text) > 300:
            return "complex"
        if len(text) > 120:
            return "medium"

        return "medium"

    @classmethod
    def cache_key(cls, messages: list[dict]) -> str:
        user_msgs = [m for m in messages if m.get("role") == "user"]
        content = str(user_msgs[-1].get("content", "")) if user_msgs else ""
        return hashlib.md5(content.encode()).hexdigest()

    @classmethod
    def get_cache(cls, key: str) -> str | None:
        if key in cls._cache:
            if time.time() - cls._cache_ttl.get(key, 0) < cls.CACHE_TTL_SECONDS:
                return cls._cache[key]
            del cls._cache[key]
            del cls._cache_ttl[key]
        return None

    @classmethod
    def set_cache(cls, key: str, value: str):
        # Limitar caché a 200 entradas (LRU simple: eliminar el más viejo)
        if len(cls._cache) >= 200:
            oldest = min(cls._cache_ttl, key=cls._cache_ttl.get)
            del cls._cache[oldest]
            del cls._cache_ttl[oldest]
        cls._cache[key] = value
        cls._cache_ttl[key] = time.time()

    @classmethod
    def compress_messages(cls, messages: list[dict], max_chars: int = 12000) -> list[dict]:
        """
        Comprime el historial antes de enviar a nube para minimizar tokens.
        Conserva system prompt + últimos 3 intercambios + resume el resto.
        """
        total = sum(len(str(m.get("content", ""))) for m in messages)
        if total <= max_chars:
            return messages

        system = [m for m in messages if m["role"] == "system"]
        others = [m for m in messages if m["role"] != "system"]

        # Conservar últimos 6 mensajes (3 intercambios user/assistant)
        recent = others[-6:] if len(others) > 6 else others
        old = others[:-6] if len(others) > 6 else []

        if old:
            summary_parts = []
            for m in old:
                role = "Usuario" if m["role"] == "user" else "Asistente"
                content = str(m.get("content", ""))[:150].replace("\n", " ")
                summary_parts.append(f"[{role}]: {content}...")
            summary = "Contexto previo resumido:\n" + "\n".join(summary_parts)
            context_msg = {"role": "user", "content": summary}
            compressed = system + [context_msg] + recent
        else:
            compressed = system + recent

        return compressed


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
    use_edge_routing: bool = True,
) -> str:
    """
    Cadena Edge-first: Local(simple) → Groq(medium) → Mistral(complex) → Ollama(fallback).

    Con use_edge_routing=True (default):
      - Consultas simples van directo al modelo local → 0 tokens cloud
      - Consultas medium van a Groq (gratis) con contexto comprimido
      - Consultas complejas van a Groq → Mistral → Ollama fallback
      - Respuestas cacheadas para consultas repetidas (~300ms → ~0ms)

    Con use_edge_routing=False: comportamiento legacy Groq → Mistral → Ollama.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    if use_edge_routing:
        # 1. Verificar caché primero (respuesta instantánea)
        cache_key = EdgeRouter.cache_key(messages)
        cached = EdgeRouter.get_cache(cache_key)
        if cached:
            return cached

        complexity = EdgeRouter.classify(messages)

        # 2. SIMPLE → local primero (0 tokens cloud, latencia mínima)
        if complexity == "simple" and ollama_client and ollama_client.is_available():
            r = ollama_client.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if r:
                EdgeRouter.set_cache(cache_key, r)
                return r

        # 3. MEDIUM/COMPLEX → Groq con contexto comprimido
        if groq_client and groq_client.client:
            compressed = EdgeRouter.compress_messages(messages)
            r = groq_client.chat(compressed, temperature=temperature, max_tokens=max_tokens)
            if r:
                if complexity in ("simple", "medium"):
                    EdgeRouter.set_cache(cache_key, r)
                return r

        # 4. COMPLEX → GitHub Copilot si está disponible (sin RPM)
        # (llamar_ia no usa make_ai_chat_fn, por lo que Copilot necesita su propio slot aquí)
        # Se importa de forma diferida para evitar referencia circular
        # --- Copilot no es argumento de llamar_ia; se deja para make_ai_chat_fn ---

        # 4b. COMPLEX → Mistral con contexto comprimido
        if mistral_client and mistral_client.client:
            compressed = EdgeRouter.compress_messages(messages)
            r = mistral_client.chat(compressed, temperature=temperature, max_tokens=max_tokens)
            if r:
                return r

        # 5. Fallback final → local sin importar complejidad
        if ollama_client:
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            r = ollama_client.generate(full_prompt, temperature=temperature, max_tokens=max_tokens)
            if r:
                return r

    else:
        # Comportamiento legacy: Groq → Mistral → Ollama
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


# ─────────────────────────────────────────────────────────────────────────────
#  Fábrica compartida de función de chat con fallback Groq → Mistral → Ollama
# ─────────────────────────────────────────────────────────────────────────────

def make_ai_chat_fn(
    groq_client: "GroqClient | None" = None,
    mistral_client: "MistralClient | None" = None,
    ollama_client: "OllamaClient | None" = None,
    copilot_client: "GitHubCopilotClient | None" = None,
    copilot_model: str | None = None,
    compress: bool = True,
    compress_max_chars: int = 14000,
    filter_rejections: bool = True,
):
    """
    Devuelve una función de chat AI con cadena de fallback.

    Prioridad: Ollama(simple) → Copilot(medium/complex) → Groq → Mistral → Ollama.

    Args:
        groq_client:     Instancia de GroqClient (puede ser None).
        mistral_client:  Instancia de MistralClient (puede ser None).
        ollama_client:   Instancia de OllamaClient (puede ser None).
        copilot_client:  Instancia de GitHubCopilotClient — primer slot nube si disponible.
        copilot_model:   Modelo Copilot a usar (default: gpt-4o-mini para el loop agéntico).
                         Pasa 'gpt-4o' para calidad máxima en GUI, None para usar el default.
        compress:        True → comprime historial (WhatsApp). False → sin comprimir (GUI).
        compress_max_chars: Límite caracteres para compresión.
        filter_rejections:  True → filtra respuestas de rechazo. False → acepta todo.

    Returns:
        Callable con firma (messages, temperature=0.4, max_tokens=2000) -> str
    """
    # gpt-4o-mini: ~2x más rápido que gpt-4o, mismo límite de contexto, ideal para agentloop
    _copilot_model = copilot_model or "gpt-4o-mini"
    def _chat_fn(messages, temperature=0.4, max_tokens=2000):
        if filter_rejections:
            from core.tools import es_rechazo_llm
            ok = lambda r: bool(r) and not es_rechazo_llm(r)
        else:
            ok = lambda r: bool(r)

        complexity = EdgeRouter.classify(messages)

        # Consultas simples (saludos, ok/gracias, mensajes ≤60 chars) → local
        # Sin gastar tokens de API, latencia mínima
        if complexity == "simple" and ollama_client:
            r = ollama_client.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if ok(r):
                return r

        # Consultas medium/complex → comprimir historial y enviar a nube
        msgs = (
            EdgeRouter.compress_messages(messages, max_chars=compress_max_chars)
            if compress
            else messages
        )

        # GitHub Copilot primero para medium/complex (modelo potente, sin RPM limit)
        if copilot_client and copilot_client.available:
            r = copilot_client.chat(msgs, temperature=temperature, max_tokens=max_tokens,
                                    model_override=_copilot_model)
            if ok(r):
                return r

        if groq_client and groq_client.client:
            r = groq_client.chat(msgs, temperature=temperature, max_tokens=max_tokens)
            if ok(r):
                return r

        if mistral_client and mistral_client.client:
            r = mistral_client.chat(msgs, temperature=temperature, max_tokens=max_tokens)
            if ok(r):
                return r

        # Fallback final: local sin importar complejidad
        if ollama_client:
            r = ollama_client.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if ok(r):
                return r

        return ""

    return _chat_fn
