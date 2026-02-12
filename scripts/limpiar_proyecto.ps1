# Script de limpieza de archivos innecesarios en Raymundo
# Ejecutar con: .\scripts\limpiar_proyecto.ps1

Write-Host "🧹 Limpiando archivos innecesarios de Raymundo..." -ForegroundColor Cyan
Write-Host ""

# 1. Eliminar archivos temporales de audio
Write-Host "📁 Limpiando audios temporales..." -ForegroundColor Yellow
$audioTempPath = "resources\whatsapp\whatsapp_temp"
if (Test-Path $audioTempPath) {
    $archivosEliminados = 0
    Get-ChildItem -Path $audioTempPath -Include *.wav,*.mp3,*.ogg -Recurse | ForEach-Object {
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
        $archivosEliminados++
    }
    if ($archivosEliminados -gt 0) {
        Write-Host "   ✅ Eliminados $archivosEliminados archivos de audio temporales" -ForegroundColor Green
    } else {
        Write-Host "   ℹ️  No se encontraron archivos de audio temporales" -ForegroundColor Gray
    }
} else {
    Write-Host "   ℹ️  Carpeta de audios temporales no existe" -ForegroundColor Gray
}

# 2. Eliminar carpeta docs duplicada
Write-Host ""
Write-Host "📁 Buscando carpeta docs duplicada..." -ForegroundColor Yellow
$docsDuplicada = "resources\docs"
if (Test-Path $docsDuplicada) {
    Write-Host "   ⚠️  Encontrada carpeta docs duplicada en resources/" -ForegroundColor Red
    $respuesta = Read-Host "   ¿Deseas eliminarla? (S/N)"
    if ($respuesta -eq "S" -or $respuesta -eq "s") {
        Remove-Item -Path $docsDuplicada -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "   ✅ Carpeta eliminada" -ForegroundColor Green
    } else {
        Write-Host "   ⏭️  Omitido" -ForegroundColor Gray
    }
} else {
    Write-Host "   ✅ No hay carpeta docs duplicada" -ForegroundColor Green
}

# 3. Eliminar scripts duplicados
Write-Host ""
Write-Host "📁 Buscando scripts duplicados..." -ForegroundColor Yellow
$scriptsDuplicados = "resources\scripts"
if (Test-Path $scriptsDuplicados) {
    Write-Host "   ⚠️  Encontrada carpeta scripts duplicada en resources/" -ForegroundColor Red
    $respuesta = Read-Host "   ¿Deseas eliminarla? (S/N)"
    if ($respuesta -eq "S" -or $respuesta -eq "s") {
        Remove-Item -Path $scriptsDuplicados -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "   ✅ Carpeta eliminada" -ForegroundColor Green
    } else {
        Write-Host "   ⏭️  Omitido" -ForegroundColor Gray
    }
} else {
    Write-Host "   ✅ No hay carpeta scripts duplicada" -ForegroundColor Green
}

# 4. Eliminar archivos .pyc y __pycache__
Write-Host ""
Write-Host "📁 Limpiando archivos Python compilados..." -ForegroundColor Yellow
$pycacheCount = 0
Get-ChildItem -Path . -Recurse -Include __pycache__ | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    $pycacheCount++
}
Get-ChildItem -Path . -Recurse -Include *.pyc,*.pyo | ForEach-Object {
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
}
if ($pycacheCount -gt 0) {
    Write-Host "   ✅ Eliminadas $pycacheCount carpetas __pycache__" -ForegroundColor Green
} else {
    Write-Host "   ✅ No hay archivos Python compilados" -ForegroundColor Green
}

# 5. Limpiar archivos de log antiguos
Write-Host ""
Write-Host "📁 Limpiando archivos de log..." -ForegroundColor Yellow
$logsCount = 0
Get-ChildItem -Path . -Filter *.log | ForEach-Object {
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    $logsCount++
}
if ($logsCount -gt 0) {
    Write-Host "   ✅ Eliminados $logsCount archivos de log" -ForegroundColor Green
} else {
    Write-Host "   ✅ No hay archivos de log" -ForegroundColor Green
}

# 6. Verificar archivos duplicados en raíz
Write-Host ""
Write-Host "📁 Verificando archivos batch duplicados..." -ForegroundColor Yellow
$archivosDuplicados = @()
if (Test-Path "rAImundoGPT exe.bat") {
    $archivosDuplicados += "rAImundoGPT exe.bat"
}
if (Test-Path "rAImundoGPT Server.bat") {
    $archivosDuplicados += "rAImundoGPT Server.bat"
}

if ($archivosDuplicados.Count -gt 0) {
    Write-Host "   ⚠️  Encontrados archivos batch redundantes:" -ForegroundColor Red
    $archivosDuplicados | ForEach-Object {
        Write-Host "      - $_" -ForegroundColor Yellow
    }
    $respuesta = Read-Host "   ¿Deseas eliminarlos? (S/N)"
    if ($respuesta -eq "S" -or $respuesta -eq "s") {
        $archivosDuplicados | ForEach-Object {
            Remove-Item $_ -Force -ErrorAction SilentlyContinue
        }
        Write-Host "   ✅ Archivos eliminados" -ForegroundColor Green
    } else {
        Write-Host "   ⏭️  Omitido" -ForegroundColor Gray
    }
} else {
    Write-Host "   ✅ No hay archivos batch duplicados" -ForegroundColor Green
}

# Resumen final
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "✅ Limpieza completada" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Archivos mantenidos:" -ForegroundColor Cyan
Write-Host "   - raymundo.py (núcleo del agente)" -ForegroundColor White
Write-Host "   - whatsapp_server.py (API Flask)" -ForegroundColor White
Write-Host "   - config_agente.json (configuración)" -ForegroundColor White
Write-Host "   - Iniciar WhatsApp.bat (launcher completo)" -ForegroundColor White
Write-Host "   - iniciar_simple.bat (GUI local)" -ForegroundColor White
Write-Host ""
Write-Host "💡 Recomendación: Revisa docs/REFACTORIZACION_COMPLETA.md para más detalles" -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
