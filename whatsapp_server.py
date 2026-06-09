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
import sys
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"

# Cargar variables de entorno — prioridad: config/.env, fallback raíz
_dotenv_path = CONFIG_DIR / ".env"
if _dotenv_path.exists():
    load_dotenv(dotenv_path=_dotenv_path)
else:
    load_dotenv()

os.environ.pop("GITHUB_TOKEN", None)
os.environ.pop("GH_TOKEN", None)
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"


def limpiar_formato_markdown(texto: str) -> str:
    """Elimina formato markdown de las respuestas para que suenen naturales en WhatsApp."""
    if not texto:
        return texto
    # Quitar prefijo "Raymundo:" o "rAI:" que el modelo a veces agrega
    texto = re.sub(r'^(?:Raymundo|rAI)\s*:\s*', '', texto)
    # Quitar negritas **texto** o __texto__
    texto = re.sub(r'\*\*(.+?)\*\*', r'\1', texto)
    texto = re.sub(r'__(.+?)__', r'\1', texto)
    # Quitar cursivas *texto* o _texto_ (solo si no es un emoticon como *-*)
    texto = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'\1', texto)
    # Quitar encabezados ### texto → texto
    texto = re.sub(r'^#{1,6}\s*', '', texto, flags=re.MULTILINE)
    # Quitar viñetas de lista "- item" al inicio de línea → "item"
    texto = re.sub(r'^[\-\•]\s+', '', texto, flags=re.MULTILINE)
    # Quitar bloques de código ```
    texto = re.sub(r'```[\s\S]*?```', lambda m: m.group(0).replace('```', ''), texto)
    # Quitar backticks inline `texto`
    texto = re.sub(r'`([^`]+?)`', r'\1', texto)
    # Quitar disclaimers comunes que el modelo mete
    texto = re.sub(
        r'\n*\*?(?:Nota|Aclaración|Disclaimer|Advertencia|Importante|Recuerda)\*?:\s*'
        r'(?:Esto es solo|Este es solo|Esto no es|Recuerda que|Si necesitas|Ten en cuenta).*$',
        '', texto, flags=re.IGNORECASE | re.MULTILINE
    )
    # Quitar secciones de disculpa/disclaimer sutiles
    texto = re.sub(
        r'\n*(?:—|---)\s*\n.*(?:no comparto|cambiar de tema|algo más|ayudarte).*$',
        '', texto, flags=re.IGNORECASE | re.DOTALL
    )
    return texto.strip()

