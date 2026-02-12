# 📊 Sistema de Monitoreo de Tokens y Estadísticas

## 🎯 Descripción

Raymundo ahora incluye un sistema completo de tracking de tokens, requests y estadísticas de uso para monitorear el consumo de APIs y el desempeño del agente.

## ✨ Características

### 🔍 Métricas Rastreadas

1. **Tokens Consumidos**
   - Tokens de Ollama (modelo local)
   - Tokens de GPT-4o (modelo cloud)
   - Total combinado

2. **Requests**
   - Total de requests procesados
   - Requests por tipo (chat, presentación, documento, etc.)
   - Tiempo promedio de respuesta

3. **Errores**
   - Cantidad total de errores
   - Tasa de éxito (%)

4. **Rate Limits (Free Tier)**
   - GitHub Models Free: 15 RPM, 150 RPD, 150K TPM
   - Monitoreo de uso vs límites
   - Ollama: Sin límites (local)

5. **Uptime**
   - Tiempo desde que se inició el servidor
   - Timestamp del último request

## 🚀 Uso

### 📱 Desde WhatsApp

Para ver las estadísticas, envía alguno de estos comandos:

```
/raymundo stats
/raymundo estadisticas
/raymundo estado
```

**Respuesta:**
```
📊 **ESTADÍSTICAS DE RAYMUNDO**

🟢 **Estado:** ✅ Operativo
⏰ **Uptime:** 2d 5h 34m
🆓 **Plan:** GitHub Models Free + Ollama Local

📈 **Uso General:**
• Total requests: 247
• Errores: 3
• Tasa de éxito: 98.8%
• Tiempo promedio: 2.45s

🤖 **Tokens Consumidos:**
• Ollama (local): 45,230 🆓
• GPT-4o (cloud): 128,450 🆓
• **Total**: 173,680

📊 **Rate Limits (GitHub Models Free):**
• Tokens/Minuto: 128,450 / 150,000 TPM (85.6%)
• Requests/Día: 247 / 150 RPD (164.7%)

📋 **Requests por Tipo:**
• Chat: 189
• Presentaciones: 12
• Documentos: 25
• Hojas de cálculo: 8
• Web scraping: 11
• Correcciones: 2
• Visión/Imágenes: 0

🕐 **Último request:** 2024-01-15T14:32:18

💡 **Nota:** Todo el uso es gratuito dentro de los límites del Free Tier
```

### 🌐 Via API REST

#### Ver Estadísticas (JSON)

```bash
curl http://localhost:5000/stats
```

**Respuesta:**
```json
{
  "estado": "✅ Operativo",
  "inicio": "2024-01-13T09:00:00",
  "uptime": "2d 5h 34m",
  "total_requests": 247,
  "tokens": {
    "ollama_local": 45230,
    "gpt4o_cloud": 128450,
    "total": 173680
  },
  "requests_por_tipo": {
    "chat": 189,
    "presentacion": 12,
    "documento": 25,
    "hoja_calculo": 8,
    "web_scraping": 11,
    "correccion": 2,
    "vision": 0
  }tier": "🆓 Gratuito",
  "rate_limits": {
    "tokens_pm": "128,450 / 150,000 TPM",
    "requests_dia": "247 / 150 RPD",
    "uso_tpm": "85.6%",
    "uso_rpd": "164.7%"
  }
  "errores": 3,
  "tasa_exito": "98.8%",
  "tiempo_promedio_respuesta": "2.45s",
  "ultimo_request": "2024-01-15T14:32:18",
  "costo_estimado_usd": "$5.7803",
  "conversaciones": {
    "activas": 5,
    "total_mensajes": 124,
    "usuarios": ["user1", "user2", "user3"]
  }
}
```

#### Ver Estadísticas (Texto para WhatsApp)

```bash
curl "http://localhost:5000/stats?format=text"
```

#### Reiniciar Métricas

```bash
curl -X POST http://localhost:5000/metrics/reset
```

**Respuesta:**
```json
{
  "message": "Métricas reiniciadas exitosamente",
  "nuevo_inicio": "2024-01-15T14:45:00"
}
```

## 📁 Archivos Involucrados

### 1. `metrics_tracker.py`

Clase principal del sistema de métricas:

```python
class MetricsTracker:
    def __init__(self, metrics_file='metrics.json')
    def track_request(tipo, tokens_used, modelo, tiempo_respuesta, user_id)
    def track_error()
    def get_stats()
    def get_stats_formatted()
    def reset_metrics()
```

