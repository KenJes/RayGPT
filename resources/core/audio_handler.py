"""
🎙️ MÓDULO DE AUDIO - RAYMUNDO
Gestión de texto a voz y voz a texto
- Piper TTS: Síntesis de voz local y rápida
- OpenAI Whisper: Reconocimiento de voz

Autor: Sistema IA
Versión: 1.0
"""

import os
import wave
import tempfile
import subprocess
import threading
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

try:
    import piper
    from piper import PiperVoice
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False
    print("⚠️ piper-tts no instalado. Instala con: pip install piper-tts")

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("⚠️ openai-whisper no instalado. Instala con: pip install openai-whisper")

try:
    import sounddevice as sd
    import soundfile as sf
    AUDIO_IO_AVAILABLE = True
except ImportError:
    AUDIO_IO_AVAILABLE = False
    print("⚠️ sounddevice/soundfile no instalados. Instala con: pip install sounddevice soundfile")

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("⚠️ gTTS no instalado. Instala con: pip install gtts")

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    print("⚠️ pyttsx3 no instalado. Instala con: pip install pyttsx3")


class AudioHandler:
    """Maneja todas las operaciones de audio del agente"""
    
    def __init__(self, audio_dir: Optional[Path] = None, voice_config: dict = None):
        """
        Inicializa el manejador de audio
        
        Args:
            audio_dir: Directorio para archivos de audio temporales
            voice_config: Configuración de voz {'engine': 'pyttsx3|gtts', 'gender': 'male|female', 'rate': 150-200}
        """
        self.audio_dir = audio_dir or Path(tempfile.gettempdir()) / "raymundo_audio"
        self.audio_dir.mkdir(exist_ok=True, parents=True)
        
        # Configuración de voz por defecto
        self.voice_config = voice_config or {
            'engine': 'pyttsx3',  # pyttsx3 (mejor calidad) > gtts > piper
            'gender': 'male',      # male | female
            'rate': 180            # Velocidad: 150=lento, 180=normal, 200=rápido
        }
        
        # Estado de grabación
        self.is_recording = False
        self.recording_thread = None
        self.recorded_frames = []
        
        # Inicializar componentes
        self.piper_voice = None
        self.whisper_model = None
        self.pyttsx3_engine = None
        
        if PYTTSX3_AVAILABLE:
            self._init_pyttsx3()
        
        if PIPER_AVAILABLE:
            self._init_piper()
        
        if WHISPER_AVAILABLE:
            self._init_whisper()
    
    def _init_pyttsx3(self):
        """Inicializa el motor pyttsx3 con voces del sistema"""
        try:
            self.pyttsx3_engine = pyttsx3.init()
            
            # Configurar velocidad
            rate = self.voice_config.get('rate', 180)
            self.pyttsx3_engine.setProperty('rate', rate)
            
            # Configurar volumen
            self.pyttsx3_engine.setProperty('volume', 0.9)
            
            # Buscar voz según género preferido
            voices = self.pyttsx3_engine.getProperty('voices')
            gender_pref = self.voice_config.get('gender', 'male').lower()
            
            selected_voice = None
            
            # Buscar voz en español mexicano primero (prioridad)
            for voice in voices:
                voice_name = voice.name.lower()
                voice_id_lower = voice.id.lower()
                
                # Detectar voces mexicanas específicas (Raúl, Sabina)
                if 'raul' in voice_name or 'raul' in voice_id_lower or 'sabina' in voice_name or 'sabina' in voice_id_lower:
                    is_male = 'raul' in voice_name or 'raul' in voice_id_lower
                    is_female = 'sabina' in voice_name or 'sabina' in voice_id_lower
                    
                    if gender_pref == 'male' and is_male:
                        selected_voice = voice.id
                        print(f"✅ Voz masculina en español mexicano seleccionada: {voice.name}")
                        break
                    elif gender_pref == 'female' and is_female:
                        selected_voice = voice.id
                        print(f"✅ Voz femenina en español mexicano seleccionada: {voice.name}")
                        break
            
            # Si no hay mexicanas, buscar otras voces en español
            if not selected_voice:
                for voice in voices:
                    voice_name = voice.name.lower()
                    
                    # Detectar voces en español (cualquier variante)
                    if 'spanish' in voice_name or 'español' in voice_name or 'helena' in voice_name or 'pablo' in voice_name:
                        # Detectar género por nombre
                        is_male = any(keyword in voice_name for keyword in ['male', 'pablo', 'jorge', 'diego', 'carlos'])
                        is_female = any(keyword in voice_name for keyword in ['female', 'helena', 'monica', 'lucia'])
                        
                        if gender_pref == 'male' and is_male:
                            selected_voice = voice.id
                            print(f"✅ Voz masculina en español seleccionada: {voice.name}")
                            break
                        elif gender_pref == 'female' and is_female:
                            selected_voice = voice.id
                            print(f"✅ Voz femenina en español seleccionada: {voice.name}")
                            break
            
            # Si no hay español, buscar en inglés del género preferido
            if not selected_voice:
                for voice in voices:
                    voice_name = voice.name.lower()
                    is_male = 'male' in voice_name or 'david' in voice_name or 'mark' in voice_name
                    is_female = 'female' in voice_name or 'zira' in voice_name or 'susan' in voice_name
                    
                    if gender_pref == 'male' and is_male:
                        selected_voice = voice.id
                        print(f"⚠️ Voz masculina en inglés seleccionada: {voice.name} (no hay español masculino)")
                        break
                    elif gender_pref == 'female' and is_female:
                        selected_voice = voice.id
                        print(f"⚠️ Voz femenina en inglés seleccionada: {voice.name} (no hay español femenino)")
                        break
            
            # Aplicar voz seleccionada
            if selected_voice:
                self.pyttsx3_engine.setProperty('voice', selected_voice)
            else:
                print("⚠️ Usando voz por defecto del sistema")
            
            print(f"✅ pyttsx3 inicializado (Velocidad: {rate}, Género: {gender_pref})")
            
        except Exception as e:
            print(f"⚠️ Error inicializando pyttsx3: {e}")
            self.pyttsx3_engine = None
    
    def _init_piper(self):
        """Inicializa el modelo Piper TTS"""
        try:
            # Buscar voz en español (puedes descargar voces de https://github.com/rhasspy/piper/releases)
            # Por defecto intentamos usar una voz del sistema
            voices_dir = self.audio_dir / "voices"
            voices_dir.mkdir(exist_ok=True)
            
            # Intentar cargar voz española si existe
            spanish_voice = voices_dir / "es_ES-claude-medium.onnx"
            
            if spanish_voice.exists():
                self.piper_voice = PiperVoice.load(str(spanish_voice))
                print("✅ Piper TTS inicializado con voz en español")
            else:
                print("⚠️ Voz en español no encontrada. Descarga desde:")
                print("   https://github.com/rhasspy/piper/releases/tag/v1.2.0")
                print(f"   y guarda en: {voices_dir}")
        except Exception as e:
            print(f"⚠️ Error inicializando Piper: {e}")
            self.piper_voice = None
    
    def _init_whisper(self):
        """Inicializa el modelo Whisper para STT"""
        try:
            # Cargar modelo base (balance entre velocidad y precisión)
            # Opciones: tiny, base, small, medium, large
            print("⏳ Cargando modelo Whisper (puede tardar la primera vez)...")
            self.whisper_model = whisper.load_model("base")
            print("✅ Whisper STT inicializado")
        except Exception as e:
            print(f"⚠️ Error inicializando Whisper: {e}")
            self.whisper_model = None
    
    def text_to_speech(self, text: str, output_file: Optional[str] = None) -> Optional[str]:
        """
        Convierte texto a audio usando el mejor motor disponible
        Prioridad: pyttsx3 (mejor calidad) > Piper (local rápido) > gTTS (fallback)
        
        Args:
            text: Texto a convertir
            output_file: Ruta del archivo de salida (opcional)
        
        Returns:
            Ruta del archivo de audio generado o None si falló
        """
        # 1. Intentar con pyttsx3 primero (mejor calidad, voces del sistema)
        if PYTTSX3_AVAILABLE and self.pyttsx3_engine:
            try:
                if not output_file:
                    output_file = str(self.audio_dir / f"tts_{os.getpid()}_{int(os.times()[4]*1000)}.wav")
                
                # Generar audio
                self.pyttsx3_engine.save_to_file(text, output_file)
                self.pyttsx3_engine.runAndWait()
                
                print(f"✅ Audio generado con pyttsx3: {output_file}")
                return output_file
            
            except Exception as e:
                print(f"⚠️ Error en pyttsx3: {e}, intentando con Piper...")
        
        # 2. Intentar con Piper (más rápido y local si tiene modelo)
        if PIPER_AVAILABLE and self.piper_voice:
            try:
                if not output_file:
                    output_file = str(self.audio_dir / f"tts_{os.getpid()}_{int(os.times()[4]*1000)}.wav")
                
                # Generar audio
                with wave.open(output_file, 'wb') as wav_file:
                    self.piper_voice.synthesize(text, wav_file)
                
                print(f"✅ Audio generado con Piper: {output_file}")
                return output_file
            
            except Exception as e:
                print(f"⚠️ Error en Piper TTS: {e}, intentando con gTTS...")
        
        # 3. Fallback a gTTS (requiere internet pero siempre funciona)
        if GTTS_AVAILABLE:
            try:
                if not output_file:
                    output_file = str(self.audio_dir / f"tts_{os.getpid()}_{int(os.times()[4]*1000)}.mp3")
                
                # Generar audio con gTTS
                tts = gTTS(text=text, lang='es', slow=False)
                tts.save(output_file)
                
                print(f"✅ Audio generado con gTTS: {output_file}")
                return output_file
            
            except Exception as e:
                print(f"❌ Error en gTTS: {e}")
                return None
        
        print("❌ No hay sistema TTS disponible (ni pyttsx3 ni Piper ni gTTS)")
        return None
    
    def play_audio(self, audio_file: str) -> bool:
        """
        Reproduce un archivo de audio
        
        Args:
            audio_file: Ruta del archivo a reproducir
        
        Returns:
            True si se reprodujo correctamente, False en caso contrario
        """
        if not AUDIO_IO_AVAILABLE:
            print("❌ sounddevice no disponible para reproducción")
            return False
        
        try:
            # Leer archivo de audio
            data, samplerate = sf.read(audio_file)
            
            # Reproducir
            sd.play(data, samplerate)
            sd.wait()  # Esperar a que termine
            
            return True
        
        except Exception as e:
            print(f"❌ Error reproduciendo audio: {e}")
            return False
    
    def start_recording(self, duration: int = 10, sample_rate: int = 16000) -> bool:
        """
        Inicia la grabación de audio
        
        Args:
            duration: Duración máxima en segundos
            sample_rate: Tasa de muestreo
        
        Returns:
            True si inició correctamente
        """
        if not AUDIO_IO_AVAILABLE:
            print("❌ sounddevice no disponible para grabación")
            return False
        
        if self.is_recording:
            print("⚠️ Ya hay una grabación en curso")
            return False
        
        self.is_recording = True
        self.recorded_frames = []
        
        def record():
            try:
                print(f"🎙️ Grabando audio ({duration}s máximo)...")
                recording = sd.rec(
                    int(duration * sample_rate),
                    samplerate=sample_rate,
                    channels=1,
                    dtype='float32'
                )
                sd.wait()
                self.recorded_frames = recording
                print("✅ Grabación completada")
            except Exception as e:
                print(f"❌ Error en grabación: {e}")
            finally:
                self.is_recording = False
        
        self.recording_thread = threading.Thread(target=record, daemon=True)
        self.recording_thread.start()
        return True
    
    def stop_recording(self) -> Optional[str]:
        """
        Detiene la grabación y guarda el archivo
        
        Returns:
            Ruta del archivo grabado o None si falló
        """
        if not self.is_recording:
            print("⚠️ No hay grabación activa")
            return None
        
        # Detener grabación
        sd.stop()
        self.is_recording = False
        
        if self.recording_thread:
            self.recording_thread.join(timeout=2)
        
        if len(self.recorded_frames) == 0:
            print("⚠️ No se grabó audio")
            return None
        
        try:
            # Guardar archivo
            output_file = str(self.audio_dir / f"recording_{os.getpid()}_{int(os.times()[4]*1000)}.wav")
            sf.write(output_file, self.recorded_frames, 16000)
            
            print(f"✅ Audio guardado: {output_file}")
            return output_file
        
        except Exception as e:
            print(f"❌ Error guardando grabación: {e}")
            return None
    
    def speech_to_text(self, audio_file: str, language: str = "es") -> Optional[str]:
        """
        Convierte audio a texto usando Whisper
        
        Args:
            audio_file: Ruta del archivo de audio
            language: Código de idioma (es, en, etc.)
        
        Returns:
            Texto transcrito o None si falló
        """
        if not WHISPER_AVAILABLE or not self.whisper_model:
            print("❌ Whisper STT no disponible")
            return None
        
        try:
            print("⏳ Transcribiendo audio...")
            
            # Transcribir
            result = self.whisper_model.transcribe(
                audio_file,
                language=language,
                fp16=False  # Usar fp32 para compatibilidad
            )
            
            text = result["text"].strip()
            
            if text:
                print(f"✅ Transcripción: {text}")
            else:
                print("⚠️ Transcripción: (vacía - no se detectó habla)")
            
            return text if text else None
        
        except Exception as e:
            print(f"❌ Error en speech_to_text: {e}")
            return None
    
    def process_voice_message(self, audio_file: str) -> Optional[str]:
        """
        Procesa un mensaje de voz completo (STT)
        
        Args:
            audio_file: Ruta del archivo de audio
        
        Returns:
            Texto transcrito o None si falló
        """
        return self.speech_to_text(audio_file)
    
    def generate_voice_response(self, text: str) -> Optional[str]:
        """
        Genera una respuesta en audio (TTS)
        
        Args:
            text: Texto a convertir
        
        Returns:
            Ruta del archivo de audio generado o None si falló
        """
        return self.text_to_speech(text)
    
    def cleanup(self):
        """Limpia archivos temporales de audio"""
        try:
            import shutil
            shutil.rmtree(self.audio_dir, ignore_errors=True)
            self.audio_dir.mkdir(exist_ok=True)
            print("✅ Archivos de audio temporales limpiados")
        except Exception as e:
            print(f"⚠️ Error limpiando archivos: {e}")
    
    def is_tts_available(self) -> bool:
        """Verifica si TTS está disponible (pyttsx3, Piper o gTTS)"""
        return PYTTSX3_AVAILABLE or (PIPER_AVAILABLE and self.piper_voice is not None) or GTTS_AVAILABLE
    
    def is_stt_available(self) -> bool:
        """Verifica si STT está disponible"""
        return WHISPER_AVAILABLE and self.whisper_model is not None
    
    def get_status(self) -> dict:
        """Retorna el estado del manejador de audio"""
        return {
            "tts_available": self.is_tts_available(),
            "stt_available": self.is_stt_available(),
            "audio_io_available": AUDIO_IO_AVAILABLE,
            "is_recording": self.is_recording,
            "audio_dir": str(self.audio_dir)
        }


# Instancia global (singleton)
_audio_handler_instance = None

def get_audio_handler(voice_config: dict = None) -> AudioHandler:
    """Retorna la instancia global del manejador de audio
    
    Args:
        voice_config: {'engine': 'pyttsx3|gtts', 'gender': 'male|female', 'rate': 150-200}
    """
    global _audio_handler_instance
    if _audio_handler_instance is None:
        _audio_handler_instance = AudioHandler(voice_config=voice_config)
    return _audio_handler_instance
    return _audio_handler_instance


# Ejemplo de uso
if __name__ == "__main__":
    # Test básico
    handler = AudioHandler()
    
    print("\n📊 Estado del sistema de audio:")
    status = handler.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Test TTS
    if handler.is_tts_available():
        print("\n🔊 Probando TTS...")
        audio_file = handler.text_to_speech("Hola, soy Raymundo. ¿En qué puedo ayudarte?")
        if audio_file:
            print(f"Audio generado: {audio_file}")
            # handler.play_audio(audio_file)
    
    # Test STT
    if handler.is_stt_available():
        print("\n🎙️ STT disponible para pruebas")
