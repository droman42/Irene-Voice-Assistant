"""
ASR Provider Base Classes

Abstract base class for all ASR (Automatic Speech Recognition) implementations.
Following ABC inheritance pattern for type safety and runtime validation.
"""

from abc import abstractmethod
from typing import Dict, Any, List, AsyncIterator
from pathlib import Path

from ..base import ProviderBase


class ASRProvider(ProviderBase):
    """
    Abstract base class for speech recognition implementations.
    
    Enhanced in TODO #4 Phase 1 with proper ProviderBase inheritance.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with provider-specific configuration
        
        Args:
            config: Provider-specific configuration dictionary
        """
        # Call ProviderBase.__init__ to get status tracking, logging, etc.
        super().__init__(config)
    
    @abstractmethod
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        """Transcribe audio data to text
        
        Args:
            audio_data: Raw audio bytes to transcribe
            **kwargs: Provider-specific parameters (language, confidence_threshold, etc.)
            
        Returns:
            Transcribed text string
        """
        pass
    
    @abstractmethod
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Transcribe streaming audio data
        
        Args:
            audio_stream: Async iterator of audio chunks
            
        Yields:
            Transcribed text chunks as they become available
        """
        pass
    
    @abstractmethod
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for provider-specific parameters
        
        Returns:
            Dictionary describing available parameters, types, and defaults
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Return list of supported language codes
        
        Returns:
            List of language codes (e.g., ['ru', 'en', 'es'])
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Return list of supported audio formats
        
        Returns:
            List of format strings (e.g., ['wav', 'mp3', 'flac'])
        """
        pass
    
    @abstractmethod
    def get_preferred_sample_rates(self) -> List[int]:
        """Return list of preferred sample rates in order of preference (Phase 3)
        
        Returns:
            List of sample rates in Hz, ordered by preference (best first)
        """
        pass
    
    @abstractmethod
    def supports_sample_rate(self, rate: int) -> bool:
        """Check if this provider supports a specific sample rate (Phase 3)
        
        Args:
            rate: Sample rate in Hz to check
            
        Returns:
            True if the sample rate is supported, False otherwise
        """
        pass
    
    async def set_language(self, language: str) -> None:
        """Set the recognition language (optional override)
        
        Args:
            language: Language code to set
            
        Note:
            Default implementation does nothing. Override if dynamic language
            switching is supported by the provider.
        """
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities (optional override)
        
        Returns:
            Dictionary with capability information
        """
        return {
            "languages": self.get_supported_languages(),
            "formats": self.get_supported_formats(),
            "streaming": True,  # Most providers support streaming
            "real_time": False,  # Override if real-time processing supported
            "confidence_scores": False  # Override if confidence scores provided
        } 