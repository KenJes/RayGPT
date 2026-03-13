"""
spotify_client.py — Cliente de Spotify para Raymundo.

Maneja autenticación OAuth 2.0 y control de reproducción.
Requiere: pip install spotipy

Flujo de autenticación:
    1. El usuario visita /spotify/auth
    2. Se redirige a Spotify para autorizar
    3. Spotify redirige a /spotify/callback con un code
    4. Se intercambia el code por tokens (access + refresh)
    5. Los tokens se guardan en data/spotify_token.json
    6. El refresh_token renueva automáticamente el access_token

Configuración en config_agente.json:
    "spotify": {
        "client_id": "...",
        "client_secret": "...",
        "redirect_uri": "http://localhost:5000/spotify/callback"
    }
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)

_TOKEN_PATH = Path(__file__).resolve().parent.parent / "data" / "spotify_token.json"

# Scopes necesarios para control completo de reproducción
_SCOPES = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
    "user-read-recently-played",
])


class SpotifyClient:
    """Cliente de Spotify con OAuth persistente y control de reproducción."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

        self._oauth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=_SCOPES,
            cache_handler=_FileTokenCache(_TOKEN_PATH),
            open_browser=False,
        )

        self._sp: spotipy.Spotify | None = None
        self._try_load_token()

    # ─── Autenticación ────────────────────────────────────────

    def _try_load_token(self):
        """Intenta cargar token guardado y crear cliente."""
        token_info = self._oauth.cache_handler.get_cached_token()
        if token_info:
            # Renovar si expiró
            if self._oauth.is_token_expired(token_info):
                try:
                    token_info = self._oauth.refresh_access_token(token_info["refresh_token"])
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo renovar token de Spotify: {e}")
                    self._sp = None
                    return
            self._sp = spotipy.Spotify(auth=token_info["access_token"])
            logger.info("✅ Spotify conectado (token cargado)")

    @property
    def is_authenticated(self) -> bool:
        return self._sp is not None

    def get_auth_url(self) -> str:
        """Genera URL para que el usuario autorice la app."""
        return self._oauth.get_authorize_url()

    def handle_callback(self, code: str) -> bool:
        """Procesa el callback de Spotify con el authorization code."""
        try:
            token_info = self._oauth.get_access_token(code, as_dict=True)
            self._sp = spotipy.Spotify(auth=token_info["access_token"])
            logger.info("✅ Spotify autenticado exitosamente")
            return True
        except Exception as e:
            logger.error(f"❌ Error autenticando Spotify: {e}")
            return False

    def _ensure_auth(self) -> spotipy.Spotify:
        """Verifica autenticación y renueva token si es necesario."""
        if not self._sp:
            raise RuntimeError("Spotify no está autenticado. Visita /spotify/auth")
        # Verificar si el token expiró
        token_info = self._oauth.cache_handler.get_cached_token()
        if token_info and self._oauth.is_token_expired(token_info):
            token_info = self._oauth.refresh_access_token(token_info["refresh_token"])
            self._sp = spotipy.Spotify(auth=token_info["access_token"])
        return self._sp

    # ─── Reproducción ─────────────────────────────────────────

    def play(self, query: str | None = None, device_id: str | None = None) -> str:
        """
        Reproduce música. Si hay query, busca y reproduce.
        Si no hay query, reanuda la reproducción actual.
        """
        sp = self._ensure_auth()

        if query:
            # Buscar la canción/album/artista
            result = self._smart_search(query)
            if not result:
                return f"❌ No encontré '{query}' en Spotify"

            tipo = result["type"]
            uri = result["uri"]
            nombre = result["name"]

            if tipo == "track":
                sp.start_playback(uris=[uri], device_id=device_id)
                artist = result.get("artist", "")
                return f"🎵 Reproduciendo: **{nombre}** — {artist}"
            elif tipo == "album":
                sp.start_playback(context_uri=uri, device_id=device_id)
                artist = result.get("artist", "")
                return f"💿 Reproduciendo álbum: **{nombre}** — {artist}"
            elif tipo == "playlist":
                sp.start_playback(context_uri=uri, device_id=device_id)
                return f"📋 Reproduciendo playlist: **{nombre}**"
            elif tipo == "artist":
                sp.start_playback(context_uri=uri, device_id=device_id)
                return f"🎤 Reproduciendo: **{nombre}** (Top canciones)"
        else:
            sp.start_playback(device_id=device_id)
            return "▶️ Reproducción reanudada"

    def pause(self) -> str:
        sp = self._ensure_auth()
        sp.pause_playback()
        return "⏸️ Música pausada"

    def next_track(self) -> str:
        sp = self._ensure_auth()
        sp.next_track()
        # Esperar un momento para que Spotify actualice
        time.sleep(0.5)
        current = self.current_track()
        return f"⏭️ Siguiente canción\n{current}"

    def previous_track(self) -> str:
        sp = self._ensure_auth()
        sp.previous_track()
        time.sleep(0.5)
        current = self.current_track()
        return f"⏮️ Canción anterior\n{current}"

    def current_track(self) -> str:
        sp = self._ensure_auth()
        data = sp.current_playback()
        if not data or not data.get("item"):
            return "🔇 No hay nada reproduciéndose"

        track = data["item"]
        nombre = track["name"]
        artistas = ", ".join(a["name"] for a in track["artists"])
        album = track["album"]["name"]
        progreso_ms = data.get("progress_ms", 0)
        duracion_ms = track.get("duration_ms", 0)
        is_playing = data.get("is_playing", False)

        progreso = self._ms_to_time(progreso_ms)
        duracion = self._ms_to_time(duracion_ms)
        estado = "▶️" if is_playing else "⏸️"

        return (
            f"{estado} **{nombre}**\n"
            f"🎤 {artistas}\n"
            f"💿 {album}\n"
            f"⏱️ {progreso} / {duracion}"
        )

    def set_volume(self, volume: int) -> str:
        sp = self._ensure_auth()
        volume = max(0, min(100, volume))
        sp.volume(volume)
        bars = "█" * (volume // 10) + "░" * (10 - volume // 10)
        return f"🔊 Volumen: {volume}% [{bars}]"

    def add_to_queue(self, query: str) -> str:
        sp = self._ensure_auth()
        result = self._smart_search(query)
        if not result or result["type"] != "track":
            return f"❌ No encontré la canción '{query}'"
        sp.add_to_queue(result["uri"])
        return f"➕ Agregado a la cola: **{result['name']}** — {result.get('artist', '')}"

    def shuffle(self, state: bool = True) -> str:
        sp = self._ensure_auth()
        sp.shuffle(state)
        return f"🔀 Shuffle {'activado' if state else 'desactivado'}"

    def repeat(self, mode: str = "track") -> str:
        """mode: 'track', 'context' (album/playlist), 'off'"""
        sp = self._ensure_auth()
        sp.repeat(mode)
        labels = {"track": "🔂 Repitiendo canción", "context": "🔁 Repitiendo album/playlist", "off": "➡️ Repetición desactivada"}
        return labels.get(mode, f"Repetición: {mode}")

    def get_devices(self) -> str:
        sp = self._ensure_auth()
        devices = sp.devices()
        if not devices or not devices.get("devices"):
            return "❌ No hay dispositivos activos. Abre Spotify en algún dispositivo."
        lines = ["📱 **Dispositivos disponibles:**"]
        for d in devices["devices"]:
            active = " ✅" if d["is_active"] else ""
            lines.append(f"  • {d['name']} ({d['type']}){active}")
        return "\n".join(lines)

    def search(self, query: str, limit: int = 5) -> str:
        """Búsqueda general en Spotify, devuelve resultados formateados."""
        sp = self._ensure_auth()
        results = sp.search(q=query, limit=limit, type="track,artist,album,playlist")
        lines = [f"🔍 **Resultados para: '{query}'**\n"]

        tracks = results.get("tracks", {}).get("items", [])
        if tracks:
            lines.append("🎵 **Canciones:**")
            for i, t in enumerate(tracks[:3], 1):
                artist = ", ".join(a["name"] for a in t["artists"])
                lines.append(f"  {i}. {t['name']} — {artist}")

        artists = results.get("artists", {}).get("items", [])
        if artists:
            lines.append("\n🎤 **Artistas:**")
            for i, a in enumerate(artists[:3], 1):
                lines.append(f"  {i}. {a['name']}")

        albums = results.get("albums", {}).get("items", [])
        if albums:
            lines.append("\n💿 **Álbumes:**")
            for i, al in enumerate(albums[:3], 1):
                artist = ", ".join(a["name"] for a in al["artists"])
                lines.append(f"  {i}. {al['name']} — {artist}")

        return "\n".join(lines) if len(lines) > 1 else f"❌ No encontré resultados para '{query}'"

    # ─── Búsqueda inteligente ─────────────────────────────────

    def _smart_search(self, query: str) -> dict | None:
        """
        Busca inteligentemente en Spotify.
        Detecta si el query pide una canción, artista, album o playlist.
        """
        sp = self._ensure_auth()
        q_lower = query.lower()

        # Detectar intención
        if any(kw in q_lower for kw in ["playlist", "lista"]):
            results = sp.search(q=query, limit=1, type="playlist")
            items = results.get("playlists", {}).get("items", [])
            if items:
                return {"type": "playlist", "uri": items[0]["uri"], "name": items[0]["name"]}

        if any(kw in q_lower for kw in ["album", "disco", "álbum"]):
            results = sp.search(q=query, limit=1, type="album")
            items = results.get("albums", {}).get("items", [])
            if items:
                artist = ", ".join(a["name"] for a in items[0]["artists"])
                return {"type": "album", "uri": items[0]["uri"], "name": items[0]["name"], "artist": artist}

        # Por defecto: buscar canción primero, luego artista
        results = sp.search(q=query, limit=10, type="track")
        tracks = results.get("tracks", {}).get("items", [])
        if tracks:
            best = self._best_track_match(query, tracks)
            artist = ", ".join(a["name"] for a in best["artists"])
            return {"type": "track", "uri": best["uri"], "name": best["name"], "artist": artist}

        # Si no hay canción, buscar artista
        results = sp.search(q=query, limit=1, type="artist")
        artists = results.get("artists", {}).get("items", [])
        if artists:
            return {"type": "artist", "uri": artists[0]["uri"], "name": artists[0]["name"]}

        return None

    @staticmethod
    def _best_track_match(query: str, tracks: list) -> dict:
        """
        De una lista de tracks de Spotify elige el que más se parece al query.
        Prioridad: coincidencia exacta del nombre > empieza igual > contiene query > primero.
        """
        import unicodedata

        def normalize(s: str) -> str:
            s = s.lower().strip()
            s = unicodedata.normalize("NFD", s)
            s = "".join(c for c in s if unicodedata.category(c) != "Mn")
            return s

        q = normalize(query)

        def score(t):
            name = normalize(t["name"])
            if name == q:
                return 4
            if name.startswith(q):
                return 3
            if q.startswith(name):
                return 2
            if q in name:
                return 1
            return 0

        return max(tracks, key=score)

    # ─── Utilidades ───────────────────────────────────────────

    @staticmethod
    def _ms_to_time(ms: int) -> str:
        seconds = ms // 1000
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"


class _FileTokenCache(spotipy.CacheHandler):
    """Almacena tokens de Spotify en un archivo JSON."""

    def __init__(self, path: Path):
        self._path = path

    def get_cached_token(self):
        if self._path.exists():
            try:
                with open(self._path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def save_token_to_cache(self, token_info):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(token_info, f, indent=2)

    def delete_cached_token(self):
        if self._path.exists():
            self._path.unlink()
