# TODO16: General Command Disambiguation & Context-Aware Action Resolution

## Overview

The current implementation has fragmented and hardcoded approaches to command disambiguation. The "stop" command handling is just one example of a broader need for **context-aware command resolution** that can handle ambiguous commands across multiple active actions and domains.

## Current State Analysis (Updated 2025-01-27)

### What We Have ✅

#### 1. **Robust Context-Aware Infrastructure (Already Excellent)**
- **`ContextAwareNLUProcessor`**: Client identification, device context, entity resolution
- **`ContextualEntityResolver`**: Multi-type entity resolution with context awareness
- **`ConversationContext`**: Comprehensive active actions tracking (`active_actions`, `recent_actions`, `failed_actions`)
- **`ContextManager`**: Session management with **sophisticated unused disambiguation logic**
- **`RequestContext`**: Client-aware workflow processing

#### 2. **Sophisticated Action Tracking (Working Well)**
- `ConversationContext.active_actions` - Domain-based action tracking with metadata
- Fire-and-forget action framework with timeout/retry capabilities
- Action completion and failure tracking with detailed metadata
- Cross-session action state management

#### 3. **Donation-Based Domain Priorities (Fragmented)**
```json
// assets/donations/audio_playback_handler/ru.json
"action_domain_priority": 90
// assets/donations/timer_handler/ru.json  
"action_domain_priority": 70
// assets/donations/voice_synthesis_handler/ru.json
"action_domain_priority": 60
```

#### 4. **Externalized Localization (Modern)**
- `assets/localization/commands/{language}.yaml` - Command patterns externalized
- `assets/localization/domains/{language}.yaml` - Domain hints externalized
- Multi-language support with proper asset management

#### 5. **Central Orchestration Points (Ready for Integration)**
- **`IntentOrchestrator`**: Central intent routing and execution
- **`IntentHandlerManager`**: Handler discovery, registration, donation loading
- **`IntentRegistry`**: Handler capability management

#### 6. **NLU Cascade System (Critical Integration Point)**
- **`NLUComponent.recognize()`**: Cascading providers (`["hybrid_keyword_matcher", "spacy_nlu"]`)
- **Provider cascade**: Up to 4 attempts with 200ms timeout per attempt
- **Fallback logic**: Failed recognition → `conversation.general` with `"_recognition_provider": "fallback"`
- **⚠️ Integration Gap**: Contextual commands should be recognized during NLU cascade, not in orchestrator

#### 7. **Fire-and-Forget Action Termination (Active)**
- **`ConversationContext.active_actions`**: Domain-based tracking of running actions
- **`ConversationContext.cancel_action()`**: Marks actions for cancellation
- **`ConversationContext.remove_completed_action()`**: Moves completed actions to history
- **Handler-specific state**: Each handler maintains own action state (e.g., `TimerHandler.active_timers`)
- **⚠️ Synchronization Gap**: Context tracking vs actual running task state coordination

### What's Broken ❌

#### 1. **Stop-Specific Command Framework (Must Be Generalized)**
```python
# PROBLEM: Stop-specific implementation in base.py
def parse_stop_command(self, intent: Intent) -> Optional[Dict[str, Any]]:
    # Hard-coded for "stop" only - needs to be generic
    
# PROBLEM: Each handler duplicates stop logic
async def _handle_stop_command(self, stop_info: dict, context: ConversationContext):
    target_domains = stop_info.get("target_domains", [])
    if not target_domains or "timer" in target_domains:
        # Handler-specific logic repeats across handlers
```

#### 2. **No Cross-Handler Coordination**
- Each handler calls `parse_stop_command()` independently 
- No centralized decision when multiple domains have active actions
- User says "стоп" with timer + music + lights → fragmented processing

#### 3. **Sophisticated Logic Successfully Integrated** ✅ **COMPLETED**
- **`resolve_contextual_command_ambiguity()` in `ContextManager` is actively used**
- Contains domain priority resolution, recency fallback, target filtering
- **Old stop-specific method removed - generalized method now handles all contextual commands**

#### 4. **Domain Priority Configuration Fragmentation**
- Priorities exist in donation files but are never loaded centrally
- No unified domain priority configuration in `config-master.toml`
- No runtime mechanism to apply priorities across handlers

#### 5. **NLU Cascade vs Contextual Command Recognition Gap**
- **Current**: Orchestrator tries to parse contextual commands after NLU recognition
- **Problem**: "stop" is already recognized as specific intent by NLU providers
- **Missing**: NLU providers should distinguish `"stop"` → `contextual.stop` vs `"stop music"` → `audio.stop`

#### 6. **Fire-and-Forget Action Termination Inconsistency**
- **Current**: Handler-specific termination logic in each `_handle_stop_command()`
- **Problem**: Duplicate termination patterns, no unified action lifecycle management
- **Missing**: Clear mechanism for stop/cancel/abort commands to terminate active fire-and-forget actions
- **Synchronization Issue**: `ConversationContext.active_actions` vs handler-specific state (e.g., `TimerHandler.active_timers`)

## The Real Problem: Generic Contextual Commands (Confirmed by Analysis)

**Analysis findings show multiple contextual commands already exist in donation files:**

### Confirmed Contextual Commands in System
1. **"stop/стоп"** → Found in: audio, timer, voice_synthesis handlers
2. **"pause/пауза"** → Found in: timer (`"pause"`), audio (`"pause audio"`)
3. **"resume/продолжи"** → Found in: timer (`"resume"`), audio (`"resume"`)
4. **"cancel/отмени"** → Found in: timer (`"cancel timer"`), voice_synthesis (`"cancel synthesis"`)
5. **"next/previous"** → Found in: audio (`"next"`, `"previous"`)
6. **"volume/громче"** → Found in: audio (`"volume"`)

### Current Implementation Proves The Problem
```json
// Every handler duplicates contextual command patterns:
// timer_handler/en.json:
"action_patterns": ["stop", "pause", "resume", "cancel"]

// audio_playback_handler/en.json:  
"action_patterns": ["stop", "pause", "resume", "next", "previous", "volume"]

// voice_synthesis_handler/en.json:
"stop_command_patterns": ["stop speech", "cancel synthesis"]
```

### Existing Disambiguation Factors (From `ContextManager.resolve_contextual_command_ambiguity()`)
1. **Active Fire-and-Forget Actions** - Primary context source from `ConversationContext.active_actions`
2. **Domain Priority** - `domain_priorities.get(domain, 0)` (from parameters)
3. **Target Domain Filtering** - `target_domains` from command parsing  
4. **Recency Fallback** - `started_at` timestamp comparison for tie-breaking
5. **Action State Awareness** - Active vs recent actions separation

### Critical Insight: Fire-and-Forget Actions Define Context
**Active fire-and-forget actions are the PRIMARY disambiguation source:**
```python
# If audio playback is active:
active_actions = {"audio": {"action": "play_music", "started_at": 123456}}
# → "stop/pause/louder" commands target audio domain

# If timer + audio both active:
active_actions = {
    "audio": {"action": "play_music", "started_at": 123456},  
    "timers": {"action": "set_timer", "started_at": 123457}
}
# → Domain priorities resolve ambiguity (audio=90 > timers=70)
```

## MECE Implementation Plan

**Strategy: Leverage existing sophisticated infrastructure, generalize stop-specific patterns**

### Architecture: Three Connected Systems

#### 1. **Contextual Command Preprocessing (New)**
```python
class ContextualCommandProcessor:
    """
    Generalized version of parse_stop_command() for any contextual command.
    Integrates with IntentOrchestrator for cross-handler coordination.
    """
    
    def parse_contextual_command(
        self,
        intent: Intent,
        command_types: List[str] = ["stop", "pause", "resume", "cancel", "volume"]
    ) -> Optional[ContextualCommandInfo]:
        """Generic command parsing using existing localization infrastructure"""
        pass
        
    def should_coordinate_across_handlers(
        self,
        command_info: ContextualCommandInfo,
        active_actions: Dict[str, Any]
    ) -> bool:
        """Determine if cross-handler coordination is needed"""
        pass
```

#### 2. **Domain Priority Management (Centralize Existing)**
```python  
class DomainPriorityManager:
    """
    Centralizes domain priorities from donation files and config.
    Extends existing donation loading in IntentHandlerManager.
    """
    
    def load_priorities_from_donations(self) -> Dict[str, int]:
        """Extract action_domain_priority from all donation files"""
        pass
        
    def get_unified_priorities(self) -> Dict[str, int]:
        """Merge donation priorities with config overrides"""
        pass
```

