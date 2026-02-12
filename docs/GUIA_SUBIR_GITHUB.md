# 🚀 Guía para Subir rAImundoGPT a GitHub de Forma Segura

Esta guía te ayuda a subir tu proyecto a GitHub **sin exponer tus API keys ni credenciales**.

---

## ✅ Pre-requisitos Completados

El proyecto ya está preparado con:
- ✅ `.gitignore` configurado (protege credenciales)
- ✅ `config/.env.example` creado (plantilla pública)
- ✅ Archivos de test eliminados
- ✅ Caché de Python limpiado
- ✅ `.env` duplicado eliminado

---

## 🔒 Verificación de Seguridad

### **1. Archivos Protegidos** (NO se subirán)

El `.gitignore` ya protege estos archivos críticos:
```
✅ config/.env                    # TUS API KEYS
✅ config/google-credentials.json # Credenciales Google
✅ resources/data/memoria_agente.json  # Historial personal
✅ resources/data/metrics.json    # Estadísticas
✅ resources/data/token.json      # OAuth tokens
✅ whatsapp_session/              # Sesión de WhatsApp
✅ .wwebjs_cache/                 # Caché de WhatsApp
✅ __pycache__/                   # Caché Python
✅ .venv/                         # Entorno virtual
```

### **2. Verificar ANTES del Primer Commit**

```bash
# Ver qué archivos se subirán
git status

# Ver qué archivos están ignorados
git ls-files --others --ignored --exclude-standard

# NUNCA debe aparecer:
# - config/.env
# - config/google-credentials.json
# - whatsapp_session/
```

---

## 📤 Pasos para Subir a GitHub

### **Paso 1: Crear Repositorio en GitHub**

1. Ve a: https://github.com/new
2. Nombre: `raimundo-gpt` (o el que prefieras)
3. Descripción: "Agente IA personal con WhatsApp, Google Workspace y múltiples modelos"
4. **Visibilidad:**
   - ✅ **Public**: Si quieres compartirlo
   - ⚠️ **Private**: Si tiene datos sensibles
5. **NO** marques "Add README" ni ".gitignore" (ya los tienes)
6. Click en **"Create repository"**

### **Paso 2: Inicializar Git Local**

```bash
# Si es la primera vez con Git en este proyecto
git init
git add .
git commit -m "Initial commit: rAImundoGPT v2.0"
```

### **Paso 3: Conectar con GitHub**

```bash
# Cambiar "tu-usuario" por tu nombre de usuario de GitHub
git remote add origin https://github.com/tu-usuario/raimundo-gpt.git
git branch -M main
git push -u origin main
```

