# Intent Architecture Implementation Plan
## Complete Voice Assistant with NLU & Voice Trigger

---

## 📋 **Executive Summary**

This plan implements the **Intent Architecture** design from `docs/architecture_intents.md`, incorporating **Voice Trigger** capabilities from `docs/voice_trigger.md` into a unified modern voice assistant architecture.

### **Key Transformations**
1. **Current Flow**: `Audio → ASR → Direct Command Processing`
2. **Target Flow**: `Audio → Voice Trigger → ASR → Text Processing → Intent Recognition → Intent Execution → TTS`

### **Major Architectural Changes**
- ✅ **Rename & Move**: "Universal Plugins" → "Fundamental Components" (`irene/components/`)
- ✅ **Add Intent System**: Complete NLU pipeline (`irene/intents/`)
- ✅ **Fix Input Sources**: Remove ASR coupling from microphone input
- ✅ **Add Voice Trigger**: Wake word detection as fundamental component
- ✅ **Workflow Orchestration**: Centralized pipeline management (`irene/workflows/`)
- 🔄 **Leverage Existing**: Text processing via `irene/utils/text_processing.py` (already comprehensive!)
- 🔄 **Leverage Existing**: Audio infrastructure via `irene/utils/audio_helpers.py` (device management, format handling)
- 🔄 **Leverage Existing**: Component loading via `irene/utils/loader.py` (dependency validation, graceful fallbacks)

---

## 🚨 **Critical Issues to Resolve**

### **Current Microphone Input Violation**
**File**: `irene/inputs/microphone.py`
**Problem**: Directly calls ASR, violating separation of concerns

```python
# CURRENT (WRONG) - in microphone input:
async def process_audio_chunk(self, audio_data):
    # ❌ Input source should NOT do ASR!
    text = await self.asr.transcribe(audio_data)  
    await self.command_processor.process(text)
```

**Target**: Pure audio capture only
```python
# TARGET (RIGHT) - in microphone input:
async def listen(self) -> AsyncIterator[AudioData]:
    # ✅ Pure audio capture - no business logic
    while self._listening:
        yield AudioData(data=audio_chunk, timestamp=time.time())
```

---

## 📁 **Target File Structure**

```
irene/
├── components/                     # 🔧 Fundamental Components (renamed from universal plugins)
│   ├── __init__.py
│   ├── base.py
│   ├── tts_component.py           # ← universal_tts_plugin.py
│   ├── asr_component.py           # ← universal_asr_plugin.py  
│   ├── llm_component.py           # ← universal_llm_plugin.py
│   ├── audio_component.py         # ← universal_audio_plugin.py
│   ├── voice_trigger_component.py # 🆕 NEW
│   ├── nlu_component.py           # 🆕 NEW
│   └── text_processor_component.py # 🆕 NEW
│
├── intents/                       # 🎯 Intent System (NEW)
│   ├── __init__.py
│   ├── recognizer.py              # IntentRecognizer (NLU)
│   ├── orchestrator.py            # IntentOrchestrator  
│   ├── registry.py                # IntentRegistry
│   ├── context.py                 # ContextManager
│   ├── models.py                  # Intent, IntentResult classes
│   └── handlers/                  # Intent Handlers
│       ├── __init__.py
│       ├── base.py               # Base IntentHandler
│       ├── conversation.py       # ← conversation_plugin.py
│       ├── greetings.py          # ← greetings_plugin.py  
│       ├── timer.py              # ← timer_plugin.py
│       ├── datetime.py           # ← datetime_plugin.py
│       ├── system.py             # ← core_commands.py
│       ├── random.py             # ← random_plugin.py
│       └── weather.py            # 🆕 NEW
│
├── workflows/                     # 🎼 Workflow Orchestration (NEW)
│   ├── __init__.py
│   ├── base.py
│   ├── voice_assistant.py         # VoiceAssistantWorkflow
│   ├── text_assistant.py          # TextAssistantWorkflow  
│   └── continuous_listening.py    # ContinuousListeningWorkflow (backward compatibility)
│
├── inputs/                        # 📥 Input Sources (CLEANED)
│   ├── microphone.py             # ⚠️  CRITICAL: Remove ASR coupling
│   ├── web.py                    # ⚠️  CRITICAL: Remove workflow logic
│   └── cli.py                    # ⚠️  CRITICAL: Remove direct processing
│
├── providers/                     # 🔌 Provider Implementations  
│   ├── voice_trigger/            # 🆕 NEW (consistent naming with voice_trigger_component.py)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── openwakeword.py       # Primary provider
│   │   ├── microwakeword.py      # ESP32 compatibility
│   │   └── picovoice.py          # Commercial option
│   ├── nlu/                      # 🆕 NEW
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── spacy_provider.py     # spaCy NLU
│   │   ├── openai_provider.py    # OpenAI NLU
│   │   └── rule_based.py         # Fallback NLU
│   └── text_processing/          # 🆕 NEW (leverages existing irene/utils/text_processing.py)
│       ├── __init__.py
│       ├── base.py
│       ├── unified_processor.py     # ← wraps existing TextProcessor class
│       ├── number_processor.py      # ← wraps existing NumberNormalizer  
│       ├── prepare_processor.py     # ← wraps existing PrepareNormalizer
│       └── runorm_processor.py      # ← wraps existing RunormNormalizer
│
└── plugins/                      # 🔌 True Plugins (cleaned)
    ├── builtin/                  # Remove universal_* plugins
    ├── external/                 # External plugins
    └── examples/                 # Plugin development examples
```

