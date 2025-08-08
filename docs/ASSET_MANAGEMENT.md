# Asset Management System

The Irene Voice Assistant includes a centralized asset management system for handling models, cache files, and credentials. This system provides unified storage locations that work seamlessly with Docker deployments.

**Enhanced in TODO #4 Phase 2 with configuration-driven provider asset management.**

## Overview

The asset management system provides:
1. **Unified root directories** for models, cache, and credentials
2. **Environment variable configuration** for easy Docker deployment
3. **Provider-driven asset configuration** with intelligent defaults and TOML overrides
4. **Automatic model downloading** and caching
5. **Centralized credential management**
6. **External provider extensibility** via configuration

## Configuration-Driven Asset Management (NEW)

Starting with TODO #4 Phase 2, providers now define their own asset requirements through configuration methods. This eliminates hardcoding and enables seamless external provider integration.

### Provider Asset Configuration

Each provider can define:
- **File extensions**: Default file formats (`.pt`, `.onnx`, `.wav`, etc.)
- **Directory names**: Where to store provider-specific assets
- **Credential patterns**: Required environment variables
- **Cache types**: Which caches to use (models, runtime, temp, etc.)
- **Model URLs**: Default download locations

### Intelligent Defaults

Providers use intelligent defaults based on their implementation:

```python
# Example: SileroV3TTSProvider automatically provides:
{
    "file_extension": ".pt",              # PyTorch format
    "directory_name": "silero",           # Provider-specific directory
    "credential_patterns": [],            # No credentials (open source)
    "cache_types": ["models", "runtime"], # Models + runtime cache
    "model_urls": {                       # Default model URLs
        "v3_ru": "https://models.silero.ai/models/tts/ru/v3_1_ru.pt",
        "v3_en": "https://models.silero.ai/models/tts/en/v3_en.pt"
    }
}
```

### TOML Configuration Overrides

Override provider defaults in configuration files:

```toml
# Override Silero v3 asset configuration
[providers.tts.silero_v3.assets]
directory_name = "silero_custom"          # Custom directory name
cache_types = ["models"]                  # Only models cache

[providers.tts.silero_v3.assets.model_urls]
v3_ru = "https://custom-mirror.com/silero_ru.pt"  # Custom URL

# Configure ElevenLabs credentials
[providers.tts.elevenlabs.assets]
credential_patterns = ["ELEVENLABS_API_KEY"]
file_extension = ".mp3"
cache_types = ["runtime"]

# Configure Whisper with custom directory
[providers.asr.whisper.assets]
directory_name = "whisper_models"
cache_types = ["models", "runtime"]

[providers.asr.whisper.assets.model_urls]
tiny = "auto"     # Let whisper library handle download
base = "auto"
small = "auto"
```

### External Provider Support

Third-party providers integrate seamlessly:

```toml
# Third-party package adds entry-point:
# [project.entry-points."irene.providers.tts"]
# my_custom_tts = "my_package.providers:MyCustomTTSProvider"

# Configuration with asset customization:
[providers.tts.my_custom_tts]
enabled = true

[providers.tts.my_custom_tts.assets]
file_extension = ".custom"
directory_name = "my_provider_models"
credential_patterns = ["MY_CUSTOM_API_KEY"]
cache_types = ["models", "runtime"]
```

## Environment Variables

Configure the system using these environment variables:

### Core Asset Directories

```bash
# Root directories for all assets
IRENE_MODELS_ROOT=/data/models      # All AI models (Whisper, Silero, VOSK, etc.)
IRENE_CACHE_ROOT=/data/cache        # Runtime cache, downloads, temporary files
IRENE_CREDENTIALS_ROOT=/data/credentials  # API keys, service account files
```

### API Credentials

```bash
# Cloud service API keys
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
VSEGPT_API_KEY=your_vsegpt_api_key_here

# Google Cloud credentials
GOOGLE_APPLICATION_CREDENTIALS=/data/credentials/google-cloud.json
GOOGLE_CLOUD_PROJECT_ID=your_google_project_id
```

