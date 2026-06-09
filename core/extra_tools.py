"""
extra_tools.py — Herramientas adicionales 100% gratuitas para Raymundo.

Sin tarjeta de crédito, sin cuentas de pago:

  WeatherClient   — Open-Meteo         (sin API key, 10 000 req/día)
  CryptoClient    — CoinGecko           (sin API key, datos en tiempo real)
  QRGenerator     — qrcode[pil]         (librería Python local, sin API)
  ImageGenerator  — Pollinations.ai     (sin API key, imágenes IA gratis)
  NasaClient      — NASA APOD / NeoWs   (DEMO_KEY incluido, API key opcional)
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

# ───────────────────────────────────────────────────────────────
# WEATHER — Open-Meteo (https://open-meteo.com)
# ───────────────────────────────────────────────────────────────

# Coordenadas precargadas para ciudades comunes (evita llamada de geocoding)
_CIUDAD_COORDS: dict[str, tuple[float, float, str]] = {
    "ciudad de mexico": (19.4326, -99.1332, "Ciudad de México, México"),
    "cdmx":             (19.4326, -99.1332, "Ciudad de México, México"),
    "monterrey":        (25.6866, -100.3161, "Monterrey, México"),
    "guadalajara":      (20.6597, -103.3496, "Guadalajara, México"),
    "puebla":           (19.0414, -98.2063, "Puebla, México"),
    "tijuana":          (32.5149, -117.0382, "Tijuana, México"),
    "leon":             (21.1221, -101.6824, "León, México"),
    "juarez":           (31.7333, -106.4833, "Ciudad Juárez, México"),
    "cancun":           (21.1619, -86.8515, "Cancún, México"),
    "merida":           (20.9674, -89.5926, "Mérida, México"),
    "queretaro":        (20.5888, -100.3899, "Querétaro, México"),
    "nueva york":       (40.7128, -74.0060,  "Nueva York, EE.UU."),
    "new york":         (40.7128, -74.0060,  "Nueva York, EE.UU."),
    "los angeles":      (34.0522, -118.2437, "Los Ángeles, EE.UU."),
    "miami":            (25.7617, -80.1918,  "Miami, EE.UU."),
    "madrid":           (40.4168, -3.7038,   "Madrid, España"),
    "barcelona":        (41.3851, 2.1734,    "Barcelona, España"),
    "bogota":           (4.7110,  -74.0721,  "Bogotá, Colombia"),
    "buenos aires":     (-34.6037, -58.3816, "Buenos Aires, Argentina"),
    "lima":             (-12.0464, -77.0428, "Lima, Perú"),
    "santiago":         (-33.4489, -70.6693, "Santiago, Chile"),
    "tokyo":            (35.6762, 139.6503,  "Tokio, Japón"),
    "paris":            (48.8566, 2.3522,    "París, Francia"),
    "london":           (51.5074, -0.1278,   "Londres, Reino Unido"),
    "Londres":          (51.5074, -0.1278,   "Londres, Reino Unido"),
}

_WMO_CODES: dict[int, str] = {
    0:  "☀️ Despejado",
    1:  "🌤️ Mayormente despejado",
    2:  "⛅ Parcialmente nublado",
    3:  "☁️ Nublado",
    45: "🌫️ Neblina",
    48: "🌫️ Niebla escarchada",
    51: "🌦️ Llovizna ligera",
    53: "🌦️ Llovizna moderada",
    55: "🌧️ Llovizna intensa",
    61: "🌧️ Lluvia ligera",
    63: "🌧️ Lluvia moderada",
    65: "🌧️ Lluvia fuerte",
    71: "❄️ Nieve ligera",
    73: "❄️ Nieve moderada",
    75: "❄️ Nieve intensa",
    80: "🌦️ Chubascos ligeros",
    81: "🌧️ Chubascos moderados",
    82: "⛈️ Chubascos fuertes",
    95: "⛈️ Tormenta",
    96: "⛈️ Tormenta con granizo",
    99: "⛈️ Tormenta con granizo intenso",
}


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


class WeatherClient:
    """Consulta el clima con Open-Meteo — completamente gratis, sin API key."""

    _BASE_GEO = "https://geocoding-api.open-meteo.com/v1/search"
    _BASE_WX  = "https://api.open-meteo.com/v1/forecast"

    def _geocode(self, ciudad: str) -> tuple[float, float, str] | None:
        key = _strip_accents(ciudad.lower().strip())
        for k, v in _CIUDAD_COORDS.items():
            if _strip_accents(k) == key:
                return v
        # Geocoding API de Open-Meteo
        try:
            url = (
                f"{self._BASE_GEO}?name={urllib.parse.quote(ciudad)}"
                "&count=1&language=es&format=json"
            )
            with urllib.request.urlopen(url, timeout=6) as r:
                data = json.loads(r.read())
            results = data.get("results", [])
            if not results:
                return None
            res = results[0]
            nombre = f"{res.get('name', '')}, {res.get('country', '')}"
            return res["latitude"], res["longitude"], nombre
        except Exception:
            return None

    def get_current(self, ciudad: str) -> str:
        coords = self._geocode(ciudad)
        if not coords:
            return (
                f"❌ No encontré la ciudad **{ciudad}**.\n"
                "Prueba con el nombre completo, por ejemplo: *¿Cómo está el clima en Monterrey?*"
            )
        lat, lon, nombre_ciudad = coords
        try:
            url = (
                f"{self._BASE_WX}?latitude={lat}&longitude={lon}"
                "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m,precipitation_probability"
                "&hourly=temperature_2m,precipitation_probability"
                "&forecast_days=1&timezone=auto"
            )
            with urllib.request.urlopen(url, timeout=8) as r:
                d = json.loads(r.read())

            cur        = d.get("current", {})
            temp       = cur.get("temperature_2m", "?")
            sensacion  = cur.get("apparent_temperature", "?")
            humedad    = cur.get("relative_humidity_2m", "?")
            viento     = cur.get("wind_speed_10m", "?")
            wcode      = cur.get("weather_code", 0)
            precip_pct = cur.get("precipitation_probability", 0)
            condicion  = _WMO_CODES.get(wcode, "⛅ Variable")

            temps_h  = d.get("hourly", {}).get("temperature_2m", [])[:12]
            precip_h = d.get("hourly", {}).get("precipitation_probability", [])[:12]
            max_t    = max(temps_h) if temps_h else "?"
            min_t    = min(temps_h) if temps_h else "?"
            max_lluvia = max(precip_h) if precip_h else 0

            lluvia_aviso = ""
            if max_lluvia > 60:
                lluvia_aviso = f"\n☔ **Alta probabilidad de lluvia** ({max_lluvia}%) en las próximas horas"
            elif max_lluvia > 30:
                lluvia_aviso = f"\n🌂 Posible lluvia ({max_lluvia}%) — lleva paraguas"

            return (
                f"🌍 **Clima en {nombre_ciudad}**\n\n"
                f"{condicion}\n"
                f"🌡️ Temperatura: **{temp}°C** (sensación {sensacion}°C)\n"
                f"📈 Máx {max_t}°C / Mín {min_t}°C hoy\n"
                f"💧 Humedad: {humedad}%\n"
                f"💨 Viento: {viento} km/h\n"
                f"🌧️ Prob. lluvia ahora: {precip_pct}%"
                f"{lluvia_aviso}\n\n"
                f"_(Fuente: Open-Meteo — sin API key)_"
            )
        except Exception as e:
            return f"❌ Error consultando el clima: {e}"


# ───────────────────────────────────────────────────────────────
# CRYPTO — CoinGecko (https://www.coingecko.com/api)
# ───────────────────────────────────────────────────────────────

_CRYPTO_ALIASES: dict[str, str] = {
    "bitcoin":      "bitcoin",   "btc":  "bitcoin",
    "ethereum":     "ethereum",  "eth":  "ethereum",
    "solana":       "solana",    "sol":  "solana",
    "cardano":      "cardano",   "ada":  "cardano",
    "xrp":          "ripple",    "ripple": "ripple",
    "dogecoin":     "dogecoin",  "doge": "dogecoin",
    "shiba":        "shiba-inu", "shib": "shiba-inu",
    "polkadot":     "polkadot",  "dot":  "polkadot",
    "litecoin":     "litecoin",  "ltc":  "litecoin",
    "avalanche":    "avalanche-2","avax": "avalanche-2",
    "chainlink":    "chainlink", "link": "chainlink",
    "polygon":      "matic-network", "matic": "matic-network",
    "tron":         "tron",      "trx":  "tron",
    "tether":       "tether",    "usdt": "tether",
    "usd coin":     "usd-coin",  "usdc": "usd-coin",
    "binance coin": "binancecoin","bnb": "binancecoin",
    "pepe":         "pepe",
    "sui":          "sui",
}


class CryptoClient:
    """Precios de criptomonedas con CoinGecko — sin API key."""

    _BASE = "https://api.coingecko.com/api/v3"

    def _resolve_id(self, nombre: str) -> str:
        return _CRYPTO_ALIASES.get(nombre.lower().strip(), nombre.lower().strip())

    @staticmethod
    def _fmt_large(n: float) -> str:
        if n >= 1e12:
            return f"${n/1e12:.2f}T"
        if n >= 1e9:
            return f"${n/1e9:.2f}B"
        if n >= 1e6:
            return f"${n/1e6:.2f}M"
        return f"${n:,.0f}"

    def get_price(self, moneda: str) -> str:
        coin_id = self._resolve_id(moneda)
        try:
            url = (
                f"{self._BASE}/simple/price?ids={coin_id}"
                "&vs_currencies=usd,mxn"
                "&include_24hr_change=true"
                "&include_24hr_vol=true"
                "&include_market_cap=true"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Raymundo/4.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())

            if coin_id not in data:
                return (
                    f"❌ No encontré **{moneda}**.\n"
                    "Prueba con el nombre completo: bitcoin, ethereum, solana, etc."
                )
            c = data[coin_id]
            precio_usd = c.get("usd", 0)
            precio_mxn = c.get("mxn", 0)
            cambio_24h = c.get("usd_24h_change", 0) or 0
            vol_24h    = c.get("usd_24h_vol", 0)
            mktcap     = c.get("usd_market_cap", 0)
            flecha     = "📈" if cambio_24h >= 0 else "📉"
            signo      = "+" if cambio_24h >= 0 else ""

            return (
                f"₿ **{moneda.capitalize()}** ({coin_id.upper()})\n\n"
                f"💵 Precio: **${precio_usd:,.4f} USD** ({precio_mxn:,.2f} MXN)\n"
                f"{flecha} Cambio 24h: **{signo}{cambio_24h:.2f}%**\n"
                f"📊 Volumen 24h: {self._fmt_large(vol_24h)}\n"
                f"🏦 Market Cap: {self._fmt_large(mktcap)}\n\n"
                f"_(Fuente: CoinGecko — sin API key)_"
            )
        except Exception as e:
            return f"❌ Error consultando {moneda}: {e}"

    def get_top(self, n: int = 10) -> str:
        try:
            url = (
                f"{self._BASE}/coins/markets"
                "?vs_currency=usd&order=market_cap_desc"
                f"&per_page={min(n, 20)}&page=1"
                "&price_change_percentage=24h"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Raymundo/4.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                coins = json.loads(r.read())

            lines = [f"🏆 **Top {len(coins)} Criptomonedas por Market Cap**\n"]
            for i, c in enumerate(coins, 1):
                change = c.get("price_change_percentage_24h", 0) or 0
                flecha = "📈" if change >= 0 else "📉"
                lines.append(
                    f"{i:>2}. **{c['name']}** ({c['symbol'].upper()}) — "
                    f"${c['current_price']:,.2f} USD  {flecha} {change:+.1f}%"
                )
            lines.append("\n_(Fuente: CoinGecko — sin API key)_")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Error obteniendo el ranking: {e}"


# ───────────────────────────────────────────────────────────────
# QR CODE — librería qrcode (pip install qrcode[pil])
# ───────────────────────────────────────────────────────────────

class QRGenerator:
    """Genera códigos QR como imagen PNG. Solo requiere: pip install qrcode[pil]"""

    _OUTPUT_DIR = Path("output")

    def generate(self, texto: str) -> dict:
        """Genera un QR y lo guarda en output/. Retorna dict con path y mensaje."""
        try:
            import qrcode  # type: ignore  # noqa: F401

            self._OUTPUT_DIR.mkdir(exist_ok=True)
            nombre_archivo = re.sub(r"[^\w\-]", "_", texto[:40])
            path = self._OUTPUT_DIR / f"qr_{nombre_archivo}.png"

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(texto)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#1a1a2e", back_color="white")
            img.save(str(path))

            preview = texto if len(texto) <= 60 else texto[:57] + "..."
            return {
                "success": True,
                "path": str(path.resolve()),
                "texto": (
                    f"✅ **Código QR generado**\n\n"
                    f"📄 Contenido: `{preview}`\n"
                    f"📁 Guardado en: `{path}`"
                ),
            }
        except ImportError:
            return {
                "success": False,
                "path": None,
                "texto": (
                    "❌ Falta la librería QR.\n\n"
                    "Instala con: `pip install qrcode[pil]`"
                ),
            }
        except Exception as e:
            return {"success": False, "path": None, "texto": f"❌ Error generando QR: {e}"}


# ───────────────────────────────────────────────────────────────
# IMAGE GENERATION — Pollinations.ai (sin API key, gratis)
# ───────────────────────────────────────────────────────────────

class ImageGenerator:
    """
    Genera imágenes IA con Pollinations.ai — completamente gratis, sin API key.
    Solo necesita conexión a internet.
    Modelos disponibles: flux (default), turbo, gptimage
    """

    _BASE   = "https://image.pollinations.ai/prompt"
    _OUTPUT = Path("output")

    def generate(self, prompt: str, width: int = 1024, height: int = 768,
                 model: str = "flux") -> dict:
        self._OUTPUT.mkdir(exist_ok=True)
        nombre = re.sub(r"[^\w\-]", "_", prompt[:40])
        path   = self._OUTPUT / f"img_{nombre}.png"
        url    = (
            f"{self._BASE}/{urllib.parse.quote(prompt)}"
            f"?width={width}&height={height}&nologo=true&model={model}&seed=-1"
        )
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Raymundo/4.0", "Accept": "image/*"},
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                content_type = r.headers.get("Content-Type", "")
                if "image" not in content_type:
                    return {
                        "success": False,
                        "path": None,
                        "texto": "❌ La API no devolvió una imagen válida. Intenta con otro prompt.",
                    }
                data = r.read()

            with open(path, "wb") as f:
                f.write(data)

            return {
                "success": True,
                "path": str(path.resolve()),
                "texto": (
                    f"🎨 **Imagen generada con IA**\n\n"
                    f"Prompt: _{prompt}_\n"
                    f"📁 Guardada en: `{path}`\n"
                    f"_(Fuente: Pollinations.ai — sin API key)_"
                ),
            }
        except Exception as e:
            return {
                "success": False,
                "path": None,
                "texto": (
                    f"❌ Error generando imagen: {e}\n\n"
                    "Verifica tu conexión a internet."
                ),
            }


# ───────────────────────────────────────────────────────────────
# NASA — APOD & Near Earth Objects (API key gratis opcional)
# ───────────────────────────────────────────────────────────────

class NasaClient:
    """
    Consulta la API pública de NASA.
    Sin configurar NASA_API_KEY usa DEMO_KEY (30 req/hora, 50/día).
    API key gratis en: https://api.nasa.gov  (1000 req/hora)
    """

    _BASE   = "https://api.nasa.gov"
    _OUTPUT = Path("output")

    def __init__(self) -> None:
        self.api_key = os.environ.get("NASA_API_KEY", "DEMO_KEY")

    def apod(self) -> dict:
        """Astronomic Picture of the Day."""
        url = f"{self._BASE}/planetary/apod?api_key={self.api_key}&thumbs=true"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Raymundo/4.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read())

            titulo      = data.get("title", "Sin título")
            explicacion = data.get("explanation", "")[:600]
            fecha       = data.get("date", "")
            media_type  = data.get("media_type", "image")
            url_img     = (
                data.get("url", "")
                if media_type == "image"
                else data.get("thumbnail_url", "")
            )

            texto = (
                f"🔭 **NASA — Foto Astronómica del Día**\n\n"
                f"📌 **{titulo}**\n"
                f"📅 {fecha}\n\n"
                f"_{explicacion}..._\n\n"
            )

            img_path: str | None = None
            if url_img:
                self._OUTPUT.mkdir(exist_ok=True)
                path = self._OUTPUT / "nasa_apod.jpg"
                try:
                    req_img = urllib.request.Request(
                        url_img, headers={"User-Agent": "Raymundo/4.0"}
                    )
                    with urllib.request.urlopen(req_img, timeout=30) as r:
                        with open(path, "wb") as f:
                            f.write(r.read())
                    img_path = str(path.resolve())
                    texto += f"📁 Imagen guardada en: `output/nasa_apod.jpg`"
                except Exception:
                    texto += f"🔗 Ver imagen: {url_img}"

            return {"success": True, "path": img_path, "texto": texto}
        except Exception as e:
            return {"success": False, "path": None, "texto": f"❌ Error consultando NASA API: {e}"}

    def neo(self) -> str:
        """Near Earth Objects — asteroides cercanos hoy."""
        import datetime
        today = datetime.date.today().isoformat()
        url = (
            f"{self._BASE}/neo/rest/v1/feed"
            f"?start_date={today}&end_date={today}&api_key={self.api_key}"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Raymundo/4.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read())

            neos = data.get("near_earth_objects", {}).get(today, [])
            if not neos:
                return "🌌 No hay asteroides cercanos registrados para hoy."

            peligrosos = [n for n in neos if n.get("is_potentially_hazardous_asteroid")]
            texto = (
                f"☄️ **Asteroides cercanos a la Tierra hoy ({today})**\n\n"
                f"Total detectados: {len(neos)} | ⚠️ Potencialmente peligrosos: {len(peligrosos)}\n\n"
            )

            def _dist_km(n):
                try:
                    return float(
                        n["close_approach_data"][0]["miss_distance"]["kilometers"]
                    )
                except Exception:
                    return 9e15

            for n in sorted(neos, key=_dist_km)[:5]:
                nombre    = n.get("name", "Desconocido")
                peligro   = " ⚠️ PELIGROSO" if n.get("is_potentially_hazardous_asteroid") else ""
                dist_km   = _dist_km(n)
                dist_fmt  = f"{dist_km:,.0f} km" if dist_km < 9e14 else "?"
                diam      = n.get("estimated_diameter", {}).get("meters", {})
                diam_min  = diam.get("estimated_diameter_min", 0)
                diam_max  = diam.get("estimated_diameter_max", 0)
                texto += f"• **{nombre}**{peligro}\n"
                texto += f"  Distancia: {dist_fmt} | Diámetro: {diam_min:.0f}–{diam_max:.0f} m\n"

            texto += "\n_(Fuente: NASA NeoWs API)_"
            return texto
        except Exception as e:
            return f"❌ Error consultando asteroides: {e}"


# ───────────────────────────────────────────────────────────────
# COMFYUI — Generación de imágenes local con Stable Diffusion
# ───────────────────────────────────────────────────────────────

class ComfyUIClient:
    """
    Genera imágenes con ComfyUI local (http://127.0.0.1:8188 por defecto).
    Requiere ComfyUI corriendo y al menos un checkpoint instalado.
    Compatible con cualquier modelo SD 1.5 / SDXL / Flux instalado en ComfyUI.
    """

    _OUTPUT = Path("output")

    def __init__(self, host: str = None):
        import os
        self._host = (host or os.environ.get("COMFYUI_HOST", "http://127.0.0.1:8188")).rstrip("/")

    def is_available(self) -> bool:
        """Verifica si el servidor ComfyUI está corriendo."""
        try:
            req = urllib.request.Request(
                f"{self._host}/system_stats",
                headers={"User-Agent": "RAIGPT/4.0"},
            )
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            return False

    def get_checkpoints(self) -> list:
        """Lista los checkpoints disponibles en ComfyUI."""
        try:
            req = urllib.request.Request(
                f"{self._host}/object_info/CheckpointLoaderSimple",
                headers={"User-Agent": "RAIGPT/4.0"},
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
            return (
                data.get("CheckpointLoaderSimple", {})
                .get("input", {})
                .get("required", {})
                .get("ckpt_name", [[]])[0]
            )
        except Exception:
            return []

    def _build_workflow(self, prompt: str, neg_prompt: str, checkpoint: str,
                        width: int, height: int, steps: int, cfg: float) -> dict:
        import random
        seed = random.randint(0, 2 ** 32 - 1)
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": cfg,
                    "denoise": 1.0,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "karras",
                    "seed": seed,
                    "steps": steps,
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": checkpoint},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"batch_size": 1, "height": height, "width": width},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": prompt},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": neg_prompt},
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "raigpt", "images": ["8", 0]},
            },
        }

    def generate(self, prompt: str,
                 neg_prompt: str = "ugly, blurry, low quality, deformed, watermark",
                 width: int = 512, height: int = 512,
                 steps: int = 20, cfg: float = 7.0) -> dict:
        """Genera una imagen y la devuelve como ruta local."""
        self._OUTPUT.mkdir(exist_ok=True)

        if not self.is_available():
            return {
                "success": False,
                "path": None,
                "texto": (
                    "❌ **ComfyUI no está corriendo**\n\n"
                    "Para usarlo:\n"
                    "1. Inicia ComfyUI (doble clic en `run_nvidia_gpu.bat` o similar)\n"
                    "2. Espera a que abra en `http://127.0.0.1:8188`\n"
                    "3. Vuelve a intentarlo\n\n"
                    "_(Alternativa sin instalar nada: *Genera una imagen de ...* usa Pollinations.ai)_"
                ),
            }

        checkpoints = self.get_checkpoints()
        if not checkpoints:
            return {
                "success": False,
                "path": None,
                "texto": (
                    "❌ No se encontraron checkpoints en ComfyUI.\n\n"
                    "Descarga un modelo `.safetensors` y colócalo en la carpeta "
                    "`ComfyUI/models/checkpoints/`."
                ),
            }

        checkpoint = checkpoints[0]
        workflow   = self._build_workflow(prompt, neg_prompt, checkpoint, width, height, steps, cfg)

        # Enviar tarea
        payload = json.dumps({"prompt": workflow}).encode("utf-8")
        req_post = urllib.request.Request(
            f"{self._host}/prompt",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "RAIGPT/4.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req_post, timeout=10) as r:
                result = json.loads(r.read())
        except Exception as e:
            return {"success": False, "path": None, "texto": f"❌ Error enviando tarea a ComfyUI: {e}"}

        prompt_id = result.get("prompt_id")
        if not prompt_id:
            return {"success": False, "path": None, "texto": "❌ ComfyUI no devolvió un ID de tarea."}

        # Esperar resultado (polling, máx 3 min)
        import time
        for _ in range(180):
            time.sleep(1)
            try:
                req_h = urllib.request.Request(
                    f"{self._host}/history/{prompt_id}",
                    headers={"User-Agent": "RAIGPT/4.0"},
                )
                with urllib.request.urlopen(req_h, timeout=5) as r:
                    history = json.loads(r.read())
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_output in outputs.values():
                        images = node_output.get("images", [])
                        if images:
                            img_info  = images[0]
                            filename  = img_info["filename"]
                            subfolder = img_info.get("subfolder", "")
                            img_type  = img_info.get("type", "output")
                            view_url  = (
                                f"{self._host}/view"
                                f"?filename={urllib.parse.quote(filename)}"
                                f"&subfolder={urllib.parse.quote(subfolder)}"
                                f"&type={img_type}"
                            )
                            out_path = self._OUTPUT / filename
                            req_img = urllib.request.Request(
                                view_url, headers={"User-Agent": "RAIGPT/4.0"}
                            )
                            with urllib.request.urlopen(req_img, timeout=30) as r:
                                with open(out_path, "wb") as f:
                                    f.write(r.read())
                            return {
                                "success": True,
                                "path": str(out_path.resolve()),
                                "texto": (
                                    f"🎭 **Imagen generada con ComfyUI**\n\n"
                                    f"Prompt: _{prompt}_\n"
                                    f"Checkpoint: `{checkpoint}`\n"
                                    f"📁 Guardada en: `output/{filename}`\n"
                                    f"_(Resolución: {width}×{height} | Pasos: {steps})_"
                                ),
                            }
            except Exception:
                continue

        return {
            "success": False,
            "path": None,
            "texto": (
                "⏱️ ComfyUI tardó demasiado en generar la imagen.\n\n"
                "Prueba con menos pasos o una resolución más pequeña."
            ),
        }
