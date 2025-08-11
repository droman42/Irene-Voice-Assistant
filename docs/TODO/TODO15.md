# TODO #15: Handler Response Templates and Configuration Refactoring

## Overview

This TODO covers the refactoring of hardcoded response templates, LLM prompts, and configuration values found during Phase 3.5 pattern analysis. These patterns are **NOT** part of the JSON donation system (which focuses on NLU recognition patterns) but require separate refactoring approaches.

## Scope: ~150 Non-NLU Hardcoded Patterns

### Phase 3.5B Findings - Patterns NOT for JSON Donations:
- **LLM System Prompts**: Hardcoded conversation prompts and templates
- **Response Templates**: Greeting messages, error responses, status text
- **Configuration Values**: Timeouts, models, version info, default settings
- **Localization Data**: Language-specific formatting arrays for output generation

## Handler-Specific Refactoring Tasks

### 1. ConversationIntentHandler - LLM Prompt Externalization

**Current Hardcoded Prompts (Lines 68-70):**
```python
self.config = {
    "chat_system_prompt": "Ты - Ирина, голосовой помощник, помогающий человеку. Давай ответы кратко и по существу.",
    "reference_system_prompt": "Ты помощник для получения точных фактов. Отвечай максимально кратко и точно на русском языке.",
    "reference_prompt_template": "Вопрос: {0}. Ответь на русском языке максимально кратко - только запрошенные данные.",
    # ... other config
}
```

**TODO Tasks:**
- [ ] Create `prompts/conversation/` directory structure
- [ ] Extract prompts to external files:
  - `prompts/conversation/chat_system.txt`
  - `prompts/conversation/reference_system.txt` 
  - `prompts/conversation/reference_template.txt`
- [ ] Implement prompt loading system with fallback to defaults
- [ ] Support multiple languages: `prompts/conversation/ru/`, `prompts/conversation/en/`
- [ ] Add prompt validation and error handling
- [ ] Update configuration schema to reference prompt files

**Priority**: High (LLM integration critical)

### 2. GreetingsIntentHandler - Response Template System

**Current Hardcoded Templates (Lines 33-102):**
```python
self.greetings_ru = [10 hardcoded responses]
self.greetings_en = [10 hardcoded responses]  
self.farewells_ru = [10 hardcoded responses]
self.farewells_en = [10 hardcoded responses]
self.welcome_messages_ru = [5 hardcoded responses]
self.welcome_messages_en = [5 hardcoded responses]
```

**TODO Tasks:**
- [ ] Create `templates/greetings/` directory structure
- [ ] Extract templates to YAML/JSON files:
  - `templates/greetings/ru/greetings.yaml`
  - `templates/greetings/ru/farewells.yaml`
  - `templates/greetings/ru/welcomes.yaml`
  - `templates/greetings/en/greetings.yaml`
  - `templates/greetings/en/farewells.yaml`
  - `templates/greetings/en/welcomes.yaml`
- [ ] Implement template loading system with random selection
- [ ] Support template variables and formatting
- [ ] Add fallback to hardcoded defaults if files missing

**Priority**: Medium (user-facing but not critical)

### 3. SystemIntentHandler - Multi-line Response Templates

**Current Hardcoded Templates (Lines 122-265):**
```python
help_text = """I'm Irene, your voice assistant. Here's what I can help you with:
🗣️ **Conversation**: Just talk to me naturally
⏰ **Timers**: "Set timer for 5 minutes"
# ... ~10 lines per language
"""
```

**TODO Tasks:**
- [ ] Create `templates/system/` directory structure  
- [ ] Extract large multi-line templates to markdown files:
  - `templates/system/ru/help.md`
  - `templates/system/ru/status.md`
  - `templates/system/ru/version.md`
  - `templates/system/en/help.md`
  - `templates/system/en/status.md`
  - `templates/system/en/version.md`
- [ ] Implement markdown template rendering with variable substitution
- [ ] Support dynamic content injection (uptime, version, etc.)

**Priority**: Medium (informational responses)

### 4. DateTimeIntentHandler - Localization System

**Current Hardcoded Arrays (Lines 33-72):**
```python
# Russian temporal formatting (for OUTPUT, not NLU input)
self.weekdays_ru = ["понедельник", "вторник", "среда", ...]
self.months_ru = ["января", "февраля", "марта", ...]  
self.days_ru = ["первое", "второе", "третье", ...]
self.hours_ru = ["двенадцать", "час", "два", ...]

# English temporal formatting
self.weekdays_en = ["Monday", "Tuesday", "Wednesday", ...]
self.months_en = ["January", "February", "March", ...]
```

**TODO Tasks:**
- [ ] Create `localization/datetime/` directory structure
- [ ] Extract temporal formatting to locale files:
  - `localization/datetime/ru.yaml` (weekdays, months, ordinals, time periods)
  - `localization/datetime/en.yaml` (weekdays, months, ordinals, time periods)
- [ ] Implement locale-aware datetime formatting system
- [ ] Support ICU/CLDR standard formatting where possible
- [ ] **IMPORTANT**: Keep NLU recognition patterns in JSON donations (separate concern)

**Priority**: High (essential functionality, complex separation needed)

### 5. TimerIntentHandler - Configuration Constants

