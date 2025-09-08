"""
Audio Processing Helpers

Common audio processing utilities for Irene Voice Assistant.
These utilities provide shared functionality for audio plugins:
- Volume control and normalization
- Audio format validation
- Sample rate conversion helpers
- Device enumeration utilities
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Union, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


def validate_audio_file(file_path: Union[str, Path]) -> bool:
    """
    Validate if a file is a supported audio file.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        True if file exists and has a supported audio extension
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
        
    if not file_path.exists():
        logger.warning(f"Audio file does not exist: {file_path}")
        return False
        
    supported_extensions = {'.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aac'}
    if file_path.suffix.lower() not in supported_extensions:
        logger.warning(f"Unsupported audio format: {file_path.suffix}")
        return False
        
    return True


def normalize_volume(volume: Optional[Union[int, float]]) -> float:
    """
    Normalize volume to a 0.0-1.0 range.
    
    Args:
        volume: Volume value (can be None, 0-100 int, or 0.0-1.0 float)
        
    Returns:
        Normalized volume as float between 0.0 and 1.0
    """
    if volume is None:
        return 1.0
        
    if isinstance(volume, int):
        # Assume 0-100 scale for integers
        return max(0.0, min(100.0, float(volume))) / 100.0
    else:
        # Assume 0.0-1.0 scale for floats
        return max(0.0, min(1.0, float(volume)))


def format_audio_duration(seconds: float) -> str:
    """
    Format audio duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string (e.g., "1:23", "2:45:30")
    """
    if seconds < 0:
        return "0:00"
        
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def detect_sample_rate(file_path: Union[str, Path]) -> Optional[int]:
    """
    Detect the sample rate of an audio file.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Sample rate in Hz, or None if detection failed
    """
    try:
        # Try soundfile first (most comprehensive)
        try:
            import soundfile as sf  # type: ignore
            with sf.SoundFile(str(file_path)) as f:
                return f.samplerate
        except ImportError:
            pass
        
        # Try wave module for WAV files
        if str(file_path).lower().endswith('.wav'):
            import wave
            with wave.open(str(file_path), 'rb') as f:
                return f.getframerate()
                
        # Default fallback
        logger.debug(f"Could not detect sample rate for {file_path}, using default")
        return 44100
        
    except Exception as e:
        logger.warning(f"Error detecting sample rate for {file_path}: {e}")
        return None


async def get_audio_devices() -> List[Dict[str, Any]]:
    """
    Get list of available audio devices asynchronously.
    
    Returns:
        List of device dictionaries with 'id', 'name', 'channels', etc.
    """
    devices = []
    
    try:
        # Try sounddevice for comprehensive device info
        import sounddevice as sd  # type: ignore
        device_list = await asyncio.to_thread(sd.query_devices)
        
        for i, device in enumerate(device_list):
            devices.append({
                'id': i,
                'name': device['name'],
                'channels': device['max_output_channels'],
                'sample_rate': device['default_samplerate'],
                'hostapi': device['hostapi'],
                'available': device['max_output_channels'] > 0
            })
            
    except ImportError:
        logger.debug("sounddevice not available for device enumeration")
        # Provide basic default device info
        devices.append({
            'id': 0,
            'name': 'Default Audio Device',
            'channels': 2,
            'sample_rate': 44100,
            'hostapi': 0,
            'available': True
        })
    except Exception as e:
        logger.warning(f"Error querying audio devices: {e}")
        
    return devices


async def get_default_audio_device() -> Optional[Dict[str, Any]]:
    """
    Get the default audio output device.
    
    Returns:
        Default device dictionary or None if detection failed
    """
    try:
        devices = await get_audio_devices()
        if devices:
            # Return the first available device as default
            for device in devices:
                if device.get('available', False):
                    return device
            # If no available devices, return the first one anyway
            return devices[0]
    except Exception as e:
        logger.warning(f"Error getting default audio device: {e}")
        
    return None


