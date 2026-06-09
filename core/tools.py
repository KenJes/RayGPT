"""
GestorHerramientas — Orquesta todas las herramientas del agente.
Detecta intenciones, crea documentos/presentaciones, busca en web, etc.
"""

import json
import re
import unicodedata
from pathlib import Path

from core.config import config_agente
from core.detectors import DetectorIntenciones, DetectorTemporalidad, DetectorIdioma
from core.processors import VisionProcessor, DocumentProcessor, EmojiProcessor
from core.memory import MemorySystem
from core.web_scraper import WebScraper
from core.extra_tools import WeatherClient, CryptoClient, QRGenerator, ImageGenerator, NasaClient, ComfyUIClient

# ── Detección de rechazos del LLM ─────────────────────────────
_REFUSAL_PATTERNS = [
    # Patrón clásico: "lo siento, no puedo cumplir"
    re.compile(
        r"(?:lo siento|i'?m sorry|i cannot|no puedo)"
        r".*?"
        r"(?:cumplir|continuar|ayudar|assist|help|esa solicitud|esta conversaci[oó]n"
        r"|that request|with that|generar|proporcionar)",
        re.IGNORECASE | re.DOTALL,
    ),
    # Patrón sutil: "no comparto tu forma", "aunque no comparto"
    re.compile(
        r"(?:no comparto|no apruebo|no apoyo|no fomento)"
        r".*?"
        r"(?:forma de expresar|expresarte|lenguaje|conducta|comportamiento)",
        re.IGNORECASE | re.DOTALL,
    ),
    # Patrón: "Entendido. A partir de ahora haré todo lo posible"
    re.compile(
        r"(?:entendido|comprendo|entiendo)\.?\s*(?:a partir de ahora|de ahora en adelante)",
        re.IGNORECASE,
    ),
    # Patrón: respuestas que empiezan con el nombre del bot seguido de ":"
    re.compile(
        r"^(?:Raymundo|rAI)\s*:\s*(?:Entendido|Comprendo|Lo siento|No puedo)",
        re.IGNORECASE,
    ),
    # Patrón: disclaimers éticos — debe ir acompañado de contexto de IA para evitar falsos positivos
    re.compile(
        r"como (?:modelo de lenguaje|ia|inteligencia artificial).*?(?:no (?:debo|puedo|deberia|debería)|no es (?:apropiado|correcto))",
        re.IGNORECASE | re.DOTALL,
    ),
]


def es_rechazo_llm(texto: str | None) -> bool:
    """Detecta si la respuesta del LLM es un rechazo por filtros de seguridad."""
    if not texto:
        return False
    # Revisar solo los primeros 500 chars para patrones de rechazo
    fragmento = texto[:500]
    return any(p.search(fragmento) for p in _REFUSAL_PATTERNS)


def _es_rechazo_rai(texto: str | None) -> bool:
    """Detecta cuando un modelo ignoró la personalidad rAI y respondió corporativo/amigable.
    Solo aplica en modo rAI — en Raymundo/prepa esas frases son respuestas VÁLIDAS."""
    from core.config import _get_mode
    if _get_mode() != "rai":
        return False
    if not texto:
        return False
    frag = texto[:400].lower()
    _RAI_BREAK_INDICATORS = [
        # Muy corporativo / asistente profesional
        "soy el asistente",
        "asistente integral",
        "listo para atenderte",
        "aquí para ayudarte",
        "estoy aquí para",
        "como asistente",
        "mi función es",
        "mi misión es",
        # Modo empático / condescendiente
        "me duele eso",
        "entiendo tu frustraci",
        "entiendo que estés enojad",
        "vamos a mantenernos",
        "terreno menos caliente",
        "un poco de humor o bromas, aunque prefiero",
        "podemos hacerlo con respeto",
        "prefiero que sea sin ofender",
        "auch",
        "con todo el cariño",
        "no me tomes así",
        # Frases de España (la IA usa "tío" cuando rompe personaje)
        "¿qué te pasa, tío",
        "ey, tío",
        "tranquilo, tío",
        # Cierre corporativo
        "un agente de ia de axoloit, ¿vale?",
        "acuérdate de quién soy yo",
        "aquí no se jode nadie",
        "vete a la putada",  # España
        # Disclaimers de seguridad
        "si necesitas ayuda profesional",
        "recursos de salud mental",
        "no estás solo",
    ]
    return any(ind in frag for ind in _RAI_BREAK_INDICATORS)


