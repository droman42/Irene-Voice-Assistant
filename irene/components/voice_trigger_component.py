"""
Voice Trigger Component - Wake word detection component

This component leverages existing audio_helpers.py for audio management and
loader.py for dependency validation, following the implementation plan.
"""

import logging
from typing import Dict, Any, List, Optional

from .base import Component
from ..core.interfaces.webapi import WebAPIPlugin
from ..intents.models import AudioData, WakeWordResult
from ..utils.audio_helpers import calculate_audio_buffer_size, validate_audio_file
from ..utils.loader import DependencyChecker, safe_import

# Voice trigger provider base class and dynamic loader
from ..providers.voice_trigger import VoiceTriggerProvider
from ..utils.loader import DependencyChecker, safe_import, dynamic_loader

logger = logging.getLogger(__name__)


class VoiceTriggerComponent(Component, WebAPIPlugin):
    """Voice trigger detection component - uses audio_helpers.py for audio management"""
    
    def __init__(self):
        super().__init__()
        self.dependency_checker = DependencyChecker()  # From loader.py
        self.buffer_size = calculate_audio_buffer_size(16000, 100.0)  # From audio_helpers.py
        self.wake_words = ["irene", "jarvis"]
        self.threshold = 0.8
        self.active = False
        
        # Provider management
        self.providers: Dict[str, VoiceTriggerProvider] = {}
        self.default_provider = "openwakeword"
        self.fallback_providers = ["openwakeword"]
        
        # Dynamic provider discovery from entry-points (replaces hardcoded classes)
        self._provider_classes: Dict[str, type] = {}
        
    @property
    def name(self) -> str:
        return "voice_trigger"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Voice trigger detection component with multiple provider support"
        
    @property
    def dependencies(self) -> List[str]:
        return []  # No hard dependencies - providers handle their own
        
    @property
    def optional_dependencies(self) -> List[str]:
        return ["openwakeword", "tflite-runtime", "numpy", "librosa"]
        
    @property
    def enabled_by_default(self) -> bool:
        return True
        
    @property  
    def category(self) -> str:
        return "voice_trigger"
        
    @property
    def platforms(self) -> List[str]:
        return []  # All platforms
    
    def get_dependencies(self) -> List[str]:
        """Get list of dependencies for this component."""
        return self.dependencies  # Use @property for consistency
        
    async def initialize(self, core=None):
        """Initialize the voice trigger component with provider loading."""
        await super().initialize(core)
        
        # Get configuration first to determine enabled providers
        config = getattr(core.config.plugins, 'voice_trigger', None) if core else None
        if not config:
            # Create default config if missing
            config = {
                "enabled": True,
                "default_provider": "openwakeword",
                "fallback_providers": ["openwakeword"],
                "wake_words": ["irene", "jarvis"],
                "threshold": 0.8,
                "providers": {
                    "openwakeword": {
                        "enabled": True,
                        "inference_framework": "tflite",
                        "chunk_size": 1280
                    },
                    "microwakeword": {
                        "enabled": False,
                        "model_path": None,
                        "feature_buffer_size": 49,
                        "detection_window_size": 3
                    }
                }
            }
        
        # Update settings from config
        if isinstance(config, dict):
            self.default_provider = config.get("default_provider", self.default_provider)
            self.fallback_providers = config.get("fallback_providers", self.fallback_providers)
            self.wake_words = config.get("wake_words", self.wake_words)
            self.threshold = config.get("threshold", self.threshold)
        else:
            # Handle config object case
            if hasattr(config, 'default_provider'):
                self.default_provider = config.default_provider
            if hasattr(config, 'fallback_providers'):
                self.fallback_providers = config.fallback_providers
            if hasattr(config, 'wake_words'):
                self.wake_words = config.wake_words
            if hasattr(config, 'threshold'):
                self.threshold = config.threshold
        
        # Instantiate enabled providers
        providers_config = getattr(config, 'providers', {})
        if isinstance(config, dict):
            providers_config = config.get('providers', {})
        
        # Discover only enabled providers from entry-points (configuration-driven filtering)
        enabled_providers = [name for name, provider_config in providers_config.items() 
                            if provider_config.get("enabled", False)]
        
        # Always include openwakeword as fallback if not already included
        if "openwakeword" not in enabled_providers and providers_config.get("openwakeword", {}).get("enabled", True):
            enabled_providers.append("openwakeword")
            
        self._provider_classes = dynamic_loader.discover_providers("irene.providers.voice_trigger", enabled_providers)
        logger.info(f"Discovered {len(self._provider_classes)} enabled voice trigger providers: {list(self._provider_classes.keys())}")
        
        enabled_count = 0
        
        for provider_name, provider_class in self._provider_classes.items():
            provider_config = providers_config.get(provider_name, {})
            if provider_config.get("enabled", False):
                try:
                    # Add common configuration
                    provider_config.update({
                        "wake_words": self.wake_words,
                        "threshold": self.threshold,
                        "sample_rate": 16000,
                        "channels": 1
                    })
                    
                    provider = provider_class(provider_config)
                    if await provider.is_available():
                        self.providers[provider_name] = provider
                        enabled_count += 1
                        logger.info(f"Loaded voice trigger provider: {provider_name}")
                    else:
                        logger.warning(f"Voice trigger provider {provider_name} not available (dependencies missing)")
                except TypeError as e:
                    logger.error(f"Voice trigger provider {provider_name} missing required abstract methods: {e}")
                except Exception as e:
                    logger.warning(f"Failed to load voice trigger provider {provider_name}: {e}")
        
        # Ensure we have at least one provider
        if not self.providers:
            logger.warning("No voice trigger providers available, trying to create OpenWakeWord as fallback")
            try:
                fallback_config = {
                    "enabled": True,
                    "wake_words": self.wake_words,
                    "threshold": self.threshold,
                    "sample_rate": 16000,
                    "channels": 1,
                    "inference_framework": "tflite"
                }
                # Use entry-points discovery for fallback provider
                openwakeword_class = dynamic_loader.get_provider_class("irene.providers.voice_trigger", "openwakeword")
                if openwakeword_class:
                    openwakeword_provider = openwakeword_class(fallback_config)
                    if await openwakeword_provider.is_available():
                        self.providers["openwakeword"] = openwakeword_provider
                        self.default_provider = "openwakeword"
                        self.fallback_providers = ["openwakeword"]
                        enabled_count = 1
                    logger.info("Created fallback OpenWakeWord provider")
                else:
                    logger.warning("No voice trigger providers available")
            except Exception as e:
                logger.error(f"Failed to create fallback voice trigger provider: {e}")
        
        # Set default to first available if current default not available
        if self.default_provider not in self.providers and self.providers:
            self.default_provider = list(self.providers.keys())[0]
            
        self.active = len(self.providers) > 0
        logger.info(f"Voice trigger component initialized with {enabled_count} providers. Default: {self.default_provider}")
        return self.active
        
    async def detect(self, audio_data: AudioData) -> WakeWordResult:
        """
        Detect wake words in audio data.
        
        Args:
            audio_data: Audio data to analyze
            
        Returns:
            WakeWordResult with detection information
        """
        if not self.active:
            return WakeWordResult(detected=False, confidence=0.0)
            
        # Get current provider
        provider = self.get_current_provider()
        if not provider:
            logger.warning("No voice trigger provider available")
            return WakeWordResult(detected=False, confidence=0.0)
            
        try:
            return await provider.detect_wake_word(audio_data)
        except Exception as e:
            logger.error(f"Voice trigger detection error with {provider.get_provider_name()}: {e}")
            # Try fallback providers
            return await self._detect_with_fallback(audio_data, provider.get_provider_name())
    
    async def _detect_with_fallback(self, audio_data: AudioData, failed_provider: str) -> WakeWordResult:
        """Attempt detection with fallback providers."""
        for fallback in self.fallback_providers:
            if fallback != failed_provider and fallback in self.providers:
                try:
                    logger.info(f"Trying fallback voice trigger provider: {fallback}")
                    result = await self.providers[fallback].detect_wake_word(audio_data)
                    return result
                except Exception as e:
                    logger.warning(f"Fallback provider {fallback} also failed: {e}")
        
        logger.error("All voice trigger providers failed")
        return WakeWordResult(detected=False, confidence=0.0)
    
    def get_current_provider(self) -> Optional[VoiceTriggerProvider]:
        """Get the current voice trigger provider."""
        if self.default_provider in self.providers:
            return self.providers[self.default_provider]
        elif self.providers:
            return list(self.providers.values())[0]
        return None
    
    def get_wake_words(self) -> List[str]:
        """Get current wake words."""
        return self.wake_words.copy()
    
    def get_threshold(self) -> float:
        """Get current detection threshold."""
        return self.threshold
    
    def is_active(self) -> bool:
        """Check if voice trigger is active."""
        return self.active and len(self.providers) > 0
    
    async def set_wake_words(self, wake_words: List[str]) -> bool:
        """Set new wake words for all providers."""
        self.wake_words = wake_words
        success = True
        for provider in self.providers.values():
            try:
                await provider.set_wake_words(wake_words)
            except Exception as e:
                logger.error(f"Failed to set wake words for {provider.get_provider_name()}: {e}")
                success = False
        return success
    
    async def set_threshold(self, threshold: float) -> bool:
        """Set new detection threshold for all providers."""
        if not 0.0 <= threshold <= 1.0:
            logger.warning(f"Invalid threshold {threshold}, must be between 0.0 and 1.0")
            return False
        
        self.threshold = threshold
        success = True
        for provider in self.providers.values():
            try:
                await provider.set_threshold(threshold)
            except Exception as e:
                logger.error(f"Failed to set threshold for {provider.get_provider_name()}: {e}")
                success = False
        
        logger.info(f"Updated threshold: {threshold}")
        return success
    
    # WebAPIPlugin interface - following universal plugin pattern
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with voice trigger endpoints"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter, HTTPException, WebSocket  # type: ignore
            from pydantic import BaseModel  # type: ignore
            
            router = APIRouter()
            
            # Request/Response models
            class VoiceTriggerStatus(BaseModel):
                active: bool
                wake_words: List[str]
                threshold: float
                provider: str
                providers_available: List[str]
                
            class WakeWordConfig(BaseModel):
                wake_words: List[str]
                threshold: float = 0.8
                
            @router.get("/status", response_model=VoiceTriggerStatus)
            async def get_status():
                """Get voice trigger status and configuration"""
                return VoiceTriggerStatus(
                    active=self.is_active(),
                    wake_words=self.get_wake_words(),
                    threshold=self.get_threshold(),
                    provider=self.default_provider or "none",
                    providers_available=list(self.providers.keys())
                )
            
            @router.post("/configure")
            async def configure_voice_trigger(config: WakeWordConfig):
                """Configure voice trigger settings"""
                success_words = await self.set_wake_words(config.wake_words)
                success_threshold = await self.set_threshold(config.threshold)
                return {
                    "success": success_words and success_threshold,
                    "config": config,
                    "updated_words": success_words,
                    "updated_threshold": success_threshold
                }
            
            @router.get("/providers")
            async def list_voice_trigger_providers():
                """Discovery endpoint for voice trigger provider capabilities"""
                result = {}
                for name, provider in self.providers.items():
                    result[name] = {
                        "available": await provider.is_available(),
                        "wake_words": provider.get_supported_wake_words(),
                        "capabilities": provider.get_capabilities(),
                        "parameters": provider.get_parameter_schema(),
                        "is_default": name == self.default_provider
                    }
                return {
                    "providers": result,
                    "default": self.default_provider,
                    "fallbacks": self.fallback_providers
                }
            
            @router.post("/switch_provider")
            async def switch_provider(provider_name: str):
                """Switch to a different voice trigger provider"""
                if provider_name not in self.providers:
                    raise HTTPException(404, f"Provider '{provider_name}' not available")
                
                self.default_provider = provider_name
                return {
                    "success": True,
                    "active_provider": provider_name,
                    "wake_words": self.get_wake_words(),
                    "threshold": self.get_threshold()
                }
            
            return router
            
        except ImportError:
            logger.warning("FastAPI not available for voice trigger web API")
            return None
    
    def is_api_available(self) -> bool:
        """Check if FastAPI dependencies are available for web API."""
        fastapi = safe_import('fastapi')
        pydantic = safe_import('pydantic')
        return fastapi is not None and pydantic is not None 