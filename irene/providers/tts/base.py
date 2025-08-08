"""
TTS Provider Interface - Abstract base class for TTS implementations

Defines the interface that all TTS provider implementations must follow.
This is used by UniversalTTSPlugin to manage multiple TTS backends.
"""

from typing import Dict, Any, List
from pathlib import Path
from abc import abstractmethod

from ..base import ProviderBase


class TTSProvider(ProviderBase):
    """
    Abstract base class for TTS provider implementations.
    
    TTS providers are pure implementation classes without plugin overhead,
    managed by UniversalTTSPlugin through configuration-driven instantiation.
    
    Enhanced in TODO #4 Phase 1 with proper ProviderBase inheritance.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration dictionary
        """
        # Call ProviderBase.__init__ to get status tracking, logging, etc.
        super().__init__(config)
    
    @abstractmethod
    async def speak(self, text: str, **kwargs) -> None:
        """
        Convert text to speech and play it.
        
        Args:
            text: Text to convert to speech
            **kwargs: Provider-specific parameters (speaker, speed, etc.)
        """
        pass
    
    @abstractmethod
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """
        Convert text to speech and save to audio file.
        
        Args:
            text: Text to convert to speech
            output_path: Path where to save the audio file
            **kwargs: Provider-specific parameters
        """
        pass
    
    @abstractmethod
    def get_parameter_schema(self) -> Dict[str, Any]:
        """
        Return schema for provider-specific parameters.
        
        Used by UniversalTTSPlugin to validate requests and provide
        API documentation.
        
        Returns:
            JSON Schema-like dictionary describing supported parameters
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return provider capabilities information.
        
        Returns:
            Dictionary containing:
            - languages: List of supported language codes
            - voices: List of available voice names/IDs
            - formats: List of supported audio formats
            - features: List of special features supported
        """
        pass
    
    def get_supported_voices(self) -> List[str]:
        """
        Get list of available voices for this provider.
        
        Returns:
            List of voice identifiers/names
        """
        capabilities = self.get_capabilities()
        return capabilities.get("voices", [])
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.
        
        Returns:
            List of language codes (e.g., ['en-US', 'ru-RU'])
        """
        capabilities = self.get_capabilities()
        return capabilities.get("languages", [])
    
    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported audio file formats.
        
        Returns:
            List of format names (e.g., ['wav', 'mp3', 'ogg'])
        """
        capabilities = self.get_capabilities()
        return capabilities.get("formats", ["wav"])
    
    async def validate_parameters(self, **kwargs) -> bool:
        """
        Validate provider-specific parameters.
        
        Args:
            **kwargs: Parameters to validate
            
        Returns:
            True if all parameters are valid
        """
        # Default implementation - override in providers for specific validation
        return True
    
    async def configure(self, config: Dict[str, Any]) -> None:
        """
        Update provider configuration at runtime.
        
        Args:
            config: New configuration values
        """
        # Default implementation - override in providers that support runtime config
        self.config.update(config) 