## Directory Structure

The asset management system creates provider-driven directory structures:

```
/data/models/                    # IRENE_MODELS_ROOT
├── whisper/                     # WhisperASRProvider.directory_name
│   ├── tiny.pt                  # WhisperASRProvider.file_extension
│   ├── base.pt
│   └── small.pt
├── silero/                      # SileroV3TTSProvider.directory_name  
│   ├── v3_ru.pt                 # SileroV3TTSProvider.file_extension
│   └── v4_ru.pt
├── vosk/                        # VoskASRProvider.directory_name
│   ├── ru_small/                # VoskASRProvider.file_extension (empty = directories)
│   └── en_us/
├── openwakeword/               # OpenWakeWordProvider.directory_name
│   ├── alexa_v0.1.onnx         # OpenWakeWordProvider.file_extension
│   ├── hey_jarvis_v0.1.onnx
│   └── hey_mycroft_v0.1.onnx
└── custom_provider/            # ExternalProvider.directory_name (configurable)
    └── model.custom            # ExternalProvider.file_extension (configurable)

/data/cache/                     # IRENE_CACHE_ROOT
├── downloads/                   # Download cache
├── runtime/                     # Runtime model cache
├── tts/                         # TTS audio cache  
└── temp/                        # Temporary files

/data/credentials/               # IRENE_CREDENTIALS_ROOT
├── google-cloud.json
└── azure-speech.json
```

**Note**: Provider-specific directory names and file extensions are now determined by provider asset configuration, not hardcoded properties.

## Docker Integration

### Docker Compose Example

```yaml
version: '3.8'
services:
  irene:
    build: .
    ports:
      - "5003:5003"
    volumes:
      - ./data/models:/data/models      # Persistent model storage
      - ./data/cache:/data/cache        # Persistent cache
      - ./data/credentials:/data/credentials  # Credentials
    environment:
      - IRENE_MODELS_ROOT=/data/models
      - IRENE_CACHE_ROOT=/data/cache
      - IRENE_CREDENTIALS_ROOT=/data/credentials
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    env_file:
      - .env
```

### Dockerfile Integration

```dockerfile
FROM python:3.10-slim

# Create mount points for persistent storage
RUN mkdir -p /data/models /data/cache /data/credentials

# Environment variables with defaults
ENV IRENE_MODELS_ROOT=/data/models
ENV IRENE_CACHE_ROOT=/data/cache
ENV IRENE_CREDENTIALS_ROOT=/data/credentials

# Volume mounts for persistence
VOLUME ["/data/models", "/data/cache", "/data/credentials"]

# ... rest of Dockerfile
```

## Provider Configuration Evolution

### Phase 1: Legacy Hardcoded Configuration

**Before (Legacy):**
```python
{
    "whisper": {
        "download_root": "~/.cache/irene/whisper",
        "model_size": "base"
    },
    "vosk": {
        "model_paths": {
            "ru": "./models/vosk-model-ru-0.22",
            "en": "./models/vosk-model-en-us-0.22"
        }
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY"
    }
}
```

### Phase 2: Configuration-Driven Asset Management (NEW)

**Current (Provider-Driven):**
```toml
# Providers automatically determine their asset needs
[providers.asr.whisper]
enabled = true
model_size = "base"
# Asset configuration provided by WhisperASRProvider class

[providers.asr.vosk]
enabled = true
sample_rate = 16000
# Asset configuration provided by VoskASRProvider class

[providers.llm.openai]
enabled = true
default_model = "gpt-4"
# Asset configuration provided by OpenAILLMProvider class

# Optional: Override provider asset defaults
[providers.asr.whisper.assets]
directory_name = "whisper_custom"     # Override default "whisper"
cache_types = ["models"]              # Override default ["models", "runtime"]

[providers.llm.openai.assets]
credential_patterns = ["OPENAI_API_KEY", "OPENAI_ORG_ID"]  # Add extra credentials
```

### Benefits of New Approach

