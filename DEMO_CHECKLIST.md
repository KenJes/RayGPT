# 🎯 DEMO CHECKLIST — RAIGPT (Miércoles/Jueves)

> Fecha creada: 21 mayo 2026  
> Estado: **8 funciones rotas** que arreglar antes del demo.  
> Verificado con diagnóstico automático de módulos.

---

## ✅ FUNCIONA (no tocar)

| # | Función | Evidencia |
|---|---------|-----------|
| 1 | **Chat IA principal** (Groq → Mistral → Ollama) | Groq cargado, Mistral key OK |
| 2 | **Clima en tiempo real** (`🌤️ El tiempo`) | Open-Meteo, sin API key, probado OK |
| 3 | **Precios cripto** (`₿ Cripto`) | CoinGecko, sin API key, probado OK |
| 4 | **Generar imagen** (Pollinations.ai) | Sin API key, descarga PNG a `output/` |
| 5 | **Código QR** (`📲 Código QR`) | qrcode + Pillow instalados, probado OK |
| 6 | **NASA Foto del día** (`🔭 NASA hoy`) | APOD API, devuelve imagen + texto |
| 7 | **YouTube** (`buscar video`) | API key configurada, servicio conectado |
| 8 | **Crear Google Docs** (Service Account) | SA conectada, servicio inicializado |
| 9 | **Crear Google Slides** (Service Account) | SA conectada, servicio inicializado |
| 10 | **Crear Google Sheets** (Service Account) | SA conectada, servicio inicializado |
| 11 | **Adjuntar imagen/PDF** | PIL + DocumentProcessor OK |
| 12 | **TTS Edge** (DaliaNeural es-MX) | edge_tts instalado, voz neural |
| 13 | **STT Whisper** (grabación de voz) | whisper + sounddevice instalados |
| 14 | **🎓 Planeación Didáctica** (wizard en chat) | Nuevo wizard, probado OK |
| 15 | **Modo 😊 Amigable / 🔥 Sin filtros** | Personalidades cargan bien |
| 16 | **🗑️ Nueva conversación** | Limpia historial + BD |

---

## ❌ ROTO — Arreglar antes del demo

### 🔴 CRÍTICO (bloqueadores del demo)

---

#### ❌ 1. Ollama no está corriendo
**Síntoma:** Si Groq y Mistral fallan, toda respuesta de IA falla.  
**Causa:** El servidor Ollama no inicia automáticamente con Windows.  
**Cómo reproducir:** Sin Ollama, las respuestas fallan en frío.

**Solución:**
```
# Opción A — Ejecutar antes del demo:
ollama serve

# Opción B — Agregar al .bat de inicio (Iniciar Raymundo.bat):
start "" ollama serve
timeout /t 3 >nul
python raymundo.py
```
**Prioridad:** ⭐⭐⭐ Alta — LLM local es el fallback final  
**Tiempo estimado:** 10 min

---

#### ❌ 2. Gmail no funciona (OAuth expirado)
**Síntoma:** "Tengo correos nuevos?" → no muestra nada / error silencioso.  
**Causa:** `data/token.json` tiene refresh_token inválido (`invalid_grant: Bad Request`).  
Gmail **solo funciona con OAuth**, no con Service Account.

**Solución:**
```bash
# En terminal (con el .venv activado):
python resources/scripts/autorizar_google.py
# Se abre el navegador → autorizar con tu cuenta Google
# El nuevo token.json se guarda automáticamente
```
**Prioridad:** ⭐⭐⭐ Alta — Gmail es parte del demo  
**Tiempo estimado:** 5 min (solo clic en el navegador)

---

#### ❌ 3. Google Calendar devuelve vacío
**Síntoma:** "¿Qué tengo hoy?" → lista vacía aunque haya eventos.  
**Causa:** La Service Account tiene su propio calendario vacío, no ve el tuyo personal.  
El Service Account necesita que **compartas** tu calendario con su email.

