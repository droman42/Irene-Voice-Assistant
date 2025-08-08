"""
Audio Component - Audio coordinator managing multiple providers

Implements the fundamental component pattern for audio playback functionality.
Manages multiple audio providers based on configuration and provides unified web APIs.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File  # type: ignore
from pydantic import BaseModel

from .base import Component
from ..core.interfaces.audio import AudioPlugin
from ..core.interfaces.webapi import WebAPIPlugin
from ..core.interfaces.command import CommandPlugin
from ..core.context import Context
from ..core.commands import CommandResult

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


class AudioComponent(Component, AudioPlugin, WebAPIPlugin, CommandPlugin):
    """
    Audio Component that manages multiple audio providers.
    
    Features:
    - Configuration-driven provider instantiation
    - Unified web API (/audio/*)
    - Voice commands for audio control
    - Fallback and load balancing
    - Runtime provider switching
    """
    
    def get_dependencies(self) -> List[str]:
        """Get list of dependencies for this component."""
        return self.dependencies  # Use @property for consistency
    
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
    def dependencies(self) -> list[str]:
        """No required dependencies (providers handle their own)"""
        return []
        
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
        
        # Get configuration first to determine enabled providers
        config = getattr(core.config.plugins, 'universal_audio', None)
        if not config:
            # Create default config if missing
            config = {
                "enabled": True,
                "default_provider": "console",
                "fallback_providers": ["console"],
                "concurrent_playback": False,
                "providers": {
                    "console": {
                        "enabled": True,
                        "color_output": True,
                        "timing_simulation": False
                    }
                }
            }
        
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
    
    # CommandPlugin interface - voice control
    def get_triggers(self) -> List[str]:
        """Get command triggers for audio control"""
        return [
            "играй", "воспроизведи", "останови", "стоп", "музыка", "аудио",
            "переключись на", "покажи аудио", "список аудио", "громкость"
        ]
    
    async def can_handle(self, command: str, context: Context) -> bool:
        """Check if this command is audio-related"""
        triggers = self.get_triggers()
        command_lower = command.lower()
        return any(trigger in command_lower for trigger in triggers)
    
    async def handle_command(self, command: str, context: Context) -> CommandResult:
        """Handle voice commands for audio control"""
        command_lower = command.lower()
        
        if "играй" in command_lower or "воспроизведи" in command_lower:
            # "играй музыку", "воспроизведи файл"
            return CommandResult(success=True, response="Команды воспроизведения аудио доступны через веб-API")
            
        elif "останови" in command_lower and ("аудио" in command_lower or "музыку" in command_lower):
            # "останови аудио", "останови музыку"
            await self.stop_playback()
            return CommandResult(success=True, response="Воспроизведение аудио остановлено")
            
        elif "переключись на" in command_lower and ("аудио" in command_lower):
            # "переключись на sounddevice аудио"
            provider_name = self._parse_provider_name(command_lower)
            if provider_name and provider_name in self.providers:
                self.default_provider = provider_name
                return CommandResult(success=True, response=f"Переключился на аудио провайдер {provider_name}")
            else:
                available = ", ".join(self.providers.keys())
                return CommandResult(success=False, response=f"Неизвестный провайдер. Доступные: {available}")
                
        elif "покажи аудио" in command_lower or "список аудио" in command_lower:
            # "покажи аудио провайдеры", "список аудио устройств"
            info = self._get_providers_info()
            return CommandResult(success=True, response=info)
        
        return CommandResult(success=False, response="Неизвестная аудио команда")
    
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
            
            # Save uploaded file temporarily
            import tempfile
            filename = file.filename or "audio_file"
            suffix = Path(filename).suffix if filename else ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_path = Path(temp_file.name)
            
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
        return ["fastapi>=0.100.0", "uvicorn[standard]>=0.20.0"] 