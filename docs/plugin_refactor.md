# Plugin Refactoring Implementation Plan
## Reorganization to Universal Plugin + Provider Architecture

---

## 🎯 **Overview**

This document outlines the complete reorganization of Irene Voice Assistant v13 plugins from the current "many small plugins" approach to a "Universal Plugin + Provider" architecture. This refactoring will create cleaner abstractions, unified APIs, and better maintainability.

### **Current State:**
- 14+ individual plugin classes
- Separate plugins for each TTS/Audio backend
- No unified web APIs
- Complex inter-plugin dependencies

### **Target State:**
- 8 Universal Plugin classes (coordinators with web APIs)
- 12+ Provider classes (pure implementations)
- Unified web APIs for all functionality
- Configuration-driven provider instantiation

---

## 🏗️ **Architecture Overview**

### **Design Patterns:**

#### **0. ABC Inheritance Pattern** ✅ **IMPLEMENTED**
```python
from abc import ABC, abstractmethod

class TTSProvider(ABC):
    """Abstract base class for all TTS implementations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    async def speak(self, text: str, **kwargs) -> None:
        pass

class ConsoleTTSProvider(TTSProvider):
    """Concrete implementation with proper inheritance"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)  # Proper ABC inheritance
        # Provider-specific initialization
```

**Benefits:**
- **Type Safety**: Python enforces interface compliance at class definition
- **Runtime Validation**: Missing abstract methods cause immediate errors  
- **Better IDE Support**: Autocomplete and error detection
- **Clear Contracts**: Explicit inheritance shows relationships
- **Maintainability**: Easier to understand and extend

#### **1. Universal Plugin Pattern**
```python
class UniversalTTSPlugin(TTSPlugin, WebAPIPlugin, CommandPlugin):
    """
    Coordinator plugin that:
    - Instantiates providers based on configuration
    - Provides unified web API (/tts/*)
    - Handles voice commands for TTS control
    - Manages fallbacks and load balancing
    """
```

#### **2. Provider Interface Pattern**
```python
class TTSProvider(Protocol):
    """
    Pure implementation interface:
    - No plugin overhead
    - Configuration-driven instantiation
    - Managed by Universal Plugin
    - Clean dependency isolation
    """
```

#### **3. Configuration-Driven Instantiation**
```toml
# Universal plugin creates providers based on config
[plugins.universal_tts.providers.silero_v3]
enabled = true
model_path = "~/.cache/irene/models/silero_v3"
```

### **Key Principles:**
1. **Single Responsibility**: Universal plugins coordinate, providers implement
2. **Configuration Over Code**: Provider selection via config, not plugin discovery
3. **Unified APIs**: One web API per functionality domain
4. **Clean Abstraction**: Providers are implementation details
5. **Type Safety**: ABC inheritance ensures interface compliance and runtime validation

---

## 📊 **Plugin Reorganization Summary**

### **Before (Current):**
```
14 Plugin Classes:
├── Core Commands: GreetingsPlugin, DateTimePlugin, RandomPlugin, AsyncTimerPlugin
├── TTS Engines: PyttsTTSPlugin, ConsoleTTSPlugin, SileroV3TTSPlugin, SileroV4TTSPlugin, VoskTTSPlugin
└── Audio Backends: SoundDeviceAudioPlugin, AudioPlayerAudioPlugin, AplayAudioPlugin, SimpleAudioPlugin, ConsoleAudioPlugin
```

### **After (Target):**
```
8 Universal Plugin Classes (True Plugins):
├── Coordinators: UniversalTTSPlugin, UniversalAudioPlugin, UniversalASRPlugin, UniversalLLMPlugin
└── Enhanced Simple: AsyncTimerPlugin, DateTimePlugin, GreetingsPlugin, RandomPlugin

12+ Provider Classes (Implementation Details):
├── TTS: SileroV3TTSProvider, SileroV4TTSProvider, PyttsTTSProvider, ConsoleTTSProvider
├── Audio: SoundDeviceAudioProvider, AudioPlayerAudioProvider, AplayAudioProvider, etc.
├── ASR: VoskASRProvider, WhisperASRProvider, GoogleCloudASRProvider
└── LLM: OpenAILLMProvider, AnthropicLLMProvider, LocalLlamaLLMProvider
```

---

## 🔌 **Technical Architecture**

### **Provider Interface Definitions:**

#### **TTSProvider Interface**
```python
# irene/providers/tts/base.py
from typing import Protocol, Dict, Any, List
from pathlib import Path

class TTSProvider(Protocol):
    """Interface for TTS implementations"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with provider-specific config"""
        pass
    
    async def is_available(self) -> bool:
        """Check if provider dependencies are available"""
        pass
    
    async def speak(self, text: str, **kwargs) -> None:
        """Speak text with provider-specific parameters"""
        pass
    
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """Generate audio file"""
        pass
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for provider-specific parameters"""
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities (languages, formats, etc.)"""
        pass
    
    def get_provider_name(self) -> str:
        """Unique provider identifier"""
        pass
```

#### **AudioProvider Interface**
```python
# irene/providers/audio/base.py
class AudioProvider(Protocol):
    """Interface for audio playback implementations"""
    
    def __init__(self, config: Dict[str, Any]): ...
    
    async def is_available(self) -> bool: ...
    
    async def play_file(self, file_path: Path, **kwargs) -> None: ...
    
    async def play_stream(self, audio_stream: AsyncIterator[bytes], **kwargs) -> None: ...
    
    def get_parameter_schema(self) -> Dict[str, Any]: ...
    
    def get_supported_formats(self) -> List[str]: ...
    
    async def set_volume(self, volume: float) -> None: ...
    
    async def stop_playback(self) -> None: ...
```

#### **ASRProvider Interface**
```python
# irene/providers/asr/base.py
from abc import ABC, abstractmethod

class ASRProvider(ABC):
    """Abstract base class for speech recognition implementations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    async def is_available(self) -> bool:
        pass
    
    @abstractmethod
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        pass
    
    @abstractmethod
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        pass
    
    async def set_language(self, language: str) -> None:
        # Default implementation - override if supported
        pass
```

#### **LLMProvider Interface**
```python
# irene/providers/llm/base.py
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """Abstract base class for LLM implementations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    async def is_available(self) -> bool:
        pass
    
    @abstractmethod
    async def enhance_text(self, text: str, task: str = "improve", **kwargs) -> str:
        pass
    
    @abstractmethod
    async def chat_completion(self, messages: List[Dict], **kwargs) -> str:
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        pass
    
    @abstractmethod
    def get_supported_tasks(self) -> List[str]:
        pass
```

### **Universal Plugin Template:**
```python
# Template for universal plugins
class UniversalTTSPlugin(TTSPlugin, WebAPIPlugin, CommandPlugin):
    """TTS coordinator managing multiple providers"""
    
    def __init__(self):
        self.providers: Dict[str, TTSProvider] = {}
        self.default_provider: str = "pyttsx"
        self.fallback_providers: List[str] = ["pyttsx", "console"]
        
    async def initialize(self, core) -> None:
        """Instantiate providers based on configuration"""
        config = core.config.plugins.universal_tts
        
        # Define available provider classes
        provider_classes = {
            "pyttsx": PyttsTTSProvider,
            "silero_v3": SileroV3TTSProvider,
            "silero_v4": SileroV4TTSProvider,
            "vosk_tts": VoskTTSProvider,
            "console": ConsoleTTSProvider,
            "elevenlabs": ElevenLabsTTSProvider
        }
        
        # Instantiate enabled providers
        for provider_name, provider_class in provider_classes.items():
            provider_config = config.providers.get(provider_name, {})
            if provider_config.get("enabled", False):
                try:
                    provider = provider_class(provider_config)
                    if await provider.is_available():
                        self.providers[provider_name] = provider
                        logger.info(f"Loaded TTS provider: {provider_name}")
                except Exception as e:
                    logger.warning(f"Failed to load TTS provider {provider_name}: {e}")
        
        # Set default to first available
        if self.providers:
            self.default_provider = list(self.providers.keys())[0]
    
    # TTSPlugin interface - delegates to providers
    async def speak(self, text: str, **kwargs) -> None:
        provider_name = kwargs.get("provider", self.default_provider)
        if provider_name in self.providers:
            await self.providers[provider_name].speak(text, **kwargs)
        else:
            await self._speak_with_fallback(text, **kwargs)
    
    # CommandPlugin interface - voice control
    async def handle_command(self, command: str, context: Context) -> CommandResult:
        if "скажи" in command and "голосом" in command:
            # "скажи привет голосом ксении"
            text, provider, model = self._parse_tts_command(command)
            await self.speak(text, provider=provider, speaker=model)
            return CommandResult(success=True, response=f"Сказал '{text}' голосом {model}")
        elif "переключись на" in command:
            # "переключись на силеро"
            new_provider = self._parse_provider_name(command)
            if new_provider in self.providers:
                self.default_provider = new_provider
                return CommandResult(success=True, response=f"Переключился на {new_provider}")
        elif "покажи голоса" in command:
            info = self._get_providers_info()
            return CommandResult(success=True, response=info)
    
    # WebAPIPlugin interface - unified API
    def get_router(self) -> APIRouter:
        router = APIRouter()
        
        @router.post("/speak")
        async def unified_speak(request: TTSRequest):
            """Unified TTS endpoint for all providers"""
            provider = request.provider or self.default_provider
            provider_params = self._extract_provider_params(request, provider)
            
            if provider not in self.providers:
                raise HTTPException(404, f"Provider '{provider}' not available")
            
            await self.providers[provider].speak(request.text, **provider_params)
            return {"success": True, "provider": provider, "text": request.text}
        
        @router.get("/providers")
        async def list_providers():
            """Discovery endpoint for all provider capabilities"""
            result = {}
            for name, provider in self.providers.items():
                result[name] = {
                    "available": await provider.is_available(),
                    "parameters": provider.get_parameter_schema(),
                    "capabilities": provider.get_capabilities()
                }
            return {"providers": result, "default": self.default_provider}
        
        @router.post("/configure")
        async def configure_tts(provider: str, set_as_default: bool = False):
            """Configure TTS settings"""
            if provider in self.providers:
                if set_as_default:
                    self.default_provider = provider
                return {"success": True, "default_provider": self.default_provider}
            else:
                raise HTTPException(404, f"Provider '{provider}' not available")
        
        return router
```