### 2. `metrics.json`

Archivo persistente que almacena todas las métricas:

```json
{
  "inicio": "2024-01-13T09:00:00",
  "total_requests": 247,
  "total_tokens_ollama": 45230,
  "total_tokens_gpt4o": 128450,
  "requests_por_tipo": {
    "chat": 189,
    "presentacion": 12,
    "documento": 25,
    "hoja_calculo": 8,
    "web_scraping": 11,
    "correccion": 2,
    "vision": 0
  },
  "errores": 3,
  "tiempo_promedio_respuesta": 2.45,
  "usuarios_unicos": 5,
  "ultimo_request": "2024-01-15T14:32:18"
}
```

### 3. Modificaciones en `raymundo.py`

**OllamaClient:**
```python
def __init__(self):
    self.last_tokens_used = 0  # ← Nuevo atributo

def generate(self, prompt, ...):
    # ...
    self.last_tokens_used = data.get('eval_count', 0)  # ← Captura tokens
    return data.get('response', '')
```

**GitHubModelsClient:**
```python
def __init__(self):
    self.last_tokens_used = 0  # ← Nuevo atributo

def chat(self, messages, ...):
    # ...
    if hasattr(response, 'usage'):
        self.last_tokens_used = response.usage.total_tokens  # ← Captura tokens
    return response.choices[0].message.content
```

### 4. Modificaciones en `whatsapp_server.py`

**Imports:**
```python
from metrics_tracker import MetricsTracker
import time
```

**Inicialización:**
```python
metrics = MetricsTracker('metrics.json')
```

**Tracking automático:**
```python
tiempo_inicio = time.time()
# ... procesar mensaje ...
tiempo_respuesta = time.time() - tiempo_inicio

tokens_ollama = ollama.last_tokens_used
tokens_gpt4o = github.last_tokens_used

if tokens_gpt4o > 0:
    metrics.track_request(
        tipo='chat',
        tokens_used=tokens_gpt4o,
        modelo='gpt4o',
        tiempo_respuesta=tiempo_respuesta,
        user_idrate limits

```python
import requests

response = requests.get('http://localhost:5000/stats')
stats = response.json()

# Verificar uso de rate limits
uso_tpm = float(stats['rate_limits']['uso_tpm'].replace('%', ''))
uso_rpd = float(stats['rate_limits']['uso_rpd'].replace('%', ''))

if uso_rpd > 90:
    print("⚠️ ALERTA: Cerca del límite de requests diarios (150 RPD)")
    
if uso_tpm > 80:
    print("⚠️ ALERTA: Alto uso de tokens por minuto (150K TPM)

costo = float(stats['costo_estimado_usd'].replace('$', ''))
print(f"Costo acumulado: ${costo:.2f} USD")

if costo > 10.0:
    print("⚠️ ALERTA: Costo superó $10 USD")
```

### Dashboard simple en terminal

```bash
# Linux/Mac
watch -n 10 'curl -s "http://localhost:5000/stats?format=text"'

# PowerShell
while ($true) { curl "http://localhost:5000/stats?format=text"; Start-Sleep -Seconds 10; cls }
```

### Exportar métricas a CSV

```python
import requests
import csv
from datetime import datetime

stats = requests.get('http://localhost:5000/stats').json()

with open('metricas.csv', 'a', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        datetime.now(),
        stats['total_requests'],
        stats['tokens']['total'],
        stats['costo_estimado_usd'],
        stats['tasa_exito']
    ])
