"""
SimpleAudio Audio Provider - Lightweight audio playback

Converted from irene/plugins/builtin/simpleaudio_audio_plugin.py to provider pattern.
Provides lightweight audio playback using simpleaudio library.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, AsyncIterator
import uuid

from .base import AudioProvider

logger = logging.getLogger(__name__)


class SimpleAudioProvider(AudioProvider):
    """
    SimpleAudio audio provider for lightweight audio playback.
    
    Features:
    - Lightweight audio playback using simpleaudio
    - WAV file support only
    - Minimal dependencies
    - Fast and reliable operation
    - Centralized temp file management via asset manager
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize SimpleAudioProvider with configuration.
        
        Args:
            config: Provider configuration including volume settings
        """
        super().__init__(config)
        
        # Asset management integration for temp files
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Configuration values
        self._volume = config.get("volume", 1.0)
        self._available = False
        self._sa = None
        
        # Try to import simpleaudio
        try:
            import simpleaudio as sa  # type: ignore
            self._sa = sa
            self._available = True
            logger.debug("SimpleAudio audio provider: dependencies available")
        except ImportError as e:
            self._available = False
            logger.warning(f"SimpleAudio audio provider: dependencies missing - {e}")
    
    async def is_available(self) -> bool:
        """Check if SimpleAudio dependencies are available"""
        return self._available
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """SimpleAudio works best with WAV files"""
        return ".wav"
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """SimpleAudio directory for temp audio files"""
        return "simpleaudio"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """SimpleAudio doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """SimpleAudio uses temp and runtime cache"""
        return ["temp", "runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """SimpleAudio doesn't use models"""
        return {}
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """SimpleAudio requires simpleaudio library (when available)"""
        return ["simpleaudio>=1.0.4"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """SimpleAudio is cross-platform, no system dependencies"""
        return {
            "linux.ubuntu": ["libasound2"],
            "linux.alpine": ["alsa-lib"],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """SimpleAudio supports all major platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """Play an audio file using simpleaudio."""
        if not self._available or not self._sa:
            raise RuntimeError("SimpleAudio audio backend not available")
            
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
            
        # SimpleAudio only supports WAV files
        if file_path.suffix.lower() != '.wav':
            raise ValueError(f"SimpleAudio only supports WAV files, got: {file_path.suffix}")
            
        try:
            volume = kwargs.get('volume', self._volume)
            
            # Play audio asynchronously
            await asyncio.to_thread(self._play_audio_blocking, str(file_path), volume)
            
        except Exception as e:
            logger.error(f"Failed to play audio file {file_path}: {e}")
            raise RuntimeError(f"Audio playback failed: {e}")
    
    async def play_stream(self, audio_stream: AsyncIterator[bytes], **kwargs) -> None:
        """Play audio from a byte stream."""
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
        # SimpleAudio only supports WAV
        return ['wav']
    
    async def set_volume(self, volume: float) -> None:
        """Set playback volume"""
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
        self._volume = volume
    
    async def stop_playback(self) -> None:
        """Stop current audio playback"""
        # SimpleAudio doesn't support stopping, track for future enhancement
        self._current_playback = None
    
    def get_provider_name(self) -> str:
        """Get unique provider identifier"""
        return "simpleaudio"
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities information"""
        return {
            "formats": self.get_supported_formats(),
            "features": [
                "simple",
                "lightweight",
                "cross_platform",
                "wav_only"
            ] if self._available else ["unavailable"],
            "concurrent_playback": False,
            "devices": False,
            "quality": "basic",
            "speed": "fast"
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
            
        logger.debug(f"SimpleAudio audio provider configuration updated: {config}")
    
    def _play_audio_blocking(self, file_path: str, volume: float) -> None:
        """Blocking audio playback (called from thread)"""
        if not self._sa:
            return
            
        try:
            self._current_playback = file_path
            
            # Load and play WAV file
            wave_obj = self._sa.WaveObject.from_wave_file(file_path)  # type: ignore
            
            # Apply volume if needed (would require manual audio data manipulation)
            # For simplicity, just play at original volume
            play_obj = wave_obj.play()
            play_obj.wait_done()  # Block until playback completes
            
        except Exception as e:
            logger.error(f"SimpleAudio playback error: {e}")
            raise
        finally:
            self._current_playback = None 