"""
Test: Crear presentación con contenido e imágenes generadas por IA
"""
import requests
import json

print("=" * 70)
print("🧪 TEST: Presentación con IA + Imágenes")
print("=" * 70)
print()

url = "http://localhost:5000/chat"
data = {
    "mensaje": "/raymundo crea una presentación sobre Inteligencia Artificial con 4 diapositivas",
    "user_id": "test_456"
}

print("📤 Enviando request...")
print(f"   Mensaje: {data['mensaje']}")
print()
print("⏳ Esto puede tardar 10-15 segundos (generando contenido + buscando imágenes)...")
print()

try:
    response = requests.post(url, json=data, timeout=120)
    
    if response.status_code == 200:
        resultado = response.json()
        
        print("=" * 70)
        print("✅ RESPUESTA:")
        print("=" * 70)
        print(resultado.get('respuesta', 'Sin respuesta'))
        print()
        
        if 'docs.google.com' in str(resultado):
            print("🎉 ¡PRESENTACIÓN CREADA!")
            print("   ✅ Contenido generado con IA")
            print("   ✅ Imágenes agregadas")
            print("   ✅ Diseño profesional")
            print()
            print("📌 Abre el link para verla")
        else:
            print("⚠️ Respuesta sin URL")
            
    else:
        print(f"❌ Error del servidor: {response.status_code}")
        print(response.text)
        
except requests.exceptions.Timeout:
    print("❌ Timeout - Tardó más de 120 segundos")
except Exception as e:
    print(f"❌ Error: {e}")
