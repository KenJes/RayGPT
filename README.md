# 🤖 Raymundo - Asistente IA Personal

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

**Raymundo** es un asistente de inteligencia artificial versátil que combina múltiples modelos de IA para ofrecerte una experiencia completa de productividad y automatización.

---

## ✨ Funcionalidades Principales

### 💬 Chat Inteligente
- **Conversación natural** con memoria contextual
- **Dos personalidades intercambiables:**
  - 🎯 **Raymundo** (amigable): Profesional, claro y motivador
  - 🔥 **rAI** (directo): Informal, agresivo pero efectivo
- **Cambio de personalidad en tiempo real** con comandos `/amigable` o `/puteado`
- Respuestas con análisis de ortografía y contexto

### 📊 Creación Automática de Documentos
Genera contenido profesional con tu estilo de personalidad:

- **📑 Presentaciones** (Google Slides)
  - Con imágenes automáticas desde web
  - Diseño visual atractivo
  - Estructura profesional

- **📄 Documentos** (Google Docs)
  - Formato markdown avanzado
  - Estructura clara y organizada
  - Exportable a DOCX

- **📈 Hojas de Cálculo** (Google Sheets)
  - Datos organizados
  - Fórmulas y estructuras automáticas
  - Exportable a XLSX

### 🖼️ Análisis de Imágenes
- **Visión por computadora** con GPT-4o Vision
- Describe, analiza y extrae información de imágenes
- Reconocimiento de objetos, textos y contexto

### 📚 Lectura de Documentos
- **PDF, DOCX, TXT, MD** - Lectura y análisis
- Extracción de información clave
- Resúmenes automáticos

### 🌐 Web Scraping Inteligente
- Extrae contenido de páginas web
- Analiza y resume información
- Búsqueda de imágenes en Google

### 🎙️ Capacidades de Audio
- **Texto a Voz (TTS)** con Piper TTS
- **Voz a Texto (STT)** con OpenAI Whisper
- **Chat por voz** en WhatsApp
- Respuestas en audio automáticas

### 📱 Integración WhatsApp
- Bot de WhatsApp completamente funcional
- Todas las funcionalidades disponibles por mensajería
- Soporte para mensajes de voz
- Manejo de archivos adjuntos

---

## 🚀 Instalación Rápida

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

## 🎯 Uso

### Modo Local (Interfaz Gráfica)
```bash
python raymundo.py
```

Funciones:
- Chat con memoria contextual
- Botón 🎤 para grabar voz
- Botón 🔊 para escuchar respuestas
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

## 💡 Comandos Especiales

### En el Chat Local
- `/puteado` o `/rai` - Cambia a personalidad directa
- `/amigable` o `/raymundo` - Cambia a personalidad profesional
- 🎤 - Grabar mensaje de voz
- 🔊 - Reproducir última respuesta en audio

### En WhatsApp
**IMPORTANTE**: El bot solo responde a mensajes que comiencen con comandos específicos (para evitar responder a todos los mensajes automáticamente).

#### Comandos de invocación:
- **`/raymundo [mensaje]`** - Invoca a Raymundo en modo amigable
- **`/rai [mensaje]`** - Invoca a rAI en modo puteado
- **`/amigable`** - Cambia a personalidad amigable (Raymundo)
- **`/puteado`** - Cambia a personalidad directa (rAI)

#### Comandos de utilidad:
- `/ping` - Verifica que el bot está activo
- `/health` - Estado del servidor

#### Respuestas con audio:
Para recibir respuesta en audio, incluye frases como:
- `/raymundo dile a Kenneth **en un audio** que es la IA`
- `/rai manda **un audio** explicando machine learning`
- Enviar mensaje de voz - Responde automáticamente con audio

**Nota**: Si eres el propietario de la cuenta, puedes escribir directamente sin comandos y el bot responderá.

### Ejemplos de Uso
```
Usuario: /raymundo crear presentación sobre inteligencia artificial con 8 slides
Raymundo: ✅ [Crea presentación profesional]

Usuario: /puteado
rAI: oke wey, haora soy rAI...

Usuario: /rai crear presentación sobre inteligencia artificial
rAI: ✅ [Crea presentación con estilo informal]

Usuario: /raymundo analiza esta imagen [adjunta imagen]
Raymundo: 🖼️ [Describe la imagen con detalle]

Usuario: [envía mensaje de voz]
Raymundo: 🎙️ [Transcribe y responde con audio]

Usuario: /raymundo dile a Kenneth en un audio que es la inteligencia artificial
Raymundo: 🎙️ [Responde con mensaje de voz explicando qué es la IA]

Usuario: /rai explícame en audio qué son las redes neuronales
rAI: 🎙️ [Responde con audio en estilo agresivo sobre redes neuronales]

Usuario: /raymundo manda un audio explicando machine learning
Raymundo: 🎙️ [Responde con audio profesional sobre ML]
```

