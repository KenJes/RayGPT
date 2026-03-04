"""
WebScraper — Extrae contenido de páginas web.
"""

import re
import requests
from bs4 import BeautifulSoup


class WebScraper:
    """Obtiene información de páginas web."""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def extraer_url(self, texto):
        """Extrae URLs del mensaje."""
        patron = r"https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}"
        urls = re.findall(patron, texto)
        return [url if url.startswith("http") else f"https://{url}" for url in urls]

    def scrape(self, url):
        """Obtiene contenido de una URL."""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()

            titulo = soup.find("title")
            titulo_texto = titulo.get_text() if titulo else "Sin título"

            meta_desc = soup.find("meta", attrs={"name": "description"})
            descripcion = meta_desc.get("content", "") if meta_desc else ""

            texto = soup.get_text(separator="\n", strip=True)
            texto = "\n".join([line for line in texto.split("\n") if line])[:2000]

            return {
                "success": True,
                "url": url,
                "titulo": titulo_texto,
                "descripcion": descripcion,
                "contenido": texto,
            }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Error al acceder a {url}: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Error procesando página: {e}"}
