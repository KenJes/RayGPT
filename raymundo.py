"""
🤖 RAYMUNDO — AGENTE IA UNIFICADO
Interfaz gráfica (tkinter) que integra todos los módulos de core/.

Autor: Axoloit / Kenneth Alcalá
Versión: 3.0 (modular)
"""

import tkinter as tk
from tkinter import scrolledtext, filedialog
import threading
from pathlib import Path

# ── Core imports ───────────────────────────────────────────────
from core.config import config_agente, AppConfig
from core.ai_clients import OllamaClient, GitHubModelsClient, GroqClient
from core.tools import GestorHerramientas
from core.audio_handler import get_audio_handler

# ── AgentField connector (opcional) ───────────────────────────
try:
    from agentes.raymundo_connector import (
        delegar as _af_delegar,
        esta_disponible as _af_disponible,
    )
    _AGENTFIELD_ENABLED = True
except ImportError:
    _AGENTFIELD_ENABLED = False
    def _af_delegar(*a, **kw): return None
    def _af_disponible(): return False


# ═══════════════════════════════════════════════════════════════
# INTERFAZ GRÁFICA
# ═══════════════════════════════════════════════════════════════

class ChatGUI:
    """Interfaz gráfica estilo ChatGPT."""

    def __init__(self, root):
        self.root = root
        nombre = config_agente.get_nombre_agente()
        self.root.title(f"🤖 {nombre} - IA Unificada")
        self.root.geometry("1100x800")
        self.root.configure(bg="#212121")
        self.root.minsize(900, 600)

        # Inicializar componentes
        cfg = AppConfig()
        self.ollama = OllamaClient(cfg.ollama_url, cfg.ollama_model)
        self.github = GitHubModelsClient(cfg.github_token)
        self.groq_client = GroqClient()
        self.google = cfg.google_client
        self.herramientas = GestorHerramientas(
            self.ollama, self.github, google=self.google, groq=self.groq_client
        )

        # Audio
        self.audio_handler = get_audio_handler()
        self.ultimo_audio_respuesta = None

        self.historial_chat = []
        self.contador_mensajes = 0
        self.procesando = False
        self.archivo_adjunto = None

        self._construir_interfaz()
        self._mostrar_bienvenida()

    # ───── UI ──────────────────────────────────────────────────

    def _construir_interfaz(self):
        # Header
        header = tk.Frame(self.root, bg="#1f1f1f", height=50)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        nombre_agente = config_agente.get_nombre_agente()
        tk.Label(
            header, text=f"🤖 {nombre_agente} v3.0",
            font=("Segoe UI", 14, "bold"), bg="#1f1f1f", fg="#ffffff",
        ).pack(side="left", padx=20)

        self.label_estado = tk.Label(
            header, text="● Listo",
            font=("Segoe UI", 9), bg="#1f1f1f", fg="#10a37f",
        )
        self.label_estado.pack(side="right", padx=15)

        # Chat area
        self.text_chat = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, bg="#212121", fg="#ececec",
            font=("Segoe UI", 10), relief="flat", padx=20, pady=20,
            state="disabled",
        )
        self.text_chat.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Tags
        self.text_chat.tag_config("user", foreground="#ececec")
        self.text_chat.tag_config("assistant", foreground="#d4d4d4")
        self.text_chat.tag_config("user_label", foreground="#10a37f", font=("Segoe UI", 10, "bold"))
        self.text_chat.tag_config("assistant_label", foreground="#9e9e9e", font=("Segoe UI", 10, "bold"))

        # Input area
        input_container = tk.Frame(self.root, bg="#212121")
        input_container.pack(fill="x", padx=20, pady=(0, 20))
        input_frame = tk.Frame(input_container, bg="#2d2d2d", relief="flat")
        input_frame.pack(fill="x")

        self.entry_mensaje = tk.Text(
            input_frame, height=1, bg="#2d2d2d", fg="#ececec",
            font=("Segoe UI", 11), relief="flat", padx=15, pady=12,
            wrap=tk.WORD, insertbackground="#ffffff",
        )
        self.entry_mensaje.pack(fill="both", expand=True, side="left")
        self.entry_mensaje.bind("<Return>", self._enviar_mensaje_enter)

        # Botón grabar audio
        self.btn_grabar = tk.Button(
            input_frame, text="🎤", command=self._toggle_grabacion,
            bg="#2d2d2d", fg="#e0e0e0", font=("Segoe UI", 12),
            relief="flat", padx=10, cursor="hand2",
        )
        self.btn_grabar.pack(side="right", padx=5, pady=8)

        # Botón reproducir audio
        self.btn_reproducir = tk.Button(
            input_frame, text="🔊", command=self._reproducir_ultima_respuesta,
            bg="#2d2d2d", fg="#e0e0e0", font=("Segoe UI", 12),
            relief="flat", padx=10, cursor="hand2", state="disabled",
        )
        self.btn_reproducir.pack(side="right", padx=5, pady=8)

        # Botón adjuntar
        tk.Button(
            input_frame, text="📎", command=self._seleccionar_archivo,
            bg="#2d2d2d", fg="#e0e0e0", font=("Segoe UI", 12),
            relief="flat", padx=10, cursor="hand2",
        ).pack(side="right", padx=5, pady=8)

        # Botón enviar
        tk.Button(
            input_frame, text="➤", command=self._enviar_mensaje,
            bg="#10a37f", fg="#ffffff", font=("Segoe UI", 14, "bold"),
            relief="flat", padx=15, pady=8, cursor="hand2", width=3,
        ).pack(side="right", padx=8, pady=8)

    # ───── Bienvenida ─────────────────────────────────────────

    def _mostrar_bienvenida(self):
        nombre = config_agente.get_nombre_agente()
        self.text_chat.config(state="normal")
        self.text_chat.insert("end", f"Hola! Soy {nombre} ¿En qué puedo ayudarte?")
        self.text_chat.config(state="disabled")

    # ───── Audio ──────────────────────────────────────────────

    def _toggle_grabacion(self):
        if not self.audio_handler.is_stt_available():
            return
        if not self.audio_handler.is_recording:
            if self.audio_handler.start_recording(duration=30):
                self.btn_grabar.config(fg="#ff4444", text="⏹️")
                self.label_estado.config(text="🎙️ Grabando...", fg="#ff4444")
        else:
            self.btn_grabar.config(fg="#e0e0e0", text="🎤")
            self.label_estado.config(text="⏳ Procesando audio...", fg="#ffa500")
            threading.Thread(target=self._procesar_audio_grabado, daemon=True).start()

    def _procesar_audio_grabado(self):
        audio_file = self.audio_handler.stop_recording()
        if not audio_file:
            self.root.after(0, lambda: self.label_estado.config(text="❌ Error", fg="#ff4444"))
            return
        texto = self.audio_handler.speech_to_text(audio_file)
        if texto and texto.strip():
            self.root.after(0, lambda: self.entry_mensaje.delete("1.0", tk.END))
            self.root.after(0, lambda: self.entry_mensaje.insert("1.0", texto))
            self.root.after(0, lambda: self.label_estado.config(text="✅ Transcrito", fg="#10a37f"))
            self.root.after(100, self._enviar_mensaje)
        else:
            self.root.after(0, lambda: self.label_estado.config(text="⚠️ Sin habla detectada", fg="#ffa500"))

    def _reproducir_ultima_respuesta(self):
        if not self.ultimo_audio_respuesta or not self.audio_handler.is_tts_available():
            return
        threading.Thread(
            target=self._reproducir_audio,
            args=(self.ultimo_audio_respuesta,),
            daemon=True,
        ).start()

    def _reproducir_audio(self, audio_file):
        self.root.after(0, lambda: self.label_estado.config(text="🔊 Reproduciendo...", fg="#10a37f"))
        self.audio_handler.play_audio(audio_file)
        self.root.after(0, lambda: self.label_estado.config(text="● Listo", fg="#10a37f"))

    # ───── Archivos ───────────────────────────────────────────

    def _seleccionar_archivo(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo",
            filetypes=[
                ("Imágenes", "*.png *.jpg *.jpeg *.gif"),
                ("Documentos", "*.pdf *.txt *.docx *.md"),
                ("Todos", "*.*"),
            ],
        )
        if archivo:
            self.archivo_adjunto = archivo
            self.label_estado.config(text=f"📎 {Path(archivo).name}")

    # ───── Envío de mensajes ──────────────────────────────────

    def _enviar_mensaje_enter(self, event):
        if not event.state & 1:  # Shift no presionado
            self._enviar_mensaje()
            return "break"

    def _enviar_mensaje(self):
        mensaje = self.entry_mensaje.get("1.0", "end-1c").strip()
        if not mensaje or self.procesando:
            return
        if self.archivo_adjunto:
            mensaje = f"{mensaje}\n\nArchivo: {self.archivo_adjunto}"
            self.archivo_adjunto = None

        self.entry_mensaje.delete("1.0", "end")
        self.text_chat.config(state="normal")
        self.text_chat.insert("end", "\n\nTú\n", "user_label")
        self.text_chat.insert("end", f"{mensaje}\n", "user")
        self.text_chat.config(state="disabled")
        self.text_chat.see("end")

        self.procesando = True
        self.label_estado.config(text="⏳ Procesando...")
        threading.Thread(target=self._procesar_mensaje, args=(mensaje,), daemon=True).start()

    def _procesar_mensaje(self, mensaje):
        try:
            # Cambio de personalidad
            if mensaje.lower() in ["/puteado", "/raymundo", "/ray", "/malo"]:
                resp = config_agente.cambiar_personalidad("puteado")
                self.historial_chat = []
                self.contador_mensajes = 0
                resp += "\n\nQue pedo w soy rAI, un cabron ke no se anda kon mamadas. ke vergas kieres?"
                self._mostrar_respuesta(resp)
                return
            if mensaje.lower() in ["/amigable", "/raycito", "/bueno"]:
                resp = config_agente.cambiar_personalidad("amigable")
                self.historial_chat = []
                self.contador_mensajes = 0
                resp += "\n\n¡Hola! Ahora soy Raymundo en modo amigable 😊 ¿En qué puedo ayudarte?"
                self._mostrar_respuesta(resp)
                return

            # Herramientas
            af_del = _af_delegar if _AGENTFIELD_ENABLED else None
            af_dis = _af_disponible if _AGENTFIELD_ENABLED else None
            resultado = self.herramientas.procesar_mensaje(mensaje, af_delegar=af_del, af_disponible=af_dis)

            if resultado["ejecuto_herramienta"]:
                respuesta = resultado["resultado"]
            elif self._es_mensaje_simple(mensaje):
                respuesta = self._chat_ollama(mensaje)
            else:
                respuesta = self._chat_hibrido(mensaje)

            self._mostrar_respuesta(respuesta)
        except Exception as e:
            self._mostrar_respuesta(f"❌ Error: {e}")
        finally:
            self.procesando = False
            self.root.after(0, lambda: self.label_estado.config(text="● Listo"))

    # ───── Chat helpers ───────────────────────────────────────

    def _es_mensaje_simple(self, mensaje):
        palabras_simples = ["hola", "gracias", "ok", "bien", "mal", "adiós"]
        return len(mensaje) < 50 or any(p in mensaje.lower() for p in palabras_simples)

    def _chat_ollama(self, mensaje):
        prompt = f"{config_agente.get_prompt_sistema()}\n\nUsuario: {mensaje}\nAsistente:"
        return self.ollama.generate(prompt, temperature=0.7) or "Error al conectar con Ollama"

    def _chat_hibrido(self, mensaje):
        self.historial_chat.append({"role": "user", "content": mensaje})
        self.contador_mensajes += 1
        respuesta = self.herramientas.chat_hibrido(mensaje) or "Error al conectar"
        self.historial_chat.append({"role": "assistant", "content": respuesta})
        if len(self.historial_chat) > 20:
            self.historial_chat = self.historial_chat[-20:]
        return respuesta

    # ───── Mostrar respuesta ──────────────────────────────────

    def _mostrar_respuesta(self, respuesta):
        self.root.after(0, self.__mostrar_respuesta_ui, respuesta)

    def __mostrar_respuesta_ui(self, respuesta):
        nombre = config_agente.get_nombre_agente()
        self.text_chat.config(state="normal")
        self.text_chat.insert("end", f"\n{nombre}\n", "assistant_label")
        self.text_chat.insert("end", f"{respuesta}\n", "assistant")
        self.text_chat.config(state="disabled")
        self.text_chat.see("end")

        # TTS en background
        if self.audio_handler.is_tts_available():
            threading.Thread(
                target=self._generar_audio_respuesta,
                args=(respuesta,),
                daemon=True,
            ).start()

    def _generar_audio_respuesta(self, texto):
        limpio = "".join(c for c in texto if c.isalnum() or c.isspace() or c in ".,;:¿?¡!-")
        if len(limpio) > 500:
            limpio = limpio[:500] + "..."
        audio_file = self.audio_handler.text_to_speech(limpio)
        if audio_file:
            self.ultimo_audio_respuesta = audio_file
            self.root.after(0, lambda: self.btn_reproducir.config(state="normal"))
        else:
            self.root.after(0, lambda: self.btn_reproducir.config(state="disabled"))


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    ChatGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
