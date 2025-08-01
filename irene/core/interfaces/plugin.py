"""
Base Plugin Interface - Core plugin contracts

Defines the fundamental interface that all plugins must implement,
along with the plugin manager protocol.
"""

from typing import Optional, Protocol, Any
from abc import ABC, abstractmethod


class PluginInterface(ABC):
    """
    Base interface that all plugins must implement.
    
    This provides the fundamental contract for plugin lifecycle,
    metadata, and basic functionality.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name (unique identifier)"""
        pass
        
    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version string"""
        pass
        
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable plugin description"""
        pass
        
    @property
    def dependencies(self) -> list[str]:
        """List of required dependencies (plugin names)"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """List of optional dependencies"""
        return []
        
    async def initialize(self, core) -> None:
        """
        Initialize the plugin.
        
        Args:
            core: Reference to the AsyncVACore instance
        """
        pass
        
    async def shutdown(self) -> None:
        """Clean up plugin resources"""
        pass
        
    def get_config_schema(self) -> Optional[dict[str, Any]]:
        """Return plugin configuration schema (JSON Schema format)"""
        return None
        
    async def configure(self, config: dict[str, Any]) -> None:
        """Configure the plugin with provided settings"""
        pass


class PluginManager(Protocol):
    """
    Protocol defining the plugin manager interface.
    
    This allows different plugin manager implementations
    while maintaining a consistent interface.
    """
    
    async def load_plugin(self, plugin: PluginInterface) -> None:
        """Load and initialize a plugin"""
        ...
        
    async def unload_plugin(self, plugin_name: str) -> None:
        """Unload and cleanup a plugin"""
        ...
        
    async def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """Get a loaded plugin by name"""
        ...
        
    async def list_plugins(self) -> list[PluginInterface]:
        """List all loaded plugins"""
        ...
        
    async def reload_plugin(self, plugin_name: str) -> None:
        """Reload a plugin"""
        ... 