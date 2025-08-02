"""
Async Plugin Manager - Non-blocking plugin management

Replaces the legacy synchronous plugin system with proper async
plugin loading, initialization, and lifecycle management.
"""

import asyncio
import logging
from typing import Optional, Set, Type, Union, TypeVar, Generic, Any, cast
from pathlib import Path

from ..core.interfaces.plugin import PluginInterface, PluginManager
from ..core.interfaces.command import CommandPlugin
from ..core.interfaces.tts import TTSPlugin
from ..core.interfaces.audio import AudioPlugin
from ..core.interfaces.input import InputPlugin
from ..core.interfaces.asr import ASRPlugin
from ..core.interfaces.llm import LLMPlugin
from .registry import PluginRegistry

logger = logging.getLogger(__name__)


class AsyncPluginManager:
    """
    Manages plugin lifecycle in an async-friendly way.
    
    Features:
    - Async plugin loading and initialization
    - Dependency resolution
    - Plugin categorization by interface
    - Graceful error handling with exception groups
    - Hot reloading support
    - Interface-compliant plugin management
    - Generic type support for Python 3.11
    """
    
    def __init__(self):
        self._plugins: dict[str, PluginInterface] = {}
        self._registry = PluginRegistry()
        self._core_reference = None
        self._loading_lock = asyncio.Lock()
        
        # Categorized plugin access
        self._command_plugins: list[CommandPlugin] = []
        self._tts_plugins: list[TTSPlugin] = []
        self._audio_plugins: list[AudioPlugin] = []
        self._input_plugins: list[InputPlugin] = []
        
    async def initialize(self, core) -> None:
        """Initialize the plugin manager with core reference"""
        self._core_reference = core
        logger.info("AsyncPluginManager initialized")
        
    # PluginManager Protocol Implementation
    async def load_plugin(self, plugin: PluginInterface) -> None:
        """Load and initialize a plugin instance (PluginManager protocol)"""
        try:
            # Check for name conflicts
            if plugin.name in self._plugins:
                logger.warning(f"Plugin '{plugin.name}' already loaded, skipping")
                return
                
            # Initialize plugin
            await plugin.initialize(self._core_reference)
            
            # Store plugin
            self._plugins[plugin.name] = plugin
            
            # Categorize plugin
            await self._categorize_plugin(plugin)
            
            logger.info(f"Loaded plugin: {plugin.name} v{plugin.version}")
            
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin.name}: {e}")
            raise
            
    async def unload_plugin(self, plugin_name: str) -> None:
        """Unload and cleanup a plugin (PluginManager protocol)"""
        if plugin_name not in self._plugins:
            raise ValueError(f"Plugin '{plugin_name}' not found")
            
        await self._unload_plugin_internal(plugin_name)
        
    async def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """Get a loaded plugin by name (PluginManager protocol)"""
        return self._plugins.get(plugin_name)
        
    async def list_plugins(self) -> list[PluginInterface]:
        """List all loaded plugins (PluginManager protocol)"""
        return list(self._plugins.values())
        
    async def reload_plugin(self, plugin_name: str) -> None:
        """Reload a plugin (PluginManager protocol)"""
        if plugin_name not in self._plugins:
            raise ValueError(f"Plugin '{plugin_name}' not found")
            
        # Get plugin class for reloading
        plugin_class = type(self._plugins[plugin_name])
        
        # Unload current instance
        await self.unload_plugin(plugin_name)
        
        # Create and load new instance
        new_plugin = plugin_class()
        await self.load_plugin(new_plugin)
        
    # Extended Plugin Management Methods
    async def load_plugins(self, plugin_paths: Optional[list[Path]] = None) -> None:
        """
        Load and initialize all plugins with exception groups.
        
        Args:
            plugin_paths: Optional list of paths to search for plugins
        """
        async with self._loading_lock:
            logger.info("Starting plugin loading...")
            
            try:
                # Discover plugins
                if plugin_paths:
                    for path in plugin_paths:
                        await self._registry.scan_directory(path)
                else:
                    # Load built-in plugins via registry
                    await self._load_builtin_plugins()
                    
                # Get discovered plugins
                discovered_plugins = await self._registry.get_discovered_plugins()
                
                # Resolve dependencies and load in order
                load_order = self._resolve_dependencies(discovered_plugins)
                
                # Load plugins with exception groups for better error handling
                await self._load_plugins_with_exception_groups(load_order)
                    
                logger.info(f"Loaded {len(self._plugins)} plugins successfully")
                
            except Exception as e:
                logger.error(f"Error loading plugins: {e}")
                raise

    async def _load_plugins_with_exception_groups(self, plugin_classes: list[Type[PluginInterface]]) -> None:
        """Load plugins with Python 3.11 exception groups for better error reporting"""
        errors = []
        
        for plugin_class in plugin_classes:
            try:
                await self._load_single_plugin(plugin_class)
            except Exception as e:
                errors.append(e)
                logger.error(f"Failed to load plugin {plugin_class.__name__}: {e}")
        
        # Use exception groups if any errors occurred
        if errors:
            raise ExceptionGroup("Plugin initialization failed", errors)

    async def _load_builtin_plugins(self) -> None:
        """Load built-in plugins using the registry system"""
        try:
            # Instead of scanning directory (which causes import issues), 
            # directly register builtin plugins from the dynamic registry
            from .builtin import get_builtin_plugins
            
            builtin_plugins = get_builtin_plugins()
            logger.info(f"Discovered {len(builtin_plugins)} builtin plugins")
            
            # Register each builtin plugin with the registry
            for plugin_name, plugin_class in builtin_plugins.items():
                try:
                    # Create temporary instance to extract metadata
                    temp_instance = plugin_class()
                    
                    # Register in our discovery registry
                    self._registry._discovered_plugins[plugin_name] = plugin_class
                    self._registry._plugin_metadata[plugin_name] = {
                        "name": temp_instance.name,
                        "version": temp_instance.version,
                        "description": temp_instance.description,
                        "dependencies": temp_instance.dependencies,
                        "optional_dependencies": temp_instance.optional_dependencies,
                        "class": plugin_class.__name__,
                        "module": plugin_class.__module__,
                        "file_path": f"builtin:{plugin_class.__module__}",
                        "config_schema": temp_instance.get_config_schema(),
                        # Additional metadata for discovery
                        "enabled_by_default": getattr(temp_instance, 'enabled_by_default', False),
                        "category": getattr(temp_instance, 'category', 'unknown'),
                        "platforms": getattr(temp_instance, 'platforms', [])
                    }
                    
                    logger.debug(f"Registered builtin plugin: {plugin_name}")
                    
                except Exception as e:
                    logger.warning(f"Failed to register builtin plugin {plugin_name}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error loading builtin plugins: {e}")
            raise
            
    async def _load_single_plugin(self, plugin_class: Type[PluginInterface]) -> None:
        """Load and initialize a single plugin class"""
        try:
            # Create plugin instance
            plugin = plugin_class()
            
            # Use the standard load_plugin method
            await self.load_plugin(plugin)
            
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_class.__name__}: {e}")
            raise
            
    async def _categorize_plugin(self, plugin: PluginInterface) -> None:
        """Categorize plugin by its interfaces"""
        if isinstance(plugin, CommandPlugin):
            self._command_plugins.append(plugin)
            
        if isinstance(plugin, TTSPlugin):
            self._tts_plugins.append(plugin)
            
        if isinstance(plugin, AudioPlugin):
            self._audio_plugins.append(plugin)
            
        if isinstance(plugin, InputPlugin):
            self._input_plugins.append(plugin)
            
    def _resolve_dependencies(self, plugins: list[Type[PluginInterface]]) -> list[Type[PluginInterface]]:
        """
        Resolve plugin dependencies and return load order.
        
        Args:
            plugins: List of plugin classes to resolve
            
        Returns:
            List of plugin classes in dependency order
        """
        # Simple topological sort for dependency resolution
        loaded = set()
        load_order = []
        remaining = {p.__name__: p for p in plugins}
        
        def can_load(plugin_class):
            try:
                plugin_instance = plugin_class()
                return all(dep in loaded for dep in plugin_instance.dependencies)
            except Exception:
                return True  # If we can't check dependencies, allow loading
            
        max_iterations = len(remaining) * 2  # Prevent infinite loops
        iteration = 0
        
        while remaining and iteration < max_iterations:
            ready_to_load = [
                name for name, plugin_class in remaining.items()
                if can_load(plugin_class)
            ]
            
            if not ready_to_load:
                # Break circular dependencies or missing dependencies
                logger.warning("Breaking circular dependency or missing dependency")
                ready_to_load = [next(iter(remaining.keys()))]
                
            for name in ready_to_load:
                plugin_class = remaining.pop(name)
                load_order.append(plugin_class)
                loaded.add(name)
                
            iteration += 1
                
        if remaining:
            logger.warning(f"Could not resolve dependencies for plugins: {list(remaining.keys())}")
                
        return load_order
        
    async def _unload_plugin_internal(self, plugin_name: str) -> bool:
        """Internal method to unload a specific plugin"""
        if plugin_name not in self._plugins:
            return False
            
        plugin = self._plugins[plugin_name]
        
        try:
            # Shutdown plugin
            await plugin.shutdown()
            
            # Remove from storage
            del self._plugins[plugin_name]
            
            # Remove from categories
            self._command_plugins = [p for p in self._command_plugins if p.name != plugin_name]
            self._tts_plugins = [p for p in self._tts_plugins if p.name != plugin_name]
            self._audio_plugins = [p for p in self._audio_plugins if p.name != plugin_name]
            self._input_plugins = [p for p in self._input_plugins if p.name != plugin_name]
            
            logger.info(f"Unloaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_name}: {e}")
            return False
            
    async def unload_all(self) -> None:
        """Unload all plugins"""
        plugin_names = list(self._plugins.keys())
        for name in plugin_names:
            await self._unload_plugin_internal(name)
            
    # Plugin access methods
    def get_plugin_sync(self, plugin_name: str) -> Optional[PluginInterface]:
        """Get a plugin by name (synchronous)"""
        return self._plugins.get(plugin_name)
        
    def get_command_plugins(self) -> list[CommandPlugin]:
        """Get all command handling plugins"""
        return self._command_plugins.copy()
        
    def get_tts_plugins(self) -> list[TTSPlugin]:
        """Get all TTS plugins"""
        return self._tts_plugins.copy()
        
    def get_audio_plugins(self) -> list[AudioPlugin]:
        """Get all audio plugins"""
        return self._audio_plugins.copy()
        
    def get_input_plugins(self) -> list[InputPlugin]:
        """Get all input plugins"""
        return self._input_plugins.copy()
        
    def list_plugins_sync(self) -> list[PluginInterface]:
        """Get all loaded plugins (synchronous)"""
        return list(self._plugins.values())
        
    def has_plugin(self, plugin_name: str) -> bool:
        """Check if a plugin is loaded"""
        return plugin_name in self._plugins
    
    # Typed plugin getters for better type safety
    def get_asr_plugin(self, plugin_name: str = "universal_asr") -> Optional[ASRPlugin]:
        """
        Get ASR plugin with proper typing
        
        Args:
            plugin_name: Name of the ASR plugin (default: "universal_asr")
            
        Returns:
            ASR plugin instance with transcribe_audio method, or None
        """
        plugin = self._plugins.get(plugin_name)
        # Runtime type check for safety - verify it has ASR capabilities
        if plugin and hasattr(plugin, 'transcribe_audio'):
            return cast(ASRPlugin, plugin)
        return None
    
    def get_llm_plugin(self, plugin_name: str = "universal_llm") -> Optional[LLMPlugin]:
        """
        Get LLM plugin with proper typing
        
        Args:
            plugin_name: Name of the LLM plugin (default: "universal_llm")
            
        Returns:
            LLM plugin instance with enhance_text method, or None
        """
        plugin = self._plugins.get(plugin_name)
        # Runtime type check for safety - verify it has LLM capabilities
        if plugin and hasattr(plugin, 'enhance_text'):
            return cast(LLMPlugin, plugin)  # Cast to Any for method access
        return None
    
    def get_tts_plugin(self, plugin_name: str = "universal_tts") -> Optional[TTSPlugin]:
        """
        Get TTS plugin with proper typing
        
        Args:
            plugin_name: Name of the TTS plugin (default: "universal_tts")
            
        Returns:
            TTS plugin instance with speak method, or None
        """
        plugin = self._plugins.get(plugin_name)
        # Runtime type check for safety - verify it has TTS capabilities
        if plugin and hasattr(plugin, 'speak'):
            return cast(TTSPlugin, plugin)
        return None
    
    def get_audio_plugin(self, plugin_name: str = "universal_audio") -> Optional[AudioPlugin]:
        """
        Get Audio plugin with proper typing
        
        Args:
            plugin_name: Name of the Audio plugin (default: "universal_audio")
            
        Returns:
            Audio plugin instance with play_stream method, or None
        """
        plugin = self._plugins.get(plugin_name)
        # Runtime type check for safety - verify it has Audio capabilities
        if plugin and hasattr(plugin, 'play_stream'):
            return cast(AudioPlugin, plugin)
        return None
        
    def get_plugin_info(self, plugin_name: str) -> Optional[dict]:
        """Get plugin metadata"""
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            return None
            
        return {
            "name": plugin.name,
            "version": plugin.version,
            "description": plugin.description,
            "dependencies": plugin.dependencies,
            "optional_dependencies": plugin.optional_dependencies,
            "initialized": getattr(plugin, 'is_initialized', None) or True,
            "interfaces": self._get_plugin_interfaces(plugin)
        }
        
    def _get_plugin_interfaces(self, plugin: PluginInterface) -> list[str]:
        """Get list of interfaces implemented by plugin"""
        interfaces = ["PluginInterface"]
        
        if isinstance(plugin, CommandPlugin):
            interfaces.append("CommandPlugin")
        if isinstance(plugin, TTSPlugin):
            interfaces.append("TTSPlugin")
        if isinstance(plugin, AudioPlugin):
            interfaces.append("AudioPlugin")
        if isinstance(plugin, InputPlugin):
            interfaces.append("InputPlugin")
            
        return interfaces
        
    @property
    def plugin_count(self) -> int:
        """Get number of loaded plugins"""
        return len(self._plugins)
        
    @property
    def registry(self) -> PluginRegistry:
        """Get access to plugin registry"""
        return self._registry


