"""
Whisper ASR Provider

OpenAI Whisper speech recognition provider implementation.
Supports multiple model sizes and languages with high accuracy.
"""

import asyncio
import tempfile
import os
from typing import Dict, Any, List, AsyncIterator
from pathlib import Path
import logging

from .base import ASRProvider

logger = logging.getLogger(__name__)


class WhisperASRProvider(ASRProvider):
    """OpenAI Whisper ASR Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Whisper provider with configuration
        
        Args:
            config: Provider configuration containing:
                - model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
                - device: Device to run on ('cpu', 'cuda')
                - download_root: Directory for cached models (deprecated - uses asset manager)
                - default_language: Default language code (None for auto-detect)
        """
        super().__init__(config)  # Proper ABC inheritance
        self.model_size = config.get("model_size", "base")
        self.device = config.get("device", "cpu")
        
        # Asset management integration
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Use asset manager for download root, fallback to config for backwards compatibility
        legacy_download_root = config.get("download_root")
        if legacy_download_root:
            self.download_root = Path(legacy_download_root).expanduser()
            logger.warning("Using legacy download_root config. Consider using IRENE_MODELS_ROOT environment variable.")
        else:
            self.download_root = self.asset_manager.config.whisper_models_dir
            
        self.default_language = config.get("default_language", None)  # None = auto-detect
        self._model: Any = None  # Lazy-loaded Whisper model
        
    async def is_available(self) -> bool:
        """Check if Whisper dependencies are available"""
        try:
            import whisper  # type: ignore
            return True
        except ImportError:
            logger.warning("Whisper library not available")
            return False
    
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        """Transcribe audio using Whisper"""
        language = kwargs.get("language", self.default_language)
        
        try:
            # Load model if not already loaded
            if self._model is None:
                await self._load_model()
            
            # Save audio data to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                # Transcribe audio file
                result = await asyncio.to_thread(
                    self._model.transcribe,
                    temp_path,
                    language=language,
                    fp16=False  # Use fp32 for better CPU compatibility
                )
                
                return result["text"].strip()
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
        
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return ""
    
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Transcribe streaming audio using Whisper
        
        Note: Whisper doesn't natively support streaming, so we buffer chunks
        and transcribe when we have enough audio data.
        """
        buffer = bytearray()
        chunk_size = 1024 * 1024  # 1MB chunks for processing
        
        async for audio_chunk in audio_stream:
            buffer.extend(audio_chunk)
            
            # Process when we have enough data
            if len(buffer) >= chunk_size:
                try:
                    # Transcribe current buffer
                    text = await self.transcribe_audio(bytes(buffer))
                    if text.strip():
                        yield text.strip()
                    
                    # Clear processed buffer
                    buffer.clear()
                    
                except Exception as e:
                    logger.error(f"Whisper streaming error: {e}")
        
        # Process remaining buffer
        if buffer:
            try:
                text = await self.transcribe_audio(bytes(buffer))
                if text.strip():
                    yield text.strip()
            except Exception as e:
                logger.error(f"Whisper final chunk error: {e}")
    
    async def _load_model(self) -> None:
        """Load Whisper model using asset management"""
        try:
            import whisper  # type: ignore
            
            # Ensure download directory exists
            self.download_root.mkdir(parents=True, exist_ok=True)
            
            # Check if we should use asset manager download (for future enhancement)
            # For now, let whisper library handle download as before
            model_info = self.asset_manager.get_model_info("whisper", self.model_size)
            if model_info:
                logger.info(f"Loading Whisper model {self.model_size} (size: {model_info.get('size', 'unknown')})")
            
            # Load model in thread to avoid blocking
            self._model = await asyncio.to_thread(
                whisper.load_model,  # type: ignore
                self.model_size,
                device=self.device,
                download_root=str(self.download_root)
            )
            
            logger.info(f"Loaded Whisper model: {self.model_size} on {self.device} at {self.download_root}")
            
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for Whisper-specific parameters"""
        return {
            "language": {
                "type": "string",
                "options": self.get_supported_languages(),
                "default": self.default_language,
                "description": "Language code for recognition (None for auto-detect)"
            },
            "model_size": {
                "type": "string",
                "options": ["tiny", "base", "small", "medium", "large"],
                "default": self.model_size,
                "description": "Whisper model size"
            },
            "device": {
                "type": "string",
                "options": ["cpu", "cuda"],
                "default": self.device,
                "description": "Device to run model on"
            }
        }
    
    def get_provider_name(self) -> str:
        """Return provider identifier"""
        return "whisper"
    
    def get_supported_languages(self) -> List[str]:
        """Return list of supported language codes"""
        return [
            "en", "ru", "es", "fr", "de", "it", "ja", "ko", "zh", "auto",
            "ar", "bg", "ca", "cs", "da", "el", "et", "fi", "he", "hi",
            "hr", "hu", "id", "is", "lt", "lv", "ms", "mt", "nl", "no",
            "pl", "pt", "ro", "sk", "sl", "sv", "th", "tr", "uk", "vi"
        ]
    
    def get_supported_formats(self) -> List[str]:
        """Return list of supported audio formats"""
        return ["wav", "mp3", "m4a", "flac", "ogg", "wma", "aac"]
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return Whisper provider capabilities"""
        return {
            "languages": self.get_supported_languages(),
            "formats": self.get_supported_formats(),
            "streaming": True,  # Buffered streaming support
            "real_time": False,  # Not real-time due to model processing time
            "confidence_scores": False,  # Whisper doesn't provide confidence scores
            "offline": True,  # Works offline after model download
            "model_based": True,
            "auto_language_detection": True,  # Can auto-detect language
            "high_accuracy": True,  # Generally high accuracy
            "multilingual": True
        } 