"""
Test: Verificar que Drive API funciona para exportar
"""
from google_workspace_client import GoogleWorkspaceClient

print("=" * 70)
print("🧪 TEST: Exportar presentación a PPTX")
print("=" * 70)
print()

client = GoogleWorkspaceClient('google-credentials.json')

if not client.is_available():
    print("❌ Cliente no disponible")
    exit(1)

print(f"🔑 Tipo de autenticación: {client.auth_type}")
print()

# Crear presentación
print("🔨 Creando presentación...")
resultado = client.crear_presentacion("🧪 TEST EXPORT - Python")

if not resultado or 'error' in resultado:
    print(f"❌ Error al crear: {resultado}")
    exit(1)

print(f"✅ Presentación creada: {resultado['id']}")
print()

# Intentar exportar
print("📥 Intentando exportar a PPTX...")
pptx_path = client.exportar_presentacion_pptx(resultado['id'], 'test_export.pptx')

print()
print("=" * 70)
if pptx_path and pptx_path != "ERROR":
    print("✅ ¡ÉXITO! Archivo exportado")
    print(f"   Ruta: {pptx_path}")
    print()
    print("🎉 Google Drive API funcionando correctamente")
else:
    print("❌ Error al exportar")
    print()
    print("📋 SOLUCIÓN:")
    print("   1. Ve a: https://console.cloud.google.com/apis/library/drive.googleapis.com?project=trace-cf294")
    print("   2. Haz clic en 'HABILITAR'")
    print("   3. Espera 1-2 minutos")
    print("   4. Vuelve a ejecutar este script")
