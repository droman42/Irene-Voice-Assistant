# TODO - Irene Voice Assistant

This document tracks architectural improvements and refactoring tasks for the Irene Voice Assistant project.

## 1. Hardcoded Provider Loading Pattern

**Status:** Open  
**Priority:** Critical  
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

## 2. Target Build System: Minimal Container and Service Builds

**Status:** Open  
**Priority:** Critical  
**Components:** Build system, Docker configuration, Service installation

### Problem

The project needs a sophisticated build system that creates minimal deployments based on TOML configuration, including only the required Irene modules and their dependencies. This is critical for both Docker container size optimization and lean service installations.

### Current State

- ✅ Project configuration through TOML files exists
- ❌ TOML configuration compliance needs full verification
- ❌ No selective module inclusion based on configuration
- ❌ Docker builds include all modules regardless of usage
- ❌ No service installation script with selective components

### Required Implementation

**Phase 1: TOML Configuration Verification**
- Audit existing TOML configuration system for completeness
- Verify all components, providers, and dependencies are properly declared
- Ensure configuration accurately reflects module requirements
- Validate dependency mapping between components and providers

**Phase 2: Selective Build System**
- Create Python script for analyzing TOML configuration
- Implement dependency resolution for selected components
- Build module inclusion/exclusion logic based on configuration
- Generate minimal file trees for target deployments

**Phase 3: Docker Build Integration**
```python
# Example configuration-driven inclusion
[components]
enabled = ["audio", "llm", "asr"]  # TTS excluded
providers.audio = ["sounddevice", "console"]
providers.llm = ["openai"]
providers.asr = ["whisper"]

# Result: TTS component and all TTS providers excluded from build
```

**Phase 4: Service Installation Script**
- Bash script for minimal service installations
- Selective component installation based on configuration
- Dependency management for lean deployments
- Runtime configuration validation

**Phase 5: Binary Dependency Management**
- Install or build binary dependencies (binary libraries) alongside Python dependencies
- Platform-specific binary resolution (Linux, macOS, Windows)
- Native library compilation and linking for audio/ML components
- System package management integration (apt, yum, brew, etc.)
- Cross-compilation support for different architectures

### Technical Architecture

**Build Process Flow**
```
TOML Config → Dependency Analyzer → Module Selector → Build Generator
     ↓              ↓                    ↓              ↓
Configuration   Resolve deps      Include/exclude   Docker/Service
validation      recursively       modules           build artifacts
```

**Key Components**
1. **Configuration Parser**: Parse and validate TOML build specifications
2. **Dependency Resolver**: Map component dependencies recursively
3. **Module Selector**: Determine which files/directories to include
4. **Build Generator**: Create Docker files and installation scripts
5. **Validation Engine**: Verify build completeness and runtime requirements

### Implementation Examples

**Minimal Audio-Only Build**
```toml
[build.target]
name = "irene-audio-only"
components = ["audio"]
providers.audio = ["sounddevice"]
workflows = ["continuous_listening"]

# Results in container with only:
# - Audio component and sounddevice provider
# - Core engine and workflow manager
# - No TTS, LLM, ASR, or NLU components
```

**Complete Assistant Build**
```toml
[build.target]
name = "irene-full-assistant"
components = ["audio", "tts", "llm", "asr", "voice_trigger"]
providers.audio = ["sounddevice", "console"]
providers.tts = ["elevenlabs", "console"]
providers.llm = ["openai", "anthropic"]
providers.asr = ["whisper"]
providers.voice_trigger = ["microwakeword"]
workflows = ["voice_assistant"]
```

### Build Outputs

**Docker Build**
- Minimal Dockerfile with only required dependencies
- Binary dependency compilation and installation in container layers
- Optimized layer structure for caching (separate layers for binary deps)
- Runtime environment with selected components only
- Significantly reduced container size
- Multi-stage builds for binary compilation vs runtime

**Service Installation**
- Bash script for targeted service deployment
- System dependency installation (only required packages)
- Binary library compilation and linking
- Platform-specific native dependency resolution
- Configuration template generation
- Service file creation with minimal footprint

