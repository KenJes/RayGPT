"""
🤖 RAYMUNDO — AGENTE IA UNIFICADO
Interfaz gráfica (tkinter) que integra todos los módulos de core/.

Autor: Axoloit / Kenneth Alcalá
Versión: 3.0 (modular)
"""

import json
import os
import tkinter as tk
from tkinter import scrolledtext, filedialog
import threading
from pathlib import Path

# ── Core imports ───────────────────────────────────────────────
from core.config import config_agente, AppConfig
from core.ai_clients import OllamaClient, MistralClient, GroqClient, GitHubCopilotClient
from core.tools import GestorHerramientas
from core.audio_handler import get_audio_handler
from core.adapters import build_registry
from core.agent_loop import AgentLoop
from core.agent_logger import AgentLogger
from core.agent_memory import VectorMemory
from core.agent_runtime import AgentRuntime, AgentRequest
from core.approval import approval_manager, ApprovalStatus
from core.spotify_client import SpotifyClient
from core.deepface_panel import DeepFacePanel
from core.planeacion_wizard import PlaneacionWizard
from core.knowledge_db import KnowledgeBase
from core.conversation_db import ConversationDB, clear_user
from core.context_manager import ContextManager

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
# TOOLTIP HELPER
# ═══════════════════════════════════════════════════════════════

