"""
Aplay Audio Plugin - Linux audio playback via aplay command

Replaces legacy plugin_playwav_aplay.py with modern async architecture.
Provides audio playback on Linux systems using the ALSA aplay command.
"""

import asyncio
import logging
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from ...core.interfaces.audio import AudioPlugin

logger = logging.getLogger(__name__)


class AplayAudioPlugin(AudioPlugin):
    """
    Aplay audio plugin for Linux audio playback.
    
    Features:
    - Uses ALSA aplay command for audio playback
    - Works on most Linux distributions
    - No Python audio library dependencies
    - Async subprocess execution
    - Device selection support
    - Graceful handling when aplay unavailable
    """
    
    @property
    def name(self) -> str:
        return "aplay_audio"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Linux audio playback using ALSA aplay command"
        
    @property
    def optional_dependencies(self) -> List[str]:
        return []  # No Python dependencies, just system aplay command
        
    def __init__(self):
        super().__init__()
        self._available = False
        self._current_process = None
        self._output_device = None
        self._volume = 1.0
        
        # Check if aplay command is available
        try:
            aplay_path = shutil.which('aplay')
            if aplay_path:
                self._aplay_path = aplay_path
                self._available = True
                logger.info(f"Aplay audio backend available at: {aplay_path}")
            else:
                logger.warning("aplay command not found in PATH")
                self._aplay_path = None
                
        except Exception as e:
            logger.warning(f"Failed to check for aplay command: {e}")
            self._aplay_path = None
            
    def is_available(self) -> bool:
        """Check if aplay backend is available"""
        return self._available
        
    async def initialize(self, core) -> None:
        """Initialize the audio plugin"""
        await super().initialize(core)
        
        if not self._available:
            logger.warning("Aplay audio plugin initialized but aplay command not available")
            logger.info("Install ALSA utilities: sudo apt install alsa-utils (Ubuntu/Debian)")
            return
            
        # Try to get available devices
        try:
            await self._discover_devices()
        except Exception as e:
            logger.warning(f"Failed to discover audio devices: {e}")
            
        logger.info("Aplay audio plugin initialized successfully")
        
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """
        Play an audio file using aplay command.
        
        Args:
            file_path: Path to the audio file
            **kwargs: device (str), volume (float - ignored by aplay)
        """
        if not self._available or not self._aplay_path:
            raise RuntimeError("Aplay audio backend not available")
            
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
            
        try:
            device = kwargs.get('device', self._output_device)
            
            # Build aplay command
            cmd = [self._aplay_path]
            
            # Add device selection if specified
            if device:
                cmd.extend(['-D', str(device)])
                
            # Add file path
            cmd.append(str(file_path))
            
            logger.debug(f"Playing audio with command: {' '.join(cmd)}")
            
            # Execute aplay asynchronously
            await self._run_aplay_async(cmd)
            
        except Exception as e:
            logger.error(f"Failed to play audio file {file_path}: {e}")
            raise RuntimeError(f"Audio playback failed: {e}")
            
    async def play_stream(self, audio_data: bytes, format: str = "wav", **kwargs) -> None:
        """
        Play audio from a byte stream using aplay.
        
        Args:
            audio_data: Raw audio data
            format: Audio format (wav, raw, etc.)
            **kwargs: device (str), sample_rate (int), channels (int), format_spec (str)
        """
        if not self._available or not self._aplay_path:
            raise RuntimeError("Aplay audio backend not available")
            
        try:
            device = kwargs.get('device', self._output_device)
            sample_rate = kwargs.get('sample_rate', 44100)
            channels = kwargs.get('channels', 2)
            format_spec = kwargs.get('format_spec', 'S16_LE')
            
            # Build aplay command for stdin input
            cmd = [self._aplay_path]
            
            # Add device selection if specified
            if device:
                cmd.extend(['-D', str(device)])
                
            # Add format specifications for raw audio
            if format.lower() == 'raw':
                cmd.extend(['-f', format_spec])
                cmd.extend(['-r', str(sample_rate)])
                cmd.extend(['-c', str(channels)])
            elif format.lower() == 'wav':
                # WAV files have format info in header
                pass
            else:
                raise ValueError(f"Unsupported format for stream playback: {format}")
                
            # Read from stdin
            cmd.append('-')
            
            logger.debug(f"Playing audio stream with command: {' '.join(cmd)}")
            
            # Execute aplay with audio data as input
            await self._run_aplay_with_input(cmd, audio_data)
            
        except Exception as e:
            logger.error(f"Failed to play audio stream: {e}")
            raise RuntimeError(f"Stream playback failed: {e}")
            
    async def stop_playback(self) -> None:
        """Stop current audio playback"""
        if self._current_process and not self._current_process.returncode:
            try:
                self._current_process.terminate()
                try:
                    await asyncio.wait_for(self._current_process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self._current_process.kill()
                    await self._current_process.wait()
                    
                self._current_process = None
                logger.debug("Audio playback stopped")
            except Exception as e:
                logger.warning(f"Error stopping playback: {e}")
                
    async def pause_playback(self) -> None:
        """Pause current audio playback (not supported by aplay)"""
        logger.warning("Pause not supported by aplay backend")
        
    async def resume_playback(self) -> None:
        """Resume paused audio playback (not supported by aplay)"""
        logger.warning("Resume not supported by aplay backend")
        
    def get_supported_formats(self) -> List[str]:
        """Get list of supported audio formats"""
        if not self._available:
            return []
            
        # aplay supports these common formats
        return ['wav', 'raw', 'au', 'aiff']
        
    def get_playback_devices(self) -> List[Dict[str, Any]]:
        """Get list of available audio output devices"""
        if not self._available:
            return []
            
        # Return cached devices from initialization
        return getattr(self, '_devices', [])
        
    async def set_output_device(self, device_id: Union[str, int]) -> None:
        """Set the audio output device"""
        if not self._available:
            raise RuntimeError("Aplay audio backend not available")
            
        # Validate device exists
        devices = self.get_playback_devices()
        device_names = [d['id'] for d in devices]
        
        if str(device_id) not in device_names and device_id != 'default':
            logger.warning(f"Device {device_id} not found in available devices: {device_names}")
            
        self._output_device = str(device_id)
        logger.info(f"Audio output device set to: {device_id}")
        
    async def set_volume(self, volume: float) -> None:
        """Set playback volume (not directly supported by aplay)"""
        if volume < 0.0 or volume > 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")
            
        self._volume = volume
        logger.warning("Volume control not directly supported by aplay backend")
        logger.info("Use amixer or alsamixer to control system volume")
        
    async def _run_aplay_async(self, cmd: List[str]) -> None:
        """Run aplay command asynchronously"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self._current_process = process
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                raise RuntimeError(f"aplay failed with code {process.returncode}: {error_msg}")
                
        except Exception as e:
            logger.error(f"aplay execution error: {e}")
            raise
        finally:
            self._current_process = None
            
    async def _run_aplay_with_input(self, cmd: List[str], audio_data: bytes) -> None:
        """Run aplay command with audio data as input"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self._current_process = process
            
            stdout, stderr = await process.communicate(input=audio_data)
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                raise RuntimeError(f"aplay failed with code {process.returncode}: {error_msg}")
                
        except Exception as e:
            logger.error(f"aplay stream execution error: {e}")
            raise
        finally:
            self._current_process = None
            
    async def _discover_devices(self) -> None:
        """Discover available ALSA audio devices"""
        devices = [{'id': 'default', 'name': 'Default ALSA Device', 'default': True}]
        
        if not self._aplay_path:
            self._devices = devices
            return
        
        try:
            # Try to get device list using aplay -l
            process = await asyncio.create_subprocess_exec(
                self._aplay_path, '-l',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output = stdout.decode('utf-8', errors='ignore')
                # Parse aplay -l output to extract device information
                for line in output.split('\n'):
                    if line.startswith('card '):
                        # Extract card and device info
                        # Format: card 0: PCH [HDA Intel PCH], device 0: ALC269VC Analog [ALC269VC Analog]
                        try:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                card_info = parts[0].strip()
                                device_info = parts[1].strip()
                                
                                # Extract card number
                                card_num = card_info.split()[1]
                                device_id = f"hw:{card_num},0"
                                
                                devices.append({
                                    'id': device_id,
                                    'name': device_info.split(',')[0].strip(),
                                    'default': False
                                })
                        except Exception as e:
                            logger.debug(f"Failed to parse device line: {line}, error: {e}")
                            
        except Exception as e:
            logger.warning(f"Failed to discover ALSA devices: {e}")
            
        self._devices = devices
        logger.debug(f"Discovered {len(devices)} audio devices") 