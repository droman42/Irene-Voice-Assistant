"""
AudioPlayer Audio Plugin - Cross-platform audio playback

Replaces legacy plugin_playwav_audioplayer.py with modern async architecture.
Provides simple cross-platform audio playback using the audioplayer library.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from ...core.interfaces.audio import AudioPlugin

logger = logging.getLogger(__name__)


class AudioPlayerAudioPlugin(AudioPlugin):
    """
    AudioPlayer audio plugin for cross-platform audio playback.
    
    Features:
    - Simple cross-platform audio playback
    - Minimal dependencies
    - Good compatibility across operating systems
    - Async operation with threading
    - Graceful handling of missing dependencies
    """
    
    @property
    def name(self) -> str:
        return "audioplayer_audio"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Cross-platform audio playback using audioplayer with threading"
        
    @property
    def dependencies(self) -> list[str]:
        """No required dependencies (audioplayer is optional)"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """Requires audioplayer for cross-platform support"""
        return ["audioplayer"]
        
    # Additional metadata for PluginRegistry discovery
    @property
    def enabled_by_default(self) -> bool:
        """AudioPlayer not enabled by default (requires dependency)"""
        return False
        
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
        self._available = False
        self._current_player = None
        self._volume = 1.0
        
        # Try to import audioplayer
        try:
            from audioplayer import AudioPlayer  # type: ignore
            self._AudioPlayer = AudioPlayer
            self._available = True
            logger.info("AudioPlayer audio backend available")
            
        except ImportError as e:
            logger.warning(f"AudioPlayer dependency not available: {e}")
            logger.info("Install with: uv add 'audioplayer>=0.6.0'")
            self._AudioPlayer = None
            
    def is_available(self) -> bool:
        """Check if audioplayer backend is available"""
        return self._available
        
    async def initialize(self, core) -> None:
        """Initialize the audio plugin"""
        await super().initialize(core)
        
        if not self._available:
            logger.warning("AudioPlayer audio plugin initialized but dependencies missing")
            return
            
        logger.info("AudioPlayer audio plugin initialized successfully")
            
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """
        Play an audio file using audioplayer.
        
        Args:
            file_path: Path to the audio file
            **kwargs: volume (float) - other parameters ignored
        """
        if not self._available or not self._AudioPlayer:
            raise RuntimeError("AudioPlayer audio backend not available")
            
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
            
        try:
            volume = kwargs.get('volume', self._volume)
            
            logger.debug(f"Playing audio file: {file_path}")
            
            # Create audio player instance
            player = self._AudioPlayer(str(file_path))
            self._current_player = player
            
            # Set volume if supported
            if hasattr(player, 'volume') and volume != 1.0:
                try:
                    player.volume = int(volume * 100)  # AudioPlayer uses 0-100 scale
                except Exception as e:
                    logger.warning(f"Failed to set volume: {e}")
            
            # Play audio asynchronously
            await self._play_audio_async(player)
            
        except Exception as e:
            logger.error(f"Failed to play audio file {file_path}: {e}")
            raise RuntimeError(f"Audio playback failed: {e}")
        finally:
            self._current_player = None
            
    async def play_stream(self, audio_data: bytes, format: str = "wav", **kwargs) -> None:
        """
        Play audio from a byte stream.
        
        Args:
            audio_data: Raw audio data
            format: Audio format 
            **kwargs: Additional parameters
        """
        # AudioPlayer doesn't support direct byte stream playback
        # Would need to write to temporary file
        raise NotImplementedError("Stream playback not supported by AudioPlayer backend")
        
    async def stop_playback(self) -> None:
        """Stop current audio playback"""
        if self._current_player:
            try:
                if hasattr(self._current_player, 'stop'):
                    await asyncio.to_thread(self._current_player.stop)
                elif hasattr(self._current_player, 'close'):
                    await asyncio.to_thread(self._current_player.close)
                    
                self._current_player = None
                logger.debug("Audio playback stopped")
            except Exception as e:
                logger.warning(f"Error stopping playback: {e}")
                
    async def pause_playback(self) -> None:
        """Pause current audio playback"""
        if self._current_player and hasattr(self._current_player, 'pause'):
            try:
                await asyncio.to_thread(self._current_player.pause)
                logger.debug("Audio playback paused")
            except Exception as e:
                logger.warning(f"Error pausing playback: {e}")
        else:
            logger.warning("Pause not supported by current AudioPlayer instance")
        
    async def resume_playback(self) -> None:
        """Resume paused audio playback"""
        if self._current_player and hasattr(self._current_player, 'resume'):
            try:
                await asyncio.to_thread(self._current_player.resume)
                logger.debug("Audio playback resumed")
            except Exception as e:
                logger.warning(f"Error resuming playback: {e}")
        else:
            logger.warning("Resume not supported by current AudioPlayer instance")
        
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats"""
        if not self._available:
            return []
            
        # AudioPlayer supports common formats
        return ['wav', 'mp3', 'ogg', 'flac', 'm4a', 'wma']
        
    def get_playback_devices(self) -> List[Dict[str, Any]]:
        """Get list of available audio output devices"""
        # AudioPlayer uses system default - no device enumeration
        return [{'id': 'default', 'name': 'System Default', 'default': True}]
        
    async def set_output_device(self, device_id: Union[str, int]) -> None:
        """Set the audio output device"""
        # AudioPlayer doesn't support device selection
        if device_id != 'default':
            logger.warning("AudioPlayer backend only supports system default audio device")
        
    async def set_volume(self, volume: float) -> None:
        """Set playback volume (0.0 to 1.0)"""
        if volume < 0.0 or volume > 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
            
        self._volume = volume
        logger.debug(f"Audio volume set to: {volume}")
        
        # Apply to current player if active
        if self._current_player and hasattr(self._current_player, 'volume'):
            try:
                self._current_player.volume = int(volume * 100)
            except Exception as e:
                logger.warning(f"Failed to apply volume to current playback: {e}")
        
    async def _play_audio_async(self, player) -> None:
        """Play audio using threading to avoid blocking"""
        try:
            # Use asyncio.to_thread for blocking operations
            await asyncio.to_thread(self._play_audio_blocking, player)
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            raise
            
    def _play_audio_blocking(self, player) -> None:
        """Blocking audio playback (called from thread)"""
        try:
            # Play and wait for completion
            player.play(block=True)
        except Exception as e:
            logger.error(f"AudioPlayer playback error: {e}")
            raise 