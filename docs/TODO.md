# TODO - Irene Voice Assistant

This document tracks architectural improvements and refactoring tasks for the Irene Voice Assistant project.

## 1. AudioComponent Command Handling Architecture Issue

**Status:** Open  
**Priority:** Medium  
**Component:** `irene/components/audio_component.py`  

### Problem

`AudioComponent` implements voice command handling directly via the `CommandPlugin` interface, creating architectural inconsistency:

1. **Mixed Responsibilities**: The component handles both:
   - Core audio functionality (AudioPlugin interface)
   - Voice command interpretation (CommandPlugin interface)
   - Web API endpoints (WebAPIPlugin interface)

2. **Intent System Bypass**: Audio commands are processed through `handle_command()` method instead of the dedicated intent system in `irene/intents/`

3. **Missing Integration**: No clear integration path between:
   - ComponentManager's component discovery
   - CommandProcessor registration for voice commands
   - WebAPI registration for REST endpoints

### Current Implementation Issues

```python
# In AudioComponent.handle_command()
if "играй" in command_lower or "воспроизведи" in command_lower:
    return CommandResult(success=True, response="Команды воспроизведения аудио доступны через веб-API")
```

This is essentially intent recognition logic that should be in the intent system.

### Proposed Solutions

**Option A: Move to Intent System**
- Create `AudioIntentHandler` in `irene/intents/handlers/`
- Remove `CommandPlugin` from `AudioComponent`
- Keep `AudioComponent` focused on pure audio functionality
- Audio intents delegate to AudioComponent for actual audio operations

**Option B: Fix Integration**
- Ensure ComponentManager properly registers components with CommandProcessor
- Create unified component lifecycle that handles all interface implementations
- Maintain current structure but fix the integration gaps

### Impact
- Architectural consistency with existing intent system
- Clearer separation of concerns
- Better testability and maintainability
- Proper component lifecycle management

### Related Files
- `irene/components/audio_component.py` (lines 273-301)
- `irene/core/commands.py` (CommandProcessor registration)
- `irene/core/components.py` (ComponentManager integration)
- `irene/intents/handlers/` (intent system)

## 2. Hardcoded Provider Loading Pattern

**Status:** Open  
**Priority:** High  
**Components:** All universal components (`audio`, `llm`, `tts`, `asr`)

### Problem

All components use explicit imports and hardcoded provider mappings instead of configuration-driven loading, violating the Open/Closed Principle:

1. **Explicit Import Dependencies**: Every component imports ALL available providers at module level:
   ```python
   # Import all audio providers
   from ..providers.audio import (
       AudioProvider,
       ConsoleAudioProvider,
       SoundDeviceAudioProvider,
       AudioPlayerAudioProvider,
       AplayAudioProvider,
       SimpleAudioProvider
   )
   ```

2. **Hardcoded Provider Mappings**: Each component maintains hardcoded dictionaries:
   ```python
   self._provider_classes = {
       "console": ConsoleAudioProvider,
       "sounddevice": SoundDeviceAudioProvider,
       "audioplayer": AudioPlayerAudioProvider,
       "aplay": AplayAudioProvider,
       "simpleaudio": SimpleAudioProvider
   }
   ```

3. **Duplicated Loading Logic**: Nearly identical provider instantiation code across all components

### Current Issues

- **Tight Coupling**: Components must know about ALL providers at compile time
- **Import-Time Loading**: All provider modules imported even if unused
- **Extension Difficulties**: External plugins cannot easily add new providers
- **Maintenance Overhead**: Adding providers requires code changes in multiple places
- **Scalability Problems**: Provider lists become unwieldy as ecosystem grows

### Proposed Solution: Configuration-Driven Provider System

**Phase 1: Dynamic Provider Discovery**
- Create provider registry system similar to existing `PluginRegistry`
- Use existing `safe_import()` utility from `loader.py` for dynamic loading
- Define provider configuration schema in config files

**Phase 2: Provider Registration API**
```python
# Configuration-based
providers:
  audio:
    - name: "console"
      module: "irene.providers.audio.console"
      class: "ConsoleAudioProvider"
      enabled: true

# Or decorator-based registration
@register_audio_provider("sounddevice")
class SoundDeviceAudioProvider(AudioProvider):
    pass
```

**Phase 3: Lazy Loading**
- Load providers only when needed
- Cache provider instances efficiently
- Support hot-swapping of providers

### Benefits
- **Loose Coupling**: Components discover providers through configuration
- **External Extensibility**: Plugins can register new providers
- **Performance**: Lazy loading reduces startup overhead
- **Maintainability**: No code changes needed to add providers
- **Testability**: Easy to mock/substitute providers

### Existing Infrastructure
The codebase already has supporting utilities:
- `PluginRegistry` (dynamic discovery pattern)
- `safe_import()` (graceful dynamic imports)
- `DependencyChecker` (provider availability validation)

### Impact
- **Breaking Change**: Provider loading mechanism changes
- **Migration Needed**: All components require refactoring
- **Configuration Changes**: Provider configs need restructuring
- **Plugin API**: New provider registration system