### Benefits

- **Container Optimization**: Dramatically reduced Docker image sizes
- **Security**: Smaller attack surface with fewer installed components
- **Performance**: Faster startup times with fewer modules to load
- **Deployment Flexibility**: Multiple specialized builds for different use cases
- **Resource Efficiency**: Lower memory and storage requirements
- **Maintenance**: Easier updates for targeted deployments

### Technical Challenges

1. **Dependency Resolution**: Complex inter-module dependencies need accurate mapping
2. **Binary Dependency Management**: Cross-platform compilation, linking, and distribution of native libraries
3. **Runtime Validation**: Ensure minimal builds are functionally complete
4. **Configuration Complexity**: TOML specifications must be comprehensive yet intuitive
5. **Build Automation**: Integration with CI/CD pipelines
6. **Platform Compatibility**: Handle different architectures and operating systems
7. **Testing**: Validate all possible component combinations across platforms

### Existing Infrastructure to Leverage

- Current TOML configuration system
- Existing dependency checking utilities in `utils/loader.py`
- Plugin registry patterns for dynamic loading
- Component manager architecture
- Docker configuration foundation

### Impact

- **Breaking Change**: Build process fundamentally changes
- **Deployment Revolution**: Multiple specialized deployment options
- **Development Workflow**: New build validation requirements
- **Configuration Management**: Enhanced TOML specification needed
- **CI/CD Updates**: Build pipeline modifications required

### Related Files

- `pyproject.toml` (current configuration)
- `Dockerfile` (current Docker build)
- `irene/utils/loader.py` (dependency utilities)
- `irene/core/components.py` (component management)
- `irene/plugins/registry.py` (dynamic loading patterns)
- Build automation scripts (to be created)

## 3. AudioComponent Command Handling Architecture Issue

**Status:** Open  
**Priority:** High  
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

## 4. Disconnected NLU and Intent Handler Systems

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

## 5. NLU Architecture Revision: Keyword-First with Intent Donation

**Status:** Open  
**Priority:** High  
**Components:** NLU providers (`irene/providers/nlu/`), Intent system (`irene/intents/`), Text processing (`irene/providers/text_processing/`)

### Problem

The current NLU architecture should be simplified to prioritize lightweight keyword matching as the mandatory default approach, with additional NLU plugins (including spacy) as configurable fallbacks. Intent handlers should donate keywords and the system should leverage existing text processing utilities for optimal performance.

### Current Architecture Issues

1. **Complex Default**: Current system may over-rely on heavy NLU providers like spacy for simple keyword-based intents
2. **No Intent Keyword Donation**: Intents cannot contribute their own keywords for identification
3. **Inflexible Plugin Chain**: No clear extensible hierarchy of NLU approaches from simple to complex
4. **Underutilized Text Processing**: Existing text processing providers not integrated with NLU pipeline

### Proposed Solution: Extensible Keyword-First NLU with Intent Donation

**Phase 1: Intent Keyword Donation System**
- Add `get_keywords()` method to `IntentHandler` base class
- Intent handlers donate lists of keywords and word forms that identify them as workflow targets
- Mandatory keyword matcher uses donated keywords for fast initial recognition
- Integration with existing text processing providers

**Phase 2: Russian Morphological Word Forms Generation**
```python
# Automatic Russian word forms generation utility
class RussianMorphology:
    """Utility for generating Russian word forms automatically"""
    
    def generate_word_forms(self, base_word: str) -> List[str]:
        """Generate morphological forms based on Russian language rules"""
        # Implement Russian declension/conjugation rules
        # Returns: [nominative, genitive, dative, accusative, instrumental, prepositional]
        
    def get_all_forms(self, keywords: List[str]) -> Dict[str, List[str]]:
        """Generate all forms for a list of base keywords"""
        return {word: self.generate_word_forms(word) for word in keywords}

# Intent handlers donate base keywords + auto-generated forms
class TimerIntentHandler(IntentHandler):
    def get_keywords(self) -> Dict[str, List[str]]:
        base_keywords = ["таймер", "будильник", "время"]
        russian_morph = RussianMorphology()
        return {
            "base_keywords": base_keywords,
            "word_forms": russian_morph.get_all_forms(base_keywords),
            "action_keywords": ["поставь", "установи", "засеки", "отмени"]
        }
```

