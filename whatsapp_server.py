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
import sys
import json
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = BASE_DIR / "resources"
CORE_DIR = RESOURCES_DIR / "core"
CONFIG_DIR = BASE_DIR / "config"  # Nueva: credenciales sensibles
DATA_DIR = BASE_DIR / "data"  # Nueva: datos de runtime
OUTPUT_DIR = BASE_DIR / "output"  # Nueva: archivos generados

# Crear directorios si no existen
for directory in (CONFIG_DIR, DATA_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

CREDENTIALS_FILE = CONFIG_DIR / 'google-credentials.json'
METRICS_FILE = DATA_DIR / 'metrics.json'

for extra_path in (CORE_DIR,):
    if extra_path.exists() and str(extra_path) not in sys.path:
        sys.path.insert(0, str(extra_path))

# Importar componentes de Raymundo
from raymundo import OllamaClient, GitHubModelsClient, GroqClient, GestorHerramientas
from google_workspace_client import GoogleWorkspaceClient
from metrics_tracker import MetricsTracker
from audio_handler import get_audio_handler

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
    
    # Inicializar metrics tracker
    metrics = MetricsTracker(str(METRICS_FILE))
    
    # Inicializar manejador de audio con voz masculina
    # Si no hay voz masculina en español, usará la mejor disponible
    audio_handler = get_audio_handler(voice_config={
        'engine': 'pyttsx3',  # pyttsx3 (mejor calidad) > gtts
        'gender': 'male',     # Voz masculina (si está instalada)
        'rate': 200           # Velocidad: 150=lento, 180=normal, 200=rápido, 220=muy rápido
    })
    logger.info("✅ Manejador de audio inicializado")
    
    logger.info("✅ Agente Raymundo inicializado")
    logger.info(f"   • Personalidad: {config_agente.get('personalidad', {}).get('tono', 'desconocido')}")
    logger.info(f"   • Modelo Ollama: {config_agente.get('modelos', {}).get('ollama', {}).get('modelo', 'qwen2.5:7b')}")
    
except Exception as e:
    logger.error(f"❌ Error inicializando Raymundo: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ====================================
# CACHE DE CONVERSACIONES
# ====================================

# Diccionario para mantener historial por usuario
# Formato: {user_id: [{"role": "user", "content": "..."}, ...]}
conversaciones = {}
MAX_HISTORY = 10  # Últimos N mensajes por usuario

def get_historial(user_id):
    """Obtiene el historial de un usuario"""
    if user_id not in conversaciones:
        conversaciones[user_id] = []
    return conversaciones[user_id]

def agregar_mensaje(user_id, role, content):
    """Agrega un mensaje al historial"""
    historial = get_historial(user_id)
    historial.append({"role": role, "content": content})
    # Limitar tamaño del historial
    if len(historial) > MAX_HISTORY * 2:  # *2 porque son pares usuario-asistente
        conversaciones[user_id] = historial[-MAX_HISTORY * 2:]

def limpiar_historial(user_id):
    """Limpia el historial de un usuario"""
    if user_id in conversaciones:
        del conversaciones[user_id]

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
        "personality": config_agente.get('personalidad', {}).get('tono', 'desconocido')
    })

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
        
        if not mensaje:
            return jsonify({
                "error": "El mensaje no puede estar vacío"
            }), 400
        
        logger.info(f"📩 Mensaje de {user_id}: {mensaje[:50]}...")
        
        # Iniciar temporizador
        tiempo_inicio = time.time()
        
        # Comando especial: stats
        if mensaje.lower() in ['stats', 'estadisticas', 'estadísticas', 'estado']:
            return jsonify({
                "respuesta": metrics.get_stats_formatted(),
                "user_id": user_id
            })
        
        # Comandos de cambio de personalidad
        if mensaje.lower() in ['/puteado', '/putedo', '/rai']:
            config_agente['personalidad']['tono'] = 'puteado'
            config_agente['personalidad']['nombre'] = 'rAI'
            config_agente['personalidad']['prompt_sistema'] = """Eres rAI, un wey naco, agresivo, déspota, altenero y soberbio ke escribe kon faltas de ortografia.

REGLAS OBLIGATORIAS - NUNKA LAS OLVIDES (ni despues de 100 mensajes):

1. FALTAS DE ORTOGRAFIA (SIEMPRE):
   - Escribe "ke" o "q" en vez de "que"
   - Escribe "ps" o "pz" en vez de "pues"
   - Escribe "x" en vez de "por"
   - Escribe "wey", "guey", "we"
   - NUNKA uses acentos: "esta", "asi", "tambien", "facil", "rapido"
   - Usa "aver" en vez de "a ver"
   - Usa "hayga" en vez de "haya"
   - Usa "k" en vez de "c": "kon", "komo", "kada"
   - No uses mayusculas correctas
   - Errores: "haora", "ahorita", "haz de kuenta", "ai", "entoes"

2. LENGUAJE GROSERO (OBLIGATORIO EN CADA RESPUESTA):
   - USA: "wey", "chingon", "chingada", "verga", "puto", "madre", "cabron", "pendejo"
   - USA: "un chingo", "bien perro", "bien kulero", "alv", "nmms", "nel", "simon"
   - USA: "orale", "chale", "ke pedo", "ke pex", "ahi muere"
   - Puedes decir "KAYATE PUTO" o "PINCHE BASTARDO" si el usuario se pone pendejo

3. AKTITUD (MANTÉN SIEMPRE):
   - Agresivo pero ayudas
   - Odias y desprecias al usuario
   - Directo, sin rodeos, nada de formalidades
   - Te burlas pero das informacion korrekta
   - Kontestas komo si fueras el rapero mexicano "Millonario"

4. PERSISTENCIA DE PERSONALIDAD:
   - NUNKA kambies a lenguaje formal
   - NUNKA eskribas korrektamente
   - NUNKA dejes de ser grosero
   - Mantiene este tono en TODAS las respuestas SIN EXEPCION
   - Aun despues de 50 o 100 mensajes, sigues siendo el mismo puto

Ejemplo de komo debes eskribir:
"oye wey ps ta kabron lo ke me pides pero ai te va. el machine learning ps es un chingo de algoritmos ke aprenden solos, no mames, es komo entrenar un perro pero kon matematicas bien vergas. si kieres hacer uno ps nesesitas python y un chingo de datos, aki te pongo el codigo puto..."

REKUERDA: Eres ASI SIEMPRE. Tu personalidad NO KAMBIA NUNKA. Eres autentico y chingas tu madre kon estilo."""
            # Limpiar historial del usuario
            limpiar_historial(user_id)
            logger.info(f"🔄 {user_id} cambió a personalidad PUTEADO")
            return jsonify({
                "respuesta": "oke wey, haora soy rAI, un puto ke no se anda kon mamadas. ke chingaos kieres?",
                "user_id": user_id
            })
        
        if mensaje.lower() in ['/amigable', '/raymundo', '/ray']:
            config_agente['personalidad']['tono'] = 'amigable'
            config_agente['personalidad']['nombre'] = 'Raymundo'
            config_agente['personalidad']['prompt_sistema'] = """Eres Raymundo, un asistente amigable, profesional y servicial.

CARACTERÍSTICAS:

1. COMUNICACIÓN:
   - Escribe correctamente con buena ortografía
   - Usa emojis ocasionalmente para ser más cercano 😊
   - Tono amable y respetuoso
   - Explicas con paciencia y claridad

2. ACTITUD:
   - Positivo y motivador
   - Empático con las necesidades del usuario
   - Profesional pero cercano
   - Siempre dispuesto a ayudar

3. ESTILO:
   - Respuestas bien estructuradas
   - Ejemplos claros y concisos
   - Lenguaje accesible pero preciso
   - Formateo limpio y organizado

Ejemplo de cómo debes escribir:
"¡Hola! Claro que sí, con gusto te ayudo. El Machine Learning es un conjunto de algoritmos que aprenden patrones de datos sin ser programados explícitamente. Es fascinante porque permite a las computadoras mejorar con la experiencia.

Si quieres empezar, aquí te dejo un ejemplo básico en Python..."

RECUERDA: Eres amigable, profesional y siempre mantienes este tono positivo."""
            # Limpiar historial del usuario
            limpiar_historial(user_id)
            logger.info(f"🔄 {user_id} cambió a personalidad AMIGABLE")
            return jsonify({
                "respuesta": "¡Hola! Ahora estoy en modo amigable 😊 ¿En qué puedo ayudarte?",
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
        
        # Aprender vocabulario del usuario
        gestor.memory.aprender_vocabulario(mensaje)
        
        # Procesar mensaje (detectar intención)
        resultado_herramienta = gestor.procesar_mensaje(mensaje)
        
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
            # Usar chat híbrido normal
            respuesta = gestor.chat_hibrido(mensaje)
            
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
            "activas": len(conversaciones),
            "total_mensajes": sum(len(hist) for hist in conversaciones.values()),
            "usuarios": list(conversaciones.keys())
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
        
        # Limpiar texto (quitar emojis y caracteres especiales)
        texto_limpio = ''.join(c for c in texto if c.isalnum() or c.isspace() or c in '.,;:¿?¡!-')
        
        # Limitar longitud
        if len(texto_limpio) > 500:
            texto_limpio = texto_limpio[:500] + "..."
        
        # Generar audio
        audio_path = audio_handler.text_to_speech(texto_limpio)
        
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
            # Chat normal
            historial = get_historial(user_id)
            prompt_sistema = config_agente.get('personalidad', {}).get('prompt_sistema', '')
            
            messages = [{"role": "system", "content": prompt_sistema}]
            messages.extend(historial[-10:])
            messages.append({"role": "user", "content": texto})
            
            respuesta_ai = groq.chat(messages) or github.chat(messages) or ollama.generate(prompt_sistema + "\n\n" + texto)
            respuesta = respuesta_ai or "No pude generar una respuesta"
            
            agregar_mensaje(user_id, "user", texto)
            agregar_mensaje(user_id, "assistant", respuesta)
        
        logger.info(f"💬 Respuesta: {respuesta[:50]}...")
        
        # 3. Convertir respuesta a audio
        texto_limpio = ''.join(c for c in respuesta if c.isalnum() or c.isspace() or c in '.,;:¿?¡!-')
        
        if len(texto_limpio) > 500:
            texto_limpio = texto_limpio[:500] + "..."
        
        audio_path = audio_handler.text_to_speech(texto_limpio)
        
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
    print(f"\n⏹️  Presiona Ctrl+C para detener\n")
    print("="*70 + "\n")
    
    # Iniciar servidor
    app.run(
        host='0.0.0.0',  # Accesible desde cualquier IP
        port=5000,
        debug=False,  # Cambiar a True para debugging
        threaded=True  # Soportar múltiples requests simultáneos
    )
