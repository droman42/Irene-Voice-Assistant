# Language Detection Architecture Fix

## Overview

This document outlines the architectural fix for language detection in the Irene Voice Assistant system. The current implementation has language detection scattered across individual handlers, leading to inconsistent behavior, performance issues, and architectural violations.

## Current Problems

### 1. Architectural Issues
- **Wrong Abstraction Level**: Language detection happens in intent handlers instead of the NLU pipeline
- **Intent Entity Misuse**: Language information stored in `intent.entities` instead of conversation context
- **Scattered Logic**: Each handler implements its own `_detect_language()` method
- **Method Signature Inconsistency**: Donation-driven routing expects `(intent, context)` but handlers need `(intent, context, language)`

### 2. Performance Issues
- **Redundant Processing**: Language detection runs multiple times per request
- **Inefficient**: Text analysis repeated in each handler
- **No Caching**: Language preference not persisted across conversation

### 3. Code Quality Issues
- **Code Duplication**: Similar language detection logic in multiple handlers
- **Inconsistent Results**: Different handlers may detect different languages for the same text
- **Maintenance Burden**: Changes to language detection require updates in multiple files

## Proposed Solution

### Architecture Overview

```
Text Input → NLU Component → Language Detection → Context Enhancement → Intent Recognition → Handler Execution
```

### Key Principles

1. **Single Responsibility**: Language detection happens once in the NLU pipeline
2. **Context-Based Storage**: Language stored in `ConversationContext.language`
3. **Session Persistence**: Language preference maintained across conversation
4. **Handler Simplification**: Handlers use `context.language` directly

## Implementation Plan

### Phase 1: NLU-Level Language Detection ✅ **COMPLETED**

#### 1.1 Enhance NLU Component
**File**: `irene/components/nlu_component.py`

Add language detection to the `ContextAwareNLUProcessor.process_with_context()` method:

```python
async def process_with_context(self, text: str, context: ConversationContext) -> Intent:
    # 1. Detect language if not already set or if auto-detection enabled
    if not context.language or self._should_redetect_language(context):
        detected_language = await self._detect_language(text, context)
        context.language = detected_language
        self.logger.debug(f"Language detected/updated: {detected_language}")
    
    # 2. Continue with existing NLU processing
    intent = await self.nlu_component.recognize(text, context)
    
    # 3. Enhance intent with context (existing logic)
    resolved_entities = await self.entity_resolver.resolve_entities(intent.entities, context)
    enhanced_intent = await self._enhance_with_context(intent, context, resolved_entities)
    
    return enhanced_intent
```

#### 1.2 Implement Language Detection Method
**File**: `irene/components/nlu_component.py`

```python
async def _detect_language(self, text: str, context: ConversationContext) -> str:
    """
    Detect language from text with context awareness.
    
    Priority order:
    1. User preference from context.user_preferences
    2. Previous conversation language (if confidence high)
    3. Text-based detection
    4. System default
    """
    # Check user preferences
    if context.user_preferences.get('language'):
        return context.user_preferences['language']
    
    # Check conversation history confidence
    if (context.language and 
        len(context.conversation_history) > 0 and
        self._get_language_confidence(context) > 0.8):
        return context.language
    
    # Perform text-based detection
    return self._analyze_text_language(text)

def _analyze_text_language(self, text: str) -> str:
    """Analyze text to detect language using multiple indicators."""
    text_lower = text.lower()
    
    # Cyrillic character detection
    cyrillic_chars = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
    cyrillic_ratio = cyrillic_chars / len(text) if text else 0
    
    # Common Russian words
    russian_indicators = ['что', 'как', 'где', 'когда', 'почему', 'привет', 'спасибо']
    russian_count = sum(1 for word in russian_indicators if word in text_lower)
    
    # Common English words  
    english_indicators = ['what', 'how', 'where', 'when', 'why', 'hello', 'thanks']
    english_count = sum(1 for word in english_indicators if word in text_lower)
    
    # Decision logic
    if cyrillic_ratio > 0.3 or russian_count > english_count:
        return "ru"
    elif english_count > 0:
        return "en"
    else:
        return "ru"  # Default to Russian
```