### Related Files
- `irene/components/audio_component.py` (lines 24-31, 104-110)
- `irene/components/llm_component.py` (lines 20-25, 84-88)
- `irene/components/tts_component.py` (lines 21-29, 93-100)
- `irene/components/asr_component.py` (lines 24-29, 89-93)
- `irene/utils/loader.py` (existing dynamic loading utilities)
- `irene/plugins/registry.py` (pattern for configuration-driven discovery)

## 3. Disconnected NLU and Intent Handler Systems

**Status:** Open  
**Priority:** Medium  
**Components:** Intent system (`irene/intents/`) and NLU providers (`irene/providers/nlu/`)

### Problem

The intent recognition system has two separate, non-communicating parts that should be integrated:

1. **NLU Providers Define Patterns**: NLU providers have hardcoded recognition patterns:
   ```python
   # In RuleBasedNLUProvider._initialize_patterns()
   self.patterns = {
       "timer.set": [
           re.compile(r"\b(поставь|установи|засеки)\s+(таймер|время)\b"),
           re.compile(r"\b(set|start)\s+(timer|alarm)\b"),
       ],
       "greeting.hello": [
           re.compile(r"\b(привет|здравствуй|добро пожаловать)\b"),
           re.compile(r"\b(hello|hi|hey|greetings)\b"),
       ],
   }
   ```

2. **Intent Handlers Define Capabilities**: Handlers define what they can handle but don't contribute to recognition:
   ```python
   # Intent handlers define capabilities AFTER intent is recognized
   def get_supported_domains(self) -> List[str]:
       return ["timer", "system"]  # This is NOT used by NLU

   async def can_handle(self, intent: Intent) -> bool:
       return intent.domain == "timer"  # This is validation, not recognition
   ```

3. **No Bidirectional Communication**: Recognition and handling are completely separate

### Current Architecture Gap

```
Text → NLU Provider (hardcoded patterns) → Intent → Handler Registry → Handler
            ↑                                              ↓
    Hardcoded patterns                           Handler capabilities
    (NOT contributed by handlers)                (NOT used by NLU)
```

### Current Issues

- **Manual Synchronization**: Adding new intents requires updating both NLU patterns AND handler logic
- **Duplicate Knowledge**: Intent capabilities defined in two places
- **Inconsistency Risk**: NLU patterns and handler capabilities can get out of sync
- **Extension Limitations**: New intent handlers can't automatically contribute to recognition
- **Maintenance Overhead**: Pattern updates require changes in multiple files

### Proposed Solution: Dynamic Intent-Handler Integration

**Phase 1: Handler Keyword Contribution**
- Allow intent handlers to provide keywords/patterns to NLU providers
- Create `get_recognition_patterns()` method in `IntentHandler` base class
- NLU providers query registered handlers for patterns on initialization

**Phase 2: Bidirectional Communication**
```python
# Intent handlers contribute to NLU
class TimerIntentHandler(IntentHandler):
    def get_recognition_patterns(self) -> Dict[str, List[str]]:
        return {
            "timer.set": ["поставь таймер", "установи будильник", "set timer"],
            "timer.cancel": ["отмени таймер", "убери будильник", "cancel timer"]
        }

# NLU providers use handler-contributed patterns
class RuleBasedNLUProvider:
    async def _initialize_patterns(self):
        # Get patterns from registered intent handlers
        handler_patterns = await self._get_patterns_from_handlers()
        self.patterns.update(handler_patterns)
```

**Phase 3: Dynamic Pattern Updates**
- Update NLU patterns when handlers are registered/unregistered
- Support runtime pattern modifications
- Cache compiled patterns for performance

### Benefits
- **Single Source of Truth**: Intent capabilities defined once in handlers
- **Automatic Synchronization**: NLU patterns automatically reflect handler capabilities
- **Dynamic Extensibility**: New handlers automatically contribute to recognition
- **Reduced Maintenance**: Adding intents requires changes in one place only
- **Better Consistency**: No risk of NLU/handler mismatch

### Current Processing Flow
```
Audio → ASR → Text Processing → NLU Recognition → Intent Orchestration → Handler Execution
```

### Enhanced Flow
```
Handlers → Contribute Patterns → NLU Providers
           ↓
Audio → ASR → Text Processing → NLU Recognition → Intent Orchestration → Handler Execution
```

### Impact
- **Breaking Change**: NLU provider initialization logic changes
- **Handler Interface**: New methods in `IntentHandler` base class
- **Performance**: Need to balance pattern updates with runtime performance
- **Backward Compatibility**: Existing hardcoded patterns should still work

### Related Files
- `irene/intents/handlers/base.py` (base handler interface)
- `irene/intents/registry.py` (handler registration and discovery)
- `irene/intents/recognizer.py` (NLU provider coordination)
- `irene/providers/nlu/rule_based.py` (pattern-based recognition)
- `irene/providers/nlu/spacy_provider.py` (semantic recognition)
- `irene/workflows/voice_assistant.py` (main processing pipeline) 