**Phase 3: Extensible NLU Plugin Architecture**
```python
# NLU Orchestrator with extensible plugin system
class NLUOrchestrator:
    def __init__(self):
        self.plugins = [
            KeywordMatcherNLUPlugin(),      # Mandatory: fast keyword matching
            RuleBasedNLUPlugin(),          # Optional: regex patterns  
            UnifiedProcessorNLUPlugin(),   # Optional: existing text processing
            SpaCySemanticNLUPlugin(),      # Optional: semantic understanding
            # ... additional plugins can be added
        ]
        
    def configure_plugins(self, config: Dict[str, Any]):
        """Configure which plugins are enabled (keyword matcher always enabled)"""
        enabled_plugins = config.get('enabled_plugins', ['keyword_matcher'])
        # Keyword matcher is always first and mandatory
        if 'keyword_matcher' not in enabled_plugins:
            enabled_plugins.insert(0, 'keyword_matcher')
```

**Phase 4: Text Processing Integration**
- Leverage existing `irene/providers/text_processing/` utilities
- Integrate `UnifiedProcessor` and `NumberProcessor` into NLU pipeline
- Use text normalization and preprocessing from existing providers

```python
# Integration with existing text processing providers
class KeywordMatcherNLUPlugin:
    def __init__(self):
        from irene.providers.text_processing import UnifiedProcessor, NumberProcessor
        self.text_processor = UnifiedProcessor()
        self.number_processor = NumberProcessor()
        
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        # Use existing text processing utilities
        normalized_text = await self.text_processor.process(text)
        processed_numbers = await self.number_processor.process(normalized_text)
        
        # Match against donated keywords and word forms
        return await self._match_keywords(processed_numbers, context)
```

**Phase 5: Intelligent Cascading**
- Keyword matcher handles majority of common cases (mandatory first pass)
- Additional plugins process unmatched utterances in configured order
- Confidence scoring determines when to escalate through plugin chain
- Configurable confidence thresholds for each plugin

### Text Processing Provider Analysis

**Existing Infrastructure to Leverage:**
- `UnifiedProcessor`: Text normalization, cleaning, and preprocessing
- `NumberProcessor`: Number extraction and normalization
- Text processing utilities already handle Russian language specifics

**Integration Points:**
```python
# NLU pipeline leverages existing text processing
async def process_text_for_nlu(self, text: str) -> str:
    # Use existing unified processor for text normalization
    normalized = await self.unified_processor.process(text)
    
    # Use existing number processor for numeric entities
    with_numbers = await self.number_processor.process(normalized)
    
    return with_numbers
```

### Benefits

- **Performance**: Fast keyword matching for common intents (mandatory first pass)
- **Simplicity**: Intent handlers define their own identification keywords
- **Scalability**: Lightweight approach scales better than semantic models
- **Extensibility**: Plugin architecture allows additional NLU approaches
- **Russian Language Support**: Automatic morphological word form generation
- **Existing Infrastructure**: Leverages current text processing providers
- **Self-Describing Intents**: Intent handlers become self-contained with their own keywords

### Implementation Strategy

1. **Keyword Collection**: Gather donated keywords from all registered intent handlers
2. **Morphological Expansion**: Generate Russian word forms automatically
3. **Text Processing Integration**: Use existing processors for normalization
4. **Fast Matching**: Implement efficient keyword-based intent identification
5. **Plugin Chain**: Route unmatched utterances through configured NLU plugins
6. **Confidence Tuning**: Adjust thresholds for plugin escalation

### Russian Morphology Utility Requirements

