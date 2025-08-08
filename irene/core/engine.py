"""
AsyncVACore - The main async voice assistant engine

This is the heart of Irene v13, providing non-blocking command processing
with optional audio/TTS components.
"""

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass

from ..config.models import CoreConfig, ComponentConfig
from ..plugins.manager import AsyncPluginManager
from ..inputs.base import InputManager
from ..outputs.base import OutputManager
from .context import Context, ContextManager
from .timers import AsyncTimerManager
from .commands import CommandProcessor, CommandResult
from .components import ComponentManager

logger = logging.getLogger(__name__)


class AsyncVACore:
    """
    Modern async voice assistant core engine.
    
    Features:
    - Non-blocking command processing
    - Optional audio/TTS components
    - Plugin system with dependency injection
    - Concurrent request handling
    """
    
    def __init__(self, config: CoreConfig):
        self.config = config
        self.component_manager = ComponentManager(config.components)
        self.plugin_manager = AsyncPluginManager()
        self.input_manager = InputManager(self.component_manager)
        self.output_manager = OutputManager(self.component_manager)
        self.context_manager = ContextManager()
        self.timer_manager = AsyncTimerManager()
        self.command_processor = CommandProcessor()
        self._running = False
        
    async def start(self) -> None:
        """Initialize and start the assistant"""
        logger.info("Starting Irene Voice Assistant v13...")
        
        try:
            # Initialize components first
            await self.component_manager.initialize_components()
            
            await self.context_manager.start()
            await self.timer_manager.start()
            await self.plugin_manager.initialize(self)
            
            # Load builtin plugins
            await self._load_builtin_plugins()
            
            # Load external plugins
            await self.plugin_manager.load_plugins()
            
            await self.input_manager.initialize()
            await self.output_manager.initialize()
            
            self._running = True
            profile = self.component_manager.get_deployment_profile()
            logger.info(f"Irene started successfully in {profile} mode")
            
        except Exception as e:
            logger.error(f"Failed to start Irene: {e}")
            await self.stop()
            raise
            
    async def _load_builtin_plugins(self) -> None:
        """Load builtin plugins using the unified plugin manager system"""
        try:
            logger.info("Loading builtin plugins via plugin manager...")
            
            # Use plugin manager's unified loading system
            await self.plugin_manager.load_plugins()
            
            # Get loaded plugins from plugin manager
            loaded_plugins = list(self.plugin_manager._plugins.values())
            
            # Filter plugins based on configuration
            builtin_config = getattr(self.config.plugins, 'builtin_plugins', {})
            
            enabled_plugins = []
            for plugin in loaded_plugins:
                plugin_name = plugin.__class__.__name__
                if builtin_config.get(plugin_name, False):
                    enabled_plugins.append(plugin)
                    logger.info(f"Enabled builtin plugin: {plugin_name}")
                else:
                    # Remove disabled plugins from plugin manager
                    if plugin.name in self.plugin_manager._plugins:
                        await self.plugin_manager.unload_plugin(plugin.name)
                    logger.debug(f"Builtin plugin disabled in config: {plugin_name}")
            
            # Register enabled plugins with command processor
            for plugin in enabled_plugins:
                try:
                    # Register command plugins with command processor
                    if hasattr(plugin, 'get_triggers') and hasattr(plugin, 'can_handle'):
                        self.command_processor.register_plugin(plugin)
                        
                    logger.info(f"Registered builtin plugin: {plugin.name}")
                    
                except Exception as e:
                    logger.error(f"Failed to register builtin plugin {plugin.name}: {e}")
                    continue
                
        except Exception as e:
            logger.error(f"Failed to load builtin plugins: {e}")
            raise
            
    async def process_command(self, command: str, context: Optional[Context] = None) -> None:
        """Main command processing pipeline"""
        if not self._running:
            raise RuntimeError("Core engine not started")
            
        try:
            # Create context if not provided
            if context is None:
                context = self.context_manager.create_context()
                
            # Parse and execute command asynchronously
            result = await self.command_processor.process(command, context)
            
            if result.response:
                await self._send_response(result.response)
                
        except Exception as e:
            logger.error(f"Error processing command '{command}': {e}")
            await self._handle_error(e)
            
    async def say(self, text: str) -> None:
        """Send text to TTS output (if available)"""
        if self.component_manager.has_component("tts"):
            await self.output_manager.speak(text)
        else:
            await self.output_manager.text_output(text)
            
    async def _send_response(self, response: str) -> None:
        """Send response through configured output channels"""
        await self.output_manager.send_response(response)
        
    async def _handle_error(self, error: Exception) -> None:
        """Handle errors gracefully"""
        error_msg = f"Error: {str(error)}"
        await self.output_manager.send_error(error_msg)
        
    async def stop(self) -> None:
        """Graceful shutdown"""
        logger.info("Stopping Irene Voice Assistant...")
        
        self._running = False
        
        try:
            await self.timer_manager.stop()
            await self.context_manager.stop()
            await self.input_manager.close()
            await self.output_manager.close()
            await self.plugin_manager.unload_all()
            await self.component_manager.shutdown_all()
            
            logger.info("Irene stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            
    @property
    def is_running(self) -> bool:
        """Check if the core engine is running"""
        return self._running 