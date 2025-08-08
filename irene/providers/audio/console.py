"""
Console Audio Provider - Debug audio output

Converted from irene/plugins/builtin/console_audio_plugin.py to provider pattern.
Provides audio playback by printing file information to console for debugging purposes.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, AsyncIterator

from .base import AudioProvider

logger = logging.getLogger(__name__)


class ConsoleAudioProvider(AudioProvider):
    """
    Console audio provider for debugging purposes.
    
    Features:
    - Prints audio file information instead of playing
    - Colored output (if termcolor available)
    - No external dependencies required
    - Simulates playback timing
    - Useful for testing and debugging
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ConsoleAudioProvider with configuration.
        
        Args:
            config: Provider configuration including color_output, timing_simulation
        """
        super().__init__(config)
        
        # Configuration values
        self.color_output = config.get("color_output", True)
        self.timing_simulation = config.get("timing_simulation", True)
        self.prefix = config.get("prefix", "[CONSOLE AUDIO] ")
        self.simulate_delay = config.get("simulate_delay", 1.0)  # seconds per file
        
        # Runtime state
        self._current_playback = None
        self._volume = 1.0
        self._output_device = "console"
        
        # Try to import termcolor for colored output
        try:
            import termcolor  # type: ignore
            self._termcolor_available = True
            self._colored_print = termcolor.cprint
            logger.debug("Console audio provider: termcolor available")
        except ImportError:
            self._termcolor_available = False
            self._colored_print = None
            logger.debug("Console audio provider: termcolor not available, using plain text")
    
    async def is_available(self) -> bool:
        """Console audio is always available"""
        return True
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """Console audio doesn't use real files"""
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Console audio directory for logging"""
        return "console"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Console audio doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Console audio uses runtime cache for logging"""
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """Console audio doesn't use models"""
        return {}
    
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """
        'Play' an audio file by printing information to console.
        
        Args:
            file_path: Path to the audio file
            **kwargs: volume (float), device (str), simulate_timing (bool)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
            
        try:
            volume = kwargs.get('volume', self._volume)
            device = kwargs.get('device', self._output_device)
            simulate_timing = kwargs.get('simulate_timing', self.timing_simulation)
            
            # Get file information
            file_size = file_path.stat().st_size
            file_ext = file_path.suffix.lower()
            
            # Create playback info
            playback_info = {
                'file': file_path.name,
                'path': str(file_path),
                'size': f"{file_size:,} bytes",
                'format': file_ext or 'unknown',
                'volume': f"{volume:.2f}",
                'device': device
            }
            
            # Print playback information
            await self._print_playback_info(playback_info)
            
            # Simulate playback duration if enabled
            if simulate_timing:
                await self._simulate_playback_duration(file_path, file_size)
                
        except Exception as e:
            logger.error(f"Failed to process audio file {file_path}: {e}")
            raise RuntimeError(f"Console audio processing failed: {e}")
    
    async def play_stream(self, audio_stream: AsyncIterator[bytes], **kwargs) -> None:
        """
        'Play' audio from a byte stream by printing information.
        
        Args:
            audio_stream: Async iterator of audio data chunks
            **kwargs: volume, device, simulate_timing
        """
        try:
            volume = kwargs.get('volume', self._volume)
            device = kwargs.get('device', self._output_device)
            simulate_timing = kwargs.get('simulate_timing', self.timing_simulation)
            
            # Collect stream data to get size
            audio_data = b''
            async for chunk in audio_stream:
                audio_data += chunk
            
            # Create stream info
            stream_info = {
                'type': 'audio stream',
                'size': f"{len(audio_data):,} bytes",
                'format': 'stream',
                'volume': f"{volume:.2f}",
                'device': device
            }
            
            # Print stream information
            await self._print_playback_info(stream_info)
            
            # Simulate playback duration if enabled
            if simulate_timing:
                # Estimate duration based on data size (rough approximation)
                estimated_duration = len(audio_data) / 44100 / 2 / 2  # 44.1kHz, 2 channels, 2 bytes per sample
                await self._simulate_duration(estimated_duration)
                
        except Exception as e:
            logger.error(f"Failed to process audio stream: {e}")
            raise RuntimeError(f"Console audio stream processing failed: {e}")
    
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
                "type": "string",
                "description": "Console output mode",
                "options": ["console", "console_color", "console_silent"],
                "default": "console"
            },
            "simulate_timing": {
                "type": "boolean",
                "description": "Simulate playback timing",
                "default": True
            }
        }
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats (all formats for console)"""
        return ['wav', 'mp3', 'ogg', 'flac', 'aiff', 'au', 'raw', 'm4a', 'wma', 'any']
    
    async def set_volume(self, volume: float) -> None:
        """Set playback volume"""
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
        self._volume = volume
        await self._print_message(f"🔊 Volume set to {volume:.2f}", "blue")
    
    async def stop_playback(self) -> None:
        """Stop current audio 'playback'"""
        if self._current_playback:
            self._current_playback = None
            await self._print_message("🛑 Audio playback stopped", "yellow")
    
    def get_provider_name(self) -> str:
        """Get unique provider identifier"""
        return "console"
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities information"""
        return {
            "formats": self.get_supported_formats(),
            "features": [
                "debug_output",
                "colored_text" if self._termcolor_available else "plain_text",
                "timing_simulation",
                "all_formats",
                "no_dependencies"
            ],
            "concurrent_playback": False,
            "devices": True,
            "quality": "debug",
            "speed": "instant"
        }
    
    async def pause_playback(self) -> None:
        """Pause current audio 'playback'"""
        await self._print_message("⏸️  Audio playback paused", "yellow")
        
    async def resume_playback(self) -> None:
        """Resume paused audio 'playback'"""
        await self._print_message("▶️  Audio playback resumed", "green")
    
    def get_playback_devices(self) -> List[Dict[str, Any]]:
        """Get list of available audio output devices"""
        return [
            {'id': 'console', 'name': 'Console Debug Output', 'default': True},
            {'id': 'console_color', 'name': 'Console Debug Output (Colored)', 'default': False},
            {'id': 'console_silent', 'name': 'Console Silent Mode', 'default': False}
        ]
        
    async def set_output_device(self, device_id: str) -> None:
        """Set the audio output device"""
        valid_devices = ['console', 'console_color', 'console_silent']
        if device_id not in valid_devices:
            raise ValueError(f"Invalid device ID: {device_id}. Valid options: {valid_devices}")
        self._output_device = device_id
        await self._print_message(f"🔧 Output device set to: {device_id}", "blue")
    
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
                valid_devices = ['console', 'console_color', 'console_silent']
                if device not in valid_devices:
                    return False
                    
            if "simulate_timing" in kwargs:
                if not isinstance(kwargs["simulate_timing"], bool):
                    return False
                    
            return True
        except (ValueError, TypeError):
            return False
    
    async def configure(self, config: Dict[str, Any]) -> None:
        """Update provider configuration at runtime"""
        self.config.update(config)
        
        # Update settings
        if "color_output" in config:
            self.color_output = config["color_output"]
            
        if "timing_simulation" in config:
            self.timing_simulation = config["timing_simulation"]
            
        if "prefix" in config:
            self.prefix = config["prefix"]
            
        if "simulate_delay" in config:
            self.simulate_delay = config["simulate_delay"]
            
        logger.debug(f"Console audio provider configuration updated: {config}")
    
    # Helper methods
    async def _print_playback_info(self, info: Dict[str, Any]) -> None:
        """Print formatted playback information"""
        if self._output_device == 'console_silent':
            return
            
        use_color = (self._termcolor_available and 
                    self._output_device == 'console_color' and 
                    self._colored_print)
        
        lines = [
            "┌─ Console Audio Playback ─────────────────┐",
            f"│ File: {info.get('file', info.get('type', 'Unknown')):35} │",
            f"│ Size: {info['size']:35} │",
            f"│ Format: {info['format']:33} │",
            f"│ Volume: {info['volume']:33} │",
            f"│ Device: {info['device']:33} │",
            "└──────────────────────────────────────────┘"
        ]
        
        for line in lines:
            if use_color and self._colored_print:
                self._colored_print(line, "cyan")
            else:
                print(line)
                
        # Small delay to simulate processing
        await asyncio.sleep(0.01)
        
    async def _print_message(self, message: str, color: str = "white") -> None:
        """Print a message with optional color"""
        if self._output_device == 'console_silent':
            return
            
        use_color = (self._termcolor_available and 
                    self._output_device == 'console_color' and 
                    self._colored_print)
        
        if use_color and self._colored_print:
            self._colored_print(f"{self.prefix}{message}", color)
        else:
            print(f"{self.prefix}{message}")
            
    async def _simulate_playback_duration(self, file_path: Path, file_size: int) -> None:
        """Simulate playback duration based on file characteristics"""
        # Rough estimation based on file size and format
        file_ext = file_path.suffix.lower()
        
        # Estimate duration (very rough approximation)
        if file_ext == '.wav':
            # Uncompressed: ~44.1kHz * 2 channels * 2 bytes = ~176KB per second
            estimated_duration = file_size / 176000
        elif file_ext in ['.mp3', '.ogg']:
            # Compressed: ~128kbps average = ~16KB per second
            estimated_duration = file_size / 16000
        else:
            # Default estimation
            estimated_duration = file_size / 100000
            
        # Cap duration for practical reasons
        estimated_duration = min(estimated_duration, 10.0)  # Max 10 seconds simulation
        estimated_duration = max(estimated_duration, 0.1)   # Min 0.1 seconds
        
        await self._simulate_duration(estimated_duration)
        
    async def _simulate_duration(self, duration: float) -> None:
        """Simulate playback for specified duration"""
        self._current_playback = "simulating"
        
        await self._print_message(f"⏳ Simulating playback for {duration:.1f} seconds...", "green")
        
        try:
            await asyncio.sleep(duration)
            await self._print_message("✅ Playback simulation completed", "green")
        except asyncio.CancelledError:
            await self._print_message("❌ Playback simulation cancelled", "red")
            raise
        finally:
            self._current_playback = None 