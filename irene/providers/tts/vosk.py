"""
Vosk TTS Provider - Text-to-speech using Vosk backend

Simplified provider implementation for Vosk-based TTS functionality.
This is a placeholder implementation that can be enhanced with actual Vosk TTS features.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List

from .base import TTSProvider

logger = logging.getLogger(__name__)


class VoskTTSProvider(TTSProvider):
    """
    Vosk TTS provider using Vosk speech synthesis.
    
    Features:
    - Vosk-based text-to-speech synthesis
    - Multiple language support
    - Offline operation
    - Configurable voice parameters
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize VoskTTSProvider with configuration"""
        super().__init__(config)
        self._available = False
        
        # Asset management integration
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Configuration values with asset management
        legacy_model_path = config.get("model_path")
        if legacy_model_path:
            self.model_path = Path(legacy_model_path)
            logger.warning("Using legacy model_path config. Consider using IRENE_MODELS_ROOT environment variable.")
        else:
            # Use asset manager for model path
            self.model_path = self.asset_manager.get_model_path("vosk", "tts", "vosk-tts")
            
        self.default_language = config.get("default_language", "ru")
        self.sample_rate = config.get("sample_rate", 22050)
        self.voice_speed = config.get("voice_speed", 1.0)
        
        # Available languages
        self._languages = ["ru", "en", "de", "fr"]
        
        # Try to import Vosk dependencies
        try:
            import vosk  # type: ignore
            self._vosk = vosk
            self._available = True
            logger.info("Vosk TTS provider dependencies available")
        except ImportError:
            self._available = False
            logger.warning("Vosk TTS provider dependencies not available (vosk required)")
        
        # Initialize model on startup if requested
        preload_models = config.get("preload_models", False)
        if preload_models and self._available:
            # Schedule model loading for startup
            import asyncio
            asyncio.create_task(self.warm_up())
    
    async def is_available(self) -> bool:
        """Check if provider dependencies are available and functional"""
        if not self._available:
            return False
        
        # Check if model path exists or can be downloaded
        if self.model_path.exists():
            return True
            
        # Check if model can be downloaded via asset manager
        model_info = self.asset_manager.get_model_info("vosk", "tts")
        return model_info is not None
    
    async def speak(self, text: str, **kwargs) -> None:
        """Convert text to speech and play it"""
        # Create temporary file for audio
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            
        try:
            await self.to_file(text, temp_path, **kwargs)
            
            # Play using audio plugins if available
            core = kwargs.get('core')
            if core and hasattr(core, 'output_manager'):
                audio_plugins = getattr(core.output_manager, '_audio_plugins', [])
                if audio_plugins:
                    for plugin in audio_plugins:
                        if plugin.is_available():
                            await plugin.play_file(temp_path)
                            break
                    else:
                        logger.warning("No audio plugins available for playback")
                        
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """Convert text to speech and save to audio file using asset management"""
        if not self._available:
            raise RuntimeError("Vosk TTS provider not available")
            
        # Ensure model is available
        await self._ensure_model_available()
            
        # Extract parameters
        language = kwargs.get('language', self.default_language)
        sample_rate = kwargs.get('sample_rate', self.sample_rate)
        speed = kwargs.get('speed', self.voice_speed)
        
        # Validate language
        if language not in self._languages:
            logger.warning(f"Unknown language: {language}, using default: {self.default_language}")
            language = self.default_language
            
        # Generate speech using Vosk TTS
        try:
            # Generate speech with specified parameters
            await self._generate_speech_async(
                text, output_path, language, sample_rate, speed
            )
            
            logger.info(f"Vosk TTS speech generated: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate Vosk TTS speech: {e}")
            raise RuntimeError(f"TTS generation failed: {e}")
    
    async def _ensure_model_available(self) -> None:
        """Ensure VOSK TTS model is available, download if necessary"""
        if self.model_path.exists():
            return
            
        logger.info("VOSK TTS model not found, attempting download...")
        
        try:
            # Get model info for logging
            model_info = self.asset_manager.get_model_info("vosk", "tts")
            if model_info:
                logger.info(f"Downloading VOSK TTS model (size: {model_info.get('size', 'unknown')})")
            
            # Download using asset manager
            downloaded_path = await self.asset_manager.download_model("vosk", "tts")
            
            # If downloaded to different location, update model path
            if downloaded_path != self.model_path:
                self.model_path = downloaded_path
                
        except Exception as e:
            logger.error(f"Failed to download VOSK TTS model: {e}")
            raise RuntimeError(f"VOSK TTS model not found and download failed: {self.model_path}")
    
    async def warm_up(self) -> None:
        """Warm up by preloading the VOSK TTS model"""
        try:
            logger.info("Warming up VOSK TTS model...")
            await self._ensure_model_available()
            logger.info("VOSK TTS model warmed up successfully")
        except Exception as e:
            logger.error(f"Failed to warm up VOSK TTS model: {e}")
            # Don't raise - let the provider work with lazy loading
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for provider-specific parameters"""
        return {
            "language": {
                "type": "string",
                "description": "Language for speech synthesis",
                "options": self._languages,
                "default": self.default_language
            },
            "sample_rate": {
                "type": "integer",
                "description": "Audio sample rate in Hz",
                "options": [16000, 22050, 44100],
                "default": self.sample_rate
            },
            "speed": {
                "type": "number",
                "description": "Speech speed multiplier",
                "default": self.voice_speed,
                "min": 0.5,
                "max": 2.0
            }
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities information"""
        return {
            "languages": ["ru-RU", "en-US", "de-DE", "fr-FR"],
            "voices": ["vosk_default"],
            "formats": ["wav"],
            "features": [
                "offline_synthesis",
                "multilingual",
                "configurable_speed",
                "low_resource"
            ],
            "quality": "medium",
            "speed": "fast"
        }
    
    def get_provider_name(self) -> str:
        """Get unique provider identifier"""
        return "vosk_tts"
    
    async def validate_parameters(self, **kwargs) -> bool:
        """Validate provider-specific parameters"""
        try:
            if "language" in kwargs:
                if kwargs["language"] not in self._languages:
                    return False
                    
            if "sample_rate" in kwargs:
                valid_rates = [16000, 22050, 44100]
                if kwargs["sample_rate"] not in valid_rates:
                    return False
                    
            if "speed" in kwargs:
                speed = float(kwargs["speed"])
                if not (0.5 <= speed <= 2.0):
                    return False
                    
            return True
        except (ValueError, TypeError):
            return False 

    async def _generate_speech_async(self, text: str, output_path: Path, 
                                   language: str, sample_rate: int, speed: float) -> None:
        """Generate speech asynchronously using Vosk TTS"""
        await asyncio.to_thread(
            self._generate_speech_blocking, 
            text, output_path, language, sample_rate, speed
        )
        
    def _generate_speech_blocking(self, text: str, output_path: Path,
                                language: str, sample_rate: int, speed: float) -> None:
        """Generate speech in blocking mode (called from thread)"""
        if not self._available:
            raise RuntimeError("Vosk TTS provider not available")
            
        try:
            # Note: This is a simplified implementation that simulates Vosk TTS
            # In a real implementation, you would use the actual Vosk TTS library
            # which might require additional dependencies
            
            # Method 1: Try using espeak/espeak-ng as a fallback TTS engine
            self._generate_with_espeak(text, output_path, language, sample_rate, speed)
            
        except Exception as fallback_error:
            logger.warning(f"Primary TTS failed, trying pyttsx3 fallback: {fallback_error}")
            try:
                # Method 2: Fallback to pyttsx3 for basic TTS functionality
                self._generate_with_pyttsx3(text, output_path, language, sample_rate, speed)
            except Exception as final_error:
                logger.error(f"All TTS methods failed: {final_error}")
                raise RuntimeError(f"TTS generation failed: {final_error}")
                
    def _generate_with_espeak(self, text: str, output_path: Path,
                            language: str, sample_rate: int, speed: float) -> None:
        """Generate speech using espeak/espeak-ng"""
        import subprocess
        import shutil
        
        # Check if espeak is available
        espeak_cmd = None
        for cmd in ['espeak-ng', 'espeak']:
            if shutil.which(cmd):
                espeak_cmd = cmd
                break
                
        if not espeak_cmd:
            raise RuntimeError("espeak/espeak-ng not found")
        
        # Map language codes
        lang_map = {
            'ru': 'ru',
            'en': 'en',
            'de': 'de',
            'fr': 'fr',
            'es': 'es'
        }
        espeak_lang = lang_map.get(language, 'en')
        
        # Calculate speed (espeak uses words per minute)
        # Normal speed is around 175 wpm, adjust based on speed parameter
        wpm = int(175 * speed)
        
        try:
            # Generate speech using espeak
            cmd = [
                espeak_cmd,
                '-v', espeak_lang,
                '-s', str(wpm),
                '-w', str(output_path),
                text
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.debug(f"Generated speech with espeak: {output_path}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"espeak command failed: {e}")
            raise RuntimeError(f"espeak TTS failed: {e}")
            
    def _generate_with_pyttsx3(self, text: str, output_path: Path,
                             language: str, sample_rate: int, speed: float) -> None:
        """Generate speech using pyttsx3 as fallback"""
        try:
            import pyttsx3  # type: ignore
        except ImportError:
            raise RuntimeError("pyttsx3 not available for fallback TTS")
            
        try:
            # Initialize pyttsx3 engine
            engine = pyttsx3.init()
            
            # Set properties
            engine.setProperty('rate', int(200 * speed))  # Adjust speech rate
            
            # Set voice based on language
            voices = engine.getProperty('voices')
            if voices:
                for voice in voices:
                    if language in voice.id.lower() or language in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        break
            
            # Save to file
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
            
            logger.debug(f"Generated speech with pyttsx3: {output_path}")
            
        except Exception as e:
            logger.error(f"pyttsx3 TTS failed: {e}")
            raise RuntimeError(f"pyttsx3 TTS failed: {e}")
        finally:
            try:
                engine.stop()
            except:
                pass 