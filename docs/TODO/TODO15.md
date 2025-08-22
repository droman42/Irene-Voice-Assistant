# TODO #15: Handler Response Templates and Configuration Refactoring

## Overview

This TODO covers the refactoring of hardcoded response templates, LLM prompts, and configuration values found during Phase 3.5 pattern analysis. These patterns are **NOT** part of the JSON donation system (which focuses on NLU recognition patterns) but require separate refactoring approaches.

## Scope: ~200+ Non-NLU Hardcoded Patterns Across 15 Intent Handlers

### Pattern Categories (MECE Classification):
1. **LLM System Prompts**: Hardcoded conversation prompts and templates (1 handler)
2. **Response Templates**: Greeting messages, error responses, status text (8 handlers)
3. **Configuration Constants**: Timeouts, limits, API settings (4 handlers)
4. **Localization Data**: Language-specific formatting arrays (3 handlers)
5. **Asset Migration**: JSON donation files and schema relocation (all handlers)

## Handler Classification by Pattern Type

### Category A: Configuration-Driven Handlers (Require Pydantic Models)
These handlers have configurable parameters that need TOML configuration and Pydantic validation.

#### A1. ConversationIntentHandler - LLM Prompts + Configuration
**Current Issues:**
```python
# Hardcoded prompts (Lines 68-70)
self.config = {
    "chat_system_prompt": "Ты - Ирина, голосовой помощник...",
    "reference_system_prompt": "Ты помощник для получения точных фактов...",
    "session_timeout": 1800, "max_sessions": 50, "max_context_length": 10
}
```

**Required Pydantic Model:**
```python
class ConversationHandlerConfig(BaseModel):
    session_timeout: int = Field(default=1800, ge=60, description="Session timeout in seconds")
    max_sessions: int = Field(default=50, ge=1, le=1000, description="Maximum concurrent sessions")
    max_context_length: int = Field(default=10, ge=1, le=100, description="Maximum conversation context length")
    default_conversation_confidence: float = Field(default=0.6, ge=0.0, le=1.0, description="Default confidence threshold")
```

**Priority**: High (LLM integration + configuration critical)

#### A2. TrainScheduleIntentHandler - API Configuration
**Current Issues:**
```python
# Already uses config.get() but lacks validation (Lines 47-49, 187)
self.api_key = self.config.get("api_key", "")
self.default_from_station = self.config.get("from_station", "s9600681")
self.max_results = self.config.get("max_results", 3)
response = requests.get(url, params=params, timeout=10)  # Hardcoded timeout
```

**Required Pydantic Model:**
```python
class TrainScheduleHandlerConfig(BaseModel):
    api_key: str = Field(default="", description="Yandex Schedules API key")
    from_station: str = Field(default="s9600681", description="Default departure station ID")
    to_station: str = Field(default="s2000002", description="Default destination station ID")
    max_results: int = Field(default=3, ge=1, le=20, description="Maximum schedule results")
    request_timeout: int = Field(default=10, ge=1, le=60, description="API request timeout in seconds")
```

**Priority**: Medium (existing config usage, needs proper model)

#### A3. TimerIntentHandler - Time Limits and Multipliers
**Current Issues:**
```python
# Hardcoded constants (Lines 383-396)
unit_multipliers = {'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400}
if total_seconds < 1: raise ValueError("Время таймера слишком мало")
if total_seconds > 86400: raise ValueError("Время таймера слишком велико")
```

**Required Pydantic Model:**
```python
class TimerHandlerConfig(BaseModel):
    min_seconds: int = Field(default=1, ge=1, description="Minimum timer duration in seconds")
    max_seconds: int = Field(default=86400, ge=1, description="Maximum timer duration in seconds")
    unit_multipliers: Dict[str, int] = Field(default={'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400})
```

**Priority**: Medium (affects timer functionality limits)

