# Irene Voice Assistant v14 - Configuration Guide

This document explains how to configure Irene Voice Assistant v14 with the new clean architecture that provides clear separation of concerns and intuitive configuration patterns.

## 🎯 Overview

The v14 configuration architecture provides:

- **Clean separation of concerns**: System, Input, Component, and Workflow configurations
- **Intuitive TOML structure**: Direct mapping to logical system architecture  
- **Environment variable integration**: Secure handling of API keys and paths
- **Asset management**: Unified model and cache storage via `IRENE_ASSETS_ROOT`
- **Automatic v13 migration**: Seamless upgrade from legacy configurations

## 🚀 Quick Start

1. **Copy the master configuration:**
   ```bash
   cp configs/config-master.toml config.toml
   ```

2. **Set environment variables:**
   ```bash
   # Asset management (recommended)
   export IRENE_ASSETS_ROOT="/data/irene"
   
   # API keys for cloud providers
   export OPENAI_API_KEY="your_openai_key_here"
   export ELEVENLABS_API_KEY="your_elevenlabs_key_here"
   export ANTHROPIC_API_KEY="your_anthropic_key_here"
   ```

3. **Customize for your needs:**
   - Enable/disable components based on your use case
   - Configure only the providers you plan to use
   - Set deployment-specific system capabilities

4. **Run Irene:**
   ```bash
   uv run python -m irene.runners.webapi --config config.toml
   ```

## 📋 v14 Architecture Overview

### **Core Configuration Structure**
```toml
# Core assistant settings
name = "Irene"
version = "14.0.0"
language = "en-US"

# System capabilities (what your hardware/environment supports)
[system]
microphone_enabled = true
web_api_enabled = true

# Input sources (how users interact)
[inputs]
microphone = true
web = true
default_input = "microphone"

# Components (processing capabilities)
[components]
tts = true          # Text-to-Speech
audio = true        # Audio output
asr = false         # Speech recognition (optional)

# Workflows (processing pipelines)
[workflows]
enabled = ["voice_assistant"]
default = "voice_assistant"

# Asset management (unified storage)
[assets]
assets_root = "${IRENE_ASSETS_ROOT}"
```

## 🔧 Configuration Sections

### **1. Core Settings**
```toml
name = "Irene"                      # Assistant name
version = "14.0.0"                  # Configuration version
debug = false                       # Debug mode
log_level = "INFO"                  # Logging level
language = "en-US"                  # Primary language
timezone = "UTC"                    # System timezone
```

### **2. System Capabilities**
```toml
[system]
# Hardware capabilities
microphone_enabled = true           # System has microphone
audio_playback_enabled = true      # System can play audio

# Service capabilities  
web_api_enabled = true             # Enable REST API server
web_port = 8000                    # API server port
metrics_enabled = false            # Prometheus metrics
```

### **3. Input Sources**
```toml
[inputs]
microphone = true                  # Accept voice input
web = true                         # Accept web/API input
cli = false                        # Accept command-line input
default_input = "microphone"       # Primary input method
```

### **4. Processing Components**

#### **Enable Components Based on Use Case:**
```toml
[components]
# Core components
tts = true                         # Text-to-Speech output
audio = true                       # Audio playback

# Optional components
asr = false                        # Speech recognition
llm = false                        # Language model
voice_trigger = false              # Wake word detection
nlu = false                        # Natural language understanding
text_processor = false             # Text processing
intent_system = false              # Intent handling
```

### **5. Component-Specific Configuration**

#### **Text-to-Speech (TTS)**
```toml
[tts]
default_provider = "elevenlabs"
fallback_providers = ["console"]

[tts.providers.elevenlabs]
enabled = true
voice = "Rachel"
model = "eleven_multilingual_v2"
api_key = "${ELEVENLABS_API_KEY}"

[tts.providers.console]
enabled = true                     # Fallback for testing
```

#### **Audio Output**
```toml
[audio]
default_provider = "sounddevice"
fallback_providers = ["console"]

[audio.providers.sounddevice]
enabled = true
sample_rate = 22050
channels = 1

[audio.providers.console]
enabled = true                     # Text output for testing
```

#### **Speech Recognition (ASR)**
```toml
[asr]
default_provider = "whisper"
fallback_providers = []

[asr.providers.whisper]
enabled = true
model = "base"
language = "en"
api_key = "${OPENAI_API_KEY}"

[asr.providers.vosk]
enabled = false
model_name = "vosk-model-en-us-0.22"
```

#### **Voice Trigger (Wake Words)**
```toml
[voice_trigger]
default_provider = "openwakeword"
wake_words = ["irene"]

[voice_trigger.providers.openwakeword]
enabled = true
model_paths = {}                   # Uses IRENE_ASSETS_ROOT/models
inference_framework = "onnx"

[voice_trigger.providers.microwakeword]
enabled = false
model_paths = {}                   # Uses IRENE_ASSETS_ROOT/models
feature_buffer_size = 49
```

### **6. Workflows**
```toml
[workflows]
enabled = ["voice_assistant"]      # Active workflow pipelines
default = "voice_assistant"        # Primary workflow

[workflows.voice_assistant]
# Workflow-specific settings
auto_listen = true
context_timeout = 300
```

### **7. Asset Management**
```toml
[assets]
assets_root = "${IRENE_ASSETS_ROOT}"   # Base directory for all assets
auto_download = true                   # Download models automatically
cache_enabled = true                   # Enable model caching
cleanup_on_startup = false           # Clean temp files on startup
```

## 🎛️ Common Deployment Scenarios

