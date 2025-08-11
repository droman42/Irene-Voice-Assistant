# Phase 3.5 REVISED Pattern Analysis - JSON Donations vs Other Refactoring

## Executive Summary

**CLARIFICATION**: Not all hardcoded patterns belong in JSON donations. LLM prompts, response templates, and configuration values should be handled through separate refactoring approaches.

**REVISED JSON DONATION GAPS**: ~150+ patterns (not 300+) specifically related to NLU pattern recognition

**SEPARATE REFACTORING NEEDED**: ~150+ patterns for prompts, templates, and configuration

## JSON Donations vs Other Refactoring Categories

### ✅ **BELONGS IN JSON DONATIONS** (NLU Pattern Recognition)
- Intent name matching arrays (`intent.name in [...]`)
- Action matching arrays (`intent.action in [...]`)
- Language detection keyword arrays for NLU processing
- Recognition patterns from `get_*_patterns()` methods
- Parameter extraction patterns (regex, spaCy patterns)
- Entity recognition patterns
- Trigger phrases and lemmas
- Token patterns and slot patterns

### ❌ **DOES NOT BELONG IN JSON DONATIONS** (Separate Refactoring)
- LLM system prompts and conversation prompts
- Response templates and message arrays
- Configuration dictionaries (timeouts, models, etc.)
- Version information and build constants
- API keys and default settings
- Error messages and status responses
- Complex business logic and conditional responses

## Revised Handler-by-Handler Analysis

### 1. GreetingsIntentHandler
**JSON Donation Gaps (30 patterns):**
- ✅ Intent name arrays: `["greeting.hello", "greeting.goodbye", "greeting.welcome"]`
- ✅ Action matching: `["hello", "goodbye", "welcome", "greet"]`
- ✅ Language detection arrays (11 values)
- ✅ Pattern method patterns (13 regex patterns)
- ✅ Time-based recognition patterns (2-3 patterns)

**SEPARATE Refactoring (50+ patterns):**
- ❌ Response templates (50+ greeting/farewell messages) → **External template files**
- ❌ Time-based responses → **Configuration/template system**

### 2. SystemIntentHandler
**JSON Donation Gaps (25 patterns):**
- ✅ Intent name arrays: `["system.status", "system.help", "system.version", "system.info"]`
- ✅ Action matching: `["status", "help", "version", "info", "statistics"]`
- ✅ Language detection arrays (11 values)
- ✅ Pattern method patterns (8 regex patterns)

**SEPARATE Refactoring (200+ patterns):**
- ❌ Response templates (200+ lines of help/status text) → **External template files**
- ❌ Version information ("13.0.0") → **Configuration system**

### 3. ConversationIntentHandler
**JSON Donation Gaps (25 patterns):**
- ✅ Intent name arrays: `["chat.start", "chat.continue", "chat.reference", "chat.end"]`
- ✅ Language detection for trigger recognition
- ✅ Pattern method patterns (10 regex patterns)
- ✅ Confidence threshold patterns for fallback detection

**SEPARATE Refactoring (20+ patterns):**
- ❌ LLM system prompts → **External prompt files + TODO comment**
- ❌ Configuration dictionary (models, timeouts) → **Configuration system**
- ❌ Response templates (greeting/farewell arrays) → **External template files**

### 4. DateTimeIntentHandler ⚠️ MOST COMPLEX
**JSON Donation Gaps (50+ patterns):**
- ✅ Intent name arrays: `["datetime.current_time", "datetime.current_date", "datetime.current_datetime"]`
- ✅ Action matching: `["current_time", "current_date", "get_time", "get_date"]`
- ✅ Language detection arrays (11 values)
- ✅ Pattern method patterns (8 regex patterns)
- ✅ **Temporal recognition patterns**: Partial migration of weekday/month recognition for NLU

**SEPARATE Refactoring (70+ patterns):**
- ❌ **Response formatting arrays** (weekdays, months, ordinals for OUTPUT) → **Localization files**
- ❌ **Complex time logic** (period assignments, formatting rules) → **Keep in handler logic**

