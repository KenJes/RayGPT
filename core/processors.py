"""
Procesadores — Visión, documentos, emojis y OCR local (Tesseract).
"""

import base64
import io
import tempfile
from pathlib import Path

import emoji
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter

# Ruta del binario de Tesseract en Windows
_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if Path(_TESSERACT_PATH).exists():
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_PATH


class EmojiProcessor:
    """Procesa y explica emojis en el texto."""

    def procesar(self, texto):
        emojis_encontrados = [c for c in texto if c in emoji.EMOJI_DATA]
        if emojis_encontrados:
            texto_con_desc = emoji.demojize(texto, delimiters=("", ""))
            return {
                "tiene_emojis": True,
                "emojis": emojis_encontrados,
                "texto_original": texto,
                "texto_procesado": texto_con_desc,
            }
        return {"tiene_emojis": False, "texto_procesado": texto}


class VisionProcessor:
    """OCR local con Tesseract + fallback a APIs de Vision si están disponibles."""

    def __init__(self, mistral_client=None, groq_client=None):
        self.mistral_client = mistral_client
        self.groq_client = groq_client
        self.supported_formats = [".png", ".jpg", ".jpeg", ".gif", ".webp"]

    # ─── Métodos públicos ─────────────────────────────────────

    def encode_image(self, image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def analyze_image(self, image_path, prompt="Describe esta imagen en detalle"):
        if not Path(image_path).exists():
            return "❌ Imagen no encontrada"
        try:
            b64 = self.encode_image(image_path)
            return self._analyze_base64(b64, prompt)
        except Exception as e:
            return f"❌ Error: {e}"

    def analyze_image_base64(self, b64_data: str, prompt: str = "Describe esta imagen en detalle") -> str:
        """Analiza una imagen desde datos base64."""
        try:
            return self._analyze_base64(b64_data, prompt)
        except Exception as e:
            return f"❌ Error: {e}"

    def extract_text_from_image(self, image_path: str) -> str:
        """Extrae texto de una imagen. Usa Tesseract local."""
        if not Path(image_path).exists():
            return "❌ Imagen no encontrada"
        try:
            img = Image.open(image_path)
            return self._ocr_local(img)
        except Exception as e:
            return f"❌ Error OCR: {e}"

    def extract_text_from_base64(self, b64_data: str, mimetype: str | None = None) -> str:
        """Extrae texto de media base64. Detecta PDF vs imagen automáticamente."""
        try:
            raw = base64.b64decode(b64_data)
            is_pdf = (
                (mimetype and "pdf" in mimetype.lower())
                or raw[:5] == b"%PDF-"
            )
            if is_pdf:
                return self._extract_text_from_pdf_bytes(raw)
            img = Image.open(io.BytesIO(raw))
            return self._ocr_local(img)
        except Exception as e:
            return f"❌ Error OCR: {e}"

    def _extract_text_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """Extrae texto de bytes de un PDF usando PyPDF2."""
        try:
            import PyPDF2
        except ImportError:
            return "❌ PyPDF2 no instalado. Ejecuta: pip install pypdf2"
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        pages_text = []
        for page in reader.pages[:50]:
            t = page.extract_text()
            if t:
                pages_text.append(t)
            if sum(len(p) for p in pages_text) > 50000:
                break
        text = "\n\n".join(pages_text).strip()
        if not text:
            return "❌ No se detectó texto en el PDF"
        return text

    def save_base64_to_temp(self, b64_data: str, suffix: str = ".jpg") -> str:
        """Guarda datos base64 en un archivo temporal y devuelve la ruta."""
        img_bytes = base64.b64decode(b64_data)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=str(Path("output")))
        tmp.write(img_bytes)
        tmp.close()
        return tmp.name

    # ─── OCR local (Tesseract) ────────────────────────────────

    def _ocr_local(self, img: Image.Image) -> str:
        """OCR local con Tesseract. Preprocesa la imagen para mejorar precisión."""
        # Preprocesamiento para mejorar OCR
        processed = self._preprocess_for_ocr(img)

        # Extraer texto con Tesseract (español + inglés)
        text = pytesseract.image_to_string(processed, lang="spa+eng", config="--psm 6")
        text = text.strip()

        if not text:
            # Reintentar con diferente modo de segmentación
            text = pytesseract.image_to_string(processed, lang="spa+eng", config="--psm 3")
            text = text.strip()

        if not text:
            return "❌ No se detectó texto en la imagen"

        return text

    def _preprocess_for_ocr(self, img: Image.Image) -> Image.Image:
        """Preprocesa imagen para mejorar la precisión del OCR."""
        # Convertir a escala de grises
        if img.mode != "L":
            img = img.convert("L")

        # Escalar si es muy pequeña (Tesseract funciona mejor con imágenes grandes)
        w, h = img.size
        if w < 1000:
            scale = 1000 / w
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Aumentar contraste
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # Aumentar nitidez
        img = img.filter(ImageFilter.SHARPEN)

        return img

    # ─── Vision API (fallback opcional) ───────────────────────

    def _analyze_base64(self, b64_data: str, prompt: str) -> str:
        """Intenta APIs de Vision si están disponibles; si no, OCR local."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"},
                    },
                ],
            }
        ]

        # Intento 1: Mistral Pixtral (Vision)
        if self.mistral_client and self.mistral_client.client:
            result = self.mistral_client.chat_with_images(messages, max_tokens=2000)
            if result and not str(result).startswith("❌"):
                return result

        # Intento 2: Groq Vision
        if self.groq_client and self.groq_client.client:
            for model in ("llama-3.2-90b-vision-preview", "llama-3.2-11b-vision-preview"):
                try:
                    resp = self.groq_client.client.chat.completions.create(
                        model=model, messages=messages, temperature=0.3, max_tokens=2000,
                    )
                    if resp and resp.choices:
                        return resp.choices[0].message.content
                except Exception:
                    continue

        # Intento 3: OCR local con Tesseract (siempre disponible)
        try:
            img = self._b64_to_pil(b64_data)
            return self._ocr_local(img)
        except Exception as e:
            return f"❌ Error OCR local: {e}"

    # ─── Utilidades ───────────────────────────────────────────

    def _b64_to_pil(self, b64_data: str) -> Image.Image:
        """Convierte base64 a imagen PIL."""
        img_bytes = base64.b64decode(b64_data)
        return Image.open(io.BytesIO(img_bytes))


class DocumentProcessor:
    """Procesa documentos PDF, DOCX, TXT."""

    def __init__(self):
        self.max_chars = 50000

    def read_txt(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()[: self.max_chars]
            return {"success": True, "content": content, "format": "text"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_pdf(self, file_path):
        try:
            import PyPDF2

            text = ""
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages[:50]:
                    text += page.extract_text() + "\n\n"
                    if len(text) > self.max_chars:
                        break
            return {"success": True, "content": text[: self.max_chars], "format": "pdf"}
        except ImportError:
            return {"success": False, "error": "Instala PyPDF2: pip install pypdf2"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_document(self, file_path):
        ext = Path(file_path).suffix.lower()
        if ext in [".txt", ".md"]:
            return self.read_txt(file_path)
        if ext == ".pdf":
            return self.read_pdf(file_path)
        return {"success": False, "error": "Formato no soportado"}