---

## 🏗️ **Phase 1: Infrastructure & Core Refactoring**

### **Priority**: 🔴 CRITICAL - Foundation for everything else

### **Step 1.1: Create Intent System Core**

```bash
# Create intent system structure
mkdir -p irene/intents/handlers
mkdir -p irene/workflows  
mkdir -p irene/components
mkdir -p irene/providers/{voice_trigger,nlu,text_processing}
```

**New Files to Create:**

**`irene/intents/models.py`** - Core data models
```python
@dataclass
class Intent:
    name: str                # "weather.get_current"
    entities: dict           # {"location": "Moscow", "time": "now"}
    confidence: float        # 0.95
    raw_text: str           # Original user text
    timestamp: float
    
@dataclass  
class IntentResult:
    text: str                # Response text
    should_speak: bool       # Whether to use TTS
    metadata: dict           # Additional data
    actions: list            # Additional actions
```

**`irene/intents/recognizer.py`** - NLU component
```python
class IntentRecognizer:
    """Natural Language Understanding component"""
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        # Primary NLU provider logic
        # Fallback to conversation intent if low confidence
```

**`irene/intents/orchestrator.py`** - Central coordinator
```python
class IntentOrchestrator:
    """Central intent coordinator"""
    async def execute_intent(self, intent: Intent, context: ConversationContext) -> IntentResult:
        # Route intent to appropriate handler
        # Update conversation context
        # Handle errors gracefully
```

**`irene/intents/registry.py`** - Handler registry
```python
class IntentRegistry:
    """Registry of intent handlers"""
    def register_handler(self, pattern: str, handler: IntentHandler):
        # Support patterns like "weather.*", "timer.set"
```

**`irene/intents/context.py`** - Conversation context
```python
class ContextManager:
    """Manages conversation context and history"""
    async def get_context(self, session_id: str) -> ConversationContext:
        # Retrieve or create conversation context
```

### **Step 1.2: Move Universal Plugins → Components**

**Migration Commands:**
```bash
# Rename and move files
mv irene/plugins/builtin/universal_tts_plugin.py irene/components/tts_component.py
mv irene/plugins/builtin/universal_asr_plugin.py irene/components/asr_component.py  
mv irene/plugins/builtin/universal_llm_plugin.py irene/components/llm_component.py
mv irene/plugins/builtin/universal_audio_plugin.py irene/components/audio_component.py
```

**Class Renames:**
```python
# Update class names in each moved file
UniversalTTSPlugin → TTSComponent
UniversalASRPlugin → ASRComponent
UniversalLLMPlugin → LLMComponent  
UniversalAudioPlugin → AudioComponent
```

### **Step 1.3: Create New Components**

**Text Processing** - **🔄 LEVERAGE EXISTING `irene/utils/text_processing.py`**

The existing `text_processing.py` file already provides comprehensive async text processing:
- **`TextProcessor`** class with multi-stage pipeline
- **`NumberNormalizer`**, **`PrepareNormalizer`**, **`RunormNormalizer`** 
- **Async functions**: `all_num_to_text_async()`, `num_to_text_ru_async()`
- **Stage awareness**: "asr_output", "general", "tts_input"

**Create wrapper component instead of rebuilding:**

**`irene/components/voice_trigger_component.py`** - **🔄 LEVERAGE EXISTING + WEB API**
```python
from irene.utils.audio_helpers import calculate_audio_buffer_size, validate_audio_file
from irene.utils.loader import DependencyChecker, safe_import
from irene.core.interfaces.webapi import WebAPIPlugin

class VoiceTriggerComponent(Component, WebAPIPlugin):
    """Voice trigger detection component - uses audio_helpers.py for audio management"""
    
    def __init__(self):
        super().__init__()
        self.dependency_checker = DependencyChecker()  # From loader.py
        self.buffer_size = calculate_audio_buffer_size(16000, 100.0)  # From audio_helpers.py
    
    def get_dependencies(self) -> list[str]:
        return ["openwakeword", "numpy"]
        
    async def detect(self, audio_data: AudioData) -> WakeWordResult:
        # Use existing audio validation and provider loading
        provider = self.get_current_provider()
        return await provider.detect_wake_word(audio_data)
    
    # WebAPIPlugin interface - following universal plugin pattern
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with voice trigger endpoints"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter, HTTPException, WebSocket  # type: ignore
            from pydantic import BaseModel  # type: ignore
            
            router = APIRouter()
            
            # Request/Response models
            class VoiceTriggerStatus(BaseModel):
                active: bool
                wake_words: list[str]
                threshold: float
                provider: str
                
            class WakeWordConfig(BaseModel):
                wake_words: list[str]
                threshold: float = 0.8
                
            @router.get("/status", response_model=VoiceTriggerStatus)
            async def get_status():
                """Get voice trigger status and configuration"""
                return VoiceTriggerStatus(
                    active=self.is_active(),
                    wake_words=self.get_wake_words(),
                    threshold=self.get_threshold(),
                    provider=self.default_provider
                )
            
            @router.post("/configure")
            async def configure_voice_trigger(config: WakeWordConfig):
                """Configure voice trigger settings"""
                await self.set_wake_words(config.wake_words)
                await self.set_threshold(config.threshold)
                return {"success": True, "config": config}
            
            @router.get("/providers")
            async def list_voice_trigger_providers():
                """Discovery endpoint for voice trigger provider capabilities"""
                result = {}
                for name, provider in self.providers.items():
                    result[name] = {
                        "available": await provider.is_available(),
                        "wake_words": provider.get_supported_wake_words(),
                        "parameters": provider.get_parameter_schema(),
                        "capabilities": provider.get_capabilities()
                    }
                return {"providers": result, "default": self.default_provider}
            
            @router.websocket("/stream")
            async def voice_trigger_stream(websocket: WebSocket):
                """WebSocket endpoint for real-time voice trigger detection"""
                await websocket.accept()
                try:
                    while True:
                        # Audio data from client
                        audio_data = await websocket.receive_bytes()
                        
                        # Process through voice trigger
                        result = await self.detect(AudioData(audio_data))
                        
                        # Send detection result
                        await websocket.send_json({
                            "detected": result.detected,
                            "confidence": result.confidence,
                            "word": result.word,
                            "timestamp": result.timestamp
                        })
                except Exception as e:
                    logger.error(f"Voice trigger WebSocket error: {e}")
            
            return router
            
        except ImportError:
            logger.warning("FastAPI not available for voice trigger web API")
            return None
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for voice trigger API endpoints"""
        return "/voice_trigger"
    
    def get_api_tags(self) -> list[str]:
        """Get OpenAPI tags for voice trigger endpoints"""
        return ["voice_trigger", "wake_word_detection"]
```