**SPECIAL CASE**: DateTimeIntentHandler requires careful separation:
- **Recognition patterns** (input processing) → JSON donations
- **Formatting patterns** (output generation) → Localization system

### 5. TimerIntentHandler
**JSON Donation Gaps (40+ patterns):**
- ✅ Intent name arrays: `["timer.set", "timer.cancel", "timer.list", "timer.status"]`
- ✅ Action matching: `["set", "cancel", "list", "status", "create", "remove"]`
- ✅ Pattern method patterns (9 regex patterns)
- ✅ **Duration parsing patterns** (5 regex patterns for extraction)
- ✅ **Unit recognition patterns** (Russian unit text recognition)
- ✅ **Message extraction patterns** (3 regex patterns)

**SEPARATE Refactoring (15+ patterns):**
- ❌ Unit multipliers (seconds/minutes/hours/days) → **Configuration constants**
- ❌ Error messages and responses → **Template system**

### 6. TrainScheduleIntentHandler
**JSON Donation Gaps (15+ patterns):**
- ✅ Intent name arrays: `["transport.train_schedule", "transport.get_trains"]`
- ✅ Domain/action matching
- ✅ **Train keywords**: `["электричка", "электрички", "поезд", "ближайший поезд", "расписание поездов", "расписание электричек"]`

**SEPARATE Refactoring (15+ patterns):**
- ❌ Configuration defaults (station IDs, max results) → **Configuration system**
- ❌ Response templates (7+ response strings) → **Template system**

## REVISED Migration Priority

### Priority 1 (CRITICAL): DateTimeIntentHandler - Input Recognition Only
- **50+ NLU patterns** for temporal recognition
- **Keep formatting logic** in handler (not JSON donations)
- **Most complex separation** between input recognition vs output formatting

### Priority 2 (HIGH): TimerIntentHandler
- **40+ parsing patterns** for duration and unit recognition
- **Clear separation** between recognition (JSON) and processing (handler)

### Priority 3 (MEDIUM): All Other Handlers
- **25-30 patterns each** mostly intent/action arrays and basic recognition
- **Simpler patterns** to migrate

## Required JSON Schema Enhancements

### New Fields for JSON Donations:
- **Intent/Action Arrays**: Complete intent name and action arrays
- **Recognition Keywords**: Language-specific trigger words for NLU
- **Complex Extraction**: Multi-step regex and spaCy patterns for parameter extraction
- **Entity Recognition**: Enhanced entity patterns for complex extractions

### NOT Needed in JSON Schema:
- ❌ Response templates (external files)
- ❌ LLM prompts (external files + TODO)
- ❌ Configuration values (TOML configuration)
- ❌ Localization data (separate l10n system)

## Refactoring Strategy

### Phase 3.5A: JSON Donation Migration (~150 patterns)
1. **Input Recognition Patterns**: Intent matching, action matching, language detection
2. **Parameter Extraction**: Complex parsing patterns for user input
3. **Entity Recognition**: Advanced spaCy and regex patterns for NLU

### Phase 3.5B: Separate Refactoring (TODO Comments + Future Phases)
1. **LLM Prompts**: Add TODO comments, plan external prompt file system
2. **Response Templates**: Extract to external template files with i18n support
3. **Configuration**: Move hardcoded config to TOML configuration system
4. **Localization**: Extract language-specific formatting to l10n system

## Updated Risk Assessment

**REVISED SCOPE**: JSON donation migration is more focused (~150 patterns vs 300+)

**MANAGEABLE APPROACH**: 
- **Phase 3.5A**: Complete JSON donations for NLU recognition
- **Phase 3.5B**: Plan and TODO-comment other refactoring needs
- **Future Phases**: Address templates, prompts, and configuration separately

**CRITICAL PATH**: Focus on JSON donations for NLU pattern recognition first, defer template/prompt refactoring to later phases.

## Implementation Plan

1. **Complete JSON migrations** for intent recognition and parameter extraction
2. **Add TODO comments** for LLM prompts with migration plans
3. **Add TODO comments** for response templates with template system plans
4. **Keep configuration** in handlers for now, plan TOML migration later
5. **Proceed with Phase 4** once NLU recognition patterns are migrated
