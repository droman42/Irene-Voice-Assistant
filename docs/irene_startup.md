# Irene Startup Sequence and Default Workflow Initialization

This document outlines the current Irene Voice Assistant startup sequence and the planned implementation for default workflow initialization at startup.

## Current Startup Sequence

### AsyncVACore Initialization Flow

**File**: `irene/core/engine.py:47-77`

The current startup sequence follows this order:

```python
async def start(self) -> None:
    logger.info("Starting Irene Voice Assistant v13...")
    
    # 1. Component System Initialization
    await self.component_manager.initialize_components(self)  # Line 53
    
    # 2. Supporting Systems
    await self.context_manager.start()                        # Line 55
    await self.timer_manager.start()                          # Line 56
    await self.plugin_manager.initialize(self)               # Line 57
    
    # 3. Workflow Manager (CURRENT ISSUE: No workflows created)
    await self.workflow_manager.initialize()                 # Line 60
    
    # 4. External Systems
    await self.plugin_manager.load_plugins()                 # Line 65
    await self.input_manager.initialize()                    # Line 67
    
    logger.info(f"Irene started successfully in {profile} mode")
```

### Component Initialization Details

**File**: `irene/core/components.py:215-282`

During component initialization:

1. **Discovery Phase**: Available components discovered via entry-points
2. **Dependency Resolution**: Components ordered by dependencies
3. **Sequential Initialization**: Components initialized in dependency order
4. **Provider Loading**: Each component discovers and loads **only enabled providers**
5. **Model Loading**: AI models loaded **only for enabled providers** with `preload_models: true`

### Model Loading Timing

#### File-Based AI Models (Support preload_models: true)
**⚠️ Models are only downloaded and warmed up for ENABLED providers in configuration**

When `enabled: true` AND `preload_models: true`:
- **SileroV3TTSProvider**: `asyncio.create_task(self.warm_up())` during construction
- **SileroV4TTSProvider**: `asyncio.create_task(self.warm_up())` during construction  
- **VoskASRProvider**: `asyncio.create_task(self.warm_up())` during construction
- **VoskTTSProvider**: `asyncio.create_task(self.warm_up())` during construction
- **WhisperASRProvider**: `asyncio.create_task(self.warm_up())` during construction
- **OpenWakeWordProvider**: `asyncio.create_task(self.warm_up())` during construction

#### Package-Based Models (No preload_models support)
**⚠️ Only processed if provider is enabled in configuration**

When `enabled: true`:
- **SpaCyNLUProvider**: Python packages installed via pip/spacy CLI
- **API-based providers**: OpenAI, ElevenLabs (no local models)
- **Console providers**: No models to load

#### Lazy Loading (preload_models: false - default)
**⚠️ Only applies to enabled providers**

- File-based models loaded on first usage (only if provider enabled)
- Background tasks handle downloads via Asset Manager
- All model paths managed automatically by Asset Manager
- Disabled providers are completely skipped (no model loading)

## Current Problem: No Default Workflow Initialization

### Issue Analysis

**Current Log Output**:
```
2025-08-21 14:24:19,130 - irene.core.workflow_manager - INFO - Initializing WorkflowManager...
2025-08-21 14:24:19,130 - irene.core.workflow_manager - INFO - Workflow manager ready - workflows will be created on-demand
2025-08-21 14:24:19,130 - irene.core.workflow_manager - INFO - WorkflowManager initialized with workflows: []
```

**Root Cause**: 
- `WorkflowManager._create_workflows()` is empty (lines 54-58)
- No configuration passed to WorkflowManager constructor
- System relies entirely on on-demand workflow creation

**Expected Configuration**:
```toml
[workflows]
enabled = ["unified_voice_assistant"]  # List of enabled workflows
default = "unified_voice_assistant"    # Default workflow to execute

# Example: Asset management configuration
[assets]
auto_download = true               # Automatically download missing models
cache_enabled = true               # Enable model caching
preload_essential_models = false   # Preload essential models on startup

# Example: Provider-specific preloading (only enabled providers load models)
[tts.providers.silero_v4]
enabled = true                     # REQUIRED: Provider must be enabled
preload_models = true              # Load models during startup

[tts.providers.silero_v3]
enabled = false                    # DISABLED: No model loading (skipped entirely)
preload_models = true              # Ignored because provider disabled

[asr.providers.whisper]
enabled = true                     # REQUIRED: Provider must be enabled
preload_models = true              # Load models during startup

[asr.providers.vosk]
enabled = false                    # DISABLED: No model loading (skipped entirely)
```