#### 3. **Generic Disambiguation Engine (Enhance Existing)**
```python
class ContextualCommandResolver:
    """
    ✅ IMPLEMENTED: ContextManager.resolve_contextual_command_ambiguity()
    now works with any contextual command type (stop, pause, resume, cancel, etc.).
    """
    
    def resolve_command_ambiguity(
        self,
        session_id: str,
        command_info: ContextualCommandInfo,  # Generalized from stop_info
        domain_priorities: Dict[str, int] = None
    ) -> ContextualCommandResolution:
        """Generalized version of existing sophisticated logic"""
        pass
```

## MECE Implementation Plan

**Principle**: Build on existing sophisticated infrastructure, minimal disruption, maximum reuse

---

### 🏗️ **Phase 1: Foundation Integration (Connect Existing Systems)**

**Duration**: 2-3 days  
**Principle**: Connect unused sophisticated logic to actual command flow

#### 1.1 **Domain Priority Centralization**
- **Add domain priorities to `config-master.toml`**:
  ```toml
  [actions.domain_priorities]
  audio = 90      # From donation files analysis
  timers = 70     # From donation files analysis  
  voice_synthesis = 60  # From donation files analysis
  system = 50     # Default for system commands
  ```
- **Extend `DomainPriorityManager` in `IntentHandlerManager`**:
  - Load priorities from donation files during handler initialization
  - Merge with config overrides
  - Provide unified priority access

#### 1.2 **NLU Cascade Integration (Critical Architecture Fix)**
- **Enhance NLU providers to recognize contextual vs specific intents**:
  ```python
  # NLU Provider Recognition:
  "stop" → Intent(name="contextual.stop", domain="contextual", action="stop")
  "stop music" → Intent(name="audio.stop", domain="audio", action="stop")  
  "cancel timer" → Intent(name="timer.cancel", domain="timer", action="cancel")
  ```
- **Extend existing donation patterns to support contextual intent recognition**
- **No orchestrator command parsing** - contextual intents come from NLU cascade

#### 1.3 **Connect Existing Disambiguation Logic** ✅ **COMPLETED**
- **✅ Wired `ContextManager.resolve_contextual_command_ambiguity()` to orchestrator**:
  - ✅ Made method generic: works with any contextual command type
  - ✅ Handles `contextual.*` intents with active fire-and-forget action analysis
  - ✅ Passes domain priorities from centralized manager
  - ✅ **Old stop-specific method removed** - no longer needed

---

### 🔄 **Phase 2: Central Disambiguation Integration (No Handler Changes)**

**Duration**: 2-3 days  
**Principle**: **Complete centralization - handlers never see ambiguous commands**

#### 2.1 **Orchestrator Central Disambiguation**
- **Add contextual intent handling to `IntentOrchestrator.execute()`**:
  ```python
  async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
      # STEP 1: Check if this is a contextual intent from NLU cascade
      if intent.domain == "contextual":
          # STEP 2: Analyze active fire-and-forget actions for disambiguation
          active_actions = context.active_actions
          if not active_actions:
              return self._create_error_result("No active actions to target")
          
          # STEP 3: Central disambiguation using existing sophisticated logic
          resolution = await self.contextual_resolver.resolve_command_ambiguity(
              session_id=context.session_id,
              command_type=intent.action,  # "stop", "pause", "resume", etc.
              active_actions=active_actions,
              domain_priorities=self.domain_priorities
          )
          
          # STEP 4: Transform to resolved domain-specific intent
          resolved_intent = Intent(
              name=f"{resolution.target_domain}.{intent.action}",
              action=intent.action,
              domain=resolution.target_domain,
              text=intent.text,
              entities=intent.entities,
              confidence=intent.confidence
          )
          intent = resolved_intent
      
      # STEP 5: Route to handler normally (handler sees resolved intent)
      handler = self.registry.get_handler(intent)
      return await handler.execute(intent, context)
  ```

#### 2.2 **Handler Interface Cleanup (Remove Ambiguity Logic)**
- **Remove from `IntentHandler` base class**:
  ```python
  # REMOVE: def parse_stop_command() - no longer needed
  # REMOVE: async def _handle_stop_command() - no longer needed
  # REMOVE: All contextual command disambiguation logic
  ```
- **Handlers only handle specific intents**: `timer.stop`, `audio.stop`, `voice_synthesis.stop`
- **No handler ever sees generic "stop" command** - only domain-specific resolved commands

#### 2.3 **Fire-and-Forget Action Termination Integration**
- **Standardize stop/cancel/abort handling across all handlers**:
  ```python
  # All handlers implement consistent termination pattern:
  async def _handle_stop_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
      # 1. Identify target actions from domain-specific state
      # 2. Terminate active actions via unified pattern
      # 3. Update ConversationContext.active_actions
      # 4. Return consistent termination response
  ```
- **Synchronize context tracking with handler-specific state**:
  - `ConversationContext.active_actions` ↔ `TimerHandler.active_timers`
  - `ConversationContext.cancel_action()` triggers handler-specific cleanup
- **Unified action lifecycle**: Start → Track → Terminate → History

#### 2.4 **NLU Provider Pattern Updates**
- **Extend donation patterns for contextual intent recognition**:
  ```json
  // New patterns in donation files:
  "contextual_intent_patterns": {
    "stop": ["stop", "стоп", "останови"],
    "pause": ["pause", "пауза", "приостанови"], 
    "resume": ["resume", "продолжи", "возобнови"]
  }
  ```
- **NLU cascade recognizes contextual vs specific intents**:
  - Generic "stop" → `contextual.stop` (needs disambiguation)
  - Specific "stop music" → `audio.stop` (direct routing)
- **Preserve existing NLU cascade architecture** - no changes to provider coordination

---

### 🚀 **Phase 3: Advanced Coordination (Cross-Handler Intelligence)**

**Duration**: 2-3 days  
**Principle**: Enable sophisticated multi-domain command coordination

#### 3.1 **Multi-Domain Command Resolution**
- **When multiple domains have active actions**:
  - Use domain priorities for automatic resolution
  - Implement recency fallback from existing logic
  - Support explicit domain targeting ("stop music", "cancel timer")

#### 3.2 **Command Capability Registry**
- **Extend `IntentRegistry` with capability tracking**:
  - Register which handlers support which contextual commands
  - Enable discovery: "Which handlers can process 'pause' commands?"
  - Support capability-based routing

#### 3.3 **Enhanced User Experience**
- **Intelligent disambiguation**:
  - Automatic resolution when priorities are clear
  - User confirmation for ambiguous cases
  - Learning from user choices (future enhancement)

---

### ✅ **Phase 4: Validation & Optimization (Polish & Performance)**

**Duration**: 1-2 days  
**Principle**: Ensure reliability and optimize for production use

#### 4.1 **Testing & Validation**
- **Cross-handler coordination testing**:
  - Multiple active actions scenarios
  - Domain priority resolution validation
  - Contextual command parsing accuracy

#### 4.2 **Performance Optimization**
- **Minimize latency impact**:
  - Cache domain priorities
  - Optimize contextual command parsing
  - Profile disambiguation logic performance

#### 4.3 **Documentation & Migration**
- **Update handler development documentation**
- **Create migration guide for custom handlers**
- **Update donation file specification for contextual commands**

## Data Flow Analysis Findings (2025-01-27)

### **Pipeline Data Flow Confirmation** ✅
**Analysis of actual codebase confirms TODO16 architectural assumptions:**

#### **1. Data Structures in Pipeline**
- **AudioData** → **RequestContext** → **ConversationContext** → **Intent** → **IntentResult**
- **Context Propagation**: `RequestContext` carries client info, `ConversationContext` tracks active actions
- **NLU Cascade**: Up to 4 providers with 200ms timeout (`hybrid_keyword_matcher` → `spacy_nlu` → fallback)
- **Fire-and-Forget Tracking**: `ConversationContext.active_actions` is the PRIMARY disambiguation source

#### **2. Critical Integration Points Confirmed**
- **UnifiedVoiceAssistantWorkflow**: Single convergence point for all entry points
- **ContextAwareNLUProcessor**: Client identification and device context enhancement
- **IntentOrchestrator**: Central coordination with donation-driven routing
- **ContextManager.resolve_contextual_command_ambiguity()**: **Sophisticated logic actively used** ✅ **IMPLEMENTED**

