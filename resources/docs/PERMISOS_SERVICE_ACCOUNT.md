# 🔐 Solución: Permisos del Service Account

## ❌ Problema
```
Error 403: The caller does not have permission
Service Account sin permisos IAM
```

**Ya habilitaste la API** ✅ pero el Service Account necesita permisos adicionales.

---

## ✅ Solución (2 minutos)

### Paso 1: Acceder a IAM & Admin
🔗 https://console.cloud.google.com/iam-admin/iam?project=trace-cf294

### Paso 2: Encontrar el Service Account
Busca esta cuenta de servicio en la lista:
```
📧 trace-cf294@appspot.gserviceaccount.com
```

### Paso 3: Editar Permisos
1. Haz click en el **ícono de lápiz** (✏️) al lado de la cuenta
2. Click en **"+ ADD ANOTHER ROLE"**
3. En el buscador de roles, escribe: **"Editor"**
4. Selecciona: **"Editor"** (o alternativamente "Owner")
5. Click en **"Save"**

### Paso 4: Verificar
- Espera 30-60 segundos (los permisos se propagan)
- Prueba de nuevo: `/raymundo haz una presentación sobre Python`

---

## 🎯 ¿Qué hace el rol "Editor"?

| Rol | Permisos |
|-----|----------|
| **Viewer** | Solo lectura ❌ |
| **Editor** | Crear/editar/eliminar archivos ✅ |
| **Owner** | Control total ✅ |

**Recomendado**: Usa **Editor** para dar acceso suficiente sin riesgos.

---

## 🔍 Alternativa: Roles Específicos

Si prefieres dar permisos mínimos (más seguro):

1. **Service Account Token Creator**
2. **Google Workspace Admin** (si trabajas con GSuite)

Pero **Editor** es más simple y funciona para todo.

---

## ⚠️ Por qué pasa esto

El archivo `google-credentials.json` contiene la **identidad** del Service Account, pero NO sus **permisos**.

**Los permisos se configuran en**:
- ✅ **APIs habilitadas** (ya lo hiciste)
- ✅ **IAM Roles** ← **Esto falta**

---

## 📋 Verificar que funcionó

Después de dar permisos, ejecuta:

```bash
python test_google_slides.py
```

**Resultado esperado**:
```
✅ Presentación creada: https://docs.google.com/presentation/d/...
```

**Si aún da error**:
1. Verifica que aplicaste los cambios en el proyecto correcto: `trace-cf294`
2. Espera 1-2 minutos (propagación de permisos)
3. Reinicia el servidor de Raymundo

---

## 🆘 Otros Errores Comunes

### "Service account does not exist in project"
- Verifica que estás en el proyecto correcto: **trace-cf294**
- El Service Account debe estar listado en IAM

### "Permission denied on resource project"
- Tu usuario personal necesita permisos de "Owner" o "Project IAM Admin"
- Contacta al administrador del proyecto

### "API not enabled"
- Verifica que habilitaste: https://console.cloud.google.com/apis/library/slides.googleapis.com?project=trace-cf294

---

## 🎓 Entendiendo Service Accounts

```
┌─────────────────────────────────────┐
│ google-credentials.json             │
│  • Clave privada (identidad)        │
│  • Email del Service Account        │
└─────────────────────────────────────┘
           ↓  
┌─────────────────────────────────────┐
│ Google Cloud Console (IAM)          │
│  • Roles y permisos                 │
│  • Qué puede hacer la cuenta        │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ APIs Habilitadas                    │
│  • Qué servicios usar               │
│  • Slides, Docs, Drive, etc.        │
└─────────────────────────────────────┘
```

**Los 3 deben estar configurados** para que funcione.

---

## 📞 Guía Rápida de Troubleshooting

| Síntoma | Causa | Solución |
|---------|-------|----------|
| Error 403: PERMISSION_DENIED | Falta rol IAM | Dar rol "Editor" |
| Error 403: API not enabled | API no habilitada | Habilitar API |
| Error 404: Not found | Proyecto incorrecto | Verificar project_id |
| Error 401: Unauthorized | Credenciales inválidas | Regenerar google-credentials.json |

---

**Link Directo**: https://console.cloud.google.com/iam-admin/iam?project=trace-cf294
