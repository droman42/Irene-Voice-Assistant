"""
SoundDevice Audio Plugin - Primary audio playback backend

Replaces legacy plugin_playwav_sounddevice.py with modern async architecture.
Provides high-quality audio playback using sounddevice and soundfile libraries.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from ...core.interfaces.audio import AudioPlugin

logger = logging.getLogger(__name__)


class SoundDeviceAudioPlugin(AudioPlugin):
    """
    SoundDevice audio plugin for high-quality audio playback.
    
    Features:
    - High-quality audio playback using sounddevice
    - Support for multiple audio formats via soundfile
    - Device selection and configuration
    - Async operation with proper resource management
    - Graceful handling of missing dependencies
    """
    
    @property
    def name(self) -> str:
        return "sounddevice_audio"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "High-quality audio playback using sounddevice with device selection"
        
    @property
    def dependencies(self) -> list[str]:
        """No required dependencies (sounddevice is optional)"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """Requires sounddevice for high-quality audio"""
        return ["sounddevice", "soundfile"]
        
    # Additional metadata for PluginRegistry discovery
    @property
    def enabled_by_default(self) -> bool:
        """SoundDevice not enabled by default (requires dependency)"""
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
        self._output_device = None
        self._volume = 1.0
        self._sample_rate = None
        
        # Try to import dependencies
        try:
            import sounddevice as sd  # type: ignore
            import soundfile as sf  # type: ignore
            import numpy as np  # type: ignore
            
            self._sd = sd
            self._sf = sf
            self._np = np
            self._available = True
            logger.info("SoundDevice audio backend available")
            
        except ImportError as e:
            logger.warning(f"SoundDevice dependencies not available: {e}")
            logger.info("Install with: uv add 'sounddevice>=0.4.0' 'soundfile>=0.12.0' 'numpy>=1.20.0'")
            self._sd = None
            self._sf = None
            self._np = None
            
    def is_available(self) -> bool:
        """Check if sounddevice backend is available"""
        return self._available
        
    async def initialize(self, core) -> None:
        """Initialize the audio plugin"""
        await super().initialize(core)
        
        if not self._available:
            logger.warning("SoundDevice audio plugin initialized but dependencies missing")
            return
            
        # Set default settings
        try:
            if self._sd:
                # Get default output device
                default_device = self._sd.default.device[1]  # Output device
                self._output_device = default_device
                logger.info(f"Using default audio output device: {default_device}")
                
        except Exception as e:
            logger.error(f"Failed to initialize audio device: {e}")
            
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """
        Play an audio file using sounddevice.
        
        Args:
            file_path: Path to the audio file
            **kwargs: volume (float), device (str/int), sample_rate (int)
        """
        if not self._available or not self._sd or not self._sf or not self._np:
            raise RuntimeError("SoundDevice audio backend not available")
            
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
            
        try:
            # Extract parameters
            volume = kwargs.get('volume', self._volume)
            device = kwargs.get('device', self._output_device)
            
            # Load audio file
            logger.debug(f"Loading audio file: {file_path}")
            audio_data, sample_rate = self._sf.read(str(file_path), dtype='float32')
            
            # Apply volume
            if volume != 1.0:
                audio_data = audio_data * volume
                
            # Add zero padding to fix audio cutoff issue
            # This prevents the end of audio from being cut off
            # See: https://github.com/spatialaudio/python-sounddevice/issues/283
            zeros = self._np.zeros((5000,))
            if len(audio_data.shape) == 1:
                # Mono audio
                audio_data = self._np.concatenate((audio_data, zeros))
            else:
                # Stereo audio
                stereo_zeros = self._np.zeros((5000, audio_data.shape[1]))
                audio_data = self._np.concatenate((audio_data, stereo_zeros))
                
            logger.debug(f"Playing audio: {file_path.name}, duration: {len(audio_data)/sample_rate:.2f}s")
            
            # Play audio asynchronously
            await self._play_audio_async(audio_data, sample_rate, device)
            
        except Exception as e:
            logger.error(f"Failed to play audio file {file_path}: {e}")
            raise RuntimeError(f"Audio playback failed: {e}")
            
    async def play_stream(self, audio_data: bytes, format: str = "wav", **kwargs) -> None:
        """
        Play audio from a byte stream.
        
        Args:
            audio_data: Raw audio data
            format: Audio format (only 'wav' supported currently)
            **kwargs: volume (float), device (str/int), sample_rate (int)
        """
        if not self._available or not self._sd:
            raise RuntimeError("SoundDevice audio backend not available")
            
        if format.lower() != 'wav':
            raise ValueError(f"Unsupported audio format: {format} (only 'wav' supported)")
            
        # For stream playback, we'd need to implement WAV parsing or use tempfile
        # For now, raise NotImplementedError
        raise NotImplementedError("Stream playback not yet implemented for SoundDevice backend")
        
    async def stop_playback(self) -> None:
        """Stop current audio playback"""
        if self._sd and self._current_playback:
            try:
                self._sd.stop()
                self._current_playback = None
                logger.debug("Audio playback stopped")
            except Exception as e:
                logger.warning(f"Error stopping playback: {e}")
                
    async def pause_playback(self) -> None:
        """Pause current audio playback (not supported by sounddevice)"""
        logger.warning("Pause not supported by sounddevice backend")
        
    async def resume_playback(self) -> None:
        """Resume paused audio playback (not supported by sounddevice)"""
        logger.warning("Resume not supported by sounddevice backend")
        
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats"""
        if not self._available:
            return []
            
        # Formats supported by soundfile
        return ['wav', 'flac', 'ogg', 'aiff', 'au', 'raw', 'paf', 'svx', 'nist', 'voc', 'ircam', 'w64', 'mat4', 'mat5', 'pvf', 'xi', 'htk', 'sds', 'avr', 'wavex', 'sd2', 'caf', 'wve', 'mpc2k', 'rf64']
        
    def get_playback_devices(self) -> List[Dict[str, Any]]:
        """Get list of available audio output devices"""
        if not self._available or not self._sd:
            return []
            
        try:
            devices = self._sd.query_devices()
            output_devices = []
            
            for i, device in enumerate(devices):
                if device['max_output_channels'] > 0:
                    output_devices.append({
                        'id': i,
                        'name': device['name'],
                        'max_channels': device['max_output_channels'],
                        'default_sample_rate': device['default_samplerate'],
                        'hostapi': device['hostapi']
                    })
                    
            return output_devices
            
        except Exception as e:
            logger.error(f"Failed to query audio devices: {e}")
            return []
            
    async def set_output_device(self, device_id: Union[str, int]) -> None:
        """Set the audio output device"""
        if not self._available:
            raise RuntimeError("SoundDevice audio backend not available")
            
        try:
            # Convert string ID to int if needed
            if isinstance(device_id, str) and device_id.isdigit():
                device_id = int(device_id)
                
            self._output_device = device_id
            logger.info(f"Audio output device set to: {device_id}")
            
        except Exception as e:
            logger.error(f"Failed to set output device: {e}")
            raise ValueError(f"Invalid device ID: {device_id}")
            
    async def set_volume(self, volume: float) -> None:
        """Set playback volume (0.0 to 1.0)"""
        if volume < 0.0 or volume > 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
            
        self._volume = volume
        logger.debug(f"Audio volume set to: {volume}")
        
    async def _play_audio_async(self, audio_data, sample_rate: int, device=None) -> None:
        """Play audio data asynchronously using threading"""
        if not self._sd:
            return
            
        # Store current playback reference
        self._current_playback = audio_data
        
        # Use asyncio.to_thread to run blocking sounddevice operations
        try:
            await asyncio.to_thread(self._play_audio_blocking, audio_data, sample_rate, device)
        finally:
            self._current_playback = None
            
    def _play_audio_blocking(self, audio_data, sample_rate: int, device=None) -> None:
        """Blocking audio playback (called from thread)"""
        if not self._sd:
            return
            
        try:
            # Play audio and wait for completion
            self._sd.play(audio_data, sample_rate, device=device)
            self._sd.wait()  # Wait for playback to complete
            
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            raise 