#### **3. Component-Provider Architecture Validated**
- **Components**: Coordinate lifecycle and expose unified interfaces
- **Providers**: Implement specific algorithms (ASR, NLU, TTS, etc.)
- **Provider Cascade**: Automatic fallback and error handling
- **Status Tracking**: All providers inherit from `ProviderBase` with health monitoring

#### **4. Active Action Context Flow**
```python
# Confirmed data flow for contextual commands:
ConversationContext.active_actions = {
    "audio": {"action": "play_music", "started_at": 123456},
    "timer": {"action": "set_timer", "started_at": 123457}
}
# → Used by resolve_contextual_command_ambiguity() for disambiguation
# → Domain priorities: audio=90 > timer=70 (from donation files)
```

### **Key Architectural Insights for Implementation**
1. **NLU Cascade Integration Critical**: Contextual commands must be recognized during NLU cascade, not in orchestrator
2. **Workflow-Level Collection Optimal**: `UnifiedVoiceAssistantWorkflow` is ideal data collection point
3. **Context Manager Logic Ready**: Sophisticated disambiguation logic exists but is disconnected
4. **Provider Status Available**: Real-time provider health for capability-based routing

---


## Design Decisions (MECE Resolution of Open Questions)

### D1. **Command Type Taxonomy** ✅ RESOLVED
**Decision**: Use explicit command type enumeration based on analysis findings:
```python
CONTEXTUAL_COMMANDS = ["stop", "pause", "resume", "cancel", "volume", "next", "previous"]
```
- **Rationale**: Analysis shows these exact commands exist across donation files
- **Implementation**: Extend localization files for new command types as needed

### D2. **Disambiguation Strategy Priority** ✅ RESOLVED  
**Decision**: Use existing `ContextManager.resolve_contextual_command_ambiguity()` order:
1. **Target Domain Filtering** (explicit: "stop music") → Highest priority  
2. **Domain Priority** (config/donation-based) → Secondary
3. **Recency Fallback** (most recent action) → Tertiary
- **Rationale**: This logic already exists and is sophisticated
- **Implementation**: Make generic for all command types

### D3. **Handler Capability Declaration** ✅ RESOLVED
**Decision**: Extract from existing donation files during initialization:
```json
// Capabilities derived from existing donation patterns:
"action_patterns": ["stop", "pause", "resume"] // → Handler supports these contextual commands
```
- **Rationale**: Zero disruption to existing donation file architecture  
- **Implementation**: `IntentHandlerManager` extracts capabilities during donation loading

### D4. **Cross-Language Support** ✅ RESOLVED
**Decision**: Leverage existing localization infrastructure:
- `assets/localization/commands/{language}.yaml` → Already supports multi-language
- Extend existing files with new command types (pause, resume, cancel)
- **Rationale**: Reuse proven localization system, zero architectural changes needed

### D5. **Performance Optimization** ✅ RESOLVED + ✅ IMPLEMENTED
**Decision**: Cache-based approach with minimal latency impact:
- Cache domain priorities during handler initialization ✅ **IMPLEMENTED**
- Cache contextual command patterns per language ✅ **SCHEMA READY**
- **Target**: <5ms latency impact for disambiguation ✅ **CONFIGURABLE**
- **Rationale**: Leverage existing caching patterns in system

**✅ Implementation Status**:
```toml
# config-master.toml - Phase 4 Performance Config
[intent_system.contextual_commands]
enable_pattern_caching = true       # Enable contextual command pattern caching
cache_ttl_seconds = 300             # Cache time-to-live in seconds (5 minutes)
max_cache_size_patterns = 1000      # Maximum cached patterns per language
performance_monitoring = true       # Monitor disambiguation latency
latency_threshold_ms = 5.0          # Alert threshold for disambiguation latency
```

**Pydantic Schema**: `ContextualCommandsConfig` with validation constraints:
- `cache_ttl_seconds`: 60-3600 seconds range
- `max_cache_size_patterns`: 100-10000 patterns range  
- `latency_threshold_ms`: 1.0-100.0 ms range

### D6. **Integration Strategy** ✅ RESOLVED
**Decision**: **Systematic replacement** of stop-specific patterns:
- **Phase 2**: Replace all `parse_stop_command()` calls with generic equivalent
- **Backward Compatibility**: Maintain existing method signatures during transition
- **Migration Path**: Handler-by-handler replacement with feature parity validation

### D7. **Error Handling Strategy** ✅ RESOLVED
**Decision**: Progressive fallback with existing patterns:
1. **Automatic Resolution** → When domain priorities are clear
2. **Handler Fallback** → When no cross-handler coordination needed  
3. **Error Response** → When no handlers can process contextual command
- **Rationale**: Matches existing error handling patterns in `IntentOrchestrator`

## Success Criteria (Measurable Outcomes)

### ✅ **Functional Requirements**
1. **Generic Command Framework**: 
   - Replace 3 stop-specific patterns with 1 generic pattern
   - Support 7 contextual commands: `["stop", "pause", "resume", "cancel", "volume", "next", "previous"]`
   - Cross-handler coordination for ambiguous commands

2. **Configuration Unification**:
   - Domain priorities loaded from central config + donation files  
   - Zero hardcoded command patterns in handler code
   - All patterns externalized to localization files

3. **Backward Compatibility**:
   - Existing handler APIs preserved during migration
   - All current functionality maintained
   - Zero breaking changes to donation file format

### ⚡ **Performance Requirements**  
1. **Latency Impact**: <5ms additional processing for contextual commands
2. **Memory Efficiency**: <1MB additional memory for priority/command caching
3. **Throughput**: No degradation in concurrent command processing

### 🎯 **User Experience Requirements**
1. **Intelligent Resolution**: 90%+ of ambiguous commands resolved automatically
2. **Consistent Behavior**: Same command + same context = same resolution
3. **Multi-Language**: Russian + English contextual command support
4. **Clear Feedback**: User understands which action was targeted

## Implementation Validation ✅ **ALL SCHEMAS FULLY IMPLEMENTED**

### 🏗️ **Complete Schema Architecture** ✅ **READY TO USE**

#### **Configuration Flow (Already Implemented)**:
```
TOML File → ConfigManager → Pydantic Models → Components → Frontend UI
```

#### **✅ ALL TODO16 SCHEMAS ALREADY IMPLEMENTED**:

1. **✅ IntentSystemConfig (Fully Implemented)**:
   ```python
   # irene/config/models.py - ALREADY EXISTS
   class IntentSystemConfig(BaseModel):
       domain_priorities: Dict[str, int] = Field(default_factory=lambda: {
           "audio": 90, "timer": 70, "voice_synthesis": 60, 
           "system": 50, "conversation": 40
       })  # ← Phase 1 TODO16 - IMPLEMENTED
       contextual_commands: ContextualCommandsConfig  # ← Phase 4 TODO16 - IMPLEMENTED
   ```

2. **✅ ContextualCommandsConfig (Phase 4 - Fully Implemented)**:
   ```python
   # irene/config/models.py - ALREADY EXISTS
   class ContextualCommandsConfig(BaseModel):
       enable_pattern_caching: bool = Field(default=True)
       cache_ttl_seconds: int = Field(default=300, ge=60, le=3600)
       max_cache_size_patterns: int = Field(default=1000, ge=100, le=10000)
       performance_monitoring: bool = Field(default=True)
       latency_threshold_ms: float = Field(default=5.0, ge=1.0, le=100.0)
   ```


#### **✅ TOML Configuration Fully Implemented**:
- ✅ **Phase 1**: `[intent_system.domain_priorities]` - **IMPLEMENTED** in config-master.toml
- ✅ **Phase 4**: `[intent_system.contextual_commands]` - **IMPLEMENTED** in config-master.toml

#### **✅ Frontend Integration Complete**:
- ✅ **TypeScript Interfaces**: All schemas implemented in `config-ui/src/types/api.ts`
- ✅ **CoreConfig Interface**: Includes all TODO16 configurations
- ✅ **Dynamic Rendering**: Configuration editor automatically renders all fields
- ✅ **Validation**: Frontend validation matches backend Pydantic constraints