#### A4. RandomIntentHandler - Number Generation Limits
**Current Issues:**
```python
# Hardcoded limits (Lines 185, 321-326)
max_val = intent.entities.get("max", 100)  # Default max of 100
if abs(max_val - min_val) > 1000000: raise ValueError("Range too large")
```

**Required Pydantic Model:**
```python
class RandomHandlerConfig(BaseModel):
    default_max_number: int = Field(default=100, ge=1, description="Default maximum for random numbers")
    max_range_size: int = Field(default=1000000, ge=1, description="Maximum allowed range size")
    default_dice_sides: int = Field(default=6, ge=2, le=100, description="Default number of dice sides")
```

**Priority**: Low (entertainment functionality)

### Category B: Template-Only Handlers (No Configuration Needed)
These handlers only have hardcoded response templates and require template externalization.

#### B1. GreetingsIntentHandler - Static Response Arrays
```python
self.greetings_ru = [10 hardcoded responses]
self.farewells_ru = [10 hardcoded responses]
self.welcome_messages_ru = [5 hardcoded responses]
```
**Priority**: Medium (user-facing)

#### B2. SystemIntentHandler - Multi-line Help Text
```python
help_text = """I'm Irene, your voice assistant. Here's what I can help you with:..."""
```
**Priority**: Medium (informational responses)

#### B3. SpeechRecognitionIntentHandler - Error Messages
```python
response_text = f"Настройка качества распознавания речи ({quality}) пока не реализована"
```
**Priority**: Low (error messages only)

#### B4. VoiceSynthesisIntentHandler - Status Responses
```python
response_text = f"Синтезирую речь '{text_to_speak}'"
response = f"Переключился на TTS провайдер {provider_name}"
```
**Priority**: Medium (user-facing functionality)

#### B5. TranslationIntentHandler - Result Formatting
```python
response_text = f"Перевод: {translated}"
target_language = intent.entities.get("target_language", "английский")
```
**Priority**: Low (simple formatting)

#### B6. TextEnhancementIntentHandler - Result Formatting
```python
response_text = f"Улучшенный текст: {enhanced}"
```
**Priority**: Low (simple formatting)

#### B7. AudioPlaybackIntentHandler - Status Messages
```python
response_text = f"Начинаю воспроизведение аудио: {audio_file}"
```
**Priority**: Low (simple formatting)

### Category C: Localization-Driven Handlers (Language-Specific Data)
These handlers require locale-specific data externalization.

#### C1. DateTimeIntentHandler - Temporal Formatting Arrays
```python
self.weekdays_ru = ["понедельник", "вторник", "среда", ...]
self.months_ru = ["января", "февраля", "марта", ...]
self.hours_ru = ["двенадцать", "час", "два", ...]
```
**Priority**: High (essential functionality, complex separation needed)

#### C2. VoiceSynthesisIntentHandler - Provider Mappings
```python
provider_mapping = {
    "ксении": ("silero_v3", {"speaker": "xenia"}),
    "силеро": ("silero_v3", {}), "консоли": ("console", {})
}
```
**Priority**: Medium (system functionality)

#### C3. ProviderControlIntentHandler - Component Mappings
```python
component_mapping = {
    "аудио": "audio", "llm": "llm", "распознавание": "asr", "голос": "tts"
}
```
**Priority**: Medium (system control)

#### C4. BaseIntentHandler - Universal Patterns
```python
stop_patterns = ["стоп", "останови", "stop", "halt"]
domain_hints = {"music": ["музыка", "music"], "timer": ["таймер", "timer"]}
```
**Priority**: Medium (affects all handlers)

#### C5. RandomIntentHandler - Result Arrays
```python
self.coin_results_ru = ["Выпал орёл", "Выпала решка"]
self.dice_results_ru = ["Выпала единица", "Выпало два", ...]
```
**Priority**: Low (entertainment)

## Assets Infrastructure Requirements

### Unified Asset Loading Architecture

