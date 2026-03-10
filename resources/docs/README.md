# rAImundoGPT - Agente IA para WhatsApp

**Asistente de inteligencia artificial con personalidad customizable que funciona como contacto de WhatsApp**

---

## Que es esto?

Un agente IA completo que puedes agregar como contacto de WhatsApp y usar en grupos. Tiene:

- Personalidad customizable (profesional, amigable, tecnico, creativo, puteado)
- Responde en grupos y mensajes privados
- Crea y envia presentaciones PowerPoint (.pptx)
- Crea y envia documentos Word (.docx)
- Crea y envia hojas de calculo Excel (.xlsx)
- Analiza imagenes (Vision AI)
- Lee documentos (PDF, DOCX, TXT)
- Google Workspace integrado
- Aprende tu vocabulario y lo usa en respuestas

---

## Inicio Rapido (3 pasos)

### 1. Instalar Node.js

```
https://nodejs.org/
```

Descarga e instala la version LTS (recomendada).

### 2. Ejecutar el launcher

```powershell
.\iniciar_whatsapp.bat
```

Este script automaticamente:
- Verifica Node.js y Python
- Instala todas las dependencias
- Inicia servidor Python (Flask)
- Inicia bot de WhatsApp (Node.js)

### 3. Escanear codigo QR

1. Se abrira una ventana con codigo QR
2. Abre WhatsApp en tu telefono
3. Ve a **Ajustes > Dispositivos vinculados**
4. Escanea el QR
5. Listo!

---

## Configurar Personalidad

### Metodo 1: Configurador interactivo (recomendado)

```powershell
python configurar_agente.py
```

**Opciones de personalidad:**

1. **Profesional**: Formal, educado, corporativo
2. **Amigable**: Casual, cercano, simpatico
3. **Tecnico**: Preciso, detallado, especializado
4. **Creativo**: Innovador, expresivo, original
5. **Puteado**: Irreverente, groserias, faltas ortograficas (estilo mexicano)

El configurador te permite:
- Elegir nombre del agente
- Seleccionar tono de personalidad
- Ajustar temperaturas (creatividad)
- Personalizar colores de interfaz
- Guardar configuracion en `config_agente.json`

### Metodo 2: Editar config_agente.json

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

## Uso en WhatsApp

### Comando unico:

**El bot SOLO responde cuando usas el comando `/raymundo`**

Esto evita que responda a mensajes accidentales y protege tu privacidad.

### En grupos:

```
/raymundo crea una presentacion sobre blockchain
/raymundo explica machine learning
/raymundo que es docker
```

### En mensajes privados:

```
/raymundo crea una presentacion sobre inteligencia artificial
/raymundo explicame python
/raymundo ayuda con mi codigo
```

**Importante:**
- `/raymundo` (con diagonal) - FUNCIONA
- `raymundo` (sin diagonal) - NO funciona
- `@raymundo` - NO funciona
- `RAImundo` - NO funciona

---

## Archivos que puede enviar

| Tipo | Comando | Archivo |
|------|---------|---------|
| **Presentacion** | "crea presentacion sobre X" | .pptx |
| **Documento** | "crea documento sobre X" | .docx |
| **Hoja de calculo** | "crea tabla de X" | .xlsx |

Todos los archivos se envian automaticamente y son descargables directamente desde WhatsApp.

---

## Aprendizaje de Vocabulario

Raymundo aprende las palabras que usas con frecuencia y las incorpora en sus respuestas.

Por ejemplo:
```
Tu: "/raymundo wey, necesito una presentacion chida sobre APIs"

[Despues de varias conversaciones]

Raymundo: "oye wey, aqui ta tu presentacion chida sobre APIs ps..."
```

El vocabulario se guarda en `memoria_agente.json` y se actualiza automaticamente.

---

## Configuracion Avanzada

### Cambiar prefijos del bot

Edita `whatsapp_bot.js`, linea ~28:

```javascript
COMANDO: '/raymundo',  // Cambiar a otro comando como '/bot' o '/ai'
```

### Cambiar puerto del servidor

Edita `whatsapp_server.py`, linea ~230:

```python
app.run(port=5000)  # Cambiar a otro puerto
```

---

## Arquitectura Tecnica

```
WhatsApp (tu telefono)
    |
whatsapp_bot.js (Node.js)
    | HTTP
whatsapp_server.py (Flask API)
    |
raymundo.py (Agente IA)
    |
Ollama (GPU local) + GPT-4o (cloud)
    |
Google Workspace APIs
```

**Componentes:**
- **Ollama**: Procesamiento local con GPU (llama3.1:8b)
- **GPT-4o**: Respuestas avanzadas cloud (GitHub Models)
- **Vision AI**: Analisis de imagenes
- **Google Workspace**: Docs, Sheets, Slides, Drive, Calendar
- **Sistema de memoria**: Aprende vocabulario y contexto

---

## Requisitos

### Software:
- Python 3.9+ 
- Node.js 16+ (descargar de nodejs.org)
- Ollama 0.15.4+ (para procesamiento local)

### Cuentas/Credenciales:
- GitHub Token (para GPT-4o): En archivo `.env`
- Google Service Account (para Workspace): `google-credentials.json`
- WhatsApp instalado en telefono

### Dependencias Python (se instalan automaticamente):
```
flask
flask-cors
azure-ai-inference
requests
PyPDF2
python-docx
Pillow
```

### Dependencias Node.js (se instalan automaticamente):
```
whatsapp-web.js
qrcode-terminal
axios
```

