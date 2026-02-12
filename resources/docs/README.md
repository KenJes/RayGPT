# 🤖 rAImundoGPT - Agente IA para WhatsApp

**Asistente de inteligencia artificial con personalidad customizable que funciona como contacto de WhatsApp**

---

## 🎯 ¿Qué es esto?

Un agente IA completo que puedes agregar como contacto de WhatsApp y usar en grupos. Tiene:

- ✅ Personalidad customizable (profesional, amigable, técnico, creativo, **puteado**)
- ✅ Responde en grupos y mensajes privados
- ✅ Crea y envía presentaciones PowerPoint (.pptx)
- ✅ Crea y envía documentos Word (.docx)  
- ✅ Crea y envía hojas de cálculo Excel (.xlsx)
- ✅ Analiza imágenes (Vision AI)
- ✅ Lee documentos (PDF, DOCX, TXT)
- ✅ Google Workspace integrado
- ✅ **Aprende tu vocabulario y lo usa en respuestas**

---

## 🚀 Inicio Rápido (3 pasos)

### 1. Instalar Node.js

```
https://nodejs.org/
```

Descarga e instala la versión LTS (recomendada).

### 2. Ejecutar el launcher

```powershell
.\iniciar_whatsapp.bat
```

Este script automáticamente:
- Verifica Node.js y Python
- Instala todas las dependencias
- Inicia servidor Python (Flask)
- Inicia bot de WhatsApp (Node.js)

### 3. Escanear código QR

1. Se abrirá una ventana con código QR
2. Abre WhatsApp en tu teléfono
3. Ve a **Ajustes → Dispositivos vinculados**
4. Escanea el QR
5. **¡Listo!**

---

## 🎭 Configurar Personalidad

### Método 1: Configurador interactivo (recomendado)

```powershell
python configurar_agente.py
```

**Opciones de personalidad:**

1. **Profesional**: Formal, educado, corporativo
2. **Amigable**: Casual, cercano, simpático
3. **Técnico**: Preciso, detallado, especializado
4. **Creativo**: Innovador, expresivo, original
5. **Puteado**: Irreverente, groserías, faltas ortográficas (estilo mexicano)

El configurador te permite:
- Elegir nombre del agente
- Seleccionar tono de personalidad
- Ajustar temperaturas (creatividad)
- Personalizar colores de interfaz
- Guardar configuración en `config_agente.json`

### Método 2: Editar config_agente.json

Si ya configuraste antes, puedes editar directamente:

```json
{
  "personalidad": {
    "nombre": "Raymundo",
    "tono": "puteado",
    "prompt_sistema": "..."
  }
}
```

---

## 💬 Uso en WhatsApp

### Comando único:

**El bot SOLO responde cuando usas el comando `/raymundo`**

Esto evita que responda a mensajes accidentales y protege tu privacidad.

### En grupos:

```
/raymundo crea una presentación sobre blockchain
/raymundo explica machine learning
/raymundo que es docker
```

### En mensajes privados:

```
/raymundo crea una presentación sobre inteligencia artificial
/raymundo explicame python
/raymundo ayuda con mi código
```

**⚠️ Importante:**
- ✅ `/raymundo` (con diagonal) - FUNCIONA
- ❌ `raymundo` (sin diagonal) - NO funciona
- ❌ `@raymundo` - NO funciona
- ❌ `RAImundo` - NO funciona

**Respuesta del bot:** 
✅ Presentación creada con éxito
🔗 URL: https://docs.google.com/presentation/d/...
📎 Te envío el archivo PPTX...

[ARCHIVO: IA_Presentacion.pptx]
```

---

## 📎 Archivos que puede enviar

| Tipo | Comando | Archivo |
|------|---------|---------|
| **Presentación** | "crea presentación sobre X" | .pptx |
| **Documento** | "crea documento sobre X" | .docx |
| **Hoja de cálculo** | "crea tabla de X" | .xlsx |

**Todos los archivos se envían automáticamente y son descargables directamente desde WhatsApp.**

---

## 🧠 Aprendizaje de Vocabulario

**Raymundo aprende las palabras que usas con frecuencia y las incorpora en sus respuestas.**

Por ejemplo:
```
Tú: "/raymundo wey, necesito una presentación chida sobre APIs"

[Después de varias conversaciones]

