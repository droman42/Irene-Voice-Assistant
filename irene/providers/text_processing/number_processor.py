"""
Number Text Processing Provider

Wraps the existing NumberNormalizer and number conversion utilities 
from irene/utils/text_processing.py for the intent system.
"""

import logging
from typing import Dict, Any

from ..base import ProviderBase

logger = logging.getLogger(__name__)


class NumberTextProcessor(ProviderBase):
    """
    Number-to-text provider - wraps existing number conversion utilities.
    
    Leverages the existing utilities:
    - NumberNormalizer for digit replacement
    - all_num_to_text_async() for Russian number conversion
    - num_to_text_ru_async() for Russian-specific conversion
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.normalizer = None
        self.default_language = config.get('default_language', 'ru')
        self.enabled_operations = config.get('enabled_operations', ['normalize', 'convert_to_text'])
        
    def get_provider_name(self) -> str:
        return "number_text_processor"
    
    async def is_available(self) -> bool:
        """Check if number processing is available"""
        try:
            if not self.normalizer:
                await self._initialize_normalizer()
            return self.normalizer is not None
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"Number processor initialization failed: {e}")
            return False
    
    async def _do_initialize(self) -> None:
        """Initialize the number processor"""
        await self._initialize_normalizer()
    
    async def _initialize_normalizer(self):
        """Initialize the existing NumberNormalizer"""
        try:
            from ...utils.text_processing import NumberNormalizer
            self.normalizer = NumberNormalizer()
            
            logger.info("Number text processor initialized with existing NumberNormalizer")
            
        except Exception as e:
            logger.error(f"Failed to initialize number normalizer: {e}")
            self.normalizer = None
            raise
    
    async def convert_numbers_to_text(self, text: str, language: str = None) -> str:
        """
        Convert numbers in text to words using existing all_num_to_text_async.
        
        Args:
            text: Text containing numbers to convert
            language: Target language for conversion (defaults to configured language)
            
        Returns:
            Text with numbers converted to words
        """
        if 'convert_to_text' not in self.enabled_operations:
            return text
        
        target_language = language or self.default_language
        
        try:
            from ...utils.text_processing import all_num_to_text_async
            return await all_num_to_text_async(text, target_language)
            
        except Exception as e:
            logger.error(f"Number-to-text conversion failed: {e}")
            return text
    
    async def convert_numbers_to_russian_text(self, text: str) -> str:
        """
        Convert numbers to Russian text using existing num_to_text_ru_async.
        
        Args:
            text: Text containing numbers to convert
            
        Returns:
            Text with numbers converted to Russian words
        """
        if 'convert_to_text' not in self.enabled_operations:
            return text
        
        try:
            from ...utils.text_processing import num_to_text_ru_async
            return await num_to_text_ru_async(text)
            
        except Exception as e:
            logger.error(f"Russian number conversion failed: {e}")
            return text
    
    async def normalize_numbers(self, text: str) -> str:
        """
        Apply number normalization using existing normalizer.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        if 'normalize' not in self.enabled_operations:
            return text
        
        if not self.normalizer:
            await self._initialize_normalizer()
        
        if not self.normalizer:
            logger.warning("Number normalizer not available, returning original text")
            return text
        
        try:
            return await self.normalizer.normalize(text)
            
        except Exception as e:
            logger.error(f"Number normalization failed: {e}")
            return text
    
    async def process_for_tts(self, text: str, language: str = None) -> str:
        """
        Process text for TTS output - convert numbers to text for better speech.
        
        Args:
            text: Text to process
            language: Target language
            
        Returns:
            TTS-ready text with numbers converted to words
        """
        target_language = language or self.default_language
        
        # Apply number normalization first
        normalized = await self.normalize_numbers(text)
        
        # Then convert to text for TTS
        return await self.convert_numbers_to_text(normalized, target_language)
    
    async def process_for_asr(self, text: str) -> str:
        """
        Process ASR output - apply normalization but keep numbers as digits.
        
        Args:
            text: ASR output text
            
        Returns:
            Normalized text with consistent number formatting
        """
        return await self.normalize_numbers(text)
    
    def get_supported_languages(self) -> list[str]:
        """Get list of supported languages for number conversion"""
        return ['ru', 'en']  # Based on existing utilities
    
    def get_supported_operations(self) -> list[str]:
        """Get list of supported operations"""
        return ['normalize', 'convert_to_text', 'process_for_tts', 'process_for_asr']
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get number processor capabilities"""
        return {
            "supported_languages": self.get_supported_languages(),
            "supported_operations": self.get_supported_operations(),
            "enabled_operations": self.enabled_operations,
            "default_language": self.default_language,
            "features": {
                "digit_normalization": True,
                "number_to_text": True,
                "russian_specific": True,
                "tts_optimization": True,
                "asr_post_processing": True
            }
        }
    
    def validate_config(self) -> bool:
        """Validate number processor configuration"""
        if self.default_language not in self.get_supported_languages():
            self.logger.error(f"Unsupported default language: {self.default_language}")
            return False
        
        if not isinstance(self.enabled_operations, list):
            self.logger.error("enabled_operations must be a list")
            return False
        
        supported_ops = self.get_supported_operations()
        for operation in self.enabled_operations:
            if operation not in supported_ops:
                self.logger.error(f"Unsupported operation: {operation}")
                return False
        
        return True
    
    async def cleanup(self) -> None:
        """Clean up number processor resources"""
        if self.normalizer:
            # NumberNormalizer doesn't need explicit cleanup
            self.normalizer = None
            logger.info("Number processor cleaned up") 