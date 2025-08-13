"""
Aplay Audio Provider - Linux ALSA audio playback

Converted from irene/plugins/builtin/aplay_audio_plugin.py to provider pattern.
Provides Linux ALSA audio playback using the aplay command-line tool.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, AsyncIterator
import uuid

from .base import AudioProvider

logger = logging.getLogger(__name__)


class AplayAudioProvider(AudioProvider):
    """
    Aplay audio provider for Linux ALSA playback.
    
    Features:
    - Linux ALSA audio system integration
    - Command-line aplay tool usage
    - Device selection support
    - Format flexibility
    - Centralized temp file management via asset manager
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize AplayAudioProvider with configuration.
        
        Args:
            config: Provider configuration including device and volume settings
        """
        super().__init__(config)
        
        # Asset management integration for temp files
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Configuration values
        self.device = config.get("device", "default")
        self._volume = config.get("volume", 1.0)
        self._available = False
        self._current_playback = None
        
        # Check if aplay is available (Linux only)
        import shutil
        self._available = shutil.which("aplay") is not None
        
        if not self._available:
            logger.warning("Aplay audio provider: aplay command not found (Linux ALSA required)")
        else:
            logger.debug("Aplay audio provider: aplay command available")
    
    async def is_available(self) -> bool:
        """Check if aplay command is available"""
        return self._available
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """Aplay works best with WAV files"""
        return ".wav"
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Aplay directory for temp audio files"""
        return "aplay"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Aplay doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Aplay uses temp and runtime cache"""
        return ["temp", "runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """Aplay doesn't use models"""
        return {}
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Aplay uses system binaries, no Python dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Platform-specific system packages for aplay"""
        return {
            "linux.ubuntu": ["alsa-utils"],
            "linux.alpine": ["alsa-utils"],
            "macos": [],  # Not supported
            "windows": []  # Not supported
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Aplay is primarily available on Linux systems"""
        return ["linux.ubuntu", "linux.alpine"]
    
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
            
            # Use asset manager for temp file instead of system temp
            temp_dir = self.asset_manager.get_cache_path("temp")
            temp_file = temp_dir / f"audio_stream_{uuid.uuid4().hex}.wav"
            
            # Ensure temp directory exists
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Write audio data to temp file
            with open(temp_file, 'wb') as f:
                f.write(audio_data)
            
            try:
                await self.play_file(temp_file, **kwargs)
            finally:
                if temp_file.exists():
                    temp_file.unlink()
                    
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