**Si te pide credenciales:**
- Usuario: tu_usuario_github
- Password: **Personal Access Token** (crea uno en: https://github.com/settings/tokens)

### **Paso 4: Verificar en GitHub**

1. Ve a tu repositorio: `https://github.com/tu-usuario/raimundo-gpt`
2. Verifica que **NO aparezcan:**
   - ❌ `config/.env`
   - ❌ `google-credentials.json`
   - ❌ `whatsapp_session/`
3. Verifica que **SÍ aparezcan:**
   - ✅ `config/.env.example`
   - ✅ `README.md`
   - ✅ `raymundo.py`
   - ✅ `.gitignore`

---

## 🛡️ Medidas de Seguridad Adicionales

### **Si Accidentalmente Subes Credenciales**

⚠️ **¡ALERTA!** Si por error subes `config/.env`:

1. **Revocar API Keys INMEDIATAMENTE:**
   - Groq: https://console.groq.com/keys
   - GitHub: https://github.com/settings/tokens
   - Google: https://console.cloud.google.com/

2. **Eliminar del historial de Git:**
   ```bash
   # Eliminar archivo del último commit
   git rm --cached config/.env
   git commit --amend -m "Remove sensitive files"
   git push --force
   
   # Si está en commits antiguos, usar BFG Repo-Cleaner
   # https://rtyley.github.io/bfg-repo-cleaner/
   ```

3. **Generar nuevas API Keys**

### **GitHub Secret Scanning**

GitHub automáticamente escanea repositorios públicos buscando:
- API keys expuestas
- Tokens de acceso
- Contraseñas

Si detecta algo, te enviará una alerta por email.

---

## 📋 Checklist Final

Antes de hacer `git push`, verifica:

- [ ] `git status` NO muestra `config/.env`
- [ ] `git status` NO muestra `google-credentials.json`
- [ ] `git status` NO muestra archivos en `whatsapp_session/`
- [ ] Existe `config/.env.example` (SIN tus keys reales)
- [ ] `.gitignore` incluye todos los archivos sensibles
- [ ] README.md está actualizado
- [ ] Has probado que el proyecto funciona localmente

---

## 🔄 Flujo de Trabajo Recomendado

### **Para Nuevos Colaboradores**

1. **Clonar repo:**
   ```bash
   git clone https://github.com/tu-usuario/raimundo-gpt.git
   cd raimundo-gpt
   ```

2. **Configurar entorno:**
   ```bash
   # Copiar plantilla
   cp config/.env.example config/.env
   
   # Editar y agregar TUS API keys
   nano config/.env
   ```

3. **Instalar dependencias:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   ```

### **Para Commits Futuros**

```bash
# Verificar cambios
git status
git diff

# Agregar archivos
git add .

# NUNCA uses: git add -f config/  ❌

# Commit
git commit -m "Descripción del cambio"

# Push
git push origin main
```

---

## 🌟 Buenas Prácticas

### **Commits Descriptivos**
```bash
✅ git commit -m "feat: Agregar soporte para voz Raúl"
✅ git commit -m "fix: Corregir error en GroqClient.__init__"
✅ git commit -m "docs: Actualizar guía de instalación"
✅ git commit -m "refactor: Eliminar código duplicado en audio_handler"

❌ git commit -m "cambios"
❌ git commit -m "fix"
```

### **Branches para Features**
```bash
# Crear nueva rama para feature
git checkout -b feature/nueva-funcionalidad

# Trabajar en la rama
git add .
git commit -m "feat: Agregar nueva funcionalidad"

# Mergear a main
git checkout main
git merge feature/nueva-funcionalidad
git push origin main
```

### **Mantener .gitignore Actualizado**

Si agregas nuevos archivos sensibles:
```bash
# Editar .gitignore
echo "nuevo_archivo_secreto.json" >> .gitignore

# Verificar que funciona
git status  # nuevo_archivo_secreto.json NO debe aparecer
```

---

## 🆘 Problemas Comunes

### **Error: "src refspec main does not match any"**
```bash
# Crear rama main si no existe
git branch -M main
```

### **Error: "remote origin already exists"**
```bash
# Cambiar URL del remote
git remote set-url origin https://github.com/tu-usuario/raimundo-gpt.git
```

### **Error: "Updates were rejected"**
```bash
# Hacer pull primero
git pull origin main --rebase
git push origin main
```

### **Ver qué archivos están siendo ignorados**
```bash
git ls-files --others --ignored --exclude-standard
```

---

## 📞 Soporte

Si encuentras problemas:
1. Revisa el `.gitignore`
2. Ejecuta `git status` para verificar
3. Consulta la documentación de Git: https://git-scm.com/doc
4. GitHub Docs: https://docs.github.com/

---

## ✅ Resumen: Comandos Completos

```bash
# 1. Verificar estado
git status

# 2. Inicializar (si es primera vez)
git init
git add .
git commit -m "Initial commit: rAImundoGPT v2.0"

# 3. Conectar con GitHub
git remote add origin https://github.com/TU-USUARIO/raimundo-gpt.git
git branch -M main
git push -u origin main

# 4. Verificar en GitHub que NO se subieron credenciales

# 5. Para futuros cambios
git add .
git commit -m "Descripción del cambio"
git push origin main
```

---

<div align="center">
  <strong>🎉 ¡Listo! Tu proyecto está seguro en GitHub</strong>
</div>

---

**RECUERDA:** 
- ✅ `config/.env.example` se sube (plantilla SIN keys)
- ❌ `config/.env` NUNCA se sube (tus keys reales)