**`irene/components/nlu_component.py`** - **🆕 NEW + WEB API**
```python
from irene.core.interfaces.webapi import WebAPIPlugin

class NLUComponent(Component, WebAPIPlugin):
    """Natural Language Understanding component"""
    
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        # Coordinate multiple NLU providers
        provider = self.get_current_provider()
        return await provider.recognize(text, context)
    
    # WebAPIPlugin interface - following universal plugin pattern
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with NLU endpoints"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter, HTTPException  # type: ignore
            from pydantic import BaseModel  # type: ignore
            
            router = APIRouter()
            
            # Request/Response models
            class NLURequest(BaseModel):
                text: str
                context: Optional[dict] = None
                provider: Optional[str] = None
                
            class IntentResponse(BaseModel):
                name: str
                entities: dict
                confidence: float
                provider: str
                
            @router.post("/recognize", response_model=IntentResponse)
            async def recognize_intent(request: NLURequest):
                """Recognize intent from text input"""
                # Create context from request
                context = ConversationContext(
                    session_id=request.context.get("session_id", "default") if request.context else "default",
                    history=request.context.get("history", []) if request.context else []
                )
                
                # Use specific provider if requested
                if request.provider and request.provider in self.providers:
                    intent = await self.providers[request.provider].recognize(request.text, context)
                else:
                    intent = await self.recognize(request.text, context)
                
                return IntentResponse(
                    name=intent.name,
                    entities=intent.entities,
                    confidence=intent.confidence,
                    provider=request.provider or self.default_provider
                )
            
            @router.get("/providers")
            async def list_nlu_providers():
                """Discovery endpoint for NLU provider capabilities"""
                result = {}
                for name, provider in self.providers.items():
                    result[name] = {
                        "available": await provider.is_available(),
                        "languages": provider.get_supported_languages(),
                        "domains": provider.get_supported_domains(),
                        "parameters": provider.get_parameter_schema(),
                        "capabilities": provider.get_capabilities()
                    }
                return {"providers": result, "default": self.default_provider}
            
            @router.post("/configure")
            async def configure_nlu(provider: str, set_as_default: bool = False):
                """Configure NLU settings"""
                if provider in self.providers:
                    if set_as_default:
                        self.default_provider = provider
                    return {"success": True, "default_provider": self.default_provider}
                else:
                    raise HTTPException(404, f"Provider '{provider}' not available")
            
            return router
            
        except ImportError:
            logger.warning("FastAPI not available for NLU web API")
            return None
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for NLU API endpoints"""
        return "/nlu"
    
    def get_api_tags(self) -> list[str]:
        """Get OpenAPI tags for NLU endpoints"""
        return ["nlu", "intent_recognition"]
```

