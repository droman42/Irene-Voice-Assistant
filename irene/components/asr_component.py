"""
ASR Component

Speech Recognition Coordinator managing multiple ASR providers.
Provides unified web API (/asr/*), voice commands, and multi-source audio processing.
"""

from typing import Dict, Any, List, Optional, AsyncIterator, Type
from pathlib import Path
import json
import time
import base64
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect  # type: ignore
from pydantic import BaseModel
from .base import Component
from ..core.interfaces.asr import ASRPlugin
from ..core.interfaces.webapi import WebAPIPlugin
from ..intents.models import AudioData


# Import ASR provider base class and dynamic loader
from ..providers.asr import ASRProvider
from ..utils.loader import dynamic_loader

logger = logging.getLogger(__name__)


class ASRComponent(Component, ASRPlugin, WebAPIPlugin):
    """
    ASR Component - Speech Recognition Coordinator
    
    Manages multiple ASR providers and provides:
    - Unified web API (/asr/*)
    - Voice commands for ASR control
    - Multi-source audio processing (microphone, web, files)
    - Provider switching and fallbacks
    """
    
    @property
    def name(self) -> str:
        return "asr"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "ASR component coordinating multiple speech recognition providers"
        

        
    @property
    def optional_dependencies(self) -> List[str]:
        return ["vosk", "openai-whisper", "google-cloud-speech", "numpy", "soundfile"]
        
    @property
    def enabled_by_default(self) -> bool:
        return True
        
    @property  
    def category(self) -> str:
        return "asr"
        
    @property
    def platforms(self) -> List[str]:
        return []  # All platforms
    

    def get_component_dependencies(self) -> List[str]:
        """Get list of required component dependencies."""
        return []  # ASR is foundational, no component dependencies
    
    def get_service_dependencies(self) -> Dict[str, type]:
        """Get list of required service dependencies."""
        return {}  # No service dependencies
    
    def __init__(self):
        super().__init__()
        self.providers: Dict[str, ASRProvider] = {}  # Proper ABC type hint
        self.default_provider = "vosk"
        self.default_language = "ru"
        self.core = None  # Store core reference for LLM integration
        
        # Dynamic provider discovery from entry-points (replaces hardcoded classes)
        self._provider_classes: Dict[str, type] = {}
        
        # Phase 5: Runtime monitoring
        self._resampling_metrics = {
            'total_resampling_operations': 0,
            'total_resampling_time_ms': 0.0,
            'resampling_failures': 0,
            'provider_fallbacks': 0,
            'configuration_warnings': 0
        }
        
    async def initialize(self, core) -> None:
        """Initialize ASR providers from configuration"""
        await super().initialize(core)
        try:
            self.core = core  # Store core reference
            
            # Get configuration (V14 Architecture)
            config = getattr(core.config, 'asr', None)
            if not config:
                # Create default config if missing
                from ..config.models import ASRConfig
                config = ASRConfig()
            
            # Convert Pydantic model to dict for backward compatibility with existing logic
            if hasattr(config, 'model_dump'):
                config = config.model_dump()
            elif hasattr(config, 'dict'):
                config = config.dict()
            else:
                # FATAL: Invalid configuration - cannot proceed with hardcoded defaults
                raise ValueError(
                    "ASRComponent: Invalid configuration object received. "
                    "Expected a valid ASRConfig instance, but got an invalid config. "
                    "Please check your configuration file for proper v14 asr section formatting."
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
            
            self._provider_classes = dynamic_loader.discover_providers("irene.providers.asr", enabled_providers)
            logger.info(f"Discovered {len(self._provider_classes)} enabled ASR providers: {list(self._provider_classes.keys())}")
            
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
                            logger.info(f"Loaded ASR provider: {provider_name}")
                        else:
                            logger.warning(f"ASR provider {provider_name} not available (dependencies missing)")
                    except TypeError as e:
                        logger.error(f"ASR provider {provider_name} missing required abstract methods: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to load ASR provider {provider_name}: {e}")
            
            # Set defaults from config
            if isinstance(config, dict):
                self.default_provider = config.get("default_provider", "vosk")
                self.default_language = config.get("default_language", "ru")
            else:
                self.default_provider = getattr(config, "default_provider", "vosk")
                self.default_language = getattr(config, "default_language", "ru")
            
            # Ensure we have at least one provider
            if not self.providers:
                logger.warning("No ASR providers available")
            else:
                logger.info(f"Universal ASR Plugin initialized with {len(self.providers)} providers")
                
        except Exception as e:
            logger.error(f"Failed to initialize Universal ASR Plugin: {e}")
    
    # Workflow-compatible interface for AudioData objects
    async def process_audio(self, audio_data: AudioData, **kwargs) -> str:
        """
        Process AudioData with intelligent sample rate handling (Phase 4 enhancement)
        
        This method implements the complete Phase 4 workflow:
        1. Extract provider requirements
        2. Check sample rate compatibility  
        3. Auto-resample if needed and supported
        4. Call transcribe_audio with converted data
        5. Handle fallback providers on rate mismatch
        
        Args:
            audio_data: AudioData object containing audio bytes and metadata
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Transcribed text
        """
        provider_name = kwargs.get("provider", self.default_provider)
        
        # Debug logging for audio data reception
        logger.info(f"🎧 ASR received audio data: {len(audio_data.data)} bytes, "
                   f"sample_rate={audio_data.sample_rate}, channels={audio_data.channels}, "
                   f"format={audio_data.format}, provider={provider_name}")
        
        if provider_name not in self.providers:
            logger.error(f"❌ ASR provider '{provider_name}' not available. Available: {list(self.providers.keys())}")
            raise ValueError(f"ASR provider '{provider_name}' not available")
        
        provider = self.providers[provider_name]
        
        # Phase 4 Step 1: Get ASR configuration (AUTHORITATIVE per fix_vosk.md)
        asr_config = {}
        if hasattr(self, 'core') and self.core:
            config_obj = getattr(self.core.config, 'asr', {})
            if hasattr(config_obj, 'model_dump'):
                asr_config = config_obj.model_dump()
            elif hasattr(config_obj, 'dict'):
                asr_config = config_obj.dict()
            elif isinstance(config_obj, dict):
                asr_config = config_obj
        
        # Phase 4 Step 2: Check configuration authority (per fix_vosk.md Section 5.3)
        config_sample_rate = asr_config.get('sample_rate')
        allow_resampling = asr_config.get('allow_resampling', True)
        resample_quality = asr_config.get('resample_quality', 'high')
        
        logger.debug(f"ASR configuration: sample_rate={config_sample_rate}, allow_resampling={allow_resampling}")
        logger.debug(f"Current audio rate: {audio_data.sample_rate}Hz")
        
        # Phase 4 Step 3: Apply configuration authority logic
        if config_sample_rate and config_sample_rate != audio_data.sample_rate:
            # Configuration is AUTHORITATIVE - must resample to config rate regardless of provider capabilities
            logger.info(f"Configuration requires {config_sample_rate}Hz, resampling from {audio_data.sample_rate}Hz (configuration authority)")
            
            if not allow_resampling:
                logger.error(f"Configuration requires {config_sample_rate}Hz but allow_resampling=false")
                return await self._handle_sample_rate_mismatch(audio_data, provider, **kwargs)
            
            try:
                # Use Phase 2 AudioProcessor for resampling
                from ..utils.audio_helpers import AudioProcessor, ConversionMethod
                
                # Phase 6: Get optimal conversion method for ASR (quality-optimized)
                conversion_method = AudioProcessor.get_optimal_conversion_path(
                    audio_data.sample_rate, config_sample_rate, use_case="asr"
                )
                
                # Phase 5: Track resampling metrics
                import time
                start_time = time.time()
                
                try:
                    # Resample the audio data to configuration-required rate
                    resampled_audio = await AudioProcessor.resample_audio_data(
                        audio_data, config_sample_rate, conversion_method
                    )
                    
                    # Update metrics
                    resampling_time = (time.time() - start_time) * 1000
                    self._resampling_metrics['total_resampling_operations'] += 1
                    self._resampling_metrics['total_resampling_time_ms'] += resampling_time
                    
                    logger.debug(f"Successfully resampled audio to {config_sample_rate}Hz using {conversion_method.value} in {resampling_time:.1f}ms")
                    
                    # Phase 4 Step 4: Call transcribe_audio with configuration-compliant data
                    return await self.transcribe_audio(resampled_audio.data, **kwargs)
                    
                except Exception as resampling_error:
                    # Update failure metrics
                    self._resampling_metrics['resampling_failures'] += 1
                    logger.error(f"Configuration-required resampling failed: {resampling_error}")
                    raise resampling_error
                
            except Exception as e:
                logger.error(f"Configuration authority resampling failed for {provider_name}: {e}")
                # Continue to fallback handling
        
        elif config_sample_rate and config_sample_rate == audio_data.sample_rate:
            # Configuration matches input rate - use as-is
            logger.debug(f"Configuration authority: {audio_data.sample_rate}Hz matches required {config_sample_rate}Hz")
            audio_bytes = audio_data.data
            return await self.transcribe_audio(audio_bytes, **kwargs)
            
        else:
            # No configuration override - use provider preferences (fallback to old behavior)
            logger.debug(f"No configuration sample_rate specified, using provider preferences for {provider_name}")
            
            try:
                preferred_rates = provider.get_preferred_sample_rates()
                supports_rate = provider.supports_sample_rate(audio_data.sample_rate)
                
                logger.debug(f"ASR provider {provider_name} preferred rates: {preferred_rates}")
                logger.debug(f"Current audio rate {audio_data.sample_rate}Hz supported: {supports_rate}")
                
                if supports_rate:
                    # Direct compatibility - use audio as-is
                    logger.debug(f"Direct compatibility: {audio_data.sample_rate}Hz supported by {provider_name}")
                    audio_bytes = audio_data.data
                    return await self.transcribe_audio(audio_bytes, **kwargs)
                elif allow_resampling and preferred_rates:
                    # Attempt resampling to preferred rate
                    target_rate = preferred_rates[0]  # Use most preferred rate
                    logger.info(f"Resampling audio from {audio_data.sample_rate}Hz to {target_rate}Hz for {provider_name}")
                    
                    # Use Phase 2 AudioProcessor for resampling
                    from ..utils.audio_helpers import AudioProcessor, ConversionMethod
                    
                    conversion_method = AudioProcessor.get_optimal_conversion_path(
                        audio_data.sample_rate, target_rate, use_case="asr"
                    )
                    
                    import time
                    start_time = time.time()
                    
                    try:
                        resampled_audio = await AudioProcessor.resample_audio_data(
                            audio_data, target_rate, conversion_method
                        )
                        
                        resampling_time = (time.time() - start_time) * 1000
                        self._resampling_metrics['total_resampling_operations'] += 1
                        self._resampling_metrics['total_resampling_time_ms'] += resampling_time
                        
                        logger.debug(f"Successfully resampled audio to {target_rate}Hz using {conversion_method.value} in {resampling_time:.1f}ms")
                        
                        return await self.transcribe_audio(resampled_audio.data, **kwargs)
                        
                    except Exception as resampling_error:
                        self._resampling_metrics['resampling_failures'] += 1
                        raise resampling_error
                        
            except Exception as e:
                logger.warning(f"Could not get provider requirements for {provider_name}: {e}")
                # Fallback to simple extraction for older providers
                audio_bytes = audio_data.data
                return await self.transcribe_audio(audio_bytes, **kwargs)
        
        # Phase 4 Step 5: Handle fallback providers on rate mismatch
        return await self._handle_sample_rate_mismatch(audio_data, provider, **kwargs)
    
    async def _handle_sample_rate_mismatch(self, audio_data: AudioData, provider, **kwargs) -> str:
        """
        Handle sample rate mismatch by attempting resampling or fallback providers (Phase 4)
        
        Args:
            audio_data: Original AudioData with incompatible sample rate
            provider: Primary provider that doesn't support the sample rate
            **kwargs: Additional parameters
            
        Returns:
            Transcribed text from fallback strategy
        """
        provider_name = provider.get_provider_name()
        logger.warning(f"Sample rate mismatch: {audio_data.sample_rate}Hz not supported by {provider_name}")
        
        # Try other available providers that might support this sample rate
        for fallback_name, fallback_provider in self.providers.items():
            if fallback_name == provider_name:
                continue  # Skip the failing provider
                
            try:
                if fallback_provider.supports_sample_rate(audio_data.sample_rate):
                    logger.info(f"Using fallback provider {fallback_name} for {audio_data.sample_rate}Hz audio")
                    
                    # Phase 5: Track provider fallback
                    self._resampling_metrics['provider_fallbacks'] += 1
                    
                    # Temporarily switch provider and recurse
                    kwargs_copy = kwargs.copy()
                    kwargs_copy["provider"] = fallback_name
                    return await self.process_audio(audio_data, **kwargs_copy)
                    
            except Exception as e:
                logger.warning(f"Fallback provider {fallback_name} failed: {e}")
                continue
        
        # If no fallback providers work, try force resampling to a common rate
        logger.warning(f"No compatible providers found for {audio_data.sample_rate}Hz, force resampling to 16kHz")
        
        try:
            from ..utils.audio_helpers import AudioProcessor, ConversionMethod
            
            # Force resample to 16kHz (most common rate)
            target_rate = 16000
            conversion_method = AudioProcessor.get_optimal_conversion_path(
                audio_data.sample_rate, target_rate, use_case="asr"
            )
            
            resampled_audio = await AudioProcessor.resample_audio_data(
                audio_data, target_rate, conversion_method
            )
            
            logger.info(f"Force resampled to {target_rate}Hz, retrying with original provider")
            
            # Try original provider again with resampled audio
            return await self.transcribe_audio(resampled_audio.data, **kwargs)
            
        except Exception as e:
            logger.error(f"Force resampling failed: {e}")
            
            # Last resort: try with original audio data anyway
            logger.warning(f"Using original audio data despite rate mismatch - quality may be degraded")
            return await self.transcribe_audio(audio_data.data, **kwargs)
    
    # Primary ASR interface - used by input sources
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        """
        Core ASR functionality - transcribe audio to text
        
        Args:
            audio_data: Raw audio bytes
            provider: ASR provider to use (default: self.default_provider)
            language: Language code (default: self.default_language)
            **kwargs: Provider-specific parameters
            
        Returns:
            Transcribed text
        """
        provider_name = kwargs.get("provider", self.default_provider)
        language = kwargs.get("language", self.default_language)
        
        if provider_name not in self.providers:
            raise HTTPException(404, f"ASR provider '{provider_name}' not available")
        
        provider = self.providers[provider_name]
        
        # Start timing for performance metrics
        start_time = time.time()
        
        # Perform transcription
        result = await provider.transcribe_audio(audio_data, language=language, **kwargs)
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Log ASR result with info level
        if result and result.strip():
            logger.info(f"🎯 ASR transcription successful: '{result}' "
                       f"(provider: {provider_name}, language: {language}, "
                       f"processing_time: {processing_time:.1f}ms, "
                       f"audio_size: {len(audio_data)} bytes)")
        else:
            logger.info(f"📭 ASR transcription empty "
                       f"(provider: {provider_name}, language: {language}, "
                       f"processing_time: {processing_time:.1f}ms, "
                       f"audio_size: {len(audio_data)} bytes)")
        
        return result
    
    # Public methods for intent handler delegation
    def set_default_provider(self, provider_name: str) -> bool:
        """Set default ASR provider - simple atomic operation"""
        if provider_name in self.providers:
            self.default_provider = provider_name
            return True
        return False
    
    def get_providers_info(self) -> str:
        """Implementation of abstract method - Get ASR providers information"""
        return self._get_providers_info()
    
    def get_runtime_metrics(self) -> Dict[str, Any]:
        """Get Phase 5 runtime monitoring metrics enhanced with Phase 6 cache statistics"""
        avg_resampling_time = 0.0
        if self._resampling_metrics['total_resampling_operations'] > 0:
            avg_resampling_time = (
                self._resampling_metrics['total_resampling_time_ms'] / 
                self._resampling_metrics['total_resampling_operations']
            )
        
        # Phase 6: Include cache performance metrics
        from ..utils.audio_helpers import AudioProcessor
        cache_stats = AudioProcessor.get_cache_stats()
        
        return {
            **self._resampling_metrics,
            'average_resampling_time_ms': avg_resampling_time,
            'resampling_success_rate': (
                (self._resampling_metrics['total_resampling_operations'] - self._resampling_metrics['resampling_failures']) /
                max(1, self._resampling_metrics['total_resampling_operations'])
            ),
            'cache_statistics': cache_stats
        }
    
    def parse_provider_name_from_text(self, text: str) -> Optional[str]:
        """Override base method with ASR-specific aliases and logic"""
        # First try base implementation
        result = super().parse_provider_name_from_text(text)
        if result:
            return result
        
        # ASR-specific aliases
        return self._parse_provider_name(text)
    
    async def switch_language(self, language: str) -> tuple[bool, str]:
        """Switch ASR language - public method for intent handlers"""
        # TODO: Implement language switching logic
        return False, "Переключение языка пока не реализовано"
    
    def _get_providers_info(self) -> str:
        """Get formatted information about available providers"""
        if not self.providers:
            return "Нет доступных провайдеров ASR"
        
        info_lines = [f"Доступные провайдеры ASR ({len(self.providers)}):"]
        for name, provider in self.providers.items():
            status = "✓ (по умолчанию)" if name == self.default_provider else "✓"
            languages = ", ".join(provider.get_supported_languages()[:3])  # Show first 3
            info_lines.append(f"  {status} {name}: {languages}...")
        
        return "\n".join(info_lines)
    
    def _parse_provider_name(self, command: str) -> Optional[str]:
        """Extract provider name from voice command"""
        command_lower = command.lower()
        for provider_name in self.providers.keys():
            if provider_name in command_lower:
                return provider_name
        
        # Handle common aliases
        aliases = {
            "воск": "vosk",
            "виспер": "whisper", 
            "гугл": "google_cloud",
            "облако": "google_cloud"
        }
        
        for alias, provider_name in aliases.items():
            if alias in command_lower and provider_name in self.providers:
                return provider_name
        
        return None
    
    # WebAPIPlugin interface - unified API
    def get_router(self) -> APIRouter:
        router = APIRouter()
        
        @router.post("/transcribe")
        async def transcribe_audio_file(
            audio: UploadFile = File(...),
            provider: Optional[str] = None,
            language: str = "ru",
            enhance: bool = False
        ):
            """Transcribe uploaded audio file - NEW CAPABILITY!"""
            provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            # Read and transcribe audio
            audio_data = await audio.read()
            text = await self.transcribe_audio(
                audio_data, provider=provider_name, language=language
            )
            
            # Optional LLM enhancement
            enhanced_text = None
            if enhance and text.strip():
                # Get LLM plugin and enhance text
                if hasattr(self, 'core') and self.core:
                    llm_plugin = self.core.plugin_manager.get_plugin("universal_llm")
                    if llm_plugin:
                        try:
                            enhanced_text = await llm_plugin.enhance_text(
                                text, task="improve_speech_recognition"
                            )
                        except Exception as e:
                            logger.warning(f"LLM enhancement failed: {e}")
                
                if enhanced_text:
                    return {
                        "original_text": text,
                        "enhanced_text": enhanced_text,
                        "provider": provider_name,
                        "language": language,
                        "enhanced": True
                    }
            
            return {
                "text": text,
                "provider": provider_name,
                "language": language,
                "enhanced": False
            }
        
        @router.websocket("/stream")
        async def stream_transcription(websocket: WebSocket):
            """WebSocket endpoint for real-time ASR - NEW CAPABILITY!"""
            await websocket.accept()
            
            try:
                while True:
                    # Receive audio chunk
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    if message["type"] == "audio_chunk":
                        # Decode and process audio
                        audio_data = base64.b64decode(message["data"])
                        language = message.get("language", self.default_language)
                        provider_name = message.get("provider", self.default_provider)
                        
                        # Transcribe chunk
                        try:
                            text = await self.transcribe_audio(
                                audio_data, 
                                provider=provider_name,
                                language=language
                            )
                            
                            if text.strip():
                                # Send result back
                                response = {
                                    "type": "transcription_result",
                                    "text": text,
                                    "provider": provider_name,
                                    "language": language,
                                    "timestamp": time.time()
                                }
                                await websocket.send_text(json.dumps(response))
                        except Exception as e:
                            error_response = {
                                "type": "error",
                                "error": str(e),
                                "timestamp": time.time()
                            }
                            await websocket.send_text(json.dumps(error_response))
                            
            except WebSocketDisconnect:
                logger.info("ASR WebSocket client disconnected")
            except Exception as e:
                logger.error(f"ASR WebSocket error: {e}")
        
        @router.get("/providers")
        async def list_asr_providers():
            """Discovery endpoint for all ASR provider capabilities"""
            result = {}
            for name, provider in self.providers.items():
                try:
                    result[name] = {
                        "available": await provider.is_available(),
                        "parameters": provider.get_parameter_schema(),
                        "languages": provider.get_supported_languages(),
                        "formats": provider.get_supported_formats(),
                        "capabilities": provider.get_capabilities()
                    }
                except Exception as e:
                    result[name] = {
                        "available": False,
                        "error": str(e)
                    }
            return {"providers": result, "default": self.default_provider}
        
        @router.post("/configure")
        async def configure_asr(provider: str, set_as_default: bool = False):
            """Configure ASR settings"""
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
        """ASR component needs web API functionality"""
        return ["fastapi>=0.100.0", "uvicorn[standard]>=0.20.0", "websockets>=11.0.0"]
    
    async def stop(self) -> None:
        """Stop the ASR component (alias for shutdown)"""
        await self.shutdown()
    
    # Config interface methods (Phase 3 - Configuration Architecture Cleanup)
    @classmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the Pydantic config model for this component"""
        from ..config.models import ASRConfig
        return ASRConfig
    
    @classmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to this component's config (V14 Architecture)"""
        return "asr" 