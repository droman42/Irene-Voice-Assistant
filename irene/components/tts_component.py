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
            from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect  # type: ignore
            from ..api.schemas import (
                TTSRequest, TTSResponse, TTSProvidersResponse,
                TTSStreamRequest, TTSAudioChunk, TTSSynthesisComplete, TTSErrorMessage,
                BinaryTTSSessionMessage, TTSTextRequest, TTSSynthesisStarted, 
                TTSBinarySynthesisComplete, BinaryTTSProtocol,
                ChunkMetadata, SynthesisMetadata, SynthesisStats
            )
            from ..web_api.asyncapi import websocket_api, extract_websocket_specs_from_router
            import json
            import time
            import uuid
            import tempfile
            import asyncio
            
            router = APIRouter()
                
            @router.post("/speak", response_model=TTSResponse)
            async def unified_speak(request: TTSRequest):
                """
                Enhanced TTS endpoint with audio format control
                
                Supports configurable audio output format including sample rate, 
                channels, and format specification. Uses AudioData infrastructure
                for high-quality resampling and format conversion.
                """
                try:
                    provider_name = request.provider or self.default_provider
                    
                    if provider_name not in self.providers:
                        raise HTTPException(404, f"Provider '{provider_name}' not available")
                    
                    provider = self.providers[provider_name]
                    if not await provider.is_available():
                        raise HTTPException(503, f"Provider '{provider_name}' temporarily unavailable")
                    
                    # Extract provider-specific parameters
                    kwargs = {
                        "language": request.language
                    }
                    if request.speaker:
                        kwargs["speaker"] = request.speaker
                    
                    # Get audio configuration with defaults
                    from ..api.schemas import AudioConfigRequest
                    audio_config = request.audio_config or AudioConfigRequest()
                    
                    # Create temporary file for synthesis
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                        temp_path = Path(temp_file.name)
                    
                    try:
                        # Synthesize audio to file
                        await provider.synthesize_to_file(
                            request.text,
                            temp_path,
                            **kwargs
                        )
                        
                        # Read and convert audio to requested format
                        from ..intents.models import AudioData
                        from ..utils.audio_helpers import AudioProcessor
                        
                        # Check if this is a text-only provider (like console)
                        capabilities = provider.get_capabilities()
                        provider_formats = capabilities.get("formats", ["wav"])
                        
                        if "wav" not in provider_formats and "audio" not in provider_formats:
                            # Handle text-only providers (console, debug, etc.)
                            logger.debug(f"Provider {provider_name} is text-only, reading as text")
                            
                            # Read as text and convert to fake audio data
                            with open(temp_path, 'r', encoding='utf-8') as f:
                                text_content = f.read()
                            
                            # Convert text to bytes (fake audio for consistency)
                            text_bytes = text_content.encode('utf-8')
                            audio_base64 = base64.b64encode(text_bytes).decode('utf-8')
                            
                            # Create metadata for text output
                            audio_metadata = {
                                "sample_rate": audio_config.sample_rate,
                                "channels": audio_config.channels,
                                "format": "text",  # Indicate this is text, not audio
                                "duration_ms": len(text_content) * 10,  # Estimate 10ms per character
                                "file_size": len(text_bytes),
                                "content_type": "text"
                            }
                            
                        else:
                            # Handle actual audio providers
                            logger.debug(f"Provider {provider_name} generates audio, processing with AudioData")
                            
                            # Read generated audio file
                            with open(temp_path, 'rb') as f:
                                audio_bytes = f.read()
                            
                            # Get provider capabilities to determine source format
                            provider_sample_rate = capabilities.get("sample_rate", 22050)
                            provider_channels = capabilities.get("channels", 1)
                            
                            # Create AudioData object
                            audio_data = AudioData(
                                data=audio_bytes,
                                timestamp=time.time(),
                                sample_rate=provider_sample_rate,
                                channels=provider_channels,
                                format="wav",
                                metadata={
                                    'source': 'tts_http_provider',
                                    'provider': provider_name,
                                    'text': request.text,
                                    'language': request.language
                                }
                            )
                            
                            # Convert to requested format if needed
                            target_rate = audio_config.sample_rate
                            target_channels = audio_config.channels
                            
                            if (audio_data.sample_rate != target_rate or 
                                audio_data.channels != target_channels):
                                logger.debug(f"Converting audio from {audio_data.sample_rate}Hz/{audio_data.channels}ch to {target_rate}Hz/{target_channels}ch")
                                audio_data = await AudioProcessor.resample_audio_data(
                                    audio_data, target_rate
                                )
                            
                            # Extract PCM data and encode as base64
                            pcm_data = audio_data.data
                            audio_base64 = base64.b64encode(pcm_data).decode('utf-8')
                            
                            # Calculate audio metadata
                            bytes_per_ms = (target_rate * target_channels * 2) // 1000  # 16-bit PCM
                            duration_ms = len(pcm_data) / bytes_per_ms
                            
                            audio_metadata = {
                                "sample_rate": target_rate,
                                "channels": target_channels,
                                "format": audio_config.format,
                                "duration_ms": duration_ms,
                                "file_size": len(pcm_data),
                                "content_type": "audio"
                            }
                        
                        return TTSResponse(
                            success=True,
                            provider=provider_name,
                            text=request.text,
                            audio_content=audio_base64,
                            audio_metadata=audio_metadata
                        )
                        
                    finally:
                        # Clean up temporary file
                        if temp_path.exists():
                            temp_path.unlink()
                    
                except Exception as e:
                    logger.error(f"TTS API error: {e}")
                    return TTSResponse(
                        success=False,
                        provider=request.provider or self.default_provider,
                        text=request.text,
                        error=str(e)
                    )
            
            @router.get("/providers", response_model=TTSProvidersResponse)
            async def list_providers():
                """Discovery endpoint for all provider capabilities"""
                result = {}
                for name, provider in self.providers.items():
                    result[name] = {
                        "available": await provider.is_available(),
                        "parameters": provider.get_parameter_schema(),
                        "capabilities": provider.get_capabilities()
                    }
                
                return TTSProvidersResponse(
                    success=True,
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
            
            # WebSocket endpoints for TTS streaming
            
            @websocket_api(
                description="Real-time text-to-speech streaming with base64-encoded audio",
                receives=TTSStreamRequest,
                sends=TTSAudioChunk,
                tags=["Text-to-Speech", "Real-time", "Base64"]
            )
            @router.websocket("/stream")
            async def stream_synthesis(websocket: WebSocket):
                """
                Real-time text-to-speech streaming with base64-encoded audio chunks
                
                This endpoint provides streaming speech synthesis for web applications
                and clients that need to receive audio data as base64-encoded JSON messages.
                
                Protocol Flow:
                1. Client connects to WebSocket endpoint
                2. Client sends TTSStreamRequest with text and configuration
                3. Server processes text through configured TTS provider
                4. Server responds with TTSAudioChunk messages containing base64 audio
                5. Server sends TTSSynthesisComplete when synthesis is complete
                
                Message Format (Client → Server):
                {
                    "type": "tts_request",
                    "text": "Hello, how are you doing today?",
                    "language": "en",
                    "provider": "silero_v4",
                    "speaker": "natasha",
                    "audio_config": {
                        "sample_rate": 16000,
                        "channels": 1,
                        "format": "pcm16"
                    }
                }
                
                Response Format (Server → Client):
                Audio Chunk: {
                    "type": "audio_chunk",
                    "data": "<base64-encoded-audio>",
                    "sequence": 1,
                    "chunk_info": {...},
                    "synthesis_metadata": {...},
                    "is_final_chunk": false
                }
                Complete: {
                    "type": "synthesis_complete",
                    "total_chunks": 12,
                    "total_duration_ms": 1250.0,
                    "synthesis_stats": {...}
                }
                Error: {
                    "type": "error",
                    "error": "error description",
                    "error_code": "ERROR_CODE",
                    "recoverable": true
                }
                
                Features:
                - Real-time speech synthesis streaming
                - Configurable audio format per request
                - Base64-encoded audio chunks for web compatibility
                - Comprehensive error handling with recovery guidance
                - Provider-specific voice and language selection
                
                Best For:
                - Web applications with JavaScript clients
                - Simple integration without binary data handling
                - Development and testing environments
                - Scenarios where base64 encoding overhead is acceptable
                """
                await websocket.accept()
                logger.debug("TTS stream WebSocket client connected")
                
                try:
                    while True:
                        # Receive synthesis request
                        data = await websocket.receive_text()
                        message = json.loads(data)
                        
                        if message["type"] == "tts_request":
                            try:
                                # Parse and validate request
                                request = TTSStreamRequest(**message)
                                
                                # Get provider and validate
                                provider_name = request.provider or self.default_provider
                                if provider_name not in self.providers:
                                    error_response = TTSErrorMessage(
                                        error=f"Provider '{provider_name}' not available",
                                        error_code="PROVIDER_UNAVAILABLE",
                                        provider=provider_name,
                                        recoverable=True
                                    ).dict()
                                    await websocket.send_text(json.dumps(error_response))
                                    continue
                                
                                provider = self.providers[provider_name]
                                if not await provider.is_available():
                                    error_response = TTSErrorMessage(
                                        error=f"Provider '{provider_name}' temporarily unavailable",
                                        error_code="PROVIDER_UNAVAILABLE",
                                        provider=provider_name,
                                        recoverable=True
                                    ).dict()
                                    await websocket.send_text(json.dumps(error_response))
                                    continue
                                
                                # Start synthesis
                                synthesis_start_time = time.time()
                                
                                # Generate audio
                                kwargs = {}
                                if request.speaker:
                                    kwargs["speaker"] = request.speaker
                                kwargs["language"] = request.language
                                
                                # Create temporary file for synthesis
                                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                                    temp_path = Path(temp_file.name)
                                
                                try:
                                    # Synthesize audio to file
                                    await provider.synthesize_to_file(
                                        request.text, 
                                        temp_path, 
                                        **kwargs
                                    )
                                    
                                    # Read and convert audio to requested format
                                    from ..intents.models import AudioData
                                    from ..utils.audio_helpers import AudioProcessor
                                    
                                    # Read generated audio file
                                    with open(temp_path, 'rb') as f:
                                        audio_bytes = f.read()
                                    
                                    # Get provider capabilities to determine source format
                                    capabilities = provider.get_capabilities()
                                    provider_sample_rate = capabilities.get("sample_rate", 22050)
                                    provider_channels = capabilities.get("channels", 1)
                                    
                                    # Create AudioData object
                                    audio_data = AudioData(
                                        data=audio_bytes,
                                        timestamp=time.time(),
                                        sample_rate=provider_sample_rate,
                                        channels=provider_channels,
                                        format="wav",
                                        metadata={
                                            'source': 'tts_provider',
                                            'provider': provider_name,
                                            'text': request.text,
                                            'language': request.language
                                        }
                                    )
                                    
                                    # Convert to requested format if needed
                                    target_rate = request.audio_config.sample_rate
                                    target_channels = request.audio_config.channels
                                    
                                    if (audio_data.sample_rate != target_rate or 
                                        audio_data.channels != target_channels):
                                        logger.debug(f"Converting audio from {audio_data.sample_rate}Hz/{audio_data.channels}ch to {target_rate}Hz/{target_channels}ch")
                                        audio_data = await AudioProcessor.resample_audio_data(
                                            audio_data, target_rate
                                        )
                                    
                                    # Split audio into chunks and stream
                                    chunk_duration_ms = 100  # 100ms chunks
                                    bytes_per_ms = (target_rate * target_channels * 2) // 1000  # 16-bit PCM
                                    chunk_size_bytes = int(chunk_duration_ms * bytes_per_ms)
                                    
                                    total_chunks = 0
                                    sequence = 1
                                    
                                    # Extract PCM data from AudioData
                                    pcm_data = audio_data.data
                                    
                                    # Stream audio chunks
                                    offset = 0
                                    while offset < len(pcm_data):
                                        chunk_data = pcm_data[offset:offset + chunk_size_bytes]
                                        if not chunk_data:
                                            break
                                        
                                        # Encode chunk as base64
                                        chunk_base64 = base64.b64encode(chunk_data).decode('utf-8')
                                        
                                        # Calculate chunk duration
                                        actual_chunk_duration = (len(chunk_data) / bytes_per_ms)
                                        
                                        # Create chunk metadata
                                        chunk_info = ChunkMetadata(
                                            sample_rate=target_rate,
                                            channels=target_channels,
                                            format=request.audio_config.format,
                                            duration_ms=actual_chunk_duration,
                                            chunk_size_bytes=len(chunk_data)
                                        )
                                        
                                        synthesis_metadata = SynthesisMetadata(
                                            provider=provider_name,
                                            speaker=request.speaker,
                                            language=request.language,
                                            original_text=request.text
                                        )
                                        
                                        is_final = (offset + chunk_size_bytes >= len(pcm_data))
                                        
                                        # Send audio chunk
                                        chunk_message = TTSAudioChunk(
                                            data=chunk_base64,
                                            sequence=sequence,
                                            chunk_info=chunk_info,
                                            synthesis_metadata=synthesis_metadata,
                                            is_final_chunk=is_final
                                        )
                                        
                                        await websocket.send_text(json.dumps(chunk_message.dict()))
                                        
                                        offset += chunk_size_bytes
                                        sequence += 1
                                        total_chunks += 1
                                    
                                    # Send synthesis complete message
                                    synthesis_end_time = time.time()
                                    synthesis_stats = SynthesisStats(
                                        generation_time_ms=(synthesis_end_time - synthesis_start_time) * 1000,
                                        total_audio_bytes=len(pcm_data),
                                        provider=provider_name
                                    )
                                    
                                    # Calculate total duration
                                    total_duration_ms = (len(pcm_data) / bytes_per_ms)
                                    
                                    complete_message = TTSSynthesisComplete(
                                        total_chunks=total_chunks,
                                        total_duration_ms=total_duration_ms,
                                        synthesis_stats=synthesis_stats
                                    )
                                    
                                    await websocket.send_text(json.dumps(complete_message.dict()))
                                    logger.debug(f"TTS stream synthesis completed: {total_chunks} chunks, {total_duration_ms:.1f}ms")
                                    
                                finally:
                                    # Clean up temporary file
                                    if temp_path.exists():
                                        temp_path.unlink()
                                        
                            except Exception as e:
                                logger.error(f"TTS stream synthesis error: {e}")
                                error_response = TTSErrorMessage(
                                    error=str(e),
                                    error_code="SYNTHESIS_ERROR",
                                    provider=request.provider if 'request' in locals() else None,
                                    recoverable=True
                                ).dict()
                                await websocket.send_text(json.dumps(error_response))
                                
                except WebSocketDisconnect:
                    logger.info("TTS stream WebSocket client disconnected")
                except Exception as e:
                    logger.error(f"TTS stream WebSocket error: {e}")
            
            @websocket_api(
                description="Binary TTS streaming for external devices (ESP32-optimized)",
                receives=BinaryTTSProtocol,
                sends=TTSAudioChunk,  # For JSON responses, binary frames documented separately
                tags=["Text-to-Speech", "Binary Streaming", "ESP32"]
            )
            @router.websocket("/binary")
            async def binary_synthesis(websocket: WebSocket):
                """
                Optimized binary TTS streaming for ESP32/external devices
                
                This endpoint eliminates base64 encoding overhead by sending raw PCM audio
                data as binary WebSocket frames. Designed for high-performance applications
                and embedded devices where bandwidth and CPU efficiency are critical.
                
                Protocol Flow:
                1. Client sends BinaryTTSSessionMessage (JSON) for configuration
                2. Server responds with session_ready confirmation (JSON)
                3. Client sends TTSTextRequest (JSON) with text to synthesize
                4. Server responds with synthesis_started (JSON)
                5. Server streams raw PCM binary frames
                6. Server sends synthesis_complete (JSON) when done
                
                Session Configuration:
                {
                    "type": "binary_tts_session",
                    "session_config": {
                        "sample_rate": 16000,
                        "channels": 1,
                        "format": "pcm_s16le",
                        "language": "en",
                        "provider": "silero_v4",
                        "speaker": "natasha",
                        "chunk_size_ms": 100
                    }
                }
                
                Text Request:
                {
                    "type": "text_request",
                    "text": "Hello, how are you doing today?",
                    "request_id": "req_001"
                }
                
                Response Format (Server → Client):
                Session Ready: {
                    "type": "session_ready",
                    "message": "Binary TTS session initialized",
                    "config": {...},
                    "session_id": "tts_session_abc123"
                }
                Synthesis Started: {
                    "type": "synthesis_started",
                    "request_id": "req_001",
                    "estimated_chunks": 12,
                    "estimated_duration_ms": 1250.0
                }
                Binary Audio: [Raw PCM binary frames]
                Synthesis Complete: {
                    "type": "synthesis_complete",
                    "request_id": "req_001",
                    "total_chunks": 12,
                    "total_bytes": 38400,
                    "synthesis_time_ms": 234.5
                }
                
                Performance Benefits:
                - ~33% bandwidth reduction (no base64 encoding overhead)
                - Significantly lower CPU usage on both client and server
                - Optimized for continuous synthesis scenarios
                - Better real-time performance for ESP32 and embedded devices
                - Session persistence for multiple text requests
                
                Best For:
                - ESP32 and embedded device integration
                - High-throughput audio streaming applications
                - Real-time systems with strict latency requirements
                - Production deployments with bandwidth constraints
                - IoT devices with limited computational resources
                """
                await websocket.accept()
                logger.debug("TTS binary WebSocket client connected")
                
                session_config = None
                session_id = f"tts_session_{uuid.uuid4().hex[:8]}"
                
                try:
                    # Session initialization
                    config_data = await websocket.receive_text()
                    config_message = json.loads(config_data)
                    
                    # Support both wrapper format and direct format for compatibility
                    if config_message.get("type") == "binary_tts_protocol":
                        session_msg = BinaryTTSSessionMessage(**config_message["session_config"])
                    elif config_message.get("type") == "binary_tts_session":
                        session_msg = BinaryTTSSessionMessage(**config_message)
                    else:
                        raise ValueError("Invalid session configuration message")
                    
                    session_config = session_msg.session_config
                    
                    # Validate provider
                    provider_name = session_config.provider or self.default_provider
                    if provider_name not in self.providers:
                        error_response = {
                            "type": "error",
                            "error": f"Provider '{provider_name}' not available",
                            "error_code": "PROVIDER_UNAVAILABLE",
                            "recoverable": False,
                            "timestamp": time.time()
                        }
                        await websocket.send_text(json.dumps(error_response))
                        return
                    
                    provider = self.providers[provider_name]
                    if not await provider.is_available():
                        error_response = {
                            "type": "error", 
                            "error": f"Provider '{provider_name}' temporarily unavailable",
                            "error_code": "PROVIDER_UNAVAILABLE",
                            "recoverable": True,
                            "timestamp": time.time()
                        }
                        await websocket.send_text(json.dumps(error_response))
                        return
                    
                    # Send session ready confirmation
                    session_ready = {
                        "type": "session_ready",
                        "message": "Binary TTS session initialized",
                        "config": session_config.dict(),
                        "session_id": session_id,
                        "timestamp": time.time()
                    }
                    await websocket.send_text(json.dumps(session_ready))
                    logger.debug(f"TTS binary session {session_id} initialized for provider {provider_name}")
                    
                    # Process text requests
                    while True:
                        # Receive text request
                        request_data = await websocket.receive_text()
                        request_message = json.loads(request_data)
                        
                        if request_message["type"] == "text_request":
                            try:
                                text_request = TTSTextRequest(**request_message)
                                
                                # Send synthesis started notification
                                synthesis_start_time = time.time()
                                
                                # Estimate audio characteristics for progress feedback
                                estimated_duration_ms = len(text_request.text) * 75  # ~75ms per character estimate
                                chunk_duration_ms = session_config.chunk_size_ms
                                estimated_chunks = max(1, int(estimated_duration_ms / chunk_duration_ms))
                                
                                synthesis_started = TTSSynthesisStarted(
                                    request_id=text_request.request_id,
                                    estimated_chunks=estimated_chunks,
                                    estimated_duration_ms=estimated_duration_ms
                                )
                                await websocket.send_text(json.dumps(synthesis_started.dict()))
                                
                                # Generate audio
                                kwargs = {
                                    "language": session_config.language
                                }
                                if session_config.speaker:
                                    kwargs["speaker"] = session_config.speaker
                                
                                # Create temporary file for synthesis
                                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                                    temp_path = Path(temp_file.name)
                                
                                try:
                                    # Synthesize audio to file
                                    await provider.synthesize_to_file(
                                        text_request.text,
                                        temp_path,
                                        **kwargs
                                    )
                                    
                                    # Read and convert audio
                                    from ..intents.models import AudioData
                                    from ..utils.audio_helpers import AudioProcessor
                                    
                                    # Read generated audio file 
                                    with open(temp_path, 'rb') as f:
                                        audio_bytes = f.read()
                                    
                                    # Get provider capabilities
                                    capabilities = provider.get_capabilities()
                                    provider_sample_rate = capabilities.get("sample_rate", 22050)
                                    provider_channels = capabilities.get("channels", 1)
                                    
                                    # Create AudioData object
                                    audio_data = AudioData(
                                        data=audio_bytes,
                                        timestamp=time.time(),
                                        sample_rate=provider_sample_rate,
                                        channels=provider_channels,
                                        format="wav",
                                        metadata={
                                            'source': 'tts_binary_provider',
                                            'provider': provider_name,
                                            'request_id': text_request.request_id
                                        }
                                    )
                                    
                                    # Convert to session format if needed
                                    target_rate = session_config.sample_rate
                                    target_channels = session_config.channels
                                    
                                    if (audio_data.sample_rate != target_rate or 
                                        audio_data.channels != target_channels):
                                        audio_data = await AudioProcessor.resample_audio_data(
                                            audio_data, target_rate
                                        )
                                    
                                    # Stream binary audio chunks
                                    bytes_per_ms = (target_rate * target_channels * 2) // 1000  # 16-bit PCM
                                    chunk_size_bytes = int(session_config.chunk_size_ms * bytes_per_ms)
                                    
                                    # Extract PCM data
                                    pcm_data = audio_data.data
                                    total_chunks = 0
                                    total_bytes_sent = 0
                                    
                                    # Stream binary chunks
                                    offset = 0
                                    while offset < len(pcm_data):
                                        chunk_data = pcm_data[offset:offset + chunk_size_bytes]
                                        if not chunk_data:
                                            break
                                        
                                        # Send raw binary PCM data
                                        await websocket.send_bytes(chunk_data)
                                        
                                        offset += chunk_size_bytes
                                        total_chunks += 1
                                        total_bytes_sent += len(chunk_data)
                                    
                                    # Send synthesis complete notification
                                    synthesis_end_time = time.time()
                                    synthesis_time_ms = (synthesis_end_time - synthesis_start_time) * 1000
                                    
                                    complete_message = TTSBinarySynthesisComplete(
                                        request_id=text_request.request_id,
                                        total_chunks=total_chunks,
                                        total_bytes=total_bytes_sent,
                                        synthesis_time_ms=synthesis_time_ms
                                    )
                                    
                                    await websocket.send_text(json.dumps(complete_message.dict()))
                                    logger.debug(f"TTS binary synthesis completed: {total_chunks} chunks, {total_bytes_sent} bytes")
                                    
                                finally:
                                    # Clean up temporary file
                                    if temp_path.exists():
                                        temp_path.unlink()
                                        
                            except Exception as e:
                                logger.error(f"TTS binary synthesis error: {e}")
                                error_response = {
                                    "type": "error",
                                    "error": str(e),
                                    "error_code": "SYNTHESIS_ERROR",
                                    "recoverable": True,
                                    "timestamp": time.time()
                                }
                                await websocket.send_text(json.dumps(error_response))
                        else:
                            # Unknown message type
                            error_response = {
                                "type": "error",
                                "error": f"Unknown message type: {request_message.get('type')}",
                                "error_code": "INVALID_MESSAGE_TYPE",
                                "recoverable": True,
                                "timestamp": time.time()
                            }
                            await websocket.send_text(json.dumps(error_response))
                            
                except WebSocketDisconnect:
                    logger.info(f"TTS binary WebSocket session {session_id} disconnected")
                except Exception as e:
                    logger.error(f"TTS binary WebSocket session {session_id} error: {e}")
            
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
    
    def get_websocket_spec(self) -> Optional[dict]:
        """Get AsyncAPI specification for TTS WebSocket endpoints"""
        try:
            from ..web_api.asyncapi import extract_websocket_specs_from_router
            router = self.get_router()
            if router:
                return extract_websocket_specs_from_router(
                    router=router,
                    component_name="tts",
                    api_prefix=self.get_api_prefix()
                )
            return None
        except Exception as e:
            logger.error(f"Error generating AsyncAPI spec for TTS component: {e}")
            return None
    
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