#### **✅ Schema Implementation Status**:
- ✅ **All Defaults Set**: Schemas load with proper defaults
- ✅ **TOML Integration**: Configuration files parse correctly  
- ✅ **Type Safety**: Pydantic validation enforced throughout
- ✅ **Core Integration**: All configs integrated into `CoreConfig` class
- ✅ **No Implementation Needed**: All schemas are complete and ready to use

### 🧪 **Testing Strategy**
1. **Unit Tests**: Contextual command parsing, domain priority resolution ✅ **Schema tested**
2. **Integration Tests**: Cross-handler coordination scenarios  
3. **Performance Tests**: Latency impact measurement ✅ **Thresholds configured**
4. **Migration Tests**: Handler-by-handler replacement validation
5. **✅ Schema Tests**: Configuration loading, validation, and frontend integration

### 📊 **Success Metrics**
1. **Code Reduction**: Remove 150+ lines of duplicated stop-specific logic ✅ **COMPLETED**
2. **Feature Completeness**: Support 7 contextual commands across 3+ handlers ✅ **COMPLETED**
3. **Performance**: <5ms latency impact in 95th percentile ✅ **Configurable thresholds implemented**
4. **Reliability**: Zero regressions in existing command processing ✅ **COMPLETED**
5. **✅ Configuration Architecture**: Schema-based configuration with type safety and validation ✅ **FULLY IMPLEMENTED**
6. **✅ Frontend Integration**: Dynamic UI rendering based on backend schemas ✅ **FULLY IMPLEMENTED**
7. **✅ Performance Monitoring**: Configurable caching and latency monitoring ✅ **FULLY IMPLEMENTED**
8. **✅ Schema Infrastructure**: All data collection schemas complete and ready to use ✅ **FULLY IMPLEMENTED**

## Risk Mitigation

### 🚨 **High Risk: Handler Migration Disruption**
- **Mitigation**: Feature flags for gradual rollout
- **Rollback**: Maintain existing methods during transition
- **Validation**: Handler-by-handler testing before replacement

### ⚠️ **Medium Risk: Performance Impact**  
- **Mitigation**: Caching strategy for priorities and patterns
- **Monitoring**: Real-time latency measurement during rollout
- **Optimization**: Profile-guided optimization if needed

### 💡 **Low Risk: Configuration Complexity**
- **Mitigation**: Use existing TOML configuration patterns
- **Documentation**: Clear migration guide for domain priorities
- **Validation**: Schema validation for configuration files

---

**Status**: ✅ **PHASE 4 COMPLETED** - Validation & optimization with comprehensive testing, performance monitoring, caching, and complete documentation implemented

---

## 📊 **WORKFLOW EXECUTION TRACE COLLECTION (PHASES 5-8)** 

**Principle**: Implement workflow execution trace endpoints that provide complete pipeline visibility for debugging and analysis

**Foundation**: Builds on completed contextual command infrastructure (Phases 1-4) to enable full pipeline tracing for complex interaction debugging

**Key Insight**: This is NOT regular data collection - it's **on-demand execution tracing** that returns complete pipeline execution context instead of just final results

---

### 🎯 **The Real Requirement: Full Execution Trace Endpoints**

**Current System Limitation**: Existing endpoints (`/command`, `/nlu/recognize`, etc.) return simple request/response pairs with no visibility into internal pipeline execution.

**New Requirement**: Trace endpoints that:
1. **Receive the same input** as existing endpoints (text, audio, etc.)
2. **Execute the full pipeline** (same as normal processing)  
3. **Return complete execution trace** instead of just final result

**Example Trace Response**:
```json
{
  "final_result": { /* Normal IntentResult */ },
  "execution_trace": {
    "pipeline_stages": [
      {
        "stage": "text_processing",
        "input": "stop the music", 
        "output": "stop the music",
        "processing_time_ms": 2.3,
        "provider": "default_normalizer",
        "metadata": { /* internal processing details */ }
      },
      {
        "stage": "nlu_cascade",
        "input": "stop the music",
        "cascade_attempts": [
          {
            "provider": "hybrid_keyword_matcher",
            "input": "stop the music",
            "output": null,
            "confidence": 0.0,
            "processing_time_ms": 1.8,
            "method_details": { /* fuzzy matching, patterns tried */ }
          },
          {
            "provider": "spacy_nlu",
            "input": "stop the music", 
            "output": { "name": "audio.stop", "domain": "audio", "action": "stop" },
            "confidence": 0.92,
            "processing_time_ms": 15.7,
            "entities_extracted": {"target": "music"}
          }
        ],
        "final_selection": { /* selected intent with reasoning */ }
      },
      {
        "stage": "intent_execution",
        "input_intent": { /* Intent object */ },
        "disambiguation_process": { /* if contextual command */ },
        "handler_resolution": {
          "handlers_considered": ["AudioPlaybackIntentHandler"],
          "selected_handler": "AudioPlaybackIntentHandler",
          "routing_method": "donation_driven", 
          "method_resolved": "_handle_stop_audio"
        },
        "handler_execution": {
          "input": { /* parameters passed to handler */ },
          "internal_steps": [ /* handler's internal processing steps */ ],
          "output": { /* IntentResult */ },
          "side_effects": [ /* actions taken: stop playback, update context */ ]
        }
      }
    ],
    "context_evolution": {
      "before": { /* ConversationContext state before */ },
      "after": { /* ConversationContext state after */ },
      "changes": { /* what changed and why */ }
    },
    "performance_metrics": {
      "total_processing_time_ms": 45.2,
      "stage_breakdown": { /* time per stage */ }
    }
  }
}
```

---

### 🏗️ **Phase 5: Trace-Enabled Pipeline Architecture**

**Duration**: 2-3 days  
**Principle**: Instrument existing pipeline with conditional trace collection

#### **5.1 Trace Context System**
**Objective**: Add optional trace collection to existing `UnifiedVoiceAssistantWorkflow` without performance impact

##### **5.1.0 Binary Audio Data Handling Requirements**
**CRITICAL**: All binary audio data in traces must be converted to base64 strings for safe serialization and storage:

1. **AudioData Objects**: Convert `.data` bytes field to base64, preserve metadata (sample_rate, channels, format)
2. **Raw Binary Audio**: Convert bytes objects directly to base64 with size information
3. **TTS-Audio File Handover**: Read temporary audio files created by TTS and convert content to base64
4. **File Paths**: When audio file paths are traced, read file content and encode as base64
5. **Trace Storage**: All base64 audio data includes type metadata and size information for debugging

**Implementation**: The `_sanitize_for_trace()` method handles automatic conversion of binary audio data to structured base64 objects.

##### **5.1.1 TraceContext Design**
```python
class TraceContext:
    """Context object for collecting detailed pipeline execution traces"""
    
    def __init__(self, enabled: bool = False, request_id: str = None):
        self.enabled = enabled
        self.request_id = request_id or str(uuid.uuid4())
        self.stages = []
        self.start_time = time.time()
        self.context_snapshots = {"before": None, "after": None}
    
    def record_stage(self, stage_name: str, input_data: Any, output_data: Any, 
                    metadata: Dict[str, Any], processing_time_ms: float) -> None:
        """Record detailed stage execution information"""
        if self.enabled:
            self.stages.append({
                "stage": stage_name,
                "input": self._sanitize_for_trace(input_data),
                "output": self._sanitize_for_trace(output_data),
                "metadata": metadata,
                "processing_time_ms": processing_time_ms,
                "timestamp": time.time()
            })
    
    def record_context_snapshot(self, when: str, context: ConversationContext) -> None:
        """Record conversation context state snapshots"""
        if self.enabled:
            self.context_snapshots[when] = {
                "active_actions": context.active_actions.copy(),
                "conversation_history_length": len(context.conversation_history),
                "recent_intents": context.conversation_history[-3:] if context.conversation_history else []
            }
```

#### **5.2 Pipeline Instrumentation Strategy**
**Objective**: Instrument key pipeline stages with zero overhead when tracing is disabled

