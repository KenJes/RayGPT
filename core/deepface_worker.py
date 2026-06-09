"""
deepface_worker.py — Proceso worker de DeepFace para análisis facial.

Se ejecuta con Python 3.12 (que soporta TensorFlow/DeepFace).
Lee rutas de imágenes desde stdin (una por línea) y escribe
resultados JSON a stdout (una línea por resultado).

Protocolo:
    IN  (stdin):  ruta_de_imagen.jpg\\n
    OUT (stdout): {"ok": true, "faces": [...]}\\n
    OUT (error):  {"ok": false, "error": "mensaje"}\\n

    Enviar "QUIT\\n" para cerrar el worker limpiamente.

Uso:
    .venv312\\Scripts\\python.exe core\\deepface_worker.py
"""

import json
import sys
import os
import tempfile
from pathlib import Path

# Suprimir warnings de TensorFlow
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import warnings
warnings.filterwarnings("ignore")

import logging
logging.getLogger("tensorflow").setLevel(logging.ERROR)

try:
    from deepface import DeepFace
except ImportError:
    print(json.dumps({"ok": False, "error": "DeepFace no disponible: pip install deepface"}),
          flush=True)
    sys.exit(1)


import numpy as np
try:
    import cv2
except ImportError:
    cv2 = None


def _to_python(val):
    """Convierte tipos numpy a tipos Python nativos para JSON."""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, np.ndarray):
        return val.tolist()
    if isinstance(val, dict):
        return {k: _to_python(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_to_python(v) for v in val]
    return val


def analyze_image(path: str) -> dict:
    """Analiza una imagen con DeepFace y retorna resultado serializable."""
    try:
        resultados = DeepFace.analyze(
            img_path=path,
            actions=["age", "gender", "emotion", "race"],
            enforce_detection=False,
            silent=True,
        )
        if not isinstance(resultados, list):
            resultados = [resultados]

        faces = []
        for r in resultados:
            face = {
                "age": _to_python(r.get("age")),
                "gender": str(r.get("dominant_gender", "")),
                "gender_confidence": _to_python(r.get("gender", {}).get(
                    r.get("dominant_gender", ""), 0
                )),
                "emotion": str(r.get("dominant_emotion", "")),
                "emotion_confidence": _to_python(r.get("emotion", {}).get(
                    r.get("dominant_emotion", ""), 0
                )),
                "race": str(r.get("dominant_race", "")),
                "race_confidence": _to_python(r.get("race", {}).get(
                    r.get("dominant_race", ""), 0
                )),
                "region": _to_python(r.get("region", {})),
            }
            faces.append(face)

        return {"ok": True, "faces": faces}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def verify_images(path1: str, path2: str) -> dict:
    """Verifica si dos imágenes son la misma persona usando DeepFace.verify()."""
    try:
        result = DeepFace.verify(
            img1_path=path1,
            img2_path=path2,
            enforce_detection=False,
            silent=True,
        )
        return {
            "ok": True,
            "verified": bool(result["verified"]),
            "distance": float(result["distance"]),
            "threshold": float(result["threshold"]),
            "model": str(result.get("model", "VGG-Face")),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def extract_faces(path: str) -> dict:
    """Extrae y cuenta los rostros en una imagen usando DeepFace.extract_faces()."""
    try:
        faces = DeepFace.extract_faces(
            img_path=path,
            enforce_detection=False,
        )
        return {
            "ok": True,
            "count": len(faces),
            "faces": [
                {
                    "confidence": float(f.get("confidence", 0)),
                    "area": _to_python(f.get("facial_area", {})),
                }
                for f in faces
            ],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def find_in_db(path: str, db_path: str, max_results: int = 5) -> dict:
    """Busca coincidencias de un rostro en una carpeta de base de datos."""
    try:
        results = DeepFace.find(
            img_path=path,
            db_path=db_path,
            enforce_detection=False,
            silent=True,
        )

        if not results:
            return {"ok": True, "matches": []}

        df = results[0]
        if getattr(df, "empty", False):
            return {"ok": True, "matches": []}

        matches = []
        top_rows = df.head(max_results)
        for _, row in top_rows.iterrows():
            matches.append({
                "identity": str(row.get("identity", "")),
                "distance": float(row.get("distance", 0.0)),
            })

        return {"ok": True, "matches": matches}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def represent_face(path: str, max_values: int = 10) -> dict:
    """Genera embedding facial de una imagen."""
    try:
        results = DeepFace.represent(
            img_path=path,
            enforce_detection=False,
        )
        if not isinstance(results, list):
            results = [results]

        faces = []
        for r in results:
            emb = r.get("embedding", []) or []
            faces.append({
                "model": str(r.get("model", "VGG-Face")),
                "dimensions": len(emb),
                "first_values": [float(v) for v in emb[:max_values]],
                "facial_area": _to_python(r.get("facial_area", {})),
            })

        return {"ok": True, "faces": faces}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _swap_face_internal(img_destino, reg_destino, img_fuente, reg_fuente):
    """Intercambia un rostro usando seamless clone."""
    sx, sy = reg_fuente["x"], reg_fuente["y"]
    sw, sh = reg_fuente["w"], reg_fuente["h"]
    dx, dy = reg_destino["x"], reg_destino["y"]
    dw, dh = reg_destino["w"], reg_destino["h"]

    cara_fuente = img_fuente[sy:sy + sh, sx:sx + sw]
    cara_redim = cv2.resize(cara_fuente, (dw, dh))

    canvas = img_destino.copy()
    canvas[dy:dy + dh, dx:dx + dw] = cara_redim

    mascara_local = np.zeros((dh, dw), dtype=np.uint8)
    cv2.ellipse(
        mascara_local,
        (dw // 2, dh // 2),
        (max(dw // 2 - 5, 1), max(dh // 2 - 5, 1)),
        0,
        0,
        360,
        255,
        -1,
    )
    mascara_full = np.zeros(img_destino.shape[:2], dtype=np.uint8)
    mascara_full[dy:dy + dh, dx:dx + dw] = mascara_local

    centro = (dx + dw // 2, dy + dh // 2)
    try:
        return cv2.seamlessClone(canvas, img_destino, mascara_full, centro, cv2.NORMAL_CLONE)
    except cv2.error:
        return canvas


def face_swap(path1: str, path2: str, out_dir: str = "") -> dict:
    """Intercambia rostros entre dos imágenes y guarda resultados."""
    if cv2 is None:
        return {"ok": False, "error": "OpenCV no disponible en el worker (pip install opencv-python)"}
    try:
        img1 = cv2.imread(path1)
        img2 = cv2.imread(path2)
        if img1 is None or img2 is None:
            return {"ok": False, "error": "No se pudieron leer una o ambas imágenes."}

        rostros1 = DeepFace.extract_faces(img_path=path1, enforce_detection=False)
        rostros2 = DeepFace.extract_faces(img_path=path2, enforce_detection=False)
        if not rostros1 or not rostros2:
            return {"ok": False, "error": "No se detectaron rostros en una o ambas imágenes."}

        reg1 = _to_python(rostros1[0].get("facial_area", {}))
        reg2 = _to_python(rostros2[0].get("facial_area", {}))

        swap_a = _swap_face_internal(img1, reg1, img2, reg2)
        swap_b = _swap_face_internal(img2, reg2, img1, reg1)

        if not out_dir:
            out_dir = tempfile.mkdtemp(prefix="raymundo_face_swap_")
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        out_a = str(Path(out_dir) / "rostro_swap_a.jpg")
        out_b = str(Path(out_dir) / "rostro_swap_b.jpg")
        cv2.imwrite(out_a, swap_a)
        cv2.imwrite(out_b, swap_b)

        return {
            "ok": True,
            "output_a": out_a,
            "output_b": out_b,
            "region_a": reg1,
            "region_b": reg2,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    """Loop principal: lee paths de stdin, escribe JSON a stdout."""
    # Señal de que el worker está listo
    print(json.dumps({"ok": True, "status": "ready"}), flush=True)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:  # EOF — pipe cerrado
                break
            line = line.strip()
            if not line:
                continue
            if line.upper() == "QUIT":
                break

            # Accept JSON command {"op": "analyze"|"verify"|"extract", ...}
            # or plain path string (backward compat → analyze)
            if line.startswith("{"):
                try:
                    cmd = json.loads(line)
                    op = cmd.get("op", "analyze")
                    if op == "verify":
                        result = verify_images(cmd.get("path1", ""), cmd.get("path2", ""))
                    elif op == "extract":
                        result = extract_faces(cmd.get("path", ""))
                    elif op == "find":
                        result = find_in_db(
                            cmd.get("path", ""),
                            cmd.get("db_path", ""),
                            int(cmd.get("max_results", 5)),
                        )
                    elif op == "represent":
                        result = represent_face(
                            cmd.get("path", ""),
                            int(cmd.get("max_values", 10)),
                        )
                    elif op == "face_swap":
                        result = face_swap(
                            cmd.get("path1", ""),
                            cmd.get("path2", ""),
                            cmd.get("out_dir", ""),
                        )
                    else:
                        result = analyze_image(cmd.get("path", ""))
                except json.JSONDecodeError as je:
                    result = {"ok": False, "error": f"JSON inválido: {je}"}
            else:
                # Plain path — backward compat (analyze)
                result = analyze_image(line)

            print(json.dumps(result), flush=True)
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}), flush=True)

    # Despedida limpia
    print(json.dumps({"ok": True, "status": "shutdown"}), flush=True)


if __name__ == "__main__":
    main()