- **Declension Rules**: Implement Russian noun declension patterns
- **Conjugation Rules**: Handle Russian verb conjugation
- **Gender/Number**: Account for grammatical gender and number variations
- **Case System**: Generate all six Russian cases automatically
- **Integration**: Work seamlessly with existing text processing pipeline

### Configuration Example

```toml
[nlu]
# Extensible plugin configuration
enabled_plugins = [
    "keyword_matcher",    # Mandatory - always enabled
    "rule_based",         # Optional - regex patterns
    "unified_processor",  # Optional - existing text processing
    "spacy_semantic"      # Optional - semantic understanding
]

[nlu.keyword_matcher]
# Mandatory plugin configuration
auto_generate_word_forms = true
russian_morphology = true
confidence_threshold = 0.8

[nlu.spacy_semantic]
# Optional plugin configuration  
model_name = "ru_core_news_sm"
confidence_threshold = 0.7
fallback_only = true
```

### Impact

- **Performance Improvement**: Faster intent recognition for common cases
- **Reduced Complexity**: Simpler mandatory default NLU path
- **Better Intent Encapsulation**: Handlers own their identification logic
- **Resource Efficiency**: Less reliance on heavy semantic models
- **Russian Language Enhancement**: Native morphological support
- **Existing Infrastructure Reuse**: Leverages current text processing providers

### Related Files

- `irene/intents/handlers/base.py` (intent handler base class)
- `irene/providers/nlu/rule_based.py` (keyword matching implementation)
- `irene/providers/nlu/spacy_provider.py` (semantic fallback)
- `irene/providers/text_processing/unified_processor.py` (existing text processing)
- `irene/providers/text_processing/number_processor.py` (number processing)
- `irene/intents/recognizer.py` (NLU coordination and plugin chain)
- `irene/intents/registry.py` (intent handler registration)
- Russian morphology utility (to be created)

## 6. Named Client Support for Contextual Command Processing

**Status:** Open  
**Priority:** Medium  
**Components:** Workflow system, RequestContext, Voice trigger, Intent system

### Problem

The current system lacks support for named clients (device identification) that would allow the same command to behave differently based on the source device. This is essential for multi-device deployments where business logic needs to interpret commands contextually based on the originating client.

### Current Architecture Limitations

**Generic Request Context:**
```python
class RequestContext:
    def __init__(self,
                 source: str = "unknown",        # Generic source name
                 session_id: str = "default",    # Session ID
                 # No client/device identification
```

**Missing Components:**
- No client identifier propagation from VoiceTrigger
- No business logic interpretation of client identifiers
- No contextual command routing based on source device
- No standardized client naming scheme

### Proposed Solution: Named Client Architecture

**Phase 1: Client Identification Infrastructure**
- Extend `RequestContext` with client identifier support
- Add client ID propagation from voice trigger to intent execution
- Create client registry and metadata management
- Implement client-aware intent routing

**Phase 2: VoiceTrigger Integration**
```python
# VoiceTrigger passes client identifier
class WakeWordResult:
    def __init__(self, 
                 detected: bool,
                 confidence: float,
                 word: str,
                 client_id: Optional[str] = None):  # NEW: Client identifier
```

**Phase 3: Intent Context Awareness**
```python
# Enhanced RequestContext
class RequestContext:
    def __init__(self,
                 source: str = "unknown",
                 session_id: str = "default", 
                 client_id: Optional[str] = None,     # NEW: Named client
                 client_metadata: Optional[Dict] = None,  # NEW: Client data
                 wants_audio: bool = False,
                 skip_wake_word: bool = False,
                 metadata: Optional[Dict[str, Any]] = None):
```

**Phase 4: Business Logic Integration**
```python
# Intent handlers become client-aware
class IntentHandler(ABC):
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        # Access client information for contextual processing
        client_id = context.request_context.client_id
        client_metadata = context.request_context.client_metadata
        
        # Same command, different behavior based on client
        if intent.action == "close_curtains":
            return await self._handle_curtains_for_client(client_id)
```

### Technical Implementation

