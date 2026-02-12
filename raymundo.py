"""
🤖 RAYMUNDO - AGENTE IA UNIFICADO
Arquitectura híbrida: Ollama (local GPU) + GPT-4o (cloud)
Todas las funciones integradas en un solo archivo

Autor: Sistema IA
Versión: 2.0 Unificada
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = BASE_DIR / "resources"
CORE_DIR = RESOURCES_DIR / "core"
CONFIG_DIR = BASE_DIR / "config"  # Nueva: credenciales sensibles
DATA_DIR = BASE_DIR / "data"  # Nueva: datos de runtime
OUTPUT_DIR = BASE_DIR / "output"  # Nueva: archivos generados

# Crear directorios si no existen
for directory in (CONFIG_DIR, DATA_DIR, OUTPUT_DIR):
    directory.mkdir(exist_ok=True)

for extra_path in (CORE_DIR,):
    if extra_path.exists() and str(extra_path) not in sys.path:
        sys.path.insert(0, str(extra_path))

# Cargar variables de entorno desde config/.env si existe
dotenv_path = CONFIG_DIR / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()
import base64
import requests
from PIL import Image
import io
from bs4 import BeautifulSoup
import emoji
from spellchecker import SpellChecker

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from groq import Groq

from google_workspace_client import GoogleWorkspaceClient
from audio_handler import get_audio_handler


# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

class ConfigAgente(dict):
    """Wrapper con helpers para acceder a la configuración del agente."""

    def __init__(self, data):
        super().__init__(data or {})
        # Compatibilidad: algunos bloques esperan .config como dict
        self.config = self

    def get_nombre_agente(self):
        return self.config.get('personalidad', {}).get('nombre', 'Raymundo')

    def get_prompt_sistema(self):
        personalidad = self.config.get('personalidad', {})
        prompt = personalidad.get('prompt_sistema')
        if prompt:
            return prompt
        tono = personalidad.get('tono', 'amigable')
        return (
            f"Eres {self.get_nombre_agente()}, un asistente con tono {tono}. "
            "Responde siempre con precisión y mantén ese estilo."
        )
    
    def get_tono(self):
        """Retorna el tono actual de personalidad desde config_agente.json"""
        return self.config.get('personalidad', {}).get('tono', 'amigable')


# Cargar configuración del agente
with open('config_agente.json', 'r', encoding='utf-8') as f:
    config_agente = ConfigAgente(json.load(f))


class AppConfig:
    """Administra ajustes locales (modelos y credenciales)."""

    def __init__(self):
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
        self.github_token = os.environ.get("GITHUB_TOKEN")

        creds_env = os.environ.get("GOOGLE_CREDENTIALS_FILE")
        default_creds = CONFIG_DIR / 'google-credentials.json'
        self.google_credentials_file = Path(creds_env) if creds_env else default_creds
        self.google_client = None
        if self.google_credentials_file and self.google_credentials_file.exists():
            try:
                self.google_client = GoogleWorkspaceClient(str(self.google_credentials_file))
            except Exception as e:
                print(f"⚠️ No se pudo inicializar Google Workspace: {e}")


# ═══════════════════════════════════════════════════════════════
# CLIENTES DE IA
# ═══════════════════════════════════════════════════════════════

class OllamaClient:
    """Cliente para Ollama local (GPU)"""
    
    def __init__(self, url="http://localhost:11434", model="qwen2.5:7b"):
        self.url = url
        self.model = model
        self.last_tokens_used = 0
    
    def generate(self, prompt, temperature=0.7, max_tokens=2000):
        """Genera respuesta con Ollama"""
        try:
            response = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False,
                    "options": {"num_predict": max_tokens}
                },
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                # Ollama devuelve 'eval_count' (tokens generados)
                self.last_tokens_used = data.get('eval_count', 0)
                return data.get('response', '')
            return None
        except Exception as e:
            print(f"Error Ollama: {e}")
            return None
    
    def is_available(self):
        """Verifica si Ollama está disponible"""
        try:
            response = requests.get(f"{self.url}/api/version", timeout=2)
            return response.status_code == 200
        except:
            return False


class GitHubModelsClient:
    """Cliente para GitHub Models (GPT-4o)"""
    
    def __init__(self, token=None, model="gpt-4o"):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.model = model
        self.endpoint = "https://models.inference.ai.azure.com"
        self.last_tokens_used = 0
        
        if not self.token:
            self.client = None
        else:
            try:
                self.client = ChatCompletionsClient(
                    endpoint=self.endpoint,
                    credential=AzureKeyCredential(self.token)
                )
            except Exception as e:
                print(f"Error inicializando GitHub Models: {e}")
                self.client = None
    
    def chat(self, messages, temperature=0.7, max_tokens=4000):
        """Realiza consulta a GPT-4o"""
        if not self.client:
            return None
        
        try:
            formatted_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    formatted_messages.append(SystemMessage(content=msg["content"]))
                elif msg["role"] == "user":
                    formatted_messages.append(UserMessage(content=msg["content"]))
            
            response = self.client.complete(
                messages=formatted_messages,
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extraer tokens usados si están disponibles
            if hasattr(response, 'usage'):
                self.last_tokens_used = response.usage.total_tokens
            else:
                self.last_tokens_used = 0
            
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e)
            # Detectar error 429 (Rate Limit)
            if '429' in error_msg or 'RateLimitReached' in error_msg:
                print("⚠️ Rate limit alcanzado en GitHub Models (Free Tier)")
                print("   Límites: 15 RPM, 150 RPD, 150K TPM")
                print("   Fallback automático a Ollama activado")
                return None  # Triggerá fallback a Ollama
            print(f"Error GitHub Models: {error_msg}")
            return None
    
    def chat_with_images(self, messages, temperature=0.7, max_tokens=1000):
        """Consulta con imágenes (Vision API)"""
        if not self.client:
            return "❌ GitHub Models no configurado"
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}"
            }
            
            payload = {
                "messages": messages,
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            response = requests.post(
                f"{self.endpoint}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            elif response.status_code == 429:
                print("⚠️ Rate limit alcanzado en GitHub Models Vision API")
                return "❌ No puedo procesar imágenes ahora (rate limit alcanzado). Los límites del Free Tier son: 15 RPM, 150 RPD, 150K TPM. Intenta de nuevo en unos minutos."
            return f"❌ Error en API: {response.status_code}"
        except Exception as e:
            return f"❌ Error procesando imagen: {str(e)}"


class GroqClient:
    """Cliente para Groq API (Llama 3.3 70B - Ultra rápido y gratis)"""
    
    def __init__(self, api_key=None, model="llama-3.3-70b-versatile"):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model
        self.last_tokens_used = 0
        self.client = None  # Inicializar siempre primero
        
        if not self.api_key:
            print("⚠️ Groq API key no encontrada en .env (usando fallback a otros modelos)")
            return
        
        try:
            self.client = Groq(api_key=self.api_key)
            print("✅ Groq client inicializado (14,400 RPD gratis)")
        except Exception as e:
            print(f"⚠️ Error inicializando Groq: {e}")
            print("   Usando fallback a GitHub Models / Ollama")
            self.client = None
    
    def chat(self, messages, temperature=0.7, max_tokens=4000):
        """Realiza consulta a Groq (ultra rápido)"""
        if not self.client:
            return None
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extraer tokens usados
            if hasattr(response, 'usage'):
                self.last_tokens_used = response.usage.total_tokens
            else:
                self.last_tokens_used = 0
            
            return response.choices[0].message.content
            
        except Exception as e:
            error_msg = str(e)
            # Detectar rate limit
            if '429' in error_msg or 'rate_limit' in error_msg.lower():
                print("⚠️ Groq rate limit alcanzado (30 RPM)")
                print("   Fallback automático activado")
                return None
            print(f"Error Groq: {error_msg}")
            return None
    
    def is_available(self):
        """Verifica si Groq está disponible"""
        if not self.client:
            return False
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            return True
        except:
            return False


# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# DETECTOR DE INTENCIONES
# ═══════════════════════════════════════════════════════════════

class CorrectorOrtografico:
    """Detecta errores ortográficos y responde con estilo directo"""
    
    def __init__(self):
        self.spell = SpellChecker(language='es')
        # Palabras técnicas/slang que no son errores
        self.whitelist = {
            'wey', 'raymundo', 'whatsapp', 'ok', 'xd', 'lol', 'wtf',
            'omg', 'hola', 'gracias', 'pendejo', 'chido', 'ñ'
        }
    
    def tiene_errores(self, texto):
        """Detecta si hay errores ortográficos significativos"""
        # Remover URLs, menciones, comandos
        texto_limpio = re.sub(r'http[s]?://\S+', '', texto)
        texto_limpio = re.sub(r'@\S+', '', texto_limpio)
        texto_limpio = re.sub(r'/\S+', '', texto_limpio)
        
        palabras = texto_limpio.lower().split()
        errores = []
        
        for palabra in palabras:
            # Limpiar puntuación
            palabra_limpia = re.sub(r'[^a-záéíóúñü]', '', palabra)
            if len(palabra_limpia) < 3:
                continue
            if palabra_limpia in self.whitelist:
                continue
            
            # Verificar si está mal escrita
            if palabra_limpia and palabra_limpia not in self.spell:
                correccion = self.spell.correction(palabra_limpia)
                if correccion and correccion != palabra_limpia:
                    errores.append((palabra_limpia, correccion))
        
        return errores
    

class WebScraper:
    """Obtiene información de páginas web"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def extraer_url(self, texto):
        """Extrae URLs del mensaje"""
        patron = r'https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
        urls = re.findall(patron, texto)
        return [url if url.startswith('http') else f'https://{url}' for url in urls]
    
    def scrape(self, url):
        """Obtiene contenido de una URL"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remover scripts, estilos
            for script in soup(["script", "style", "nav", "footer"]):
                script.decompose()
            
            # Extraer información relevante
            titulo = soup.find('title')
            titulo_texto = titulo.get_text() if titulo else "Sin título"
            
            # Meta descripción
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            descripcion = meta_desc.get('content', '') if meta_desc else ''
            
            # Texto principal
            texto = soup.get_text(separator='\n', strip=True)
            # Limitar a 2000 caracteres
            texto = '\n'.join([line for line in texto.split('\n') if line])[:2000]
            
            return {
                'success': True,
                'url': url,
                'titulo': titulo_texto,
                'descripcion': descripcion,
                'contenido': texto
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Error al acceder a {url}: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Error procesando página: {str(e)}'
            }


class EmojiProcessor:
    """Procesa y explica emojis en el texto"""
    
    def procesar(self, texto):
        """Convierte emojis a descripción textual"""
        # Extraer emojis
        emojis_encontrados = [c for c in texto if c in emoji.EMOJI_DATA]
        
        if emojis_encontrados:
            # Crear versión con descripciones
            texto_con_desc = emoji.demojize(texto, delimiters=("", ""))
            return {
                'tiene_emojis': True,
                'emojis': emojis_encontrados,
                'texto_original': texto,
                'texto_procesado': texto_con_desc
            }
        
        return {
            'tiene_emojis': False,
            'texto_procesado': texto
        }


class DetectorIntenciones:
    """Detecta qué quiere hacer el usuario"""
    
    KEYWORDS_PRESENTACION = [
        'presentación', 'presentacion', 'slides', 'diapositivas',
        'ppt', 'powerpoint', 'exponer', 'exposición', 'exposicion',
        'pitch', 'presentar', 'haz una presentación', 'haz una presentacion',
        'crea una presentación', 'crea una presentacion', 'genera una presentación',
        'genera una presentacion', 'quiero una presentación', 'necesito una presentación',
        'presentación de', 'presentacion de', 'presentación sobre', 'presentacion sobre'
    ]
    
    KEYWORDS_DOCUMENTO = [
        'documento', 'doc', 'escribir', 'redactar', 'texto',
        'informe', 'reporte', 'nota', 'artículo', 'articulo',
        'crea un documento', 'genera un documento', 'haz un documento',
        'documento sobre', 'documento de'
    ]
    
    KEYWORDS_HOJA_CALCULO = [
        'hoja de cálculo', 'hoja de calculo', 'spreadsheet', 'excel',
        'tabla de datos', 'tabla', 'datos', 'xlsx',
        'crea una hoja', 'genera una hoja', 'haz una hoja',
        'hoja con datos', 'registro de'
    ]
    
    KEYWORDS_IMAGENES = [
        'imagen', 'imágenes', 'imagenes', 'foto', 'fotos',
        'analiza imagen', 'analiza la imagen', 'qué hay en la imagen',
        'describe imagen', 'describe la imagen', 'lee la imagen'
    ]
    
    KEYWORDS_DOCUMENTOS_ANALISIS = [
        'lee el documento', 'lee este documento', 'analiza el documento',
        'resume el documento', 'qué dice el documento', 'que dice el documento',
        'lee el pdf', 'lee este pdf', 'lee el archivo',
        'resume este', 'analiza este', 'extrae del documento'
    ]
    
    KEYWORDS_WEB_SCRAPING = [
        'qué es', 'que es', 'información sobre', 'informacion sobre',
        'busca', 'investiga', 'dime sobre', 'cuéntame de', 'cuentame de',
        '.com', '.mx', '.org', '.net', 'http', 'www', 'página', 'pagina',
        'sitio web', 'website'
    ]
    
    def detectar(self, mensaje):
        """Detecta la intención del mensaje"""
        mensaje_lower = mensaje.lower()
        
        scores = {
            'presentacion': self._contar_keywords(mensaje_lower, self.KEYWORDS_PRESENTACION),
            'documento': self._contar_keywords(mensaje_lower, self.KEYWORDS_DOCUMENTO),
            'hoja_calculo': self._contar_keywords(mensaje_lower, self.KEYWORDS_HOJA_CALCULO),
            'imagenes': self._contar_keywords(mensaje_lower, self.KEYWORDS_IMAGENES),
            'analisis_documento': self._contar_keywords(mensaje_lower, self.KEYWORDS_DOCUMENTOS_ANALISIS),
            'web_scraping': self._contar_keywords(mensaje_lower, self.KEYWORDS_WEB_SCRAPING),
        }
        
        intencion_principal = max(scores, key=scores.get)
        confianza = scores[intencion_principal] / 10.0
        
        if confianza < 0.3:
            return {
                'intencion': 'chat',
                'confianza': 1.0,
                'tema': mensaje,
                'detalles': {}
            }
        
        tema = self._extraer_tema(mensaje, intencion_principal)
        detalles = self._extraer_detalles(mensaje, intencion_principal)
        
        return {
            'intencion': intencion_principal,
            'confianza': min(confianza, 1.0),
            'tema': tema,
            'detalles': detalles
        }
    
    def _contar_keywords(self, texto, keywords):
        count = 0
        for keyword in keywords:
            if keyword in texto:
                if ' ' in keyword:  # Frase completa
                    count += 5
                else:  # Palabra
                    count += 2
        return count
    
    def _extraer_tema(self, mensaje, intencion):
        patrones = [
            r'sobre (.+?)(?:\.|$)',
            r'de (.+?)(?:\.|$)',
            r'acerca de (.+?)(?:\.|$)',
        ]
        
        for patron in patrones:
            match = re.search(patron, mensaje, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return mensaje
    
    def _extraer_detalles(self, mensaje, intencion):
        detalles = {}
        
        if intencion == 'presentacion':
            match_slides = re.search(r'(\d+)\s*(?:diapositiva|slide)', mensaje, re.IGNORECASE)
            if match_slides:
                detalles['num_slides'] = int(match_slides.group(1))
            else:
                detalles['num_slides'] = 5
            
            detalles['con_imagenes'] = any(word in mensaje.lower() 
                                          for word in ['imagen', 'foto', 'ilustr', 'visual'])
            
            if any(word in mensaje.lower() for word in ['profesional', 'formal', 'negocio']):
                detalles['estilo'] = 'profesional'
            elif any(word in mensaje.lower() for word in ['creativ', 'modern', 'colorid']):
                detalles['estilo'] = 'creativo'
            else:
                detalles['estilo'] = 'profesional'
        
        return detalles


# ═══════════════════════════════════════════════════════════════
# PROCESADORES
# ═══════════════════════════════════════════════════════════════

class VisionProcessor:
    """Procesa imágenes con GPT-4o Vision"""
    
    def __init__(self, github_client):
        self.github_client = github_client
        self.supported_formats = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
    
    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def analyze_image(self, image_path, prompt="Describe esta imagen en detalle"):
        if not Path(image_path).exists():
            return "❌ Imagen no encontrada"
        
        try:
            base64_image = self.encode_image(image_path)
            
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }}
                ]
            }]
            
            return self.github_client.chat_with_images(messages, max_tokens=1000)
        except Exception as e:
            return f"❌ Error: {str(e)}"


class DocumentProcessor:
    """Procesa documentos PDF, DOCX, TXT"""
    
    def __init__(self):
        self.max_chars = 50000
    
    def read_txt(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()[:self.max_chars]
            return {'success': True, 'content': content, 'format': 'text'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def read_pdf(self, file_path):
        try:
            import PyPDF2
            text = ""
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages[:50]:
                    text += page.extract_text() + "\n\n"
                    if len(text) > self.max_chars:
                        break
            return {'success': True, 'content': text[:self.max_chars], 'format': 'pdf'}
        except ImportError:
            return {'success': False, 'error': 'Instala PyPDF2: pip install pypdf2'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def process_document(self, file_path):
        ext = Path(file_path).suffix.lower()
        if ext in ['.txt', '.md']:
            return self.read_txt(file_path)
        elif ext == '.pdf':
            return self.read_pdf(file_path)
        return {'success': False, 'error': 'Formato no soportado'}


class MemorySystem:
    """Sistema de memoria contextual"""
    
    def __init__(self, memory_file=None):
        default_memory = DATA_DIR / "memoria_agente.json"
        self.memory_file = Path(memory_file) if memory_file else default_memory
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.memory = {
            'documents': [],
            'images': [],
            'vocabulario_usuario': {},
            'max_items': 20
        }
        self.load_memory()
    
    def load_memory(self):
        try:
            if self.memory_file.exists():
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    self.memory = json.load(f)
        except:
            pass
    
    def save_memory(self):
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    def add_document(self, file_path, content, summary=""):
        doc_entry = {
            'filename': Path(file_path).name,
            'content': content[:5000],
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        }
        self.memory['documents'].append(doc_entry)
        if len(self.memory['documents']) > self.memory['max_items']:
            self.memory['documents'] = self.memory['documents'][-self.memory['max_items']:]
        self.save_memory()
    
    def add_image(self, file_path, description=""):
        img_entry = {
            'filename': Path(file_path).name,
            'description': description,
            'timestamp': datetime.now().isoformat()
        }
        self.memory['images'].append(img_entry)
        if len(self.memory['images']) > self.memory['max_items']:
            self.memory['images'] = self.memory['images'][-self.memory['max_items']:]
        self.save_memory()
    
    def aprender_vocabulario(self, mensaje_usuario):
        """Aprende palabras y frases del usuario para usarlas después"""
        # Extraer palabras clave (3+ caracteres, no comunes)
        palabras_comunes = {'que', 'para', 'con', 'por', 'una', 'los', 'las', 'del', 'como', 'sobre', 'esto', 'eso'}
        palabras = mensaje_usuario.lower().split()
        
        for palabra in palabras:
            palabra_limpia = re.sub(r'[^a-záéíóúñ]', '', palabra)
            if len(palabra_limpia) >= 3 and palabra_limpia not in palabras_comunes:
                if palabra_limpia not in self.memory['vocabulario_usuario']:
                    self.memory['vocabulario_usuario'][palabra_limpia] = 1
                else:
                    self.memory['vocabulario_usuario'][palabra_limpia] += 1
        
        # Mantener solo las 100 palabras más usadas
        if len(self.memory['vocabulario_usuario']) > 100:
            sorted_vocab = sorted(
                self.memory['vocabulario_usuario'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:100]
            self.memory['vocabulario_usuario'] = dict(sorted_vocab)
        
        self.save_memory()
    
    def get_vocabulario_frecuente(self, top_n=10):
        """Obtiene las palabras más usadas por el usuario"""
        sorted_vocab = sorted(
            self.memory['vocabulario_usuario'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        return [word for word, count in sorted_vocab]


# ═══════════════════════════════════════════════════════════════
# GESTOR DE HERRAMIENTAS
# ═══════════════════════════════════════════════════════════════

class GestorHerramientas:
    """Orquesta todas las herramientas del agente"""
    
    def __init__(self, ollama, github, google=None, groq=None):
        self.ollama = ollama
        self.github = github
        self.groq_client = groq  # Nuevo: Groq como primario
        self.google = google
        self.detector = DetectorIntenciones()
        self.vision = VisionProcessor(github)
        self.docs = DocumentProcessor()
        self.memory = MemorySystem()
        self.scraper = WebScraper()
        self.emoji_processor = EmojiProcessor()
        self.rate_limit_hit = False  # Flag para detectar rate limit
        self.rate_limit_hit = False  # Flag para detectar rate limit
    
    def procesar_mensaje(self, mensaje):
        """Procesa mensaje y detecta intenciones"""
        # 1. PROCESAR EMOJIS
        resultado_emoji = self.emoji_processor.procesar(mensaje)
        mensaje_procesado = resultado_emoji['texto_procesado']
       
        
        # 3. DETECTAR INTENCIÓN
        resultado_intencion = self.detector.detectar(mensaje_procesado)
        
        if resultado_intencion['confianza'] >= 0.7:
            intencion = resultado_intencion['intencion']
            
            if intencion == 'presentacion' and self.google:
                tema = resultado_intencion.get('tema', mensaje)
                detalles = resultado_intencion.get('detalles', {})
                resultado_pres = self.crear_presentacion(tema, detalles)
                return {
                    'ejecuto_herramienta': True, 
                    'tipo': 'presentacion',
                    'resultado': resultado_pres['texto'],
                    'archivo': resultado_pres.get('archivo')
                }
            
            elif intencion == 'documento' and self.google:
                tema = resultado_intencion.get('tema', mensaje)
                detalles = resultado_intencion.get('detalles', {})
                resultado_doc = self.crear_documento(tema, detalles)
                return {
                    'ejecuto_herramienta': True,
                    'tipo': 'documento',
                    'resultado': resultado_doc['texto'],
                    'archivo': resultado_doc.get('archivo')
                }
            
            elif intencion == 'hoja_calculo' and self.google:
                tema = resultado_intencion.get('tema', mensaje)
                detalles = resultado_intencion.get('detalles', {})
                resultado_sheet = self.crear_hoja_calculo(tema, detalles)
                return {
                    'ejecuto_herramienta': True,
                    'tipo': 'hoja_calculo',
                    'resultado': resultado_sheet['texto'],
                    'archivo': resultado_sheet.get('archivo')
                }
            
            elif intencion == 'imagenes':
                if self._tiene_ruta_archivo(mensaje):
                    path = self._extraer_ruta(mensaje)
                    if Path(path).exists():
                        resultado = self.vision.analyze_image(path, mensaje)
                        self.memory.add_image(path, resultado[:500])
                        return {'ejecuto_herramienta': True, 'tipo': 'vision',
                               'resultado': f"🖼️ **{Path(path).name}**\n\n{resultado}"}
            
            elif intencion == 'analisis_documento':
                if self._tiene_ruta_archivo(mensaje_procesado):
                    path = self._extraer_ruta(mensaje_procesado)
                    if Path(path).exists():
                        doc = self.docs.process_document(path)
                        if doc['success']:
                            self.memory.add_document(path, doc['content'])
                            return {'ejecuto_herramienta': True, 'tipo': 'documento',
                                   'resultado': f"📄 **{Path(path).name}** cargado en memoria"}
            
            elif intencion == 'web_scraping':
                urls = self.scraper.extraer_url(mensaje)
                if urls:
                    resultado_web = self.buscar_en_web(urls[0], mensaje_procesado)
                    return {
                        'ejecuto_herramienta': True,
                        'tipo': 'web_scraping',
                        'resultado': resultado_web
                    }
        
        return {'ejecuto_herramienta': False}
    
    def crear_presentacion(self, tema, detalles):
        """Crea presentación con Google Slides con contenido e imágenes generadas por IA"""
        if not self.google:
            return {"texto": "❌ Google Slides no configurado", "archivo": None}
        
        try:
            num_slides = detalles.get('num_slides', 5)
            
            # Obtener personalidad actual
            tono_actual = config_agente.get_tono()
            nombre_agente = config_agente.get_nombre_agente()
            
            # Ajustar instrucciones según personalidad
            if tono_actual == 'puteado':
                instrucciones_estilo = """- ESTILO rAI: Escribe con faltas de ortografia, usa "k", "naco", "cabrón", "estúpido", "imbecil", "puto", "wey", "chingon", "verga", "alv", etc.
