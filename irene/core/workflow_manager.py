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
from ..workflows.voice_assistant import UnifiedVoiceAssistantWorkflow
from ..intents.models import AudioData, IntentResult
from ..inputs.base import InputSource
from ..utils.audio_helpers import validate_audio_file
from ..config.manager import ConfigValidationError

logger = logging.getLogger(__name__)


class WorkflowMode(Enum):
    """Available processing modes for unified workflow"""
    UNIFIED = "unified"  # Single unified workflow handles all input types


class WorkflowManager:
    """
    Manages workflow execution and input coordination.
    
    Provides the interface for processing text and audio input
    through the unified workflow with conditional pipeline stages.
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
        # No need to pre-create workflows anymore.
        # UnifiedVoiceAssistantWorkflow is created on-demand via _get_or_create_unified_workflow()
        logger.info("Workflow manager ready - workflows will be created on-demand")
    
    async def _inject_components(self, workflow: Workflow) -> None:
        """Inject required components into a workflow"""
        try:
            # Get components from component manager
            components = self.component_manager.get_available_components()
            
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
            
            # Inject configuration for temp_audio_dir access (Phase 2 implementation)
            workflow.add_component('config', self.component_manager.config)
                
            logger.debug(f"Injected {len(workflow.components)} components into {workflow.name}")
            
        except Exception as e:
            logger.error(f"Component injection failed for {workflow.name}: {e}")
            raise
    
    def set_input_manager(self, input_manager) -> None:
        """Set the input manager reference"""
        self.input_manager = input_manager
    

    
    async def process_text_input(
        self, 
        text: str, 
        session_id: str = "default", 
        wants_audio: bool = False,
        client_context: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        """
        Process text input through the unified workflow (enhanced interface).
        
        This method implements the Q1 decision for unified entry points.
        Skips voice trigger and ASR stages, processes text directly through NLU → Intent → Response.
        
        Args:
            text: Input text to process
            session_id: Session identifier for conversation context
            wants_audio: Whether the response should include audio output (TTS)
            client_context: Optional client context and metadata
            
        Returns:
            IntentResult from processing with optional action metadata
        """
        # Use UnifiedVoiceAssistantWorkflow for all processing
        unified_workflow = await self._get_or_create_unified_workflow()
        
        # Create enhanced request context
        context = RequestContext(
            source="text",
            session_id=session_id,
            wants_audio=wants_audio,
            skip_wake_word=True,  # Always skip for text input
            metadata=client_context or {"mode": "text_input"},
            client_id=client_context.get("client_id") if client_context else None,
            room_name=client_context.get("room_name") if client_context else None,
            device_context=client_context.get("device_context") if client_context else None
        )
        
        result = await unified_workflow.process_text_input(text, context)
        
        # Process action metadata if present
        if result.action_metadata:
            await self._process_action_metadata_integration(result, session_id)
        
        return result
    
    async def process_audio_stream(
        self,
        audio_stream: AsyncIterator[AudioData],
        session_id: str = "default", 
        skip_wake_word: bool = False,
        wants_audio: bool = True,
        client_context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[IntentResult]:
        """
        Process audio stream through the unified workflow (enhanced interface).
        
        This method implements the Q1 decision for unified entry points.
        Processes audio through conditional pipeline stages based on skip_wake_word parameter.
        
        Args:
            audio_stream: Async iterator of audio data to process
            session_id: Session identifier for conversation context
            skip_wake_word: Whether to skip wake word detection (True for WebAPI, False for Voice)
            wants_audio: Whether the response should include audio output (TTS)
            client_context: Optional client context and metadata
            
        Yields:
            IntentResult objects as they are generated
        """
        # Use UnifiedVoiceAssistantWorkflow for all processing
        unified_workflow = await self._get_or_create_unified_workflow()
        
        # Create enhanced request context
        context = RequestContext(
            source="audio_stream" if skip_wake_word else "voice",
            session_id=session_id,
            wants_audio=wants_audio,
            skip_wake_word=skip_wake_word,
            metadata=client_context or {"mode": "audio_stream"},
            client_id=client_context.get("client_id") if client_context else None,
            room_name=client_context.get("room_name") if client_context else None,
            device_context=client_context.get("device_context") if client_context else None
        )
        
        async for result in unified_workflow.process_audio_stream(audio_stream, context):
            # Process action metadata if present
            if result.action_metadata:
                await self._process_action_metadata_integration(result, session_id)
            yield result
    
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
    
    async def _get_or_create_unified_workflow(self) -> UnifiedVoiceAssistantWorkflow:
        """
        Get or create the unified workflow instance for all entry points.
        
        This implements the unified architecture where a single workflow
        handles all input types with conditional pipeline stages.
        
        Returns:
            UnifiedVoiceAssistantWorkflow instance ready for processing
        """
        # Check if we already have a unified workflow instance
        unified_workflow = self.workflows.get("unified_voice_assistant")
        
        if not unified_workflow:
            # Create new UnifiedVoiceAssistantWorkflow
            unified_workflow = UnifiedVoiceAssistantWorkflow()
            await self._inject_components(unified_workflow)
            await unified_workflow.initialize()
            self.workflows["unified_voice_assistant"] = unified_workflow
            logger.info("Created and initialized UnifiedVoiceAssistantWorkflow")
        
        return unified_workflow
    
    async def _process_action_metadata_integration(self, result: IntentResult, session_id: str):
        """
        Enhanced action metadata processing for Phase 5 fire-and-forget actions.
        
        This method handles action metadata from intent results and ensures
        it gets properly merged into the conversation context for tracking.
        Supports both active_actions and recent_actions from action execution.
        
        Args:
            result: IntentResult containing action metadata
            session_id: Session identifier for context retrieval
        """
        if not result.action_metadata:
            return
        
        try:
            # Get conversation context through context manager if available
            context_manager = None
            conversation_context = None
            
            if hasattr(self.component_manager, 'context_manager'):
                context_manager = self.component_manager.context_manager
            
            # Fallback to workflow context manager if available
            if not context_manager and hasattr(self, 'context_manager'):
                context_manager = self.context_manager
            
            if context_manager:
                conversation_context = await context_manager.get_context(session_id)
                
                # Process active_actions metadata (fire-and-forget action starts)
                if 'active_actions' in result.action_metadata:
                    active_actions = result.action_metadata['active_actions']
                    for action_name, action_info in active_actions.items():
                        # Update conversation context active actions
                        if not hasattr(conversation_context, 'active_actions'):
                            conversation_context.active_actions = {}
                        
                        conversation_context.active_actions[action_name] = action_info
                        logger.info(f"Added active action '{action_name}' for session {session_id}: {action_info.get('domain', 'unknown')}")
                
                # Process recent_actions metadata (completed/failed actions)
                if 'recent_actions' in result.action_metadata:
                    recent_actions = result.action_metadata['recent_actions']
                    for action_info in recent_actions:
                        # Update conversation context recent actions
                        if not hasattr(conversation_context, 'recent_actions'):
                            conversation_context.recent_actions = []
                        
                        conversation_context.recent_actions.append(action_info)
                        
                        # Keep only last 10 recent actions to prevent memory bloat
                        if len(conversation_context.recent_actions) > 10:
                            conversation_context.recent_actions = conversation_context.recent_actions[-10:]
                        
                        status = action_info.get('status', 'unknown')
                        action_name = action_info.get('action', 'unknown')
                        logger.info(f"Added recent action '{action_name}' with status '{status}' for session {session_id}")
                
                # Update context metadata with action statistics
                if not hasattr(conversation_context, 'metadata'):
                    conversation_context.metadata = {}
                
                action_stats = conversation_context.metadata.get('action_stats', {
                    'total_actions': 0,
                    'active_count': 0,
                    'successful_count': 0,
                    'failed_count': 0
                })
                
                # Update statistics
                if 'active_actions' in result.action_metadata:
                    action_stats['total_actions'] += len(result.action_metadata['active_actions'])
                    action_stats['active_count'] = len(getattr(conversation_context, 'active_actions', {}))
                
                if 'recent_actions' in result.action_metadata:
                    for action_info in result.action_metadata['recent_actions']:
                        status = action_info.get('status', 'unknown')
                        if status == 'completed':
                            action_stats['successful_count'] += 1
                        elif status == 'failed':
                            action_stats['failed_count'] += 1
                
                conversation_context.metadata['action_stats'] = action_stats
                logger.debug(f"Updated action statistics for session {session_id}: {action_stats}")
            
            else:
                logger.warning(f"No context manager available for action metadata processing in session {session_id}")
        
        except Exception as e:
            logger.warning(f"Failed to process action metadata integration: {e}")
    
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