**Client Registry System**
```python
class ClientRegistry:
    """Registry for managing named clients and their metadata"""
    
    def register_client(self, client_id: str, metadata: Dict[str, Any]):
        """Register a named client with metadata"""
        
    def get_client_metadata(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a named client"""
        
    def update_client_status(self, client_id: str, status: Dict[str, Any]):
        """Update client status information"""
```

**Workflow Integration**
- Voice trigger components pass client identifiers
- Workflows propagate client context through pipeline
- Intent orchestrator provides client-aware routing
- Intent handlers receive client information for business logic

### Use Cases Enabled

**Multi-Device Scenarios:**
- Same voice command behaves differently in different rooms
- Device-specific capabilities and configurations
- Contextual responses based on client location
- Client-specific user preferences and settings

**Example: Contextual Commands**
```python
# Command: "Turn on the lights"
# kitchen_device -> Controls kitchen lights
# bedroom_device -> Controls bedroom lights  
# living_room_device -> Controls living room lights
```

### Benefits

- **Contextual Intelligence**: Same commands work differently based on source
- **Multi-Device Support**: Natural scaling to multiple voice endpoints
- **Business Logic Flexibility**: Intent handlers can implement client-specific behavior
- **Future Extensibility**: Foundation for smart home, IoT, and enterprise scenarios
- **Backwards Compatibility**: Optional client ID doesn't break existing workflows

### Configuration Example

```toml
[clients]
# Client registry configuration
kitchen = { type = "room", location = "kitchen", capabilities = ["lighting", "music"] }
bedroom = { type = "room", location = "bedroom", capabilities = ["lighting", "climate"] }
office = { type = "workspace", location = "office", capabilities = ["lighting", "presentation"] }

[voice_trigger]
# Client ID can be configured per voice trigger instance
client_id = "kitchen"  # This device represents the kitchen

[intents.handlers]
# Intent handlers can access client information
contextual_routing = true
```

### Impact

- **Workflow Changes**: RequestContext and workflow pipeline modifications
- **Intent System**: Enhanced context propagation and handler capabilities
- **Voice Trigger**: Client ID integration in wake word detection
- **Configuration**: Client registry and mapping configuration
- **Backward Compatibility**: Existing implementations continue to work with null client_id

### Related Files

- `irene/workflows/base.py` (RequestContext enhancement)
- `irene/intents/models.py` (Intent and context models)
- `irene/intents/orchestrator.py` (client-aware routing)
- `irene/intents/handlers/base.py` (intent handler base class)
- `irene/providers/voice_trigger/base.py` (voice trigger client ID support)
- `irene/core/workflow_manager.py` (workflow context management)

## 7. Review New Providers for Asset Management Compliance

**Status:** Open  
**Priority:** Medium  
**Components:** All provider modules

### Problem

New providers need to be reviewed for compliance with the project's asset management guidelines to ensure consistent resource handling, model storage, and configuration management across the codebase.

### Required Review Areas

1. **Model Storage**: Verify providers follow the centralized model storage pattern defined via environment variables
2. **Cache Management**: Ensure providers use the unified cache folder structure
3. **Resource Cleanup**: Check for proper cleanup of temporary files and resources
4. **Configuration Patterns**: Validate adherence to standard configuration schemas
5. **Documentation**: Ensure provider documentation includes asset management details

### Asset Management Guidelines

Based on project memories:
- All AI models and cache folders should be placed under a single root directory defined via environment variables in .env file
- This allows for consistent configuration when mounting from Docker images
- Providers should not create their own isolated storage patterns

### Impact
- Consistent resource management across all providers
- Better Docker deployment support
- Reduced storage fragmentation
- Improved maintainability and debugging

### Related Files
- `docs/ASSET_MANAGEMENT.md` (asset management guidelines)
- All provider modules in `irene/providers/`
- `.env` configuration files
- Docker configuration files

## 8. MicroWakeWord Hugging Face Integration

**Status:** Open  
**Priority:** Medium  
**Component:** `irene/providers/voice_trigger/microwakeword.py`

### Problem

The MicroWakeWordProvider has been integrated with asset management but still needs Hugging Face model download support for seamless model distribution and updates.

