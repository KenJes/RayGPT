"""
Script para autorizar Raymundo con tu cuenta de Google (solo se ejecuta una vez)
"""
import os
import sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Alcances necesarios
SCOPES = [
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

def main():
    print("=" * 70)
    print("🔐 AUTORIZACIÓN DE GOOGLE PARA RAYMUNDO")
    print("=" * 70)
    print()
    
    creds = None
    token_file = 'token.json'
    oauth_file = 'oauth-credentials.json'
    
    # Verificar si ya existe el token
    if os.path.exists(token_file):
        print("⚠️  Ya existe un token de autorización.")
        respuesta = input("¿Quieres renovar la autorización? (s/n): ")
        if respuesta.lower() != 's':
            print("❌ Operación cancelada.")
            return
        os.remove(token_file)
        print("✅ Token anterior eliminado.")
        print()
    
    # Verificar que existan las credenciales OAuth
    if not os.path.exists(oauth_file):
        print("❌ ERROR: No se encuentra el archivo 'oauth-credentials.json'")
        print()
        print("Por favor, descarga las credenciales OAuth desde:")
        print("https://console.cloud.google.com/apis/credentials?project=trace-cf294")
        print()
        sys.exit(1)
    
    print("📂 Credenciales OAuth encontradas")
    print("🌐 Abriendo navegador para autorización...")
    print()
    print("=" * 70)
    print("⚡ IMPORTANTE:")
    print("   1. Se abrirá tu navegador")
    print("   2. Inicia sesión con tu cuenta de Gmail")
    print("   3. Acepta los permisos solicitados")
    print("   4. Google puede mostrar una advertencia porque la app está en prueba")
    print("      -> Haz clic en 'Avanzado' o 'Advanced'")
    print("      -> Luego en 'Ir a Raymundo Assistant (no seguro)'")
    print("   5. Autoriza todos los permisos")
    print("=" * 70)
    print()
    input("Presiona ENTER cuando estés listo para continuar...")
    print()
    
    try:
        # Flujo de autorización
        flow = InstalledAppFlow.from_client_secrets_file(oauth_file, SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Guardar el token
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
        
        print()
        print("=" * 70)
        print("✅ ¡AUTORIZACIÓN EXITOSA!")
        print("=" * 70)
        print()
        print(f"📁 Token guardado en: {os.path.abspath(token_file)}")
        print()
        print("✅ Raymundo ya puede crear presentaciones, documentos y hojas de cálculo")
        print("✅ No necesitas volver a autorizar (el token se renueva automáticamente)")
        print()
        print("🚀 Ahora puedes usar: /raymundo crea una presentación sobre Python")
        print()
        
    except Exception as e:
        print()
        print("=" * 70)
        print("❌ ERROR EN LA AUTORIZACIÓN")
        print("=" * 70)
        print(f"   {str(e)}")
        print()
        print("Intenta ejecutar el script nuevamente y sigue los pasos cuidadosamente.")
        sys.exit(1)

if __name__ == '__main__':
    main()