- USA lenguaje informal, muy agresivo pero informativo
- Ejemplo: "• ps este punto ta bien perro, no mames wey, es super importante pa entender la verga"
- Mantén el tono naco y directo en TODO el contenido"""
            else:
                instrucciones_estilo = """- ESTILO Amigable: Escribe correctamente, profesional pero cercano
- Usa lenguaje claro, motivador y accesible
- Ejemplo: "• Este punto es fundamental para comprender el concepto 💡"
- Mantén el tono profesional y positivo en TODO el contenido"""
            
            # Paso 1: Generar esquema completo de la presentación con IA
            print(f"🤖 Generando contenido para {num_slides} diapositivas...")
            
            prompt_contenido = f"""Actúa como {nombre_agente}, un conferencista experto. Diseña una presentación profesional sobre: {tema}

{instrucciones_estilo}

Devuelve exclusivamente un JSON válido con esta estructura:

{{
    "titulo_presentacion": "Título impactante y profesional",
    "subtitulo_presentacion": "Subtítulo descriptivo (opcional)",
    "diapositivas": [
        {{
            "tipo": "portada|contenido|conclusion",
            "titulo": "Título de la diapositiva",
            "contenido": "Contenido de la slide",
            "tiene_imagen": true/false,
            "keywords_imagen": "keywords en inglés"
        }}
    ]
}}

