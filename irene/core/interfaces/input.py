"""
Input Plugin Interface - For handling input sources

Defines the interface for plugins that handle different input sources
like microphone, web, CLI, etc.
"""

from typing import AsyncIterator, Dict, Any, Optional
from abc import abstractmethod

from .plugin import PluginInterface


class InputPlugin(PluginInterface):
    """
    Interface for Input source plugins.
    
    Input plugins handle different sources of commands:
    microphone, web interface, CLI, remote connections, etc.
    """
    
    @abstractmethod
    async def listen(self) -> AsyncIterator[str]:
        """
        Start listening for input and yield commands as they arrive.
        
        Yields:
            Command strings as they are received
        """
        pass
        
    @abstractmethod
    async def start_listening(self) -> None:
        """Initialize and start the input source."""
        pass
        
    @abstractmethod
    async def stop_listening(self) -> None:
        """Stop listening and clean up resources."""
        pass
        
    def is_listening(self) -> bool:
        """
        Check if currently listening for input.
        
        Returns:
            True if actively listening
        """
        return False
        
    def is_available(self) -> bool:
        """
        Check if input source is available.
        
        Returns:
            True if input source can be used
        """
        return True
        
    def get_input_type(self) -> str:
        """
        Get the type of input this plugin handles.
        
        Returns:
            Input type identifier (e.g., 'microphone', 'web', 'cli')
        """
        return "unknown"
        
    def get_settings(self) -> Dict[str, Any]:
        """
        Get current input settings.
        
        Returns:
            Dictionary of current settings
        """
        return {}
        
    async def configure_input(self, **settings) -> None:
        """
        Configure input source settings.
        
        Args:
            **settings: Input-specific configuration options
        """
        pass
        
    async def test_input(self) -> bool:
        """
        Test if input source is working correctly.
        
        Returns:
            True if input test was successful
        """
        return True 