```

## 🎨 Personalización

### Agregar nuevos tipos de request

En `metrics_tracker.py`, modifica el diccionario inicial:

```python
'requests_por_tipo': {
    'chat': 0,
    'presentacion': 0,
    'documenlímites de rate limit

En `metrics_tracker.py`, método `get_stats()`:

```python
# Ajustar límites según tu plan
tpm_limit = 150000  # tokens por minuto (Free Tier)
rpd_limit = 150     # requests por día (Free Tier)

# Para plan de pago, ajusta estos valores
# tpm_limit = 2000000  # Example: Paid tier
# rpd_limit = 1000

### Cambiar formato de costo

En `metrics_tracker.py`, método `get_stats()`:

```python
# Cambiar pricing de GPT-4o
tokens_gpt4o = self.metrics['total_tokens_gpt4o']
costo_estimado = (tokens_gpt4o / 1000) * 0.045  # ← Ajustar aquí
```

### Agregar alertas

```python
def track_request(self, ...):
    # ... código existente ...
    
    # Alerta de tokens
    if self.metrics['total_tokens_gpt4o'] > 100000:
        print("⚠️ ALERTA: Más de 100K tokens consumidos")
    
    # Alerta de errores
    tasa_error = self.metrics['errores'] / self.metrics['total_requests']
    if tasa_error > 0.05:  # 5%
        print("⚠️ ALERTA: Tasa de error alta")
```

## 🔧 Troubleshooting

### Las métricas no se guardan

**Problema:** El archivo `metrics.json` no persiste entre reinicios.

**Solución:** Verifica permisos de escritura:
```bash
# Linux/Mac
chmod 666 metrics.json

# Windows PowerShell
icacls metrics.json /grant Everyone:F
```

### Tokens siempre en 0

**Problema:** `last_tokens_used` siempre es 0.

**Posibles causas:**
1. API no devuelve `usage` en respuesta
2. Modelo local no devuelve `eval_count`

**Debug:**
```pRate limits excedidos

**Problema:** Recibes errores 429 (Too Many Requests).

**Solución:** GitHub Models Free Tier tiene límites:
- **15 RPM** (Requests Per Minute)
- **150 RPD** (Requests Per Day)  
- **150K TPM** (Tokens Per Minute)

Implementa rate limiting en el código:
```python
import time
from datetime import datetime, timedelta

# Trackear timestamps de requests
request_times = []

def check_rate_limit():
    now = datetime.now()
    # Eliminar requests más viejos de 1 minuto
    request_times[:] = [t for t in request_times if now - t < timedelta(minutes=1)]
    
    if len(request_times) >= 15:
        print("⚠️ Rate limit alcanzado, esperando...")
        time.sleep(60)
    
    request_times.append(now)
```
**Problema:** El costo estimado no coincide con GitHub Models billing.

**Solución:** GitHub Models tiene pricing diferenciado:
- Input tokens: $0.03/1K
- Output tokens: $0.06/1K

El cálculo actual usa promedio 50/50. Para mayor precisión, captura `prompt_tokens` y `completion_tokens` por separado.

## 📊 Métricas Avanzadas (Futuras)
 Importantes

- **GitHub Models es GRATUITO** con límites de rate (15 RPM, 150 RPD, 150K TPM)
- **Ollama es 100% gratuito** (se ejecuta localmente)
- Las métricas se persisten en `metrics.json` automáticamente
- El archivo se crea la primera vez que se inicia el servidor
- Los tokens de Ollama son aproximados (cuenta output tokens)
- Los tokens de GPT-4o son exactos (vienen de la API)
- Monitorea el **uso de rate limits** para evitar errores 429

### 🆓 GitHub Models Free Tier

El tier gratuito incluye:
- ✅ Acceso a GPT-4o, GPT-4o-mini, Phi-3, Llama 3, etc.
- ✅ Sin tarjeta de crédito requerida
- ✅ 150 requests por día
- ✅ 150K tokens por minuto
- ⚠️ No para producción de alto volumen

Fuente: [GitHub Models Docs](https://github.com/marketplace/models)

2. **Gráficos**
   - Integración con Grafana/Prometheus
   - Dashboard web con Chart.js

3. **Alertas automáticas**
   - Email cuando el costo supera umbral
   - Webhook a Slack/Discord

4. **Análisis temporal**
   - Tokens por hora del día
   - Días de mayor uso
   - Proyección de costos mensual

5. **Caché inteligente**
   - Detectar preguntas repetidas
   - Cachear respuestas comunes
   - Reducir consumo de tokens

## 📝 Notas

- Las métricas se persisten en `metrics.json` automáticamente
- El archivo se crea la primera vez que se inicia el servidor
- Los tokens de Ollama son aproximados (cuenta output tokens)
- Los tokens de GPT-4o son exactos (vienen de la API)
- El costo es **estimado** basado en pricing público

## 🔐 Seguridad

- **No expongas** el endpoint `/stats` públicamente sin autenticación
- El archivo `metrics.json` puede contener información sensible
- Considera encriptar o proteger con permisos restrictivos

## 📚 Referencias

- [GitHub Models Pricing](https://github.com/features/models)
- [Azure AI Inference API Docs](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Ollama API Reference](https://github.com/ollama/ollama/blob/main/docs/api.md)

---

**Autor:** Raymundo AI Team  
**Versión:** 1.0  
**Última actualización:** 2024-01-15