REGLAS ESTRICTAS:

📊 ESTRUCTURA (Exactamente {num_slides} diapositivas):
1. Primera slide (tipo: "portada"): 
   - Solo título y subtítulo de la presentación
   - NO incluir contenido adicional
   - tiene_imagen: false

2. Slides intermedias (tipo: "contenido"):
   - Título descriptivo en 4-7 palabras
   - Contenido VARIADO en cada slide:
     * Algunas slides: Solo párrafos (2-3 párrafos de 40-60 palabras c/u)
     * Otras slides: Solo viñetas (• Punto 1\n• Punto 2\n• Punto 3\n• Punto 4)
     * Algunas slides: Combinación (Párrafo introductorio + viñetas)
   - Incluir datos específicos, estadísticas, ejemplos concretos
   - tiene_imagen: true (para agregar imagen relevante)

3. Última slide (tipo: "conclusion"):
   - Título: "Conclusión" o "Para Concluir" o similar
   - Contenido: Resumen ejecutivo en párrafos (3-4 oraciones impactantes)
   - Incluir llamado a la acción o reflexión final
   - tiene_imagen: true

📝 FORMATO DE CONTENIDO:
- Párrafos: Texto corrido, sin viñetas, explicativo y detallado
- Viñetas: Iniciar con "• ", 12-20 palabras cada una, concisas
- Combinación: Párrafo (30-50 palabras) + 3-4 viñetas
- Usa saltos de línea (\n\n) entre párrafos

