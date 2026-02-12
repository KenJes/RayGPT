"""
Prueba directa de Google Slides API con permisos IAM
"""
from google_workspace_client import GoogleWorkspaceClient

print("=" * 60)
print("🧪 TEST: Crear presentación con Google Slides API")
print("=" * 60)

# Inicializar cliente
client = GoogleWorkspaceClient('google-credentials.json')

if not client.is_available():
    print("❌ Cliente no disponible")
    exit(1)

print("✅ Cliente Google Workspace inicializado")
print(f"   Service Account: trace-cf294@appspot.gserviceaccount.com")
print()

# Intentar crear presentación
print("🔨 Creando presentación de prueba...")
resultado = client.crear_presentacion("Test - Presentación de Prueba")

print()
print("=" * 60)
print("📋 RESULTADO:")
print("=" * 60)

if resultado:
    if 'error' in resultado:
        print(f"❌ Error: {resultado['error']}")
        print(f"   Mensaje: {resultado.get('message', 'N/A')}")
        print(f"   Link: {resultado.get('link', 'N/A')}")
    else:
        print(f"✅ ¡ÉXITO! Presentación creada")
        print(f"   ID: {resultado['id']}")
        print(f"   Título: {resultado['titulo']}")
        print(f"   URL: {resultado['url']}")
        print()
        print("🎉 ¡Los permisos IAM están configurados correctamente!")
else:
    print("❌ Resultado None - Error desconocido")

print("=" * 60)
