"""
GestorHerramientas — Orquesta todas las herramientas del agente.
Detecta intenciones, crea documentos/presentaciones, busca en web, etc.
"""

import json
import re
from pathlib import Path

from core.config import config_agente
from core.detectors import DetectorIntenciones, DetectorTemporalidad, DetectorIdioma
from core.processors import VisionProcessor, DocumentProcessor, EmojiProcessor
from core.memory import MemorySystem
from core.web_scraper import WebScraper

# ── Detección de rechazos del LLM ─────────────────────────────
_REFUSAL_PATTERNS = re.compile(
    r"(?:lo siento|i'?m sorry|i cannot|no puedo)"
    r".*?"
    r"(?:cumplir|continuar|ayudar|assist|help|esa solicitud|esta conversaci[oó]n"
    r"|that request|with that|generar|proporcionar)",
    re.IGNORECASE | re.DOTALL,
)


def es_rechazo_llm(texto: str | None) -> bool:
    """Detecta si la respuesta del LLM es un rechazo por filtros de seguridad."""
    if not texto or len(texto) > 300:
        return False
    return bool(_REFUSAL_PATTERNS.search(texto))


class GestorHerramientas:
    """Orquesta todas las herramientas del agente."""

    def __init__(self, ollama, github, google=None, groq=None):
        self.ollama = ollama
        self.github = github
        self.groq_client = groq
        self.google = google
        self.detector = DetectorIntenciones()
        self.detector_temporal = DetectorTemporalidad()
        self.detector_idioma = DetectorIdioma()
        self.vision = VisionProcessor(github, groq)
        self.docs = DocumentProcessor()
        self.memory = MemorySystem()
        self.scraper = WebScraper()
        self.emoji_processor = EmojiProcessor()

    # ───── Punto de entrada principal ─────────────────────────

    def procesar_mensaje(self, mensaje, af_delegar=None, af_disponible=None,
                         user_name=None, user_id=None, tono_override=None, usuario_agresivo=False):
        """Procesa mensaje y detecta intenciones."""

        # Aprender vocabulario del usuario (separado por user_id si viene de WhatsApp)
        self.memory.aprender_vocabulario(mensaje, user_id=user_id)

        # 0. Comandos rápidos
        cmd = self._procesar_comando_rapido(mensaje)
        if cmd:
            return cmd

        # 0b. AgentField — delegar si los agentes están corriendo
        if af_delegar and af_disponible and af_disponible():
            af_res = af_delegar(mensaje)
            if af_res and af_res.get("exito"):
                texto = af_res.get("resultado", "")
                url = af_res.get("url")
                agente = af_res.get("agente_usado", "agente")
                skill = af_res.get("skill_usado", "")
                if url:
                    texto = f"{texto}\n\n🔗 {url}"
                return {
                    "ejecuto_herramienta": True,
                    "tipo": f"agentfield:{agente}",
                    "resultado": texto,
                    "archivo": url,
                }

        # 1. Emojis
        resultado_emoji = self.emoji_processor.procesar(mensaje)
        mensaje_procesado = resultado_emoji["texto_procesado"]

        # 2. Detectar intención
        resultado_intencion = self.detector.detectar(mensaje_procesado)

        if resultado_intencion["confianza"] >= 0.3:
            intencion = resultado_intencion["intencion"]

            if intencion == "presentacion" and self.google:
                tema = resultado_intencion.get("tema", mensaje)
                detalles = resultado_intencion.get("detalles", {})
                res = self.crear_presentacion(tema, detalles)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "presentacion",
                    "resultado": res["texto"],
                    "archivo": res.get("archivo"),
                }

            if intencion == "documento" and self.google:
                tema = resultado_intencion.get("tema", mensaje)
                detalles = resultado_intencion.get("detalles", {})
                res = self.crear_documento(tema, detalles)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "documento",
                    "resultado": res["texto"],
                    "archivo": res.get("archivo"),
                }

            if intencion == "hoja_calculo" and self.google:
                tema = resultado_intencion.get("tema", mensaje)
                detalles = resultado_intencion.get("detalles", {})
                res = self.crear_hoja_calculo(tema, detalles)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "hoja_calculo",
                    "resultado": res["texto"],
                    "archivo": res.get("archivo"),
                }

            if intencion == "imagenes":
                if self._tiene_ruta_archivo(mensaje):
                    path = self._extraer_ruta(mensaje)
                    if Path(path).exists():
                        resultado = self.vision.analyze_image(path, mensaje)
                        self.memory.add_image(path, resultado[:500])
                        return {
                            "ejecuto_herramienta": True,
                            "tipo": "vision",
                            "resultado": f"🖼️ **{Path(path).name}**\n\n{resultado}",
                        }

            if intencion == "analisis_documento":
                if self._tiene_ruta_archivo(mensaje_procesado):
                    path = self._extraer_ruta(mensaje_procesado)
                    if Path(path).exists():
                        doc = self.docs.process_document(path)
                        if doc["success"]:
                            self.memory.add_document(path, doc["content"])
                            return {
                                "ejecuto_herramienta": True,
                                "tipo": "documento",
                                "resultado": f"📄 **{Path(path).name}** cargado en memoria",
                            }

            if intencion == "web_scraping":
                urls = self.scraper.extraer_url(mensaje)
                if urls:
                    res_web = self.buscar_en_web(urls[0], mensaje_procesado)
                    return {
                        "ejecuto_herramienta": True,
                        "tipo": "web_scraping",
                        "resultado": res_web,
                    }

        return {"ejecuto_herramienta": False}

    # ───── Google Workspace ────────────────────────────────────

    def crear_presentacion(self, tema, detalles):
        if not self.google:
            return {"texto": "❌ Google Slides no configurado", "archivo": None}
        try:
            num_slides = min(detalles.get("num_slides", 5), 12)
            tono_actual = config_agente.get_tono()
            nombre_agente = config_agente.get_nombre_agente()

            if tono_actual == "puteado":
                instrucciones_estilo = (
                    '- ESTILO rAI: Escribe con faltas de ortografia, usa "naco", "cabrón", '
                    '"estúpido", "imbecil", "puto", "wey", "chingon", "verga", "alv", etc.\n'
                    "- USA lenguaje informal, muy agresivo pero informativo\n"
                    "- Mantén el tono naco y directo en TODO el contenido"
                )
            else:
                instrucciones_estilo = (
                    "- ESTILO Amigable: Escribe correctamente, profesional pero cercano\n"
                    "- Usa lenguaje claro, motivador y accesible\n"
                    "- Mantén el tono profesional y positivo en TODO el contenido"
                )

            prompt_contenido = f"""Actúa como {nombre_agente}, un conferencista experto. Diseña una presentación profesional sobre: {tema}

{instrucciones_estilo}

Devuelve exclusivamente un JSON válido con esta estructura:

{{
    "titulo_presentacion": "Título impactante y profesional",
    "subtitulo_presentacion": "Subtítulo descriptivo (opcional)",
    "diapositivas": [
        {{
            "tipo": "portada|contenido|conclusion",
            "titulo": "Título de la diapositiva",
            "contenido": "Contenido de la slide",
            "tiene_imagen": true/false,
            "keywords_imagen": "keywords en inglés"
        }}
    ]
}}

REGLAS ESTRICTAS:
📊 ESTRUCTURA (Exactamente {num_slides} diapositivas):
1. Primera slide (tipo: "portada"): Solo título y subtítulo, tiene_imagen: false
2. Slides intermedias (tipo: "contenido"): Contenido variado, datos específicos, tiene_imagen: true
3. Última slide (tipo: "conclusion"): Resumen ejecutivo, tiene_imagen: true

📝 FORMATO: Usa viñetas (• Punto) o párrafos según slide. Máx 5 puntos por slide.
🖼️ IMÁGENES: keywords_imagen en inglés, 2-4 palabras descriptivas.
Sin markdown extra, sin explicaciones fuera del JSON."""

            respuesta_ia = self.groq_client.chat(
                [{"role": "user", "content": prompt_contenido}],
                temperature=0.5,
            )

            json_match = re.search(r"\{[\s\S]*\}", respuesta_ia)
            if json_match:
                respuesta_ia = json_match.group(0)
            respuesta_ia = self._normalizar_json_respuesta(respuesta_ia)
            esquema = json.loads(respuesta_ia)

            titulo_final = esquema.get("titulo_presentacion", f"{tema} - Presentación")
            subtitulo = esquema.get("subtitulo_presentacion", "")
            diapositivas_data = esquema.get("diapositivas", [])
            tema_visual = self._seleccionar_tema_visual(tema)

            diapositivas_completas = []
            for idx, diapo in enumerate(diapositivas_data, 1):
                tipo_slide = diapo.get("tipo", "contenido")
                imagen_url = None
                if diapo.get("tiene_imagen", False):
                    keywords = diapo.get("keywords_imagen", tema.split()[0])
                    imagen_url = self.google.buscar_imagen_web(keywords)

                diapositivas_completas.append({
                    "tipo": tipo_slide,
                    "titulo": diapo.get("titulo", f"Diapositiva {idx}"),
                    "contenido": diapo.get("contenido", ""),
                    "imagen_url": imagen_url,
                    "subtitulo": subtitulo if tipo_slide == "portada" else None,
                })

            pres = self.google.crear_presentacion(
                titulo=titulo_final,
                diapositivas=diapositivas_completas,
                tema_visual=tema_visual,
            )

            if pres and "error" in pres:
                return {"texto": f"❌ Error: {pres.get('message', pres['error'])}", "archivo": None}

            if pres and "id" in pres:
                return {
                    "texto": (
                        f"✅ Presentación creada\n\n"
                        f"🔗 **URL**: {pres['url']}\n"
                        f"📊 {titulo_final} — {len(diapositivas_completas)} slides"
                    ),
                    "archivo": {
                        "presentation_id": pres["id"],
                        "titulo": titulo_final,
                        "tipo": "presentacion",
                    },
                }
            return {"texto": "❌ Error al crear presentación", "archivo": None}
        except json.JSONDecodeError:
            return {"texto": "❌ La IA no generó un formato válido. Intenta de nuevo.", "archivo": None}

    def crear_documento(self, tema, detalles):
        if not self.google:
            return {"texto": "❌ Google Docs no configurado", "archivo": None}
        try:
            tono_actual = config_agente.get_tono()
            nombre_agente = config_agente.get_nombre_agente()
            if tono_actual == "puteado":
                estilo = 'Escribe como rAI: usa "ke", "ps", "kon", wey, chingon, verga, alv. Agresivo pero informativo.'
            else:
                estilo = "Escribe profesionalmente, con ortografía correcta y tono amigable 💡"

            prompt = (
                f"Eres {nombre_agente}. Escribe un documento sobre: {tema}\n\n"
                f"Estilo: {estilo}\n"
                "Formato markdown con # para títulos. Incluye introducción, desarrollo y conclusión."
            )
            contenido = self.github.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
            )
            doc = self.google.crear_documento(f"{tema} - Documento", contenido)
            if doc:
                return {
                    "texto": f"✅ Documento creado\n\n🔗 **URL**: {doc['url']}",
                    "archivo": {"document_id": doc["id"], "tipo": "documento"},
                }
            return {"texto": "❌ Error al crear documento", "archivo": None}
        except Exception as e:
            return {"texto": f"❌ Error: {e}", "archivo": None}

    def crear_hoja_calculo(self, tema, detalles):
        if not self.google:
            return {"texto": "❌ Google Sheets no configurado", "archivo": None}
        try:
            sheet = self.google.crear_hoja_calculo(f"{tema} - Datos")
            if sheet:
                return {
                    "texto": f"✅ Hoja de cálculo creada\n\n🔗 **URL**: {sheet['url']}",
                    "archivo": {"spreadsheet_id": sheet["id"], "tipo": "hoja_calculo"},
                }
            return {"texto": "❌ Error al crear hoja de cálculo", "archivo": None}
        except Exception as e:
            return {"texto": f"❌ Error: {e}", "archivo": None}

    # ───── Web ─────────────────────────────────────────────────

    def buscar_en_web(self, url, pregunta):
        resultado = self.scraper.scrape(url)
        if not resultado["success"]:
            return f"❌ {resultado['error']}"
        contenido = resultado['contenido'] or resultado.get('descripcion') or "(sin contenido extraído)"
        prompt = (
            f"Analiza esta página web:\n"
            f"Título: {resultado['titulo']}\nURL: {resultado['url']}\n\n"
            f"Contenido:\n{contenido[:1500]}\n\n"
            f"Pregunta: {pregunta}\n\nResponde claro y conciso en español."
        )
        respuesta = self._consultar_ia(prompt, 0.7, 500)
        titulo = resultado['titulo'] or url
        return f"🌐 **{titulo}**\n\n{respuesta}"

    # ───── Chat híbrido (Smart Routing) ────────────────────────

    def chat_hibrido(self, mensaje, idioma_override=None,
                     user_name=None, user_id=None, tono_override=None, usuario_agresivo=False,
                     history=None, knowledge_context=None):
        idioma = idioma_override or self.detector_idioma.detectar(mensaje)
        if idioma == "en":
            prompt_sistema = config_agente.get_prompt_sistema_en()
        else:
            prompt_sistema = config_agente.get_prompt_sistema()

        # Inyectar nombre del interlocutor
        if user_name and user_name.strip() and user_name != user_id:
            prompt_sistema += (
                f"\n\nESTÁS CHATEANDO CON: {user_name}. "
                f"Llámalo/a por su nombre ({user_name}) en tus respuestas cuando sea natural."
            )

        # Inyectar señal de tono: persistente O por agresividad detectada en este mensaje
        if tono_override == 'amigable':
            prompt_sistema += (
                "\n\nINSTRUCCIÓN DE TONO: El usuario pidió que seas amable y respetuoso. "
                "Sé cordial, sin groserías, aunque él use alguna."
            )
        elif tono_override == 'puteado':
            prompt_sistema += (
                "\n\nINSTRUCCIÓN DE TONO: El usuario quiere tu modo directo sin filtros. "
                "Groserías permitidas, sé agresivo y directo."
            )
        elif usuario_agresivo:
            # Sin override permanente pero el mensaje actual es agresivo → espeja
            prompt_sistema += (
                "\n\nTONO DEL USUARIO EN ESTE MENSAJE: Está siendo grosero o agresivo. "
                "Respóndele exactamente en el mismo nivel — groserías con groserías, "
                "sin perder el hilo de la respuesta útil."
            )

        # Inyectar estilo de slang del usuario (si aplica)
        vocab_hint = self.memory.get_vocabulario_hint(user_id=user_id)
        if vocab_hint:
            prompt_sistema += vocab_hint

        # Inyectar conocimiento almacenado relevante
        if knowledge_context:
            prompt_sistema += f"\n\n{knowledge_context}"

        # Construir messages con historial de conversación
        messages = [{"role": "system", "content": prompt_sistema}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": mensaje})

        # Para Ollama (que usa prompt plano), construir texto con contexto
        history_text = ""
        if history:
            for msg in history[-10:]:  # Últimos 10 mensajes para el prompt plano
                role_label = "Usuario" if msg["role"] == "user" else "Asistente"
                history_text += f"{role_label}: {msg['content']}\n"

        temporalidad = self.detector_temporal.detectar(mensaje)
        ollama_prompt = f"{prompt_sistema}\n\n{history_text}Usuario: {mensaje}\nAsistente:"

        if temporalidad == "actual":
            if self.groq_client and self.groq_client.client:
                r = self.groq_client.chat(messages, temperature=0.7)
                if r and not es_rechazo_llm(r):
                    return r
            if self.github and self.github.client:
                r = self.github.chat(messages, temperature=0.7)
                if r and not es_rechazo_llm(r):
                    return r
            r = self.ollama.generate(ollama_prompt, temperature=0.7, max_tokens=500)
            if r and not es_rechazo_llm(r):
                return f"⚠️ *[Modo local]*\n\n{r}"
            # Todos rechazaron — forzar respuesta en personaje
            return self._respuesta_fallback_rechazo(mensaje)
        else:
            r = self.ollama.generate(ollama_prompt, temperature=0.7, max_tokens=2000)
            if r and not es_rechazo_llm(r):
                return r
            if self.groq_client and self.groq_client.client:
                r = self.groq_client.chat(messages, temperature=0.7)
                if r and not es_rechazo_llm(r):
                    return r
            if self.github and self.github.client:
                r = self.github.chat(messages, temperature=0.7)
                if r and not es_rechazo_llm(r):
                    return r
            return "❌ No se pudo conectar a ningún modelo de IA"

    # ───── Comandos rápidos ────────────────────────────────────

    @staticmethod
    def _respuesta_fallback_rechazo(mensaje: str) -> str:
        """Genera una respuesta genérica en personaje cuando todos los modelos rechazan."""
        msg = mensaje.lower()
        if any(w in msg for w in ('presentate', 'preséntate', 'quien eres', 'quién eres')):
            return ("¿Qué onda? Soy Raymundo, de Axoloit. Soy tu asistente para lo que necesites — "
                    "programación, negocios, lo que sea. ¿En qué te ayudo, wey?")
        return ("Órale, los modelos de IA están de flojos ahorita y no quieren contestar. "
                "Intenta decirlo de otra forma o pregúntame algo diferente y le echamos ganas.")

    def _consultar_ia(self, prompt, temperature=0.7, max_tokens=2000):
        messages = [{"role": "user", "content": prompt}]
        if self.groq_client and self.groq_client.client:
            r = self.groq_client.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if r:
                return r
        if self.github and self.github.client:
            r = self.github.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if r:
                return r
        r = self.ollama.generate(prompt, temperature=temperature, max_tokens=max_tokens)
        return r or "❌ No se pudo conectar a ningún modelo de IA"

    def _procesar_comando_rapido(self, mensaje):
        msg = mensaje.strip()
        lower = msg.lower()

        if lower.startswith("/resumir"):
            contenido = msg[len("/resumir"):].strip()
            if not contenido:
                return {"ejecuto_herramienta": True, "tipo": "comando",
                        "resultado": "⚠️ Uso: `/resumir <URL o texto largo>`"}
            return {"ejecuto_herramienta": True, "tipo": "comando",
                    "resultado": self._cmd_resumir(contenido)}

        if lower.startswith("/traducir"):
            contenido = msg[len("/traducir"):].strip()
            if not contenido:
                return {"ejecuto_herramienta": True, "tipo": "comando",
                        "resultado": "⚠️ Uso: `/traducir <texto>`"}
            return {"ejecuto_herramienta": True, "tipo": "comando",
                    "resultado": self._cmd_traducir(contenido)}

        if lower.startswith("/email"):
            contenido = msg[len("/email"):].strip()
            if not contenido:
                return {"ejecuto_herramienta": True, "tipo": "comando",
                        "resultado": "⚠️ Uso: `/email <instrucciones>`"}
            return {"ejecuto_herramienta": True, "tipo": "comando",
                    "resultado": self._cmd_email(contenido)}

        if lower.startswith("/codigo") or lower.startswith("/código"):
            contenido = msg.split(maxsplit=1)[1] if " " in msg else ""
            if not contenido:
                return {"ejecuto_herramienta": True, "tipo": "comando",
                        "resultado": "⚠️ Uso: `/codigo <descripción>`"}
            return {"ejecuto_herramienta": True, "tipo": "comando",
                    "resultado": self._cmd_codigo(contenido)}

        if lower in ["/ayuda", "/help", "/comandos"]:
            return {"ejecuto_herramienta": True, "tipo": "comando",
                    "resultado": self._ayuda_comandos()}

        return None

    def _cmd_resumir(self, contenido):
        urls = self.scraper.extraer_url(contenido)
        if urls:
            res = self.scraper.scrape(urls[0])
            if res["success"]:
                texto_fuente = f"Título: {res['titulo']}\n\n{res['contenido'][:3000]}"
            else:
                return f"❌ No pude acceder a la URL: {res['error']}"
        else:
            texto_fuente = contenido
        prompt = (
            "Resume el siguiente texto de forma clara y estructurada.\n"
            "Incluye los puntos clave en viñetas y un párrafo de conclusión.\n\n"
            f"Texto:\n{texto_fuente[:4000]}\n\nResumen:"
        )
        resumen = self._consultar_ia(prompt, temperature=0.3, max_tokens=1500)
        titulo = urls[0] if urls else contenido[:60] + "..."
        return f"📝 **Resumen de:** {titulo}\n\n{resumen}"

    def _cmd_traducir(self, texto):
        idioma_origen = self.detector_idioma.detectar(texto)
        if idioma_origen == "en":
            instruccion = "Traduce del inglés al español."
            flag = "🇲🇽"
        else:
            instruccion = "Translate from Spanish to English."
            flag = "🇺🇸"
        prompt = f"{instruccion} Mantén el tono original.\n\nTexto:\n{texto}\n\nTraducción:"
        return f"{flag} **Traducción:**\n\n{self._consultar_ia(prompt, temperature=0.3)}"

    def _cmd_email(self, instrucciones):
        prompt = (
            f"Genera un correo electrónico profesional:\n{instrucciones}\n\n"
            "Formato:\n**Asunto:** [asunto]\n\n[cuerpo del correo]\n\n"
            "Reglas: tono profesional, estructura clara, usa placeholders como [TU NOMBRE]."
        )
        email = self._consultar_ia(prompt, temperature=0.5, max_tokens=1500)
        return f"✉️ **Email generado:**\n\n{email}"

    def _cmd_codigo(self, descripcion):
        prompt = (
            f"Genera código funcional para:\n{descripcion}\n\n"
            "Reglas: detecta el lenguaje apropiado (Python por defecto), "
            "incluye comentarios y una sección '💡 Explicación:' al final."
        )
        return f"💻 **Código generado:**\n\n{self._consultar_ia(prompt, temperature=0.3, max_tokens=3000)}"

    def _ayuda_comandos(self):
        return """⚡ **Comandos rápidos:**

📝 `/resumir <URL o texto>` — Resume contenido largo
🌐 `/traducir <texto>` — Traduce ES↔EN
✉️ `/email <instrucciones>` — Genera correos profesionales
💻 `/codigo <descripción>` — Genera código con explicación
🔄 `/puteado` · `/amigable` — Cambiar personalidad
❓ `/ayuda` — Este menú"""

    # ───── Helpers internos ────────────────────────────────────

    def _seleccionar_tema_visual(self, tema):
        tema_lower = (tema or "").lower()
        paletas = [
            {
                "nombre": "tech_ocean",
                "nombre_mostrable": "Tech Ocean",
                "keywords": ["ia", "ai", "inteligencia artificial", "tecnolog", "software", "cloud", "data", "robot"],
                "color_fondo": {"red": 0.07, "green": 0.11, "blue": 0.24},
                "estilos_titulo": {"color": {"red": 0.95, "green": 0.97, "blue": 0.99}, "fuente": "Montserrat", "tamano": 36, "bold": True},
                "estilos_contenido": {"color": {"red": 0.85, "green": 0.89, "blue": 0.95}, "fuente": "Open Sans", "tamano": 20},
            },
            {
                "nombre": "business_coral",
                "nombre_mostrable": "Business Coral",
                "keywords": ["marketing", "ventas", "negocio", "estrategia", "finanzas", "liderazgo", "startup"],
                "color_fondo": {"red": 0.9, "green": 0.36, "blue": 0.2},
                "estilos_titulo": {"color": {"red": 1, "green": 0.97, "blue": 0.95}, "fuente": "Playfair Display", "tamano": 34, "bold": True},
                "estilos_contenido": {"color": {"red": 1, "green": 0.96, "blue": 0.92}, "fuente": "Lato", "tamano": 20},
            },
            {
                "nombre": "eco_fresh",
                "nombre_mostrable": "Eco Fresh",
                "keywords": ["sostenibilidad", "medio ambiente", "salud", "educación", "agricultura", "turismo"],
                "color_fondo": {"red": 0.1, "green": 0.35, "blue": 0.22},
                "estilos_titulo": {"color": {"red": 0.9, "green": 0.98, "blue": 0.92}, "fuente": "Poppins", "tamano": 34, "bold": True},
                "estilos_contenido": {"color": {"red": 0.86, "green": 0.95, "blue": 0.89}, "fuente": "Nunito", "tamano": 20},
            },
        ]
        for p in paletas:
            for kw in p["keywords"]:
                if kw in tema_lower:
                    return p
        return {
            "nombre": "modern_neutral",
            "nombre_mostrable": "Modern Neutral",
            "color_fondo": {"red": 0.16, "green": 0.18, "blue": 0.2},
            "estilos_titulo": {"color": {"red": 0.97, "green": 0.97, "blue": 0.97}, "fuente": "Montserrat", "tamano": 34, "bold": True},
            "estilos_contenido": {"color": {"red": 0.9, "green": 0.9, "blue": 0.9}, "fuente": "Inter", "tamano": 20},
        }

    def _normalizar_json_respuesta(self, texto):
        if not texto:
            return texto
        resultado = []
        dentro = False
        escape = False
        for char in texto:
            if char == '"' and not escape:
                dentro = not dentro
            elif char == "\\" and not escape:
                escape = True
                resultado.append(char)
                continue
            if escape:
                resultado.append(char)
                escape = False
                continue
            if dentro and char in ["\n", "\r"]:
                resultado.append("\\n")
                continue
            resultado.append(char)
        return "".join(resultado)

    def _tiene_ruta_archivo(self, texto):
        return bool(re.search(r"[a-zA-Z]:[\\\/][^\s]+", texto))

    def _extraer_ruta(self, texto):
        match = re.search(r"[a-zA-Z]:[\\\/][^\s]+", texto)
        return match.group(0).strip("'\"") if match else ""