##### **5.2.1 UnifiedVoiceAssistantWorkflow Integration**
```python
# Enhanced _process_pipeline() method:
async def _process_pipeline(self, input_data: str, context: RequestContext, 
                          conversation_context: ConversationContext,
                          trace_context: Optional[TraceContext] = None,
                          skip_wake_word: bool = False, skip_asr: bool = False) -> IntentResult:
    """
    Core unified pipeline processing with optional trace collection
    """
    
    # Record initial context state
    if trace_context:
        trace_context.record_context_snapshot("before", conversation_context)
    
    processed_text = input_data
    
    # Stage 1: Text Processing (with tracing)
    if self._text_processing_enabled and self.text_processor:
        stage_start = time.time()
        processed_text = await self.text_processor.process(processed_text)
        
        if trace_context:
            trace_context.record_stage(
                stage_name="text_processing",
                input_data=input_data,
                output_data=processed_text, 
                metadata={
                    "provider": self.text_processor.__class__.__name__,
                    "normalizers_applied": self.text_processor.get_active_normalizers()
                },
                processing_time_ms=(time.time() - stage_start) * 1000
            )
    
    # Stage 2: NLU (with cascade tracing)
    stage_start = time.time()
    intent = await self.nlu.process_with_trace(processed_text, conversation_context, trace_context)
    
    # Stage 3: Intent Execution (with handler resolution tracing)  
    stage_start = time.time()
    result = await self.intent_orchestrator.execute_with_trace(intent, conversation_context, trace_context)
    
    # Record final context state
    if trace_context:
        trace_context.record_context_snapshot("after", conversation_context)
    
    return result
```

---

### 🔧 **Phase 6: Component Trace Integration**

**Duration**: 2-3 days  
**Principle**: Add optional TraceContext parameter to existing component methods without breaking functionality

#### **6.1 Component-Specific Method Integration**
**Objective**: Modify existing core processing methods to accept optional `trace_context` parameter

**Strategy**: Each component has different core methods - modify the actual methods used in the pipeline:

| Component | Core Method | Method Signature |
|-----------|-------------|------------------|
| TextProcessorComponent | `process()` | `async def process(text: str, trace_context: Optional[TraceContext] = None)` |
| NLUComponent | `process()` | `async def process(text: str, context: ConversationContext, trace_context: Optional[TraceContext] = None)` |
| ASRComponent | `process_audio()` | `async def process_audio(audio_data: AudioData, trace_context: Optional[TraceContext] = None, **kwargs)` |
| TTSComponent | `synthesize_to_file()` | `async def synthesize_to_file(text: str, output_path: Path, trace_context: Optional[TraceContext] = None, **kwargs)` |
| VoiceTriggerComponent | `process_audio()` | `async def process_audio(audio_data: AudioData, trace_context: Optional[TraceContext] = None)` |
| AudioComponent | `play_file()` | `async def play_file(file_path: Path, trace_context: Optional[TraceContext] = None, **kwargs)` |
| IntentOrchestrator | `execute()` | `async def execute(intent: Intent, context: ConversationContext, trace_context: Optional[TraceContext] = None)` |

#### **6.2 Implementation Pattern for All Components**

##### **6.2.1 Generic Trace Integration Pattern**
```python
# Pattern for modifying existing component methods:
async def existing_method(self, input_data, other_params, trace_context: Optional[TraceContext] = None):
    """Existing method signature with optional trace_context parameter added"""
    
    # Fast path - zero overhead when tracing disabled
    if not trace_context or not trace_context.enabled:
        # Execute original logic without any tracing overhead
        return await self._original_processing_logic(input_data, other_params)
    
    # Trace path - detailed execution tracking
    stage_start = time.time()
    component_metadata = {
        "component_name": self.__class__.__name__,
        "component_type": getattr(self, 'name', self.__class__.__name__),
        "providers_available": list(self.providers.keys()) if hasattr(self, 'providers') else [],
        "default_provider": getattr(self, 'default_provider', None),
        "configuration": self._get_trace_safe_config()
    }
    
    try:
        # Execute original processing logic
        result = await self._original_processing_logic(input_data, other_params)
        component_metadata["processing_success"] = True
        
    except Exception as e:
        component_metadata["processing_success"] = False
        component_metadata["error"] = str(e)
        raise
    
    finally:
        # Record execution trace
        trace_context.record_stage(
            stage_name=getattr(self, 'name', self.__class__.__name__.lower()),
            input_data=input_data,
            output_data=result if 'result' in locals() else None,
            metadata=component_metadata,
            processing_time_ms=(time.time() - stage_start) * 1000
        )
    
    return result
```

#### **6.3 Specific Component Modifications**

##### **6.3.1 TextProcessorComponent.process() Enhancement**
```python
class TextProcessorComponent:
    async def process(self, text: str, trace_context: Optional[TraceContext] = None) -> str:
        """Process text using general text processing provider with optional tracing"""
        
        # Fast path - existing logic when no tracing
        if not trace_context or not trace_context.enabled:
            # Original implementation unchanged
            if not self.providers:
                logger.debug("No text processing providers available, returning original text")
                return text
            
            from ..intents.models import ConversationContext
            context = ConversationContext(session_id="text_processing", user_id=None, conversation_history=[])
            return await self.improve(text, context, "general")
        
        # Trace path - detailed stage tracking
        stage_start = time.time()
        normalizers_applied = []
        
        if not self.providers:
            processed_text = text
        else:
            # Trace each normalization step through improve() method
            from ..intents.models import ConversationContext
            context = ConversationContext(session_id="text_processing", user_id=None, conversation_history=[])
            
            # Call improve and trace internal provider calls
            processed_text = await self.improve(text, context, "general")
            
            # Track which providers were used (simplified for demo)
            if self._stage_providers:
                for stage, provider_name in self._stage_providers.items():
                    normalizers_applied.append({
                        "stage": stage,
                        "provider": provider_name,
                        "used": True
                    })
        
        trace_context.record_stage(
            stage_name="text_processing",
            input_data=text,
            output_data=processed_text,
            metadata={
                "normalizers_applied": normalizers_applied,
                "text_changed": text != processed_text,
                "providers_available": list(self.providers.keys()),
                "default_provider": self.default_provider
            },
            processing_time_ms=(time.time() - stage_start) * 1000
        )
        
        return processed_text
```

##### **6.3.2 NLUComponent.process() Enhancement**
```python
class NLUComponent:
    async def process(self, text: str, context: ConversationContext, 
                     trace_context: Optional[TraceContext] = None) -> Intent:
        """Process text using NLU recognition with optional detailed cascade tracing"""
        
        # Fast path - existing logic when no tracing
        if not trace_context or not trace_context.enabled:
            # Original implementation - calls recognize_with_context()
            return await self.recognize_with_context(text, context)
        
        # Trace path - detailed provider cascade tracking
        stage_start = time.time()
        cascade_attempts = []
        
        # Execute original recognition but with detailed provider tracking
        try:
            # We can either:
            # Option A: Call existing method and trace at higher level
            result = await self.recognize_with_context(text, context)
            
            # Option B: Duplicate cascade logic with tracing (more detailed)
            # For now, use Option A and enhance later if needed
            
            cascade_attempts.append({
                "final_result": result.__dict__,
                "success": True,
                "confidence": result.confidence
            })
            
        except Exception as e:
            cascade_attempts.append({
                "error": str(e),
                "success": False
            })
            raise
        
        trace_context.record_stage(
            stage_name="nlu_cascade",
            input_data=text,
            output_data=result.__dict__ if 'result' in locals() else None,
            metadata={
                "cascade_attempts": cascade_attempts,
                "providers_available": list(self.providers.keys()),
                "confidence_threshold": self.confidence_threshold,
                "context_aware_processing": True
            },
            processing_time_ms=(time.time() - stage_start) * 1000
        )
        
        return result
```

