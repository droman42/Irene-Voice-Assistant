"""
Audio Device Detection Utility

Provides reusable functions for detecting and listing available audio devices
with their capabilities. Extracted from microphone input for use across
the system including configuration UI.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def is_audio_available() -> bool:
    """Check if audio device detection is available"""
    try:
        import sounddevice as sd  # type: ignore
        return True
    except ImportError:
        return False


def list_audio_input_devices() -> List[Dict[str, Any]]:
    """
    List available audio input devices with their capabilities
    
    Returns:
        List of dictionaries containing device information:
        - id: Device ID for selection
        - name: Human-readable device name
        - channels: Maximum input channels
        - sample_rate: Default sample rate
        - is_default: Whether this is the system default device
    """
    if not is_audio_available():
        logger.warning("Audio device detection not available - sounddevice package missing")
        return []
        
    try:
        import sounddevice as sd  # type: ignore
        devices = sd.query_devices()
        input_devices = []
        
        # Get default input device
        try:
            default_device_id = sd.default.device[0]
        except Exception:
            default_device_id = None
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': int(device['max_input_channels']),
                    'sample_rate': int(device['default_samplerate']),
                    'is_default': i == default_device_id
                })
        
        logger.debug(f"Found {len(input_devices)} audio input devices")
        return input_devices
        
    except Exception as e:
        logger.error(f"Error listing audio devices: {e}")
        return []


def list_audio_output_devices() -> List[Dict[str, Any]]:
    """
    List available audio output devices with their capabilities
    
    Returns:
        List of dictionaries containing device information:
        - id: Device ID for selection
        - name: Human-readable device name
        - channels: Maximum output channels
        - sample_rate: Default sample rate
        - is_default: Whether this is the system default device
    """
    if not is_audio_available():
        logger.warning("Audio device detection not available - sounddevice package missing")
        return []
        
    try:
        import sounddevice as sd  # type: ignore
        devices = sd.query_devices()
        output_devices = []
        
        # Get default output device
        try:
            default_device_id = sd.default.device[1]  # Output is index 1
        except Exception:
            default_device_id = None
        
        for i, device in enumerate(devices):
            if device['max_output_channels'] > 0:
                output_devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': int(device['max_output_channels']),
                    'sample_rate': int(device['default_samplerate']),
                    'is_default': i == default_device_id
                })
        
        logger.debug(f"Found {len(output_devices)} audio output devices")
        return output_devices
        
    except Exception as e:
        logger.error(f"Error listing audio output devices: {e}")
        return []


def get_device_info(device_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific audio device
    
    Args:
        device_id: Device ID (None for default device)
        
    Returns:
        Device information dictionary or None if not found
    """
    devices = list_audio_input_devices()
    
    if device_id is None:
        # Find default device
        for device in devices:
            if device['is_default']:
                return device
        return devices[0] if devices else None
    
    # Find specific device
    for device in devices:
        if device['id'] == device_id:
            return device
            
    return None


def print_audio_devices() -> None:
    """Print available audio devices to console (for CLI tools)"""
    devices = list_audio_input_devices()
    
    if not devices:
        print("❌ No audio input devices found")
        return
    
    print("🎤 Available Audio Input Devices:")
    print("=" * 50)
    
    for device in devices:
        default_marker = " (default)" if device['is_default'] else ""
        print(f"{device['id']:2d}: {device['name']}{default_marker}")
        print(f"    Channels: {device['channels']}, Sample Rate: {device['sample_rate']} Hz")
