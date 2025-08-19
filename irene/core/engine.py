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
from .context import Context, ContextManager
from .timers import AsyncTimerManager

from .components import ComponentManager
from .workflow_manager import WorkflowManager

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
        self.component_manager = ComponentManager(config)
        self.plugin_manager = AsyncPluginManager()
        self.input_manager = InputManager(self.component_manager, config.inputs)
        self.context_manager = ContextManager()
        self.timer_manager = AsyncTimerManager()

        self.workflow_manager = WorkflowManager(self.component_manager)  # NEW: Unified workflow manager
        self._running = False
        
    async def start(self) -> None:
        """Initialize and start the assistant"""
        logger.info("Starting Irene Voice Assistant v13...")
        
        try:
            # Initialize components first - PASS CORE REFERENCE
            await self.component_manager.initialize_components(self)
            
            await self.context_manager.start()
            await self.timer_manager.start()
            await self.plugin_manager.initialize(self)
            
            # Initialize workflow manager with components
            await self.workflow_manager.initialize()
            
            # NOTE: Builtin plugin loading removed - functionality moved to intent handlers
            
            # Load external plugins
            await self.plugin_manager.load_plugins()
            
            await self.input_manager.initialize()
            
            self._running = True
            profile = self.component_manager.get_deployment_profile()
            logger.info(f"Irene started successfully in {profile} mode")
            
        except Exception as e:
            logger.error(f"Failed to start Irene: {e}")
            await self.stop()
            raise
            

            


        
    async def stop(self) -> None:
        """Graceful shutdown"""
        logger.info("Stopping Irene Voice Assistant...")
        
        self._running = False
        
        try:
            await self.timer_manager.stop()
            await self.context_manager.stop()
            await self.workflow_manager.cleanup()
            await self.input_manager.close()
            await self.plugin_manager.unload_all()
            await self.component_manager.shutdown_all()
            
            logger.info("Irene stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            
    @property
    def is_running(self) -> bool:
        """Check if the core engine is running"""
        return self._running 