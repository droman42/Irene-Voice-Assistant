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
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ConversionMethod(Enum):
    """Audio conversion methods with different quality/performance trade-offs."""
    LINEAR = "linear"           # Fast linear interpolation
    POLYPHASE = "polyphase"     # Balanced polyphase filtering  
    SINC_KAISER = "sinc_kaiser" # High quality Kaiser windowed sinc
    ADAPTIVE = "adaptive"       # Dynamic based on rate ratio


@dataclass
class ResamplingResult:
    """Result of audio resampling operation."""
    success: bool
    original_rate: int
    target_rate: int
    method_used: ConversionMethod
    duration_ms: float = 0.0
    quality_loss: float = 0.0  # Estimated quality loss (0.0 = no loss, 1.0 = maximum loss)


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


def detect_sample_rate_from_audio_data(audio_data: 'AudioData') -> int:
    """
    Detect sample rate from AudioData object (Phase 2 enhancement).
    
    Args:
        audio_data: AudioData object to analyze
        
    Returns:
        Sample rate in Hz from AudioData metadata
    """
    return audio_data.sample_rate


def validate_cross_component_compatibility(
    microphone_config: Dict[str, Any],
    asr_config: Dict[str, Any], 
    voice_trigger_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate sample rate compatibility across microphone, ASR, and voice trigger components.
    
    Args:
        microphone_config: Microphone configuration dict
        asr_config: ASR component configuration dict
        voice_trigger_config: Voice trigger component configuration dict
        
    Returns:
        Validation result dict with compatibility status and recommendations
    """
    result = {
        'compatible': True,
        'warnings': [],
        'errors': [],
        'recommendations': []
    }
    
    # Extract sample rates
    mic_rate = microphone_config.get('sample_rate', 16000)
    asr_rate = asr_config.get('sample_rate', 16000)
    vt_rate = voice_trigger_config.get('sample_rate', 16000)
    
    # Check for mismatches
    rates = [mic_rate, asr_rate, vt_rate]
    unique_rates = set(rates)
    
    if len(unique_rates) > 1:
        result['warnings'].append(
            f"Sample rate mismatch detected - Mic: {mic_rate}Hz, ASR: {asr_rate}Hz, VT: {vt_rate}Hz"
        )
        
        # Check if resampling is enabled
        asr_resample = asr_config.get('allow_resampling', True)
        vt_resample = voice_trigger_config.get('allow_resampling', True)
        
        if not asr_resample and asr_rate != mic_rate:
            result['errors'].append(
                f"ASR requires {asr_rate}Hz but microphone provides {mic_rate}Hz with resampling disabled"
            )
            result['compatible'] = False
            
        if not vt_resample and vt_rate != mic_rate:
            result['errors'].append(
                f"Voice trigger requires {vt_rate}Hz but microphone provides {mic_rate}Hz with resampling disabled"
            )
            result['compatible'] = False
            
        # Add recommendations
        if result['compatible']:
            result['recommendations'].append(
                "Consider standardizing sample rates across components for optimal performance"
            )
            if asr_resample or vt_resample:
                result['recommendations'].append(
                    "Resampling is enabled and will handle rate differences automatically"
                )
    
    # Check channel compatibility
    mic_channels = microphone_config.get('channels', 1)
    asr_channels = asr_config.get('channels', 1)
    vt_channels = voice_trigger_config.get('channels', 1)
    
    if mic_channels != asr_channels:
        result['warnings'].append(
            f"Channel mismatch - Mic: {mic_channels} channels, ASR expects: {asr_channels} channels"
        )
        
    if mic_channels != vt_channels:
        result['warnings'].append(
            f"Channel mismatch - Mic: {mic_channels} channels, Voice trigger expects: {vt_channels} channels"
        )
    
    return result


def validate_startup_audio_configuration(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate audio configuration at startup for early error detection.
    
    Args:
        config: Complete system configuration dict
        
    Returns:
        Validation result with any fatal errors or warnings
    """
    result = {
        'valid': True,
        'fatal_errors': [],
        'warnings': [],
        'component_configs': {}
    }
    
    # Extract component configurations
    microphone_config = config.get('inputs', {}).get('microphone_config', {})
    asr_config = config.get('asr', {})
    voice_trigger_config = config.get('voice_trigger', {})
    
    # Store extracted configs for reference
    result['component_configs'] = {
        'microphone': microphone_config,
        'asr': asr_config,
        'voice_trigger': voice_trigger_config
    }
    
    # Validate individual component configs
    for component_name, component_config in result['component_configs'].items():
        sample_rate = component_config.get('sample_rate')
        if sample_rate and (sample_rate < 8000 or sample_rate > 192000):
            result['fatal_errors'].append(
                f"{component_name}: Invalid sample rate {sample_rate}Hz (must be 8000-192000Hz)"
            )
            result['valid'] = False
            
        channels = component_config.get('channels')
        if channels and (channels < 1 or channels > 8):
            result['fatal_errors'].append(
                f"{component_name}: Invalid channel count {channels} (must be 1-8)"
            )
            result['valid'] = False
    
    # Cross-component compatibility validation
    if result['valid']:
        compatibility = validate_cross_component_compatibility(
            microphone_config, asr_config, voice_trigger_config
        )
        
        if not compatibility['compatible']:
            result['fatal_errors'].extend(compatibility['errors'])
            result['valid'] = False
        
        result['warnings'].extend(compatibility['warnings'])
        result['warnings'].extend(compatibility['recommendations'])
    
    return result


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


class AudioProcessor:
    """
    Centralized resampling utilities that preserve AudioData metadata.
    
    This class provides AudioData-aware audio processing operations including
    resampling, validation, and conversion path optimization as specified in Phase 2.
    Enhanced with Phase 6 performance optimizations.
    """
    
    # Phase 6: Performance optimization - resampling cache
    _resampling_cache: Dict[tuple, bytes] = {}
    _cache_hits = 0
    _cache_misses = 0
    _max_cache_size = 100  # Maximum cached conversions
    
    # Phase 6: Buffer management for conversion operations  
    _conversion_buffers: Dict[int, bytes] = {}
    _buffer_pool_sizes = [1024, 2048, 4096, 8192, 16384, 32768]
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """Get resampling cache performance statistics."""
        total_requests = cls._cache_hits + cls._cache_misses
        hit_rate = cls._cache_hits / max(1, total_requests)
        return {
            'cache_hits': cls._cache_hits,
            'cache_misses': cls._cache_misses,
            'hit_rate': hit_rate,
            'cache_size': len(cls._resampling_cache),
            'max_cache_size': cls._max_cache_size
        }
    
    @classmethod
    def clear_cache(cls):
        """Clear resampling cache to free memory."""
        cls._resampling_cache.clear()
        cls._conversion_buffers.clear()
        cls._cache_hits = 0
        cls._cache_misses = 0
    
    @classmethod
    def _get_buffer(cls, size: int) -> bytes:
        """Get or create buffer for conversion operations."""
        # Find optimal buffer size
        optimal_size = min(size for size in cls._buffer_pool_sizes if size >= size) if any(size >= size for size in cls._buffer_pool_sizes) else max(cls._buffer_pool_sizes)
        
        if optimal_size not in cls._conversion_buffers:
            cls._conversion_buffers[optimal_size] = b'\x00' * optimal_size
        
        return cls._conversion_buffers[optimal_size][:size]
    
    @staticmethod
    async def resample_audio_data(
        audio_data: 'AudioData', 
        target_rate: int, 
        method: ConversionMethod = ConversionMethod.POLYPHASE
    ) -> 'AudioData':
        """
        Resample AudioData to target sample rate preserving metadata.
        
        Args:
            audio_data: Input AudioData object
            target_rate: Target sample rate in Hz
            method: Conversion method to use
            
        Returns:
            New AudioData object with resampled audio and updated metadata
        """
        from ..intents.models import AudioData
        import time
        import hashlib
        
        start_time = time.time()
        
        # If already at target rate, return copy with no changes
        if audio_data.sample_rate == target_rate:
            return AudioData(
                data=audio_data.data,
                timestamp=audio_data.timestamp,
                sample_rate=target_rate,
                channels=audio_data.channels,
                format=audio_data.format,
                metadata={
                    **audio_data.metadata,
                    'resampling_applied': False,
                    'original_sample_rate': audio_data.sample_rate
                }
            )
        
        # Phase 6: Check resampling cache for repeated conversions
        cache_key = (
            hashlib.md5(audio_data.data[:1024]).hexdigest(),  # Sample first 1KB for cache key
            audio_data.sample_rate,
            target_rate,
            audio_data.channels,
            method.value
        )
        
        if cache_key in AudioProcessor._resampling_cache:
            AudioProcessor._cache_hits += 1
            cached_data = AudioProcessor._resampling_cache[cache_key]
            
            duration_ms = (time.time() - start_time) * 1000
            
            return AudioData(
                data=cached_data,
                timestamp=audio_data.timestamp,
                sample_rate=target_rate,
                channels=audio_data.channels,
                format=audio_data.format,
                metadata={
                    **audio_data.metadata,
                    'resampling_applied': True,
                    'original_sample_rate': audio_data.sample_rate,
                    'resampling_method': method.value,
                    'resampling_duration_ms': duration_ms,
                    'cache_hit': True
                }
            )
        else:
            AudioProcessor._cache_misses += 1
        
        try:
            # Perform actual resampling
            resampled_data = await AudioProcessor._resample_bytes(
                audio_data.data, 
                audio_data.sample_rate, 
                target_rate, 
                audio_data.channels,
                method
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Phase 6: Cache the resampled result for future use (ASR optimization)
            if len(AudioProcessor._resampling_cache) < AudioProcessor._max_cache_size:
                AudioProcessor._resampling_cache[cache_key] = resampled_data
            elif len(AudioProcessor._resampling_cache) >= AudioProcessor._max_cache_size:
                # Remove oldest entry (simple FIFO eviction)
                oldest_key = next(iter(AudioProcessor._resampling_cache))
                del AudioProcessor._resampling_cache[oldest_key]
                AudioProcessor._resampling_cache[cache_key] = resampled_data
            
            # Create new AudioData with resampled data and preserved metadata
            return AudioData(
                data=resampled_data,
                timestamp=audio_data.timestamp,
                sample_rate=target_rate,
                channels=audio_data.channels,
                format=audio_data.format,
                metadata={
                    **audio_data.metadata,
                    'resampling_applied': True,
                    'original_sample_rate': audio_data.sample_rate,
                    'resampling_method': method.value,
                    'resampling_duration_ms': duration_ms,
                    'cache_hit': False
                }
            )
            
        except Exception as e:
            logger.error(f"Audio resampling failed: {e}")
            # Return original data on failure
            return audio_data
    
    @staticmethod
    def validate_sample_rate_compatibility(source_rate: int, target_rates: List[int]) -> bool:
        """
        Validate if source sample rate is compatible with any target rates.
        
        Args:
            source_rate: Source sample rate in Hz
            target_rates: List of acceptable target sample rates
            
        Returns:
            True if source rate matches any target rate or can be converted efficiently
        """
        if not target_rates:
            return True  # No restrictions
            
        # Direct match
        if source_rate in target_rates:
            return True
            
        # Check for efficient conversion ratios (integer multiples/divisions)
        for target_rate in target_rates:
            ratio = max(source_rate, target_rate) / min(source_rate, target_rate)
            # Allow ratios up to 4:1 as efficient
            if ratio <= 4.0 and (ratio.is_integer() or (1/ratio).is_integer()):
                return True
                
        return False
    
    @staticmethod
    def get_optimal_conversion_path(source_rate: int, target_rate: int, use_case: str = "general") -> ConversionMethod:
        """
        Determine optimal conversion method based on sample rate ratio and use case.
        
        Args:
            source_rate: Source sample rate in Hz
            target_rate: Target sample rate in Hz
            use_case: "voice_trigger" (latency-optimized), "asr" (quality-optimized), "general" (balanced)
            
        Returns:
            Recommended ConversionMethod for this rate conversion
        """
        if source_rate == target_rate:
            return ConversionMethod.LINEAR  # No conversion needed
            
        ratio = max(source_rate, target_rate) / min(source_rate, target_rate)
        
        # Phase 6: Enhanced quality-performance trade-offs based on use case
        if use_case == "voice_trigger":
            # Voice trigger: prioritize low latency over quality
            if ratio <= 2.0:
                return ConversionMethod.LINEAR  # Fastest for real-time processing
            else:
                return ConversionMethod.POLYPHASE  # Balanced for larger ratios
        elif use_case == "asr":
            # ASR: prioritize quality over latency  
            if ratio <= 1.5:
                return ConversionMethod.SINC_KAISER  # Highest quality for small changes
            elif ratio <= 3.0:
                return ConversionMethod.POLYPHASE  # Good balance for medium changes
            else:
                return ConversionMethod.ADAPTIVE  # Dynamic for large changes
        else:
            # General: balanced approach
            if ratio <= 1.5:
                return ConversionMethod.POLYPHASE  # Good quality for small changes
            elif ratio <= 3.0:
                return ConversionMethod.POLYPHASE  # Consistent balanced approach
            else:
                return ConversionMethod.ADAPTIVE  # Dynamic for large changes
    
    @staticmethod
    async def _resample_bytes(
        audio_bytes: bytes, 
        source_rate: int, 
        target_rate: int, 
        channels: int,
        method: ConversionMethod
    ) -> bytes:
        """
        Internal method to resample raw audio bytes.
        
        Args:
            audio_bytes: Input audio data as bytes
            source_rate: Source sample rate in Hz
            target_rate: Target sample rate in Hz
            channels: Number of audio channels
            method: Conversion method to use
            
        Returns:
            Resampled audio data as bytes
        """
        try:
            # Try librosa for high-quality resampling
            import librosa  # type: ignore
            import numpy as np  # type: ignore
            
            def _convert():
                # Convert bytes to numpy array (assuming 16-bit PCM)
                audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
                
                # Handle multi-channel audio
                if channels > 1:
                    audio_array = audio_array.reshape(-1, channels)
                    # Process each channel separately
                    resampled_channels = []
                    for channel in range(channels):
                        channel_data = audio_array[:, channel].astype(np.float32) / 32768.0
                        
                        if method == ConversionMethod.SINC_KAISER:
                            resampled = librosa.resample(channel_data, orig_sr=source_rate, target_sr=target_rate, res_type='kaiser_best')
                        elif method == ConversionMethod.POLYPHASE:
                            resampled = librosa.resample(channel_data, orig_sr=source_rate, target_sr=target_rate, res_type='kaiser_fast')
                        elif method == ConversionMethod.ADAPTIVE:
                            # Phase 6: Dynamic method selection based on rate ratio
                            ratio = max(source_rate, target_rate) / min(source_rate, target_rate)
                            if ratio <= 2.0:
                                resampled = librosa.resample(channel_data, orig_sr=source_rate, target_sr=target_rate, res_type='kaiser_fast')
                            elif ratio <= 4.0:
                                resampled = librosa.resample(channel_data, orig_sr=source_rate, target_sr=target_rate, res_type='fft')
                            else:
                                resampled = librosa.resample(channel_data, orig_sr=source_rate, target_sr=target_rate, res_type='soxr_hq')
                        else:  # LINEAR
                            resampled = librosa.resample(channel_data, orig_sr=source_rate, target_sr=target_rate, res_type='linear')
                        
                        resampled_channels.append(resampled)
                    
                    # Interleave channels back
                    resampled_audio = np.column_stack(resampled_channels).flatten()
                else:
                    # Single channel
                    audio_float = audio_array.astype(np.float32) / 32768.0
                    
                    if method == ConversionMethod.SINC_KAISER:
                        resampled_audio = librosa.resample(audio_float, orig_sr=source_rate, target_sr=target_rate, res_type='kaiser_best')
                    elif method == ConversionMethod.POLYPHASE:
                        resampled_audio = librosa.resample(audio_float, orig_sr=source_rate, target_sr=target_rate, res_type='kaiser_fast')
                    elif method == ConversionMethod.ADAPTIVE:
                        # Phase 6: Dynamic method selection based on rate ratio (single channel)
                        ratio = max(source_rate, target_rate) / min(source_rate, target_rate)
                        if ratio <= 2.0:
                            resampled_audio = librosa.resample(audio_float, orig_sr=source_rate, target_sr=target_rate, res_type='kaiser_fast')
                        elif ratio <= 4.0:
                            resampled_audio = librosa.resample(audio_float, orig_sr=source_rate, target_sr=target_rate, res_type='fft')
                        else:
                            resampled_audio = librosa.resample(audio_float, orig_sr=source_rate, target_sr=target_rate, res_type='soxr_hq')
                    else:  # LINEAR
                        resampled_audio = librosa.resample(audio_float, orig_sr=source_rate, target_sr=target_rate, res_type='linear')
                
                # Convert back to 16-bit PCM bytes
                resampled_int16 = (resampled_audio * 32767).astype(np.int16)
                return resampled_int16.tobytes()
            
            return await asyncio.to_thread(_convert)
            
        except ImportError:
            logger.debug("librosa not available, using basic resampling")
            # Fallback to basic resampling
            return await AudioProcessor._basic_resample_bytes(audio_bytes, source_rate, target_rate, channels)
            
    @staticmethod
    async def _basic_resample_bytes(
        audio_bytes: bytes, 
        source_rate: int, 
        target_rate: int, 
        channels: int
    ) -> bytes:
        """
        Basic resampling fallback using simple interpolation.
        
        Args:
            audio_bytes: Input audio data as bytes
            source_rate: Source sample rate in Hz
            target_rate: Target sample rate in Hz
            channels: Number of audio channels
            
        Returns:
            Resampled audio data as bytes
        """
        try:
            import numpy as np  # type: ignore
            
            def _basic_convert():
                # Convert bytes to numpy array (assuming 16-bit PCM)
                audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
                
                # Calculate conversion ratio
                ratio = target_rate / source_rate
                new_length = int(len(audio_array) * ratio)
                
                # Simple linear interpolation
                old_indices = np.linspace(0, len(audio_array) - 1, new_length)
                new_audio = np.interp(old_indices, np.arange(len(audio_array)), audio_array.astype(np.float32))
                
                # Convert back to int16
                return new_audio.astype(np.int16).tobytes()
            
            return await asyncio.to_thread(_basic_convert)
            
        except ImportError:
            logger.warning("numpy not available, cannot perform resampling")
            return audio_bytes  # Return original if no resampling possible


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
    async def convert_audio_data(
        audio_data: 'AudioData',
        target_rate: Optional[int] = None,
        target_channels: Optional[int] = None,
        target_format: Optional[str] = None,
        quality: str = "medium"
    ) -> 'AudioData':
        """
        Convert AudioData to different format/rate/channels (Phase 2 enhancement).
        
        Args:
            audio_data: Input AudioData object
            target_rate: Target sample rate in Hz (None = keep current)
            target_channels: Target channel count (None = keep current)
            target_format: Target format (None = keep current)
            quality: Conversion quality ("fast", "medium", "high", "best")
            
        Returns:
            New AudioData object with converted audio
        """
        from ..intents.models import AudioData
        
        # Start with a copy of input data
        result_data = audio_data.data
        result_rate = audio_data.sample_rate
        result_channels = audio_data.channels
        result_format = audio_data.format
        
        metadata_updates = {}
        
        # Convert sample rate if needed
        if target_rate and target_rate != audio_data.sample_rate:
            method = AudioFormatConverter._get_conversion_method_for_quality(quality)
            temp_audio = AudioData(
                data=result_data,
                timestamp=audio_data.timestamp,
                sample_rate=result_rate,
                channels=result_channels,
                format=result_format,
                metadata=audio_data.metadata
            )
            
            resampled_audio = await AudioProcessor.resample_audio_data(temp_audio, target_rate, method)
            result_data = resampled_audio.data
            result_rate = target_rate
            metadata_updates.update(resampled_audio.metadata)
        
        # Convert channels if needed (future enhancement placeholder)
        if target_channels and target_channels != result_channels:
            # TODO: Implement channel conversion (mono<->stereo)
            logger.warning(f"Channel conversion not yet implemented: {result_channels} -> {target_channels}")
        
        # Convert format if needed (future enhancement placeholder)
        if target_format and target_format != result_format:
            # TODO: Implement format conversion (pcm16, pcm24, float32, etc.)
            logger.warning(f"Format conversion not yet implemented: {result_format} -> {target_format}")
        
        return AudioData(
            data=result_data,
            timestamp=audio_data.timestamp,
            sample_rate=result_rate,
            channels=result_channels,
            format=result_format,
            metadata={
                **audio_data.metadata,
                **metadata_updates,
                'conversion_applied': True,
                'conversion_quality': quality
            }
        )
    
    @staticmethod
    def _get_conversion_method_for_quality(quality: str) -> ConversionMethod:
        """Map quality string to ConversionMethod."""
        quality_map = {
            "fast": ConversionMethod.LINEAR,
            "medium": ConversionMethod.POLYPHASE,
            "high": ConversionMethod.SINC_KAISER,
            "best": ConversionMethod.SINC_KAISER,
            "adaptive": ConversionMethod.ADAPTIVE
        }
        return quality_map.get(quality, ConversionMethod.POLYPHASE)
    
    @staticmethod
    async def convert_audio_data_streaming(
        audio_stream: List['AudioData'],
        target_rate: int,
        chunk_size: int = 4096,
        quality: str = "medium",
        parallel_processing: bool = True
    ) -> List['AudioData']:
        """
        Convert audio stream with memory-efficient chunk-based processing.
        Enhanced with Phase 6 streaming optimizations.
        
        Args:
            audio_stream: List of AudioData chunks
            target_rate: Target sample rate in Hz
            chunk_size: Processing chunk size in samples
            quality: Conversion quality level
            parallel_processing: Enable parallel chunk processing
            
        Returns:
            List of converted AudioData chunks
        """
        if not audio_stream:
            return []
        
        # Phase 6: Streaming optimization - parallel processing for chunks
        if parallel_processing and len(audio_stream) > 1:
            import asyncio
            
            async def convert_chunk_with_index(index: int, chunk: 'AudioData') -> tuple:
                try:
                    converted = await AudioFormatConverter.convert_audio_data(
                        chunk, 
                        target_rate=target_rate, 
                        quality=quality
                    )
                    return (index, converted)
                except Exception as e:
                    logger.error(f"Failed to convert audio chunk {index}: {e}")
                    return (index, chunk)  # Return original on failure
            
            # Process chunks in parallel while preserving order
            tasks = [convert_chunk_with_index(i, chunk) for i, chunk in enumerate(audio_stream)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Sort by index to maintain order
            converted_chunks = [None] * len(audio_stream)
            for result in results:
                if isinstance(result, tuple):
                    index, chunk = result
                    converted_chunks[index] = chunk
                else:
                    logger.error(f"Chunk conversion error: {result}")
            
            # Filter out None values and return
            return [chunk for chunk in converted_chunks if chunk is not None]
        else:
            # Sequential processing fallback
            converted_chunks = []
            
            for i, audio_chunk in enumerate(audio_stream):
                try:
                    converted_chunk = await AudioFormatConverter.convert_audio_data(
                        audio_chunk, 
                        target_rate=target_rate, 
                        quality=quality
                    )
                    converted_chunks.append(converted_chunk)
                except Exception as e:
                    logger.error(f"Failed to convert audio chunk {i}: {e}")
                    # Keep original chunk on conversion failure
                    converted_chunks.append(audio_chunk)
            
            return converted_chunks
    
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


# Voice Activity Detection utility functions

def calculate_audio_energy(audio_data: 'AudioData') -> float:
    """
    Calculate RMS energy like ESP32 VAD.
    
    This function provides RMS energy calculation for voice activity detection
    that's compatible with the ESP32 firmware VAD implementation.
    
    Args:
        audio_data: AudioData object containing audio frame
        
    Returns:
        Normalized RMS energy (0.0-1.0)
    """
    try:
        import numpy as np  # type: ignore
        
        # Convert bytes to numpy array (assuming 16-bit PCM)
        audio_array = np.frombuffer(audio_data.data, dtype=np.int16)
        
        if len(audio_array) == 0:
            return 0.0
        
        # Calculate RMS energy (same method as ESP32)
        sum_squares = np.sum(audio_array.astype(np.float64) ** 2)
        rms = np.sqrt(sum_squares / len(audio_array))
        
        # Normalize to 0.0-1.0 range
        normalized_energy = rms / 32768.0
        
        return min(1.0, normalized_energy)
        
    except ImportError:
        logger.warning("numpy not available for energy calculation")
        return 0.0
    except Exception as e:
        logger.warning(f"Error calculating audio energy: {e}")
        return 0.0


def calculate_zero_crossing_rate(audio_data: 'AudioData') -> float:
    """
    Calculate ZCR for speech detection.
    
    Zero Crossing Rate is useful for distinguishing between voiced/unvoiced speech
    and can improve VAD accuracy when combined with energy analysis.
    
    Args:
        audio_data: AudioData object containing audio frame
        
    Returns:
        Zero crossing rate as ratio (0.0-1.0)
    """
    try:
        import numpy as np  # type: ignore
        
        # Convert bytes to numpy array (assuming 16-bit PCM)
        audio_array = np.frombuffer(audio_data.data, dtype=np.int16)
        
        if len(audio_array) <= 1:
            return 0.0
        
        # Calculate zero crossings
        zero_crossings = np.sum(np.diff(np.sign(audio_array)) != 0)
        
        # Normalize by frame length
        zcr = zero_crossings / (len(audio_array) - 1)
        
        return zcr
        
    except ImportError:
        logger.warning("numpy not available for ZCR calculation")
        return 0.0
    except Exception as e:
        logger.warning(f"Error calculating ZCR: {e}")
        return 0.0


def detect_voice_activity_simple(audio_data: 'AudioData', threshold: float = 0.01) -> bool:
    """
    Simple voice activity detection for quick integration.
    
    Energy-based voice activity detection without state management.
    This is a lightweight wrapper around the main VAD functionality.
    
    Args:
        audio_data: AudioData object containing audio frame
        threshold: RMS energy threshold for voice detection (0.0-1.0)
        
    Returns:
        True if voice activity detected, False otherwise
    """
    energy = calculate_audio_energy(audio_data)
    return energy > threshold


def validate_vad_configuration(vad_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate VAD configuration parameters.
    
    Args:
        vad_config: VAD configuration dictionary
        
    Returns:
        Validation result with any errors or warnings
    """
    result = {
        'valid': True,
        'warnings': [],
        'errors': [],
        'normalized_config': {}
    }
    
    # Validate threshold
    threshold = vad_config.get('threshold', 0.01)
    if not 0.0 <= threshold <= 1.0:
        result['errors'].append(f"VAD threshold {threshold} must be between 0.0 and 1.0")
        result['valid'] = False
    else:
        result['normalized_config']['threshold'] = threshold
    
    # Validate sensitivity
    sensitivity = vad_config.get('sensitivity', 0.5)
    if not 0.1 <= sensitivity <= 2.0:
        result['errors'].append(f"VAD sensitivity {sensitivity} must be between 0.1 and 2.0")
        result['valid'] = False
    else:
        result['normalized_config']['sensitivity'] = sensitivity
    
    # Validate frame requirements
    voice_frames = vad_config.get('voice_frames_required', 2)
    if not isinstance(voice_frames, int) or voice_frames < 1:
        result['errors'].append(f"voice_frames_required {voice_frames} must be a positive integer")
        result['valid'] = False
    else:
        result['normalized_config']['voice_frames_required'] = voice_frames
    
    silence_frames = vad_config.get('silence_frames_required', 5)
    if not isinstance(silence_frames, int) or silence_frames < 1:
        result['errors'].append(f"silence_frames_required {silence_frames} must be a positive integer")
        result['valid'] = False
    else:
        result['normalized_config']['silence_frames_required'] = silence_frames
    
    # Validate optional features
    max_segment_duration = vad_config.get('max_segment_duration_s', 10)
    if not isinstance(max_segment_duration, (int, float)) or max_segment_duration <= 0:
        result['warnings'].append(f"max_segment_duration_s {max_segment_duration} should be a positive number")
        result['normalized_config']['max_segment_duration_s'] = 10
    else:
        result['normalized_config']['max_segment_duration_s'] = max_segment_duration
    
    # Check for conflicting settings
    if voice_frames > silence_frames:
        result['warnings'].append(
            f"voice_frames_required ({voice_frames}) > silence_frames_required ({silence_frames}) "
            "may cause detection instability"
        )
    
    return result


def estimate_optimal_vad_threshold(audio_samples: list['AudioData'], 
                                 noise_percentile: int = 15,
                                 voice_multiplier: float = 3.0) -> float:
    """
    Estimate optimal VAD threshold from audio samples.
    
    Analyzes a collection of audio samples to determine appropriate
    VAD threshold based on background noise characteristics.
    
    Args:
        audio_samples: List of AudioData samples (should include silence periods)
        noise_percentile: Percentile to use for noise floor estimation
        voice_multiplier: Multiplier above noise floor for voice threshold
        
    Returns:
        Suggested VAD threshold value
    """
    if not audio_samples:
        logger.warning("No audio samples provided for threshold estimation")
        return 0.01  # Default threshold
    
    try:
        # Calculate energy for all samples
        energies = [calculate_audio_energy(sample) for sample in audio_samples]
        
        # Remove zero energies
        energies = [e for e in energies if e > 0]
        
        if not energies:
            logger.warning("All audio samples have zero energy")
            return 0.01
        
        # Calculate noise floor (low percentile)
        sorted_energies = sorted(energies)
        noise_index = (len(sorted_energies) * noise_percentile) // 100
        noise_floor = sorted_energies[noise_index]
        
        # Calculate suggested threshold
        suggested_threshold = noise_floor * voice_multiplier
        
        # Clamp to reasonable range
        suggested_threshold = max(0.001, min(0.1, suggested_threshold))
        
        logger.info(f"VAD threshold estimation: noise_floor={noise_floor:.4f}, "
                   f"suggested_threshold={suggested_threshold:.4f}")
        
        return suggested_threshold
        
    except Exception as e:
        logger.warning(f"Error estimating VAD threshold: {e}")
        return 0.01


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
    # Phase 2 New Exports - Audio Infrastructure Enhancement
    'ConversionMethod',
    'ResamplingResult', 
    'AudioProcessor',
    'detect_sample_rate_from_audio_data',
    'validate_cross_component_compatibility',
    'validate_startup_audio_configuration',
    
    # Phase 1 VAD Exports - Voice Activity Detection
    'calculate_audio_energy',
    'calculate_zero_crossing_rate',
    'detect_voice_activity_simple',
    'validate_vad_configuration',
    'estimate_optimal_vad_threshold',
    
    # Existing Exports
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