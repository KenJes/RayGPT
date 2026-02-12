"""
Test directo con Google Slides API sin módulos personalizados
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/presentations']

print("=" * 60)
print("🧪 TEST DIRECTO CON GOOGLE SLIDES API")
print("=" * 60)

# Cargar credenciales
credentials = service_account.Credentials.from_service_account_file(
    'google-credentials.json',
    scopes=SCOPES
)

print(f"✅ Service Account: {credentials.service_account_email}")
print()

# Crear servicio
service = build('slides', 'v1', credentials=credentials)

print("🔨 Intentando crear presentación...")

try:
    presentation = {
        'title': '✅ TEST EXITOSO - Raymundo Workspace'
    }
    
    result = service.presentations().create(body=presentation).execute()
    
    print()
    print("=" * 60)
    print("🎉 ¡ÉXITO! PRESENTACIÓN CREADA")
    print("=" * 60)
    print(f"   ID: {result['presentationId']}")
    print(f"   URL: https://docs.google.com/presentation/d/{result['presentationId']}/edit")
    print()
    print("✅ El Service Account tiene permisos correctos")
    print("✅ Google Slides API está funcionando")
    
except HttpError as e:
    print()
    print("=" * 60)
    print("❌ ERROR")
    print("=" * 60)
    print(f"   Status: {e.resp.status}")
    print(f"   Reason: {e.reason}")
    print(f"   Details: {e.error_details if hasattr(e, 'error_details') else 'N/A'}")