Instead of multiple separate managers, we will implement a **single unified `IntentAssetLoader`** that handles all asset types. This approach:

1. **Reuses Existing Patterns**: Extends the proven `DonationLoader` pattern already in use
2. **Eliminates Duplication**: Single loader for all asset types (donations, templates, prompts, localization)
3. **Maintains Consistency**: Unified error handling, validation, and caching across all assets
4. **Simplifies Dependencies**: Handlers receive one asset loader instead of multiple managers

### IntentAssetLoader Architecture

```python
class IntentAssetLoader:
    """Unified loader for all intent handler assets"""
    
    def __init__(self, assets_root: Path, config: AssetLoaderConfig):
        self.assets_root = assets_root
        self.config = config
        
        # Asset caches
        self.donations: Dict[str, HandlerDonation] = {}
        self.templates: Dict[str, Dict[str, Any]] = {}
        self.prompts: Dict[str, Dict[str, str]] = {}
        self.localizations: Dict[str, Dict[str, Any]] = {}
        
        # Error tracking (reuse donation loader pattern)
        self.validation_errors: List[str] = []
        self.warnings: List[str] = []
    
    async def load_all_assets(self, handler_names: List[str]) -> None:
        """Load all asset types for specified handlers"""
        await self._load_donations(handler_names)      # JSON donations
        await self._load_templates(handler_names)      # Response templates  
        await self._load_prompts(handler_names)        # LLM prompts
        await self._load_localizations(handler_names)  # Locale data
        
    # Unified API for handlers (extends existing donation loader interface)
    def get_donation(self, handler_name: str) -> Optional[HandlerDonation]:
        """Get JSON donation (existing functionality)"""
        
    def get_template(self, handler_name: str, template_name: str, language: str = "ru") -> str:
        """Get response template with i18n fallback"""
        
    def get_prompt(self, handler_name: str, prompt_type: str, language: str = "ru") -> str:
        """Get LLM prompt with language fallback"""
        
    def get_localization(self, domain: str, language: str = "ru") -> Dict[str, Any]:
        """Get localization data (arrays, mappings) with language fallback"""
        
    # Asset discovery and validation (reuses donation loader patterns)
    async def _discover_assets(self, asset_type: str, handler_names: List[str]) -> Dict[str, Path]:
        """Discover asset files following donation loader discovery patterns"""
        
    async def _validate_asset_schema(self, asset_path: Path, asset_type: str) -> bool:
        """Validate asset schemas (similar to donation validation)"""
        
    def _handle_validation_errors(self) -> None:
        """Fatal error handling (reuses donation loader error handling)"""
```

### Migration from Existing DonationLoader

The `IntentAssetLoader` will replace the current `DonationLoader` and `EnhancedHandlerManager` pattern:

**Current Architecture:**
```python
# Current: irene/core/donation_loader.py
class DonationLoader:
    async def discover_and_load_donations(handler_paths) -> Dict[str, HandlerDonation]

class EnhancedHandlerManager:
    def __init__(self, config):
        self.donation_loader = DonationLoader(...)
```

**New Unified Architecture:**
```python
# New: irene/core/intent_asset_loader.py  
class IntentAssetLoader:
    async def load_all_assets(handler_names) -> None:
        await self._load_donations(handler_names)      # Migrated from DonationLoader
        await self._load_templates(handler_names)      # New functionality
        await self._load_prompts(handler_names)        # New functionality  
        await self._load_localizations(handler_names)  # New functionality

class EnhancedHandlerManager:
    def __init__(self, config):
        self.asset_loader = IntentAssetLoader(...)  # Replaces donation_loader
```

### Asset Type Loading Implementation

**Donations (Existing Pattern Extended):**
- Migrate existing `DonationLoader._load_and_validate_donation()` logic
- Path: `assets/donations/{handler_name}.json`
- Validation: Existing JSON schema validation

