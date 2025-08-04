"""Base workflow class for orchestrating assistant operations."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncIterator, Optional

from ..intents.models import AudioData, ConversationContext, IntentResult

logger = logging.getLogger(__name__)


class RequestContext:
    """Context for a single request through the workflow."""
    
    def __init__(self,
                 source: str = "unknown",
                 session_id: str = "default", 
                 wants_audio: bool = False,
                 skip_wake_word: bool = False,
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize request context.
        
        Args:
            source: Source of the request (e.g., "microphone", "web", "cli")
            session_id: Session identifier for context management
            wants_audio: Whether the response should include audio output
            skip_wake_word: Whether to skip wake word detection
            metadata: Additional request metadata
        """
        self.source = source
        self.session_id = session_id
        self.wants_audio = wants_audio
        self.skip_wake_word = skip_wake_word
        self.metadata = metadata or {}


class Workflow(ABC):
    """Base class for all workflow implementations."""
    
    def __init__(self):
        """Initialize the workflow."""
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
        self.components: Dict[str, Any] = {}
        self.initialized = False
    
    @abstractmethod
    async def initialize(self):
        """Initialize the workflow and its components."""
        pass
    
    @abstractmethod
    async def process_audio_stream(self, audio_stream: AsyncIterator[AudioData], context: RequestContext) -> AsyncIterator[IntentResult]:
        """
        Process an audio stream through the workflow.
        
        Args:
            audio_stream: Async iterator of audio data
            context: Request context
            
        Yields:
            IntentResult objects as they are generated
        """
        pass
    
    async def process_text_input(self, text: str, context: RequestContext) -> IntentResult:
        """
        Process text input through the workflow.
        
        Args:
            text: Input text to process
            context: Request context
            
        Returns:
            IntentResult from processing
        """
        # Default implementation - can be overridden
        raise NotImplementedError("Text processing not implemented for this workflow")
    
    def add_component(self, name: str, component: Any):
        """
        Add a component to the workflow.
        
        Args:
            name: Component name
            component: Component instance
        """
        self.components[name] = component
        self.logger.info(f"Added component '{name}' to workflow")
    
    def get_component(self, name: str) -> Optional[Any]:
        """
        Get a component by name.
        
        Args:
            name: Component name
            
        Returns:
            Component instance or None if not found
        """
        return self.components.get(name)
    
    async def shutdown(self):
        """Shutdown the workflow and clean up resources."""
        for name, component in self.components.items():
            if hasattr(component, 'shutdown'):
                try:
                    await component.shutdown()
                    self.logger.info(f"Shutdown component: {name}")
                except Exception as e:
                    self.logger.error(f"Error shutting down component {name}: {e}")
        
        self.initialized = False
        self.logger.info(f"Workflow {self.name} shutdown complete")
    
    async def is_healthy(self) -> bool:
        """
        Check if the workflow is healthy and ready to process requests.
        
        Returns:
            True if workflow is healthy
        """
        if not self.initialized:
            return False
        
        # Check component health
        for name, component in self.components.items():
            if hasattr(component, 'is_healthy'):
                try:
                    if not await component.is_healthy():
                        self.logger.warning(f"Component {name} is not healthy")
                        return False
                except Exception as e:
                    self.logger.error(f"Error checking health of component {name}: {e}")
                    return False
        
        return True
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get workflow capabilities.
        
        Returns:
            Dictionary describing workflow capabilities
        """
        capabilities = {
            "name": self.name,
            "initialized": self.initialized,
            "components": list(self.components.keys()),
            "supports_audio": hasattr(self, 'process_audio_stream'),
            "supports_text": hasattr(self, 'process_text_input')
        }
        
        # Add component capabilities
        component_caps = {}
        for name, component in self.components.items():
            if hasattr(component, 'get_capabilities'):
                try:
                    component_caps[name] = component.get_capabilities()
                except Exception as e:
                    component_caps[name] = {"error": str(e)}
            else:
                component_caps[name] = {"available": True}
        
        capabilities["component_capabilities"] = component_caps
        return capabilities
    
    async def _route_response(self, result: IntentResult, context: RequestContext):
        """
        Route the response to appropriate output channels.
        
        Args:
            result: The intent result to output
            context: Request context
        """
        # Text output (always available)
        if hasattr(self, 'text_output') and self.text_output:
            await self.text_output.send_text(result.text)
        
        # Audio output (if requested and available)
        if context.wants_audio and result.should_speak:
            if hasattr(self, 'tts') and self.tts:
                try:
                    await self.tts.speak(result.text)
                except Exception as e:
                    self.logger.error(f"TTS error: {e}")
            else:
                self.logger.warning("TTS requested but not available")
        
        # Web output (if source is web)
        if context.source == "web" and hasattr(self, 'web_output') and self.web_output:
            await self.web_output.send_response(result, context)
    
    def __str__(self) -> str:
        """String representation of the workflow."""
        return f"{self.name}(initialized={self.initialized}, components={len(self.components)})" 