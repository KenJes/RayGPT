"""
Servidor local para el Generador de Planeaciones Didácticas.

Sirve el HTML en http://127.0.0.1:8765/
y actúa como proxy CORS para las llamadas a Ollama (/api/chat).

Uso desde Python:
    from planeacion_server import start_server
    url = start_server()          # http://127.0.0.1:8765
    webbrowser.open(url)

Uso directo:
    python planeacion_server.py
"""

import threading
import urllib.request
import urllib.error
from pathlib import Path

from flask import Flask, request, jsonify, send_file, abort

app = Flask(__name__)

HTML_PATH = Path(__file__).parent / "resources" / "planeacion" / "genplanAI.html"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

# ── CORS ──────────────────────────────────────────────────────

def _add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ── Rutas ─────────────────────────────────────────────────────

@app.route("/")
def index():
    if HTML_PATH.exists():
        return send_file(str(HTML_PATH))
    abort(404, description=f"Archivo no encontrado: {HTML_PATH}")


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def proxy_ollama():
    if request.method == "OPTIONS":
        return _add_cors(app.response_class(status=200))

    try:
        payload = request.get_data()
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            data = r.read()
        resp = app.response_class(response=data, status=200, mimetype="application/json")
        return _add_cors(resp)

    except urllib.error.URLError as e:
        resp = jsonify({"error": f"Ollama no disponible: {e.reason}"})
        resp.status_code = 503
        return _add_cors(resp)
    except Exception as e:
        resp = jsonify({"error": str(e)})
        resp.status_code = 500
        return _add_cors(resp)


# ── Arranque embebido ──────────────────────────────────────────

_started = False
_lock = threading.Lock()


def start_server(port: int = 8765) -> str:
    """Inicia el servidor en un hilo daemon (solo una vez).

    Returns:
        URL base, e.g. "http://127.0.0.1:8765"
    """
    global _started
    with _lock:
        if not _started:
            import logging
            logging.getLogger("werkzeug").setLevel(logging.ERROR)

            t = threading.Thread(
                target=lambda: app.run(
                    host="127.0.0.1",
                    port=port,
                    debug=False,
                    use_reloader=False,
                ),
                daemon=True,
                name="PlaneacionServer",
            )
            t.start()
            _started = True
    return f"http://127.0.0.1:{port}"


# ── Entrada directa ───────────────────────────────────────────

if __name__ == "__main__":
    print("🎓 Servidor de Planeaciones Didácticas")
    print("   URL: http://127.0.0.1:8765")
    print("   Proxy Ollama: http://127.0.0.1:11434")
    print("   Presiona Ctrl+C para detener\n")
    app.run(host="127.0.0.1", port=8765, debug=False)
