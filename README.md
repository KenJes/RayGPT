# Raymundo

Raymundo es un asistente de inteligencia artificial conversacional desarrollado por Axoloit. Combina multiples modelos de lenguaje con integraciones a servicios de Google Workspace, YouTube, Spotify y WhatsApp para ofrecer una plataforma unificada de automatizacion y productividad.

---

## Descripcion

Raymundo actua como asistente personal inteligente accesible desde una interfaz de escritorio o desde WhatsApp. Puede mantener conversaciones con memoria persistente por usuario, crear documentos en Google Workspace, gestionar eventos en Google Calendar, buscar videos en YouTube, controlar Spotify y analizar imagenes o archivos adjuntos.

El sistema esta disenado con una arquitectura modular: un nucleo reutilizable en `core/`, microservicios independientes en `agentes/` y un servidor Flask dedicado para la integracion con WhatsApp.

---

## Funcionalidades

### Conversacion

- Chat con memoria contextual persistente por usuario mediante SQLite.
- Dos modos de personalidad configurables por sesion: amigable y directo.
- Cambio de modo en tiempo real mediante los comandos `/amigable` y `/puteado`.
- Aprendizaje progresivo del vocabulario del usuario.

### Google Workspace

- Creacion de presentaciones en Google Slides con imagenes automaticas.
- Generacion de documentos en Google Docs exportables a DOCX.
- Creacion de hojas de calculo en Google Sheets exportables a XLSX.
- Gestion de eventos y recordatorios en Google Calendar con soporte de fechas relativas (hoy, manana, el lunes que viene, etc.).

### Otras integraciones

- Busqueda y recomendacion de videos en YouTube con resultados en espanol.
- Control de reproduccion en Spotify: reproducir, pausar, siguiente, anterior.
- Analisis de imagenes mediante GPT-4o Vision.
- Lectura y resumen de archivos PDF, DOCX, TXT y MD.
- Extraccion de contenido de paginas web.
- Texto a voz mediante Piper TTS y voz a texto mediante OpenAI Whisper.

### WhatsApp

- Todas las funcionalidades accesibles por mensajeria de WhatsApp.
- Aislamiento de contexto y base de conocimiento por numero de telefono.
- Soporte de imagenes y documentos adjuntos.

### Multi-Agente

- Orchestrator en el puerto 8000: coordinacion central de peticiones.
- Research Agent en el puerto 8001: investigacion web e inteligencia de mercado.
- Propuesta Agent en el puerto 8002: generacion de propuestas para municipios.
- Google Agent en el puerto 8003: creacion de documentos en Google Workspace.

---

## Stack Tecnologico

| Capa | Tecnologia |
|---|---|
| Lenguaje principal | Python 3.11 |
| Servidor WhatsApp | Flask |
| Microservicios | FastAPI |
| Interfaz de escritorio | Tkinter |
| Base de datos de conversaciones | SQLite |
| Base de conocimiento | SQLite con busqueda de texto completo |
| Modelo de IA en la nube (primario) | Groq API - Llama 3.3 70B |
| Modelo de IA en la nube (secundario) | GitHub Models - GPT-4o |
| Modelo de IA local (fallback) | Ollama - Qwen 2.5 7B |
| Reconocimiento de voz | OpenAI Whisper |
| Sintesis de voz | Piper TTS, pyttsx3, gTTS |
| Google Workspace | Google API Python Client |
| Bot de WhatsApp | whatsapp-web.js sobre Node.js |
| Web scraping | BeautifulSoup4 y requests |

---

## Requisitos

### Software

- Python 3.11 o superior.
- Node.js 18 o superior (unicamente para el bot de WhatsApp).
- Git.
- Ollama instalado y corriendo localmente (opcional, se usa como fallback ante fallos de APIs en la nube).

### Credenciales

- Cuenta de Google Cloud con las siguientes APIs habilitadas: Google Docs, Google Slides, Google Sheets, Google Drive, Google Calendar y YouTube Data API v3.
- Credenciales OAuth 2.0 descargadas desde Google Cloud Console en formato JSON.
- API key de Groq, disponible de forma gratuita en console.groq.com.
- Token de GitHub Models (opcional).
- Credenciales de Spotify (opcional).

---

## Instalacion

### 1. Clonar el repositorio

```
git clone https://github.com/KenJes/RayGPT.git
cd RayGPT
```

### 2. Crear entorno virtual e instalar dependencias

```
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux y macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Crea el archivo `config/.env` con el siguiente contenido y rellena los valores correspondientes:

```
GITHUB_TOKEN=tu_token_de_github_models
GROQ_API_KEY=tu_api_key_de_groq
SPOTIFY_CLIENT_ID=tu_client_id
SPOTIFY_CLIENT_SECRET=tu_client_secret
```

### 4. Autorizar Google

Coloca el archivo `client_secret_*.json` descargado desde Google Cloud Console en la carpeta `resources/data/` y ejecuta el siguiente script:

```
python resources/scripts/autorizar_google.py
```

Esto abrira el navegador para completar la autorizacion OAuth 2.0. El token resultante se guarda en `resources/data/token.json` y se sincroniza automaticamente a `data/token.json` al iniciar el servidor.

### 5. Instalar dependencias de Node.js

Este paso es necesario unicamente para usar el bot de WhatsApp:

```
cd resources/whatsapp
npm install
cd ../..
```

---

## Ejecucion

### Interfaz de escritorio

```
python raymundo.py
```

### Servidor de WhatsApp

En dos terminales separadas:

```
python whatsapp_server.py
```

```
node resources/whatsapp/whatsapp_bot.js
```

### Microservicios multi-agente

```
python agentes/orchestrator.py
python agentes/research_agent.py
python agentes/propuesta_agent.py
python agentes/google_agent.py
```

Tambien es posible iniciar todos los servicios ejecutando `Axoloit Agentes.bat`.

---

## Estructura del Proyecto

```
core/
    config.py                    Configuracion y personalidad del agente
    ai_clients.py                Clientes de IA: Ollama, GitHub Models, Groq
    tools.py                     Orquestacion de herramientas
    detectors.py                 Deteccion de intenciones e idioma
    knowledge_db.py              Base de conocimiento aislada por usuario
    conversation_db.py           Historial de conversaciones por usuario
    google_workspace_client.py   Integracion con APIs de Google
    processors.py                Vision por computadora y procesamiento de archivos
    web_scraper.py               Extraccion de contenido web
    audio_handler.py             Entrada y salida de audio
    memory.py                    Memoria persistente y vocabulario

agentes/
    orchestrator.py              Puerto 8000 - coordinacion central
    research_agent.py            Puerto 8001 - investigacion web
    propuesta_agent.py           Puerto 8002 - propuestas para municipios
    google_agent.py              Puerto 8003 - documentos Google Workspace

raymundo.py                      Aplicacion de escritorio
whatsapp_server.py               Servidor Flask para WhatsApp
config/.env                      Variables de entorno (no incluido en el repositorio)
```

---

## Producto de Axoloit

Raymundo es un producto desarrollado y mantenido por Axoloit.