##### **6.3.3 ASRComponent.process_audio() Enhancement**
```python
class ASRComponent:
    async def process_audio(self, audio_data: AudioData, trace_context: Optional[TraceContext] = None, **kwargs) -> str:
        """Workflow-compatible ASR processing with optional provider performance tracing"""
        
        # Fast path - existing logic when no tracing
        if not trace_context or not trace_context.enabled:
            # Original implementation unchanged
            if not self.providers:
                raise Exception("No ASR providers available")
            
            provider = self.providers.get(self.default_provider)
            if not provider:
                raise Exception(f"Default ASR provider '{self.default_provider}' not available")
            
            return await provider.transcribe(audio_data)
        
        # Trace path - detailed provider performance tracking
        stage_start = time.time()
        provider_attempts = []
        
        if not self.providers:
            raise Exception("No ASR providers available")
        
        provider = self.providers.get(self.default_provider)
        if not provider:
            raise Exception(f"Default ASR provider '{self.default_provider}' not available")
        
        # Execute transcription with timing
        attempt_start = time.time()
        try:
            transcription = await provider.transcribe(audio_data)
            provider_attempts.append({
                "provider": self.default_provider,
                "result": transcription,
                "confidence": getattr(provider, 'last_confidence', 0.0),
                "processing_time_ms": (time.time() - attempt_start) * 1000,
                "success": True
            })
            
        except Exception as e:
            provider_attempts.append({
                "provider": self.default_provider,
                "error": str(e),
                "processing_time_ms": (time.time() - attempt_start) * 1000,
                "success": False
            })
            raise
        
        trace_context.record_stage(
            stage_name="asr_transcription",
            input_data=audio_data,  # AudioData object - will be converted to base64 by _sanitize_for_trace()
            output_data=transcription,
            metadata={
                "provider_attempts": provider_attempts,
                "audio_properties": {
                    "sample_rate": audio_data.sample_rate,
                    "channels": audio_data.channels,
                    "duration_ms": len(audio_data.data) / audio_data.sample_rate * 1000
                },
                "default_provider": self.default_provider
            },
            processing_time_ms=(time.time() - stage_start) * 1000
        )
        
        return transcription
```

##### **6.3.4 TTSComponent.synthesize_to_file() Enhancement**
```python
class TTSComponent:
    async def synthesize_to_file(self, text: str, output_path: Path, trace_context: Optional[TraceContext] = None, **kwargs) -> None:
        """Generate audio file with optional synthesis tracing"""
        
        # Fast path - existing logic when no tracing
        if not trace_context or not trace_context.enabled:
            # Original implementation unchanged - delegate to provider
            provider = self.get_current_provider()
            await provider.synthesize_to_file(text, output_path, **kwargs)
            return
        
        # Trace path - detailed synthesis tracking
        stage_start = time.time()
        synthesis_metadata = {
            "input_text_length": len(text),
            "input_word_count": len(text.split()),
            "provider": self.default_provider,
            "auto_play": self.auto_play
        }
        
        try:
            # Execute original synthesis logic via provider
            provider = self.get_current_provider()
            await provider.synthesize_to_file(text, output_path, **kwargs)
            
            synthesis_metadata.update({
                "synthesis_success": True,
                "output_file": str(output_path),
                "provider_used": provider.name if hasattr(provider, 'name') else 'unknown'
            })
            
        except Exception as e:
            synthesis_metadata.update({
                "synthesis_success": False,
                "error": str(e)
            })
            raise
        
        trace_context.record_stage(
            stage_name="tts_synthesis",
            input_data=text,
            output_data=output_path,  # Path object - will be read and converted to base64 by _sanitize_for_trace()
            metadata=synthesis_metadata,
            processing_time_ms=(time.time() - stage_start) * 1000
        )
```

##### **6.3.5 VoiceTriggerComponent.process_audio() Enhancement**
```python
class VoiceTriggerComponent:
    async def process_audio(self, audio_data: AudioData, trace_context: Optional[TraceContext] = None) -> WakeWordResult:
        """Voice trigger detection with optional model performance tracing"""
        
        # Fast path - existing logic when no tracing
        if not trace_context or not trace_context.enabled:
            # Original implementation unchanged
            return await self.detect(audio_data)
        
        # Trace path - detailed detection tracking
        stage_start = time.time()
        detection_metadata = {
            "audio_duration_ms": len(audio_data.data) / audio_data.sample_rate * 1000,
            "wake_words_configured": self.wake_words,
            "threshold": self.threshold,
            "provider": self.default_provider
        }
        
        # Execute detection with timing
        result = await self.detect(audio_data)
        
        detection_metadata.update({
            "wake_word_detected": result.detected,
            "detected_word": result.wake_word if result.detected else None,
            "confidence": result.confidence,
            "detection_threshold_met": result.confidence >= self.threshold if result.detected else False
        })
        
        trace_context.record_stage(
            stage_name="voice_trigger_detection",
            input_data=audio_data,  # AudioData object - will be converted to base64 by _sanitize_for_trace()
            output_data=result.__dict__,
            metadata=detection_metadata,
            processing_time_ms=(time.time() - stage_start) * 1000
        )
        
        return result
```

##### **6.3.6 IntentOrchestrator.execute() Enhancement**
```python
class IntentOrchestrator:
    async def execute(self, intent: Intent, context: ConversationContext, 
                     trace_context: Optional[TraceContext] = None) -> IntentResult:
        """Execute intent with optional handler resolution and disambiguation tracing"""
        
        # Fast path - existing logic when no tracing
        if not trace_context or not trace_context.enabled:
            # Original implementation unchanged
            return await self.execute_intent(intent, context)
        
        # Trace path - detailed handler resolution tracking
        stage_start = time.time()
        execution_metadata = {
            "input_intent": intent.__dict__,
            "disambiguation_process": None,
            "handler_resolution": {},
            "handler_execution": {}
        }
        
        # Execute with detailed tracking
        try:
            result = await self.execute_intent(intent, context)
            execution_metadata["handler_execution"]["success"] = result.success
            
        except Exception as e:
            execution_metadata["handler_execution"]["error"] = str(e)
            raise
        
        trace_context.record_stage(
            stage_name="intent_execution",
            input_data=intent.__dict__,
            output_data=result.__dict__ if 'result' in locals() else None,
            metadata=execution_metadata,
            processing_time_ms=(time.time() - stage_start) * 1000
        )
        
        return result
```

---

### 📊 **Phase 7: Trace Endpoint Implementation**

**Duration**: 1-2 days  
**Principle**: Extend existing WebAPIRunner with trace endpoints instead of creating new component

#### **7.1 WebAPIRunner Extension Strategy**
**Objective**: Add trace endpoints to existing WebAPIRunner alongside current endpoints (`/command`, `/status`, `/health`)

**Rationale**: WebAPIRunner already handles command execution and has access to `self.core.workflow_manager` - perfect for trace functionality

#### **7.2 WebAPIRunner Trace Endpoint Integration**