**Current Hardcoded Config (Lines 312-317, 322-326):**
```python
unit_multipliers = {
    'seconds': 1,
    'minutes': 60,
    'hours': 3600,
    'days': 86400
}
# Time limits: 1 second minimum, 24 hours maximum
```

**TODO Tasks:**
- [ ] Move unit multipliers to TOML configuration
- [ ] Move time limits to TOML configuration  
- [ ] Extract error messages to template system
- [ ] Support configurable timer constraints per deployment

**Priority**: Low (internal constants, low user impact)

### 6. TrainScheduleIntentHandler - Configuration Defaults

**Current Hardcoded Config (Lines 47-49):**
```python
self.default_from_station = self.config.get("from_station", "s9600681")  # Moscow
self.default_to_station = self.config.get("to_station", "s2000002")     
self.max_results = self.config.get("max_results", 3)
```

**TODO Tasks:**
- [ ] Move all defaults to TOML configuration
- [ ] Extract response templates to template system
- [ ] Support multiple default station configurations

**Priority**: Low (optional functionality)

## Implementation Architecture

### Template System Design

```python
class TemplateManager:
    """Manages response templates with i18n support"""
    
    def __init__(self, template_dir: str):
        self.template_dir = Path(template_dir)
        self.templates = {}
        self.load_templates()
    
    def get_template(self, handler: str, template_name: str, language: str = "ru") -> str:
        """Get template with fallback to default language"""
        # Implementation with fallback logic
        
    def render_template(self, template: str, **kwargs) -> str:
        """Render template with variable substitution"""
        # Support Jinja2-style templates or simple format strings
```

### Prompt System Design

```python
class PromptManager:
    """Manages LLM prompts with external file support"""
    
    def __init__(self, prompt_dir: str):
        self.prompt_dir = Path(prompt_dir)
        self.prompts = {}
        self.load_prompts()
    
    def get_system_prompt(self, handler: str, prompt_type: str = "default") -> str:
        """Get system prompt with fallback to hardcoded default"""
        
    def format_prompt(self, prompt: str, **kwargs) -> str:
        """Format prompt with dynamic variables"""
```

### Localization System Design

```python
class LocalizationManager:
    """Manages locale-specific formatting data"""
    
    def __init__(self, locale_dir: str):
        self.locale_dir = Path(locale_dir)
        self.locales = {}
        self.load_locales()
    
    def get_locale_data(self, domain: str, language: str = "ru") -> Dict[str, Any]:
        """Get locale-specific data (weekdays, months, etc.)"""
        
    def format_datetime(self, dt: datetime, format_type: str, language: str = "ru") -> str:
        """Format datetime using locale-specific rules"""
```

## Directory Structure

```
irene/
├── templates/
│   ├── greetings/
│   │   ├── ru/
│   │   │   ├── greetings.yaml
│   │   │   ├── farewells.yaml
│   │   │   └── welcomes.yaml
│   │   └── en/
│   │       ├── greetings.yaml
│   │       ├── farewells.yaml
│   │       └── welcomes.yaml
│   └── system/
│       ├── ru/
│       │   ├── help.md
│       │   ├── status.md
│       │   └── version.md
│       └── en/
│           ├── help.md
│           ├── status.md
│           └── version.md
├── prompts/
│   └── conversation/
│       ├── ru/
│       │   ├── chat_system.txt
│       │   ├── reference_system.txt
│       │   └── reference_template.txt
│       └── en/
│           ├── chat_system.txt
│           ├── reference_system.txt
│           └── reference_template.txt
└── localization/
    ├── datetime/
    │   ├── ru.yaml
    │   └── en.yaml
    └── units/
        ├── ru.yaml
        └── en.yaml
```

## Migration Strategy

### Phase 1: Create Infrastructure (TODO #15A)
- [ ] Implement TemplateManager, PromptManager, LocalizationManager
- [ ] Create directory structures
- [ ] Add loading and fallback logic

### Phase 2: Extract Critical Templates (TODO #15B)
- [ ] ConversationIntentHandler LLM prompts (highest priority)
- [ ] DateTimeIntentHandler localization data (essential functionality)

### Phase 3: Extract Remaining Templates (TODO #15C)  
- [ ] GreetingsIntentHandler response templates
- [ ] SystemIntentHandler multi-line responses
- [ ] Error messages and status responses

### Phase 4: Configuration Cleanup (TODO #15D)
- [ ] TimerIntentHandler configuration constants
- [ ] TrainScheduleIntentHandler defaults
- [ ] Version information centralization

## Dependencies

- **Requires**: Phase 3.5A (JSON donations) completion
- **Blocks**: None (parallel development possible)
- **Related**: TODO #5 (Build system configuration)

## Success Criteria

- [ ] All LLM prompts externalized to files
- [ ] All response templates support i18n
- [ ] All hardcoded configuration moved to TOML
- [ ] Fallback mechanisms working for missing files
- [ ] No functionality regression during migration
- [ ] Template/prompt editing doesn't require code changes

## Estimated Effort

- **Phase 1 (Infrastructure)**: 1-2 weeks
- **Phase 2 (Critical)**: 1 week  
- **Phase 3 (Remaining)**: 1-2 weeks
- **Phase 4 (Config)**: 1 week

**Total**: 4-6 weeks (parallel with other development)

## Notes

This refactoring is **separate from and complementary to** the JSON donation system. JSON donations focus on NLU pattern recognition, while this TODO addresses response generation and configuration management.