#### 1.3 Configuration Enhancement
**File**: `irene/config/models.py`

Add language detection configuration to `NLUConfig`:

```python
class NLUConfig(BaseModel):
    # ... existing fields ...
    
    # Language detection settings
    auto_detect_language: bool = True
    language_detection_confidence_threshold: float = 0.8
    persist_language_preference: bool = True
    supported_languages: List[str] = ["ru", "en"]
    default_language: str = "ru"
```

**Phase 1 Implementation Status:**
- ✅ Enhanced `ContextAwareNLUProcessor.process_with_context()` method with language detection
- ✅ Implemented `_detect_language()` method with priority-based detection logic
- ✅ Implemented `_analyze_text_language()` method with Cyrillic and keyword detection
- ✅ Implemented `_should_redetect_language()` method for configuration-driven re-detection
- ✅ Implemented `_get_language_confidence()` method for conversation history analysis
- ✅ Added language detection configuration to `NLUConfig` in `irene/config/models.py`
- ✅ Added language detection configuration section to `configs/config-master.toml`

**Files Modified:**
- `irene/components/nlu_component.py` - Added language detection methods to `ContextAwareNLUProcessor`
- `irene/config/models.py` - Extended `NLUConfig` with language detection settings
- `configs/config-master.toml` - Added language detection configuration section

### Phase 2: Handler Simplification ✅ **COMPLETED**

#### 2.1 Remove Language Detection from Handlers
**Files**: All handler files in `irene/intents/handlers/`

**Before**:
```python
async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
    # Determine language preference (default to Russian)
    language = self._detect_language(intent.raw_text, context)
    
    if intent.action == "goodbye":
        return await self._handle_farewell(intent, context, language)
    # ...

def _detect_language(self, text: str, context: ConversationContext) -> str:
    # ... duplicate detection logic ...
```

**After**:
```python
async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
    # Use language from context (detected by NLU)
    language = context.language
    
    if intent.action == "goodbye":
        return await self._handle_farewell(intent, context)
    # ...

# Remove _detect_language method entirely
```

#### 2.2 Update Method Signatures
**Files**: All handler files

**Before**:
```python
async def _handle_greeting(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
    # Extract language from intent parameters or detect from text
    language = intent.entities.get("language", "ru")
    if not language:
        language = self._detect_language(intent.raw_text, context)
    # ...
```

**After**:
```python
async def _handle_greeting(self, intent: Intent, context: ConversationContext) -> IntentResult:
    # Use language from context (already detected by NLU)
    language = context.language
    # ...
```

#### 2.3 Update Execute Method Calls
**Files**: All handler files

**Before**:
```python
return await self._handle_greeting(intent, context, language)
```

**After**:
```python
return await self._handle_greeting(intent, context)
```

**Phase 2 Implementation Status:**
- ✅ Removed `_detect_language()` method from all intent handlers
- ✅ Updated `execute()` methods to use `context.language` instead of individual detection
- ✅ Updated method signatures to remove `language` parameter from handler methods
- ✅ Updated method calls to remove `language` parameter
- ✅ Fixed error handling to use `context.language` for localized messages

**Files Modified:**
- `irene/intents/handlers/greetings.py` - Removed `_detect_language()` method, updated all methods
- `irene/intents/handlers/conversation.py` - Removed `_detect_language()` method, updated method signatures
- `irene/intents/handlers/datetime.py` - Removed `_detect_language()` method, updated all handler methods
- `irene/intents/handlers/system.py` - Removed `_detect_language()` method, updated all handler methods
- `irene/intents/handlers/random_handler.py` - Removed `_get_language()` method, updated 4 handler methods
- `irene/intents/handlers/timer.py` - Fixed 3 hardcoded language assignments to use `context.language`
- `irene/intents/handlers/train_schedule.py` - Removed `_get_language()` method, updated 5 usage locations
- `irene/intents/handlers/audio_playback_handler.py` - Removed `_get_language()` method, updated all usages
- `irene/intents/handlers/voice_synthesis_handler.py` - Removed `_get_language()` method, updated all usages
- `irene/intents/handlers/provider_control_handler.py` - Removed `_get_language()` method, updated all usages

