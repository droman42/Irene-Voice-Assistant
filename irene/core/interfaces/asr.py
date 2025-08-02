"""
ASR Plugin Interface - For speech recognition functionality

Defines the interface for plugins that convert speech to text
using various ASR engines.
"""

from typing import Dict, Any, Optional
from abc import abstractmethod

from .plugin import PluginInterface


class ASRPlugin(PluginInterface):
    """
    Interface for Automatic Speech Recognition plugins.
    
    ASR plugins convert speech to text using various engines
    and provide speech recognition capabilities.
    """
    
    @abstractmethod
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        """
        Convert audio data to text.
        
        Args:
            audio_data: Raw audio data bytes
            language: Language code (e.g., 'en-US', 'ru-RU')
            **kwargs: Engine-specific parameters
            
        Returns:
            Transcribed text
        """
        pass
        
    def get_supported_languages(self) -> list[str]:
        """
        Get list of supported language codes.
        
        Returns:
            List of language codes (e.g., ['en-US', 'ru-RU'])
        """
        return ['en-US']
        
    def get_supported_formats(self) -> list[str]:
        """
        Get list of supported audio formats.
        
        Returns:
            List of format strings (e.g., ['wav', 'mp3', 'flac'])
        """
        return ['wav']
        
    async def set_language(self, language: str) -> None:
        """
        Set the recognition language.
        
        Args:
            language: Language code
        """
        pass
        
    def get_confidence_threshold(self) -> float:
        """
        Get current confidence threshold.
        
        Returns:
            Confidence threshold (0.0 to 1.0)
        """
        return 0.5
        
    async def set_confidence_threshold(self, threshold: float) -> None:
        """
        Set confidence threshold for recognition.
        
        Args:
            threshold: Confidence threshold (0.0 to 1.0)
        """
        pass
        
    def is_available(self) -> bool:
        """
        Check if ASR system is available.
        
        Returns:
            True if ASR system is functional
        """
        return True 