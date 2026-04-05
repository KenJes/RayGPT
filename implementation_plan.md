# Comando `/reset` + Mejora de Context Injection con RAG

Raymundo actualmente no tiene un comando para borrar el caché de conversaciones desde chat.  
Además, la inyección de contexto está dispersa en múltiples archivos — el usuario tiene que repetirle a Raymundo qué hacer y cómo actuar.

Este plan agrega el comando `/reset` y centraliza/mejora la inyección de contexto con RAG automático.

## Proposed Changes

### Comando `/reset` — Borrar caché de conversaciones

---

#### [MODIFY] [whatsapp_server.py](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/whatsapp_server.py)

Agregar manejo del comando `/reset` (y variantes `/borrar`, `/limpiar`, `/nuevo`) en el endpoint `/chat`:
- Borra historial de conversación del usuario (`conversation_db.clear_history`)
- Borra resúmenes compactados
- Limpia personalidad override del usuario
- Responde con confirmación

---

#### [MODIFY] [tools.py](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/core/tools.py)

Agregar comando `/reset` en [_procesar_comando_rapido()](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/core/tools.py#769-810) para la interfaz GUI:
- Requiere acceso al [ConversationDB](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/core/conversation_db.py#34-255) (lo pasamos como parámetro opcional)
- Actualizar [_ayuda_comandos()](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/core/tools.py#858-867) con el nuevo comando

---

#### [MODIFY] [raymundo.py](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/raymundo.py)

En [_procesar_mensaje()](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/raymundo.py#285-354), detectar `/reset` y limpiar el historial local + BD.

---

### Context Injection Mejorado — ContextManager centralizado

---

#### [NEW] [context_manager.py](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/core/context_manager.py)

Módulo centralizado que construye el contexto completo para el LLM en un solo lugar:

```python
class ContextManager:
    def build_system_prompt(user_id, query, ...) -> str
```

Responsabilidades:
1. **System prompt base** — personalidad desde archivo markdown (ya existe)
2. **Conocimiento RAG automático** — busca en [KnowledgeBase](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/core/knowledge_db.py#34-508) datos relevantes al query del usuario y los inyecta sin que el usuario tenga que pedirlo explícitamente
3. **Temas frecuentes del usuario** — inyecta los temas más discutidos por el usuario como contexto pasivo ("Este usuario suele hablar de: X, Y, Z")
4. **Vocabulario/estilo** — inyecta hints de tono (ya existe en [memory.py](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/core/memory.py), lo centraliza)
5. **Capacidades disponibles** — inyecta un recordatorio de qué herramientas tiene disponibles (calendario, YouTube, Spotify, presentaciones, etc.) para que Raymundo no olvide que puede usarlas

---

#### [MODIFY] [whatsapp_server.py](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/whatsapp_server.py)

Reemplazar la construcción manual del contexto en las rutas de chat con `ContextManager.build_system_prompt()`.

---

#### [MODIFY] [tools.py](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/core/tools.py)

En [chat_hibrido()](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/core/tools.py#662-740), usar `ContextManager` para construir el system prompt en lugar de armarlo manualmente.

---

#### [MODIFY] [personalidad_raymundo.md](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/data/personalidad_raymundo.md)

Agregar al final una sección de capacidades que el `ContextManager` pueda referenciar:

```
CAPACIDADES: Puedes crear presentaciones, documentos, hojas de cálculo (Google Workspace), 
manejar calendario, buscar en YouTube, controlar Spotify, buscar en la web, 
analizar imágenes y documentos. Cuando el usuario pida algo, usa tus herramientas.
```

---

#### [MODIFY] [personalidad_rai.md](file:///c:/Users/kenne/Visual%20Studio%20Code/Agentes/data/personalidad_rai.md)

Misma sección de capacidades adaptada al estilo rAI.

---

## Verification Plan

### Manual Verification

1. **Comando `/reset` en WhatsApp**: Enviar `/reset` → verificar que responde con confirmación y que el siguiente mensaje no tiene contexto previo
2. **Comando `/reset` en GUI**: Escribir `/reset` en la interfaz tkinter → verificar que limpia historial
3. **Context injection mejorado**: Enviar un mensaje normal sin contexto previo → verificar en los logs del servidor que el system prompt incluye las capacidades y el conocimiento RAG relevante
4. **Verificar que `/ayuda` muestra el nuevo comando**

> [!NOTE]
> No existen tests unitarios en el proyecto actualmente, y el flujo depende de servicios externos (Ollama, Groq, WhatsApp). La verificación es manual ejecutando el servidor y enviando mensajes.
