"""
Audio Provider Interface - Abstract base class for audio implementations

Defines the interface that all audio provider implementations must follow.
This is used by UniversalAudioPlugin to manage multiple audio backends.
"""

from typing import Dict, Any, List, AsyncIterator
from pathlib import Path
from abc import abstractmethod

from ..base import ProviderBase


class AudioProvider(ProviderBase):
    """
    Abstract base class for audio provider implementations.
    
    Audio providers are pure implementation classes without plugin overhead,
    managed by UniversalAudioPlugin through configuration-driven instantiation.
    
    Enhanced in TODO #4 Phase 1 with proper ProviderBase inheritance.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration dictionary
        """
        # Call ProviderBase.__init__ to get status tracking, logging, etc.
        super().__init__(config)
    
    @abstractmethod
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """
        Play an audio file.
        
        Args:
            file_path: Path to the audio file
            **kwargs: Provider-specific parameters (volume, device, etc.)
        """
        pass
    
    @abstractmethod
    async def play_stream(self, audio_stream: AsyncIterator[bytes], **kwargs) -> None:
        """
        Play audio from a byte stream.
        
        Args:
            audio_stream: Async iterator of audio data chunks
            **kwargs: Provider-specific parameters
        """
        pass
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """
        Auto-generate parameter schema from Pydantic model.
        
        Used by UniversalAudioPlugin to validate requests and provide
        API documentation.
        
        Returns:
            JSON Schema-like dictionary describing supported parameters
        """
        from irene.config.auto_registry import AutoSchemaRegistry
        
        # Extract component type from module path
        component_type = self.__class__.__module__.split('.')[-2]  # e.g., 'tts', 'audio'
        provider_name = self.get_provider_name()
        
        return AutoSchemaRegistry.get_provider_parameter_schema(component_type, provider_name)
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported audio file formats.
        
        Returns:
            List of format extensions (e.g., ['wav', 'mp3', 'ogg'])
        """
        pass
    
    @abstractmethod
    async def set_volume(self, volume: float) -> None:
        """
        Set playback volume.
        
        Args:
            volume: Volume level (0.0 to 1.0)
        """
        pass
    
    @abstractmethod
    async def stop_playback(self) -> None:
        """Stop current audio playback."""
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return provider capabilities information.
        
        Returns:
            Dictionary containing:
            - formats: List of supported audio formats
            - features: List of special features supported
            - concurrent_playback: Whether concurrent playback is supported
            - devices: Whether device selection is supported
        """
        return {
            "formats": self.get_supported_formats(),
            "features": [],
            "concurrent_playback": False,
            "devices": False
        }
    
    async def pause_playback(self) -> None:
        """Pause current audio playback."""
        # Default implementation - override if provider supports pausing
        pass
        
    async def resume_playback(self) -> None:
        """Resume paused audio playback."""
        # Default implementation - override if provider supports resume
        pass
    
    def get_playback_devices(self) -> List[Dict[str, Any]]:
        """
        Get list of available audio output devices.
        
        Returns:
            List of device information dictionaries
        """
        # Default implementation - override if provider supports device selection
        return []
        
    async def set_output_device(self, device_id: str) -> None:
        """
        Set the audio output device.
        
        Args:
            device_id: Device identifier
        """
        # Default implementation - override if provider supports device selection
        pass
    
    def get_volume(self) -> float:
        """
        Get current playback volume.
        
        Returns:
            Current volume level (0.0 to 1.0)
        """
        # Default implementation - override if provider supports volume reading
        return 1.0
        
    def is_playing(self) -> bool:
        """
        Check if audio is currently playing.
        
        Returns:
            True if audio is playing
        """
        # Default implementation - override if provider supports playback status
        return False
    
    async def validate_parameters(self, **kwargs) -> bool:
        """
        Validate provider-specific parameters.
        
        Args:
            **kwargs: Parameters to validate
            
        Returns:
            True if all parameters are valid
        """
        # Default implementation - override for specific validation
        return True
    
    async def configure(self, config: Dict[str, Any]) -> None:
        """
        Update provider configuration at runtime.
        
        Args:
            config: New configuration values
        """
        # Default implementation - override if provider supports runtime config
        self.config.update(config) 