1. **Provider Self-Description**: Providers declare their own asset needs
2. **Zero Hardcoding**: No more hardcoded directory names or file extensions in core code
3. **External Extensibility**: Third-party providers integrate seamlessly
4. **TOML Override Support**: Customize provider defaults without code changes
5. **Intelligent Defaults**: Providers provide sensible defaults based on their implementation

## Migration Guide

### For Existing Installations

1. **Set environment variables:**
   ```bash
   export IRENE_MODELS_ROOT=/path/to/your/models
   export IRENE_CACHE_ROOT=/path/to/your/cache
   export IRENE_CREDENTIALS_ROOT=/path/to/your/credentials
   ```

2. **Move existing models:**
   ```bash
   # Move existing Whisper models
   mv ~/.cache/whisper/* $IRENE_MODELS_ROOT/whisper/
   
   # Move existing VOSK ASR models
   mv ./models/vosk-model-* $IRENE_MODELS_ROOT/vosk/
   
   # Move existing VOSK TTS models
   mv ./models/vosk-tts* $IRENE_MODELS_ROOT/vosk/
   
   # Move existing Silero models
   mv ~/.cache/irene/models/silero* $IRENE_MODELS_ROOT/silero/
   ```

3. **Update configuration files:**
   - Remove `download_root`, `model_paths`, `credentials_path` from provider configs
   - Set environment variables instead

### Backwards Compatibility

The system maintains backwards compatibility:
- Legacy configuration keys still work but show deprecation warnings
- Providers fall back to old behavior if environment variables aren't set
- Existing model files in legacy locations continue to work

## Supported Providers

All 25 providers now support configuration-driven asset management:

### TTS Providers (6)
- **Silero v3**: `.pt` files, `silero` directory, models + runtime cache
- **Silero v4**: `.pt` files, `silero_v4` directory, models + runtime cache  
- **ElevenLabs**: `.mp3` files, `ELEVENLABS_API_KEY` credentials, runtime cache
- **PyTTSx**: No files, runtime cache only
- **VoSK TTS**: `.zip` files, `vosk` directory, models + runtime cache
- **Console**: No files, runtime cache only

### ASR Providers (3)
- **Whisper**: `.pt` files, `whisper` directory, models + runtime cache
- **VoSK ASR**: `.zip` files, `vosk` directory, models + runtime cache
- **Google Cloud**: `GOOGLE_APPLICATION_CREDENTIALS` + `GOOGLE_CLOUD_PROJECT_ID`, runtime cache

### LLM Providers (3)
- **OpenAI**: `OPENAI_API_KEY` credentials, runtime cache only
- **Anthropic**: `ANTHROPIC_API_KEY` credentials, runtime cache only
- **VseGPT**: `VSEGPT_API_KEY` credentials, runtime cache only

### Audio Providers (5)
- **SoundDevice**: `.wav` files, runtime cache only
- **SimpleAudio**: `.wav` files, runtime cache only
- **AudioPlayer**: `.wav` files, runtime cache only
- **Aplay**: `.wav` files, runtime cache only
- **Console**: No files, runtime cache only

### Voice Trigger Providers (2)
- **OpenWakeWord**: `.onnx` files, `openwakeword` directory, models + runtime cache
- **MicroWakeWord**: `.tflite` files, `microwakeword` directory, models + runtime cache

### NLU Providers (2)
- **Rule-based**: No files, runtime cache only
- **SpaCy**: spaCy models, models + runtime cache

### Text Processing Providers (4)
- **ASR Text Processor**: No files, runtime cache only
- **General Text Processor**: No files, runtime cache only  
- **TTS Text Processor**: No files, runtime cache only
- **Number Text Processor**: No files, runtime cache only

### Asset Configuration Examples

Each provider defines intelligent defaults. Common patterns:

