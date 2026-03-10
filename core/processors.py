"""
Procesadores — Visión, documentos, emojis y OCR.
"""

import base64
import io
import tempfile
from pathlib import Path

import emoji
from PIL import Image


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
    """Procesa imágenes con GPT-4o Vision y OCR, con fallback a Groq Vision."""

    def __init__(self, github_client, groq_client=None):
        self.github_client = github_client
        self.groq_client = groq_client
        self.supported_formats = [".png", ".jpg", ".jpeg", ".gif", ".webp"]

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
        """Analiza una imagen desde datos base64 (sin archivo en disco)."""
        try:
            return self._analyze_base64(b64_data, prompt)
        except Exception as e:
            return f"❌ Error: {e}"

    def extract_text_from_image(self, image_path: str) -> str:
        """Extrae texto de una imagen usando GPT-4o Vision como OCR inteligente."""
        prompt = (
            "Extrae TODO el texto visible en esta imagen, exactamente como aparece. "
            "Mantén el formato, saltos de línea y estructura. "
            "Si es un CV/currículum, incluye TODOS los datos: nombre, experiencia, "
            "educación, habilidades, certificaciones, idiomas, contacto."
        )
        return self.analyze_image(image_path, prompt)

    def extract_text_from_base64(self, b64_data: str) -> str:
        """Extrae texto de una imagen base64 usando GPT-4o Vision como OCR."""
        prompt = (
            "Extrae TODO el texto visible en esta imagen, exactamente como aparece. "
            "Mantén el formato, saltos de línea y estructura. "
            "Si es un CV/currículum, incluye TODOS los datos: nombre, experiencia, "
            "educación, habilidades, certificaciones, idiomas, contacto."
        )
        return self.analyze_image_base64(b64_data, prompt)

    def save_base64_to_temp(self, b64_data: str, suffix: str = ".jpg") -> str:
        """Guarda datos base64 en un archivo temporal y devuelve la ruta."""
        img_bytes = base64.b64decode(b64_data)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=str(Path("output")))
        tmp.write(img_bytes)
        tmp.close()
        return tmp.name

    def _analyze_base64(self, b64_data: str, prompt: str) -> str:
        """Envía imagen base64 a GPT-4o Vision, con fallback a Groq Vision."""
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
        # Intento 1: GitHub Models (GPT-4o Vision)
        result = self.github_client.chat_with_images(messages, max_tokens=2000)
        if result and not str(result).startswith("❌"):
            return result

        # Intento 2: Groq Vision (llama-3.2-90b-vision-preview)
        if self.groq_client and self.groq_client.client:
            try:
                groq_response = self.groq_client.client.chat.completions.create(
                    model="llama-3.2-90b-vision-preview",
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000,
                )
                if groq_response and groq_response.choices:
                    return groq_response.choices[0].message.content
            except Exception as e:
                # Si 90b falla, intentar con 11b
                try:
                    groq_response = self.groq_client.client.chat.completions.create(
                        model="llama-3.2-11b-vision-preview",
                        messages=messages,
                        temperature=0.3,
                        max_tokens=2000,
                    )
                    if groq_response and groq_response.choices:
                        return groq_response.choices[0].message.content
                except Exception:
                    pass

        return result or "❌ No se pudo analizar la imagen (todos los proveedores fallaron)"


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
