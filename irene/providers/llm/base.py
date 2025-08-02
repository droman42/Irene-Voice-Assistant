"""
LLM Provider Base Classes

Abstract base class for all LLM (Large Language Model) implementations.
Following ABC inheritance pattern for type safety and runtime validation.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class LLMProvider(ABC):
    """Abstract base class for LLM implementations"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with provider-specific configuration
        
        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider dependencies and credentials are available
        
        Returns:
            True if provider can be used, False otherwise
        """
        pass
    
    @abstractmethod
    async def enhance_text(self, text: str, task: str = "improve", **kwargs) -> str:
        """Enhance text using LLM for various tasks
        
        Args:
            text: Input text to enhance
            task: Enhancement task ("improve", "grammar_correction", "translation", etc.)
            **kwargs: Provider-specific parameters
            
        Returns:
            Enhanced text string
        """
        pass
    
    @abstractmethod
    async def chat_completion(self, messages: List[Dict], **kwargs) -> str:
        """Generate chat completion response
        
        Args:
            messages: List of message dictionaries with role/content
            **kwargs: Provider-specific parameters
            
        Returns:
            Response text string
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Return list of available models for this provider
        
        Returns:
            List of model names/identifiers
        """
        pass
    
    @abstractmethod
    def get_supported_tasks(self) -> List[str]:
        """Return list of supported enhancement tasks
        
        Returns:
            List of task identifiers
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
    def get_provider_name(self) -> str:
        """Return unique provider identifier
        
        Returns:
            Provider name string
        """
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities (optional override)
        
        Returns:
            Dictionary with capability information
        """
        return {
            "models": self.get_available_models(),
            "tasks": self.get_supported_tasks(),
            "streaming": False,  # Override if streaming supported
            "multimodal": False,  # Override if multimodal supported
            "function_calling": False  # Override if function calling supported
        } 