**Solución:**
1. Ve a [calendar.google.com](https://calendar.google.com)
2. Clic en `⋮` junto a tu calendario → **"Configuración y uso compartido"**
3. En **"Compartir con personas específicas"** → agrega el email del SA:
   - Abre `resources/data/google-credentials.json`
   - Busca el campo `client_email` (algo como `axoloit@proyecto.iam.gserviceaccount.com`)
4. Dale permiso: **"Ver todos los detalles de los eventos"**

**ó** (más fácil para el demo): Re-autorizar OAuth (paso 2 arriba) para que use tu cuenta personal directamente.

**Prioridad:** ⭐⭐⭐ Alta — Calendar es parte del demo  
**Tiempo estimado:** 5 min

---

#### ❌ 4. Spotify no configurado
**Síntoma:** "Pon música" → "Spotify no está configurado"  
**Causa:** `client_id` y `client_secret` están vacíos en `config_agente.json`

**Solución:**
1. Ve a [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Crea una app → copia Client ID y Client Secret
3. Edita `config_agente.json`:
```json
"spotify": {
  "client_id": "TU_CLIENT_ID_AQUI",
  "client_secret": "TU_SECRET_AQUI",
  "redirect_uri": "http://127.0.0.1:5000/spotify/callback"
}
```
4. Inicia `whatsapp_server.py` (o cualquier servidor Flask)
5. Ve a `http://localhost:5000/spotify/auth` y autoriza
6. Reinicia Raymundo

**Si el demo es sin Spotify:** puedes simplemente esconder el chip `🎵 Pon música` comentando su línea en `raymundo.py`.

**Prioridad:** ⭐⭐ Media  
**Tiempo estimado:** 15-20 min

---

### 🟡 MODERADO (funciona parcialmente, puede fallar en vivo)

---

#### ⚠️ 5. Búsqueda web sin API key (Serper vacío)
**Síntoma:** "Busca X en internet" → puede devolver resultado pobre o error  
**Causa:** `SERPER_API_KEY` vacía en `config/.env`. El scraper básico puede funcionar pero es lento.

**Solución:**
- Ve a [serper.dev](https://serper.dev) → registro gratis → 100 búsquedas/mes
- Agrega la key en `config/.env`:
```
SERPER_API_KEY=tu_key_aqui
```
**ó** para el demo: evitar mostrar búsqueda web directa.

**Prioridad:** ⭐⭐ Media  
**Tiempo estimado:** 5 min

---

#### ⚠️ 6. ComfyUI no está corriendo
**Síntoma:** `🎭 ComfyUI` → "ComfyUI no está disponible"  
**Causa:** El servidor ComfyUI debe iniciarse manualmente en el puerto 8188.

**Solución para el demo:**
```bash
# En una terminal separada:
cd C:\ComfyUI   # o donde lo tengas instalado
python main.py --listen 0.0.0.0 --port 8188
```
O iniciarlo con `Iniciar Vision.bat` si ya está configurado ahí.

**Si no tienes ComfyUI instalado:** quitar el chip del demo o mostrar la imagen de Pollinations como alternativa.

**Prioridad:** ⭐ Baja (Pollinations ya funciona como alternativa)  
**Tiempo estimado:** 5 min si ya está instalado

---

#### ⚠️ 7. NASA usa DEMO_KEY (límite bajo)
**Síntoma:** Puede fallar con error 429 (Too Many Requests) si se llama varias veces.  
**Causa:** `NASA_API_KEY` no está configurada → usa `DEMO_KEY` que tiene límite de 30 req/hora.

**Solución:**
1. Regístrate gratis en [api.nasa.gov](https://api.nasa.gov) → key llega por email
2. Agrega en `config/.env`:
```
NASA_API_KEY=tu_key_aqui
```
3. En `core/extra_tools.py` verificar que `NasaClient` use `os.environ.get('NASA_API_KEY', 'DEMO_KEY')`

**Prioridad:** ⭐ Baja  
**Tiempo estimado:** 10 min

---

#### ⚠️ 8. DeepFace panel requiere Python 3.12 separado
**Síntoma:** El botón `🎭 DeepFace (8 funciones)` puede fallar si el worker no inicia  
**Causa:** DeepFace corre en un subprocess con Python 3.12 (el venv principal es otra versión)

**Verificar:**
```bash
python --version   # debe ser 3.12.x en el subprocess
python resources/tests/test_deepface.py
```
**Si falla:** mostrar el panel pero solo demostrar con imágenes previamente guardadas en `data/face_db/`

**Prioridad:** ⭐ Baja (feature opcional para el demo)  
**Tiempo estimado:** variable (depende de instalación de Python 3.12)

---

## 📋 ORDEN RECOMENDADO PARA HOY

```
□ 1. Autorizar Google OAuth  (5 min)  → arregla Gmail + Calendar personal
□ 2. Compartir Calendar con SA ó usar OAuth (5 min)
□ 3. Configurar inicio de Ollama en el .bat  (10 min)
□ 4. Configurar Spotify  (15 min)  → solo si lo quieres en el demo
□ 5. Agregar Serper API key  (5 min)
□ 6. Verificar DeepFace  (15 min)
□ 7. Hacer prueba completa end-to-end  (30 min)
```

---

## 🧪 SCRIPT DE PRUEBA RÁPIDA PRE-DEMO

Ejecuta esto 30 min antes del demo para confirmar que todo funciona:

```bash
cd "c:\Users\kenne\Visual Studio Code\Agentes"
.venv\Scripts\python.exe -c "
from dotenv import load_dotenv; load_dotenv('config/.env')
from core.extra_tools import WeatherClient, CryptoClient, NasaClient, QRGenerator, ImageGenerator
print('CLIMA:', WeatherClient().get_current('Monterrey')[:50])
print('CRIPTO:', CryptoClient().get_price('bitcoin')[:50])
print('NASA:', NasaClient().apod().get('texto','')[:50])
print('QR:', QRGenerator().generate('demo')['success'])
print('IMAGEN:', ImageGenerator().generate('cat')['success'])
"
```

---

## 🎤 GUIÓN SUGERIDO PARA EL DEMO

1. **Chat básico** → "Hola, ¿cómo estás?" → respuesta con personalidad
2. **Clima** → chip "🌤️ El tiempo" + "Monterrey" → resultado en tiempo real
3. **Cripto** → chip "₿ Cripto" → precio Bitcoin con gráfico
4. **NASA** → chip "🔭 NASA hoy" → foto astronómica del día (con imagen en chat)
5. **Generar imagen** → chip "🎨 Generar imagen" + prompt → imagen en chat
6. **QR** → chip "📲 Código QR" + URL → QR en chat
7. **Google Docs** → "Crea un documento sobre IA" → link en Google Docs
8. **Google Slides** → "Crea una presentación sobre Python" → link en Slides
9. **Gmail** → chip "📧 Mis correos" → lista de correos (requiere OAuth arreglado)
10. **Calendario** → chip "📅 ¿Qué tengo hoy?" (requiere arreglo)
11. **Voz** → botón "🎤 Grabar voz" → pregunta → respuesta + TTS
12. **🎓 Planeación Didáctica** → botón verde → wizard paso a paso en chat

---

*Archivo generado automáticamente con diagnóstico del 21/05/2026.*
