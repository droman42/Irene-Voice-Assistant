"""
Component Management - Optional component loading and lifecycle

Handles optional components with graceful dependency checking,
automatic fallbacks, and component lifecycle management.
Enhanced with existing utilities from loader.py.
"""

import asyncio
import logging
from typing import Optional, Any, Type, TypeVar, Dict
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ..config.models import ComponentConfig, CoreConfig
from ..utils.loader import DependencyChecker, get_component_status
from ..components import (
    TTSComponent,
    ASRComponent, 
    LLMComponent,
    AudioComponent,
    VoiceTriggerComponent,
    NLUComponent,
    TextProcessorComponent,
    IntentComponent
)

logger = logging.getLogger(__name__)

T = TypeVar('T', bound='Component')


class ComponentNotAvailable(Exception):
    """Raised when optional component dependencies are missing"""
    pass



@dataclass
class ComponentInfo:
    """Information about a component's status and capabilities"""
    name: str
    available: bool
    initialized: bool = False
    error_message: Optional[str] = None
    dependencies: Optional[list[str]] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class Component(ABC):
    """
    Base class for all optional components.
    
    Provides lifecycle management and graceful dependency handling.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.initialized = False
        self.logger = logging.getLogger(f"component.{name}")
        
    @abstractmethod
    def get_dependencies(self) -> list[str]:
        """Return list of required Python modules"""
        pass
        
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the component"""
        pass
        
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown and cleanup the component"""
        pass
        
    def is_available(self) -> bool:
        """Check if component dependencies are available"""
        dependencies = self.get_dependencies()
        try:
            for dependency in dependencies:
                __import__(dependency)
            return True
        except ImportError:
            return False
        
    async def start(self) -> bool:
        """Start the component with error handling"""
        if not self.is_available():
            self.logger.warning(f"Component {self.name} dependencies not available")
            return False
            
        try:
            await self.initialize()
            self.initialized = True
            self.logger.info(f"Component {self.name} started successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start component {self.name}: {e}")
            return False
            
    async def stop(self) -> None:
        """Stop the component with cleanup"""
        if not self.initialized:
            return
            
        try:
            await self.shutdown()
            self.initialized = False
            self.logger.info(f"Component {self.name} stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping component {self.name}: {e}")


class ComponentManager:
    """
    Manages optional components with graceful dependency checking.
    
    Features:
    - Automatic component discovery using ComponentLoader
    - Dependency checking and graceful fallbacks
    - Component lifecycle management
    - Deployment profile detection
    - Enhanced with existing utilities from loader.py
    """
    
    def __init__(self, config: ComponentConfig):
        self.config = config
        self._components: dict[str, Component] = {}
        self._discovery_tasks: Optional[list[asyncio.Task]] = None
        self._initialized = False
        self.dependency_checker = DependencyChecker()  # From loader.py
    
    def get_available_components(self) -> Dict[str, Type]:
        """Get available components through existing entry-point discovery"""
        # Use EXISTING dynamic_loader instead of hardcoded dictionary
        from ..utils.loader import dynamic_loader
        return dynamic_loader.discover_providers("irene.components")
        
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status using loader.py utilities"""
        return get_component_status()  # From loader.py
        
    async def initialize_components(self, core) -> None:
        """Initialize all configured components using existing entry-point system"""
        if self._initialized:
            return
            
        logger.info("Initializing unified component system...")
        
        # Initialize all components using entry-point system
        await self._initialize_components_from_entrypoints(core)
        
        self._initialized = True
        
        # Log deployment profile
        profile = self.get_deployment_profile()
        logger.info(f"Components initialized. Deployment profile: {profile}")
    
    async def _initialize_components_from_entrypoints(self, core) -> None:
        """Initialize components using entry-point discovery"""
        # Use EXISTING entry-point discovery system
        available_components = self.get_available_components()
        
        for name, component_class in available_components.items():
            if self._is_component_enabled(name, core.config):
                try:
                    # Create component instance
                    component_instance = component_class()
                    
                    # Initialize with core reference
                    await component_instance.initialize(core)
                    
                    # Store in components dict
                    self._components[name] = component_instance
                    
                    logger.info(f"Initialized component '{name}' successfully")
                    
                except Exception as e:
                    logger.error(f"Failed to initialize component '{name}': {e}")

    def _is_component_enabled(self, component_name: str, config: CoreConfig) -> bool:
        """Check if component is enabled using its own config declaration"""
        from ..config.resolver import is_component_enabled_by_name
        return is_component_enabled_by_name(component_name, config)
        
    def has_component(self, name: str) -> bool:
        """Check if a component is available and initialized"""
        return name in self._components and self._components[name].initialized
        
    def get_component(self, name: str) -> Optional[Component]:
        """Get a component by name"""
        return self._components.get(name)
        
    def get_active_components(self) -> list[str]:
        """Get list of active (initialized) component names"""
        return list(self._components.keys())
    
    def get_components(self) -> Dict[str, Component]:
        """Get all component instances (NEW METHOD for WorkflowManager)"""
        return self._components.copy()
        
    def get_deployment_profile(self) -> str:
        """Auto-detect current deployment profile based on available components"""
        available = set(self._components.keys())
        
        # Detect profile based on modern component combinations
        if ("voice_trigger" in available and "nlu" in available and 
            "asr" in available and "tts" in available):
            return "Smart Voice Assistant"  # Complete modern system
        elif "tts" in available and "audio" in available and "asr" in available:
            return "Voice Assistant"  # Voice without wake word
        elif "llm" in available and "nlu" in available:
            return "Text Assistant"  # NLU + LLM processing
        elif available:
            return "Custom"
        else:
            return "Minimal"
            
    def get_component_info(self) -> dict[str, ComponentInfo]:
        """Get information about all initialized components"""
        info = {}
        
        # Only report on actually initialized components
        for name, component in self._components.items():
            info[name] = ComponentInfo(
                name=name,
                available=True,
                initialized=component.initialized,
                dependencies=component.get_dependencies()
            )
                
        return info
    
    async def shutdown_all(self) -> None:
        """Shutdown all components gracefully"""
        if not self._initialized:
            return
            
        logger.info("Shutting down components...")
        
        shutdown_tasks = []
        for component in self._components.values():
            task = asyncio.create_task(component.stop())
            shutdown_tasks.append(task)
            
        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
            
        self._components.clear()
        self._initialized = False
        logger.info("All components shutdown complete") 