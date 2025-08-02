"""
AudioPlayer Audio Provider - Cross-platform audio playback

Converted from irene/plugins/builtin/audioplayer_audio_plugin.py to provider pattern.
Provides simple cross-platform audio playback using the audioplayer library.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, AsyncIterator

from .base import AudioProvider

logger = logging.getLogger(__name__)


class AudioPlayerAudioProvider(AudioProvider):
    """
    AudioPlayer audio provider for cross-platform audio playback.
    
    Features:
    - Simple cross-platform audio playback
    - Minimal dependencies
    - Good compatibility across operating systems
    - Async operation with threading
    - Graceful handling of missing dependencies
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize AudioPlayerAudioProvider with configuration."""
        super().__init__(config)
        
        # Configuration values
        self.volume = config.get("volume", 0.8)
        self.fade_in = config.get("fade_in", False)
        self.fade_out = config.get("fade_out", True)
        
        # Runtime state
        self._current_playback = None
        self._volume = self.volume
        self._available = False
        
        # Try to import audioplayer
        try:
            from audioplayer import AudioPlayer  # type: ignore
            self._AudioPlayer = AudioPlayer
            self._available = True
            logger.debug("AudioPlayer audio provider: dependencies available")
        except ImportError as e:
            self._AudioPlayer = None
            self._available = False
            logger.warning(f"AudioPlayer audio provider: dependencies missing - {e}")
    
    async def is_available(self) -> bool:
        """Check if AudioPlayer dependencies are available"""
        return self._available
    
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """Play an audio file using audioplayer."""
        if not self._available or not self._AudioPlayer:
            raise RuntimeError("AudioPlayer audio backend not available")
            
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
            
        try:
            volume = kwargs.get('volume', self._volume)
            
            # Play audio asynchronously
            await asyncio.to_thread(self._play_audio_blocking, str(file_path), volume)
            
        except Exception as e:
            logger.error(f"Failed to play audio file {file_path}: {e}")
            raise RuntimeError(f"Audio playback failed: {e}")
    
    async def play_stream(self, audio_stream: AsyncIterator[bytes], **kwargs) -> None:
        """Play audio from a byte stream."""
        # Collect stream data and save to temporary file
        try:
            audio_data = b''
            async for chunk in audio_stream:
                audio_data += chunk
            
            # Save to temporary file and play
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = Path(temp_file.name)
            
            try:
                await self.play_file(temp_path, **kwargs)
            finally:
                if temp_path.exists():
                    temp_path.unlink()
                    
        except Exception as e:
            logger.error(f"Failed to play audio stream: {e}")
            raise RuntimeError(f"Audio stream playback failed: {e}")
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for provider-specific parameters"""
        return {
            "volume": {
                "type": "number",
                "description": "Playback volume",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.8
            }
        }
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats"""
        if not self._available:
            return []
        return ['wav', 'mp3', 'ogg', 'flac', 'm4a']
    
    async def set_volume(self, volume: float) -> None:
        """Set playback volume"""
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
        self._volume = volume
    
    async def stop_playback(self) -> None:
        """Stop current audio playback"""
        # AudioPlayer doesn't support stopping, track current playback for future enhancement
        self._current_playback = None
    
    def get_provider_name(self) -> str:
        """Get unique provider identifier"""
        return "audioplayer"
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities information"""
        return {
            "formats": self.get_supported_formats(),
            "features": [
                "cross_platform",
                "simple",
                "volume_control"
            ] if self._available else ["unavailable"],
            "concurrent_playback": False,
            "devices": False,
            "quality": "good",
            "speed": "medium"
        }
    
    def get_volume(self) -> float:
        """Get current playback volume"""
        return self._volume
        
    def is_playing(self) -> bool:
        """Check if audio is currently playing"""
        return self._current_playback is not None
    
    async def validate_parameters(self, **kwargs) -> bool:
        """Validate provider-specific parameters"""
        try:
            if "volume" in kwargs:
                volume = kwargs["volume"]
                if not isinstance(volume, (int, float)) or not 0.0 <= volume <= 1.0:
                    return False
            return True
        except (ValueError, TypeError):
            return False
    
    async def configure(self, config: Dict[str, Any]) -> None:
        """Update provider configuration at runtime"""
        self.config.update(config)
        
        if "volume" in config:
            self.volume = config["volume"]
            self._volume = self.volume
            
        logger.debug(f"AudioPlayer audio provider configuration updated: {config}")
    
    def _play_audio_blocking(self, file_path: str, volume: float) -> None:
        """Blocking audio playback (called from thread)"""
        if not self._AudioPlayer:
            return
            
        try:
            self._current_playback = file_path
            
            # Create AudioPlayer instance and play
            player = self._AudioPlayer(file_path)
            player.volume = int(volume * 100)  # AudioPlayer uses 0-100 range
            player.play(block=True)  # Block until playback completes
            
        except Exception as e:
            logger.error(f"AudioPlayer playback error: {e}")
            raise
        finally:
            self._current_playback = None 