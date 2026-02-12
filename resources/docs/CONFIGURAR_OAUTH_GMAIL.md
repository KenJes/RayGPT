# 🔐 Configurar OAuth 2.0 para Gmail Personal

## ¿Por qué OAuth en lugar de Service Account?

**Service Accounts** → Solo para Google Workspace con domain-wide delegation (de paga)  
**OAuth 2.0** → Para Gmail personal, el usuario autoriza la app directamente

---

## 📋 Pasos para configurar OAuth 2.0

### Paso 1: Crear credenciales OAuth en Google Cloud Console

1. Ve a: https://console.cloud.google.com/apis/credentials?project=trace-cf294

2. Clic en **"+ CREAR CREDENCIALES"** → **"ID de cliente de OAuth"**

3. Si te pide configurar "Pantalla de consentimiento OAuth":
   - Clic en **"CONFIGURAR PANTALLA DE CONSENTIMIENTO"**
   - Selecciona **"Externo"** (para Gmail personal)
   - Clic en **"CREAR"**
   
4. Llena los datos mínimos:
   - **Nombre de la app**: `Raymundo Assistant`
   - **Correo de asistencia**: Tu email
   - **Correo del desarrollador**: Tu email
   - Clic en **"GUARDAR Y CONTINUAR"**

5. En "Alcances" (Scopes):
   - Clic en **"AÑADIR O QUITAR ALCANCES"**
   - Busca y selecciona:
     - `https://www.googleapis.com/auth/presentations` (Google Slides)
     - `https://www.googleapis.com/auth/documents` (Google Docs)
     - `https://www.googleapis.com/auth/spreadsheets` (Google Sheets)
     - `https://www.googleapis.com/auth/drive.file` (Google Drive)
   - Clic en **"ACTUALIZAR"**
   - Clic en **"GUARDAR Y CONTINUAR"**

6. En "Usuarios de prueba":
   - Clic en **"+ ADD USERS"**
   - Agrega tu email de Gmail
   - Clic en **"GUARDAR Y CONTINUAR"**

7. Revisa el resumen y clic en **"VOLVER AL PANEL"**

8. Ahora vuelve a **Credenciales**: https://console.cloud.google.com/apis/credentials?project=trace-cf294

9. Clic en **"+ CREAR CREDENCIALES"** → **"ID de cliente de OAuth"**

10. Selecciona:
    - **Tipo de aplicación**: `Aplicación de escritorio`
    - **Nombre**: `Raymundo Desktop`
    - Clic en **"CREAR"**

11. Se abrirá un popup con tus credenciales:
    - Clic en **"DESCARGAR JSON"**
    - Guarda el archivo (se llamará algo como `client_secret_XXX.json`)

12. Renombra el archivo descargado a: **`oauth-credentials.json`**

13. Mueve `oauth-credentials.json` a la carpeta: `C:\Users\kenne\Visual Studio Code\Agentes\`

---

### Paso 2: Autorizar la aplicación (solo una vez)

Yo crearé un script que:
1. Abre el navegador automáticamente
2. Te pide que autorices la app
3. Guarda el token en `token.json`
4. Ese token funciona permanentemente (se renueva automáticamente)

---

## ✅ Ventajas de OAuth 2.0

- ✅ Funciona con Gmail personal (gratis)
- ✅ Solo autorizas una vez
- ✅ El token se renueva automáticamente
- ✅ Acceso completo a tus Slides, Docs, Sheets, Drive
- ✅ Raymundo crea archivos en TU cuenta (no en Service Account)

---

## 🆚 Diferencia con Service Account

| Característica | Service Account | OAuth 2.0 |
|----------------|-----------------|-----------|
| **Para Gmail personal** | ❌ No funciona | ✅ Funciona |
| **Para Google Workspace** | ✅ Con domain-wide delegation | ✅ Funciona |
| **Autorización** | Automática (solo Workspace) | Una vez por usuario |
| **Archivos creados** | En cuenta del SA (no accesibles) | En TU cuenta ✅ |
| **Costo** | Gratis (si tienes Workspace) | Gratis |

---

## 🚀 Siguiente paso

Dime cuando hayas completado el **Paso 1** (descargar `oauth-credentials.json`) y yo crearé el script de autorización.