async def get_audio_input_devices() -> List[Dict[str, Any]]:
    """
    Get list of available audio input devices asynchronously.
    
    Returns:
        List of input device dictionaries with 'id', 'name', 'input_channels', etc.
    """
    devices = []
    
    try:
        # Try sounddevice for comprehensive device info
        import sounddevice as sd  # type: ignore
        device_list = await asyncio.to_thread(sd.query_devices)
        
        for i, device in enumerate(device_list):
            input_channels = device.get('max_input_channels', 0)
            if input_channels > 0:  # Only include devices with input capability
                devices.append({
                    'id': i,
                    'name': device['name'],
                    'input_channels': input_channels,
                    'output_channels': device.get('max_output_channels', 0),
                    'sample_rate': device['default_samplerate'],
                    'hostapi': device['hostapi'],
                    'available': True
                })
                
    except ImportError:
        logger.debug("sounddevice not available for input device enumeration")
        # Provide basic default input device info
        devices.append({
            'id': 0,
            'name': 'Default Audio Input Device',
            'input_channels': 1,
            'output_channels': 0,
            'sample_rate': 16000,
            'hostapi': 0,
            'available': True
        })
    except Exception as e:
        logger.warning(f"Error getting audio input devices: {e}")
        
    return devices


async def get_default_audio_input_device() -> Optional[Dict[str, Any]]:
    """
    Get the default audio input device suitable for microphone input.
    
    Returns:
        Default input device dictionary or None if detection failed
    """
    try:
        input_devices = await get_audio_input_devices()
        if input_devices:
            # Return the first available input device
            return input_devices[0]
    except Exception as e:
        logger.warning(f"Error getting default audio input device: {e}")
        
    return None


async def validate_audio_input_device(device_id: int) -> Optional[Dict[str, Any]]:
    """
    Validate that a specific device ID exists and supports audio input.
    
    Args:
        device_id: The device ID to validate
        
    Returns:
        Device dictionary if valid, None if invalid
    """
    try:
        import sounddevice as sd  # type: ignore
        device_list = await asyncio.to_thread(sd.query_devices)
        
        if 0 <= device_id < len(device_list):
            device = device_list[device_id]
            input_channels = device.get('max_input_channels', 0)
            
            if input_channels > 0:
                return {
                    'id': device_id,
                    'name': device['name'],
                    'input_channels': input_channels,
                    'output_channels': device.get('max_output_channels', 0),
                    'sample_rate': device['default_samplerate'],
                    'hostapi': device['hostapi'],
                    'available': True
                }
            else:
                logger.warning(f"Device {device_id} ({device['name']}) has no input channels")
                return None
        else:
            logger.warning(f"Device ID {device_id} is out of range (0-{len(device_list)-1})")
            return None
            
    except ImportError:
        logger.warning("sounddevice not available for device validation")
        return None
    except Exception as e:
        logger.warning(f"Error validating audio input device {device_id}: {e}")
        return None