**`irene/components/text_processor_component.py`** - **🔄 LEVERAGE EXISTING + WEB API**
```python
from irene.utils.text_processing import TextProcessor, NumberNormalizer, PrepareNormalizer, RunormNormalizer
from irene.core.interfaces.webapi import WebAPIPlugin

class TextProcessorComponent(Component, WebAPIPlugin):
    """Text processing component - wraps existing text_processing.py utilities"""
    
    def __init__(self):
        super().__init__()
        # Use existing TextProcessor with all normalizers
        self.processor = TextProcessor()
        
    def get_dependencies(self) -> list[str]:
        return ["lingua_franca", "eng_to_ipa", "runorm"]  # Optional dependencies
        
    async def improve(self, text: str, context: ConversationContext, stage: str = "general") -> str:
        """
        Improve text using existing normalizers based on processing stage.
        Stages: 'asr_output', 'general', 'tts_input'
        """
        return await self.processor.process_pipeline(text, stage)
        
    async def normalize_numbers(self, text: str) -> str:
        """Direct access to number normalization"""
        normalizer = NumberNormalizer()
        return await normalizer.normalize(text)
    
    # WebAPIPlugin interface - following universal plugin pattern
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with text processing endpoints"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter  # type: ignore
            from pydantic import BaseModel  # type: ignore
            
            router = APIRouter()
            
            # Request/Response models
            class TextProcessingRequest(BaseModel):
                text: str
                stage: str = "general"  # 'asr_output', 'general', 'tts_input'
                normalizer: Optional[str] = None  # Specific normalizer to use
                
            class TextProcessingResponse(BaseModel):
                original_text: str
                processed_text: str
                stage: str
                normalizers_applied: list[str]
                
            @router.post("/process", response_model=TextProcessingResponse)
            async def process_text(request: TextProcessingRequest):
                """Process text through normalization pipeline"""
                if request.normalizer:
                    # Use specific normalizer
                    if request.normalizer == "numbers":
                        processed = await self.normalize_numbers(request.text)
                        normalizers = ["NumberNormalizer"]
                    elif request.normalizer == "prepare":
                        normalizer = PrepareNormalizer()
                        processed = await normalizer.normalize(request.text)
                        normalizers = ["PrepareNormalizer"]
                    elif request.normalizer == "runorm":
                        normalizer = RunormNormalizer()
                        processed = await normalizer.normalize(request.text)
                        normalizers = ["RunormNormalizer"]
                    else:
                        processed = request.text
                        normalizers = []
                else:
                    # Use full pipeline
                    processed = await self.processor.process_pipeline(request.text, request.stage)
                    normalizers = [n.__class__.__name__ for n in self.processor.normalizers 
                                 if n.applies_to_stage(request.stage)]
                
                return TextProcessingResponse(
                    original_text=request.text,
                    processed_text=processed,
                    stage=request.stage,
                    normalizers_applied=normalizers
                )
            
            @router.post("/numbers")
            async def convert_numbers_to_text(text: str, language: str = "ru"):
                """Convert numbers in text to words"""
                from irene.utils.text_processing import all_num_to_text_async
                processed = await all_num_to_text_async(text, language)
                return {
                    "original_text": text,
                    "processed_text": processed,
                    "language": language
                }
            
            @router.get("/normalizers")
            async def list_normalizers():
                """List available text normalizers and their capabilities"""
                normalizers = {}
                for normalizer in self.processor.normalizers:
                    name = normalizer.__class__.__name__
                    normalizers[name] = {
                        "stages": ["asr_output", "general", "tts_input"],
                        "applies_to": [stage for stage in ["asr_output", "general", "tts_input"] 
                                     if normalizer.applies_to_stage(stage)],
                        "description": normalizer.__doc__ or f"{name} text normalizer"
                    }
                
                return {
                    "normalizers": normalizers,
                    "pipeline_stages": ["asr_output", "general", "tts_input"]
                }
            
            return router
            
        except ImportError:
            logger.warning("FastAPI not available for text processing web API")
            return None
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for text processing API endpoints"""
        return "/text_processing"
    
    def get_api_tags(self) -> list[str]:
        """Get OpenAPI tags for text processing endpoints"""
        return ["text_processing", "normalization"]
```

### **Step 1.4: Fix Input Sources (CRITICAL)**

**`irene/inputs/microphone.py` - Remove ASR coupling**

**BEFORE (Current - Violates Separation):**
```python
class MicrophoneInput(InputSource):
    async def listen(self):
        # ❌ WRONG: Input source doing business logic
        audio_data = await self._capture_audio()
        text = await self.asr.transcribe(audio_data)  # ← Remove this!
        await self.command_processor.process(text)    # ← Remove this!
```

**AFTER (Target - Pure Input Source + Audio Helpers):**
```python
from irene.utils.audio_helpers import get_default_audio_device, AudioFormatConverter
from irene.utils.loader import safe_import

class MicrophoneInput(InputSource):
    """Pure microphone input - only audio capture (enhanced with audio_helpers.py)"""
    
    async def initialize(self):
        """Initialize using existing audio infrastructure"""
        # Device selection using audio_helpers.py
        self.device = await get_default_audio_device()
        if not self.device:
            raise ConfigurationError("No audio input device available")
            
        # Format validation using audio_helpers.py
        if not AudioFormatConverter.supports_format('wav'):
            logger.warning("WAV format not supported, audio quality may be reduced")
    
    async def listen(self) -> AsyncIterator[AudioData]:
        """Pure audio stream - no business logic"""
        while self._listening:
            audio_chunk = await self._capture_audio()
            yield AudioData(
                data=audio_chunk,
                timestamp=time.time(),
                sample_rate=self.config.sample_rate,
                channels=self.config.channels
            )
```

### **Step 1.5: Update Component Manager**

