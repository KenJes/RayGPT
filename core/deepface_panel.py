"""
DeepFace panel for Raymundo GUI.
Provides 8 actions similar to demo_analisis_facial_deepface.py,
backed by the Python 3.12 DeepFace worker.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from core.deepface_stream import DeepFaceStream


class DeepFacePanel:
    """Standalone window with 8 DeepFace actions."""

    def __init__(self, root: tk.Tk, deepface_client):
        self.root = root
        self.deepface_client = deepface_client
        self.window: tk.Toplevel | None = None
        self.log_widget: scrolledtext.ScrolledText | None = None
        self.stream: DeepFaceStream | None = None

    def open(self):
        if not self.deepface_client or not getattr(self.deepface_client, "available", False):
            messagebox.showwarning(
                "DeepFace no disponible",
                "No se encontro el worker de DeepFace.\n"
                "Se requiere Python 3.12 con deepface en .venv312.",
            )
            return

        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return

        self.window = tk.Toplevel(self.root)
        self.window.title("DeepFace - 8 funciones")
        self.window.geometry("900x620")
        self.window.configure(bg="#1b1b1b")
        self.window.minsize(760, 520)
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        header = tk.Frame(self.window, bg="#141421", height=56)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="DeepFace (worker Python 3.12)",
            bg="#141421",
            fg="#f0f0f0",
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left", padx=14, pady=10)

        actions = tk.Frame(self.window, bg="#1b1b1b")
        actions.pack(fill="x", padx=12, pady=10)

        buttons = [
            ("1. analyze()", self._run_analyze),
            ("2. verify()", self._run_verify),
            ("3. find()", self._run_find),
            ("4. represent()", self._run_represent),
            ("5. extract_faces()", self._run_extract),
            ("6. Tiempo real", self._run_realtime),
            ("7. Ejecutar TODOS", self._run_all),
            ("8. face_swap()", self._run_face_swap),
        ]

        for idx, (label, fn) in enumerate(buttons):
            btn = tk.Button(
                actions,
                text=label,
                command=lambda cb=fn: threading.Thread(target=cb, daemon=True).start(),
                bg="#2f2f52",
                fg="#e3e3f8",
                activebackground="#45457a",
                activeforeground="#ffffff",
                relief="flat",
                padx=10,
                pady=7,
                cursor="hand2",
                font=("Segoe UI", 9),
            )
            btn.grid(row=idx // 4, column=idx % 4, padx=5, pady=5, sticky="ew")

        for c in range(4):
            actions.grid_columnconfigure(c, weight=1)

        self.log_widget = scrolledtext.ScrolledText(
            self.window,
            wrap=tk.WORD,
            bg="#101015",
            fg="#e6e6e6",
            font=("Consolas", 10),
            relief="flat",
            padx=10,
            pady=10,
            state="normal",
        )
        self.log_widget.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._log("Panel DeepFace listo.")
        self._log("Usando worker en Python 3.12: .venv312\\Scripts\\python.exe")

    def _close(self):
        if self.stream and self.stream.is_running:
            self.stream.stop()
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None

    def _pick_image(self, title: str) -> str:
        return filedialog.askopenfilename(
            title=title,
            filetypes=[
                ("Imagenes", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("Todos", "*.*"),
            ],
        )

    def _pick_folder(self, title: str) -> str:
        return filedialog.askdirectory(title=title)

    def _log(self, text: str):
        if not self.log_widget:
            return
        self.log_widget.insert(tk.END, text + "\n")
        self.log_widget.see(tk.END)

    def _run_analyze(self):
        path = self._pick_image("Imagen para analyze()")
        if not path:
            return
        self._log(f"[analyze] {path}")
        res = self.deepface_client.analyze(path)
        if not res:
            self._log("  Error: no hubo respuesta del worker")
            return
        faces = res.get("faces", [])
        self._log(f"  Rostros detectados: {len(faces)}")
        for i, face in enumerate(faces, 1):
            self._log(
                f"  #{i} edad~{face.get('age')} genero={face.get('gender')} "
                f"emocion={face.get('emotion')} raza={face.get('race')}"
            )

    def _run_verify(self):
        path1 = self._pick_image("Imagen 1 para verify()")
        if not path1:
            return
        path2 = self._pick_image("Imagen 2 para verify()")
        if not path2:
            return
        self._log(f"[verify] {path1} vs {path2}")
        res = self.deepface_client.verify(path1, path2)
        if not res:
            self._log("  Error: no hubo respuesta del worker")
            return
        self._log(
            "  verified={} distance={:.4f} threshold={:.4f} model={}".format(
                res.get("verified"),
                float(res.get("distance", 0.0)),
                float(res.get("threshold", 0.0)),
                res.get("model", "?"),
            )
        )

    def _run_find(self):
        path = self._pick_image("Imagen query para find()")
        if not path:
            return
        db_path = self._pick_folder("Carpeta de base de datos")
        if not db_path:
            return
        self._log(f"[find] query={path} db={db_path}")
        res = self.deepface_client.find(path, db_path, max_results=5)
        if not res:
            self._log("  Error: no hubo respuesta del worker")
            return
        matches = res.get("matches", [])
        self._log(f"  Coincidencias: {len(matches)}")
        for i, m in enumerate(matches, 1):
            self._log(f"  #{i} dist={float(m.get('distance', 0.0)):.4f} file={m.get('identity', '')}")

    def _run_represent(self):
        path = self._pick_image("Imagen para represent()")
        if not path:
            return
        self._log(f"[represent] {path}")
        res = self.deepface_client.represent(path, max_values=10)
        if not res:
            self._log("  Error: no hubo respuesta del worker")
            return
        faces = res.get("faces", [])
        self._log(f"  Embeddings detectados: {len(faces)}")
        for i, f in enumerate(faces, 1):
            self._log(
                f"  #{i} model={f.get('model')} dims={f.get('dimensions')} "
                f"first10={f.get('first_values')}"
            )

    def _run_extract(self):
        path = self._pick_image("Imagen para extract_faces()")
        if not path:
            return
        self._log(f"[extract_faces] {path}")
        res = self.deepface_client.extract_faces(path)
        if not res:
            self._log("  Error: no hubo respuesta del worker")
            return
        self._log(f"  Rostros detectados: {res.get('count', 0)}")
        for i, f in enumerate(res.get("faces", []), 1):
            self._log(f"  #{i} conf={float(f.get('confidence', 0.0)):.4f} area={f.get('area', {})}")

    def _run_realtime(self):
        if self.stream and self.stream.is_running:
            self._log("[tiempo real] Deteniendo stream...")
            self.stream.stop()
            return

        self._log("[tiempo real] Iniciando stream (Q o ESC para cerrar ventana OpenCV)...")
        self.stream = DeepFaceStream(camera_index=0, analyze_interval=1.8)
        res = self.stream.start()
        if not res.get("success"):
            self._log(f"  Error: {res.get('error', 'desconocido')}")
        else:
            self._log("  Stream activo")

    def _run_all(self):
        self._log("[todos] Ejecutando suite guiada...")
        self._run_analyze()
        self._run_verify()
        self._run_find()
        self._run_represent()
        self._run_extract()
        self._log("[todos] Listo. Puedes ejecutar tiempo real y face_swap por separado.")

    def _run_face_swap(self):
        path1 = self._pick_image("Imagen A para face_swap()")
        if not path1:
            return
        path2 = self._pick_image("Imagen B para face_swap()")
        if not path2:
            return
        out_dir = self._pick_folder("Carpeta de salida (opcional)")
        self._log(f"[face_swap] A={path1} B={path2}")
        res = self.deepface_client.face_swap(path1, path2, out_dir=out_dir)
        if not res:
            self._log("  Error: no hubo respuesta del worker")
            return
        self._log(f"  Output A: {res.get('output_a', '')}")
        self._log(f"  Output B: {res.get('output_b', '')}")
        self._log(f"  Region A: {res.get('region_a', {})}")
        self._log(f"  Region B: {res.get('region_b', {})}")
