# Asset Management System

The Irene Voice Assistant now includes a centralized asset management system for handling models, cache files, and credentials. This system provides unified storage locations that work seamlessly with Docker deployments.

## Overview

The asset management system provides:
1. **Unified root directories** for models, cache, and credentials
2. **Environment variable configuration** for easy Docker deployment
3. **Backwards compatibility** with existing configurations
4. **Automatic model downloading** and caching
5. **Centralized credential management**

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

When configured, the asset management system creates this structure:

```
/data/models/                    # IRENE_MODELS_ROOT
├── whisper/
│   ├── tiny.pt
│   ├── base.pt
│   ├── small.pt
│   └── large.pt
├── silero/
│   ├── v3_ru.pt
│   └── v4_ru.pt
├── vosk/
│   ├── ru_small/
│   └── en_us/
└── huggingface/                # Future expansion

/data/cache/                     # IRENE_CACHE_ROOT
├── downloads/                   # Temporary download files
├── runtime/                     # Runtime model cache
├── tts/                        # TTS audio cache
└── temp/                       # Temporary files

/data/credentials/               # IRENE_CREDENTIALS_ROOT
├── google-cloud.json
├── azure-speech.json
└── ...
```

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

## Provider Configuration Changes

### Legacy vs New Configuration

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

**After (Asset Management):**
```python
{
    "whisper": {
        "model_size": "base"
        # download_root automatically uses IRENE_MODELS_ROOT/whisper
    },
    "vosk": {
        # model_paths automatically uses IRENE_MODELS_ROOT/vosk
        "sample_rate": 16000
    },
    "openai": {
        # api_key automatically uses OPENAI_API_KEY environment variable
        "default_model": "gpt-4"
    }
}
```

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
   
   # Move existing VOSK models
   mv ./models/vosk-* $IRENE_MODELS_ROOT/vosk/
   
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

### Model-based Providers
- **Whisper ASR**: Uses `IRENE_MODELS_ROOT/whisper/`
- **Silero TTS v3/v4**: Uses `IRENE_MODELS_ROOT/silero/`
- **VOSK ASR**: Uses `IRENE_MODELS_ROOT/vosk/`

### Cloud Providers
- **OpenAI**: Uses `OPENAI_API_KEY`
- **Anthropic**: Uses `ANTHROPIC_API_KEY`
- **ElevenLabs**: Uses `ELEVENLABS_API_KEY`
- **Google Cloud**: Uses `GOOGLE_APPLICATION_CREDENTIALS`

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