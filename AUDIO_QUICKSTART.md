# 🎙️ GUÍA RÁPIDA: AUDIO EN RAYMUNDO

## ¿Qué es?
Raymundo ahora puede **hablar y escuchar**. Puedes enviarle mensajes de voz y te responderá con audio.

---

## 🚀 Instalación (3 pasos)

### 1️⃣ Ejecuta el script de instalación

**Windows:**
```bash
instalar_audio.bat
```

**Linux/Mac:**
```bash
chmod +x instalar_audio.sh
./instalar_audio.sh
```

### 2️⃣ Descarga una voz

1. Ve a: https://github.com/rhasspy/piper/releases/tag/v1.2.0
2. Busca y descarga: `es_ES-claude-medium.onnx` y `es_ES-claude-medium.onnx.json`
3. Guárdalos en: `resources/data/audio/voices/`

### 3️⃣ Prueba el sistema

```bash
python resources/tests/test_audio.py
```

---

## 💬 Cómo usar

### En la aplicación de escritorio

1. **Grabar voz:**
   - Haz clic en el botón 🎤
   - Habla tu pregunta
   - Haz clic en ⏹️ para detener
   - El texto aparecerá automáticamente

2. **Escuchar respuesta:**
   - Después de recibir una respuesta
   - Haz clic en el botón 🔊
   - Escucharás la respuesta en audio

### En WhatsApp

1. **Envía un mensaje de voz** a Raymundo
2. **Automáticamente:**
   - Transcribe tu audio
   - Procesa tu pregunta
   - Te responde con un mensaje de voz

---

## ❓ Problemas comunes

### "FFmpeg no encontrado"
```bash
# Windows
choco install ffmpeg

# Linux
sudo apt install ffmpeg

# Mac
brew install ffmpeg
```

### "Piper TTS no disponible"
- Asegúrate de haber descargado la voz (paso 2)
- Verifica que esté en `resources/data/audio/voices/`

### "Error en WhatsApp con audio"
- Verifica que el servidor Flask esté corriendo: `python whatsapp_server.py`
- Verifica que instalaste las dependencias: `npm install`

---

## 📚 Más información

Lee [AUDIO_INTEGRATION.md](AUDIO_INTEGRATION.md) para:
- Configuración avanzada
- API endpoints
- Personalización de voces
- Troubleshooting detallado

---

## ✨ Características

- ✅ Síntesis de voz local (Piper TTS)
- ✅ Reconocimiento de voz (Whisper)
- ✅ Chat por voz en WhatsApp
- ✅ Interfaz con botones de audio
- ✅ Respuestas automáticas en audio
- ✅ Procesamiento rápido (~1s por respuesta)

---

**¿Necesitas ayuda?** Revisa [AUDIO_INTEGRATION.md](AUDIO_INTEGRATION.md) o ejecuta el test: `python resources/tests/test_audio.py`
