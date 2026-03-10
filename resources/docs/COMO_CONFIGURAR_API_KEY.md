# 🔑 Dónde Pegar tu API Key de Groq

## ✅ Opción 1: Archivo `.env` (RECOMENDADO)

### Paso a paso:

1. **Abre el archivo `.env`** en la carpeta raíz del proyecto
   ```
   c:\Users\kenne\Visual Studio Code\Agentes\.env
   ```

2. **Busca la línea** que dice:
   ```bash
   GROQ_API_KEY=
   ```

3. **Pega tu API key después del `=`**:
   ```bash
   GROQ_API_KEY=gsk_tu_key_aqui_sin_espacios
   ```

4. **Guarda el archivo** (Ctrl + S)

5. **¡Listo!** Ya está configurado

### Ejemplo Completo:

```bash
# Groq API (Llama 3.1 70B) - Ultra rápido y gratis (14,400 RPD)
# Obtén tu key en: https://console.groq.com/keys
GROQ_API_KEY=gsk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# Ollama Local - Ya configurado
OLLAMA_MODEL=llama3.1:8b
```

---

## ⚙️ Opción 2: Variables de Entorno de Windows

### Temporal (solo para la sesión actual):

```powershell
# En PowerShell
$env:GROQ_API_KEY = "gsk_tu_key_aqui"
```

### Permanente (todo el sistema):

1. **Abrir Panel de Control** → Sistema → Configuración avanzada del sistema
2. **Variables de entorno**
3. **Nueva variable de usuario**:
   - Nombre: `GROQ_API_KEY`
   - Valor: `gsk_tu_key_aqui`
4. **Aceptar y reiniciar terminal**

---

## 🚀 Cómo Obtener tu API Key de Groq

### Paso 1: Registrarte (2 minutos)

1. **Ir a**: https://console.groq.com/
2. **Click en "Sign in"**
3. **Seleccionar** "Sign up with Google" o "Sign up with GitHub"
4. **Aceptar términos** (sin tarjeta de crédito requerida)

### Paso 2: Crear API Key (1 minuto)

1. **Dashboard** → Click en tu nombre (arriba derecha)
2. **API Keys** en el menú
3. **Click "Create API Key"**
4. **Copiar la key** (empieza con `gsk_`)
   ```
   gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
5. **¡IMPORTANTE!** Guárdala ahora, solo se muestra una vez

### Paso 3: Pegar en `.env`

```bash
# Abrir archivo .env
code .env

# Pegar después del =
GROQ_API_KEY=gsk_la_key_que_copiaste
```

---

## ✅ Verificar que Funciona

### Opción 1: Ejecutar test rápido

```powershell
# En PowerShell (carpeta del proyecto)
python -c "import os; from groq import Groq; print('✅ Groq configurado!' if os.getenv('GROQ_API_KEY') else '❌ Falta API key')"
```

### Opción 2: Reiniciar servidor

```powershell
# Detener servidor actual
Get-Process | Where-Object { $_.ProcessName -eq 'python' } | Stop-Process -Force

# Iniciar de nuevo
.\iniciar_whatsapp.bat
```

**Si ves en los logs:**
```
✅ Groq client inicializado
```
¡Está funcionando!

---

## 🔒 Seguridad de tu API Key

### ✅ Buenas Prácticas:

1. **NUNCA** subas el archivo `.env` a GitHub
   - El `.gitignore` ya lo excluye automáticamente

2. **NUNCA** compartas tu API key en capturas o mensajes

3. **Si la expones por error**:
   - Ve a https://console.groq.com/keys
   - Revoca la key comprometida
   - Crea una nueva

4. **Verifica que `.env` esté en `.gitignore`**:
   ```bash
   # Ver .gitignore
   cat .gitignore | grep .env
   ```
   Debe mostrar: `.env`

---

## 🆘 Problemas Comunes

### ❌ "No module named 'groq'"

**Solución:**
```powershell
pip install groq
```

### ❌ "Invalid API key"

**Causas:**
1. Key copiada incorrectamente (espacios extra)
2. Key revocada en Groq console
3. Archivo `.env` no guardado

**Solución:**
```powershell
# Verificar contenido del .env
Get-Content .env | Select-String "GROQ"

# Debe mostrar: GROQ_API_KEY=gsk_...
```

### ❌ "Environment variable not found"

**Causa:** Servidor no recargó el `.env`

**Solución:**
```powershell
# Reiniciar servidor
.\iniciar_whatsapp.bat
```

---

## 📝 Resumen Visual

```
📁 c:\Users\kenne\Visual Studio Code\Agentes\
│
├── 📄 .env  ← PEGA TU API KEY AQUÍ
│   │
│   └── GROQ_API_KEY=gsk_tu_key_aqui
│
├── 🐍 raymundo.py  (lee la key automáticamente)
├── 🤖 whatsapp_server.py  (usa la key)
└── 🚀 iniciar_whatsapp.bat  (reinicia con nueva config)
```

### Flujo:

1. **Obtener key** → https://console.groq.com/keys
2. **Copiar** → `gsk_...`
3. **Pegar** → `.env` después de `GROQ_API_KEY=`
4. **Guardar** → Ctrl + S
5. **Reiniciar** → `.\iniciar_whatsapp.bat`
6. **¡Funciona!** → 14,400 requests/día gratis

---

## 🎯 Siguiente Paso

Una vez que pegues tu API key:

1. ✅ Guarda el archivo `.env`
2. ✅ Yo integraré el cliente de Groq en Raymundo
3. ✅ Configuraremos el fallback automático
4. ✅ ¡Tendrás 14,400 RPD gratis!

**¿Ya tienes tu API key de Groq, o necesitas ayuda para obtenerla?**
