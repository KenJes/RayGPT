"""
voice_assistant.py — Asistente de voz con doble persona.

    Dos personas:
      • Raymundo — voz masculina (Edge TTS · Jorge)
      • R.E.I.N.A. — voz femenina  (Edge TTS · Dalia)

El wake word activo coincide con la persona actual:
    - persona='raymundo' → solo responde a "Raymundo"
    - persona='reina'    → solo responde a "Reina"
Se puede cambiar en caliente: "cambia a Reina" / "cambia a Raymundo".

Ciclo principal:
    1. Escucha corta (4s) → Whisper STT
    2. ¿Contiene el wake word activo? → Sonido de activación
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
import queue
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
# Wake-word patterns  (separados por persona)
# ──────────────────────────────────────────────────────────────
_WAKE_RAYMUNDO = re.compile(
    r"\b(ray\s*mundo|ray|rai\s*mundo|raimundo|reimundo|rai)\b",
    re.IGNORECASE,
)
_WAKE_REINA = re.compile(
    r"\b(reina|reynah?|rei\s*na)\b",
    re.IGNORECASE,
)


def _split_after_wake(text: str, persona: str = "raymundo") -> tuple[bool, str]:
    """
    Si el texto contiene la wake word de la persona activa,
    devuelve (True, comando).
    """
    regex = _WAKE_REINA if persona == "reina" else _WAKE_RAYMUNDO
    m = regex.search(text)
    if not m:
        return False, ""
    command = text[m.end():].strip()
    return True, command


class VoiceAssistant:
    """
    Asistente de voz hands-free con dos personas:
    - "raymundo" → voz masculina (JorgeNeural), wake word "Raymundo"
    - "reina"    → voz femenina (DaliaNeural), wake word "Reina"
    """

    # Configuración de audio
    SAMPLE_RATE = 16000
    WAKE_LISTEN_SEC = 4      # Segundos de escucha para detectar wake word
    COMMAND_LISTEN_SEC = 8   # Segundos de escucha para capturar comando
    SILENCE_THRESHOLD = 0.01 # RMS mínimo para considerar que hay audio

    def __init__(self, process_fn, tts_fn, stt_fn, play_fn,
                 on_wake=None, on_listen=None, on_think=None, on_idle=None,
                 on_speak=None, persona="raymundo"):
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
            on_speak:   callback() — Se llama cuando empieza a responder con voz
            persona:    'raymundo' (male/Jorge) o 'reina' (female/Dalia)
        """
        self.process_fn = process_fn
        self.tts_fn = tts_fn
        self.stt_fn = stt_fn
        self.play_fn = play_fn

        self.on_wake = on_wake or (lambda: None)
        self.on_listen = on_listen or (lambda: None)
        self.on_think = on_think or (lambda: None)
        self.on_idle = on_idle or (lambda: None)
        self.on_speak = on_speak or (lambda: None)

        self.persona = persona  # 'raymundo' o 'reina'

        self._running = False
        self._thread: threading.Thread | None = None
        self._muted = False
        self._trigger_event = threading.Event()
        self._stop_recording = threading.Event()

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
        self._trigger_event.clear()
        self._stop_recording.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="VoiceAssistant")
        self._thread.start()
        logger.info("🎤 Asistente iniciado — haz clic en el orbe para hablar")

    def stop(self):
        """Detiene el asistente."""
        self._running = False
        self._trigger_event.set()      # desbloquear si está esperando
        self._stop_recording.set()     # desbloquear grabación
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("🔇 Asistente de voz detenido")

    def trigger(self):
        """Llamado al hacer clic en el orbe. Alterna escucha/parar."""
        if self._trigger_event.is_set():
            # Ya estaba escuchando → forzar parada de grabación
            self._stop_recording.set()
        else:
            # Idle → empezar a escuchar
            self._trigger_event.set()

    def mute(self):
        self._muted = True

    def unmute(self):
        self._muted = False

    @property
    def is_running(self) -> bool:
        return self._running

    # ─── Loop principal ───────────────────────────────────────

    def _loop(self):
        """Ciclo click-to-talk: espera clic → graba → procesa → responde."""
        logger.info("👂 Esperando clic en el orbe...")
        self.on_idle()

        while self._running:
            try:
                if self._muted:
                    time.sleep(0.5)
                    continue

                # 1. Esperar clic del usuario (o wake word en 2do plano)
                self._trigger_event.wait()
                if not self._running:
                    break
                self._trigger_event.clear()
                self._stop_recording.clear()

                # 2. Escuchar (animación LISTENING)
                logger.info("👂 Escuchando...")
                self.on_listen()
                cmd_audio = self._record_until_silence()
                command = ""
                if cmd_audio is not None:
                    command = self._transcribe(cmd_audio) or ""

                if not command or len(command) < 2:
                    self._speak("¿Sí? No te escuché. Inténtalo de nuevo.")
                    self.on_idle()
                    continue

                logger.info(f"Transcrito: '{command}'")

                # Detectar cambio de voz antes de procesar
                # (se maneja dentro de process_fn)

                # 3. Procesar el comando
                logger.info(f"🧠 Procesando: '{command}'")
                self.on_think()

                try:
                    response = self.process_fn(command)
                except Exception as e:
                    logger.error(f"❌ Error procesando: {e}")
                    response = f"Hubo un error: {e}"

                # 4. Responder con voz
                logger.info(f"🗣️ Respuesta: '{response[:80]}...'")
                self.on_speak()
                self._speak(response)
                self.on_idle()

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Error en voice loop: {e}")
                self.on_idle()
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

    def _record_until_silence(self, max_seconds: float = 12.0,
                               silence_sec: float = 1.5,
                               grace_sec: float = 2.0,
                               threshold: float | None = None) -> np.ndarray | None:
        """Graba audio con InputStream continuo (no abre/cierra el mic por chunk).

        grace_sec: segundos iniciales donde NO se corta por silencio
                   (da tiempo al usuario a empezar a hablar tras el clic).
        También se detiene si _stop_recording se setea (clic del usuario).
        """
        chunk_sec = 0.3
        chunk_frames = int(chunk_sec * self.SAMPLE_RATE)
        max_chunks = int(max_seconds / chunk_sec)
        silence_needed = max(1, int(silence_sec / chunk_sec))
        grace_chunks = int(grace_sec / chunk_sec)

        audio_q: queue.Queue[np.ndarray] = queue.Queue()

        def _callback(indata, frames, time_info, status):
            audio_q.put(indata.copy())

        chunks: list[np.ndarray] = []
        silent_count = 0
        has_speech = False

        try:
            with sd.InputStream(samplerate=self.SAMPLE_RATE, channels=1,
                                dtype="float32", blocksize=chunk_frames,
                                callback=_callback):
                # Calibrar ruido ambiental con los primeros 0.5s
                cal_chunks = max(1, int(0.5 / chunk_sec))
                cal_data = []
                for _ in range(cal_chunks):
                    try:
                        data = audio_q.get(timeout=1.0)
                        cal_data.append(data.flatten())
                    except queue.Empty:
                        break
                if cal_data:
                    cal_audio = np.concatenate(cal_data)
                    noise_floor = float(np.sqrt(np.mean(cal_audio ** 2)))
                else:
                    noise_floor = 0.005

                if threshold is None:
                    threshold = max(self.SILENCE_THRESHOLD, noise_floor * 3)
                logger.info(f"VAD: noise={noise_floor:.5f}, umbral={threshold:.5f}")

                # Grabar chunks del stream abierto
                for i in range(max_chunks):
                    if not self._running or self._stop_recording.is_set():
                        break
                    try:
                        data = audio_q.get(timeout=1.0)
                    except queue.Empty:
                        continue
                    flat = data.flatten()
                    chunks.append(flat)

                    rms = float(np.sqrt(np.mean(flat ** 2)))
                    if rms >= threshold:
                        has_speech = True
                        silent_count = 0
                    elif has_speech and i >= grace_chunks:
                        silent_count += 1
                        if silent_count >= silence_needed:
                            logger.debug("VAD: silencio detectado, cortando")
                            break
        except Exception as e:
            logger.error(f"Error en grabación VAD: {e}")
            return None

        if not chunks:
            return None

        audio = np.concatenate(chunks)
        peak = float(np.max(np.abs(audio)))
        logger.info(f"Audio grabado: {len(audio)/self.SAMPLE_RATE:.1f}s, "
                    f"peak={peak:.4f}, speech={'sí' if has_speech else 'no'}")
        return audio

    def _transcribe(self, audio: np.ndarray) -> str | None:
        """Transcribe audio usando la función STT provista.
        Normaliza el audio antes de enviar a Whisper."""
        import tempfile, os

        # Normalizar: amplificar para llenar el rango [-1, 1]
        peak = float(np.max(np.abs(audio)))
        if peak > 1e-6:
            audio = audio / peak * 0.95
        else:
            logger.warning("Audio prácticamente vacío (peak ≈ 0)")
            return None

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
    """Ejecuta el asistente de voz con GUI moderna."""
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

    # ── GUI ───────────────────────────────────────────────────
    from core.voice_gui import VoiceGUI
    gui = VoiceGUI(persona='raymundo')

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
            logger.info(f"🎵 Spotify: {'autenticado' if spotify_client.is_authenticated else 'no autenticado'}")
        except Exception as e:
            logger.warning(f"⚠️ Spotify no disponible: {e}")

    # Adapters + AgentLoop
    registry = build_registry(gestor, knowledge_base=knowledge_base, spotify_client=spotify_client)
    agent_logger = AgentLogger()
    agent_memory = VectorMemory()

    def _ai_chat(messages, temperature=0.4, max_tokens=2000):
        from core.tools import es_rechazo_llm
        # 1. Ollama local (gratis, ilimitado)
        r = ollama.chat(messages, temperature=temperature, max_tokens=max_tokens)
        if r and not es_rechazo_llm(r):
            return r
        # 2. Groq (rate limited)
        if groq and groq.client:
            r = groq.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if r and not es_rechazo_llm(r):
                return r
        # 3. GitHub Models GPT-4o
        if github and github.client:
            r = github.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if r and not es_rechazo_llm(r):
                return r
        return ""

    agent_loop = AgentLoop(
        registry=registry,
        ai_chat_fn=_ai_chat,
        logger=agent_logger,
        memory=agent_memory,
    )

    # Audio handler — arranca con voz masculina (Jorge = Raymundo)
    audio = get_audio_handler(voice_config={
        'engine': 'edge-tts',
        'gender': 'male',
        'rate': 180,
    })
    logger.info(f"🔊 TTS: {'disponible' if audio.is_tts_available() else 'no disponible'}")
    logger.info(f"🎤 STT: {'disponible' if audio.is_stt_available() else 'no disponible'}")

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
                assistant.persona = 'reina'
                gui.set_persona('reina')
                return "Hola, ahora soy Reina. Di 'Reina' para hablarme."
            else:
                audio.set_gender('male')
                assistant.persona = 'raymundo'
                gui.set_persona('raymundo')
                return "Qué onda, ahora soy Raymundo. Di 'Raymundo' para hablarme."

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

        # 2. Herramientas: calendario, YouTube, presentaciones, docs, web, etc.
        resultado_herramienta = gestor.procesar_mensaje(
            command, user_name="Kenneth", user_id=user_id,
        )
        if resultado_herramienta.get("ejecuto_herramienta"):
            response = resultado_herramienta["resultado"]
            agregar_mensaje(user_id, "assistant", response)
            return response

        # 3. Meta compleja → AgentLoop
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
            # 4. Chat híbrido (fallback)
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

    # ── Callbacks → GUI ───────────────────────────────────────
    def on_wake():
        gui.set_state(VoiceGUI.WAKE, "¡Activado!")

    def on_listen():
        gui.set_state(VoiceGUI.LISTENING, "Escuchando\u2026",
                      "Toca el orbe para enviar")

    def on_think():
        gui.set_state(VoiceGUI.THINKING, "Pensando\u2026")

    def on_speak():
        gui.set_state(VoiceGUI.SPEAKING, "Respondiendo\u2026")

    def on_idle():
        gui.set_state(VoiceGUI.IDLE, "Esperando\u2026",
                      "Toca el orbe para hablar")

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
        on_speak=on_speak,
        persona='raymundo',
    )
    # Conectar clic del orbe al asistente
    gui._on_orb_click = assistant.trigger
    assistant.start()
    try:
        gui.run()  # bloquea en el hilo principal (tk mainloop)
    finally:
        assistant.stop()
        logger.info("👋 Asistente de voz apagado.")


if __name__ == "__main__":
    _run_standalone()
