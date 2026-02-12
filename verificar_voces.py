"""
Script para verificar si la voz Raúl está instalada
"""

import pyttsx3

engine = pyttsx3.init()
voices = engine.getProperty('voices')

print("🎤 VOCES INSTALADAS EN EL SISTEMA:\n")

spanish_male = []
spanish_female = []
english_male = []
english_female = []
other = []

for voice in voices:
    name = voice.name
    is_spanish = 'spanish' in name.lower() or 'español' in name.lower() or 'raul' in name.lower() or 'raúl' in name.lower() or 'pablo' in name.lower() or 'sabina' in name.lower() or 'helena' in name.lower()
    is_male = 'male' in name.lower() or 'raul' in name.lower() or 'raúl' in name.lower() or 'pablo' in name.lower() or 'diego' in name.lower() or 'david' in name.lower()
    
    if is_spanish:
        if is_male:
            spanish_male.append(f"✅ {name}")
        else:
            spanish_female.append(f"✅ {name}")
    elif 'english' in name.lower():
        if is_male:
            english_male.append(f"   {name}")
        else:
            english_female.append(f"   {name}")
    else:
        other.append(f"   {name}")

# Mostrar resultados
if spanish_male:
    print("🎙️  ESPAÑOL MASCULINO (IDEAL):")
    for v in spanish_male:
        print(f"   {v}")
    print()

if spanish_female:
    print("🎙️  ESPAÑOL FEMENINO:")
    for v in spanish_female:
        print(f"   {v}")
    print()

if english_male:
    print("🎙️  INGLÉS MASCULINO:")
    for v in english_male:
        print(f"   {v}")
    print()

if english_female:
    print("🎙️  INGLÉS FEMENINO:")
    for v in english_female:
        print(f"   {v}")
    print()

if other:
    print("🎙️  OTROS IDIOMAS:")
    for v in other:
        print(f"   {v}")
    print()

# Verificar si Raúl está instalado
tiene_raul = any('raul' in v.name.lower() or 'raúl' in v.name.lower() for v in voices)

print("=" * 60)
if tiene_raul:
    print("✅ VOZ RAÚL DETECTADA - Lista para usar")
    print("\n💡 Reinicia el servidor de WhatsApp para activarla:")
    print("   1. Detén el servidor actual (Ctrl+C)")
    print("   2. Ejecuta: .\\Iniciar WhatsApp.bat")
else:
    print("⚠️  VOZ RAÚL NO ENCONTRADA")
    print("\n💡 Para instalarla:")
    print("   1. Configuración → Hora e idioma → Idioma")
    print("   2. Español (México) → Opciones")
    print("   3. Voz → + Agregar voces")
    print("   4. Descarga 'Raúl'")
    print("\n   O ejecuta: .\\instalar_voz_raul.bat")

print("=" * 60)