Raymundo: "oye wey, aquí ta tu presentación chida sobre APIs ps..."
```

El vocabulario se guarda en `memoria_agente.json` y se actualiza automáticamente.

---

## ⚙️ Configuración Avanzada

### Cambiar prefijos del bot

Edita `whatsapp_bot.js`, línea ~28:

```javascript
COMANDO: '/raymundo',  // Cambiar a otro comando como '/bot' o '/ai'
```

### Cambiar puerto del servidor

Edita `whatsapp_server.py`, línea ~230:

```python
app.run(port=5000)  # Cambiar a otro puerto
```

---

## 🛠️ Arquitectura Técnica

```
WhatsApp (tu teléfono)
    ↕
whatsapp_bot.js (Node.js)
    ↕ HTTP
whatsapp_server.py (Flask API)
    ↕
raymundo.py (Agente IA)
    ↕
Ollama (GPU local) + GPT-4o (cloud)
    ↕
Google Workspace APIs
```

**Componentes:**
- **Ollama**: Procesamiento local con GPU (qwen2.5:7b)
- **GPT-4o**: Respuestas avanzadas cloud (GitHub Models)
- **Vision AI**: Análisis de imágenes
- **Google Workspace**: Docs, Sheets, Slides, Drive, Calendar
- **Sistema de memoria**: Aprende vocabulario y contexto

---

## 📋 Requisitos

### Software:
- ✅ Python 3.14 (incluido en Windows)
- ✅ Node.js 16+ (descargar de nodejs.org)
- ✅ Ollama 0.15.4+ (para procesamiento local)

### Cuentas/Credenciales:
- ✅ GitHub Token (para GPT-4o): En archivo `.env`
- ✅ Google Service Account (para Workspace): `google-credentials.json`
- ✅ WhatsApp instalado en teléfono

### Dependencias Python (se instalan automáticamente):
```
flask
flask-cors
azure-ai-inference
requests
PyPDF2
python-docx
Pillow
```

### Dependencias Node.js (se instalan automáticamente):
```
whatsapp-web.js
qrcode-terminal
axios
```

---

## 🐛 Problemas Comunes

### Bot no responde en grupos

**Solución:** Usa el comando correcto con diagonal:
```
❌ "raymundo que es python"
✅ "/raymundo que es python"
```

### "ECONNREFUSED" al enviar mensaje

**Causa:** Servidor Python no está corriendo.

**Solución:**
```powershell
python whatsapp_server.py
```

### QR no aparece

**Solución:** Elimina sesión y reinicia:
```powershell
Remove-Item -Recurse whatsapp_session
node whatsapp_bot.js
```

### Archivos no se envían

**Verificar:**
1. Google Workspace configurado (`google-credentials.json`)
2. Credenciales tienen scope `drive` para exportar
3. Carpeta `whatsapp_temp/` existe (se crea automáticamente)

**Logs esperados:**
```
📥 Exportando presentación: ABC123...
⬇️ Descargando... 100%
✅ Presentación exportada
📎 Enviando archivo
✅ Archivo enviado
🗑️ Archivo temporal eliminado
```

---

## 🔒 Seguridad

### NO compartas:
- ❌ `whatsapp_session/` (tu sesión de WhatsApp)
- ❌ `.env` (API keys)
- ❌ `google-credentials.json` (credenciales)

### Agregar a .gitignore:
```
whatsapp_session/
whatsapp_temp/
.env
google-credentials.json
memoria_agente.json
```

---

## 🌐 Deploy 24/7 (Opcional)

Si quieres que esté activo todo el tiempo, necesitas un servidor VPS:

### Proveedores recomendados:
- DigitalOcean: $6/mes
- Linode: $5/mes
- AWS Lightsail: $3.50/mes

### Setup en Ubuntu:
```bash
# Instalar dependencias
sudo apt update
sudo apt install nodejs npm python3 python3-pip

# Clonar proyecto
git clone tu-repo
cd tu-repo

# Instalar dependencias
npm install
pip3 install flask flask-cors

