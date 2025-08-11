## 6. Unified Command Flow Architecture Issue (System-Wide)

**Status:** Open  
**Priority:** Critical  
**Scope:** Entire command processing architecture  
**Components:** All CommandPlugin implementations, CLI runner, WebAPI runner, Core engine  

### Problem

**Fundamental architectural inconsistency**: The system has **multiple competing command processing pipelines** instead of the intended **unified flow design**.

#### **Intended Design (Unified Flow)**
**Single pipeline with 3 entry points:**
- **Voice Assistant**: `Audio → Voice Trigger → ASR → Text Processing → NLU → Intent → Response (+TTS)`
- **Command Line**: `Text → [Skip Voice+ASR] → Text Processing → NLU → Intent → Response (+TTS)`  
- **WebAPI**: `WebSocket → [Skip Voice Trigger] → ASR → Text Processing → NLU → Intent → Response (+TTS)`

**Principle:** All flows are **permutations of the same pipeline**, starting at different stages.
**TTS Integration:** Optional TTS output available for all three entry points based on context and configuration.

#### **Current Reality (Multiple Broken Systems)**
1. **Pipeline Fragmentation**: 3 separate command processing systems competing
2. **Entry Point Confusion**: Different input sources use different processing paths
3. **Component Isolation**: Components implement CommandPlugin but are never integrated
4. **Legacy Dependencies**: Core systems depend on broken CommandProcessor architecture

### Current Implementation Analysis (MECE Framework)

#### A. Entry Point Deviations

##### A.1 CLI Entry Point (❌ Wrong Pipeline)
```python
# irene/runners/cli.py lines 306, 343, 463, 508
await core.process_command(args.command)  # Goes to legacy CommandProcessor!

# Should be:
await workflow_manager.process_text_input(text, session_id)
```
**Problem:** CLI bypasses unified workflow entirely.

##### A.2 WebAPI Entry Point (🔧 Dual Path)
```python
# irene/runners/webapi_runner.py lines 604-617
if not workflow_manager:
    await self.core.process_command(request.text)  # Legacy fallback
else:
    result = await workflow_manager.process_text_input(request.text)  # Correct path
```
**Problem:** WebAPI has competing processing paths.

##### A.3 Voice Entry Point (✅ Correct)
```python
# irene/workflows/voice_assistant.py - Working as intended
Audio → Voice Trigger → ASR → Text Processing → NLU → Intent → Response
```

#### B. Component Command Handling (💀 Orphaned)

##### B.1 AudioComponent Hardcoded Patterns
```python
# Lines 271, 285-286
"играй", "воспроизведи", "останови", "стоп", "музыка", "аудио"
if "играй" in command_lower or "воспроизведи" in command_lower:
    return CommandResult(success=True, response="Команды воспроизведения аудио доступны через веб-API")
```

##### B.2 LLMComponent Hardcoded Patterns
```python
# Lines 174, 183, 191
if "улучши" in command or "исправь" in command:
elif "переведи" in command:
elif "переключись на" in command:
```

##### B.3 ASRComponent Hardcoded Patterns
```python
# Lines 171, 174, 182
if "покажи распознавание" in command or "покажи провайдеры" in command:
elif "переключись на" in command:
elif "язык" in command:
```

##### B.4 TTSComponent Hardcoded Patterns
```python
# Lines 395, 400, 405
if "скажи" in command_lower and "голосом" in command_lower:
elif "переключись на" in command_lower:
elif any(phrase in command_lower for phrase in ["покажи голоса", "список голосов"]):
```

**Critical Issue:** All component `handle_command()` methods are **never called** - components aren't registered with CommandProcessor.

#### C. Legacy System Dependencies

##### C.1 Core Engine Integration
```python
# irene/core/engine.py lines 120-131
async def process_command(self, command: str, context: Optional[Context] = None):
    result = await self.command_processor.process(command, context)  # Wrong system!
```

##### C.2 CommandProcessor System
```python
# irene/core/commands.py - Manages registration but components never register
# Only builtin plugins register, not components
```

##### C.3 Component Registration Gap
```python
# ComponentManager loads components but never registers them with CommandProcessor
# Result: Command handling infrastructure exists but is disconnected
```

### Open Questions (Must Be Resolved Before Implementation)

#### Q1. Unified Pipeline Entry Point Strategy ✅ **RESOLVED**
**Decision:** Option B+ - Enhanced separate methods with single unified workflow

