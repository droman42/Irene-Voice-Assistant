# TODO16: General Command Disambiguation & Context-Aware Action Resolution

## Overview

The current implementation has fragmented and hardcoded approaches to command disambiguation. The "stop" command handling is just one example of a broader need for **context-aware command resolution** that can handle ambiguous commands across multiple active actions and domains.

## Current State Analysis

### What We Have

#### 1. **Fragmented Stop Command Handling**
- `irene/intents/context.py`: `resolve_stop_command_ambiguity()` - Centralized but **unused**
- `irene/intents/handlers/base.py`: `parse_stop_command()` - Handler-level parsing
- Each handler implements its own `_handle_stop_command()` logic
- **Result**: No cross-handler disambiguation capability

#### 2. **Configuration Infrastructure (Exists but Disconnected)**
```toml
# configs/full.toml & configs/development.toml
[actions.domain_priorities]
music = 100
smart_home = 80
timers = 70
media = 60
system = 50
```

#### 3. **Action Context Tracking (Working)**
- `ConversationContext.active_actions` - Tracks running actions
- `ConversationContext.recent_actions` - Tracks completed/failed actions
- `IntentResult.action_metadata` - Propagates action state changes

#### 4. **Handler-Level Domain Priorities (Inconsistent)**
- Defined in JSON donation files: `"action_domain_priority": N`
- Not integrated with centralized configuration
- No runtime resolution mechanism

### What's Broken

#### 1. **Hardcoded Command Patterns**
```python
# This is wrong - stop is just ONE example of contextual commands
def parse_stop_command(self, intent: Intent) -> Optional[Dict[str, Any]]:
    stop_patterns = ["стоп", "останови", "прекрати", ...]
```

#### 2. **No Cross-Handler Coordination**
- User says "стоп" with timer, music, and lights running
- No system decides which action to stop based on domain priorities
- Each handler processes independently

#### 3. **Unused Centralized Logic**
- `resolve_stop_command_ambiguity()` method exists but is never called
- Sophisticated disambiguation logic is completely bypassed

#### 4. **Configuration Disconnect**
- Domain priorities in config files are not loaded or used by handlers
- No mechanism to apply global priorities to local handler decisions

## The Real Problem: General Contextual Commands

"Stop" is just **one example** of commands that require context awareness:

### Examples of Contextual Commands
1. **"стоп/stop"** - Which active action to stop?
2. **"пауза/pause"** - Which media/process to pause?
3. **"продолжи/resume"** - Which paused action to resume?
4. **"громче/louder"** - Which audio source to adjust?
5. **"покажи статус/show status"** - Status of which active processes?
6. **"отмени/cancel"** - Which pending operation to cancel?
7. **"перезапуски/restart"** - Which service/action to restart?

### Disambiguation Factors
1. **Domain Priority** - Music > Smart Home > Timers > System
2. **Recency** - Most recently started/interacted with
3. **Context Hints** - "stop music", "cancel timer", "pause video"
4. **User Preference** - Learned from past disambiguation choices
5. **Action State** - Running vs paused vs pending

## Proposed Architecture

### 1. **Generic Command Disambiguation Framework**

```python
class ContextualCommandResolver:
    """
    Resolves ambiguous commands across multiple active actions and domains.
    Replaces hardcoded stop-specific logic with generic resolution.
    """
    
    def resolve_contextual_command(
        self,
        intent: Intent,
        session_id: str,
        command_type: str,  # "stop", "pause", "resume", "status", etc.
        context_hints: List[str] = None
    ) -> ContextualCommandResolution:
        """
        Generic resolution for any contextual command that could apply
        to multiple active actions.
        """
        pass
```

### 2. **Unified Action Registry**

```python
class ActionRegistry:
    """
    Central registry of all active, paused, and recent actions across handlers.
    Enables cross-handler command resolution.
    """
    
    def register_action_capabilities(
        self,
        handler_class: str,
        supported_commands: Dict[str, ActionCommandCapability]
    ):
        """Register what contextual commands each handler can process."""
        pass
        
    def find_candidate_actions(
        self,
        command_type: str,
        target_domains: List[str] = None,
        action_states: List[str] = None
    ) -> List[ActionCandidate]:
        """Find all actions that could handle this contextual command."""
        pass
```

### 3. **Configuration-Driven Priorities**

```python
class DisambiguationConfig:
    """
    Loads and manages disambiguation rules from configuration files.
    """
    
    def load_domain_priorities(self) -> Dict[str, int]:
        """Load from configs/*/actions.domain_priorities"""
        pass
        
    def load_command_preferences(self) -> Dict[str, DisambiguationRule]:
        """Load user-specific disambiguation preferences"""
        pass
```

## Implementation Plan

### Phase 1: Framework Foundation
1. **Create `ContextualCommandResolver` class**
   - Generic command resolution logic
   - Support for multiple disambiguation factors
   - Extensible command type system

