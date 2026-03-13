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
import re
import time
import unicodedata
from collections import deque
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)

_TOKEN_PATH = Path(__file__).resolve().parent.parent / "data" / "spotify_token.json"

# ──────────────────────────────────────────────────────────────
# Detección de intents de Spotify (compartida entre server y voice)
# ──────────────────────────────────────────────────────────────
_PLAY_RE = re.compile(
    r"^(?:pon(?:me)?|reproduce|toca|play|"
    r"quiero\s+(?:escuchar|o[ií]r)|"
    r"pon(?:me)?\s+(?:la\s+)?(?:canci[oó]n|rola|pista))\s+(.+)",
    re.IGNORECASE,
)
_SUFFIX_RE = re.compile(
    r"\s+en\s+(?:spotify|apple\s+music|youtube\s+music|deezer|tidal)\s*$",
    re.IGNORECASE,
)


def detect_spotify_intent(t: str) -> tuple[str | None, str]:
    """
    Detecta si un texto (en minúsculas, strip) es un comando de Spotify.
    Devuelve (intent, query) o (None, "").
    """
    # Pausa
    if re.search(
        r"\b(pausa|pause|para\s+la\s+m[uú]sica|det[eé]n\s+la\s+m[uú]sica|"
        r"stop\s+music|deja\s+de\s+tocar|calla\s+la\s+m[uú]sica)\b", t
    ):
        return ("pause", "")

    # Reanudar
    if re.fullmatch(
        r"(?:play|dale\s+play|reanuda|contin[uú]a|sigue\s+tocando|resume)", t
    ):
        return ("play", "")

    # Siguiente
    if re.search(r"\b(siguiente(?:\s+canci[oó]n)?|next|skip|salta)\b", t):
        return ("next", "")

    # Anterior
    if re.search(r"\b(anterior(?:\s+canci[oó]n)?|previous|atr[aá]s|regresa)\b", t):
        return ("previous", "")

    # Qué suena
    if re.search(
        r"\b(qu[eé]\s+su[eé]na|qu[eé]\s+est[aá]\s+sonando|what.s\s+playing|"
        r"qu[eé]\s+canci[oó]n\s+(?:es|suena)|qu[eé]\s+estoy\s+escuchando)\b", t
    ):
        return ("current", "")

    # Reproducir algo con query
    m = _PLAY_RE.match(t)
    if m:
        query = m.group(1).strip()
        query = _SUFFIX_RE.sub("", query).strip()
        if query:
            return ("play", query)

    return (None, "")


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

    # Regex para detectar "canción DE artista" en el query
    _DE_ARTIST_RE = re.compile(
        r"^(.+?)\s+(?:de|by|of)\s+(.+)$", re.IGNORECASE
    )

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

        # Contexto de escucha reciente (últimos 5 artistas)
        self._recent_artists: deque[str] = deque(maxlen=5)

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
            self._load_recent_context()

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
            self._load_recent_context()
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
                self._remember_artist(artist)
                return f"🎵 Reproduciendo: **{nombre}** — {artist}"
            elif tipo == "album":
                sp.start_playback(context_uri=uri, device_id=device_id)
                artist = result.get("artist", "")
                self._remember_artist(artist)
                return f"💿 Reproduciendo álbum: **{nombre}** — {artist}"
            elif tipo == "playlist":
                sp.start_playback(context_uri=uri, device_id=device_id)
                return f"📋 Reproduciendo playlist: **{nombre}**"
            elif tipo == "artist":
                sp.start_playback(context_uri=uri, device_id=device_id)
                self._remember_artist(nombre)
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
        time.sleep(0.5)
        self._update_context_from_playback()
        current = self.current_track()
        return f"⏭️ Siguiente canción\n{current}"

    def previous_track(self) -> str:
        sp = self._ensure_auth()
        sp.previous_track()
        time.sleep(0.5)
        self._update_context_from_playback()
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

    # ─── Búsqueda de playlists ──────────────────────────────

    def _search_playlist(self, query: str) -> dict | None:
        """
        Busca playlist: primero en las del usuario, luego global.
        Prioriza coincidencia exacta del nombre.
        """
        sp = self._ensure_auth()

        # Limpiar query: quitar "la playlist", "playlist de", etc.
        clean = self._PLAYLIST_PREFIX_RE.sub("", query).strip()
        if not clean:
            clean = query
        q = self._normalize(clean)
        logger.debug(f"🔍 Playlist search: query='{clean}' (normalized='{q}')")

        # 1. Buscar en playlists del usuario (propias + guardadas)
        user_playlists = []
        try:
            offset = 0
            while offset < 200:  # Máximo 200 playlists del usuario
                batch = sp.current_user_playlists(limit=50, offset=offset)
                items = batch.get("items", [])
                if not items:
                    break
                user_playlists.extend(items)
                offset += 50
                if not batch.get("next"):
                    break
        except Exception as e:
            logger.warning(f"⚠️ No se pudieron cargar playlists del usuario: {e}")

        # Buscar match en playlists del usuario
        if user_playlists:
            best_user = self._best_name_match(clean, user_playlists)
            user_score = self._name_score(q, self._normalize(best_user["name"]))
            logger.debug(f"📋 Mejor playlist del usuario: '{best_user['name']}' "
                          f"(score={user_score:.1f})")
            # Si hay match razonable (>= 40), usar la del usuario
            if user_score >= 40:
                return {"type": "playlist", "uri": best_user["uri"], "name": best_user["name"]}

        # 2. Buscar en Spotify global
        results = sp.search(q=clean, limit=20, type="playlist")
        global_playlists = results.get("playlists", {}).get("items", [])

        if global_playlists:
            best_global = self._best_name_match(clean, global_playlists)
            global_score = self._name_score(q, self._normalize(best_global["name"]))
            logger.debug(f"🌐 Mejor playlist global: '{best_global['name']}' "
                          f"(score={global_score:.1f})")

            # Comparar: si el usuario tiene una buena y la global es mejor, elegir la mejor
            if user_playlists and user_score >= 40:
                # Bonus de +10 para playlists propias (preferir las del usuario)
                if user_score + 10 >= global_score:
                    return {"type": "playlist", "uri": best_user["uri"],
                            "name": best_user["name"]}
            return {"type": "playlist", "uri": best_global["uri"],
                    "name": best_global["name"]}

        # 3. Si global no encontró nada pero el usuario tiene algo
        if user_playlists:
            return {"type": "playlist", "uri": best_user["uri"], "name": best_user["name"]}

        return None

    def _best_name_match(self, query: str, items: list) -> dict:
        """Elige el item con nombre más cercano al query."""
        q = self._normalize(query)
        return max(items, key=lambda item: self._name_score(q, self._normalize(item["name"])))

    @staticmethod
    def _name_score(q: str, name: str) -> float:
        """
        Scoring de similitud entre query y nombre de playlist/album.
        Maneja nombres parciales, emojis, y prefijos como 'This Is'.
        """
        # Limpiar emojis y caracteres especiales para comparación
        import re as _re
        emoji_re = _re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
            "\U0001F900-\U0001F9FF\U00002702-\U000027B0\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF\U00002600-\U000026FF]+", flags=_re.UNICODE
        )
        name_clean = emoji_re.sub("", name).strip()
        q_clean = emoji_re.sub("", q).strip()

        pts = 0.0

        # Coincidencia exacta
        if name_clean == q_clean:
            return 100.0

        # Coincidencia sin emojis/extras
        if q_clean and name_clean and (
            q_clean in name_clean or name_clean in q_clean
        ):
            # Ratio de cobertura: qué tanto del nombre cubre el query
            overlap = len(q_clean) / max(len(name_clean), 1)
            pts = 40 + (overlap * 40)  # 40-80 pts

        # Si empieza igual
        if name_clean.startswith(q_clean) or q_clean.startswith(name_clean):
            pts = max(pts, 70)

        # Bonus por palabras en común
        q_words = set(q_clean.split())
        name_words = set(name_clean.split())
        common = q_words & name_words
        if q_words and common:
            word_ratio = len(common) / len(q_words)
            pts = max(pts, 30 + word_ratio * 50)  # 30-80

        return pts

    # ─── Búsqueda inteligente (contexto artistas) ─────────────

    def _remember_artist(self, artist_str: str):
        """Guarda artistas recientes para contexto de búsqueda."""
        if not artist_str:
            return
        for a in artist_str.split(","):
            name = a.strip()
            if name:
                normalized = self._normalize(name)
                self._recent_artists = deque(
                    [x for x in self._recent_artists if self._normalize(x) != normalized],
                    maxlen=5,
                )
                self._recent_artists.appendleft(name)

    def _update_context_from_playback(self):
        """Lee lo que está sonando y actualiza el contexto de artistas."""
        try:
            sp = self._ensure_auth()
            data = sp.current_playback()
            if data and data.get("item"):
                artists = ", ".join(a["name"] for a in data["item"]["artists"])
                self._remember_artist(artists)
        except Exception:
            pass

    def _load_recent_context(self):
        """Carga artistas de las últimas canciones para tener contexto al iniciar."""
        try:
            sp = self._ensure_auth()
            recent = sp.current_user_recently_played(limit=5)
            for item in reversed(recent.get("items", [])):
                track = item.get("track", {})
                artists = ", ".join(a["name"] for a in track.get("artists", []))
                self._remember_artist(artists)
            if self._recent_artists:
                logger.debug(f"📝 Contexto Spotify cargado: {list(self._recent_artists)}")
        except Exception as e:
            logger.debug(f"No se pudo cargar contexto reciente de Spotify: {e}")

    def _parse_artist_hint(self, query: str) -> tuple[str, str | None]:
        """
        Detecta si el query incluye artista explícito.
        'el malo de aventura' → ('el malo', 'aventura')
        'mojabi ghost'        → ('mojabi ghost', None)
        """
        m = self._DE_ARTIST_RE.match(query)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return query, None

    # Regex para limpiar prefijos de playlist del query
    _PLAYLIST_PREFIX_RE = re.compile(
        r"^(?:la\s+)?(?:playlist|lista)\s+(?:de\s+)?",
        re.IGNORECASE,
    )

    def _smart_search(self, query: str) -> dict | None:
        """
        Busca inteligentemente en Spotify usando contexto de escucha reciente.
        1. Detecta intención (playlist/album/track)
        2. Para playlists: busca en las del usuario primero, luego global
        3. Para tracks: usa contexto de artistas recientes
        """
        sp = self._ensure_auth()
        q_lower = query.lower()

        # ─── Playlist ────────────────────────────────────────
        if any(kw in q_lower for kw in ["playlist", "lista"]):
            return self._search_playlist(query) or None

        # ─── Album ────────────────────────────────────────────
        if any(kw in q_lower for kw in ["album", "disco", "álbum"]):
            clean = re.sub(r"\b(?:album|disco|álbum)\b", "", query, flags=re.IGNORECASE).strip()
            results = sp.search(q=clean or query, limit=10, type="album")
            items = results.get("albums", {}).get("items", [])
            if items:
                best = self._best_name_match(clean or query, items)
                artist = ", ".join(a["name"] for a in best["artists"])
                return {"type": "album", "uri": best["uri"], "name": best["name"], "artist": artist}

        # ─── Búsqueda de track con contexto ───────────────────

        song_query, artist_hint = self._parse_artist_hint(query)
        logger.debug(f"🔍 Spotify: song='{song_query}', artist_hint='{artist_hint}', "
                      f"recent={list(self._recent_artists)}")

        # Estrategia de búsqueda:
        # 1. Si hay artista explícito ("el malo de aventura") → buscar "el malo artist:aventura"
        # 2. Si no hay artista pero hay contexto reciente → buscar con y sin artista, combinar
        # 3. Si no hay nada → búsqueda simple

        all_tracks = []

        if artist_hint:
            # Búsqueda focalizada: "canción" + artist:artista
            results = sp.search(q=f"{song_query} artist:{artist_hint}", limit=10, type="track")
            all_tracks.extend(results.get("tracks", {}).get("items", []))
            # También buscar sin filtro por si el artist:X no da resultados exactos
            results = sp.search(q=f"{song_query} {artist_hint}", limit=5, type="track")
            for t in results.get("tracks", {}).get("items", []):
                if t["uri"] not in {x["uri"] for x in all_tracks}:
                    all_tracks.append(t)
        else:
            # Búsqueda base
            results = sp.search(q=query, limit=10, type="track")
            all_tracks.extend(results.get("tracks", {}).get("items", []))

            # Si hay artistas recientes y el query es corto/genérico,
            # hacer búsqueda contextual con cada artista reciente
            if self._recent_artists and len(query.split()) <= 4:
                seen_uris = {t["uri"] for t in all_tracks}
                for recent_artist in list(self._recent_artists)[:3]:
                    results = sp.search(
                        q=f"{query} artist:{recent_artist}", limit=3, type="track"
                    )
                    for t in results.get("tracks", {}).get("items", []):
                        if t["uri"] not in seen_uris:
                            all_tracks.append(t)
                            seen_uris.add(t["uri"])

        if all_tracks:
            best = self._best_track_match(song_query, all_tracks, artist_hint)
            artist = ", ".join(a["name"] for a in best["artists"])
            return {"type": "track", "uri": best["uri"], "name": best["name"], "artist": artist}

        # Si no hay canción, buscar artista
        results = sp.search(q=query, limit=1, type="artist")
        artists = results.get("artists", {}).get("items", [])
        if artists:
            return {"type": "artist", "uri": artists[0]["uri"], "name": artists[0]["name"]}

        return None

    def _best_track_match(self, query: str, tracks: list,
                          artist_hint: str | None = None) -> dict:
        """
        Elige el mejor track con scoring multi-criterio:
          - Coincidencia de nombre con el query
          - Coincidencia de artista con el hint explícito
          - Coincidencia de artista con contexto reciente
          - Popularidad de Spotify como desempate
        """
        q = self._normalize(query)
        hint_n = self._normalize(artist_hint) if artist_hint else None
        recent_n = [self._normalize(a) for a in self._recent_artists]

        def score(t):
            name = self._normalize(t["name"])
            track_artists = [self._normalize(a["name"]) for a in t["artists"]]
            popularity = t.get("popularity", 0)  # 0-100

            pts = 0.0

            # ── Nombre (max 40 pts) ──
            if name == q:
                pts += 40
            elif name.startswith(q) or q.startswith(name):
                pts += 30
            elif q in name or name in q:
                pts += 20

            # ── Artista explícito "de X" (max 35 pts) ──
            if hint_n:
                for ta in track_artists:
                    if hint_n == ta:
                        pts += 35
                        break
                    elif hint_n in ta or ta in hint_n:
                        pts += 25
                        break

            # ── Artista del contexto reciente (max 20 pts, decae) ──
            if not hint_n and recent_n:
                for i, ra in enumerate(recent_n):
                    for ta in track_artists:
                        if ra == ta:
                            pts += 20 - (i * 4)  # 20, 16, 12, 8, 4
                            break
                        elif ra in ta or ta in ra:
                            pts += 15 - (i * 3)  # 15, 12, 9, 6, 3
                            break
                    else:
                        continue
                    break

            # ── Popularidad como desempate (max 5 pts) ──
            pts += (popularity / 100) * 5

            return pts

        best = max(tracks, key=score)
        best_score = score(best)
        best_artists = ", ".join(a["name"] for a in best["artists"])
        logger.debug(f"🎯 Mejor match: '{best['name']}' — {best_artists} "
                      f"(score={best_score:.1f})")
        return best

    @staticmethod
    def _normalize(s: str) -> str:
        """Normaliza texto para comparación: minúsculas, sin acentos."""
        s = s.lower().strip()
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return s

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
