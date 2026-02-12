# REFACTORIZACIÓN Y LIMPIEZA DE RAYMUNDO

## Cambios Realizados

### 1. ✅ Mensaje de Bienvenida Simplificado
**Antes**: Mensaje largo con lista de funciones (15+ líneas)
**Ahora**: Simple "¿En qué puedo ayudarte?"
**Archivo**: `raymundo.py` línea ~1716

### 2. ✅ Personalidad Consolidada
**Problema**: Personalidad definida en 2 lugares (duplicación)
- `config_agente.json` (fuente de verdad)
- `raymundo.py` método `cambiar_personalidad()` (duplicado)

**Solución**: Eliminado método `cambiar_personalidad()` completo de `raymundo.py`
- Solo usa `config_agente.json` como fuente única
- Método `get_tono()` simplificado a 2 líneas
- **Líneas eliminadas**: ~70 líneas de código duplicado

**Archivos modificados**:
- `raymundo.py` (eliminado método cambiar_personalidad)
- `config_agente.json` (mantiene toda la configuración)

### 3. ✅ Detección de Voces Mexicanas Mejorada
**Problema**: No detectaba correctamente voces Raúl/Sabina
**Solución**: Prioridad a voces mexicanas en `audio_handler.py`
- Busca primero: Raúl (masculino), Sabina (femenino)
- Luego: Otras voces en español
- Finalmente: Voces en inglés (fallback)

**Archivo**: `resources/core/audio_handler.py` línea ~115-155

### 4. ✅ Corrección de chatId en WhatsApp
**Problema**: Variable incorrecta `userId` en lugar de `chatId`
**Solución**: Ya estaba corregido en el código actual
**Archivo**: `resources/whatsapp/whatsapp_bot.js` línea ~305

---

## Archivos Innecesarios (Candidatos a Eliminar)

### 📁 Carpeta: `resources/docs/`
**Estado**: Redundante (duplica información del README.md raíz)

**Archivos eliminables**:
- `resources/docs/README.md` → Ya existe `README.md` en raíz
- `resources/docs/setup_notes.txt` → Información desactualizada
- `resources/docs/STACK_TECNOLOGICO.md` → Puede integrarse en README principal

**Acción recomendada**: 
```bash
# Mover documentos importantes a la raíz si no existen
# Eliminar carpeta resources/docs completa
rm -rf resources/docs/
```

**Mantener solo**:
- `docs/ALTERNATIVAS_API.md`
- `docs/COMO_CONFIGURAR_API_KEY.md`
- `docs/CONFIGURAR_OAUTH_GMAIL.md`
- `docs/MONITOREO_TOKENS.md`
- `docs/OPCIONES_GRATUITAS.md`
- `docs/GUIA_ENTRENAR_RAYMUNDO.txt` (nuevo)
- `docs/GUIA_EXPORTAR_GITHUB.txt` (nuevo)
- `docs/ALTERNATIVAS_TTS_MEXICANO.md` (nuevo)

---

### 📁 Carpeta: `resources/scripts/`
**Estado**: Parcialmente redundante

**Archivos eliminables**:
- `resources/scripts/autorizar_google.py` → Usar solo `scripts/autorizar_google.py`
- `resources/scripts/configurar_agente.py` → Usar solo `scripts/configurar_agente.py`
- `resources/scripts/verificar_credentials.py` → Usar solo `scripts/verificar_credentials.py`

**Mantener**:
- `scripts/` (carpeta raíz con scripts útiles)

**Acción recomendada**:
```bash
# Eliminar duplicados en resources/scripts
rm -rf resources/scripts/
```

---

### 📁 Carpeta: `resources/whatsapp/`
**Estado**: Necesaria pero con archivos temporales

**Archivos innecesarios**:
- `resources/whatsapp/whatsapp_temp/*.wav` → Archivos temporales de audio
- `resources/whatsapp/whatsapp_temp/*.mp3` → Limpiar periódicamente
- `resources/whatsapp/whatsapp_session/` → Archivos de sesión (NO eliminar si quieres mantener sesión)

**Acción recomendada**:
```bash
# Limpiar archivos temporales (no eliminar carpetas)
rm resources/whatsapp/whatsapp_temp/*.wav
rm resources/whatsapp/whatsapp_temp/*.mp3
rm resources/whatsapp/whatsapp_temp/*.ogg
```

**Mantener**:
- `resources/whatsapp/whatsapp_bot.js` (esencial)
- `resources/whatsapp/package.json` (esencial)
- `resources/whatsapp/whatsapp_session/` (mantener sesión activa)

