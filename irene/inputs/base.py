"""
Input Manager - Manages multiple input sources

Coordinates different input sources and provides unified interface
for the core engine.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncIterator, Union
from abc import ABC, abstractmethod

from ..core.metadata import EntryPointMetadata
from ..intents.models import AudioData

logger = logging.getLogger(__name__)

# Type alias for input data - can be text commands or raw audio data
InputData = Union[str, AudioData]


class ComponentNotAvailable(Exception):
    """Exception raised when a required component is not available"""
    pass


class InputSource(EntryPointMetadata, ABC):
    """
    Abstract base class for input sources.
    
    Provides async iterator interface for command streams.
    """
    
    @abstractmethod
    def listen(self) -> AsyncIterator[InputData]:
        """
        Start listening for input and yield data as it arrives.
        
        Yields:
            InputData - either text commands (str) or audio data (AudioData)
            - CLI/Web text: str
            - Microphone: AudioData
            - Web audio: Could be either
        """
        # This is an async generator method
        # Implementations should use: async def listen(self) -> AsyncIterator[InputData]:
        # with yield statements inside
        return
        yield  # This makes it an async generator
        
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
        Get the type of input this source handles.
        
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


class LegacyInputSource(ABC):
    """Legacy interface for backward compatibility - deprecated"""
    
    @abstractmethod
    async def get_command(self) -> Optional[str]:
        """Get the next command (non-blocking, returns None if no command available)"""
        pass
        
    @abstractmethod
    async def start(self) -> None:
        """Start the input source"""
        pass
        
    @abstractmethod
    async def stop(self) -> None:
        """Stop the input source"""
        pass
        
    @abstractmethod
    def is_available(self) -> bool:
        """Check if input source is available"""
        pass


class LegacyInputAdapter(InputSource):
    """
    Adapter to make legacy InputSource work with new interface.
    
    Wraps legacy sources to provide new AsyncIterator interface.
    """
    
    def __init__(self, legacy_source: LegacyInputSource):
        self.legacy_source = legacy_source
        self._listening = False
        self.logger = logging.getLogger(f"adapter.{legacy_source.__class__.__name__}")
        
    async def listen(self) -> AsyncIterator[InputData]:
        """Adapt legacy get_command to async iterator"""
        while self._listening:
            try:
                command = await self.legacy_source.get_command()
                if command and command.strip():
                    yield command.strip()
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error in legacy input adapter: {e}")
                break
                
    async def start_listening(self) -> None:
        """Start the legacy source"""
        await self.legacy_source.start()
        self._listening = True
        
    async def stop_listening(self) -> None:
        """Stop the legacy source"""
        self._listening = False
        await self.legacy_source.stop()
        
    def is_listening(self) -> bool:
        """Check if adapter is listening"""
        return self._listening
        
    def is_available(self) -> bool:
        """Check if legacy source is available"""
        return self.legacy_source.is_available()
        
    def get_input_type(self) -> str:
        """Get input type from legacy source"""
        return getattr(self.legacy_source, 'input_type', 'legacy')


class InputManager:
    """
    Manages multiple input sources and coordinates input collection.
    
    Features:
    - Multiple input source support
    - Automatic source discovery
    - Non-blocking input collection
    - Graceful component handling
    """
    
    def __init__(self, component_manager):
        self.component_manager = component_manager
        self._sources: dict[str, InputSource] = {}
        self._active_sources: list[str] = []
        self._listen_tasks: dict[str, asyncio.Task] = {}
        self._input_queue = asyncio.Queue()
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self) -> None:
        """Initialize the input manager"""
        self._running = True
        
        # Try to load available input sources
        await self._discover_input_sources()
        
        logger.info("InputManager initialized")
        
    async def _discover_input_sources(self) -> None:
        """Discover available input sources without plugin injection (separation of concerns)"""
        try:
            # Add CLI input (always available)
            from .cli import CLIInput
            cli_input = CLIInput()
            await self.add_source("cli", cli_input)
            
            # Try to add microphone input (pure audio capture)
            try:
                from .microphone import MicrophoneInput
                mic_input = MicrophoneInput()  # No plugin injection
                if mic_input.is_available():
                    await self.add_source("microphone", mic_input)
            except (ImportError, ComponentNotAvailable) as e:
                logger.info(f"Microphone input not available: {e}")
                
            # Try to add web input (pure command/audio capture)
            try:
                from .web import WebInput
                web_input = WebInput()  # No core reference injection
                if web_input.is_available():
                    await self.add_source("web", web_input)
            except (ImportError, ComponentNotAvailable) as e:
                logger.info(f"Web input not available: {e}")
                
        except Exception as e:
            logger.error(f"Error discovering input sources: {e}")
        
    async def add_source(self, name: str, source: InputSource) -> None:
        """Add an input source"""
        if not source.is_available():
            logger.warning(f"Input source '{name}' is not available")
            return
            
        # No need for legacy adapter - modern sources implement InputSource directly
        self._sources[name] = source
        logger.info(f"Added input source: {name} ({source.get_input_type()})")
        
    async def start_source(self, name: str) -> bool:
        """Start a specific input source"""
        if name not in self._sources:
            logger.warning(f"Input source '{name}' not found")
            return False
            
        try:
            source = self._sources[name]
            await source.start_listening()
            
            if name not in self._active_sources:
                self._active_sources.append(name)
                
            # Start listening task for this source
            if name not in self._listen_tasks:
                self._listen_tasks[name] = asyncio.create_task(
                    self._listen_to_source(name, source)
                )
                
            logger.info(f"Started input source: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start input source '{name}': {e}")
            return False
            
    async def stop_source(self, name: str) -> bool:
        """Stop a specific input source"""
        if name not in self._active_sources:
            return False
            
        try:
            source = self._sources[name]
            await source.stop_listening()
            
            # Cancel listening task
            if name in self._listen_tasks:
                self._listen_tasks[name].cancel()
                try:
                    await self._listen_tasks[name]
                except asyncio.CancelledError:
                    pass
                del self._listen_tasks[name]
                
            self._active_sources.remove(name)
            logger.info(f"Stopped input source: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop input source '{name}': {e}")
            return False
            
    async def _listen_to_source(self, source_name: str, source: InputSource) -> None:
        """Listen to a specific source using async iterator"""
        try:
            async for data in source.listen():
                if data:
                    # Handle different input data types
                    if isinstance(data, str) and data.strip():
                        await self._input_queue.put((source_name, data.strip()))
                    elif isinstance(data, AudioData):
                        await self._input_queue.put((source_name, data))
                    # Note: AudioData objects are passed through directly to workflow for processing
                    
        except asyncio.CancelledError:
            logger.debug(f"Listening cancelled for source: {source_name}")
        except Exception as e:
            logger.error(f"Error listening to source '{source_name}': {e}")
            
    async def start_all_sources(self) -> None:
        """Start all available input sources"""
        for name in list(self._sources.keys()):
            await self.start_source(name)
            
    async def get_next_input(self) -> tuple[str, InputData]:
        """
        Get the next input data.
        
        Returns:
            Tuple of (source_name, input_data) where input_data can be str or AudioData
        """
        return await self._input_queue.get()
        
    def get_available_sources(self) -> List[str]:
        """Get list of available input source names"""
        return [name for name, source in self._sources.items() if source.is_available()]
        
    def get_active_sources(self) -> List[str]:
        """Get list of active input source names"""
        return self._active_sources.copy()
        
    def get_source_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific input source"""
        if name not in self._sources:
            return None
            
        source = self._sources[name]
        return {
            "name": name,
            "type": source.get_input_type(),
            "available": source.is_available(),
            "listening": source.is_listening(),
            "settings": source.get_settings()
        }
        
    async def close(self) -> None:
        """Close all input sources"""
        self._running = False
        
        # Stop all sources
        for name in list(self._active_sources):
            await self.stop_source(name)
            
        # Cancel any remaining tasks
        for task in self._listen_tasks.values():
            task.cancel()
            
        logger.info("InputManager closed")
        
    @property
    def active_source_count(self) -> int:
        """Get number of active input sources"""
        return len(self._active_sources)
        
    @property
    def available_source_count(self) -> int:
        """Get number of available input sources"""
        return len([s for s in self._sources.values() if s is not None])
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Input sources provide user interface - minimal dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Input sources have no system dependencies - interface logic only"""
        return {
            "ubuntu": [],
            "alpine": [],
            "centos": [],
            "macos": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Input sources support all platforms"""
        return ["linux", "windows", "macos"] 