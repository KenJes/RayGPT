"""
Script para ajustar la configuración de voz de rAImundoGPT
"""

# CONFIGURACIÓN DE VOZ
# ====================

# Motor de voz ('pyttsx3' recomendado, 'gtts' como fallback)
ENGINE = 'pyttsx3'

# Género preferido ('male' o 'female')
GENDER = 'male'  # Cambiar a 'female' si no tienes voces masculinas en español

# Velocidad (palabras por minuto)
# 150 = Lento
# 180 = Normal  ⬅️ ACTUAL
# 200 = Rápido
# 220 = Muy rápido
RATE = 180

# ====================
# NO MODIFICAR DEBAJO DE ESTA LÍNEA
# ====================

import sys
sys.path.insert(0, 'resources/core')

from audio_handler import get_audio_handler

print("🎤 Configuración de voz actual:")
print(f"   • Motor: {ENGINE}")
print(f"   • Género: {GENDER}")
print(f"   • Velocidad: {RATE} palabras/minuto")
print()

voice_config = {
    'engine': ENGINE,
    'gender': GENDER,
    'rate': RATE
}

handler = get_audio_handler(voice_config=voice_config)

if handler.is_tts_available():
    print("✅ Sistema de voz funcionando")
    
    # Prueba de voz
    print("\n🔊 Generando audio de prueba...")
    test_text = "Hola, soy Raymundo. Esta es mi voz actual."
    audio_file = handler.text_to_speech(test_text)
    
    if audio_file:
        print(f"✅ Audio generado: {audio_file}")
        print("\n💡 Si quieres cambiar:")
        print("   1. Modifica las variables al inicio de este archivo")
        print("   2. Vuelve a ejecutar: python ajustar_voz.py")
        print("   3. Reinicia el servidor de WhatsApp")
    else:
        print("❌ Error generando audio")
else:
    print("❌ Sistema de voz no disponible")
    print("   Instala: pip install pyttsx3")
