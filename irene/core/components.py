"""
Component Management - Optional component loading and lifecycle

Handles optional components with graceful dependency checking,
automatic fallbacks, and component lifecycle management.
"""

import asyncio
import logging
from typing import Optional, Any, Type, TypeVar
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ..config.models import ComponentConfig

logger = logging.getLogger(__name__)

T = TypeVar('T', bound='Component')


class ComponentNotAvailable(Exception):
    """Raised when optional component dependencies are missing"""
    pass


class ComponentLoader:
    """
    Graceful component loading with dependency checking.
    
    Features:
    - Automatic dependency detection
    - Graceful fallback handling  
    - Component availability caching
    - Detailed error reporting
    - Optional component loading
    """
    
    _availability_cache: dict[str, bool] = {}
    _error_cache: dict[str, str] = {}
    
    @classmethod
    def is_available(cls, component_name: str, dependencies: list[str]) -> bool:
        """
        Check if component dependencies are available.
        
        Args:
            component_name: Name of the component for caching
            dependencies: List of module names to check
            
        Returns:
            True if all dependencies are available
        """
        if component_name in cls._availability_cache:
            return cls._availability_cache[component_name]
            
        try:
            for dependency in dependencies:
                __import__(dependency)
            cls._availability_cache[component_name] = True
            return True
            
        except ImportError as e:
            error_msg = f"Missing dependencies for {component_name}: {e}"
            cls._error_cache[component_name] = error_msg
            cls._availability_cache[component_name] = False
            logger.debug(error_msg)
            return False
    
    @classmethod
    def load_microphone_component(cls) -> Optional['MicrophoneComponent']:
        """Load microphone component with graceful fallback"""
        if cls.is_available("microphone", ["vosk", "sounddevice"]):
            try:
                return MicrophoneComponent()
            except Exception as e:
                logger.warning(f"Failed to create MicrophoneComponent: {e}")
                return None
        return None
    
    @classmethod
    def load_tts_component(cls) -> Optional['TTSComponent']:
        """Load TTS component with graceful fallback"""
        if cls.is_available("tts", ["pyttsx3"]):
            try:
                return TTSComponent()
            except Exception as e:
                logger.warning(f"Failed to create TTSComponent: {e}")
                return None
        return None
    
    @classmethod  
    def load_audio_output_component(cls) -> Optional['AudioOutputComponent']:
        """Load audio output component with graceful fallback"""
        if cls.is_available("audio_output", ["sounddevice", "soundfile"]):
            try:
                return AudioOutputComponent()
            except Exception as e:
                logger.warning(f"Failed to create AudioOutputComponent: {e}")
                return None
        return None
    
    @classmethod
    def load_web_api_component(cls) -> Optional['WebAPIComponent']:
        """Load web API component with graceful fallback"""
        if cls.is_available("web_api", ["fastapi", "uvicorn"]):
            try:
                return WebAPIComponent()
            except Exception as e:
                logger.warning(f"Failed to create WebAPIComponent: {e}")
                return None
        return None
    
    @classmethod
    def get_availability_report(cls) -> dict[str, Any]:
        """Get detailed component availability report"""
        return {
            "availability": cls._availability_cache.copy(),
            "errors": cls._error_cache.copy(),
            "checked_components": list(cls._availability_cache.keys())
        }
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear availability cache (useful for testing)"""
        cls._availability_cache.clear()
        cls._error_cache.clear()


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
        return ComponentLoader.is_available(self.name, self.get_dependencies())
        
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


class MicrophoneComponent(Component):
    """Microphone input component using VOSK and sounddevice"""
    
    def __init__(self):
        super().__init__("microphone")
        self._device = None
        self._stream = None
        
    def get_dependencies(self) -> list[str]:
        return ["vosk", "sounddevice", "soundfile"]
        
    async def initialize(self) -> None:
        """Initialize microphone with VOSK model"""
        if not self.is_available():
            raise ComponentNotAvailable("Microphone dependencies not available")
            
        # Dynamic imports
        import sounddevice as sd
        import vosk
        
        # Initialize VOSK model (would need actual model path)
        self.logger.info("Microphone component initialized")
        
    async def shutdown(self) -> None:
        """Cleanup microphone resources"""
        if self._stream:
            self._stream.stop()
            self._stream.close()
        self.logger.info("Microphone component shutdown")


class TTSComponent(Component):
    """Text-to-speech component using pyttsx3"""
    
    def __init__(self):
        super().__init__("tts")
        self._engine = None
        
    def get_dependencies(self) -> list[str]:
        return ["pyttsx3"]
        
    async def initialize(self) -> None:
        """Initialize TTS engine"""
        if not self.is_available():
            raise ComponentNotAvailable("TTS dependencies not available")
            
        # Dynamic import
        import pyttsx3
        
        self._engine = pyttsx3.init()
        self.logger.info("TTS component initialized")
        
    async def shutdown(self) -> None:
        """Cleanup TTS resources"""
        if self._engine:
            self._engine.stop()
        self.logger.info("TTS component shutdown")
        
    async def speak(self, text: str) -> None:
        """Speak text using TTS engine"""
        if not self.initialized or not self._engine:
            raise ComponentNotAvailable("TTS component not initialized")
            
        # Non-blocking TTS call
        await asyncio.to_thread(self._engine.say, text)
        await asyncio.to_thread(self._engine.runAndWait)


class AudioOutputComponent(Component):
    """Audio output component using sounddevice"""
    
    def __init__(self):
        super().__init__("audio_output")
        
    def get_dependencies(self) -> list[str]:
        return ["sounddevice", "soundfile"]
        
    async def initialize(self) -> None:
        """Initialize audio output"""
        if not self.is_available():
            raise ComponentNotAvailable("Audio output dependencies not available")
            
        # Dynamic imports
        import sounddevice as sd
        import soundfile as sf
        
        self.logger.info("Audio output component initialized")
        
    async def shutdown(self) -> None:
        """Cleanup audio resources"""
        self.logger.info("Audio output component shutdown")


class WebAPIComponent(Component):
    """Web API component using FastAPI and uvicorn"""
    
    def __init__(self):
        super().__init__("web_api")
        self._app = None
        self._server = None
        
    def get_dependencies(self) -> list[str]:
        return ["fastapi", "uvicorn"]
        
    async def initialize(self) -> None:
        """Initialize FastAPI application"""
        if not self.is_available():
            raise ComponentNotAvailable("Web API dependencies not available")
            
        # Dynamic imports
        from fastapi import FastAPI
        import uvicorn
        
        self._app = FastAPI(title="Irene Voice Assistant API")
        self.logger.info("Web API component initialized")
        
    async def shutdown(self) -> None:
        """Shutdown web server"""
        if self._server:
            self._server.shutdown()
        self.logger.info("Web API component shutdown")


class ComponentManager:
    """
    Manages optional components with graceful dependency checking.
    
    Features:
    - Automatic component discovery using ComponentLoader
    - Dependency checking and graceful fallbacks
    - Component lifecycle management
    - Deployment profile detection
    """
    
    def __init__(self, config: ComponentConfig):
        self.config = config
        self._components: dict[str, Component] = {}
        self._discovery_tasks: Optional[list[asyncio.Task]] = None
        self._initialized = False
        
    async def initialize_components(self) -> None:
        """Initialize all configured components using ComponentLoader"""
        if self._initialized:
            return
            
        logger.info("Initializing components...")
        
        # Use ComponentLoader for graceful loading
        component_loaders = {
            "microphone": (self.config.microphone, ComponentLoader.load_microphone_component),
            "tts": (self.config.tts, ComponentLoader.load_tts_component),
            "audio_output": (self.config.audio_output, ComponentLoader.load_audio_output_component),
            "web_api": (self.config.web_api, ComponentLoader.load_web_api_component),
        }
        
        # Load and start components concurrently
        initialization_tasks = []
        
        for component_name, (enabled, loader_func) in component_loaders.items():
            if enabled:
                task = asyncio.create_task(self._initialize_single_component(component_name, loader_func))
                initialization_tasks.append(task)
        
        # Wait for all components to initialize
        if initialization_tasks:
            results = await asyncio.gather(*initialization_tasks, return_exceptions=True)
            
            # Log results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"Component initialization failed: {result}")
        
        self._initialized = True
        
        # Log deployment profile
        profile = self.get_deployment_profile()
        logger.info(f"Components initialized. Deployment profile: {profile}")
        
    async def _initialize_single_component(self, name: str, loader_func) -> None:
        """Initialize a single component with error handling"""
        try:
            component = loader_func()
            if component:
                success = await component.start()
                if success:
                    self._components[name] = component
                    logger.info(f"Component '{name}' loaded successfully")
                else:
                    logger.warning(f"Component '{name}' failed to start")
            else:
                logger.info(f"Component '{name}' not available (dependencies missing)")
                
        except Exception as e:
            logger.error(f"Error initializing component '{name}': {e}")
    
    def has_component(self, name: str) -> bool:
        """Check if a component is available and initialized"""
        return name in self._components and self._components[name].initialized
        
    def get_component(self, name: str) -> Optional[Component]:
        """Get a component by name"""
        return self._components.get(name)
        
    def get_deployment_profile(self) -> str:
        """Auto-detect current deployment profile based on available components"""
        available = set(self._components.keys())
        
        if "microphone" in available and "tts" in available and "web_api" in available:
            return "Voice Assistant"
        elif "web_api" in available:
            return "API Server"
        elif available:
            return "Custom"
        else:
            return "Headless"
            
    def get_component_info(self) -> dict[str, ComponentInfo]:
        """Get information about all components"""
        info = {}
        
        # Check configured components
        component_configs = {
            "microphone": self.config.microphone,
            "tts": self.config.tts, 
            "audio_output": self.config.audio_output,
            "web_api": self.config.web_api,
        }
        
        for name, enabled in component_configs.items():
            component = self._components.get(name)
            
            if component:
                info[name] = ComponentInfo(
                    name=name,
                    available=True,
                    initialized=component.initialized,
                    dependencies=component.get_dependencies()
                )
            else:
                # Check availability even if not loaded
                loader_map = {
                    "microphone": ["vosk", "sounddevice"],
                    "tts": ["pyttsx3"],
                    "audio_output": ["sounddevice", "soundfile"],
                    "web_api": ["fastapi", "uvicorn"],
                }
                
                dependencies = loader_map.get(name, [])
                available = ComponentLoader.is_available(name, dependencies)
                error_msg = None if available else ComponentLoader._error_cache.get(name)
                
                info[name] = ComponentInfo(
                    name=name,
                    available=available,
                    initialized=False,
                    error_message=error_msg,
                    dependencies=dependencies
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