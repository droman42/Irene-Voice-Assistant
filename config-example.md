# Irene Voice Assistant - Configuration Example Guide

This document explains how to use the `config-example.toml` file to configure Irene Voice Assistant v13 with entry-points based dynamic discovery and configuration-driven provider filtering.

## 🎯 Overview

The `config-example.toml` demonstrates all configuration capabilities implemented in Irene Voice Assistant v13, including:

- **Entry-points based dynamic discovery**: Providers loaded via setuptools entry-points
- **Configuration-driven filtering**: Only enabled providers are discovered and loaded
- **Modular component system**: Enable/disable entire subsystems
- **Comprehensive provider settings**: All 19 providers across 5 categories configured
- **Deployment scenarios**: Examples for different use cases

## 🚀 Quick Start

1. **Copy the example configuration:**
   ```bash
   cp config-example.toml config.toml
   ```

2. **Edit for your needs:**
   - Set API keys in environment variables (see `.env` section)
   - Enable/disable components and providers as needed
   - Adjust provider-specific settings

3. **Set environment variables:**
   ```bash
   cp docs/env-example.txt .env
   # Edit .env with your API keys and paths
   ```

4. **Run Irene:**
   ```bash
   uv run python -m irene.runners.webapi --config config.toml
   ```

## 📋 Configuration Structure

### Core System
```toml
[core]
name = "Irene"           # Assistant name
debug = false            # Debug mode
log_level = "INFO"       # Logging level
language = "en-US"       # Primary language
```

### Component System (Entry-Points Discovery)
```toml
[components]
enabled = ["audio", "tts", "asr", "llm", "voice_trigger"]
disabled = ["nlu", "text_processor"]
```
**Result**: Only enabled components are discovered via entry-points and loaded.

### Provider Configuration (Configuration-Driven Filtering)
```toml
[plugins.universal_tts.providers.elevenlabs]
enabled = true           # This provider will be discovered
voice = "Rachel"
model = "eleven_multilingual_v2"

[plugins.universal_tts.providers.pyttsx]
enabled = false          # This provider will be skipped
```
**Result**: Only `elevenlabs` is discovered and loaded for TTS.

## 🔧 Configuration Sections

### 1. Asset Management
```toml
[assets]
models_root = "./models"
cache_root = "./cache"
data_root = "./data"
credentials_root = "./credentials"
```
**Purpose**: Unified storage for all models, cache, and credentials across providers.

### 2. Component System
```toml
[components]
enabled = ["audio", "tts", "asr", "llm", "voice_trigger"]
disabled = ["nlu", "text_processor"]
```
**Purpose**: Enable/disable entire subsystems. Disabled components are not loaded.

### 3. Provider Configurations

#### Audio Output Providers
- **console**: Text-based audio simulation
- **sounddevice**: High-quality audio via sounddevice 
- **audioplayer**: Cross-platform audio playback
- **aplay**: Linux ALSA audio
- **simpleaudio**: Simple audio playback

#### Text-to-Speech Providers
- **console**: Text output for testing
- **elevenlabs**: High-quality neural TTS (API key required)
- **pyttsx**: Cross-platform TTS
- **silero_v3/v4**: Neural TTS models
- **vosk_tts**: TTS from Vosk

#### Speech Recognition Providers
- **vosk**: Offline speech recognition
- **whisper**: OpenAI Whisper (API key required)
- **google_cloud**: Google Cloud Speech (credentials required)

#### Language Model Providers
- **openai**: GPT models (API key required)
- **anthropic**: Claude models (API key required)
- **vsegpt**: Alternative LLM provider (API key required)

#### Voice Trigger Providers
- **openwakeword**: Open-source wake word detection
- **microwakeword**: Lightweight TensorFlow Lite models

### 4. Security & Advanced Settings
```toml
[security]
enable_auth = false
cors_origins = ["*"]

[development]
auto_reload = false
verbose_logging = false

[logging]
level = "INFO"
file_logging = false
```

## 🎛️ Configuration-Driven Filtering in Action

The example demonstrates how configuration drives provider discovery:

### Example: TTS Configuration
```toml
[plugins.universal_tts]
default_provider = "elevenlabs"
fallback_providers = ["console"]

[plugins.universal_tts.providers.console]
enabled = true                    # ← Will be discovered

[plugins.universal_tts.providers.elevenlabs]
enabled = true                    # ← Will be discovered
voice = "Rachel"

[plugins.universal_tts.providers.pyttsx]
enabled = false                   # ← Will be skipped

[plugins.universal_tts.providers.silero_v3]
enabled = false                   # ← Will be skipped
```

**Result**: Only `console` and `elevenlabs` providers are discovered via entry-points, loaded, and available for use. The other providers are completely skipped.

