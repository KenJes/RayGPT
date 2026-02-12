
# ALTERNATIVAS TTS EN ESPAÑOL MEXICANO (Código Abierto)

## Problema Actual
- **pyttsx3** con voces de Windows depende de que el usuario instale manualmente voces mexicanas (Raúl, Sabina)
- Si no están disponibles, hace fallback a voces en inglés o español de España

## Soluciones Recomendadas (Código Abierto)

### 1. **Coqui TTS** ⭐ RECOMENDADO
**Descripción**: Motor TTS de código abierto con voces pre-entrenadas de alta calidad  
**Licencia**: Mozilla Public License 2.0 (Open Source)

**Ventajas**:
- Voces neurales de alta calidad
- Modelos pre-entrenados en español latino
- Calidad similar a voces comerciales (Google, Amazon)
- 100% local (sin internet)
- Instalación simple

**Instalación**:
```bash
pip install TTS
```

**Uso en audio_handler.py**:
```python
from TTS.api import TTS

# Inicializar con modelo español
tts = TTS(model_name="tts_models/es/css10/vits")

# Generar audio
tts.tts_to_file(
    text="Hola, soy Raymundo",
    file_path="output.wav"
)
```

**Modelos Disponibles**:
- `tts_models/es/css10/vits` - Español neutro, voz femenina
- `tts_models/multilingual/multi-dataset/your_tts` - Multi-idioma, personalizable
- Puedes entrenar tu propio modelo con grabaciones

**Peso del modelo**: ~50-100 MB  
**Velocidad**: Medio (más lento que pyttsx3, más rápido que servicios cloud)

---

### 2. **Larynx** (Sucesor de Piper TTS)
**Descripción**: Motor TTS rápido basado en VITS, optimizado para Raspberry Pi  
**Licencia**: MIT (Open Source)

**Ventajas**:
- Muy rápido (optimizado para hardware limitado)
- Voces en español disponibles
- Consume poca RAM
- Calidad decente

**Instalación**:
```bash
pip install larynx
```

**Uso**:
```python
import larynx

# Cargar voz
voice = larynx.load_voice("es-mx")

# Generar audio
larynx.tts("Hola wey", voice=voice, output_file="audio.wav")
```

**Peso del modelo**: ~30-50 MB  
**Velocidad**: Rápido

---

### 3. **MozillaTTS** (Proyecto archivado pero funcional)
**Descripción**: Proyecto de Mozilla, base de Coqui TTS  
**Licencia**: MPL 2.0

**Nota**: Recomendamos usar Coqui TTS en su lugar (es la versión actualizada)

---

### 4. **Piper TTS con Voz Mexicana**
**Descripción**: Ya está integrado en tu código pero falta descargar voz mexicana  
**Licencia**: MIT

**Instalación de voz**:
1. Descargar modelo mexicano desde: https://github.com/rhasspy/piper/releases
2. Buscar: `es_MX-claude-medium.tar.gz`
3. Extraer en: `C:\Users\kenne\AppData\Local\Temp\raymundo_audio\voices\`

**Archivos necesarios**:
- `es_MX-claude-medium.onnx` (modelo)
- `es_MX-claude-medium.onnx.json` (config)

**Ya implementado**: Tu `audio_handler.py` ya busca voces Piper, solo falta descargar

---

### 5. **Festival TTS** (Clásico pero estable)
**Descripción**: Motor TTS clásico de Unix/Linux  
**Licencia**: MIT-style

**Ventajas**:
- Muy estable
- Bajo consumo de recursos
- Voces en español disponibles

**Desventajas**:
- Calidad de voz robótica (inferior a Coqui/Piper)
- Configuración más compleja en Windows

---

## Comparación Rápida

| Motor | Calidad | Velocidad | Peso Modelo | Dificultad Instalación | Acento Mexicano |
|-------|---------|-----------|-------------|------------------------|-----------------|
| **Coqui TTS** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ~100 MB | Fácil | ⭐⭐⭐⭐ (con fine-tuning) |
| **Piper/Larynx** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ~40 MB | Fácil | ⭐⭐⭐ |
| **pyttsx3 + Raúl** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 0 (del sistema) | Media* | ⭐⭐⭐⭐⭐ |
| **Festival** | ⭐⭐ | ⭐⭐⭐⭐ | ~20 MB | Difícil | ⭐⭐ |
| **gTTS** | ⭐⭐⭐ | ⭐⭐ | 0 (requiere internet) | Muy fácil | ⭐⭐⭐ |

*pyttsx3 + Raúl requiere instalación manual de voz en Windows

---

## Recomendación Final para Raymundo

### Opción A (Mejor calidad, más recursos):
```python
# Prioridad: Coqui TTS > pyttsx3 (Raúl) > Piper > gTTS

1. Coqui TTS con modelo español (100 MB, calidad excelente)
2. Fallback a pyttsx3 con Raúl si está instalado
3. Fallback a Piper con voz mexicana
4. Último fallback: gTTS (requiere internet)
```

### Opción B (Balance velocidad/calidad):
```python
# Prioridad: pyttsx3 (Raúl) > Piper > Coqui TTS > gTTS

