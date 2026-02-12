# ⚠️ Rate Limits de GitHub Models (Free Tier)

## 🚨 Error 429: RateLimitReached

Si ves este error, has alcanzado los límites del **Free Tier** de GitHub Models.

## 📊 Límites del Free Tier

GitHub Models ofrece acceso gratuito con los siguientes límites:

| Límite | Valor | Descripción |
|--------|-------|-------------|
| **RPM** | 15 | Requests por minuto |
| **RPD** | 150 | Requests por día |
| **TPM** | 150,000 | Tokens por minuto |

## 🔄 Solución Automática

**Raymundo tiene fallback automático implementado:**

Cuando se alcanza el rate limit:
1. ✅ Detecta el error 429 automáticamente
2. 🔄 Cambia a **Ollama** (modelo local, sin límites)
3. 📢 Te notifica con el mensaje: `⚠️ *[Modo local - Rate limit alcanzado]*`
4. 🚀 Continúa funcionando sin interrupciones

**Ejemplo de respuesta con fallback:**
```
⚠️ *[Modo local - Rate limit alcanzado]*

Claro, puedo ayudarte con eso...
```

## ⏰ ¿Cuándo se reinician los límites?

- **RPM (15 por minuto):** Se reinicia cada minuto
- **RPD (150 por día):** Se reinicia a las 00:00 UTC
- **TPM (150K por minuto):** Se reinicia cada minuto

## 📉 Reducir el Consumo

### 1. Usar Ollama directamente para tareas simples

Modifica el código para usar solo Ollama en chats casuales:

```python
# En whatsapp_server.py
if 'simple' in mensaje.lower():
    # Usar solo Ollama
    respuesta = gestor.ollama.generate(mensaje)
else:
    # Usar híbrido (GPT-4o + fallback)
    respuesta = gestor.chat_hibrido(mensaje)
```

### 2. Implementar caché de respuestas

```python
# Cache para preguntas repetidas
cache_respuestas = {}

def get_cached_or_generate(mensaje):
    if mensaje in cache_respuestas:
        return cache_respuestas[mensaje]
    
    respuesta = gestor.chat_hibrido(mensaje)
    cache_respuestas[mensaje] = respuesta
    return respuesta
```

### 3. Limitar requests por usuario

```python
# En whatsapp_server.py
usuarios_requests = {}
MAX_REQUESTS_POR_HORA = 10

def check_user_limits(user_id):
    now = datetime.now()
    if user_id not in usuarios_requests:
        usuarios_requests[user_id] = []
    
    # Filtrar requests de última hora
    usuarios_requests[user_id] = [
        t for t in usuarios_requests[user_id] 
        if now - t < timedelta(hours=1)
    ]
    
    if len(usuarios_requests[user_id]) >= MAX_REQUESTS_POR_HORA:
        return False
    
    usuarios_requests[user_id].append(now)
    return True
```

### 4. Priorizar Ollama para funciones específicas

```python
# Correcciones ortográficas → Solo Ollama (rápido, sin consumir GPT-4o)
# Web scraping → GPT-4o (mejor análisis)
# Documentos/Presentaciones → GPT-4o (mejor calidad)
# Chat casual → Ollama (suficiente para conversación)
```

## 🎯 Estrategia Recomendada

```python
def elegir_modelo(tipo_tarea, complejidad):
    """
    Elige el modelo óptimo según la tarea
    """
    if tipo_tarea in ['chat_casual', 'correccion', 'optimizacion']:
        # Tareas simples → Ollama
        return 'ollama'
    
    elif tipo_tarea in ['documento', 'presentacion', 'hoja_calculo']:
        # Generación de contenido → GPT-4o
        return 'gpt4o'
    
    elif tipo_tarea == 'web_scraping':
        # Análisis complejo → GPT-4o
        return 'gpt4o'
    
    else:
        # Por defecto, híbrido con fallback
        return 'hibrido'
```

## 💡 Verificar Estado de Límites

```bash
# Ver estadísticas actuales
curl "http://localhost:5000/stats?format=text"
```

O desde WhatsApp:
```
/raymundo stats
```

**Salida esperada:**
```
📊 Rate Limits (GitHub Models Free):
• Tokens/Minuto: 145,230 / 150,000 TPM (96.8%)  ⚠️ CERCA DEL LÍMITE
• Requests/Día: 142 / 150 RPD (94.7%)          ⚠️ CERCA DEL LÍMITE
```

## 🔓 Actualizar a Plan de Pago (Futuro)

Si necesitas más capacidad:

1. **Azure OpenAI Service** (plan de pago)
   - Sin límites estrictos de RPM/RPD
   - Pago por uso (pay-as-you-go)
   - Mejor para producción

2. **Ollama Pro (cuando exista)**
   - Modelos más grandes localmente
   - Sin costos de API

3. **Hosting propio de modelos**
   - Llama 3, Mistral, etc.
   - Control total, sin límites

## 📚 Referencias

- [GitHub Models Docs](https://github.com/marketplace/models)
- [Azure AI Rate Limits](https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits)
- [Ollama Documentation](https://github.com/ollama/ollama)

## ✅ Estado Actual de Raymundo

| Feature | Estado |
|---------|--------|
| Detección de error 429 | ✅ Implementado |
| Fallback automático a Ollama | ✅ Implementado |
| Notificación al usuario | ✅ Implementado |
| Tracking de rate limits | ✅ Implementado (`/stats`) |
| Caché de respuestas | ❌ Por implementar |
| Rate limiting preventivo | ❌ Por implementar |

---

**Última actualización:** Febrero 6, 2026  
**Versión:** 2.1