🖼️ IMÁGENES:
- keywords_imagen: 2-4 palabras en inglés, conceptuales y descriptivas
- Evitar keywords genéricas, ser específico al tema de la slide

💡 CALIDAD:
- Contenido profundo y educativo, no superficial
- Datos específicos, nombres propios, fechas cuando sean relevantes
- Variación en el formato entre slides para mantener interés

Sin markdown extra, sin explicaciones fuera del JSON."""

            # Generar con Groq (rápido y confiable)
            respuesta_ia = self.groq_client.chat(
                [{"role": "user", "content": prompt_contenido}],
                temperature=0.5
            )
            
            # Parsear JSON
            import re
            
            # Limpiar respuesta (por si hay texto antes/después del JSON)
            json_match = re.search(r'\{[\s\S]*\}', respuesta_ia)
            if json_match:
                respuesta_ia = json_match.group(0)
            respuesta_ia = self._normalizar_json_respuesta(respuesta_ia)
            
            esquema = json.loads(respuesta_ia)
            
            titulo_final = esquema.get('titulo_presentacion', f"{tema} - Presentación")
            subtitulo_presentacion = esquema.get('subtitulo_presentacion', '')
            diapositivas_data = esquema.get('diapositivas', [])
            tema_visual = self._seleccionar_tema_visual(tema)
            
            print(f"✅ Esquema generado: {len(diapositivas_data)} diapositivas")
            
            # Paso 2: Buscar imágenes para cada diapositiva (solo si tiene_imagen=true)
            diapositivas_completas = []
            for idx, diapo in enumerate(diapositivas_data, 1):
                tipo_slide = diapo.get('tipo', 'contenido')
                tiene_imagen = diapo.get('tiene_imagen', False)
                imagen_url = None
                
                # Buscar imagen solo si la slide la necesita
                if tiene_imagen:
                    print(f"🖼️  Buscando imagen para diapositiva {idx} ({tipo_slide})...")
                    keywords = diapo.get('keywords_imagen', tema.split()[0])
                    imagen_url = self.google.buscar_imagen_web(keywords)
                else:
                    print(f"📄 Diapositiva {idx} ({tipo_slide}) - sin imagen")
                
                diapositivas_completas.append({
                    'tipo': tipo_slide,
                    'titulo': diapo.get('titulo', f'Diapositiva {idx}'),
                    'contenido': diapo.get('contenido', ''),
                    'imagen_url': imagen_url,
                    'subtitulo': subtitulo_presentacion if tipo_slide == 'portada' else None
                })
            
            # Paso 3: Crear presentación con todo el contenido
            print(f"🎨 Creando presentación en Google Slides...")
            pres = self.google.crear_presentacion(
                titulo=titulo_final,
                diapositivas=diapositivas_completas,
                tema_visual=tema_visual
            )
            
            # Verificar errores
            if pres and 'error' in pres:
                if pres['error'] == 'PERMISSION_DENIED':
                    mensaje_error = f"""❌ Service Account sin permisos