```python
# Model-based providers (Silero, Whisper, VoSK)
{
    "file_extension": ".pt",              # Or .zip, .onnx, .tflite
    "directory_name": "provider_name",    # Provider-specific directory
    "cache_types": ["models", "runtime"], # Model storage + runtime cache
    "model_urls": {...}                   # Download URLs
}

# API-based providers (OpenAI, ElevenLabs)
{
    "credential_patterns": ["API_KEY"],   # Required environment variables
    "cache_types": ["runtime"],           # Runtime cache only
    "file_extension": "",                 # No model files
    "directory_name": "provider_name"     # Minimal directory usage
}

# Processing providers (Text processors, Console providers)
{
    "cache_types": ["runtime"],           # Runtime cache only
    "credential_patterns": [],            # No credentials
    "file_extension": "",                 # No persistent files
    "directory_name": "provider_name"     # Minimal directory usage
}
```

## Benefits

1. **Docker-friendly**: Single mount points for all assets
2. **Environment-driven**: Easy configuration via .env files
3. **Organized**: Clear separation between models, cache, and credentials
4. **Scalable**: Easy to add new providers following the same pattern
5. **Portable**: Copy `/data` directory to migrate between systems
6. **Backwards compatible**: Existing setups continue to work

## Model Registry

The system includes a built-in model registry with information about available models:

```python
{
    "whisper": {
        "tiny": {"size": "39MB", "url": "auto"},
        "base": {"size": "74MB", "url": "auto"},
        "small": {"size": "244MB", "url": "auto"},
        "medium": {"size": "769MB", "url": "auto"},
        "large": {"size": "1550MB", "url": "auto"}
    },
    "silero": {
        "v3_ru": {
            "url": "https://models.silero.ai/models/tts/ru/v3_1_ru.pt",
            "size": "36MB"
        },
        "v4_ru": {
            "url": "https://models.silero.ai/models/tts/ru/v4_ru.pt",
            "size": "50MB"
        }
    },
    "vosk": {
                 "ru_small": {
             "url": "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
             "size": "50MB",
             "extract": True
         },
         "tts": {
             "url": "https://alphacephei.com/vosk/models/vosk-tts-ru.zip",
             "size": "100MB",
             "extract": True
         }
    }
}
```

## Troubleshooting

### Common Issues

1. **Permission errors**: Ensure the user has write access to the configured directories
2. **Missing models**: Check that `IRENE_MODELS_ROOT` is correctly set and accessible
3. **API key errors**: Verify environment variables are set and accessible to the application
4. **Docker volume issues**: Ensure volumes are correctly mounted and persistent

### Debug Commands

```bash
# Check environment variables
env | grep IRENE

# Verify directory structure
ls -la $IRENE_MODELS_ROOT
ls -la $IRENE_CACHE_ROOT
ls -la $IRENE_CREDENTIALS_ROOT

# Test model availability
python -c "from irene.core.assets import get_asset_manager; am = get_asset_manager(); print(am.config.models_root)"
``` 

## Custom Wake Word Models

### Training Custom Models

OpenWakeWord supports training custom wake word models for words not included in the pre-trained models. For example, to create an "irene" wake word model:

1. **Train the model** using OpenWakeWord's training notebooks (see [Training New Models](https://github.com/dscripka/openWakeWord#training-new-models))

2. **Place the model file** in the voice trigger models directory:
   ```
   /data/models/voice_trigger/custom_irene_v1.0.onnx
   ```

3. **Configure the provider** to use your custom model:
   ```yaml
   # In your configuration
   voice_trigger:
     provider: "openwakeword"
     wake_words: ["irene"]
     model_paths:
       irene: "/data/models/voice_trigger/custom_irene_v1.0.onnx"
   ```

### Legacy Model Paths Support

The OpenWakeWord provider maintains backwards compatibility with the legacy `model_paths` configuration for custom models:

```yaml
voice_trigger:
  provider: "openwakeword"
  model_paths:
    irene: "~/.local/share/irene/models/irene_custom.onnx"
    custom_phrase: "/path/to/custom/model.onnx"
```

However, using the centralized asset management system (`IRENE_MODELS_ROOT`) is recommended for Docker deployments. 