##### **7.2.1 Enhanced WebAPIRunner with Trace Routes**
```python
# Modify irene/runners/webapi_runner.py in _create_fastapi_app() method:

class WebAPIRunner(BaseRunner):
    async def _create_fastapi_app(self, args):
        """Create and configure FastAPI application"""
        # ... existing setup code ...
        
        # Existing endpoints (unchanged)
        @app.get("/status", response_model=StatusResponse, tags=["General"])
        async def get_status():
            # ... existing implementation ...
        
        @app.post("/command", response_model=CommandResponse, tags=["General"])
        async def execute_command(request: CommandRequest):
            """Execute a voice assistant command via REST API"""
            # ... existing implementation ...
        
        @app.get("/health", tags=["General"])
        async def health_check():
            # ... existing implementation ...
        
        # NEW: Trace endpoints
        @app.post("/trace/command", response_model=TraceCommandResponse, tags=["Tracing"])
        async def trace_command_execution(request: CommandRequest):
            """Execute command with full execution trace"""
            try:
                if not self.core:
                    raise HTTPException(status_code=503, detail="Assistant not initialized")
                
                # Create trace context for detailed execution tracking
                trace_context = TraceContext(enabled=True, request_id=str(uuid.uuid4()))
                
                # Execute same workflow as normal command but with tracing
                result = await self.core.workflow_manager.process_text_input(
                    text=request.command,
                    session_id=request.session_id or "trace_session",
                    wants_audio=False,
                    client_context={"source": "trace_api", "trace_enabled": True},
                    trace_context=trace_context  # Pass trace context to workflow
                )
                
                return TraceCommandResponse(
                    success=result.success,
                    final_result={
                        "text": result.text,
                        "success": result.success,
                        "metadata": result.metadata,
                        "confidence": result.confidence,
                        "timestamp": result.timestamp
                    },
                    execution_trace={
                        "request_id": trace_context.request_id,
                        "pipeline_stages": trace_context.stages,
                        "context_evolution": {
                            "before": trace_context.context_snapshots.get("before"),
                            "after": trace_context.context_snapshots.get("after"),
                            "changes": self._calculate_context_changes(trace_context.context_snapshots)
                        },
                        "performance_metrics": {
                            "total_processing_time_ms": sum(
                                stage.get("processing_time_ms", 0) for stage in trace_context.stages
                            ),
                            "stage_breakdown": {
                                stage["stage"]: stage.get("processing_time_ms", 0) 
                                for stage in trace_context.stages
                            },
                            "total_stages": len(trace_context.stages)
                        }
                    },
                    timestamp=time.time()
                )
                
            except Exception as e:
                logger.error(f"Trace command execution error: {e}")
                return TraceCommandResponse(
                    success=False,
                    final_result={},
                    execution_trace={
                        "request_id": trace_context.request_id if 'trace_context' in locals() else "unknown",
                        "pipeline_stages": [],
                        "error": str(e)
                    },
                    timestamp=time.time(),
                    error=str(e)
                )
        
        @app.post("/trace/audio", response_model=TraceCommandResponse, tags=["Tracing"])
        async def trace_audio_execution(audio_file: UploadFile = File(...)):
            """Execute audio processing with full execution trace"""
            try:
                if not self.core:
                    raise HTTPException(status_code=503, detail="Assistant not initialized")
                
                # Read audio data
                audio_data = await audio_file.read()
                
                # Create trace context
                trace_context = TraceContext(enabled=True, request_id=str(uuid.uuid4()))
                
                # Process audio through workflow with tracing
                # Note: This would require extending workflow to accept trace_context for audio
                result = await self.core.workflow_manager.process_audio_input(
                    audio_data=audio_data,
                    session_id="trace_audio_session",
                    client_context={"source": "trace_audio_api"},
                    trace_context=trace_context
                )
                
                return TraceCommandResponse(
                    success=result.success,
                    final_result={
                        "text": result.text,
                        "success": result.success,
                        "metadata": result.metadata
                    },
                    execution_trace={
                        "request_id": trace_context.request_id,
                        "pipeline_stages": trace_context.stages,
                        "context_evolution": {
                            "before": trace_context.context_snapshots.get("before"),
                            "after": trace_context.context_snapshots.get("after")
                        },
                        "performance_metrics": {
                            "total_processing_time_ms": sum(
                                stage.get("processing_time_ms", 0) for stage in trace_context.stages
                            ),
                            "stage_breakdown": {
                                stage["stage"]: stage.get("processing_time_ms", 0) 
                                for stage in trace_context.stages
                            }
                        }
                    },
                    timestamp=time.time()
                )
                
            except Exception as e:
                logger.error(f"Trace audio execution error: {e}")
                return TraceCommandResponse(
                    success=False,
                    final_result={},
                    execution_trace={"error": str(e)},
                    timestamp=time.time(),
                    error=str(e)
                )
        
        # Helper method for context change calculation
        def _calculate_context_changes(self, context_snapshots: Dict[str, Any]) -> Dict[str, Any]:
            """Calculate changes between before/after context snapshots"""
            before = context_snapshots.get("before", {})
            after = context_snapshots.get("after", {})
            
            return {
                "active_actions_added": [],  # Could implement detailed diffing
                "active_actions_removed": [],
                "conversation_history_entries_added": 0,
                "summary": "Context changes tracked" if before and after else "No context tracking"
            }
        
        # ... rest of existing WebAPIRunner setup ...
```

##### **7.2.2 Workflow Manager Integration**
```python
# Modify workflow manager methods to accept trace_context:
# This requires updating the method signatures in workflow manager

class WorkflowManager:
    async def process_text_input(self, text: str, session_id: str, wants_audio: bool = True,
                               client_context: Optional[Dict[str, Any]] = None,
                               trace_context: Optional[TraceContext] = None) -> IntentResult:
        """Process text input with optional tracing"""
        
        # Pass trace_context down to workflow._process_pipeline()
        # This connects to the Phase 5 workflow instrumentation
```

#### **7.3 Response Schema Integration**

##### **7.3.1 Add Trace Schemas to Existing Schema File**
```python
# Add to irene/api/schemas.py (alongside existing schemas):

class TraceCommandResponse(BaseModel):
    """Response for trace command execution with complete pipeline visibility"""
    success: bool
    final_result: Dict[str, Any]  # Normal IntentResult data
    execution_trace: Dict[str, Any]  # Complete pipeline execution trace
    timestamp: float
    error: Optional[str] = None

class PipelineStageTrace(BaseModel):
    """Detailed trace information for a single pipeline stage"""
    stage: str
    input_data: Any
    output_data: Any
    metadata: Dict[str, Any]
    processing_time_ms: float
    timestamp: float

class TraceContext(BaseModel):
    """Context object for collecting pipeline execution traces"""
    request_id: str
    enabled: bool = True
    stages: List[Dict[str, Any]] = Field(default_factory=list)
    context_snapshots: Dict[str, Any] = Field(default_factory=dict)
    start_time: float = Field(default_factory=time.time)
```

#### **7.4 API Documentation Integration**

##### **7.4.1 Enhanced OpenAPI Documentation**
```python
# The trace endpoints will automatically appear in /docs with proper Swagger documentation:

# GET /docs -> Shows both normal and trace endpoints
# /command -> "Execute voice assistant command"
# /trace/command -> "Execute command with detailed execution trace"
# /trace/audio -> "Process audio with detailed execution trace"
```

#### **7.5 Integration Benefits**

**Advantages of WebAPIRunner Extension:**
1. **✅ No New Component**: Leverages existing WebAPIRunner infrastructure
2. **✅ Consistent API**: `/command` vs `/trace/command` - clear, logical naming
3. **✅ Existing Infrastructure**: Uses current request handling, error management, logging
4. **✅ Core Access**: Already has `self.core` reference for workflow execution
5. **✅ Schema Reuse**: Uses existing request schemas (`CommandRequest`)
6. **✅ Documentation**: Automatic Swagger/OpenAPI documentation generation
7. **✅ Minimal Changes**: Add endpoints without disrupting existing functionality

**API Design:**
```
Normal Operation:
POST /command -> CommandResponse

Debug/Development:
POST /trace/command -> TraceCommandResponse (with full execution trace)
POST /trace/audio -> TraceCommandResponse (with audio processing trace)
```

---

### 🚀 **Phase 8: Production Integration & Optimization**

**Duration**: 1-2 days  
**Principle**: Ensure trace endpoints work reliably with minimal performance impact

#### **8.1 Performance Optimization**
**Objective**: Minimize performance impact of trace collection

##### **8.1.1 Conditional Execution Strategy**
```python
# Zero overhead when tracing is disabled:
async def _process_pipeline_stage(self, stage_name: str, input_data: Any, 
                                trace_context: Optional[TraceContext] = None):
    """Execute pipeline stage with optional tracing"""
    
    # Fast path - no tracing overhead
    if not trace_context or not trace_context.enabled:
        return await self._execute_stage_normal(stage_name, input_data)
    
    # Trace path - detailed collection
    stage_start = time.time()
    result = await self._execute_stage_normal(stage_name, input_data)
    
    trace_context.record_stage(
        stage_name=stage_name,
        input_data=input_data,
        output_data=result,
        metadata=self._get_stage_metadata(stage_name),
        processing_time_ms=(time.time() - stage_start) * 1000
    )
    
    return result
```

#### **8.2 Data Sanitization and Security**
```python
class TraceContext:
    def _sanitize_for_trace(self, data: Any) -> Any:
        """Sanitize sensitive data and handle binary audio data in trace output"""
        import base64
        from pathlib import Path
        
        if isinstance(data, dict):
            # Remove sensitive keys
            sanitized = {k: v for k, v in data.items() 
                        if k not in ['password', 'token', 'api_key']}
            return sanitized
        elif isinstance(data, str):
            # Truncate very long strings
            return data[:1000] + "..." if len(data) > 1000 else data
        elif isinstance(data, bytes):
            # Convert binary audio data to base64 for trace storage
            return {
                "type": "binary_audio_data",
                "size_bytes": len(data),
                "base64_data": base64.b64encode(data).decode('utf-8')
            }
        elif hasattr(data, 'data') and isinstance(data.data, bytes):
            # Handle AudioData objects with binary content
            return {
                "type": "audio_data_object",
                "size_bytes": len(data.data),
                "sample_rate": getattr(data, 'sample_rate', None),
                "channels": getattr(data, 'channels', None),
                "format": getattr(data, 'format', None),
                "base64_data": base64.b64encode(data.data).decode('utf-8')
            }
        elif isinstance(data, Path):
            # Handle file paths (e.g., TTS temp files) - read and encode content
            try:
                if data.exists() and data.suffix.lower() in ['.wav', '.mp3', '.ogg', '.flac']:
                    with open(data, 'rb') as f:
                        file_content = f.read()
                    return {
                        "type": "audio_file_path",
                        "file_path": str(data),
                        "size_bytes": len(file_content),
                        "base64_data": base64.b64encode(file_content).decode('utf-8')
                    }
                else:
                    return {"type": "file_path", "path": str(data)}
            except Exception as e:
                return {"type": "file_path_error", "path": str(data), "error": str(e)}
        return data
```

