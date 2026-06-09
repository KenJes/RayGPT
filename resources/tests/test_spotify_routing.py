"""Quick test: verifica que detect_spotify_intent atrapa comandos de música
antes de que lleguen al detector de calendario."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.spotify_client import detect_spotify_intent

tests = [
    ("pon musica de bad bunny",     "play"),
    ("reproduce algo de reggaeton", "play"),
    ("pon la cancion de shakira",   "play"),
    ("siguiente cancion",           "next"),
    ("pausa la musica",             "pause"),
    ("que suena",                   "current"),
    ("pon musica en spotify",       "play"),
    ("pon concierto de violines en el calendario", None),  # NO debe ser Spotify
]

ok = True
for text, expected in tests:
    intent, query = detect_spotify_intent(text.lower())
    status = "OK" if intent == expected else "FAIL"
    if status == "FAIL":
        ok = False
    print(f"  [{status}] {text!r:45} => intent={intent!r}")

print()
print("RESULTADO:", "TODOS OK ✅" if ok else "HAY FALLOS ❌")