🔧 **SOLUCIÓN (2 minutos)**:

1️⃣ Abre este link:
   {pres.get('link', 'https://console.cloud.google.com/iam-admin/iam?project=trace-cf294')}

2️⃣ Busca esta cuenta:
   📧 trace-cf294@appspot.gserviceaccount.com

3️⃣ Haz click en el ícono de **lápiz** (Edit)

4️⃣ Click en **"+ ADD ANOTHER ROLE"**

5️⃣ Selecciona: **"Editor"** (o "Google Workspace Admin")

6️⃣ Click en **"Save"**

7️⃣ Espera 30 segundos y vuelve a intentar

💡 Esto da permisos al Service Account para crear archivos en Google Workspace."""
                    return {"texto": mensaje_error, "archivo": None}
                elif pres['error'] == 'API_NOT_ENABLED':
                    mensaje_error = f"""❌ Google Slides API no habilitada

🔧 **SOLUCIÓN (1 minuto)**:

1️⃣ Abre este link:
   {pres.get('link', 'https://console.cloud.google.com/apis/library/slides.googleapis.com')}

2️⃣ Haz click en **"ENABLE"** (Habilitar)

3️⃣ Espera 1-2 minutos y vuelve a intentar

💡 Solo se hace una vez."""
                    return {"texto": mensaje_error, "archivo": None}
                else:
                    return {"texto": f"❌ Error: {pres.get('message', 'Error desconocido')}", "archivo": None}
            
            if pres and 'id' in pres:
                respuesta_texto = f"""✅ Presentación creada con éxito

🔗 **URL**: {pres['url']}

📊 **Detalles**:
• Tema: {titulo_final}
• Diapositivas: {len(diapositivas_completas)} (con contenido e imágenes)
• Estilo: {tema_visual.get('nombre_mostrable', 'Moderno')}

📎 Te envío el archivo PPTX..."""
                return {
                    "texto": respuesta_texto,
                    "archivo": {
                        "presentation_id": pres['id'],
                        "titulo": titulo_final,
                        "tipo": "presentacion"
                    }
                }
            
            return {"texto": "❌ Error al crear presentación", "archivo": None}
            
        except json.JSONDecodeError as e:
            print(f"❌ Error al parsear JSON de IA: {e}")
            try:
                print(f"Respuesta IA: {respuesta_ia[:500]}...")
            except NameError:
                print("Respuesta IA no disponible (falló antes de asignarse)")
            return {"texto": f"❌ Error: La IA no generó un formato válido. Por favor intenta de nuevo.", "archivo": None}
    
    def crear_documento(self, tema, detalles):
        """Crea documento con Google Docs"""
        if not self.google:
            return {"texto": "❌ Google Docs no configurado", "archivo": None}
        
        try:
            # Obtener personalidad actual
            tono_actual = config_agente.get_tono()
            nombre_agente = config_agente.get_nombre_agente()
            
            # Ajustar instrucciones según personalidad
            if tono_actual == 'puteado':
                instrucciones_estilo = """IMPORTANTE: Escribe como rAI - usa faltas de ortografia intencionadas:
- "ke" en vez de "que", "ps" en vez de "pues", "kon" en vez de "con"
- Usa: wey, chingon, verga, alv, nmms, bien perro
- Tono agresivo pero informativo: "oye wey ps el tema ta kabron pero te lo explico"
- Ejemplo: "ps mira wey, este documento ta bien chingon pa ke entiendas la verga del tema..."""
            else:
                instrucciones_estilo = """IMPORTANTE: Escribe profesionalmente:
- Ortografía correcta y lenguaje formal
- Tono amigable, claro y motivador
- Usa emojis ocasionalmente 💡
- Ejemplo: "¡Hola! Este documento te ayudará a comprender el tema de manera clara y precisa."""
            
            # Paso 1: GPT-4o genera el contenido del documento
            prompt = f"""Eres {nombre_agente}. Escribe un documento sobre: {tema}
            
{instrucciones_estilo}

Requisitos:
- Título llamativo
- Introducción clara
- Desarrollo bien estructurado
- Conclusión
- Usa formato markdown con # para títulos
- Longitud: {detalles.get('longitud', 'media')}
- MANTÉN el estilo de personalidad en TODO el documento
"""
            
            contenido = self.github.chat(
                prompt,
                temperature=0.7,
                max_tokens=2000
            )
            
            # Paso 2: Crear documento en Google Docs
            doc = self.google.crear_documento(f"{tema} - Documento", contenido)
            
            if doc:
                respuesta_texto = f"""✅ Documento creado con éxito

🔗 **URL**: {doc['url']}

📄 **Detalles**:
• Tema: {tema[:100]}...
• Palabras: ~{len(contenido.split())}

📎 Te envío el archivo DOCX..."""
                return {
                    "texto": respuesta_texto,
                    "archivo": {
                        "document_id": doc['id'],
                        "titulo": f"{tema} - Documento",
                        "tipo": "documento"
                    }
                }
            
            if not self.google or not self.google.is_available():
                return {"texto": "❌ Google Workspace no configurado", "archivo": None}
            
            return {"texto": "❌ Error al crear documento (verifica permisos de Google API)", "archivo": None}
        except Exception as e:
            return {"texto": f"❌ Error: {str(e)}", "archivo": None}
    
    def crear_hoja_calculo(self, tema, detalles):
        """Crea hoja de cálculo con Google Sheets"""
        if not self.google:
            return {"texto": "❌ Google Sheets no configurado", "archivo": None}
        
        try:
            # Obtener personalidad actual
            tono_actual = config_agente.get_tono()
            nombre_agente = config_agente.get_nombre_agente()
            
            # Ajustar instrucciones según personalidad
            if tono_actual == 'puteado':
                instrucciones_estilo = "Los nombres de columnas pueden tener jerga: ej. 'nombre_verga', 'precio_chingon', 'fecha_perro'"
            else:
                instrucciones_estilo = "Los nombres de columnas deben ser profesionales y claros"
            
            # Paso 1: GPT-4o genera la estructura de datos
            prompt = f"""Eres {nombre_agente}. Genera una estructura de hoja de cálculo sobre: {tema}
            
{instrucciones_estilo}

Dame:
1. Nombres de columnas (separadas por comas)
2. 5 filas de ejemplo con datos realistas

Formato:
COLUMNAS: col1, col2, col3
FILA1: dato1, dato2, dato3
FILA2: dato1, dato2, dato3
...
"""
            
            estructura = self.github.chat(
                prompt,
                temperature=0.5,
                max_tokens=1000
            )
            
            # Paso 2: Crear hoja en Google Sheets
            sheet = self.google.crear_hoja_calculo(f"{tema} - Datos")
            
            if sheet:
                respuesta_texto = f"""✅ Hoja de cálculo creada con éxito

🔗 **URL**: {sheet['url']}

📊 **Detalles**:
• Tema: {tema[:100]}...
• Estructura generada automáticamente

📎 Te envío el archivo XLSX..."""
                return {
                    "texto": respuesta_texto,
                    "archivo": {
                        "spreadsheet_id": sheet['id'],
                        "titulo": f"{tema} - Datos",
                        "tipo": "hoja_calculo"
                    }
                }
            
            if not self.google or not self.google.is_available():
                return {"texto": "❌ Google Workspace no configurado", "archivo": None}
            
            return {"texto": "❌ Error al crear hoja de cálculo (verifica permisos de Google API)", "archivo": None}
        except Exception as e:
            return {"texto": f"❌ Error: {str(e)}", "archivo": None}
    
    def buscar_en_web(self, url, pregunta):
        """Busca información en una URL y la analiza con AI"""
        resultado = self.scraper.scrape(url)
        
        if not resultado['success']:
            return f"❌ {resultado['error']}"
        
        # Usar GPT-4o para analizar el contenido
        prompt = f"""Analiza esta página web y responde la pregunta del usuario.

Página: {resultado['titulo']}
URL: {resultado['url']}
Descripción: {resultado['descripcion']}

Contenido:
{resultado['contenido'][:1500]}

Pregunta del usuario: {pregunta}

Responde de forma clara y concisa."""
        
        respuesta = self.github.chat(prompt, temperature=0.7, max_tokens=500)
        
        return f"""🌐 **Información de {resultado['url']}**

📄 **{resultado['titulo']}**

{respuesta}"""
    def _seleccionar_tema_visual(self, tema):
        """Define paletas visuales según el tema solicitado"""
        tema_lower = (tema or '').lower()
        paletas = [
            {
                'nombre': 'tech_ocean',
                'nombre_mostrable': 'Tech Ocean',
                'keywords': ['ia', 'ai', 'inteligencia artificial', 'tecnolog', 'software', 'cloud', 'data', 'robot'],
                'color_fondo': {'red': 0.07, 'green': 0.11, 'blue': 0.24},
                'estilos_titulo': {
                    'color': {'red': 0.95, 'green': 0.97, 'blue': 0.99},
                    'fuente': 'Montserrat',
                    'tamano': 36,
                    'bold': True
                },
                'estilos_contenido': {
                    'color': {'red': 0.85, 'green': 0.89, 'blue': 0.95},
                    'fuente': 'Open Sans',
                    'tamano': 20
                }
            },
            {
                'nombre': 'business_coral',
                'nombre_mostrable': 'Business Coral',
                'keywords': ['marketing', 'ventas', 'negocio', 'estrategia', 'finanzas', 'liderazgo', 'startup'],
                'color_fondo': {'red': 0.9, 'green': 0.36, 'blue': 0.2},
                'estilos_titulo': {
                    'color': {'red': 1, 'green': 0.97, 'blue': 0.95},
                    'fuente': 'Playfair Display',
                    'tamano': 34,
                    'bold': True
                },
                'estilos_contenido': {
                    'color': {'red': 1, 'green': 0.96, 'blue': 0.92},
                    'fuente': 'Lato',
                    'tamano': 20
                }
            },
            {
                'nombre': 'eco_fresh',
                'nombre_mostrable': 'Eco Fresh',
                'keywords': ['sostenibilidad', 'medio ambiente', 'salud', 'educación', 'agricultura', 'turismo'],
                'color_fondo': {'red': 0.1, 'green': 0.35, 'blue': 0.22},
                'estilos_titulo': {
                    'color': {'red': 0.9, 'green': 0.98, 'blue': 0.92},
                    'fuente': 'Poppins',
                    'tamano': 34,
                    'bold': True
                },
                'estilos_contenido': {
                    'color': {'red': 0.86, 'green': 0.95, 'blue': 0.89},
                    'fuente': 'Nunito',
                    'tamano': 20
                }
            }
        ]
        for palette in paletas:
            for keyword in palette['keywords']:
                if keyword in tema_lower:
                    return palette
        return {
            'nombre': 'modern_neutral',
            'nombre_mostrable': 'Modern Neutral',
            'color_fondo': {'red': 0.16, 'green': 0.18, 'blue': 0.2},
            'estilos_titulo': {
                'color': {'red': 0.97, 'green': 0.97, 'blue': 0.97},
                'fuente': 'Montserrat',
                'tamano': 34,
                'bold': True
            },
            'estilos_contenido': {
                'color': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
                'fuente': 'Inter',
                'tamano': 20
            }
        }

    def _normalizar_json_respuesta(self, texto):
        """Escapa saltos de línea dentro de strings para poder parsear JSON"""
        if not texto:
            return texto
        resultado = []
        dentro = False
        escape = False
        for char in texto:
            if char == '"' and not escape:
                dentro = not dentro
                resultado.append(char)
                continue
            if char == '\\' and not escape:
                escape = True
                resultado.append(char)
                continue
            if escape:
                resultado.append(char)
                escape = False
                continue
            if dentro and char in ['\n', '\r']:
                resultado.append('\\n')
                continue
            resultado.append(char)
        return ''.join(resultado)
    
    def _tiene_ruta_archivo(self, texto):
        return bool(re.search(r'[a-zA-Z]:[\\\/][^\s]+', texto))
    
    def _extraer_ruta(self, texto):
        match = re.search(r'[a-zA-Z]:[\\\/][^\s]+', texto)
        return match.group(0).strip('\'"') if match else ""
    
    def chat_hibrido(self, mensaje):
        """
        Chat híbrido optimizado con Groq:
        1. Groq genera respuesta (ultra rápido, 14,400 RPD gratis)
        2. Fallback a GitHub Models si Groq falla
        3. Fallback a Ollama local si todo falla
        """
        # Obtener prompt del sistema desde config global
        prompt_sistema = config_agente.get('personalidad', {}).get('prompt_sistema', 
            'Eres un asistente útil y amigable.')
        
        # Construir mensajes
        messages = [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": mensaje}
        ]
        
        # Paso 1: Intentar Groq primero (14,400 RPD gratis, ultra rápido)
        if self.groq_client and self.groq_client.client:
            respuesta_groq = self.groq_client.chat(messages, temperature=0.7)
            
            if respuesta_groq:
                return respuesta_groq
            else:
                # Groq falló (rate limit o error), intentar GitHub Models
                print("⚠️ Groq no disponible, intentando GitHub Models...")
        
        # Paso 2: Fallback a GitHub Models
        if self.github and self.github.client:
            respuesta_gpt = self.github.chat(messages, temperature=0.7)
            
            if respuesta_gpt:
                return respuesta_gpt
            else:
                print("⚠️ GitHub Models no disponible (rate limit excedido)...")
        
        # Paso 3: Último fallback - Ollama local (ilimitado)
        print("🔄 Usando Ollama local como último recurso...")
        respuesta_ollama = self.ollama.generate(
            f"{prompt_sistema}\n\nUsuario: {mensaje}\nAsistente:",
            temperature=0.7,
            max_tokens=500
        )
        
        return f"⚠️ *[Modo local - APIs no disponibles]*\n\n{respuesta_ollama or 'Error al conectar con Ollama'}"


# ═══════════════════════════════════════════════════════════════
# INTERFAZ GRÁFICA
# ═══════════════════════════════════════════════════════════════