**Chosen Architecture:**
- **Enhanced separate methods**: `process_text_input()` and `process_audio_stream()` with unified parameters
- **Single unified workflow**: `UnifiedVoiceAssistantWorkflow` replaces multiple workflow types
- **Conditional pipeline stages**: Same `_process_pipeline()` method with stage skipping based on input type
- **Universal TTS**: Optional TTS output available for all entry points via `wants_audio` parameter

**Interface Design:**
```python
# WorkflowManager Enhanced Interface
async def process_text_input(
    text: str, session_id: str = "default", wants_audio: bool = False,
    client_context: Optional[Dict[str, Any]] = None
) -> IntentResult

async def process_audio_stream(
    audio_stream: AsyncIterator[AudioData], session_id: str = "default", 
    skip_wake_word: bool = False, wants_audio: bool = True,
    client_context: Optional[Dict[str, Any]] = None
) -> AsyncIterator[IntentResult]
```

**Entry Point Mapping:**
- **CLI**: `process_text_input(wants_audio=args.enable_tts)`
- **WebAPI Text**: `process_text_input(wants_audio=request.wants_audio)`
- **WebAPI Audio**: `process_audio_stream(skip_wake_word=True)`
- **Voice**: `process_audio_stream(skip_wake_word=False, wants_audio=True)`

#### Q2. Legacy `core.process_command()` Migration Strategy ✅ **RESOLVED**
**Decision:** Option A - Complete migration (delete and update all call sites)

**Rationale:** Since project is not yet released, we can safely break API without backward compatibility concerns.

**Migration Strategy:**
- **Delete** `core.process_command()` method entirely
- **Update all 19+ call sites** to use `core.workflow_manager.process_text_input()`
- **Remove** `core.command_processor` dependency
- **Update** examples, tests, CLI, and WebAPI runners
- **Add** `workflow_manager` initialization to `AsyncVACore.start()`

**Call Site Migration Pattern:**
```python
# Old:
await core.process_command(text)

# New:
await core.workflow_manager.process_text_input(
    text=text,
    session_id=session_id,
    wants_audio=context_wants_audio,
    client_context=client_info
)
```

#### Q3. Component CommandPlugin Interface Resolution ✅ **RESOLVED**
**Decision:** Option B - Convert hardcoded logic to proper intent handlers with component-specific analysis

**Component-by-Component Intent Handler Mapping:**

**Functional Intent Handlers (User-Facing Features):**
1. **`AudioPlaybackIntentHandler`** - Audio/music control commands
   - "играй музыку", "останови аудио", "воспроизведи файл"
   - Delegates to AudioComponent for actual playback control

2. **`TranslationIntentHandler`** - Text translation commands  
   - "переведи [text]", "переведи [text] на [language]"
   - Delegates to LLMComponent.enhance_text() with translation task

3. **`TextEnhancementIntentHandler`** - Text improvement commands
   - "улучши [text]", "исправь [text]", "поправь [text]"
   - Delegates to LLMComponent.enhance_text() with improvement task

4. **`VoiceSynthesisIntentHandler`** - TTS with specific voices
   - "скажи [text] голосом [voice]", "покажи голоса"
   - Delegates to TTSComponent for voice-specific synthesis

**System Control Intent Handlers (Configuration):**
5. **`ProviderControlIntentHandler`** - Provider switching (shared across components)
   - "переключись на [provider]", "покажи провайдеры [component]"
   - Delegates to appropriate component's switch_provider() method

6. **`SpeechRecognitionIntentHandler`** - ASR configuration
   - "покажи распознавание", "переключи язык на [language]"
   - Delegates to ASRComponent configuration methods

**Implementation Strategy:**
- Remove `CommandPlugin` interface from all components
- Convert `handle_command()` logic to public component methods  
- Create 6 specific intent handlers with JSON pattern configuration
- Intent handlers delegate to component methods for actual functionality
- Preserve all existing functionality while fixing architecture

#### Q4. CommandProcessor and Legacy System Elimination ✅ **RESOLVED**
**Decision:** Option A - Complete removal of entire CommandProcessor system

**Rationale:** Clean architectural purity with single command processing system through intent handlers.