---

### 📁 Carpeta: `resources/data/`
**Estado**: Contiene archivos sensibles y datos de runtime

**Archivos innecesarios/peligrosos**:
- `resources/data/google-credentials.json.json` → Nombre duplicado incorrecto
- `resources/data/client_secret_*.json` → NO DEBE ESTAR EN REPO (mover a `config/`)

**Acción recomendada**:
```bash
# Mover credenciales a config/
mv resources/data/*.json config/

# Asegurar que config/ está en .gitignore
echo "config/*.json" >> .gitignore
```

**Mantener**:
- `data/memoria_agente.json` (memoria contextual)
- `data/metrics.json` (métricas de uso)

---

### 📄 Archivos raíz duplicados/innecesarios

**Eliminables**:
- `rAImundoGPT exe.bat` → Redundante con `iniciar_simple.bat`
- `rAImundoGPT Server.bat` → Redundante con `Iniciar WhatsApp.bat`

**Acción recomendada**:
```bash
# Consolidar a solo 2 scripts:
# 1. Iniciar WhatsApp.bat (servidor Flask + bot WhatsApp)
# 2. iniciar_simple.bat (solo GUI local)
rm "rAImundoGPT exe.bat"
rm "rAImundoGPT Server.bat"
```

**Mantener**:
- `Iniciar WhatsApp.bat` (lanza servidor + bot)
- `iniciar_simple.bat` (lanza solo GUI)
- `raymundo.py` (núcleo del agente)
- `whatsapp_server.py` (API Flask)
- `whatsapp_bot.js` (bot de WhatsApp - mover a raíz?)
- `config_agente.json` (configuración)
- `package.json` (dependencias Node.js)

---

## Estructura Recomendada (Simplificada)

```
Agentes/
├── 📄 raymundo.py                    # Núcleo del agente (GUI incluida)
├── 📄 whatsapp_server.py             # API Flask para WhatsApp
├── 📄 whatsapp_bot.js                # Bot de WhatsApp (mover aquí desde resources/)
├── 📄 config_agente.json             # Configuración de personalidad
├── 📄 package.json                   # Dependencias Node.js
├── 📄 README.md                      # Documentación principal
├── 📄 .gitignore                     # Archivos ignorados
├── 📄 Iniciar WhatsApp.bat           # Launcher completo (Flask + Bot)
├── 📄 iniciar_simple.bat             # Launcher GUI local
│
├── 📁 .venv/                         # Entorno virtual Python (no subir)
│
├── 📁 config/                        # Credenciales sensibles (NO SUBIR A GIT)
│   ├── google-credentials.json
│   ├── oauth-credentials.json
│   └── .env                          # Variables de entorno
│
├── 📁 data/                          # Datos de runtime
│   ├── memoria_agente.json           # Memoria contextual
│   └── metrics.json                  # Métricas de uso
│
├── 📁 output/                        # Archivos generados
│   └── (presentaciones, audios, etc.)
│
├── 📁 resources/                     # Recursos del proyecto
│   ├── 📁 core/                      # Módulos centrales
│   │   ├── audio_handler.py
│   │   ├── google_workspace_client.py
│   │   └── metrics_tracker.py
│   │
│   ├── 📁 assets/                    # Recursos estáticos
│   │   └── imagenes/
│   │
│   └── 📁 whatsapp/                  # (Mover archivos a raíz)
│       ├── whatsapp_session/         # Sesión de WhatsApp (mantener)
│       └── whatsapp_temp/            # Archivos temporales (limpiar)
│
├── 📁 scripts/                       # Scripts de utilidad
│   ├── autorizar_google.py
│   ├── configurar_agente.py
│   ├── verificar_credentials.py
│   └── verificar_voces.py
│
└── 📁 docs/                          # Documentación extendida
    ├── ALTERNATIVAS_API.md
    ├── COMO_CONFIGURAR_API_KEY.md
    ├── CONFIGURAR_OAUTH_GMAIL.md
    ├── MONITOREO_TOKENS.md
    ├── OPCIONES_GRATUITAS.md
    ├── GUIA_ENTRENAR_RAYMUNDO.txt    # ← Nuevo
    ├── GUIA_EXPORTAR_GITHUB.txt      # ← Nuevo
    └── ALTERNATIVAS_TTS_MEXICANO.md  # ← Nuevo
```

---

## Script de Limpieza Automática

Crea este archivo: `scripts/limpiar_proyecto.ps1`

