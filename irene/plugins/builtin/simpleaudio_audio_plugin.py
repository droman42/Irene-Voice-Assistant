"""
SimpleAudio Audio Plugin - Simple audio playback backend

Replaces legacy plugin_playwav_simpleaudio.py with modern async architecture.
Provides simple audio playback using the simpleaudio library.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from ...core.interfaces.audio import AudioPlugin

logger = logging.getLogger(__name__)


class SimpleAudioPlugin(AudioPlugin):
    """
    SimpleAudio audio plugin for simple audio playback.
    
    Features:
    - Simple WAV file playback using simpleaudio
    - Lightweight and minimal dependencies
    - Cross-platform compatibility
    - Async operation with threading
    - Graceful handling of missing dependencies
    """
    
    @property
    def name(self) -> str:
        return "simpleaudio_audio"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Simple WAV playback using simpleaudio with volume control"
        
    @property
    def dependencies(self) -> list[str]:
        """No required dependencies (simpleaudio is optional)"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """Requires simpleaudio for WAV playback"""
        return ["simpleaudio", "numpy"]
        
    # Additional metadata for PluginRegistry discovery
    @property
    def enabled_by_default(self) -> bool:
        """SimpleAudio not enabled by default (requires dependency)"""
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
        self._current_playback = None
        self._volume = 1.0
        
        # Try to import simpleaudio
        try:
            import simpleaudio as sa  # type: ignore
            self._sa = sa
            self._available = True
            logger.info("SimpleAudio audio backend available")
            
        except ImportError as e:
            logger.warning(f"SimpleAudio dependency not available: {e}")
            logger.info("Install with: uv add 'simpleaudio>=1.0.4'")
            self._sa = None
            
    def is_available(self) -> bool:
        """Check if simpleaudio backend is available"""
        return self._available
        
    async def initialize(self, core) -> None:
        """Initialize the audio plugin"""
        await super().initialize(core)
        
        if not self._available:
            logger.warning("SimpleAudio audio plugin initialized but dependencies missing")
            return
            
        logger.info("SimpleAudio audio plugin initialized successfully")
            
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """
        Play an audio file using simpleaudio.
        
        Args:
            file_path: Path to the audio file (must be WAV format)
            **kwargs: volume (float) - applied by data manipulation
        """
        if not self._available or not self._sa:
            raise RuntimeError("SimpleAudio audio backend not available")
            
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
            
        # Check if file is WAV format
        if file_path.suffix.lower() != '.wav':
            raise ValueError(f"SimpleAudio only supports WAV files, got: {file_path.suffix}")
            
        try:
            volume = kwargs.get('volume', self._volume)
            
            logger.debug(f"Playing WAV file: {file_path}")
            
            # Load WAV file
            wave_obj = self._sa.WaveObject.from_wave_file(str(file_path))
            
            # Apply volume if needed (requires numpy)
            if volume != 1.0:
                try:
                    import numpy as np  # type: ignore
                    # Get raw audio data and apply volume
                    audio_data = wave_obj.audio_data
                    # Convert to numpy array, apply volume, and convert back
                    np_data = np.frombuffer(audio_data, dtype=np.int16)
                    np_data = (np_data * volume).astype(np.int16)
                    
                    # Create new wave object with modified data
                    wave_obj = self._sa.WaveObject(
                        np_data.tobytes(),
                        wave_obj.num_channels,
                        wave_obj.bytes_per_sample,
                        wave_obj.sample_rate
                    )
                except ImportError:
                    logger.warning("numpy not available - volume control disabled")
                except Exception as e:
                    logger.warning(f"Failed to apply volume: {e}")
            
            # Play audio asynchronously
            await self._play_wave_async(wave_obj)
            
        except Exception as e:
            logger.error(f"Failed to play audio file {file_path}: {e}")
            raise RuntimeError(f"Audio playback failed: {e}")
            
    async def play_stream(self, audio_data: bytes, format: str = "wav", **kwargs) -> None:
        """
        Play audio from a byte stream.
        
        Args:
            audio_data: Raw audio data
            format: Audio format (only 'wav' supported)
            **kwargs: Additional parameters
        """
        if not self._available or not self._sa:
            raise RuntimeError("SimpleAudio audio backend not available")
            
        if format.lower() != 'wav':
            raise ValueError(f"SimpleAudio only supports WAV format, got: {format}")
            
        # For stream playback, we'd need to parse WAV header or use tempfile
        # For now, raise NotImplementedError
        raise NotImplementedError("Stream playback not yet implemented for SimpleAudio backend")
        
    async def stop_playback(self) -> None:
        """Stop current audio playback"""
        if self._current_playback and self._current_playback.is_playing():
            try:
                self._current_playback.stop()
                self._current_playback = None
                logger.debug("Audio playback stopped")
            except Exception as e:
                logger.warning(f"Error stopping playback: {e}")
                
    async def pause_playback(self) -> None:
        """Pause current audio playback (not supported by simpleaudio)"""
        logger.warning("Pause not supported by simpleaudio backend")
        
    async def resume_playback(self) -> None:
        """Resume paused audio playback (not supported by simpleaudio)"""
        logger.warning("Resume not supported by simpleaudio backend")
        
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats"""
        if not self._available:
            return []
            
        # SimpleAudio only supports WAV files
        return ['wav']
        
    def get_playback_devices(self) -> List[Dict[str, Any]]:
        """Get list of available audio output devices"""
        # SimpleAudio uses system default - no device enumeration
        return [{'id': 'default', 'name': 'System Default', 'default': True}]
        
    async def set_output_device(self, device_id: Union[str, int]) -> None:
        """Set the audio output device"""
        # SimpleAudio doesn't support device selection
        if device_id != 'default':
            logger.warning("SimpleAudio backend only supports system default audio device")
        
    async def set_volume(self, volume: float) -> None:
        """Set playback volume (0.0 to 1.0)"""
        if volume < 0.0 or volume > 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
            
        self._volume = volume
        logger.debug(f"Audio volume set to: {volume}")
        logger.info("Volume will be applied to next playback (requires numpy)")
        
    async def _play_wave_async(self, wave_obj) -> None:
        """Play wave object asynchronously using threading"""
        try:
            # Use asyncio.to_thread for blocking operations
            await asyncio.to_thread(self._play_wave_blocking, wave_obj)
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            raise
        finally:
            self._current_playback = None
            
    def _play_wave_blocking(self, wave_obj) -> None:
        """Blocking audio playback (called from thread)"""
        try:
            # Play wave and wait for completion
            play_obj = wave_obj.play()
            self._current_playback = play_obj
            play_obj.wait_done()
            
        except Exception as e:
            logger.error(f"SimpleAudio playback error: {e}")
            raise 