"""
Test: Crear presentación con OAuth 2.0
"""
from google_workspace_client import GoogleWorkspaceClient

print("=" * 70)
print("🧪 TEST: Crear presentación con OAuth 2.0")
print("=" * 70)
print()

# Inicializar cliente (usará token.json automáticamente)
client = GoogleWorkspaceClient('google-credentials.json')

if not client.is_available():
    print("❌ Cliente no disponible")
    exit(1)

print(f"🔑 Tipo de autenticación: {client.auth_type}")
print()

# Crear presentación de prueba
print("🔨 Creando presentación de prueba...")
resultado = client.crear_presentacion("✅ TEST OAUTH - Raymundo Funciona")

print()
print("=" * 70)
print("📋 RESULTADO:")
print("=" * 70)

if resultado and 'error' not in resultado:
    print("✅ ¡ÉXITO! Presentación creada")
    print(f"   ID: {resultado['id']}")
    print(f"   URL: {resultado['url']}")
    print()
    print("🎉 Raymundo ya puede crear presentaciones en tu Google Drive")
else:
    print("❌ Error:", resultado)
