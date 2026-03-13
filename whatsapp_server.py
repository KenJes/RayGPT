"""
rAImundoGPT WhatsApp Server

Servidor Flask que expone el agente Raymundo como API REST
para que el bot de WhatsApp pueda consultarlo.

REQUISITOS:
    pip install flask flask-cors

USO:
    python whatsapp_server.py

ENDPOINTS:
    POST /chat
        Body: {"mensaje": "tu pregunta aquí"}
        Response: {"respuesta": "respuesta de Raymundo"}
        
    GET /health
        Response: {"status": "ok", "agent": "rAImundoGPT"}
"""

import re
import json
import os
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

# Crear directorios si no existen
for directory in (CONFIG_DIR, DATA_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

CREDENTIALS_FILE = BASE_DIR / 'resources' / 'data' / 'google-credentials.json'
METRICS_FILE = DATA_DIR / 'metrics.json'

# Importar componentes desde core/
from core.ai_clients import OllamaClient, GitHubModelsClient, GroqClient
from core.tools import GestorHerramientas
from core.detectors import DetectorIdioma
from core.config import config_agente as config_agente_module
from core.google_workspace_client import GoogleWorkspaceClient
from core.metrics_tracker import MetricsTracker
from core.audio_handler import get_audio_handler
from core.adapters import build_registry
from core.agent_loop import AgentLoop, es_meta_compleja
from core.agent_logger import AgentLogger
from core.agent_memory import VectorMemory
from core.approval import approval_manager
from core.conversation_db import ConversationDB
from core.knowledge_db import KnowledgeBase
from core.spotify_client import SpotifyClient, detect_spotify_intent

# ====================================
# CONFIGURACIÓN DE FLASK
# ====================================
app = Flask(__name__)
CORS(app)  # Permitir CORS para Node.js

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ====================================
# INICIALIZAR AGENTE RAYMUNDO
# ====================================

print("🤖 Inicializando rAImundoGPT para WhatsApp...")


def generar_nombre_archivo(titulo):
    """Genera un nombre de archivo seguro para Windows."""
    if not titulo:
        return "archivo"
    # Reemplazar caracteres no permitidos por guion bajo
    nombre = re.sub(r'[\\/:*?"<>|]', '_', titulo)
    # Reemplazar espacios y guiones dobles por guion bajo
    nombre = re.sub(r'\s+', '_', nombre)
    nombre = nombre.replace('-', '_')
    nombre = nombre.strip('_')
    return nombre or "archivo"

try:
    # Cargar configuración desde JSON
    with open('config_agente.json', 'r', encoding='utf-8') as f:
        config_agente = json.load(f)
    logger.info("✅ Configuración cargada")
    
    # Inicializar clientes AI
    ollama = OllamaClient()
    github = GitHubModelsClient()
    groq = GroqClient()  # Nuevo: Groq (14,400 RPD gratis)
    google = GoogleWorkspaceClient(str(CREDENTIALS_FILE))
    
    # Crear gestor de herramientas con Groq
    gestor = GestorHerramientas(ollama, github, google, groq=groq)
    detector_idioma = DetectorIdioma()  # Bilingual personality routing
    
    # Inicializar metrics tracker
    metrics = MetricsTracker(str(METRICS_FILE))
    
    # Inicializar manejador de audio con voz masculina (Edge TTS Jorge Neural)
    audio_handler = get_audio_handler(voice_config={
        'engine': 'edge-tts',  # edge-tts (neural, calidad TikTok) > pyttsx3 > gtts
        'gender': 'male',      # male=JorgeNeural | female=DaliaNeural
        'rate': 180            # Velocidad: 150=lento, 180=normal, 200=rápido
    })
    logger.info("✅ Manejador de audio inicializado")
    
    logger.info("✅ Agente Raymundo inicializado")
    logger.info(f"   • Personalidad: {config_agente.get('personalidad', {}).get('tono', 'desconocido')}")
    logger.info(f"   • Modelo Ollama: {config_agente.get('modelos', {}).get('ollama', {}).get('modelo', 'llama3.1:8b')}")

    # Inicializar infraestructura agéntica
    knowledge_base = KnowledgeBase()  # data/conocimiento.db
    logger.info("✅ Base de conocimiento inicializada (SQLite)")

    # Inicializar Spotify (opcional — solo si hay config)
    spotify_config = config_agente.get("spotify", {})
    sp_client_id = os.getenv("SPOTIFY_CLIENT_ID") or spotify_config.get("client_id", "")
    sp_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET") or spotify_config.get("client_secret", "")
    sp_redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI") or spotify_config.get("redirect_uri", "http://localhost:5000/spotify/callback")
    spotify_client = None
    if sp_client_id and sp_client_secret:
        spotify_client = SpotifyClient(
            client_id=sp_client_id,
            client_secret=sp_client_secret,
            redirect_uri=sp_redirect_uri,
        )
        status = "✅ autenticado" if spotify_client.is_authenticated else "⚠️ pendiente de auth (/spotify/auth)"
        logger.info(f"🎵 Spotify inicializado ({status})")
    else:
        logger.info("⚠️ Spotify no configurado (agrega SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET en el archivo .env)")

    adapter_registry = build_registry(gestor, knowledge_base=knowledge_base, spotify_client=spotify_client)

    def _ai_chat_for_agent(messages, temperature=0.4, max_tokens=2000):
        """Función de chat para el AgentLoop — usa la cadena de fallback."""
        if groq and groq.client:
            r = groq.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if r:
                return r
        if github and github.client:
            r = github.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if r:
                return r
        # Ollama solo acepta prompt plano
        prompt = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}" for m in messages
        )
        return ollama.generate(prompt, temperature=temperature, max_tokens=max_tokens) or ""

    agent_logger = AgentLogger()
    agent_memory = VectorMemory()
    agent_loop = AgentLoop(
        registry=adapter_registry,
        ai_chat_fn=_ai_chat_for_agent,
        logger=agent_logger,
        memory=agent_memory,
        approval=approval_manager,
    )
    logger.info("✅ Infraestructura agéntica inicializada (adapters, loop, memory, logger)")
    
