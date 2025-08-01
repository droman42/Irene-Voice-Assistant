"""
Console Audio Plugin - Debug audio output

Replaces legacy plugin_playwav_consolewav.py with modern async architecture.
Provides debug audio output by printing file information to console.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from ...core.interfaces.audio import AudioPlugin

logger = logging.getLogger(__name__)


class ConsoleAudioPlugin(AudioPlugin):
    """
    Console audio plugin for debugging audio playback.
    
    Features:
    - Prints audio file information instead of playing
    - Colored output (if termcolor available)
    - No external dependencies required
    - Simulates playback timing
    - Useful for testing and debugging
    """
    
    @property
    def name(self) -> str:
        return "console_audio"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Debug audio output to console (no actual playback)"
        
    @property
    def optional_dependencies(self) -> List[str]:
        return []  # No dependencies required
        
    def __init__(self):
        super().__init__()
        self._available = True  # Always available
        self._current_playback = None
        self._volume = 1.0
        self._output_device = "console"
        self._simulate_timing = True
        
        # Try to import termcolor for colored output
        try:
            import termcolor  # type: ignore
            self._termcolor_available = True
            self._colored_print = termcolor.cprint
        except ImportError:
            self._termcolor_available = False
            self._colored_print = None
            
        logger.info("Console audio backend available (debug mode)")
            
    def is_available(self) -> bool:
        """Check if console backend is available (always True)"""
        return self._available
        
    async def initialize(self, core) -> None:
        """Initialize the audio plugin"""
        await super().initialize(core)
        logger.info("Console audio plugin initialized successfully")
            
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
            simulate_timing = kwargs.get('simulate_timing', self._simulate_timing)
            
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
            
    async def play_stream(self, audio_data: bytes, format: str = "wav", **kwargs) -> None:
        """
        'Play' audio from a byte stream by printing information.
        
        Args:
            audio_data: Raw audio data
            format: Audio format
            **kwargs: Additional parameters
        """
        try:
            volume = kwargs.get('volume', self._volume)
            device = kwargs.get('device', self._output_device)
            simulate_timing = kwargs.get('simulate_timing', self._simulate_timing)
            
            # Create stream info
            stream_info = {
                'type': 'audio stream',
                'size': f"{len(audio_data):,} bytes",
                'format': format,
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
            
    async def stop_playback(self) -> None:
        """Stop current audio 'playback'"""
        if self._current_playback:
            self._current_playback = None
            await self._print_message("🛑 Audio playback stopped", "yellow")
                
    async def pause_playback(self) -> None:
        """Pause current audio 'playback'"""
        await self._print_message("⏸️  Audio playback paused", "yellow")
        
    async def resume_playback(self) -> None:
        """Resume paused audio 'playback'"""
        await self._print_message("▶️  Audio playback resumed", "green")
        
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats (all formats for console)"""
        return ['wav', 'mp3', 'ogg', 'flac', 'aiff', 'au', 'raw', 'm4a', 'wma', 'any']
        
    def get_playback_devices(self) -> List[Dict[str, Any]]:
        """Get list of available audio output devices"""
        return [
            {'id': 'console', 'name': 'Console Debug Output', 'default': True},
            {'id': 'console_color', 'name': 'Console Debug Output (Colored)', 'default': False},
            {'id': 'console_silent', 'name': 'Console Silent Mode', 'default': False}
        ]
        
    async def set_output_device(self, device_id: Union[str, int]) -> None:
        """Set the audio output device"""
        valid_devices = ['console', 'console_color', 'console_silent']
        device_str = str(device_id)
        
        if device_str not in valid_devices:
            logger.warning(f"Unknown console device: {device_id}, using 'console'")
            device_str = 'console'
            
        self._output_device = device_str
        await self._print_message(f"📻 Console audio device set to: {device_str}", "blue")
        
    async def set_volume(self, volume: float) -> None:
        """Set playback volume (0.0 to 1.0)"""
        if volume < 0.0 or volume > 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
            
        self._volume = volume
        await self._print_message(f"🔊 Console audio volume set to: {volume:.2f}", "blue")
        
    async def set_timing_simulation(self, enabled: bool) -> None:
        """Enable or disable playback timing simulation"""
        self._simulate_timing = enabled
        status = "enabled" if enabled else "disabled"
        await self._print_message(f"⏱️  Timing simulation {status}", "blue")
        
    async def _print_playback_info(self, info: Dict[str, Any]) -> None:
        """Print playback information to console"""
        if self._output_device == 'console_silent':
            return
            
        # Create formatted output
        header = "🎵 CONSOLE AUDIO PLAYBACK 🎵"
        separator = "=" * len(header)
        
        lines = [
            separator,
            header,
            separator
        ]
        
        for key, value in info.items():
            lines.append(f"  {key.capitalize()}: {value}")
            
        lines.append(separator)
        
        # Print with color if available and enabled
        use_color = (self._termcolor_available and 
                    self._output_device == 'console_color' and 
                    self._colored_print)
        
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
            self._colored_print(f"[CONSOLE AUDIO] {message}", color)
        else:
            print(f"[CONSOLE AUDIO] {message}")
            
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