# Crear directorios si no existen
for directory in (CONFIG_DIR, DATA_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

CREDENTIALS_FILE = BASE_DIR / 'resources' / 'data' / 'google-credentials.json'
METRICS_FILE = DATA_DIR / 'metrics.json'

# Importar componentes desde core/
from core.ai_clients import OllamaClient, MistralClient, GroqClient
from core.tools import GestorHerramientas
from core.detectors import DetectorIdioma

from core.google_workspace_client import GoogleWorkspaceClient
from core.metrics_tracker import MetricsTracker
from core.audio_handler import get_audio_handler
from core.adapters import build_registry
from core.agent_loop import AgentLoop
from core.agent_logger import AgentLogger
from core.agent_memory import VectorMemory
from core.approval import approval_manager
from core.conversation_db import ConversationDB
from core.knowledge_db import KnowledgeBase
from core.spotify_client import SpotifyClient, detect_spotify_intent
from core.context_manager import ContextManager
from core.agent_runtime import AgentRuntime, AgentRequest

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


def construir_adjunto_local(path_archivo, tipo=None, title=None):
    """Normaliza un archivo local para respuesta JSON de WhatsApp."""
    if not path_archivo:
        return None
    try:
        resolved_path = Path(str(path_archivo)).resolve()
    except Exception:
        return None
    if not resolved_path.exists() or not resolved_path.is_file():
        return None
    return {
        "path": str(resolved_path),
        "filename": resolved_path.name,
        "tipo": tipo or resolved_path.suffix.lstrip('.') or 'archivo',
        "title": title or resolved_path.stem,
    }


def normalizar_adjuntos_locales(artifacts):
    """Filtra y deduplica adjuntos locales reales para enviar por WhatsApp."""
    normalized = []
    seen_paths = set()

    for artifact in artifacts or []:
        if isinstance(artifact, dict):
            entry = construir_adjunto_local(
                artifact.get('path'),
                tipo=artifact.get('tipo'),
                title=artifact.get('title') or artifact.get('filename'),
            )
        else:
            entry = construir_adjunto_local(artifact)

        if entry and entry['path'] not in seen_paths:
            normalized.append(entry)
            seen_paths.add(entry['path'])

    return normalized


def agregar_adjuntos_respuesta(response_data, archivos):
    if not archivos:
        return response_data
    response_data['archivos'] = archivos
    response_data['archivo'] = archivos[0]['path']
    response_data['tipo_archivo'] = archivos[0]['tipo']
    return response_data

try:
    # Cargar configuración desde JSON
    with open('config_agente.json', 'r', encoding='utf-8') as f:
        config_agente = json.load(f)
    logger.info("✅ Configuración cargada")

    # Detectar modo de personalidad — leer desde core.config que ya procesó el env var
    from core.config import _PERSONALITY_MODE as _PM_STARTUP, PERSONALITY_FILE as _PF_STARTUP
    logger.info("=" * 60)
    logger.info(f"  PERSONALITY_MODE env  : {os.environ.get('PERSONALITY_MODE', '(no seteado — default raymundo)')}")
    logger.info(f"  _PERSONALITY_MODE     : {_PM_STARTUP}")
    logger.info(f"  Archivo de personalidad: {_PF_STARTUP}")
    logger.info(f"  Archivo existe        : {_PF_STARTUP.exists()}")
    logger.info("=" * 60)
    
    # Inicializar clientes AI
    ollama = OllamaClient()
    mistral = MistralClient()
    groq = GroqClient()  # Nuevo: Groq (14,400 RPD gratis)
    google = GoogleWorkspaceClient(str(CREDENTIALS_FILE))
    
    # Crear gestor de herramientas con Groq
    gestor = GestorHerramientas(ollama, mistral, google, groq=groq)
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

    # Inicializar FaceManager — reconocimiento facial (opcional)
    face_manager = None
    try:
        from core.face_recognition import FaceManager
        deepface_config = config_agente.get("deepface", {})
        face_manager = FaceManager(config=deepface_config, knowledge_base=knowledge_base)
        if face_manager.available:
            gestor.face_manager = face_manager
            logger.info("✅ FaceManager inicializado (reconocimiento facial activo)")
        else:
            logger.info("⚠️ FaceManager creado pero modelos no disponibles")
    except Exception as fe:
        logger.warning(f"⚠️ No se pudo inicializar FaceManager: {fe}")

    # Inicializar DeepFace Worker (Python 3.12 subprocess) — análisis completo (edad/género/emoción/raza)
    # Se inicia lazy: el worker arranca en la primera solicitud de análisis facial
    deepface_worker = None
    try:
        from core.deepface_stream import _DeepFaceWorkerProxy
        deepface_worker = _DeepFaceWorkerProxy()
        if deepface_worker.available:
            logger.info("✅ DeepFace worker disponible (inicio lazy al primer análisis facial)")
        else:
            logger.info("⚠️ DeepFace worker no disponible (Python 3.12 no encontrado)")
            deepface_worker = None
    except Exception as dfe:
        logger.warning(f"⚠️ No se pudo crear DeepFace worker: {dfe}")

    adapter_registry = build_registry(gestor, knowledge_base=knowledge_base, spotify_client=spotify_client, face_manager=face_manager)

    from core.ai_clients import make_ai_chat_fn, GitHubCopilotClient as _CopilotCls
    _copilot_wa = _CopilotCls(model="gpt-4o-mini")  # rápido para el loop; sin RPM limit
    _ai_chat_for_agent = make_ai_chat_fn(
        groq_client=groq,
        mistral_client=mistral,
        ollama_client=ollama,
        copilot_client=_copilot_wa,
        copilot_model="gpt-4o-mini",
        compress=True,
        compress_max_chars=10000,
        filter_rejections=True,
    )

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

    # Inicializar ContextManager centralizado
    context_manager = ContextManager(
        knowledge_base=knowledge_base,
        memory_system=gestor.memory,
    )
    logger.info("✅ ContextManager inicializado (RAG + context injection)")
    
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

agent_runtime = AgentRuntime(
    gestor=gestor,
    agent_loop=agent_loop,
    conversation_db=conversation_db,
    knowledge_base=knowledge_base,
    context_manager=context_manager,
)
logger.info("✅ AgentRuntime inicializado para WhatsApp")

# Dict en RAM solo para cosas efímeras (idioma override por sesión)
conversaciones = {}  # Solo para idioma_override

# Personalidad y nombre por usuario (override independiente por sesión)
personalidades_por_usuario = {}

# Nombres de contacto conocidos
nombres_contactos = {}

# ── Wizard de Planeación Didáctica (sesión independiente por usuario) ──────────
from core.planeacion_wizard import PlaneacionWizard
_planeacion_wizards: dict = {}

def _ai_fn_planeacion(prompt: str) -> str:
    """Llamada al LLM con tokens extra para generación del plan."""
    try:
        return gestor._consultar_ia(prompt, temperature=0.7, max_tokens=16000) or ""
    except Exception:
        return ""


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
    # En modo rAI y prepa, el MD define el tono — ignorar overrides por usuario
    from core.config import _PERSONALITY_MODE
    if _PERSONALITY_MODE in ("rai", "prepa"):
        return None
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

def _generar_respuesta_facial_template(face_text: str, nombre: str, tono: str | None) -> str:
    """
    Genera una respuesta hilarante sobre el análisis facial SIN llamar a ningún LLM.
    Fallback de último recurso cuando Groq/Mistral/Ollama no responden.
    """
    import random
    # Extraer datos del face_text (formato: "Edad: ~26 años, Género: Hombre, Emoción: neutral, Raza/Etnia: latino/hispano")
    edad = ""
    genero = ""
    emocion = ""
    raza = ""
    for part in face_text.split(","):
        p = part.strip()
        if "Edad" in p:
            edad = p.replace("Edad:", "").strip().replace("~", "").replace(" años", "")
        elif "Género" in p or "Genero" in p:
            genero = p.split(":")[-1].strip()
        elif "Emoción" in p or "Emocion" in p:
            emocion = p.split(":")[-1].strip()
        elif "Raza" in p or "Etnia" in p:
            raza = p.split(":")[-1].strip()

    _EMOCION_BURLA = {
        "neutral": ["cara de que te vale todo", "cara de 'no me importa nada' nivel pro",
                    "expresión de funcionario del IMSS"],
        "feliz": ["sonrisa tipo comercial de detergente", "cara de que ganaste 20 pesos en la lotería"],
        "triste": ["cara de bolero de los años 50", "expresión de perrito mojado"],
        "enojado/a": ["cara de que le cortaron el wifi", "mirada de jefe de oficina los lunes"],
        "sorprendido/a": ["cara de que le dijeron el precio del dólar", "expresión de abuelita en TikTok"],
        "disgustado/a": ["cara de que olió el Metro a las 8am", "expresión de que probó el agua del garrafón"],
        "asustado/a": ["cara de que llegó la cuenta del CFE", "expresión de tamal en microondas"],
    }
    burla_emo = random.choice(_EMOCION_BURLA.get(emocion.lower(), ["cara de 'me vale madre'"]))

    from core.config import _get_mode
    modo = _get_mode()

    if modo == "rai" or tono == "puteado":
        plantillas = [
            f"Wey, la IA dice que tienes {edad} años, eres {genero} y traes {burla_emo}. No te la creo, pareces más viejo pendejo.",
            f"Nmms, {edad} años con {burla_emo}. Y de raza {raza}. Eso explica muchas cosas que prefiero no decir.",
            f"Te detectaron {edad} años, {burla_emo}, y {raza}. Buen trabajo DNA, la verdad.",
        ]
    else:
        plantillas = [
            f"Órale, la IA dice que tienes unos {edad} años, eres {genero} y traes {burla_emo}. Yo no dije nada, fue el algoritmo.",
            f"Chido, {edad} años con {burla_emo}. Y lo de la raza {raza}... eso ya es tu herencia cultural, no te quejo.",
            f"El análisis dice: {edad} años, {genero}, {burla_emo}. Qué le dices a la ciencia, wey, tiene sus razones.",
        ]
    return random.choice(plantillas)


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

    # Ejecutar el comando con retry automático en 401
    try:
        return spotify_client.execute_command(intent, query)
    except Exception as e:
        return f"❌ Error Spotify: {e}"

    return None


# ====================================
# ENDPOINTS
# ====================================

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de salud para verificar que el servidor está corriendo"""
    from core.config import _PERSONALITY_MODE
    return jsonify({
        "status": "ok",
        "agent": "rAImundoGPT",
        "version": "2.0",
        "personality": _PERSONALITY_MODE,
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

        # Comando de diagnóstico: modo actual
        if mensaje.lower() in ['/modo', '/mode', '/debug', '/quien', '/quién']:
            from core.config import _PERSONALITY_MODE as _PM_D, PERSONALITY_FILE as _PF_D
            env_val = os.environ.get('PERSONALITY_MODE', '(no seteado)')
            prompt_preview = _PF_D.read_text(encoding='utf-8')[:80].replace('\n', ' ') if _PF_D.exists() else 'ARCHIVO NO EXISTE'
            return jsonify({
                "respuesta": (
                    f"MODO ACTIVO: {_PM_D}\n"
                    f"ENV PERSONALITY_MODE: {env_val}\n"
                    f"Archivo: {_PF_D.name}\n"
                    f"Preview: {prompt_preview}..."
                ),
                "user_id": user_id
            })
        
        # ── Comando /reset: borrar caché de conversaciones ────────
        if mensaje.lower() in ['/reset', '/borrar', '/limpiar', '/nuevo', '/clear']:
            # Cancelar wizard de planeación si está activo
            if user_id in _planeacion_wizards:
                del _planeacion_wizards[user_id]
            # 1. SQLite: mensajes + resúmenes del usuario
            limpiar_historial(user_id)
            # 2. Limpiar personalidad override del usuario
            if user_id in personalidades_por_usuario:
                del personalidades_por_usuario[user_id]
            # 3. Limpiar override de idioma
            if 'idioma_override' in conversaciones and user_id in conversaciones.get('idioma_override', {}):
                del conversaciones['idioma_override'][user_id]
            # 4. Limpiar vocabulario/estilo/temas acumulados del usuario (memoria_agente.json)
            #    SIN borrar documentos, CVs ni imágenes
            try:
                gestor.memory.clear_user_context(user_id)
            except Exception:
                pass
            # 5. Limpiar VectorMemory del agente (RAG acumulado)
            try:
                agent_memory.clear()
            except Exception:
                pass
            logger.info(f"🗑️ {user_name or user_id} ejecutó /reset — historial + contexto borrados")
            from core.config import _PERSONALITY_MODE as _PM_RESET
            if _PM_RESET == 'rai':
                return jsonify({
                    "respuesta": "ya wey, borre toda la conversacion. ahora si, q chingados kieres?",
                    "user_id": user_id
                })
            return jsonify({
                "respuesta": "🗑️ Listo, borré todo el historial de nuestra conversación. Empezamos de cero, ¿en qué te ayudo?",
                "user_id": user_id
            })

        # ── Wizard de Planeación Didáctica ─────────────────────────────────
        # Interceptar mensajes cuando el usuario tiene un wizard activo
        if user_id in _planeacion_wizards and _planeacion_wizards[user_id].is_active:
            wizard_resp = _planeacion_wizards[user_id].step(mensaje)
            still_active = _planeacion_wizards[user_id].is_active
            if not still_active:
                del _planeacion_wizards[user_id]
            logger.info(f"🎓 {user_name or user_id} — wizard planeación")
            return jsonify({"respuesta": wizard_resp, "user_id": user_id, "wizard_active": still_active})

        # Comando /planeacion: iniciar el wizard
        if mensaje.lower().strip() == '/planeacion':
            wizard = PlaneacionWizard(_ai_fn_planeacion)
            _planeacion_wizards[user_id] = wizard
            logger.info(f"🎓 {user_name or user_id} inició wizard de planeación didáctica")
            return jsonify({"respuesta": wizard.start(), "user_id": user_id, "wizard_active": True})

        # Comandos de cambio de personalidad — ahora son PER-USER
        if mensaje.lower() in ['/puteado', '/putedo', '/rai']:
            set_tono_usuario(user_id, 'puteado')
            logger.info(f"🔄 {user_name or user_id} cambió a personalidad PUTEADO")
            return jsonify({
                "respuesta": "oke wey, haora soy rAI, un puto ke no se anda kon mamadas. ke chingaos kieres?",
                "user_id": user_id
            })
        
        if mensaje.lower() in ['/amigable', '/raymundo', '/ray', '/friendly']:
            from core.config import _PERSONALITY_MODE as _PM_CHECK
            if _PM_CHECK == 'rai':
                # En modo rAI el servidor no cambia a amigable nunca
                return jsonify({
                    "respuesta": "nel wey, no me conviertas en esa nenaza. soy rAI y asi me quedo, pendejo",
                    "user_id": user_id
                })
            set_tono_usuario(user_id, 'amigable')
            logger.info(f"🔄 {user_name or user_id} cambió a personalidad AMIGABLE")
            return jsonify({
                "respuesta": "¡Hola! Ahora estoy en modo amigable 😊 ¿En qué puedo ayudarte?",
                "user_id": user_id
            })

        if mensaje.lower() in ['/prepa', '/school', '/escuela']:
            limpiar_historial(user_id)
            logger.info(f"🏫 {user_name or user_id} solicitó modo PREPA")
            return jsonify({
                "respuesta": "Órale wey, modo prepa al cien. Sin groserías pero con actitud. ¿Qué necesitas?",
                "user_id": user_id
            })

        # Comando para personalidad en inglés
        if mensaje.lower() in ['/english', '/en', '/inglés', '/ingles']:
            # Activar personalidad en inglés (usando configuración del JSON)

            
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

Has superado los límites del API:

🔄 **No te preocupes:**
Raymundo cambió automáticamente a **Ollama (local)** y seguirá funcionando sin interrupciones.

⏰ Los límites se reinician periódicamente.

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

        # ── /reset después de limpiar prefijo (e.g. "/Raymundo /reset") ──
        if mensaje_limpio.lower() in ['/reset', '/borrar', '/limpiar', '/nuevo', '/clear', 'reset']:
            limpiar_historial(user_id)
            if user_id in personalidades_por_usuario:
                del personalidades_por_usuario[user_id]
            if 'idioma_override' in conversaciones and user_id in conversaciones.get('idioma_override', {}):
                del conversaciones['idioma_override'][user_id]
            try:
                gestor.memory.clear_user_context(user_id)
            except Exception:
                pass
            try:
                agent_memory.clear()
            except Exception:
                pass
            logger.info(f"🗑️ {user_name or user_id} ejecutó /reset — historial + contexto + memoria borrados")
            from core.config import _PERSONALITY_MODE as _PM_RESET2
            if _PM_RESET2 == 'rai':
                return jsonify({
                    "respuesta": "ya wey, borre toda la conversacion y la memoria. ahora si, q chingados kieres?",
                    "user_id": user_id
                })
            return jsonify({
                "respuesta": "🗑️ Listo, borré todo el historial y la memoria de nuestra conversación. Empezamos de cero, ¿en qué te ayudo?",
                "user_id": user_id
            })

        # Detectar cambio de personalidad en lenguaje natural (omitir en modo rAI)
        from core.config import _PERSONALITY_MODE as _PM_CHECK2
        if _PM_CHECK2 != 'rai':
            cambio_natural = detectar_cambio_personalidad_natural(mensaje_limpio)
            if cambio_natural:
                set_tono_usuario(user_id, cambio_natural)
                logger.info(f"🔄 {user_name or user_id} cambió a {cambio_natural} (lenguaje natural)")

        logger.info(f"📩 [{user_name or user_id}] {mensaje_limpio[:60]}...")

        # Detectar si el usuario está siendo agresivo en ESTE mensaje (no persistente)
        usuario_agresivo = detectar_agresividad_usuario(mensaje_limpio)

        # ─── COMANDO "según mi cara" sin imagen adjunta ───────────
        # Detecta peticiones faciales sin imagen (usa último resultado del stream si está activo)
        _segun_cara_patterns = [
            r"seg[uú]n\s+mi\s+cara", r"bas[aá]ndote\s+en\s+mi\s+cara",
            r"con\s+mi\s+cara",  r"por\s+mi\s+cara",
        ]
        _es_peticion_cara_sin_imagen = (
            not image_base64
            and any(re.search(p, mensaje_limpio, re.IGNORECASE) for p in _segun_cara_patterns)
        )
        if _es_peticion_cara_sin_imagen:
            # Intentar leer el último resultado del DeepFaceStream (cámara activa)
            _last_df = None
            try:

                # Acceder a la instancia global si existe en voice_assistant o similar
                import sys as _sys
                for _mod in list(_sys.modules.values()):
                    if hasattr(_mod, '_face_stream') and hasattr(_mod._face_stream, 'last_result'):
                        _last_df = _mod._face_stream.last_result
                        break
            except Exception:
                pass

            if _last_df and _last_df.get("ok") and _last_df.get("faces"):
                _f = _last_df["faces"][0]
                _GENDER_ES2 = {"Man": "Hombre", "Woman": "Mujer"}
                _EMO_ES2 = {"happy": "feliz", "sad": "triste", "angry": "enojado/a",
                            "surprise": "sorprendido/a", "fear": "asustado/a",
                            "disgust": "disgustado/a", "neutral": "neutral"}
                _RACE_ES2 = {"white": "blanco/a", "black": "negro/a", "asian": "asiático/a",
                             "indian": "indio/a", "middle eastern": "de medio oriente",
                             "latino hispanic": "latino/hispano"}
                _face_txt_stream = (
                    f"Edad: ~{_f.get('age','?')} años, "
                    f"Género: {_GENDER_ES2.get(_f.get('gender',''), _f.get('gender','?'))}, "
                    f"Emoción: {_EMO_ES2.get(_f.get('emotion',''), _f.get('emotion','?'))}, "
                    f"Raza/Etnia: {_RACE_ES2.get(_f.get('race',''), _f.get('race','?'))}"
                )
                from core.config import config_agente as _cfg_stream
                _sp_min = _cfg_stream.get_prompt_sistema()[:2000]
                _sp_min += context_manager._build_tone_instruction(get_tono_usuario(user_id), usuario_agresivo)
                if user_name and user_name != user_id:
                    _sp_min += f"\n\nChateando con: {user_name}."
                _stream_msg = (
                    f"{mensaje_limpio}\n\n"
                    f"[DATOS DEEPFACE CÁMARA]: {_face_txt_stream}\n\n"
                    f"Responde de forma hilarante y directa sobre estos datos. Máx 3 oraciones."
                )
                _resp_stream = limpiar_formato_markdown(gestor.chat_hibrido(
                    _stream_msg, history=[], system_prompt=_sp_min,
                ))
                agregar_mensaje(user_id, "user", mensaje_limpio)
                agregar_mensaje(user_id, "assistant", _resp_stream)
                return jsonify({"respuesta": _resp_stream, "user_id": user_id})
            else:
                # Sin datos de cámara → pedir foto
                from core.config import _PERSONALITY_MODE as _PM_CARA
                if _PM_CARA == 'rai':
                    _no_cam = "wey, mándame una foto pendejo, no tengo cámara aquí, cómo quieres que vea tu cara?"
                else:
                    _no_cam = "Para analizar tu cara necesitas mandarme una foto. Adjunta una imagen y repite la pregunta 📸"
                agregar_mensaje(user_id, "user", mensaje_limpio)
                agregar_mensaje(user_id, "assistant", _no_cam)
                return jsonify({"respuesta": _no_cam, "user_id": user_id})

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
        face_analysis_text = None
        _face_analyzed = False  # Flag para saltar AgentLoop
        if image_base64:
            tipo_media = media_mimetype or 'desconocido'
            logger.info(f"📎 [{user_name or user_id}] Media adjunta recibida ({tipo_media}), extrayendo texto...")
            try:
                texto_imagen_extraido = gestor.vision.extract_text_from_base64(image_base64, mimetype=media_mimetype)
                if texto_imagen_extraido and not texto_imagen_extraido.startswith("❌"):
                    logger.info(f"📝 Texto extraído de imagen: {len(texto_imagen_extraido)} chars")
                    # Cap OCR a 1500 chars para no inflar el payload del LLM
                    _ocr_truncado = texto_imagen_extraido[:1500]
                    if len(texto_imagen_extraido) > 1500:
                        _ocr_truncado += "\n[...texto truncado...]"
                    mensaje_limpio = (
                        f"{mensaje_limpio}\n\n"
                        f"[CONTENIDO EXTRAÍDO DE LA IMAGEN ADJUNTA]:\n"
                        f"{_ocr_truncado}"
                    )
                    # Guardar documento en la base de conocimiento (texto completo, sin truncar)
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

            # ─── DeepFace: análisis facial si el mensaje lo pide ────
            if media_mimetype and 'image' in media_mimetype.lower():
                from core.detectors import DetectorIntenciones
                _face_detector = DetectorIntenciones()
                _face_score = _face_detector._contar_keywords(
                    mensaje_limpio.lower(),
                    DetectorIntenciones.KEYWORDS_RECONOCIMIENTO_FACIAL,
                )
                if _face_score >= 1:
                    logger.info(f"👤 [{user_name or user_id}] Intent facial detectado, analizando...")
                    _deepface_done = False

                    # ── Opción 1: DeepFace worker (edad/género/emoción/raza completo) ──
                    if deepface_worker and deepface_worker.available:
                        try:
                            df_result = deepface_worker.analyze_b64(image_base64)
                            if df_result and df_result.get("ok") and df_result.get("faces"):
                                _deepface_done = True
                                _GENDER_ES = {"Man": "Hombre", "Woman": "Mujer"}
                                _EMOTION_ES = {
                                    "happy": "feliz", "sad": "triste", "angry": "enojado/a",
                                    "surprise": "sorprendido/a", "fear": "asustado/a",
                                    "disgust": "disgustado/a", "neutral": "neutral",
                                    "contempt": "desprecio",
                                }
                                _RACE_ES = {
                                    "white": "blanco/a", "black": "negro/a",
                                    "asian": "asiático/a", "indian": "indio/a",
                                    "middle eastern": "medio oriente",
                                    "latino hispanic": "latino/hispano",
                                }
                                face_lines = []
                                for i, f in enumerate(df_result["faces"], 1):
                                    prefix = f"Rostro {i}:" if len(df_result["faces"]) > 1 else ""
                                    parts = [
                                        f"Edad: ~{f.get('age', '?')} años",
                                        f"Género: {_GENDER_ES.get(f.get('gender', ''), f.get('gender', '?'))}",
                                        f"Emoción: {_EMOTION_ES.get(f.get('emotion', ''), f.get('emotion', '?'))}",
                                        f"Raza/Etnia: {_RACE_ES.get(f.get('race', ''), f.get('race', '?'))}",
                                    ]
                                    face_lines.append(f"{prefix} {', '.join(parts)}".strip())
                                face_analysis_text = "\n".join(face_lines)
                                mensaje_limpio = (
                                    f"{mensaje_limpio}\n\n"
                                    f"[ANÁLISIS FACIAL DEEPFACE — datos reales detectados]:\n"
                                    f"{face_analysis_text}\n\n"
                                    f"[INSTRUCCIÓN]: El usuario te pidió que analices su cara. "
                                    f"Con base en los datos del análisis facial de arriba, "
                                    f"hazle un comentario burlón y creativo sobre "
                                    f"su edad, género, emoción o raza detectada. "
                                    f"REGLAS: Menciona los datos reales detectados. "
                                    f"Haz UNA broma ingeniosa basada en esos datos. "
                                    f"NO repitas muletillas (nmms, wey) más de una vez. "
                                    f"NO digas cosas sin sentido ni te inventes datos. "
                                    f"Máximo 3 oraciones. Sé creativo y directo."
                                )
                                logger.info(f"👤 DeepFace worker completado: {face_analysis_text[:120]}")
                                _face_analyzed = True
                            elif df_result and df_result.get("ok") and not df_result.get("faces"):
                                _deepface_done = True
                                _face_analyzed = True
                                mensaje_limpio = (
                                    f"{mensaje_limpio}\n\n"
                                    f"[ANÁLISIS FACIAL]: No se detectaron rostros en la imagen.\n"
                                    f"[INSTRUCCIÓN]: Dile al usuario que no pudiste ver ninguna cara "
                                    f"en la foto que mandó, y búrlate de eso."
                                )
                        except Exception as dfe:
                            logger.warning(f"⚠️ Error en DeepFace worker: {dfe}")

                    # ── Opción 2: Fallback a FaceManager (solo emoción) ──
                    if not _deepface_done and face_manager and face_manager.available:
                        try:
                            from core.face_recognition import FaceManager
                            face_result = face_manager.analyze(b64=image_base64)
                            if face_result["success"]:
                                face_analysis_text = FaceManager.format_analysis(face_result)
                                mensaje_limpio = (
                                    f"{mensaje_limpio}\n\n"
                                    f"[ANÁLISIS FACIAL]:\n"
                                    f"{face_analysis_text}\n\n"
                                    f"[INSTRUCCIÓN]: El usuario te pidió que analices su cara. "
                                    f"Con base en el análisis facial, hazle un comentario "
                                    f"burlón basado en los datos reales. Máximo 3 oraciones. "
                                    f"NO repitas muletillas, sé creativo."
                                )
                                _face_analyzed = True
                        except Exception as fe:
                            logger.warning(f"⚠️ Error en análisis facial (fallback): {fe}")

        # ─── RUTA FACIAL: respuesta directa sin AgentLoop ni historial pesado ──
        if _face_analyzed:
            logger.info(f"👤 [{user_name or user_id}] Análisis facial completado → respuesta directa")
            try:
                # Prompt MÍNIMO: solo personalidad (cap 2000) + tono + nombre.
                # Sin KB, sin herramientas, sin capacidades — evita overflow 413.
                from core.config import config_agente as _cfg_f
                _base_pers = _cfg_f.get_prompt_sistema()[:2000]
                _tono_instr = context_manager._build_tone_instruction(
                    get_tono_usuario(user_id), usuario_agresivo
                )
                _face_system = _base_pers + _tono_instr
                if user_name and user_name != user_id:
                    _face_system += f"\n\nChateando con: {user_name}."

                # Mensaje compacto: SOLO datos deepface + petición original.
                # NO incluir OCR completo (puede ser miles de chars).
                _original_req = mensaje or ""
                if face_analysis_text:
                    _face_user_msg = (
                        f"{_original_req}\n\n"
                        f"[ANÁLISIS DEEPFACE]: {face_analysis_text}\n\n"
                        f"Hazme un comentario burlón y creativo sobre lo que detectaste. "
                        f"Máximo 3 oraciones, sé directo e hilarante."
                    )
                else:
                    _face_user_msg = (
                        f"{_original_req}\n\n"
                        f"[ANÁLISIS FACIAL]: No se detectaron rostros en la imagen. "
                        f"Dile al usuario que no pudiste ver ninguna cara y búrlate."
                    )

                # Intentar con gemma2-9b-it (15k TPM) o cualquier modelo disponible
                _face_messages = [
                    {"role": "system", "content": _face_system},
                    {"role": "user", "content": _face_user_msg},
                ]
                respuesta = None
                # 1) Groq con gemma2-9b-it (15,000 TPM vs 6,000 de llama-3.1-8b-instant)
                if gestor.groq_client and gestor.groq_client.client:
                    _r = gestor.groq_client.chat(
                        _face_messages, temperature=0.8, max_tokens=400,
                        model_override="gemma2-9b-it",
                    )
                    from core.tools import es_rechazo_llm, _es_rechazo_rai
                    if _r and not es_rechazo_llm(_r) and not _es_rechazo_rai(_r):
                        respuesta = _r
                # 2) Groq con modelo default (por si gemma2 también falla)
                if not respuesta and gestor.groq_client and gestor.groq_client.client:
                    _r = gestor.groq_client.chat(_face_messages, temperature=0.8, max_tokens=400)
                    if _r and not es_rechazo_llm(_r) and not _es_rechazo_rai(_r):
                        respuesta = _r
                # 3) Mistral fallback
                if not respuesta and gestor.mistral and gestor.mistral.client:
                    _r = gestor.mistral.chat(_face_messages, temperature=0.8, max_tokens=400)
                    if _r and not es_rechazo_llm(_r) and not _es_rechazo_rai(_r):
                        respuesta = _r
                # 4) Ollama local
                if not respuesta:
                    _r = gestor.ollama.chat(_face_messages, temperature=0.8, max_tokens=400)
                    if _r and not es_rechazo_llm(_r):
                        respuesta = _r
                # 5) Template sin LLM — siempre funciona
                if not respuesta and face_analysis_text:
                    respuesta = _generar_respuesta_facial_template(
                        face_analysis_text, user_name or "amigo",
                        get_tono_usuario(user_id)
                    )
                if not respuesta:
                    respuesta = "Nmms, no pude ver bien tu cara. Intenta con mejor foto."
                respuesta = limpiar_formato_markdown(respuesta)
            except Exception as face_llm_err:
                logger.warning(f"⚠️ Error LLM en análisis facial: {face_llm_err}")
                if face_analysis_text:
                    respuesta = _generar_respuesta_facial_template(
                        face_analysis_text, user_name or "amigo",
                        get_tono_usuario(user_id)
                    )
                else:
                    respuesta = "No pude generar el comentario sobre tu cara, intenta de nuevo."

            logger.info(f"✅ Respuesta facial generada ({len(respuesta)} chars)")
            agregar_mensaje(user_id, "user", mensaje_limpio)
            agregar_mensaje(user_id, "assistant", respuesta)
            _extraer_y_guardar_conocimiento(mensaje_limpio, respuesta, user_id)
            return jsonify({"respuesta": respuesta, "user_id": user_id})

        # ─── RUTA DIRECTA: herramientas/exportación del canal ─────
        # Procesar mensaje (detectar intención, aprender vocabulario internamente)
        resultado_herramienta = gestor.procesar_mensaje(
            mensaje_limpio,
            user_name=user_name,
            user_id=user_id,
            tono_override=get_tono_usuario(user_id),
            usuario_agresivo=usuario_agresivo,
        )
        
        if resultado_herramienta['ejecuto_herramienta']:
            # Manejar señal de reset del gestor de herramientas
            if resultado_herramienta.get('tipo') == 'reset' or resultado_herramienta.get('resultado') == '__RESET__':
                limpiar_historial(user_id)
                try:
                    gestor.memory.clear_user_context(user_id)
                except Exception:
                    pass
                try:
                    agent_memory.clear()
                except Exception:
                    pass
                logger.info(f"🗑️ {user_name or user_id} ejecutó /reset (via herramienta) — historial + memoria borrados")
                from core.config import _PERSONALITY_MODE as _PM_RESET3
                if _PM_RESET3 == 'rai':
                    return jsonify({
                        "respuesta": "ya wey, borre toda la conversacion y la memoria. ahora si, q chingados kieres?",
                        "user_id": user_id
                    })
                return jsonify({
                    "respuesta": "🗑️ Listo, borré todo el historial y la memoria de nuestra conversación. Empezamos de cero, ¿en qué te ayudo?",
                    "user_id": user_id
                })

            respuesta = limpiar_formato_markdown(resultado_herramienta['resultado'])
            archivo_info = resultado_herramienta.get('archivo')
            imagen_path = resultado_herramienta.get('imagen_path')
            
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
            tokens_mistral = mistral.last_tokens_used
            tokens_groq = groq.last_tokens_used if groq and groq.client else 0
            
            # Determinar qué modelo se usó (prioridad: Groq > Mistral > Ollama)
            if tokens_groq > 0:
                metrics.track_request(
                    tipo=archivo_info.get('tipo', 'chat') if archivo_info else 'chat',
                    tokens_used=tokens_groq,
                    modelo='groq',
                    tiempo_respuesta=tiempo_respuesta,
                    user_id=user_id
                )
            elif tokens_mistral > 0:
                metrics.track_request(
                    tipo=archivo_info.get('tipo', 'chat') if archivo_info else 'chat',
                    tokens_used=tokens_mistral,
                    modelo='mistral',
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
            logger.info(f"   • Tiempo: {tiempo_respuesta:.2f}s | Groq: {tokens_groq} | Mistral: {tokens_mistral} | Ollama: {tokens_ollama}")
            
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
            adjuntos_locales = []
            if archivo_path:
                adjuntos_locales.append(
                    construir_adjunto_local(
                        archivo_path,
                        tipo=archivo_info.get('tipo') if archivo_info else None,
                        title=archivo_info.get('titulo') if archivo_info else None,
                    )
                )
            if imagen_path:
                adjuntos_locales.append(construir_adjunto_local(imagen_path))
            if adjuntos_locales:
                archivos = normalizar_adjuntos_locales(adjuntos_locales)
                agregar_adjuntos_respuesta(response_data, archivos)
            
            return jsonify(response_data)
        else:
            resultado_runtime = agent_runtime.handle_text(
                AgentRequest(
                    text=mensaje_limpio,
                    user_id=user_id,
                    user_name=user_name,
                    channel="whatsapp",
                    tono_override=get_tono_usuario(user_id),
                    usuario_agresivo=usuario_agresivo,
                )
            )
            respuesta = limpiar_formato_markdown(resultado_runtime.response)
            
            # Calcular tiempo de respuesta
            tiempo_respuesta = time.time() - tiempo_inicio
            
            # Rastrear métricas
            tokens_ollama = ollama.last_tokens_used
            tokens_mistral = mistral.last_tokens_used
            tokens_groq = groq.last_tokens_used if groq and groq.client else 0
            
            if tokens_groq > 0:
                metrics.track_request(
                    tipo='chat',
                    tokens_used=tokens_groq,
                    modelo='groq',
                    tiempo_respuesta=tiempo_respuesta,
                    user_id=user_id
                )
            elif tokens_mistral > 0:
                metrics.track_request(
                    tipo='chat',
                    tokens_used=tokens_mistral,
                    modelo='mistral',
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
            logger.info(f"   • Tiempo: {tiempo_respuesta:.2f}s | Groq: {tokens_groq} | Mistral: {tokens_mistral} | Ollama: {tokens_ollama}")

            # Extraer y guardar datos de personas mencionadas
            _extraer_y_guardar_conocimiento(mensaje_limpio, respuesta, user_id)

            response_data = {
                "respuesta": respuesta,
                "user_id": user_id,
                "agentic": resultado_runtime.used_agent_loop,
                "steps": resultado_runtime.steps_taken,
                "run_id": resultado_runtime.run_id,
            }
            agregar_adjuntos_respuesta(
                response_data,
                normalizar_adjuntos_locales(resultado_runtime.artifacts),
            )
            return jsonify(response_data)
        
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
        resultado_herramienta = gestor.procesar_mensaje(texto, user_id=user_id)
        
        if resultado_herramienta['ejecuto_herramienta']:
            respuesta = resultado_herramienta['resultado']
            agregar_mensaje(user_id, "user", texto)
            agregar_mensaje(user_id, "assistant", respuesta)
        else:
            resultado_runtime = agent_runtime.handle_text(
                AgentRequest(
                    text=texto,
                    user_id=user_id,
                    channel="whatsapp",
                )
            )
            respuesta = limpiar_formato_markdown(resultado_runtime.response)
        
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
    import atexit

    def _cleanup_deepface_worker():
        if deepface_worker:
            try:
                deepface_worker.stop()
            except Exception:
                pass

    atexit.register(_cleanup_deepface_worker)

    # ⚠️ SYNC: Copiar token.json a data/ (necesario para Google APIs)
    import shutil
    from pathlib import Path
    token_resources = Path("resources/data/token.json")
    token_local = Path("data/token.json")
    if token_resources.exists() and (not token_local.exists() or token_resources.stat().st_mtime > token_local.stat().st_mtime):
        try:
            token_local.parent.mkdir(exist_ok=True)
            shutil.copy2(token_resources, token_local)
            logger.info("✅ Token.json sincronizado desde resources/data/ a data/")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo sincronizar token.json: {e}")
    
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