1. pyttsx3 con Raúl (más rápido, 0 MB adicional)
2. Fallback a Piper con voz mexicana (rápido, 40 MB)
3. Fallback a Coqui TTS (mejor calidad, más lento)
4. Último fallback: gTTS
```

### Opción C (Solo local, sin internet):
```python
# Solo Coqui TTS o Piper (sin gTTS)

1. Coqui TTS o Piper exclusivamente
2. Error si no está disponible
```

---

## Implementación Recomendada (Coqui TTS)

### Paso 1: Instalar Coqui TTS
```bash
.\.venv\Scripts\python.exe -m pip install TTS
```

### Paso 2: Modificar audio_handler.py

Añadir al inicio del archivo:
```python
try:
    from TTS.api import TTS
    COQUI_AVAILABLE = True
except ImportError:
    COQUI_AVAILABLE = False
    print("⚠️ Coqui TTS no instalado. Instala con: pip install TTS")
```

Añadir método `_init_coqui` en clase AudioHandler:
```python
def _init_coqui(self):
    """Inicializa Coqui TTS con modelo español"""
    try:
        print("⏳ Cargando modelo Coqui TTS (puede tardar la primera vez)...")
        # Usar modelo español neutro (funciona para México)
        self.coqui_tts = TTS(model_name="tts_models/es/css10/vits")
        print("✅ Coqui TTS inicializado con voz en español")
    except Exception as e:
        print(f"⚠️ Error inicializando Coqui TTS: {e}")
        self.coqui_tts = None
```

Modificar `text_to_speech()` para añadir Coqui como prioridad alta:
```python
def text_to_speech(self, text: str, output_file: Optional[str] = None) -> Optional[str]:
    # 1. Intentar con pyttsx3 primero (más rápido si Raúl está instalado)
    if PYTTSX3_AVAILABLE and self.pyttsx3_engine:
        try:
            # ... código existente ...
        except Exception as e:
            print(f"⚠️ Error en pyttsx3: {e}, intentando con Coqui TTS...")
    
    # 2. Intentar con Coqui TTS (calidad superior)
    if COQUI_AVAILABLE and self.coqui_tts:
        try:
            if not output_file:
                output_file = str(self.audio_dir / f"tts_{os.getpid()}_{int(os.times()[4]*1000)}.wav")
            
            # Generar audio
            self.coqui_tts.tts_to_file(text=text, file_path=output_file)
            
            print(f"✅ Audio generado con Coqui TTS: {output_file}")
            return output_file
        
        except Exception as e:
            print(f"⚠️ Error en Coqui TTS: {e}, intentando con Piper...")
    
    # 3. Fallback a Piper (ya implementado)
    # ... código existente ...
    
    # 4. Último fallback a gTTS (ya implementado)
    # ... código existente ...
```

### Paso 3: Probar
```bash
.\.venv\Scripts\python.exe resources\core\audio_handler.py
```

---

## Entrenamiento de Voz Personalizada (Avanzado)

Si quieres una voz 100% mexicana personalizada:

### 1. Grabar muestras (10-30 minutos de audio)
- Frases variadas en español mexicano
- Buena calidad de grabación
- Voz masculina (para Raymundo)

### 2. Entrenar con Coqui TTS
```bash
tts-train --config_path <config.json> \
          --dataset_path <grabaciones/> \
          --output_path <modelo_raymundo/>
```

### 3. Usar modelo personalizado
```python
tts = TTS(model_path="modelo_raymundo/best_model.pth")
```

**Tiempo de entrenamiento**: 2-8 horas (GPU recomendado)

---

## Archivos a Modificar para Implementar Coqui TTS

1. `resources/core/audio_handler.py` - Añadir soporte Coqui TTS
2. `requirements.txt` - Añadir `TTS>=0.22.0`
3. `README.md` - Documentar nueva dependencia

---

## Preguntas Frecuentes

### ¿Coqui TTS funciona sin internet?
**Sí**, una vez descargado el modelo (primera ejecución), funciona 100% offline.

### ¿Cuánto espacio ocupa?
- Coqui TTS: ~100 MB (modelo español)
- Piper: ~40 MB
- pyttsx3: 0 MB (usa voces del sistema)

### ¿Qué es más rápido?
1. pyttsx3 (instantáneo)
2. Piper/Larynx (muy rápido)
3. Coqui TTS (medio, ~1-3 segundos por frase)
4. gTTS (lento, depende de internet)

### ¿Puedo usar acento mexicano específico?
Con **Coqui TTS** + entrenamiento personalizado: **Sí** (requiere grabaciones)  
Con **pyttsx3 + Raúl**: **Sí** (si Windows tiene la voz instalada)  
Con **Piper**: **Parcial** (depende del modelo disponible)

---

## Conclusión

Para Raymundo con personalidad "puteado" y acento mexicano:

**Mejor opción actual**: 
1. Instalar voz **Raúl** en Windows (gratuito, 0 MB adicional, muy rápido)
2. Si no está disponible, usar **Coqui TTS** (~100 MB, calidad excelente)
3. Fallback a **gTTS** (requiere internet)

**Implementación mínima**: Solo añadir 15-20 líneas de código para Coqui TTS en `audio_handler.py`

