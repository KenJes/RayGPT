"""
Procesadores — Visión, documentos y emojis.
"""

import base64
from pathlib import Path

import emoji


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
    """Procesa imágenes con GPT-4o Vision."""

    def __init__(self, github_client):
        self.github_client = github_client
        self.supported_formats = [".png", ".jpg", ".jpeg", ".gif", ".webp"]

    def encode_image(self, image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def analyze_image(self, image_path, prompt="Describe esta imagen en detalle"):
        if not Path(image_path).exists():
            return "❌ Imagen no encontrada"
        try:
            b64 = self.encode_image(image_path)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ]
            return self.github_client.chat_with_images(messages, max_tokens=1000)
        except Exception as e:
            return f"❌ Error: {e}"


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
