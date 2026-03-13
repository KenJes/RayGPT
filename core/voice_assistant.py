"""
voice_assistant.py — R.E.I.N.A. · Asistente de voz estilo Alexa.

    R.E.I.N.A.  —  Raymundo's Enhanced Intelligent Neural Assistant
    La contraparte femenina de Raymundo (Rey → Reina).

Escucha continuamente con el micrófono, detecta la wake word "Reina"
(o "Raymundo" como alias), captura el comando que sigue, lo procesa
con el cerebro agéntico, y responde con voz neural (Edge TTS · Dalia).

Ciclo principal:
    1. Escucha corta (4s) → Whisper STT
    2. ¿Contiene "Reina" / "Raymundo"? → Sonido de activación
    3. Escucha larga (8s) → Captura el comando
    4. Procesar con chat_hibrido / AgentLoop / Spotify
    5. TTS (Edge TTS DaliaNeural) → Responder con voz
    6. Repetir

Uso:
    python -m core.voice_assistant
    o desde rAImundoGPT exe.bat --voice
    o Reina Voz.bat
"""

from __future__ import annotations

import logging
import re
import sys
import threading
import time
from pathlib import Path

import numpy as np

# Agregar raíz del proyecto al path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Dependencias opcionales
# ──────────────────────────────────────────────────────────────
try:
    import sounddevice as sd
    _SD = True
except ImportError:
    _SD = False

try:
    import soundfile as sf
    _SF = True
except ImportError:
    _SF = False


# ──────────────────────────────────────────────────────────────
# Wake-word patterns
# ──────────────────────────────────────────────────────────────
_WAKE_RE = re.compile(
    r"\b(reina|reynah?|rei\s*na"
    r"|ray\s*mundo|ray|rai\s*mundo|raimundo|reimundo|rai)\b",
    re.IGNORECASE,
)


def _split_after_wake(text: str) -> tuple[bool, str]:
    """
    Si el texto contiene la wake word, devuelve (True, comando).
    El comando es todo lo que viene después de la wake word.
    """
    m = _WAKE_RE.search(text)
    if not m:
        return False, ""
    command = text[m.end():].strip()
    return True, command