## Recent Configuration Architecture Improvements

### Clean Provider Schemas
The configuration system has been updated with provider-specific schemas:

- **SileroV3ProviderSchema**: v3-specific configuration (sample_rate=24000, put_accent, put_yo)
- **SileroV4ProviderSchema**: v4-specific configuration (sample_rate=48000, more speakers)
- **VoskASRProviderSchema**: ASR-specific configuration (confidence_threshold)
- **VoskTTSProviderSchema**: TTS-specific configuration (voice_speed)

### Asset Manager Integration
- **No model_path configuration**: All model paths managed by Asset Manager
- **Automatic model discovery**: Providers find models via `asset_manager.get_model_path()`
- **Unified model storage**: `IRENE_ASSETS_ROOT/models/{provider}/{model_id}`
- **Environment-driven**: Configure via `IRENE_ASSETS_ROOT` environment variable

### Preload Models Support
- **File-based models**: Support `preload_models` configuration for faster startup
- **Package-based models**: No preloading (SpaCy uses pip-installed packages)
- **API-based providers**: No local models to preload

### Provider Enablement Flow
1. **Configuration Check**: Only providers with `enabled: true` are instantiated
2. **Provider Discovery**: Entry-point system discovers available provider classes
3. **Provider Instantiation**: Only enabled providers are created and initialized
4. **Model Loading**: Only enabled providers can load/download models
5. **Component Registration**: Only enabled providers are registered with components

**Key Point**: Disabled providers (`enabled: false`) are completely skipped - no instantiation, no model loading, no resource usage.

## Implementation Plan: Default Workflow Initialization

### Phase 1: Basic Default Workflow Initialization ✅ COMPLETED

#### 1.1 WorkflowManager Constructor Changes ✅ COMPLETED
**File**: `irene/core/workflow_manager.py:36-43`

**Current**:
```python
def __init__(self, component_manager):
    self.component_manager = component_manager
    self.workflows: Dict[str, Workflow] = {}
    # ... other initialization
```

**Required Changes**:
```python
def __init__(self, component_manager, config):
    self.component_manager = component_manager
    self.config = config
    self.workflows: Dict[str, Workflow] = {}
    # ... other initialization
```

#### 1.2 AsyncVACore Constructor Update ✅ COMPLETED
**File**: `irene/core/engine.py:44`

**Current**:
```python
self.workflow_manager = WorkflowManager(self.component_manager)
```

**Required Changes**:
```python
self.workflow_manager = WorkflowManager(self.component_manager, config)
```

#### 1.3 Implement _create_workflows() Method ✅ COMPLETED
**File**: `irene/core/workflow_manager.py:54-58`

**Current**:
```python
async def _create_workflows(self) -> None:
    """Create and initialize workflow instances"""
    # No need to pre-create workflows anymore.
    # UnifiedVoiceAssistantWorkflow is created on-demand via _get_or_create_unified_workflow()
    logger.info("Workflow manager ready - workflows will be created on-demand")
```

**Required Implementation**:
```python
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
    
    # Initialize enabled workflows
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
    """Create and initialize a specific workflow"""
    if workflow_name == "unified_voice_assistant":
        # Create UnifiedVoiceAssistantWorkflow
        from ..workflows.voice_assistant import UnifiedVoiceAssistantWorkflow
        workflow = UnifiedVoiceAssistantWorkflow()
        await self._inject_components(workflow)
        await workflow.initialize()
        self.workflows[workflow_name] = workflow
    else:
        raise ValueError(f"Unknown workflow type: {workflow_name}")
```

#### 1.4 Update Logging ✅ COMPLETED
**File**: `irene/core/workflow_manager.py:52`

**Current**:
```python
logger.info(f"WorkflowManager initialized with workflows: {list(self.workflows.keys())}")
```

