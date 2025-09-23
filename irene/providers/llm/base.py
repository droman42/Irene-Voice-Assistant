"""
LLM Provider Base Classes

Abstract base class for all LLM (Large Language Model) implementations.
Following ABC inheritance pattern for type safety and runtime validation.
"""

from abc import abstractmethod
from typing import Dict, Any, List

from ..base import ProviderBase


class LLMProvider(ProviderBase):
    """
    Abstract base class for LLM implementations.
    
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
            List of task names (e.g., ['improve', 'grammar_correction', 'translation'])
        """
        pass
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Auto-generate parameter schema from Pydantic model
        
        Returns:
            Dictionary describing available parameters, types, and defaults
        """
        from irene.config.auto_registry import AutoSchemaRegistry
        
        # Extract component type from module path
        component_type = self.__class__.__module__.split('.')[-2]  # e.g., 'tts', 'audio'
        provider_name = self.get_provider_name()
        
        return AutoSchemaRegistry.get_provider_parameter_schema(component_type, provider_name) 