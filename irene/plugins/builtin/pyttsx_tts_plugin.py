"""
Pyttsx TTS Plugin - Speech synthesis using pyttsx3

Replaces legacy plugin_tts_pyttsx.py with modern async architecture.
Provides text-to-speech using the pyttsx3 engine.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List

from ...core.interfaces.tts import TTSPlugin


class PyttsTTSPlugin(TTSPlugin):
    """
    Pyttsx TTS plugin using the pyttsx3 engine.
    
    Features:
    - Cross-platform text-to-speech
    - Multiple voice selection
    - Configurable speech rate and volume
    - File output support
    - Async operation with threading
    """
    
    @property
    def name(self) -> str:
        return "pyttsx_tts"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Cross-platform TTS using pyttsx3 with voice selection"
        
    @property
    def dependencies(self) -> list[str]:
        """No required dependencies (pyttsx3 is optional)"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """Requires pyttsx3 for TTS functionality"""
        return ["pyttsx3"]
        
    # Additional metadata for PluginRegistry discovery
    @property
    def enabled_by_default(self) -> bool:
        """Pyttsx TTS not enabled by default (requires dependency)"""
        return False
        
    @property  
    def category(self) -> str:
        """Plugin category"""
        return "tts"
        
    @property
    def platforms(self) -> list[str]:
        """Supported platforms (empty = all platforms)"""
        return []
        
    def __init__(self):
        super().__init__()
        self._engine = None
        self._available = False
        self._voices = []
        self._current_voice_id = 0
        
        # Default settings
        self._settings = {
            "voice_id": 0,  # System voice index
            "rate": 200,    # Speech rate (words per minute)
            "volume": 1.0   # Volume (0.0 to 1.0)
        }
        
        # Try to initialize pyttsx3
        self._initialize_engine()
        
    def _initialize_engine(self):
        """Initialize the pyttsx3 engine"""
        try:
            import pyttsx3  # type: ignore
            self._engine = pyttsx3.init()
            self._available = True
            
            # Get available voices
            voices = self._engine.getProperty("voices")
            self._voices = voices if voices else []
            
            # Set default voice and properties
            if self._voices:
                self._engine.setProperty("voice", self._voices[self._settings["voice_id"]].id)
            self._engine.setProperty("rate", self._settings["rate"])
            self._engine.setProperty("volume", self._settings["volume"])
            
        except ImportError:
            self._available = False
            self._engine = None
        except Exception as e:
            self._available = False
            self._engine = None
            print(f"Failed to initialize pyttsx3: {e}")
            
    async def speak(self, text: str, **kwargs) -> None:
        """
        Convert text to speech and play it.
        
        Args:
            text: Text to speak
            **kwargs: Additional parameters (voice_id, rate, volume)
        """
        if not self.is_available():
            raise RuntimeError("Pyttsx3 TTS engine not available")
            
        # Update settings if provided
        await self._update_settings_from_kwargs(**kwargs)
        
        # Use asyncio.to_thread to make blocking pyttsx3 calls non-blocking
        await asyncio.to_thread(self._speak_sync, text)
        
    def _speak_sync(self, text: str) -> None:
        """Synchronous speech method for threading"""
        if self._engine:
            self._engine.say(str(text))
            self._engine.runAndWait()
            
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """
        Convert text to speech and save to file.
        
        Args:
            text: Text to convert
            output_path: Path to save audio file
            **kwargs: Additional parameters
        """
        if not self.is_available():
            raise RuntimeError("Pyttsx3 TTS engine not available")
            
        # Update settings if provided
        await self._update_settings_from_kwargs(**kwargs)
        
        # Use asyncio.to_thread for file generation
        await asyncio.to_thread(self._to_file_sync, text, str(output_path))
        
    def _to_file_sync(self, text: str, file_path: str) -> None:
        """Synchronous file generation method for threading"""
        if self._engine:
            self._engine.save_to_file(str(text), file_path)
            self._engine.runAndWait()
            
    def get_supported_voices(self) -> List[str]:
        """Get list of available system voices"""
        if not self._voices:
            return []
            
        voice_names = []
        for i, voice in enumerate(self._voices):
            # Extract voice name from ID or use index
            voice_name = getattr(voice, 'name', f"Voice {i}")
            voice_names.append(voice_name)
            
        return voice_names
        
    def get_supported_languages(self) -> List[str]:
        """Get supported languages (depends on system voices)"""
        if not self._voices:
            return ["en-US"]
            
        languages = set()
        for voice in self._voices:
            # Try to extract language from voice attributes
            if hasattr(voice, 'languages') and voice.languages:
                languages.update(voice.languages)
            else:
                # Default fallback
                languages.add("en-US")
                
        return list(languages)
        
    def get_voice_settings(self) -> Dict[str, Any]:
        """Get current voice settings"""
        current_settings = self._settings.copy()
        
        if self._engine:
            # Get actual engine properties
            try:
                current_settings["rate"] = self._engine.getProperty("rate")
                current_settings["volume"] = self._engine.getProperty("volume")
            except Exception:
                pass  # Use stored settings as fallback
                
        return current_settings
        
    async def set_voice_settings(self, **settings) -> None:
        """
        Update voice settings.
        
        Args:
            **settings: Settings to update (voice_id, rate, volume)
        """
        await self._update_settings_from_kwargs(**settings)
        
    async def _update_settings_from_kwargs(self, **kwargs) -> None:
        """Update settings from keyword arguments"""
        for key, value in kwargs.items():
            if key in self._settings:
                self._settings[key] = value
                
        # Apply settings to engine
        if self._engine:
            try:
                # Set voice if voice_id changed
                if "voice_id" in kwargs and self._voices:
                    voice_id = int(kwargs["voice_id"])
                    if 0 <= voice_id < len(self._voices):
                        self._engine.setProperty("voice", self._voices[voice_id].id)
                        
                # Set rate if changed
                if "rate" in kwargs:
                    self._engine.setProperty("rate", int(kwargs["rate"]))
                    
                # Set volume if changed
                if "volume" in kwargs:
                    volume = float(kwargs["volume"])
                    volume = max(0.0, min(1.0, volume))  # Clamp to 0.0-1.0
                    self._engine.setProperty("volume", volume)
                    
            except Exception as e:
                print(f"Error updating pyttsx3 settings: {e}")
                
    def is_available(self) -> bool:
        """Check if pyttsx3 TTS engine is available"""
        return self._available and self._engine is not None
        
    async def test_speech(self) -> bool:
        """Test the pyttsx3 TTS engine"""
        try:
            await self.speak("Pyttsx TTS test successful")
            return True
        except Exception as e:
            print(f"Pyttsx TTS test failed: {e}")
            return False 