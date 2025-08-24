"""
VOSK TTS Provider - Text-to-speech using VOSK TTS backend

Real VOSK TTS implementation using vosk-tts package and dedicated TTS models.
Supports Russian multi-speaker synthesis with high quality offline operation.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import TTSProvider

logger = logging.getLogger(__name__)


class VoskTTSProvider(TTSProvider):
    """
    VOSK TTS Provider - Real text-to-speech using vosk-tts package
    
    Features:
    - VOSK TTS-based speech synthesis (vosk-tts package)
    - Russian multi-speaker support
    - Offline operation
    - High-quality neural synthesis
    - Multiple voice selection
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize VoskTTSProvider with configuration"""
        super().__init__(config)
        self._available = False
        self._model = None
        self._synth = None
        
        # Asset management integration - single source of truth
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Use asset manager for model paths - unified pattern
        asset_config = self.asset_manager._get_provider_asset_config("vosk_tts")
        directory_name = asset_config.get("directory_name", "vosk_tts")
        self.model_path = self.asset_manager.config.models_root / directory_name
            
        self.default_language = config.get("default_language", "ru")
        self.sample_rate = config.get("sample_rate", 22050)
        self.voice_speed = config.get("voice_speed", 1.0)
        self.default_speaker_id = config.get("default_speaker_id", 0)
        
        # Available languages (VOSK TTS currently supports Russian primarily)
        self._languages = ["ru"]
        
        # Available speakers for Russian model
        self._speakers = {
            0: "neutral",
            1: "female_1", 
            2: "female_2",
            3: "male_1",
            4: "male_2"
        }
        
        # Try to import VOSK TTS dependencies
        try:
            import vosk_tts  # type: ignore
            self._vosk_tts = vosk_tts
            self._available = True
            logger.info("VOSK TTS provider dependencies available")
        except ImportError:
            self._available = False
            logger.warning("VOSK TTS provider dependencies not available (vosk-tts required)")
        
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
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """VOSK TTS models are extracted to directories, no file extension"""
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Vosk TTS directory"""
        return "vosk_tts"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Vosk TTS doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Vosk TTS uses models and runtime cache"""
        return ["models", "runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, Any]:
        """VOSK TTS model URLs and configuration"""
        return {
            "ru_multi": {
                "url": "https://alphacephei.com/vosk/models/vosk-model-tts-ru-0.8-multi.zip",
                "size": "500MB",
                "extract": True,
                "description": "Russian multi-speaker TTS model"
            }
        }
    
    async def synthesize_to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """Convert text to speech and save to audio file using VOSK TTS"""
        if not self._available:
            raise RuntimeError("VOSK TTS provider not available")
            
        # Ensure model is loaded
        await self._ensure_model_loaded()
            
        # Extract parameters
        language = kwargs.get('language', self.default_language)
        speaker_id = kwargs.get('speaker_id', self.default_speaker_id)
        speed = kwargs.get('speed', self.voice_speed)
        
        # Validate language
        if language not in self._languages:
            logger.warning(f"Unknown language: {language}, using default: {self.default_language}")
            language = self.default_language
            
        # Validate speaker_id
        if speaker_id not in self._speakers:
            logger.warning(f"Unknown speaker_id: {speaker_id}, using default: {self.default_speaker_id}")
            speaker_id = self.default_speaker_id
            
        # Generate speech using VOSK TTS
        try:
            await self._generate_speech_async(text, output_path, speaker_id, speed)
            logger.info(f"VOSK TTS speech generated: {output_path} (speaker: {self._speakers[speaker_id]})")
            
        except Exception as e:
            logger.error(f"Failed to generate VOSK TTS speech: {e}")
            raise RuntimeError(f"TTS generation failed: {e}")
    
    async def _ensure_model_loaded(self) -> None:
        """Ensure VOSK TTS model is loaded into memory"""
        if self._model is not None and self._synth is not None:
            return
            
        # First ensure model is downloaded
        await self._ensure_model_available()
        
        # Load the model
        await self._load_model()
    
    async def _ensure_model_available(self) -> None:
        """Ensure VOSK TTS model is available, download if necessary"""
        # Check if extracted model exists - look recursively for model files
        if self.model_path.exists():
            # Look recursively for directories that contain VOSK TTS model files
            for subdir in self.model_path.rglob("*"):
                if subdir.is_dir() and (subdir / "model.onnx").exists():
                    return  # Model already available
            
        logger.info("VOSK TTS model not found, attempting download...")
        
        try:
            # Get model info for logging
            model_info = self.asset_manager.get_model_info("vosk_tts", "ru_multi")
            if model_info:
                logger.info(f"Downloading VOSK TTS model (size: {model_info.get('size', 'unknown')})")
            
            # Download using asset manager
            downloaded_path = await self.asset_manager.download_model("vosk_tts", "ru_multi")
            logger.info(f"VOSK TTS model downloaded to: {downloaded_path}")
                
        except Exception as e:
            logger.warning(f"Asset manager download failed for VOSK TTS model: {e}")
            # Fallback: Provide helpful instructions for manual installation
            logger.error(f"VOSK TTS model not found at {self.model_path}")
            logger.error(f"Please download the VOSK TTS model manually from: https://alphacephei.com/vosk/models")
            logger.error(f"Extract vosk-model-tts-ru-0.8-multi.zip to: {self.model_path}")
            raise RuntimeError(f"VOSK TTS model not found: {self.model_path}")
    
    async def _load_model(self) -> None:
        """Load VOSK TTS model into memory"""
        try:
            logger.info("Loading VOSK TTS model...")
            
            # Find the extracted model directory with model.onnx file recursively
            model_dir = None
            if self.model_path.exists():
                for subdir in self.model_path.rglob("*"):
                    if subdir.is_dir() and (subdir / "model.onnx").exists():
                        model_dir = subdir
                        logger.debug(f"Found VOSK TTS model in: {model_dir}")
                        break
            
            if not model_dir:
                raise FileNotFoundError(f"VOSK TTS model directory with model.onnx not found in {self.model_path}")
            
            # Load model in thread to avoid blocking
            self._model, self._synth = await asyncio.to_thread(self._load_model_sync, str(model_dir))
            logger.info(f"VOSK TTS model loaded successfully: {model_dir}")
            
        except Exception as e:
            logger.error(f"Failed to load VOSK TTS model: {e}")
            raise
    
    def _load_model_sync(self, model_path: str):
        """Load VOSK TTS model synchronously (called from thread)"""
        try:
            # Initialize VOSK TTS model and synthesizer
            model = self._vosk_tts.Model(model_path)
            synth = self._vosk_tts.Synth(model)
            return model, synth
        except Exception as e:
            raise RuntimeError(f"Failed to initialize VOSK TTS model: {e}")
    
    async def _generate_speech_async(self, text: str, output_path: Path, 
                                   speaker_id: int, speed: float) -> None:
        """Generate speech asynchronously using VOSK TTS"""
        await asyncio.to_thread(
            self._generate_speech_sync, text, output_path, speaker_id, speed
        )
    
    def _generate_speech_sync(self, text: str, output_path: Path,
                            speaker_id: int, speed: float) -> None:
        """Generate speech synchronously using VOSK TTS (called from thread)"""
        if not self._synth:
            raise RuntimeError("VOSK TTS synthesizer not loaded")
            
        try:
            # Generate speech using VOSK TTS
            # Note: Speed adjustment may need to be implemented at text preprocessing level
            # as VOSK TTS might not support direct speed control
            self._synth.synth(text, str(output_path), speaker_id=speaker_id)
            
            logger.debug(f"VOSK TTS synthesis completed: {output_path}")
            
        except Exception as e:
            logger.error(f"VOSK TTS synthesis failed: {e}")
            raise RuntimeError(f"VOSK TTS synthesis failed: {e}")
    
    async def warm_up(self) -> None:
        """Warm up by preloading the VOSK TTS model"""
        try:
            logger.info("Warming up VOSK TTS model...")
            await self._ensure_model_loaded()
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
            "speaker_id": {
                "type": "integer",
                "description": "Speaker voice ID",
                "options": list(self._speakers.keys()),
                "default": self.default_speaker_id
            },
            "speed": {
                "type": "number",
                "description": "Speech speed multiplier (limited VOSK TTS support)",
                "default": self.voice_speed,
                "min": 0.8,
                "max": 1.2
            }
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities information"""
        return {
            "languages": ["ru-RU"],
            "voices": list(self._speakers.values()),
            "formats": ["wav"],
            "features": [
                "offline_synthesis",
                "multi_speaker",
                "neural_synthesis",
                "high_quality"
            ],
            "quality": "high",
            "speed": "medium"
        }
    
    def get_provider_name(self) -> str:
        """Get unique provider identifier"""
        return "vosk_tts"
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """VOSK TTS requires vosk-tts package"""
        return ["vosk-tts>=0.3.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Platform-specific system packages for VOSK TTS"""
        return {
            "linux.ubuntu": ["libffi-dev"],
            "linux.alpine": ["libffi-dev"],
            "macos": [],  # macOS includes FFI libraries
            "windows": []  # Windows package management differs
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """VOSK TTS supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    async def validate_parameters(self, **kwargs) -> bool:
        """Validate provider-specific parameters"""
        try:
            if "language" in kwargs:
                if kwargs["language"] not in self._languages:
                    return False
                    
            if "speaker_id" in kwargs:
                if kwargs["speaker_id"] not in self._speakers:
                    return False
                    
            if "speed" in kwargs:
                speed = float(kwargs["speed"])
                if not (0.8 <= speed <= 1.2):
                    return False
                    
            return True
        except (ValueError, TypeError):
            return False 