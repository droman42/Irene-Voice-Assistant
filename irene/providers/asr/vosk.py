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
        
        # Asset management integration
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Handle model paths with asset management
        legacy_model_paths = config.get("model_paths", {})
        if legacy_model_paths:
            self.model_paths = {lang: Path(path) for lang, path in legacy_model_paths.items()}
            logger.warning("Using legacy model_paths config. Consider using IRENE_MODELS_ROOT environment variable.")
        else:
            # Use asset manager for standard model paths
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
        """Vosk models use zip format for distribution"""
        return ".zip"
    
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
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """Vosk ASR model URLs for different languages"""
        return {
            "ru": "https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip",
            "en": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip",
            "de": "https://alphacephei.com/vosk/models/vosk-model-de-0.21.zip",
            "es": "https://alphacephei.com/vosk/models/vosk-model-es-0.42.zip",
            "fr": "https://alphacephei.com/vosk/models/vosk-model-fr-0.22.zip"
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
                logger.error(f"Failed to download VOSK model for {language}: {e}")
                raise FileNotFoundError(f"VOSK model not found and download failed: {model_path}")
        
        try:
            import vosk  # type: ignore
            # Load model in thread to avoid blocking
            model = await asyncio.to_thread(vosk.Model, str(model_path))  # type: ignore
            self._models[language] = model
            logger.info(f"Loaded VOSK model for {language}: {model_path}")
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