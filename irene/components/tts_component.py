"""
TTS Component - Coordinator for multiple TTS providers

This component implements the fundamental component pattern from the refactoring plan.
It manages multiple TTS providers through configuration-driven instantiation
and provides unified web APIs and voice command interfaces.
"""

import asyncio
import logging
import base64
from typing import Dict, Any, List, Optional, Type
from pathlib import Path
from datetime import datetime

from pydantic import BaseModel

from .base import Component
from ..core.interfaces.tts import TTSPlugin
from ..core.interfaces.webapi import WebAPIPlugin

# Import TTS provider base class and dynamic loader
from ..providers.tts import TTSProvider
from ..utils.loader import dynamic_loader

logger = logging.getLogger(__name__)


class TTSComponent(Component, TTSPlugin, WebAPIPlugin):
    """
    TTS component that coordinates multiple TTS providers.
    
    Features:
    - Configuration-driven provider instantiation
    - Unified web API (/tts/* endpoints)
    - Voice command interface for TTS control
    - Provider fallback and load balancing
    - Runtime provider switching
    """
    
    @property
    def name(self) -> str:
        return "tts"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "TTS component coordinating multiple TTS providers with unified API"
        

        
    @property
    def optional_dependencies(self) -> list[str]:
        return ["torch", "pyttsx3", "vosk", "fastapi"]
        
    @property
    def enabled_by_default(self) -> bool:
        return True
        
    @property  
    def category(self) -> str:
        return "tts"
        
    @property
    def platforms(self) -> list[str]:
        return []  # All platforms
    

    def get_component_dependencies(self) -> list[str]:
        """Get list of required component dependencies."""
        return ["audio"]  # TTS needs audio component to play generated speech
    
    def get_service_dependencies(self) -> Dict[str, type]:
        """Get list of required service dependencies."""
        return {}  # No service dependencies
        
    def __init__(self):
        super().__init__()
        self.providers: Dict[str, TTSProvider] = {}
        self._loaded_providers: Dict[str, TTSProvider] = {}  # Cache for lazy-loaded providers
        self.default_provider: str = "console"
        self.fallback_providers: List[str] = ["console"]
        self.core = None
        self._provider_configs: Dict[str, Dict[str, Any]] = {}  # Cache provider configs
        self._lazy_loading_enabled: bool = True  # Feature flag for lazy loading
        
        # Dynamic provider discovery from entry-points (replaces hardcoded classes)
        self._provider_classes: Dict[str, type] = {}
        
    async def initialize(self, core) -> None:
        """Initialize providers with concurrent loading and lazy loading support"""
        await super().initialize(core)
        self.core = core
        
        # Get configuration first to determine enabled providers (V14 Architecture)
        config = getattr(core.config, 'tts', None)
        if not config:
            # Create default config if missing
            from ..config.models import TTSConfig
            config = TTSConfig()
        
        # Convert Pydantic model to dict for backward compatibility with existing logic
        if hasattr(config, 'model_dump'):
            config_dict = config.model_dump()
        elif hasattr(config, 'dict'):
            config_dict = config.dict()
        else:
            # FATAL: Invalid configuration - cannot proceed with hardcoded defaults
            raise ValueError(
                "TTSComponent: Invalid configuration object received. "
                "Expected a valid TTSConfig instance, but got an invalid config. "
                "Please check your configuration file for proper v14 tts section formatting."
            )
        
        # Add TTS-specific settings not in v14 config but needed for backward compatibility
        config_dict["lazy_loading"] = True
        config_dict["concurrent_initialization"] = True
        
        # Use the converted config dict
        config = config_dict
            
        self.default_provider = config.get("default_provider", "console")
        self.fallback_providers = config.get("fallback_providers", ["console"])
        self._lazy_loading_enabled = config.get("lazy_loading", True)
        concurrent_init = config.get("concurrent_initialization", True)
        
        # Cache provider configurations for lazy loading
        self._provider_configs = config.get("providers", {})
        
        # Discover only enabled providers from entry-points (configuration-driven filtering)
        enabled_providers = [name for name, provider_config in self._provider_configs.items() 
                            if provider_config.get("enabled", False)]
        
        # Always include console as fallback if not already included
        if "console" not in enabled_providers and self._provider_configs.get("console", {}).get("enabled", True):
            enabled_providers.append("console")
            
        self._provider_classes = dynamic_loader.discover_providers("irene.providers.tts", enabled_providers)
        logger.info(f"Discovered {len(self._provider_classes)} enabled TTS providers: {list(self._provider_classes.keys())}")
        
        if self._lazy_loading_enabled:
            # Lazy loading: Only load essential providers immediately
            await self._initialize_essential_providers()
        else:
            # Traditional loading: Load all providers
            if concurrent_init:
                await self._initialize_providers_concurrent()
            else:
                await self._initialize_providers_sequential()
        
        # Ensure we have at least one provider
        if not self.providers and not self._lazy_loading_enabled:
            await self._load_fallback_provider()
        
        # Set default to first available if current default not available
        if self.default_provider not in self.providers and self.providers:
            self.default_provider = list(self.providers.keys())[0]
            logger.info(f"Set default TTS provider to: {self.default_provider}")
            
        logger.info(f"Universal TTS plugin initialized with {len(self.providers)} providers (lazy loading: {self._lazy_loading_enabled})")
    
    async def _initialize_essential_providers(self) -> None:
        """Initialize only essential providers for lazy loading"""
        essential_providers = ["console"]  # Always load console as fallback
        
        # Add default provider if it's different from console
        if self.default_provider not in essential_providers:
            essential_providers.append(self.default_provider)
        
        for provider_name in essential_providers:
            if provider_name in self._provider_classes:
                provider_config = self._provider_configs.get(provider_name, {})
                if provider_config.get("enabled", provider_name == "console"):  # Console enabled by default
                    await self._load_single_provider(provider_name, provider_config)
    
    async def _initialize_providers_concurrent(self) -> None:
        """Initialize providers concurrently for better performance"""
        provider_configs = self._provider_configs
        
        # Create initialization tasks
        init_tasks = []
        for provider_name, provider_class in self._provider_classes.items():
            provider_config = provider_configs.get(provider_name, {})
            if provider_config.get("enabled", False):
                task = asyncio.create_task(
                    self._init_single_provider(provider_name, provider_config)
                )
                init_tasks.append((provider_name, task))
        
        if not init_tasks:
            logger.warning("No TTS providers enabled in configuration")
            return
        
        # Wait for all providers to initialize
        results = await asyncio.gather(*[task for _, task in init_tasks], return_exceptions=True)
        
        # Process results
        for (provider_name, _), result in zip(init_tasks, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to initialize TTS provider {provider_name}: {result}")
            elif isinstance(result, TTSProvider):  # Explicit type check for TTSProvider
                self.providers[provider_name] = result
                logger.info(f"Concurrently initialized TTS provider: {provider_name}")
            else:
                logger.warning(f"TTS provider {provider_name} initialization returned unexpected type: {type(result)}")
    
    async def _initialize_providers_sequential(self) -> None:
        """Initialize providers sequentially (traditional method)"""
        provider_configs = self._provider_configs
        
        for provider_name, provider_class in self._provider_classes.items():
            provider_config = provider_configs.get(provider_name, {})
            if provider_config.get("enabled", False):
                await self._load_single_provider(provider_name, provider_config)
    
    async def _init_single_provider(self, provider_name: str, provider_config: Dict[str, Any]) -> Optional[TTSProvider]:
        """Initialize a single provider (for concurrent initialization)"""
        try:
            provider_class = self._provider_classes[provider_name]
            provider = provider_class(provider_config)
            
            if await provider.is_available():
                return provider
            else:
                logger.warning(f"TTS provider {provider_name} not available (dependencies missing)")
                return None
        except TypeError as e:
            logger.error(f"TTS provider {provider_name} missing required abstract methods: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to load TTS provider {provider_name}: {e}")
            return None
    
    async def _load_single_provider(self, provider_name: str, provider_config: Dict[str, Any]) -> bool:
        """Load a single provider (for sequential and lazy loading)"""
        try:
            provider_class = self._provider_classes[provider_name]
            provider = provider_class(provider_config)
            
            if await provider.is_available():
                self.providers[provider_name] = provider
                logger.info(f"Loaded TTS provider: {provider_name}")
                return True
            else:
                logger.warning(f"TTS provider {provider_name} not available (dependencies missing)")
                return False
        except TypeError as e:
            logger.error(f"TTS provider {provider_name} missing required abstract methods: {e}")
            return False
        except Exception as e:
            logger.warning(f"Failed to load TTS provider {provider_name}: {e}")
            return False
    
    async def _load_provider_lazy(self, provider_name: str) -> Optional[TTSProvider]:
        """Load provider only when first used (lazy loading)"""
        if provider_name in self._loaded_providers:
            return self._loaded_providers[provider_name]
        
        if provider_name not in self._provider_classes:
            logger.error(f"Unknown TTS provider: {provider_name}")
            return None
        
        provider_config = self._provider_configs.get(provider_name, {})
        if not provider_config.get("enabled", False):
            logger.warning(f"TTS provider {provider_name} not enabled in configuration")
            return None
        
        try:
            provider_class = self._provider_classes[provider_name]
            provider = provider_class(provider_config)
            
            if await provider.is_available():
                self._loaded_providers[provider_name] = provider
                self.providers[provider_name] = provider  # Add to active providers
                logger.info(f"Lazy-loaded TTS provider: {provider_name}")
                return provider
            else:
                logger.warning(f"TTS provider {provider_name} not available (dependencies missing)")
                return None
        except Exception as e:
            logger.error(f"Failed to lazy-load TTS provider {provider_name}: {e}")
            return None
    
    async def _load_fallback_provider(self) -> None:
        """Load fallback console provider if no providers are available"""
        try:
            # Use entry-points discovery for fallback provider
            console_class = dynamic_loader.get_provider_class("irene.providers.tts", "console")
            if console_class:
                console_provider = console_class({"enabled": True, "color_output": True})
                self.providers["console"] = console_provider
                logger.info("Fallback: Loaded console TTS provider via entry-points")
            else:
                logger.error("Console TTS provider not found in entry-points")
        except Exception as e:
            logger.error(f"Failed to load fallback console provider: {e}")
    
    # TTSPlugin interface - delegates to providers
    async def synthesize_to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """Generate speech file using configured provider with lazy loading support"""
        provider_name = kwargs.get("provider", self.default_provider)
        
        # Try to get provider, with lazy loading if enabled
        provider = await self._get_provider(provider_name)
        
        if provider:
            try:
                await provider.synthesize_to_file(text, output_path, **kwargs)
            except Exception as e:
                logger.error(f"TTS provider {provider_name} failed: {e}")
                await self._synthesize_with_fallback(text, output_path, **kwargs)
        else:
            logger.warning(f"TTS provider {provider_name} not available")
            await self._synthesize_with_fallback(text, output_path, **kwargs)
    
    async def speak(self, text: str, **kwargs) -> str:
        """
        Convert text to speech and save to timestamped file.
        
        Args:
            text: Text to convert to speech
            **kwargs: Engine-specific parameters (voice, speed, etc.)
            
        Returns:
            str: Filename of the generated audio file
        """
        # Generate timestamped filename in current directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
        filename = f"tts_{timestamp}.wav"
        output_path = Path.cwd() / filename
        
        # Use existing synthesize_to_file implementation
        await self.synthesize_to_file(text, output_path, **kwargs)
        
        return filename
    
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """
        Convert text to speech and save to specified file.
        
        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file
            **kwargs: Engine-specific parameters
        """
        # Delegate to existing synthesize_to_file implementation
        await self.synthesize_to_file(text, output_path, **kwargs)

    def get_supported_voices(self) -> List[str]:
        """Get voices from all available providers"""
        voices = []
        for provider_name, provider in self.providers.items():
            provider_voices = provider.get_capabilities().get("voices", [])
            # Prefix with provider name for uniqueness
            voices.extend([f"{provider_name}:{voice}" for voice in provider_voices])
        return voices
    
    def get_supported_languages(self) -> List[str]:
        """Get languages from all available providers"""
        languages = set()
        for provider in self.providers.values():
            provider_languages = provider.get_capabilities().get("languages", [])
            languages.update(provider_languages)
        return list(languages)
    
    def is_available(self) -> bool:
        """Check if at least one provider is available"""
        return len(self.providers) > 0
    
    async def _get_provider(self, provider_name: str) -> Optional[TTSProvider]:
        """Get provider with lazy loading support"""
        # First check if provider is already loaded
        if provider_name in self.providers:
            return self.providers[provider_name]
        
        # If lazy loading is enabled, try to load the provider
        if self._lazy_loading_enabled:
            provider = await self._load_provider_lazy(provider_name)
            if provider:
                return provider
        
        return None
    
    async def _synthesize_with_fallback(self, text: str, output_path: Path, **kwargs) -> None:
        """Try fallback providers when primary fails"""
        for fallback_provider in self.fallback_providers:
            if fallback_provider in self.providers:
                try:
                    await self.providers[fallback_provider].synthesize_to_file(text, output_path, **kwargs)
                    logger.info(f"Used fallback TTS provider: {fallback_provider}")
                    return
                except Exception as e:
                    logger.warning(f"Fallback TTS provider {fallback_provider} failed: {e}")
                    continue
        
        # All providers failed
        logger.error("All TTS providers failed")
        raise RuntimeError("No TTS providers available")
    
    # Public methods for intent handler delegation

    
    def set_default_provider(self, provider_name: str) -> bool:
        """Set default TTS provider - simple atomic operation"""
        # Map common names to actual provider names
        provider_mapping = {
            "силеро": "silero_v3",
            "силеро3": "silero_v3", 
            "силеро4": "silero_v4",
            "консоль": "console",
            "системный": "pyttsx",
            "воск": "vosk_tts"
        }
        
        # Try direct match first
        if provider_name in self.providers:
            self.default_provider = provider_name
            return True
            
        # Try mapped name
        mapped_name = provider_mapping.get(provider_name.lower())
        if mapped_name and mapped_name in self.providers:
            self.default_provider = mapped_name
            return True
            
        return False
    
    def switch_provider(self, provider_name: str) -> bool:
        """Override base method with TTS-specific provider name mapping"""
        return self.set_default_provider(provider_name)
    
    def get_providers_info(self) -> str:
        """Implementation of abstract method - Get TTS providers information"""
        if not self.providers:
            return "Нет доступных TTS провайдеров"
        
        info = []
        info.append(f"Доступные TTS провайдеры ({len(self.providers)}):")
        info.append(f"Текущий: {self.default_provider}")
        info.append("")
        
        for provider_name, provider in self.providers.items():
            capabilities = provider.get_capabilities()
            voices = capabilities.get("voices", [])
            languages = capabilities.get("languages", [])
            quality = capabilities.get("quality", "unknown")
            
            info.append(f"• {provider_name} ({quality} качество)")
            info.append(f"  Голоса: {', '.join(voices[:3])}{'...' if len(voices) > 3 else ''}")
            info.append(f"  Языки: {', '.join(languages)}")
            info.append("")
        
        return "\n".join(info)
    

    # WebAPIPlugin interface - unified API
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with TTS endpoints"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter, HTTPException  # type: ignore
            from pydantic import BaseModel  # type: ignore
            
            router = APIRouter()
            
            # Request/Response models
            class TTSRequest(BaseModel):
                text: str
                provider: Optional[str] = None
                speaker: Optional[str] = None
                language: Optional[str] = None
                
            class TTSResponse(BaseModel):
                success: bool
                provider: str
                text: str
                audio_content: Optional[str] = None  # Base64 encoded audio data
                error: Optional[str] = None
                
            class ProvidersResponse(BaseModel):
                providers: Dict[str, Any]
                default: str
                
            @router.post("/speak", response_model=TTSResponse)
            async def unified_speak(request: TTSRequest):
                """Unified TTS endpoint for all providers"""
                try:
                    provider = request.provider or self.default_provider
                    
                    if provider not in self.providers:
                        raise HTTPException(404, f"Provider '{provider}' not available")
                    
                    # Extract provider-specific parameters
                    kwargs = {}
                    if request.speaker:
                        kwargs["speaker"] = request.speaker
                    if request.language:
                        kwargs["language"] = request.language
                    
                    # Call speak method which returns filename
                    filename = await self.speak(request.text, provider=provider, **kwargs)
                    
                    # Read the generated file and encode as base64
                    file_path = Path.cwd() / filename
                    try:
                        with open(file_path, 'rb') as audio_file:
                            audio_data = audio_file.read()
                            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                        
                        # Delete the temporary file
                        file_path.unlink()
                        
                        return TTSResponse(
                            success=True,
                            provider=provider,
                            text=request.text,
                            audio_content=audio_base64
                        )
                    except Exception as file_error:
                        logger.error(f"Failed to read/process audio file {filename}: {file_error}")
                        # Try to clean up file if it exists
                        if file_path.exists():
                            file_path.unlink()
                        raise HTTPException(500, f"Failed to process audio file: {file_error}")
                    
                except Exception as e:
                    logger.error(f"TTS API error: {e}")
                    return TTSResponse(
                        success=False,
                        provider=request.provider or self.default_provider,
                        text=request.text,
                        error=str(e)
                    )
            
            @router.get("/providers", response_model=ProvidersResponse)
            async def list_providers():
                """Discovery endpoint for all provider capabilities"""
                result = {}
                for name, provider in self.providers.items():
                    result[name] = {
                        "available": await provider.is_available(),
                        "parameters": provider.get_parameter_schema(),
                        "capabilities": provider.get_capabilities()
                    }
                
                return ProvidersResponse(
                    providers=result,
                    default=self.default_provider
                )
            
            @router.post("/configure")
            async def configure_tts(provider: str, set_as_default: bool = False):
                """Configure TTS settings"""
                if provider in self.providers:
                    if set_as_default:
                        self.default_provider = provider
                    return {
                        "success": True, 
                        "default_provider": self.default_provider,
                        "available_providers": list(self.providers.keys())
                    }
                else:
                    raise HTTPException(404, f"Provider '{provider}' not available")
            
            return router
            
        except ImportError:
            logger.warning("FastAPI not available for TTS web API")
            return None
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for TTS API endpoints"""
        return "/tts"
    
    def get_api_tags(self) -> list[str]:
        """Get OpenAPI tags for TTS endpoints"""
        return ["Text-To-Speech"]
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """TTS component needs web API functionality"""
        return ["fastapi>=0.100.0", "uvicorn[standard]>=0.20.0"]
    
    # Config interface methods (Phase 3 - Configuration Architecture Cleanup)
    @classmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the Pydantic config model for this component"""
        from ..config.models import TTSConfig
        return TTSConfig
    
    @classmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to this component's config (V14 Architecture)"""
        return "tts" 