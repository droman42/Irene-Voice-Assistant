"""
Pyttsx TTS Provider - Cross-platform text-to-speech using pyttsx3

Converted from irene/plugins/builtin/pyttsx_tts_plugin.py to provider pattern.
Provides cross-platform TTS using the pyttsx3 engine.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List

from .base import TTSProvider

logger = logging.getLogger(__name__)


class PyttsTTSProvider(TTSProvider):
    """
    Pyttsx TTS provider using the pyttsx3 engine.
    
    Features:
    - Cross-platform text-to-speech
    - Multiple voice selection
    - Configurable speech rate and volume
    - File output support
    - Async operation with threading
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PyttsTTSProvider with configuration.
        
        Args:
            config: Provider configuration including voice_id, rate, volume
        """
        super().__init__(config)
        self._engine = None
        self._available = False
        self._voices = []
        
        # Configuration values
        self.voice_id = config.get("voice_id", 0)
        self.voice_rate = config.get("voice_rate", 200)
        self.voice_volume = config.get("voice_volume", 1.0)
        
        # Settings dictionary for compatibility
        self._settings = {
            "voice_id": self.voice_id,
            "rate": self.voice_rate,
            "volume": self.voice_volume
        }
        
        # Try to initialize pyttsx3
        self._initialize_engine()
    
    def _initialize_engine(self):
        """Initialize the pyttsx3 engine"""
        try:
            import pyttsx3  # type: ignore
            self._engine = pyttsx3.init()
            self._available = True
            
            # Get available voices
            voices = self._engine.getProperty("voices")
            self._voices = voices if voices else []
            
            # Set default voice and properties
            if self._voices and 0 <= self.voice_id < len(self._voices):
                self._engine.setProperty("voice", self._voices[self.voice_id].id)
            self._engine.setProperty("rate", self.voice_rate)
            self._engine.setProperty("volume", self.voice_volume)
            
            logger.info("Pyttsx TTS provider initialized successfully")
            
        except ImportError:
            self._available = False
            self._engine = None
            logger.warning("Pyttsx TTS provider dependencies not available (pyttsx3 required)")
        except Exception as e:
            self._available = False
            self._engine = None
            logger.error(f"Failed to initialize pyttsx3: {e}")
    
    async def is_available(self) -> bool:
        """Check if provider dependencies are available and functional"""
        return self._available and self._engine is not None
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """Pyttsx3 can save to various audio formats, WAV is most common"""
        return ".wav"
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Pyttsx3 TTS directory for audio cache"""
        return "pyttsx"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Pyttsx3 doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Pyttsx3 uses temp and runtime cache for audio files"""
        return ["temp", "runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """Pyttsx3 uses system TTS engines, no models to download"""
        return {}
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Pyttsx TTS requires pyttsx3 library"""
        return ["pyttsx3>=2.90"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Platform-specific system packages for pyttsx3"""
        return {
            "linux.ubuntu": ["espeak-ng", "espeak-ng-data", "espeak-ng-espeak"],
            "linux.alpine": ["espeak-ng"],
            "macos": [],  # macOS has built-in TTS
            "windows": []  # Windows has built-in TTS
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Pyttsx3 supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    async def synthesize_to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """
        Convert text to speech and save to audio file.
        
        Args:
            text: Text to convert
            output_path: Path where to save the audio file
            **kwargs: voice_id, rate, volume
        """
        if not await self.is_available():
            raise RuntimeError("Pyttsx3 TTS engine not available")
            
        # Update settings if provided
        await self._update_settings_from_kwargs(**kwargs)
        
        # Use asyncio.to_thread for file generation
        await asyncio.to_thread(self._to_file_sync, text, str(output_path))
    
    def _to_file_sync(self, text: str, file_path: str) -> None:
        """Synchronous file generation method for threading"""
        if self._engine:
            self._engine.save_to_file(str(text), file_path)
            self._engine.runAndWait()
    
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities information"""
        # Extract languages from voices
        languages = set()
        voices = []
        
        for i, voice in enumerate(self._voices):
            voice_name = getattr(voice, 'name', f"Voice {i}")
            voices.append(voice_name)
            
            # Try to extract language from voice attributes
            if hasattr(voice, 'languages') and voice.languages:
                languages.update(voice.languages)
            else:
                languages.add("en-US")  # Default fallback
        
        return {
            "languages": list(languages) if languages else ["en-US"],
            "voices": voices,
            "formats": ["wav", "aiff"],  # pyttsx3 typically supports these
            "features": [
                "cross_platform",
                "system_voices",
                "rate_control",
                "volume_control",
                "file_output"
            ],
            "quality": "medium",
            "speed": "fast"
        }
    
    def get_provider_name(self) -> str:
        """Get unique provider identifier"""
        return "pyttsx"
    
    async def _update_settings_from_kwargs(self, **kwargs) -> None:
        """Update settings from keyword arguments"""
        for key, value in kwargs.items():
            if key in self._settings:
                self._settings[key] = value
                
        # Apply settings to engine
        if self._engine:
            try:
                # Set voice if voice_id changed
                if "voice_id" in kwargs and self._voices:
                    voice_id = int(kwargs["voice_id"])
                    if 0 <= voice_id < len(self._voices):
                        self._engine.setProperty("voice", self._voices[voice_id].id)
                        
                # Set rate if changed
                if "rate" in kwargs:
                    self._engine.setProperty("rate", int(kwargs["rate"]))
                    
                # Set volume if changed
                if "volume" in kwargs:
                    volume = float(kwargs["volume"])
                    volume = max(0.0, min(1.0, volume))  # Clamp to 0.0-1.0
                    self._engine.setProperty("volume", volume)
                    
            except Exception as e:
                logger.error(f"Error updating pyttsx3 settings: {e}")
    
    async def validate_parameters(self, **kwargs) -> bool:
        """Validate provider-specific parameters"""
        try:
            if "voice_id" in kwargs:
                voice_id = int(kwargs["voice_id"])
                if not (0 <= voice_id < len(self._voices)):
                    return False
                    
            if "rate" in kwargs:
                rate = int(kwargs["rate"])
                if not (50 <= rate <= 400):
                    return False
                    
            if "volume" in kwargs:
                volume = float(kwargs["volume"])
                if not (0.0 <= volume <= 1.0):
                    return False
                    
            return True
        except (ValueError, TypeError):
            return False 