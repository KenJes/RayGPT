import sys
sys.path.insert(0, '.')

print('=== Probando Ollama ===')
try:
    from core.ai_clients import OllamaClient
    ol = OllamaClient()
    r = ol.chat([{'role': 'user', 'content': 'di hola'}], temperature=0.5, max_tokens=20)
    print('Ollama OK:', r)
except Exception as e:
    print('Ollama ERROR:', e)

print()
print('=== Probando Groq ===')
try:
    from core.ai_clients import GroqClient
    gc = GroqClient()
    r = gc.chat([{'role': 'user', 'content': 'di hola'}], temperature=0.5, max_tokens=20)
    print('Groq OK:', r)
except Exception as e:
    print('Groq ERROR:', e)

print()
print('=== Probando Mistral ===')
try:
    from core.ai_clients import MistralClient
    mc = MistralClient()
    r = mc.chat([{'role': 'user', 'content': 'di hola'}], temperature=0.5, max_tokens=20)
    print('Mistral OK:', r)
except Exception as e:
    print('Mistral ERROR:', e)
