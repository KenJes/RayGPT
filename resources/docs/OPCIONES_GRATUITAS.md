# 🆓 Alternativas GRATUITAS para Raymundo

## Para uso personal sin fines de lucro - Sin pagar nada

---

## 🥇 OPCIÓN #1: **Groq** (LA MEJOR - RECOMENDADA)

### ¿Por qué Groq?
- ✅ **100% GRATIS** - Sin tarjeta de crédito
- 🚀 **Ultra rápido** (500+ tokens/segundo)
- 📊 **Límites generosos**: 30 RPM, **14,400 RPD** (96x más que GitHub Models!)
- 🤖 **Modelos potentes**: Llama 3.1 70B, Mixtral 8x7B
- 🎯 **Sin restricciones de personalidad** (puedes usar lenguaje soez)
- ⚡ **Respuestas instantáneas**

### Rate Limits (Free Tier)

| Límite | Valor | vs GitHub Models |
|--------|-------|------------------|
| **RPM** | 30 | 2x mejor |
| **RPD** | **14,400** | **96x mejor** 🔥 |
| **TPM** | 250,000 | 1.6x mejor |

**14,400 requests/día = suficiente para ti y 10+ amigos usando intensivamente**

### Implementación en Raymundo

```python
# pip install groq

import os
from groq import Groq

class GroqClient:
    """Cliente para Groq API (100% gratis)"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.client = Groq(api_key=self.api_key)
        self.model = "llama-3.1-70b-versatile"  # 70B parámetros!
        self.last_tokens_used = 0
    
    def chat(self, messages, temperature=0.7, max_tokens=4000):
        """Realiza consulta a Groq (ultra rápido)"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extraer tokens usados
            if hasattr(response, 'usage'):
                self.last_tokens_used = response.usage.total_tokens
            
            return response.choices[0].message.content
            
        except Exception as e:
            error_msg = str(e)
            # Detectar rate limit
            if '429' in error_msg or 'rate_limit' in error_msg.lower():
                print("⚠️ Rate limit Groq alcanzado (30 RPM)")
                return None
            print(f"Error Groq: {e}")
            return None
    
    def is_available(self):
        """Verifica si Groq está disponible"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            return True
        except:
            return False


# Modelos disponibles en Groq (todos gratis)
GROQ_MODELS = {
    'llama-3.1-70b-versatile': 'Mejor balance calidad/velocidad',
    'llama-3.1-8b-instant': 'Ultra rápido, menos tokens',
    'llama3-70b-8192': 'Contexto grande',
    'mixtral-8x7b-32768': 'Contexto 32K tokens',
    'gemma2-9b-it': 'Modelo de Google, rápido'
}
```

### Registrarse (2 minutos)

1. **Ir a**: https://console.groq.com/
2. **Sign up** con GitHub/Google (sin tarjeta)
3. **Crear API Key**: https://console.groq.com/keys
4. **Copiar la key** y agregarla a tu `.env`

```bash
# .env
GROQ_API_KEY=gsk_tu_api_key_aqui
```

---

## 🥈 OPCIÓN #2: **Ollama + Modelos Grandes Locales**

### Mejorar tu Ollama actual

Ya tienes Ollama, pero puedes usar modelos **MUCHO mejores**:

```bash
# Modelos recomendados (gratis, locales)

# 1. Llama 3.1 70B (similar a GPT-4)
ollama pull llama3.1:70b

# 2. Qwen 2.5 32B (China, excelente en español)
ollama pull qwen2.5:32b

# 3. Mixtral 8x22B (muy potente)
ollama pull mixtral:8x22b

# 4. DeepSeek Coder V2 (mejor para código)
ollama pull deepseek-coder-v2:16b
```

**Ventajas:**
- ✅ 100% gratis, 100% privado
- ✅ Sin rate limits
- ✅ Sin restricciones de contenido
- ✅ Funciona offline
- ⚠️ Necesita GPU potente (8GB+ VRAM para 70B)

### Configurar modelo grande

```python
# En raymundo.py
self.ollama = OllamaClient(
    url="http://localhost:11434",
    model="llama3.1:70b"  # Cambiar a modelo grande
)
```