### **1. Full Voice Assistant**
```toml
# Complete voice interaction system
[system]
microphone_enabled = true
audio_playback_enabled = true
web_api_enabled = true

[inputs]
microphone = true
web = true
default_input = "microphone"

[components]
tts = true
audio = true
asr = true
llm = true
voice_trigger = true
intent_system = true

[workflows]
enabled = ["voice_assistant"]
default = "voice_assistant"
```

### **2. API-Only Server**
```toml
# Headless server for API clients
[system]
microphone_enabled = false
audio_playback_enabled = false
web_api_enabled = true
web_port = 8080

[inputs]
microphone = false
web = true
cli = false
default_input = "web"

[components]
tts = true
audio = false
asr = true
llm = true
voice_trigger = false
```

### **3. Development/Testing**
```toml
# Console-based testing setup
[system]
microphone_enabled = false
audio_playback_enabled = false

[inputs]
cli = true
default_input = "cli"

[components]
tts = true
audio = true

# Use console providers for testing
[tts.providers.console]
enabled = true

[audio.providers.console]
enabled = true
```

### **4. Minimal Voice Output**
```toml
# Simple TTS-only system
[system]
audio_playback_enabled = true

[inputs]
web = true
default_input = "web"

[components]
tts = true
audio = true
# All other components disabled (false)
```

## 🔑 Environment Variables

Set these environment variables for secure configuration:

```bash
# Asset Management (highly recommended)
export IRENE_ASSETS_ROOT="/data/irene"

# Cloud Provider API Keys
export OPENAI_API_KEY="sk-..."
export ELEVENLABS_API_KEY="..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"

# Optional: Override default asset locations
export IRENE_MODELS_ROOT="/data/models"
export IRENE_CACHE_ROOT="/data/cache"
export IRENE_CREDENTIALS_ROOT="/data/credentials"
```

## 🔄 Migration from v13

v14 automatically migrates v13 configurations:

### **Automatic Changes:**
- `[plugins.universal_*]` → `[*]` (component sections)
- `[components.enabled]` lists → boolean fields
- Legacy boolean flags → proper component structure

### **Manual Updates Needed:**
- Move API keys to environment variables
- Update asset paths to use `IRENE_ASSETS_ROOT`
- Review provider configurations for new options

### **Migration Example:**
```toml
# v13 (legacy)
[components]
enabled = ["tts", "audio"]

[plugins.universal_tts]
default_provider = "elevenlabs"

# v14 (new)
[components]
tts = true
audio = true

[tts]
default_provider = "elevenlabs"
```

## 🧪 Configuration Validation

### **1. Syntax Validation:**
```bash
# Check TOML syntax
uv run python -c "
import tomllib
with open('config.toml', 'rb') as f:
    config = tomllib.load(f)
print('✅ TOML syntax valid')
"
```

### **2. Schema Validation:**
```bash
# Validate against v14 schema
uv run python -c "
from irene.config.manager import ConfigManager
from pathlib import Path
import asyncio

async def validate():
    manager = ConfigManager()
    config = await manager.load_config(Path('config.toml'))
    print('✅ Configuration schema valid')
    print(f'Assistant: {config.name}')
    print(f'Enabled components: {[k for k, v in config.components.model_dump().items() if v]}')

asyncio.run(validate())
"
```

### **3. Provider Discovery Test:**
```bash
# Test that enabled providers are discoverable
uv run python -c "
from irene.config.manager import ConfigManager
from pathlib import Path
import asyncio

async def test_discovery():
    manager = ConfigManager()
    config = await manager.load_config(Path('config.toml'))
    
    # Test TTS providers
    if config.components.tts:
        enabled_tts = [name for name, cfg in config.tts.providers.items() if cfg.get('enabled', False)]
        print(f'Enabled TTS providers: {enabled_tts}')
    
    print('✅ Provider discovery working')

asyncio.run(test_discovery())
"
```

## 📚 Key Differences from v13

### **Architectural Improvements:**
1. **Clean separation**: System ≠ Input ≠ Component ≠ Workflow
2. **Intuitive naming**: `[tts]` instead of `[plugins.universal_tts]`
3. **Boolean components**: `tts = true` instead of `enabled = ["tts"]`
4. **Environment integration**: `${VAR}` support for sensitive data
5. **Asset unification**: Single `IRENE_ASSETS_ROOT` for all models

### **Configuration Benefits:**
- **Easier to understand**: Logical structure matches system architecture
- **Faster to configure**: Less nested sections and clearer names
- **More secure**: API keys in environment variables
- **Better organized**: Each concern has its own configuration section

### **Compatibility:**
- **Automatic migration**: v13 configs are converted to v14 automatically
- **Deprecation warnings**: Legacy patterns show helpful migration hints
- **Backward compatibility**: Existing deployments continue working during transition

## ⚠️ Important Notes

- **Always use environment variables for API keys** - never put secrets in config files
- **Set `IRENE_ASSETS_ROOT`** to control where models and cache are stored
- **Component dependencies**: Some components require others (e.g., voice_assistant workflow needs TTS and Audio)
- **Provider fallbacks**: Always configure console providers as fallbacks for testing
- **Asset management**: Models are automatically downloaded to `IRENE_ASSETS_ROOT/models`

## 🎯 Performance Tips

1. **Disable unused components**: Saves memory and startup time
2. **Use local providers**: Vosk/Silero are faster than API-based providers
3. **Configure asset caching**: Improves model loading performance
4. **Optimize workflow settings**: Adjust timeouts based on your use case

## 📖 Further Reading

- **Migration Guide**: `docs/config_cleanup.md` - Complete v13 to v14 migration details
- **Asset Management**: `docs/ASSET_MANAGEMENT.md` - Unified storage system
- **Component Architecture**: `docs/architecture.md` - System design overview
- **Provider Documentation**: Individual provider configuration guides
- **Workflow Configuration**: Custom pipeline creation and management