2. **Create `ActionRegistry` class**
   - Central action tracking across handlers
   - Command capability registration
   - Candidate action discovery

3. **Create `DisambiguationConfig` class**
   - Configuration loading from TOML files
   - User preference management
   - Rule-based resolution policies

### Phase 2: Handler Integration
1. **Modify base handler class**
   - Remove hardcoded `parse_stop_command()`
   - Add generic `handle_contextual_command()` method
   - Integrate with `ContextualCommandResolver`

2. **Update existing handlers**
   - Register action capabilities with `ActionRegistry`
   - Replace stop-specific logic with generic contextual handling
   - Update donation files with contextual command patterns

3. **Configuration migration**
   - Move domain priorities from donation files to central config
   - Add contextual command configuration section
   - Create disambiguation rule definitions

### Phase 3: Advanced Features
1. **Learning and adaptation**
   - Track user disambiguation choices
   - Adapt priorities based on usage patterns
   - Suggest clarifications for highly ambiguous commands

2. **Multi-modal disambiguation**
   - Visual clarification prompts for GUI clients
   - Voice confirmation for audio-only interactions
   - Context-aware response generation

## Open Questions

### 1. **Command Type Taxonomy**
- How do we categorize contextual commands?
- Should we use semantic groupings (control, query, modify) or domain-specific?
- How do we handle command aliases and variations?

### 2. **Disambiguation Strategy Priority**
- What's the precedence order: Domain Priority > Recency > Context Hints > User Preference?
- Should this be configurable per command type?
- How do we handle ties in priority scoring?

### 3. **Handler Capability Declaration**
- Should handlers declare capabilities in code, donation files, or separate config?
- How granular should capability declarations be?
- How do we handle dynamic capabilities (context-dependent)?

### 4. **Cross-Language Support**
- How do we handle contextual commands in multiple languages?
- Should disambiguation logic be language-agnostic?
- How do we deal with language-specific context patterns?

### 5. **Performance Considerations**
- How do we optimize resolution for high-frequency contextual commands?
- Should we cache resolution results?
- What's the impact on response time for ambiguous commands?

### 6. **Error Handling and Fallbacks**
- What happens when no actions can handle the contextual command?
- How do we handle partial matches or uncertain resolutions?
- Should we always ask for clarification or make best-guess decisions?

### 7. **Integration with Existing Systems**
- How does this integrate with the current fire-and-forget action framework?
- Should this replace or augment the current `parse_stop_command` approach?
- How do we maintain backward compatibility during migration?

## Success Criteria

### Functional Requirements
1. **Generic Resolution**: Single framework handles all contextual commands (stop, pause, resume, etc.)
2. **Cross-Handler Coordination**: Commands can target actions across different handlers
3. **Configuration-Driven**: Disambiguation rules and priorities loaded from config files
4. **User Adaptation**: System learns from user disambiguation choices
5. **Multilingual Support**: Works with Russian and English contextual commands

### Technical Requirements
1. **Minimal Response Latency**: Disambiguation adds <50ms to response time
2. **Extensible Architecture**: New command types can be added without core changes
3. **Handler Decoupling**: Handlers don't need to know about other handlers' actions
4. **Configuration Hot-Reload**: Disambiguation rules can be updated without restart
5. **Comprehensive Logging**: All disambiguation decisions are logged for analysis

### User Experience Requirements
1. **Intelligent Defaults**: System makes reasonable choices without constant clarification
2. **Clear Feedback**: User understands what action was taken and why
3. **Easy Override**: User can easily correct wrong disambiguation choices
4. **Consistent Behavior**: Similar commands resolve similarly across sessions
5. **Graceful Degradation**: Works even when disambiguation confidence is low

## Migration Strategy

### Phase 1: Parallel Implementation
- Implement new framework alongside existing hardcoded logic
- Add feature flags to switch between old and new systems
- Ensure 100% backward compatibility

### Phase 2: Gradual Migration
- Migrate one command type at a time (start with "stop")
- Update handlers incrementally
- Validate behavior against existing test cases

### Phase 3: Cleanup and Optimization
- Remove deprecated hardcoded logic
- Optimize performance based on real usage data
- Add advanced features (learning, multi-modal disambiguation)

## Dependencies

### Configuration System
- Requires robust TOML configuration loading
- Need environment-specific override capabilities
- Must support hot-reload for development

### Logging and Analytics
- Detailed disambiguation decision logging
- User interaction tracking for learning
- Performance metrics collection

### Testing Framework
- Unit tests for disambiguation logic
- Integration tests for cross-handler scenarios
- User acceptance testing for UX validation

---

**Status**: 📋 **DRAFT** - Awaiting review and refinement

**Next Steps**: 
1. Review and refine open questions
2. Create detailed technical specifications
3. Design API interfaces for core classes
4. Plan implementation timeline and milestones
