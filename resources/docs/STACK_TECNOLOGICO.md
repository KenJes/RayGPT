# 🎓 Stack Tecnológico - Agentes IA
## Guía Didáctica para Ingeniería en Computación

---

## 📚 **ÍNDICE**

1. [Fundamentos Teóricos](#fundamentos)
2. [Stack de Raymundo (Caso Práctico)](#stack-raymundo)
3. [Lenguajes de Programación](#lenguajes)
4. [APIs y Servicios Cloud](#apis)
5. [Frameworks y Librerías](#frameworks)
6. [Arquitectura de Agentes](#arquitectura)
7. [Ruta de Aprendizaje](#ruta)
8. [Proyectos Recomendados](#proyectos)

---

## 🧠 **1. FUNDAMENTOS TEÓRICOS** <a name="fundamentos"></a>

### **¿Qué es un Agente IA?**
Un agente IA es un sistema autónomo que:
- **Percibe** su entorno (mensajes, archivos, APIs)
- **Razona** sobre acciones a tomar (LLMs, lógica)
- **Actúa** para alcanzar objetivos (crear archivos, responder)
- **Aprende** de interacciones (memoria, preferencias)

### **Componentes Esenciales**
```
┌─────────────────────────────────────────┐
│         AGENTE IA INTELIGENTE           │
├─────────────────────────────────────────┤
│ 1. INTERFAZ (WhatsApp, Web, API)       │
│ 2. CEREBRO (LLM - Large Language Model)│
│ 3. HERRAMIENTAS (APIs externas)        │
│ 4. MEMORIA (Contexto persistente)      │
│ 5. ORQUESTADOR (Flujo de decisiones)   │
└─────────────────────────────────────────┘
```

---

## 🏗️ **2. STACK DE RAYMUNDO (Caso Práctico)** <a name="stack-raymundo"></a>

### **Arquitectura Completa**
```
┌──────────────────────────────────────────────┐
│            USUARIO (WhatsApp)                │
└───────────────┬──────────────────────────────┘
                │ /raymundo hola
                ↓
┌──────────────────────────────────────────────┐
│     whatsapp_bot.js (Node.js)                │
│     • whatsapp-web.js                        │
│     • Escucha comando /raymundo              │
└───────────────┬──────────────────────────────┘
                │ HTTP POST
                ↓
┌──────────────────────────────────────────────┐
│   whatsapp_server.py (Flask - Python)        │
│   • Recibe peticiones del bot               │
│   • Orquesta herramientas                   │
└───────────────┬──────────────────────────────┘
                │
                ↓
┌──────────────────────────────────────────────┐
│       raymundo.py (Agente Principal)         │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │  DetectorIntenciones                │    │
│  │  • Analiza qué quiere el usuario    │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  ┌──────────────┐  ┌──────────────────┐     │
│  │ OllamaClient │  │ GitHubModelsClient│    │
│  │ (Local GPU)  │  │   (GPT-4o Cloud) │    │
│  └──────────────┘  └──────────────────┘     │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │  GestorHerramientas                 │    │
│  │  • Google Workspace (Docs/Sheets)   │    │
│  │  • Vision (Análisis de imágenes)    │    │
│  │  • DocumentProcessor (PDFs)         │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │  MemorySystem                       │    │
│  │  • Aprende vocabulario del usuario  │    │
│  │  • Historial de conversaciones      │    │
│  └─────────────────────────────────────┘    │
└──────────────┬───────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────┐
│         APIs EXTERNAS                        │
│  • GitHub Models (GPT-4o)                    │
│  • Google Workspace APIs                    │
│  • Ollama (qwen2.5:7b local)                │
└──────────────────────────────────────────────┘
```

---

## 💻 **3. LENGUAJES DE PROGRAMACIÓN** <a name="lenguajes"></a>

### **Python (Core del Agente)**
**Por qué Python:**
- 🐍 Ecosistema IA/ML más grande
- 📚 Librerías maduras (openai, transformers, langchain)
- 🔧 Fácil integración con APIs
- ⚡ Desarrollo rápido de prototipos

**Conceptos Clave:**
```python
# 1. Programación Orientada a Objetos (Clases)
class AgenteIA:
    def __init__(self):
        self.memoria = {}
    
    def procesar(self, mensaje):
        # Lógica del agente
        pass

# 2. Manejo de APIs REST
import requests
response = requests.post(url, json=data)

# 3. Programación Asíncrona (para eficiencia)
import asyncio
async def procesar_mensaje():
    await modelo.generar()

# 4. Decoradores (Flask)
@app.route('/chat', methods=['POST'])
def chat():
    return jsonify(respuesta)
```

### **JavaScript/Node.js (Integraciones)**
**Por qué JavaScript:**
- 🌐 Conectar con APIs web (WhatsApp, Telegram)
- 📦 NPM tiene librerías para todo
- 🔄 Event-driven (perfecto para bots)

**Conceptos Clave:**
```javascript
// 1. Promesas y Async/Await
async function enviarMensaje(texto) {
    await client.sendMessage(numero, texto);
}

// 2. Event Listeners (Reactividad)
client.on('message', async (msg) => {
    // Procesar mensaje
});

// 3. Callbacks (Patrones asíncronos)
axios.post(url, data)
    .then(response => console.log(response))
    .catch(error => console.error(error));
```

---

## 🌐 **4. APIs Y SERVICIOS CLOUD** <a name="apis"></a>

### **Modelos de Lenguaje (LLMs)**

#### **OpenAI API / GitHub Models**
```python
# ¿Qué es? Acceso a GPT-4o, GPT-3.5, etc.
from openai import OpenAI

client = OpenAI(api_key="sk-...")
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "Eres un asistente útil"},
        {"role": "user", "content": "¿Qué es IA?"}
    ]
)
print(response.choices[0].message.content)
```

**Conceptos:**
- **Tokens**: Fragmentos de texto (~4 chars = 1 token)
- **Temperature**: Creatividad (0 = determinista, 1 = creativo)
- **Max Tokens**: Límite de respuesta
- **System Prompt**: Personalidad del agente

#### **Ollama (Local LLM)**
```bash
# ¿Por qué local? Privacidad + Sin costos API
ollama run qwen2.5:7b
```

**Ventajas:**
- ✅ Datos privados (no salen de tu máquina)
- ✅ Sin límites de tokens
- ✅ Personalizable (fine-tuning)
- ❌ Requiere GPU potente

### **Google Workspace APIs**
```python
# Crear documentos programáticamente
from googleapiclient.discovery import build

docs_service = build('docs', 'v1', credentials=creds)
doc = docs_service.documents().create(
    body={'title': 'Mi Documento IA'}
).execute()
```

**APIs Disponibles:**
- 📄 **Google Docs API**: Crear/editar documentos
- 📊 **Google Sheets API**: Hojas de cálculo
- 📽️ **Google Slides API**: Presentaciones
- 📁 **Google Drive API**: Gestión de archivos

### **WhatsApp Web (via whatsapp-web.js)**
```javascript
// Conectar sin API oficial (gratis)
const { Client } = require('whatsapp-web.js');

const client = new Client();
client.on('qr', qr => {
    // Escanear QR con teléfono
});

client.on('message', msg => {
    if (msg.body === '/help') {
        msg.reply('¿En qué puedo ayudarte?');
    }
});
```

---

## 📦 **5. FRAMEWORKS Y LIBRERÍAS** <a name="frameworks"></a>

### **Backend (Python)**

#### **Flask** (API REST simple)
```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/chat', methods=['POST'])
def chat():
    mensaje = request.json['mensaje']
    respuesta = agente.procesar(mensaje)
    return jsonify({'respuesta': respuesta})

if __name__ == '__main__':
    app.run(port=5000)
```

**Alternativas:**
- **FastAPI**: Más moderno, async nativo, validación automática
- **Django**: Framework completo (si necesitas admin, auth, etc.)

#### **LangChain** (Orquestación de LLMs)
```python
from langchain.agents import initialize_agent
from langchain.llms import OpenAI
from langchain.tools import Tool

# Definir herramientas
tools = [
    Tool(
        name="Calculadora",
        func=lambda x: eval(x),
        description="Útil para cálculos matemáticos"
    )
]

# Crear agente
agent = initialize_agent(
    tools=tools,
    llm=OpenAI(temperature=0),
    agent="zero-shot-react-description"
)

# Usar
agent.run("¿Cuánto es 25 * 4 + 10?")
```

**Características:**
- 🧩 Modular (conecta múltiples LLMs)
- 🛠️ Abstrae APIs comunes
- 🔗 Chains (secuencias de prompts)
- 🤖 Agentes con herramientas

### **Frontend (Node.js)**

#### **whatsapp-web.js**
```javascript
// Puppeteer + WhatsApp Web = Bot sin API oficial
const { Client, LocalAuth } = require('whatsapp-web.js');

const client = new Client({
    authStrategy: new LocalAuth() // Guarda sesión
});

client.initialize();
```

---

## 🏛️ **6. ARQUITECTURA DE AGENTES** <a name="arquitectura"></a>

### **Patrones de Diseño**

#### **1. Patrón ReAct (Reasoning + Acting)**
```
Usuario: "Crea una presentación sobre IA"

PENSAMIENTO 1: Detectar intención → "crear_presentacion"
ACCIÓN 1: Llamar a GPT-4o para generar contenido
OBSERVACIÓN 1: Contenido generado exitosamente

PENSAMIENTO 2: Usar herramienta Google Slides
ACCIÓN 2: crear_presentacion(tema="IA", slides=5)
OBSERVACIÓN 2: URL de presentación lista

RESPUESTA: "✅ Presentación creada: [URL]"
```

#### **2. Patrón RAG (Retrieval Augmented Generation)**
```python
# 1. RETRIEVE: Buscar información relevante
docs = vector_db.buscar(query=mensaje, top_k=3)

# 2. AUGMENT: Enriquecer el prompt
prompt = f"""Contexto relevante:
{docs}

Pregunta del usuario: {mensaje}

Responde basándote en el contexto."""

# 3. GENERATE: Generar respuesta
respuesta = llm.generate(prompt)
```

**Uso:** Cuando el agente necesita conocimiento actualizado o específico.

#### **3. Arquitectura Chain-of-Thought**
```python
# Hacer que el LLM "piense paso a paso"
prompt = f"""Resuelve esto paso a paso:

Pregunta: {mensaje}

Paso 1: Identificar qué se necesita
Paso 2: Planificar solución
Paso 3: Ejecutar
Paso 4: Verificar resultado
"""
```

**Ventaja:** Mejora precisión en tareas complejas.

---

## 🎯 **7. RUTA DE APRENDIZAJE** <a name="ruta"></a>

### **Nivel 1: Fundamentos (2-3 meses)**
```
[ ] Python Básico
    • Variables, funciones, clases
    • Manejo de archivos
    • Requests HTTP
    
[ ] APIs REST
    • GET, POST, PUT, DELETE
    • JSON
    • Autenticación (API keys, OAuth)
    
[ ] Git/GitHub
    • Clone, commit, push
    • Branches
    • Colaboración
```

**Recursos:**
- [Real Python](https://realpython.com)
- [Postman Learning Center](https://learning.postman.com)

### **Nivel 2: Backend (2-3 meses)**
```
[ ] Flask/FastAPI
    • Rutas y endpoints
    • Validación de datos
    • CORS
    
[ ] Bases de Datos
    • SQL (PostgreSQL)
    • NoSQL (MongoDB)
    • ORMs (SQLAlchemy)
    
[ ] Docker
    • Contenedores
    • Docker Compose
    • Despliegue
```

**Recursos:**
- [Miguel Grinberg's Flask Mega-Tutorial](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world)
- [FastAPI Docs](https://fastapi.tiangolo.com)

### **Nivel 3: IA/ML (3-4 meses)**
```
[ ] LLMs Fundamentals
    • Transformers architecture
    • Tokenization
    • Embeddings
    
[ ] Prompt Engineering
    • System prompts
    • Few-shot learning
    • Chain-of-thought
    
[ ] APIs de LLMs
    • OpenAI API
    • Anthropic Claude
    • Ollama local
```

**Recursos:**
- [Andrew Ng's Deep Learning Specialization](https://www.coursera.org/specializations/deep-learning)
- [Prompt Engineering Guide](https://www.promptingguide.ai)

### **Nivel 4: Agentes IA (2-3 meses)**
```
[ ] LangChain
    • Chains
    • Agents
    • Memory
    
[ ] Vector Databases
    • Pinecone, Weaviate
    • Embeddings
    • Semantic search
    
[ ] AutoGPT/BabyAGI
    • Task decomposition
    • Self-prompting
    • Goal-oriented agents
```

**Recursos:**
- [LangChain Documentation](https://python.langchain.com)
- [DeepLearning.AI - Building Systems with ChatGPT](https://www.deeplearning.ai/short-courses/chatgpt-prompt-eng/)

---

## 🚀 **8. PROYECTOS RECOMENDADOS** <a name="proyectos"></a>

### **Principiante**
```
1. Chatbot Básico con Flask + OpenAI API
   • 3 rutas: /chat, /history, /clear
   • Sistema de mensajes
   • Historial en JSON
   
2. Bot de WhatsApp Simple
   • Responde preguntas FAQ
   • Lee/escribe JSON
   • Comandos básicos
```

### **Intermedio**
```
3. Asistente Personal Multi-Tarea
   • Gestión de calendario
   • Recordatorios
   • Búsqueda web
   • Resúmenes de noticias
   
4. Generador de Contenido
   • Blog posts
   • Tweets
   • Scripts de video
   • Con memoria de estilo
```

### **Avanzado**
```
5. Agente RAG con Vector Database
   • Ingesta de documentos
   • Búsqueda semántica
   • Respuestas contextualizadas
   
6. Sistema Multi-Agente
   • Agente investigador
   • Agente escritor
   • Agente revisor
   • Coordinador central
```

---

## 🛠️ **HERRAMIENTAS ESENCIALES**

### **Editor/IDE**
- **VS Code** + extensiones (Python, Pylance, GitHub Copilot)
- **PyCharm** (alternativa)

### **Control de Versiones**
- **Git** + **GitHub**
- **Conventional Commits**

### **Testing**
```python
# pytest
def test_agente_responde():
    respuesta = agente.procesar("hola")
    assert respuesta is not None
    assert len(respuesta) > 0
```

### **Deployment**
- **Render** (gratis, Python/Node)
- **Railway** (gratis con límites)
- **Vercel** (frontend)
- **Google Cloud Run** (contenedores)

---

## 📖 **RECURSOS ADICIONALES**

### **Cursos Online**
- [DeepLearning.AI](https://www.deeplearning.ai) - Andrew Ng
- [Fast.ai](https://www.fast.ai) - Práctico y directo
- [Hugging Face Course](https://huggingface.co/course) - NLP/LLMs

### **Libros**
- **"Building LLM Apps"** - Valentino Zocca
- **"Designing Data-Intensive Applications"** - Martin Kleppmann
- **"Python for Data Analysis"** - Wes McKinney

### **Comunidades**
- [r/MachineLearning](https://reddit.com/r/MachineLearning)
- [Hugging Face Forums](https://discuss.huggingface.co)
- [LangChain Discord](https://discord.gg/langchain)

### **Newsletters**
- **The Batch** by DeepLearning.AI
- **Import AI** by Jack Clark
- **The Rundown AI**

---

## 💡 **CONSEJOS FINALES**

### **1. Practica Constantemente**
```python
# Dedica 1-2 horas diarias a:
- Leer código de proyectos open source
- Hacer tus propios experimentos
- Resolver problemas en LeetCode/HackerRank
```

### **2. Documenta Todo**
```markdown
# README.md de cada proyecto:
- ¿Qué hace?
- ¿Cómo instalarlo?
- ¿Cómo usarlo?
- Screenshots/GIFs
- Stack tecnológico
```

### **3. Construye en Público**
- Sube proyectos a GitHub
- Escribe posts en Medium/Dev.to
- Comparte en Twitter/LinkedIn
- **Portfolio = Tu mejor CV**

### **4. Enfócate en Resolver Problemas Reales**
```
❌ "Voy a aprender IA"
✅ "Voy a crear un bot que automatice mi tarea X"

El aprendizaje surge de resolver problemas concretos.
```

---

## 🎓 **CONCLUSIÓN**

El stack tecnológico para agentes IA es **amplio pero accesible**. La clave es:

1. **Dominar lo básico** (Python, APIs, Git)
2. **Experimentar constantemente** (builds, fails, learns)
3. **Mantenerse actualizado** (la IA avanza rápido)
4. **Construir proyectos reales** (portfolio > teoría)

**Siguiente paso:** Elige un proyecto del nivel que corresponda y **empieza hoy**. No esperes a "estar listo" - aprenderás construyendo.

---

## 📞 **CONTACTO Y RECURSOS**

**Raymundo (este proyecto):**
- GitHub: [Tu repositorio]
- Stack: Python + Flask + Node.js + GPT-4o + Ollama + Google APIs
- Arquitectura: Agente híbrido con herramientas múltiples

**¿Preguntas?**
Estudia el código de Raymundo - es un ejemplo real de todo lo mencionado aquí.

---

**Creado por:** Sistema de Agentes IA  
**Fecha:** Febrero 2026  
**Versión:** 1.0 - Guía Completa
