"""
TTS Output Target - Text-to-Speech output

Provides speech synthesis output using various TTS engines.
This is an optional component that requires additional dependencies.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path

from .base import OutputTarget, Response, ComponentNotAvailable

if TYPE_CHECKING:
    # Type hints for optional dependencies
    try:
        import pyttsx3  # type: ignore
    except ImportError:
        pyttsx3 = None

logger = logging.getLogger(__name__)


class TTSOutput(OutputTarget):
    """
    Text-to-Speech output target.
    
    Supports various TTS engines like pyttsx3, elevenlabs, etc.
    Gracefully handles missing dependencies.
    """
    
    def __init__(self, engine: str = "pyttsx3", voice: Optional[str] = None):
        self.engine = engine
        self.voice = voice
        self._tts_engine: Optional[Any] = None
        self._settings = {
            "rate": 200,
            "volume": 0.9,
            "voice": voice
        }
        
        # Check for required dependencies
        try:
            if engine == "pyttsx3":
                import pyttsx3  # type: ignore
                self._pyttsx3_available = True
            else:
                self._pyttsx3_available = False
                
            self._engine_available = True
        except ImportError as e:
            logger.warning(f"TTS dependencies not available: {e}")
            self._engine_available = False
        
    def is_available(self) -> bool:
        """Check if TTS output is available"""
        return self._engine_available
        
    def get_output_type(self) -> str:
        """Get output type identifier"""
        return "tts"
        
    def supports_response_type(self, response_type: str) -> bool:
        """Check if this target supports the response type"""
        # TTS handles text and tts response types
        return response_type in ["text", "tts"]
        
    def get_settings(self) -> Dict[str, Any]:
        """Get current TTS settings"""
        return {
            "engine": self.engine,
            "voice": self.voice,
            "available": self._engine_available,
            **self._settings
        }
        
    async def configure_output(self, **settings) -> None:
        """Configure TTS settings"""
        for key, value in settings.items():
            if key in self._settings:
                self._settings[key] = value
                
        if "voice" in settings:
            self.voice = settings["voice"]
            self._settings["voice"] = settings["voice"]
            
    async def test_output(self) -> bool:
        """Test TTS functionality"""
        if not self.is_available():
            return False
            
        try:
            test_response = Response("TTS test", response_type="test")
            await self.send(test_response)
            return True
        except Exception as e:
            logger.error(f"TTS test failed: {e}")
            return False
        
    async def send(self, response: Response) -> None:
        """Send response via TTS"""
        if not self.is_available():
            raise ComponentNotAvailable("TTS engine not available")
            
        try:
            # Initialize TTS engine if needed
            if not self._tts_engine:
                await self._initialize_engine()
                
            # Speak the text
            await self._speak_text(response.text)
            
        except Exception as e:
            logger.error(f"TTS output error: {e}")
            raise
            
    async def send_error(self, error: str) -> None:
        """Send error message via TTS"""
        error_response = Response(f"Error: {error}", response_type="error")
        await self.send(error_response)
        
    async def _initialize_engine(self) -> None:
        """Initialize the TTS engine"""
        if not self.is_available():
            raise ComponentNotAvailable(f"TTS engine '{self.engine}' not available")
            
        try:
            if self.engine == "pyttsx3":
                import pyttsx3  # type: ignore
                self._tts_engine = pyttsx3.init()
                
                # Configure engine settings
                if self._tts_engine:
                    self._tts_engine.setProperty('rate', self._settings['rate'])
                    self._tts_engine.setProperty('volume', self._settings['volume'])
                    
                    if self._settings['voice']:
                        voices = self._tts_engine.getProperty('voices')
                        for voice in voices:
                            if self._settings['voice'] in voice.id:
                                self._tts_engine.setProperty('voice', voice.id)
                                break
                                
                logger.info(f"Initialized {self.engine} TTS engine")
                
        except Exception as e:
            logger.error(f"Failed to initialize TTS engine: {e}")
            raise ComponentNotAvailable(f"TTS engine initialization failed: {e}")
            
    async def _speak_text(self, text: str) -> None:
        """Speak text using the TTS engine"""
        if not self._tts_engine:
            raise ComponentNotAvailable("TTS engine not initialized")
            
        try:
            if self.engine == "pyttsx3":
                # Run TTS in a thread to avoid blocking
                await asyncio.to_thread(self._pyttsx3_speak, text)
            else:
                logger.warning(f"Speaking not implemented for engine: {self.engine}")
                
        except Exception as e:
            logger.error(f"Error speaking text: {e}")
            raise
            
    def _pyttsx3_speak(self, text: str) -> None:
        """Synchronous pyttsx3 speaking method"""
        try:
            if self._tts_engine:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
            else:
                raise ComponentNotAvailable("TTS engine not initialized")
        except Exception as e:
            logger.error(f"pyttsx3 speaking error: {e}")
            raise
            
    async def to_file(self, text: str, output_path: Path) -> None:
        """Save TTS output to file"""
        if not self.is_available():
            raise ComponentNotAvailable("TTS engine not available")
            
        try:
            if not self._tts_engine:
                await self._initialize_engine()
                
            if self.engine == "pyttsx3":
                # pyttsx3 can save to file
                await asyncio.to_thread(self._pyttsx3_save_to_file, text, output_path)
            else:
                logger.warning(f"File output not implemented for engine: {self.engine}")
                
        except Exception as e:
            logger.error(f"Error saving TTS to file: {e}")
            raise
            
    def _pyttsx3_save_to_file(self, text: str, output_path: Path) -> None:
        """Save pyttsx3 output to file"""
        try:
            if self._tts_engine:
                self._tts_engine.save_to_file(text, str(output_path))
                self._tts_engine.runAndWait()
            else:
                raise ComponentNotAvailable("TTS engine not initialized")
        except Exception as e:
            logger.error(f"pyttsx3 file save error: {e}")
            raise
            
    def get_supported_voices(self) -> list[str]:
        """Get list of available voices"""
        if not self.is_available() or not self._tts_engine:
            return []
            
        try:
            if self.engine == "pyttsx3":
                voices = self._tts_engine.getProperty('voices')
                return [voice.id for voice in voices] if voices else []
            else:
                return []
        except Exception as e:
            logger.error(f"Error getting voices: {e}")
            return [] 