---

## ⚙️ **Configuration Architecture**

### **New Configuration Structure:**
```toml
# Universal plugins configuration
[plugins.universal_tts]
enabled = true
default_provider = "silero_v3"
fallback_providers = ["pyttsx", "console"]
load_balancing = false
auto_retry = true

# Provider configurations (nested under universal plugin)
[plugins.universal_tts.providers.silero_v3]
enabled = true
model_path = "~/.cache/irene/models/silero_v3"
default_speaker = "xenia"
sample_rate = 48000
torch_device = "cpu"

[plugins.universal_tts.providers.silero_v4]
enabled = false
model_path = "~/.cache/irene/models/silero_v4"
default_speaker = "xenia"
torch_device = "cuda"

[plugins.universal_tts.providers.pyttsx]
enabled = true
voice_rate = 200
voice_volume = 0.9
voice_id = "russian"

[plugins.universal_tts.providers.console]
enabled = true
color_output = true
timing_simulation = true

[plugins.universal_audio]
enabled = true
default_provider = "sounddevice"
concurrent_playback = false

[plugins.universal_audio.providers.sounddevice]
enabled = true
device_id = -1
sample_rate = 44100
channels = 2
buffer_size = 1024

[plugins.universal_audio.providers.audioplayer]
enabled = true
volume = 0.8
fade_in = false
fade_out = true

[plugins.universal_asr]
enabled = true
default_provider = "vosk"
default_language = "ru"
confidence_threshold = 0.7

[plugins.universal_asr.providers.vosk]
enabled = true
model_path_ru = "./models/vosk-model-ru-0.22"
model_path_en = "./models/vosk-model-en-us-0.22"
sample_rate = 16000

[plugins.universal_asr.providers.whisper]
enabled = true
model_size = "base"
device = "cpu"
download_root = "~/.cache/irene/whisper"

[plugins.universal_llm]
enabled = true
default_provider = "openai"
default_task = "improve_speech_recognition"

[plugins.universal_llm.providers.openai]
enabled = true
api_key_env = "OPENAI_API_KEY"
default_model = "gpt-4"
base_url = "https://api.openai.com/v1"
max_tokens = 150
temperature = 0.3

[plugins.universal_llm.providers.anthropic]
enabled = true
api_key_env = "ANTHROPIC_API_KEY"
default_model = "claude-3-haiku"
max_tokens = 150

# Enhanced simple plugins
[plugins.async_timer]
enabled = true
max_concurrent_timers = 10
default_notification_sound = true

[plugins.datetime]
enabled = true
timezone = "Europe/Moscow"
date_format = "%Y-%m-%d"
time_format = "%H:%M:%S"

[plugins.greetings]
enabled = true
multilingual = true
custom_greetings_file = "custom_greetings.json"

[plugins.random]
enabled = true
secure_random = false
max_number = 1000000
```

### **Backward Compatibility (Phase 1-4):**
```toml
# Old format still works during migration
[plugins.silero_v3_tts]
enabled = true
model_path = "~/.cache/irene/models/silero_v3"

# Automatically converted to:
[plugins.universal_tts.providers.silero_v3]
enabled = true
model_path = "~/.cache/irene/models/silero_v3"
```

---

## 🚀 **Implementation Phases**

### **Phase 1: Foundation & TTS Migration** (1-2 weeks) ✅ COMPLETED

#### **Goals:**
- Establish Provider interface pattern
- Migrate TTS plugins to provider pattern
- Create working UniversalTTSPlugin
- Maintain backward compatibility

#### **Detailed Tasks:**

##### **1.1: Create Provider Interfaces** (2 days) ✅ COMPLETED
```bash
# New directory structure:
irene/providers/
├── __init__.py
├── base.py                    # Common provider utilities
├── tts/
│   ├── __init__.py
│   ├── base.py               # TTSProvider interface
│   ├── pyttsx.py             # PyttsTTSProvider
│   ├── silero_v3.py          # SileroV3TTSProvider
│   ├── silero_v4.py          # SileroV4TTSProvider
│   ├── console.py            # ConsoleTTSProvider
│   └── vosk.py               # VoskTTSProvider
├── audio/
│   └── __init__.py           # Prepared for Phase 2
├── asr/
│   └── __init__.py           # Prepared for Phase 4
└── llm/
    └── __init__.py           # Prepared for Phase 4
```

##### **1.2: Convert TTS Plugins to Providers** (3 days) ✅ COMPLETED
```python
# Convert each existing plugin:

# BEFORE: irene/plugins/builtin/silero_v3_tts_plugin.py
class SileroV3TTSPlugin(TTSPlugin): ...

# AFTER: irene/providers/tts/silero_v3.py
class SileroV3TTSProvider(TTSProvider):
    def __init__(self, config: Dict[str, Any]):
        self.model_path = config["model_path"]
        self.default_speaker = config.get("default_speaker", "xenia")
        self.sample_rate = config.get("sample_rate", 48000)
        self.torch_device = config.get("torch_device", "cpu")
        self._model = None
        
    async def is_available(self) -> bool:
        try:
            import torch
            import soundfile
            return Path(self.model_path).exists()
        except ImportError:
            return False
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {
            "speaker": {
                "type": "string", 
                "options": ["aidar", "baya", "xenia", "kseniya"],
                "default": self.default_speaker
            },
            "sample_rate": {
                "type": "integer", 
                "options": [8000, 24000, 48000],
                "default": self.sample_rate
            },
            "torch_device": {
                "type": "string",
                "options": ["cpu", "cuda"],
                "default": self.torch_device
            }
        }
    
    async def speak(self, text: str, **kwargs) -> None:
        speaker = kwargs.get("speaker", self.default_speaker)
        sample_rate = kwargs.get("sample_rate", self.sample_rate)
        # Silero v3 implementation...
```

##### **1.3: Create UniversalTTSPlugin** (3 days) ✅ COMPLETED
```python
# New file: irene/plugins/builtin/universal_tts_plugin.py
class UniversalTTSPlugin(TTSPlugin, WebAPIPlugin, CommandPlugin):
    # Full implementation as shown in template above
```

##### **1.4: Update Configuration & Plugin Loading** (1 day) ✅ COMPLETED
```python
# Update irene/config/models.py
class UniversalTTSConfig(BaseModel):
    enabled: bool = True
    default_provider: str = "pyttsx"
    fallback_providers: List[str] = ["pyttsx", "console"]
    providers: Dict[str, Dict[str, Any]] = {}

# Update irene/core/engine.py
async def _load_builtin_plugins(self) -> None:
    builtin_plugins = [
        CoreCommandsPlugin(),
        UniversalTTSPlugin(),  # NEW
        # Keep old plugins for compatibility (temporary)
        GreetingsPlugin(),
        DateTimePlugin(),
        RandomPlugin(),
        AsyncTimerPlugin()
    ]
```

##### **1.5: Integration Testing** (1 day) ✅ COMPLETED
```python
# Test cases:
class TestUniversalTTSPlugin:
    async def test_provider_loading(self):
        # Test providers load based on config
        
    async def test_speak_delegation(self):
        # Test speaking delegates to correct provider
        
    async def test_web_api_endpoints(self):
        # Test /tts/speak, /tts/providers, /tts/configure
        
    async def test_voice_commands(self):
        # Test "скажи привет голосом ксении"
        
    async def test_fallback_behavior(self):
        # Test fallback when primary provider fails
```

#### **Validation Criteria:**
- ✅ All existing TTS functionality works through UniversalTTSPlugin
- ✅ Web API endpoints (/tts/speak, /tts/providers) work correctly
- ✅ Voice commands for TTS control work ("скажи привет голосом ксении")
- ✅ Provider switching works at runtime
- ✅ Fallback to alternative providers works when primary fails
- ✅ Old plugin configurations still work (backward compatibility)
- ✅ Performance equivalent or better than before

---

### **Phase 2: Audio Migration** (1 week) ✅ COMPLETED

#### **Goals:**
- Migrate audio plugins to provider pattern
- Create UniversalAudioPlugin
- Maintain all existing audio functionality

#### **Detailed Tasks:**

##### **2.1: Create Audio Providers** (3 days) ✅ COMPLETED
```python
# irene/providers/audio/base.py
class AudioProvider(Protocol):
    # Interface definition as shown above

# irene/providers/audio/sounddevice.py
class SoundDeviceAudioProvider(AudioProvider):
    def __init__(self, config: Dict[str, Any]):
        self.device_id = config.get("device_id", -1)
        self.sample_rate = config.get("sample_rate", 44100)
        self.channels = config.get("channels", 2)
        self.buffer_size = config.get("buffer_size", 1024)
        
    async def is_available(self) -> bool:
        try:
            import sounddevice as sd
            return True
        except ImportError:
            return False
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {
            "device_id": {"type": "integer", "default": -1},
            "sample_rate": {"type": "integer", "options": [44100, 48000, 96000]},
            "channels": {"type": "integer", "options": [1, 2]},
            "volume": {"type": "float", "min": 0.0, "max": 1.0}
        }
    
    async def play_file(self, file_path: Path, **kwargs) -> None:
        # sounddevice implementation
        
# Similar implementations for:
# AudioPlayerAudioProvider, AplayAudioProvider, SimpleAudioProvider, ConsoleAudioProvider
```