**Complete Removal Strategy:**
- **Delete CommandProcessor infrastructure**: `irene/core/commands.py`, `irene/core/interfaces/command.py`
- **Remove from AsyncVACore**: Delete `command_processor`, `_load_builtin_plugins()` method
- **Migrate 2 builtin plugins to intent handlers**:
  - `RandomPlugin` → `RandomIntentHandler` ("подбрось монету", "брось кубик")
  - `AsyncServiceDemoPlugin` → `SystemServiceIntentHandler` ("service status")
- **Delete plugin base classes**: Remove `BaseCommandPlugin` from `irene/plugins/base.py`
- **Clean configuration**: Remove `builtin_plugins` config section

**Benefits:**
- Single command processing system (intent-based only)
- No dual systems or adapter patterns
- Consistent behavior across all command types
- Simplified testing and maintenance
- Unified command configuration through intent JSON files

**Migration Impact:** Low - only 2 simple builtin plugins to convert, same user functionality preserved

#### Q5. WebAPI Entry Point Unification ✅ **RESOLVED**
**Decision:** Complete unification with voice trigger bypass for all WebAPI audio inputs

**WebAPI Entry Point Mapping:**
- **Text Endpoints**: `workflow_manager.process_text_input(wants_audio=request.wants_audio)`
  - Skip voice trigger + ASR stages
  - Direct to text processing → NLU → Intent → Response
  - Optional TTS based on client preference

- **Audio Upload Endpoints**: `workflow_manager.process_audio_stream(skip_wake_word=True)`
  - Skip voice trigger, process through ASR
  - ASR → Text Processing → NLU → Intent → Response
  - Optional TTS based on client preference

- **WebSocket Audio Streaming**: `workflow_manager.process_audio_stream(skip_wake_word=True)`
  - Real-time audio streaming with immediate ASR processing
  - No wake word detection (user explicitly sends audio)
  - Same pipeline convergence as other audio sources

**Voice Trigger Decision:** Always bypass for WebAPI because:
- User control: WebAPI users explicitly send audio
- Efficiency: No unnecessary wake word processing overhead
- Predictability: Immediate processing of all uploaded audio
- API Consistency: All WebAPI audio treated as intentional input

**Unified Pipeline Convergence:** All WebAPI inputs (text/audio) converge on same NLU → Intent → Response stages, maintaining consistency with CLI and voice entry points.

#### Q6. Pipeline Action Execution Framework ✅ **RESOLVED**
**Decision:** Fire-and-forget action execution with context-aware action tracking

**Core Architecture:**
- **Response-Action Decoupling**: Voice assistant completes response generation before action execution
- **Fire-and-Forget Pattern**: Intent handlers execute actions directly and return result immediately
- **Dependency Isolation**: Action dependencies contained within specific intent handlers only
- **Build Modularity**: Excluding intent handlers removes their action dependencies from build
- **Unified Security**: All entry points (CLI, WebAPI, Voice) have identical action capabilities

**Action Context Management:**
```python
# Enhanced ConversationContext fields
active_actions: Dict[str, Any] = field(default_factory=dict)      # Currently running actions
recent_actions: List[Dict[str, Any]] = field(default_factory=list) # Recently completed/failed actions

# Enhanced IntentResult for action metadata
@dataclass  
class IntentResult:
    text: str
    should_speak: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    actions: List[str] = field(default_factory=list)        # Deprecated - kept for compatibility
    action_metadata: Dict[str, Any] = field(default_factory=dict)  # NEW: Action context updates
    success: bool = True
    # ... other fields
```

**Action Lifecycle:**
1. **Initiation**: Intent handler executes action via `asyncio.create_task()` 
2. **Context Update**: Handler returns `action_metadata` with active action info
3. **Workflow Processing**: Workflow merges `action_metadata` into `ConversationContext`
4. **Completion Tracking**: Background tasks update context when actions complete/fail
5. **Context Awareness**: "stop" commands use action history for disambiguation

**Example Implementation:**
```python
class SmartHomeIntentHandler(IntentHandler):
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        # Fire-and-forget execution
        task = asyncio.create_task(self.controller.turn_on_lights(intent.entities))
        
        return IntentResult(
            text="Включаю свет",
            should_speak=True,
            action_metadata={
                "active_action": {
                    "lights": {
                        "handler": "smart_home", 
                        "action": "turn_on",
                        "started_at": time.time(),
                        "task_id": id(task)
                    }
                }
            }
        )
```

**Ambiguity Resolution:**
- **Domain Priority**: Configure in TOML (`music=100, smart_home=80, timers=70`)
- **Most Recent Fallback**: If same priority, choose most recently started action
- **Multi-Action Scenarios**: System asks "Stop music or vacuum cleaner?"