### Verification
You can verify the filtering works:
```bash
uv run python -c "
import tomllib
from irene.utils.loader import dynamic_loader

with open('config.toml', 'rb') as f:
    config = tomllib.load(f)

tts_config = config['plugins']['universal_tts']['providers']
enabled = [name for name, cfg in tts_config.items() if cfg.get('enabled', False)]
discovered = dynamic_loader.discover_providers('irene.providers.tts', enabled)

print('Enabled in config:', enabled)
print('Discovered by entry-points:', list(discovered.keys()))
"
```

## 🚀 Deployment Scenarios

### 1. Full Voice Assistant
```toml
[components]
enabled = ["audio", "tts", "asr", "llm", "voice_trigger"]

[plugins.universal_tts.providers.elevenlabs]
enabled = true

[plugins.universal_asr.providers.whisper]
enabled = true

[plugins.voice_trigger.providers.openwakeword]
enabled = true
```

### 2. API-Only Server
```toml
[components]
enabled = ["tts", "asr", "llm"]
disabled = ["audio", "voice_trigger"]

[components.web]
host = "0.0.0.0"
port = 8080

[inputs]
enabled = ["web"]
disabled = ["microphone"]
```

### 3. CLI-Only Testing
```toml
[components]
enabled = []

[inputs]
enabled = ["cli"]

[plugins.universal_tts.providers.console]
enabled = true
```

### 4. Development Mode
```toml
[development]
auto_reload = true
verbose_logging = true
test_mode = true

[logging]
level = "DEBUG"

# Enable console providers for all components
[plugins.universal_tts.providers.console]
enabled = true
[plugins.universal_audio.providers.console]
enabled = true
```

## 🔑 Environment Variables

Create a `.env` file with your API keys:
```bash
# Required for cloud providers
OPENAI_API_KEY=your_openai_key_here
ELEVENLABS_API_KEY=your_elevenlabs_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GOOGLE_APPLICATION_CREDENTIALS=/path/to/google-credentials.json

# Asset management (optional)
IRENE_MODELS_ROOT=/data/models
IRENE_CACHE_ROOT=/data/cache
IRENE_CREDENTIALS_ROOT=/data/credentials
```

## 🧪 Testing Your Configuration

1. **Validate TOML syntax:**
   ```bash
   uv run python -c "import tomllib; tomllib.load(open('config.toml', 'rb'))"
   ```

2. **Test provider discovery:**
   ```bash
   uv run python -c "
   from irene.utils.loader import dynamic_loader
   tts = dynamic_loader.discover_providers('irene.providers.tts')
   print('Available TTS providers:', list(tts.keys()))
   "
   ```

3. **Test configuration filtering:**
   ```bash
   uv run python -c "
   import tomllib
   from irene.utils.loader import dynamic_loader
   
   with open('config.toml', 'rb') as f:
       config = tomllib.load(f)
   
   # Test TTS filtering
   tts_providers = config['plugins']['universal_tts']['providers']
   enabled = [name for name, cfg in tts_providers.items() if cfg.get('enabled', False)]
   discovered = dynamic_loader.discover_providers('irene.providers.tts', enabled)
   
   print('Config enables:', enabled)
   print('Discovery finds:', list(discovered.keys()))
   print('Filtering works:', enabled == list(discovered.keys()))
   "
   ```

## 📚 Related Documentation

- **Entry-Points Architecture**: See `docs/TODO.md` for implementation details
- **Provider Documentation**: See `docs/plugins/` for provider-specific guides
- **Environment Setup**: See `docs/env-example.txt` for all environment variables
- **Asset Management**: See `docs/ASSET_MANAGEMENT.md` for unified storage
- **Voice Trigger**: See `docs/voice_trigger.md` for wake word configuration

## 🔄 Migration from Previous Versions

If upgrading from older versions:

1. **Replace hardcoded configurations** with entry-points discovery
2. **Update provider sections** to use the new `enabled` pattern
3. **Use unified asset management** instead of provider-specific paths
4. **Set API keys in environment variables** instead of config files

The configuration system automatically handles backward compatibility for most settings while providing warnings for deprecated patterns.

## ⚠️ Important Notes

- **Provider filtering happens at discovery time**: Disabled providers are never loaded
- **External packages work automatically**: Third-party entry-points are discovered
- **API keys should be in environment variables**: Never put secrets in config files  
- **Asset paths are unified**: All providers use the same model/cache directories
- **Components can be completely disabled**: Saves memory and startup time

## 🎯 Performance Benefits

With configuration-driven filtering:
- **Faster startup**: Only enabled providers are loaded
- **Lower memory usage**: Disabled providers never instantiated  
- **Selective builds**: Ready for TODO #3 minimal container builds
- **Development efficiency**: Easy to test with minimal configurations 