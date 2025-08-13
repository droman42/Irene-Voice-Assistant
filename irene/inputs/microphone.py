"""
Microphone Input Source - Pure audio capture

REFACTORED: Pure audio capture input source that provides only audio data.
Follows the fundamental component pattern for clean separation of concerns.

Responsibilities:
- Audio capture only - no business logic
- Yields AudioData objects for pipeline processing  
- Uses audio_helpers.py for audio device management
"""

import asyncio
import logging
import queue
import time
from typing import AsyncIterator, Dict, Any, Optional, List
from pathlib import Path

from .base import InputSource, ComponentNotAvailable, InputData
from ..intents.models import AudioData
from ..utils.audio_helpers import get_default_audio_device, AudioFormatConverter
from ..utils.loader import safe_import

logger = logging.getLogger(__name__)


class MicrophoneInput(InputSource):
    """
    Pure microphone input - only audio capture (enhanced with audio_helpers.py)
    
    Responsibilities:
    - Audio capture only - no business logic
    - Yields AudioData objects for pipeline processing
    - Uses existing audio infrastructure for device management
    """
    
    def __init__(self, device_id: Optional[int] = None, samplerate: int = 16000, blocksize: int = 8000):
        """Initialize microphone input using existing audio infrastructure
        
        Args:
            device_id: Audio device ID (None for default)
            samplerate: Audio sample rate in Hz  
            blocksize: Audio block size for processing
        """
        self.device_id = device_id
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.device = None  # Will be set during initialization
        self._listening = False
        self._audio_queue = None
        self._audio_stream = None
        self._task = None
        
        # Check for audio dependencies only (no VOSK required)
        try:
            import sounddevice as sd  # type: ignore
            self._sd_available = True
        except ImportError as e:
            logger.warning(f"Audio input dependencies not available: {e}")
            self._sd_available = False
    
    async def initialize(self):
        """Initialize using existing audio infrastructure"""
        # Device selection using audio_helpers.py
        self.device = await get_default_audio_device()
        if not self.device:
            logger.warning("No specific audio input device found, using default")
            
        # Format validation using audio_helpers.py  
        if not AudioFormatConverter.supports_format('wav'):
            logger.warning("WAV format not supported, audio quality may be reduced")
        
        logger.info(f"Initialized microphone input with device: {self.device}")
        
    def is_available(self) -> bool:
        """Check if audio capture is available"""
        return self._sd_available
        
    def get_input_type(self) -> str:
        """Get input type identifier"""
        return "microphone"
        
    def get_settings(self) -> Dict[str, Any]:
        """Get current microphone settings"""
        return {
            "device_id": self.device_id,
            "samplerate": self.samplerate,
            "blocksize": self.blocksize,
            "sounddevice_available": self._sd_available,
            "device": self.device
        }
        
    async def configure_input(self, **settings) -> None:
        """Configure microphone settings"""
        if "device_id" in settings:
            self.device_id = settings["device_id"]
        if "samplerate" in settings:
            self.samplerate = settings["samplerate"]
        if "blocksize" in settings:
            self.blocksize = settings["blocksize"]
            
    async def test_input(self) -> bool:
        """Test microphone functionality"""
        if not self.is_available():
            return False
            
        try:
            import sounddevice as sd  # type: ignore
            # Test if we can get audio devices
            devices = sd.query_devices()
            return len(devices) > 0
        except Exception as e:
            logger.error(f"Microphone test failed: {e}")
            return False
        
    def list_audio_devices(self) -> list[Dict[str, Any]]:
        """List available audio input devices"""
        if not self.is_available():
            return []
            
        try:
            import sounddevice as sd  # type: ignore
            devices = sd.query_devices()
            input_devices = []
            
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append({
                        'id': i,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'samplerate': device['default_samplerate']
                    })
            
            return input_devices
        except Exception as e:
            logger.error(f"Error listing audio devices: {e}")
            return []
        
    async def start_listening(self) -> None:
        """Initialize and start audio capture (NO VOSK loading)"""
        if not self.is_available():
            raise ComponentNotAvailable("Audio dependencies (sounddevice) not available")
            
        try:
            import sounddevice as sd  # type: ignore
            
            # Audio device setup only - no VOSK model loading
            if self.device_id is not None:
                device_info = sd.query_devices(self.device_id, 'input')
                if self.samplerate is None:
                    self.samplerate = int(device_info['default_samplerate'])
            
            # Initialize audio queue
            self._audio_queue = queue.Queue()
            
            # Set up audio callback (unchanged)
            def audio_callback(indata, frames, time, status):
                """Audio callback for sounddevice"""
                if status:
                    logger.warning(f"Audio status: {status}")
                if self._listening and self._audio_queue:
                    self._audio_queue.put(bytes(indata))
            
            # Create audio stream
            self._audio_stream = sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                device=self.device_id,
                dtype='int16',
                channels=1,
                callback=audio_callback
            )
            
            # Start listening
            self._listening = True
            self._audio_stream.start()
            
            logger.info(f"Audio capture started - Device: {self.device_id or 'default'}, "
                       f"Sample rate: {self.samplerate} Hz")
            
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            await self._cleanup()
            raise ComponentNotAvailable(f"Audio initialization failed: {e}")
        
    async def stop_listening(self) -> None:
        """Stop audio capture"""
        self._listening = False
        await self._cleanup()
        logger.info("Audio capture stopped")
        
    def is_listening(self) -> bool:
        """Check if currently listening"""
        return self._listening
        
    async def listen(self) -> AsyncIterator[InputData]:
        """
        Pure audio stream - no business logic
        
        Yields AudioData objects for pipeline processing
        """
        if not self._listening or not self._audio_queue:
            return
            
        logger.info("Starting pure audio capture...")
        
        while self._listening:
            try:
                # Get audio data from queue
                try:
                    audio_chunk = await asyncio.to_thread(self._audio_queue.get, timeout=1.0)
                except queue.Empty:
                    await asyncio.sleep(0.1)
                    continue
                
                # Yield pure AudioData object
                yield AudioData(
                    data=audio_chunk,
                    timestamp=time.time(),
                    sample_rate=self.samplerate,
                    channels=1,  # Microphone is typically mono
                    format="pcm16"
                )
                
            except Exception as e:
                logger.error(f"Error in audio capture: {e}")
                await asyncio.sleep(0.1)
                
    async def get_audio_info(self) -> Dict[str, Any]:
        """Get current audio capture status and info"""
        return {
            "listening": self._listening,
            "audio_stream_active": self._audio_stream is not None and self._audio_stream.active,
            "queue_size": self._audio_queue.qsize() if self._audio_queue else 0,
            "audio_devices": self.list_audio_devices(),
            "sample_rate": self.samplerate,
            "device_id": self.device_id,
            "device": self.device
        }
        
    async def _cleanup(self) -> None:
        """Clean up audio resources"""
        try:
            if self._audio_stream:
                if self._audio_stream.active:
                    self._audio_stream.stop()
                self._audio_stream.close()
                self._audio_stream = None
                
            if self._audio_queue:
                # Clear remaining queue items
                while not self._audio_queue.empty():
                    try:
                        self._audio_queue.get_nowait()
                    except queue.Empty:
                        break
                self._audio_queue = None
                
        except Exception as e:
            logger.error(f"Error during audio cleanup: {e}") 
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Microphone input needs audio processing libraries"""
        return ["sounddevice>=0.4.0", "soundfile>=0.12.0"] 