##### **2.2: Create UniversalAudioPlugin** (2 days) ✅ COMPLETED
```python
# irene/plugins/builtin/universal_audio_plugin.py
class UniversalAudioPlugin(AudioPlugin, WebAPIPlugin, CommandPlugin):
    def __init__(self):
        self.providers: Dict[str, AudioProvider] = {}
        self.default_provider = "sounddevice"
        
    async def initialize(self, core) -> None:
        config = core.config.plugins.universal_audio
        
        provider_classes = {
            "sounddevice": SoundDeviceAudioProvider,
            "audioplayer": AudioPlayerAudioProvider,
            "aplay": AplayAudioProvider,
            "simpleaudio": SimpleAudioProvider,
            "console": ConsoleAudioProvider
        }
        
        # Same pattern as TTS...
    
    def get_router(self) -> APIRouter:
        router = APIRouter()
        
        @router.post("/play")
        async def play_audio(file: UploadFile, provider: Optional[str] = None):
            """Play uploaded audio file"""
            provider_name = provider or self.default_provider
            # Save file and play using specified provider
            
        @router.get("/providers")
        async def list_audio_providers():
            """List available audio backends"""
            
        @router.get("/devices")
        async def list_audio_devices():
            """List available audio devices for current provider"""
            
        return router
```

##### **2.3: Update Configuration & Testing** (2 days) ✅ COMPLETED
```toml
# Add to config schema
[plugins.universal_audio]
enabled = true
default_provider = "sounddevice"
concurrent_playback = false

[plugins.universal_audio.providers.sounddevice]
enabled = true
device_id = -1
sample_rate = 44100
```

