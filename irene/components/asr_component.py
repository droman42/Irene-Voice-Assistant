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
import asyncio

from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect  # type: ignore
from pydantic import BaseModel
from .base import Component
from ..core.interfaces.asr import ASRPlugin
from ..core.interfaces.webapi import WebAPIPlugin
from ..intents.models import AudioData
from ..core.metrics import get_metrics_collector
from ..web_api.asyncapi import websocket_api, extract_websocket_specs_from_router
from ..api.schemas import AudioChunkMessage, TranscriptionResultMessage, TranscriptionErrorMessage, BinaryAudioSessionMessage, BinaryAudioStreamMessage, BinaryWebSocketProtocol


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
    

    def __init__(self):
        super().__init__()
        self.providers: Dict[str, ASRProvider] = {}  # Proper ABC type hint
        self.default_provider = "vosk"
        self.default_language = "ru"
        self.core = None  # Store core reference for LLM integration
        
        # Dynamic provider discovery from entry-points (replaces hardcoded classes)
        self._provider_classes: Dict[str, type] = {}
        
        # Phase 1: Runtime monitoring now handled by unified metrics collector
        
        # Phase 1: Unified metrics integration
        self._metrics_push_task: Optional[asyncio.Task] = None
        self._metrics_push_interval = 60.0  # seconds
        
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
                
            # Phase 1: Start unified metrics push task
            self._start_metrics_push_task()
                
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
                    
                    # Update metrics (Phase 1: Unified metrics integration)
                    resampling_time = (time.time() - start_time) * 1000
                    get_metrics_collector().record_resampling_operation("asr", resampling_time, success=True)
                    
                    logger.debug(f"Successfully resampled audio to {config_sample_rate}Hz using {conversion_method.value} in {resampling_time:.1f}ms")
                    
                    # Phase 4 Step 4: Call transcribe_audio with configuration-compliant data
                    return await self.transcribe_audio(resampled_audio.data, **kwargs)
                    
                except Exception as resampling_error:
                    # Update failure metrics (Phase 1: Unified metrics integration)
                    resampling_time = (time.time() - start_time) * 1000
                    get_metrics_collector().record_resampling_operation("asr", resampling_time, success=False)
                    logger.error(f"Configuration-required resampling failed: {resampling_error}")
                    # Reset provider state after resampling failure to ensure clean state
                    self.reset_provider_state(provider_name)
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
                        # Reset provider state after resampling failure
                        self.reset_provider_state(provider_name)
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
        """Get runtime monitoring metrics from unified collector (Phase 1: Complete integration)"""
        metrics_collector = get_metrics_collector()
        
        # Get component-specific metrics from unified collector
        resampling_metrics = metrics_collector.get_component_resampling_metrics("asr")
        
        # Phase 6: Include cache performance metrics
        from ..utils.audio_helpers import AudioProcessor
        cache_stats = AudioProcessor.get_cache_stats()
        
        # Combine and return unified metrics
        combined_metrics = {
            'total_resampling_operations': resampling_metrics.get('total_operations', 0),
            'total_resampling_time_ms': resampling_metrics.get('total_time_ms', 0.0),
            'resampling_failures': resampling_metrics.get('failures', 0),
            'average_resampling_time_ms': resampling_metrics.get('average_time_ms', 0.0),
            'resampling_success_rate': (
                1.0 - (resampling_metrics.get('failures', 0) / max(1, resampling_metrics.get('total_operations', 1)))
            ),
            'provider_fallbacks': 0,  # To be enhanced later
            'configuration_warnings': 0,  # To be enhanced later
            'cache_statistics': cache_stats
        }
        
        return combined_metrics
    
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
    
    def reset_provider_state(self, provider_name: str = None, language: str = None) -> bool:
        """
        Reset ASR provider state to prevent contamination between utterances.
        
        This method calls the reset() method on the specified provider(s) to clear
        any internal state that might persist between transcription calls.
        
        Args:
            provider_name: Provider to reset (None = reset all providers)
            language: Language to reset (None = reset all languages)
            
        Returns:
            True if at least one reset was successful, False otherwise
        """
        success_count = 0
        total_attempts = 0
        
        try:
            if provider_name is None:
                # Reset all providers
                for name, provider in self.providers.items():
                    total_attempts += 1
                    try:
                        if provider.reset(language):
                            success_count += 1
                            logger.debug(f"Reset ASR provider state: {name}")
                        else:
                            logger.warning(f"Failed to reset ASR provider state: {name}")
                    except Exception as e:
                        logger.warning(f"Error resetting ASR provider {name}: {e}")
                
                if total_attempts > 0:
                    logger.info(f"Reset {success_count}/{total_attempts} ASR providers")
                    
            else:
                # Reset specific provider
                if provider_name in self.providers:
                    total_attempts = 1
                    try:
                        if self.providers[provider_name].reset(language):
                            success_count = 1
                            logger.debug(f"Reset ASR provider state: {provider_name}")
                        else:
                            logger.warning(f"Failed to reset ASR provider state: {provider_name}")
                    except Exception as e:
                        logger.warning(f"Error resetting ASR provider {provider_name}: {e}")
                else:
                    logger.warning(f"ASR provider not found: {provider_name}")
                    return False
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error in reset_provider_state: {e}")
            return False
    
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
            
            # Save uploaded file to configured temp directory
            import uuid
            from pathlib import Path
            from ..config.models import CoreConfig
            
            # Get temp audio directory from configuration
            config = self.core.config if hasattr(self, 'core') and self.core else CoreConfig()
            temp_dir = config.assets.temp_audio_dir
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename
            filename = audio.filename or "audio_file"
            suffix = Path(filename).suffix if filename else ".wav"
            unique_filename = f"{uuid.uuid4()}{suffix}"
            temp_path = temp_dir / unique_filename
            
            # Write uploaded content to file
            audio_data = await audio.read()
            temp_path.write_bytes(audio_data)
            
            try:
                # Transcribe from file (some providers may prefer file input)
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
                
            finally:
                # Clean up temporary file
                if temp_path.exists():
                    temp_path.unlink()
        
        @websocket_api(
            description="Real-time speech recognition streaming",
            receives=AudioChunkMessage,
            sends=TranscriptionResultMessage,
            tags=["Speech Recognition", "Real-time"]
        )
        @router.websocket("/stream")
        async def stream_transcription(websocket: WebSocket):
            """
            Real-time speech recognition streaming with base64-encoded audio chunks
            
            This endpoint provides continuous speech recognition for web applications
            and clients that need to send audio data as base64-encoded JSON messages.
            
            Protocol Flow:
            1. Client connects to WebSocket endpoint
            2. Client sends JSON messages with base64-encoded audio chunks
            3. Server processes audio through configured ASR provider
            4. Server responds with transcription results as JSON
            
            Message Format (Client → Server):
            {
                "type": "audio_chunk",
                "data": "<base64-encoded-audio>",
                "language": "ru|en",  # optional, defaults to component default
                "provider": "vosk|whisper|google"  # optional, defaults to component default
            }
            
            Response Format (Server → Client):
            Success: {
                "type": "transcription_result",
                "text": "recognized speech text",
                "provider": "vosk",
                "language": "ru",
                "timestamp": 1234567890.123
            }
            Error: {
                "type": "error", 
                "error": "error description",
                "timestamp": 1234567890.123
            }
            
            Features:
            - Automatic provider state reset on session start/end for clean transcription
            - Configurable ASR provider per request
            - Multi-language support
            - Graceful error handling with provider state recovery
            - Real-time processing with immediate response
            
            Best For:
            - Web applications with JavaScript clients
            - Scenarios where base64 encoding is acceptable
            - Simple integration without binary data handling
            - Development and testing environments
            """
            await websocket.accept()
            
            # Reset all ASR provider states for clean session start
            self.reset_provider_state()
            logger.debug("Reset ASR provider states for new WebSocket session")
            
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
                            # Reset provider state after transcription error
                            provider_name = message.get("provider", self.default_provider)
                            self.reset_provider_state(provider_name)
                            logger.debug(f"Reset ASR provider {provider_name} after WebSocket transcription error")
                            
                            error_response = {
                                "type": "error",
                                "error": str(e),
                                "timestamp": time.time()
                            }
                            await websocket.send_text(json.dumps(error_response))
                            
            except WebSocketDisconnect:
                logger.info("ASR WebSocket client disconnected")
                # Reset provider states on disconnect for clean state
                self.reset_provider_state()
                logger.debug("Reset ASR provider states after WebSocket disconnect")
            except Exception as e:
                logger.error(f"ASR WebSocket error: {e}")
                # Reset provider states after WebSocket error
                self.reset_provider_state()
                logger.debug("Reset ASR provider states after WebSocket error")
        
        @websocket_api(
            description="Binary WebSocket streaming for external devices (ESP32-optimized)",
            receives=BinaryWebSocketProtocol,
            sends=TranscriptionResultMessage,
            tags=["Speech Recognition", "Binary Streaming", "ESP32"]
        )
        @router.websocket("/binary")
        async def binary_audio_stream(websocket: WebSocket):
            """
            Optimized binary audio streaming for ESP32/external devices
            
            This endpoint eliminates base64 encoding overhead by accepting raw PCM audio
            data as binary WebSocket frames. Designed for high-performance applications
            and embedded devices where bandwidth and CPU efficiency are critical.
            
            Protocol Formats:
            
            Format 1 (Full Protocol Wrapper - Recommended):
            1. Client sends BinaryWebSocketProtocol JSON (includes session_config)
            2. Server responds with session_ready confirmation or error
            3. Client streams raw PCM binary frames continuously
            4. Server responds with transcription results as JSON
            
            Format 2 (Direct Session Config - Backward Compatible):
            1. Client sends BinaryAudioSessionMessage JSON directly
            2. Server responds with session_ready confirmation or error  
            3. Client streams raw PCM binary frames continuously
            4. Server responds with transcription results as JSON
            
            Session Configuration:
            {
                "type": "binary_websocket_protocol",  # or "session_config" for direct mode
                "session_config": {
                    "sample_rate": 16000,     # Hz, typically 16000 for speech
                    "channels": 1,            # Mono audio recommended
                    "format": "pcm_s16le",    # PCM signed 16-bit little-endian
                    "language": "ru",         # optional, defaults to component default  
                    "provider": "vosk"        # optional, defaults to component default
                }
            }
            
            Response Format (Server → Client):
            Session Ready: {
                "type": "session_ready",
                "message": "Binary audio streaming session initialized",
                "protocol_format": "wrapper|direct",
                "config": { ... },        # Echo of final configuration
                "timestamp": 1234567890.123
            }
            Transcription: {
                "type": "transcription_result", 
                "text": "recognized speech",
                "provider": "vosk",
                "language": "ru",
                "timestamp": 1234567890.123
            }
            Error: {
                "type": "error",
                "error": "error description", 
                "recoverable": true,      # Whether client can retry
                "timestamp": 1234567890.123
            }
            
            Performance Benefits:
            - ~33% bandwidth reduction (no base64 encoding overhead)
            - Significantly lower CPU usage on both client and server
            - Optimized for continuous audio streaming scenarios
            - Better real-time performance for ESP32 and embedded devices
            - Reduced memory allocation and garbage collection pressure
            
            Best For:
            - ESP32 and embedded device integration
            - High-throughput audio streaming applications
            - Real-time systems with strict latency requirements
            - Production deployments with bandwidth constraints
            - IoT devices with limited computational resources
            """
            await websocket.accept()
            
            # Reset all ASR provider states for clean session start
            self.reset_provider_state()
            logger.debug("Reset ASR provider states for new binary WebSocket session")
            
            # Session configuration variables
            session_config = None
            language = self.default_language
            provider_name = self.default_provider
            
            try:
                # Step 1: Receive protocol configuration (JSON)
                config_data = await websocket.receive_text()
                config_message = json.loads(config_data)
                
                # Handle both old direct session_config and new wrapper protocol
                if config_message.get("type") == "session_config":
                    # Direct session config (backward compatibility)
                    session_config = BinaryAudioSessionMessage(**config_message)
                elif config_message.get("type") == "binary_websocket_protocol":
                    # New wrapper protocol
                    protocol_wrapper = BinaryWebSocketProtocol(**config_message)
                    session_config = protocol_wrapper.session_config
                else:
                    raise ValueError("First message must be 'session_config' or 'binary_websocket_protocol'")
                
                # Extract session parameters
                language = session_config.language or self.default_language
                provider_name = session_config.provider or self.default_provider
                
                # Validate provider availability
                if provider_name not in self.providers:
                    error_response = {
                        "type": "error",
                        "error": f"ASR provider '{provider_name}' not available",
                        "available_providers": list(self.providers.keys()),
                        "recoverable": True,
                        "timestamp": time.time()
                    }
                    await websocket.send_text(json.dumps(error_response))
                    return
                
                # Send session confirmation
                protocol_format = "wrapper" if config_message.get("type") == "binary_websocket_protocol" else "direct"
                session_response = {
                    "type": "session_ready",
                    "message": "Binary audio streaming session initialized",
                    "protocol_format": protocol_format,
                    "config": {
                        "sample_rate": session_config.sample_rate,
                        "channels": session_config.channels,
                        "format": session_config.format,
                        "language": language,
                        "provider": provider_name
                    },
                    "timestamp": time.time()
                }
                await websocket.send_text(json.dumps(session_response))
                
                logger.info(f"Binary WebSocket session initialized ({protocol_format} protocol): "
                           f"{session_config.sample_rate}Hz, {session_config.channels}ch, {session_config.format}, "
                           f"provider={provider_name}, language={language}")
                
                # Step 2: Stream binary audio data
                while True:
                    # Receive raw PCM binary data
                    audio_data = await websocket.receive_bytes()
                    
                    if not audio_data:
                        continue
                    
                    logger.debug(f"Received binary audio chunk: {len(audio_data)} bytes")
                    
                    # Create AudioData object for processing
                    from ..intents.models import AudioData
                    audio_obj = AudioData(
                        data=audio_data,
                        sample_rate=session_config.sample_rate,
                        channels=session_config.channels,
                        format=session_config.format
                    )
                    
                    # Transcribe using the optimized process_audio method
                    try:
                        text = await self.process_audio(
                            audio_obj,
                            provider=provider_name,
                            language=language
                        )
                        
                        if text.strip():
                            # Send transcription result
                            response = {
                                "type": "transcription_result",
                                "text": text,
                                "provider": provider_name,
                                "language": language,
                                "timestamp": time.time()
                            }
                            await websocket.send_text(json.dumps(response))
                            
                            logger.debug(f"Binary WebSocket transcription: '{text}' "
                                        f"(provider: {provider_name}, {len(audio_data)} bytes)")
                        
                    except Exception as transcription_error:
                        # Reset provider state after transcription error
                        self.reset_provider_state(provider_name)
                        logger.debug(f"Reset ASR provider {provider_name} after binary WebSocket transcription error")
                        
                        error_response = {
                            "type": "error",
                            "error": f"Transcription failed: {str(transcription_error)}",
                            "provider": provider_name,
                            "recoverable": True,
                            "timestamp": time.time()
                        }
                        await websocket.send_text(json.dumps(error_response))
                        
            except WebSocketDisconnect:
                logger.info("Binary ASR WebSocket client disconnected")
                # Reset provider states on disconnect for clean state
                self.reset_provider_state()
                logger.debug("Reset ASR provider states after binary WebSocket disconnect")
            except Exception as e:
                logger.error(f"Binary ASR WebSocket error: {e}")
                
                # Try to send error message if connection is still open
                try:
                    error_response = {
                        "type": "error",
                        "error": f"Session error: {str(e)}",
                        "recoverable": False,
                        "timestamp": time.time()
                    }
                    await websocket.send_text(json.dumps(error_response))
                except:
                    pass  # Connection might be closed
                
                # Reset provider states after WebSocket error
                self.reset_provider_state()
                logger.debug("Reset ASR provider states after binary WebSocket error")
        
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
        
        @router.post("/reset")
        async def reset_asr_state(provider: Optional[str] = None, language: Optional[str] = None):
            """Reset ASR provider state to clear internal buffers and prevent contamination"""
            try:
                success = self.reset_provider_state(provider, language)
                if success:
                    return {
                        "success": True,
                        "message": f"Reset ASR state for provider: {provider or 'all'}, language: {language or 'all'}"
                    }
                else:
                    return {
                        "success": False,
                        "message": "Failed to reset ASR state"
                    }
            except Exception as e:
                raise HTTPException(500, f"Error resetting ASR state: {str(e)}")
        
        return router 
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for ASR API endpoints"""
        return "/asr"
    
    def get_api_tags(self) -> List[str]:
        """Get OpenAPI tags for ASR endpoints"""
        return ["Speech Recognition"]
    
    def get_websocket_spec(self) -> Optional[dict]:
        """Get AsyncAPI specification for ASR WebSocket endpoints"""
        try:
            router = self.get_router()
            if router:
                return extract_websocket_specs_from_router(
                    router=router,
                    component_name="asr",
                    api_prefix=self.get_api_prefix()
                )
            return None
        except Exception as e:
            logger.error(f"Error generating AsyncAPI spec for ASR component: {e}")
            return None
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """ASR component needs web API functionality"""
        return [
            "fastapi>=0.100.0", 
            "uvicorn[standard]>=0.20.0", 
            "websockets>=11.0.0",
            "python-multipart>=0.0.6"  # Required for file upload endpoints
        ]
    
    # Phase 1: Unified metrics integration methods
    def _start_metrics_push_task(self) -> None:
        """Start the periodic metrics push task"""
        if self._metrics_push_task is None:
            self._metrics_push_task = asyncio.create_task(self._metrics_push_loop())
            logger.debug("ASR component metrics push task started")
    
    async def _stop_metrics_push_task(self) -> None:
        """Stop the periodic metrics push task"""
        if self._metrics_push_task:
            self._metrics_push_task.cancel()
            try:
                await self._metrics_push_task
            except asyncio.CancelledError:
                pass
            self._metrics_push_task = None
            logger.debug("ASR component metrics push task stopped")
    
    async def _metrics_push_loop(self) -> None:
        """Periodic loop to push runtime metrics to unified collector"""
        while True:
            try:
                # Get current runtime metrics
                runtime_metrics = self.get_runtime_metrics()
                
                # Push to unified metrics collector
                metrics_collector = get_metrics_collector()
                metrics_collector.record_component_metrics("asr", runtime_metrics)
                
                logger.debug(f"Pushed ASR metrics to unified collector: {len(runtime_metrics)} metrics")
                
                # Wait for next push cycle
                await asyncio.sleep(self._metrics_push_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ASR metrics push loop: {e}")
                await asyncio.sleep(10)  # Brief pause before retrying
    
    async def stop(self) -> None:
        """Stop the ASR component (alias for shutdown)"""
        # Phase 1: Stop unified metrics push task
        await self._stop_metrics_push_task()
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