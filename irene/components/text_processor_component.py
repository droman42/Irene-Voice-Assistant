"""
Text Processor Component - Text processing and normalization

This component provides comprehensive text processing through stage-specific
providers and maintains backward compatibility with legacy utilities.

Phase 3 of TODO #2: Updated to use new stage-specific providers
"""

import logging
import time
from typing import Dict, Any, List, Optional, Type

from pydantic import BaseModel
from .base import Component
from ..core.interfaces.webapi import WebAPIPlugin
from ..core.trace_context import TraceContext
from ..intents.models import UnifiedConversationContext
from ..utils.loader import dynamic_loader
from ..utils.text_processing import all_num_to_text_async
from ..providers.text_processing.base import TextProcessingProvider

logger = logging.getLogger(__name__)


class TextProcessorComponent(Component, WebAPIPlugin):
    """Text processing component using stage-specific providers"""
    
    def __init__(self):
        super().__init__()
        self.providers: Dict[str, TextProcessingProvider] = {}  # Proper ABC type hint
        self._provider_classes: Dict[str, type] = {}
        self._stage_providers: Dict[str, str] = {}  # Map stages to preferred providers
        self.context_manager = None  # Will be injected
        
    async def initialize(self, core) -> None:
        """Initialize text processing providers with configuration-driven filtering"""
        await super().initialize(core)
        
        # Get configuration first to determine enabled providers (V14 Architecture)
        config = getattr(core.config, 'text_processor', None)
        if not config:
            # Create default config if missing
            from ..config.models import TextProcessorConfig
            config = TextProcessorConfig()
        
        # Convert Pydantic model to dict for backward compatibility with existing logic
        if hasattr(config, 'model_dump'):
            config = config.model_dump()
        elif hasattr(config, 'dict'):
            config = config.dict()
        else:
            # FATAL: Invalid configuration - cannot proceed with hardcoded defaults
            raise ValueError(
                "TextProcessorComponent: Invalid configuration object received. "
                "Expected a valid TextProcessorConfig instance, but got an invalid config. "
                "Please check your configuration file for proper v14 text_processor section formatting."
            )
        
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
    
    async def process(self, text: str, context: 'UnifiedConversationContext', 
                      trace_context: Optional[TraceContext] = None) -> str:
        """
        Process text using the general text processing provider with optional tracing.
        
        Args:
            text: Input text to process
            context: UnifiedConversationContext with session and room information
            trace_context: Optional trace context for detailed execution tracking
            
        Returns:
            Processed text
        """
        # Fast path - existing logic when no tracing
        if not trace_context or not trace_context.enabled:
            if not self.providers:
                logger.debug("No text processing providers available, returning original text")
                return text
            
            # USE PASSED CONTEXT - NO CREATION
            return await self.improve(text, context, "general")
        
        # Trace path - detailed stage tracking
        stage_start = time.time()
        normalizers_applied = []
        
        if not self.providers:
            processed_text = text
        else:
            # USE PASSED CONTEXT - NO CREATION
            processed_text = await self.improve(text, context, "general")
            
            # Track which providers were used
            if self._stage_providers:
                for stage, provider_name in self._stage_providers.items():
                    normalizers_applied.append({
                        "stage": stage,
                        "provider": provider_name,
                        "used": stage == "general"
                    })
        
        trace_context.record_stage(
            stage_name="text_processing",
            input_data=text,
            output_data=processed_text,
            metadata={
                "normalizers_applied": normalizers_applied,
                "provider_count": len(self.providers),
                "session_id": context.session_id,
                "room_context": bool(context.client_id)
            },
            processing_time_ms=(time.time() - stage_start) * 1000
        )
        
        return processed_text
    
    def get_providers_info(self) -> str:
        """Implementation of abstract method - Get text processing providers information"""
        if not self.providers:
            return "Нет доступных провайдеров обработки текста"
        
        info_lines = [f"Доступные провайдеры обработки текста ({len(self.providers)}):"]
        for name, provider in self.providers.items():
            status = "✓ (по умолчанию)" if name == self.default_provider else "✓"
            capabilities = getattr(provider, 'get_capabilities', lambda: {})()
            stages = capabilities.get("stages", ["general"])
            languages = capabilities.get("languages", ["ru"])
            info_lines.append(f"  {status} {name}: {', '.join(stages[:2])}, {', '.join(languages)}")
        
        return "\n".join(info_lines)
        
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
    

    async def improve(self, text: str, context: UnifiedConversationContext, stage: str = "general") -> str:
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
        """Get FastAPI router with text processing endpoints using centralized schemas"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter  # type: ignore
            from ..api.schemas import (
                TextProcessingRequest, TextProcessingResponse,
                NumberConversionRequest, NumberConversionResponse,
                TextProcessingNormalizersResponse, TextNormalizerInfo,
                TextProcessingConfigResponse, TextProcessorConfigureResponse
            )
            from ..config.models import TextProcessorConfig
            
            router = APIRouter()
                
            @router.post("/process", response_model=TextProcessingResponse)
            async def process_text(request: TextProcessingRequest):
                """Process text through text processing pipeline with context"""
                try:
                    # GET CONTEXT FROM CONTEXT MANAGER - NO CREATION
                    context = await self.context_manager.get_context(
                        request.context.get("session_id", "api_session") if request.context else "api_session"
                    )
                    
                    # Inject API request context if available
                    if request.context:
                        if "client_id" in request.context:
                            context.client_id = request.context["client_id"]
                        if "room_name" in request.context:
                            context.room_name = request.context["room_name"]
                        if "device_context" in request.context:
                            context.client_metadata.update(request.context["device_context"])
                    
                    if request.stage == "bypass":
                        processed = request.text
                        normalizers_applied = []
                    else:
                        # Use context from context manager
                        processed = await self.improve(request.text, context, request.stage)
                        normalizers_applied = [n.__class__.__name__ for n in self.processor.normalizers 
                                             if n.applies_to_stage(request.stage)]
                
                    return TextProcessingResponse(
                        success=True,
                        original_text=request.text,
                        processed_text=processed,
                        stage=request.stage,
                        normalizers_applied=normalizers_applied,
                        session_id=context.session_id,
                        room_context=bool(context.client_id)
                    )
                    
                except Exception as e:
                    logger.error(f"Text processing error: {e}")
                    raise HTTPException(500, f"Text processing failed: {str(e)}")
            
            @router.post("/numbers", response_model=NumberConversionResponse)
            async def convert_numbers_to_text(request: NumberConversionRequest):
                """Convert numbers in text to words"""
                processed = await self.convert_numbers_to_words(request.text, request.language)
                return NumberConversionResponse(
                    success=True,
                    original_text=request.text,
                    processed_text=processed,
                    language=request.language
                )
            
            @router.get("/normalizers", response_model=TextProcessingNormalizersResponse)
            async def list_normalizers():
                """List available text normalizers and their capabilities"""
                normalizers = {}
                for normalizer in self.processor.normalizers:
                    name = normalizer.__class__.__name__
                    normalizers[name] = TextNormalizerInfo(
                        stages=["asr_output", "general", "tts_input"],
                        applies_to=[stage for stage in ["asr_output", "general", "tts_input"] 
                                   if normalizer.applies_to_stage(stage)],
                        description=normalizer.__doc__ or f"{name} text normalizer"
                    )
                
                return TextProcessingNormalizersResponse(
                    success=True,
                    normalizers=normalizers,
                    pipeline_stages=["asr_output", "general", "tts_input"],
                    available_languages=["ru", "en"]  # For number conversion
                )
            
            @router.get("/config", response_model=TextProcessingConfigResponse)
            async def get_text_processor_config():
                """Get text processor configuration"""
                return TextProcessingConfigResponse(
                    success=True,
                    normalizer_count=len(self.processor.normalizers),
                    supported_stages=["asr_output", "general", "tts_input"],
                    supported_languages=["ru", "en"],
                    dependencies=self.get_component_dependencies()
                )
            
            @router.post("/configure", response_model=TextProcessorConfigureResponse)
            async def configure_text_processor(config_update: TextProcessorConfig):
                """Configure text processor settings using unified TOML schema"""
                try:
                    # Apply runtime configuration without TOML persistence
                    # Convert to dict for backward compatibility with existing logic
                    config_dict = config_update.model_dump()
                    
                    # Update provider configurations if provided
                    if config_dict.get("providers"):
                        # Re-initialize providers with new configuration
                        self.providers.clear()
                        self._provider_classes.clear()
                        
                        providers_config = config_dict.get("providers", {})
                        enabled_providers = [name for name, provider_config in providers_config.items() 
                                           if provider_config.get("enabled", False)]
                        
                        # Discover and initialize providers with new config
                        self._provider_classes = dynamic_loader.discover_providers("irene.providers.text_processing", enabled_providers)
                        
                        for provider_name, provider_class in self._provider_classes.items():
                            provider_config = providers_config.get(provider_name, {})
                            if provider_config.get("enabled", False):
                                try:
                                    provider = provider_class(provider_config)
                                    if hasattr(provider, 'is_available'):
                                        if await provider.is_available():
                                            self.providers[provider_name] = provider
                                            logger.info(f"Runtime reconfigured text processing provider: {provider_name}")
                                    else:
                                        self.providers[provider_name] = provider
                                        logger.info(f"Runtime reconfigured text processing provider: {provider_name}")
                                except Exception as e:
                                    logger.error(f"Failed to runtime reconfigure text processing provider {provider_name}: {e}")
                    
                    # Update stages if provided
                    if config_dict.get("stages"):
                        # Stage configuration can be applied immediately
                        logger.info(f"Runtime updated text processing stages: {config_dict['stages']}")
                    
                    # Update normalizers configuration if provided
                    if config_dict.get("normalizers"):
                        # Normalizer configuration can be applied to existing providers
                        logger.info(f"Runtime updated normalizer configurations: {list(config_dict['normalizers'].keys())}")
                    
                    return TextProcessorConfigureResponse(
                        success=True,
                        message="Text processor configuration applied successfully",
                        enabled_providers=list(self.providers.keys()),
                        stages=config_dict.get("stages", []),
                        normalizers=list(config_dict.get("normalizers", {}).keys())
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to configure text processor: {e}")
                    return TextProcessorConfigureResponse(
                        success=False,
                        message=f"Failed to apply text processor configuration: {str(e)}",
                        enabled_providers=list(self.providers.keys()),
                        stages=[],
                        normalizers=[]
                    )
            
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
        return ["Text Normalization"]

    def get_service_dependencies(self) -> Dict[str, type]:
        """Define service dependencies for injection"""
        from ..intents.context import ContextManager
        return {
            'context_manager': ContextManager
        }
    
    def inject_dependency(self, name: str, dependency: Any) -> None:
        """Inject service dependencies"""
        if name == 'context_manager':
            self.context_manager = dependency
            logger.debug("Context manager injected into TextProcessorComponent")
        else:
            super().inject_dependency(name, dependency)

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Text processor component needs web API functionality"""
        return ["fastapi>=0.100.0", "uvicorn[standard]>=0.20.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Text processor component has no system dependencies - coordinates providers only"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Text processor component supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    # Config interface methods (Phase 3 - Configuration Architecture Cleanup)
    @classmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the Pydantic config model for this component"""
        from ..config.models import TextProcessorConfig
        return TextProcessorConfig
    
    @classmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to this component's config (V14 Architecture)"""
        return "text_processor" 