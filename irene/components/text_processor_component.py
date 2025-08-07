"""
Text Processor Component - Text processing and normalization

This component provides comprehensive text processing through stage-specific
providers and maintains backward compatibility with legacy utilities.

Phase 3 of TODO #2: Updated to use new stage-specific providers
"""

import logging
from typing import Dict, Any, List, Optional

from .base import Component
from ..core.interfaces.webapi import WebAPIPlugin
from ..intents.models import ConversationContext
from ..utils.loader import dynamic_loader
from ..utils.text_processing import all_num_to_text_async

logger = logging.getLogger(__name__)


class TextProcessorComponent(Component, WebAPIPlugin):
    """Text processing component using stage-specific providers"""
    
    def __init__(self):
        super().__init__()
        self._provider_classes: Dict[str, type] = {}
        self._stage_providers: Dict[str, str] = {}  # Map stages to preferred providers
        
    async def initialize(self, core) -> None:
        """Initialize text processing providers with configuration-driven filtering"""
        await super().initialize(core)
        
        # Get configuration first to determine enabled providers
        config = getattr(core.config.plugins, 'universal_text_processor', {})
        
        # Default configuration if not provided (updated for new providers)
        if not config:
            config = {
                "enabled": True,
                "providers": {
                    # New stage-specific providers (preferred)
                    "asr_text_processor": {
                        "enabled": True,
                        "language": "ru"
                    },
                    "general_text_processor": {
                        "enabled": True,
                        "language": "ru"
                    },
                    "number_text_processor": {
                        "enabled": True,
                        "language": "ru"
                    },
                    "tts_text_processor": {
                        "enabled": False,  # Resource-intensive, enabled on demand
                        "language": "ru"
                    }
                }
            }
        
        # Get provider configurations
        providers_config = config.get("providers", {})
        
        # Discover only enabled providers from entry-points (configuration-driven filtering)
        enabled_providers = [name for name, provider_config in providers_config.items() 
                            if provider_config.get("enabled", False)]
        
        # Ensure at least one general processor is available as fallback
        if not any(p in enabled_providers for p in ["general_text_processor"]):
            if providers_config.get("general_text_processor", {}).get("enabled", False) is not False:
                enabled_providers.append("general_text_processor")
            
        self._provider_classes = dynamic_loader.discover_providers("irene.providers.text_processing", enabled_providers)
        logger.info(f"Discovered {len(self._provider_classes)} enabled text processing providers: {list(self._provider_classes.keys())}")
        
        # Initialize enabled providers
        enabled_count = 0
        for provider_name, provider_class in self._provider_classes.items():
            provider_config = providers_config.get(provider_name, {})
            if provider_config.get("enabled", False):
                try:
                    provider = provider_class(provider_config)
                    if hasattr(provider, 'is_available'):
                        if await provider.is_available():
                            self.providers[provider_name] = provider
                            enabled_count += 1
                            logger.info(f"Loaded text processing provider: {provider_name}")
                        else:
                            logger.warning(f"Text processing provider {provider_name} not available (dependencies missing)")
                    else:
                        self.providers[provider_name] = provider
                        enabled_count += 1
                        logger.info(f"Loaded text processing provider: {provider_name}")
                except Exception as e:
                    logger.error(f"Failed to load text processing provider {provider_name}: {e}")
        
        # Set default provider if not set
        if not self.default_provider and self.providers:
            self.default_provider = next(iter(self.providers.keys()))
            logger.info(f"Set default text processing provider to: {self.default_provider}")
        
        logger.info(f"Text processing component initialized with {enabled_count} providers")
        
    @property
    def name(self) -> str:
        return "text_processor"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Text processing component with normalization and enhancement capabilities"
        
    @property
    def dependencies(self) -> List[str]:
        return []  # No hard dependencies
        
    @property
    def optional_dependencies(self) -> List[str]:
        return ["lingua_franca", "eng_to_ipa", "runorm"]
        
    @property
    def enabled_by_default(self) -> bool:
        return True
        
    @property  
    def category(self) -> str:
        return "text_processing"
        
    @property
    def platforms(self) -> List[str]:
        return []  # All platforms
    
    def get_dependencies(self) -> List[str]:
        """Get list of dependencies for this component."""
        return self.dependencies  # Use @property for consistency
        
    async def improve(self, text: str, context: ConversationContext, stage: str = "general") -> str:
        """
        Improve text using stage-specific providers or fallback to legacy processor.
        Stages: 'asr_output', 'general', 'tts_input'
        
        Args:
            text: Text to process
            context: Conversation context
            stage: Processing stage
            
        Returns:
            Processed text
        """
        try:
            # Use stage-specific providers (Phase 2 providers)
            stage_provider_map = {
                "asr_output": "asr_text_processor",
                "general": "general_text_processor", 
                "tts_input": "tts_text_processor"
            }
            
            # Try stage-specific provider first
            preferred_provider = stage_provider_map.get(stage)
            if preferred_provider and preferred_provider in self.providers:
                provider = self.providers[preferred_provider]
                if hasattr(provider, 'process_pipeline'):
                    return await provider.process_pipeline(text, stage)
                elif hasattr(provider, 'improve_text'):
                    return await provider.improve_text(text, context, stage)
            
            # Fallback to any available provider
            provider = self.get_current_provider()
            if provider:
                if hasattr(provider, 'process_pipeline'):
                    return await provider.process_pipeline(text, stage)
                elif hasattr(provider, 'improve_text'):
                    return await provider.improve_text(text, context, stage)
            
            # No providers available - return original text
            logger.warning(f"No text processing providers available for stage '{stage}'")
            return text
            
        except Exception as e:
            logger.error(f"Text processing error: {e}")
            return text  # Return original text on error
        
    async def normalize_numbers(self, text: str) -> str:
        """Direct access to number normalization (uses new providers)"""
        try:
            # Use number_text_processor or any available provider with number normalization
            if "number_text_processor" in self.providers:
                provider = self.providers["number_text_processor"]
                return await provider.normalize_numbers(text)
            
            # Try other providers that support number normalization
            for provider in self.providers.values():
                if hasattr(provider, 'normalize_numbers'):
                    return await provider.normalize_numbers(text)
            
            logger.warning("No text processing providers with number normalization available")
            return text
        except Exception as e:
            logger.error(f"Number normalization error: {e}")
            return text
    
    async def convert_numbers_to_words(self, text: str, language: str = "ru") -> str:
        """Convert numbers in text to words using existing utilities."""
        try:
            return await all_num_to_text_async(text, language)
        except Exception as e:
            logger.error(f"Number to text conversion error: {e}")
            return text
    
    async def prepare_normalize(self, text: str) -> str:
        """Apply prepare normalization (uses new providers)"""
        try:
            # Use general_text_processor or any provider with text preparation
            if "general_text_processor" in self.providers:
                provider = self.providers["general_text_processor"]
                return await provider.prepare_text(text)
            
            # Try other providers that support text preparation
            for provider in self.providers.values():
                if hasattr(provider, 'prepare_text'):
                    return await provider.prepare_text(text)
            
            logger.warning("No text processing providers with text preparation available")
            return text
        except Exception as e:
            logger.error(f"Prepare normalization error: {e}")
            return text
    
    async def runorm_normalize(self, text: str) -> str:
        """Apply runorm normalization (uses new providers)"""
        try:
            # Use tts_text_processor (has RunormNormalizer)
            if "tts_text_processor" in self.providers:
                provider = self.providers["tts_text_processor"]
                return await provider.advanced_normalize(text)
            
            # Try other providers that support advanced normalization
            for provider in self.providers.values():
                if hasattr(provider, 'advanced_normalize'):
                    return await provider.advanced_normalize(text)
            
            logger.warning("No text processing providers with advanced normalization available")
            return text
        except Exception as e:
            logger.error(f"Runorm normalization error: {e}")
            return text
    
    # WebAPIPlugin interface - following universal plugin pattern
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with text processing endpoints"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter  # type: ignore
            from pydantic import BaseModel  # type: ignore
            
            router = APIRouter()
            
            # Request/Response models
            class TextProcessingRequest(BaseModel):
                text: str
                stage: str = "general"  # 'asr_output', 'general', 'tts_input'
                normalizer: Optional[str] = None  # Specific normalizer to use
                
            class TextProcessingResponse(BaseModel):
                original_text: str
                processed_text: str
                stage: str
                normalizers_applied: List[str]
            
            class NumberConversionRequest(BaseModel):
                text: str
                language: str = "ru"
                
            @router.post("/process", response_model=TextProcessingResponse)
            async def process_text(request: TextProcessingRequest):
                """Process text through normalization pipeline"""
                normalizers_applied = []
                
                if request.normalizer:
                    # Use specific normalizer
                    if request.normalizer == "numbers":
                        processed = await self.normalize_numbers(request.text)
                        normalizers_applied = ["NumberNormalizer"]
                    elif request.normalizer == "prepare":
                        processed = await self.prepare_normalize(request.text)
                        normalizers_applied = ["PrepareNormalizer"]
                    elif request.normalizer == "runorm":
                        processed = await self.runorm_normalize(request.text)
                        normalizers_applied = ["RunormNormalizer"]
                    else:
                        processed = request.text
                        normalizers_applied = []
                else:
                    # Use full pipeline
                    context = ConversationContext(session_id="api")
                    processed = await self.improve(request.text, context, request.stage)
                    normalizers_applied = [n.__class__.__name__ for n in self.processor.normalizers 
                                         if n.applies_to_stage(request.stage)]
                
                return TextProcessingResponse(
                    original_text=request.text,
                    processed_text=processed,
                    stage=request.stage,
                    normalizers_applied=normalizers_applied
                )
            
            @router.post("/numbers")
            async def convert_numbers_to_text(request: NumberConversionRequest):
                """Convert numbers in text to words"""
                processed = await self.convert_numbers_to_words(request.text, request.language)
                return {
                    "original_text": request.text,
                    "processed_text": processed,
                    "language": request.language
                }
            
            @router.get("/normalizers")
            async def list_normalizers():
                """List available text normalizers and their capabilities"""
                normalizers = {}
                for normalizer in self.processor.normalizers:
                    name = normalizer.__class__.__name__
                    normalizers[name] = {
                        "stages": ["asr_output", "general", "tts_input"],
                        "applies_to": [stage for stage in ["asr_output", "general", "tts_input"] 
                                     if normalizer.applies_to_stage(stage)],
                        "description": normalizer.__doc__ or f"{name} text normalizer"
                    }
                
                return {
                    "normalizers": normalizers,
                    "pipeline_stages": ["asr_output", "general", "tts_input"],
                    "available_languages": ["ru", "en"]  # For number conversion
                }
            
            @router.get("/config")
            async def get_text_processor_config():
                """Get text processor configuration"""
                return {
                    "normalizer_count": len(self.processor.normalizers),
                    "supported_stages": ["asr_output", "general", "tts_input"],
                    "supported_languages": ["ru", "en"],
                    "dependencies": self.get_dependencies()
                }
            
            return router
            
        except ImportError:
            logger.warning("FastAPI not available for text processing web API")
            return None
    
    def is_api_available(self) -> bool:
        """Check if web API is available."""
        try:
            import fastapi
            import pydantic
            return True
        except ImportError:
            return False
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for text processing API endpoints"""
        return "/text_processing"
    
    def get_api_tags(self) -> List[str]:
        """Get OpenAPI tags for text processing endpoints"""
        return ["text_processing", "normalization"] 