# Python 3.11 Generic Plugin Manager
T = TypeVar('T', bound=PluginInterface)


class GenericPluginManager(Generic[T]):
    """
    Generic plugin manager using Python 3.11 generics for type-safe plugin handling.
    
    Features:
    - Type-safe plugin operations
    - Generic plugin storage and retrieval
    - Compile-time type checking with mypy
    - Plugin interface constraints
    
    Example:
        command_manager = GenericPluginManager[CommandPlugin]()
        tts_manager = GenericPluginManager[TTSPlugin]()
    """
    
    def __init__(self):
        self._plugins: dict[str, T] = {}
        
    async def register(self, plugin: T) -> None:
        """Register a plugin of the generic type"""
        await plugin.initialize(None)  # Core reference would be injected
        self._plugins[plugin.name] = plugin
        
    async def unregister(self, plugin_name: str) -> bool:
        """Unregister a plugin by name"""
        if plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            await plugin.shutdown()
            del self._plugins[plugin_name]
            return True
        return False
        
    def get_plugin(self, plugin_name: str) -> Optional[T]:
        """Get a plugin by name with type safety"""
        return self._plugins.get(plugin_name)
        
    def get_plugins(self) -> list[T]:
        """Get all plugins with type safety"""
        return list(self._plugins.values())
        
    def has_plugin(self, plugin_name: str) -> bool:
        """Check if plugin exists"""
        return plugin_name in self._plugins
        
    @property
    def plugin_count(self) -> int:
        """Get number of registered plugins"""
        return len(self._plugins)
        
    def filter_plugins(self, predicate) -> list[T]:
        """Filter plugins with a predicate function"""
        return [plugin for plugin in self._plugins.values() if predicate(plugin)] 