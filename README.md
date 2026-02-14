#  Raymundo - Asistente IA Personal

**Raymundo** es un asistente de inteligencia artificial versátil que combina múltiples modelos de IA para ofrecerte una experiencia completa de productividad y automatización.

---

##  Funcionalidades Principales

###  Chat Inteligente
- **Conversación natural** con memoria contextual
- **Dos personalidades intercambiables:**
  -  **Raymundo** (amigable): Profesional, claro y motivador
  -  **rAI** (directo): Informal, agresivo pero efectivo
- **Cambio de personalidad en tiempo real** con comandos `/amigable` o `/puteado`
- Respuestas con análisis de ortografía y contexto

###  Creación Automática de Documentos
Genera contenido profesional con tu estilo de personalidad:

- ** Presentaciones** (Google Slides)
  - Con imágenes automáticas desde web
  - Diseño visual atractivo
  - Estructura profesional

- ** Documentos** (Google Docs)
  - Formato markdown avanzado
  - Estructura clara y organizada
  - Exportable a DOCX

- ** Hojas de Cálculo** (Google Sheets)
  - Datos organizados
  - Fórmulas y estructuras automáticas
  - Exportable a XLSX

###  Análisis de Imágenes
- **Visión por computadora** con GPT-4o Vision
- Describe, analiza y extrae información de imágenes
- Reconocimiento de objetos, textos y contexto

###  Lectura de Documentos
- **PDF, DOCX, TXT, MD** - Lectura y análisis
- Extracción de información clave
- Resúmenes automáticos

###  Web Scraping Inteligente
- Extrae contenido de páginas web
- Analiza y resume información
- Búsqueda de imágenes en Google

###  Capacidades de Audio
- **Texto a Voz (TTS)** con Piper TTS
- **Voz a Texto (STT)** con OpenAI Whisper
- **Chat por voz** en WhatsApp
- Respuestas en audio automáticas

###  Integración WhatsApp
- Bot de WhatsApp completamente funcional
- Todas las funcionalidades disponibles por mensajería
- Soporte para mensajes de voz
- Manejo de archivos adjuntos

---

##  Instalación Rápida

### Requisitos
- Python 3.9 o superior
- Node.js 16+ (para WhatsApp)
- Git
- Cuenta de Google Cloud (para documentos)

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/RayGPT.git
cd RayGPT
```

### 2. Crear entorno virtual
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

### 3. Instalar dependencias
```bash
# Python
pip install -r resources/setup/requirements_audio.txt

# Node.js (para WhatsApp)
npm install
```

### 4. Configurar credenciales

#### a) Copiar archivo de ejemplo
```bash
# Windows
copy resources\examples\env.example config\.env

# Linux/Mac
cp resources/examples/env.example config/.env
```

#### b) Editar `config/.env` y agregar tus API keys:
```env
GITHUB_TOKEN=ghp_tu_token_aqui
GROQ_API_KEY=gsk_tu_api_key_aqui
GOOGLE_CREDENTIALS_FILE=config/google-credentials.json
```

#### c) Descargar credenciales de Google:
1. Ve a [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Crea una Service Account
3. Descarga el JSON
4. Guárdalo como `config/google-credentials.json`

### 5. (Opcional) Configurar Audio
```bash
# Windows
.\instalar_audio.bat

# Linux/Mac
chmod +x instalar_audio.sh
./instalar_audio.sh
```

---

##  Uso

### Modo Local (Interfaz Gráfica)
```bash
python raymundo.py
```

Funciones:
- Chat con memoria contextual
- Botón para grabar voz
- Botón para escuchar respuestas
- Adjuntar imágenes y documentos
- Cambiar personalidad con `/puteado` o `/amigable`

### Modo WhatsApp

#### Terminal 1: Servidor
```bash
python whatsapp_server.py
```

#### Terminal 2: Bot de WhatsApp
```bash
node whatsapp_bot.js
```

Escanea el código QR con WhatsApp y comienza a chatear.

---

##  Arquitectura

```
Raymundo 2.0
├──  Modelos de IA
│   ├── Ollama (local) - Qwen 2.5:7b
│   ├── Groq API - Llama 3.3 70B
│   └── GitHub Models - GPT-4o
│
├──  Herramientas
│   ├── Google Workspace (Docs, Slides, Sheets)
│   ├── Visión (GPT-4o Vision)
│   ├── Audio (Piper TTS + Whisper STT)
│   └── Web Scraping
│
└──  Interfaces
    ├── GUI Local (Tkinter)
    ├── WhatsApp Bot (Node.js)
    └── API REST (Flask)
```

---

## Tecnologías

### Backend
- Python 3.9+
- Flask (API REST)
- Tkinter (GUI)

### IA y ML
- Ollama (Qwen 2.5)
- Groq API (Llama 3.3)
- GitHub Models (GPT-4o)
- OpenAI Whisper (STT)
- Piper TTS

### Integraciones
- Google Workspace API
- WhatsApp Web.js
- BeautifulSoup4 (Web Scraping)

### Node.js
- whatsapp-web.js
- axios
- qrcode-terminal