class _Tooltip:
    """Tooltip ligero que aparece al pasar el ratón por encima de un botón."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _event=None):
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=self.text, justify="left",
            bg="#3a3a4a", fg="#ffffff", relief="flat",
            font=("Segoe UI", 9), padx=8, pady=5,
        ).pack()

    def _hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ═══════════════════════════════════════════════════════════════
# INTERFAZ GRÁFICA
# ═══════════════════════════════════════════════════════════════

class ChatGUI:
    """Interfaz gráfica del asistente IA."""

    def __init__(self, root):
        self.root = root
        nombre = config_agente.get_nombre_agente()
        self.root.title(f"🤖 {nombre} — Asistente IA")
        self.root.geometry("1200x860")
        self.root.configure(bg="#1e1e1e")
        self.root.minsize(960, 640)

        # Inicializar componentes
        cfg = AppConfig()
        self.ollama = OllamaClient(cfg.ollama_url, cfg.ollama_model)
        self.mistral = MistralClient(cfg.mistral_api_key)
        self.groq_client = GroqClient()
        self.copilot = GitHubCopilotClient()
        self.google = cfg.google_client

        # Inicializar Spotify (opcional — no rompe si no está configurado)
        self.spotify = None
        try:
            import json as _json
            with open("config_agente.json", "r", encoding="utf-8") as _f:
                _cfg_json = _json.load(_f)
            _sp = _cfg_json.get("spotify", {})
            # Preferir config_agente.json; si vacío, usar variables de entorno
            _sp_id     = _sp.get("client_id", "") or os.environ.get("SPOTIFY_CLIENT_ID", "")
            _sp_secret = _sp.get("client_secret", "") or os.environ.get("SPOTIFY_CLIENT_SECRET", "")
            _sp_redir  = (_sp.get("redirect_uri", "") or
                          os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5000/spotify/callback"))
            if _sp_id and _sp_secret:
                self.spotify = SpotifyClient(_sp_id, _sp_secret, _sp_redir)
                if self.spotify.is_authenticated:
                    print("✅ Spotify conectado en GUI")
                else:
                    print("⚠️ Spotify no autenticado — visita http://localhost:5000/spotify/auth")
        except Exception as _e:
            print(f"⚠️ Spotify no disponible en GUI: {_e}")

        self.herramientas = GestorHerramientas(
            self.ollama, self.mistral, google=self.google, groq=self.groq_client,
            spotify=self.spotify, copilot=self.copilot,
        )
        self.knowledge_base = KnowledgeBase()
        self.conversation_db = ConversationDB()
        self.context_manager = ContextManager(
            knowledge_base=self.knowledge_base,
            memory_system=self.herramientas.memory,
        )

        # Infraestructura agéntica
        self.face_manager = None
        try:
            from core.face_recognition import FaceManager
            import json
            with open('config_agente.json', 'r', encoding='utf-8') as f:
                _cfg_json = json.load(f)
            deepface_config = _cfg_json.get("deepface", {})
            self.face_manager = FaceManager(config=deepface_config)
            if self.face_manager.available:
                self.herramientas.face_manager = self.face_manager
        except Exception:
            pass
        self.adapter_registry = build_registry(
            self.herramientas,
            knowledge_base=self.knowledge_base,
            spotify_client=self.spotify,
            face_manager=self.face_manager,
        )

        # ── DeepFace worker (Python 3.12 subprocess) ──────────────────────
        self.deepface_client = None
        try:
            from core.deepface_stream import _DeepFaceWorkerProxy, _DEEPFACE_AVAILABLE
            if _DEEPFACE_AVAILABLE:
                self.deepface_client = _DeepFaceWorkerProxy()
                self.herramientas.deepface_client = self.deepface_client
                print("✅ DeepFace client configurado (inicio diferido)")
            else:
                print("⚠️ DeepFace no disponible (se necesita Python 3.12 con deepface)")
        except Exception as _e:
            print(f"⚠️ DeepFace no disponible: {_e}")
        self.deepface_panel = DeepFacePanel(self.root, self.deepface_client)
        self.agent_logger = AgentLogger()
        self.agent_memory = VectorMemory()

        from core.ai_clients import make_ai_chat_fn
        _ai_chat_gui = make_ai_chat_fn(
            groq_client=self.groq_client,
            mistral_client=self.mistral,
            ollama_client=self.ollama,
            copilot_client=self.copilot,
            copilot_model="gpt-4o",  # GUI usa modelo completo; loop usa gpt-4o-mini vía WA
            compress=False,
            filter_rejections=False,
        )

        # Callback de aprobación: muestra diálogo tkinter
        def _on_approval_needed(req):
            self.root.after(0, lambda: self._show_approval_dialog(req))

        approval_manager.on_approval_needed = _on_approval_needed

        self.agent_loop = AgentLoop(
            registry=self.adapter_registry,
            ai_chat_fn=_ai_chat_gui,
            logger=self.agent_logger,
            memory=self.agent_memory,
            approval=approval_manager,
            on_progress=lambda msg: self.root.after(0, self._mostrar_progreso, msg),
        )
        self.agent_runtime = AgentRuntime(
            gestor=self.herramientas,
            agent_loop=self.agent_loop,
            conversation_db=self.conversation_db,
            knowledge_base=self.knowledge_base,
            context_manager=self.context_manager,
        )

        # Audio
        self.audio_handler = get_audio_handler()
        self.ultimo_audio_respuesta = None

        self._planeacion_wizard: PlaneacionWizard | None = None

        self.historial_chat = []
        self.contador_mensajes = 0
        self.procesando = False
        self.archivo_adjunto = None
        self._image_refs: list = []   # mantiene referencias PIL para evitar GC

        self._construir_interfaz()
        self._mostrar_bienvenida()

    # ───── UI ──────────────────────────────────────────────────

    def _construir_interfaz(self):
        # ── ENCABEZADO ──────────────────────────────────────────
        header = tk.Frame(self.root, bg="#1a1a2e", height=62)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        nombre_agente = config_agente.get_nombre_agente()
        tk.Label(
            header, text=f"🤖  {nombre_agente}",
            font=("Segoe UI", 15, "bold"), bg="#1a1a2e", fg="#ffffff",
        ).pack(side="left", padx=18, pady=10)
        tk.Label(
            header, text="Asistente de IA",
            font=("Segoe UI", 9), bg="#1a1a2e", fg="#666688",
        ).pack(side="left", pady=10)

        self.label_estado = tk.Label(
            header, text="✅  Listo para ayudarte",
            font=("Segoe UI", 9), bg="#1a1a2e", fg="#10a37f",
        )
        self.label_estado.pack(side="right", padx=14, pady=10)

        btn_nuevo = tk.Button(
            header, text="🗑️  Nueva conversación",
            command=self._nueva_conversacion,
            bg="#2d2d4e", fg="#ccccdd", font=("Segoe UI", 9),
            relief="flat", padx=12, pady=6, cursor="hand2",
        )
        btn_nuevo.pack(side="right", padx=6, pady=10)
        _Tooltip(btn_nuevo, "Borrar el historial y empezar de cero")

        tk.Label(
            header, text="|", font=("Segoe UI", 14),
            bg="#1a1a2e", fg="#333355",
        ).pack(side="right", pady=10)

        tk.Label(
            header, text="Modo:", font=("Segoe UI", 9),
            bg="#1a1a2e", fg="#666688",
        ).pack(side="right", padx=(6, 0), pady=10)
        self._modo_var = tk.StringVar(value="😊 Raymundo")
        modo_menu = tk.OptionMenu(
            header, self._modo_var,
            "😊 Raymundo", "🏫 Prepa", "🔥 rAI",
            command=self._cambiar_modo_desde_menu,
        )
        modo_menu.config(
            bg="#2d2d4e", fg="#ccccdd", font=("Segoe UI", 9),
            relief="flat", cursor="hand2", highlightthickness=0,
            activebackground="#3d3d6e", activeforeground="#ffffff", bd=0,
        )
        modo_menu["menu"].config(
            bg="#2d2d4e", fg="#ccccdd", font=("Segoe UI", 9),
            activebackground="#4d4d8e", activeforeground="#ffffff",
        )
        modo_menu.pack(side="right", padx=2, pady=10)

        # ── Selector de modelo Copilot ─────────────────────────
        tk.Label(
            header, text="|", font=("Segoe UI", 14),
            bg="#1a1a2e", fg="#333355",
        ).pack(side="right", pady=10)

        copilot_label_text = "Copilot:" if self.copilot.available else "Copilot: ✗"
        copilot_label_color = "#666688" if self.copilot.available else "#554444"
        tk.Label(
            header, text=copilot_label_text, font=("Segoe UI", 9),
            bg="#1a1a2e", fg=copilot_label_color,
        ).pack(side="right", padx=(6, 0), pady=10)

        self._copilot_model_var = tk.StringVar(value=self.copilot.model)
        copilot_menu = tk.OptionMenu(
            header, self._copilot_model_var,
            *GitHubCopilotClient.MODELS,
            command=self._cambiar_modelo_copilot,
        )
        copilot_menu.config(
            bg="#2d2d4e", fg="#ccccdd" if self.copilot.available else "#554455",
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            highlightthickness=0, activebackground="#3d3d6e",
            activeforeground="#ffffff", bd=0,
            state="normal" if self.copilot.available else "disabled",
        )
        copilot_menu["menu"].config(
            bg="#2d2d4e", fg="#ccccdd", font=("Segoe UI", 9),
            activebackground="#4d4d8e", activeforeground="#ffffff",
        )
        copilot_menu.pack(side="right", padx=2, pady=10)
        input_outer = tk.Frame(self.root, bg="#141414", pady=10)
        input_outer.pack(fill="x", side="bottom")

        tk.Label(
            input_outer,
            text="Enter = enviar   •   Shift+Enter = nueva línea",
            bg="#141414", fg="#3a3a3a", font=("Segoe UI", 8),
        ).pack(pady=(0, 4))

        btn_row = tk.Frame(input_outer, bg="#141414")
        btn_row.pack(fill="x", padx=18, pady=(0, 6))

        self.btn_grabar = tk.Button(
            btn_row, text="🎤  Grabar voz",
            command=self._toggle_grabacion,
            bg="#252535", fg="#cccccc", font=("Segoe UI", 9),
            relief="flat", padx=10, pady=5, cursor="hand2",
        )
        self.btn_grabar.pack(side="left", padx=(0, 6))
        _Tooltip(
            self.btn_grabar,
            "Habla en lugar de escribir.\n"
            "Clic para empezar a grabar, clic de nuevo para enviar.")

        self.btn_reproducir = tk.Button(
            btn_row, text="🔊  Escuchar respuesta",
            command=self._reproducir_ultima_respuesta,
            bg="#252535", fg="#555555", font=("Segoe UI", 9),
            relief="flat", padx=10, pady=5, cursor="hand2", state="disabled",
        )
        self.btn_reproducir.pack(side="left", padx=(0, 6))
        _Tooltip(self.btn_reproducir, "Escuchar la última respuesta en voz alta")

        self.btn_adjuntar = tk.Button(
            btn_row, text="📎  Adjuntar archivo",
            command=self._seleccionar_archivo,
            bg="#252535", fg="#cccccc", font=("Segoe UI", 9),
            relief="flat", padx=10, pady=5, cursor="hand2",
        )
        self.btn_adjuntar.pack(side="left", padx=(0, 6))
        _Tooltip(
            self.btn_adjuntar,
            "Adjuntar una imagen o documento.\n"
            "Luego escribe tu pregunta sobre él y presiona Enviar.")

        input_row = tk.Frame(input_outer, bg="#141414")
        input_row.pack(fill="x", padx=18)
        input_frame = tk.Frame(input_row, bg="#2a2a2a", relief="flat")
        input_frame.pack(fill="both", expand=True, side="left")

        self.entry_mensaje = tk.Text(
            input_frame, height=2, bg="#2a2a2a", fg="#ececec",
            font=("Segoe UI", 12), relief="flat", padx=14, pady=10,
            wrap=tk.WORD, insertbackground="#ffffff",
        )
        self.entry_mensaje.pack(fill="both", expand=True)
        self.entry_mensaje.bind("<Return>", self._enviar_mensaje_enter)
        self.entry_mensaje.bind("<FocusIn>", self._on_entry_focus)
        self.entry_mensaje.bind("<FocusOut>", self._on_entry_blur)
        self.entry_mensaje.bind("<Key>", self._on_entry_key, add="+")

        self._placeholder = "Escribe aquí tu pregunta o petición..."
        self._placeholder_active = False
        self._set_placeholder()

        btn_enviar = tk.Button(
            input_row, text="  Enviar  ➤",
            command=self._enviar_mensaje,
            bg="#10a37f", fg="#ffffff", font=("Segoe UI", 12, "bold"),
            relief="flat", padx=16, pady=10, cursor="hand2",
        )
        btn_enviar.pack(side="right", padx=(8, 0))
        _Tooltip(btn_enviar, "Enviar mensaje\n(o presiona Enter)")

        # ── SEPARADOR ─────────────────────────────────────────────
        tk.Frame(self.root, bg="#2a2a2a", height=1).pack(fill="x", side="bottom")

        # ── CHIPS DE ACCESO RÁPIDO ────────────────────────────────
        self._sugerencias_frame = tk.Frame(self.root, bg="#1a1a1a", pady=8)
        self._sugerencias_frame.pack(fill="x", side="bottom")

        tk.Label(
            self._sugerencias_frame,
            text="  💡 Acceso rápido:",
            bg="#1a1a1a", fg="#555577", font=("Segoe UI", 9),
        ).pack(anchor="w", padx=18, pady=(0, 4))

        chips_row = tk.Frame(self._sugerencias_frame, bg="#1a1a1a")
        chips_row.pack(anchor="w", padx=14)
        for label, texto in [
            ("📅 ¿Qué tengo hoy?",   "¿Qué eventos tengo en mi calendario hoy?"),
            ("📧 Mis correos",        "¿Tengo correos nuevos importantes?"),
            ("🎵 Pon música",         "Pon música relajante en Spotify"),
            ("🌤️ El tiempo",          "¿Cómo está el clima en "),
            ("₿ Cripto",              "¿Cuánto vale Bitcoin hoy?"),
            ("🎨 Generar imagen",     "Genera una imagen de "),
            ("🎭 ComfyUI",            "Genera con ComfyUI "),
            ("📲 Código QR",          "Genera un QR de "),
            ("🔭 NASA hoy",           "Muéstrame la foto del día de la NASA"),
        ]:
            btn = tk.Button(
                chips_row, text=label,
                command=lambda t=texto: self._usar_sugerencia(t),
                bg="#252540", fg="#b8b8cc", font=("Segoe UI", 9),
                relief="flat", padx=9, pady=5, cursor="hand2",
                activebackground="#353560", activeforeground="#ffffff",
            )
            btn.pack(side="left", padx=3, pady=2)

        btn_deepface = tk.Button(
            self._sugerencias_frame,
            text="🎭 DeepFace (8 funciones)",
            command=self._abrir_deepface_panel,
            bg="#1f3a2f",
            fg="#c8f0dc",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
            activebackground="#2b5a45",
            activeforeground="#ffffff",
        )
        btn_deepface.pack(anchor="w", padx=18, pady=(6, 0))

        btn_planeacion = tk.Button(
            self._sugerencias_frame,
            text="🎓 Planeación Didáctica",
            command=self._abrir_planeacion,
            bg="#1e5128",
            fg="#c8f0dc",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
            activebackground="#2b7a40",
            activeforeground="#ffffff",
        )
        btn_planeacion.pack(anchor="w", padx=18, pady=(4, 8))

        # ── CHAT (ocupa todo el espacio central restante) ─────────
        self.text_chat = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, bg="#1e1e1e", fg="#e8e8e8",
            font=("Segoe UI", 12), relief="flat", padx=24, pady=16,
            state="disabled", spacing1=4, spacing3=4,
        )
        self.text_chat.tag_config(
            "user_label", foreground="#10c994", font=("Segoe UI", 11, "bold"))
        self.text_chat.tag_config(
            "user", foreground="#e8e8e8", font=("Segoe UI", 12),
            lmargin1=10, lmargin2=10)
        self.text_chat.tag_config(
            "assistant_label", foreground="#9090ff", font=("Segoe UI", 11, "bold"))
        self.text_chat.tag_config(
            "assistant", foreground="#d0d0d0", font=("Segoe UI", 12),
            lmargin1=10, lmargin2=10)
        self.text_chat.tag_config(
            "bienvenida", foreground="#10c994", font=("Segoe UI", 14, "bold"))
        self.text_chat.tag_config(
            "info", foreground="#888888", font=("Segoe UI", 11))
        self.text_chat.tag_config(
            "pista", foreground="#555577", font=("Segoe UI", 10, "italic"))
        self.text_chat.pack(fill="both", expand=True)

    # ───── Bienvenida ─────────────────────────────────────────

    def _mostrar_bienvenida(self):
        nombre = config_agente.get_nombre_agente()
        self.text_chat.config(state="normal")
        self.text_chat.insert("end", f"\n  👋  ¡Hola! Soy {nombre}\n", "bienvenida")
        self.text_chat.insert(
            "end",
            "  Tu asistente de inteligencia artificial. Puedo ayudarte con:\n\n",
            "assistant",
        )
        for cap in [
            "  📅  Agenda — ver y crear eventos en Google Calendar",
            "  📧  Correo — leer y enviar emails con Gmail",
            "  📄  Documentos y presentaciones con Google Docs / Slides",
            "  📊  Hojas de cálculo con Google Sheets",
            "  🎵  Controlar Spotify (reproducir, pausar, buscar canciones)",
            "  📺  Buscar videos en YouTube",
            "  🔍  Buscar cualquier cosa en internet",
            "  💬  Responder preguntas y conversar sobre cualquier tema",
            "  🖼️  Leer y analizar imágenes o documentos que adjuntes",
            "  🎤  Entenderte por voz si tienes micrófono",
            "  🌤️  Clima en tiempo real — sin API key (Open-Meteo)",
            "  ₿   Precios de criptomonedas en tiempo real (CoinGecko)",
            "  🎨  Generar imágenes con IA — sin API key (Pollinations.ai)",
            "  🎭  Generar imágenes con ComfyUI local (Stable Diffusion)",
            "  📲  Generar códigos QR al instante",
            "  🔭  Foto astronómica del día + asteroides cercanos (NASA)\n",
            "  🤖  GitHub Copilot — GPT-4o / Claude / o3-mini (menú superior)\n",
        ]:
            self.text_chat.insert("end", f"{cap}\n", "info")
        self.text_chat.insert(
            "end",
            "  Escribe tu pregunta abajo o toca uno de los botones de acceso rápido 👇\n\n",
            "pista",
        )
        self.text_chat.config(state="disabled")

    # ───── Audio ──────────────────────────────────────────────

    # ───── Placeholder y sugerencias ──────────────────────────

    def _set_placeholder(self):
        """Muestra texto de ayuda en el campo cuando está vacío."""
        self.entry_mensaje.delete("1.0", tk.END)
        self.entry_mensaje.insert("1.0", self._placeholder)
        self.entry_mensaje.config(fg="#555555")
        self._placeholder_active = True

    def _on_entry_focus(self, _event=None):
        if self._placeholder_active:
            self.entry_mensaje.delete("1.0", tk.END)
            self.entry_mensaje.config(fg="#ececec")
            self._placeholder_active = False

    def _on_entry_key(self, _event=None):
        """Limpia el placeholder cuando el usuario empieza a escribir,
        incluso si el entry ya tenía el foco (ej: después de enviar con Enter)."""
        if self._placeholder_active:
            self.entry_mensaje.delete("1.0", tk.END)
            self.entry_mensaje.config(fg="#ececec")
            self._placeholder_active = False

    def _on_entry_blur(self, _event=None):
        if not self.entry_mensaje.get("1.0", "end-1c").strip():
            self._set_placeholder()

    def _usar_sugerencia(self, texto):
        """Inserta texto de un chip de acceso rápido y envía si está completo."""
        self._on_entry_focus()
        self.entry_mensaje.delete("1.0", tk.END)
        self.entry_mensaje.insert("1.0", texto)
        self.entry_mensaje.focus_set()
        # Si el texto termina en ': ' espera que el usuario complete; si no, envía
        if not texto.endswith(": "):
            self.root.after(50, self._enviar_mensaje)

    def _abrir_deepface_panel(self):
        """Abre la ventana de DeepFace con las 8 funciones del demo."""
        self.deepface_panel.open()

    def _abrir_planeacion(self):
        """Activa el wizard de planeación didáctica directamente en el chat."""
        def _ai_fn(prompt: str) -> str:
            resultado = self.herramientas._consultar_ia(
                prompt, temperature=0.7, max_tokens=16000
            )
            return resultado or ""

        self._planeacion_wizard = PlaneacionWizard(_ai_fn)
        self._mostrar_respuesta(self._planeacion_wizard.start())

    def _nueva_conversacion(self):
        """Borra el historial y muestra la pantalla de bienvenida."""
        self.historial_chat = []
        self.contador_mensajes = 0
        user_id = getattr(self, '_user_id', 'local_user')
        try:
            from core.conversation_db import clear_user
            clear_user(user_id)
        except Exception:
            pass
        try:
            self.herramientas.memory.clear_user_context(user_id)
        except Exception:
            pass
        try:
            self.agent_memory.clear()
        except Exception:
            pass
        self.text_chat.config(state="normal")
        self.text_chat.delete("1.0", tk.END)
        self.text_chat.config(state="disabled")
        self._mostrar_bienvenida()
        self.label_estado.config(text="✅  Listo para ayudarte", fg="#10a37f")

    def _cambiar_modo_desde_menu(self, seleccion):
        """Cambia la personalidad al seleccionar en el menú del encabezado."""
        import os as _os
        if "rAI" in seleccion:
            _os.environ["PERSONALITY_MODE"] = "rai"
            config_agente.cambiar_personalidad("puteado")
            confirmacion = "ya wey, soy rAI. sin filtros y sin diplomacia. ke chingaos kieres?"
        elif "Prepa" in seleccion:
            _os.environ["PERSONALITY_MODE"] = "prepa"
            config_agente.cambiar_personalidad("amigable")
            confirmacion = "Órale, modo prepa activado. Al cien y sin groserías. ¿Qué necesitas wey?"
        else:
            _os.environ["PERSONALITY_MODE"] = "raymundo"
            config_agente.cambiar_personalidad("amigable")
            confirmacion = "Modo Raymundo activado. Profesional y al servicio. ¿En qué te ayudo?"
        self.historial_chat = []
        self.contador_mensajes = 0
        self._mostrar_respuesta(confirmacion)

    def _cambiar_modelo_copilot(self, seleccion: str):
        """Cambia el modelo de GitHub Copilot desde el menú del encabezado."""
        self.copilot.set_model(seleccion)

    # ───── Audio ──────────────────────────────────────────────

    def _toggle_grabacion(self):
        if not self.audio_handler.is_stt_available():
            return
        if not self.audio_handler.is_recording:
            if self.audio_handler.start_recording(duration=30):
                self.btn_grabar.config(fg="#ff4444", text="⏹️  Detener grabación")
                self.label_estado.config(text="🎙️ Te estoy escuchando...", fg="#ff4444")
        else:
            self.btn_grabar.config(fg="#cccccc", text="🎤  Grabar voz")
            self.label_estado.config(text="⏳ Procesando tu mensaje de voz...", fg="#ffa500")
            threading.Thread(target=self._procesar_audio_grabado, daemon=True).start()

    def _procesar_audio_grabado(self):
        audio_file = self.audio_handler.stop_recording()
        if not audio_file:
            self.root.after(0, lambda: self.label_estado.config(
                text="❌ No se pudo capturar el audio", fg="#ff4444"))
            return
        texto = self.audio_handler.speech_to_text(audio_file)
        if texto and texto.strip():
            def _set_transcribed():
                self._on_entry_focus()
                self.entry_mensaje.delete("1.0", tk.END)
                self.entry_mensaje.insert("1.0", texto)
                self.label_estado.config(text="✅ ¡Entendido! Enviando...", fg="#10a37f")
            self.root.after(0, _set_transcribed)
            self.root.after(150, self._enviar_mensaje)
        else:
            self.root.after(0, lambda: self.label_estado.config(
                text="⚠️ No detecté lo que dijiste, intenta de nuevo", fg="#ffa500"))

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
        self.root.after(0, lambda: self.label_estado.config(text="✅  Listo para ayudarte", fg="#10a37f"))

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
            nombre_corto = Path(archivo).name
            if len(nombre_corto) > 28:
                nombre_corto = nombre_corto[:25] + "..."
            self.label_estado.config(
                text=f"📎 Archivo listo: {nombre_corto}", fg="#10a37f")
            self.btn_adjuntar.config(text=f"✅  {nombre_corto}")

    # ───── Envío de mensajes ──────────────────────────────────

    def _enviar_mensaje_enter(self, event):
        if not event.state & 1:  # Shift no presionado
            self._enviar_mensaje()
            return "break"

    def _enviar_mensaje(self):
        if getattr(self, '_placeholder_active', False):
            return
        mensaje = self.entry_mensaje.get("1.0", "end-1c").strip()
        if not mensaje or self.procesando:
            return

        archivo_path = None
        if self.archivo_adjunto:
            archivo_path = self.archivo_adjunto
            self.archivo_adjunto = None
            self.label_estado.config(text="⏳ Leyendo archivo adjunto...")
            self.btn_adjuntar.config(text="📎  Adjuntar archivo")

        self.entry_mensaje.delete("1.0", "end")
        self._set_placeholder()
        self.text_chat.config(state="normal")
        self.text_chat.insert("end", "\n\nTú\n", "user_label")
        display_msg = mensaje
        if archivo_path:
            display_msg += f"\n📎 {Path(archivo_path).name}"
        self.text_chat.insert("end", f"{display_msg}\n", "user")
        self.text_chat.config(state="disabled")
        self.text_chat.see("end")

        self.procesando = True
        self.label_estado.config(text="⏳ Pensando en tu respuesta...", fg="#ffa500")
        threading.Thread(
            target=self._procesar_mensaje, args=(mensaje, archivo_path), daemon=True
        ).start()

    def _procesar_mensaje(self, mensaje, archivo_adjunto=None):
        try:
            # ── Wizard de planeación didáctica ─────────────────────────────
            if self._planeacion_wizard and self._planeacion_wizard.is_active:
                if mensaje.lower() in ("/cancelar", "/salir", "/cancel"):
                    resp = self._planeacion_wizard.cancel()
                    self._planeacion_wizard = None
                else:
                    if self._planeacion_wizard.estado == "generating":
                        pass  # already generating, wait
                    self.root.after(
                        0,
                        lambda: self.label_estado.config(
                            text="⏳ Generando planeación...", fg="#ffa500"
                        ),
                    )
                    resp = self._planeacion_wizard.step(mensaje)
                    if self._planeacion_wizard.is_done:
                        self._planeacion_wizard = None
                self._mostrar_respuesta(resp)
                return

            # Si hay imagen adjunta, extraer texto con Vision OCR
            if archivo_adjunto:
                ext = Path(archivo_adjunto).suffix.lower()
                if ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
                    self.root.after(0, lambda: self.label_estado.config(text="📸 Leyendo imagen..."))
                    # Always embed the path so deepface/vision tools can locate the file
                    mensaje = f"{mensaje}\n\nArchivo: {archivo_adjunto}"
                    texto_extraido = self.herramientas.vision.extract_text_from_image(archivo_adjunto)
                    if texto_extraido and not texto_extraido.startswith("❌"):
                        mensaje = (
                            f"{mensaje}\n\n"
                            f"[CONTENIDO EXTRAÍDO DE LA IMAGEN ADJUNTA]:\n"
                            f"{texto_extraido}"
                        )
                elif ext in [".pdf", ".txt", ".md"]:
                    doc = self.herramientas.docs.process_document(archivo_adjunto)
                    if doc["success"]:
                        mensaje = (
                            f"{mensaje}\n\n"
                            f"[CONTENIDO DEL DOCUMENTO ADJUNTO ({Path(archivo_adjunto).name})]:\n"
                            f"{doc['content'][:3000]}"
                        )
                    else:
                        mensaje = f"{mensaje}\n\nArchivo: {archivo_adjunto}"
                else:
                    mensaje = f"{mensaje}\n\nArchivo: {archivo_adjunto}"

            # Limpiar historial / reset
            if mensaje.lower() in ["/reset", "/borrar", "/limpiar", "/nuevo", "/clear"]:
                self.historial_chat = []
                self.contador_mensajes = 0
                user_id = getattr(self, '_user_id', 'local_user')
                # Limpiar también la BD persistente
                try:
                    clear_user(user_id)
                except Exception:
                    pass
                # Limpiar vocabulario/estilo/temas acumulados
                try:
                    self.herramientas.memory.clear_user_context(user_id)
                except Exception:
                    pass
                # Limpiar VectorMemory del agente (RAG acumulado)
                try:
                    self.agent_memory.clear()
                except Exception:
                    pass
                from core.config import _get_mode
                if _get_mode() == "rai":
                    self._mostrar_respuesta("ya wey, borre toda la conversacion. ahora si, q chingados kieres?")
                else:
                    self._mostrar_respuesta("🗑️ Listo, borré el historial. Empezamos de cero, ¿en qué te ayudo?")
                return

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

            runtime_response = self.agent_runtime.handle_text(
                AgentRequest(
                    text=mensaje,
                    user_id=getattr(self, '_user_id', 'local_user'),
                    user_name=os.environ.get("USERNAME") or None,
                    channel="desktop_gui",
                    tono_override=config_agente.get_tono(),
                )
            )
            artifact_paths = self._extraer_paths_artifacts(runtime_response.artifacts)
            imagen_path = self._extraer_imagen_artifact(artifact_paths)
            respuesta = self._anexar_artifacts_a_respuesta(runtime_response.response, artifact_paths)
            paths_para_abrir = [path for path in artifact_paths if path != imagen_path]
            self._abrir_artifact_generado(paths_para_abrir)
            self._mostrar_respuesta(respuesta, imagen_path=imagen_path)
        except Exception as e:
            self._mostrar_respuesta(f"❌ Error: {e}")
        finally:
            self.procesando = False
            self.root.after(0, lambda: self.label_estado.config(
                text="✅  Listo para ayudarte", fg="#10a37f"))

    # ───── Chat helpers ───────────────────────────────────────

    def _es_mensaje_simple(self, mensaje):
        palabras_simples = ["hola", "gracias", "ok", "bien", "mal", "adiós"]
        return len(mensaje) < 50 or any(p in mensaje.lower() for p in palabras_simples)

    def _chat_ollama(self, mensaje):
        prompt_base = config_agente.get_prompt_sistema()
        user_id = getattr(self, '_user_id', 'local_user')
        vocab_hint = self.herramientas.memory.get_vocabulario_hint(user_id=user_id)
        prompt = f"{prompt_base}{vocab_hint}\n\nUsuario: {mensaje}\nAsistente:"
        return self.ollama.generate(prompt, temperature=0.7) or "Error al conectar con Ollama"

    def _chat_hibrido(self, mensaje):
        history = self.historial_chat[-16:]
        self.historial_chat.append({"role": "user", "content": mensaje})
        self.contador_mensajes += 1
        respuesta = self.herramientas.chat_hibrido(
            mensaje,
            user_id=getattr(self, '_user_id', 'local_user'),
            history=history,
        ) or "Error al conectar"
        self.historial_chat.append({"role": "assistant", "content": respuesta})
        if len(self.historial_chat) > 16:   # 8 pares máx para no sobrecargar el LLM
            self.historial_chat = self.historial_chat[-16:]
        return respuesta

    # ───── Agéntico: progreso y aprobación ───────────────────

    def _mostrar_progreso(self, msg):
        """Muestra un mensaje de progreso del agente en el chat."""
        self.text_chat.config(state="normal")
        self.text_chat.insert("end", f"\n⏳ {msg}\n", "assistant")
        self.text_chat.config(state="disabled")
        self.text_chat.see("end")
        self.label_estado.config(text="🧠 Agente pensando...", fg="#ffa500")

    def _show_approval_dialog(self, req):
        """Muestra un diálogo tkinter para aprobar/rechazar una acción del agente."""
        import tkinter.messagebox as mb
        msg = (
            f"El agente quiere ejecutar una acción que requiere aprobación:\n\n"
            f"Acción: {req.action}\n"
            f"Argumentos: {json.dumps(req.args, indent=2, ensure_ascii=False)[:300]}\n\n"
            f"Razón: {req.reason[:200]}\n\n"
            f"¿Aprobar esta acción?"
        )
        aprobado = mb.askyesno("Aprobación requerida", msg)
        if aprobado:
            approval_manager.approve(req.id)
        else:
            approval_manager.deny(req.id)

    # ───── Mostrar respuesta ──────────────────────────────────

    def _mostrar_respuesta(self, respuesta, imagen_path=None):
        self.root.after(0, self.__mostrar_respuesta_ui, respuesta, imagen_path)

    def _extraer_paths_artifacts(self, artifacts):
        paths = []
        seen_paths = set()
        for artifact in artifacts or []:
            if not isinstance(artifact, dict):
                continue
            path = artifact.get("path")
            if path and path not in seen_paths:
                paths.append(path)
                seen_paths.add(path)
        return paths

    def _extraer_imagen_artifact(self, artifact_paths):
        for path in artifact_paths:
            if Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
                return path
        return None

    def _anexar_artifacts_a_respuesta(self, respuesta, artifact_paths):
        if not artifact_paths:
            return respuesta
        lines = [(respuesta or "").rstrip(), "", "Archivos generados:"]
        lines.extend(f"- {path}" for path in artifact_paths)
        return "\n".join(line for line in lines if line is not None).strip()

    def _abrir_artifact_generado(self, artifact_paths):
        if not artifact_paths or not hasattr(os, "startfile"):
            return
        try:
            os.startfile(artifact_paths[0])  # type: ignore[attr-defined]
        except Exception:
            pass

    def __mostrar_respuesta_ui(self, respuesta, imagen_path=None):
        nombre = config_agente.get_nombre_agente()
        self.text_chat.config(state="normal")
        self.text_chat.insert("end", f"\n  {nombre}\n", "assistant_label")
        self.text_chat.insert("end", f"{respuesta}\n", "assistant")

        if imagen_path:
            self._insertar_imagen_ui(imagen_path)

        self.text_chat.insert("end", "\n", "assistant")
        self.text_chat.config(state="disabled")
        self.text_chat.see("end")

        # TTS en background
        if self.audio_handler.is_tts_available():
            threading.Thread(
                target=self._generar_audio_respuesta,
                args=(respuesta,),
                daemon=True,
            ).start()

    def _insertar_imagen_ui(self, path: str):
        """Inserta una imagen PIL directamente en el chat (hilo principal)."""
        try:
            from PIL import Image, ImageTk  # type: ignore
            img = Image.open(path)
            img.thumbnail((520, 390), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.text_chat.insert("end", "\n")
            self.text_chat.image_create("end", image=photo)
            self.text_chat.insert("end", "\n")
            self._image_refs.append(photo)   # evitar garbage collection
        except Exception as e:
            self.text_chat.insert("end", f"[No se pudo mostrar imagen: {e}]\n", "info")

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
    import traceback
    root = tk.Tk()
    try:
        ChatGUI(root)
        root.mainloop()
    except Exception as exc:
        err = traceback.format_exc()
        # Escribir log de error
        try:
            log_path = Path(__file__).parent / "data" / "raymundo_error.log"
            log_path.parent.mkdir(exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(err)
            print(f"\n❌ Error al iniciar Raymundo. Log guardado en:\n   {log_path}\n")
        except Exception:
            pass
        # Mostrar error en ventana si tkinter sigue activo
        try:
            import tkinter.messagebox as _mb
            root2 = tk.Tk()
            root2.withdraw()
            _mb.showerror(
                "Error al iniciar Raymundo",
                f"{type(exc).__name__}: {exc}\n\nRevisa data/raymundo_error.log para el detalle completo.",
            )
            root2.destroy()
        except Exception:
            print(err)
        raise


if __name__ == "__main__":
    main()
