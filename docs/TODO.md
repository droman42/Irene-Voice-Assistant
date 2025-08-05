# TODO - Irene Voice Assistant

This document tracks architectural improvements and refactoring tasks for the Irene Voice Assistant project.

## 1. Review New Providers for Asset Management Compliance

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

## 2. AudioComponent Command Handling Architecture Issue

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

## 3. Hardcoded Provider Loading Pattern

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

## 4. Disconnected NLU and Intent Handler Systems

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

## 5. NLU Architecture Revision: Keyword-First with Intent Donation

**Status:** Open  
**Priority:** Medium  
**Components:** NLU providers (`irene/providers/nlu/`) and Intent system (`irene/intents/`)

### Problem

The current NLU architecture should be simplified to prioritize lightweight keyword matching as the default approach, with spacy as a fallback for more complex semantic understanding. Intent handlers should be able to donate keywords to help identify themselves as targets for workflow execution.

### Current Architecture Issues

1. **Complex Default**: Current system may over-rely on heavy NLU providers like spacy for simple keyword-based intents
2. **No Intent Keyword Donation**: Intents cannot contribute their own keywords for identification
3. **Inflexible Fallback Chain**: No clear hierarchy of NLU approaches from simple to complex

### Proposed Solution: Keyword-First NLU with Intent Donation

**Phase 1: Intent Keyword Donation System**
- Add `get_keywords()` method to `IntentHandler` base class
- Intent handlers donate lists of keywords that identify them as workflow targets
- Simple keyword matcher uses donated keywords for fast initial recognition

**Phase 2: Hierarchical NLU Processing**
```python
# Intent handlers donate keywords
class TimerIntentHandler(IntentHandler):
    def get_keywords(self) -> List[str]:
        return ["timer", "таймер", "alarm", "будильник", "set", "поставь"]

# NLU processing hierarchy
1. Simple keyword matcher (fast, donated keywords)
2. Rule-based patterns (medium complexity, regex)
3. Spacy semantic understanding (fallback, complex cases)
```

**Phase 3: Intelligent Fallback**
- Keyword matcher handles 80% of common cases
- Spacy only invoked for ambiguous or complex utterances
- Confidence scoring determines when to escalate to more complex NLU

### Benefits

- **Performance**: Fast keyword matching for common intents
- **Simplicity**: Intent handlers define their own identification keywords
- **Scalability**: Lightweight approach scales better than semantic models
- **Fallback Safety**: Spacy available for complex cases that keywords miss
- **Self-Describing Intents**: Intent handlers become self-contained with their own keywords

### Implementation Strategy

1. **Keyword Collection**: Gather donated keywords from all registered intent handlers
2. **Fast Matching**: Implement efficient keyword-based intent identification
3. **Fallback Chain**: Route unmatched utterances to more complex NLU providers
4. **Confidence Tuning**: Adjust thresholds for when to escalate to semantic understanding

### Impact

- **Performance Improvement**: Faster intent recognition for common cases
- **Reduced Complexity**: Simpler default NLU path
- **Better Intent Encapsulation**: Handlers own their identification logic
- **Resource Efficiency**: Less reliance on heavy semantic models

### Related Files

- `irene/intents/handlers/base.py` (intent handler base class)
- `irene/providers/nlu/rule_based.py` (keyword matching implementation)
- `irene/providers/nlu/spacy_provider.py` (semantic fallback)
- `irene/intents/recognizer.py` (NLU coordination and fallback logic)
- `irene/intents/registry.py` (intent handler registration)

## 6. Target Build System: Minimal Container and Service Builds

**Status:** Open  
**Priority:** High  
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

## 8. Binary WebSocket Optimization for External Devices

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

## 7. MicroWakeWord Hugging Face Integration

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