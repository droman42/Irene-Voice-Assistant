"""
Number Text Processor Provider

Specialized text processor for pure number operations.
Uses only NumberNormalizer for focused number-to-text conversion.

Phase 2 of TODO #2: Text Processing Provider Architecture Refactoring
- Focused on pure number processing operations
- Minimal overhead for number-specific workflows
- Composes shared NumberNormalizer utility
"""

import logging
from typing import Dict, Any, Optional, List

from ..base import ProviderBase
from ...utils.text_normalizers import NumberNormalizer
from ...intents.models import ConversationContext

logger = logging.getLogger(__name__)


class NumberTextProcessor(ProviderBase):
    """
    Pure number processing provider for number-to-text conversion.
    
    Provides focused number operations, optimized for:
    - Direct number-to-text conversion
    - Number extraction and processing
    - Minimal processing overhead
    - Language-specific number handling
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.number_normalizer = None
        self.language = config.get('language', 'ru')
        self.enabled = config.get('enabled', True)
        
        # Number processing options
        self.number_options = config.get('number_options', {
            'decimal_places': 2,
            'handle_percentages': True,
            'handle_ranges': True,
            'handle_negatives': True
        })
        
    def get_provider_name(self) -> str:
        return "number_text_processor"
    
    async def is_available(self) -> bool:
        """Check if number text processor is available"""
        try:
            if not self.enabled:
                self._set_status(self.status.__class__.UNAVAILABLE, "Number text processor disabled in config")
                return False
                
            if not self.number_normalizer:
                await self._initialize_normalizer()
            return self.number_normalizer is not None
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"Number text processor initialization failed: {e}")
            return False
    
    async def _initialize_normalizer(self) -> None:
        """Initialize the number normalizer"""
        try:
            self._set_status(self.status.__class__.INITIALIZING)
            
            # Initialize number normalizer with language support
            self.number_normalizer = NumberNormalizer(language=self.language)
            
            self._set_status(self.status.__class__.AVAILABLE)
            logger.info(f"Number text processor initialized with language: {self.language}")
            
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"Failed to initialize number normalizer: {e}")
            logger.error(f"Failed to initialize number text processor: {e}")
            raise
    
    async def convert_numbers_to_text(self, text: str) -> str:
        """
        Convert all numbers in text to word representation.
        
        Args:
            text: Text containing numbers to convert
            
        Returns:
            Text with all numbers converted to words
        """
        if not self.number_normalizer:
            await self._initialize_normalizer()
        
        if not self.number_normalizer:
            logger.warning("Number normalizer not available, returning original text")
            return text
        
        try:
            return await self.number_normalizer.normalize(text)
            
        except Exception as e:
            logger.error(f"Number conversion failed: {e}")
            return text
    
    async def process_numbers_only(self, text: str) -> str:
        """
        Process text focusing only on number conversion.
        
        Args:
            text: Text to process
            
        Returns:
            Text with numbers converted to words
        """
        return await self.convert_numbers_to_text(text)
    
    async def process_pipeline(self, text: str, stage: str = "number_processing") -> str:
        """
        Process text through number-focused pipeline.
        
        Args:
            text: Text to process
            stage: Processing stage (any stage supported)
            
        Returns:
            Processed text
        """
        return await self.process_numbers_only(text)
    
    async def improve_text(self, text: str, context: ConversationContext, stage: str = "number_processing") -> str:
        """
        Improve text using context-aware number processing.
        
        Args:
            text: Text to improve
            context: Conversation context (reserved for future context-aware improvements)
            stage: Processing stage
            
        Returns:
            Improved text
        """
        # For now, use standard number processing
        # Future enhancement: use context for domain-specific number handling
        return await self.process_pipeline(text, stage)
    
    async def normalize_numbers(self, text: str) -> str:
        """Direct access to number normalization (primary method)"""
        return await self.convert_numbers_to_text(text)
    
    async def process_for_tts(self, text: str) -> str:
        """
        Process numbers specifically for TTS output.
        
        Args:
            text: Text to process for TTS
            
        Returns:
            Text with numbers optimized for speech synthesis
        """
        return await self.convert_numbers_to_text(text)
    
    async def process_for_asr(self, text: str) -> str:
        """
        Process numbers for ASR output consistency.
        
        Args:
            text: ASR output text
            
        Returns:
            Text with numbers normalized for consistency
        """
        return await self.convert_numbers_to_text(text)
    
    def get_supported_stages(self) -> list[str]:
        """Get supported processing stages (supports all stages)"""
        return ["asr_output", "general", "tts_input", "number_processing"]
    
    def get_supported_operations(self) -> list[str]:
        """Get list of supported number processing operations"""
        return [
            "convert_numbers_to_text", 
            "process_numbers_only", 
            "normalize_numbers",
            "process_for_tts",
            "process_for_asr"
        ]
    
    def get_supported_languages(self) -> list[str]:
        """Get list of supported languages for number conversion"""
        return ['ru', 'en']
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get number text processor capabilities"""
        return {
            "supported_stages": self.get_supported_stages(),
            "supported_operations": self.get_supported_operations(),
            "supported_languages": self.get_supported_languages(),
            "language": self.language,
            "number_options": self.number_options,
            "features": {
                "number_normalization": True,
                "symbol_processing": False,
                "latin_transcription": False,
                "advanced_normalization": False,
                "pure_number_processing": True,
                "fast_processing": True,
                "cross_stage_compatible": True,
                "tts_optimization": True,
                "asr_optimization": True
            }
        }
    
    def validate_config(self) -> bool:
        """Validate number text processor configuration"""
        if not isinstance(self.enabled, bool):
            self.logger.error("enabled must be a boolean")
            return False
        
        if not isinstance(self.language, str):
            self.logger.error("language must be a string")
            return False
        
        if not isinstance(self.number_options, dict):
            self.logger.error("number_options must be a dictionary")
            return False
        
        # Validate language support
        if self.language not in self.get_supported_languages():
            self.logger.error(f"Unsupported language: {self.language}. Supported: {self.get_supported_languages()}")
            return False
        
        # Validate number options
        if 'decimal_places' in self.number_options:
            if not isinstance(self.number_options['decimal_places'], int):
                self.logger.error("decimal_places must be an integer")
                return False
        
        return True
    
    async def cleanup(self) -> None:
        """Clean up number text processor resources"""
        if self.number_normalizer:
            # NumberNormalizer doesn't need explicit cleanup
            self.number_normalizer = None
        
        self._set_status(self.status.__class__.UNKNOWN)
        logger.info("Number text processor cleaned up") 
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """Number text processor doesn't use persistent files"""
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Number text processor directory"""
        return "numbertextprocessor"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Number text processor doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Number text processor uses runtime cache"""
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """Number text processor doesn't use models"""
        return {}
    
    async def process(self, text: str, stage: str, **kwargs) -> str:
        """
        Process text through number normalization pipeline.
        
        Args:
            text: Text to process
            stage: Processing stage
            
        Returns:
            Processed text with normalized numbers
        """
        return await self.process_numbers(text) 
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Number text processor requires lingua-franca for NumberNormalizer"""
        return [
            "lingua-franca @ git+https://github.com/MycroftAI/lingua-franca.git@5bfd75fe5996fd364102a0eec3f714c9ddc9275c"
        ]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Number text processor has no system dependencies"""
        return {
            "ubuntu": [],
            "alpine": [],
            "centos": [],
            "macos": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Number text processor supports all platforms"""
        return ["linux", "windows", "macos"] 