#### **Validation Criteria:**
- ✅ All audio backends work through UniversalAudioPlugin
- ✅ Audio playback works for all supported file formats
- ✅ /audio/* API endpoints work correctly
- ✅ Runtime backend switching works
- ✅ Voice commands for audio control work
- ✅ Device discovery and selection works

---

### **Phase 3: Simple Plugin Enhancement** (1 week) ✅ **COMPLETED**

#### **Goals:**
- ✅ Add WebAPIPlugin interface to simple plugins
- ✅ Enhance with web endpoints
- ✅ Keep existing voice functionality intact

#### **Detailed Tasks:**

##### **3.1: Enhance AsyncTimerPlugin** (2 days) ✅ **COMPLETED**
```python
# Extend irene/plugins/builtin/async_timer_plugin.py
class AsyncTimerPlugin(CommandPlugin, WebAPIPlugin):
    def __init__(self):
        # Existing timer functionality
        self.active_timers: Dict[str, Timer] = {}
        
    # Existing CommandPlugin methods...
    
    # NEW: WebAPIPlugin interface
    def get_router(self) -> APIRouter:
        router = APIRouter()
        
        @router.post("/set")
        async def set_timer(duration: int, message: str = "Timer finished!", unit: str = "seconds"):
            """Set a timer via API"""
            timer_id = await self.start_timer_async(duration, message, unit)
            return {
                "timer_id": timer_id, 
                "duration": duration, 
                "unit": unit,
                "message": message,
                "expires_at": datetime.now() + timedelta(seconds=duration)
            }
            
        @router.get("/list")
        async def list_timers():
            """List all active timers"""
            timers = []
            for timer_id, timer in self.active_timers.items():
                timers.append({
                    "id": timer_id,
                    "remaining": timer.remaining_time(),
                    "message": timer.message,
                    "created_at": timer.created_at
                })
            return {"active_timers": timers, "count": len(timers)}
            
        @router.delete("/{timer_id}")
        async def cancel_timer(timer_id: str):
            """Cancel a specific timer"""
            success = await self.cancel_timer_async(timer_id)
            return {"cancelled": success, "timer_id": timer_id}
            
        @router.post("/pause/{timer_id}")
        async def pause_timer(timer_id: str):
            """Pause a running timer"""
            success = await self.pause_timer_async(timer_id)
            return {"paused": success, "timer_id": timer_id}
            
        @router.post("/resume/{timer_id}")
        async def resume_timer(timer_id: str):
            """Resume a paused timer"""
            success = await self.resume_timer_async(timer_id)
            return {"resumed": success, "timer_id": timer_id}
        
        return router
```

##### **3.2: Enhance DateTimePlugin** (1 day) ✅ **COMPLETED**
```python
# Extend irene/plugins/builtin/datetime_plugin.py
class DateTimePlugin(CommandPlugin, WebAPIPlugin):
    # Existing voice commands: "который час", "какое число"
    
    def get_router(self) -> APIRouter:
        router = APIRouter()
        
        @router.get("/current")
        async def get_current_datetime():
            """Get current date and time"""
            now = datetime.now()
            return {
                "datetime": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timezone": str(now.astimezone().tzinfo),
                "weekday": now.strftime("%A"),
                "unix_timestamp": now.timestamp()
            }
            
        @router.get("/format")
        async def format_datetime(timestamp: Optional[float] = None, format_str: str = "%Y-%m-%d %H:%M:%S"):
            """Format datetime with custom format"""
            dt = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()
            return {
                "formatted": dt.strftime(format_str),
                "original": dt.isoformat()
            }
            
        @router.get("/timezone/{timezone_name}")
        async def get_time_in_timezone(timezone_name: str):
            """Get current time in specified timezone"""
            try:
                import pytz
                tz = pytz.timezone(timezone_name)
                now = datetime.now(tz)
                return {
                    "datetime": now.isoformat(),
                    "timezone": timezone_name,
                    "utc_offset": str(now.utcoffset())
                }
            except Exception as e:
                raise HTTPException(400, f"Invalid timezone: {e}")
        
        return router
```

##### **3.3: Enhance Other Simple Plugins** (2 days) ✅ **COMPLETED**
```python
# GreetingsPlugin enhancement
class GreetingsPlugin(CommandPlugin, WebAPIPlugin):
    def get_router(self) -> APIRouter:
        router = APIRouter()
        
        @router.get("/random")
        async def get_random_greeting(language: str = "ru"):
            """Get a random greeting"""
            
        @router.post("/custom")
        async def add_custom_greeting(text: str, language: str = "ru"):
            """Add custom greeting"""
            
        @router.get("/languages")
        async def list_languages():
            """List supported languages"""
            
        return router

# RandomPlugin enhancement  
class RandomPlugin(CommandPlugin, WebAPIPlugin):
    def get_router(self) -> APIRouter:
        router = APIRouter()
        
        @router.post("/number")
        async def random_number(min_val: int = 1, max_val: int = 100):
            """Generate random number"""
            
        @router.post("/choice")
        async def random_choice(options: List[str]):
            """Choose randomly from options"""
            
        @router.post("/coin")
        async def coin_flip():
            """Flip a coin"""
            
        @router.post("/dice")
        async def roll_dice(sides: int = 6, count: int = 1):
            """Roll dice"""
            
        return router
```

##### **3.4: API Documentation & Testing** (2 days) ✅ **COMPLETED**
```python
# Integration tests
class TestSimplePluginAPIs:
    async def test_timer_api_endpoints(self):
        # Test all timer endpoints
        
    async def test_datetime_api_endpoints(self):
        # Test datetime formatting and timezone handling
        
    async def test_voice_and_api_parity(self):
        # Ensure voice commands and API provide same functionality
```

#### **Validation Criteria:**
- ✅ All existing voice commands still work unchanged
- ✅ New web APIs provide equivalent functionality to voice commands
- ✅ API documentation is auto-generated and accurate
- ✅ Can use timer/datetime/random functionality via both voice and web
- ✅ Error handling is consistent between voice and web interfaces

#### **Implementation Summary:**
- ✅ **AsyncTimerPlugin Enhanced**: Added comprehensive WebAPI with `/set`, `/list`, `/pause`, `/resume`, `/cancel` endpoints
- ✅ **DateTimePlugin Enhanced**: Added WebAPI with `/current`, `/format`, `/timezone/{name}`, `/timezones` endpoints  
- ✅ **GreetingsPlugin Enhanced**: Added WebAPI with `/random`, `/custom`, `/list`, `/languages`, `/stats` endpoints
- ✅ **RandomPlugin Enhanced**: Added WebAPI with `/coin`, `/dice`, `/number`, `/choice` endpoints
- ✅ **Full Feature Parity**: Voice commands and web APIs provide equivalent functionality
- ✅ **Backward Compatibility**: All existing voice functionality preserved
- ✅ **Proper Error Handling**: Comprehensive validation and error responses in APIs
- ✅ **OpenAPI Documentation**: Auto-generated docs with proper schemas and examples

---

### **Phase 4: New Capabilities** (1.5-2 weeks) ✅ **COMPLETED**

#### **Goals:**
- ✅ Add ASR universal plugin with providers (clean separation from input layer)
- ✅ Add LLM universal plugin with providers (including separate VseGPT provider)
- ✅ Enable audio streaming and AI enhancement
- ✅ Refactor MicrophoneInput to pure audio capture
- ✅ Migrate text normalizers to processing pipeline utilities
- ✅ Add ElevenLabs TTS provider

#### **Detailed Tasks:**

##### **4.1: ASR Infrastructure** (1 week)

**Key Architectural Decision**: Move ASR completely out of input layer to Universal Plugin for proper separation of concerns.

**Current State Analysis**: 
- ✅ MicrophoneInput already has excellent VOSK implementation
- ✅ Audio capture and device management already working  
- ❌ ASR mixed with input responsibilities (violation of separation of concerns)
- ❌ Only microphone can use ASR (no web upload, file processing, streaming)

**Target State**: Clean separation where Input Layer handles audio capture, Plugin Layer handles ASR processing.

###### **ASR Providers** (2 days) ✅ **Following ABC Pattern**
```python
# irene/providers/asr/base.py
from abc import ABC, abstractmethod

class ASRProvider(ABC):
    """Abstract base class for speech recognition implementations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    async def is_available(self) -> bool:
        pass
    
    @abstractmethod
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        pass
    
    @abstractmethod
    def get_parameter_schema(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        pass

# irene/providers/asr/vosk.py
class VoskASRProvider(ASRProvider):
    """VOSK ASR Provider - extracted from MicrophoneInput"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)  # Proper ABC inheritance
        self.model_paths = config.get("model_paths", {})
        self.default_language = config.get("default_language", "ru")
        self.sample_rate = config.get("sample_rate", 16000)
        self.confidence_threshold = config.get("confidence_threshold", 0.7)
        self._models = {}  # Lazy-loaded models
        
    async def is_available(self) -> bool:
        try:
            import vosk
            # Check if at least one model exists
            return any(Path(path).exists() for path in self.model_paths.values())
        except ImportError:
            return False
    
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        """Transcribe audio using VOSK - code moved from MicrophoneInput"""
        language = kwargs.get("language", self.default_language)
        confidence_threshold = kwargs.get("confidence_threshold", self.confidence_threshold)
        
        # Load model for language if not already loaded
        if language not in self._models:
            await self._load_model(language)
        
        # VOSK transcription implementation (reuse existing logic)
        recognizer = vosk.KaldiRecognizer(self._models[language], self.sample_rate)
        
        if recognizer.AcceptWaveform(audio_data):
            result = json.loads(recognizer.Result())
            text = result.get("text", "")
            confidence = result.get("confidence", 0.0)
            
            if confidence >= confidence_threshold:
                return text.strip()
        
        return ""
    
    def get_supported_languages(self) -> List[str]:
        return list(self.model_paths.keys())
    
    def get_supported_formats(self) -> List[str]:
        return ["wav", "raw", "pcm"]

# irene/providers/asr/whisper.py
class WhisperASRProvider(ASRProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_size = config.get("model_size", "base")
        self.device = config.get("device", "cpu")
        self.download_root = config.get("download_root", "~/.cache/irene/whisper")
        self._model = None
        
    async def is_available(self) -> bool:
        try:
            import whisper
            return True
        except ImportError:
            return False
    
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        if not self._model:
            import whisper
            self._model = whisper.load_model(self.model_size)
        
        # Convert audio_data to temporary file
        # Whisper transcription implementation
        result = self._model.transcribe(temp_audio_file)
        return result["text"].strip()
    
    def get_supported_languages(self) -> List[str]:
        return ["en", "ru", "es", "fr", "de", "it", "ja", "ko", "zh", "auto"]
    
    def get_supported_formats(self) -> List[str]:
        return ["wav", "mp3", "m4a", "flac", "ogg", "wma"]

# irene/providers/asr/google_cloud.py  
class GoogleCloudASRProvider(ASRProvider):
    """Google Cloud Speech-to-Text Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.credentials_path = config.get("credentials_path")
        self.project_id = config.get("project_id")
        self.default_language = config.get("default_language", "ru-RU")
        
    async def is_available(self) -> bool:
        try:
            from google.cloud import speech
            return self.credentials_path and Path(self.credentials_path).exists()
        except ImportError:
            return False
```

###### **UniversalASRPlugin** (2 days) ✅ **Following ABC Pattern**
```python
# irene/plugins/builtin/universal_asr_plugin.py
from typing import Dict, Any, List, Optional, AsyncIterator
from pathlib import Path
import json
import time
import base64

from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from ...core.interfaces.plugin import PluginInterface
from ...core.interfaces.webapi import WebAPIPlugin
from ...core.interfaces.command import CommandPlugin
from ...core.context import Context
from ...core.commands import CommandResult

# Import all ASR providers using ABC pattern
from ...providers.asr import (
    ASRProvider,
    VoskASRProvider,
    WhisperASRProvider,
    GoogleCloudASRProvider
)

class UniversalASRPlugin(PluginInterface, WebAPIPlugin, CommandPlugin):
    """
    Universal ASR Plugin - Speech Recognition Coordinator
    
    Manages multiple ASR providers and provides:
    - Unified web API (/asr/*)
    - Voice commands for ASR control
    - Multi-source audio processing (microphone, web, files)
    - Provider switching and fallbacks
    """
    
    def __init__(self):
        super().__init__()
        self.providers: Dict[str, ASRProvider] = {}  # Proper ABC type hint
        self.default_provider = "vosk"
        self.default_language = "ru"
        
        # Provider class mapping
        self._provider_classes = {
            "vosk": VoskASRProvider,
            "whisper": WhisperASRProvider,
            "google_cloud": GoogleCloudASRProvider,
        }
        
    @property
    def name(self) -> str:
        return "universal_asr"
    
    @property 
    def version(self) -> str:
        return "1.0.0"
        
    async def initialize(self, core) -> None:
        """Initialize ASR providers from configuration"""
        config = core.config.plugins.universal_asr
        
        # Initialize enabled providers with ABC error handling
        providers_config = config.get("providers", {})
        
        for provider_name, provider_class in self._provider_classes.items():
            provider_config = providers_config.get(provider_name, {})
            if provider_config.get("enabled", False):
                try:
                    provider = provider_class(provider_config)
                    if await provider.is_available():
                        self.providers[provider_name] = provider
                        logger.info(f"Loaded ASR provider: {provider_name}")
                    else:
                        logger.warning(f"ASR provider {provider_name} not available (dependencies missing)")
                except TypeError as e:
                    logger.error(f"ASR provider {provider_name} missing required abstract methods: {e}")
                except Exception as e:
                    logger.warning(f"Failed to load ASR provider {provider_name}: {e}")
    
    # Primary ASR interface - used by input sources
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        """
        Core ASR functionality - transcribe audio to text
        
        Args:
            audio_data: Raw audio bytes
            provider: ASR provider to use (default: self.default_provider)
            language: Language code (default: self.default_language)
            **kwargs: Provider-specific parameters
            
        Returns:
            Transcribed text
        """
        provider_name = kwargs.get("provider", self.default_provider)
        language = kwargs.get("language", self.default_language)
        
        if provider_name not in self.providers:
            raise HTTPException(404, f"ASR provider '{provider_name}' not available")
        
        provider = self.providers[provider_name]
        return await provider.transcribe_audio(audio_data, language=language, **kwargs)
    
    # CommandPlugin interface - voice control
    def get_triggers(self) -> List[str]:
        """Get command triggers for ASR control"""
        return [
            "распознай", "транскрибируй", "переключись на", "покажи распознавание",
            "язык", "качество", "микрофон", "запись"
        ]
    
    async def can_handle(self, command: str, context: Context) -> bool:
        """Check if this command is ASR-related"""
        triggers = self.get_triggers()
        command_lower = command.lower()
        return any(trigger in command_lower for trigger in triggers)
    
    async def handle_command(self, command: str, context: Context) -> CommandResult:
        """Handle ASR voice commands"""
        if "покажи распознавание" in command or "покажи провайдеры" in command:
            info = self._get_providers_info()
            return CommandResult(success=True, response=info)
        elif "переключись на" in command:
            # "переключись на whisper"
            new_provider = self._parse_provider_name(command)
            if new_provider in self.providers:
                self.default_provider = new_provider
                return CommandResult(success=True, response=f"Переключился на {new_provider}")
        elif "язык" in command:
            # Handle language switching commands
            pass
            
        return CommandResult(success=False, error="Неизвестная команда распознавания")
    
    # WebAPIPlugin interface - unified API
    def get_router(self) -> APIRouter:
        router = APIRouter()
        
        @router.post("/transcribe")
        async def transcribe_audio_file(
            audio: UploadFile = File(...),
            provider: Optional[str] = None,
            language: str = "ru",
            enhance: bool = False
        ):
            """Transcribe uploaded audio file - NEW CAPABILITY!"""
            provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            # Read and transcribe audio
            audio_data = await audio.read()
            text = await self.transcribe_audio(
                audio_data, provider=provider_name, language=language
            )
            
            # Optional LLM enhancement
            if enhance and text.strip():
                # Get LLM plugin and enhance text
                llm_plugin = self.core.plugin_manager.get_plugin("universal_llm")
                if llm_plugin:
                    enhanced_text = await llm_plugin.enhance_text(
                        text, task="improve_speech_recognition"
                    )
                    return {
                        "original_text": text,
                        "enhanced_text": enhanced_text,
                        "provider": provider_name,
                        "language": language
                    }
            
            return {
                "text": text,
                "provider": provider_name,
                "language": language
            }
        
        @router.websocket("/stream")
        async def stream_transcription(websocket: WebSocket):
            """WebSocket endpoint for real-time ASR - NEW CAPABILITY!"""
            await websocket.accept()
            
            try:
                while True:
                    # Receive audio chunk
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    if message["type"] == "audio_chunk":
                        # Decode and process audio
                        audio_data = base64.b64decode(message["data"])
                        
                        # Transcribe chunk
                        text = await self.transcribe_audio(
                            audio_data, 
                            language=message.get("language", self.default_language)
                        )
                        
                        if text.strip():
                            # Send result back
                            response = {
                                "type": "transcription_result",
                                "text": text,
                                "timestamp": time.time()
                            }
                            await websocket.send_text(json.dumps(response))
                            
            except WebSocketDisconnect:
                logger.info("ASR WebSocket client disconnected")
        
        @router.get("/providers")
        async def list_asr_providers():
            """Discovery endpoint for all ASR provider capabilities"""
            result = {}
            for name, provider in self.providers.items():
                result[name] = {
                    "available": await provider.is_available(),
                    "parameters": provider.get_parameter_schema(),
                    "languages": provider.get_supported_languages(),
                    "formats": provider.get_supported_formats()
                }
            return {"providers": result, "default": self.default_provider}
        
        @router.post("/configure")
        async def configure_asr(provider: str, set_as_default: bool = False):
            """Configure ASR settings"""
            if provider in self.providers:
                if set_as_default:
                    self.default_provider = provider
                return {"success": True, "default_provider": self.default_provider}
            else:
                raise HTTPException(404, f"Provider '{provider}' not available")
        
        return router
```

###### **MicrophoneInput Refactoring** (1 day) - Clean Separation
```python
# REFACTOR: irene/inputs/microphone.py
class MicrophoneInput(InputSource):
    """
    REFACTORED: Pure audio capture input source
    
    Responsibilities changed:
    - BEFORE: Audio capture + VOSK ASR processing
    - AFTER: Audio capture only, delegates ASR to UniversalASRPlugin
    """
    
    def __init__(self, asr_plugin: Optional[Any] = None, device_id: Optional[int] = None,
                 samplerate: int = 16000, blocksize: int = 8000):
        # Remove VOSK-specific parameters - now handled by ASR plugin
        self.device_id = device_id
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.asr_plugin = asr_plugin  # Injected ASR plugin
        self._listening = False
        self._audio_queue = None
        self._audio_stream = None
        
        # Check for audio dependencies only
        try:
            import sounddevice as sd  # type: ignore
            self._sd_available = True
        except ImportError as e:
            logger.warning(f"Audio input dependencies not available: {e}")
            self._sd_available = False
    
    def is_available(self) -> bool:
        """Check if audio capture is available"""
        return self._sd_available
    
    async def start_listening(self) -> None:
        """Initialize and start audio capture (NO VOSK loading)"""
        if not self.is_available():
            raise ComponentNotAvailable("Audio dependencies (sounddevice) not available")
            
        try:
            import sounddevice as sd  # type: ignore
            
            # Audio device setup only - no VOSK model loading
            if self.device_id is not None:
                device_info = sd.query_devices(self.device_id, 'input')
                if self.samplerate is None:
                    self.samplerate = int(device_info['default_samplerate'])
            
            # Initialize audio queue
            self._audio_queue = queue.Queue()
            
            # Set up audio callback (unchanged)
            def audio_callback(indata, frames, time, status):
                if status:
                    logger.warning(f"Audio status: {status}")
                if self._listening and self._audio_queue:
                    self._audio_queue.put(bytes(indata))
            
            # Create audio stream
            self._audio_stream = sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                device=self.device_id,
                dtype='int16',
                channels=1,
                callback=audio_callback
            )
            
            # Start listening
            self._listening = True
            self._audio_stream.start()
            
            logger.info(f"Audio capture started - Device: {self.device_id or 'default'}, "
                       f"Sample rate: {self.samplerate} Hz")
            
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            await self._cleanup()
            raise ComponentNotAvailable(f"Audio initialization failed: {e}")
    
    async def listen(self) -> AsyncIterator[str]:
        """
        REFACTORED: Audio capture → ASR processing separation
        
        Now: Audio capture → UniversalASRPlugin → Text commands
        """
        if not self._listening or not self._audio_queue:
            return
            
        logger.info("Starting audio capture with ASR processing...")
        
        while self._listening:
            try:
                # Get audio data from queue
                try:
                    data = await asyncio.to_thread(self._audio_queue.get, timeout=1.0)
                except queue.Empty:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process audio with ASR plugin (NEW: clean separation)
                if self.asr_plugin:
                    text = await self.asr_plugin.transcribe_audio(data)
                    if text.strip():
                        logger.info(f"Speech recognized: '{text}'")
                        yield text
                else:
                    logger.warning("No ASR plugin available - audio captured but not processed")
                
            except Exception as e:
                logger.error(f"Error in audio processing: {e}")
                await asyncio.sleep(0.1)
```

###### **WebInput Enhancement** (1 day) - Audio Processing Support
```python
# ENHANCE: irene/inputs/web.py  
class WebInput(InputSource):
    async def handle_websocket_message(self, websocket, message_data: str) -> None:
        """ENHANCED: Handle both text and audio messages"""
        try:
            message = json.loads(message_data)
            
            # Existing text command handling
            if message.get("type") == "command":
                command = message.get("command", "").strip()
                if command:
                    await self.send_command(command)
                    
            # NEW: Audio chunk handling via ASR plugin
            elif message.get("type") == "audio_chunk":
                await self._handle_audio_chunk(websocket, message)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _handle_audio_chunk(self, websocket, message: dict) -> None:
        """NEW: Process audio chunk using ASR plugin"""
        try:
            # Get ASR plugin from core
            asr_plugin = self.core.plugin_manager.get_plugin("universal_asr")
            if not asr_plugin:
                raise ComponentNotAvailable("ASR plugin not available")
            
            # Decode base64 audio
            audio_data = base64.b64decode(message["data"])
            language = message.get("language", "ru")
            enhance = message.get("enhance", False)
            
            # Transcribe audio using ASR plugin
            text = await asr_plugin.transcribe_audio(
                audio_data, language=language
            )
            
            if text.strip():
                # Optional LLM enhancement
                if enhance:
                    llm_plugin = self.core.plugin_manager.get_plugin("universal_llm")
                    if llm_plugin:
                        enhanced_text = await llm_plugin.enhance_text(text)
                        text = enhanced_text
                
                # Send transcribed text as command
                await self.send_command(text.strip())
                
                # Send result back to client
                response = {
                    "type": "transcription_result",
                    "original_audio_size": len(audio_data),
                    "transcribed_text": text,
                    "enhanced": enhance,
                    "success": True
                }
                await websocket.send_text(json.dumps(response))
                
        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            error_response = {
                "type": "error",
                "success": False,
                "error": str(e)
            }
            await websocket.send_text(json.dumps(error_response))
```

###### **Integration & Testing** (1 day)
```python
class TestUniversalASRPlugin:
    async def test_audio_file_transcription(self):
        """Test file upload and transcription via web API"""
        
    async def test_web_audio_streaming(self):
        """Test WebSocket audio streaming"""
        
    async def test_microphone_integration(self):
        """Test microphone → ASR plugin integration"""
        
    async def test_provider_switching(self):
        """Test switching between VOSK and Whisper"""
        
    async def test_multi_language_support(self):
        """Test different languages across providers"""
```

##### **4.2: Text Processing Pipeline Migration** (2 days)

**Key Insight**: Text normalizers are NOT plugins - they are text processing utilities that should be part of the processing pipeline.

###### **Migrate Normalizers to Utilities** (1 day)
```python
# irene/utils/text_processing.py - ENHANCED
class TextProcessor:
    """Unified text processing pipeline for ASR, LLM, and TTS stages"""
    
    def __init__(self):
        self.normalizers = [
            NumberNormalizer(),      # "123" → "сто двадцать три"
            PrepareNormalizer(),     # Latin→Cyrillic, symbols cleanup
            RunormNormalizer()       # Advanced Russian normalization
        ]
        
    async def process_pipeline(self, text: str, stage: str = "general") -> str:
        """Apply normalizers based on processing stage"""
        processed_text = text
        
        for normalizer in self.normalizers:
            if normalizer.applies_to_stage(stage):
                processed_text = await normalizer.normalize(processed_text)
                
        return processed_text

# Extract functionality from existing plugins:
class NumberNormalizer:
    """Extracted from plugin_normalizer_numbers.py"""
    def applies_to_stage(self, stage: str) -> bool:
        return stage in ["asr_output", "general", "tts_input"]
        
    async def normalize(self, text: str) -> str:
        # Move core.all_num_to_text() functionality here
        return self._convert_numbers_to_text(text)

class PrepareNormalizer:
    """Extracted from plugin_normalizer_prepare.py"""
    def applies_to_stage(self, stage: str) -> bool:
        return stage in ["tts_input", "general"]
        
    async def normalize(self, text: str) -> str:
        # Latin→Cyrillic transcription, symbol replacement, etc.
        text = self._transcribe_latin_to_cyrillic(text)
        text = self._replace_symbols(text)
        return text

class RunormNormalizer:
    """Extracted from plugin_normalizer_runorm.py"""
    def applies_to_stage(self, stage: str) -> bool:
        return stage in ["tts_input"]
        
    async def normalize(self, text: str) -> str:
        # Advanced Russian text normalization
        return self._advanced_russian_normalization(text)
```

###### **Integration with ASR/LLM Pipeline** (1 day)
```python
# Update UniversalASRPlugin to use text processing
class UniversalASRPlugin:
    def __init__(self):
        self.text_processor = TextProcessor()
        
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        # ASR processing
        raw_text = await provider.transcribe_audio(audio_data, **kwargs)
        
        # Text processing pipeline
        processed_text = await self.text_processor.process_pipeline(
            raw_text, stage="asr_output"
        )
        
        return processed_text

# Update UniversalLLMPlugin for LLM → TTS pipeline
class UniversalLLMPlugin:
    def __init__(self):
        self.text_processor = TextProcessor()
        
    async def enhance_text(self, text: str, task: str = "improve", **kwargs) -> str:
        # LLM enhancement
        enhanced = await provider.enhance_text(text, task=task, **kwargs)
        
        # Prepare for TTS if needed
        if task == "improve_for_tts":
            enhanced = await self.text_processor.process_pipeline(
                enhanced, stage="tts_input"
            )
            
        return enhanced

# Integration in core processing
async def process_audio_command(audio_data: bytes) -> str:
    # Audio → ASR (with text processing)
    text = await asr_plugin.transcribe_audio(audio_data)
    
    # Optional: ASR → LLM enhancement
    if llm_enhancement_enabled:
        text = await llm_plugin.enhance_text(text, task="improve_speech_recognition")
    
    # Final text processing for command execution
    final_text = await text_processor.process_pipeline(text, stage="command_input")
    
    return final_text
```

##### **4.3: LLM Infrastructure** (4 days)

###### **LLM Providers** (2 days) ✅ **Following ABC Pattern**
```python
# irene/providers/llm/openai.py
class OpenAILLMProvider(LLMProvider):
    """Official OpenAI LLM Provider"""
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)  # Proper ABC inheritance
        self.api_key = os.getenv(config["api_key_env"])
        self.base_url = "https://api.openai.com/v1"
        self.default_model = config.get("default_model", "gpt-4")
        self.max_tokens = config.get("max_tokens", 150)
        self.temperature = config.get("temperature", 0.3)
        
    async def is_available(self) -> bool:
        return self.api_key is not None
    
    async def enhance_text(self, text: str, task: str = "improve", **kwargs) -> str:
        model = kwargs.get("model", self.default_model)
        
        prompts = {
            "improve_speech_recognition": "You are an assistant that fixes speech recognition errors. Fix the following text while preserving its meaning:",
            "grammar_correction": "Fix grammar and punctuation in the following text:",
            "translation": "Translate the following text to {target_language}:",
        }
        
        system_prompt = prompts.get(task, prompts["improve_speech_recognition"])
        if task == "translation":
            system_prompt = system_prompt.format(target_language=kwargs.get("target_language", "English"))
        
        # OpenAI API call
        import openai
        client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
        
        return response.choices[0].message.content.strip()

# irene/providers/llm/vsegpt.py
class VseGPTLLMProvider(LLMProvider):
    """VseGPT LLM Provider - OpenAI-compatible API with different endpoint"""
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)  # Proper ABC inheritance
        self.api_key = os.getenv(config["api_key_env"])
        self.base_url = "https://api.vsegpt.ru/v1"
        self.default_model = config.get("default_model", "openai/gpt-4o-mini")
        self.max_tokens = config.get("max_tokens", 150)
        self.temperature = config.get("temperature", 0.3)
        
    async def is_available(self) -> bool:
        return self.api_key is not None
    
    async def enhance_text(self, text: str, task: str = "improve", **kwargs) -> str:
        # Same implementation as OpenAI but with VseGPT endpoint
        model = kwargs.get("model", self.default_model)
        
        prompts = {
            "improve_speech_recognition": "You are an assistant that fixes speech recognition errors. Fix the following text while preserving its meaning:",
            "grammar_correction": "Fix grammar and punctuation in the following text:",
            "translation": "Translate the following text to {target_language}:",
        }
        
        system_prompt = prompts.get(task, prompts["improve_speech_recognition"])
        if task == "translation":
            system_prompt = system_prompt.format(target_language=kwargs.get("target_language", "English"))
        
        # VseGPT API call (OpenAI-compatible)
        import openai
        client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
        
        return response.choices[0].message.content.strip()

# irene/providers/llm/anthropic.py
class AnthropicLLMProvider(LLMProvider):
    # Similar implementation for Anthropic Claude

# irene/providers/llm/local_llama.py
class LocalLlamaLLMProvider(LLMProvider):
    # Local Llama implementation using llama.cpp or similar
```

###### **UniversalLLMPlugin** (2 days) ✅ **Following ABC Pattern**
```python
# irene/plugins/builtin/universal_llm_plugin.py
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException
from ...core.interfaces.plugin import PluginInterface
from ...core.interfaces.webapi import WebAPIPlugin
from ...core.interfaces.command import CommandPlugin
from ...core.context import Context
from ...core.commands import CommandResult

# Import all LLM providers using ABC pattern
from ...providers.llm import (
    LLMProvider,
    OpenAILLMProvider,
    VseGPTLLMProvider,
    AnthropicLLMProvider,
    LocalLlamaLLMProvider
)

class UniversalLLMPlugin(PluginInterface, CommandPlugin, WebAPIPlugin):
    def __init__(self):
        super().__init__()
        self.providers: Dict[str, LLMProvider] = {}  # Proper ABC type hint
        self.default_provider = "openai"
        self.default_task = "improve"
        
        # Provider class mapping
        self._provider_classes = {
            "openai": OpenAILLMProvider,
            "vsegpt": VseGPTLLMProvider,
            "anthropic": AnthropicLLMProvider,
            "local_llama": LocalLlamaLLMProvider
        }
        
    async def initialize(self, core) -> None:
        config = core.config.plugins.universal_llm
        
        # Initialize enabled providers with ABC error handling
        providers_config = config.get("providers", {})
        
        for provider_name, provider_class in self._provider_classes.items():
            provider_config = providers_config.get(provider_name, {})
            if provider_config.get("enabled", False):
                try:
                    provider = provider_class(provider_config)
                    if await provider.is_available():
                        self.providers[provider_name] = provider
                        logger.info(f"Loaded LLM provider: {provider_name}")
                    else:
                        logger.warning(f"LLM provider {provider_name} not available (dependencies missing)")
                except TypeError as e:
                    logger.error(f"LLM provider {provider_name} missing required abstract methods: {e}")
                except Exception as e:
                    logger.warning(f"Failed to load LLM provider {provider_name}: {e}")
    
    # CommandPlugin interface - voice control
    def get_triggers(self) -> List[str]:
        """Get command triggers for LLM control"""
        return [
            "улучши", "исправь", "переведи", "переформулируй", "проверь",
            "чат", "ответь", "объясни", "переключись на"
        ]
    
    async def can_handle(self, command: str, context: Context) -> bool:
        """Check if this command is LLM-related"""
        triggers = self.get_triggers()
        command_lower = command.lower()
        return any(trigger in command_lower for trigger in triggers)
    
    async def handle_command(self, command: str, context: Context) -> CommandResult:
        """Handle LLM voice commands"""
        # LLM command handling implementation
        pass
    
    def get_router(self) -> APIRouter:
        router = APIRouter()
        
        @router.post("/enhance")
        async def enhance_text(
            text: str,
            task: str = "improve",
            provider: Optional[str] = None,
            **kwargs
        ):
            """Enhance text using LLM"""
            provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            enhanced = await self.providers[provider_name].enhance_text(
                text, task=task, **kwargs
            )
            
            return {
                "original_text": text,
                "enhanced_text": enhanced,
                "task": task,
                "provider": provider_name
            }
        
        @router.post("/chat")
        async def chat_completion(
            messages: List[Dict[str, str]],
            provider: Optional[str] = None,
            **kwargs
        ):
            """Chat completion"""
            provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            response = await self.providers[provider_name].chat_completion(
                messages, **kwargs
            )
            
            return {
                "response": response,
                "provider": provider_name
            }
            
        return router
```

##### **4.4: ElevenLabs TTS Provider Enhancement** (1 day)

###### **Add ElevenLabs TTS Provider** (1 day) ✅ **Following ABC Pattern**
```python
# irene/providers/tts/elevenlabs.py
from typing import Dict, Any, List
import os
import httpx
from pathlib import Path

class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs TTS Provider - High-quality neural voice synthesis"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)  # Proper ABC inheritance
        self.api_key = os.getenv(config["api_key_env"])
        self.voice_id = config.get("voice_id", "default")
        self.model = config.get("model", "eleven_monolingual_v1")
        self.stability = config.get("stability", 0.5)
        self.similarity_boost = config.get("similarity_boost", 0.5)
        self.base_url = "https://api.elevenlabs.io/v1"
        
    async def is_available(self) -> bool:
        """Check if ElevenLabs API is available"""
        if not self.api_key:
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/voices",
                    headers={"xi-api-key": self.api_key},
                    timeout=5.0
                )
                return response.status_code == 200
        except Exception:
            return False
    
    async def speak(self, text: str, **kwargs) -> None:
        """Generate and play speech using ElevenLabs"""
        voice_id = kwargs.get("voice_id", self.voice_id)
        stability = kwargs.get("stability", self.stability)
        similarity_boost = kwargs.get("similarity_boost", self.similarity_boost)
        
        # Generate audio
        audio_data = await self._generate_audio(
            text, voice_id, stability, similarity_boost
        )
        
        # Play using audio plugin
        if hasattr(self, 'audio_plugin') and self.audio_plugin:
            # Save to temporary file and play
            temp_file = Path("/tmp/elevenlabs_output.mp3")
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            await self.audio_plugin.play_file(temp_file)
    
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """Generate audio file using ElevenLabs"""
        voice_id = kwargs.get("voice_id", self.voice_id)
        stability = kwargs.get("stability", self.stability)
        similarity_boost = kwargs.get("similarity_boost", self.similarity_boost)
        
        audio_data = await self._generate_audio(
            text, voice_id, stability, similarity_boost
        )
        
        with open(output_path, "wb") as f:
            f.write(audio_data)
    
    async def _generate_audio(self, text: str, voice_id: str, 
                            stability: float, similarity_boost: float) -> bytes:
        """Call ElevenLabs API to generate audio"""
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost
            }
        }
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.content
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for ElevenLabs-specific parameters"""
        return {
            "voice_id": {
                "type": "string",
                "description": "ElevenLabs voice ID",
                "default": self.voice_id
            },
            "stability": {
                "type": "float",
                "min": 0.0,
                "max": 1.0,
                "description": "Voice stability (0-1)",
                "default": self.stability
            },
            "similarity_boost": {
                "type": "float", 
                "min": 0.0,
                "max": 1.0,
                "description": "Voice similarity boost (0-1)",
                "default": self.similarity_boost
            },
            "model": {
                "type": "string",
                "options": ["eleven_monolingual_v1", "eleven_multilingual_v1"],
                "default": self.model
            }
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities"""
        return {
            "languages": ["en", "ru", "es", "fr", "de", "it", "pt", "pl"],
            "formats": ["mp3"],
            "quality": "high",
            "real_time": True,
            "custom_voices": True
        }
    
    def get_provider_name(self) -> str:
        return "elevenlabs"

# Update UniversalTTSPlugin to include ElevenLabs
class UniversalTTSPlugin:
    def __init__(self):
        # ... existing code ...
        self._provider_classes = {
            "pyttsx": PyttsTTSProvider,
            "silero_v3": SileroV3TTSProvider,
            "silero_v4": SileroV4TTSProvider,
            "vosk_tts": VoskTTSProvider,
            "console": ConsoleTTSProvider,
            "elevenlabs": ElevenLabsTTSProvider,  # NEW
        }
```

###### **Configuration for ElevenLabs** (Include in config schema)
```toml
[plugins.universal_tts.providers.elevenlabs]
enabled = true
api_key_env = "ELEVENLABS_API_KEY"
voice_id = "21m00Tcm4TlvDq8ikWAM"  # Default voice
model = "eleven_monolingual_v1"
stability = 0.5
similarity_boost = 0.5
```

##### **4.5: Integration & Configuration** (2 days)

###### **Input Manager Integration** (1 day)
```python
# UPDATE: irene/inputs/base.py
class InputManager:
    async def _discover_input_sources(self) -> None:
        """UPDATED: Inject ASR plugin into microphone input"""
        try:
            # Add CLI input (always available)
            from .cli import CLIInput
            cli_input = CLIInput()
            await self.add_source("cli", cli_input)
            
            # Try to add microphone input with ASR plugin injection
            try:
                from .microphone import MicrophoneInput
                
                # Get ASR plugin from core
                asr_plugin = None
                if hasattr(self.component_manager, 'core'):
                    asr_plugin = self.component_manager.core.plugin_manager.get_plugin("universal_asr")
                
                mic_input = MicrophoneInput(asr_plugin=asr_plugin)
                if mic_input.is_available():
                    await self.add_source("microphone", mic_input)
            except (ImportError, ComponentNotAvailable) as e:
                logger.info(f"Microphone input not available: {e}")
                
            # Try to add web input with core reference for ASR
            try:
                from .web import WebInput
                web_input = WebInput()
                web_input.core = self.component_manager.core  # Inject core reference
                if web_input.is_available():
                    await self.add_source("web", web_input)
            except (ImportError, ComponentNotAvailable) as e:
                logger.info(f"Web input not available: {e}")
                
        except Exception as e:
            logger.error(f"Error discovering input sources: {e}")
```

###### **Configuration Schema** (1 day)
```toml
# NEW: Configuration for ASR and LLM plugins
[plugins.universal_asr]
enabled = true
default_provider = "vosk"
default_language = "ru"
confidence_threshold = 0.7

[plugins.universal_asr.providers.vosk]
enabled = true
model_paths = {ru = "./models/vosk-model-ru-0.22", en = "./models/vosk-model-en-us-0.22"}
sample_rate = 16000
confidence_threshold = 0.7

[plugins.universal_asr.providers.whisper]
enabled = false
model_size = "base"
device = "cpu"
download_root = "~/.cache/irene/whisper"

[plugins.universal_asr.providers.google_cloud]
enabled = false
credentials_path = "path/to/credentials.json"
project_id = "your-project-id"
default_language = "ru-RU"

[plugins.universal_llm]
enabled = true
default_provider = "openai"
default_task = "improve_speech_recognition"

# Separate LLM providers
[plugins.universal_llm.providers.openai]
enabled = true
api_key_env = "OPENAI_API_KEY"
default_model = "gpt-4"
max_tokens = 150
temperature = 0.3

[plugins.universal_llm.providers.vsegpt]
enabled = false
api_key_env = "VSEGPT_API_KEY"
default_model = "openai/gpt-4o-mini"
max_tokens = 150
temperature = 0.3

[plugins.universal_llm.providers.anthropic]
enabled = false
api_key_env = "ANTHROPIC_API_KEY"
default_model = "claude-3-haiku"
max_tokens = 150

# Text processing configuration
[text_processing]
enabled = true
stages = ["asr_output", "tts_input", "command_input", "general"]

[text_processing.normalizers.numbers]
enabled = true
stages = ["asr_output", "general", "tts_input"]

[text_processing.normalizers.prepare]
enabled = true
stages = ["tts_input", "general"]
latin_to_cyrillic = true
symbol_replacement = true

[text_processing.normalizers.runorm]
enabled = true
stages = ["tts_input"]
advanced_normalization = true
```

##### **4.4: Full Pipeline Testing** (1 day)
```python
class TestFullAudioPipeline:
    async def test_microphone_to_command_pipeline(self):
        """Test: Microphone → Audio Capture → ASR → Command Processing"""
        
    async def test_web_audio_upload_pipeline(self):
        """Test: File Upload → ASR → Command Processing"""
        
    async def test_web_audio_streaming_pipeline(self):
        """Test: WebSocket Audio Stream → ASR → Real-time Commands"""
        
    async def test_audio_with_llm_enhancement(self):
        """Test: Audio → ASR → LLM Enhancement → Enhanced Command"""
        
    async def test_multi_provider_functionality(self):
        """Test: Different ASR and LLM provider combinations"""
        
    async def test_error_handling_and_fallbacks(self):
        """Test: Error handling when providers fail"""
```

#### **Validation Criteria:**
- ✅ **Clean Architecture**: ASR moved completely out of input layer to Universal Plugin
- ✅ **Multiple Audio Sources**: Microphone, web upload, and streaming all use same ASR
- ✅ **File Upload Transcription**: Can upload audio files via web API and get transcription
- ✅ **Real-time Streaming**: WebSocket audio streaming with live transcription
- ✅ **Provider Flexibility**: Can switch between VOSK, Whisper, Google Cloud providers
- ✅ **LLM Enhancement**: ASR → LLM pipeline improves transcription quality
- ✅ **VseGPT Integration**: Separate VseGPT provider for alternative LLM services
- ✅ **Text Processing Pipeline**: Normalizers properly integrated in ASR/LLM/TTS workflow
- ✅ **ElevenLabs TTS**: High-quality neural voice synthesis working via UniversalTTSPlugin
- ✅ **Voice Commands**: Can control ASR, LLM, and TTS settings via voice
- ✅ **Web API Completeness**: Full REST API for all ASR, LLM, and enhanced TTS functionality
- ✅ **Error Handling**: Robust error handling when providers fail
- ✅ **Backward Compatibility**: Existing microphone and TTS functionality preserved
- ✅ **Configuration Driven**: Provider selection and settings via config files

#### **Architectural Benefits Achieved:**

**🏗️ Clean Separation of Concerns:**
```
BEFORE: MicrophoneInput[Audio Capture + VOSK ASR] → Text Commands
AFTER:  MicrophoneInput[Audio Capture] → UniversalASRPlugin[Multi-Provider ASR] → Text Commands
```

**🎯 Universal ASR Access:**
```
✅ Microphone Audio    → UniversalASRPlugin → Commands
✅ Web Upload Audio    → UniversalASRPlugin → Commands  
✅ WebSocket Streaming → UniversalASRPlugin → Commands
✅ File Processing     → UniversalASRPlugin → Commands
```

**🔧 Enhanced Capabilities:**
- **ASR Provider Flexibility**: Switch between VOSK, Whisper, Google Cloud at runtime
- **LLM Provider Options**: OpenAI, VseGPT, Anthropic, Local models
- **Multi-Language Support**: Different providers for different languages
- **Full Audio Pipeline**: ASR → Text Processing → LLM → Enhanced Text → TTS/Commands
- **Text Processing Pipeline**: Automatic number conversion, symbol normalization, Russian text processing
- **High-Quality TTS**: ElevenLabs neural voice synthesis alongside existing providers
- **Rich Web API**: Full REST endpoints for all ASR, LLM, and TTS functionality
- **Real-time Streaming**: WebSocket support for live audio processing

**📊 Performance & Reliability:**
- **Lazy Loading**: ASR providers load only when needed
- **Error Isolation**: Failed ASR provider doesn't break audio capture
- **Graceful Fallbacks**: Automatic fallback to alternative providers
- **Resource Optimization**: Shared models across multiple audio sources

---

### **Phase 5: Cleanup & Optimization** (5 days) ✅ **COMPLETED**

#### **Goals:**
- ✅ Remove old plugin implementations
- ✅ Optimize configuration structure  
- ✅ Performance improvements
- ✅ Documentation updates

#### **Detailed Tasks:**

##### **5.1: Remove Legacy Plugins** (2 days) ✅ **COMPLETED**
```bash
# Files deleted:
✅ irene/plugins/builtin/silero_v3_tts_plugin.py
✅ irene/plugins/builtin/silero_v4_tts_plugin.py
✅ irene/plugins/builtin/pyttsx_tts_plugin.py
✅ irene/plugins/builtin/console_tts_plugin.py
✅ irene/plugins/builtin/vosk_tts_plugin.py
✅ irene/plugins/builtin/sounddevice_audio_plugin.py
✅ irene/plugins/builtin/audioplayer_audio_plugin.py
✅ irene/plugins/builtin/aplay_audio_plugin.py
✅ irene/plugins/builtin/simpleaudio_audio_plugin.py
✅ irene/plugins/builtin/console_audio_plugin.py

# Updated plugin loading
✅ irene/plugins/builtin/__init__.py - Removed legacy plugin references
```

##### **5.2: Configuration Migration Tool** (2 days) ✅ **COMPLETED**
```python
# ✅ Created tools/migrate_to_universal_plugins.py
class ConfigMigrator:
    """Tool to migrate old plugin configs to new universal format"""
    
    ✅ Auto-migration of TTS and audio plugins
    ✅ Backup creation for safety
    ✅ Dry-run mode for preview
    ✅ Directory batch processing
    ✅ Comprehensive error handling
    ✅ Migration validation and reporting

# CLI tool usage:
✅ python tools/migrate_to_universal_plugins.py config.toml
✅ python tools/migrate_to_universal_plugins.py --directory ~/.config/irene/
✅ python tools/migrate_to_universal_plugins.py --dry-run config.toml
```

##### **5.3: Performance Optimization** (2 days) ✅ **COMPLETED**
```python
# ✅ Provider lazy loading optimization
class UniversalTTSPlugin:
    async def _load_provider_lazy(self, provider_name: str) -> TTSProvider:
        """Load provider only when first used"""
        ✅ Lazy loading implementation
        ✅ Provider caching
        ✅ Runtime provider loading

# ✅ Model caching optimization
class SileroV3TTSProvider:
    _model_cache: Dict[str, Any] = {}  # Class-level cache
    ✅ Shared model cache across instances
    ✅ Cache key generation (model_path:device)
    ✅ Thread-safe cache access

# ✅ Concurrent initialization
class UniversalTTSPlugin:
    async def _initialize_providers_concurrent(self) -> None:
        """Initialize providers concurrently for better performance"""
        ✅ Parallel provider initialization
        ✅ Asyncio.gather for concurrent loading
        ✅ Exception handling for failed providers
```

##### **5.4: Documentation & Examples** (1 day) ✅ **COMPLETED**
```markdown
# ✅ Complete documentation structure created:
docs/
├── plugins/
│   ✅ universal_tts.md         # Comprehensive TTS plugin documentation
│   ✅ migration_guide.md       # Complete migration guide
└── examples/
    ✅ tts_provider_example.py   # Full custom provider example with ABC inheritance

# ✅ Documentation includes:
- Architecture overview with Universal Plugin pattern
- Complete configuration examples  
- API reference with request/response examples
- Voice command documentation
- Troubleshooting guides
- Performance optimization tips
- Migration instructions with before/after examples
- Custom provider development guide
```

#### **Validation Criteria:**
- ✅ **No legacy plugin code remains in codebase** - All 10 legacy plugin files removed
- ✅ **Configuration migration tool works correctly** - Comprehensive tool with dry-run, backup, batch processing
- ✅ **Performance improvements implemented** - Lazy loading, model caching, concurrent initialization
- ✅ **Memory usage optimized** - Shared model cache, lazy provider loading
- ✅ **Documentation complete and accurate** - Full documentation suite with examples
- ✅ **Migration guide helps users upgrade seamlessly** - Step-by-step guide with troubleshooting
- ✅ **All functionality preserved after cleanup** - Universal plugins provide full feature parity

#### **Implementation Summary:**
- ✅ **Legacy Plugin Removal**: Cleaned up 10 legacy TTS and audio plugin files, updated import system
- ✅ **Migration Tool**: Created comprehensive migration tool with auto-detection, backup, and validation
- ✅ **Performance Optimizations**: Added lazy loading, model caching, and concurrent initialization to Universal plugins
- ✅ **Documentation Suite**: Complete documentation including API reference, migration guide, and development examples
- ✅ **ABC Inheritance**: All optimizations follow proper ABC inheritance pattern with type safety
- ✅ **Error Handling**: Robust error handling and graceful fallbacks throughout
- ✅ **Configuration Validation**: Migration tool validates and reports configuration changes

#### **Performance Improvements Achieved:**
- **🚀 Faster Startup**: Lazy loading reduces initial load time
- **💾 Memory Efficiency**: Shared model cache prevents duplicate model loading
- **⚡ Concurrent Loading**: Parallel provider initialization when lazy loading disabled
- **🔄 Runtime Flexibility**: Dynamic provider loading on demand
- **📊 Better Resource Usage**: Optimized model caching for Silero providers

---

## 🧪 **Testing Strategy**

### **Test Categories:**

#### **1. Unit Tests**
```python
# Test each provider independently
class TestSileroV3TTSProvider:
    async def test_initialization(self):
    async def test_speak_functionality(self):
    async def test_parameter_validation(self):
    async def test_error_handling(self):

# Test universal plugins
class TestUniversalTTSPlugin:
    async def test_provider_loading(self):
    async def test_provider_delegation(self):
    async def test_fallback_behavior(self):
    async def test_web_api_endpoints(self):
```

#### **2. Integration Tests**
```python
class TestPluginIntegration:
    async def test_voice_command_to_api_consistency(self):
    async def test_provider_switching(self):
    async def test_cross_plugin_communication(self):
    async def test_configuration_changes(self):
```

#### **3. End-to-End Tests**
```python
class TestFullPipeline:
    async def test_audio_upload_to_response(self):
    async def test_voice_command_pipeline(self):
    async def test_web_api_workflows(self):
    async def test_error_recovery(self):
```

#### **4. Performance Tests**
```python
class TestPerformance:
    async def test_provider_loading_time(self):
    async def test_concurrent_requests(self):
    async def test_memory_usage(self):
    async def test_response_times(self):
```

### **Continuous Validation:**
- Automated testing after each phase
- Performance regression detection
- Configuration validation
- API contract testing

---

## ⚠️ **Risk Mitigation**

### **1. Backward Compatibility**
```python
# During Phases 1-4: Support both old and new configs
class ConfigManager:
    def load_config(self) -> Config:
        config = self._load_raw_config()
        
        # Auto-migrate old format if detected
        if self._has_old_plugin_format(config):
            config = self._auto_migrate_config(config)
            logger.info("Auto-migrated old plugin configuration")
            
        return config
```

### **2. Feature Flags**
```toml
[plugins.universal_tts]
enabled = true
use_legacy_compatibility = true  # Can switch back if issues
provider_lazy_loading = true     # Can disable for debugging
concurrent_initialization = true # Can disable if stability issues
```

### **3. Rollback Strategy**
```bash
# Git branches for each phase
git checkout phase-1-foundation    # If phase 2 has issues
git checkout phase-2-audio         # If phase 3 has issues
git checkout phase-3-enhancement   # If phase 4 has issues
git checkout phase-4-capabilities  # If phase 5 has issues

# Emergency rollback to old system
git checkout pre-refactor-backup
```

### **4. Monitoring & Validation**
```python
# Health checks for each phase
class PluginHealthChecker:
    async def validate_phase_1(self) -> bool:
        # Verify TTS functionality works
        
    async def validate_phase_2(self) -> bool:
        # Verify audio functionality works
        
    async def validate_performance(self) -> bool:
        # Check that performance hasn't regressed
```

---

## 📅 **Timeline & Milestones**

### **Detailed Schedule:**
```
Week 1-2: Phase 1 - Foundation & TTS Migration
├── Day 1-2: Provider interfaces and infrastructure
├── Day 3-5: TTS provider conversion
├── Day 6-8: UniversalTTSPlugin implementation  
├── Day 9-10: Configuration and testing
└── Milestone: Working unified TTS system

Week 3: Phase 2 - Audio Migration
├── Day 1-3: Audio provider implementations
├── Day 4-5: UniversalAudioPlugin implementation
├── Day 6-7: Testing and validation
└── Milestone: Unified audio system

Week 4: Phase 3 - Simple Plugin Enhancement
├── Day 1-2: Timer plugin web API enhancement
├── Day 3: DateTime plugin web API
├── Day 4-5: Other simple plugins (greetings, random)
├── Day 6-7: API documentation and testing
└── Milestone: All plugins have web APIs

Week 5-6: Phase 4 - New Capabilities  
├── Week 5, Day 1-5: ASR Infrastructure (1 week)
│   ├── Day 1-2: ASR Providers (VOSK, Whisper, Google Cloud)
│   ├── Day 3-4: UniversalASRPlugin + Input Refactoring  
│   └── Day 5: Integration & Testing
├── Week 6, Day 1-2: Text Processing Pipeline Migration (2 days)
│   ├── Day 1: Migrate normalizers to utilities (Numbers, Prepare, Runorm)
│   └── Day 2: Integration with ASR/LLM pipeline
├── Week 6, Day 3-6: LLM Infrastructure (4 days)
│   ├── Day 3-4: LLM Providers (OpenAI, VseGPT, Anthropic, Local)
│   ├── Day 5: UniversalLLMPlugin Implementation
│   └── Day 6: LLM Enhancement Pipeline
├── Week 6, Day 7: ElevenLabs TTS Provider (1 day)
│   └── Add ElevenLabs provider to UniversalTTSPlugin
├── Week 7, Day 1-2: Integration & Testing (2 days)
│   ├── Day 1: Configuration, Input Manager updates
│   └── Day 2: Full pipeline testing
└── Milestone: Complete ASR + LLM + Enhanced TTS audio processing pipeline

Week 7, Day 3-7: Phase 5 - Cleanup & Optimization
├── Day 3-4: Remove legacy code
├── Day 5-6: Configuration migration tools & Performance optimization
├── Day 7: Documentation and examples
└── Final Milestone: Production-ready system
```

### **Success Metrics:**
- **Functionality**: All existing features work through new system
- **Performance**: Equal or better response times
- **API Coverage**: 100% feature parity between voice and web
- **Configuration**: Successful migration from old format
- **Documentation**: Complete API docs and migration guide

---

## 🎯 **Expected Benefits**

### **0. ABC Inheritance Benefits** ✅ **IMPLEMENTED**
- **Type Safety**: Python enforces interface compliance at class definition time
- **Runtime Validation**: Missing abstract methods cause immediate TypeError
- **Better IDE Support**: Autocomplete, error detection, and IntelliSense
- **Clear Contracts**: Explicit inheritance shows relationships between classes
- **Development Experience**: Easier to understand, extend, and debug
- **Future-Proof**: Consistent patterns for all provider implementations

### **1. Architectural Improvements**
- **Reduced complexity**: 8 plugins instead of 14+
- **Clear separation**: Universal plugins coordinate, providers implement
- **Unified APIs**: Consistent web interfaces across all functionality
- **Better testability**: Isolated providers, mockable interfaces

### **2. Developer Experience**
- **Easier extension**: Add new providers by implementing ABC interfaces with proper inheritance
- **Better debugging**: Clear component boundaries, error isolation, and ABC validation
- **Cleaner configuration**: Hierarchical, typed configuration
- **Improved documentation**: Auto-generated API docs with proper type hints
- **Type Safety**: ABC inheritance provides compile-time and runtime validation

### **3. User Experience**
- **Consistent interfaces**: Same patterns across all functionality
- **Feature parity**: Voice and web access to all features
- **Better reliability**: Graceful fallbacks and error handling
- **Enhanced capabilities**: Audio streaming, AI enhancement

### **4. Operational Benefits**
- **Easier deployment**: Configuration-driven component selection
- **Better monitoring**: Health checks and provider status
- **Simplified maintenance**: Fewer plugin interactions
- **Performance optimization**: Lazy loading, caching, concurrency

---

## 📚 **References & Dependencies**

### **External Dependencies:**
```toml
# Core dependencies (existing)
fastapi = ">=0.100.0"
uvicorn = ">=0.20.0"
pydantic = ">=2.0.0"
asyncio-mqtt = ">=0.13.0"

# Provider dependencies (optional)
torch = ">=1.10.0"           # For Silero TTS
whisper = ">=1.0.0"          # For Whisper ASR
vosk = ">=0.3.45"           # For VOSK ASR
openai = ">=1.0.0"          # For OpenAI LLM
anthropic = ">=0.18.0"      # For Anthropic LLM
sounddevice = ">=0.4.0"     # For audio I/O
soundfile = ">=0.12.0"      # For audio processing
```

### **Configuration Schema:**
- Full TOML schema for all universal plugins
- Validation rules for provider configurations
- Migration mappings from old to new format

### **API Documentation:**
- OpenAPI 3.0 schemas for all endpoints
- Example requests and responses
- Error code documentation

This implementation plan provides a comprehensive roadmap for transforming the Irene Voice Assistant plugin architecture into a modern, scalable, and maintainable system. The phased approach ensures minimal risk while delivering incremental value at each stage. 