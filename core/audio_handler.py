"""
🎙️ MÓDULO DE AUDIO - REINA / RAYMUNDO
Gestión de texto a voz y voz a texto
- Edge TTS: Voces neurales de Microsoft (DaliaNeural es-MX) — calidad TikTok/CapCut
- pyttsx3: Voces del sistema (SAPI5 + OneCore)
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

try:
    import edge_tts
    import asyncio
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False


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
            'engine': 'edge-tts',  # edge-tts (neural, mejor) > pyttsx3 > piper > gtts
            'gender': 'female',    # female=Dalia | male=Jorge (para edge-tts)
            'rate': 180            # Velocidad: 150=lento, 180=normal, 200=rápido
        }
        
        # Voces neurales de Edge TTS (es-MX)
        self._edge_voice_es = None
        self._edge_voice_en = None
        if EDGE_TTS_AVAILABLE:
            gender = self.voice_config.get('gender', 'female').lower()
            if gender == 'female':
                self._edge_voice_es = 'es-MX-DaliaNeural'
                self._edge_voice_en = 'en-US-JennyNeural'
            else:
                self._edge_voice_es = 'es-MX-JorgeNeural'
                self._edge_voice_en = 'en-US-GuyNeural'
            print(f"✅ Edge TTS configurado: {self._edge_voice_es}")
        
        # Estado de grabación
        self.is_recording = False
        self.recording_thread = None
        self.recorded_frames = []
        
        # Inicializar componentes
        self.piper_voice = None
        self.whisper_model = None
        self.pyttsx3_engine = None
        self.voice_es = None  # Voice ID para español
        self.voice_en = None  # Voice ID para inglés
        self._voice_es_is_onecore = False  # Voces OneCore no reportan bien en getProperty
        self._tts_lock = threading.Lock()  # Proteger pyttsx3 contra acceso concurrente
        
        if PYTTSX3_AVAILABLE:
            self._init_pyttsx3()
        
        if PIPER_AVAILABLE:
            self._init_piper()
        
        if WHISPER_AVAILABLE:
            self._init_whisper()
    
    def _init_pyttsx3(self):
        """Inicializa el motor pyttsx3 con voces del sistema (SAPI5 + OneCore)"""
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
            
            # ═══ DESCUBRIR VOCES ONECORE (Windows) ═══
            # pyttsx3 solo lista SAPI5; OneCore tiene más voces (e.g. Raúl MX)
            onecore_voices = self._discover_onecore_voices()
            
            selected_voice = None
            
            # ═══ BUSCAR VOZ EN ESPAÑOL ═══
            # Prioridad: 1) SAPI5 género preferido → 2) OneCore género preferido
            #             3) SAPI5 cualquier español → 4) OneCore cualquier español
            
            # --- Paso 1: SAPI5 español, género preferido ---
            for voice in voices:
                voice_name = voice.name.lower()
                voice_id_lower = voice.id.lower()
                
                if 'raul' in voice_name or 'raul' in voice_id_lower or 'sabina' in voice_name or 'sabina' in voice_id_lower:
                    is_male = 'raul' in voice_name or 'raul' in voice_id_lower
                    is_female = 'sabina' in voice_name or 'sabina' in voice_id_lower
                    
                    if gender_pref == 'male' and is_male:
                        selected_voice = voice.id
                        print(f"✅ Voz masculina en español mexicano (SAPI5): {voice.name}")
                        break
                    elif gender_pref == 'female' and is_female:
                        selected_voice = voice.id
                        print(f"✅ Voz femenina en español mexicano (SAPI5): {voice.name}")
                        break
            
            # --- Paso 2: OneCore español, género preferido ---
            if not selected_voice and onecore_voices:
                for oc_name, oc_id in onecore_voices:
                    name_l = oc_name.lower()
                    id_l = oc_id.lower()
                    is_spanish = 'esmx' in id_l or 'es-mx' in id_l or 'es_es' in id_l or 'es-es' in id_l
                    if not is_spanish:
                        continue
                    is_male = 'raul' in name_l or 'raul' in id_l
                    is_female = 'sabina' in name_l or 'sabina' in id_l
                    
                    if gender_pref == 'male' and is_male:
                        selected_voice = oc_id
                        self._voice_es_is_onecore = True
                        print(f"✅ Voz masculina en español mexicano (OneCore): {oc_name}")
                        break
                    elif gender_pref == 'female' and is_female:
                        selected_voice = oc_id
                        self._voice_es_is_onecore = True
                        print(f"✅ Voz femenina en español mexicano (OneCore): {oc_name}")
                        break
            
            # --- Paso 3: SAPI5 cualquier español (ignorar género) ---
            if not selected_voice:
                for voice in voices:
                    voice_name = voice.name.lower()
                    voice_id_lower = voice.id.lower()
                    is_spanish = any(kw in voice_name or kw in voice_id_lower for kw in
                                     ['spanish', 'español', 'es-mx', 'es_mx', 'es-es',
                                      'raul', 'sabina', 'helena', 'pablo', 'jorge'])
                    if is_spanish:
                        selected_voice = voice.id
                        print(f"✅ Voz en español seleccionada (SAPI5, otro género): {voice.name}")
                        break
            
            # --- Paso 4: OneCore cualquier español ---
            if not selected_voice and onecore_voices:
                for oc_name, oc_id in onecore_voices:
                    id_l = oc_id.lower()
                    if 'esmx' in id_l or 'es-mx' in id_l or 'es_es' in id_l or 'es-es' in id_l:
                        selected_voice = oc_id
                        self._voice_es_is_onecore = True
                        print(f"✅ Voz en español seleccionada (OneCore, otro género): {oc_name}")
                        break
            
            # Guardar voz en español
            self.voice_es = selected_voice
            
            # ═══ BUSCAR VOZ EN INGLÉS ═══
            english_voice = None
            for voice in voices:
                voice_name = voice.name.lower()
                is_male = 'male' in voice_name or 'david' in voice_name or 'mark' in voice_name
                is_female = 'female' in voice_name or 'zira' in voice_name or 'susan' in voice_name
                is_english = 'english' in voice_name or 'david' in voice_name or 'zira' in voice_name or 'mark' in voice_name or 'susan' in voice_name
                
                if not is_english:
                    continue
                
                if gender_pref == 'male' and is_male:
                    english_voice = voice.id
                    print(f"✅ Voz masculina en inglés encontrada: {voice.name}")
                    break
                elif gender_pref == 'female' and is_female:
                    english_voice = voice.id
                    print(f"✅ Voz femenina en inglés encontrada: {voice.name}")
                    break
            
            # Si no encontró del género preferido, buscar cualquier voz inglesa
            if not english_voice:
                for voice in voices:
                    voice_name = voice.name.lower()
                    if 'english' in voice_name or 'david' in voice_name or 'zira' in voice_name:
                        english_voice = voice.id
                        print(f"⚠️ Voz en inglés seleccionada (género no preferido): {voice.name}")
                        break
            
            self.voice_en = english_voice
            
            # Si no hay español, usar la voz en inglés como fallback
            if not selected_voice and english_voice:
                selected_voice = english_voice
                self.voice_es = english_voice
                print(f"⚠️ Usando voz en inglés como fallback (no hay español)")
            
            # Aplicar voz seleccionada (español por defecto)
            if selected_voice:
                self.pyttsx3_engine.setProperty('voice', selected_voice)
            else:
                print("⚠️ Usando voz por defecto del sistema")
            
            print(f"✅ pyttsx3 inicializado (Velocidad: {rate}, Género: {gender_pref})")
            print(f"   • Voz ES: {'Sí' if self.voice_es else 'No'} | Voz EN: {'Sí' if self.voice_en else 'No'}")
            
        except Exception as e:
            print(f"⚠️ Error inicializando pyttsx3: {e}")
    
    @staticmethod
    def _discover_onecore_voices():
        """Descubre voces OneCore de Windows que pyttsx3 no lista por defecto."""
        results = []
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens",
            )
            i = 0
            while True:
                try:
                    token_name = winreg.EnumKey(key, i)
                    token_path = rf"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens\{token_name}"
                    full_id = rf"HKEY_LOCAL_MACHINE\{token_path}"
                    # Leer nombre legible
                    try:
                        sub = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, token_path)
                        display_name = winreg.QueryValueEx(sub, "")[0]
                    except Exception:
                        display_name = token_name
                    results.append((display_name, full_id))
                    i += 1
                except OSError:
                    break
        except Exception:
            pass  # No es Windows o no hay voces OneCore
        return results
    
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
    
    def _tts_edge(self, text: str, output_file: str, language: str = 'es') -> Optional[str]:
        """Genera audio con Edge TTS (voces neurales, requiere internet)."""
        voice = self._edge_voice_en if language == 'en' else self._edge_voice_es
        if not voice:
            return None
        try:
            communicate = edge_tts.Communicate(text, voice)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, communicate.save(output_file)).result()
            else:
                asyncio.run(communicate.save(output_file))
            return output_file
        except Exception as e:
            print(f"⚠️ Error en Edge TTS: {e}")
            return None

    def text_to_speech(self, text: str, output_file: Optional[str] = None, language: str = 'es') -> Optional[str]:
        """
        Convierte texto a audio usando el mejor motor disponible
        Prioridad: Edge TTS (neural) > pyttsx3 > Piper (local) > gTTS (fallback)
        
        Args:
            text: Texto a convertir
            output_file: Ruta del archivo de salida (opcional)
            language: Idioma del texto ('es' o 'en'). Determina qué voz usar.
        
        Returns:
            Ruta del archivo de audio generado o None si falló
        """
        # 1. Intentar con Edge TTS primero (voces neurales, calidad TikTok)
        if EDGE_TTS_AVAILABLE and self._edge_voice_es:
            if not output_file:
                output_file = str(self.audio_dir / f"tts_{os.getpid()}_{int(os.times()[4]*1000)}.mp3")
            result = self._tts_edge(text, output_file, language)
            if result:
                print(f"✅ Audio generado con Edge TTS: {output_file}")
                return result
            print("⚠️ Edge TTS falló, intentando con pyttsx3...")

        # 2. Intentar con pyttsx3 (voces del sistema, offline)
        if PYTTSX3_AVAILABLE and self.pyttsx3_engine:
            try:
                if not output_file:
                    output_file = str(self.audio_dir / f"tts_{os.getpid()}_{int(os.times()[4]*1000)}.wav")
                
                with self._tts_lock:
                    # Cambiar voz según idioma
                    target_voice = None
                    if language == 'en' and self.voice_en:
                        target_voice = self.voice_en
                        print(f"🌐 TTS: Usando voz en INGLÉS")
                    elif self.voice_es:
                        target_voice = self.voice_es
                    
                    if target_voice:
                        self.pyttsx3_engine.setProperty('voice', target_voice)
                        # Voces OneCore no reportan correctamente en getProperty;
                        # solo verificar para voces SAPI5 normales.
                        is_onecore = 'Speech_OneCore' in target_voice
                        if not is_onecore:
                            actual_voice = self.pyttsx3_engine.getProperty('voice')
                            if actual_voice != target_voice:
                                print(f"⚠️ Voz no aplicada (esperada: {target_voice}, actual: {actual_voice}). Re-inicializando engine...")
                                self.pyttsx3_engine = pyttsx3.init()
                                self.pyttsx3_engine.setProperty('rate', self.voice_config.get('rate', 180))
                                self.pyttsx3_engine.setProperty('volume', 0.9)
                                self.pyttsx3_engine.setProperty('voice', target_voice)
                    
                    # Generar audio
                    self.pyttsx3_engine.save_to_file(text, output_file)
                    self.pyttsx3_engine.runAndWait()
                
                print(f"✅ Audio generado con pyttsx3: {output_file}")
                return output_file
            
            except Exception as e:
                print(f"⚠️ Error en pyttsx3: {e}, intentando con Piper...")
        
        # 3. Intentar con Piper (más rápido y local si tiene modelo)
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
        
        # 4. Fallback a gTTS (requiere internet pero siempre funciona)
        if GTTS_AVAILABLE:
            try:
                if not output_file:
                    output_file = str(self.audio_dir / f"tts_{os.getpid()}_{int(os.times()[4]*1000)}.mp3")
                
                # Generar audio con gTTS usando el idioma correcto
                tts_lang = language if language in ('es', 'en') else 'es'
                tts = gTTS(text=text, lang=tts_lang, slow=False)
                tts.save(output_file)
                
                print(f"✅ Audio generado con gTTS ({tts_lang}): {output_file}")
                return output_file
            
            except Exception as e:
                print(f"❌ Error en gTTS: {e}")
                return None
        
        print("❌ No hay sistema TTS disponible (ni Edge TTS, pyttsx3, Piper ni gTTS)")
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
        """Verifica si TTS está disponible"""
        return EDGE_TTS_AVAILABLE or PYTTSX3_AVAILABLE or (PIPER_AVAILABLE and self.piper_voice is not None) or GTTS_AVAILABLE
    
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
