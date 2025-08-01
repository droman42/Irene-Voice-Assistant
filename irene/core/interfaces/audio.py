"""
Audio Plugin Interface - For audio playback functionality

Defines the interface for plugins that handle audio playback
and audio processing operations.
"""

from typing import Dict, Any, Optional, AsyncIterator
from abc import abstractmethod
from pathlib import Path

from .plugin import PluginInterface


class AudioPlugin(PluginInterface):
    """
    Interface for Audio playback plugins.
    
    Audio plugins handle audio file playback, streaming,
    and audio processing operations.
    """
    
    @abstractmethod
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """
        Play an audio file.
        
        Args:
            file_path: Path to the audio file
            **kwargs: Playback parameters (volume, loop, etc.)
        """
        pass
        
    @abstractmethod
    async def play_stream(self, audio_data: bytes, format: str = "wav", **kwargs) -> None:
        """
        Play audio from a byte stream.
        
        Args:
            audio_data: Raw audio data
            format: Audio format (wav, mp3, etc.)
            **kwargs: Playback parameters
        """
        pass
        
    async def stop_playback(self) -> None:
        """Stop current audio playback."""
        pass
        
    async def pause_playback(self) -> None:
        """Pause current audio playback."""
        pass
        
    async def resume_playback(self) -> None:
        """Resume paused audio playback."""
        pass
        
    def get_supported_formats(self) -> list[str]:
        """
        Get list of supported audio formats.
        
        Returns:
            List of format extensions (e.g., ['wav', 'mp3', 'ogg'])
        """
        return ['wav']
        
    def get_playback_devices(self) -> list[Dict[str, Any]]:
        """
        Get list of available audio output devices.
        
        Returns:
            List of device information dictionaries
        """
        return []
        
    async def set_output_device(self, device_id: str) -> None:
        """
        Set the audio output device.
        
        Args:
            device_id: Device identifier
        """
        pass
        
    async def set_volume(self, volume: float) -> None:
        """
        Set playback volume.
        
        Args:
            volume: Volume level (0.0 to 1.0)
        """
        pass
        
    def get_volume(self) -> float:
        """
        Get current playback volume.
        
        Returns:
            Current volume level (0.0 to 1.0)
        """
        return 1.0
        
    def is_playing(self) -> bool:
        """
        Check if audio is currently playing.
        
        Returns:
            True if audio is playing
        """
        return False
        
    def is_available(self) -> bool:
        """
        Check if audio playback is available.
        
        Returns:
            True if audio system is functional
        """
        return True 