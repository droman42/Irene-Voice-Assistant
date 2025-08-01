"""
Microphone Input Source - Speech recognition input

Provides speech-to-text input using VOSK or other speech recognition engines.
This is an optional component that requires additional dependencies.
"""

import asyncio
import logging
from typing import AsyncIterator, Dict, Any, Optional

from .base import InputSource, ComponentNotAvailable

logger = logging.getLogger(__name__)


class MicrophoneInput(InputSource):
    """
    Microphone input source with speech recognition.
    
    Requires VOSK and sounddevice for operation.
    Gracefully handles missing dependencies.
    """
    
    def __init__(self, model_path: Optional[str] = None, device_id: Optional[int] = None):
        self.model_path = model_path
        self.device_id = device_id
        self._listening = False
        self._recognizer = None
        self._audio_queue = None
        
        # Check for required dependencies
        try:
            import vosk
            import sounddevice as sd
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
            "vosk_available": self._vosk_available,
            "sounddevice_available": self._sd_available
        }
        
    async def configure_input(self, **settings) -> None:
        """Configure microphone settings"""
        if "device_id" in settings:
            self.device_id = settings["device_id"]
        if "model_path" in settings:
            self.model_path = settings["model_path"]
            
    async def test_input(self) -> bool:
        """Test microphone functionality"""
        if not self.is_available():
            return False
            
        try:
            import sounddevice as sd
            # Test if we can get audio devices
            devices = sd.query_devices()
            return len(devices) > 0
        except Exception as e:
            logger.error(f"Microphone test failed: {e}")
            return False
        
    async def start_listening(self) -> None:
        """Initialize and start microphone listening"""
        if not self.is_available():
            raise ComponentNotAvailable("Microphone dependencies (VOSK, sounddevice) not available")
            
        try:
            import vosk
            import sounddevice as sd
            import json
            
            # Initialize VOSK recognizer
            if not self.model_path:
                self.model_path = "model"  # Default model path
                
            model = vosk.Model(self.model_path)
            self._recognizer = vosk.KaldiRecognizer(model, 16000)
            
            # Initialize audio queue
            self._audio_queue = asyncio.Queue()
            
            self._listening = True
            logger.info("Microphone listening started")
            
        except Exception as e:
            logger.error(f"Failed to start microphone: {e}")
            raise ComponentNotAvailable(f"Microphone initialization failed: {e}")
        
    async def stop_listening(self) -> None:
        """Stop microphone listening"""
        self._listening = False
        self._recognizer = None
        self._audio_queue = None
        logger.info("Microphone listening stopped")
        
    def is_listening(self) -> bool:
        """Check if currently listening"""
        return self._listening
        
    async def listen(self) -> AsyncIterator[str]:
        """
        Listen for speech and yield recognized commands.
        
        This is a simplified implementation. A full implementation would
        need proper audio streaming and VOSK integration.
        """
        if not self._listening:
            return
            
        logger.warning("Microphone input is not fully implemented yet")
        
        # Placeholder implementation
        # In a real implementation, this would:
        # 1. Stream audio from microphone
        # 2. Process chunks with VOSK
        # 3. Yield recognized speech as commands
        
        while self._listening:
            # Simulate waiting for speech recognition
            await asyncio.sleep(1.0)
            
            # This would be replaced with actual speech recognition
            # For now, we don't yield anything to avoid blocking
            if False:  # Placeholder condition
                yield "recognized speech would go here" 