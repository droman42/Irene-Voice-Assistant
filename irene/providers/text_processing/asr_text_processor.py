"""
ASR Text Processor Provider

Stage-specific text processor for ASR output cleanup.
Uses only NumberNormalizer for simple number-to-text conversion.

Phase 2 of TODO #2: Text Processing Provider Architecture Refactoring
- Focused on asr_output stage processing
- Minimal processing overhead for ASR workflows
- Composes shared NumberNormalizer utility
"""

import logging
from typing import Dict, Any, Optional

from ..base import ProviderBase
from ...utils.text_normalizers import NumberNormalizer
from ...intents.models import ConversationContext

logger = logging.getLogger(__name__)


class ASRTextProcessor(ProviderBase):
    """
    ASR-focused text processor for post-ASR cleanup.
    
    Applies only number normalization to ASR output, optimized for:
    - Fast processing of ASR transcription results
    - Minimal latency in voice workflows
    - Number consistency in recognized speech
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.number_normalizer = None
        self.language = config.get('language', 'ru')
        self.enabled = config.get('enabled', True)
        
    def get_provider_name(self) -> str:
        return "asr_text_processor"
    
    async def is_available(self) -> bool:
        """Check if ASR text processor is available"""
        try:
            if not self.enabled:
                self._set_status(self.status.__class__.UNAVAILABLE, "ASR text processor disabled in config")
                return False
                
            if not self.number_normalizer:
                await self._initialize_normalizers()
            return self.number_normalizer is not None
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"ASR text processor initialization failed: {e}")
            return False
    
    async def _initialize_normalizers(self) -> None:
        """Initialize the number normalizer for ASR processing"""
        try:
            self._set_status(self.status.__class__.INITIALIZING)
            
            # Initialize only number normalizer for ASR stage
            self.number_normalizer = NumberNormalizer(language=self.language)
            
            self._set_status(self.status.__class__.AVAILABLE)
            logger.info(f"ASR text processor initialized with language: {self.language}")
            
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"Failed to initialize ASR normalizers: {e}")
            logger.error(f"Failed to initialize ASR text processor: {e}")
            raise
    
    async def process_asr_output(self, text: str) -> str:
        """
        Process ASR output with number normalization only.
        
        Args:
            text: Raw ASR transcription text
            
        Returns:
            Text with numbers normalized for consistency
        """
        if not self.number_normalizer:
            await self._initialize_normalizers()
        
        if not self.number_normalizer:
            logger.warning("Number normalizer not available, returning original text")
            return text
        
        try:
            # Apply only number normalization for ASR output
            return await self.number_normalizer.normalize(text)
            
        except Exception as e:
            logger.error(f"ASR text processing failed: {e}")
            return text
    
    async def process_pipeline(self, text: str, stage: str = "asr_output") -> str:
        """
        Process text through ASR-focused pipeline.
        
        Args:
            text: Text to process
            stage: Processing stage (should be 'asr_output' for this processor)
            
        Returns:
            Processed text
        """
        if stage != "asr_output":
            logger.warning(f"ASR processor received non-ASR stage '{stage}', processing anyway")
        
        return await self.process_asr_output(text)
    
    async def improve_text(self, text: str, context: ConversationContext, stage: str = "asr_output") -> str:
        """
        Improve ASR text using context (currently just applies standard processing).
        
        Args:
            text: Text to improve
            context: Conversation context (reserved for future context-aware improvements)
            stage: Processing stage
            
        Returns:
            Improved text
        """
        # For now, use standard ASR processing
        # Future enhancement: use context for ASR-specific corrections
        return await self.process_pipeline(text, stage)
    
    async def normalize_numbers(self, text: str) -> str:
        """Direct access to number normalization"""
        if not self.number_normalizer:
            await self._initialize_normalizers()
        
        if not self.number_normalizer:
            logger.warning("Number normalizer not available, returning original text")
            return text
        
        try:
            return await self.number_normalizer.normalize(text)
        except Exception as e:
            logger.error(f"Number normalization failed: {e}")
            return text
    
    def get_supported_stages(self) -> list[str]:
        """Get supported processing stages"""
        return ["asr_output"]
    
    def get_supported_operations(self) -> list[str]:
        """Get list of supported text processing operations"""
        return ["normalize_numbers", "process_asr_output"]
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get ASR text processor capabilities"""
        return {
            "supported_stages": self.get_supported_stages(),
            "supported_operations": self.get_supported_operations(),
            "language": self.language,
            "features": {
                "number_normalization": True,
                "symbol_processing": False,
                "latin_transcription": False,
                "advanced_normalization": False,
                "fast_processing": True,
                "asr_optimized": True
            }
        }
    
    def validate_config(self) -> bool:
        """Validate ASR text processor configuration"""
        if not isinstance(self.enabled, bool):
            self.logger.error("enabled must be a boolean")
            return False
        
        if not isinstance(self.language, str):
            self.logger.error("language must be a string")
            return False
        
        # Validate language support
        supported_languages = ['ru', 'en']
        if self.language not in supported_languages:
            self.logger.warning(f"Language '{self.language}' may not be fully supported. Supported: {supported_languages}")
        
        return True
    
    async def cleanup(self) -> None:
        """Clean up ASR text processor resources"""
        if self.number_normalizer:
            # NumberNormalizer doesn't need explicit cleanup
            self.number_normalizer = None
        
        self._set_status(self.status.__class__.UNKNOWN)
        logger.info("ASR text processor cleaned up") 