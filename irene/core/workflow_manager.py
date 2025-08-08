"""
Workflow Manager - Coordinates workflows with input sources

This manager handles the coordination between input sources and workflows,
supporting both voice assistant mode (with wake words) and continuous mode.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, AsyncIterator
from enum import Enum

from ..workflows.base import Workflow, RequestContext
from ..workflows.voice_assistant import VoiceAssistantWorkflow
from ..workflows.continuous_listening import ContinuousListeningWorkflow
from ..intents.models import AudioData, IntentResult
from ..inputs.base import InputSource
from ..utils.audio_helpers import validate_audio_file
from ..config.manager import ConfigurationError

logger = logging.getLogger(__name__)


class WorkflowMode(Enum):
    """Available workflow modes"""
    VOICE_ASSISTANT = "voice_assistant"       # With wake word detection
    CONTINUOUS_LISTENING = "continuous"       # Direct ASR processing
    TEXT_ONLY = "text_only"                  # Text input only


class WorkflowManager:
    """
    Manages workflow execution and input coordination.
    
    Provides the interface for starting different workflow modes
    and coordinating them with input sources.
    """
    
    def __init__(self, component_manager):
        self.component_manager = component_manager
        self.workflows: Dict[str, Workflow] = {}
        self.active_workflow: Optional[Workflow] = None
        self.active_mode: Optional[WorkflowMode] = None
        self.input_manager = None
        self._workflow_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self) -> None:
        """Initialize the workflow manager with available workflows"""
        logger.info("Initializing WorkflowManager...")
        
        # Create workflow instances
        await self._create_workflows()
        
        logger.info(f"WorkflowManager initialized with workflows: {list(self.workflows.keys())}")
        
    async def _create_workflows(self) -> None:
        """Create and initialize workflow instances"""
        try:
            # Create VoiceAssistantWorkflow
            voice_workflow = VoiceAssistantWorkflow()
            await self._inject_components(voice_workflow)
            self.workflows["voice_assistant"] = voice_workflow
            
            # Create ContinuousListeningWorkflow  
            continuous_workflow = ContinuousListeningWorkflow()
            await self._inject_components(continuous_workflow)
            self.workflows["continuous"] = continuous_workflow
            
            logger.info("Created workflow instances")
            
        except Exception as e:
            logger.error(f"Failed to create workflows: {e}")
            raise ConfigurationError(f"Workflow creation failed: {e}")
    
    async def _inject_components(self, workflow: Workflow) -> None:
        """Inject required components into a workflow"""
        try:
            # Get components from component manager
            components = await self.component_manager.get_available_components()
            
            # Inject components into workflow
            for name, component in components.items():
                workflow.add_component(name, component)
            
            # NEW: Inject intent orchestrator from IntentComponent if available
            intent_component = self.component_manager.get_component('intent_system')
            if intent_component and hasattr(intent_component, 'get_orchestrator'):
                intent_orchestrator = intent_component.get_orchestrator()
                if intent_orchestrator:
                    workflow.add_component('intent_orchestrator', intent_orchestrator)
                    logger.debug("Injected intent_orchestrator from IntentComponent")
            
            # Also inject the context manager if available
            if hasattr(self.component_manager, 'context_manager'):
                workflow.add_component('context_manager', self.component_manager.context_manager)
                
            logger.debug(f"Injected {len(workflow.components)} components into {workflow.name}")
            
        except Exception as e:
            logger.error(f"Component injection failed for {workflow.name}: {e}")
            raise
    
    def set_input_manager(self, input_manager) -> None:
        """Set the input manager reference"""
        self.input_manager = input_manager
    
    async def start_voice_assistant_mode(self, session_id: str = "default") -> None:
        """
        Start with voice trigger workflow.
        
        Args:
            session_id: Session identifier for conversation context
        """
        logger.info("Starting voice assistant mode...")
        
        if not self.input_manager:
            raise ConfigurationError("Input manager not set")
        
        # Get voice assistant workflow
        workflow = self.workflows.get("voice_assistant")
        if not workflow:
            raise ConfigurationError("Voice assistant workflow not available")
        
        # Get microphone input source
        mic_input = self._get_input_source("microphone")
        if not mic_input:
            raise ConfigurationError("Microphone input not available for voice assistant mode")
        
        # Initialize workflow
        await workflow.initialize()
        
        # Create request context
        context = RequestContext(
            source="microphone",
            session_id=session_id,
            wants_audio=True,
            skip_wake_word=False,
            metadata={"mode": "voice_assistant"}
        )
        
        # Start workflow
        self.active_workflow = workflow
        self.active_mode = WorkflowMode.VOICE_ASSISTANT
        
        # Start processing
        await self._start_audio_workflow(mic_input, workflow, context)
        
    async def start_continuous_mode(self, session_id: str = "default") -> None:
        """
        Start without voice trigger (current behavior).
        
        Args:
            session_id: Session identifier for conversation context
        """
        logger.info("Starting continuous listening mode...")
        
        if not self.input_manager:
            raise ConfigurationError("Input manager not set")
        
        # Get continuous workflow
        workflow = self.workflows.get("continuous")
        if not workflow:
            raise ConfigurationError("Continuous workflow not available")
        
        # Get microphone input source
        mic_input = self._get_input_source("microphone")
        if not mic_input:
            raise ConfigurationError("Microphone input not available for continuous mode")
        
        # Initialize workflow
        await workflow.initialize()
        
        # Create request context
        context = RequestContext(
            source="microphone",
            session_id=session_id,
            wants_audio=True,
            skip_wake_word=True,  # Skip wake word detection
            metadata={"mode": "continuous"}
        )
        
        # Start workflow
        self.active_workflow = workflow
        self.active_mode = WorkflowMode.CONTINUOUS_LISTENING
        
        # Start processing
        await self._start_audio_workflow(mic_input, workflow, context)
    
    async def start_text_mode(self, session_id: str = "default") -> None:
        """
        Start text-only mode (no audio processing).
        
        Args:
            session_id: Session identifier for conversation context
        """
        logger.info("Starting text-only mode...")
        
        # Use voice assistant workflow for text processing
        workflow = self.workflows.get("voice_assistant")
        if not workflow:
            raise ConfigurationError("Voice assistant workflow not available")
        
        # Initialize workflow
        await workflow.initialize()
        
        self.active_workflow = workflow
        self.active_mode = WorkflowMode.TEXT_ONLY
        
        logger.info("Text-only mode ready - use process_text_input() to send text")
    
    async def process_text_input(self, text: str, session_id: str = "default") -> IntentResult:
        """
        Process text input through the active workflow.
        
        Args:
            text: Input text to process
            session_id: Session identifier
            
        Returns:
            IntentResult from processing
        """
        if not self.active_workflow:
            raise RuntimeError("No active workflow - start a mode first")
        
        context = RequestContext(
            source="text",
            session_id=session_id,
            wants_audio=False,
            skip_wake_word=True,
            metadata={"mode": "text_input"}
        )
        
        return await self.active_workflow.process_text_input(text, context)
    
    async def _start_audio_workflow(self, input_source: InputSource, workflow: Workflow, context: RequestContext) -> None:
        """Start audio processing workflow"""
        try:
            # Start input source
            await input_source.start_listening()
            
            # Get audio stream from input source
            audio_stream = self._get_audio_stream(input_source)
            
            # Start workflow task
            self._workflow_task = asyncio.create_task(
                self._run_workflow(workflow, audio_stream, context)
            )
            
            logger.info(f"Started audio workflow: {workflow.name}")
            
        except Exception as e:
            logger.error(f"Failed to start audio workflow: {e}")
            raise
    
    async def _run_workflow(self, workflow: Workflow, audio_stream: AsyncIterator[AudioData], context: RequestContext) -> None:
        """Run the workflow with audio stream processing"""
        try:
            async for result in workflow.process_audio_stream(audio_stream, context):
                # Handle workflow results
                logger.info(f"Workflow result: {result.text[:50]}...")
                
                # TODO: Add result handling/routing here
                # This could include outputting to different channels,
                # triggering actions, etc.
                
        except asyncio.CancelledError:
            logger.debug("Workflow processing cancelled")
        except Exception as e:
            logger.error(f"Workflow processing error: {e}")
    
    def _get_input_source(self, source_name: str) -> Optional[InputSource]:
        """Get an input source by name"""
        if not self.input_manager:
            return None
        
        return self.input_manager._sources.get(source_name)
    
    async def _get_audio_stream(self, input_source: InputSource) -> AsyncIterator[AudioData]:
        """
        Convert input source to audio stream.
        
        Note: This assumes the input source has been updated to provide AudioData.
        For Phase 2, we may need to adapt existing sources.
        """
        # TODO: This will need to be implemented based on how the microphone
        # input source is updated in the next phases. For now, this is a placeholder.
        
        # The microphone input should be updated to yield AudioData objects
        # instead of text commands after Phase 1 fixes are applied.
        
        # Placeholder implementation:
        async for data in input_source.listen():
            # This will need to be updated when microphone input
            # is fixed to provide AudioData instead of text
            if isinstance(data, str):
                # Legacy text input - convert to AudioData if needed
                # This is temporary until microphone input is fully updated
                continue
            else:
                # Proper AudioData from updated input source
                yield data
    
    async def stop_current_workflow(self) -> None:
        """Stop the currently active workflow"""
        if self._workflow_task:
            self._workflow_task.cancel()
            try:
                await self._workflow_task
            except asyncio.CancelledError:
                pass
            self._workflow_task = None
        
        if self.active_workflow:
            logger.info(f"Stopped workflow: {self.active_workflow.name}")
            self.active_workflow = None
            self.active_mode = None
    
    def get_current_mode(self) -> Optional[WorkflowMode]:
        """Get the current workflow mode"""
        return self.active_mode
    
    def get_available_workflows(self) -> list[str]:
        """Get list of available workflow names"""
        return list(self.workflows.keys())
    
    async def get_workflow_status(self) -> Dict[str, Any]:
        """Get status of all workflows"""
        status = {
            "active_mode": self.active_mode.value if self.active_mode else None,
            "active_workflow": self.active_workflow.name if self.active_workflow else None,
            "available_workflows": self.get_available_workflows(),
            "workflows": {}
        }
        
        for name, workflow in self.workflows.items():
            status["workflows"][name] = {
                "initialized": workflow.initialized,
                "components": len(workflow.components)
            }
        
        return status
    
    async def cleanup(self) -> None:
        """Clean up workflow manager resources"""
        await self.stop_current_workflow()
        
        # Clean up workflows
        for workflow in self.workflows.values():
            if hasattr(workflow, 'cleanup'):
                try:
                    await workflow.cleanup()
                except Exception as e:
                    logger.error(f"Workflow cleanup error: {e}")
        
        logger.info("WorkflowManager cleaned up") 