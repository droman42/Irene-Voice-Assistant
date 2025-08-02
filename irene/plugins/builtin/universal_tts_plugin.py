"""
Universal TTS Plugin - Coordinator for multiple TTS providers

This plugin implements the Universal Plugin pattern from the refactoring plan.
It manages multiple TTS providers through configuration-driven instantiation
and provides unified web APIs and voice command interfaces.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from ...core.interfaces.tts import TTSPlugin
from ...core.interfaces.webapi import WebAPIPlugin
from ...core.interfaces.command import CommandPlugin
from ...core.context import Context
from ...core.commands import CommandResult
# Import all TTS providers
from ...providers.tts import (
    TTSProvider,
    ConsoleTTSProvider,
    PyttsTTSProvider,
    SileroV3TTSProvider,
    SileroV4TTSProvider,
    VoskTTSProvider,
    ElevenLabsTTSProvider  # Phase 4 addition
)

logger = logging.getLogger(__name__)


class UniversalTTSPlugin(TTSPlugin, WebAPIPlugin, CommandPlugin):
    """
    Universal TTS plugin that coordinates multiple TTS providers.
    
    Features:
    - Configuration-driven provider instantiation
    - Unified web API (/tts/* endpoints)
    - Voice command interface for TTS control
    - Provider fallback and load balancing
    - Runtime provider switching
    """
    
    @property
    def name(self) -> str:
        return "universal_tts"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Universal TTS coordinator managing multiple TTS providers with unified API"
        
    @property
    def dependencies(self) -> list[str]:
        return []  # No hard dependencies
        
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
        
    def __init__(self):
        super().__init__()
        self.providers: Dict[str, TTSProvider] = {}
        self._loaded_providers: Dict[str, TTSProvider] = {}  # Cache for lazy-loaded providers
        self.default_provider: str = "console"
        self.fallback_providers: List[str] = ["console"]
        self.core = None
        self._provider_configs: Dict[str, Dict[str, Any]] = {}  # Cache provider configs
        self._lazy_loading_enabled: bool = True  # Feature flag for lazy loading
        
        # Define available provider classes
        self._provider_classes = {
            "silero_v3": SileroV3TTSProvider,
            "silero_v4": SileroV4TTSProvider,
            "pyttsx": PyttsTTSProvider,
            "console": ConsoleTTSProvider,
            "vosk_tts": VoskTTSProvider,
            "elevenlabs": ElevenLabsTTSProvider  # Phase 4 addition
        }
        
    async def initialize(self, core) -> None:
        """Initialize providers with concurrent loading and lazy loading support"""
        self.core = core
        
        # Get configuration
        config = getattr(core.config.plugins, 'universal_tts', {})
        
        # Default configuration if not provided
        if not config:
            config = {
                "enabled": True,
                "default_provider": "console",
                "fallback_providers": ["console"],
                "lazy_loading": True,
                "concurrent_initialization": True,
                "providers": {
                    "console": {
                        "enabled": True,
                        "color_output": True,
                        "timing_simulation": False
                    }
                }
            }
            
        self.default_provider = config.get("default_provider", "console")
        self.fallback_providers = config.get("fallback_providers", ["console"])
        self._lazy_loading_enabled = config.get("lazy_loading", True)
        concurrent_init = config.get("concurrent_initialization", True)
        
        # Cache provider configurations for lazy loading
        self._provider_configs = config.get("providers", {})
        
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
            console_provider = ConsoleTTSProvider({"enabled": True, "color_output": True})
            self.providers["console"] = console_provider
            logger.info("Fallback: Loaded console TTS provider")
        except Exception as e:
            logger.error(f"Failed to load fallback console provider: {e}")
    
    # TTSPlugin interface - delegates to providers
    async def speak(self, text: str, **kwargs) -> None:
        """Convert text to speech using configured provider with lazy loading support"""
        provider_name = kwargs.get("provider", self.default_provider)
        
        # Try to get provider, with lazy loading if enabled
        provider = await self._get_provider(provider_name)
        
        if provider:
            try:
                # Pass core reference for audio playback
                kwargs["core"] = self.core
                await provider.speak(text, **kwargs)
            except Exception as e:
                logger.error(f"TTS provider {provider_name} failed: {e}")
                await self._speak_with_fallback(text, **kwargs)
        else:
            logger.warning(f"TTS provider {provider_name} not available")
            await self._speak_with_fallback(text, **kwargs)
    
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """Generate speech file using configured provider with lazy loading support"""
        provider_name = kwargs.get("provider", self.default_provider)
        
        # Try to get provider, with lazy loading if enabled
        provider = await self._get_provider(provider_name)
        
        if provider:
            try:
                await provider.to_file(text, output_path, **kwargs)
            except Exception as e:
                logger.error(f"TTS provider {provider_name} failed: {e}")
                raise
        else:
            raise ValueError(f"TTS provider {provider_name} not available")
    
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
    
    async def _speak_with_fallback(self, text: str, **kwargs) -> None:
        """Try fallback providers when primary fails"""
        for fallback_provider in self.fallback_providers:
            if fallback_provider in self.providers:
                try:
                    kwargs["core"] = self.core
                    await self.providers[fallback_provider].speak(text, **kwargs)
                    logger.info(f"Used fallback TTS provider: {fallback_provider}")
                    return
                except Exception as e:
                    logger.warning(f"Fallback TTS provider {fallback_provider} failed: {e}")
                    continue
        
        # All providers failed
        logger.error("All TTS providers failed")
        raise RuntimeError("No TTS providers available")
    
    # CommandPlugin interface - voice control
    def get_triggers(self) -> List[str]:
        """Get command triggers for TTS control"""
        return [
            "скажи", "говори", "произнеси", "голос", "переключись",
            "покажи голоса", "список голосов", "говори голосом"
        ]
    
    async def can_handle(self, command: str, context: Context) -> bool:
        """Check if this command is TTS-related"""
        triggers = self.get_triggers()
        command_lower = command.lower()
        return any(trigger in command_lower for trigger in triggers)
    
    async def handle_command(self, command: str, context: Context) -> CommandResult:
        """Handle TTS voice commands"""
        command_lower = command.lower()
        
        try:
            if "скажи" in command_lower and "голосом" in command_lower:
                # "скажи привет голосом ксении"
                result = await self._handle_speak_with_voice_command(command)
                return result
                
            elif "переключись на" in command_lower:
                # "переключись на силеро"
                result = await self._handle_switch_provider_command(command)
                return result
                
            elif any(phrase in command_lower for phrase in ["покажи голоса", "список голосов"]):
                # "покажи голоса" or "список голосов"
                result = await self._handle_list_voices_command()
                return result
                
            else:
                return CommandResult(
                    success=False, 
                    response="Неизвестная команда управления TTS"
                )
                
        except Exception as e:
            logger.error(f"TTS command handling error: {e}")
            return CommandResult(
                success=False,
                response=f"Ошибка обработки команды TTS: {e}"
            )
    
    async def _handle_speak_with_voice_command(self, command: str) -> CommandResult:
        """Handle 'скажи ... голосом ...' commands"""
        # Simple parsing - extract text and voice
        parts = command.lower().split()
        
        if "скажи" in parts and "голосом" in parts:
            try:
                speak_idx = parts.index("скажи")
                voice_idx = parts.index("голосом")
                
                # Extract text between "скажи" and "голосом"
                text_parts = parts[speak_idx + 1:voice_idx]
                text = " ".join(text_parts)
                
                # Extract voice/provider after "голосом"
                if voice_idx + 1 < len(parts):
                    voice_name = parts[voice_idx + 1]
                    
                    # Map voice names to providers
                    provider_mapping = {
                        "ксении": ("silero_v3", {"speaker": "xenia"}),
                        "кcении": ("silero_v3", {"speaker": "xenia"}),
                        "айдара": ("silero_v3", {"speaker": "aidar"}),
                        "силеро": ("silero_v3", {}),
                        "консоли": ("console", {}),
                        "системным": ("pyttsx", {})
                    }
                    
                    if voice_name in provider_mapping:
                        provider, params = provider_mapping[voice_name]
                        if provider in self.providers:
                            await self.speak(text, provider=provider, **params)
                            return CommandResult(
                                success=True,
                                response=f"Сказал '{text}' голосом {voice_name}"
                            )
                        else:
                            return CommandResult(
                                success=False,
                                response=f"Голос {voice_name} недоступен"
                            )
                    else:
                        # Use default provider
                        await self.speak(text)
                        return CommandResult(
                            success=True,
                            response=f"Сказал '{text}' обычным голосом"
                        )
                else:
                    # No voice specified, use default
                    await self.speak(text)
                    return CommandResult(
                        success=True,
                        response=f"Сказал '{text}'"
                    )
                    
            except Exception as e:
                return CommandResult(
                    success=False,
                    response=f"Ошибка обработки команды: {e}"
                )
        
        return CommandResult(
            success=False,
            response="Не удалось распознать команду"
        )
    
    async def _handle_switch_provider_command(self, command: str) -> CommandResult:
        """Handle provider switching commands"""
        command_lower = command.lower()
        
        # Simple provider name mapping
        provider_mapping = {
            "силеро": "silero_v3",
            "силеро3": "silero_v3", 
            "силеро4": "silero_v4",
            "консоль": "console",
            "системный": "pyttsx",
            "воск": "vosk_tts"
        }
        
        for name, provider in provider_mapping.items():
            if name in command_lower:
                if provider in self.providers:
                    self.default_provider = provider
                    return CommandResult(
                        success=True,
                        response=f"Переключился на TTS провайдер: {name}"
                    )
                else:
                    return CommandResult(
                        success=False,
                        response=f"TTS провайдер {name} недоступен"
                    )
        
        return CommandResult(
            success=False,
            response="Неизвестный TTS провайдер"
        )
    
    async def _handle_list_voices_command(self) -> CommandResult:
        """Handle list voices commands"""
        if not self.providers:
            return CommandResult(
                success=False,
                response="Нет доступных TTS провайдеров"
            )
        
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
        
        return CommandResult(
            success=True,
            response="\n".join(info)
        )
    
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
                    
                    await self.speak(request.text, provider=provider, **kwargs)
                    
                    return TTSResponse(
                        success=True,
                        provider=provider,
                        text=request.text
                    )
                    
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
        return ["TTS", "Text-to-Speech"] 