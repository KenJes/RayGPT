# 🎨 Cómo Habilitar Google Slides API

## ❌ Problema
```
Error al crear presentación (verifica permisos de Google API)
403 Forbidden - PERMISSION_DENIED
```

## ✅ Solución (5 minutos)

### Paso 1: Acceder a Google Cloud Console
🔗 https://console.cloud.google.com/apis/library/slides.googleapis.com

### Paso 2: Seleccionar Proyecto
- Haz clic en el selector de proyectos (arriba)
- Selecciona el proyecto donde configuraste tu Service Account
- (El mismo proyecto donde creaste `google-credentials.json`)

### Paso 3: Habilitar API
1. Verifica que estés en la página de **Google Slides API**
2. Haz clic en el botón **"ENABLE"** (Habilitar) azul
3. Espera 1-2 minutos mientras se activa

### Paso 4: Verificar
```bash
# En WhatsApp, prueba de nuevo:
/raymundo haz una presentación sobre IA
```

---

## 📋 Otras APIs que puedes necesitar

Si usas otras funcionalidades, asegúrate de habilitar:

| API | Link | Funcionalidad |
|-----|------|--------------|
| **Google Drive API** | https://console.cloud.google.com/apis/library/drive.googleapis.com | Subir/descargar archivos |
| **Google Docs API** | https://console.cloud.google.com/apis/library/docs.googleapis.com | Crear/editar documentos |
| **Google Sheets API** | https://console.cloud.google.com/apis/library/sheets.googleapis.com | Crear/editar hojas de cálculo |
| **Google Calendar API** | https://console.cloud.google.com/apis/library/calendar-json.googleapis.com | Agendar eventos |
| **Gmail API** | https://console.cloud.google.com/apis/library/gmail.googleapis.com | Enviar correos |

---

## 🔍 Cómo verificar APIs habilitadas

1. Ve a: https://console.cloud.google.com/apis/dashboard
2. Selecciona tu proyecto
3. Verás la lista de APIs habilitadas

**APIs necesarias para Raymundo:**
- ✅ Google Drive API
- ✅ Google Docs API
- ✅ Google Sheets API
- ✅ Google Slides API
- ✅ Google Calendar API

---

## ⚠️ Notas Importantes

### Service Account vs OAuth
- **Service Account** (actual): No requiere autorización del usuario, pero necesita habilitar APIs manualmente
- **OAuth2**: Pide permisos al usuario, las APIs se habilitan automáticamente

### Permisos de Archivos
Si el Service Account no puede acceder a archivos existentes:

1. Comparte el archivo con el email del Service Account:
   ```
   nombre-cuenta@proyecto.iam.gserviceaccount.com
   ```
2. O usa el método `compartir_con_cuenta()` en el código

---

## 🆘 Solución de Problemas

### "Project not found"
- Verifica que estés usando el proyecto correcto en Cloud Console
- El Service Account debe pertenecer a ese proyecto

### "API not enabled"
- Espera 2-3 minutos después de habilitar
- Recarga la página de Cloud Console
- Reinicia el servidor de Raymundo

### "Insufficient permissions"
- Verifica que el archivo `google-credentials.json` tenga el scope:
  ```json
  "https://www.googleapis.com/auth/presentations"
  ```
- Regenera las credenciales si es necesario

---

## 📞 Contacto

Si el problema persiste:
1. Verifica los logs del servidor: mira los errores en la terminal
2. Comprueba que `google-credentials.json` esté en la carpeta correcta
3. Revisa que el Service Account tenga rol de **"Editor"** en el proyecto

**Link útil**: https://developers.google.com/slides/api/guides/authorizing
