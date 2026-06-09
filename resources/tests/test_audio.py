"""
Test del sistema de audio de Raymundo
Verifica que TTS y STT funcionen correctamente
"""

import sys
from pathlib import Path

# Agregar raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.audio_handler import get_audio_handler

def test_audio():
    print("\n" + "="*60)
    print("  🎙️ TEST DEL SISTEMA DE AUDIO - RAYMUNDO")
    print("="*60 + "\n")
    
    # Obtener manejador de audio
    handler = get_audio_handler()
    
    # Mostrar estado
    print("📊 ESTADO DEL SISTEMA:")
    status = handler.get_status()
    for key, value in status.items():
        emoji = "✅" if value else "❌"
        if isinstance(value, bool):
            print(f"  {emoji} {key}: {value}")
        else:
            print(f"  📁 {key}: {value}")
    
    print("\n" + "-"*60 + "\n")
    
    # Test TTS
    if handler.is_tts_available():
        print("🔊 TEST 1: TEXT-TO-SPEECH (TTS)")
        print("  Generando audio de prueba...")
        
        texto_prueba = "Hola, soy Raymundo. Este es un test del sistema de audio."
        audio_file = handler.text_to_speech(texto_prueba)
        
        if audio_file:
            print(f"  ✅ Audio generado: {audio_file}")
            
            # Preguntar si reproducir
            respuesta = input("\n  ¿Reproducir audio? (s/n): ").lower()
            if respuesta == 's':
                print("  🔊 Reproduciendo...")
                if handler.play_audio(audio_file):
                    print("  ✅ Reproducción completada")
                else:
                    print("  ❌ Error en reproducción")
        else:
            print("  ❌ Error generando audio")
    else:
        print("❌ TTS NO DISPONIBLE")
        print("  Instala con: pip install piper-tts")
        print("  Y descarga una voz desde:")
        print("  https://github.com/rhasspy/piper/releases/tag/v1.2.0")
    
    print("\n" + "-"*60 + "\n")
    
    # Test STT
    if handler.is_stt_available():
        print("🎙️ TEST 2: SPEECH-TO-TEXT (STT)")
        
        # Verificar si hay audio de prueba
        if handler.is_tts_available() and audio_file:
            print("  Transcribiendo audio generado...")
            texto = handler.speech_to_text(audio_file)
            
            if texto:
                print(f"  ✅ Texto transcrito: '{texto}'")
            else:
                print("  ❌ Error transcribiendo")
        else:
            print("  ⚠️ No hay audio para transcribir")
            print("  (requiere TTS funcionando para generar audio de prueba)")
    else:
        print("❌ STT NO DISPONIBLE")
        print("  Instala con: pip install openai-whisper")
        print("  Y asegúrate de tener FFmpeg instalado")
    
    print("\n" + "-"*60 + "\n")
    
    # Resumen
    print("📋 RESUMEN:")
    if handler.is_tts_available() and handler.is_stt_available():
        print("  ✅ Sistema de audio completamente funcional")
        print("  🚀 Listo para usarse en Raymundo y WhatsApp")
    elif handler.is_tts_available():
        print("  ⚠️ Solo TTS disponible (falta STT)")
        print("  💡 Instala Whisper para reconocimiento de voz")
    elif handler.is_stt_available():
        print("  ⚠️ Solo STT disponible (falta TTS)")
        print("  💡 Instala Piper y descarga una voz")
    else:
        print("  ❌ Sistema de audio no configurado")
        print("  💡 Ejecuta: instalar_audio.bat")
    
    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    try:
        test_audio()
    except Exception as e:
        print(f"\n❌ ERROR EN TEST: {e}")
        import traceback
        traceback.print_exc()
