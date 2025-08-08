"""
SoundDevice Audio Provider - High-quality audio playback

Converted from irene/plugins/builtin/sounddevice_audio_plugin.py to provider pattern.
Provides high-quality audio playback using sounddevice and soundfile libraries.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, AsyncIterator, Union
import uuid

from .base import AudioProvider

logger = logging.getLogger(__name__)


class SoundDeviceAudioProvider(AudioProvider):
    """
    SoundDevice audio provider for high-quality audio playback.
    
    Features:
    - High-quality audio playback using sounddevice
    - Support for multiple audio formats via soundfile
    - Device selection and configuration
    - Async operation with proper resource management
    - Graceful handling of missing dependencies
    - Centralized temp file management via asset manager
    
    Enhanced in TODO #4 Phase 1 with intelligent asset defaults.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize SoundDeviceAudioProvider with configuration.
        
        Args:
            config: Provider configuration including device_id, sample_rate, etc.
        """
        super().__init__(config)
        
        # Asset management integration for temp files
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Configuration values
        self.device_id = config.get("device_id", -1)  # -1 means default device
        self.sample_rate = config.get("sample_rate", 44100)
        self.channels = config.get("channels", 2)
        self.buffer_size = config.get("buffer_size", 1024)
        
        # Runtime state
        self._current_playback = None
        self._volume = 1.0
        self._output_device = self.device_id
        self._available = False
        
        # Try to import dependencies
        try:
            import sounddevice as sd  # type: ignore
            import soundfile as sf   # type: ignore
            import numpy as np       # type: ignore
            
            self._sd = sd
            self._sf = sf
            self._np = np
            self._available = True
            logger.debug("SoundDevice audio provider: dependencies available")
            
        except ImportError as e:
            self._sd = None
            self._sf = None
            self._np = None
            self._available = False
            logger.warning(f"SoundDevice audio provider: dependencies missing - {e}")
        
        # Initialize default device if available
        if self._available and self._sd:
            try:
                # Get default output device
                default_device = self._sd.default.device[1]  # type: ignore  # Output device
                self._output_device = default_device
                logger.debug(f"Using default audio output device: {default_device}")
            except Exception as e:
                logger.warning(f"Failed to get default audio device: {e}")
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """SoundDevice typically works with WAV files"""
        return ".wav"
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """SoundDevice uses temp cache for audio file processing"""
        return "sounddevice"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """SoundDevice is a local library, no credentials needed"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Uses temp cache for temporary audio file processing"""
        return ["temp", "runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """SoundDevice doesn't require model downloads"""
        return {}
    
    async def is_available(self) -> bool:
        """Check if SoundDevice dependencies are available"""
        return self._available
    
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
    
    async def play_stream(self, audio_stream: AsyncIterator[bytes], **kwargs) -> None:
        """
        Play audio from a byte stream.
        
        Args:
            audio_stream: Async iterator of audio data chunks
            **kwargs: volume (float), device (str/int), format (str)
        """
        if not self._available or not self._sd:
            raise RuntimeError("SoundDevice audio backend not available")
            
        # For now, collect all stream data and play as file
        # Future enhancement: implement real streaming
        try:
            audio_data = b''
            async for chunk in audio_stream:
                audio_data += chunk
            
            # Use asset manager for temp file instead of system temp
            temp_dir = self.asset_manager.get_cache_path("temp")
            temp_file = temp_dir / f"audio_stream_{uuid.uuid4().hex}.wav"
            
            # Ensure temp directory exists
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Write audio data to temp file
            with open(temp_file, 'wb') as f:
                f.write(audio_data)
            
            try:
                # Play the temporary file
                await self.play_file(temp_file, **kwargs)
            finally:
                # Clean up temporary file
                if temp_file.exists():
                    temp_file.unlink()
                    
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
                "default": 1.0
            },
            "device": {
                "type": ["string", "integer"],
                "description": "Audio output device ID",
                "default": -1
            },
            "sample_rate": {
                "type": "integer",
                "description": "Audio sample rate",
                "options": [8000, 22050, 44100, 48000, 96000],
                "default": 44100
            }
        }
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats"""
        if not self._available:
            return []
        
        # SoundFile supports many formats
        return ['wav', 'flac', 'ogg', 'aiff', 'au', 'raw', 'paf', 'svx', 'nist', 'voc', 'w64', 'mat4', 'mat5', 'pvf', 'xi', 'htk', 'sds', 'avr', 'wavex', 'sd2', 'caf', 'wve']
    
    async def set_volume(self, volume: float) -> None:
        """Set playback volume"""
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
        self._volume = volume
        logger.debug(f"Audio volume set to: {volume}")
    
    async def stop_playback(self) -> None:
        """Stop current audio playback"""
        if self._sd and self._current_playback:
            try:
                self._sd.stop()  # type: ignore
                self._current_playback = None
                logger.debug("Audio playback stopped")
            except Exception as e:
                logger.warning(f"Error stopping playback: {e}")
    
    def get_provider_name(self) -> str:
        """Get unique provider identifier"""
        return "sounddevice"
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities information"""
        return {
            "formats": self.get_supported_formats(),
            "features": [
                "high_quality",
                "device_selection",
                "volume_control",
                "multi_format"
            ] if self._available else ["unavailable"],
            "concurrent_playback": False,
            "devices": True,
            "quality": "high",
            "speed": "fast"
        }
    
    async def pause_playback(self) -> None:
        """Pause current audio playback (not supported by sounddevice)"""
        logger.warning("Pause not supported by sounddevice backend")
        
    async def resume_playback(self) -> None:
        """Resume paused audio playback (not supported by sounddevice)"""
        logger.warning("Resume not supported by sounddevice backend")
    
    def get_playback_devices(self) -> List[Dict[str, Any]]:
        """Get list of available audio output devices"""
        if not self._available or not self._sd:
            return []
        
        try:
            devices = []
            device_list = self._sd.query_devices()  # type: ignore
            
            for i, device in enumerate(device_list):
                if device['max_output_channels'] > 0:  # Output device
                    devices.append({
                        'id': i,
                        'name': device['name'],
                        'channels': device['max_output_channels'],
                        'sample_rate': device['default_samplerate'],
                        'default': i == self._sd.default.device[1]  # type: ignore
                    })
            
            return devices
            
        except Exception as e:
            logger.error(f"Failed to query audio devices: {e}")
            return []
    
    async def set_output_device(self, device_id: Union[str, int]) -> None:
        """Set the audio output device"""
        if not self._available or not self._sd:
            raise RuntimeError("SoundDevice audio backend not available")
            
        try:
            # Convert string ID to int if needed
            if isinstance(device_id, str) and device_id.isdigit():
                device_id = int(device_id)
                
            # Validate device exists
            devices = self._sd.query_devices()  # type: ignore
            if isinstance(device_id, int) and (device_id < 0 or device_id >= len(devices)):
                raise ValueError(f"Device ID {device_id} out of range")
                
            self._output_device = device_id
            logger.info(f"Audio output device set to: {device_id}")
            
        except Exception as e:
            logger.error(f"Failed to set output device: {e}")
            raise ValueError(f"Invalid device ID: {device_id}")
    
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
                    
            if "device" in kwargs:
                device = kwargs["device"]
                if not isinstance(device, (int, str)):
                    return False
                if isinstance(device, str) and not device.isdigit():
                    return False
                    
            if "sample_rate" in kwargs:
                sample_rate = kwargs["sample_rate"]
                if not isinstance(sample_rate, int) or sample_rate <= 0:
                    return False
                    
            return True
        except (ValueError, TypeError):
            return False
    
    async def configure(self, config: Dict[str, Any]) -> None:
        """Update provider configuration at runtime"""
        self.config.update(config)
        
        # Update settings
        if "device_id" in config:
            await self.set_output_device(config["device_id"])
            
        if "sample_rate" in config:
            self.sample_rate = config["sample_rate"]
            
        if "channels" in config:
            self.channels = config["channels"]
            
        if "buffer_size" in config:
            self.buffer_size = config["buffer_size"]
            
        logger.debug(f"SoundDevice audio provider configuration updated: {config}")
    
    # Helper methods
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
            self._sd.play(audio_data, sample_rate, device=device)  # type: ignore
            self._sd.wait()  # type: ignore  # Wait for playback to complete
            
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            raise 