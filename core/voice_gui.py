"""
voice_gui.py — GUI minimalista para el asistente de voz.

Ventana oscura con animación de orbe central que refleja
el estado del asistente: idle · wake · listening · thinking · speaking.
"""

from __future__ import annotations

import math
import sys
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

# ── Paleta de colores ─────────────────────────────────────────
_P = {
    "bg":        "#0d1117",
    "surface":   "#161b22",
    "border":    "#30363d",
    "text":      "#e6edf3",
    "subtext":   "#8b949e",
    "dim":       "#484f58",
    "idle":      "#58a6ff",
    "wake":      "#3fb950",
    "listening": "#f78166",
    "thinking":  "#bc8cff",
    "speaking":  "#79c0ff",
}


def _lerp(c1: str, c2: str, t: float) -> str:
    """Interpolación lineal entre dos colores hex."""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = max(0, min(255, int(r1 + (r2 - r1) * t)))
    g = max(0, min(255, int(g1 + (g2 - g1) * t)))
    b = max(0, min(255, int(b1 + (b2 - b1) * t)))
    return f"#{r:02x}{g:02x}{b:02x}"


class VoiceGUI:
    """Ventana principal del asistente de voz con animaciones de orbe."""

    # Estados públicos
    IDLE      = "idle"
    WAKE      = "wake"
    LISTENING = "listening"
    THINKING  = "thinking"
    SPEAKING  = "speaking"

    _FPS = 30

    def __init__(self, persona: str = "raymundo",
                 on_close: Callable[[], None] | None = None):
        self._persona = persona
        self._on_close = on_close
        self._state = self.IDLE
        self._frame = 0
        self._alive = True

        # ── Ventana ───────────────────────────────────────────
        self._root = tk.Tk()
        name = "Raymundo" if persona == "raymundo" else "R.E.I.N.A."
        self._root.title(f"{name} · Asistente de Voz")
        self._root.configure(bg=_P["bg"])
        self._root.geometry("420x560")
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._handle_close)

        # Barra de título oscura (Windows 10 1903+ / 11)
        self._apply_dark_titlebar()

        # ── Fuentes ───────────────────────────────────────────
        self._ft_title  = tkfont.Font(family="Segoe UI", size=24, weight="bold")
        self._ft_sub    = tkfont.Font(family="Segoe UI", size=11)
        self._ft_status = tkfont.Font(family="Segoe UI", size=14)
        self._ft_hint   = tkfont.Font(family="Segoe UI", size=9)

        self._build()
        self._tick()

    # ── Construir interfaz ────────────────────────────────────

    def _build(self):
        bg = _P["bg"]

        # Título
        lbl_name = "RAYMUNDO" if self._persona == "raymundo" else "R.E.I.N.A."
        self._lbl_title = tk.Label(
            self._root, text=lbl_name,
            font=self._ft_title, fg=_P["text"], bg=bg,
        )
        self._lbl_title.pack(pady=(40, 0))

        # Sub-título (voz activa)
        voice = "Voz: Jorge · Masculina" if self._persona == "raymundo" \
                else "Voz: Dalia · Femenina"
        self._lbl_voice = tk.Label(
            self._root, text=voice,
            font=self._ft_hint, fg=_P["subtext"], bg=bg,
        )
        self._lbl_voice.pack(pady=(4, 25))

        # Canvas del orbe
        sz = 260
        self._cvs = tk.Canvas(
            self._root, width=sz, height=sz,
            bg=bg, highlightthickness=0,
        )
        self._cvs.pack()
        self._cx = sz // 2
        self._cy = sz // 2

        # Estado
        self._lbl_status = tk.Label(
            self._root, text="Esperando\u2026",
            font=self._ft_status, fg=_P["text"], bg=bg,
        )
        self._lbl_status.pack(pady=(25, 4))

        # Hint
        wake = "Raymundo" if self._persona == "raymundo" else "Reina"
        self._lbl_hint = tk.Label(
            self._root, text=f'Di "{wake}" para activar',
            font=self._ft_hint, fg=_P["subtext"], bg=bg,
        )
        self._lbl_hint.pack(pady=(0, 0))

        # Hint inferior (switch)
        self._lbl_switch = tk.Label(
            self._root,
            text='"Cambia a Reina" \u00b7 "Cambia a Raymundo"',
            font=self._ft_hint, fg=_P["dim"], bg=bg,
        )
        self._lbl_switch.pack(side=tk.BOTTOM, pady=(0, 20))

    # ── API pública (thread-safe) ─────────────────────────────

    def set_state(self, state: str, status: str = "",
                  hint: str = ""):
        """Cambia estado + textos.  Seguro desde cualquier hilo."""
        self._root.after(0, self._apply_state, state, status, hint)

    def set_persona(self, persona: str):
        """Cambia la persona mostrada.  Thread-safe."""
        self._root.after(0, self._apply_persona, persona)

    def run(self):
        """Inicia el mainloop de Tk (debe ejecutarse en el hilo principal)."""
        self._root.mainloop()

    def destroy(self):
        self._alive = False
        try:
            self._root.destroy()
        except tk.TclError:
            pass

    # ── Internos ──────────────────────────────────────────────

    def _apply_state(self, state: str, status: str, hint: str):
        self._state = state
        self._frame = 0
        if status:
            self._lbl_status.config(text=status)
        if hint:
            self._lbl_hint.config(text=hint)

    def _apply_persona(self, persona: str):
        self._persona = persona
        name  = "RAYMUNDO" if persona == "raymundo" else "R.E.I.N.A."
        voice = "Voz: Jorge \u00b7 Masculina" if persona == "raymundo" \
                else "Voz: Dalia \u00b7 Femenina"
        wake  = "Raymundo" if persona == "raymundo" else "Reina"
        self._lbl_title.config(text=name)
        self._lbl_voice.config(text=voice)
        self._lbl_hint.config(text=f'Di "{wake}" para activar')
        self._root.title(f"{name} \u00b7 Asistente de Voz")

    def _handle_close(self):
        self._alive = False
        if self._on_close:
            self._on_close()
        try:
            self._root.destroy()
        except tk.TclError:
            pass

    def _apply_dark_titlebar(self):
        """Fuerza barra de título oscura en Windows 10/11."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            self._root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self._root.winfo_id())
            DWMWA = 20  # DWMWA_USE_IMMERSIVE_DARK_MODE
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA,
                ctypes.byref(ctypes.c_int(1)),
                ctypes.sizeof(ctypes.c_int),
            )
        except Exception:
            pass

    # ── Tick de animación ─────────────────────────────────────

    def _tick(self):
        if not self._alive:
            return
        self._cvs.delete("all")
        self._frame += 1

        _draw = {
            self.IDLE:      self._draw_idle,
            self.WAKE:      self._draw_wake,
            self.LISTENING: self._draw_listening,
            self.THINKING:  self._draw_thinking,
            self.SPEAKING:  self._draw_speaking,
        }
        _draw.get(self._state, self._draw_idle)()
        self._root.after(1000 // self._FPS, self._tick)

    # ── Animaciones ───────────────────────────────────────────

    def _draw_idle(self):
        """Anillo que respira suavemente (azul)."""
        col = _P["idle"]
        t = math.sin(self._frame * 0.05) * 0.5 + 0.5
        r = 50 + t * 8

        # Resplandor exterior
        for i in range(5, 0, -1):
            gr = r + i * 9
            self._oval(gr, _lerp(_P["bg"], col, 0.06 * (6 - i)))

        self._ring(r, col, w=3)
        self._oval(5, col)

    def _draw_wake(self):
        """Flash verde de activación (~0.5 s)."""
        col = _P["wake"]
        p = min(self._frame / 15, 1.0)

        # Onda expansiva
        wr = 50 + p * 60
        self._oval(wr, _lerp(_P["bg"], col, max(0, (1 - p) * 0.45)))

        # Anillo base
        cr = 50 + (1 - abs(1 - p * 2)) * 15
        self._ring(cr, col, w=4)
        self._oval(7, col)

    def _draw_listening(self):
        """Ondas concéntricas expansivas (naranja)."""
        col = _P["listening"]
        base = 42

        for w in range(3):
            off = (self._frame * 2 + w * 22) % 65
            wr = base + off
            a = max(0, 1 - off / 65)
            self._ring(wr, _lerp(_P["bg"], col, a * 0.55),
                       w=max(1, int(3 * a)))

        # Núcleo pulsante
        t = math.sin(self._frame * 0.15) * 0.5 + 0.5
        cr = 32 + t * 10
        self._oval(cr, _lerp(_P["bg"], col, 0.22))
        self._ring(cr, col, w=3)
        self._oval(6, col)

    def _draw_thinking(self):
        """Puntos orbitando (morado)."""
        col = _P["thinking"]
        n = 8
        orbit = 50
        ang0 = self._frame * 0.08

        self._ring(65, _lerp(_P["bg"], col, 0.12), w=1)

        for i in range(n):
            a = ang0 + 2 * math.pi * i / n
            x = self._cx + orbit * math.cos(a)
            y = self._cy + orbit * math.sin(a)
            frac = i / n
            dc = _lerp(_P["bg"], col, 0.2 + 0.8 * frac)
            dr = 3 + frac * 5
            self._cvs.create_oval(
                x - dr, y - dr, x + dr, y + dr,
                fill=dc, outline="",
            )

        t = math.sin(self._frame * 0.1) * 0.5 + 0.5
        self._oval(10 + t * 5, _lerp(_P["bg"], col, 0.35))

    def _draw_speaking(self):
        """Orbe pulsante orgánico (azul claro)."""
        col = _P["speaking"]
        t1 = math.sin(self._frame * 0.12) * 0.5 + 0.5
        t2 = math.sin(self._frame * 0.07 + 1) * 0.3 + 0.5
        r = 42 + t1 * 20 + t2 * 10

        for i in range(4, 0, -1):
            gr = r + i * 11
            self._oval(gr, _lerp(_P["bg"], col, 0.05 * (5 - i)))

        self._oval(r, _lerp(_P["bg"], col, 0.28))
        self._ring(r, col, w=3)
        self._oval(7, col)

    # ── Helpers de Canvas ─────────────────────────────────────

    def _oval(self, r: float, fill: str):
        cx, cy = self._cx, self._cy
        self._cvs.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill=fill, outline="",
        )

    def _ring(self, r: float, outline: str, w: int = 2):
        cx, cy = self._cx, self._cy
        self._cvs.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill="", outline=outline, width=w,
        )