---

## 🏗️ Arquitectura

```
Raymundo 2.0
├── 🧠 Modelos de IA
│   ├── Ollama (local) - Qwen 2.5:7b
│   ├── Groq API - Llama 3.3 70B
│   └── GitHub Models - GPT-4o
│
├── 🎨 Herramientas
│   ├── Google Workspace (Docs, Slides, Sheets)
│   ├── Visión (GPT-4o Vision)
│   ├── Audio (Piper TTS + Whisper STT)
│   └── Web Scraping
│
└── 🔌 Interfaces
    ├── GUI Local (Tkinter)
    ├── WhatsApp Bot (Node.js)
    └── API REST (Flask)
```

---

## 📁 Estructura del Proyecto

```
raymundo/
├── raymundo.py              # Aplicación principal
├── whatsapp_server.py       # Servidor API Flask
├── whatsapp_bot.js          # Bot de WhatsApp
├── config_agente.json       # Configuración de personalidades
├── package.json             # Dependencias Node.js
│
├── config/                  # ⚠️ No versionado (credenciales)
│   ├── .env
│   └── google-credentials.json
│
├── data/                    # ⚠️ No versionado (datos runtime)
│   ├── memoria_agente.json
│   └── metrics.json
│
├── output/                  # ⚠️ No versionado (archivos generados)
│
└── resources/
    ├── core/                # Módulos principales
    ├── examples/            # Archivos de ejemplo
    ├── docs/                # Documentación técnica
    └── tests/               # Tests
```

---

## 🎨 Personalidades

### Raymundo (Amigable)
- ✅ Ortografía correcta
- ✅ Tono profesional y motivador
- ✅ Emojis ocasionales 😊
- ✅ Explicaciones claras

**Ejemplo:**
> "¡Hola! Claro que sí, con gusto te ayudo. El Machine Learning es un conjunto de algoritmos que aprenden patrones de datos..."

### rAI (Puteado)
- 🔥 Faltas de ortografía intencionadas
- 🔥 Lenguaje directo y agresivo
- 🔥 Jerga mexicana
- 🔥 Efectivo pero irreverente

**Ejemplo:**
> "oye wey ps ta kabron lo ke me pides pero ai te va. el machine learning ps es un chingo de algoritmos ke aprenden solos, no mames..."

---

## 🔧 Tecnologías

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

---

## 📖 Documentación Adicional

- [Instalación de Audio](AUDIO_QUICKSTART.md) - Guía completa de audio
- [Configuración de Google](resources/docs/CREAR_SERVICE_ACCOUNT.md)
- [Configurar API Keys](resources/docs/COMO_CONFIGURAR_API_KEY.md)
- [Documentación Técnica](resources/docs/)

---

## 🤝 Contribuir

¿Tienes ideas para mejorar Raymundo? 

1. Fork el proyecto
2. Crea una rama (`git checkout -b feature/nueva-funcion`)
3. Commit tus cambios (`git commit -am 'Agregar nueva función'`)
4. Push a la rama (`git push origin feature/nueva-funcion`)
5. Abre un Pull Request

---

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo `LICENSE` para más detalles.

---

## ⚠️ Aviso Importante

- Este proyecto requiere **API keys** de servicios externos
- Las credenciales **NO** están incluidas en el repositorio
- Lee `resources/examples/README.md` para configurar tus credenciales
- **Nunca** compartas tus API keys públicamente

---

## 🆘 Soporte

¿Problemas? Revisa:
1. [Documentación](resources/docs/)
2. [Issues en GitHub](https://github.com/tu-usuario/RayGPT/issues)
3. Ejecuta los tests: `python resources/tests/test_audio.py`

---

**Desarrollado con ❤️ por la comunidad**  
**Versión:** 2.0 con Audio  
**Última actualización:** Febrero 2026

---

## 🎙️ Guía Rápida de Audio en WhatsApp

El bot detecta automáticamente cuando pides una respuesta en audio buscando frases clave en tu mensaje:

### ✅ Responde con audio:
- `dile a Kenneth **en un audio** que es la IA`
- `/raymundo explícame **con audio** qué son las GPU`
- `**manda un audio** explicando machine learning`
- `**envía audio** sobre redes neuronales`
- `/rai **hazme un audio** de cómo programar`

### ❌ Responde con texto:
- `qué es la inteligencia artificial` (sin mencionar audio)
- `/raymundo explícame machine learning` (sin solicitar audio)
- `ayúdame con Python` (mensaje normal)

**Tip:** Si quieres respuesta en voz, simplemente incluye "en audio", "con audio", "manda audio" o similares en tu mensaje.