**Error Handling:**
- **Immediate Response**: TTS responds immediately ("Turning on lights")
- **Failure Follow-up**: Send notification if action fails ("Light connection failed")
- **Context Update**: Mark failed actions in `recent_actions` with error status
- **Silent Fallback**: If follow-up impossible, fail silently without user notification

**Scope & Persistence:**
- **Session + Device Based**: Actions tied to `session_id` + `client_id` combination
- **Session Timeout**: Actions expire with conversation context (30 minutes default)
- **Room Isolation**: Kitchen actions don't affect living room ambiguity resolution

### Proposed Solutions (MECE Approach)

#### Option A: Complete Unified Pipeline Implementation (Recommended)
**Scope:** Entire command processing architecture

##### A.1 Pipeline Unification ✅ **RESOLVED**
- Implement `UnifiedVoiceAssistantWorkflow` with single `_process_pipeline()` method
- Enhanced `process_text_input()` and `process_audio_stream()` methods with unified parameters
- Remove competing command processing paths (CommandProcessor system)
- Ensure all input sources converge on unified pipeline with conditional stages

##### A.2 Entry Point Standardization ✅ **RESOLVED**
- **CLI**: `workflow_manager.process_text_input(wants_audio=args.enable_tts)`
- **WebAPI Text**: `workflow_manager.process_text_input(wants_audio=request.wants_audio)`
- **WebAPI Audio**: `workflow_manager.process_audio_stream(skip_wake_word=True)`
- **Voice**: `workflow_manager.process_audio_stream(skip_wake_word=False, wants_audio=True)`

##### A.3 Legacy System Removal ✅ **RESOLVED**
- Delete `core.process_command()` method (Q2: complete migration)
- Complete CommandProcessor system removal (Q4: full removal decided)
- Convert component commands to 6 specific intent handlers (Q3: resolved mapping)
- Migrate 2 builtin plugins to intent handlers (Q4: RandomPlugin + AsyncServiceDemoPlugin)

##### A.4 Benefits
- Single processing pipeline with clear entry points
- Consistent behavior across all input sources
- Clean architecture without competing systems

#### Option B: Gradual Migration Framework
**Scope:** Phased transition approach

##### B.1 Wrapper Integration
- Keep `core.process_command()` as wrapper around workflow manager
- Add deprecation warnings and migration guidance
- Gradually update call sites

##### B.2 Dual System Support
- Maintain CommandProcessor for builtin plugins
- Route component commands through intent system
- Support both until transition complete

##### B.3 Trade-offs
- Preserves backward compatibility during transition
- More complex interim architecture
- Risk of incomplete migration

### Impact Assessment (MECE Analysis)

#### A. Technical Impact
- **Architecture:** Complete unification of command processing pipelines
- **Performance:** Elimination of redundant command processing overhead
- **Maintainability:** Single point of truth for command flow logic
- **Testability:** Unified testing approach across all input sources

#### B. Development Impact  
- **Effort:** High - requires changes across CLI, WebAPI, Core engine, and all components
- **Risk:** Medium - affects core system behavior and requires careful migration
- **Timeline:** Must address all open questions before implementation can begin
- **Scope:** 19+ call sites need updates, 4 components need CommandPlugin removal

#### C. Operational Impact
- **User Experience:** Consistent behavior across CLI, WebAPI, and voice interfaces
- **Configuration:** Unified command configuration through intent system
- **Deployment:** Simplified architecture reduces operational complexity
- **Backward Compatibility:** Breaking changes require careful migration strategy

### Implementation Dependencies (MECE Analysis)

#### A. Decision Dependencies
Open questions status (ALL RESOLVED):
- ✅ Q1 affects pipeline architecture design - **RESOLVED**
- ✅ Q2 affects migration scope and timeline - **RESOLVED**
- ✅ Q3 affects component interface design - **RESOLVED**
- ✅ Q4 affects legacy system cleanup scope - **RESOLVED**
- ✅ Q5 affects WebAPI architecture - **RESOLVED**
- ✅ Q6 affects action execution framework and response flow design - **RESOLVED**

#### B. Code Dependencies
- **High Priority:** `irene/core/engine.py` - Core command processing
- **High Priority:** `irene/runners/cli.py` - CLI entry point
- **High Priority:** `irene/runners/webapi_runner.py` - WebAPI entry point
- **Medium Priority:** All component `handle_command()` implementations
- **Medium Priority:** Examples and tests using `core.process_command()`

