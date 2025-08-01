"""
Microphone Input Source - Speech recognition input

Provides speech-to-text input using VOSK speech recognition engines.
This is an optional component that requires additional dependencies.
"""

import asyncio
import logging
import queue
import json
from typing import AsyncIterator, Dict, Any, Optional
from pathlib import Path

from .base import InputSource, ComponentNotAvailable

logger = logging.getLogger(__name__)


class MicrophoneInput(InputSource):
    """
    Microphone input source with VOSK speech recognition.
    
    Requires VOSK and sounddevice for operation.
    Gracefully handles missing dependencies.
    """
    
    def __init__(self, model_path: Optional[str] = None, device_id: Optional[int] = None,
                 samplerate: int = 16000, blocksize: int = 8000):
        self.model_path = model_path or "model"
        self.device_id = device_id
        self.samplerate = samplerate
        self.blocksize = blocksize
        self._listening = False
        self._recognizer = None
        self._model = None
        self._audio_queue = None
        self._audio_stream = None
        self._recognition_task = None
        
        # Check for required dependencies
        try:
            import vosk  # type: ignore
            import sounddevice as sd  # type: ignore
            self._vosk_available = True
            self._sd_available = True
        except ImportError as e:
            logger.warning(f"Microphone input dependencies not available: {e}")
            self._vosk_available = False
            self._sd_available = False
        
    def is_available(self) -> bool:
        """Check if microphone input is available"""
        return self._vosk_available and self._sd_available
        
    def get_input_type(self) -> str:
        """Get input type identifier"""
        return "microphone"
        
    def get_settings(self) -> Dict[str, Any]:
        """Get current microphone settings"""
        return {
            "model_path": self.model_path,
            "device_id": self.device_id,
            "samplerate": self.samplerate,
            "blocksize": self.blocksize,
            "vosk_available": self._vosk_available,
            "sounddevice_available": self._sd_available
        }
        
    async def configure_input(self, **settings) -> None:
        """Configure microphone settings"""
        if "device_id" in settings:
            self.device_id = settings["device_id"]
        if "model_path" in settings:
            self.model_path = settings["model_path"]
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
        """Initialize and start microphone listening"""
        if not self.is_available():
            raise ComponentNotAvailable("Microphone dependencies (VOSK, sounddevice) not available")
            
        try:
            import vosk  # type: ignore
            import sounddevice as sd  # type: ignore
            
            # Load VOSK model
            model_path = Path(self.model_path)
            if not model_path.exists():
                raise ComponentNotAvailable(f"VOSK model not found at: {model_path}")
                
            logger.info(f"Loading VOSK model from: {model_path}")
            self._model = vosk.Model(str(model_path))
            
            # Get audio device info and sample rate
            if self.device_id is not None:
                device_info = sd.query_devices(self.device_id, 'input')
                if self.samplerate is None:
                    self.samplerate = int(device_info['default_samplerate'])
            
            # Create recognizer
            self._recognizer = vosk.KaldiRecognizer(self._model, self.samplerate)
            
            # Initialize audio queue
            self._audio_queue = queue.Queue()
            
            # Set up audio callback
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
            
            logger.info(f"Microphone listening started - Device: {self.device_id or 'default'}, "
                       f"Sample rate: {self.samplerate} Hz, Block size: {self.blocksize}")
            
        except Exception as e:
            logger.error(f"Failed to start microphone: {e}")
            await self._cleanup()
            raise ComponentNotAvailable(f"Microphone initialization failed: {e}")
        
    async def stop_listening(self) -> None:
        """Stop microphone listening"""
        self._listening = False
        await self._cleanup()
        logger.info("Microphone listening stopped")
        
    def is_listening(self) -> bool:
        """Check if currently listening"""
        return self._listening
        
    async def listen(self) -> AsyncIterator[str]:
        """
        Listen for speech and yield recognized commands.
        
        Yields recognized speech commands as they are detected.
        """
        if not self._listening or not self._audio_queue or not self._recognizer:
            return
            
        logger.info("Starting speech recognition...")
        
        while self._listening:
            try:
                # Get audio data from queue (non-blocking with timeout)
                try:
                    data = await asyncio.to_thread(self._audio_queue.get, timeout=1.0)
                except queue.Empty:
                    # No audio data, continue listening
                    await asyncio.sleep(0.1)
                    continue
                
                # Process audio with VOSK
                if self._recognizer.AcceptWaveform(data):
                    # Complete recognition result
                    result = self._recognizer.Result()
                    result_data = json.loads(result)
                    text = result_data.get("text", "").strip()
                    
                    if text:
                        logger.info(f"Speech recognized: '{text}'")
                        yield text
                        
                # Optional: Handle partial results for debugging
                # else:
                #     partial = self._recognizer.PartialResult()
                #     partial_data = json.loads(partial)
                #     partial_text = partial_data.get("partial", "")
                #     if partial_text:
                #         logger.debug(f"Partial recognition: '{partial_text}'")
                
            except Exception as e:
                logger.error(f"Error in speech recognition: {e}")
                # Continue listening even if there's an error
                await asyncio.sleep(0.1)
                
    async def get_recognition_info(self) -> Dict[str, Any]:
        """Get current recognition status and info"""
        return {
            "listening": self._listening,
            "model_loaded": self._model is not None,
            "recognizer_ready": self._recognizer is not None,
            "audio_stream_active": self._audio_stream is not None and self._audio_stream.active,
            "queue_size": self._audio_queue.qsize() if self._audio_queue else 0,
            "audio_devices": self.list_audio_devices()
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
                
            self._recognizer = None
            self._model = None
            
        except Exception as e:
            logger.error(f"Error during microphone cleanup: {e}") 