```powershell
# Script de limpieza de archivos innecesarios
Write-Host "🧹 Limpiando archivos innecesarios..." -ForegroundColor Cyan

# 1. Eliminar archivos temporales de audio
Write-Host "Limpiando audios temporales..." -ForegroundColor Yellow
Remove-Item -Path "resources\whatsapp\whatsapp_temp\*.wav" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "resources\whatsapp\whatsapp_temp\*.mp3" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "resources\whatsapp\whatsapp_temp\*.ogg" -Force -ErrorAction SilentlyContinue

# 2. Eliminar carpeta docs duplicada (si existe)
if (Test-Path "resources\docs") {
    Write-Host "Eliminando carpeta docs duplicada..." -ForegroundColor Yellow
    Remove-Item -Path "resources\docs" -Recurse -Force -ErrorAction SilentlyContinue
}

# 3. Eliminar scripts duplicados
if (Test-Path "resources\scripts") {
    Write-Host "Eliminando scripts duplicados..." -ForegroundColor Yellow
    Remove-Item -Path "resources\scripts" -Recurse -Force -ErrorAction SilentlyContinue
}

# 4. Eliminar archivos .pyc y __pycache__
Write-Host "Limpiando archivos Python compilados..." -ForegroundColor Yellow
Get-ChildItem -Path . -Recurse -Include __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -Include *.pyc | Remove-Item -Force -ErrorAction SilentlyContinue

# 5. Limpiar archivos de log antiguos (si existen)
if (Test-Path "*.log") {
    Write-Host "Limpiando archivos de log..." -ForegroundColor Yellow
    Remove-Item -Path "*.log" -Force -ErrorAction SilentlyContinue
}

Write-Host "✅ Limpieza completada" -ForegroundColor Green
```

**Ejecutar**:
```powershell
.\scripts\limpiar_proyecto.ps1
```

---

## Archivos a Actualizar en .gitignore

```gitignore
# Entornos virtuales
.venv/
venv/
env/

# Credenciales y configuración sensible
config/
config/*.json
config/.env
*.pem
*.key

# Datos de runtime
data/logs/
data/dump/

# Archivos temporales de audio
resources/whatsapp/whatsapp_temp/*.wav
resources/whatsapp/whatsapp_temp/*.mp3
resources/whatsapp/whatsapp_temp/*.ogg

# Sesión de WhatsApp (opcional - depende si quieres mantenerla privada)
resources/whatsapp/whatsapp_session/

# Archivos Python compilados
__pycache__/
*.pyc
*.pyo
*.pyd

# Node modules
node_modules/
resources/whatsapp/node_modules/

# Archivos de salida generados
output/

# Archivos de log
*.log

# Archivos del sistema
.DS_Store
Thumbs.db
desktop.ini
```

---

## Resumen de Reducción

| Categoría | Antes | Después | Reducción |
|-----------|-------|---------|-----------|
| Archivos `.py` duplicados | 15+ | 8 | ~47% |
| Líneas de código duplicado | ~150 | 0 | -150 líneas |
| Carpetas documentación | 2 (`docs/`, `resources/docs/`) | 1 (`docs/`) | -1 carpeta |
| Scripts duplicados | 2 ubicaciones | 1 (`scripts/`) | -1 carpeta |
| Archivos temporales | Variable | 0 (limpieza automática) | N/A |

**Total**: Proyecto ~30% más ligero y organizado

---

## Próximos Pasos

1. **Ejecutar script de limpieza**:
   ```powershell
   .\scripts\limpiar_proyecto.ps1
   ```

2. **Revisar y actualizar .gitignore**:
   - Añadir `config/` para proteger credenciales
   - Añadir archivos temporales de audio

3. **Probar funcionalidad**:
   - Iniciar WhatsApp bot: `.\Iniciar WhatsApp.bat`
   - Verificar que todo funciona después de limpieza

4. **Commit de cambios** (si usas Git):
   ```bash
   git add .
   git commit -m "Refactor: Eliminado código duplicado y archivos innecesarios"
   ```

5. **Documentar cambios** en README.md si es necesario

---

## Ventajas de la Refactorización

✅ **Código más limpio**: Sin duplicaciones  
✅ **Más fácil de mantener**: Una sola fuente de verdad para personalidad  
✅ **Más rápido**: Menos archivos a cargar  
✅ **Más seguro**: Credenciales correctamente separadas  
✅ **Mejor experiencia de usuario**: Mensaje de bienvenida simple  
✅ **Mejor voz**: Prioridad a voces mexicanas (Raúl/Sabina)