---

## Problemas Comunes

### Bot no responde en grupos

Solucion: Usa el comando correcto con diagonal:
```
Mal: "raymundo que es python"
Bien: "/raymundo que es python"
```

### "ECONNREFUSED" al enviar mensaje

Causa: Servidor Python no esta corriendo.

Solucion:
```powershell
python whatsapp_server.py
```

### QR no aparece

Solucion: Elimina sesion y reinicia:
```powershell
Remove-Item -Recurse whatsapp_session
node whatsapp_bot.js
```

### Archivos no se envian

Verificar:
1. Google Workspace configurado (`google-credentials.json`)
2. Credenciales tienen scope `drive` para exportar
3. Carpeta `whatsapp_temp/` existe (se crea automaticamente)

---

## Seguridad

### NO compartas:
- `whatsapp_session/` (tu sesion de WhatsApp)
- `.env` (API keys)
- `google-credentials.json` (credenciales)

### Agregar a .gitignore:
```
whatsapp_session/
whatsapp_temp/
.env
google-credentials.json
memoria_agente.json
```

---

## Deploy 24/7 (Opcional)

Si quieres que este activo todo el tiempo, necesitas un servidor VPS:

### Proveedores recomendados:
- DigitalOcean: $6/mes
- Linode: $5/mes
- AWS Lightsail: $3.50/mes

### Setup en Ubuntu:
```bash
sudo apt update
sudo apt install nodejs npm python3 python3-pip

git clone tu-repo
cd tu-repo

npm install
pip3 install flask flask-cors

npm install -g pm2
pm2 start whatsapp_server.py --interpreter python3 --name raymundo
pm2 start whatsapp_bot.js --name whatsapp-bot
pm2 save
pm2 startup
```

Nota: Tendras que vincular WhatsApp cada vez que el servidor reinicie (QR).

---

## Casos de Uso

### 1. Asistente tecnico en grupos de trabajo

```
Grupo: "Alguien sabe Docker?"
Tu: "/raymundo explica Docker"
Raymundo: "ps wey docker es como..."
```

### 2. Creacion rapida de documentos

```
"/raymundo crea presentacion para mi reunion de ventas Q1"
-> Recibe archivo.pptx listo para presentar
```

### 3. Analisis de codigo

```
[Envias screenshot de codigo]
"/raymundo que hace este codigo?"
-> Analisis detallado con Vision AI
```

### 4. Educacion personalizada

```
"/raymundo explica quantum computing"
-> Respuesta adaptada a tu vocabulario habitual
```

---

## Estadisticas

**Velocidad de respuesta:**
- Pregunta simple: 2-3 segundos
- Con archivo adjunto: 5-8 segundos
- Analisis de imagen: 8-12 segundos

**Tamanio de archivos:**
- Presentacion (5 slides): ~50 KB
- Documento (5 paginas): ~30 KB
- Hoja de calculo: ~20 KB

**Limites:**
- WhatsApp: 100 MB por archivo
- Sin limite de mensajes por dia
- Archivos temporales se eliminan automaticamente

---

## Personalizacion Avanzada

### Crear nuevo tono de personalidad

1. Edita `configurar_agente.py`
2. Agrega en funcion `mostrar_menu_tonos()`:

```python
def mostrar_menu_tonos():
    # ... tonos existentes ...
    print("6. Sarcastico")
```

3. Agrega prompt en `crear_prompt_personalizado()`:

```python
elif tono == 'sarcastico':
    return f"Eres {nombre}, un asistente IA con tono sarcastico..."
```

4. Ejecuta `python configurar_agente.py` y elige el nuevo tono

### Agregar comandos especiales

Edita `whatsapp_bot.js`, event handler `message`:

```javascript
if (mensajeLimpio === 'ayuda') {
    await message.reply('Comandos disponibles:\n- ayuda\n- presentacion\n...');
    return;
}
```

---

## Ventajas vs Otros Asistentes

| Caracteristica | rAImundoGPT | ChatGPT | Gemini | Copilot |
|----------------|-------------|---------|--------|---------|
| WhatsApp nativo | Si | No | No | No |
| Personalidad custom | Si | No | No | No |
| Envio de archivos (.pptx, .docx, .xlsx) | Si | No | Limitado | No |
| Aprendizaje vocabulario | Si | No | No | No |
| Google Workspace | Si | Limitado | Si | Limitado |
| Procesamiento local (Ollama GPU) | Si | No | No | No |
| Vision AI | Si | Si | Si | Si |
| Gratis | Si | Limitado | Limitado | Limitado |

---

## Archivos Importantes

```
Agentes/
    raymundo.py              # Agente principal
    whatsapp_server.py       # Servidor Flask API
    resources/whatsapp/
        whatsapp_bot.js      # Bot de WhatsApp
    resources/scripts/
        configurar_agente.py # Configurador de personalidad
    .env                     # API keys (GITHUB_TOKEN)
    google-credentials.json  # Credenciales Google
    config_agente.json       # Configuracion de personalidad
    data/memoria_agente.json # Memoria y vocabulario aprendido
```

---

## Soporte

Si algo no funciona:

1. Revisa logs en ambas terminales (Python y Node.js)
2. Verifica Ollama: `ollama list` debe mostrar `llama3.1:8b`
3. Verifica conexion: Internet estable requerida
4. Reinicia servicios: Ctrl+C y volver a ejecutar

---

**Version:** 3.0  
**Licencia:** MIT