**Enhanced Logging**:
```python
initialized_workflows = list(self.workflows.keys())
logger.info(f"WorkflowManager initialized with workflows: {initialized_workflows}")

if self.active_workflow:
    logger.info(f"Active workflow: {self.active_workflow.name}")
else:
    logger.info("No active workflow set - will create on-demand")
```

### Phase 2: Enhanced State Management ✅ COMPLETED

#### 2.1 Workflow State Tracking ✅ COMPLETED
**File**: `irene/core/workflow_manager.py`

**Add Workflow States**:
```python
from enum import Enum

class WorkflowState(Enum):
    INITIALIZING = "initializing"
    WARMING_UP = "warming_up"  
    READY = "ready"
    ERROR = "error"

class WorkflowManager:
    def __init__(self, component_manager, config):
        # ... existing initialization
        self.workflow_states: Dict[str, WorkflowState] = {}
```

#### 2.2 Progressive Readiness Updates ✅ COMPLETED
**File**: `irene/core/workflow_manager.py`

**Add State Management Methods**:
```python
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
```

#### 2.3 Enhanced Status Reporting ✅ COMPLETED
**File**: `irene/core/workflow_manager.py:278-292`

**Update get_workflow_status() Method**:
```python
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
```

#### 2.4 Configuration Validation ✅ ALREADY IMPLEMENTED
**File**: `irene/config/validator.py` (new or existing)

**Add Workflow Validation**:
```python
def validate_workflow_configuration(self, config: CoreConfig) -> None:
    """Validate workflow configuration and dependencies"""
    workflows = config.workflows
    
    # Validate default workflow is in enabled list
    if workflows.default not in workflows.enabled:
        raise ConfigValidationError(
            f"Default workflow '{workflows.default}' not found in enabled workflows: {workflows.enabled}"
        )
    
    # Validate workflow names
    valid_workflows = ["unified_voice_assistant"]
    for workflow in workflows.enabled:
        if workflow not in valid_workflows:
            logger.warning(f"Unknown workflow '{workflow}' in configuration")
    
    # Validate component dependencies
    if "unified_voice_assistant" in workflows.enabled:
        required_components = ["intent_system", "nlu"]
        for component in required_components:
            if not getattr(config.components, component, False):
                raise ConfigValidationError(
                    f"Workflow 'unified_voice_assistant' requires component '{component}' to be enabled"
                )
```

### Phase 3: Advanced Features ✅ COMPLETED

#### 3.1 Model Loading Progress Monitoring ✅ COMPLETED
- ✅ Real-time asset manager integration
- ✅ Download progress tracking with periodic updates
- ✅ Progress percentage calculation and reporting
- ✅ User-facing progress indicators via logging

#### 3.2 Dynamic Workflow Management ✅ COMPLETED
- ✅ Runtime workflow switching with `switch_workflow()`
- ✅ Hot-reload workflow configurations with `hot_reload_workflow()`
- ✅ Workflow dependency management with `get_workflow_dependencies()`
- ✅ On-demand workflow creation with `create_workflow_on_demand()`

#### 3.3 Performance Optimizations ✅ COMPLETED
- ✅ Parallel workflow initialization for multiple workflows
- ✅ Component sharing analysis with `optimize_component_sharing()`
- ✅ Startup performance metrics with `get_startup_performance_metrics()`
- ✅ Automatic progress monitoring lifecycle management

## Error Handling and Graceful Degradation

### Backward Compatibility Strategy

1. **Configuration Fallbacks**: Missing workflow config falls back to on-demand creation
2. **Component Dependencies**: Workflows degrade gracefully when components unavailable
3. **Model Loading Failures**: Workflows operate with available providers only
4. **API Compatibility**: Existing `_get_or_create_unified_workflow()` unchanged

### Error Scenarios

1. **Missing Configuration**: Log warning, use on-demand creation
2. **Component Initialization Failure**: Create workflow with available components
3. **Model Loading Timeout**: Mark workflow as partially ready, continue startup
4. **Invalid Workflow Name**: Log error, skip invalid workflow, continue with valid ones

## Expected Outcome

