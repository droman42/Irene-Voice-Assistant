"""
Workflow Manager - Coordinates workflows with input sources

This manager handles the coordination between input sources and workflows,
supporting both voice assistant mode (with wake words) and continuous mode.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, AsyncIterator, List
from enum import Enum

from ..workflows.base import Workflow, RequestContext
from ..intents.models import AudioData, IntentResult
from ..inputs.base import InputSource
from ..utils.audio_helpers import validate_audio_file
from ..config.manager import ConfigValidationError
from ..utils.loader import dynamic_loader

logger = logging.getLogger(__name__)


class WorkflowMode(Enum):
    """Available processing modes for unified workflow"""
    UNIFIED = "unified"  # Single unified workflow handles all input types


class WorkflowState(Enum):
    """Available states for workflow lifecycle"""
    INITIALIZING = "initializing"
    WARMING_UP = "warming_up"  
    READY = "ready"
    ERROR = "error"


class WorkflowManager:
    """
    Manages workflow execution and input coordination.
    
    Provides the interface for processing text and audio input
    through the unified workflow with conditional pipeline stages.
    """
    
    def __init__(self, component_manager, config):
        self.component_manager = component_manager
        self.config = config
        self.workflows: Dict[str, Workflow] = {}
        self.workflow_states: Dict[str, WorkflowState] = {}
        self.active_workflow: Optional[Workflow] = None
        self.active_mode: Optional[WorkflowMode] = None
        self.input_manager = None
        self._workflow_task: Optional[asyncio.Task] = None
        self._progress_monitor_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Cache for discovered workflows
        self._available_workflows: Optional[Dict[str, type]] = None

    def discover_workflows(self) -> Dict[str, type]:
        """
        Discover available workflow classes via entry-points
        
        Returns:
            Dictionary mapping workflow names to their classes
        """
        if self._available_workflows is None:
            try:
                self._available_workflows = dynamic_loader.discover_providers("irene.workflows")
                
                if not self._available_workflows:
                    logger.warning("No workflows discovered via entry-points. This may indicate a configuration issue.")
                else:
                    logger.info(f"Discovered {len(self._available_workflows)} workflows: {list(self._available_workflows.keys())}")
                    
            except Exception as e:
                logger.error(f"Failed to discover workflows via entry-points: {e}")
                self._available_workflows = {}
        
        return self._available_workflows

    def get_workflow_class(self, workflow_name: str) -> Optional[type]:
        """
        Get a specific workflow class by name
        
        Args:
            workflow_name: Name of the workflow to get
            
        Returns:
            Workflow class or None if not found
        """
        try:
            workflows = self.discover_workflows()
            workflow_class = workflows.get(workflow_name)
            
            if workflow_class is None:
                logger.error(f"Workflow '{workflow_name}' not found in discovered workflows: {list(workflows.keys())}")
                return None
            
            # Validate that the class is actually a workflow
            from ..workflows.base import Workflow
            if not issubclass(workflow_class, Workflow):
                logger.error(f"Class for workflow '{workflow_name}' does not inherit from Workflow base class")
                return None
            
            return workflow_class
            
        except Exception as e:
            logger.error(f"Error getting workflow class '{workflow_name}': {e}")
            return None

    def list_available_workflow_names(self) -> List[str]:
        """
        Get list of all available workflow names from entry-points
        
        Returns:
            List of workflow names
        """
        return list(self.discover_workflows().keys())
        
    async def initialize(self) -> None:
        """Initialize the workflow manager with available workflows"""
        logger.info("Initializing WorkflowManager...")
        
        # Create workflow instances
        await self._create_workflows()
        
        initialized_workflows = list(self.workflows.keys())
        logger.info(f"WorkflowManager initialized with workflows: {initialized_workflows}")

        if self.active_workflow:
            logger.info(f"Active workflow: {self.active_workflow.name}")
        else:
            logger.info("No active workflow set - will create on-demand")
        
        # Start progress monitoring if workflows are warming up
        warming_up_workflows = [name for name, state in self.workflow_states.items() 
                               if state == WorkflowState.WARMING_UP]
        if warming_up_workflows:
            await self.start_progress_monitoring()
            logger.info(f"Started progress monitoring for warming workflows: {warming_up_workflows}")
        
    async def _create_workflows(self) -> None:
        """Create and initialize workflow instances from configuration"""
        
        # Read workflow configuration
        workflow_config = getattr(self.config, 'workflows', None)
        if not workflow_config:
            logger.warning("No workflow configuration found, falling back to on-demand creation")
            return
        
        enabled_workflows = workflow_config.enabled or ["unified_voice_assistant"]
        default_workflow = workflow_config.default or "unified_voice_assistant"
        
        logger.info(f"Initializing enabled workflows: {enabled_workflows}")
        
        # Initialize enabled workflows in parallel for better performance
        if len(enabled_workflows) > 1:
            logger.info("Initializing workflows in parallel for better performance...")
            workflow_tasks = []
            for workflow_name in enabled_workflows:
                task = asyncio.create_task(
                    self._create_and_initialize_workflow_with_logging(workflow_name),
                    name=f"init_workflow_{workflow_name}"
                )
                workflow_tasks.append((workflow_name, task))
            
            # Wait for all workflows to complete
            for workflow_name, task in workflow_tasks:
                try:
                    await task
                except Exception as e:
                    logger.error(f"❌ Failed to initialize workflow '{workflow_name}': {e}")
        else:
            # Single workflow - no need for parallel processing
            for workflow_name in enabled_workflows:
                try:
                    await self._create_and_initialize_workflow(workflow_name)
                    logger.info(f"✅ Workflow '{workflow_name}' initialized successfully")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize workflow '{workflow_name}': {e}")
        
        # Set default workflow as active
        if default_workflow in self.workflows:
            self.active_workflow = self.workflows[default_workflow]
            self.active_mode = WorkflowMode.UNIFIED
            logger.info(f"Set default workflow: {default_workflow}")
        else:
            logger.warning(f"Default workflow '{default_workflow}' not available")

    async def _create_and_initialize_workflow(self, workflow_name: str) -> None:
        """Create and initialize a specific workflow using entry-points discovery"""
        # Set initial state
        self.set_workflow_state(workflow_name, WorkflowState.INITIALIZING)
        
        try:
            # Get workflow class via entry-points discovery
            workflow_class = self.get_workflow_class(workflow_name)
            if workflow_class is None:
                raise ValueError(f"Workflow '{workflow_name}' not found in entry-points. "
                               f"Available workflows: {self.list_available_workflow_names()}. "
                               f"Register the workflow in pyproject.toml under [project.entry-points.\"irene.workflows\"]")
            
            # Create workflow instance
            workflow = workflow_class()
            await self._inject_components(workflow)
            
            # Get workflow-specific configuration
            workflow_config = self._get_workflow_config(workflow_name)
            await workflow.initialize(workflow_config)
            self.workflows[workflow_name] = workflow
            
            # Set state to warming up (models may still be loading)
            self.set_workflow_state(workflow_name, WorkflowState.WARMING_UP)
            logger.debug(f"Successfully created workflow '{workflow_name}' using class {workflow_class.__name__}")
            
        except Exception as e:
            self.set_workflow_state(workflow_name, WorkflowState.ERROR)
            logger.error(f"Failed to create workflow '{workflow_name}': {e}")
            raise

    def _get_workflow_config(self, workflow_name: str):
        """
        Get workflow-specific configuration dynamically
        
        Args:
            workflow_name: Name of the workflow
            
        Returns:
            Workflow-specific configuration object
            
        Raises:
            ValueError: If no configuration found for the workflow
        """
        # Get the workflows configuration object
        workflows_config = self.config.workflows
        
        # Try to get the workflow-specific config by attribute name
        if hasattr(workflows_config, workflow_name):
            return getattr(workflows_config, workflow_name)
        else:
            # List available workflow configurations
            available_configs = [attr for attr in dir(workflows_config) 
                               if not attr.startswith('_') and attr not in ['enabled', 'default']]
            raise ValueError(f"No configuration found for workflow '{workflow_name}'. "
                           f"Available workflow configurations: {available_configs}. "
                           f"Add '{workflow_name}' configuration to WorkflowConfig model.")

    async def _create_and_initialize_workflow_with_logging(self, workflow_name: str) -> None:
        """Create and initialize a workflow with success/failure logging"""
        try:
            await self._create_and_initialize_workflow(workflow_name)
            logger.info(f"✅ Workflow '{workflow_name}' initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize workflow '{workflow_name}': {e}")
            raise

    def set_workflow_state(self, workflow_name: str, state: WorkflowState) -> None:
        """Update workflow state and log changes"""
        old_state = self.workflow_states.get(workflow_name)
        self.workflow_states[workflow_name] = state
        
        if old_state != state:
            logger.info(f"Workflow '{workflow_name}' state: {old_state} → {state}")

    async def check_workflow_readiness(self, workflow_name: str) -> bool:
        """Check if workflow is fully ready (all models loaded)"""
        workflow = self.workflows.get(workflow_name)
        if not workflow:
            return False
        
        # Check if all required components have loaded models
        for component_name, component in workflow.components.items():
            if hasattr(component, 'providers'):
                # Note: component.providers only contains ENABLED providers
                for provider_name, provider in component.providers.items():
                    # Only check file-based model providers
                    if hasattr(provider, '_model') and provider._model is None:
                        return False  # Model still loading
                    # SpaCy and other package-based providers are always "ready"
        
        return True

    async def update_workflow_readiness(self) -> None:
        """Update workflow states based on model loading progress"""
        for workflow_name, workflow in self.workflows.items():
            current_state = self.workflow_states.get(workflow_name, WorkflowState.INITIALIZING)
            
            if current_state == WorkflowState.WARMING_UP:
                if await self.check_workflow_readiness(workflow_name):
                    self.set_workflow_state(workflow_name, WorkflowState.READY)

    async def monitor_model_loading_progress(self) -> Dict[str, Any]:
        """Monitor real-time model loading progress across all workflows"""
        progress_report = {
            "overall_progress": 0.0,
            "total_models": 0,
            "loaded_models": 0,
            "loading_models": [],
            "failed_models": [],
            "workflows": {}
        }
        
        total_models = 0
        loaded_models = 0
        
        for workflow_name, workflow in self.workflows.items():
            workflow_progress = await self._get_model_loading_progress(workflow)
            progress_report["workflows"][workflow_name] = {
                "state": self.workflow_states.get(workflow_name, WorkflowState.INITIALIZING).value,
                "progress": workflow_progress,
                "progress_percentage": (
                    (workflow_progress["loaded_providers"] / max(workflow_progress["total_providers"], 1)) * 100
                ) if workflow_progress["total_providers"] > 0 else 100.0
            }
            
            total_models += workflow_progress["total_providers"]
            loaded_models += workflow_progress["loaded_providers"]
            progress_report["loading_models"].extend(workflow_progress["loading_providers"])
            progress_report["failed_models"].extend(workflow_progress.get("failed_providers", []))
        
        progress_report["total_models"] = total_models
        progress_report["loaded_models"] = loaded_models
        progress_report["overall_progress"] = (loaded_models / max(total_models, 1)) * 100 if total_models > 0 else 100.0
        
        return progress_report

    async def start_progress_monitoring(self, update_interval: float = 2.0) -> None:
        """Start continuous progress monitoring with periodic updates"""
        if hasattr(self, '_progress_monitor_task') and self._progress_monitor_task:
            return  # Already running
        
        async def monitor_loop():
            while not self._shutdown_event.is_set():
                try:
                    progress = await self.monitor_model_loading_progress()
                    
                    # Update workflow readiness based on progress
                    await self.update_workflow_readiness()
                    
                    # Log progress for workflows still loading
                    for workflow_name, workflow_data in progress["workflows"].items():
                        if workflow_data["state"] == "warming_up" and workflow_data["progress_percentage"] < 100:
                            loading_providers = workflow_data["progress"]["loading_providers"]
                            if loading_providers:
                                logger.info(f"Workflow '{workflow_name}' loading progress: "
                                          f"{workflow_data['progress_percentage']:.1f}% "
                                          f"(waiting for: {', '.join(loading_providers)})")
                    
                    # Stop monitoring when all workflows are ready
                    if progress["overall_progress"] >= 100.0:
                        logger.info("All workflows ready - stopping progress monitoring")
                        break
                        
                except Exception as e:
                    logger.error(f"Error in progress monitoring: {e}")
                
                await asyncio.sleep(update_interval)
        
        self._progress_monitor_task = asyncio.create_task(monitor_loop())
        logger.info("Started model loading progress monitoring")

    async def stop_progress_monitoring(self) -> None:
        """Stop progress monitoring"""
        if hasattr(self, '_progress_monitor_task') and self._progress_monitor_task:
            self._progress_monitor_task.cancel()
            try:
                await self._progress_monitor_task
            except asyncio.CancelledError:
                pass
            self._progress_monitor_task = None
            logger.info("Stopped progress monitoring")
    
    async def _inject_components(self, workflow: Workflow) -> None:
        """Inject required components into a workflow"""
        try:
            # Get actual component instances, not classes
            component_instances = self.component_manager.get_components()
            
            # Inject component instances into workflow
            for name, component in component_instances.items():
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
            
            # Inject configuration for temp_audio_dir access
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
        # Use active workflow or create unified workflow on-demand
        if not self.active_workflow:
            await self.create_workflow_on_demand("unified_voice_assistant")
            if "unified_voice_assistant" in self.workflows:
                self.active_workflow = self.workflows["unified_voice_assistant"]
                self.active_mode = WorkflowMode.UNIFIED
        
        if not self.active_workflow:
            raise RuntimeError("No active workflow available and failed to create unified_voice_assistant workflow")
        
        unified_workflow = self.active_workflow
        
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
        # Use active workflow or create unified workflow on-demand
        if not self.active_workflow:
            await self.create_workflow_on_demand("unified_voice_assistant")
            if "unified_voice_assistant" in self.workflows:
                self.active_workflow = self.workflows["unified_voice_assistant"]
                self.active_mode = WorkflowMode.UNIFIED
        
        if not self.active_workflow:
            raise RuntimeError("No active workflow available and failed to create unified_voice_assistant workflow")
        
        unified_workflow = self.active_workflow
        
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
        
        Handles both legacy text input sources and modern AudioData sources.
        Microphone input now provides AudioData objects directly.
        """
        async for data in input_source.listen():
            # Handle different input data types
            if isinstance(data, AudioData):
                # Modern AudioData from microphone input - pass through directly
                yield data
            elif hasattr(data, 'data') and hasattr(data, 'timestamp'):
                # InputData that contains audio data - convert to AudioData
                yield AudioData(
                    data=data.data,
                    timestamp=getattr(data, 'timestamp', time.time()),
                    sample_rate=getattr(data, 'sample_rate', 16000),
                    channels=getattr(data, 'channels', 1),
                    format=getattr(data, 'format', 'pcm16')
                )
            elif isinstance(data, str):
                # Legacy text input - skip (not audio data)
                logger.debug(f"Skipping text input in audio stream: {data[:50]}...")
                continue
            else:
                # Unknown data type - log warning but continue
                logger.warning(f"Unknown input data type in audio stream: {type(data)}")
                continue
    
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
        """Get list of available workflow names from entry-points discovery"""
        return self.list_available_workflow_names()

    async def switch_workflow(self, workflow_name: str) -> bool:
        """
        Dynamically switch to a different workflow
        
        Args:
            workflow_name: Name of the workflow to switch to
            
        Returns:
            bool: True if switch was successful, False otherwise
        """
        if workflow_name not in self.workflows:
            logger.error(f"Cannot switch to unknown workflow: {workflow_name}")
            return False
        
        # Check if workflow is ready
        workflow_state = self.workflow_states.get(workflow_name, WorkflowState.INITIALIZING)
        if workflow_state != WorkflowState.READY:
            logger.warning(f"Switching to workflow '{workflow_name}' that is not ready (state: {workflow_state})")
        
        # Stop current workflow if running
        if self.active_workflow and self._workflow_task:
            logger.info(f"Stopping current workflow: {self.active_workflow.name}")
            await self.stop_current_workflow()
        
        # Switch to new workflow
        old_workflow = self.active_workflow.name if self.active_workflow else None
        self.active_workflow = self.workflows[workflow_name]
        self.active_mode = WorkflowMode.UNIFIED
        
        logger.info(f"Switched workflow: {old_workflow} → {workflow_name}")
        return True

    async def hot_reload_workflow(self, workflow_name: str) -> bool:
        """
        Hot-reload a workflow with new configuration
        
        Args:
            workflow_name: Name of the workflow to reload
            
        Returns:
            bool: True if reload was successful, False otherwise
        """
        if workflow_name not in self.workflows:
            logger.error(f"Cannot reload unknown workflow: {workflow_name}")
            return False
        
        try:
            # Mark as reloading
            self.set_workflow_state(workflow_name, WorkflowState.INITIALIZING)
            logger.info(f"Hot-reloading workflow: {workflow_name}")
            
            # Store reference to old workflow
            old_workflow = self.workflows[workflow_name]
            was_active = self.active_workflow == old_workflow
            
            # Stop if currently active
            if was_active and self._workflow_task:
                await self.stop_current_workflow()
            
            # Clean up old workflow
            if hasattr(old_workflow, 'cleanup'):
                await old_workflow.cleanup()
            
            # Create new instance
            await self._create_and_initialize_workflow(workflow_name)
            
            # Reactivate if it was active before
            if was_active:
                self.active_workflow = self.workflows[workflow_name]
                self.active_mode = WorkflowMode.UNIFIED
                logger.info(f"Reactivated reloaded workflow: {workflow_name}")
            
            logger.info(f"✅ Successfully hot-reloaded workflow: {workflow_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to hot-reload workflow '{workflow_name}': {e}")
            self.set_workflow_state(workflow_name, WorkflowState.ERROR)
            return False

    async def create_workflow_on_demand(self, workflow_name: str) -> bool:
        """
        Create a new workflow on-demand if it doesn't exist
        
        Args:
            workflow_name: Name of the workflow to create
            
        Returns:
            bool: True if creation was successful, False otherwise
        """
        if workflow_name in self.workflows:
            logger.info(f"Workflow '{workflow_name}' already exists")
            return True
        
        # Check if the workflow is available via entry-points first
        available_workflows = self.list_available_workflow_names()
        if workflow_name not in available_workflows:
            logger.error(f"Workflow '{workflow_name}' not found in available workflows: {available_workflows}")
            return False
        
        try:
            logger.info(f"Creating workflow on-demand: {workflow_name}")
            await self._create_and_initialize_workflow(workflow_name)
            logger.info(f"✅ Successfully created workflow: {workflow_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create workflow '{workflow_name}': {e}")
            return False

    def get_workflow_dependencies(self, workflow_name: str) -> Dict[str, Any]:
        """
        Get dependency information for a workflow from the workflow class itself
        
        Args:
            workflow_name: Name of the workflow to analyze
            
        Returns:
            Dict containing dependency information
        """
        dependencies = {
            "required_components": [],
            "optional_components": [],
            "required_providers": [],
            "missing_dependencies": []
        }
        
        try:
            # Get workflow class via discovery system
            workflow_class = self.get_workflow_class(workflow_name)
            if workflow_class is None:
                logger.warning(f"Cannot get dependencies for unknown workflow: {workflow_name}")
                return dependencies
            
            # Check if workflow defines its own dependencies
            if hasattr(workflow_class, 'get_dependencies'):
                class_dependencies = workflow_class.get_dependencies()
                dependencies.update(class_dependencies)
            else:
                logger.warning(f"Workflow '{workflow_name}' does not define dependencies via get_dependencies() method")
            
            # Check which components are available
            available_components = set(self.component_manager.get_components().keys())
            for required in dependencies.get("required_components", []):
                if required not in available_components:
                    dependencies["missing_dependencies"].append(f"component:{required}")
                    
        except Exception as e:
            logger.error(f"Error getting dependencies for workflow '{workflow_name}': {e}")
        
        return dependencies

    async def optimize_component_sharing(self) -> Dict[str, Any]:
        """
        Optimize component sharing between workflows to reduce memory usage
        
        Returns:
            Dict containing optimization statistics
        """
        optimization_stats = {
            "shared_components": {},
            "memory_savings_estimated": 0,
            "workflows_optimized": 0
        }
        
        if len(self.workflows) < 2:
            return optimization_stats
        
        # Find components that can be shared between workflows
        component_usage = {}
        for workflow_name, workflow in self.workflows.items():
            for component_name, component in workflow.components.items():
                if component_name not in component_usage:
                    component_usage[component_name] = []
                component_usage[component_name].append(workflow_name)
        
        # Identify shared components
        for component_name, using_workflows in component_usage.items():
            if len(using_workflows) > 1:
                optimization_stats["shared_components"][component_name] = using_workflows
                optimization_stats["memory_savings_estimated"] += len(using_workflows) - 1
        
        optimization_stats["workflows_optimized"] = len(self.workflows)
        
        if optimization_stats["shared_components"]:
            logger.info(f"Component sharing optimization: {len(optimization_stats['shared_components'])} "
                       f"shared components across {len(self.workflows)} workflows")
        
        return optimization_stats

    async def get_startup_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for workflow startup optimization
        
        Returns:
            Dict containing performance metrics
        """
        metrics = {
            "total_workflows": len(self.workflows),
            "ready_workflows": 0,
            "warming_workflows": 0,
            "failed_workflows": 0,
            "initialization_strategy": "parallel" if len(self.workflows) > 1 else "sequential",
            "progress_monitoring_active": hasattr(self, '_progress_monitor_task') and self._progress_monitor_task is not None
        }
        
        for state in self.workflow_states.values():
            if state == WorkflowState.READY:
                metrics["ready_workflows"] += 1
            elif state == WorkflowState.WARMING_UP:
                metrics["warming_workflows"] += 1
            elif state == WorkflowState.ERROR:
                metrics["failed_workflows"] += 1
        
        metrics["startup_completion_percentage"] = (
            (metrics["ready_workflows"] / max(metrics["total_workflows"], 1)) * 100
        ) if metrics["total_workflows"] > 0 else 100.0
        
        return metrics
    
    async def get_workflow_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all workflows"""
        status = {
            "active_mode": self.active_mode.value if self.active_mode else None,
            "active_workflow": self.active_workflow.name if self.active_workflow else None,
            "available_workflows": self.get_available_workflows(),
            "workflows": {}
        }
        
        for name, workflow in self.workflows.items():
            workflow_state = self.workflow_states.get(name, WorkflowState.INITIALIZING)
            is_ready = await self.check_workflow_readiness(name)
            
            status["workflows"][name] = {
                "initialized": workflow.initialized,
                "state": workflow_state.value,
                "ready": is_ready,
                "components": len(workflow.components),
                "model_loading_progress": await self._get_model_loading_progress(workflow)
            }
        
        return status

    async def _get_model_loading_progress(self, workflow: Workflow) -> Dict[str, Any]:
        """Get model loading progress for workflow components"""
        progress = {
            "total_providers": 0,
            "loaded_providers": 0,
            "loading_providers": [],
            "failed_providers": []
        }
        
        for component_name, component in workflow.components.items():
            if hasattr(component, 'providers'):
                for provider_name, provider in component.providers.items():
                    progress["total_providers"] += 1
                    
                    # Categorize providers by type
                    if hasattr(provider, '_model'):
                        # File-based AI model provider
                        if provider._model is not None:
                            progress["loaded_providers"] += 1
                        else:
                            progress["loading_providers"].append(f"{component_name}.{provider_name}")
                    else:
                        # Package-based, API-based, or console provider (always ready)
                        progress["loaded_providers"] += 1
        
        return progress
    
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
        
        # Stop progress monitoring
        await self.stop_progress_monitoring()
        
        # Clean up workflows
        for workflow in self.workflows.values():
            if hasattr(workflow, 'cleanup'):
                try:
                    await workflow.cleanup()
                except Exception as e:
                    logger.error(f"Workflow cleanup error: {e}")
        
        logger.info("WorkflowManager cleaned up") 