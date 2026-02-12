# 🔐 ARCHIVOS EJEMPLO - CONFIGURACIÓN

Este directorio contiene archivos de ejemplo para configurar rAImundoGPT.
Los archivos reales con credenciales deben estar en la carpeta `config/` (que está en .gitignore).

## Archivos necesarios

### 1. `.env`
Copia `env.example` a `config/.env` y completa tus API keys:
```bash
cp examples/env.example config/.env
```

### 2. `google-credentials.json`
Descarga tus credenciales de Google Cloud y guárdalas en `config/`:
- Ve a: https://console.cloud.google.com/apis/credentials
- Crea una Service Account
- Descarga el JSON
- Guárdalo como: `config/google-credentials.json`

### 3. OAuth (opcional)
Si usas OAuth en lugar de Service Account:
```bash
cp examples/oauth-credentials.example.json config/oauth-credentials.json
```

## Estructura de carpetas

```
├── config/          ← Aquí van tus credenciales REALES (ignorado por git)
│   ├── .env
│   ├── google-credentials.json
│   └── token.json (generado automáticamente)
│
├── data/            ← Datos de runtime (ignorado por git)
│   ├── memoria_agente.json
│   └── metrics.json
│
└── examples/        ← Ejemplos para copiar (sí se sube a GitHub)
    ├── env.example
    └── oauth-credentials.example.json
```

## ⚠️ IMPORTANTE

**NUNCA** subas a GitHub archivos que contengan:
- API Keys
- Tokens
- Contraseñas
- Credenciales de servicios
- Datos personales

Todos estos deben estar en `config/` o `data/` que están protegidos por `.gitignore`.
