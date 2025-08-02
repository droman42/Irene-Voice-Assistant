"""
LLM Plugin Interface - For language model functionality

Defines the interface for plugins that provide language model
and text enhancement capabilities.
"""

from typing import Dict, Any, Optional, List
from abc import abstractmethod

from .plugin import PluginInterface


class LLMPlugin(PluginInterface):
    """
    Interface for Large Language Model plugins.
    
    LLM plugins provide text enhancement, completion, and 
    language processing capabilities using various models.
    """
    
    @abstractmethod
    async def enhance_text(self, text: str, task: str = "improve", **kwargs) -> str:
        """
        Enhance text using the language model.
        
        Args:
            text: Input text to enhance
            task: Enhancement task type (e.g., 'improve', 'translate', 'summarize')
            **kwargs: Model-specific parameters
            
        Returns:
            Enhanced text
        """
        pass
        
    async def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Generate chat completion response.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Model-specific parameters
            
        Returns:
            Response text
        """
        # Default implementation - can be overridden
        if messages:
            last_message = messages[-1].get('content', '')
            return await self.enhance_text(last_message, task="respond")
        return ""
        
    def get_supported_tasks(self) -> list[str]:
        """
        Get list of supported enhancement tasks.
        
        Returns:
            List of task names
        """
        return ['improve', 'translate', 'summarize', 'respond']
        
    def get_supported_languages(self) -> list[str]:
        """
        Get list of supported languages.
        
        Returns:
            List of language codes
        """
        return ['en', 'ru']
        
    async def set_model(self, model_name: str) -> None:
        """
        Set the active model.
        
        Args:
            model_name: Name of the model to use
        """
        pass
        
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.
        
        Returns:
            Dictionary with model information
        """
        return {
            "name": "default",
            "version": "1.0",
            "capabilities": self.get_supported_tasks()
        }
        
    def is_available(self) -> bool:
        """
        Check if LLM system is available.
        
        Returns:
            True if LLM system is functional
        """
        return True 