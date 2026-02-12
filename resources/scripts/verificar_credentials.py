"""
Script para verificar qué Service Account está en google-credentials.json
"""
import json

with open('google-credentials.json', 'r') as f:
    creds = json.load(f)

print("=" * 60)
print("🔍 VERIFICACIÓN DE CREDENCIALES")
print("=" * 60)
print()
print(f"📧 Service Account Email: {creds['client_email']}")
print(f"🆔 Project ID: {creds['project_id']}")
print()

if 'raymundo-workspace' in creds['client_email']:
    print("✅ Archivo CORRECTO - Usando nuevo Service Account")
    print("   Puedes crear presentaciones ahora")
elif 'appspot' in creds['client_email']:
    print("❌ Archivo INCORRECTO - Usando App Engine Service Account")
    print()
    print("🔧 SOLUCIÓN:")
    print("   1. Ve a: https://console.cloud.google.com/iam-admin/serviceaccounts?project=trace-cf294")
    print("   2. Click en: raymundo-workspace@trace-cf294.iam.gserviceaccount.com")
    print("   3. Pestaña KEYS → ADD KEY → Create new key → JSON")
    print("   4. Descarga y renombra a: google-credentials.json")
    print("   5. Reemplaza este archivo")
else:
    print("⚠️ Service Account desconocido")

print("=" * 60)
