"""
Test completo: Crear presentación via API de WhatsApp
"""
import requests

print("=" * 70)
print("🧪 TEST COMPLETO: API de WhatsApp → Raymundo → Google Slides")
print("=" * 70)
print()

url = "http://localhost:5000/chat"
data = {
    "mensaje": "/raymundo crea una presentación sobre Python con 3 diapositivas",
    "user_id": "test_123"
}

print("📤 Enviando request a WhatsApp Server...")
print(f"   URL: {url}")
print(f"   Mensaje: {data['mensaje']}")
print()

try:
    response = requests.post(url, json=data, timeout=60)
    
    if response.status_code == 200:
        resultado = response.json()
        print("=" * 70)
        print("✅ RESPUESTA DEL SERVIDOR:")
        print("=" * 70)
        print(resultado.get('respuesta', 'Sin respuesta'))
        print()
        
        if 'docs.google.com' in str(resultado):
            print("🎉 ¡ÉXITO TOTAL!")
            print("   ✅ OAuth funcionando")
            print("   ✅ Google Slides API funcionando")
            print("   ✅ Raymundo creando presentaciones")
        else:
            print("⚠️ Respuesta recibida pero sin URL de presentación")
    else:
        print(f"❌ Error del servidor: {response.status_code}")
        print(response.text)
        
except requests.exceptions.Timeout:
    print("❌ Timeout - El servidor tardó más de 60 segundos")
except Exception as e:
    print(f"❌ Error: {e}")
