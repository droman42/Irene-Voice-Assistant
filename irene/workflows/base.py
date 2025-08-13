"""Base workflow class for orchestrating assistant operations."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncIterator, Optional, List

from ..intents.models import AudioData, ConversationContext, IntentResult
from ..core.metadata import EntryPointMetadata

logger = logging.getLogger(__name__)


class RequestContext:
    """Context for a single request through the workflow with client identification."""
    
    def __init__(self,
                 source: str = "unknown",
                 session_id: str = "default", 
                 wants_audio: bool = False,
                 skip_wake_word: bool = False,
                 metadata: Optional[Dict[str, Any]] = None,
                 client_id: Optional[str] = None,
                 room_name: Optional[str] = None,
                 device_context: Optional[Dict[str, Any]] = None,
                 language: str = "ru"):
        """
        Initialize request context with client identification support.
        
        Args:
            source: Source of the request (e.g., "microphone", "web", "cli", "esp32")
            session_id: Session identifier for context management
            wants_audio: Whether the response should include audio output
            skip_wake_word: Whether to skip wake word detection
            metadata: Additional request metadata
            client_id: Client/node identifier (e.g., "kitchen_node", "living_room_esp32")
            room_name: Human-readable room name (e.g., "Кухня", "Kitchen")
            device_context: Available devices and capabilities in this client context
            language: Primary language for this request (defaults to Russian)
        """
        self.source = source
        self.session_id = session_id
        self.wants_audio = wants_audio
        self.skip_wake_word = skip_wake_word
        self.metadata = metadata or {}
        
        # Client identification and context
        self.client_id = client_id
        self.room_name = room_name
        self.device_context = device_context or {}
        self.language = language
        
        # Merge client context into metadata for backward compatibility
        if client_id:
            self.metadata["client_id"] = client_id
        if room_name:
            self.metadata["room_name"] = room_name
        if device_context:
            self.metadata["device_context"] = device_context
        self.metadata["language"] = language


class Workflow(EntryPointMetadata, ABC):
    """Base class for all workflow implementations."""
    
    def __init__(self):
        """Initialize the workflow."""
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
        self.components: Dict[str, Any] = {}
        self.initialized = False
        
        # Pipeline stage configuration for conditional processing
        self._pipeline_stages = {
            "voice_trigger": True,
            "asr": True, 
            "text_processing": True,
            "nlu": True,
            "intent_execution": True,
            "tts": True
        }
    
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
    
    def configure_pipeline_stages(self, context: RequestContext) -> Dict[str, bool]:
        """
        Configure pipeline stages based on request context.
        
        This method determines which pipeline stages should be enabled
        based on the input type and request parameters. Supports the
        unified architecture with conditional stage skipping.
        
        Args:
            context: Request context with skip flags and input type
            
        Returns:
            Dictionary mapping stage names to enabled/disabled status
        """
        stages = self._pipeline_stages.copy()
        
        # Voice trigger stage - conditional based on context
        if context.skip_wake_word or context.source == "text":
            stages["voice_trigger"] = False
        
        # ASR stage - disabled for text input
        if context.source == "text":
            stages["asr"] = False
        
        # TTS stage - conditional based on wants_audio preference
        if not context.wants_audio:
            stages["tts"] = False
        
        return stages
    
    def is_stage_enabled(self, stage_name: str, context: RequestContext) -> bool:
        """
        Check if a specific pipeline stage is enabled for this context.
        
        Args:
            stage_name: Name of the pipeline stage
            context: Request context
            
        Returns:
            True if stage is enabled, False otherwise
        """
        configured_stages = self.configure_pipeline_stages(context)
        return configured_stages.get(stage_name, False)
    
    def get_enabled_stages(self, context: RequestContext) -> List[str]:
        """
        Get list of enabled pipeline stages for this context.
        
        Args:
            context: Request context
            
        Returns:
            List of enabled stage names
        """
        configured_stages = self.configure_pipeline_stages(context)
        return [stage for stage, enabled in configured_stages.items() if enabled]
    
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
    

    
    def __str__(self) -> str:
        """String representation of the workflow."""
        return f"<{self.name} initialized={self.initialized} components={len(self.components)}>"
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Workflows coordinate components - minimal direct dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Workflows have no system dependencies - coordinate components only"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Workflows support all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"] 