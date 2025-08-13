"""
TTS Text Processor Provider

Stage-specific text processor for TTS input preparation.
Uses all three normalizers: NumberNormalizer + PrepareNormalizer + RunormNormalizer.

Phase 2 of TODO #2: Text Processing Provider Architecture Refactoring
- Focused on tts_input stage processing
- Complete text normalization pipeline for optimal TTS output
- Composes all shared normalizer utilities
"""

import logging
from typing import Dict, Any, Optional, List

from .base import TextProcessingProvider
from ...utils.text_normalizers import NumberNormalizer, PrepareNormalizer, RunormNormalizer
from ...intents.models import ConversationContext

logger = logging.getLogger(__name__)


class TTSTextProcessor(TextProcessingProvider):
    """
    TTS-focused text processor for comprehensive TTS input preparation.
    
    Applies complete normalization pipeline, optimized for:
    - High-quality TTS speech synthesis
    - Advanced Russian text normalization
    - Complete symbol and Latin processing
    - Resource-intensive but thorough processing
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.number_normalizer = None
        self.prepare_normalizer = None
        self.runorm_normalizer = None
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
        
        # RunormNormalizer options from config
        self.runorm_options = config.get('runorm_options', {
            "modelSize": "small",
            "device": "cpu"
        })
        
    def get_provider_name(self) -> str:
        return "tts_text_processor"
    
    async def is_available(self) -> bool:
        """Check if TTS text processor is available"""
        try:
            if not self.enabled:
                self._set_status(self.status.__class__.UNAVAILABLE, "TTS text processor disabled in config")
                return False
                
            if not self.number_normalizer or not self.prepare_normalizer or not self.runorm_normalizer:
                await self._initialize_normalizers()
            return (self.number_normalizer is not None and 
                   self.prepare_normalizer is not None and
                   self.runorm_normalizer is not None)
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"TTS text processor initialization failed: {e}")
            return False
    
    async def _initialize_normalizers(self) -> None:
        """Initialize all normalizers for TTS processing"""
        try:
            self._set_status(self.status.__class__.INITIALIZING)
            
            # Initialize number normalizer
            self.number_normalizer = NumberNormalizer(language=self.language)
            
            # Initialize prepare normalizer with custom options
            self.prepare_normalizer = PrepareNormalizer(options=self.prepare_options)
            
            # Initialize RunormNormalizer for advanced Russian normalization
            self.runorm_normalizer = RunormNormalizer(options=self.runorm_options)
            
            self._set_status(self.status.__class__.AVAILABLE)
            logger.info(f"TTS text processor initialized with language: {self.language}")
            
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"Failed to initialize TTS normalizers: {e}")
            logger.error(f"Failed to initialize TTS text processor: {e}")
            raise
    
    async def process_tts_input(self, text: str) -> str:
        """
        Process text with complete TTS normalization pipeline.
        
        Args:
            text: Text to process for TTS
            
        Returns:
            Text fully processed for optimal TTS speech synthesis
        """
        if not self.number_normalizer or not self.prepare_normalizer or not self.runorm_normalizer:
            await self._initialize_normalizers()
        
        if not self.number_normalizer or not self.prepare_normalizer or not self.runorm_normalizer:
            logger.warning("Some normalizers not available, falling back to partial processing")
            return await self._partial_processing(text)
        
        try:
            # Apply complete normalization pipeline
            # 1. Number normalization first
            processed_text = await self.number_normalizer.normalize(text)
            
            # 2. Text preparation (symbols, Latin transcription)
            processed_text = await self.prepare_normalizer.normalize(processed_text)
            
            # 3. Advanced Russian normalization (RunormNormalizer)
            processed_text = await self.runorm_normalizer.normalize(processed_text)
            
            return processed_text
            
        except Exception as e:
            logger.error(f"TTS text processing failed: {e}")
            # Fallback to partial processing
            return await self._partial_processing(text)
    
    async def _partial_processing(self, text: str) -> str:
        """Fallback processing when some normalizers are unavailable"""
        try:
            processed_text = text
            
            # Try number normalization
            if self.number_normalizer:
                processed_text = await self.number_normalizer.normalize(processed_text)
            
            # Try text preparation
            if self.prepare_normalizer:
                processed_text = await self.prepare_normalizer.normalize(processed_text)
            
            # Skip RunormNormalizer if unavailable (optional dependency)
            if self.runorm_normalizer:
                processed_text = await self.runorm_normalizer.normalize(processed_text)
            else:
                logger.warning("RunormNormalizer unavailable, skipping advanced normalization")
            
            return processed_text
            
        except Exception as e:
            logger.error(f"Partial TTS processing failed: {e}")
            return text
    
    async def process_pipeline(self, text: str, stage: str = "tts_input") -> str:
        """
        Process text through TTS-focused pipeline.
        
        Args:
            text: Text to process
            stage: Processing stage (should be 'tts_input' for this processor)
            
        Returns:
            Processed text
        """
        if stage != "tts_input":
            logger.warning(f"TTS processor received non-TTS stage '{stage}', processing anyway")
        
        return await self.process_tts_input(text)
    
    async def improve_text(self, text: str, context: ConversationContext, stage: str = "tts_input") -> str:
        """
        Improve text using context-aware processing.
        
        Args:
            text: Text to improve
            context: Conversation context (reserved for future context-aware improvements)
            stage: Processing stage
            
        Returns:
            Improved text
        """
        # For now, use standard TTS processing
        # Future enhancement: use context for TTS-specific optimizations
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
    
    async def advanced_normalize(self, text: str) -> str:
        """Direct access to advanced Russian normalization"""
        if not self.runorm_normalizer:
            await self._initialize_normalizers()
        
        if not self.runorm_normalizer:
            logger.warning("RunormNormalizer not available, returning original text")
            return text
        
        try:
            return await self.runorm_normalizer.normalize(text)
        except Exception as e:
            logger.error(f"Advanced normalization failed: {e}")
            return text
    
    def get_supported_stages(self) -> list[str]:
        """Get supported processing stages"""
        return ["tts_input"]
    
    def get_supported_operations(self) -> list[str]:
        """Get list of supported text processing operations"""
        return ["normalize_numbers", "prepare_text", "advanced_normalize", "process_tts_input"]
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get TTS text processor capabilities"""
        return {
            "supported_stages": self.get_supported_stages(),
            "supported_operations": self.get_supported_operations(),
            "language": self.language,
            "prepare_options": self.prepare_options,
            "runorm_options": self.runorm_options,
            "features": {
                "number_normalization": True,
                "symbol_processing": True,
                "latin_transcription": True,
                "advanced_normalization": True,
                "complete_processing": True,
                "tts_optimized": True,
                "resource_intensive": True
            }
        }
    
    def validate_config(self) -> bool:
        """Validate TTS text processor configuration"""
        if not isinstance(self.enabled, bool):
            self.logger.error("enabled must be a boolean")
            return False
        
        if not isinstance(self.language, str):
            self.logger.error("language must be a string")
            return False
        
        if not isinstance(self.prepare_options, dict):
            self.logger.error("prepare_options must be a dictionary")
            return False
        
        if not isinstance(self.runorm_options, dict):
            self.logger.error("runorm_options must be a dictionary")
            return False
        
        # Validate required prepare options
        required_prepare_options = ["changeNumbers", "changeLatin", "changeSymbols", "keepSymbols", "deleteUnknownSymbols"]
        for option in required_prepare_options:
            if option not in self.prepare_options:
                self.logger.error(f"Missing required prepare option: {option}")
                return False
        
        # Validate required runorm options
        required_runorm_options = ["modelSize", "device"]
        for option in required_runorm_options:
            if option not in self.runorm_options:
                self.logger.error(f"Missing required runorm option: {option}")
                return False
        
        # Validate language support
        supported_languages = ['ru', 'en']
        if self.language not in supported_languages:
            self.logger.warning(f"Language '{self.language}' may not be fully supported. Supported: {supported_languages}")
        
        return True
    
    async def cleanup(self) -> None:
        """Clean up TTS text processor resources"""
        if self.number_normalizer:
            self.number_normalizer = None
        
        if self.prepare_normalizer:
            self.prepare_normalizer = None
        
        if self.runorm_normalizer:
            await self.runorm_normalizer.cleanup()
            self.runorm_normalizer = None
        
        self._set_status(self.status.__class__.UNKNOWN)
        logger.info("TTS text processor cleaned up") 

    # Asset configuration methods (TODO #4 Phase 1)
    @classmethod
    def _get_default_extension(cls) -> str:
        """TTS text processor doesn't use files"""
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """TTS text processor directory"""
        return "tts_text"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """TTS text processor doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """TTS text processor uses runtime cache"""
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """TTS text processor doesn't use models"""
        return {}
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """TTS text processor requires all text processing libraries for normalizers"""
        return [
            "lingua-franca @ git+https://github.com/MycroftAI/lingua-franca.git@5bfd75fe5996fd364102a0eec3f714c9ddc9275c",
            "runorm>=0.1.0",
            "eng-to-ipa>=0.0.2"
        ]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """TTS text processor has no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """TTS text processor supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    async def process(self, text: str, stage: str, **kwargs) -> str:
        """
        Process text through TTS-focused pipeline.
        
        Args:
            text: Text to process
            stage: Processing stage (should be 'tts_input' for this processor)
            
        Returns:
            Processed text
        """
        if stage != "tts_input":
            logger.warning(f"TTS processor received non-TTS stage '{stage}', processing anyway")
        
        return await self.process_tts_input(text) 