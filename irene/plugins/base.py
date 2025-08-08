"""
Base Plugin Classes - Common plugin functionality

Provides base classes with common functionality that plugin
developers can inherit from.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from abc import abstractmethod

from ..core.interfaces.plugin import PluginInterface
from ..core.interfaces.command import CommandPlugin
from ..core.context import Context
from ..core.commands import CommandResult
from ..core.metadata import EntryPointMetadata

logger = logging.getLogger(__name__)


class BasePlugin(EntryPointMetadata, PluginInterface):
    """
    Base plugin class with common functionality.
    
    Provides standard implementations for plugin lifecycle,
    logging, and configuration management.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"plugin.{self.name}")
        self._core = None
        self._config = {}
        self._initialized = False
        
    async def initialize(self, core) -> None:
        """Initialize the plugin with core reference"""
        self._core = core
        self._initialized = True
        self.logger.info(f"Plugin {self.name} initialized")
        
    async def shutdown(self) -> None:
        """Clean up plugin resources"""
        self._initialized = False
        self.logger.info(f"Plugin {self.name} shutdown")
        
    async def configure(self, config: dict[str, Any]) -> None:
        """Configure the plugin with settings"""
        # Default implementation - plugins can override
        pass
        
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)
        
    @property
    def is_initialized(self) -> bool:
        """Check if plugin is initialized"""
        return self._initialized
        
    @property
    def core(self):
        """Get reference to core engine"""
        return self._core


class BaseCommandPlugin(BasePlugin, CommandPlugin):
    """
    Base class for command plugins.
    
    Provides common command handling patterns and utilities.
    """
    
    def __init__(self):
        super().__init__()
        self._triggers = []
        
    async def can_handle(self, command: str, context: Context) -> bool:
        """Default implementation checks triggers"""
        command_lower = command.lower().strip()
        triggers = [trigger.lower() for trigger in self.get_triggers()]
        
        if self.supports_partial_matching():
            return any(trigger in command_lower for trigger in triggers)
        else:
            return any(command_lower.startswith(trigger) for trigger in triggers)
            
    def add_trigger(self, trigger: str) -> None:
        """Add a trigger word/phrase"""
        if trigger not in self._triggers:
            self._triggers.append(trigger)
            
    def remove_trigger(self, trigger: str) -> None:
        """Remove a trigger word/phrase"""
        if trigger in self._triggers:
            self._triggers.remove(trigger)
            
    def get_triggers(self) -> List[str]:
        """Get list of triggers"""
        return self._triggers.copy()
        
    async def handle_command(self, command: str, context: Context) -> CommandResult:
        """
        Default command handling with error catching.
        Subclasses should override _handle_command_impl
        """
        try:
            return await self._handle_command_impl(command, context)
        except Exception as e:
            self.logger.error(f"Error handling command '{command}': {e}")
            return CommandResult.error_result(f"Command failed: {str(e)}")
            
    @abstractmethod
    async def _handle_command_impl(self, command: str, context: Context) -> CommandResult:
        """Implementation method for command handling"""
        pass
        
    def extract_parameters(self, command: str, trigger: str) -> str:
        """Extract parameters from command after removing trigger"""
        command_lower = command.lower()
        trigger_lower = trigger.lower()
        
        if command_lower.startswith(trigger_lower):
            return command[len(trigger):].strip()
        return ""
        
    async def send_response(self, text: str) -> None:
        """Send response through core engine"""
        if self._core:
            await self._core.say(text)


class ConfigurablePlugin(BasePlugin):
    """
    Base class for plugins that need complex configuration.
    
    Provides configuration validation and schema support.
    """
    
    def __init__(self):
        super().__init__()
        self._config_schema = None
        
    def get_config_schema(self) -> Optional[Dict[str, Any]]:
        """Return configuration schema"""
        return self._config_schema
        
    def set_config_schema(self, schema: dict[str, Any]) -> None:
        """Set the configuration schema for validation"""
        self._config_schema = schema
        
    async def configure(self, config: dict[str, Any]) -> None:
        """Configure the plugin with validation"""
        if self._config_schema:
            self._validate_config(config)
        await super().configure(config)
        
    def _validate_config(self, config: dict[str, Any]) -> None:
        """Validate configuration against schema"""
        # Simple validation - could be extended with jsonschema
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")


class AsyncServicePlugin(BasePlugin):
    """
    Base class for plugins that run background services.
    
    Provides async task management and lifecycle.
    """
    
    def __init__(self):
        super().__init__()
        self._service_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def initialize(self, core) -> None:
        """Initialize and start service"""
        await super().initialize(core)
        await self.start_service()
        
    async def shutdown(self) -> None:
        """Stop service and cleanup"""
        await self.stop_service()
        await super().shutdown()
        
    async def start_service(self) -> None:
        """Start the background service"""
        if self._service_task is None:
            self._running = True
            self._service_task = asyncio.create_task(self._service_loop())
            self.logger.info(f"Started service for {self.name}")
            
    async def stop_service(self) -> None:
        """Stop the background service"""
        self._running = False
        
        if self._service_task:
            self._service_task.cancel()
            try:
                await self._service_task
            except asyncio.CancelledError:
                pass
            self._service_task = None
            self.logger.info(f"Stopped service for {self.name}")
            
    @abstractmethod
    async def _service_loop(self) -> None:
        """Service loop implementation"""
        pass
        
    @property
    def is_service_running(self) -> bool:
        """Check if service is running"""
        return self._service_task is not None and not self._service_task.done()
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Plugins extend functionality - minimal dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Plugins have no system dependencies - extension logic only"""
        return {
            "ubuntu": [],
            "alpine": [],
            "centos": [],
            "macos": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Plugins support all platforms"""
        return ["linux", "windows", "macos"] 