**Key Changes:**
- All handlers now use `context.language or "ru"` for language determination
- Removed **10 language detection methods** (6 `_detect_language()` + 4 `_get_language()`)
- Eliminated **~200 lines of duplicate language detection code**
- Updated **25+ handler method signatures** to remove language parameter
- Fixed **3 hardcoded language assignments** in timer stop commands
- **Complete centralization** - zero redundant language detection remaining

### Phase 3: Context Enhancement ✅ **COMPLETED**

#### 3.1 Language Preference Persistence ✅ **COMPLETED**
**File**: `irene/intents/context.py`

```python
async def update_language_preference(self, session_id: str, language: str):
    """Update user's language preference for future sessions."""
    context = await self.get_context(session_id)
    context.user_preferences['language'] = language
    context.language = language
    context.last_updated = time.time()
    logger.info(f"Updated language preference for session {session_id}: {language}")
```

#### 3.2 Language Switching Support ✅ **COMPLETED**
**File**: `irene/intents/handlers/system.py`

Add language switching intent handler:

```python
async def _handle_language_switch(self, intent: Intent, context: ConversationContext) -> IntentResult:
    """Handle language switching requests."""
    target_language = intent.entities.get('language', 'ru')
    
    # Validate language
    if target_language not in ['ru', 'en']:
        return IntentResult(
            text="Поддерживаются только русский и английский языки." if context.language == 'ru' 
                 else "Only Russian and English languages are supported.",
            should_speak=True
        )
    
    # Update context and preferences
    context.language = target_language
    context.user_preferences['language'] = target_language
    
    response = "Язык изменён на русский." if target_language == 'ru' else "Language changed to English."
    
    return IntentResult(
        text=response,
        should_speak=True,
        metadata={'language_changed': target_language}
    )
```

**Phase 3 Implementation Status:**
- ✅ Added `update_language_preference()` method to `ContextManager` in `irene/intents/context.py`
- ✅ Added `_handle_language_switch()` method to `SystemIntentHandler` in `irene/intents/handlers/system.py`
- ✅ Updated system handler routing to support language switch intents
- ✅ Implemented language validation (supports 'ru' and 'en')
- ✅ Added context manager integration with fallback for direct context updates
- ✅ Added proper error handling and logging

**Files Modified:**
- `irene/intents/context.py` - Added language preference persistence method
- `irene/intents/handlers/system.py` - Added language switching handler and routing

## Implementation Details

### Files to Modify

#### Core Components
1. **`irene/components/nlu_component.py`**
   - Add language detection to `ContextAwareNLUProcessor`
   - Implement `_detect_language()` and `_analyze_text_language()`
   - Add configuration support

2. **`irene/config/models.py`**
   - Extend `NLUConfig` with language detection settings

3. **`irene/intents/context.py`**
   - Add language preference persistence methods

#### Intent Handlers (Remove language detection)
1. **`irene/intents/handlers/greetings.py`** ⚠️ **SPECIAL ATTENTION REQUIRED**
   - **Current State**: Partially fixed with wrong approach - method signatures updated but still contains language detection logic
   - **Required Changes**:
     - Remove `_detect_language()` method (lines 162-178)
     - Update `execute()` method to use `context.language` instead of `self._detect_language()` (line 82)
     - Remove individual language detection in handler methods (lines 183-185, 208-210, 228-230)
     - Remove `intent.entities.get("language", "ru")` fallback logic (lines 183, 208, 228)
   - Use `context.language` directly throughout

2. **`irene/intents/handlers/conversation.py`**
   - Remove `_detect_language()` method
   - Update method signatures
   - Use `context.language` directly

3. **`irene/intents/handlers/datetime.py`**
   - Remove `_detect_language()` method
   - Update method signatures
   - Use `context.language` directly

