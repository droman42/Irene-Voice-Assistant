"""
VOSK ASR Provider

VOSK speech recognition provider implementation.
Extracted from MicrophoneInput for clean separation of concerns.
"""

import json
import asyncio
from typing import Dict, Any, List, AsyncIterator
from pathlib import Path
import logging

from .base import ASRProvider

logger = logging.getLogger(__name__)


class VoskASRProvider(ASRProvider):
    """VOSK ASR Provider - extracted from MicrophoneInput"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize VOSK provider with configuration
        
        Args:
            config: Provider configuration containing:
                - model_paths: Dict mapping language codes to model paths (deprecated - uses asset manager)
                - default_language: Default language code (default: 'ru')
                - sample_rate: Audio sample rate (default: 16000)
                - confidence_threshold: Minimum confidence for results (default: 0.7)
        """
        super().__init__(config)  # Proper ABC inheritance
        
        # Asset management integration - single source of truth
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Use asset manager for model paths - unified pattern
        self.model_paths = {
            "ru": self.asset_manager.get_model_path("vosk", "ru_small"),
            "en": self.asset_manager.get_model_path("vosk", "en_us")
        }
            
        self.default_language = config.get("default_language", "ru")
        self.sample_rate = config.get("sample_rate", 16000)
        self.confidence_threshold = config.get("confidence_threshold", 0.7)
        self._models: Dict[str, Any] = {}  # Lazy-loaded VOSK models cache
        self._recognizers: Dict[str, Any] = {}  # Cached VOSK recognizers per language
        
        # Initialize model on startup if requested
        preload_models = config.get("preload_models", False)
        if preload_models:
            # Schedule model loading for startup
            import asyncio
            asyncio.create_task(self.warm_up())
        
    async def is_available(self) -> bool:
        """Check if VOSK dependencies and models are available"""
        try:
            import vosk  # type: ignore
            # Check if at least one model exists or can be downloaded
            if not self.model_paths:
                logger.warning("No VOSK model paths configured")
                return False
            
            # Check for existing models or downloadable models via asset manager
            for lang, path in self.model_paths.items():
                if path.exists():
                    return True
                # Check if model can be downloaded via asset manager
                model_id = f"{lang}_small" if lang == "ru" else lang + "_us"
                if self.asset_manager.get_model_info("vosk", model_id):
                    return True
                    
            return False
        except ImportError:
            logger.warning("VOSK library not available")
            return False
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """Vosk models are extracted to directories, no file extension"""
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Vosk ASR directory for model storage"""
        return "vosk"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Vosk doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Vosk uses models and runtime cache"""
        return ["models", "runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, Any]:
        """Vosk ASR model URLs for different languages with proper model IDs and extraction info"""
        return {
            # Small models for better performance and download size
            "ru_small": {
                "url": "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
                "size": "45MB",
                "extract": True
            },
            "en_us": {
                "url": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip",
                "size": "42MB", 
                "extract": True
            },
            # Full-size models for higher accuracy (optional)
            "ru": {
                "url": "https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip",
                "size": "1.8GB",
                "extract": True
            },
            "en": {
                "url": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip",
                "size": "42MB",
                "extract": True
            },
            "de": {
                "url": "https://alphacephei.com/vosk/models/vosk-model-de-0.21.zip",
                "size": "86MB",
                "extract": True
            },
            "es": {
                "url": "https://alphacephei.com/vosk/models/vosk-model-es-0.42.zip",
                "size": "1.4GB",
                "extract": True
            },
            "fr": {
                "url": "https://alphacephei.com/vosk/models/vosk-model-fr-0.22.zip",
                "size": "1.4GB",
                "extract": True
            }
        }
    
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        """Transcribe audio using VOSK - code moved from MicrophoneInput"""
        language = kwargs.get("language", self.default_language)
        confidence_threshold = kwargs.get("confidence_threshold", self.confidence_threshold)
        
        try:
            # Load model for language if not already loaded
            if language not in self._models:
                await self._load_model(language)
            
            # Get or create recognizer for this language
            if language not in self._recognizers:
                await self._create_recognizer(language)
            
            recognizer = self._recognizers[language]
            
            # Process audio with VOSK
            if recognizer.AcceptWaveform(audio_data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                confidence = result.get("confidence", 0.0)
                
                if confidence >= confidence_threshold:
                    return text.strip()
            else:
                # Check partial result for streaming scenarios
                partial_result = json.loads(recognizer.PartialResult())
                partial_text = partial_result.get("partial", "")
                if partial_text.strip():
                    return partial_text.strip()
        
        except Exception as e:
            logger.error(f"VOSK transcription error: {e}")
        
        return ""
    
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Transcribe streaming audio using VOSK"""
        language = self.default_language
        
        # Load model and create recognizer
        if language not in self._models:
            await self._load_model(language)
        if language not in self._recognizers:
            await self._create_recognizer(language)
            
        recognizer = self._recognizers[language]
        
        async for audio_chunk in audio_stream:
            try:
                if recognizer.AcceptWaveform(audio_chunk):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                    if text.strip():
                        yield text.strip()
                else:
                    # Yield partial results for real-time feedback
                    partial_result = json.loads(recognizer.PartialResult())
                    partial_text = partial_result.get("partial", "")
                    if partial_text.strip():
                        yield f"[partial] {partial_text.strip()}"
            except Exception as e:
                logger.error(f"VOSK streaming error: {e}")
    
    async def _load_model(self, language: str) -> None:
        """Load VOSK model for specified language using asset management"""
        if language not in self.model_paths:
            raise ValueError(f"No model path configured for language: {language}")
        
        model_path = self.model_paths[language]
        
        # Download model if not present using asset manager
        if not model_path.exists():
            logger.info(f"VOSK model not found for {language}, attempting download...")
            
            try:
                # Map language to asset manager model ID
                model_id = f"{language}_small" if language == "ru" else language + "_us"
                
                # Get model info for logging
                model_info = self.asset_manager.get_model_info("vosk", model_id)
                if model_info:
                    logger.info(f"Downloading VOSK model for {language} (size: {model_info.get('size', 'unknown')})")
                
                # Download using asset manager
                downloaded_path = await self.asset_manager.download_model("vosk", model_id)
                
                # If downloaded to different location, update model path
                if downloaded_path != model_path:
                    self.model_paths[language] = downloaded_path
                    model_path = downloaded_path
                    
            except Exception as e:
                logger.warning(f"Asset manager download failed for VOSK {language} model: {e}")
                # Fallback: Check if provider has its own download method or use manual installation message
                logger.error(f"VOSK model for {language} not found at {model_path}")
                logger.error(f"Please download the VOSK {language} model manually and place it at: {model_path}")
                logger.error(f"Download from: https://alphacephei.com/vosk/models")
                raise FileNotFoundError(f"VOSK model not found: {model_path}. Please download manually from https://alphacephei.com/vosk/models")
        
        try:
            import vosk  # type: ignore
            
            # Find the actual model directory
            actual_model_path = model_path
            if model_path.is_dir():
                # Look for subdirectory containing the model
                subdirs = [p for p in model_path.iterdir() if p.is_dir()]
                if len(subdirs) == 1:
                    actual_model_path = subdirs[0]
                    logger.debug(f"Found VOSK model in subdirectory: {actual_model_path}")
            
            # Load model in thread to avoid blocking
            model = await asyncio.to_thread(vosk.Model, str(actual_model_path))  # type: ignore
            self._models[language] = model
            logger.info(f"Loaded VOSK model for {language}: {actual_model_path}")
        except Exception as e:
            logger.error(f"Failed to load VOSK model for {language}: {e}")
            raise
    
    async def _create_recognizer(self, language: str) -> None:
        """Create recognizer for specified language"""
        if language not in self._models:
            await self._load_model(language)
        
        try:
            import vosk  # type: ignore
            model = self._models[language]
            recognizer = vosk.KaldiRecognizer(model, self.sample_rate)  # type: ignore
            self._recognizers[language] = recognizer
            logger.info(f"Created VOSK recognizer for {language}")
        except Exception as e:
            logger.error(f"Failed to create VOSK recognizer for {language}: {e}")
            raise
    
    async def warm_up(self) -> None:
        """Warm up by preloading the default language model"""
        try:
            logger.info(f"Warming up VOSK ASR model for default language: {self.default_language}")
            await self._load_model(self.default_language)
            await self._create_recognizer(self.default_language)
            logger.info(f"VOSK ASR model for {self.default_language} warmed up successfully")
        except Exception as e:
            logger.error(f"Failed to warm up VOSK ASR model: {e}")
            # Don't raise - let the provider work with lazy loading
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for VOSK-specific parameters"""
        return {
            "language": {
                "type": "string",
                "options": list(self.model_paths.keys()),
                "default": self.default_language,
                "description": "Language code for recognition"
            },
            "confidence_threshold": {
                "type": "float",
                "min": 0.0,
                "max": 1.0,
                "default": self.confidence_threshold,
                "description": "Minimum confidence threshold for results"
            },
            "sample_rate": {
                "type": "integer",
                "options": [8000, 16000, 22050, 44100, 48000],
                "default": self.sample_rate,
                "description": "Audio sample rate in Hz"
            }
        }
    
    def get_provider_name(self) -> str:
        """Return provider identifier"""
        return "vosk"
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Vosk ASR requires specific vosk library"""
        return ["vosk>=0.3.45"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Platform-specific system packages for Vosk"""
        return {
            "linux.ubuntu": ["libffi-dev"],
            "linux.alpine": ["libffi-dev"],
            "macos": [],  # macOS includes FFI libraries
            "windows": []  # Windows package management differs
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Vosk supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    def get_supported_languages(self) -> List[str]:
        """Return list of supported language codes"""
        return list(self.model_paths.keys())
    
    def get_supported_formats(self) -> List[str]:
        """Return list of supported audio formats"""
        return ["wav", "raw", "pcm"]
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return VOSK provider capabilities"""
        return {
            "languages": self.get_supported_languages(),
            "formats": self.get_supported_formats(),
            "streaming": True,
            "real_time": True,  # VOSK supports real-time processing
            "confidence_scores": True,  # VOSK provides confidence scores
            "offline": True,  # VOSK works offline
            "model_based": True
        } 