class ChatGUI:
    """Interfaz gráfica estilo ChatGPT"""
    
    def __init__(self, root):
        self.root = root
        nombre = config_agente.get_nombre_agente()
        self.root.title(f"🤖 {nombre} - IA Unificada")
        
        self.root.geometry("1100x800")
        self.root.configure(bg='#212121')
        self.root.minsize(900, 600)
        
        # Inicializar componentes
        cfg = AppConfig()
        self.ollama = OllamaClient(cfg.ollama_url, cfg.ollama_model)
        self.github = GitHubModelsClient(cfg.github_token)
        self.google = cfg.google_client
        self.herramientas = GestorHerramientas(self.ollama, self.github, google=self.google)
        
        # Inicializar manejador de audio
        self.audio_handler = get_audio_handler()
        self.ultimo_audio_respuesta = None
        
        self.historial = []
        self.historial_chat = []  # Historial para mantener contexto con el modelo
        self.contador_mensajes = 0  # Contador para recordatorios de personalidad
        self.procesando = False
        self.archivo_adjunto = None
        
        self.construir_interfaz()
        self.mostrar_bienvenida()
    
    def construir_interfaz(self):
        """Construye UI estilo ChatGPT"""
        
        # Header
        header = tk.Frame(self.root, bg='#1f1f1f', height=50)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)
        
        nombre_agente = config_agente.get_nombre_agente()
        tk.Label(
            header,
            text=f"🤖 {nombre_agente} v2.0",
            font=("Segoe UI", 14, "bold"),
            bg='#1f1f1f',
            fg='#ffffff'
        ).pack(side='left', padx=20)
        
        self.label_estado = tk.Label(
            header,
            text="● Listo",
            font=("Segoe UI", 9),
            bg='#1f1f1f',
            fg='#10a37f'
        )
        self.label_estado.pack(side='right', padx=15)
        
        # Chat area
        self.text_chat = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            bg='#212121',
            fg='#ececec',
            font=("Segoe UI", 10),
            relief='flat',
            padx=20,
            pady=20,
            state='disabled'
        )
        self.text_chat.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        # Tags
        self.text_chat.tag_config('user', foreground='#ececec')
        self.text_chat.tag_config('assistant', foreground='#d4d4d4')
        self.text_chat.tag_config('user_label', foreground='#10a37f', font=("Segoe UI", 10, "bold"))
        self.text_chat.tag_config('assistant_label', foreground='#9e9e9e', font=("Segoe UI", 10, "bold"))
        
        # Input
        input_container = tk.Frame(self.root, bg='#212121')
        input_container.pack(fill='x', padx=20, pady=(0, 20))
        
        input_frame = tk.Frame(input_container, bg='#2d2d2d', relief='flat')
        input_frame.pack(fill='x')
        
        self.entry_mensaje = tk.Text(
            input_frame,
            height=1,
            bg='#2d2d2d',
            fg='#ececec',
            font=("Segoe UI", 11),
            relief='flat',
            padx=15,
            pady=12,
            wrap=tk.WORD,
            insertbackground='#ffffff'
        )
        self.entry_mensaje.pack(fill='both', expand=True, side='left')
        self.entry_mensaje.bind('<Return>', self.enviar_mensaje_enter)
        
        # Botón grabar audio
        self.btn_grabar = tk.Button(
            input_frame,
            text="🎤",
            command=self.toggle_grabacion,
            bg='#2d2d2d',
            fg='#e0e0e0',
            font=("Segoe UI", 12),
            relief='flat',
            padx=10,
            cursor='hand2'
        )
        self.btn_grabar.pack(side='right', padx=5, pady=8)
        
        # Botón reproducir audio
        self.btn_reproducir = tk.Button(
            input_frame,
            text="🔊",
            command=self.reproducir_ultima_respuesta,
            bg='#2d2d2d',
            fg='#e0e0e0',
            font=("Segoe UI", 12),
            relief='flat',
            padx=10,
            cursor='hand2',
            state='disabled'
        )
        self.btn_reproducir.pack(side='right', padx=5, pady=8)
        
        # Botón adjuntar
        tk.Button(
            input_frame,
            text="📎",
            command=self.seleccionar_archivo,
            bg='#2d2d2d',
            fg='#e0e0e0',
            font=("Segoe UI", 12),
            relief='flat',
            padx=10,
            cursor='hand2'
        ).pack(side='right', padx=5, pady=8)
        
        # Botón enviar
        tk.Button(
            input_frame,
            text="➤",
            command=self.enviar_mensaje,
            bg='#10a37f',
            fg='#ffffff',
            font=("Segoe UI", 14, "bold"),
            relief='flat',
            padx=15,
            pady=8,
            cursor='hand2',
            width=3
        ).pack(side='right', padx=8, pady=8)
    
    def toggle_grabacion(self):
        """Inicia o detiene la grabación de audio"""
        if not self.audio_handler.is_stt_available():
            messagebox.showwarning("Audio no disponible", 
                                   "El reconocimiento de voz no está disponible.\n"
                                   "Instala las dependencias con:\n"
                                   "pip install openai-whisper sounddevice soundfile")
            return
        
        if not self.audio_handler.is_recording:
            # Iniciar grabación
            if self.audio_handler.start_recording(duration=30):
                self.btn_grabar.config(fg='#ff4444', text='⏹️')
                self.label_estado.config(text="🎙️ Grabando...", fg='#ff4444')
        else:
            # Detener grabación
            self.btn_grabar.config(fg='#e0e0e0', text='🎤')
            self.label_estado.config(text="⏳ Procesando audio...", fg='#ffa500')
            
            # Procesar en hilo separado
            threading.Thread(target=self._procesar_audio_grabado, daemon=True).start()
    
    def _procesar_audio_grabado(self):
        """Procesa el audio grabado y lo convierte a texto"""
        audio_file = self.audio_handler.stop_recording()
        
        if not audio_file:
            self.root.after(0, lambda: self.label_estado.config(text="❌ Error en grabación", fg='#ff4444'))
            return
        
        # Transcribir
        texto = self.audio_handler.speech_to_text(audio_file)
        
        if texto and texto.strip():
            # Insertar texto en el campo de entrada
            self.root.after(0, lambda: self.entry_mensaje.delete('1.0', tk.END))
            self.root.after(0, lambda: self.entry_mensaje.insert('1.0', texto))
            self.root.after(0, lambda: self.label_estado.config(text="✅ Texto transcrito - Procesando...", fg='#10a37f'))
            
            # Enviar automáticamente el mensaje
            self.root.after(100, self.enviar_mensaje)
        elif texto is not None:
            # Transcripción exitosa pero vacía (silencio o no reconocido)
            self.root.after(0, lambda: self.label_estado.config(text="⚠️ No se detectó habla en el audio", fg='#ffa500'))
        else:
            # Error en la transcripción
            self.root.after(0, lambda: self.label_estado.config(text="❌ No se pudo transcribir", fg='#ff4444'))
    
    def reproducir_ultima_respuesta(self):
        """Reproduce en audio la última respuesta del asistente"""
        if not self.ultimo_audio_respuesta:
            messagebox.showinfo("Sin audio", "No hay respuesta de audio disponible")
            return
        
        if not self.audio_handler.is_tts_available():
            messagebox.showwarning("Audio no disponible", 
                                   "La síntesis de voz no está disponible.\n"
                                   "Instala las dependencias con:\n"
                                   "pip install piper-tts\n"
                                   "Y descarga una voz desde el README")
            return
        
        # Reproducir en hilo separado
        threading.Thread(target=self._reproducir_audio, args=(self.ultimo_audio_respuesta,), daemon=True).start()
    
    def _reproducir_audio(self, audio_file):
        """Reproduce un archivo de audio"""
        self.root.after(0, lambda: self.label_estado.config(text="🔊 Reproduciendo...", fg='#10a37f'))
        success = self.audio_handler.play_audio(audio_file)
        
        if success:
            self.root.after(0, lambda: self.label_estado.config(text="● Listo", fg='#10a37f'))
        else:
            self.root.after(0, lambda: self.label_estado.config(text="❌ Error reproduciendo", fg='#ff4444'))
    
    def mostrar_bienvenida(self):
        nombre = config_agente.get_nombre_agente()
        
        # Verificar capacidades de audio
        audio_status = ""
        if self.audio_handler.is_tts_available():
            audio_status += "🔊 Síntesis de voz activada\n"
        if self.audio_handler.is_stt_available():
            audio_status += "🎙️ Reconocimiento de voz activado\n"
        
        mensaje = f"""Hola! Soy {nombre} ¿En qué puedo ayudarte?"""
        
        self.text_chat.config(state='normal')
        self.text_chat.insert('end', mensaje)
        self.text_chat.config(state='disabled')
    
    def seleccionar_archivo(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo",
            filetypes=[
                ("Imágenes", "*.png *.jpg *.jpeg *.gif"),
                ("Documentos", "*.pdf *.txt *.docx *.md"),
                ("Todos", "*.*")
            ]
        )
        if archivo:
            self.archivo_adjunto = archivo
            self.label_estado.config(text=f"📎 {Path(archivo).name}")
    
    def enviar_mensaje_enter(self, event):
        if not event.state & 1:
            self.enviar_mensaje()
            return 'break'
    
    def enviar_mensaje(self):
        mensaje = self.entry_mensaje.get('1.0', 'end-1c').strip()
        if not mensaje or self.procesando:
            return
        
        if self.archivo_adjunto:
            mensaje = f"{mensaje}\n\nArchivo: {self.archivo_adjunto}"
            self.archivo_adjunto = None
        
        self.entry_mensaje.delete('1.0', 'end')
        
        self.text_chat.config(state='normal')
        self.text_chat.insert('end', "\n\nTú\n", 'user_label')
        self.text_chat.insert('end', f"{mensaje}\n", 'user')
        self.text_chat.config(state='disabled')
        self.text_chat.see('end')
        
        self.procesando = True
        self.label_estado.config(text="⏳ Procesando...")
        
        threading.Thread(target=self.procesar_mensaje, args=(mensaje,), daemon=True).start()
    
    def procesar_mensaje(self, mensaje):
        try:
            # Detectar comandos de cambio de personalidad
            if mensaje.lower() in ['/puteado', '/raymundo', '/ray', '/malo']:
                respuesta = config_agente.cambiar_personalidad('puteado')
                # Limpiar historial para que la nueva personalidad tome efecto
                self.historial_chat = []
                self.contador_mensajes = 0
                respuesta += "\n\nQue pedo w soy rAI, un cabron ke no se anda kon mamadas. ke vergas kieres?"
                self.mostrar_respuesta(respuesta)
                return
            
            if mensaje.lower() in ['/amigable', '/raycito', '/bueno']:
                respuesta = config_agente.cambiar_personalidad('amigable')
                # Limpiar historial para que la nueva personalidad tome efecto
                self.historial_chat = []
                self.contador_mensajes = 0
                respuesta += "\n\n¡Hola! Ahora soy Raymundo en modo amigable 😊 ¿En qué puedo ayudarte?"
                self.mostrar_respuesta(respuesta)
                return
            
            # Detectar herramientas
            resultado_herramienta = self.herramientas.procesar_mensaje(mensaje)
            
            if resultado_herramienta['ejecuto_herramienta']:
                respuesta = resultado_herramienta['resultado']
            else:
                # Chat normal
                if self.es_mensaje_simple(mensaje):
                    respuesta = self.chat_ollama(mensaje)
                else:
                    respuesta = self.chat_hibrido(mensaje)
            
            self.mostrar_respuesta(respuesta)
        
        except Exception as e:
            self.mostrar_respuesta(f"❌ Error: {str(e)}")
        
        finally:
            self.procesando = False
            self.label_estado.config(text="● Listo")
    
    def es_mensaje_simple(self, mensaje):
        """Detecta si es mensaje simple para Ollama solo"""
        palabras_simples = ['hola', 'gracias', 'ok', 'bien', 'mal', 'adiós']
        return (len(mensaje) < 50 or 
                any(p in mensaje.lower() for p in palabras_simples))
    
    def chat_ollama(self, mensaje):
        """Chat solo con Ollama"""
        prompt_sistema = config_agente.get_prompt_sistema()
        prompt = f"{prompt_sistema}\n\nUsuario: {mensaje}\nAsistente:"
        return self.ollama.generate(prompt, temperature=0.7) or "Error al conectar con Ollama"
    
    def chat_hibrido(self, mensaje):
        """Chat híbrido: Ollama optimiza → GPT-4o responde"""
        prompt_opt = self.ollama.generate(
            f"Mejora esta pregunta: {mensaje}",
            temperature=0.3
        )
        
        # Obtener prompt del sistema
        prompt_sistema = config_agente.get_prompt_sistema()
        
        # Agregar mensaje del usuario al historial
        self.historial_chat.append({"role": "user", "content": prompt_opt or mensaje})
        self.contador_mensajes += 1
        
        # Construir mensajes con historial completo
        messages = [{"role": "system", "content": prompt_sistema}]
        
        # Agregar recordatorio de personalidad para tono "puteado" cada 5 mensajes
        tono = config_agente.config.get('personalidad', {}).get('tono', '')
        if tono == 'puteado' and self.contador_mensajes % 5 == 0:
            recordatorio = "\n\nRECORDATORIO: Mantén tu personalidad agresiva, con faltas de ortografía y groserías. NO cambies a lenguaje formal."
            messages[0]['content'] += recordatorio
        
        # Agregar historial (máximo últimos 10 mensajes para no exceder tokens)
        messages.extend(self.historial_chat[-10:])
        
        respuesta = self.github.chat(messages, temperature=0.7)
        
        # Si GPT-4o falló (rate limit), usar Ollama
        if respuesta is None:
            print("⚠️ GPT-4o no disponible (rate limit), usando Ollama...")
            respuesta_ollama = self.ollama.generate(
                f"{prompt_sistema}\n\nUsuario: {mensaje}\nAsistente:",
                temperature=0.7,
                max_tokens=500
            )
            respuesta = f"⚠️ *[Modo local - Rate limit]*\n\n{respuesta_ollama or 'Error'}"
        else:
            respuesta = respuesta or "Error al conectar con GPT-4o"
        
        # Agregar respuesta al historial
        self.historial_chat.append({"role": "assistant", "content": respuesta})
        
        # Limitar historial a últimos 20 mensajes (10 pares usuario-asistente)
        if len(self.historial_chat) > 20:
            self.historial_chat = self.historial_chat[-20:]
        
        return respuesta
    
    def mostrar_respuesta(self, respuesta):
        self.root.after(0, self._mostrar_respuesta_ui, respuesta)
    
    def _mostrar_respuesta_ui(self, respuesta):
        nombre = config_agente.get_nombre_agente()
        self.text_chat.config(state='normal')
        self.text_chat.insert('end', f"\n{nombre}\n", 'assistant_label')
        self.text_chat.insert('end', f"{respuesta}\n", 'assistant')
        self.text_chat.config(state='disabled')
        self.text_chat.see('end')
        
        # Generar audio de la respuesta en segundo plano
        if self.audio_handler.is_tts_available():
            threading.Thread(target=self._generar_audio_respuesta, args=(respuesta,), daemon=True).start()
    
    def _generar_audio_respuesta(self, texto):
        """Genera audio de la respuesta en segundo plano"""
        # Limpiar texto de emojis y caracteres especiales que pueden causar problemas
        texto_limpio = ''.join(c for c in texto if c.isalnum() or c.isspace() or c in '.,;:¿?¡!-')
        
        if len(texto_limpio) > 500:
            texto_limpio = texto_limpio[:500] + "..."
        
        audio_file = self.audio_handler.text_to_speech(texto_limpio)
        
        if audio_file:
            self.ultimo_audio_respuesta = audio_file
            self.root.after(0, lambda: self.btn_reproducir.config(state='normal'))
        else:
            self.root.after(0, lambda: self.btn_reproducir.config(state='disabled'))


def main():
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
