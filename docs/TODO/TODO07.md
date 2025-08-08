## 7. Disconnected NLU and Intent Handler Systems

**Status:** Open  
**Priority:** High  
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