class VoiceAssistant:
    """
    R.E.I.N.A. — Raymundo's Enhanced Intelligent Neural Assistant.
    Asistente de voz hands-free: escucha → detecta "Reina" → ejecuta → responde.
    """

    # Configuración de audio
    SAMPLE_RATE = 16000
    WAKE_LISTEN_SEC = 4      # Segundos de escucha para detectar wake word
    COMMAND_LISTEN_SEC = 8   # Segundos de escucha para capturar comando
    SILENCE_THRESHOLD = 0.01 # RMS mínimo para considerar que hay audio

    def __init__(self, process_fn, tts_fn, stt_fn, play_fn,
                 on_wake=None, on_listen=None, on_think=None, on_idle=None):
        """
        Args:
            process_fn: callable(str) → str  — Procesa mensaje, devuelve respuesta
            tts_fn:     callable(str) → str  — Text-to-speech, devuelve path a WAV
            stt_fn:     callable(str) → str  — Speech-to-text, devuelve transcripción
            play_fn:    callable(str) → bool — Reproduce archivo de audio
            on_wake:    callback() — Se llama cuando se detecta la wake word
            on_listen:  callback() — Se llama cuando empieza a escuchar comando
            on_think:   callback() — Se llama cuando está procesando
            on_idle:    callback() — Se llama cuando vuelve a modo escucha
        """
        self.process_fn = process_fn
        self.tts_fn = tts_fn
        self.stt_fn = stt_fn
        self.play_fn = play_fn

        self.on_wake = on_wake or (lambda: None)
        self.on_listen = on_listen or (lambda: None)
        self.on_think = on_think or (lambda: None)
        self.on_idle = on_idle or (lambda: None)

        self._running = False
        self._thread: threading.Thread | None = None
        self._muted = False

    # ─── Control ──────────────────────────────────────────────

    def start(self):
        """Inicia el asistente de voz en un hilo de fondo."""
        if self._running:
            return
        if not _SD or not _SF:
            logger.error("❌ sounddevice/soundfile no disponibles. "
                         "Instala con: pip install sounddevice soundfile")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="VoiceAssistant")
        self._thread.start()
        logger.info("🎙️ R.E.I.N.A. iniciada — di 'Reina' para activar")

    def stop(self):
        """Detiene el asistente."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("🔇 Asistente de voz detenido")

    def mute(self):
        self._muted = True

    def unmute(self):
        self._muted = False

    @property
    def is_running(self) -> bool:
        return self._running

    # ─── Loop principal ───────────────────────────────────────

    def _loop(self):
        """Ciclo principal: escucha → detecta → procesa → responde."""
        logger.info("👂 Esperando wake word 'Reina'...")
        self.on_idle()

        while self._running:
            try:
                if self._muted:
                    time.sleep(0.5)
                    continue

                # 1. Escucha corta para detectar wake word
                audio = self._record(self.WAKE_LISTEN_SEC)
                if audio is None:
                    continue

                # Verificar que hay sonido real (no silencio)
                rms = np.sqrt(np.mean(audio ** 2))
                if rms < self.SILENCE_THRESHOLD:
                    continue

                # 2. Transcribir para buscar wake word
                text = self._transcribe(audio)
                if not text:
                    continue

                detected, command = _split_after_wake(text)
                if not detected:
                    continue

                # ¡Wake word detectada!
                logger.info(f"🔔 Wake word detectada! Comando inline: '{command}'")
                self.on_wake()

                # 3. Si el comando vino junto con la wake word, usarlo
                #    Si no, escuchar más tiempo
                if not command or len(command) < 3:
                    logger.info("👂 Escuchando comando...")
                    self.on_listen()
                    cmd_audio = self._record(self.COMMAND_LISTEN_SEC)
                    if cmd_audio is not None:
                        cmd_rms = np.sqrt(np.mean(cmd_audio ** 2))
                        if cmd_rms >= self.SILENCE_THRESHOLD:
                            command = self._transcribe(cmd_audio) or ""

                if not command or len(command) < 2:
                    # No dijo nada después de la wake word
                    self._speak("¿Sí? ¿Qué necesitas?")
                    self.on_idle()
                    continue

                # 4. Procesar el comando
                logger.info(f"🧠 Procesando: '{command}'")
                self.on_think()

                try:
                    response = self.process_fn(command)
                except Exception as e:
                    logger.error(f"❌ Error procesando: {e}")
                    response = f"Hubo un error: {e}"

                # 5. Responder con voz
                logger.info(f"🗣️ Respuesta: '{response[:80]}...'")
                self._speak(response)
                self.on_idle()

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Error en voice loop: {e}")
                time.sleep(1)

        logger.info("🛑 Voice loop terminado")

    # ─── Helpers ──────────────────────────────────────────────

    def _record(self, seconds: float) -> np.ndarray | None:
        """Graba audio del micrófono."""
        try:
            frames = int(seconds * self.SAMPLE_RATE)
            audio = sd.rec(frames, samplerate=self.SAMPLE_RATE,
                           channels=1, dtype="float32")
            sd.wait()
            return audio.flatten()
        except Exception as e:
            logger.error(f"Error grabando: {e}")
            return None

    def _transcribe(self, audio: np.ndarray) -> str | None:
        """Transcribe audio usando la función STT provista."""
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False,
                                          dir=str(_ROOT / "data"))
        try:
            sf.write(tmp.name, audio, self.SAMPLE_RATE)
            tmp.close()
            text = self.stt_fn(tmp.name)
            return text
        except Exception as e:
            logger.error(f"Error transcribiendo: {e}")
            return None
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def _speak(self, text: str):
        """Convierte texto a voz y lo reproduce."""
        if not text:
            return
        # Limpiar markdown y caracteres especiales
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # **bold** → bold
        clean = re.sub(r"[*_`#]", "", clean)
        clean = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", clean)  # [text](url) → text
        clean = clean.strip()
        if not clean:
            return

        # Limitar largo para TTS (no leer textos enormes)
        if len(clean) > 600:
            clean = clean[:600] + "... y más."

        try:
            audio_file = self.tts_fn(clean)
            if audio_file:
                self.play_fn(audio_file)
        except Exception as e:
            logger.error(f"Error en TTS/reproducción: {e}")


# ──────────────────────────────────────────────────────────────
# Standalone: python -m core.voice_assistant
# ──────────────────────────────────────────────────────────────
def _run_standalone():
    """Ejecuta el asistente de voz como programa independiente."""
    import os
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    print("=" * 60)
    print("  👑  R.E.I.N.A. — Asistente de Voz")
    print("  Raymundo's Enhanced Intelligent Neural Assistant")
    print("  Di 'Reina' seguido de tu comando (o 'Raymundo')")
    print("  Ctrl+C para salir")
    print("=" * 60)

    # ── Inicializar cerebro ───────────────────────────────────
    from core.config import config_agente, AppConfig
    from core.ai_clients import OllamaClient, GitHubModelsClient, GroqClient
    from core.tools import GestorHerramientas
    from core.audio_handler import get_audio_handler
    from core.adapters import build_registry
    from core.agent_loop import AgentLoop, es_meta_compleja
    from core.agent_logger import AgentLogger
    from core.agent_memory import VectorMemory
    from core.knowledge_db import KnowledgeBase
    from core.spotify_client import SpotifyClient
    from core.conversation_db import agregar_mensaje, get_contexto_completo

    cfg = AppConfig()
    ollama = OllamaClient(cfg.ollama_url, cfg.ollama_model)
    github = GitHubModelsClient(cfg.github_token)
    groq = GroqClient()
    gestor = GestorHerramientas(ollama, github, google=cfg.google_client, groq=groq)
    knowledge_base = KnowledgeBase()

    # Spotify
    spotify_client = None
    sp_id = os.getenv("SPOTIFY_CLIENT_ID") or config_agente.get("spotify", {}).get("client_id", "")
    sp_secret = os.getenv("SPOTIFY_CLIENT_SECRET") or config_agente.get("spotify", {}).get("client_secret", "")
    sp_redirect = os.getenv("SPOTIFY_REDIRECT_URI") or config_agente.get("spotify", {}).get(
        "redirect_uri", "http://127.0.0.1:5000/spotify/callback"
    )
    if sp_id and sp_secret:
        try:
            spotify_client = SpotifyClient(sp_id, sp_secret, sp_redirect)
            status = "autenticado" if spotify_client.is_authenticated else "no autenticado"
            print(f"  🎵 Spotify: {status}")
        except Exception as e:
            print(f"  ⚠️ Spotify no disponible: {e}")

    # Adapters + AgentLoop
    registry = build_registry(gestor, knowledge_base=knowledge_base, spotify_client=spotify_client)
    agent_logger = AgentLogger()
    agent_memory = VectorMemory()

    def _ai_chat(messages, temperature=0.4, max_tokens=2000):
        if groq and groq.client:
            r = groq.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if r:
                return r
        if github and github.client:
            r = github.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if r:
                return r
        prompt = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in messages)
        return ollama.generate(prompt, temperature=temperature, max_tokens=max_tokens) or ""

    agent_loop = AgentLoop(
        ai_chat_fn=_ai_chat,
        adapter_registry=registry,
        logger=agent_logger,
        memory=agent_memory,
    )

    # Audio handler
    audio = get_audio_handler()
    print(f"  🔊 TTS: {'✅' if audio.is_tts_available() else '❌'}")
    print(f"  🎤 STT: {'✅' if audio.is_stt_available() else '❌'}")

    # ── Importar detección de Spotify ────────────────────────
    from core.spotify_client import detect_spotify_intent

    # ── Función de procesamiento ──────────────────────────────
    user_id = "voice_local"

    # ── Regex para cambio de voz ────────────────────────────
    _SWITCH_RE = re.compile(
        r"(?:cambia(?:r|te)?|pon(?:me|te)?|usa(?:r)?|switch|quiero)\s+"
        r"(?:a\s+|la\s+|el\s+)?(?:voz\s+(?:de\s+)?)?"
        r"(reina|dalia|jorge|raymundo|masculin[oa]|femenin[oa]|hombre|mujer)",
        re.IGNORECASE,
    )

    def process_command(command: str) -> str:
        """Procesa un comando de voz y devuelve la respuesta en texto."""
        # 0. Cambio de voz
        sw = _SWITCH_RE.search(command)
        if sw:
            quien = sw.group(1).lower()
            if quien in ('reina', 'dalia', 'femenina', 'femenino', 'mujer'):
                audio.set_gender('female')
                return "Listo, ahora soy Reina. ¿Qué necesitas?"
            else:
                audio.set_gender('male')
                return "Qué onda, ahora soy Jorge. ¿En qué te ayudo?"

        # Guardar en historial
        agregar_mensaje(user_id, "user", command)

        # 1. Spotify: comandos rápidos
        if spotify_client and spotify_client.is_authenticated:
            intent, query = detect_spotify_intent(command.lower().strip())
            if intent:
                try:
                    if intent == "pause":
                        result = spotify_client.pause()
                    elif intent == "play" and query:
                        result = spotify_client.play(query)
                    elif intent == "play":
                        result = spotify_client.play()
                    elif intent == "next":
                        result = spotify_client.next_track()
                    elif intent == "previous":
                        result = spotify_client.previous_track()
                    elif intent == "current":
                        result = spotify_client.current_track()
                    else:
                        result = None
                    if result:
                        agregar_mensaje(user_id, "assistant", result)
                        return result
                except Exception as e:
                    return f"Error Spotify: {e}"

        # 2. Meta compleja → AgentLoop
        if es_meta_compleja(command):
            try:
                kb_context = knowledge_base.build_knowledge_context(query=command)
                conv_context = get_contexto_completo(user_id)
                result = agent_loop.run(
                    goal=command,
                    knowledge_context=kb_context,
                    conversation_context=conv_context,
                )
                response = result.get("response", "No obtuve respuesta del agente")
            except Exception as e:
                response = f"Error del agente: {e}"
        else:
            # 3. Chat híbrido
            try:
                kb_context = knowledge_base.build_knowledge_context(query=command)
                conv_context = get_contexto_completo(user_id)
                response = gestor.chat_hibrido(
                    command,
                    user_name="Kenneth",
                    user_id=user_id,
                    history=conv_context,
                    knowledge_context=kb_context,
                )
                if not response:
                    response = "No pude generar una respuesta"
            except Exception as e:
                response = f"Error: {e}"

        agregar_mensaje(user_id, "assistant", response)
        return response

    # ── Callbacks de estado ────────────────────────────────────
    def on_wake():
        print("\n🔔 ¡Activado!")

    def on_listen():
        print("👂 Escuchando comando...")

    def on_think():
        print("🧠 Pensando...")

    def on_idle():
        print("💤 Esperando... (di 'Reina')")

    # ── Crear y arrancar ──────────────────────────────────────
    assistant = VoiceAssistant(
        process_fn=process_command,
        tts_fn=audio.text_to_speech,
        stt_fn=audio.speech_to_text,
        play_fn=audio.play_audio,
        on_wake=on_wake,
        on_listen=on_listen,
        on_think=on_think,
        on_idle=on_idle,
    )

    print("\n" + "=" * 60)
    assistant.start()

    try:
        while assistant.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\n👋 Apagando R.E.I.N.A....")
        assistant.stop()
        print("✅ Adiós!")


if __name__ == "__main__":
    _run_standalone()