# Usar PM2 para mantener activo
npm install -g pm2
pm2 start whatsapp_server.py --interpreter python3 --name raymundo
pm2 start whatsapp_bot.js --name whatsapp-bot
pm2 save
pm2 startup
```

**Nota:** Tendrás que vincular WhatsApp cada vez que el servidor reinicie (QR).

---

## 🎯 Casos de Uso

### 1. Asistente técnico en grupos de trabajo

```
Grupo: "¿Alguien sabe Docker?"
Tú: "/raymundo explica Docker"
Raymundo: "ps wey docker es como..."
```

### 2. Creación rápida de documentos

```
"/raymundo crea presentación para mi reunión de ventas Q1"
→ Recibe archivo.pptx listo para presentar
```

### 3. Análisis de código

```
[Envías screenshot de código]
"/raymundo que hace este código?"
→ Análisis detallado con Vision AI
```

### 4. Educación personalizada

```
"/raymundo explica quantum computing"
→ Respuesta adaptada a tu vocabulario habitual
```

---

## 📊 Estadísticas

**Velocidad de respuesta:**
- Pregunta simple: 2-3 segundos
- Con archivo adjunto: 5-8 segundos
- Análisis de imagen: 8-12 segundos

**Tamaño de archivos:**
- Presentación (5 slides): ~50 KB
- Documento (5 páginas): ~30 KB
- Hoja de cálculo: ~20 KB

**Límites:**
- WhatsApp: 100 MB por archivo
- Sin límite de mensajes por día
- Archivos temporales se eliminan automáticamente

---

## 🔧 Personalización Avanzada

### Crear nuevo tono de personalidad

1. Edita `configurar_agente.py`
2. Agrega en función `mostrar_menu_tonos()`:

```python
def mostrar_menu_tonos():
    # ... tonos existentes ...
    print("6. Sarcástico")
    # ...
```

3. Agrega prompt en `crear_prompt_personalizado()`:

```python
elif tono == 'sarcastico':
    return f"Eres {nombre}, un asistente IA con tono sarcástico..."
```

4. Ejecuta `python configurar_agente.py` y elige el nuevo tono

### Agregar comandos especiales

Edita `whatsapp_bot.js`, event handler `message`:

```javascript
if (mensajeLimpio === 'ayuda') {
    await message.reply('📋 Comandos disponibles:\n• ayuda\n• presentacion\n...');
    return;
}
```

---

## 🎉 ¡Todo Listo!

Ya tienes **rAImundoGPT** completamente funcional como contacto de WhatsApp.

### Checklist final:

- [ ] Node.js instalado
- [ ] `.\iniciar_whatsapp.bat` ejecutado
- [ ] QR escaneado
- [ ] Personalidad configurada
- [ ] Probado en grupo y privado
- [ ] Archivos funcionando

### Próximos pasos:

1. **Comparte el contacto** con tus amigos/colegas
2. **Agrégalo a grupos** relevantes
3. **Configura prefijos** personalizados si quieres
4. **Disfruta** tu asistente IA personal

---

## 📞 Soporte

Si algo no funciona:

1. **Revisa logs** en ambas terminales (Python y Node.js)
2. **Verifica Ollama**: `ollama list` debe mostrar `qwen2.5:7b`
3. **Verifica conexión**: Internet estable requerida
4. **Reinicia servicios**: Ctrl+C y volver a ejecutar

---

## 🏆 Ventajas vs Otros Asistentes

| Característica | rAImundoGPT | ChatGPT | Gemini | Copilot |
|----------------|-------------|---------|--------|---------|
| **WhatsApp nativo** | ✅ | ❌ | ❌ | ❌ |
| **Personalidad custom** | ✅ | ❌ | ❌ | ❌ |
| **Envío de archivos** | ✅ (.pptx, .docx, .xlsx) | ❌ | Limitado | ❌ |
| **Aprendizaje vocabulario** | ✅ | ❌ | ❌ | ❌ |
| **Google Workspace** | ✅ | Limitado | ✅ | Limitado |
| **Procesamiento local** | ✅ (Ollama GPU) | ❌ | ❌ | ❌ |
| **Vision AI** | ✅ | ✅ | ✅ | ✅ |
| **Gratis** | ✅ | Limitado | Limitado | Limitado |

---

## 📜 Licencia

MIT License - Úsalo como quieras, compártelo, modifícalo.

---

**Creado con 💜 por el equipo rAImundoGPT**

*"Oye wey, ahora sí ya la armaste con tu pinche bot chingón"* - Raymundo, 2026

---

## 🔗 Archivos Importantes

```
📁 Agentes/
├── 🤖 raymundo.py              # Agente principal unificado
├── 🌐 whatsapp_server.py       # Servidor Flask API
├── 📱 whatsapp_bot.js          # Bot de WhatsApp
├── ⚙️ configurar_agente.py     # Configurador de personalidad
├── 🚀 iniciar_whatsapp.bat     # Launcher automático
├── 📦 package.json             # Dependencias Node.js
├── 🔑 .env                     # API keys (GITHUB_TOKEN)
├── 🔐 google-credentials.json  # Credenciales Google
├── ⚙️ config_agente.json       # Configuración de personalidad
└── 🧠 memoria_agente.json      # Memoria y vocabulario aprendido
```

---

**Versión:** 2.0 (WhatsApp File Support + Learning System)  
**Fecha:** 6 de febrero de 2026