---

## 🥉 OPCIÓN #3: **Hugging Face Inference API**

### ¿Por qué Hugging Face?
- ✅ **Gratis** para modelos community
- 🤖 Miles de modelos disponibles
- 📊 Rate limits: 1,000 RPD (decente)
- 🎯 Sin restricciones

```python
# pip install huggingface_hub

from huggingface_hub import InferenceClient

class HuggingFaceClient:
    """Cliente para Hugging Face Inference API (gratis)"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("HF_TOKEN")
        self.client = InferenceClient(token=self.api_key)
        self.model = "meta-llama/Meta-Llama-3.1-70B-Instruct"
        self.last_tokens_used = 0
    
    def chat(self, messages, temperature=0.7, max_tokens=2000):
        try:
            # Construir prompt
            prompt = ""
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    prompt += f"System: {content}\n\n"
                elif role == "user":
                    prompt += f"User: {content}\n\n"
            
            prompt += "Assistant:"
            
            response = self.client.text_generation(
                prompt,
                model=self.model,
                max_new_tokens=max_tokens,
                temperature=temperature
            )
            
            return response
            
        except Exception as e:
            print(f"Error HF: {e}")
            return None
```

**Registro**: https://huggingface.co/settings/tokens

---

## 🏅 OPCIÓN #4: **Together AI**

### ¿Por qué Together?
- ✅ **$25 USD créditos gratis** cada mes (perpetuo)
- 🤖 Acceso a Llama 3.1 405B, Mixtral, etc.
- 📊 Sin rate limits estrictos
- 💰 Costo: $0.20 por 1M tokens (casi gratis)

```python
# pip install together

import together

class TogetherClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("TOGETHER_API_KEY")
        together.api_key = self.api_key
        self.model = "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
        self.last_tokens_used = 0
    
    def chat(self, messages, temperature=0.7, max_tokens=4000):
        try:
            response = together.Complete.create(
                model=self.model,
                prompt=self._format_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return response['choices'][0]['text']
        except Exception as e:
            return None
```

**Registro**: https://api.together.xyz/

---

## 🎯 COMPARACIÓN DE GRATUITAS

| Proveedor | RPD Gratis | Velocidad | Calidad | Tarjeta Requerida |
|-----------|------------|-----------|---------|-------------------|
| **Groq** | **14,400** 🔥 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ No |
| **Ollama 70B** | Ilimitado | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ❌ No |
| **Together AI** | ~125K tokens/mes | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ❌ No |
| **HuggingFace** | 1,000 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ No |
| **GitHub Models** | 150 🔴 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ No |

---

## 🚀 MI RECOMENDACIÓN PARA TI

### **Estrategia 100% Gratuita Perfecta:**

```
1. Groq (primario) → 14,400 RPD, ultra rápido
        ↓ (si alcanza rate limit)
2. Ollama local → Ilimitado, privado
        ↓ (backup)
3. Together AI → 125K tokens/mes
```

### Sistema Multi-Proveedor Gratuito

```python
class FreeAIRouter:
    """Router de APIs gratuitas con fallback inteligente"""
    
    def __init__(self):
        self.groq = GroqClient()          # Primario: rápido y generoso
        self.ollama = OllamaClient()      # Fallback: ilimitado local
        self.together = TogetherClient()  # Backup: $25/mes gratis
        
        self.groq_daily_count = 0
        self.groq_minute_count = 0
    
    def chat(self, messages):
        """Intenta Groq → Ollama → Together"""
        
        # 1. Intentar Groq primero (14,400 RPD)
        if self.groq_daily_count < 14000:  # Margen de seguridad
            response = self.groq.chat(messages)
            if response:
                self.groq_daily_count += 1
                return response
        
        # 2. Fallback a Ollama (ilimitado)
        print("⚠️ Usando Ollama local...")
        response = self.ollama.generate(self._to_prompt(messages))
        if response:
            return response
        
        # 3. Último recurso: Together AI
        print("⚠️ Usando Together AI...")
        return self.together.chat(messages)
    
    def _to_prompt(self, messages):
        """Convierte messages a prompt simple"""
        prompt = ""
        for msg in messages:
            prompt += f"{msg['role']}: {msg['content']}\n"
        return prompt
```