**Templates (New - Category B Handlers):**
- File formats: YAML (arrays), JSON (objects), Markdown (multi-line)
- Path pattern: `assets/templates/{handler_name}/{language}/{template_name}.{yaml|json|md}`
- Fallback: `ru` → `en` → hardcoded defaults

**Prompts (New - Category A1 Handler):**
- File formats: Plain text (.txt)
- Path pattern: `assets/prompts/{handler_name}/{language}/{prompt_type}.txt`
- Fallback: `ru` → `en` → hardcoded defaults

**Localizations (New - Category C Handlers):**
- File formats: YAML (structured data)
- Path pattern: `assets/localization/{domain}/{language}.yaml`
- Fallback: `ru` → `en` → hardcoded defaults

### Directory Structure
```
assets/
├── v1.0.json                    # JSON donation schema (moved from schemas/)
├── donations/                   # Intent donation files (moved from handlers/donations/)
│   ├── conversation.json
│   ├── greetings.json
│   └── [all 14 other handlers].json
├── prompts/                     # LLM prompts (Category A1: ConversationIntentHandler)
│   └── conversation/
│       ├── ru/
│       │   ├── chat_system.txt
│       │   ├── reference_system.txt
│       │   └── reference_template.txt
│       └── en/
│           ├── chat_system.txt
│           ├── reference_system.txt
│           └── reference_template.txt
├── templates/                   # Response templates (Category B: 7 handlers)
│   ├── greetings/ru|en/         # B1: Arrays of greeting/farewell messages
│   ├── system/ru|en/            # B2: Multi-line help/status markdown
│   ├── speech_recognition/ru|en/ # B3: Error message templates
│   ├── voice_synthesis/ru|en/   # B4: Status response templates
│   ├── translation/ru|en/       # B5: Result formatting templates
│   ├── text_enhancement/ru|en/  # B6: Result formatting templates
│   └── audio_playback/ru|en/    # B7: Status message templates
└── localization/                # Locale-specific data (Category C: 5 handlers)
    ├── datetime/                # C1: DateTimeIntentHandler temporal arrays
    │   ├── ru.yaml              # weekdays, months, hours arrays
    │   └── en.yaml
    ├── voice_synthesis/         # C2: VoiceSynthesisIntentHandler mappings
    │   ├── providers.yaml       # Provider name mappings
    │   └── speakers.yaml        # Speaker name mappings  
    ├── components/              # C3: ProviderControlIntentHandler mappings
    │   ├── ru.yaml              # Component name mappings (ru)
    │   └── en.yaml              # Component name mappings (en)
    ├── commands/                # C4: BaseIntentHandler universal patterns
    │   ├── ru.yaml              # Stop patterns (ru)
    │   └── en.yaml              # Stop patterns (en)
    ├── domains/                 # C4: BaseIntentHandler domain hints
    │   ├── ru.yaml              # Domain vocabulary (ru)
    │   └── en.yaml              # Domain vocabulary (en)
    └── random/                  # C5: RandomIntentHandler result arrays
        ├── ru.yaml              # Coin/dice results (ru)
        └── en.yaml              # Coin/dice results (en)
```

## MECE Implementation Phases

### Phase 0: Foundation (Week 1)
**Assets Infrastructure Setup**
- [x] Create `assets/` directory structure
- [x] Move donation files: `handlers/donations/` → `assets/donations/`
- [x] Move schema: `schemas/donation/v1.0.json` → `assets/v1.0.json`
- [x] Update all donation files: `"$schema": "../v1.0.json"`
- [x] Update donation loader paths in `irene/core/donation_loader.py`
- [x] Update build scripts (`install-irene.sh`, Docker files) for assets inclusion
- [x] Test build system with new structure