### Current State

- ✅ Asset management integration completed
- ✅ Local model support with `url: "local"` configuration
- ✅ Legacy model path backward compatibility
- ❌ Hugging Face model download not implemented

### Required Implementation

1. **Hugging Face Integration**: Add support for downloading models from Hugging Face Hub
2. **Model Registry Updates**: Update `microwakeword` section in model registry with actual Hugging Face model URLs
3. **Download Validation**: Implement model validation and checksum verification
4. **Documentation**: Update configuration examples with Hugging Face model IDs

### Technical Details

**Asset Manager Changes:**
- Add Hugging Face URL pattern recognition in `_download_model_impl`
- Support `huggingface://organization/model-name` URL format
- Integrate with `huggingface_hub` library for downloads

**Configuration Updates:**
```yaml
microwakeword:
  irene_model:
    url: "huggingface://irene-ai/microwakeword-irene-v1"
    size: "5MB"
    format: "tflite"
    description: "Official microWakeWord model for 'irene'"
```

### Dependencies

- `huggingface_hub` library for model downloads
- Model validation utilities
- Checksum verification support

### Benefits

- Seamless model distribution and updates
- Centralized model hosting on Hugging Face
- Version control for model releases
- Community model sharing capabilities

### Related Files

- `irene/providers/voice_trigger/microwakeword.py` (provider implementation)
- `irene/core/assets.py` (asset manager)
- `irene/config/models.py` (model registry)
- `docs/ASSET_MANAGEMENT.md` (asset management documentation)

## 9. Binary WebSocket Optimization for External Devices

**Status:** Open  
**Priority:** Low  
**Components:** WebSocket endpoints, ESP32 integration, Audio streaming

### Problem

While Irene already supports WebSocket-initiated ASR workflows for external devices like ESP32 through base64-encoded audio chunks, the current implementation could be optimized for binary streaming to reduce latency and improve performance for continuous audio streams from external hardware.

### Current State

- ✅ WebSocket ASR support via `/ws` and `/asr/stream` endpoints
- ✅ ESP32 can stream audio and receive transcriptions
- ✅ Voice trigger bypass with `ContinuousListeningWorkflow`
- ❌ Base64 encoding adds unnecessary overhead for binary audio data
- ❌ No ESP32-specific optimized endpoints
- ❌ No binary WebSocket support for raw PCM streaming

### Proposed Enhancement

**Phase 1: Binary WebSocket Endpoint**
- Add dedicated binary WebSocket endpoint for external devices
- Support raw PCM audio data (16kHz, 16-bit, mono)
- Eliminate base64 encoding/decoding overhead
- Optimize for continuous audio streaming

**Phase 2: ESP32-Specific Protocol**
```javascript
// Enhanced binary streaming protocol
WebSocket: /ws/audio/binary
- Audio session initiation and configuration
- Raw PCM binary frames
- Stream control messages (start/stop/pause)
- Audio format negotiation
```

**Phase 3: Session Management**
- Audio session lifecycle management
- Quality monitoring and adaptive streaming
- Connection recovery and reconnection logic
- Multi-device session support

### Technical Implementation

**Binary WebSocket Endpoint**
```python
@app.websocket("/ws/audio/binary")
async def binary_audio_stream(websocket: WebSocket):
    """Optimized binary audio streaming for ESP32/external devices"""
    await websocket.accept()
    
    # Session setup
    config = await websocket.receive_json()  # Initial config
    
    try:
        while True:
            # Receive raw PCM binary data
            audio_data = await websocket.receive_bytes()
            
            # Direct ASR processing (no base64 overhead)
            text = await asr.transcribe_audio(audio_data)
            
            # Send binary or JSON response
            if text.strip():
                await websocket.send_json({
                    "type": "transcription",
                    "text": text,
                    "timestamp": time.time()
                })
```

**ESP32 Integration Benefits**
- **Reduced Latency**: Direct binary streaming vs base64 encoding
- **Lower CPU Usage**: No encoding/decoding overhead on ESP32
- **Better Performance**: Optimized for continuous audio streams
- **Memory Efficiency**: Smaller memory footprint for audio buffers

