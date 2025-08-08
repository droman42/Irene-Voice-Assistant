"""
Output Manager - Manages multiple output targets

Coordinates different output targets and provides unified interface
for response delivery.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..core.metadata import EntryPointMetadata

logger = logging.getLogger(__name__)


class ComponentNotAvailable(Exception):
    """Exception raised when a required component is not available"""
    pass


@dataclass
class Response:
    """
    Response object containing text and metadata.
    
    Provides structure for responses with different output requirements.
    """
    text: str
    response_type: str = "text"  # text, tts, error, notification
    metadata: Optional[Dict[str, Any]] = None
    priority: int = 0  # Higher numbers = higher priority
    
    def __post_init__(self):
        """Initialize response after creation"""
        if self.metadata is None:
            self.metadata = {}


class OutputTarget(EntryPointMetadata, ABC):
    """
    Abstract base class for output targets.
    
    Provides unified interface for different output methods.
    """
    
    @abstractmethod
    async def send(self, response: Response) -> None:
        """Send response to output target"""
        pass
        
    @abstractmethod
    async def send_error(self, error: str) -> None:
        """Send error message to output target"""
        pass
        
    def is_available(self) -> bool:
        """Check if output target is available"""
        return True
        
    def get_output_type(self) -> str:
        """
        Get the type of output this target handles.
        
        Returns:
            Output type identifier (e.g., 'text', 'tts', 'web')
        """
        return "unknown"
        
    def supports_response_type(self, response_type: str) -> bool:
        """
        Check if this target supports a specific response type.
        
        Args:
            response_type: Type of response (text, tts, error, notification)
            
        Returns:
            True if target can handle this response type
        """
        return True
        
    def get_settings(self) -> Dict[str, Any]:
        """
        Get current output settings.
        
        Returns:
            Dictionary of current settings
        """
        return {}
        
    async def configure_output(self, **settings) -> None:
        """
        Configure output target settings.
        
        Args:
            **settings: Target-specific configuration options
        """
        pass
        
    async def test_output(self) -> bool:
        """
        Test if output target is working correctly.
        
        Returns:
            True if output test was successful
        """
        try:
            test_response = Response("Test output", response_type="test")
            await self.send(test_response)
            return True
        except Exception as e:
            logger.error(f"Output test failed: {e}")
            return False


class LegacyOutputTarget(ABC):
    """Legacy interface for backward compatibility - deprecated"""
    
    @abstractmethod
    async def send(self, text: str) -> None:
        """Send text to output target"""
        pass
        
    @abstractmethod
    async def send_error(self, error: str) -> None:
        """Send error message to output target"""
        pass
        
    @abstractmethod
    def is_available(self) -> bool:
        """Check if output target is available"""
        pass


class LegacyOutputAdapter(OutputTarget):
    """
    Adapter to make legacy OutputTarget work with new interface.
    
    Wraps legacy targets to provide new Response-based interface.
    """
    
    def __init__(self, legacy_target: LegacyOutputTarget):
        self.legacy_target = legacy_target
        self.logger = logging.getLogger(f"adapter.{legacy_target.__class__.__name__}")
        
    async def send(self, response: Response) -> None:
        """Adapt new Response to legacy text interface"""
        try:
            await self.legacy_target.send(response.text)
        except Exception as e:
            self.logger.error(f"Error in legacy output adapter: {e}")
            raise
            
    async def send_error(self, error: str) -> None:
        """Send error using legacy interface"""
        await self.legacy_target.send_error(error)
        
    def is_available(self) -> bool:
        """Check if legacy target is available"""
        return self.legacy_target.is_available()
        
    def get_output_type(self) -> str:
        """Get output type from legacy target"""
        return getattr(self.legacy_target, 'output_type', 'legacy')


class OutputManager:
    """
    Manages multiple output targets and coordinates response distribution.
    
    Features:
    - Multiple output target support
    - Response type routing
    - Target capability matching
    - Graceful degradation
    """
    
    def __init__(self, component_manager):
        self.component_manager = component_manager
        self._targets: dict[str, OutputTarget] = {}
        self._active_targets: list[str] = []
        self._primary_target: Optional[str] = None
        
    async def initialize(self) -> None:
        """Initialize the output manager"""
        
        # Try to load available output targets
        await self._discover_output_targets()
        
        logger.info("OutputManager initialized")
        
    async def _discover_output_targets(self) -> None:
        """Discover and initialize available output targets"""
        try:
            # Add text output (always available) - now using modern implementation
            from .text import TextOutput
            text_output = TextOutput()
            await self.add_target("text", text_output)
            
            # Try to add TTS output if available
            try:
                from .tts import TTSOutput
                tts_output = TTSOutput()
                if tts_output.is_available():
                    await self.add_target("tts", tts_output)
            except (ImportError, ComponentNotAvailable) as e:
                logger.info(f"TTS output not available: {e}")
                
            # Try to add web output if available
            try:
                from .web import WebOutput
                web_output = WebOutput()
                if web_output.is_available():
                    await self.add_target("web", web_output)
            except (ImportError, ComponentNotAvailable) as e:
                logger.info(f"Web output not available: {e}")
                
        except Exception as e:
            logger.error(f"Error discovering output targets: {e}")
        
    async def add_target(self, name: str, target: OutputTarget) -> None:
        """Add an output target"""
        if not target.is_available():
            logger.warning(f"Output target '{name}' is not available")
            return
            
        # No need for legacy adapter - modern targets implement OutputTarget directly
        self._targets[name] = target
        self._active_targets.append(name)
        
        # Set as primary if first target
        if not self._primary_target:
            self._primary_target = name
            
        logger.info(f"Added output target: {name} ({target.get_output_type()})")
        
    def set_primary_target(self, name: str) -> bool:
        """Set the primary output target"""
        if name in self._targets:
            self._primary_target = name
            logger.info(f"Set primary output target: {name}")
            return True
        return False
        
    async def send_response(self, text: str, response_type: str = "text", **metadata) -> None:
        """Send response to appropriate targets"""
        response = Response(
            text=text,
            response_type=response_type,
            metadata=metadata
        )
        await self.send_response_object(response)
        
    async def send_response_object(self, response: Response) -> None:
        """Send Response object to appropriate targets"""
        if not self._active_targets:
            logger.warning("No active output targets")
            return
            
        # Filter targets that support this response type
        compatible_targets = []
        for name in self._active_targets:
            target = self._targets[name]
            if target.supports_response_type(response.response_type):
                compatible_targets.append(name)
                
        if not compatible_targets:
            # Fallback to all targets if none specifically support the type
            compatible_targets = self._active_targets.copy()
            
        # Send to primary target first if it's compatible
        if self._primary_target and self._primary_target in compatible_targets:
            try:
                target = self._targets[self._primary_target]
                await target.send(response)
            except Exception as e:
                logger.error(f"Error sending to primary target '{self._primary_target}': {e}")
                
        # Send to other compatible targets
        for name in compatible_targets:
            if name != self._primary_target:
                try:
                    target = self._targets[name]
                    await target.send(response)
                except Exception as e:
                    logger.error(f"Error sending to target '{name}': {e}")
                    
    async def send_error(self, error: str) -> None:
        """Send error message to all active targets"""
        for name in self._active_targets:
            try:
                target = self._targets[name]
                await target.send_error(error)
            except Exception as e:
                logger.error(f"Error sending error to target '{name}': {e}")
                
    async def speak(self, text: str) -> None:
        """Send text to TTS targets specifically"""
        await self.send_response(text, response_type="tts")
        
    async def text_output(self, text: str) -> None:
        """Send text to text-only targets"""
        await self.send_response(text, response_type="text")
        
    def has_tts(self) -> bool:
        """Check if TTS component is available"""
        if self.component_manager:
            return self.component_manager.has_component("tts")
            
        # Check if any target supports TTS
        for target in self._targets.values():
            if target.get_output_type() == "tts" and target.is_available():
                return True
        return False
        
    def get_available_targets(self) -> List[str]:
        """Get list of available output target names"""
        return [name for name, target in self._targets.items() if target.is_available()]
        
    def get_active_targets(self) -> List[str]:
        """Get list of active output target names"""
        return self._active_targets.copy()
        
    def get_target_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific output target"""
        if name not in self._targets:
            return None
            
        target = self._targets[name]
        return {
            "name": name,
            "type": target.get_output_type(),
            "available": target.is_available(),
            "settings": target.get_settings()
        }
        
    async def close(self) -> None:
        """Close all output targets"""
        self._active_targets.clear()
        self._primary_target = None
        logger.info("OutputManager closed")
        
    @property
    def active_target_count(self) -> int:
        """Get number of active output targets"""
        return len(self._active_targets)
        
    @property
    def available_target_count(self) -> int:
        """Get number of available output targets"""
        return len([t for t in self._targets.values() if t is not None])
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Output targets deliver responses - minimal dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Output targets have no system dependencies - interface logic only"""
        return {
            "ubuntu": [],
            "alpine": [],
            "centos": [],
            "macos": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Output targets support all platforms"""
        return ["linux", "windows", "macos"] 