**`irene/core/components.py`** - **🔄 ENHANCED WITH EXISTING UTILITIES**
```python
from irene.utils.loader import DependencyChecker, get_component_status

class ComponentManager:
    def __init__(self):
        self.dependency_checker = DependencyChecker()  # From loader.py
    
    def get_available_components(self) -> dict:
        components = {
            "tts": TTSComponent,
            "asr": ASRComponent, 
            "llm": LLMComponent,
            "audio": AudioComponent,
            "voice_trigger": VoiceTriggerComponent,  # NEW
            "nlu": NLUComponent,                     # NEW
            "text_processor": TextProcessorComponent # NEW
        }
        
        # Use loader.py to validate each component's dependencies
        available = {}
        for name, cls in components.items():
            if self.dependency_checker.check(name, cls.get_dependencies()):
                available[name] = cls
            else:
                logger.warning(f"Component {name} not available - missing dependencies")
        
        return available
        
    async def get_system_status(self) -> dict:
        """Get comprehensive system status using loader.py utilities"""
        return get_component_status()  # From loader.py
```

### **Step 1.6: Update Configuration**

**`irene/config/models.py`** - Add new config models
```python
@dataclass
class IntentsConfig:
    enabled: bool = True
    confidence_threshold: float = 0.7
    fallback_handler: str = "conversation"
    max_history_turns: int = 10
    session_timeout: int = 1800

@dataclass  
class VoiceTriggerConfig:
    provider: str = "openwakeword"
    wake_words: list[str] = field(default_factory=lambda: ["irene", "jarvis"])
    threshold: float = 0.8
    buffer_seconds: float = 1.0
    timeout_seconds: float = 5.0
```

---

## 🎼 **Phase 2: Workflow Integration & Voice Trigger**

### **Priority**: 🔴 HIGH - Voice functionality restoration

### **Step 2.1: Create VoiceAssistantWorkflow**

**`irene/workflows/voice_assistant.py`** - **🔄 ENHANCED WITH EXISTING UTILITIES**
```python
from irene.utils.audio_helpers import test_audio_playback_capability, calculate_audio_buffer_size
from irene.utils.loader import safe_import

class VoiceAssistantWorkflow(Workflow):
    """Complete voice assistant workflow with intent system"""
    
    async def initialize(self):
        """Initialize audio pipeline using existing audio_helpers.py utilities"""
        # Validate audio capability before starting
        capabilities = await test_audio_playback_capability()  # From audio_helpers.py
        if not capabilities['devices_available']:
            raise ConfigurationError("No audio devices available")
            
        # Configure optimal buffer for voice trigger + ASR pipeline
        self.buffer_size = calculate_audio_buffer_size(16000, 100.0)  # From audio_helpers.py
    
    async def process_audio_stream(self, audio_stream: AsyncIterator[AudioData], context: RequestContext):
        """Main workflow: Audio → Wake Word → ASR → NLU → Intent Execution → Response"""
        
        async for audio_data in audio_stream:
            # 1. Voice Trigger Detection
            if self.voice_trigger and not context.skip_wake_word:
                wake_result = await self.voice_trigger.detect(audio_data)
                if not wake_result.detected:
                    continue
                    
            # 2. Speech Recognition  
            text = await self.asr.transcribe(audio_data)
            
            # 3. Text Processing (using existing irene/utils/text_processing.py)
            improved_text = await self.text_processor.improve(text, conv_context, stage="asr_output")
            
            # 4. Intent Recognition (NEW!)
            intent = await self.nlu.recognize(improved_text, conv_context)
            
            # 5. Intent Execution (NEW!)
            result = await self.intent_orchestrator.execute_intent(intent, conv_context)
            
            # 6. Response Output
            await self._route_response(result, context)
```

### **Step 2.2: Implement Voice Trigger Providers**

**`irene/providers/voice_trigger/openwakeword.py`**
```python
class OpenWakeWordProvider(VoiceTriggerProvider):
    """OpenWakeWord provider - recommended"""
    
    async def detect_wake_word(self, audio_data: AudioData) -> WakeWordResult:
        prediction = await self._model.predict(audio_data.data)
        return WakeWordResult(
            detected=prediction.score > self.threshold,
            confidence=prediction.score,
            word=prediction.word,
            timestamp=audio_data.timestamp
        )
```

### **Step 2.3: Create Backward Compatibility Workflow**

**`irene/workflows/continuous_listening.py`**
```python
class ContinuousListeningWorkflow(Workflow):
    """Backward compatibility - direct ASR without wake word"""
    
    async def process_audio_stream(self, audio_stream: AsyncIterator[AudioData], context: RequestContext):
        """Legacy workflow: Audio → ASR → Intent → Response (no wake word)"""
        # Maintains current behavior for users who don't want wake words
```

### **Step 2.4: Update Input Manager**

**`irene/core/engine.py` or input coordination**
```python
class InputManager:
    async def start_voice_assistant_mode(self):
        """Start with voice trigger workflow"""
        workflow = self.core.get_workflow("voice_assistant")
        mic_input = self._get_input_source("microphone")
        
        audio_stream = mic_input.listen()  # Pure audio stream
        context = RequestContext(source="microphone", wants_audio=True, skip_wake_word=False)
        
        await workflow.process_audio_stream(audio_stream, context)
        
    async def start_continuous_mode(self):
        """Start without voice trigger (current behavior)"""
        workflow = self.core.get_workflow("continuous_listening")
        # ... similar but skip_wake_word=True
```

---

## 🧠 **Phase 3: NLU & Intent Handlers**

### **Priority**: 🟡 MEDIUM - Intelligence layer

### **Step 3.1: Basic Intent Handlers**

