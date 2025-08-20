"""
LLM Component

LLM Coordinator managing multiple LLM providers.
Provides unified web API (/llm/*), voice commands, and text enhancement capabilities.
"""

from typing import Dict, Any, List, Optional, Type
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .base import Component
from ..core.interfaces.llm import LLMPlugin
from ..core.interfaces.webapi import WebAPIPlugin


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
    def dependencies(self) -> List[str]:
        return []  # No hard dependencies
        
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
    
    def get_dependencies(self) -> List[str]:
        """Get list of dependencies for this component."""
        return []  # No hard dependencies - matches existing @property
    
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
    async def enhance_text(self, text: str, task: str = "improve", **kwargs) -> str:
        """
        Core LLM functionality - enhance text using specified task
        
        Args:
            text: Input text to enhance
            task: Enhancement task type
            provider: LLM provider to use (default: self.default_provider)
            **kwargs: Provider-specific parameters
            
        Returns:
            Enhanced text
        """
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
    
    # Public methods for intent handler delegation

    
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
        router = APIRouter()
        
        @router.post("/enhance")
        async def enhance_text_endpoint(
            text: str,
            task: str = "improve",
            provider: Optional[str] = None,
            **kwargs
        ):
            """Enhance text using LLM"""
            provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            enhanced = await self.enhance_text(text, task=task, provider=provider_name, **kwargs)
            
            return {
                "original_text": text,
                "enhanced_text": enhanced,
                "task": task,
                "provider": provider_name
            }
        
        @router.post("/chat")
        async def chat_completion_endpoint(
            messages: List[Dict[str, str]],
            provider: Optional[str] = None,
            **kwargs
        ):
            """Chat completion"""
            provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            response = await self.providers[provider_name].chat_completion(
                messages, **kwargs
            )
            
            return {
                "response": response,
                "provider": provider_name
            }
        
        @router.get("/providers")
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
            return {"providers": result, "default": self.default_provider}
        
        @router.post("/configure")
        async def configure_llm(provider: str, set_as_default: bool = False):
            """Configure LLM settings"""
            if provider in self.providers:
                if set_as_default:
                    self.default_provider = provider
                return {"success": True, "default_provider": self.default_provider}
            else:
                raise HTTPException(404, f"Provider '{provider}' not available")
        
        return router 
    
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