4. **`irene/intents/handlers/system.py`**
   - Remove `_detect_language()` method
   - Update method signatures
   - Add language switching handler
   - Use `context.language` directly

5. **`irene/intents/handlers/timer.py`**
   - Remove `_detect_language()` method
   - Update method signatures
   - Use `context.language` directly

#### Configuration Files
1. **`configs/config-master.toml`**
   - Add language detection configuration section

### Configuration Changes

Add to `configs/config-master.toml`:

```toml
[nlu]
# ... existing NLU config ...

# Language Detection Configuration
auto_detect_language = true
language_detection_confidence_threshold = 0.8
persist_language_preference = true
supported_languages = ["ru", "en"]
default_language = "ru"
```

### Migration Strategy

#### Step 1: Implement NLU Language Detection
- Add language detection to NLU component
- Test with existing handlers (backward compatible)
- Verify language is properly set in context

#### Step 2: Update Handlers Incrementally
- Start with `GreetingsIntentHandler` (already partially fixed)
- Update one handler at a time
- Test each handler individually
- Ensure donation-driven routing works

#### Step 3: Remove Legacy Code
- Remove all `_detect_language()` methods from handlers
- Clean up unused imports
- Update tests

#### Step 4: Add Advanced Features
- Language switching intent
- User preference persistence
- Multi-language intent patterns

## Benefits

### Performance Improvements
- **Single Detection**: Language detected once per request instead of per handler
- **Caching**: Language preference cached in session context
- **Reduced Processing**: No redundant text analysis

### Code Quality Improvements
- **DRY Principle**: Single language detection implementation
- **Consistent Results**: Same language used across all handlers
- **Maintainable**: Changes in one place affect entire system
- **Testable**: Centralized logic easier to test

### User Experience Improvements
- **Consistent Responses**: All handlers use same detected language
- **Language Persistence**: Language preference remembered across conversation
- **Language Switching**: Users can change language mid-conversation
- **Better Detection**: More sophisticated detection algorithm

### Architectural Improvements
- **Proper Separation**: Language detection in NLU layer where it belongs
- **Clean Interfaces**: Handlers have consistent method signatures
- **Context-Driven**: Language as conversation state, not system config
- **Extensible**: Easy to add new languages or detection methods

## Testing Strategy

### Unit Tests
1. **Language Detection Tests**
   - Test text analysis with various inputs
   - Test context-based detection
   - Test preference persistence

2. **Handler Tests**
   - Verify handlers use `context.language`
   - Test with different language contexts
   - Ensure no regression in functionality

3. **Integration Tests**
   - Test full pipeline with language detection
   - Verify context propagation
   - Test language switching

### Test Cases
```python
# Language detection tests
def test_russian_text_detection():
    assert detect_language("Привет, как дела?") == "ru"

def test_english_text_detection():
    assert detect_language("Hello, how are you?") == "en"

def test_context_language_persistence():
    context.language = "en"
    # Verify language persists across requests

def test_user_preference_override():
    context.user_preferences['language'] = "en"
    # Verify preference takes priority over detection
```

## Rollback Plan

If issues arise during implementation:

1. **Immediate Rollback**: Revert to individual handler language detection
2. **Partial Rollback**: Keep NLU detection but restore handler fallbacks
3. **Configuration Rollback**: Disable auto-detection via configuration

## Future Enhancements

### Multi-Language Intent Patterns
- Different intent patterns per language
- Language-specific entity extraction
- Localized intent names

### Advanced Detection
- Machine learning-based detection
- Context-aware language switching
- Regional dialect support

### User Interface
- Language preference in user settings
- Visual language indicators
- Language switching commands

## Conclusion

This architectural fix addresses fundamental issues in the current language detection system by:

1. **Centralizing** language detection in the NLU pipeline
2. **Utilizing** existing `ConversationContext.language` property
3. **Simplifying** handler implementations
4. **Improving** performance and consistency
5. **Enabling** advanced language features

The implementation follows the existing architectural patterns and requires minimal breaking changes while providing significant benefits in code quality, performance, and user experience.
