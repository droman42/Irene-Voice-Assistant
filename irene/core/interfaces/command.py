"""
Command Plugin Interface - For handling voice commands

Defines the interface for plugins that process voice commands
and generate responses.
"""

from typing import List
from abc import abstractmethod

from .plugin import PluginInterface
from ..context import Context
from ..commands import CommandResult


class CommandPlugin(PluginInterface):
    """
    Interface for plugins that handle voice commands.
    
    Command plugins process specific trigger words/phrases
    and generate appropriate responses.
    """
    
    @abstractmethod
    def get_triggers(self) -> List[str]:
        """
        Get list of trigger words/phrases this plugin handles.
        
        Returns:
            List of trigger words that activate this plugin
        """
        pass
        
    @abstractmethod
    async def can_handle(self, command: str, context: Context) -> bool:
        """
        Check if this plugin can handle the given command.
        
        Args:
            command: The command string to check
            context: Current conversation context
            
        Returns:
            True if this plugin can handle the command
        """
        pass
        
    @abstractmethod
    async def handle_command(self, command: str, context: Context) -> CommandResult:
        """
        Handle the command and generate a response.
        
        Args:
            command: The command string to process
            context: Current conversation context
            
        Returns:
            CommandResult with the response or error
        """
        pass
        
    def get_priority(self) -> int:
        """
        Get the priority of this command handler.
        Lower numbers = higher priority.
        
        Returns:
            Priority value (default: 100)
        """
        return 100
        
    def supports_partial_matching(self) -> bool:
        """
        Whether this plugin supports partial command matching.
        
        Returns:
            True if plugin can handle partial matches
        """
        return False 