"""
Script de verificación pre-commit para GitHub
Verifica que no se suban archivos sensibles
"""
import os
from pathlib import Path
import subprocess

print("="*70)
print("🔍 VERIFICACIÓN PRE-COMMIT PARA GITHUB")
print("="*70 + "\n")

# Archivos que NUNCA deben estar en git
ARCHIVOS_PROHIBIDOS = [
    "config/.env",
    "config/google-credentials.json",
    "config/token.json",
    "config/oauth-credentials.json",
    "resources/data/memoria_agente.json",
    "resources/data/metrics.json",
    "resources/data/google-credentials.json",
]

CARPETAS_PROHIBIDAS = [
    "whatsapp_session",
    ".wwebjs_cache",
    "__pycache__",
    ".venv",
]

errores = []
advertencias = []

# 1. Verificar que archivos sensibles existan localmente
print("1️⃣ VERIFICANDO archivos sensibles (deben existir LOCALMENTE):")
archivos_criticos = ["config/.env", "config/.env.example"]
for archivo in archivos_criticos:
    if Path(archivo).exists():
        print(f"   ✅ {archivo} existe")
    else:
        if archivo == "config/.env":
            advertencias.append(f"⚠️ {archivo} NO existe. Crea uno desde config/.env.example")
        else:
            errores.append(f"❌ {archivo} NO existe. Es requerido para GitHub")

# 2. Verificar .gitignore
print("\n2️⃣ VERIFICANDO .gitignore:")
if Path(".gitignore").exists():
    with open(".gitignore", "r", encoding="utf-8") as f:
        gitignore_content = f.read()
    
    reglas_requeridas = [".env", "google-credentials.json", "whatsapp_session", ".venv"]
    for regla in reglas_requeridas:
        if regla in gitignore_content:
            print(f"   ✅ .gitignore incluye: {regla}")
        else:
            errores.append(f"❌ .gitignore NO incluye: {regla}")
else:
    errores.append("❌ .gitignore NO existe. Es CRÍTICO para proteger credenciales")

# 3. Verificar estado de Git
print("\n3️⃣ VERIFICANDO estado de Git:")
try:
    # Verificar si git está inicializado
    result = subprocess.run(["git", "status", "--porcelain"], 
                          capture_output=True, text=True, check=False)
    
    if result.returncode == 0:
        archivos_staged = result.stdout
        
        # Verificar que archivos prohibidos NO estén staged
        for archivo in ARCHIVOS_PROHIBIDOS:
            if archivo in archivos_staged:
                errores.append(f"❌ PELIGRO: {archivo} está en git add. Usar: git reset {archivo}")
        
        for carpeta in CARPETAS_PROHIBIDAS:
            if f"/{carpeta}/" in archivos_staged or f"{carpeta}/" in archivos_staged:
                errores.append(f"❌ PELIGRO: {carpeta}/ está en git add. Usar: git reset {carpeta}")
        
        # Verificar que config/.env.example SÍ esté
        if Path("config/.env.example").exists():
            print("   ✅ config/.env.example existe (se DEBE subir)")
        else:
            errores.append("❌ config/.env.example NO existe. Es requerido")
        
        print("   ✅ Git verificado")
    else:
        advertencias.append("⚠️ Git no inicializado. Ejecuta: git init")
        
except FileNotFoundError:
    advertencias.append("⚠️ Git no instalado. Instala desde: https://git-scm.com/")

# 4. Verificar estructura de archivos
print("\n4️⃣ VERIFICANDO estructura del proyecto:")
archivos_requeridos = [
    "README.md",
    "raymundo.py",
    "whatsapp_server.py",
    "config_agente.json",
    "requirements.txt",
]

for archivo in archivos_requeridos:
    if Path(archivo).exists():
        print(f"   ✅ {archivo}")
    else:
        advertencias.append(f"⚠️ {archivo} no encontrado (recomendado)")

# 5. Resumen
print("\n" + "="*70)
print("📊 RESUMEN")
print("="*70)

if not errores and not advertencias:
    print("\n✅ ¡PERFECTO! El proyecto está listo para subir a GitHub")
    print("\n📤 Comandos para subir:")
    print("   git init")
    print("   git add .")
    print("   git commit -m \"Initial commit: rAImundoGPT v2.0\"")
    print("   git remote add origin https://github.com/TU-USUARIO/raimundo-gpt.git")
    print("   git branch -M main")
    print("   git push -u origin main")
    
elif advertencias and not errores:
    print(f"\n⚠️ HAY {len(advertencias)} ADVERTENCIA(S):")
    for adv in advertencias:
        print(f"   {adv}")
    print("\n✅ Puedes continuar, pero revisa las advertencias")
    
else:
    print(f"\n❌ HAY {len(errores)} ERROR(ES) CRÍTICO(S):")
    for err in errores:
        print(f"   {err}")
    
    if advertencias:
        print(f"\n⚠️ Y {len(advertencias)} ADVERTENCIA(S):")
        for adv in advertencias:
            print(f"   {adv}")
    
    print("\n🛑 NO SUBAS A GITHUB HASTA RESOLVER LOS ERRORES")

print("\n" + "="*70)
print("📖 Ver guía completa en: docs/GUIA_SUBIR_GITHUB.md")
print("="*70)