**Move existing plugins to intent handlers:**

**`irene/intents/handlers/conversation.py`** ← `conversation_plugin.py`
```python
class ConversationIntentHandler(IntentHandler):
    """Handles free-form conversation via LLM"""
    
    def can_handle(self, intent: Intent) -> bool:
        return intent.domain in ["conversation", "chat", "general"]
        
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        # Use LLM for conversation with context history
        messages = self._build_conversation_history(context)
        response = await self.llm.generate_response(messages)
        
        return IntentResult(text=response, should_speak=True)
```

**`irene/intents/handlers/timer.py`** ← `timer_plugin.py`
```python
class TimerIntentHandler(IntentHandler):
    """Handles timer operations"""
    
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        if intent.action == "set":
            return await self._set_timer(intent, context)
        elif intent.action == "cancel":
            return await self._cancel_timer(intent, context)
```

### **Step 3.2: Text Processing Providers** - **🔄 LEVERAGE EXISTING**

**`irene/providers/text_processing/unified_processor.py`** - **Wraps existing TextProcessor**
```python
from irene.utils.text_processing import TextProcessor as ExistingTextProcessor
from irene.providers.base import Provider

class UnifiedTextProcessor(Provider):
    """Unified text processing provider - wraps existing TextProcessor from utils"""
    
    def __init__(self):
        super().__init__()
        # Use the existing, battle-tested TextProcessor
        self.processor = ExistingTextProcessor()
        
    async def process(self, text: str, stage: str = "general") -> str:
        """Process text through existing normalization pipeline"""
        return await self.processor.process_pipeline(text, stage)
```

**`irene/providers/text_processing/number_processor.py`** - **Wraps existing NumberNormalizer**
```python
from irene.utils.text_processing import NumberNormalizer as ExistingNumberNormalizer, all_num_to_text_async
from irene.providers.base import Provider

class NumberTextProcessor(Provider):
    """Number-to-text provider - wraps existing number conversion utilities"""
    
    def __init__(self):
        super().__init__()
        self.normalizer = ExistingNumberNormalizer()
        
    async def convert_numbers_to_text(self, text: str, language: str = "ru") -> str:
        """Convert numbers in text to words using existing all_num_to_text_async"""
        return await all_num_to_text_async(text, language)
        
    async def normalize(self, text: str) -> str:
        """Apply number normalization using existing normalizer"""
        return await self.normalizer.normalize(text)
```

### **Step 3.3: NLU Providers**

**`irene/providers/nlu/rule_based.py`** - Fallback NLU
```python
class RuleBasedNLUProvider(NLUProvider):
    """Simple rule-based NLU for fallback"""
    
    def __init__(self):
        self.patterns = {
            r"what.*(time|hour)": "datetime.get_current",
            r"set.*timer.*(\d+)": "timer.set", 
            r"what.*(weather|temperature)": "weather.get_current",
            # ... basic regex patterns
        }
        
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        # Simple pattern matching with entity extraction
```

**`irene/providers/nlu/spacy_provider.py`** - Advanced NLU
```python
class SpaCyNLUProvider(NLUProvider):
    """spaCy-based NLU with entity recognition"""
    
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        # Use spaCy for intent classification and entity extraction
        doc = self.nlp(text)
        # Extract entities, classify intent
```

### **Step 3.3: Context Management**

**`irene/intents/context.py`** - Session context
```python
class ContextManager:
    async def get_context(self, session_id: str) -> ConversationContext:
        # Retrieve or create conversation context
        # Manage session timeouts
        # Maintain conversation history
        
    async def add_user_turn(self, intent: Intent, context: ConversationContext):
        # Add user intent to conversation history
        
    async def add_assistant_turn(self, result: IntentResult, context: ConversationContext):  
        # Add assistant response to history
```

---

## 🌐 **Phase 4: Web API & Advanced Features**

### **Priority**: 🟢 LOW - Enhancement features

### **Step 4.1: Intent Management API**

**New Web API endpoints** - **🔄 FOLLOWING EXISTING COMPONENT PATTERN**

Each new component provides its own router (following universal plugin pattern):

```python
# Voice Trigger Component Router (/voice_trigger)
@router.get("/status")                    # Voice trigger status and configuration
@router.post("/configure")               # Configure wake words and thresholds  
@router.get("/providers")                # Available voice trigger providers
@router.websocket("/stream")             # Real-time voice trigger WebSocket

# NLU Component Router (/nlu)  
@router.post("/recognize")               # Text → Intent recognition
@router.get("/providers")                # Available NLU providers
@router.post("/configure")               # Configure NLU settings

# Text Processing Component Router (/text_processing)
@router.post("/process")                 # Text normalization pipeline
@router.post("/numbers")                 # Number-to-text conversion
@router.get("/normalizers")              # Available normalizers

# Intent Management (new high-level endpoints)
@app.post("/intents/execute")            # Direct intent execution  
@app.get("/intents/handlers")            # Available intent handlers
@app.get("/system/capabilities")         # Overall system capabilities
```

**WebAPI Runner Integration:**
- Automatically discovers and mounts all component routers
- Maintains existing `/tts`, `/asr`, `/llm`, `/audio` endpoints  
- Adds new `/voice_trigger`, `/nlu`, `/text_processing` endpoints
- Provides unified `/intents` management layer