### Successful Initialization Log
```
2025-08-21 14:24:19,130 - irene.core.workflow_manager - INFO - Initializing WorkflowManager...
2025-08-21 14:24:19,131 - irene.core.workflow_manager - INFO - Initializing enabled workflows: ['unified_voice_assistant']
2025-08-21 14:24:19,132 - irene.core.workflow_manager - INFO - ✅ Workflow 'unified_voice_assistant' initialized successfully
2025-08-21 14:24:19,132 - irene.core.workflow_manager - INFO - Set default workflow: unified_voice_assistant
2025-08-21 14:24:19,132 - irene.core.workflow_manager - INFO - WorkflowManager initialized with workflows: ['unified_voice_assistant']
2025-08-21 14:24:19,133 - irene.core.workflow_manager - INFO - Active workflow: unified_voice_assistant
2025-08-21 14:24:19,150 - irene.core.workflow_manager - INFO - Workflow 'unified_voice_assistant' state: warming_up → ready
```

### System Benefits

1. **Predictable Startup**: Default workflow always available after initialization
2. **Clear Status**: Visible workflow states and loading progress
3. **Better UX**: System reports readiness accurately
4. **Debugging**: Clear logs for troubleshooting startup issues
5. **Configuration-Driven**: Flexible workflow management via configuration

## Migration Path

### Phase 1 Implementation (Immediate)
- Low risk, high impact changes
- Maintains full backward compatibility
- Addresses the immediate logging issue

### Phase 2 Implementation (Short-term)
- Enhanced monitoring and status reporting
- Better user experience
- Improved debugging capabilities

### Phase 3 Implementation (Long-term)
- Advanced features for production deployments
- Performance optimizations
- Dynamic management capabilities

This implementation ensures that Irene Voice Assistant properly initializes default workflows at startup while maintaining system flexibility and robustness.

## Phase 4: Workflow Discovery Architecture ✅ COMPLETED

### Entry-Points Based Workflow Discovery ✅ COMPLETED

**Issue**: The WorkflowManager was using hardcoded workflow class imports instead of leveraging the existing entry-points discovery system used throughout the rest of the architecture.

**Solution**: Implemented entry-points based workflow discovery to bring workflows in line with the modern plugin architecture.

**Changes Made**:

#### 4.1 Dynamic Workflow Discovery ✅ COMPLETED
- **`discover_workflows()`**: Discovers available workflow classes via entry-points
- **`get_workflow_class()`**: Gets specific workflow class with validation
- **`list_available_workflow_names()`**: Lists all available workflows from entry-points
- **Entry-points Integration**: Uses existing `dynamic_loader.discover_providers("irene.workflows")`

#### 4.2 Enhanced Workflow Creation ✅ COMPLETED
- **Dynamic Instantiation**: Replaces hardcoded `if workflow_name == "unified_voice_assistant"` 
- **Entry-Points Only**: No fallback mechanism - workflows must be registered via entry-points
- **Class Validation**: Ensures discovered classes inherit from Workflow base class
- **Fatal Error Handling**: Clear error messages when workflows not found in entry-points

#### 4.3 API Consistency ✅ COMPLETED
- **`get_available_workflows()`**: Now uses entry-points instead of current workflow instances
- **`create_workflow_on_demand()`**: Validates against discovered workflows first
- **`_get_or_create_unified_workflow()`**: Updated to use discovery system

### Benefits Achieved:

1. **Architectural Consistency**: Workflows now follow the same entry-points pattern as providers, components, and inputs
2. **Plugin Extensibility**: External packages can register workflows via entry-points without core code changes
3. **Configuration-Driven**: Workflow availability determined by entry-points, not hardcoded logic
4. **No Hardcoding**: Completely eliminates hardcoded workflow mappings - pure entry-points based
5. **Clear Error Messages**: Fatal errors with helpful guidance when workflows not registered properly

### Entry-Points Configuration:

```toml
[project.entry-points."irene.workflows"]
unified_voice_assistant = "irene.workflows.voice_assistant:UnifiedVoiceAssistantWorkflow"
custom_workflow = "external_package.workflows:CustomWorkflow"
```

The system now automatically discovers and validates all registered workflows, eliminating the need for hardcoded workflow mappings and enabling true plugin-based workflow architecture.
