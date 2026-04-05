"""
Detectores — Intenciones, temporalidad e idioma.
"""

import re
import unicodedata


class DetectorIntenciones:
    """Detecta qué quiere hacer el usuario."""

    KEYWORDS_PRESENTACION = [
        "presentación", "presentacion", "slides", "diapositivas",
        "ppt", "powerpoint", "exponer", "exposición", "exposicion",
        "pitch", "presentar", "haz una presentación", "haz una presentacion",
        "crea una presentación", "crea una presentacion", "genera una presentación",
        "genera una presentacion", "quiero una presentación", "necesito una presentación",
        "presentación de", "presentacion de", "presentación sobre", "presentacion sobre",
        "presentation", "make a presentation", "create a presentation",
        "presentation about", "presentation on",
    ]

    KEYWORDS_DOCUMENTO = [
        "documento", "doc", "escribir", "redactar", "texto",
        "informe", "reporte", "nota", "artículo", "articulo",
        "crea un documento", "genera un documento", "haz un documento",
        "documento sobre", "documento de",
    ]

    KEYWORDS_HOJA_CALCULO = [
        "hoja de cálculo", "hoja de calculo", "spreadsheet", "excel",
        "tabla de datos", "tabla", "datos", "xlsx",
        "crea una hoja", "genera una hoja", "haz una hoja",
        "hoja con datos", "registro de",
    ]

    KEYWORDS_IMAGENES = [
        "imagen", "imágenes", "imagenes", "foto", "fotos",
        "analiza imagen", "analiza la imagen", "qué hay en la imagen",
        "describe imagen", "describe la imagen", "lee la imagen",
    ]

    KEYWORDS_DOCUMENTOS_ANALISIS = [
        "lee el documento", "lee este documento", "analiza el documento",
        "resume el documento", "qué dice el documento", "que dice el documento",
        "lee el pdf", "lee este pdf", "lee el archivo",
        "resume este", "analiza este", "extrae del documento",
    ]

    KEYWORDS_WEB_SCRAPING = [
        "qué es", "que es", "información sobre", "informacion sobre",
        "busca", "investiga", "dime sobre", "cuéntame de", "cuentame de",
        ".com", ".mx", ".org", ".net", "http", "www", "página", "pagina",
        "sitio web", "website",
    ]

    KEYWORDS_CALENDARIO = [
        # Acciones directas de crear
        "agenda", "agendar", "agendame", "agéndame",
        "cita", "citas", "reunion", "reunión", "junta", "juntas",
        "evento", "eventos", "recordatorio", "recordatorios",
        "recordar", "recuerda", "recuérdame", "recuerdame",
        "programa", "programar", "calendariza",
        "apunta", "apúntame", "apuntame", "anota", "anótame", "anotame",
        "agrega", "agregar", "añade", "añadir", "crea un", "crear un",
        "pon ", "poneme", "pónme", "guarda", "guárdame", "guardame",
        "avísame", "avisame", "alerta", "alarma", "notifícame", "notificame",
        "no me olvides", "no se me olvide", "no olvidar",
        "tengo que ir a", "tengo que hacer",
        "voy a ir", "iremos", "saldremos", "estaremos",
        "compromiso", "una llamada", "la llamada", "agendar llamada", "videollamada", "videoconferencia",
        "actividad", "tarea para",
        # Ver la agenda
        "mi agenda", "mis eventos", "mis citas",
        "qué tengo", "que tengo", "cuándo tengo", "cuando tengo",
        "próximos eventos", "proximos eventos",
        "qué hay en mi agenda", "que hay en mi agenda", "hay algo agendado",
        "tengo agendado", "tengo algo",
        "mi calendario", "ver calendario", "agenda del día", "agenda del dia",
        "qué eventos tengo", "que eventos tengo",
        # Referencias temporales que implican agenda
        "mañana a las", "hoy a las", "esta tarde a las", "esta noche a las",
        "pasado mañana", "la semana que viene", "la próxima semana",
        "el lunes", "el martes", "el miércoles", "el jueves",
        "el viernes", "el sábado", "el domingo",
        "agrega a mi agenda", "agrega al calendario", "agregar al calendario",
        "pon en mi agenda", "pon en el calendario", "ponme en el calendario",
        "agrega un recordatorio", "pon un recordatorio", "crea un recordatorio",
        "crea un evento", "crear un evento", "añade al calendario",
    ]

    KEYWORDS_YOUTUBE = [
        "youtube", "video", "recomienda un video", "busca en youtube",
        "videos de", "video de", "quiero ver un video",
    ]

    @staticmethod
    def _strip_accents(text):
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def detectar(self, mensaje):
        mensaje_lower = unicodedata.normalize("NFC", mensaje.lower())
        scores = {
            "presentacion": self._contar_keywords(mensaje_lower, self.KEYWORDS_PRESENTACION),
            "documento": self._contar_keywords(mensaje_lower, self.KEYWORDS_DOCUMENTO),
            "hoja_calculo": self._contar_keywords(mensaje_lower, self.KEYWORDS_HOJA_CALCULO),
            "imagenes": self._contar_keywords(mensaje_lower, self.KEYWORDS_IMAGENES),
            "analisis_documento": self._contar_keywords(mensaje_lower, self.KEYWORDS_DOCUMENTOS_ANALISIS),
            "web_scraping": self._contar_keywords(mensaje_lower, self.KEYWORDS_WEB_SCRAPING),
            "calendario": self._contar_keywords(mensaje_lower, self.KEYWORDS_CALENDARIO),
            "youtube": self._contar_keywords(mensaje_lower, self.KEYWORDS_YOUTUBE),
        }

        intencion_principal = max(scores, key=scores.get)
        confianza = scores[intencion_principal] / 10.0

        if confianza < 0.25:
            return {"intencion": "chat", "confianza": 1.0, "tema": mensaje, "detalles": {}}

        tema = self._extraer_tema(mensaje, intencion_principal)
        detalles = self._extraer_detalles(mensaje, intencion_principal)

        return {
            "intencion": intencion_principal,
            "confianza": min(confianza, 1.0),
            "tema": tema,
            "detalles": detalles,
        }

    def _contar_keywords(self, texto, keywords):
        texto_nfc = unicodedata.normalize("NFC", texto)
        texto_sin_acentos = self._strip_accents(texto_nfc)

        count = 0
        for keyword in keywords:
            keyword_nfc = unicodedata.normalize("NFC", keyword)
            keyword_sin_acentos = self._strip_accents(keyword_nfc)
            if keyword_nfc in texto_nfc or keyword_sin_acentos in texto_sin_acentos:
                count += 5 if " " in keyword else 2
        return count

    def _extraer_tema(self, mensaje, intencion):
        patrones = [
            r"sobre (.+?)(?:\.|$)",
            r"de (.+?)(?:\.|$)",
            r"acerca de (.+?)(?:\.|$)",
        ]
        for patron in patrones:
            match = re.search(patron, mensaje, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return mensaje

    def _extraer_detalles(self, mensaje, intencion):
        detalles = {}
        if intencion == "presentacion":
            match_slides = re.search(r"(\d+)\s*(?:diapositiva|slide)", mensaje, re.IGNORECASE)
            detalles["num_slides"] = int(match_slides.group(1)) if match_slides else 5
            detalles["con_imagenes"] = any(
                w in mensaje.lower() for w in ["imagen", "foto", "ilustr", "visual"]
            )
            if any(w in mensaje.lower() for w in ["profesional", "formal", "negocio"]):
                detalles["estilo"] = "profesional"
            elif any(w in mensaje.lower() for w in ["creativ", "modern", "colorid"]):
                detalles["estilo"] = "creativo"
            else:
                detalles["estilo"] = "profesional"
        return detalles


# ═══════════════════════════════════════════════════════════════

class DetectorTemporalidad:
    """Detecta si una consulta necesita info actual o conocimiento histórico."""

    KEYWORDS_ACTUAL = [
        "hoy", "ahora", "actual", "actualmente", "ahorita", "reciente",
        "recientemente", "último", "ultima", "últimas", "últimos",
        "este año", "este mes", "esta semana",
        "en 2024", "en 2025", "en 2026", "2024", "2025", "2026",
        "noticia", "noticias", "trending", "tendencia", "novedad",
        "nuevo", "nueva", "nuevos", "nuevas", "lanzamiento",
        "actualización", "actualizacion", "update",
        "qué pasó", "que paso", "qué está pasando", "que esta pasando",
        "gpt-4", "gpt4", "gpt-4o", "claude", "gemini", "llama 3",
        "chatgpt", "openai", "midjourney", "sora",
        "precio actual", "cuánto cuesta", "cuanto cuesta",
        "estado actual", "cómo está", "como esta",
    ]

    KEYWORDS_HISTORICO = [
        "qué es", "que es", "quién fue", "quien fue", "quién es", "quien es",
        "definición", "definicion", "concepto", "significa",
        "historia de", "origen de", "cómo funciona", "como funciona",
        "explica", "explícame", "explicame", "enséñame", "enseñame",
        "tutorial", "ejemplo de", "cómo hacer", "como hacer",
        "cómo se hace", "como se hace", "código", "codigo",
        "programa", "algoritmo", "función", "funcion", "clase",
        "python", "javascript", "html", "css", "sql", "java",
        "base de datos", "servidor", "framework",
        "fórmula", "formula", "ecuación", "ecuacion", "teorema",
        "calcular", "resolver", "matemáticas", "matematicas",
        "física", "fisica", "química", "quimica", "biología", "biologia",
        "libro", "película", "pelicula", "canción", "cancion",
        "receta", "cocinar", "ingredientes",
        "traduce", "traducir", "traducción", "traduccion",
        "cómo se dice", "como se dice", "en inglés", "en ingles",
    ]

    def detectar(self, mensaje):
        """Retorna 'actual' o 'historico'."""
        msg = mensaje.lower()
        score_actual = sum(3 if " " in kw else 1 for kw in self.KEYWORDS_ACTUAL if kw in msg)
        score_hist = sum(3 if " " in kw else 1 for kw in self.KEYWORDS_HISTORICO if kw in msg)

        if re.search(r"\b202[3-9]\b", msg):
            score_actual += 5
        if re.search(r"\b(1[0-9]{3}|20[01][0-9]|202[0-2])\b", msg):
            score_hist += 5
        if score_actual == 0 and score_hist == 0:
            return "historico"
        return "actual" if score_actual > score_hist else "historico"


# ═══════════════════════════════════════════════════════════════

class DetectorIdioma:
    """Detecta si el mensaje está en inglés o español."""

    ENGLISH_WORDS = {
        "the", "is", "are", "was", "were", "am", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "shall", "may", "might", "must", "can",
        "this", "that", "these", "those", "there", "here",
        "what", "which", "who", "whom", "whose", "where", "when",
        "why", "how", "not", "but", "and", "or", "because",
        "about", "with", "from", "into", "through",
        "after", "before", "between", "under", "over",
        "know", "think", "want", "need", "tell", "give", "make",
        "help", "talk", "explain", "send", "create", "please",
        "understand", "write", "read", "show", "find", "get",
        "good", "bad", "great", "important", "something", "anything",
        "english", "language", "audio", "message", "improve",
        "you", "your", "he", "she", "they", "them", "his", "her",
        "its", "our", "their", "my", "me", "we", "us",
        "yo", "bro", "bruh", "dawg", "fam", "homie",
        "ain't", "gonna", "wanna", "gotta", "tryna", "finna",
    }

    SPANISH_WORDS = {
        "el", "la", "los", "las", "un", "una", "unos", "unas",
        "es", "son", "está", "están", "fue", "ser", "estar",
        "tiene", "tienen", "hay", "haber", "hacer", "puede",
        "qué", "que", "quién", "quien", "cómo", "como", "dónde", "donde",
        "cuándo", "cuando", "por", "para", "pero", "porque", "sino",
        "este", "esta", "estos", "estas", "ese", "esa", "esos",
        "también", "tambien", "más", "muy", "bien", "mal",
        "yo", "tú", "tu", "él", "ella", "nosotros", "ellos",
        "mi", "me", "te", "se", "nos", "les",
        "hola", "gracias", "bueno", "malo", "grande",
        "necesito", "quiero", "puedo", "dime", "hazme", "mándame",
        "wey", "güey", "pedo", "chingón", "verga", "puto", "mames",
        "ke", "ps", "pz", "nmms", "alv", "nel", "simon",
    }

    def detectar(self, mensaje):
        palabras = re.findall(r"[a-záéíóúüñ']+", mensaje.lower())
        if not palabras:
            return "es"
        en_count = sum(1 for p in palabras if p in self.ENGLISH_WORDS)
        es_count = sum(1 for p in palabras if p in self.SPANISH_WORDS)
        total = len(palabras)
        en_ratio = en_count / total if total else 0
        if en_ratio > 0.3 and en_count > es_count:
            return "en"
        if en_ratio > 0.5:
            return "en"
        return "es"