#### C. System Dependencies
- Intent system must support component control commands and action execution
- Workflow manager must handle all input types with optional TTS output
- Component manager integration with unified pipeline
- Configuration system updates for unified flow and action management
- Action execution framework integration with intent orchestrator
- TTS routing logic for all entry points (CLI, WebAPI, Voice)

### Related Files (Comprehensive)

#### Entry Point Files (Critical):
- `irene/core/engine.py` (lines 120-139) - process_command method
- `irene/runners/cli.py` (lines 306, 343, 463, 508) - CLI command processing
- `irene/runners/webapi_runner.py` (lines 604-617) - WebAPI command processing
- `irene/core/workflow_manager.py` (lines 212-234) - Unified text processing

#### Component Files (CommandPlugin Removal):
- `irene/components/audio_component.py` (lines 271, 281-301)
- `irene/components/llm_component.py` (lines 172-199)
- `irene/components/asr_component.py` (lines 169-187)
- `irene/components/tts_component.py` (lines 390-419)

#### Legacy System Files (Potential Removal):
- `irene/core/commands.py` (CommandProcessor system)
- `irene/core/interfaces/command.py` (CommandPlugin interface)

#### Integration Files:
- `irene/intents/handlers/` (intent handler integration)
- `irene/workflows/voice_assistant.py` (working pipeline reference)
- Examples and tests across `irene/examples/` and `irene/tests/`

## 🚀 Implementation Plan

Based on the complete architectural analysis and all 6 resolved questions, the implementation is structured in 5 phases for systematic migration from legacy multiple pipelines to the unified architecture.

### Phase 1: Foundation & Models Enhancement
**Objective:** Prepare data models and core infrastructure for unified pipeline

**Key Changes:**
- **Enhance `IntentResult` model** with `action_metadata` field for fire-and-forget actions
- **Extend `ConversationContext`** with `active_actions` and `recent_actions` fields for action tracking
- **Update configuration schema** to support action domain priorities (`music=100, smart_home=80, timers=70`)
- **Create `UnifiedVoiceAssistantWorkflow`** class with conditional pipeline stages

**Files Modified:**
- `irene/intents/models.py` - Add action tracking fields and enhanced IntentResult
- `irene/workflows/voice_assistant.py` - Create UnifiedVoiceAssistantWorkflow
- `configs/*.toml` - Add action priority configuration section

**Success Criteria:**
- ✅ Models support action context tracking
- ✅ Unified workflow class ready for all entry points
- ✅ Configuration supports action ambiguity resolution

### Phase 2: Enhanced Workflow Manager Interface
**Objective:** Implement Q1 decision with enhanced WorkflowManager methods

**Key Changes:**
- **Enhance `WorkflowManager.process_text_input()`** with `wants_audio` and `client_context` parameters
- **Implement `WorkflowManager.process_audio_stream()`** with `skip_wake_word` parameter
- **Integrate `UnifiedVoiceAssistantWorkflow`** as the single workflow for all entry points
- **Add action metadata processing** to merge action context into conversation context

**Files Modified:**
- `irene/core/workflow_manager.py` - Enhanced interface methods
- `irene/workflows/base.py` - Support for conditional pipeline stages
- `irene/core/engine.py` - Ensure workflow_manager initialization

**Success Criteria:**
- ✅ Single workflow supports all 3 entry points (Voice, CLI, WebAPI)
- ✅ Conditional stage skipping (voice trigger, ASR) based on input type
- ✅ Action metadata flows from handlers to conversation context

### Phase 3: Legacy System Migration (Q2 + Q4)
**Objective:** Complete elimination of CommandProcessor system and process_command() migration

**Key Changes:**
- **Delete `core.process_command()`** method entirely
- **Migrate 19+ call sites** to use `workflow_manager.process_text_input()`
- **Remove CommandProcessor infrastructure** (`irene/core/commands.py`, `irene/core/interfaces/command.py`)
- **Migrate builtin plugins** to intent handlers (`RandomIntentHandler`, `SystemServiceIntentHandler`)
- **Update CLI and WebAPI runners** to use unified workflow interface

