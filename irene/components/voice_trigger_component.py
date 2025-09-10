"""
Voice Trigger Component - Wake word detection component

This component leverages existing audio_helpers.py for audio management and
loader.py for dependency validation, following the implementation plan.
"""

import logging
from typing import Dict, Any, List, Optional, Type

from pydantic import BaseModel
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
        
        # Phase 5: Runtime monitoring
        self._resampling_metrics = {
            'total_resampling_operations': 0,
            'total_resampling_time_ms': 0.0,
            'resampling_failures': 0,
            'provider_fallbacks': 0,
            'configuration_warnings': 0,
            'detection_operations': 0,
            'detection_successes': 0,
            'detection_failures': 0
        }
        
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
    

    def get_component_dependencies(self) -> List[str]:
        """Get list of required component dependencies."""
        return []  # Voice trigger works independently with audio hardware
    
    def get_service_dependencies(self) -> Dict[str, type]:
        """Get list of required service dependencies."""
        return {}  # No service dependencies
        
    async def initialize(self, core=None):
        """Initialize the voice trigger component with provider loading."""
        await super().initialize(core)
        
        # Get configuration first to determine enabled providers (V14 Architecture)
        config = getattr(core.config, 'voice_trigger', None) if core else None
        if not config:
            # Create default config if missing
            from ..config.models import VoiceTriggerConfig
            config = VoiceTriggerConfig()
        
        # Convert Pydantic model to dict for backward compatibility with existing logic
        if hasattr(config, 'model_dump'):
            config = config.model_dump()
        elif hasattr(config, 'dict'):
            config = config.dict()
        else:
            # FATAL: Invalid configuration - cannot proceed with hardcoded defaults
            raise ValueError(
                "VoiceTriggerComponent: Invalid configuration object received. "
                "Expected a valid VoiceTriggerConfig instance, but got an invalid config. "
                "Please check your configuration file for proper v14 voice_trigger section formatting."
            )
        
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
    
    async def process_audio(self, audio_data: AudioData) -> WakeWordResult:
        """
        Process audio for workflow compatibility (Phase 1 bridge method)
        
        This is a bridge method that calls the existing detect method
        to maintain compatibility with workflow expectations.
        
        Args:
            audio_data: Audio data to analyze
            
        Returns:
            WakeWordResult with detection information
        """
        return await self.detect(audio_data)
        
    async def detect(self, audio_data: AudioData) -> WakeWordResult:
        """
        Detect wake words with intelligent sample rate handling (Phase 4 enhancement)
        
        This method implements the Phase 4 workflow:
        1. Check if resampling is needed based on configuration
        2. Apply efficient resampling if sample rates don't match
        3. Call provider detect_wake_word with correct format
        4. Handle provider fallbacks on configuration conflicts
        
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
        
        # Phase 4 Step 1: Get voice trigger configuration (AUTHORITATIVE per fix_vosk.md)
        voice_trigger_config = {}
        if hasattr(self, 'core') and self.core:
            config_obj = getattr(self.core.config, 'voice_trigger', {})
            if hasattr(config_obj, 'model_dump'):
                voice_trigger_config = config_obj.model_dump()
            elif hasattr(config_obj, 'dict'):
                voice_trigger_config = config_obj.dict()
            elif isinstance(config_obj, dict):
                voice_trigger_config = config_obj
        
        # Phase 4 Step 2: Check configuration authority (per fix_vosk.md Section 5.3)
        config_sample_rate = voice_trigger_config.get('sample_rate')
        allow_resampling = voice_trigger_config.get('allow_resampling', True)
        resample_quality = voice_trigger_config.get('resample_quality', 'fast')  # Fast for real-time
        
        logger.debug(f"Voice trigger configuration: sample_rate={config_sample_rate}, allow_resampling={allow_resampling}")
        logger.debug(f"Current audio rate: {audio_data.sample_rate}Hz")
        
        # Phase 4 Step 3: Apply configuration authority logic
        processed_audio = audio_data
        
        if config_sample_rate and config_sample_rate != audio_data.sample_rate:
            # Configuration is AUTHORITATIVE - must resample to config rate regardless of provider capabilities
            logger.info(f"Configuration requires {config_sample_rate}Hz, resampling from {audio_data.sample_rate}Hz for voice trigger (configuration authority)")
            
            if not allow_resampling:
                logger.error(f"Configuration requires {config_sample_rate}Hz but allow_resampling=false")
                return await self._detect_with_fallback(audio_data, provider.get_provider_name())
            
            try:
                # Use Phase 2 AudioProcessor for resampling
                from ..utils.audio_helpers import AudioProcessor, ConversionMethod
                
                # Phase 6: Get optimal conversion method for voice trigger (latency-optimized)
                conversion_method = AudioProcessor.get_optimal_conversion_path(
                    audio_data.sample_rate, config_sample_rate, use_case="voice_trigger"
                )
                
                # For voice trigger, prefer faster methods to reduce latency
                if resample_quality == 'fast':
                    conversion_method = ConversionMethod.LINEAR
                
                # Phase 5: Track resampling metrics
                import time
                start_time = time.time()
                
                try:
                    # Resample the audio data to configuration-required rate
                    processed_audio = await AudioProcessor.resample_audio_data(
                        audio_data, config_sample_rate, conversion_method
                    )
                    
                    # Update metrics
                    resampling_time = (time.time() - start_time) * 1000
                    self._resampling_metrics['total_resampling_operations'] += 1
                    self._resampling_metrics['total_resampling_time_ms'] += resampling_time
                    
                    logger.debug(f"Successfully resampled audio to {config_sample_rate}Hz using {conversion_method.value} in {resampling_time:.1f}ms")
                    
                except Exception as resampling_error:
                    # Update failure metrics
                    self._resampling_metrics['resampling_failures'] += 1
                    logger.error(f"Configuration-required resampling failed for voice trigger: {resampling_error}")
                    raise resampling_error
                
            except Exception as e:
                logger.error(f"Configuration authority resampling failed for voice trigger: {e}")
                # Continue to fallback handling
                return await self._detect_with_fallback(audio_data, provider.get_provider_name())
        
        elif config_sample_rate and config_sample_rate == audio_data.sample_rate:
            # Configuration matches input rate - use as-is
            logger.debug(f"Configuration authority: {audio_data.sample_rate}Hz matches required {config_sample_rate}Hz")
            # processed_audio already set to audio_data above
            
        else:
            # No configuration override - use provider preferences (fallback to old behavior)
            logger.debug(f"No configuration sample_rate specified, using provider preferences for voice trigger")
            
            try:
                supported_rates = provider.get_supported_sample_rates()
                default_rate = provider.get_default_sample_rate()
                supports_resampling = provider.supports_resampling()
                
                logger.debug(f"Voice trigger provider {provider.get_provider_name()} supported rates: {supported_rates}")
                logger.debug(f"Current audio rate: {audio_data.sample_rate}Hz, provider default: {default_rate}Hz")
                logger.debug(f"Provider supports resampling: {supports_resampling}")
                
                if audio_data.sample_rate not in supported_rates:
                    # Check if provider supports resampling or if we should handle it
                    if supports_resampling:
                        logger.debug(f"Provider {provider.get_provider_name()} will handle resampling internally")
                        # Provider will handle resampling internally - use original audio
                    else:
                        # We need to resample the audio externally
                        logger.info(f"Resampling audio from {audio_data.sample_rate}Hz to {default_rate}Hz for voice trigger")
                        
                        if allow_resampling:
                            # Use Phase 2 AudioProcessor for resampling
                            from ..utils.audio_helpers import AudioProcessor, ConversionMethod
                            
                            conversion_method = AudioProcessor.get_optimal_conversion_path(
                                audio_data.sample_rate, default_rate, use_case="voice_trigger"
                            )
                            
                            if resample_quality == 'fast':
                                conversion_method = ConversionMethod.LINEAR
                            
                            import time
                            start_time = time.time()
                            
                            try:
                                processed_audio = await AudioProcessor.resample_audio_data(
                                    audio_data, default_rate, conversion_method
                                )
                                
                                resampling_time = (time.time() - start_time) * 1000
                                self._resampling_metrics['total_resampling_operations'] += 1
                                self._resampling_metrics['total_resampling_time_ms'] += resampling_time
                                
                                logger.debug(f"Successfully resampled audio to {default_rate}Hz using {conversion_method.value} in {resampling_time:.1f}ms")
                                
                            except Exception as resampling_error:
                                self._resampling_metrics['resampling_failures'] += 1
                                logger.error(f"Resampling failed for voice trigger: {resampling_error}")
                                raise resampling_error
                        else:
                            logger.warning(f"Resampling disabled but required for {provider.get_provider_name()}")
                            # Continue with original audio - let provider handle the mismatch
                            
            except Exception as e:
                logger.warning(f"Could not get provider requirements for {provider.get_provider_name()}: {e}")
                # Fallback to simple detection for older providers
                try:
                    # Phase 5: Track detection operations
                    self._resampling_metrics['detection_operations'] += 1
                    result = await provider.detect_wake_word(audio_data)
                    
                    # Track successful detection
                    if result.detected:
                        self._resampling_metrics['detection_successes'] += 1
                        
                    return result
                except Exception as detection_error:
                    logger.error(f"Voice trigger detection error: {detection_error}")
                    self._resampling_metrics['detection_failures'] += 1
                    return await self._detect_with_fallback(audio_data, provider.get_provider_name())
        
        # Phase 4 Step 3: Call provider detect_wake_word with correct format
        try:
            # Phase 5: Track detection operations
            self._resampling_metrics['detection_operations'] += 1
            result = await provider.detect_wake_word(processed_audio)
            
            # Track successful detection
            if result.detected:
                self._resampling_metrics['detection_successes'] += 1
                
            return result
        except Exception as e:
            logger.error(f"Voice trigger detection error with {provider.get_provider_name()}: {e}")
            self._resampling_metrics['detection_failures'] += 1
            # Phase 4 Step 4: Handle provider fallbacks on configuration conflicts
            return await self._detect_with_fallback(audio_data, provider.get_provider_name())
    
    async def _detect_with_fallback(self, audio_data: AudioData, failed_provider: str) -> WakeWordResult:
        """
        Attempt detection with fallback providers with sample rate intelligence (Phase 4 enhancement)
        """
        for fallback in self.fallback_providers:
            if fallback != failed_provider and fallback in self.providers:
                try:
                    fallback_provider = self.providers[fallback]
                    logger.info(f"Trying fallback voice trigger provider: {fallback}")
                    
                    # Check if fallback provider supports the current sample rate
                    try:
                        supported_rates = fallback_provider.get_supported_sample_rates()
                        if audio_data.sample_rate in supported_rates:
                            logger.debug(f"Fallback provider {fallback} supports {audio_data.sample_rate}Hz")
                            result = await fallback_provider.detect_wake_word(audio_data)
                            return result
                        else:
                            # Try resampling for fallback provider
                            default_rate = fallback_provider.get_default_sample_rate()
                            supports_resampling = fallback_provider.supports_resampling()
                            
                            if supports_resampling:
                                logger.debug(f"Fallback provider {fallback} will handle resampling internally")
                                result = await fallback_provider.detect_wake_word(audio_data)
                                return result
                            else:
                                # External resampling for fallback
                                logger.info(f"Resampling for fallback provider {fallback}: {audio_data.sample_rate}Hz -> {default_rate}Hz")
                                
                                from ..utils.audio_helpers import AudioProcessor, ConversionMethod
                                
                                # Phase 5: Track fallback resampling metrics  
                                import time
                                start_time = time.time()
                                
                                try:
                                    # Use fast resampling for fallback scenarios
                                    resampled_audio = await AudioProcessor.resample_audio_data(
                                        audio_data, default_rate, ConversionMethod.LINEAR
                                    )
                                    
                                    # Update metrics
                                    resampling_time = (time.time() - start_time) * 1000
                                    self._resampling_metrics['total_resampling_operations'] += 1
                                    self._resampling_metrics['total_resampling_time_ms'] += resampling_time
                                    self._resampling_metrics['provider_fallbacks'] += 1
                                    
                                except Exception as resampling_error:
                                    self._resampling_metrics['resampling_failures'] += 1
                                    raise resampling_error
                                
                                result = await fallback_provider.detect_wake_word(resampled_audio)
                                return result
                                
                    except Exception as provider_error:
                        logger.warning(f"Could not get provider requirements for fallback {fallback}: {provider_error}")
                        # Try anyway with original audio
                        result = await fallback_provider.detect_wake_word(audio_data)
                        return result
                        
                except Exception as e:
                    logger.warning(f"Fallback provider {fallback} also failed: {e}")
                    continue
        
        logger.error("All voice trigger providers failed")
        return WakeWordResult(detected=False, confidence=0.0)
    
    def get_current_provider(self) -> Optional[VoiceTriggerProvider]:
        """Get the current voice trigger provider."""
        if self.default_provider in self.providers:
            return self.providers[self.default_provider]
        elif self.providers:
            return list(self.providers.values())[0]
        return None
    
    def get_providers_info(self) -> str:
        """Implementation of abstract method - Get voice trigger providers information"""
        if not self.providers:
            return "Нет доступных провайдеров активации по голосу"
        
        info_lines = [f"Доступные провайдеры активации ({len(self.providers)}):"]
        for name, provider in self.providers.items():
            status = "✓ (по умолчанию)" if name == self.default_provider else "✓"
            capabilities = provider.get_capabilities()
            wake_words = capabilities.get("wake_words", self.wake_words)
            info_lines.append(f"  {status} {name}: {', '.join(wake_words[:3])}")
        
        info_lines.append(f"Порог обнаружения: {self.threshold}")
        info_lines.append(f"Активные слова: {', '.join(self.wake_words)}")
        
        return "\n".join(info_lines)
    
    def get_runtime_metrics(self) -> Dict[str, Any]:
        """Get Phase 5 runtime monitoring metrics"""
        avg_resampling_time = 0.0
        if self._resampling_metrics['total_resampling_operations'] > 0:
            avg_resampling_time = (
                self._resampling_metrics['total_resampling_time_ms'] / 
                self._resampling_metrics['total_resampling_operations']
            )
        
        detection_success_rate = 0.0
        if self._resampling_metrics['detection_operations'] > 0:
            detection_success_rate = (
                self._resampling_metrics['detection_successes'] / 
                self._resampling_metrics['detection_operations']
            )
        
        resampling_success_rate = 0.0
        if self._resampling_metrics['total_resampling_operations'] > 0:
            resampling_success_rate = (
                (self._resampling_metrics['total_resampling_operations'] - self._resampling_metrics['resampling_failures']) /
                self._resampling_metrics['total_resampling_operations']
            )
        
        return {
            **self._resampling_metrics,
            'average_resampling_time_ms': avg_resampling_time,
            'resampling_success_rate': resampling_success_rate,
            'detection_success_rate': detection_success_rate
        }
    
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

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Voice trigger component needs web API functionality"""
        return ["fastapi>=0.100.0", "uvicorn[standard]>=0.20.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Voice trigger component has no system dependencies - coordinates providers only"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Voice trigger component supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    # Config interface methods (Phase 3 - Configuration Architecture Cleanup)
    @classmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the Pydantic config model for this component"""
        from ..config.models import VoiceTriggerConfig  # Note: NOT Universal*
        return VoiceTriggerConfig
    
    @classmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to this component's config (V14 Architecture)"""
        return "voice_trigger" 