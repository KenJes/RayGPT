# Raymundo - Asistente IA Personal

**Raymundo** es un asistente de inteligencia artificial que combina multiples modelos de IA para ofrecer una experiencia completa de productividad y automatizacion.

---

## Funcionalidades Principales

### Chat Inteligente
- Conversacion natural con memoria contextual persistente
- Dos personalidades intercambiables:
  - **Raymundo** (amigable): Profesional, claro y motivador
  - **rAI** (directo): Informal, agresivo pero efectivo
- Cambio de personalidad en tiempo real con `/amigable` o `/puteado`
- Aprende el vocabulario del usuario e lo incorpora en respuestas

### Creacion Automatica de Documentos
- **Presentaciones** (Google Slides) con imagenes automaticas y diseno visual
- **Documentos** (Google Docs) en formato markdown, exportable a DOCX
- **Hojas de Calculo** (Google Sheets) con estructuras automaticas, exportable a XLSX

### Capacidades Adicionales
- **Vision por computadora** con GPT-4o Vision - analiza imagenes
- **Lectura de documentos** - PDF, DOCX, TXT, MD
- **Web Scraping** - extrae y resume contenido de paginas web
- **Audio** - Texto a Voz (Piper TTS) y Voz a Texto (OpenAI Whisper)
- **WhatsApp Bot** - todas las funcionalidades por mensajeria

### Multi-Agente (FastAPI)
- Orchestrator (puerto 8000) - punto central de coordinacion
- Research Agent (8001) - investigacion web e inteligencia de mercado
- Propuesta Agent (8002) - generador de propuestas para municipios
- Google Agent (8003) - creacion de documentos en Google Workspace

---

## Instalacion Rapida

### Requisitos
- Python 3.9+
- Node.js 16+ (para WhatsApp)
- Git
- Cuenta de Google Cloud (para documentos)

### 1. Clonar el repositorio
``bash
git clone https://github.com/KenJes/RayGPT.git
cd RayGPT
``n
### 2. Crear entorno virtual
``bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
``n
### 3. Instalar dependencias
``bash
pip install -r requirements.txt
``n
### 4. Configurar credenciales

Crea `config/.env` con tus API keys:
``env
GITHUB_TOKEN=ghp_tu_token_aqui
GROQ_API_KEY=gsk_tu_api_key_aqui
``n
---

## Uso

### Interfaz grafica
``bash
python raymundo.py
``n
### Agentes multi-servicio
``bash
python agentes/orchestrator.py    # 8000
python agentes/research_agent.py  # 8001
python agentes/propuesta_agent.py # 8002
python agentes/google_agent.py    # 8003
``n
O lanza con: `Axoloit Agentes.bat`

### Modo WhatsApp
``bash
python whatsapp_server.py
node resources/whatsapp/whatsapp_bot.js
``n
---

## Arquitectura

``n core/                          Paquete modular central
    config.py                  Configuracion y personalidad
    ai_clients.py              OllamaClient, GitHubModelsClient, GroqClient
    tools.py                   GestorHerramientas (orquestacion)
    memory.py                  Memoria persistente y vocabulario
    detectors.py               Deteccion de intenciones e idioma
    processors.py              Vision, documentos, emojis
    web_scraper.py
    google_workspace_client.py
    audio_handler.py

 agentes/                      Microservicios FastAPI
    orchestrator.py            Puerto 8000
    research_agent.py          Puerto 8001
    propuesta_agent.py         Puerto 8002
    google_agent.py            Puerto 8003
    base_agent.py              Utilidades compartidas

 raymundo.py                   GUI principal (250 lineas)
 whatsapp_server.py            Servidor Flask para WhatsApp
``n
### Modelos de IA (cadena de fallback automatica)
- **Groq API** - Llama 3.3 70B (primera prioridad, 14,400 RPD gratis)
- **GitHub Models** - GPT-4o (segunda prioridad)
- **Ollama** (local / GPU) - Qwen 2.5:7b (fallback local)

---

## Tecnologias

| Capa | Tecnologia |
|------|------------|
| Backend | Python 3.9+, Flask, FastAPI |
| GUI | Tkinter |
| IA local | Ollama (Qwen 2.5) |
| IA cloud | Groq API, GitHub Models (GPT-4o) |
| STT | OpenAI Whisper |
| TTS | Piper TTS, pyttsx3, gTTS |
| Documentos | Google Workspace API |
| WhatsApp | whatsapp-web.js (Node.js) |
| Web scraping | BeautifulSoup4 |

---

**Version:** 3.0 (modular)