### Current ESP32 Compatibility

The existing ESP32 firmware already supports:
- WebSocket connectivity with TLS
- Raw PCM audio streaming
- Audio session management
- Binary data transmission

### Benefits

- **Performance**: Significantly reduced latency for real-time audio
- **Efficiency**: Lower CPU and memory usage on both ESP32 and server
- **Scalability**: Better support for multiple simultaneous ESP32 devices
- **Battery Life**: Reduced processing overhead improves ESP32 battery efficiency
- **Quality**: Higher audio quality with direct binary transmission

### Impact

- **Low Breaking Change**: Additive enhancement to existing WebSocket support
- **Backward Compatibility**: Existing base64 endpoints remain unchanged
- **Optional Enhancement**: ESP32 devices can choose optimal endpoint
- **Infrastructure**: Minimal changes to existing workflow system

### Related Files

- `irene/runners/webapi_runner.py` (WebSocket endpoint definitions)
- `irene/components/asr_component.py` (ASR WebSocket endpoints)
- `irene/inputs/web.py` (WebSocket audio handling)
- `ESP32/firmware/common/src/network/network_manager.cpp` (ESP32 audio streaming)
- `ESP32/firmware/common/src/audio/audio_manager.cpp` (ESP32 audio processing)

## 14. ESP32 INT8 Wake Word Model Migration

**Status:** Completed  
**Priority:** High  
**Components:** ESP32 firmware, wake word training pipeline

### Problem

ESP32 wake word detection was using FP32 models with higher memory usage and slower inference. INT8 quantization provides better performance and resource efficiency for microcontroller deployment.

### Solution Implemented

Completed full INT8 migration with the following improvements:

#### C1) Integration Guide Updates
- ✅ Updated `wake_word_training/scripts/converters/to_esp32.py` 
- ✅ Added MFCC preprocessing documentation in generated integration guide
- ✅ Corrected INT8 quantization examples (input->data.int8, dequantization formulas)
- ✅ Removed FP32 assumptions from template code

#### C2) Device Sanity Checklist
- ✅ Added `perform_sanity_checks()` method to `wake_word_detector.cpp`
- ✅ Logs input/output tensor types, scales, and zero points at boot
- ✅ Reports tensor dimensions and arena memory utilization
- ✅ Performs zero-input stability test to detect model bias issues
- ✅ Validates tensor shapes match MFCC frontend expectations

#### C3) Validation Requirements Documentation
- ✅ Updated `ESP32/docs/irene_firmware.md` with INT8 validation protocol
- ✅ Defined threshold re-tuning requirements for quantized models
- ✅ Specified validation metrics: ≥95% recall, ≤2 false accepts/hour, ≤140ms latency
- ✅ Added validation log format and acceptance criteria
- ✅ Documented expected performance delta from FP32 baseline

### Benefits

- **Memory Efficiency**: Reduced PSRAM usage from 160KB to 80KB tensor arena
- **Performance**: 15-25ms inference time vs 30-40ms for FP32 models
- **Debugging**: Comprehensive sanity checks for faster troubleshooting
- **Validation**: Systematic testing protocol ensures deployment quality
- **Documentation**: Clear integration guide with INT8-specific examples

### Impact

- **Low Breaking Change**: Existing model training pipeline preserved
- **Hardware Optimization**: Better utilization of ESP32-S3 resources
- **Quality Assurance**: Robust validation prevents deployment issues
- **Developer Experience**: Improved debugging and integration documentation

### Related Files

- `wake_word_training/scripts/converters/to_esp32.py` (INT8 integration guide)
- `ESP32/firmware/common/src/audio/wake_word_detector.cpp` (sanity checks)
- `ESP32/firmware/common/include/audio/wake_word_detector.hpp` (method declarations)
- `ESP32/docs/irene_firmware.md` (validation requirements)
- `wake_word_training/scripts/tensorflow_trainer.py` (INT8 model training) 