### Phase 1: Unified Asset Infrastructure (Weeks 2-3)
**Pydantic Models and IntentAssetLoader**
- [x] **Pydantic Configuration Models** in `irene/config/models.py`:
  - [x] `ConversationHandlerConfig` (A1)
  - [x] `TrainScheduleHandlerConfig` (A2) 
  - [x] `TimerHandlerConfig` (A3)
  - [x] `RandomHandlerConfig` (A4)
  - [x] Update `IntentSystemConfig` to include handler configurations
- [x] **IntentAssetLoader Implementation** in `irene/core/intent_asset_loader.py`:
  - [x] Extend existing `DonationLoader` patterns for unified asset loading
  - [x] Implement `_load_donations()` (migrate existing donation loader logic)
  - [x] Implement `_load_templates()` (Category B: YAML/JSON/Markdown parsing)
  - [x] Implement `_load_prompts()` (Category A1: Text file loading)
  - [x] Implement `_load_localizations()` (Category C: YAML parsing)
  - [x] Unified error handling and validation following donation loader patterns
  - [x] Caching and fallback mechanisms
- [x] **Integration Points**:
  - [x] Update `EnhancedHandlerManager` to use `IntentAssetLoader` instead of separate `DonationLoader`
  - [x] Verify TOML configuration paths align with Pydantic models
  - [x] Handlers receive single asset loader instance via dependency injection

### Phase 2: Critical Externalization (Weeks 4-5) ✅ COMPLETED
**High-Priority Handlers (Essential Functionality)**
- [x] **A1: ConversationIntentHandler** - Extract LLM prompts to `prompts/conversation/` and responses to `templates/conversation/`
- [x] **C1: DateTimeIntentHandler** - Extract temporal data, periods, and templates to `localization/datetime/`
- [x] **C4: BaseIntentHandler** - Extract universal patterns to `localization/commands|domains/`

**✅ INTEGRATION STATUS:**
- [x] **A1**: ConversationIntentHandler - Fully integrated with external prompts and response templates
- [x] **C1**: DateTimeIntentHandler - Fully integrated with extended localization (periods, templates, special hours)
- [x] **C4**: BaseIntentHandler - Already completed in earlier phases

**⚠️ CRITICAL: All hardcoded fallbacks removed - handlers now raise fatal errors for missing assets**

### Phase 3: Medium-Priority Externalization (Weeks 6-7) ✅ COMPLETED
**User-Facing Response Templates**
- [x] **B1: GreetingsIntentHandler** - Extract to `templates/greetings/`
- [x] **B2: SystemIntentHandler** - Extract to `templates/system/`
- [x] **B4: VoiceSynthesisIntentHandler** - Extract to `templates/voice_synthesis/`
- [x] **C2: VoiceSynthesisIntentHandler** - Extract mappings to `localization/voice_synthesis/`
- [x] **C3: ProviderControlIntentHandler** - Extract mappings to `localization/components/`

**✅ INTEGRATION STATUS:**
- [x] **B1 & B2**: GreetingsIntentHandler & SystemIntentHandler - Fully integrated with template usage
- [x] **B4 & C2**: VoiceSynthesisIntentHandler - Fully integrated with templates and provider mappings  
- [x] **C3**: ProviderControlIntentHandler - Fully integrated with component mappings

### Phase 4: Low-Priority Externalization (Week 8) ✅ COMPLETED
**Simple Response Formatting**
- [x] **B3: SpeechRecognitionIntentHandler** - Extract to `templates/speech_recognition/`
- [x] **B5: TranslationIntentHandler** - Extract to `templates/translation/`
- [x] **B6: TextEnhancementIntentHandler** - Extract to `templates/text_enhancement/`
- [x] **B7: AudioPlaybackIntentHandler** - Extract to `templates/audio_playback/`
- [x] **C5: RandomIntentHandler** - Extract arrays to `templates/random/`