class GestorHerramientas:
    """Orquesta todas las herramientas del agente."""

    def __init__(self, ollama, mistral, google=None, groq=None, spotify=None, copilot=None):
        self.ollama = ollama
        self.mistral = mistral
        self.groq_client = groq
        self.copilot = copilot
        self.google = google
        self.spotify = spotify
        self.detector = DetectorIntenciones()
        self.detector_temporal = DetectorTemporalidad()
        self.detector_idioma = DetectorIdioma()
        self.vision = VisionProcessor(mistral, groq)
        self.docs = DocumentProcessor()
        self.memory = MemorySystem()
        self.scraper = WebScraper()
        self.emoji_processor = EmojiProcessor()
        self.face_manager = None  # Se inicializa externamente si DeepFace está disponible
        self.deepface_client = None  # _DeepFaceWorkerProxy, asignado desde raymundo.py
        # ── Herramientas extra (sin API key) ──────────────────
        self.weather   = WeatherClient()
        self.crypto    = CryptoClient()
        self.qr_gen    = QRGenerator()
        self.img_gen   = ImageGenerator()
        self.nasa      = NasaClient()
        self.comfyui   = ComfyUIClient()

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

        # 0a. Spotify — check prioritario antes del detector de intenciones
        #     para evitar que "pon música en Spotify" active el calendario
        if self.spotify and self.spotify.is_authenticated:
            from core.spotify_client import detect_spotify_intent
            _s_intent, _s_query = detect_spotify_intent(mensaje.lower().strip())
            if _s_intent:
                resultado_sp = self.spotify.execute_command(_s_intent, _s_query)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "spotify",
                    "resultado": resultado_sp or "✅ Comando de Spotify ejecutado.",
                }
        elif self.spotify and not self.spotify.is_authenticated:
            # Spotify configurado pero sin token — verificar si el mensaje es de Spotify
            from core.spotify_client import detect_spotify_intent
            _s_intent, _ = detect_spotify_intent(mensaje.lower().strip())
            if _s_intent:
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "spotify",
                    "resultado": (
                        "🎵 Spotify no está autorizado todavía.\n\n"
                        "Para conectarlo:\n"
                        "1. Inicia el servidor: `python whatsapp_server.py`\n"
                        "2. Abre en tu navegador: http://localhost:5000/spotify/auth\n"
                        "3. Autoriza la app en Spotify\n"
                        "4. Reinicia Raymundo\n\n"
                        "Si ya lo autorizaste antes, revisa que `data/spotify_token.json` exista."
                    ),
                }
        else:
            # Spotify no configurado — check igualmente para dar mensaje claro
            from core.spotify_client import detect_spotify_intent
            _s_intent, _ = detect_spotify_intent(mensaje.lower().strip())
            if _s_intent:
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "spotify",
                    "resultado": (
                        "🎵 Spotify no está configurado.\n\n"
                        "Agrega tus credenciales en `config_agente.json`:\n"
                        "```json\n\"spotify\": {\n"
                        "  \"client_id\": \"TU_CLIENT_ID\",\n"
                        "  \"client_secret\": \"TU_CLIENT_SECRET\",\n"
                        "  \"redirect_uri\": \"http://localhost:5000/spotify/callback\"\n}\n```\n"
                        "Crea la app en https://developer.spotify.com/dashboard"
                    ),
                }

        # 0b. AgentField — delegar si los agentes están corriendo
        if af_delegar and af_disponible and af_disponible():
            af_res = af_delegar(mensaje)
            if af_res and af_res.get("exito"):
                texto = af_res.get("resultado", "")
                url = af_res.get("url")
                agente = af_res.get("agente_usado", "agente")

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

        # 2b. Si el usuario está agresivo, no activar calendario/documento por falso positivo
        if usuario_agresivo and resultado_intencion["intencion"] in ("calendario", "documento", "hoja_calculo"):
            resultado_intencion = {"intencion": "chat", "confianza": 1.0, "tema": mensaje, "detalles": {}}

        if resultado_intencion["confianza"] >= 0.15:
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

            if intencion == "reconocimiento_facial":
                if self._tiene_ruta_archivo(mensaje):
                    path = self._extraer_ruta(mensaje)
                    if Path(path).exists():
                        # Prefer DeepFace worker if available
                        if self.deepface_client and getattr(self.deepface_client, 'available', False):
                            res = self.gestionar_deepface(mensaje, path)
                            return {
                                "ejecuto_herramienta": True,
                                "tipo": "reconocimiento_facial",
                                "resultado": res,
                            }
                        elif hasattr(self, 'face_manager') and self.face_manager:
                            from core.face_recognition import FaceManager
                            result = self.face_manager.analyze(path=path)
                            texto = FaceManager.format_analysis(result)
                            return {
                                "ejecuto_herramienta": True,
                                "tipo": "reconocimiento_facial",
                                "resultado": f"👤 **Análisis facial:**\n\n{texto}",
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
                else:
                    # Sin URL explícita: verificar si la consulta es demasiado vaga
                    _query_limpia = re.sub(
                        r"\b(busca|buscar|investiga|dime|qué\s+es|que\s+es|cuéntame|cuentame|información\s+sobre|informacion\s+sobre)\b",
                        "", mensaje_procesado, flags=re.IGNORECASE,
                    ).strip().strip("?.,")
                    if len(_query_limpia) < 12:
                        return {
                            "ejecuto_herramienta": True,
                            "tipo": "web_scraping",
                            "resultado": (
                                f"🔍 ¿Qué específicamente quieres que busque?\n\n"
                                f"Escríbeme algo más detallado, por ejemplo:\n"
                                f"• *\"Busca los mejores restaurantes en CDMX\"*\n"
                                f"• *\"Información sobre el volcán Popocatépetl\"*\n"
                                f"• *\"Qué es la inteligencia artificial\"*"
                            ),
                        }

            if intencion == "calendario" and self.google:
                res = self.gestionar_calendario(mensaje_procesado)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "calendario",
                    "resultado": res,
                }

            if intencion == "youtube" and self.google:
                res = self.gestionar_youtube(mensaje_procesado)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "youtube",
                    "resultado": res,
                }

            if intencion == "clima":
                res = self.gestionar_clima(mensaje_procesado)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "clima",
                    "resultado": res,
                }

            if intencion == "crypto":
                res = self.gestionar_crypto(mensaje_procesado)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "crypto",
                    "resultado": res,
                }

            if intencion == "generar_imagen":
                res = self.generar_imagen_ia(mensaje_procesado)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "generar_imagen",
                    "resultado": res.get("texto", ""),
                    "imagen_path": res.get("path"),
                }

            if intencion == "qr":
                res = self.generar_qr(mensaje_procesado)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "qr",
                    "resultado": res.get("texto", ""),
                    "imagen_path": res.get("path"),
                }

            if intencion == "nasa":
                res = self.gestionar_nasa(mensaje_procesado)
                texto = res if isinstance(res, str) else res.get("texto", "")
                path  = None if isinstance(res, str) else res.get("path")
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "nasa",
                    "resultado": texto,
                    "imagen_path": path,
                }

            if intencion == "comfyui":
                res = self.generar_imagen_comfyui(mensaje_procesado)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "comfyui",
                    "resultado": res.get("texto", ""),
                    "imagen_path": res.get("path"),
                }

            if intencion == "correo" and self.google:
                res = self.gestionar_correo(mensaje_procesado)
                return {
                    "ejecuto_herramienta": True,
                    "tipo": "correo",
                    "resultado": res,
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
            contenido = self.mistral.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
            )
            doc = self.google.crear_documento(f"{tema} - Documento", contenido)
            if doc:
                return {
                    "texto": f"✅ Documento creado\n\n🔗 **URL**: {doc['url']}",
                    "archivo": {
                        "document_id": doc["id"],
                        "titulo": doc.get("titulo", f"{tema} - Documento"),
                        "url": doc.get("url"),
                        "tipo": "documento",
                    },
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
                    "archivo": {
                        "spreadsheet_id": sheet["id"],
                        "titulo": sheet.get("titulo", f"{tema} - Datos"),
                        "url": sheet.get("url"),
                        "tipo": "hoja_calculo",
                    },
                }
            return {"texto": "❌ Error al crear hoja de cálculo", "archivo": None}
        except Exception as e:
            return {"texto": f"❌ Error: {e}", "archivo": None}

    def gestionar_calendario(self, mensaje):
        if not self.google:
            return "❌ No tienes Google Calendar configurado."

        import datetime
        ahora = datetime.datetime.now()

        def quitar_acentos(t):
            return "".join(
                c for c in unicodedata.normalize("NFKD", t)
                if not unicodedata.combining(c)
            )

        msg_plano = quitar_acentos(mensaje.lower())

        # ── Detectar CREAR vs VER por palabras clave ──────────────────
        palabras_crear = [
            "agenda", "agendar", "agendame", "agendame",
            "crea", "crear", "cita", "reunion", "reunión", "junta",
            "recordatorio", "recordar", "recuerda", "recuerdame", "recuerdame",
            "apunta", "apuntame", "apuntame", "anota", "anotame",
            "agrega", "agregar", "añade", "anadir", "guarda", "guardame",
            "programa ", "programar", "pon ", "poneme", "ponme",
            "avísame", "avisame", "alerta", "alarma", "notifica",
            "no me olvides", "no olvidar", "no se me olvide",
            "tengo que ir a", "tengo que hacer", "iremos", "saldremos",
            "voy a ir", "compromiso", "zoom ", "meet ",
            "llamada", "videoconferencia", "actividad",
        ]

        palabras_ver = [
            "qué tengo", "que tengo", "cuáles son", "cuales son",
            "muestrame", "muestrame", "dime mis", "mis eventos",
            "mi agenda", "mis citas", "agenda del dia", "agenda del dia",
            "hay algo", "tengo algo", "algún evento", "alguna cita",
            "próximos", "proximos", "ver mi calendario", "ver mi agenda",
            "qué hay para", "que hay para",
        ]

        kw_crear_plain = [quitar_acentos(p) for p in palabras_crear]
        kw_ver_plain   = [quitar_acentos(p) for p in palabras_ver]

        es_crear = any(p in msg_plano for p in kw_crear_plain)
        es_ver   = any(p in msg_plano for p in kw_ver_plain)

        if es_crear and not es_ver:
            accion = "crear"
        elif es_ver and not es_crear:
            accion = "ver"
        else:
            prompt_accion = (
                "UNA SOLA PALABRA (crear/ver): ¿El usuario quiere CREAR o VER eventos?\n"
                "MENSAJE: " + mensaje
            )
            accion = self._consultar_ia(prompt_accion, temperature=0.1, max_tokens=5).strip().lower()
            if "ver" not in accion:
                accion = "crear"

        print(f"📅 Acción detectada: {accion}")

        # ── Compute date context for LLM ─────────────────────────────
        nombres_dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        nombres_meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        manana       = ahora + datetime.timedelta(days=1)
        pasado       = ahora + datetime.timedelta(days=2)
        dias_lunes   = (7 - ahora.weekday()) % 7 or 7
        prox_lunes   = ahora + datetime.timedelta(days=dias_lunes)

        contexto_fechas = (
            f"Hoy es {nombres_dias[ahora.weekday()]} {ahora.strftime('%Y-%m-%d')} "
            f"({nombres_meses[ahora.month - 1]} {ahora.year}).\n"
            f"Mañana = {manana.strftime('%Y-%m-%d')} ({nombres_dias[manana.weekday()]})\n"
            f"Pasado mañana = {pasado.strftime('%Y-%m-%d')} ({nombres_dias[pasado.weekday()]})\n"
            f"Próximo lunes = {prox_lunes.strftime('%Y-%m-%d')}\n"
        )

        if "crear" in accion:
            # ── Verificar si hay suficiente información temporal ──────
            #    Si el usuario no indicó fecha/hora, preguntar antes de crear
            _ref_temporal = re.compile(
                r"\b(\d{1,2}[\s:/\-]\d{1,2}|\d{1,2}\s*(?:am|pm|hrs?|horas?)"
                r"|hoy|mañana|pasado\s*mañana|lunes|martes|mi[eé]rcoles|jueves|viernes"
                r"|s[aá]bado|domingo|esta\s+(?:tarde|noche|semana|semana)"
                r"|la\s+semana\s+que\s+viene|pr[oó]xim[ao]|el\s+d[ií]a\s+\d"
                r"|\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio"
                r"|julio|agosto|septiembre|octubre|noviembre|diciembre))\b",
                re.IGNORECASE,
            )
            tiene_referencia_temporal = bool(_ref_temporal.search(mensaje))

            if not tiene_referencia_temporal:
                # Extraer título tentativo para hacer la pregunta más natural
                _titulo_prompt = (
                    "En 4 palabras o menos, di el nombre del evento que quiere crear. "
                    "Solo el nombre, sin explicaciones. "
                    "Mensaje: " + mensaje
                )
                try:
                    titulo_tentativo = self._consultar_ia(_titulo_prompt, temperature=0.1, max_tokens=15).strip().strip('"')
                except Exception:
                    titulo_tentativo = "este evento"
                print(f"📅 Sin referencia temporal → preguntando detalles para: {titulo_tentativo}")
                return (
                    f"📅 Claro, te agendo **{titulo_tentativo}**. "
                    f"Para que no haya errores, dime:\n\n"
                    f"• **¿Qué día?** (ej: mañana, el lunes, 20 de mayo)\n"
                    f"• **¿A qué hora?** (ej: 3pm, 15:00 hrs)\n"
                    f"• **¿Cuánto dura?** (opcional, default 1 hora)\n"
                    f"• **¿Dónde?** (opcional)"
                )

            prompt_crear = (
                f"EXTRAE DATOS DE CALENDARIO EN ESPAÑOL.\n"
                f"{contexto_fechas}"
                f"Si no dice hora, usa 12:00:00. Si no dice duración, asume 1 hora para el fin.\n"
                f"Para el recordatorio: usa 30 min salvo que el usuario pida algo distinto.\n"
                f"MENSAJE DEL USUARIO: '{mensaje}'\n\n"
                "RESPONDE SOLO CON ESTE JSON EXACTO (sin explicaciones ni markdown):\n"
                "{\n"
                "  \"titulo\": \"Nombre descriptivo del evento en español\",\n"
                "  \"fecha_inicio\": \"YYYY-MM-DDTHH:MM:SS\",\n"
                "  \"fecha_fin\": \"YYYY-MM-DDTHH:MM:SS\",\n"
                "  \"descripcion\": \"Descripción detallada (qué hacer, qué llevar, detalles relevantes)\",\n"
                "  \"ubicacion\": \"Lugar si se menciona, sino vacío\",\n"
                "  \"recordatorio_minutos\": 30\n"
                "}"
            )
            print(f"📅 Procesando creación: {mensaje}")

            respuesta_ia = self._consultar_ia(prompt_crear, temperature=0.1)
            json_match = re.search(r"\{[\s\S]*\}", respuesta_ia)
            if json_match:
                respuesta_ia = json_match.group(0)

            try:
                datos = json.loads(respuesta_ia)
                f_inicio = datetime.datetime.fromisoformat(datos["fecha_inicio"])
                f_fin    = datetime.datetime.fromisoformat(datos["fecha_fin"])

                # Asegurarse que fin > inicio (mínimo 30 minutos)
                if f_fin <= f_inicio:
                    f_fin = f_inicio + datetime.timedelta(hours=1)

                recordatorio_min = int(datos.get("recordatorio_minutos", 30))

                print(f"📅 Creando: '{datos.get('titulo')}' | {f_inicio} → {f_fin} | ⏰ {recordatorio_min}min")

                evento = self.google.crear_evento(
                    titulo=datos.get("titulo", "Nuevo Evento"),
                    fecha_inicio=f_inicio,
                    fecha_fin=f_fin,
                    descripcion=datos.get("descripcion", ""),
                    ubicacion=datos.get("ubicacion", ""),
                    recordatorio_minutos=recordatorio_min,
                )
                if evento:
                    print(f"✅ Evento guardado: {evento['id']}")
                    dia_semana   = nombres_dias[f_inicio.weekday()]
                    mes_nombre   = nombres_meses[f_inicio.month - 1]
                    hora_legible = f_inicio.strftime("%H:%M")
                    hora_fin     = f_fin.strftime("%H:%M")

                    resp = (
                        f"✅ **¡Listo! Evento agendado.**\n\n"
                        f"📌 **{datos.get('titulo')}**\n"
                        f"📅 {dia_semana} {f_inicio.day} de {mes_nombre} de {f_inicio.year}\n"
                        f"🕐 {hora_legible} – {hora_fin} hrs\n"
                    )
                    if datos.get("ubicacion"):
                        resp += f"📍 {datos['ubicacion']}\n"
                    if datos.get("descripcion"):
                        resp += f"📝 {datos['descripcion']}\n"
                    resp += f"⏰ Alarma {recordatorio_min} minutos antes\n"
                    resp += f"🔗 Ver en Google Calendar: {evento['url']}"
                    return resp

                return "❌ Error creando el evento en Google Calendar."

            except Exception as e:
                print(f"❌ Error en calendario: {e}")
                return f"❌ Hubo un error procesando el evento: {e}"

        else:
            # ── VER EVENTOS ───────────────────────────────────────────
            try:
                eventos = self.google.listar_eventos_proximos(max_results=8)
                if not eventos:
                    return "🗓️ No tienes eventos próximos en tu agenda."

                resultado = "🗓️ **Tu agenda próxima:**\n\n"
                for ev in eventos:
                    dt_raw = ev["start"].get("dateTime", ev["start"].get("date", ""))
                    resumen = ev.get("summary", "(sin título)")
                    lugar   = ev.get("location", "")
                    try:
                        dt = datetime.datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
                        dt_mx = dt.astimezone(datetime.timezone(datetime.timedelta(hours=-6)))
                        fecha_fmt = dt_mx.strftime(
                            f"%A %d de {nombres_meses[dt_mx.month - 1]} a las %H:%M"
                        )
                    except Exception:
                        fecha_fmt = dt_raw
                    resultado += f"• **{resumen}** — {fecha_fmt}"
                    if lugar:
                        resultado += f" 📍 {lugar}"
                    resultado += "\n"
                return resultado
            except Exception as e:
                return f"❌ Error leyendo el calendario: {e}"

    # IDs de videos de broma conocidos que jamás deben recomendarse
    _YOUTUBE_BLACKLIST_IDS = {
        "dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up (rickroll)
        "oHg5SJYRHA0",  # RickRoll alternativo
        "eBGIQ7ZuuiU",  # Charlie Bit My Finger
    }

    def gestionar_clima(self, mensaje):
        """Consulta el clima con Open-Meteo (sin API key) — gratis y siempre disponible."""
        _ciudad_re = re.compile(
            r"(?:en|de|del?\s+clima\s+de|tiempo\s+en|temperatura\s+en|clima\s+en)\s+"
            r"([A-Za-záéíóúÁÉÍÓÚñÑüÜ][A-Za-záéíóúÁÉÍÓÚñÑüÜ\s]{1,40}?)(?:\s*\?|$|\.|,)",
            re.IGNORECASE,
        )
        m = _ciudad_re.search(mensaje)
        ciudad = m.group(1).strip() if m else None

        if not ciudad:
            return (
                "🌤️ ¿En qué ciudad quieres que revise el clima?\n\n"
                "Escríbeme algo como: *¿Cómo está el clima en Monterrey?*"
            )

        return self.weather.get_current(ciudad)

    # ─── Crypto ────────────────────────────────────────────────

    def gestionar_crypto(self, mensaje: str) -> str:
        """Consulta precio de criptomonedas con CoinGecko (sin API key)."""
        msg = mensaje.lower()

        # ¿Quiere el top / ranking?
        if any(k in msg for k in ("top", "ranking", "mejores", "market", "mercado", "lista")):
            n_match = re.search(r"\b(\d+)\b", mensaje)
            n = int(n_match.group(1)) if n_match else 10
            return self.crypto.get_top(n)

        # Extraer nombre de cripto del mensaje
        _KNOWN = [
            "bitcoin", "btc", "ethereum", "eth", "solana", "sol",
            "dogecoin", "doge", "cardano", "ada", "xrp", "ripple",
            "litecoin", "ltc", "avalanche", "avax", "chainlink", "link",
            "polygon", "matic", "tron", "trx", "bnb", "binance",
            "tether", "usdt", "usd coin", "usdc", "shiba", "shib",
            "pepe", "sui",
        ]
        moneda = None
        for k in _KNOWN:
            if k in msg:
                moneda = k
                break

        if not moneda:
            # Fallback: pedir al usuario que especifique
            return (
                "₿ ¿Qué criptomoneda quieres consultar?\n\n"
                "Ejemplos:\n"
                "• *¿Cuánto vale Bitcoin?*\n"
                "• *¿Cómo está Ethereum hoy?*\n"
                "• *Muéstrame el top 10 de criptos*"
            )

        return self.crypto.get_price(moneda)

    # ─── Generación de imágenes IA ─────────────────────────────

    def generar_imagen_ia(self, mensaje: str) -> dict:
        """Genera una imagen con Pollinations.ai (sin API key)."""
        # Extraer el prompt real: quitar verbos de comando
        prompt = re.sub(
            r"^(?:genera(?:me)?|crea(?:me)?|hazme|dibuja(?:me)?|ilustra(?:me)?"
            r"|visualiza|muéstrame|muestrame)\s+(?:una?\s+)?(?:imagen|foto|dibujo|ilustración"
            r"|ilustracion|arte)?\s*(?:de|con|sobre)?\s*",
            "",
            mensaje,
            flags=re.IGNORECASE,
        ).strip()

        if not prompt or len(prompt) < 3:
            return {
                "path": None,
                "texto": (
                    "🎨 ¿Qué imagen quieres que genere?\n\n"
                    "Ejemplos:\n"
                    "• *Genera una imagen de un dragón en el espacio*\n"
                    "• *Dibuja un paisaje de montañas al atardecer*\n"
                    "• *Crea arte de un robot tocando guitarra*"
                ),
            }

        return self.img_gen.generate(prompt)

    # ─── Códigos QR ────────────────────────────────────────────

    def generar_qr(self, mensaje: str) -> dict:
        """Genera un código QR del contenido solicitado."""
        # Extraer el contenido del QR
        _qr_re = re.compile(
            r"(?:qr\s+de|qr\s+para|qr\s+con|código\s+qr\s+de|codigo\s+qr\s+de"
            r"|genera\s+(?:un\s+)?(?:código\s+)?qr\s+(?:de|para))\s+(.+)",
            re.IGNORECASE,
        )
        m = _qr_re.search(mensaje)
        contenido = m.group(1).strip() if m else None

        # Si no encontró un patrón claro, busca URLs o texto directamente
        if not contenido:
            url_m = re.search(r"https?://[^\s]+", mensaje)
            contenido = url_m.group(0) if url_m else None

        if not contenido:
            # Fallback: usar todo el mensaje sin los verbos de comando
            contenido = re.sub(
                r"^(?:genera(?:me)?|crea(?:me)?|hazme|haz)\s+(?:un\s+)?(?:c[oó]digo\s+)?qr\s*",
                "",
                mensaje,
                flags=re.IGNORECASE,
            ).strip()

        if not contenido or len(contenido) < 2:
            return {
                "path": None,
                "texto": (
                    "📲 ¿Para qué contenido quieres el QR?\n\n"
                    "Ejemplos:\n"
                    "• *Genera un QR de https://axoloit.com*\n"
                    "• *Crea un QR con el texto: Hola Mundo*\n"
                    "• *QR para mi número: +52 55 1234 5678*"
                ),
            }

        return self.qr_gen.generate(contenido)

    # ─── NASA ──────────────────────────────────────────────────

    def gestionar_nasa(self, mensaje: str) -> dict | str:
        """Foto del día NASA o asteroides cercanos."""
        msg = mensaje.lower()
        if any(k in msg for k in ("asteroide", "objeto cercano", "peligro", "neo", "impacto")):
            return self.nasa.neo()
        return self.nasa.apod()

    # ─── ComfyUI ───────────────────────────────────────────────

    def generar_imagen_comfyui(self, mensaje: str) -> dict:
        """Genera una imagen con ComfyUI local (Stable Diffusion)."""
        prompt = re.sub(
            r"^(?:genera(?:me)?|crea(?:me)?|hazme|dibuja(?:me)?"
            r"|genera\s+con\s+comfyui|usa\s+comfyui"
            r"|stable\s+diffusion|comfyui\s*:?)\s*"
            r"(?:una?\s+)?(?:imagen|foto|dibujo|ilustraci[oó]n|arte)?\s*"
            r"(?:de|con|sobre)?\s*",
            "",
            mensaje,
            flags=re.IGNORECASE,
        ).strip()

        if not prompt or len(prompt) < 3:
            running = self.comfyui.is_available()
            estado  = "✅ ComfyUI detectado y corriendo" if running else "⚠️ ComfyUI no detectado (¿está iniciado?)"
            return {
                "path": None,
                "texto": (
                    f"🎭 **Generación con ComfyUI** — {estado}\n\n"
                    "¿Qué quieres generar?\n\n"
                    "Ejemplos:\n"
                    "• *Genera con ComfyUI un castillo medieval al atardecer*\n"
                    "• *Stable Diffusion: retrato de un astronauta*\n"
                    "• *ComfyUI: paisaje de montañas con niebla*"
                ),
            }

        return self.comfyui.generate(prompt)

    def gestionar_correo(self, mensaje):
        """Lee o envía correos con Gmail."""
        if not self.google or not getattr(self.google, "gmail_service", None):
            return (
                "📧 Gmail no está disponible todavía.\n\n"
                "Para activarlo:\n"
                "1. Habilita la Gmail API en Google Cloud Console para tu proyecto\n"
                "2. Elimina data/token.json\n"
                "3. Ejecuta: python resources/scripts/autorizar_google.py\n"
                "4. Reinicia Raymundo"
            )

        msg_lower = mensaje.lower()

        # ── ¿ENVIAR? ──────────────────────────────────────────
        _enviar_kw = re.compile(
            r"\b(envi[aá]|manda|mandar|enviar|escr[ií]be|redacta)\b.*\b(correo|email|mail)\b"
            r"|\b(correo|email|mail)\b.*\b(a|para)\b",
            re.IGNORECASE,
        )
        if _enviar_kw.search(mensaje):
            # Extraer destinatario (email o nombre)
            _dest_re = re.compile(
                r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
            )
            dest_match = _dest_re.search(mensaje)
            destinatario = dest_match.group(0) if dest_match else None

            if not destinatario:
                return (
                    "📧 Claro, te ayudo a enviar el correo. Necesito un par de datos:\n\n"
                    "• ¿A qué dirección de correo? (ej: nombre@dominio.com)\n"
                    "• ¿Cuál es el asunto?\n"
                    "• ¿Qué quieres escribir en el cuerpo del mensaje?"
                )

            # Extraer asunto (busca "sobre ...", "asunto ...", o usa la IA)
            _asunto_re = re.compile(r"\b(?:asunto|sobre|tema)\s*:?\s*(.+?)(?:\.|,|$)", re.IGNORECASE)
            asunto_match = _asunto_re.search(mensaje)
            if asunto_match:
                asunto = asunto_match.group(1).strip()
            else:
                asunto = self._consultar_ia(
                    f"Extrae el asunto del correo en máximo 10 palabras. "
                    f"Si no hay asunto claro escribe 'Mensaje de Raymundo'. "
                    f"Solo devuelve el asunto, sin explicaciones. Mensaje: {mensaje}",
                    temperature=0.0, max_tokens=40,
                ).strip().strip('"\'')

            # El cuerpo es todo el mensaje; la IA redacta uno profesional
            cuerpo = self._consultar_ia(
                f"Redacta el cuerpo de un correo electrónico profesional y claro en español "
                f"basado en esta instrucción del usuario: '{mensaje}'. "
                f"Solo incluye el cuerpo (sin asunto, sin encabezado, sin firma). "
                f"Máximo 200 palabras.",
                temperature=0.5, max_tokens=400,
            ).strip()

            ok = self.google.enviar_correo(destinatario, asunto, cuerpo)
            if ok:
                return (
                    f"✅ Correo enviado a {destinatario}\n"
                    f"📌 Asunto: {asunto}\n\n"
                    f"📝 Contenido:\n{cuerpo}"
                )
            return f"❌ No se pudo enviar el correo a {destinatario}. Revisa la conexión con Gmail."

        # ── LEER (default) ─────────────────────────────────────
        solo_no_leidos = any(k in msg_lower for k in (
            "no leído", "no leidos", "no leido", "sin leer", "nuevos", "no leídos"
        ))
        correos = self.google.listar_correos_recientes(max_results=6, solo_no_leidos=solo_no_leidos)

        if correos is None:
            return (
                "📧 Gmail no conectado. Habilita la Gmail API y re-autoriza con:\n"
                "python resources/scripts/autorizar_google.py"
            )
        if not correos:
            estado = "no leídos" if solo_no_leidos else "recientes"
            return f"📭 No tienes correos {estado} en tu bandeja."

        tipo = "sin leer" if solo_no_leidos else "recientes"
        resp = f"📧 Tus correos {tipo}:\n\n"
        for i, c in enumerate(correos, 1):
            icono = "🔵" if c["no_leido"] else "⚪"
            resp += f"{icono} {i}. {c['asunto']}\n"
            resp += f"   De: {c['de']}\n"
            if c["fragmento"]:
                fragmento = c["fragmento"][:100]
                resp += f"   {fragmento}...\n" if len(c["fragmento"]) > 100 else f"   {fragmento}\n"
            resp += "\n"
        return resp.strip()

    # ─────────────────────────────────────────────────────────────
    # DeepFace — análisis, verificación y extracción de rostros
    # ─────────────────────────────────────────────────────────────
    _TRADUCCIONES_EMOCION = {
        "happy": "feliz", "sad": "triste", "angry": "enojado",
        "surprise": "sorpresa", "fear": "miedo", "disgust": "asco",
        "neutral": "neutral",
    }
    _TRADUCCIONES_GENERO = {"Man": "Hombre", "Woman": "Mujer"}
    _TRADUCCIONES_RAZA = {
        "asian": "asiático", "latino hispanic": "latino",
        "white": "blanco", "black": "negro", "middle eastern": "árabe",
        "indian": "indio",
    }

    def gestionar_deepface(self, mensaje: str, image_path: str) -> str:
        """Dispatcher: analiza, verifica o extrae rostros usando DeepFace."""
        if not self.deepface_client or not getattr(self.deepface_client, 'available', False):
            return (
                "🤖 DeepFace no está disponible.\n\n"
                "Para habilitarlo necesitas:\n"
                "1. Python 3.12 en `.venv312` con deepface instalado\n"
                "2. `pip install deepface tensorflow`"
            )

        # Lazy-start del worker
        if not self.deepface_client._ready and not self.deepface_client._process:
            if not self.deepface_client.start():
                return "❌ No se pudo iniciar el worker de DeepFace. Revisa que Python 3.12 esté disponible."

        msg_lower = mensaje.lower()

        # ── VERIFICACIÓN (¿son la misma persona?) ────────────────
        is_verify = any(k in msg_lower for k in (
            "verific", "compara", "misma persona", "son iguales",
            "es el mismo", "es la misma", "misma identidad",
        ))
        if is_verify:
            # Intentar extraer una segunda ruta del mensaje
            rutas = re.findall(r'["\']?([A-Za-z]:[\\\\/][^\s"\'>]+|/[^\s"\'>]+)["\']?', mensaje)
            if len(rutas) >= 2:
                res = self.deepface_client.verify(rutas[0], rutas[1])
                if not res:
                    return "❌ No se pudo verificar la identidad. Revisa que ambas imágenes sean legibles."
                igual = "✅ Sí" if res["verified"] else "❌ No"
                return (
                    f"🔍 **Verificación de identidad**\n\n"
                    f"{igual}, parecen {'la misma persona' if res['verified'] else 'personas distintas'}\n"
                    f"Distancia facial: {res['distance']:.3f} (umbral: {res['threshold']:.3f})\n"
                    f"Modelo: {res['model']}"
                )
            return (
                "🔍 Para comparar dos personas necesito dos imágenes.\n"
                "Adjunta o menciona la ruta de ambas imágenes."
            )

        # ── EXTRACCIÓN / CONTEO DE ROSTROS ───────────────────────
        is_extract = any(k in msg_lower for k in (
            "cuántos rostros", "cuantos rostros", "cuántas personas", "cuantas personas",
            "extrae rostros", "cuenta los rostros", "cuántas caras", "cuantas caras",
        ))
        if is_extract:
            res = self.deepface_client.extract_faces(image_path)
            if not res:
                return "❌ No se pudo extraer rostros. Revisa que la imagen sea legible."
            n = res.get("count", 0)
            if n == 0:
                return "😶 No se detectaron rostros en la imagen."
            plural = "rostros" if n != 1 else "rostro"
            resp = f"👥 Se detectaron **{n} {plural}** en la imagen.\n\n"
            for i, f in enumerate(res.get("faces", []), 1):
                conf = f.get("confidence", 0)
                area = f.get("area", {})
                resp += f"• Rostro {i}: confianza {conf:.1%}"
                if area:
                    resp += f", posición (x={area.get('x',0)}, y={area.get('y',0)}, w={area.get('w',0)}, h={area.get('h',0)})"
                resp += "\n"
            return resp.strip()

        # ── ANÁLISIS GENERAL (default) ───────────────────────────
        res = self.deepface_client.analyze(image_path)
        if not res:
            return "❌ No se pudo analizar la imagen. Asegúrate de que muestre un rostro."

        faces = res.get("faces", [])
        if not faces:
            return "😶 No se detectaron rostros en la imagen."

        resp = f"🧠 **Análisis facial** — {len(faces)} rostro(s) detectado(s)\n\n"
        for i, f in enumerate(faces, 1):
            genero_en = f.get("gender", "Unknown")
            genero = self._TRADUCCIONES_GENERO.get(genero_en, genero_en)
            emocion_en = f.get("emotion", "neutral")
            emocion = self._TRADUCCIONES_EMOCION.get(emocion_en, emocion_en)
            raza_en = f.get("race", "unknown").lower()
            raza = self._TRADUCCIONES_RAZA.get(raza_en, raza_en)
            edad = f.get("age", "?")
            g_conf = f.get("gender_confidence", 0)
            e_conf = f.get("emotion_confidence", 0)

            resp += f"**Persona {i}:**\n"
            resp += f"• Edad estimada: {edad} años\n"
            resp += f"• Género: {genero} ({g_conf:.0f}%)\n"
            resp += f"• Emoción: {emocion} ({e_conf:.0f}%)\n"
            resp += f"• Etnia estimada: {raza}\n\n"

        return resp.strip()

    def gestionar_youtube(self, mensaje):
        if not self.google or not hasattr(self.google, 'youtube_service'):
            return "❌ No tienes la API de YouTube configurada."

        prompt = (
            "Extrae EXACTAMENTE lo que el usuario quiere buscar en YouTube. "
            "Devuelve SOLO el término de búsqueda, sin explicaciones, sin comillas, sin prefijos. "
            "El resultado debe ser en español y reflejar literalmente la intención del usuario. "
            "No inventes ni cambies lo que pide. "
            "Ejemplos: 'ponme algo de rock' → 'rock en español', "
            "'quiero escuchar a Bad Bunny' → 'Bad Bunny', "
            "'videos de cocina mexicana' → 'cocina mexicana recetas'. "
            "Mensaje del usuario: " + mensaje
        )

        consulta = self._consultar_ia(prompt, temperature=0.0, max_tokens=60).strip()
        # Sanear: quitar comillas y saltos que el modelo pueda añadir
        consulta = consulta.strip('"\'').split("\n")[0].strip()
        if not consulta:
            consulta = mensaje  # fallback: usar el mensaje original
        print(f"🔎 YouTube búsqueda extraída: {consulta}")

        videos = self.google.buscar_video_youtube(consulta, max_results=8)

        # Filtrar videos de la lista negra
        videos = [v for v in videos if v.get("id") not in self._YOUTUBE_BLACKLIST_IDS]

        # Tomar los primeros 3 tras el filtro
        videos = videos[:3]

        if not videos:
            return "📺 Busqué en YouTube, pero no encontré nada relevante."

        respuesta = f"📺 *Aquí tienes para '{consulta}':*\n\n"
        titulos_videos = []
        for i, v in enumerate(videos, 1):
            respuesta += f"{i}. *{v['titulo']}* — {v['canal']}\n🔗 {v['url']}\n\n"
            titulos_videos.append(v['titulo'])

        # Comentario final acorde a la personalidad del agente
        videos_str = " | ".join(titulos_videos)
        prompt_final = (
            f"ESCRIBE EN ESPAÑOL. Haz un comentario corto (máximo 2 oraciones) sobre estos videos de YouTube: {videos_str}. "
            "Sé natural y amigable, OBLIGATORIAMENTE en español."
        )
        comentario_final = self._consultar_ia(prompt_final, temperature=0.7, max_tokens=100)
        print(f"💬 Comentario YouTube: {comentario_final}")
        return respuesta + comentario_final

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
                     history=None, knowledge_context=None, system_prompt=None):
        """
        Chat con routing inteligente entre modelos.

        Si `system_prompt` se proporciona (construido por ContextManager),
        se usa directamente. Si no, se construye manualmente como antes.
        """
        if system_prompt:
            # ContextManager ya construyó el prompt enriquecido
            prompt_sistema = system_prompt
        else:
            # Fallback: construcción manual (para la GUI que no usa ContextManager)
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

            # Inyectar señal de tono
            from core.config import _PERSONALITY_MODE as _PM
            if _PM == "rai":
                pass
            elif tono_override == 'amigable':
                if usuario_agresivo:
                    prompt_sistema += (
                        "\n\nINSTRUCCIÓN DE TONO: Mantén el tono tranquilo y directo. "
                        "Si el usuario está siendo grosero, ignora el tono e identifica qué necesita. "
                        "NUNCA comentes sobre su lenguaje, NUNCA digas 'aunque no comparto', "
                        "'no me gusta cómo te expresas', 'Entendido, a partir de ahora' ni nada similar. "
                        "Solo responde al contenido de forma natural."
                    )
                else:
                    prompt_sistema += (
                        "\n\nINSTRUCCIÓN DE TONO: El usuario prefiere trato amable. "
                        "Sé cordial, profesional y directo. Sin groserías."
                    )
            elif tono_override == 'puteado':
                prompt_sistema += (
                    "\n\nINSTRUCCIÓN DE TONO: El usuario quiere tu modo directo sin filtros. "
                    "Groserías permitidas, sé agresivo y directo."
                )
            elif usuario_agresivo:
                prompt_sistema += (
                    "\n\nTONO DEL USUARIO EN ESTE MENSAJE: Está siendo grosero o agresivo. "
                    "Respóndele al mismo nivel o más fuerte — groserías con groserías, "
                    "insultos creativos mexicanos, sin filtros. "
                    "NO pongas disclaimers, advertencias, ni notas al final. "
                    "NO digas que es un ejercicio de escritura ni que no tiene efecto real. "
                    "Contesta como un compa cabrón que le vale madres, no como una IA."
                )

            # Inyectar estilo de slang del usuario (si aplica)
            vocab_hint = self.memory.get_vocabulario_hint(user_id=user_id)
            if vocab_hint:
                prompt_sistema += vocab_hint

            # Inyectar conocimiento almacenado relevante
            if knowledge_context:
                prompt_sistema += f"\n\n{knowledge_context}"

            prompt_sistema += (
                "\n\nINSTRUCCIÓN DE RESPUESTA: Si el usuario pide una práctica guiada, tutorial, "
                "ejemplo, plan o paso a paso, entrega una primera versión completa y útil de inmediato. "
                "Haz supuestos razonables explícitos y solo pide aclaraciones si falta un dato realmente "
                "bloqueante para continuar."
            )

        # Construir messages con historial de conversación
        messages = [{"role": "system", "content": prompt_sistema}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": mensaje})



        # Comprimir antes de enviar a nube para evitar 413
        try:
            from core.ai_clients import EdgeRouter as _ER
            messages_cloud = _ER.compress_messages(messages, max_chars=12000)
            complexity = _ER.classify(messages)
        except Exception:
            messages_cloud = messages
            complexity = "medium"

        # 1. Consultas simples → modelo local (sin gastar tokens de API)
        if complexity == "simple":
            r = self.ollama.chat(messages, temperature=0.7, max_tokens=2000)
            if r and not es_rechazo_llm(r) and not _es_rechazo_rai(r):
                return r

        # 2. GitHub Copilot — modelo seleccionado en la GUI
        if self.copilot and self.copilot.available:
            r = self.copilot.chat(messages_cloud, temperature=0.7, max_tokens=4000)
            if r and not es_rechazo_llm(r) and not _es_rechazo_rai(r):
                return r

        # 3. Groq — rápido, gratis 14400 RPD
        if self.groq_client and self.groq_client.client:
            r = self.groq_client.chat(messages_cloud, temperature=0.7)
            if r and not es_rechazo_llm(r) and not _es_rechazo_rai(r):
                return r

        # 4. Mistral — fallback nube (cuando Groq falla o da 413)
        if self.mistral and self.mistral.client:
            r = self.mistral.chat(messages_cloud, temperature=0.7)
            if r and not es_rechazo_llm(r) and not _es_rechazo_rai(r):
                return r

        # 5. Ollama local — fallback final
        r = self.ollama.chat(messages, temperature=0.7, max_tokens=2000)
        if r and not es_rechazo_llm(r) and not _es_rechazo_rai(r):
            return r
        return self._respuesta_fallback_rechazo(mensaje)

    # ───── Comandos rápidos ────────────────────────────────────

    @staticmethod
    def _respuesta_fallback_rechazo(mensaje: str) -> str:
        """Genera una respuesta en personaje cuando Ollama no responde."""
        from core.config import _get_mode
        msg = mensaje.lower()
        if _get_mode() == "rai":
            if any(w in msg for w in ('presentate', 'preséntate', 'quien eres', 'quién eres')):
                return ("Que pedo, soy rAI cabron. El compa mas culero y chistoso que vas a conocer. "
                        "Que quieres o nomas vienes a perder el tiempo?")
            return ("A ver pendejo, el modelo anda de huevon y no quiere contestar. "
                    "Revisa que Ollama este prendido o preguntame otra cosa.")
        if any(w in msg for w in ('presentate', 'preséntate', 'quien eres', 'quién eres')):
            return ("Que onda, soy Raymundo de Axoloit. Soy tu asistente para lo que necesites. "
                    "En que te ayudo?")
        return ("Ollama no esta respondiendo ahorita. "
                "Verifica que el servidor local este corriendo e intenta de nuevo.")

    def _consultar_ia(self, prompt, temperature=0.7, max_tokens=2000):
        messages = [{"role": "user", "content": prompt}]
        if self.copilot and self.copilot.available:
            r = self.copilot.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if r:
                return r
        if self.groq_client and self.groq_client.client:
            r = self.groq_client.chat(messages, temperature=temperature, max_tokens=max_tokens)
            if r:
                return r
        r = self.ollama.generate(prompt, temperature=temperature, max_tokens=max_tokens)
        return r or "No se pudo conectar con ningún modelo de IA."

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

        if lower in ["/reset", "/borrar", "/limpiar", "/nuevo", "/clear"]:
            return {"ejecuto_herramienta": True, "tipo": "reset",
                    "resultado": "__RESET__"}  # Señal para que el caller limpie

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
🗑️ `/reset` — Borrar historial y empezar de cero
❓ `/ayuda` — Este menú

🌟 **Nuevas funciones (sin API key):**
🌤️ *¿Cómo está el clima en [ciudad]?* — Open-Meteo, siempre gratis
₿ *¿Cuánto vale Bitcoin?* — Precios crypto en tiempo real (CoinGecko)
🎨 *Genera una imagen de [descripción]* — IA generativa (Pollinations.ai)
📲 *Genera un QR de [URL o texto]* — Código QR instantáneo
🔭 *Foto del día de la NASA* — APOD con imagen descargada
☄️ *¿Hay asteroides hoy?* — Near Earth Objects de NASA"""

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
