"""
Script de prueba para verificar Google Slides API
"""
import requests
import json

# Test 1: Verificar servidor
print("=" * 60)
print("🧪 TEST 1: Verificar servidor")
print("=" * 60)

try:
    response = requests.get("http://localhost:5000/health")
    print(f"✅ Servidor activo: {response.status_code}")
    print(f"   {response.json()}")
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

# Test 2: Crear presentación
print("\n" + "=" * 60)
print("🧪 TEST 2: Crear presentación sobre Python")
print("=" * 60)

payload = {
    "mensaje": "haz una presentación sobre Python",
    "user_id": "test_google_slides"
}

try:
    response = requests.post(
        "http://localhost:5000/chat",
        json=payload,
        timeout=60
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"\nRespuesta:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    
    if response.status_code == 200:
        result = response.json()
        if 'archivo' in result:
            print(f"\n✅ Archivo generado: {result['archivo']}")
        else:
            print(f"\n📝 Respuesta de texto solamente")
    else:
        print(f"\n❌ Error en la solicitud")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ Tests completados")
print("=" * 60)
