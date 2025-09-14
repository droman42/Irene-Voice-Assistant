"""
Audio Component - Audio coordinator managing multiple providers

Implements the fundamental component pattern for audio playback functionality.
Manages multiple audio providers based on configuration and provides unified web APIs.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncIterator, Type
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File  # type: ignore
from pydantic import BaseModel

from .base import Component
from ..core.interfaces.audio import AudioPlugin
from ..core.interfaces.webapi import WebAPIPlugin


# Import audio provider base class and dynamic loader
from ..providers.audio import AudioProvider
from ..utils.loader import dynamic_loader

logger = logging.getLogger(__name__)


class AudioPlayRequest(BaseModel):
    """Request model for audio playback API"""
    file_path: Optional[str] = None
    provider: Optional[str] = None
    volume: Optional[float] = None
    device: Optional[str] = None


class AudioComponent(Component, AudioPlugin, WebAPIPlugin):
    """
    Audio Component that manages multiple audio providers.
    
    Features:
    - Configuration-driven provider instantiation
    - Unified web API (/audio/*)
    - Voice commands for audio control
    - Fallback and load balancing
    - Runtime provider switching
    """
    

    def get_component_dependencies(self) -> List[str]:
        """Get list of required component dependencies."""
        return []  # Audio is foundational, no component dependencies
    
    def get_service_dependencies(self) -> Dict[str, type]:
        """Get list of required service dependencies."""
        return {}  # No service dependencies
    
    @property
    def name(self) -> str:
        return "audio"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Audio component managing multiple audio backends"
        

        
    @property
    def optional_dependencies(self) -> list[str]:
        """All audio provider dependencies are optional"""
        return ["sounddevice", "soundfile", "numpy", "audioplayer", "simpleaudio", "termcolor"]
        
    @property
    def enabled_by_default(self) -> bool:
        """Universal audio enabled by default"""
        return True
        
    @property  
    def category(self) -> str:
        """Plugin category"""
        return "audio"
        
    @property
    def platforms(self) -> list[str]:
        """Supported platforms (empty = all platforms)"""
        return []
    
    def __init__(self):
        super().__init__()
        self.providers: Dict[str, AudioProvider] = {}
        self.default_provider: str = "console"
        self.fallback_providers: List[str] = ["console"]
        
        # Dynamic provider discovery from entry-points (replaces hardcoded classes)
        self._provider_classes: Dict[str, type] = {}
        
        # Runtime state
        self._current_provider = None
        
    async def initialize(self, core) -> None:
        """Initialize the universal audio plugin"""
        await super().initialize(core)
        
        # Get configuration first to determine enabled providers (V14 Architecture)
        config = getattr(core.config, 'audio', None)
        if not config:
            # Create default config if missing
            from ..config.models import AudioConfig
            config = AudioConfig()
        
        # Convert Pydantic model to dict for backward compatibility with existing logic
        if hasattr(config, 'model_dump'):
            config_dict = config.model_dump()
        elif hasattr(config, 'dict'):
            config_dict = config.dict()
        else:
            # FATAL: Invalid configuration - cannot proceed with hardcoded defaults
            raise ValueError(
                "AudioComponent: Invalid configuration object received. "
                "Expected a valid AudioConfig instance, but got an invalid config. "
                "Please check your configuration file for proper v14 audio section formatting."
            )
        
        # Use the converted config dict
        config = config_dict
        
        # Update settings from config
        if isinstance(config, dict):
            self.default_provider = config.get("default_provider", self.default_provider)
            self.fallback_providers = config.get("fallback_providers", self.fallback_providers)
        else:
            # Handle config object case
            if hasattr(config, 'default_provider'):
                self.default_provider = config.default_provider
            if hasattr(config, 'fallback_providers'):
                self.fallback_providers = config.fallback_providers
        
        # Instantiate enabled providers
        providers_config = getattr(config, 'providers', {})
        if isinstance(config, dict):
            providers_config = config.get('providers', {})
        
        # Discover only enabled providers from entry-points (configuration-driven filtering)
        enabled_providers = [name for name, provider_config in providers_config.items() 
                            if provider_config.get("enabled", False)]
        
        # Always include console as fallback if not already included
        if "console" not in enabled_providers and providers_config.get("console", {}).get("enabled", True):
            enabled_providers.append("console")
            
        self._provider_classes = dynamic_loader.discover_providers("irene.providers.audio", enabled_providers)
        logger.info(f"Discovered {len(self._provider_classes)} enabled audio providers: {list(self._provider_classes.keys())}")
        
        enabled_count = 0
        
        for provider_name, provider_class in self._provider_classes.items():
            provider_config = providers_config.get(provider_name, {})
            if provider_config.get("enabled", False):
                try:
                    provider = provider_class(provider_config)
                    if await provider.is_available():
                        self.providers[provider_name] = provider
                        enabled_count += 1
                        logger.info(f"Loaded audio provider: {provider_name}")
                    else:
                        logger.warning(f"Audio provider {provider_name} not available (dependencies missing)")
                except TypeError as e:
                    logger.error(f"Audio provider {provider_name} missing required abstract methods: {e}")
                except Exception as e:
                    logger.warning(f"Failed to load audio provider {provider_name}: {e}")
        
        # Ensure we have at least one provider
        if not self.providers:
            logger.warning("No audio providers available, creating console provider as fallback")
            try:
                # Use entry-points discovery for fallback provider
                console_class = dynamic_loader.get_provider_class("irene.providers.audio", "console")
                if console_class:
                    console_provider = console_class({"enabled": True, "color_output": True})
                    self.providers["console"] = console_provider
                    self.default_provider = "console"
                    self.fallback_providers = ["console"]
                    enabled_count = 1
                else:
                    logger.error("Console audio provider not found in entry-points")
                    raise RuntimeError("No audio providers available")
            except Exception as e:
                logger.error(f"Failed to create fallback console audio provider: {e}")
                raise RuntimeError("No audio providers available")
        
        # Set default to first available if current default not available
        if self.default_provider not in self.providers:
            self.default_provider = list(self.providers.keys())[0]
            
        logger.info(f"Universal audio plugin initialized with {enabled_count} providers. Default: {self.default_provider}")
    
    # AudioPlugin interface - delegates to providers
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """Play an audio file using the specified or default provider"""
        provider_name = kwargs.get("provider", self.default_provider)
        
        if provider_name in self.providers:
            try:
                await self.providers[provider_name].play_file(file_path, **kwargs)
                self._current_provider = provider_name
            except Exception as e:
                logger.error(f"Audio playback failed with provider {provider_name}: {e}")
                await self._play_with_fallback(file_path, provider_name, **kwargs)
        else:
            logger.warning(f"Provider '{provider_name}' not available, using fallback")
            await self._play_with_fallback(file_path, provider_name, **kwargs)
    
    async def play_stream(self, audio_data: bytes, format: str = "wav", **kwargs) -> None:
        """Play audio from a byte stream"""
        provider_name = kwargs.get("provider", self.default_provider)
        
        # Convert bytes to async iterator
        async def byte_stream():
            yield audio_data
        
        if provider_name in self.providers:
            try:
                await self.providers[provider_name].play_stream(byte_stream(), **kwargs)
                self._current_provider = provider_name
            except Exception as e:
                logger.error(f"Audio stream playback failed with provider {provider_name}: {e}")
                await self._stream_with_fallback(audio_data, format, provider_name, **kwargs)
        else:
            await self._stream_with_fallback(audio_data, format, provider_name, **kwargs)
    
    async def stop_playback(self) -> None:
        """Stop current audio playback"""
        if self._current_provider and self._current_provider in self.providers:
            await self.providers[self._current_provider].stop_playback()
        
        # Stop all providers as fallback
        for provider in self.providers.values():
            try:
                await provider.stop_playback()
            except Exception as e:
                logger.debug(f"Error stopping provider: {e}")
    
    def get_supported_formats(self) -> list[str]:
        """Get union of all supported formats from all providers"""
        formats = set()
        for provider in self.providers.values():
            formats.update(provider.get_supported_formats())
        return list(formats)
    
    def get_playback_devices(self) -> list[Dict[str, Any]]:
        """Get devices from current provider"""
        if self.default_provider in self.providers:
            return self.providers[self.default_provider].get_playback_devices()
        return []
    
    async def set_output_device(self, device_id: str) -> None:
        """Set output device on current provider"""
        if self.default_provider in self.providers:
            await self.providers[self.default_provider].set_output_device(device_id)
    
    async def set_volume(self, volume: float) -> None:
        """Set volume on all providers"""
        for provider in self.providers.values():
            try:
                await provider.set_volume(volume)
            except Exception as e:
                logger.debug(f"Error setting volume on provider: {e}")
    
    # Public methods for intent handler delegation

    
    def set_default_provider(self, provider_name: str) -> bool:
        """Set default audio provider - simple atomic operation"""
        if provider_name in self.providers:
            self.default_provider = provider_name
            return True
        return False
    
    def get_providers_info(self) -> str:
        """Implementation of abstract method - Get audio providers information"""
        return self._get_providers_info()
    
    def parse_provider_name_from_text(self, text: str) -> Optional[str]:
        """Override base method with audio-specific logic"""
        # First try base implementation
        result = super().parse_provider_name_from_text(text)
        if result:
            return result
        
        # Audio-specific logic
        return self._parse_provider_name(text.lower())
    
    # WebAPIPlugin interface - unified API
    def get_router(self) -> APIRouter:
        """Get FastAPI router for audio endpoints"""
        router = APIRouter()
        
        @router.post("/play")
        async def play_audio(
            file: UploadFile = File(...),
            provider: Optional[str] = None,
            volume: Optional[float] = None,
            device: Optional[str] = None
        ):
            """Upload and play an audio file"""
            provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            # Save uploaded file to configured temp directory
            import uuid
            from ..config.models import CoreConfig
            
            # Get temp audio directory from configuration
            config = self.core.config if hasattr(self, 'core') and self.core else CoreConfig()
            temp_dir = config.assets.temp_audio_dir
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename
            filename = file.filename or "audio_file"
            suffix = Path(filename).suffix if filename else ".wav"
            unique_filename = f"{uuid.uuid4()}{suffix}"
            temp_path = temp_dir / unique_filename
            
            # Write uploaded content to file
            content = await file.read()
            temp_path.write_bytes(content)
            
            try:
                # Build parameters
                kwargs: Dict[str, Any] = {"provider": provider_name}
                if volume is not None:
                    kwargs["volume"] = volume
                if device is not None:
                    kwargs["device"] = device
                
                # Play the file
                await self.play_file(temp_path, **kwargs)
                
                return {
                    "success": True,
                    "provider": provider_name,
                    "file": file.filename,
                    "size": len(content)
                }
                
            finally:
                # Clean up temporary file
                if temp_path.exists():
                    temp_path.unlink()
        
        @router.post("/stream")
        async def play_audio_stream(
            audio_data: bytes,
            format: str = "wav",
            provider: Optional[str] = None,
            volume: Optional[float] = None
        ):
            """Play audio from raw data stream"""
            provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            kwargs: Dict[str, Any] = {"provider": provider_name}
            if volume is not None:
                kwargs["volume"] = volume
            
            await self.play_stream(audio_data, format, **kwargs)
            
            return {
                "success": True,
                "provider": provider_name,
                "format": format,
                "size": len(audio_data)
            }
        
        @router.post("/stop")
        async def stop_audio():
            """Stop current audio playback"""
            await self.stop_playback()
            return {"success": True, "message": "Audio playback stopped"}
        
        @router.get("/providers")
        async def list_providers():
            """List all available audio providers and their capabilities"""
            result = {}
            for name, provider in self.providers.items():
                result[name] = {
                    "available": await provider.is_available(),
                    "parameters": provider.get_parameter_schema(),
                    "capabilities": provider.get_capabilities(),
                    "formats": provider.get_supported_formats()
                }
            return {
                "providers": result,
                "default": self.default_provider,
                "fallbacks": self.fallback_providers
            }
        
        @router.get("/devices")
        async def list_devices(provider: Optional[str] = None):
            """List available audio output devices"""
            provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            devices = self.providers[provider_name].get_playback_devices()
            return {
                "provider": provider_name,
                "devices": devices
            }
        
        @router.post("/configure")
        async def configure_audio(
            provider: Optional[str] = None,
            set_as_default: bool = False,
            volume: Optional[float] = None,
            device: Optional[str] = None
        ):
            """Configure audio settings"""
            provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            # Apply configuration
            if set_as_default:
                self.default_provider = provider_name
            
            if volume is not None:
                await self.providers[provider_name].set_volume(volume)
            
            if device is not None:
                await self.providers[provider_name].set_output_device(device)
            
            return {
                "success": True,
                "provider": provider_name,
                "default_provider": self.default_provider,
                "volume": volume,
                "device": device
            }
        
        return router
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for audio API endpoints"""
        return "/audio"
    
    def get_api_tags(self) -> List[str]:
        """Get OpenAPI tags for audio endpoints"""
        return ["Audio Playback"]
    
    # Helper methods
    async def _play_with_fallback(self, file_path: Path, failed_provider: str, **kwargs) -> None:
        """Attempt playback with fallback providers"""
        for fallback in self.fallback_providers:
            if fallback != failed_provider and fallback in self.providers:
                try:
                    logger.info(f"Trying fallback audio provider: {fallback}")
                    await self.providers[fallback].play_file(file_path, **kwargs)
                    self._current_provider = fallback
                    return
                except Exception as e:
                    logger.warning(f"Fallback provider {fallback} also failed: {e}")
        
        raise RuntimeError("All audio providers failed")
    
    async def _stream_with_fallback(self, audio_data: bytes, format: str, failed_provider: str, **kwargs) -> None:
        """Attempt stream playback with fallback providers"""
        async def byte_stream():
            yield audio_data
            
        for fallback in self.fallback_providers:
            if fallback != failed_provider and fallback in self.providers:
                try:
                    logger.info(f"Trying fallback audio provider for stream: {fallback}")
                    await self.providers[fallback].play_stream(byte_stream(), **kwargs)
                    self._current_provider = fallback
                    return
                except Exception as e:
                    logger.warning(f"Fallback provider {fallback} also failed for stream: {e}")
        
        raise RuntimeError("All audio providers failed for stream playback")
    
    def _parse_provider_name(self, command: str) -> Optional[str]:
        """Extract provider name from voice command"""
        for provider_name in self.providers.keys():
            if provider_name in command:
                return provider_name
        return None
    
    def _get_providers_info(self) -> str:
        """Get formatted information about available providers"""
        if not self.providers:
            return "Нет доступных аудио провайдеров"
        
        info_lines = [f"Доступные аудио провайдеры ({len(self.providers)}):"]
        for name, provider in self.providers.items():
            status = "✅" if name == self.default_provider else "⚪"
            capabilities = provider.get_capabilities()
            formats = ", ".join(capabilities.get("formats", [])[:3])  # Show first 3 formats
            info_lines.append(f"{status} {name}: {formats}")
        
        info_lines.append(f"По умолчанию: {self.default_provider}")
        return "\n".join(info_lines)
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Audio component needs web API functionality"""
        return [
            "fastapi>=0.100.0", 
            "uvicorn[standard]>=0.20.0",
            "python-multipart>=0.0.6"  # Required for file upload endpoints
        ]
    
    # Config interface methods (Phase 3 - Configuration Architecture Cleanup)
    @classmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the Pydantic config model for this component"""
        from ..config.models import AudioConfig
        return AudioConfig
    
    @classmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to this component's config (V14 Architecture)"""
        return "audio" 