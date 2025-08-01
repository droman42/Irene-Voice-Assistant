"""
TTS Plugin Interface - For text-to-speech functionality

Defines the interface for plugins that convert text to speech
using various TTS engines.
"""

from typing import Dict, Any, Optional
from abc import abstractmethod
from pathlib import Path

from .plugin import PluginInterface


class TTSPlugin(PluginInterface):
    """
    Interface for Text-to-Speech plugins.
    
    TTS plugins convert text to speech using various engines
    and provide audio output capabilities.
    """
    
    @abstractmethod
    async def speak(self, text: str, **kwargs) -> None:
        """
        Convert text to speech and play it.
        
        Args:
            text: Text to convert to speech
            **kwargs: Engine-specific parameters (voice, speed, etc.)
        """
        pass
        
    @abstractmethod
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """
        Convert text to speech and save to file.
        
        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file
            **kwargs: Engine-specific parameters
        """
        pass
        
    def get_supported_voices(self) -> list[str]:
        """
        Get list of available voices for this TTS engine.
        
        Returns:
            List of voice identifiers
        """
        return []
        
    def get_supported_languages(self) -> list[str]:
        """
        Get list of supported language codes.
        
        Returns:
            List of language codes (e.g., ['en-US', 'ru-RU'])
        """
        return ['en-US']
        
    def get_voice_settings(self) -> Dict[str, Any]:
        """
        Get current voice settings.
        
        Returns:
            Dictionary of current settings (voice, speed, pitch, etc.)
        """
        return {}
        
    async def set_voice_settings(self, **settings) -> None:
        """
        Update voice settings.
        
        Args:
            **settings: Voice settings to update
        """
        pass
        
    def is_available(self) -> bool:
        """
        Check if the TTS engine is available and functional.
        
        Returns:
            True if TTS engine can be used
        """
        return True
        
    async def test_speech(self) -> bool:
        """
        Test the TTS engine with a simple phrase.
        
        Returns:
            True if test was successful
        """
        try:
            await self.speak("TTS test successful")
            return True
        except Exception:
            return False 