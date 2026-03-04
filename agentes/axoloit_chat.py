"""
🤖 AXOLOIT AGENTS — Chat GUI
Interfaz gráfica para interactuar con los agentes IA de Axoloit.
Inicia los agentes automáticamente si no están corriendo.

Uso: python agentes/axoloit_chat.py   (desde la raíz del proyecto)
     o doble clic en "Axoloit Agentes.bat"
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import subprocess
import sys
import time
import json
import webbrowser
from pathlib import Path
from datetime import datetime
import requests

# ── Paths ─────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent
AGENTES_DIR = Path(__file__).resolve().parent
PYTHON     = str(BASE_DIR / ".venv" / "Scripts" / "python.exe")

ORCHESTRATOR_URL = "http://localhost:8000"

# ── Colores (mismo estilo que Raymundo) ───────────────────────
C = {
    "bg":         "#212121",
    "surface":    "#2d2d2d",
    "header":     "#1a1a1a",
    "border":     "#383838",
    "accent":     "#10a37f",
    "accent_dim": "#0d7a60",
    "user_fg":    "#10a37f",
    "bot_fg":     "#c5c5c5",
    "label_fg":   "#9e9e9e",
    "white":      "#ececec",
    "dim":        "#666666",
    "input_bg":   "#303030",
    "btn_red":    "#c0392b",
    "btn_blue":   "#2980b9",
    "btn_orange": "#d35400",
    "btn_purple": "#8e44ad",
}

AGENTES = {
    "research":   ("🔍", "#2980b9",  "Research"),
    "propuestas": ("📋", "#10a37f",  "Propuestas"),
    "google":     ("📊", "#d35400",  "Google WS"),
    "orchestrator":("🧠","#9e9e9e","Orquestador"),
}

QUICK_ACTIONS = [
    ("📋 Propuesta",  "Genera una propuesta comercial completa para el municipio de "),
    ("🔍 Investigar", "Investiga y analiza la siguiente empresa o tema: "),
    ("📧 Email",      "Redacta un email de acercamiento para el municipio de "),
    ("🎤 Pitch",      "Genera un pitch de 2 minutos para TraceTrash"),
    ("📊 ROI",        "Calcula el ROI de TraceTrash para un municipio con "),
    ("📈 Slides",     "Crea una presentación de Google Slides sobre "),
]


class AxoloitChat(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🤖 Axoloit Agents — IA para Municipios")
        self.geometry("1050x720")
        self.minsize(800, 550)
        self.configure(bg=C["bg"])

        self._agents_running = False
        self._checking = False
        self._agent_processes = []

        self._build_ui()
        self._check_agents_status()

    # ══════════════════════════════════════════════════════
    # UI
    # ══════════════════════════════════════════════════════

    def _build_ui(self):
        # ── Header ──────────────────────────────────────
        header = tk.Frame(self, bg=C["header"], height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="🤖  Axoloit Agents",
                 font=("Segoe UI", 14, "bold"),
                 bg=C["header"], fg=C["white"]).pack(side="left", padx=18, pady=10)

        self.lbl_status = tk.Label(header, text="⏳ Iniciando agentes...",
                                    font=("Segoe UI", 9),
                                    bg=C["header"], fg=C["dim"])
        self.lbl_status.pack(side="right", padx=15)

        self.btn_open_docs = tk.Button(header, text="📖 Swagger",
                                        font=("Segoe UI", 8),
                                        bg=C["surface"], fg=C["dim"],
                                        bd=0, padx=8, pady=3, cursor="hand2",
                                        command=lambda: webbrowser.open(f"{ORCHESTRATOR_URL}/docs"))
        self.btn_open_docs.pack(side="right", padx=4, pady=10)

        # ── Agent status pills ───────────────────────────
        self.status_bar = tk.Frame(self, bg=C["border"], height=28)
        self.status_bar.pack(fill="x")
        self.status_bar.pack_propagate(False)

        self._agent_pills = {}
        for name, (icon, color, label) in AGENTES.items():
            if name == "orchestrator":
                continue
            pill = tk.Label(self.status_bar,
                            text=f"  {icon} {label} ●  ",
                            font=("Segoe UI", 8),
                            bg=C["border"], fg=C["dim"])
            pill.pack(side="left", padx=2, pady=4)
            self._agent_pills[name] = pill

        # ── Main area (chat + sidebar) ───────────────────
        main = tk.Frame(self, bg=C["bg"])
        main.pack(fill="both", expand=True)

        # Sidebar
        sidebar = tk.Frame(main, bg=C["surface"], width=200)
        sidebar.pack(side="right", fill="y", padx=(0, 0))
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="ACCIONES RÁPIDAS",
                 font=("Segoe UI", 8, "bold"),
                 bg=C["surface"], fg=C["dim"]).pack(pady=(14,6), padx=12, anchor="w")

        for label, prefill in QUICK_ACTIONS:
            btn = tk.Button(sidebar, text=label,
                            font=("Segoe UI", 9),
                            bg=C["border"], fg=C["white"],
                            bd=0, padx=10, pady=6,
                            relief="flat", cursor="hand2",
                            anchor="w",
                            command=lambda p=prefill: self._prefill(p))
            btn.pack(fill="x", padx=10, pady=2)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=C["accent_dim"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=C["border"]))

        tk.Frame(sidebar, bg=C["border"], height=1).pack(fill="x", padx=10, pady=10)

        tk.Label(sidebar, text="AGENTES",
                 font=("Segoe UI", 8, "bold"),
                 bg=C["surface"], fg=C["dim"]).pack(pady=(0,6), padx=12, anchor="w")

        self._detail_pills = {}
        for name, (icon, color, label) in AGENTES.items():
            if name == "orchestrator":
                continue
            row = tk.Frame(sidebar, bg=C["surface"])
            row.pack(fill="x", padx=12, pady=1)
            tk.Label(row, text=f"{icon}  {label}",
                     font=("Segoe UI", 9), bg=C["surface"], fg=C["white"]).pack(side="left")
            dot = tk.Label(row, text="●", font=("Segoe UI", 9),
                           bg=C["surface"], fg=C["dim"])
            dot.pack(side="right")
            self._detail_pills[name] = dot

        tk.Frame(sidebar, bg=C["border"], height=1).pack(fill="x", padx=10, pady=10)

        self.btn_start = tk.Button(sidebar, text="▶ Iniciar Agentes",
                                    font=("Segoe UI", 9, "bold"),
                                    bg=C["accent"], fg="white",
                                    bd=0, padx=10, pady=6,
                                    cursor="hand2",
                                    command=self._start_agents)
        self.btn_start.pack(fill="x", padx=10, pady=2)

        self.btn_stop = tk.Button(sidebar, text="⏹ Detener",
                                   font=("Segoe UI", 9),
                                   bg=C["btn_red"], fg="white",
                                   bd=0, padx=10, pady=5,
                                   cursor="hand2",
                                   command=self._stop_agents)
        self.btn_stop.pack(fill="x", padx=10, pady=2)

        tk.Button(sidebar, text="🗑 Limpiar chat",
                  font=("Segoe UI", 9),
                  bg=C["border"], fg=C["label_fg"],
                  bd=0, padx=10, pady=5,
                  cursor="hand2",
                  command=self._clear_chat).pack(fill="x", padx=10, pady=2)

        # Chat area
        chat_frame = tk.Frame(main, bg=C["bg"])
        chat_frame.pack(side="left", fill="both", expand=True)

        self.chat = tk.Text(chat_frame,
                            bg=C["bg"], fg=C["bot_fg"],
                            font=("Segoe UI", 10),
                            relief="flat", bd=0,
                            padx=16, pady=12,
                            wrap="word",
                            state="disabled",
                            cursor="arrow")
        self.chat.pack(fill="both", expand=True)

        scroll = tk.Scrollbar(chat_frame, command=self.chat.yview,
                               bg=C["border"], troughcolor=C["bg"])
        scroll.pack(side="right", fill="y")
        self.chat.config(yscrollcommand=scroll.set)

        # Tags
        self.chat.tag_config("user_label",   foreground=C["user_fg"],  font=("Segoe UI", 10, "bold"))
        self.chat.tag_config("user_text",    foreground=C["white"],    font=("Segoe UI", 10))
        self.chat.tag_config("agent_label",  foreground=C["label_fg"], font=("Segoe UI", 10, "bold"))
        self.chat.tag_config("agent_text",   foreground=C["bot_fg"],   font=("Segoe UI", 10))
        self.chat.tag_config("agent_green",  foreground=C["accent"],   font=("Segoe UI", 10, "bold"))
        self.chat.tag_config("agent_blue",   foreground="#2980b9",     font=("Segoe UI", 10, "bold"))
        self.chat.tag_config("agent_orange", foreground="#d35400",     font=("Segoe UI", 10, "bold"))
        self.chat.tag_config("system_msg",   foreground=C["dim"],      font=("Segoe UI", 9, "italic"))
        self.chat.tag_config("url_link",     foreground="#5dade2",
                              font=("Segoe UI", 10, "underline"),
                              underline=True)
        self.chat.tag_config("badge",        foreground="#aaa",        font=("Segoe UI", 8))
        self.chat.tag_config("heading",      foreground=C["accent"],   font=("Segoe UI", 11, "bold"))
        self.chat.tag_config("bullet",       foreground=C["bot_fg"],   font=("Segoe UI", 10),
                              lmargin1=24, lmargin2=36)

        # ── Input area ───────────────────────────────────
        input_frame = tk.Frame(self, bg=C["border"], pady=1)
        input_frame.pack(fill="x", side="bottom")

        inner = tk.Frame(input_frame, bg=C["input_bg"])
        inner.pack(fill="x")

        self.entry = tk.Text(inner, height=3,
                             bg=C["input_bg"], fg=C["white"],
                             font=("Segoe UI", 10),
                             relief="flat", bd=0,
                             padx=14, pady=10,
                             wrap="word",
                             insertbackground=C["accent"])
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>",   self._on_enter)
        self.entry.bind("<Shift-Return>", lambda e: None)  # allow newline
        self.entry.focus()

        tk.Button(inner, text="Enviar  ↵",
                  font=("Segoe UI", 10, "bold"),
                  bg=C["accent"], fg="white",
                  bd=0, padx=18, pady=10,
                  cursor="hand2",
                  command=self._send).pack(side="right", padx=4, pady=4)

        # Welcome
        self._append_system("Escribe tu mensaje o usa los Acciones Rápidas del panel derecho.\n"
                            "Los agentes se inician automáticamente.\n")

    # ══════════════════════════════════════════════════════
    # CHAT HELPERS
    # ══════════════════════════════════════════════════════

    def _append_system(self, text):
        self.chat.config(state="normal")
        self.chat.insert("end", f"{text}", "system_msg")
        self.chat.config(state="disabled")
        self.chat.see("end")

    def _append_user(self, text):
        self.chat.config(state="normal")
        now = datetime.now().strftime("%H:%M")
        self.chat.insert("end", f"\nTú  {now}\n", "user_label")
        self.chat.insert("end", f"{text}\n", "user_text")
        self.chat.config(state="disabled")
        self.chat.see("end")

    def _append_agent(self, text, agente="orchestrator", skill="", ms=None, url=None):
        icon, color, label = AGENTES.get(agente, ("🤖", C["label_fg"], agente))
        tag = {"research": "agent_blue", "propuestas": "agent_green",
               "google": "agent_orange"}.get(agente, "agent_label")

        badge = f"  {skill}" if skill else ""
        timing = f"  ·  {ms}ms" if ms else ""

        self.chat.config(state="normal")
        self.chat.insert("end", f"\n{icon} {label}{badge}{timing}\n", tag)
        self._render_text(text)
        if url:
            self.chat.insert("end", f"\n🔗 ", "agent_text")
            lnk = self.chat.index("end")
            self.chat.insert("end", f"{url}\n", "url_link")
            self.chat.tag_bind("url_link", "<Button-1>",
                                lambda e, u=url: webbrowser.open(u))
        self.chat.insert("end", "\n", "agent_text")
        self.chat.config(state="disabled")
        self.chat.see("end")

    def _render_text(self, text):
        """Render Markdown-ish text with basic formatting."""
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("### "):
                self.chat.insert("end", stripped[4:] + "\n", "heading")
            elif stripped.startswith("## "):
                self.chat.insert("end", stripped[3:] + "\n", "heading")
            elif stripped.startswith("# "):
                self.chat.insert("end", stripped[2:] + "\n", "heading")
            elif stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
                self.chat.insert("end", stripped[2:-2] + "\n", "agent_green")
            elif stripped.startswith(("- ", "• ", "* ")):
                self.chat.insert("end", "  • " + stripped[2:] + "\n", "bullet")
            elif stripped.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                self.chat.insert("end", "  " + stripped + "\n", "bullet")
            else:
                self.chat.insert("end", line + "\n", "agent_text")

    def _append_thinking(self):
        self.chat.config(state="normal")
        self.chat.insert("end", "\n⏳ Procesando...\n", "system_msg")
        self.chat.config(state="disabled")
        self.chat.see("end")
        return self.chat.index("end - 2 lines")

    def _remove_thinking(self, idx):
        self.chat.config(state="normal")
        try:
            self.chat.delete(idx, f"{idx} + 1 lines")
        except Exception:
            pass
        self.chat.config(state="disabled")

    def _clear_chat(self):
        self.chat.config(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.config(state="disabled")
        self._append_system("Chat limpiado.\n")

    # ══════════════════════════════════════════════════════
    # SEND / RECEIVE
    # ══════════════════════════════════════════════════════

    def _on_enter(self, event):
        if not (event.state & 0x1):   # Shift not pressed
            self._send()
            return "break"

    def _send(self):
        msg = self.entry.get("1.0", "end").strip()
        if not msg:
            return
        self.entry.delete("1.0", "end")
        self._append_user(msg)

        if not self._agents_running:
            self._append_system("⚠ Los agentes no están activos. Iniciando...\n")
            self._start_agents()
            # Wait a moment then retry
            self.after(5000, lambda: self._dispatch(msg))
            return

        self._dispatch(msg)

    def _dispatch(self, msg):
        thinking_idx = self._append_thinking()
        threading.Thread(target=self._call_api,
                         args=(msg, thinking_idx), daemon=True).start()

    def _call_api(self, msg, thinking_idx):
        try:
            resp = requests.post(
                f"{ORCHESTRATOR_URL}/procesar",
                json={"mensaje": msg},
                timeout=120,
            )
            self.after(0, self._remove_thinking, thinking_idx)

            if resp.status_code == 200:
                data = resp.json()
                self.after(0, self._append_agent,
                           data.get("resultado", ""),
                           data.get("agente_usado", "orchestrator"),
                           data.get("skill_usado", ""),
                           data.get("tiempo_ms"),
                           data.get("url"))
            else:
                try:
                    detail = resp.json().get("detail", resp.text[:200])
                except Exception:
                    detail = resp.text[:200]
                self.after(0, self._append_system,
                           f"❌ Error {resp.status_code}: {detail}\n")
        except requests.exceptions.ConnectionError:
            self.after(0, self._remove_thinking, thinking_idx)
            self.after(0, self._append_system,
                       "❌ No se puede conectar con los agentes. ¿Están corriendo?\n"
                       "   Usa el botón ▶ Iniciar Agentes del panel derecho.\n")
        except Exception as e:
            self.after(0, self._remove_thinking, thinking_idx)
            self.after(0, self._append_system, f"❌ Error inesperado: {e}\n")

    def _prefill(self, text):
        self.entry.delete("1.0", "end")
        self.entry.insert("1.0", text)
        self.entry.focus()
        # Put cursor at end
        self.entry.mark_set("insert", "end")

    # ══════════════════════════════════════════════════════
    # AGENT MANAGEMENT
    # ══════════════════════════════════════════════════════

    def _start_agents(self):
        """Inicia los 4 agentes en background."""
        self._append_system("▶ Iniciando agentes...\n")
        self.btn_start.config(state="disabled", text="Iniciando...")

        def _run():
            agents = [
                ("research_agent.py",   "research"),
                ("propuesta_agent.py",  "propuestas"),
                ("google_agent.py",     "google"),
                ("orchestrator.py",     "orchestrator"),
            ]
            procs = []
            for script, name in agents:
                try:
                    p = subprocess.Popen(
                        [PYTHON, str(AGENTES_DIR / script)],
                        cwd=str(BASE_DIR),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    procs.append(p)
                except Exception as e:
                    self.after(0, self._append_system, f"⚠ No se pudo iniciar {script}: {e}\n")

            self._agent_processes = procs
            # Poll until orchestrator is up (max 20s)
            for _ in range(20):
                time.sleep(1)
                try:
                    r = requests.get(f"{ORCHESTRATOR_URL}/health", timeout=2)
                    if r.status_code == 200:
                        break
                except Exception:
                    pass

            self.after(0, self._check_agents_status)
            self.after(0, lambda: self.btn_start.config(state="normal", text="▶ Iniciar Agentes"))

        threading.Thread(target=_run, daemon=True).start()

    def _stop_agents(self):
        for p in self._agent_processes:
            try:
                p.terminate()
            except Exception:
                pass
        self._agent_processes = []
        self._agents_running = False
        self._update_status_ui(False, {})
        self._append_system("⏹ Agentes detenidos.\n")

    def _check_agents_status(self):
        """Poll /health y /agentes en background."""
        def _poll():
            while True:
                try:
                    r = requests.get(f"{ORCHESTRATOR_URL}/health", timeout=2)
                    orch_up = r.status_code == 200
                except Exception:
                    orch_up = False

                agent_status = {}
                if orch_up:
                    try:
                        r2 = requests.get(f"{ORCHESTRATOR_URL}/agentes", timeout=5)
                        if r2.status_code == 200:
                            agent_status = r2.json()
                    except Exception:
                        pass

                self.after(0, self._update_status_ui, orch_up, agent_status)
                time.sleep(8)

        threading.Thread(target=_poll, daemon=True).start()

    def _update_status_ui(self, orch_up, agent_status):
        self._agents_running = orch_up
        # Header status
        if orch_up:
            active = sum(1 for v in agent_status.values() if "Activo" in str(v))
            self.lbl_status.config(
                text=f"● {active}/3 agentes activos",
                fg=C["accent"]
            )
        else:
            self.lbl_status.config(text="○ Agentes inactivos", fg=C["dim"])

        # Pills in status bar
        for name, pill in self._agent_pills.items():
            raw = str(agent_status.get(name, ""))
            icon, color, label = AGENTES[name]
            if "Activo" in raw:
                pill.config(fg=color)
            else:
                pill.config(fg=C["dim"])

        # Sidebar dots
        for name, dot in self._detail_pills.items():
            raw = str(agent_status.get(name, ""))
            icon, color, label = AGENTES[name]
            if "Activo" in raw:
                dot.config(fg=color)
            elif orch_up:
                dot.config(fg="#e67e22")
            else:
                dot.config(fg=C["dim"])


if __name__ == "__main__":
    app = AxoloitChat()
    app.mainloop()
