"""
Aplay Audio Provider - Linux ALSA audio playback

Converted from irene/plugins/builtin/aplay_audio_plugin.py to provider pattern.
Provides audio playback on Linux systems using the ALSA aplay command.
"""

import asyncio
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, AsyncIterator

from .base import AudioProvider

logger = logging.getLogger(__name__)


class AplayAudioProvider(AudioProvider):
    """
    Aplay audio provider for Linux audio playback.
    
    Features:
    - Uses ALSA aplay command for audio playback
    - Works on most Linux distributions
    - No Python audio library dependencies
    - Async subprocess execution
    - Device selection support
    - Graceful handling when aplay unavailable
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize AplayAudioProvider with configuration."""
        super().__init__(config)
        
        # Configuration values
        self.device = config.get("device", "default")
        self.volume = config.get("volume", 1.0)
        
        # Runtime state
        self._current_playback = None
        self._volume = self.volume
        self._available = False
        
        # Check if aplay is available
        self._available = shutil.which("aplay") is not None
        if self._available:
            logger.debug("Aplay audio provider: aplay command available")
        else:
            logger.warning("Aplay audio provider: aplay command not found")
    
    async def is_available(self) -> bool:
        """Check if aplay command is available"""
        return self._available
    
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """Play an audio file using aplay command."""
        if not self._available:
            raise RuntimeError("Aplay audio backend not available")
            
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
            
        try:
            device = kwargs.get('device', self.device)
            volume = kwargs.get('volume', self._volume)
            
            # Build aplay command
            cmd = ["aplay", "-D", device, str(file_path)]
            
            # Execute aplay asynchronously
            self._current_playback = str(file_path)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip() if stderr else f"aplay failed with code {process.returncode}"
                raise RuntimeError(f"Aplay failed: {error_msg}")
                
        except Exception as e:
            logger.error(f"Failed to play audio file {file_path}: {e}")
            raise RuntimeError(f"Audio playback failed: {e}")
        finally:
            self._current_playback = None
    
    async def play_stream(self, audio_stream: AsyncIterator[bytes], **kwargs) -> None:
        """Play audio from a byte stream using aplay."""
        try:
            # Collect stream data and save to temporary file
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
            "device": {
                "type": "string",
                "description": "ALSA device name",
                "default": "default"
            },
            "volume": {
                "type": "number",
                "description": "Playback volume",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 1.0
            }
        }
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats"""
        if not self._available:
            return []
        # aplay supports various formats, WAV is most common
        return ['wav', 'au', 'raw']
    
    async def set_volume(self, volume: float) -> None:
        """Set playback volume"""
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
        self._volume = volume
    
    async def stop_playback(self) -> None:
        """Stop current audio playback"""
        # For aplay, we'd need to track the process and terminate it
        self._current_playback = None
    
    def get_provider_name(self) -> str:
        """Get unique provider identifier"""
        return "aplay"
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities information"""
        return {
            "formats": self.get_supported_formats(),
            "features": [
                "linux_native",
                "alsa",
                "device_selection",
                "no_dependencies"
            ] if self._available else ["unavailable"],
            "concurrent_playback": False,
            "devices": True,
            "quality": "system",
            "speed": "fast"
        }
    
    def get_playback_devices(self) -> List[Dict[str, Any]]:
        """Get list of available ALSA devices"""
        if not self._available:
            return []
        
        # Basic device list - could be enhanced to query actual ALSA devices
        return [
            {'id': 'default', 'name': 'Default ALSA Device', 'default': True},
            {'id': 'hw:0,0', 'name': 'Hardware Device 0,0', 'default': False},
            {'id': 'hw:1,0', 'name': 'Hardware Device 1,0', 'default': False}
        ]
    
    async def set_output_device(self, device_id: str) -> None:
        """Set the ALSA output device"""
        self.device = device_id
        logger.info(f"ALSA output device set to: {device_id}")
    
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
                if not isinstance(device, str):
                    return False
                    
            return True
        except (ValueError, TypeError):
            return False
    
    async def configure(self, config: Dict[str, Any]) -> None:
        """Update provider configuration at runtime"""
        self.config.update(config)
        
        if "device" in config:
            self.device = config["device"]
            
        if "volume" in config:
            self.volume = config["volume"]
            self._volume = self.volume
            
        logger.debug(f"Aplay audio provider configuration updated: {config}") 