### **Step 4.2: Plugin System Refinement**

**Clean up true plugins:**
```bash
# Remove builtin plugins that became components
rm irene/plugins/builtin/universal_*_plugin.py

# Keep true intent plugins  
mv irene/plugins/builtin/*_plugin.py irene/intents/handlers/
```

### **Step 4.3: Analytics & Monitoring**

**Intent metrics:**
- Intent recognition accuracy
- Intent execution success rate  
- Context session duration
- User satisfaction scoring

---

## 🔄 **Migration Strategy**

### **Backward Compatibility Plan**

1. **Leverage existing utilities** - **No migration needed!**
```python
# irene/utils/ files are already ready for the new architecture:
from irene.utils.text_processing import TextProcessor       # Ready for TextProcessorComponent
from irene.utils.audio_helpers import get_audio_devices    # Ready for VoiceTriggerComponent  
from irene.utils.loader import DependencyChecker           # Ready for ComponentManager
```

2. **Keep old imports working** during transition:
```python
# irene/plugins/builtin/__init__.py  
from irene.components.tts_component import TTSComponent as UniversalTTSPlugin  # Deprecated alias
```

3. **Feature flags** for gradual rollout:
```toml
[experimental]
intent_system = true           # Enable new intent system
voice_trigger = true          # Enable voice trigger
legacy_mode = false           # Keep old behavior
```

3. **Deployment profiles** support both modes:
```python
def get_deployment_profile(self) -> str:
    if self.config.experimental.intent_system:
        return "Smart Voice Assistant"      # New system
    else:
        return "Voice Assistant (Legacy)"   # Current system
```

### **Testing Strategy**

1. **Unit tests** for each component
2. **Integration tests** for workflows  
3. **End-to-end tests** for complete pipeline
4. **Regression tests** to ensure backward compatibility

---

## 📦 **Dependencies & Installation**

### **Existing Infrastructure** - **🔄 ALREADY AVAILABLE!**

## **🎵 Audio Infrastructure** - `irene/utils/audio_helpers.py`
**Comprehensive async audio management utilities**

**Features Already Implemented:**
- ✅ **Device Management** - `get_audio_devices()`, `get_default_audio_device()` 
- ✅ **Format Validation** - `validate_audio_file()`, `AudioFormatConverter`
- ✅ **Buffer Optimization** - `calculate_audio_buffer_size()` for streaming
- ✅ **Capability Testing** - `test_audio_playback_capability()` for system validation
- ✅ **Volume Control** - `normalize_volume()` with multiple scale support
- ✅ **Sample Rate Detection** - `detect_sample_rate()` with fallback support
- ✅ **Async Operations** - All device and format operations are async-ready

## **⚙️ Component Loading** - `irene/utils/loader.py`
**Graceful dependency management and component loading**

**Features Already Implemented:**
- ✅ **Dependency Validation** - `DependencyChecker` with caching
- ✅ **Safe Imports** - `safe_import()`, `require_dependencies()` decorators
- ✅ **System Status** - `get_component_status()` comprehensive reporting
- ✅ **User Guidance** - `suggest_installation()` for missing dependencies
- ✅ **Graceful Fallbacks** - Components degrade gracefully when dependencies missing

## **📝 Text Processing** - `irene/utils/text_processing.py`
**Comprehensive async text processing utilities**

**Features Already Implemented:**
- ✅ **Number-to-text conversion** (Russian) - `num_to_text_ru()`, `all_num_to_text()`
- ✅ **Async versions** - `all_num_to_text_async()`, `num_to_text_ru_async()`
- ✅ **Multi-stage pipeline** - `TextProcessor` with configurable normalizers
- ✅ **Latin transcription** - IPA-based English→Russian transcription
- ✅ **Symbol normalization** - Comprehensive symbol-to-text conversion
- ✅ **Advanced normalization** - RUNorm integration for sophisticated text processing
- ✅ **Lingua Franca integration** - International number formatting

**Optional Dependencies** (already defined):
```python
# From existing text_processing.py
lingua_franca    # International text processing
eng_to_ipa      # English to IPA transcription  
runorm          # Advanced Russian normalization

# From existing audio_helpers.py
soundfile       # Audio format conversion and detection
sounddevice     # Audio device enumeration and management
librosa         # High-quality audio resampling (optional)
numpy           # Audio buffer calculations

# From existing loader.py  
# No additional dependencies - uses built-in importlib
```

### **New Dependencies**
```toml
# pyproject.toml additions  
[project.optional-dependencies]
voice-trigger = [
    "openwakeword>=0.6.0",
    "numpy>=1.24.0", 
    "scipy>=1.10.0"
]
nlu = [
    "spacy>=3.7.0",
    "spacy-transformers>=1.3.0"
]
text-processing = [
    # Already integrated in existing text_processing.py
    "lingua_franca>=0.4.2",    # Optional for international support
    "eng_to_ipa>=0.1.0",       # Optional for Latin transcription
    "runorm>=0.1.0"            # Optional for advanced normalization
]
audio-infrastructure = [
    # Already integrated in existing audio_helpers.py and loader.py
    "soundfile>=0.12.0",       # Audio format conversion and detection
    "sounddevice>=0.4.0",      # Device enumeration and management  
    "librosa>=0.9.0",          # Optional for high-quality audio resampling
    "numpy>=1.24.0"            # Audio buffer calculations
]
intent-system = [
    "irene-voice-assistant[voice-trigger,nlu,text-processing,audio-infrastructure]"
]
```