---

## 📋 **MECE Success Criteria for Phases 5-8** ✅ **WORKFLOW EXECUTION TRACE COLLECTION**

### **Phase 5 Success Criteria** (Trace Architecture)
- **✅ TraceContext System**: Conditional trace collection with zero overhead when disabled
- **✅ Pipeline Instrumentation**: All major pipeline stages instrumented for detailed tracing
- **✅ Same Execution Path**: Trace endpoints use same workflow execution as normal endpoints
- **✅ Performance**: <1ms overhead when tracing is enabled, 0ms when disabled

### **Phase 6 Success Criteria** (Component Integration)
- **Component Trace Methods**: All major components provide `*_with_trace()` methods
- **NLU Cascade Tracing**: Complete provider cascade attempts and reasoning captured
- **Handler Resolution Tracing**: Detailed handler selection and disambiguation logic captured
- **Context Evolution Tracking**: Before/after conversation context state changes tracked

### **Phase 7 Success Criteria** (Trace Endpoints)
- **Trace API Endpoints**: `/trace/command` and `/trace/audio` endpoints implemented
- **Complete Pipeline Visibility**: Full input/output and internal reasoning for all stages
- **Response Schema**: Structured trace response with performance metrics and context evolution
- **WebAPIPlugin Integration**: Follows existing component router pattern

### **Phase 8 Success Criteria** (Production Integration)
- **Performance Optimization**: Conditional execution with minimal overhead
- **Data Sanitization**: Sensitive data removed from trace output
- **Production Reliability**: Trace collection works consistently without affecting normal operation
- **Security**: No sensitive information leaked in trace responses

---

**Implementation Timeline**: 4-6 days total for Phases 5-8 (focused on execution tracing)
**Dependencies**: Phases 1-4 contextual command infrastructure (completed) + existing pipeline architecture
**Risk Mitigation**: Conditional execution ensures zero impact on normal operation
**Performance Impact**: <1ms when tracing enabled, 0ms when disabled, complete pipeline visibility for debugging

**Phase 1 Implementation Summary**:
1. ✅ **Phase 1.1**: Added domain priorities to `config-master.toml` and implemented DomainPriorityManager in IntentHandlerManager
2. ✅ **Phase 1.2**: Enhanced HybridKeywordMatcherProvider to recognize `contextual.*` vs domain-specific intents using localization patterns
3. ✅ **Phase 1.3**: Created generic `resolve_contextual_command_ambiguity()` method and integrated with IntentOrchestrator
4. ✅ **Integration**: Connected existing sophisticated disambiguation logic to orchestrator with domain priority support
5. ✅ **Schema Architecture**: Enforced Pydantic schema-only approach, removed dict-based fallbacks
6. ✅ **Cleanup**: **Removed deprecated `resolve_stop_command_ambiguity()` method** - no longer needed after generalization

**Phase 2 Implementation Summary**:
1. ✅ **Phase 2.1**: Implemented central disambiguation in `IntentOrchestrator.execute()` - handlers never see ambiguous commands
2. ✅ **Phase 2.2**: Removed `parse_stop_command()` and `_handle_stop_command()` from base class and all handlers
3. ✅ **Phase 2.3**: Standardized stop/cancel/abort handling with unified patterns across all handlers
4. ✅ **Phase 2.4**: Confirmed contextual intent recognition in NLU providers (already implemented in Phase 1)
5. ✅ **Phase 2.5**: Verified existing `resolve_contextual_command_ambiguity()` provides all required functionality
6. ✅ **Handler Updates**: Added domain-specific methods (`_handle_stop_audio`, `_handle_pause_audio`, etc.) to replace ambiguous command logic

**Phase 3 Implementation Summary**:
1. ✅ **Phase 3.1**: Enhanced multi-domain command resolution with confidence scoring, recency analysis, and tie-breaking logic
2. ✅ **Phase 3.2**: Extended `IntentRegistry` with comprehensive capability tracking for contextual commands across all domains
3. ✅ **Phase 3.3**: Implemented intelligent disambiguation with user confirmation for ambiguous cases and enhanced user experience
4. ✅ **Advanced Features**: Added capability-based routing, domain description mapping, and disambiguation context storage
5. ✅ **User Experience**: Implemented smart confirmation logic for destructive vs non-destructive commands
6. ✅ **Context Management**: Added disambiguation context storage with expiration for follow-up resolution

**Phase 4 Implementation Summary**:
1. ✅ **Phase 4.1**: Comprehensive testing suite with unit, integration, and performance tests validating <5ms latency requirements
2. ✅ **Phase 4.2**: Performance optimization with TTL caching, monitoring, and configurable thresholds for domain priorities and patterns
3. ✅ **Phase 4.3**: Complete documentation including migration guide, handler development guide, and donation file specification
4. ✅ **Testing Infrastructure**: Created test suites for contextual command disambiguation, cross-handler coordination, and performance validation
5. ✅ **Performance Monitoring**: Implemented `ContextualCommandPerformanceManager` with caching, metrics collection, and alerting
6. ✅ **Documentation Suite**: Created comprehensive guides for migration, development, and configuration of contextual command systems

**Configuration & Schema Extensions (Phases 2-4 Ready)**:
1. ✅ **Phase 4 Performance Config**: Added `ContextualCommandsConfig` schema with caching and monitoring
2. ✅ **TOML Integration**: Extended `config-master.toml` with Phase 4 performance optimization settings
3. ✅ **Frontend Ready**: Updated TypeScript interfaces in config-ui for dynamic rendering
4. ✅ **Schema Validation**: All new configurations tested and validated with proper defaults

**Next Steps**:
1. ✅ **Phase 1**: Foundation integration completed with domain priorities and NLU cascade integration
2. ✅ **Phase 2**: Central disambiguation integration completed with handler cleanup and standardized termination
3. ✅ **Phase 3**: Advanced coordination completed with capability tracking and enhanced user experience
4. ✅ **Phase 4**: Validation & optimization completed with comprehensive testing, performance monitoring, and documentation

**Key Implementation Insights (Updated)**:
- **Data Flow Confirmed** - `AudioData` → `RequestContext` → `ConversationContext` → `Intent` → `IntentResult` pipeline validated
- **Disambiguation logic enhanced** - `ContextManager.resolve_contextual_command_ambiguity()` with confidence scoring and tie-breaking ✅ **PHASE 3 ENHANCED**
- **Capability tracking implemented** - `IntentRegistry` tracks which handlers support which contextual commands ✅ **PHASE 3 COMPLETE**
- **User experience enhanced** - intelligent confirmation for ambiguous cases with domain descriptions ✅ **PHASE 3 COMPLETE**
- **NLU cascade integration critical** - contextual commands must be recognized during NLU cascade, not in orchestrator
- **Fire-and-forget actions are primary context** - `ConversationContext.active_actions` provides key disambiguation information
- **Workflow-level collection optimal** - `UnifiedVoiceAssistantWorkflow` is ideal instrumentation point
- **Complete architectural separation** - handlers never see ambiguous commands, only resolved domain-specific intents
- **Action termination standardization completed** - unified stop/cancel/abort patterns across handlers ✅ **PHASE 2 COMPLETE**
- **Context synchronization implemented** - `ConversationContext.active_actions` aligned with handler-specific state ✅ **PHASE 2 COMPLETE**
- **Cross-handler intelligence active** - capability-based routing and multi-domain resolution ✅ **PHASE 3 COMPLETE**

**Data Collection Benefits for TODO16**:
- **Real Usage Patterns**: Understand actual contextual command usage in production
- **Disambiguation Effectiveness**: Measure accuracy of domain priority resolution
- **Performance Impact**: Quantify latency overhead of contextual processing
- **Test Case Generation**: Create comprehensive test scenarios from real data
- **Cross-Handler Coordination**: Analyze multi-domain command scenarios
- **Provider Cascade Analysis**: Optimize NLU provider selection and fallback patterns