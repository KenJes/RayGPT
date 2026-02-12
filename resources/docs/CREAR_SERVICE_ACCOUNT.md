# 🔑 Crear Service Account para Google Workspace

## ❌ Problema Actual
El Service Account de App Engine (`trace-cf294@appspot.gserviceaccount.com`) tiene restricciones y no puede crear archivos directamente en Google Workspace.

## ✅ Solución: Crear un Service Account Personalizado

### Paso 1: Crear Service Account
🔗 https://console.cloud.google.com/iam-admin/serviceaccounts?project=trace-cf294

1. Click en **"+ CREATE SERVICE ACCOUNT"**
2. Llena los datos:
   - **Name**: `raymundo-workspace`
   - **ID**: `raymundo-workspace` (se auto-completa)
   - **Description**: `Service Account para crear docs, slides, sheets`
3. Click **"CREATE AND CONTINUE"**

### Paso 2: Asignar Roles
4. En "Grant this service account access to project":
   - Selecciona: **Editor**
5. Click **"CONTINUE"**
6. Click **"DONE"** (skip step 3)

### Paso 3: Crear Clave JSON
7. En la lista de Service Accounts, click en el nuevo: `raymundo-workspace@trace-cf294.iam.gserviceaccount.com`
8. Ve a la pestaña **"KEYS"**
9. Click **"ADD KEY"** → **"Create new key"**
10. Selecciona **"JSON"**
11. Click **"CREATE"**
12. Se descargará: `trace-cf294-xxxxx.json`

### Paso 4: Reemplazar Archivo
13. Renombra el archivo descargado a: `google-credentials.json`
14. Moverlo a: `C:\Users\kenne\Visual Studio Code\Agentes\`
15. Reemplaza el archivo actual

### Paso 5: Habilitar APIs Necesarias
Verifica que estas APIs estén habilitadas:

- ✅ Google Slides API: https://console.cloud.google.com/apis/library/slides.googleapis.com?project=trace-cf294
- ✅ Google Drive API: https://console.cloud.google.com/apis/library/drive.googleapis.com?project=trace-cf294  
- ✅ Google Docs API: https://console.cloud.google.com/apis/library/docs.googleapis.com?project=trace-cf294
- ✅ Google Sheets API: https://console.cloud.google.com/apis/library/sheets.googleapis.com?project=trace-cf294

### Paso 6: Reiniciar y Probar
```bash
python test_slides_direct.py
```

---

## 🎯 ¿Por qué App Engine Service Account no funciona?

| Tipo | Restricciones | Recomendado |
|------|--------------|-------------|
| **App Engine Default** | Solo para servicios internos de App Engine | ❌ No |
| **Service Account Personalizado** | Acceso completo según roles | ✅ Sí |

---

## 📋 Checklist

- [ ] Crear Service Account `raymundo-workspace`
- [ ] Asignar rol "Editor"
- [ ] Generar clave JSON
- [ ] Reemplazar `google-credentials.json`
- [ ] Verificar APIs habilitadas
- [ ] Probar creación de presentación

---

## 🆘 Si Sigue sin Funcionar

Si después de crear el nuevo Service Account aún da error 403, necesitarás **habilitar Domain-Wide Delegation** (solo si usas Google Workspace organizacional).

Pero para uso personal, el Service Account personalizado debería funcionar directamente.

---

**Link Directo para Crear Service Account**:  
https://console.cloud.google.com/iam-admin/serviceaccounts/create?project=trace-cf294