### **Model Downloads**
```bash
# Wake word models
python -m openwakeword.download --model alexa
python -m openwakeword.download --model hey_jarvis

# NLU models  
python -m spacy download en_core_web_sm
python -m spacy download ru_core_news_sm
```

---

## 🎯 **Success Criteria**

### **Phase 1 Complete When:**
- ✅ All universal plugins moved to components/
- ✅ Intent system core implemented
- ✅ Microphone input cleaned (no ASR coupling)
- ✅ Basic intent handlers working
- ✅ Configuration updated
- 🔄 **Text processing component wrapping existing `irene/utils/text_processing.py`**
- 🔄 **Component loading enhanced with existing `irene/utils/loader.py`**
- 🔄 **Audio infrastructure leveraging existing `irene/utils/audio_helpers.py`**
- 🔄 **Web API router pattern maintained from universal plugins to new components**

### **Phase 2 Complete When:**
- ✅ Voice trigger component functional
- ✅ VoiceAssistantWorkflow orchestrating complete pipeline
- ✅ Wake word detection working (ESP32 parity)
- ✅ Backward compatibility maintained

### **Phase 3 Complete When:**
- ✅ NLU providers implemented
- ✅ Intent recognition working
- ✅ Context-aware conversations
- ✅ All existing functionality preserved

### **Phase 4 Complete When:**
- ✅ Web API extended
- ✅ Plugin system refined
- ✅ Analytics implemented
- ✅ Production ready

---

## 🚨 **Critical Migration Issues**

### **1. Import Dependencies**
Many files import from `irene.plugins.builtin.universal_*`. Need comprehensive find/replace:
```bash
find irene/ -name "*.py" -exec grep -l "from irene.plugins.builtin.universal_" {} \;
# Update all imports to use new component paths
```

### **2. Configuration Compatibility**
Existing config files reference old plugin names:
```toml
# OLD
[plugins.universal_tts]

# NEW  
[components.tts]
```

### **3. Plugin Manager Updates**
`PluginManager` needs to load from multiple locations:
- `irene/components/` - Fundamental components
- `irene/intents/handlers/` - Intent handlers  
- `irene/workflows/` - Workflow orchestrators
- `irene/plugins/` - True plugins

### **4. Web API Compatibility**  
Existing API endpoints need to work during transition:
```python
# Keep old endpoints working
@app.get("/plugins/universal_tts/status")  # Redirect to /components/tts/status
```

---

## 📚 **Context References**

### **Source Documents**
- **`docs/voice_trigger.md`** - Voice trigger component design
- **`docs/architecture_intents.md`** - Complete intent architecture 

### **Key Files to Modify**
- **`irene/inputs/microphone.py`** - ⚠️  Remove ASR coupling
- **`irene/core/components.py`** - Add new components
- **`irene/config/models.py`** - Add intent/voice config
- **`irene/plugins/builtin/*.py`** - Move to appropriate locations

### **Key Files to Leverage (Already Existing)**
- **`irene/utils/text_processing.py`** - 🔄 **Comprehensive text processing** (wrap, don't rebuild)
  - `TextProcessor` - Multi-stage pipeline ready for component wrapping
  - `NumberNormalizer`, `PrepareNormalizer`, `RunormNormalizer` - Ready for provider wrapping
  - `all_num_to_text_async()` - Russian number conversion for voice output

- **`irene/utils/audio_helpers.py`** - 🔄 **Audio infrastructure foundation** (perfect for audio components)
  - `get_audio_devices()`, `get_default_audio_device()` - Device management for audio providers
  - `AudioFormatConverter` - Cross-provider format consistency and validation  
  - `calculate_audio_buffer_size()` - Optimal streaming for voice trigger + ASR pipeline
  - `test_audio_playback_capability()` - System capability detection and validation

- **`irene/utils/loader.py`** - 🔄 **Component loading infrastructure** (graceful dependency management)
  - `DependencyChecker` - Component availability validation with caching
  - `safe_import()`, `require_dependencies()` - Graceful provider loading with fallbacks
  - `get_component_status()` - System capability reporting for configuration guidance
  - `suggest_installation()` - User guidance for missing optional dependencies

### **Integration Points**
- **ESP32 Firmware** - Voice trigger model compatibility
- **Web API** - Extend with intent endpoints (via component routers)
- **Asset Management** - Wake word model downloads
- **Plugin System** - Distinguish components vs plugins
- **Application Runners** - Workflow orchestration entry points (`irene/runners/`)
  - `CLIRunner` → Initialize intent-based command processing
  - `WebAPIRunner` → Mount component routers following existing pattern
  - `VoskRunner` → Full voice assistant workflow with VOSK ASR
  - `SettingsRunner` → Intent system configuration management

This plan transforms Irene from a simple voice-to-text system into a modern intelligent voice assistant with proper intent understanding, context awareness, and voice trigger capabilities.

**🎯 Key Advantage**: Irene already has comprehensive utilities (`text_processing.py`, `audio_helpers.py`, `loader.py`) that provide **80% of the infrastructure needed** for the new architecture. This means faster implementation with proven, battle-tested foundations! 