**Files Modified:**
- `irene/core/engine.py` - Delete process_command(), remove CommandProcessor dependency
- `irene/runners/cli.py` - Update all process_command() calls
- `irene/runners/webapi_runner.py` - Remove dual-path, use unified workflow only
- `irene/examples/*.py` - Update all example code
- `irene/tests/*.py` - Update all test cases
- Delete: `irene/core/commands.py`, `irene/core/interfaces/command.py`
- `irene/intents/handlers/` - Add RandomIntentHandler, SystemServiceIntentHandler

**Success Criteria:**
- ✅ No `core.process_command()` calls exist in codebase
- ✅ CommandProcessor system completely removed
- ✅ All entry points use unified workflow interface
- ✅ Builtin plugins converted to intent handlers

### Phase 4: Component CommandPlugin Removal (Q3)
**Objective:** Convert component hardcoded commands to proper intent handlers

**Key Changes:**
- **Remove `CommandPlugin` interface** from all components (Audio, LLM, ASR, TTS)
- **Extract component command logic** to public methods for delegation
- **Create 6 specific intent handlers** with JSON donation patterns:
  - `AudioPlaybackIntentHandler` - Music/audio control
  - `TranslationIntentHandler` - Text translation via LLM  
  - `TextEnhancementIntentHandler` - Text improvement via LLM
  - `VoiceSynthesisIntentHandler` - TTS with specific voices
  - `ProviderControlIntentHandler` - Provider switching across components
  - `SpeechRecognitionIntentHandler` - ASR configuration
- **Create JSON donation files** for pattern matching instead of hardcoded Russian strings

**Files Modified:**
- `irene/components/audio_component.py` - Remove CommandPlugin, extract audio control methods
- `irene/components/llm_component.py` - Remove CommandPlugin, extract translation/enhancement methods  
- `irene/components/asr_component.py` - Remove CommandPlugin, extract configuration methods
- `irene/components/tts_component.py` - Remove CommandPlugin, extract voice synthesis methods
- `irene/intents/handlers/` - Create 6 new intent handlers
- `irene/intents/handlers/*.json` - Create donation files with Russian command patterns

**Success Criteria:**
- ✅ No components implement CommandPlugin interface
- ✅ All hardcoded command logic moved to proper intent handlers
- ✅ Component functionality preserved through delegation
- ✅ Commands work through unified intent system

### Phase 5: WebAPI Unification & Action Framework (Q5 + Q6)
**Objective:** Complete WebAPI unification and implement fire-and-forget action execution

**Key Changes:**
- **Unify WebAPI entry points** with voice trigger bypass for all audio inputs
- **Implement action execution framework** with fire-and-forget pattern in intent handlers
- **Add action ambiguity resolution** using domain priority configuration
- **Implement action failure follow-up** with context updates
- **Add TTS support** for all entry points based on client preferences

**Files Modified:**
- `irene/runners/webapi_runner.py` - Complete unification, remove legacy fallbacks
- `irene/intents/handlers/base.py` - Helper methods for action execution patterns
- Example action intent handlers (smart home, media control) for demonstration
- `irene/core/workflow_manager.py` - Action metadata processing and context updates
- `irene/intents/context.py` - Action ambiguity resolution logic

**Success Criteria:**
- ✅ WebAPI audio always bypasses voice trigger (user control + efficiency)  
- ✅ All entry points support optional TTS based on client preferences
- ✅ Intent handlers execute actions via fire-and-forget pattern
- ✅ Action context tracking enables "stop" command disambiguation
- ✅ Action failures trigger follow-up notifications when possible

### 📊 Implementation Dependencies

**Phase Dependencies:**
- Phase 1 → Phase 2 (models must exist before workflow enhancement)
- Phase 2 → Phase 3 (enhanced workflow interface needed before migration)  
- Phase 3 ⊥ Phase 4 (legacy removal and component conversion can be parallel)
- Phase 4 → Phase 5 (intent handlers needed before action framework)

**Estimated Timeline:**
- **Phase 1-2**: 2-3 days (foundation & interface)
- **Phase 3**: 3-4 days (comprehensive migration, many files)
- **Phase 4**: 2-3 days (component conversion, JSON donations)
- **Phase 5**: 2-3 days (WebAPI unification, action framework)
- **Total**: ~10-13 days for complete unified architecture

**Risk Mitigation:**
- Phases 1-2 are foundational and low-risk
- Phase 3 has highest impact but clear migration pattern
- Phases 4-5 preserve all user functionality while fixing architecture
- Comprehensive testing at each phase boundary

