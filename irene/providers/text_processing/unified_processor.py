"""
Unified Text Processing Provider

Wraps the existing TextProcessor from irene/utils/text_processing.py 
to provide a consistent provider interface for the intent system.
"""

import logging
from typing import Dict, Any, Optional

from ..base import ProviderBase
from ...utils.text_processing import TextProcessor as ExistingTextProcessor
from ...intents.models import ConversationContext

logger = logging.getLogger(__name__)


class UnifiedTextProcessor(ProviderBase):
    """
    Unified text processing provider - wraps existing TextProcessor from utils.
    
    Leverages the battle-tested text processing utilities with multi-stage pipeline:
    - NumberNormalizer for number-to-text conversion
    - PrepareNormalizer for text preparation  
    - RunormNormalizer for advanced Russian normalization
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Use the existing, comprehensive TextProcessor
        self.processor = None
        self.enabled_stages = config.get('enabled_stages', ['asr_output', 'general', 'tts_input'])
        
    def get_provider_name(self) -> str:
        return "unified_text_processor"
    
    async def is_available(self) -> bool:
        """Check if text processing is available"""
        try:
            if not self.processor:
                await self._initialize_processor()
            return self.processor is not None
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"Text processor initialization failed: {e}")
            return False
    
    async def _do_initialize(self) -> None:
        """Initialize the text processor"""
        await self._initialize_processor()
    
    async def _initialize_processor(self):
        """Initialize the existing TextProcessor with all normalizers"""
        try:
            # Create TextProcessor instance with all available normalizers
            self.processor = ExistingTextProcessor()
            
            logger.info("Unified text processor initialized with existing normalizers")
            
        except Exception as e:
            logger.error(f"Failed to initialize text processor: {e}")
            self.processor = None
            raise
    
    async def process_pipeline(self, text: str, stage: str = "general") -> str:
        """
        Process text through existing normalization pipeline.
        
        Args:
            text: Text to process
            stage: Processing stage ('asr_output', 'general', 'tts_input')
            
        Returns:
            Processed text
        """
        if not self.processor:
            await self._initialize_processor()
        
        if not self.processor:
            logger.warning("Text processor not available, returning original text")
            return text
        
        try:
            # Use the existing pipeline processing
            return await self.processor.process_pipeline(text, stage)
            
        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            return text
    
    async def improve_text(self, text: str, context: ConversationContext, stage: str = "general") -> str:
        """
        Improve text using context-aware processing.
        
        Args:
            text: Text to improve
            context: Conversation context for context-aware processing
            stage: Processing stage
            
        Returns:
            Improved text
        """
        # For now, use the standard pipeline
        # Future enhancement: use context for smarter processing
        return await self.process_pipeline(text, stage)
    
    async def normalize_numbers(self, text: str) -> str:
        """Direct access to number normalization via existing utilities"""
        try:
            from ...utils.text_processing import NumberNormalizer
            normalizer = NumberNormalizer()
            return await normalizer.normalize(text)
        except Exception as e:
            logger.error(f"Number normalization failed: {e}")
            return text
    
    async def prepare_text(self, text: str) -> str:
        """Direct access to text preparation via existing utilities"""
        try:
            from ...utils.text_processing import PrepareNormalizer
            normalizer = PrepareNormalizer()
            return await normalizer.normalize(text)
        except Exception as e:
            logger.error(f"Text preparation failed: {e}")
            return text
    
    async def advanced_normalize(self, text: str) -> str:
        """Direct access to advanced normalization via existing utilities"""
        try:
            from ...utils.text_processing import RunormNormalizer
            normalizer = RunormNormalizer()
            return await normalizer.normalize(text)
        except Exception as e:
            logger.error(f"Advanced normalization failed: {e}")
            return text
    
    def get_supported_stages(self) -> list[str]:
        """Get supported processing stages"""
        return self.enabled_stages
    
    def get_available_normalizers(self) -> Dict[str, str]:
        """Get information about available normalizers"""
        if not self.processor:
            return {}
        
        normalizers = {}
        for normalizer in self.processor.normalizers:
            name = normalizer.__class__.__name__
            normalizers[name] = {
                "description": normalizer.__doc__ or f"{name} text normalizer",
                "stages": [stage for stage in self.enabled_stages 
                          if hasattr(normalizer, 'applies_to_stage') and normalizer.applies_to_stage(stage)]
            }
        
        return normalizers
    
    def validate_config(self) -> bool:
        """Validate text processing provider configuration"""
        if not isinstance(self.enabled_stages, list):
            self.logger.error("enabled_stages must be a list")
            return False
        
        valid_stages = {'asr_output', 'general', 'tts_input'}
        for stage in self.enabled_stages:
            if stage not in valid_stages:
                self.logger.error(f"Invalid stage '{stage}', must be one of {valid_stages}")
                return False
        
        return True
    
    async def cleanup(self) -> None:
        """Clean up text processor resources"""
        if self.processor:
            # TextProcessor doesn't need explicit cleanup
            self.processor = None
            logger.info("Text processor cleaned up") 