**✅ INTEGRATION STATUS:**
- [x] **B3**: SpeechRecognitionIntentHandler - Fully integrated with error message templates
- [x] **B5**: TranslationIntentHandler - Fully integrated with result formatting templates
- [x] **B6**: TextEnhancementIntentHandler - Fully integrated with result formatting templates
- [x] **B7**: AudioPlaybackIntentHandler - Fully integrated with status message templates
- [x] **C5**: RandomIntentHandler - Fully integrated with result arrays and formatting templates

### Phase 5: Configuration Integration (Week 9) ✅ COMPLETED
**Handler Updates and Unified Asset Injection**
- [x] Update Category A handlers to use proper config injection instead of hardcoded dicts
- [x] Update all handlers to use `IntentAssetLoader` instead of direct file access or hardcoded values
- [x] Replace donation loader injection with unified `IntentAssetLoader` injection
- [x] Implement configuration validation end-to-end
- [x] Ensure fallback mechanisms work for missing files across all asset types

## Success Criteria

### Infrastructure
- [ ] `assets/` directory fully established and integrated
- [ ] All donation files migrated with updated schema references
- [ ] Build system updated to handle assets folder
- [ ] **IntentAssetLoader** fully functional and replaces existing donation loader
- [ ] Unified asset loading for donations, templates, prompts, and localization data

### Configuration Models
- [x] All 4 Pydantic models implemented and integrated with `IntentSystemConfig`
- [x] TOML configuration paths verified and aligned
- [x] Configuration validation working end-to-end
- [x] Handlers receive configuration via proper dependency injection

### Externalization
- [ ] All LLM prompts externalized to `assets/prompts/`
- [ ] All response templates externalized to `assets/templates/` with i18n support
- [ ] All localization data externalized to `assets/localization/`
- [ ] All hardcoded configuration moved to TOML with validation

### Quality Assurance
- [x] Fallback mechanisms working for missing files across all asset types
- [ ] No functionality regression during migration
- [ ] Template/prompt editing doesn't require code changes
- [x] **IntentAssetLoader** provides unified API for all handler asset access
- [x] Validation and error handling consistent across donations, templates, prompts, and localization

## Dependencies

- **Requires**: Phase 3.5A (JSON donations) completion
- **Blocks**: All subsequent development (assets structure must be established first)
- **Related**: TODO #5 (Build system configuration)
- **Critical**: Phase 0 must complete before any template/prompt extraction

## Estimated Effort

- **Phase 0 (Foundation)**: 1 week (critical, blocking)
- **Phase 1 (Infrastructure)**: 2 weeks (Pydantic models + management systems)
- **Phase 2 (Critical)**: 2 weeks (3 high-priority handlers)
- **Phase 3 (Medium-Priority)**: 2 weeks (5 medium-priority handlers)
- **Phase 4 (Low-Priority)**: 1 week (5 low-priority handlers)
- **Phase 5 (Integration)**: 1 week (config integration + validation)

**Total**: 9 weeks (Phase 0 must complete before parallel development)

## Notes

This refactoring is **separate from and complementary to** the JSON donation system. JSON donations focus on NLU pattern recognition, while this TODO addresses response generation and configuration management.

**Critical Architecture Change**: The introduction of `assets/` as the central location for all external resources represents a fundamental shift in the project structure, centralizing all assets under a single manageable directory and enabling proper asset management systems.

**MECE Compliance**: This restructured approach ensures:
- **Mutually Exclusive**: Each handler falls into exactly one category (A, B, or C)
- **Collectively Exhaustive**: All 15 handlers are covered across the three categories
- **No Duplication**: Single `IntentAssetLoader` eliminates multiple manager classes
- **Clear Dependencies**: Phases have explicit prerequisites and deliverables

**Unified Asset Loading**: The `IntentAssetLoader` approach provides:
- **Consistency**: Reuses proven `DonationLoader` patterns for all asset types
- **Simplicity**: Single injection point for handlers instead of 3-4 separate managers
- **Maintainability**: Unified error handling, validation, and caching logic
- **Extensibility**: Easy to add new asset types following the same patterns