except Exception as e:
    logger.error(f"❌ Error inicializando Raymundo: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ====================================
# BASE DE DATOS DE CONVERSACIONES (SQLite persistente)
# ====================================

conversation_db = ConversationDB()  # data/conversaciones.db — sobrevive reinicios
logger.info("✅ Base de datos de conversaciones inicializada (SQLite)")

# Dict en RAM solo para cosas efímeras (idioma override por sesión)
conversaciones = {}  # Solo para idioma_override

# Personalidad y nombre por usuario (override independiente por sesión)
personalidades_por_usuario = {}

# Nombres de contacto conocidos
nombres_contactos = {}


def _summarize_fn(prompt: str) -> str:
    """Función para resumir historial viejo usando la cadena de IA."""
    try:
        return gestor._consultar_ia(prompt, temperature=0.3, max_tokens=500)
    except Exception:
        return ""


def get_historial(user_id):
    """Obtiene el historial reciente de un usuario desde SQLite."""
    return conversation_db.get_history(user_id)


def get_contexto_completo(user_id):
    """Obtiene historial + resúmenes de conversaciones anteriores para el LLM."""
    return conversation_db.build_context_messages(user_id, summarize_fn=_summarize_fn)


def agregar_mensaje(user_id, role, content):
    """Guarda un mensaje en la BD persistente."""
    conversation_db.add_message(user_id, role, content)


def limpiar_historial(user_id):
    """Limpia el historial de un usuario."""
    conversation_db.clear_history(user_id)

def get_tono_usuario(user_id):
    """Devuelve el tono activo para un usuario (per-user override o global)."""
    if user_id in personalidades_por_usuario:
        return personalidades_por_usuario[user_id].get("tono")
    return config_agente.get("personalidad", {}).get("tono", "amigable")

def set_tono_usuario(user_id, tono):
    """Configura el tono para un usuario específico."""
    if user_id not in personalidades_por_usuario:
        personalidades_por_usuario[user_id] = {}
    personalidades_por_usuario[user_id]["tono"] = tono
    limpiar_historial(user_id)

# Palabras que indican que el usuario está siendo agresivo en ESTE mensaje
_PALABRAS_AGRESIVAS = {
    'pendejo', 'pendeja', 'pendejos', 'puto', 'puta', 'putos', 'putas',
    'cabron', 'cabrón', 'cabrona', 'chinga', 'chingada', 'chingon', 'chingo',
    'verga', 'vergas', 'naco', 'naca', 'pinche', 'pinches', 'culero', 'culera',
    'mierda', 'estupido', 'estúpido', 'imbecil', 'imbécil', 'idiota',
    'mamada', 'mamadas', 'maldito', 'bastardo', 'putisimo', 'putísimo',
    'gey', 'wey', 'guey',  # wey puede ser agresivo en contexto de insulto
    'joto', 'marica', 'perra', 'perro',  # como insulto
    'fuck', 'shit', 'ass', 'bitch',
}

def detectar_agresividad_usuario(texto):
    """
    Detecta si el mensaje actual contiene lenguaje agresivo/grosero.
    Devuelve True si el usuario está siendo agresivo en ESTE mensaje.
    No cambia la configuración permanente — solo da contexto para esta respuesta.
    """
    palabras = re.sub(r'[^a-záéíóúüñ ]', ' ', texto.lower()).split()
    conteo = sum(1 for p in palabras if p in _PALABRAS_AGRESIVAS)
    return conteo >= 1

def detectar_cambio_personalidad_natural(texto):
    """
    Detecta si el usuario pide un cambio de personalidad en lenguaje natural.
    Devuelve 'amigable', 'puteado', o None.
    """
    t = texto.lower()
    amigable = [
        'se amable', 'sé amable', 'se educado', 'sé educado', 'se respetuoso',
        'sé respetuoso', 'modo amable', 'modo educado', 'modo respetuoso',
        'cambia a amigable', 'cambia a modo amable', 'cambia a educado',
        'sin groserías', 'sin groseria', 'no seas grosero', 'no seas maleducado',
        'habla bien', 'portate bien', 'compórtate', 'comportate',
        'se formal', 'sé formal', 'modo formal', 'modo profesional',
        'presenta respetuosamente', 'presentate respetuosamente',
    ]
    grosero = [
        'se grosero', 'sé grosero', 'se puteado', 'sé puteado',
        'modo grosero', 'modo puteado', 'modo rudo', 'modo directo',
        'cambia a grosero', 'cambia a puteado', 'cambia a rai',
        'se rudo', 'sé rudo', 'puedes insultar', 'di groserías', 'di groseria',
        'habla con groserías', 'habla mal', 'suéltate', 'sueltate',
    ]
    for frase in amigable:
        if frase in t:
            return 'amigable'
    for frase in grosero:
        if frase in t:
            return 'puteado'
    return None

# ====================================
# EXTRACCIÓN DE CONOCIMIENTO DE CONVERSACIONES
# ====================================

def _extraer_y_guardar_conocimiento(mensaje: str, respuesta: str, user_id: str):
    """
    Analiza el mensaje y la respuesta para extraer datos de personas
    mencionadas y guardarlos en la base de conocimiento.
    Usa regex ligero — NO llama al LLM para evitar latencia extra.
    """
    try:
        texto_completo = f"{mensaje}\n{respuesta}"

        # Patrones para detectar datos de personas (nombres propios)
        # Buscar "se llama X", "X es ...", "X trabaja en ...", etc.
        patrones_nombre = [
            r'(?:se llama|mi (?:amigo|amiga|compañero|compañera|colega|jefe|conocido|sobrino|primo|hermano|esposa|esposo|novio|novia) (?:se llama )?)\s*([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
            r'(?:hablé con|platiqué con|me dijo|me contó|entrevisté a|el candidato|la candidata|conocí a)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)',
        ]

        nombres_encontrados = set()
        for patron in patrones_nombre:
            matches = re.findall(patron, texto_completo, re.IGNORECASE)
            for m in matches:
                nombre = m.strip()
                if len(nombre) > 2 and nombre.lower() not in {'con', 'que', 'del', 'los', 'las', 'una', 'uno'}:
                    nombres_encontrados.add(nombre)

        # Para cada persona detectada, guardar un fact con lo que se dijo
        for nombre in nombres_encontrados:
            # Extraer oraciones que mencionan a esta persona
            oraciones = re.findall(
                r'[^.!?]*\b' + re.escape(nombre) + r'\b[^.!?]*[.!?]',
                texto_completo,
                re.IGNORECASE,
            )
            if oraciones:
                fact = " ".join(o.strip() for o in oraciones[:3])  # Máx 3 oraciones
                knowledge_base.add_fact(nombre, fact, source="conversacion", user_id=user_id)
                logger.info(f"📝 Fact guardado sobre {nombre}")

                # Si hay datos estructurales, crear/actualizar persona
                texto_lower = texto_completo.lower()
                person_data = {"name": nombre, "added_by": user_id}

                # Detectar skills
                skills_match = re.findall(
                    r'(?:sabe|conoce|domina|maneja|experiencia en|trabaja con)\s+([^,.!?]+)',
                    texto_lower,
                )
                if skills_match:
                    person_data["skills"] = [s.strip() for s in skills_match[:5]]

                # Detectar rol
                rol_match = re.search(
                    r'(?:es|trabaja como|trabaja de|su puesto es|su rol es)\s+([^,.!?]{3,40})',
                    texto_lower,
                )
                if rol_match:
                    person_data["role"] = rol_match.group(1).strip()

                knowledge_base.store_person(**person_data)

    except Exception as e:
        logger.warning(f"⚠️ Error extrayendo conocimiento: {e}")


# ====================================
# SPOTIFY — DETECCIÓN DE COMANDOS RÁPIDOS
# ====================================

def _handle_spotify_command(mensaje: str) -> str | None:
    """
    Detecta comandos de Spotify en lenguaje natural.
    Devuelve la respuesta directa o None si no es un comando de Spotify.
    Si el comando es reconocido pero Spotify no está autenticado, avisa al usuario.
    """
    t = mensaje.lower().strip()
    intent, query = detect_spotify_intent(t)

    if intent is None:
        return None  # No es un comando de Spotify — continuar flujo normal

    # Es un comando de Spotify reconocido ─ verificar autenticación
    if not spotify_client:
        return (
            "⚠️ Spotify no está configurado. Agrega tus credenciales en el archivo .env "
            "(SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET)."
        )

    if not spotify_client.is_authenticated:
        auth_url = spotify_client.get_auth_url()
        return (
            "🎵 Para que pueda controlar Spotify necesito que me autorices primero.\n"
            "Abre este enlace en tu navegador:\n"
            f"👉 {auth_url}\n\n"
            "Una vez que autorices, vuelve a enviar el comando y lo ejecuto."
        )

    # Ejecutar el comando
    try:
        if intent == "pause":
            return spotify_client.pause()
        elif intent == "play" and query:
            return spotify_client.play(query)
        elif intent == "play":
            return spotify_client.play()
        elif intent == "next":
            return spotify_client.next_track()
        elif intent == "previous":
            return spotify_client.previous_track()
        elif intent == "current":
            return spotify_client.current_track()
    except Exception as e:
        return f"❌ Error Spotify: {e}"

    return None


# ====================================
# ENDPOINTS
# ====================================

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de salud para verificar que el servidor está corriendo"""
    return jsonify({
        "status": "ok",
        "agent": "rAImundoGPT",
        "version": "2.0",
        "personality": config_agente.get('personalidad', {}).get('tono', 'desconocido'),
        "spotify": "connected" if (spotify_client and spotify_client.is_authenticated) else "not_connected"
    })

# ====================================
# SPOTIFY OAUTH
# ====================================

@app.route('/spotify/auth', methods=['GET'])
def spotify_auth():
    """Redirige al usuario a Spotify para autorizar la app."""
    if not spotify_client:
        return jsonify({"error": "Spotify no está configurado. Agrega spotify.client_id y client_secret en config_agente.json"}), 400
    if spotify_client.is_authenticated:
        return '<h2>✅ Spotify ya está conectado!</h2><p>Puedes cerrar esta ventana.</p>'
    auth_url = spotify_client.get_auth_url()
    return f'<h2>🎵 Conectar Spotify</h2><p><a href="{auth_url}">Haz click aquí para autorizar Spotify</a></p>'

@app.route('/spotify/callback', methods=['GET'])
def spotify_callback():
    """Callback de Spotify OAuth."""
    if not spotify_client:
        return jsonify({"error": "Spotify no configurado"}), 400
    code = request.args.get('code')
    error = request.args.get('error')
    if error:
        return f'<h2>❌ Error de Spotify</h2><p>{error}</p>', 400
    if not code:
        return '<h2>❌ Falta el código de autorización</h2>', 400
    success = spotify_client.handle_callback(code)
    if success:
        return '<h2>✅ Spotify conectado exitosamente!</h2><p>Ya puedes pedirle a Raymundo que ponga música. Cierra esta ventana.</p>'
    return '<h2>❌ Error al conectar Spotify</h2><p>Intenta de nuevo.</p>', 500

@app.route('/spotify/status', methods=['GET'])
def spotify_status():
    """Estado de la conexión de Spotify."""
    if not spotify_client:
        return jsonify({"connected": False, "reason": "not_configured"})
    return jsonify({"connected": spotify_client.is_authenticated})

@app.route('/chat', methods=['POST'])
def chat():
    """
    Endpoint principal para recibir mensajes de WhatsApp
    
    Body: {
        "mensaje": "texto del mensaje",
        "user_id": "opcional - ID del usuario para mantener contexto"
    }
    
    Response: {
        "respuesta": "respuesta de Raymundo",
        "archivo": "ruta del archivo adjunto (opcional)",
        "tipo_archivo": "tipo de archivo: presentacion, documento, etc."
    }
    """
    try:
        # Obtener datos del request
        data = request.get_json()
        
        if not data or 'mensaje' not in data:
            return jsonify({
                "error": "Se requiere el campo 'mensaje'"
            }), 400
        
        mensaje = data['mensaje'].strip()
        user_id = data.get('user_id', 'default')  # ID del usuario (opcional)
        user_name = data.get('user_name', '').strip() or None  # Nombre del contacto WA
        image_base64 = data.get('image_base64')  # Imagen adjunta en base64 (opcional)
        media_mimetype = data.get('media_mimetype')  # MIME type del archivo adjunto

        # Guardar/actualizar nombre conocido del contacto
        if user_name and user_name != user_id:
            nombres_contactos[user_id] = user_name
        elif user_id in nombres_contactos:
            user_name = nombres_contactos[user_id]
        
        if not mensaje:
            return jsonify({
                "error": "El mensaje no puede estar vacío"
            }), 400
        
        logger.info(f"📩 Mensaje de {user_name or user_id} [{user_id}]: {mensaje[:50]}...")
        
        # Iniciar temporizador
        tiempo_inicio = time.time()
        
        # Comando especial: stats
        if mensaje.lower() in ['stats', 'estadisticas', 'estadísticas', 'estado']:
            return jsonify({
                "respuesta": metrics.get_stats_formatted(),
                "user_id": user_id
            })
        
        # Comandos de cambio de personalidad — ahora son PER-USER
        if mensaje.lower() in ['/puteado', '/putedo', '/rai']:
            set_tono_usuario(user_id, 'puteado')
            logger.info(f"🔄 {user_name or user_id} cambió a personalidad PUTEADO")
            return jsonify({
                "respuesta": "oke wey, haora soy rAI, un puto ke no se anda kon mamadas. ke chingaos kieres?",
                "user_id": user_id
            })
        
        if mensaje.lower() in ['/amigable', '/raymundo', '/ray', '/friendly']:
            set_tono_usuario(user_id, 'amigable')
            logger.info(f"🔄 {user_name or user_id} cambió a personalidad AMIGABLE")
            return jsonify({
                "respuesta": "¡Hola! Ahora estoy en modo amigable 😊 ¿En qué puedo ayudarte?",
                "user_id": user_id
            })
        
        # Comando para personalidad en inglés
        if mensaje.lower() in ['/english', '/en', '/inglés', '/ingles']:
            # Activar personalidad en inglés (usando configuración del JSON)
            personalidad_en = config_agente.get('personalidad_en', {})
            tono_actual = config_agente.get('personalidad', {}).get('tono', 'puteado')
            if tono_actual == 'puteado':
                prompt_en = personalidad_en.get('prompt_sistema_puteado', 'You are Ray, a helpful assistant.')
            else:
                prompt_en = personalidad_en.get('prompt_sistema_amigable', 'You are Ray, a friendly assistant.')
            
            # Guardar estado de idioma para este usuario
            if 'idioma_override' not in conversaciones:
                conversaciones['idioma_override'] = {}
            conversaciones['idioma_override'][user_id] = 'en'
            
            limpiar_historial(user_id)
            logger.info(f"🌐 {user_id} switched to ENGLISH personality")
            return jsonify({
                "respuesta": "ayo what's good nigga, Ray's in the building now 💪 I switched to English mode. whatchu need bruh?",
                "user_id": user_id
            })
        
        # Comando para volver a español
        if mensaje.lower() in ['/español', '/espanol', '/spanish', '/es']:
            if 'idioma_override' in conversaciones and user_id in conversaciones.get('idioma_override', {}):
                del conversaciones['idioma_override'][user_id]
            limpiar_historial(user_id)
            logger.info(f"🌐 {user_id} volvió a personalidad en ESPAÑOL")
            return jsonify({
                "respuesta": "orale wey, ya volvi al español ke pedo, ke kieres?",
                "user_id": user_id
            })
        
        # Comando especial: rate limit info
        if mensaje.lower() in ['rate limit', 'ratelimit', 'limite', 'límite', '429']:
            info_rate = """⚠️ **RATE LIMIT ALCANZADO**

Has superado los límites del Free Tier de GitHub Models:

📊 **Límites:**
• 15 RPM (Requests por minuto)
• 150 RPD (Requests por día)
• 150K TPM (Tokens por minuto)

🔄 **No te preocupes:**
Raymundo cambió automáticamente a **Ollama (local)** y seguirá funcionando sin interrupciones.

⏰ **Reinicio de límites:**
• RPM: Cada minuto
• RPD: A las 00:00 UTC

💡 **Tip:** Escribe `/raymundo stats` para ver tu uso actual.
"""
            return jsonify({
                "respuesta": info_rate,
                "user_id": user_id
            })
        
        # Limpiar prefijo de comando para detección de intenciones
        mensaje_limpio = mensaje
        for cmd in ['/raymundo', '/rai', '/puteado', '/amigable', '/friendly', '/ray', '/putedo']:
            if mensaje_limpio.lower().startswith(cmd):
                mensaje_limpio = mensaje_limpio[len(cmd):].strip()
                break

        # Detectar cambio de personalidad en lenguaje natural
        cambio_natural = detectar_cambio_personalidad_natural(mensaje_limpio)
        if cambio_natural:
            set_tono_usuario(user_id, cambio_natural)
            logger.info(f"🔄 {user_name or user_id} cambió a {cambio_natural} (lenguaje natural)")

        logger.info(f"📩 [{user_name or user_id}] {mensaje_limpio[:60]}...")

        # Detectar si el usuario está siendo agresivo en ESTE mensaje (no persistente)
        usuario_agresivo = detectar_agresividad_usuario(mensaje_limpio)

        # ─── SPOTIFY: comandos rápidos de reproducción ────────────
        spotify_result = _handle_spotify_command(mensaje_limpio)
        if spotify_result:
            tiempo_respuesta = time.time() - tiempo_inicio
            logger.info(f"🎵 Spotify comando directo ({tiempo_respuesta:.2f}s)")
            agregar_mensaje(user_id, "user", mensaje_limpio)
            agregar_mensaje(user_id, "assistant", spotify_result)
            return jsonify({"respuesta": spotify_result, "user_id": user_id})

        # ─── MEDIA ADJUNTA: extraer texto (imagen o PDF) ─────────
        texto_imagen_extraido = None
        if image_base64:
            tipo_media = media_mimetype or 'desconocido'
            logger.info(f"📎 [{user_name or user_id}] Media adjunta recibida ({tipo_media}), extrayendo texto...")
            try:
                texto_imagen_extraido = gestor.vision.extract_text_from_base64(image_base64, mimetype=media_mimetype)
                if texto_imagen_extraido and not texto_imagen_extraido.startswith("❌"):
                    logger.info(f"📝 Texto extraído de imagen: {len(texto_imagen_extraido)} chars")
                    mensaje_limpio = (
                        f"{mensaje_limpio}\n\n"
                        f"[CONTENIDO EXTRAÍDO DE LA IMAGEN ADJUNTA]:\n"
                        f"{texto_imagen_extraido}"
                    )
                    # Guardar documento en la base de conocimiento
                    is_pdf = media_mimetype and 'pdf' in media_mimetype.lower()
                    doc_type = 'cv' if is_pdf else 'image'
                    try:
                        doc_id = knowledge_base.store_document(
                            user_id=user_id,
                            doc_type=doc_type,
                            content=texto_imagen_extraido,
                            title=f"{'PDF' if is_pdf else 'Imagen'} de {user_name or user_id}",
                            source="whatsapp",
                        )
                        logger.info(f"💾 Imagen guardada en KB (doc_id={doc_id})")
                    except Exception as ke:
                        logger.warning(f"⚠️ No se pudo guardar imagen en KB: {ke}")
                else:
                    logger.warning(f"⚠️ No se pudo extraer texto de la imagen: {texto_imagen_extraido}")
            except Exception as e:
                logger.error(f"❌ Error extrayendo texto de imagen: {e}")

        # ─── RUTA AGÉNTICA: metas complejas van al AgentLoop ──────
        if es_meta_compleja(mensaje_limpio):
            logger.info(f"🧠 [{user_name or user_id}] Meta compleja detectada → AgentLoop")
            try:
                # Obtener contexto de conversación previo para el agente
                conv_context = get_contexto_completo(user_id)
                # Buscar conocimiento relevante en la KB
                kb_context = knowledge_base.build_knowledge_context(query=mensaje_limpio)
                resultado_agente = agent_loop.run(
                    goal=mensaje_limpio,
                    user_name=user_name,
                    user_id=user_id,
                    tono_override=get_tono_usuario(user_id),
                    usuario_agresivo=usuario_agresivo,
                    conversation_history=conv_context,
                    knowledge_context=kb_context,
                )
                respuesta = resultado_agente["response"]
                tiempo_respuesta = time.time() - tiempo_inicio

                # Guardar en BD persistente
                agregar_mensaje(user_id, "user", mensaje_limpio)
                agregar_mensaje(user_id, "assistant", respuesta)

                # Extraer y guardar datos de personas mencionadas
                _extraer_y_guardar_conocimiento(mensaje_limpio, respuesta, user_id)

                # Rastrear métricas
                tokens_groq = groq.last_tokens_used if groq and groq.client else 0
                tokens_gpt4o = github.last_tokens_used
                tokens_ollama = ollama.last_tokens_used
                modelo = "groq" if tokens_groq > 0 else "gpt4o" if tokens_gpt4o > 0 else "ollama"
                metrics.track_request(
                    tipo="agent_loop",
                    tokens_used=tokens_groq or tokens_gpt4o or tokens_ollama,
                    modelo=modelo,
                    tiempo_respuesta=tiempo_respuesta,
                    user_id=user_id,
                )

                logger.info(
                    f"✅ AgentLoop completado — {resultado_agente['steps_taken']} pasos, "
                    f"{len(respuesta)} chars, {tiempo_respuesta:.2f}s"
                )
                return jsonify({
                    "respuesta": respuesta,
                    "user_id": user_id,
                    "agentic": True,
                    "steps": resultado_agente["steps_taken"],
                    "run_id": resultado_agente["run_id"],
                })
            except Exception as e:
                logger.error(f"❌ Error en AgentLoop: {e}")
                # Fallback al flujo clásico si el loop falla
                logger.info("🔄 Fallback al flujo clásico...")

        # ─── RUTA CLÁSICA: chat directo o herramientas simples ────
        # Procesar mensaje (detectar intención, aprender vocabulario internamente)
        resultado_herramienta = gestor.procesar_mensaje(
            mensaje_limpio,
            user_name=user_name,
            user_id=user_id,
            tono_override=get_tono_usuario(user_id),
            usuario_agresivo=usuario_agresivo,
        )
        
        if resultado_herramienta['ejecuto_herramienta']:
            respuesta = resultado_herramienta['resultado']
            archivo_info = resultado_herramienta.get('archivo')
            
            # Si hay un archivo adjunto, exportarlo
            archivo_path = None
            if archivo_info and isinstance(archivo_info, dict):
                try:
                    tipo = archivo_info.get('tipo')
                    titulo_limpio = generar_nombre_archivo(archivo_info.get('titulo', 'archivo'))
                    
                    if tipo == 'presentacion':
                        presentation_id = archivo_info['presentation_id']
                        archivo_path = str((OUTPUT_DIR / f"{titulo_limpio}.pptx").resolve())
                        logger.info(f"📥 Exportando presentación: {presentation_id}")
                        result = google.exportar_presentacion_pptx(presentation_id, archivo_path)
                        
                    elif tipo == 'documento':
                        document_id = archivo_info['document_id']
                        archivo_path = str((OUTPUT_DIR / f"{titulo_limpio}.docx").resolve())
                        logger.info(f"📥 Exportando documento: {document_id}")
                        result = google.exportar_documento_docx(document_id, archivo_path)
                        
                    elif tipo == 'hoja_calculo':
                        spreadsheet_id = archivo_info['spreadsheet_id']
                        archivo_path = str((OUTPUT_DIR / f"{titulo_limpio}.xlsx").resolve())
                        logger.info(f"📥 Exportando hoja de cálculo: {spreadsheet_id}")
                        result = google.exportar_hoja_calculo_xlsx(spreadsheet_id, archivo_path)
                    
                    if not result:
                        archivo_path = None
                        respuesta += "\n\n⚠️  No pude exportar el archivo, pero puedes acceder desde el link."
                    
                except Exception as e:
                    logger.error(f"❌ Error exportando archivo: {e}")
                    archivo_path = None
                    respuesta += "\n\n⚠️  Error al generar archivo."
            
            # Calcular tiempo de respuesta
            tiempo_respuesta = time.time() - tiempo_inicio
            
            # Rastrear métricas (tokens del último modelo usado)
            tokens_ollama = ollama.last_tokens_used
            tokens_gpt4o = github.last_tokens_used
            tokens_groq = groq.last_tokens_used if groq and groq.client else 0
            
            # Determinar qué modelo se usó (prioridad: Groq > GPT-4o > Ollama)
            if tokens_groq > 0:
                metrics.track_request(
                    tipo=archivo_info.get('tipo', 'chat') if archivo_info else 'chat',
                    tokens_used=tokens_groq,
                    modelo='groq',
                    tiempo_respuesta=tiempo_respuesta,
                    user_id=user_id
                )
            elif tokens_gpt4o > 0:
                metrics.track_request(
                    tipo=archivo_info.get('tipo', 'chat') if archivo_info else 'chat',
                    tokens_used=tokens_gpt4o,
                    modelo='gpt4o',
                    tiempo_respuesta=tiempo_respuesta,
                    user_id=user_id
                )
            elif tokens_ollama > 0:
                metrics.track_request(
                    tipo='chat',
                    tokens_used=tokens_ollama,
                    modelo='ollama',
                    tiempo_respuesta=tiempo_respuesta,
                    user_id=user_id
                )
            else:
                # Sin tokens detectados, solo rastrear request
                metrics.track_request(
                    tipo='chat',
                    tokens_used=0,
                    modelo='unknown',
                    tiempo_respuesta=tiempo_respuesta,
                    user_id=user_id
                )
            
            logger.info(f"✅ Respuesta generada ({len(respuesta)} caracteres)")
            logger.info(f"   • Tiempo: {tiempo_respuesta:.2f}s | Groq: {tokens_groq} | GPT-4o: {tokens_gpt4o} | Ollama: {tokens_ollama}")
            
            # Guardar en BD persistente
            agregar_mensaje(user_id, "user", mensaje_limpio)
            agregar_mensaje(user_id, "assistant", respuesta)

            # Extraer y guardar datos de personas mencionadas
            _extraer_y_guardar_conocimiento(mensaje_limpio, respuesta, user_id)

            # Preparar respuesta JSON limpia
            response_data = {
                "respuesta": respuesta,
                "user_id": user_id
            }
            
            # Solo agregar campos de archivo si existen
            if archivo_path:
                response_data["archivo"] = archivo_path
                response_data["tipo_archivo"] = archivo_info.get('tipo') if archivo_info else None
            
            return jsonify(response_data)
        else:
            # Usar chat híbrido normal con soporte bilingüe
            idioma_override = conversaciones.get('idioma_override', {}).get(user_id)
            # Obtener historial completo (resúmenes + mensajes recientes)
            conv_context = get_contexto_completo(user_id)
            # Buscar conocimiento relevante en la KB
            kb_context = knowledge_base.build_knowledge_context(query=mensaje_limpio)
            respuesta = gestor.chat_hibrido(
                mensaje,
                idioma_override=idioma_override,
                user_name=user_name,
                user_id=user_id,
                tono_override=get_tono_usuario(user_id),
                usuario_agresivo=usuario_agresivo,
                history=conv_context,
                knowledge_context=kb_context,
            )
            
            # Calcular tiempo de respuesta
            tiempo_respuesta = time.time() - tiempo_inicio
            
            # Rastrear métricas
            tokens_ollama = ollama.last_tokens_used
            tokens_gpt4o = github.last_tokens_used
            tokens_groq = groq.last_tokens_used if groq and groq.client else 0
            
            if tokens_groq > 0:
                metrics.track_request(
                    tipo='chat',
                    tokens_used=tokens_groq,
                    modelo='groq',
                    tiempo_respuesta=tiempo_respuesta,
                    user_id=user_id
                )
            elif tokens_gpt4o > 0:
                metrics.track_request(
                    tipo='chat',
                    tokens_used=tokens_gpt4o,
                    modelo='gpt4o',
                    tiempo_respuesta=tiempo_respuesta,
                    user_id=user_id
                )
            elif tokens_ollama > 0:
                metrics.track_request(
                    tipo='chat',
                    tokens_used=tokens_ollama,
                    modelo='ollama',
                    tiempo_respuesta=tiempo_respuesta,
                    user_id=user_id
                )
            
            logger.info(f"✅ Respuesta generada ({len(respuesta)} caracteres)")
            logger.info(f"   • Tiempo: {tiempo_respuesta:.2f}s | Groq: {tokens_groq} | GPT-4o: {tokens_gpt4o} | Ollama: {tokens_ollama}")
            
            # Guardar en BD persistente
            agregar_mensaje(user_id, "user", mensaje_limpio)
            agregar_mensaje(user_id, "assistant", respuesta)

            # Extraer y guardar datos de personas mencionadas
            _extraer_y_guardar_conocimiento(mensaje_limpio, respuesta, user_id)

            return jsonify({
                "respuesta": respuesta,
                "user_id": user_id
            })
        
    except Exception as e:
        logger.error(f"❌ Error procesando mensaje: {e}")
        metrics.track_error()
        return jsonify({
            "error": "Error interno del servidor",
            "details": str(e)
        }), 500

@app.route('/clear_history/<user_id>', methods=['DELETE'])
def clear_history(user_id):
    """Limpia el historial de conversación de un usuario"""
    try:
        limpiar_historial(user_id)
        logger.info(f"🗑️  Historial de {user_id} eliminado")
        return jsonify({
            "message": f"Historial de {user_id} eliminado"
        })
    except Exception as e:
        logger.error(f"❌ Error limpiando historial: {e}")
        return jsonify({
            "error": str(e)
        }), 500

# ====================================
# ENDPOINTS AGÉNTICOS
# ====================================

@app.route('/agent/approve/<request_id>', methods=['POST'])
def approve_action(request_id):
    """Aprueba una acción pendiente del agente."""
    if approval_manager.approve(request_id):
        return jsonify({"status": "approved", "request_id": request_id})
    return jsonify({"error": "Solicitud no encontrada o ya resuelta"}), 404

@app.route('/agent/deny/<request_id>', methods=['POST'])
def deny_action(request_id):
    """Rechaza una acción pendiente del agente."""
    if approval_manager.deny(request_id):
        return jsonify({"status": "denied", "request_id": request_id})
    return jsonify({"error": "Solicitud no encontrada o ya resuelta"}), 404

@app.route('/agent/pending', methods=['GET'])
def pending_approvals():
    """Lista solicitudes de aprobación pendientes."""
    pending = approval_manager.get_pending()
    return jsonify({
        "pending": [
            {
                "id": r.id,
                "action": r.action,
                "args": r.args,
                "reason": r.reason,
                "created_at": r.created_at,
            }
            for r in pending
        ]
    })

@app.route('/agent/logs', methods=['GET'])
def agent_logs():
    """Devuelve los últimos logs del agente."""
    n = request.args.get('n', 20, type=int)
    return jsonify({"logs": agent_logger.get_last_runs(n)})

@app.route('/stats', methods=['GET'])
def stats():
    """ Estadísticas del servidor con tracking de tokens"""
    formato = request.args.get('format', 'json')  # json o text
    
    if formato == 'text':
        # Formato para WhatsApp
        return metrics.get_stats_formatted(), 200, {'Content-Type': 'text/plain; charset=utf-8'}
    else:
        # Formato JSON
        stats_data = metrics.get_stats()
        stats_data['conversaciones'] = {
            "tipo_almacenamiento": "SQLite persistente",
            "db_path": str(conversation_db._db_path),
        }
        return jsonify(stats_data)
@app.route('/metrics/reset', methods=['POST'])
def reset_metrics():
    """Reinicia todas las métricas de tracking"""
    try:
        metrics.reset_metrics()
        logger.info("🔄 Métricas reiniciadas")
        return jsonify({
            "message": "Métricas reiniciadas exitosamente",
            "nuevo_inicio": metrics.metrics['inicio']
        })
    except Exception as e:
        logger.error(f"❌ Error reiniciando métricas: {e}")
        return jsonify({
            "error": str(e)
        }), 500

# ====================================
# ENDPOINTS DE AUDIO
# ====================================

@app.route('/audio/stt', methods=['POST'])
def speech_to_text():
    """
    Endpoint para convertir audio a texto (Speech-to-Text)
    
    Body: Archivo de audio (multipart/form-data)
    
    Response: {
        "texto": "texto transcrito del audio",
        "user_id": "ID del usuario"
    }
    """
    try:
        if 'audio' not in request.files:
            return jsonify({
                "error": "Se requiere un archivo de audio"
            }), 400
        
        audio_file = request.files['audio']
        user_id = request.form.get('user_id', 'default')
        
        # Guardar archivo temporalmente
        import tempfile
        import os
        
        temp_path = os.path.join(tempfile.gettempdir(), f"audio_{user_id}_{int(time.time())}.ogg")
        audio_file.save(temp_path)
        
        logger.info(f"🎙️ Procesando audio de {user_id}")
        
        # Transcribir audio
        texto = audio_handler.speech_to_text(temp_path)
        
        # Limpiar archivo temporal
        try:
            os.remove(temp_path)
        except:
            pass
        
        if not texto:
            return jsonify({
                "error": "No se pudo transcribir el audio"
            }), 500
        
        logger.info(f"✅ Audio transcrito: {texto[:50]}...")
        
        return jsonify({
            "texto": texto,
            "user_id": user_id
        })
    
    except Exception as e:
        logger.error(f"❌ Error en STT: {e}")
        return jsonify({
            "error": f"Error procesando audio: {str(e)}"
        }), 500

@app.route('/audio/tts', methods=['POST'])
def text_to_speech():
    """
    Endpoint para convertir texto a audio (Text-to-Speech)
    
    Body: {
        "texto": "texto a convertir",
        "user_id": "opcional - ID del usuario"
    }
    
    Response: Archivo de audio WAV
    """
    try:
        data = request.get_json()
        
        if not data or 'texto' not in data:
            return jsonify({
                "error": "Se requiere el campo 'texto'"
            }), 400
        
        texto = data['texto'].strip()
        user_id = data.get('user_id', 'default')
        
        if not texto:
            return jsonify({
                "error": "El texto no puede estar vacío"
            }), 400
        
        logger.info(f"🔊 Generando audio para {user_id}: {texto[:50]}...")
        
        # Limpiar texto (quitar emojis y caracteres especiales, preservar apostrofes para slangs)
        texto_limpio = ''.join(c for c in texto if c.isalnum() or c.isspace() or c in ".,;:¿?¡!-'\"")
        
        # Limitar longitud
        if len(texto_limpio) > 500:
            texto_limpio = texto_limpio[:500] + "..."
        
        # Detectar idioma del texto para usar la voz correcta
        tts_idioma = conversaciones.get('idioma_override', {}).get(user_id) or detector_idioma.detectar(texto_limpio)
        
        # Generar audio
        audio_path = audio_handler.text_to_speech(texto_limpio, language=tts_idioma)
        
        if not audio_path:
            return jsonify({
                "error": "No se pudo generar el audio"
            }), 500
        
        logger.info(f"✅ Audio generado: {audio_path}")
        
        # Detectar tipo MIME basado en extensión
        import mimetypes
        mime_type = mimetypes.guess_type(audio_path)[0] or 'audio/wav'
        file_ext = audio_path.split('.')[-1]
        
        # Enviar archivo
        from flask import send_file
        return send_file(
            audio_path,
            mimetype=mime_type,
            as_attachment=True,
            download_name=f'respuesta_{user_id}.{file_ext}'
        )
    
    except Exception as e:
        logger.error(f"❌ Error en TTS: {e}")
        return jsonify({
            "error": f"Error generando audio: {str(e)}"
        }), 500

@app.route('/audio/chat', methods=['POST'])
def audio_chat():
    """
    Endpoint para chat con audio (recibe audio, responde con audio)
    
    Body: Archivo de audio (multipart/form-data)
    
    Response: Archivo de audio WAV con la respuesta
    """
    try:
        if 'audio' not in request.files:
            return jsonify({
                "error": "Se requiere un archivo de audio"
            }), 400
        
        audio_file = request.files['audio']
        user_id = request.form.get('user_id', 'default')
        
        # Guardar archivo temporalmente
        import tempfile
        import os
        
        temp_path = os.path.join(tempfile.gettempdir(), f"audio_{user_id}_{int(time.time())}.ogg")
        audio_file.save(temp_path)
        
        logger.info(f"🎙️ Chat de audio de {user_id}")
        
        # 1. Transcribir audio a texto
        texto = audio_handler.speech_to_text(temp_path)
        
        # Limpiar archivo temporal
        try:
            os.remove(temp_path)
        except:
            pass
        
        if not texto:
            return jsonify({
                "error": "No se pudo transcribir el audio"
            }), 500
        
        logger.info(f"📝 Texto: {texto[:50]}...")
        
        # 2. Procesar mensaje con Raymundo
        resultado_herramienta = gestor.procesar_mensaje(texto)
        
        if resultado_herramienta['ejecuto_herramienta']:
            respuesta = resultado_herramienta['resultado']
        else:
            # Chat normal with bilingual routing — usar historial persistente
            conv_context = get_contexto_completo(user_id)
            
            # Detectar idioma para seleccionar prompt
            idioma_override = conversaciones.get('idioma_override', {}).get(user_id)
            idioma = idioma_override or detector_idioma.detectar(texto)
            
            if idioma == 'en':
                personalidad_en = config_agente.get('personalidad_en', {})
                tono = config_agente.get('personalidad', {}).get('tono', 'puteado')
                if tono == 'puteado':
                    prompt_sistema = personalidad_en.get('prompt_sistema_puteado', 'You are Ray.')
                else:
                    prompt_sistema = personalidad_en.get('prompt_sistema_amigable', 'You are Ray.')
            else:
                prompt_sistema = config_agente.get('personalidad', {}).get('prompt_sistema', '')
            
            messages = [{"role": "system", "content": prompt_sistema}]
            messages.extend(conv_context)
            messages.append({"role": "user", "content": texto})
            
            respuesta_ai = groq.chat(messages) or github.chat(messages) or ollama.generate(prompt_sistema + "\n\n" + texto)
            respuesta = respuesta_ai or "No pude generar una respuesta"
            
            agregar_mensaje(user_id, "user", texto)
            agregar_mensaje(user_id, "assistant", respuesta)
        
        logger.info(f"💬 Respuesta: {respuesta[:50]}...")
        
        # 3. Convertir respuesta a audio (preservar slangs y apostrofes)
        texto_limpio = ''.join(c for c in respuesta if c.isalnum() or c.isspace() or c in ".,;:¿?¡!-'\"")
        
        if len(texto_limpio) > 500:
            texto_limpio = texto_limpio[:500] + "..."
        
        # Detectar idioma para usar la voz correcta en TTS
        tts_idioma = conversaciones.get('idioma_override', {}).get(user_id) or detector_idioma.detectar(respuesta)
        audio_path = audio_handler.text_to_speech(texto_limpio, language=tts_idioma)
        
        if not audio_path:
            return jsonify({
                "error": "No se pudo generar el audio de respuesta"
            }), 500
        
        logger.info(f"✅ Audio de respuesta generado")
        
        # Detectar tipo MIME basado en extensión
        import mimetypes
        mime_type = mimetypes.guess_type(audio_path)[0] or 'audio/wav'
        file_ext = audio_path.split('.')[-1]
        
        # 4. Enviar audio de respuesta
        from flask import send_file
        return send_file(
            audio_path,
            mimetype=mime_type,
            as_attachment=True,
            download_name=f'respuesta_{user_id}.{file_ext}'
        )
    
    except Exception as e:
        logger.error(f"❌ Error en chat de audio: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": f"Error en chat de audio: {str(e)}"
        }), 500

@app.route('/audio/status', methods=['GET'])
def audio_status():
    """Retorna el estado del sistema de audio"""
    status = audio_handler.get_status()
    return jsonify(status)

# ====================================
# MANEJO DE ERRORES
# ====================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint no encontrado",
        "available_endpoints": ["/chat", "/health", "/stats", "/clear_history/<user_id>"]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Error interno: {error}")
    return jsonify({
        "error": "Error interno del servidor"
    }), 500

# ====================================
# INICIAR SERVIDOR
# ====================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("  🚀 rAImundoGPT WhatsApp Server")
    print("="*70)
    print(f"\n📡 Servidor iniciando en http://localhost:5000")
    print(f"🤖 Agente: {config_agente.get('personalidad', {}).get('nombre', 'Raymundo')}")
    print(f"🎭 Tono: {config_agente.get('personalidad', {}).get('tono', 'desconocido')}")
    print(f"\n💡 Endpoints disponibles:")
    print(f"   • POST http://localhost:5000/chat")
    print(f"   • GET  http://localhost:5000/health")
    print(f"   • GET  http://localhost:5000/stats")
    print(f"   • DEL  http://localhost:5000/clear_history/<user_id>")
    print(f"   • GET  http://localhost:5000/spotify/auth")
    print(f"   • GET  http://localhost:5000/spotify/status")
    print(f"\n⏹️  Presiona Ctrl+C para detener\n")
    print("="*70 + "\n")
    
    # Iniciar servidor
    app.run(
        host='0.0.0.0',  # Accesible desde cualquier IP
        port=5000,
        debug=False,  # Cambiar a True para debugging
        threaded=True  # Soportar múltiples requests simultáneos
    )
