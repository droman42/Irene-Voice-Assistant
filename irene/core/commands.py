"""
Command Processing - Async command routing and handling

This module provides the command processing pipeline that routes
commands to appropriate handlers/plugins.
"""

import asyncio
import logging
from typing import List, Optional, Protocol, runtime_checkable, Dict, Any, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .context import Context

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of command processing"""
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def success_result(cls, response: str, **metadata) -> 'CommandResult':
        """Create a successful result"""
        return cls(success=True, response=response, metadata=metadata)
    
    @classmethod
    def error_result(cls, error: str, **metadata) -> 'CommandResult':
        """Create an error result"""
        return cls(success=False, error=error, metadata=metadata)


@runtime_checkable
class CommandHandler(Protocol):
    """Protocol for command handlers used by CommandProcessor"""
    
    async def can_handle(self, command: str, context: Context) -> bool:
        """Check if this handler can process the command"""
        ...
        
    async def handle(self, command: str, context: Context) -> CommandResult:
        """Handle the command and return result"""
        ...


class CommandPluginAdapter:
    """
    Adapter that wraps CommandPlugin to work with CommandProcessor.
    
    This bridges the CommandPlugin interface with the CommandHandler protocol
    that CommandProcessor expects, maintaining clean separation between
    plugin interfaces and command processing.
    """
    
    def __init__(self, command_plugin):
        """Initialize adapter with a CommandPlugin instance"""
        from .interfaces.command import CommandPlugin
        
        if not isinstance(command_plugin, CommandPlugin):
            raise TypeError("Plugin must implement CommandPlugin interface")
        
        self.plugin = command_plugin
        self.logger = logging.getLogger(f"adapter.{command_plugin.name}")
        
    async def can_handle(self, command: str, context: Context) -> bool:
        """Check if wrapped plugin can handle the command"""
        try:
            return await self.plugin.can_handle(command, context)
        except Exception as e:
            self.logger.error(f"Error checking if {self.plugin.name} can handle '{command}': {e}")
            return False
            
    async def handle(self, command: str, context: Context) -> CommandResult:
        """Handle command using wrapped plugin"""
        try:
            return await self.plugin.handle_command(command, context)
        except Exception as e:
            self.logger.error(f"Error handling command '{command}' with {self.plugin.name}: {e}")
            return CommandResult.error_result(f"Plugin {self.plugin.name} failed: {str(e)}")
            
    def __repr__(self) -> str:
        return f"CommandPluginAdapter({self.plugin.name})"


class BaseCommandHandler(ABC):
    """Legacy base class for command handlers - deprecated in favor of CommandPlugin"""
    
    @abstractmethod
    async def can_handle(self, command: str, context: Context) -> bool:
        """Check if this handler can process the command"""
        pass
        
    @abstractmethod
    async def handle(self, command: str, context: Context) -> CommandResult:
        """Handle the command and return result"""
        pass


class CommandProcessor:
    """
    Processes commands through registered handlers.
    
    Features:
    - Priority-based handler ordering
    - Plugin adapter integration
    - Graceful error handling
    - Context-aware processing
    """
    
    def __init__(self):
        self._handlers: list[CommandHandler] = []
        self._fallback_handler: Optional[CommandHandler] = None
        self.logger = logging.getLogger("command_processor")
        
    def register_plugin(self, command_plugin) -> None:
        """
        Register a CommandPlugin as a command handler.
        
        Args:
            command_plugin: Plugin implementing CommandPlugin interface
        """
        try:
            adapter = CommandPluginAdapter(command_plugin)
            self._handlers.append(adapter)
            
            # Sort handlers by priority (lower numbers = higher priority)
            if hasattr(command_plugin, 'get_priority'):
                self._handlers.sort(key=lambda h: 
                    h.plugin.get_priority() if isinstance(h, CommandPluginAdapter) and hasattr(h.plugin, 'get_priority') 
                    else 100
                )
            
            self.logger.info(f"Registered command plugin: {command_plugin.name}")
            
        except Exception as e:
            self.logger.error(f"Failed to register command plugin {command_plugin.name}: {e}")
        
    def register_handler(self, handler: CommandHandler) -> None:
        """Register a legacy command handler (deprecated)"""
        self._handlers.append(handler)
        self.logger.debug(f"Registered legacy command handler: {handler.__class__.__name__}")
        
    def unregister_handler(self, handler: CommandHandler) -> None:
        """Unregister a command handler"""
        if handler in self._handlers:
            self._handlers.remove(handler)
            self.logger.debug(f"Unregistered command handler: {handler.__class__.__name__}")
            
    def unregister_plugin(self, plugin_name: str) -> bool:
        """
        Unregister a command plugin by name.
        
        Args:
            plugin_name: Name of the plugin to unregister
            
        Returns:
            True if plugin was found and removed
        """
        for handler in self._handlers[:]:  # Create copy for safe iteration
            if (isinstance(handler, CommandPluginAdapter) and 
                hasattr(handler.plugin, 'name') and 
                handler.plugin.name == plugin_name):
                self._handlers.remove(handler)
                self.logger.info(f"Unregistered command plugin: {plugin_name}")
                return True
        return False
            
    def set_fallback_handler(self, handler: CommandHandler) -> None:
        """Set fallback handler for unrecognized commands"""
        self._fallback_handler = handler
        
    async def process(self, command: str, context: Context) -> CommandResult:
        """
        Process a command and return the result.
        
        Args:
            command: The command string to process
            context: Current conversation context
            
        Returns:
            CommandResult with the processing outcome
        """
        if not command.strip():
            return CommandResult.error_result("Empty command")
            
        self.logger.info(f"Processing command: '{command}'")
        
        # Update context with this command
        context.add_command(command)
        context.update_access_time()
        
        try:
            # Find the first handler that can handle this command
            for handler in self._handlers:
                if await handler.can_handle(command, context):
                    handler_name = (handler.plugin.name 
                                  if isinstance(handler, CommandPluginAdapter) and hasattr(handler.plugin, 'name')
                                  else handler.__class__.__name__)
                    self.logger.debug(f"Using handler: {handler_name}")
                    
                    result = await handler.handle(command, context)
                    
                    # Add interaction to context
                    if result.success and result.response:
                        context.add_conversation_entry({
                            "command": command,
                            "response": result.response
                        })
                        
                    return result
                    
            # No handler found, try fallback
            if self._fallback_handler:
                self.logger.debug("Using fallback handler")
                result = await self._fallback_handler.handle(command, context)
                
                if result.success and result.response:
                    context.add_conversation_entry({
                        "command": command,
                        "response": result.response
                    })
                    
                return result
                
            # No handler at all
            return CommandResult.error_result(f"Unknown command: {command}")
            
        except Exception as e:
            self.logger.error(f"Error processing command '{command}': {e}")
            return CommandResult.error_result(f"Command processing error: {str(e)}")
            
    def get_all_triggers(self) -> List[str]:
        """Get all triggers from registered handlers"""
        triggers = []
        for handler in self._handlers:
            if (isinstance(handler, CommandPluginAdapter) and 
                hasattr(handler.plugin, 'get_triggers')):
                triggers.extend(handler.plugin.get_triggers())
        return triggers
        
    def get_handler_count(self) -> int:
        """Get number of registered handlers"""
        return len(self._handlers)
        
    def list_handlers(self) -> List[str]:
        """Get list of handler names"""
        handlers = []
        for handler in self._handlers:
            if isinstance(handler, CommandPluginAdapter) and hasattr(handler.plugin, 'name'):
                handlers.append(f"Plugin: {handler.plugin.name}")
            else:
                handlers.append(f"Handler: {handler.__class__.__name__}")
        return handlers 