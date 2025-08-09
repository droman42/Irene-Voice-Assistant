"""
General Text Processor Provider

Stage-specific text processor for general text processing.
Uses NumberNormalizer + PrepareNormalizer for comprehensive text preparation.

Phase 2 of TODO #2: Text Processing Provider Architecture Refactoring
- Focused on general stage processing
- Comprehensive text normalization pipeline
- Composes shared NumberNormalizer and PrepareNormalizer utilities
"""

import logging
from typing import Dict, Any, Optional, List

from .base import TextProcessingProvider
from ...utils.text_normalizers import NumberNormalizer, PrepareNormalizer
from ...intents.models import ConversationContext

logger = logging.getLogger(__name__)


class GeneralTextProcessor(TextProcessingProvider):
    """
    General-purpose text processor for comprehensive text normalization.
    
    Applies number normalization and text preparation, optimized for:
    - General text processing workflows
    - Symbol replacement and cleanup
    - Latin-to-Cyrillic transcription
    - Balanced processing speed and thoroughness
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.number_normalizer = None
        self.prepare_normalizer = None
        self.language = config.get('language', 'ru')
        self.enabled = config.get('enabled', True)
        
        # PrepareNormalizer options from config
        self.prepare_options = config.get('prepare_options', {
            "changeNumbers": "process",
            "changeLatin": "process", 
            "changeSymbols": r"#$%&*+-/<=>@~[\]_`{|}№",
            "keepSymbols": r",.?!;:() ",
            "deleteUnknownSymbols": True,
        })
        
    def get_provider_name(self) -> str:
        return "general_text_processor"
    
    async def is_available(self) -> bool:
        """Check if general text processor is available"""
        try:
            if not self.enabled:
                self._set_status(self.status.__class__.UNAVAILABLE, "General text processor disabled in config")
                return False
                
            if not self.number_normalizer or not self.prepare_normalizer:
                await self._initialize_normalizers()
            return (self.number_normalizer is not None and 
                   self.prepare_normalizer is not None)
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"General text processor initialization failed: {e}")
            return False
    
    async def _initialize_normalizers(self) -> None:
        """Initialize normalizers for general processing"""
        try:
            self._set_status(self.status.__class__.INITIALIZING)
            
            # Initialize number normalizer
            self.number_normalizer = NumberNormalizer(language=self.language)
            
            # Initialize prepare normalizer with custom options
            self.prepare_normalizer = PrepareNormalizer(options=self.prepare_options)
            
            self._set_status(self.status.__class__.AVAILABLE)
            logger.info(f"General text processor initialized with language: {self.language}")
            
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"Failed to initialize general normalizers: {e}")
            logger.error(f"Failed to initialize general text processor: {e}")
            raise
    
    async def process_general(self, text: str) -> str:
        """
        Process text with full general normalization pipeline.
        
        Args:
            text: Text to process
            
        Returns:
            Text with numbers normalized and symbols/Latin processed
        """
        if not self.number_normalizer or not self.prepare_normalizer:
            await self._initialize_normalizers()
        
        if not self.number_normalizer or not self.prepare_normalizer:
            logger.warning("Normalizers not available, returning original text")
            return text
        
        try:
            # Apply number normalization first
            processed_text = await self.number_normalizer.normalize(text)
            
            # Then apply text preparation (symbols, Latin transcription)
            processed_text = await self.prepare_normalizer.normalize(processed_text)
            
            return processed_text
            
        except Exception as e:
            logger.error(f"General text processing failed: {e}")
            return text
    
    async def process_pipeline(self, text: str, stage: str = "general") -> str:
        """
        Process text through general-focused pipeline.
        
        Args:
            text: Text to process
            stage: Processing stage (should be 'general' for this processor)
            
        Returns:
            Processed text
        """
        if stage != "general":
            logger.warning(f"General processor received non-general stage '{stage}', processing anyway")
        
        return await self.process_general(text)
    
    async def improve_text(self, text: str, context: ConversationContext, stage: str = "general") -> str:
        """
        Improve text using context-aware processing.
        
        Args:
            text: Text to improve
            context: Conversation context (reserved for future context-aware improvements)
            stage: Processing stage
            
        Returns:
            Improved text
        """
        # For now, use standard general processing
        # Future enhancement: use context for domain-specific improvements
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
    
    async def prepare_text(self, text: str) -> str:
        """Direct access to text preparation (symbols, Latin transcription)"""
        if not self.prepare_normalizer:
            await self._initialize_normalizers()
        
        if not self.prepare_normalizer:
            logger.warning("Prepare normalizer not available, returning original text")
            return text
        
        try:
            return await self.prepare_normalizer.normalize(text)
        except Exception as e:
            logger.error(f"Text preparation failed: {e}")
            return text
    
    def get_supported_stages(self) -> list[str]:
        """Get supported processing stages"""
        return ["general"]
    
    def get_supported_operations(self) -> list[str]:
        """Get list of supported text processing operations"""
        return ["normalize_numbers", "prepare_text", "process_general"]
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get general text processor capabilities"""
        return {
            "supported_stages": self.get_supported_stages(),
            "supported_operations": self.get_supported_operations(),
            "language": self.language,
            "prepare_options": self.prepare_options,
            "features": {
                "number_normalization": True,
                "symbol_processing": True,
                "latin_transcription": True,
                "advanced_normalization": False,
                "comprehensive_processing": True,
                "general_optimized": True
            }
        }
    
    def validate_config(self) -> bool:
        """Validate general text processor configuration"""
        if not isinstance(self.enabled, bool):
            self.logger.error("enabled must be a boolean")
            return False
        
        if not isinstance(self.language, str):
            self.logger.error("language must be a string")
            return False
        
        if not isinstance(self.prepare_options, dict):
            self.logger.error("prepare_options must be a dictionary")
            return False
        
        # Validate required prepare options
        required_options = ["changeNumbers", "changeLatin", "changeSymbols", "keepSymbols", "deleteUnknownSymbols"]
        for option in required_options:
            if option not in self.prepare_options:
                self.logger.error(f"Missing required prepare option: {option}")
                return False
        
        # Validate language support
        supported_languages = ['ru', 'en']
        if self.language not in supported_languages:
            self.logger.warning(f"Language '{self.language}' may not be fully supported. Supported: {supported_languages}")
        
        return True
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """General text processor requires specific text processing libraries"""
        return [
            "lingua-franca @ git+https://github.com/MycroftAI/lingua-franca.git@5bfd75fe5996fd364102a0eec3f714c9ddc9275c",
            "eng-to-ipa>=0.0.2"
        ]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """General text processor has no system dependencies"""
        return {
            "ubuntu": [],
            "alpine": [],
            "centos": [],
            "macos": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """General text processor supports all platforms"""
        return ["linux", "windows", "macos"]
    
    async def cleanup(self) -> None:
        """Clean up general text processor resources"""
        if self.number_normalizer:
            self.number_normalizer = None
        
        if self.prepare_normalizer:
            self.prepare_normalizer = None
        
        self._set_status(self.status.__class__.UNKNOWN)
        logger.info("General text processor cleaned up") 