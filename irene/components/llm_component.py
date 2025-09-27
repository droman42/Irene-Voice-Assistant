"""
LLM Component

LLM Coordinator managing multiple LLM providers.
Provides unified web API (/llm/*), voice commands, and text enhancement capabilities.
"""

from typing import Dict, Any, List, Optional, Type
import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .base import Component
from ..core.interfaces.llm import LLMPlugin
from ..core.interfaces.webapi import WebAPIPlugin
from ..core.trace_context import TraceContext


# Import LLM provider base class and dynamic loader
from ..providers.llm import LLMProvider
from ..utils.loader import dynamic_loader

logger = logging.getLogger(__name__)


class LLMComponent(Component, LLMPlugin, WebAPIPlugin):
    """
    LLM Component - Language Model Coordinator
    
    Manages multiple LLM providers and provides:
    - Unified web API (/llm/*)
    - Voice commands for LLM control
    - Text enhancement capabilities
    - Provider switching and fallbacks
    """
    
    @property
    def name(self) -> str:
        return "llm"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "LLM component coordinating multiple language model providers"
        

        
    @property
    def optional_dependencies(self) -> List[str]:
        return ["openai", "anthropic", "requests", "aiohttp"]
        
    @property
    def enabled_by_default(self) -> bool:
        return True
        
    @property  
    def category(self) -> str:
        return "llm"
        
    @property
    def platforms(self) -> List[str]:
        return []  # All platforms
    

    def __init__(self):
        super().__init__()
        self.providers: Dict[str, LLMProvider] = {}  # Proper ABC type hint
        self.default_provider = "openai"
        self.default_task = "improve"
        
        # Dynamic provider discovery from entry-points (replaces hardcoded classes)
        self._provider_classes: Dict[str, type] = {}
        
    async def initialize(self, core) -> None:
        """Initialize LLM providers from configuration"""
        await super().initialize(core)
        try:
            # Get configuration (V14 Architecture)
            config = getattr(core.config, 'llm', None)
            if not config:
                # Create default config if missing
                from ..config.models import LLMConfig
                config = LLMConfig()
            
            # Convert Pydantic model to dict for backward compatibility with existing logic
            if hasattr(config, 'model_dump'):
                config = config.model_dump()
            elif hasattr(config, 'dict'):
                config = config.dict()
            else:
                # FATAL: Invalid configuration - cannot proceed with hardcoded defaults
                raise ValueError(
                    "LLMComponent: Invalid configuration object received. "
                    "Expected a valid LLMConfig instance, but got an invalid config. "
                    "Please check your configuration file for proper v14 llm section formatting."
                )
            
            # Initialize enabled providers with ABC error handling
            # Handle both dict and Pydantic config objects
            if isinstance(config, dict):
                providers_config = config.get("providers", {})
            else:
                providers_config = getattr(config, 'providers', {})
            
            # Discover only enabled providers from entry-points (configuration-driven filtering)
            enabled_providers = [name for name, provider_config in providers_config.items() 
                                if (provider_config.get("enabled", False) if isinstance(provider_config, dict) 
                                    else getattr(provider_config, "enabled", False))]
            
            self._provider_classes = dynamic_loader.discover_providers("irene.providers.llm", enabled_providers)
            logger.info(f"Discovered {len(self._provider_classes)} enabled LLM providers: {list(self._provider_classes.keys())}")
            
            for provider_name, provider_class in self._provider_classes.items():
                if isinstance(providers_config, dict):
                    provider_config = providers_config.get(provider_name, {})
                    provider_enabled = provider_config.get("enabled", False)
                else:
                    provider_config = getattr(providers_config, provider_name, {})
                    provider_enabled = getattr(provider_config, "enabled", False) if hasattr(provider_config, "enabled") else False
                
                if provider_enabled:
                    try:
                        provider = provider_class(provider_config)
                        if await provider.is_available():
                            self.providers[provider_name] = provider
                            logger.info(f"Loaded LLM provider: {provider_name}")
                        else:
                            logger.warning(f"LLM provider {provider_name} not available (dependencies missing)")
                    except TypeError as e:
                        logger.error(f"LLM provider {provider_name} missing required abstract methods: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to load LLM provider {provider_name}: {e}")
            
            # Set defaults from config
            if isinstance(config, dict):
                self.default_provider = config.get("default_provider", "openai")
                self.default_task = config.get("default_task", "improve")
            else:
                self.default_provider = getattr(config, "default_provider", "openai")
                self.default_task = getattr(config, "default_task", "improve")
            
            # Ensure we have at least one provider
            if not self.providers:
                logger.warning("No LLM providers available")
            else:
                logger.info(f"Universal LLM Plugin initialized with {len(self.providers)} providers")
                
        except Exception as e:
            logger.error(f"Failed to initialize Universal LLM Plugin: {e}")
    
    # Primary LLM interface - used by other plugins
    async def enhance_text(self, text: str, task: str = "improve", trace_context: Optional[TraceContext] = None, **kwargs) -> str:
        """
        Core LLM functionality - enhance text using specified task with optional tracing
        
        Args:
            text: Input text to enhance
            task: Enhancement task type
            trace_context: Optional trace context for detailed execution tracking
            provider: LLM provider to use (default: self.default_provider)
            **kwargs: Provider-specific parameters
            
        Returns:
            Enhanced text
        """
        # Fast path - existing logic when no tracing
        if not trace_context or not trace_context.enabled:
            # Original implementation unchanged
            provider_name = kwargs.get("provider", self.default_provider)
            
            if provider_name not in self.providers:
                logger.warning(f"LLM provider '{provider_name}' not available, using fallback")
                # Try to use any available provider as fallback
                if self.providers:
                    provider_name = list(self.providers.keys())[0]
                    logger.info(f"Using fallback provider: {provider_name}")
                else:
                    logger.error("No LLM providers available")
                    return text  # Return original text if no providers
            
            provider = self.providers[provider_name]
            try:
                return await provider.enhance_text(text, task=task, **kwargs)
            except Exception as e:
                logger.error(f"LLM enhancement failed with {provider_name}: {e}")
                return text  # Return original text on error
        
        # Trace path - detailed enhancement tracking
        stage_start = time.time()
        provider_name = kwargs.get("provider", self.default_provider)
        enhancement_metadata = {
            "input_text_length": len(text),
            "input_word_count": len(text.split()),
            "task": task,
            "provider": provider_name,
            "component_name": self.__class__.__name__
        }
        
        # Handle provider availability and fallbacks with tracing
        original_provider = provider_name
        if provider_name not in self.providers:
            logger.warning(f"LLM provider '{provider_name}' not available, using fallback")
            if self.providers:
                provider_name = list(self.providers.keys())[0]
                logger.info(f"Using fallback provider: {provider_name}")
                enhancement_metadata["fallback_used"] = True
                enhancement_metadata["original_provider"] = original_provider
                enhancement_metadata["actual_provider"] = provider_name
            else:
                logger.error("No LLM providers available")
                enhancement_metadata.update({
                    "enhancement_success": False,
                    "error": "No LLM providers available",
                    "fallback_to_original": True
                })
                
                trace_context.record_stage(
                    stage_name="llm_enhancement",
                    input_data=text,
                    output_data=text,
                    metadata=enhancement_metadata,
                    processing_time_ms=(time.time() - stage_start) * 1000
                )
                return text
        
        # Execute enhancement with timing
        provider = self.providers[provider_name]
        try:
            enhanced_text = await provider.enhance_text(text, task=task, **kwargs)
            enhancement_metadata.update({
                "enhancement_success": True,
                "text_changed": text != enhanced_text,
                "output_text_length": len(enhanced_text),
                "output_word_count": len(enhanced_text.split()),
                "provider_used": provider_name
            })
            
        except Exception as e:
            logger.error(f"LLM enhancement failed with {provider_name}: {e}")
            enhanced_text = text
            enhancement_metadata.update({
                "enhancement_success": False,
                "error": str(e),
                "fallback_to_original": True,
                "provider_used": provider_name
            })
        
        trace_context.record_stage(
            stage_name="llm_enhancement",
            input_data=text,
            output_data=enhanced_text,
            metadata=enhancement_metadata,
            processing_time_ms=(time.time() - stage_start) * 1000
        )
        
        return enhanced_text
    
    # Public methods for intent handler delegation
    
    async def generate_response(self, messages: List[Dict[str, str]], 
                               model: Optional[str] = None, 
                               provider: Optional[str] = None,
                               trace_context: Optional[TraceContext] = None,
                               **kwargs) -> str:
        """
        Generate a chat response from messages with optional conversation tracing.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            model: Model name (optional, uses provider default). Can be in format "provider/model"
            provider: Provider name (optional, uses default provider)
            trace_context: Optional trace context for detailed execution tracking
            **kwargs: Additional parameters
            
        Returns:
            Generated response text
        """
        # Fast path - existing logic when no tracing
        if not trace_context or not trace_context.enabled:
            # Original implementation unchanged
            # Parse provider/model format if present
            if model and "/" in model and not provider:
                provider_name, model_name = model.split("/", 1)
                if provider_name not in self.providers:
                    logger.warning(f"Provider '{provider_name}' from model spec '{model}' not available, using default")
                    provider_name = self.default_provider
                    model_name = model  # Use full original model string as fallback
                else:
                    model = model_name  # Use just the model part for the provider
            else:
                provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise ValueError(f"LLM provider '{provider_name}' not available")
            
            # Forward to provider's chat_completion method
            response = await self.providers[provider_name].chat_completion(
                messages, model=model, **kwargs
            )
            
            return response
        
        # Trace path - detailed conversation generation tracking
        stage_start = time.time()
        
        # Parse provider/model format if present
        if model and "/" in model and not provider:
            provider_name, model_name = model.split("/", 1)
            if provider_name not in self.providers:
                logger.warning(f"Provider '{provider_name}' from model spec '{model}' not available, using default")
                provider_name = self.default_provider
                model_name = model  # Use full original model string as fallback
            else:
                model = model_name  # Use just the model part for the provider
        else:
            provider_name = provider or self.default_provider
        
        conversation_metadata = {
            "message_count": len(messages),
            "conversation_length": sum(len(msg.get("content", "")) for msg in messages),
            "roles_present": list(set(msg.get("role", "") for msg in messages)),
            "model": model,
            "provider": provider_name,
            "component_name": self.__class__.__name__
        }
        
        try:
            if provider_name not in self.providers:
                raise ValueError(f"LLM provider '{provider_name}' not available")
            
            # Execute conversation generation with timing
            response = await self.providers[provider_name].chat_completion(
                messages, model=model, **kwargs
            )
            
            conversation_metadata.update({
                "generation_success": True,
                "response_length": len(response),
                "response_word_count": len(response.split()),
                "provider_used": provider_name
            })
            
        except Exception as e:
            conversation_metadata.update({
                "generation_success": False,
                "error": str(e),
                "provider_used": provider_name
            })
            raise
        
        trace_context.record_stage(
            stage_name="llm_conversation",
            input_data={
                "messages": messages,
                "model": model,
                "provider": provider_name
            },
            output_data=response,
            metadata=conversation_metadata,
            processing_time_ms=(time.time() - stage_start) * 1000
        )
        
        return response

    
    def set_default_provider(self, provider_name: str) -> bool:
        """Set default LLM provider - simple atomic operation"""
        if provider_name in self.providers:
            self.default_provider = provider_name
            return True
        return False
    
    def get_providers_info(self) -> str:
        """Implementation of abstract method - Get LLM providers information"""
        return self._get_providers_info()
    
    def parse_provider_name_from_text(self, text: str) -> Optional[str]:
        """Override base method with LLM-specific aliases and logic"""
        # First try base implementation
        result = super().parse_provider_name_from_text(text)
        if result:
            return result
        
        # LLM-specific aliases
        return self._parse_provider_name(text)
    
    def extract_text_from_command(self, command: str) -> Optional[str]:
        """Extract text to enhance from command - public method for intent handlers"""
        return self._extract_text_from_command(command)
    
    def extract_translation_request(self, command: str) -> Optional[tuple[str, str]]:
        """Extract text and target language from command - public method for intent handlers"""
        return self._extract_translation_request(command)
    
    def _extract_text_from_command(self, command: str) -> Optional[str]:
        """Extract text to enhance from voice command"""
        # Simple extraction - look for text after trigger words
        for trigger in ["улучши", "исправь"]:
            if trigger in command:
                parts = command.split(trigger, 1)
                if len(parts) > 1:
                    return parts[1].strip()
        return None
    
    def _extract_translation_request(self, command: str) -> Optional[tuple[str, str]]:
        """Extract text and target language from translation command"""
        # Simple extraction for translation commands
        # Example: "переведи 'hello world' на русский"
        # This is a simplified implementation
        if "переведи" in command:
            # Extract quoted text and language
            import re
            quoted_match = re.search(r"'([^']*)'", command)
            if quoted_match:
                text = quoted_match.group(1)
                if "на русский" in command:
                    return text, "русский"
                elif "на английский" in command:
                    return text, "English"
        return None
    
    def _parse_provider_name(self, command: str) -> Optional[str]:
        """Extract provider name from voice command"""
        command_lower = command.lower()
        for provider_name in self.providers.keys():
            if provider_name in command_lower:
                return provider_name
        
        # Handle common aliases
        aliases = {
            "опенаи": "openai",
            "всегпт": "vsegpt", 
            "антропик": "anthropic",
            "клод": "anthropic"
        }
        
        for alias, provider_name in aliases.items():
            if alias in command_lower and provider_name in self.providers:
                return provider_name
        
        return None
    
    def _get_providers_info(self) -> str:
        """Get formatted information about available providers"""
        if not self.providers:
            return "Нет доступных провайдеров LLM"
        
        info_lines = [f"Доступные провайдеры LLM ({len(self.providers)}):"]
        for name, provider in self.providers.items():
            status = "✓ (по умолчанию)" if name == self.default_provider else "✓"
            models = provider.get_available_models()[:2]  # Show first 2 models
            model_info = ", ".join(models) + "..." if len(models) > 1 else models[0] if models else "N/A"
            info_lines.append(f"  {status} {name}: {model_info}")
        
        return "\n".join(info_lines)
    
    # WebAPIPlugin interface - unified API
    def get_router(self) -> APIRouter:
        """Get FastAPI router with LLM endpoints using centralized schemas"""
        from ..config.models import LLMConfig
        from ..api.schemas import (
            LLMEnhanceRequest, LLMEnhanceResponse,
            LLMChatRequest, LLMChatResponse,
            LLMProvidersResponse,
            LLMConfigureResponse
        )
        
        router = APIRouter()
        
        @router.post("/enhance", response_model=LLMEnhanceResponse)
        async def enhance_text_endpoint(request: LLMEnhanceRequest):
            """Enhance text using LLM"""
            provider_name = request.provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            # Extract additional parameters for provider
            kwargs = request.parameters or {}
            
            enhanced = await self.enhance_text(
                request.text, 
                task=request.task, 
                provider=provider_name, 
                **kwargs
            )
            
            return LLMEnhanceResponse(
                success=True,
                original_text=request.text,
                enhanced_text=enhanced,
                task=request.task,
                provider=provider_name
            )
        
        @router.post("/chat", response_model=LLMChatResponse)
        async def chat_completion_endpoint(request: LLMChatRequest):
            """Chat completion with structured message format"""
            provider_name = request.provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            # Convert ChatMessage objects to the format expected by providers
            messages = [
                {"role": msg.role, "content": msg.content} 
                for msg in request.messages
            ]
            
            # Extract additional parameters for provider
            kwargs = request.parameters or {}
            
            response = await self.providers[provider_name].chat_completion(
                messages, **kwargs
            )
            
            # Try to get usage statistics if available
            usage = kwargs.get("usage") if hasattr(self.providers[provider_name], "get_usage_stats") else None
            
            return LLMChatResponse(
                success=True,
                response=response,
                provider=provider_name,
                usage=usage
            )
        
        @router.get("/providers", response_model=LLMProvidersResponse)
        async def list_llm_providers():
            """Discovery endpoint for all LLM provider capabilities"""
            result = {}
            for name, provider in self.providers.items():
                try:
                    result[name] = {
                        "available": await provider.is_available(),
                        "models": provider.get_available_models(),
                        "tasks": provider.get_supported_tasks(),
                        "parameters": provider.get_parameter_schema(),
                        "capabilities": provider.get_capabilities()
                    }
                except Exception as e:
                    result[name] = {
                        "available": False,
                        "error": str(e)
                    }
            
            return LLMProvidersResponse(
                success=True,
                providers=result,
                default=self.default_provider
            )
        
        @router.post("/configure", response_model=LLMConfigureResponse)
        async def configure_llm(config_update: LLMConfig):
            """Configure LLM settings using unified TOML schema"""
            try:
                
                # Apply runtime configuration without TOML persistence
                config_dict = config_update.model_dump()
                
                # Update default provider if provided
                if config_dict.get("default_provider"):
                    if config_dict["default_provider"] in self.providers:
                        self.default_provider = config_dict["default_provider"]
                    else:
                        logger.warning(f"LLM provider '{config_dict['default_provider']}' not available")
                
                # Update fallback providers
                fallback_providers = config_dict.get("fallback_providers", [])
                if fallback_providers:
                    logger.info(f"LLM fallback providers updated: {fallback_providers}")
                
                # Update enabled providers if provided (would require re-initialization)
                providers_config = config_dict.get("providers", {})
                if providers_config:
                    logger.info(f"LLM runtime provider configuration updated for {len(providers_config)} providers")
                
                return LLMConfigureResponse(
                    success=True,
                    message="LLM configuration applied successfully using unified schema",
                    default_provider=self.default_provider,
                    enabled_providers=list(self.providers.keys()),
                    fallback_providers=fallback_providers
                )
                
            except Exception as e:
                logger.error(f"Failed to configure LLM with unified schema: {e}")
                return LLMConfigureResponse(
                    success=False,
                    message=f"Failed to apply LLM configuration: {str(e)}",
                    default_provider=self.default_provider,
                    enabled_providers=list(self.providers.keys()),
                    fallback_providers=[]
                )
        
        return router 
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for LLM API endpoints"""
        return "/llm"
    
    def get_api_tags(self) -> List[str]:
        """Get OpenAPI tags for LLM endpoints"""
        return ["LLM Component"]
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """LLM component needs web API functionality"""
        return ["fastapi>=0.100.0", "uvicorn[standard]>=0.20.0"]
    
    # Config interface methods (Phase 3 - Configuration Architecture Cleanup)
    @classmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the Pydantic config model for this component"""
        from ..config.models import LLMConfig
        return LLMConfig
    
    @classmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to this component's config (V14 Architecture)"""
        return "llm" 