def calculate_audio_buffer_size(sample_rate: int, duration_ms: float = 100.0) -> int:
    """
    Calculate optimal audio buffer size for given sample rate and duration.
    
    Args:
        sample_rate: Sample rate in Hz
        duration_ms: Buffer duration in milliseconds
        
    Returns:
        Buffer size in samples
    """
    buffer_size = int(sample_rate * duration_ms / 1000.0)
    
    # Round to nearest power of 2 for optimal performance
    power_of_2 = 1
    while power_of_2 < buffer_size:
        power_of_2 *= 2
    
    # Use the smaller power of 2 if it's closer
    if (buffer_size - power_of_2 // 2) < (power_of_2 - buffer_size):
        return power_of_2 // 2
    else:
        return power_of_2


class AudioFormatConverter:
    """
    Helper class for audio format conversions.
    
    This class provides utilities for converting between different
    audio formats and sample rates when needed.
    """
    
    @staticmethod
    def supports_format(format_name: str) -> bool:
        """Check if a format is supported by available libraries."""
        format_name = format_name.lower().lstrip('.')
        
        # Common formats supported by most libraries
        basic_formats = {'wav', 'mp3', 'ogg', 'flac'}
        if format_name in basic_formats:
            return True
            
        # Check for extended format support
        try:
            import soundfile as sf  # type: ignore
            return format_name in [fmt.lower() for fmt in sf.available_formats().keys()]
        except ImportError:
            return False
    
    @staticmethod 
    async def convert_sample_rate_async(
        input_path: Union[str, Path],
        output_path: Union[str, Path], 
        target_rate: int
    ) -> bool:
        """
        Convert audio file to different sample rate asynchronously.
        
        Args:
            input_path: Source audio file
            output_path: Destination audio file  
            target_rate: Target sample rate in Hz
            
        Returns:
            True if conversion successful, False otherwise
        """
        try:
            # Use librosa for high-quality resampling if available
            try:
                import librosa  # type: ignore
                import soundfile as sf  # type: ignore
                
                def _convert():
                    y, sr = librosa.load(str(input_path), sr=None)
                    y_resampled = librosa.resample(y, orig_sr=sr, target_sr=target_rate)
                    sf.write(str(output_path), y_resampled, target_rate)
                    
                await asyncio.to_thread(_convert)
                return True
                
            except ImportError:
                logger.debug("librosa not available, using basic conversion")
                # Basic conversion using soundfile only
                import soundfile as sf  # type: ignore
                
                def _basic_convert():
                    data, sr = sf.read(str(input_path))
                    # Simple decimation/interpolation (not high quality)
                    if sr != target_rate:
                        ratio = target_rate / sr
                        if ratio > 1:
                            # Upsample by repeating samples
                            import numpy as np  # type: ignore
                            new_length = int(len(data) * ratio)
                            data = np.interp(np.linspace(0, len(data), new_length), 
                                           np.arange(len(data)), data)
                        else:
                            # Downsample by taking every nth sample
                            step = int(1 / ratio)
                            data = data[::step]
                    sf.write(str(output_path), data, target_rate)
                    
                await asyncio.to_thread(_basic_convert)
                return True
                
        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            return False


# Utility functions for common audio operations

def get_audio_info(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Get comprehensive information about an audio file.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Dictionary with audio file information
    """
    info = {
        'exists': False,
        'format': None,
        'duration': None,
        'sample_rate': None,
        'channels': None,
        'size_bytes': None
    }
    
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            return info
            
        info['exists'] = True
        info['format'] = file_path.suffix.lower().lstrip('.')
        info['size_bytes'] = file_path.stat().st_size
        
        # Try to get detailed audio info
        try:
            import soundfile as sf  # type: ignore
            with sf.SoundFile(str(file_path)) as f:
                info['duration'] = len(f) / f.samplerate
                info['sample_rate'] = f.samplerate
                info['channels'] = f.channels
        except ImportError:
            # Basic info for WAV files using wave module
            if info['format'] == 'wav':
                import wave
                with wave.open(str(file_path), 'rb') as f:
                    frames = f.getnframes()
                    rate = f.getframerate()
                    info['sample_rate'] = rate
                    info['duration'] = frames / rate
                    info['channels'] = f.getnchannels()
                    
    except Exception as e:
        logger.warning(f"Error getting audio info for {file_path}: {e}")
        
    return info


async def test_audio_playback_capability() -> Dict[str, Any]:
    """
    Test system audio playback capabilities.
    
    Returns:
        Dictionary with capability test results
    """
    capabilities = {
        'devices_available': False,
        'default_device': None,
        'supported_formats': [],
        'libraries_available': {}
    }
    
    # Test device availability
    try:
        devices = await get_audio_devices()
        capabilities['devices_available'] = len(devices) > 0
        capabilities['default_device'] = await get_default_audio_device()
    except Exception as e:
        logger.debug(f"Device detection failed: {e}")
    
    # Test library availability
    libraries = ['sounddevice', 'audioplayer', 'simpleaudio', 'pygame']
    for lib in libraries:
        try:
            __import__(lib)
            capabilities['libraries_available'][lib] = True
        except ImportError:
            capabilities['libraries_available'][lib] = False
    
    # Test format support
    test_formats = ['wav', 'mp3', 'ogg', 'flac']
    for fmt in test_formats:
        if AudioFormatConverter.supports_format(fmt):
            capabilities['supported_formats'].append(fmt)
    
    return capabilities


# Export commonly used functions
__all__ = [
    'validate_audio_file',
    'normalize_volume',
    'format_audio_duration',
    'detect_sample_rate',
    'get_audio_devices',
    'get_default_audio_device', 
    'get_audio_input_devices',
    'get_default_audio_input_device',
    'validate_audio_input_device',
    'calculate_audio_buffer_size',
    'AudioFormatConverter',
    'get_audio_info',
    'test_audio_playback_capability'
] 