---

## 📥 GUÍA DE IMPLEMENTACIÓN

### Paso 1: Instalar SDKs

```bash
pip install groq together huggingface_hub
```

### Paso 2: Registrarse (gratis, sin tarjeta)

```bash
# Groq (RECOMENDADO - 2 minutos)
https://console.groq.com/

# Together AI (opcional)
https://api.together.xyz/

# Hugging Face (opcional)
https://huggingface.co/settings/tokens
```

### Paso 3: Configurar .env

```bash
# .env
GROQ_API_KEY=gsk_tu_key_aqui
TOGETHER_API_KEY=tu_key_aqui
HF_TOKEN=tu_token_aqui
```

### Paso 4: Integrar en Raymundo

Archivo: `free_ai_clients.py` (nuevo)

```python
"""
Clientes de IA 100% gratuitos para Raymundo
Sin costos, sin tarjetas de crédito
"""

import os
from groq import Groq
import together
from huggingface_hub import InferenceClient

# [Código de los clientes arriba]
```

---

## 💡 VENTAJAS PARA TU CASO USO

### Para uso personal con amigos:

✅ **Groq te da 14,400 requests/día gratis**
- Si son 10 personas usando intenso
- 1,440 requests/persona/día
- = ~1 request por minuto todo el día
- **MÁS que suficiente**

✅ **Sin restricciones de personalidad soez**
- Groq, Ollama, Together: sin censura
- Puedes mantener el tono "puteado" de Raymundo

✅ **Privacidad**
- Ollama: 100% local, nadie ve tus chats
- Groq/Together: solo para inferencia

✅ **Sin riesgo de costos sorpresa**
- No necesitas tarjeta de crédito
- Nunca te cobrarán nada

---

## 🎯 PLAN DE ACCIÓN (15 minutos)

### Implementar Groq AHORA:

1. **Registrate**: https://console.groq.com/ (2 min)
2. **Copia tu API key** (1 min)
3. **Yo instalo el código** (5 min)
4. **Pruebas** (2 min)
5. **¡Listo!** - 14,400 requests/día gratis

### Ventajas inmediatas:
- ✅ 96x más requests que GitHub Models
- ✅ Respuestas 10x más rápidas
- ✅ Sin cambios en tu código de WhatsApp
- ✅ Fallback automático a Ollama

---

## 🔥 BONUS: Mejorar Ollama

Mientras implementas Groq, mejora tu Ollama:

```bash
# Descargar modelo mejor (gratis)
ollama pull llama3.1:70b

# Tarda ~45 min, pero vale la pena
# Calidad similar a GPT-4
```

**Configuración GPU óptima:**

```python
# Si tienes 8GB VRAM
ollama pull llama3.1:70b

# Si tienes 4-6GB VRAM
ollama pull qwen2.5:32b

# Si tienes menos de 4GB
ollama pull llama3.1:8b  # Ya mejor que qwen2.5:7b
```

---

## 📊 Estimación para ti y tus amigos

### Escenario: 5 personas usando Raymundo

| Uso | Requests/día | Con Groq | Con GitHub |
|-----|--------------|----------|------------|
| **Ligero** (10 msg/día) | 50 | ✅ Gratis | ✅ Gratis |
| **Medio** (50 msg/día) | 250 | ✅ Gratis | 🔴 Superas límite |
| **Intenso** (200 msg/día) | 1,000 | ✅ Gratis | 🔴 Bloqueado día 1 |

**Con Groq tienes 14,400 = suficiente para 28 personas con uso intenso**

---

## ✅ CONCLUSIÓN

### Para tu caso (personal, amigos, sin lucro):

**MEJOR OPCIÓN: Groq + Ollama**
- 🆓 100% gratis
- 📊 14,400 RPD (96x mejor que GitHub)
- ⚡ Ultra rápido
- 🔒 Sin restricciones de contenido
- 💪 Fallback ilimitado con Ollama

**COSTO TOTAL: $0 USD/mes**

---

¿Te parece bien? ¿Quieres que implemente Groq en Raymundo ahora?
