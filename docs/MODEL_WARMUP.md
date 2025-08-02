# Model Warm-up and Preloading

The Irene Voice Assistant now includes comprehensive model warm-up and preloading capabilities to ensure optimal performance and responsiveness.

## Overview

Model warm-up provides:
1. **Automatic model downloading** if models are not present locally
2. **Startup model preloading** into memory/GPU for faster response times
3. **Intelligent caching** to avoid reloading models between requests
4. **Background model preparation** to reduce first-use latency

## Configuration

### Enable Preloading

Set `preload_models: true` in your provider configuration to enable startup model loading:

```python
{
    "whisper": {
        "model_size": "base",
        "device": "cpu",
        "preload_models": True  # Download and load model on startup
    },
    "silero_v3": {
        "default_speaker": "xenia",
        "preload_models": True  # Download and load model on startup  
    },
    "vosk": {
        "default_language": "ru",
        "preload_models": True  # Download and load default language model
    }
}
```

### Environment Variables

```bash
# Enable preloading via environment variables
IRENE_PROVIDERS__ASR__WHISPER__PRELOAD_MODELS=true
IRENE_PROVIDERS__TTS__SILERO_V3__PRELOAD_MODELS=true
IRENE_PROVIDERS__ASR__VOSK__PRELOAD_MODELS=true
```

## Supported Providers

### ASR Providers

**WhisperASRProvider:**
- Downloads Whisper model if not present
- Loads model into memory/GPU on startup
- Caches model for subsequent requests
- Supports all model sizes (tiny, base, small, medium, large)

**VoskASRProvider:**
- Downloads VOSK model for default language if not present
- Loads model and creates recognizer on startup
- Caches models per language for multi-language support
- Downloads additional languages on-demand

### TTS Providers

**SileroV3TTSProvider:**
- Downloads Silero v3 model if not present
- Loads model into memory/GPU on startup
- Includes comprehensive model caching with async locks
- Supports device placement (CPU/GPU)

**SileroV4TTSProvider:**
- ✅ Full asset management integration 
- ✅ Model downloading and warm-up infrastructure
- ✅ Configuration and device placement support
- ✅ **Complete TTS synthesis** - Generates actual audio files
- Uses Silero v4 models with enhanced quality
- Requires torch and soundfile dependencies

**VoskTTSProvider:**
- ✅ Full asset management integration
- ✅ Downloads VOSK TTS model if not present
- ✅ Model availability checking and warm-up
- ✅ **Complete TTS synthesis** - Generates actual audio files
- Multi-engine fallback: espeak/espeak-ng → pyttsx3
- Works without specialized TTS libraries

## How It Works

### 1. Startup Sequence

When `preload_models: true` is set:

```python
# Provider initialization
provider = WhisperASRProvider(config)
# ↓
# Checks preload_models setting
if preload_models:
    asyncio.create_task(provider.warm_up())
# ↓
# Background warm-up process begins
await provider.warm_up()
    # ↓ Downloads model if missing
    # ↓ Loads model into memory/GPU
    # ↓ Logs completion
```

### 2. Model Download Flow

```python
# Check if model exists locally
if not model_path.exists():
    # Get model info from asset registry
    model_info = asset_manager.get_model_info(provider, model_id)
    
    # Download using asset manager
    downloaded_path = await asset_manager.download_model(provider, model_id)
    
    # Extract if needed (for ZIP archives)
    if model_info.get("extract"):
        await asset_manager._extract_archive(temp_path, model_path)
```

### 3. Model Caching

```python
# Silero example with class-level caching
class SileroV3TTSProvider:
    _model_cache: Dict[str, Any] = {}  # Shared across instances
    _cache_lock = asyncio.Lock()       # Thread-safe access
    
    async def _get_or_load_cached_model(self, cache_key: str):
        async with self._cache_lock:
            if cache_key in self._model_cache:
                self._model = self._model_cache[cache_key]  # Use cached
            else:
                await self._load_model_async()            # Load new
                self._model_cache[cache_key] = self._model # Cache it
```

## Performance Benefits

### Cold Start vs Warm Start

**Without Preloading (Cold Start):**
```
User Request → Check Model → Download (30s) → Load (10s) → Process (1s) → Response
Total: ~41 seconds for first request
```

**With Preloading (Warm Start):**
```
Startup → Download (30s) → Load (10s) → Ready
User Request → Process (1s) → Response  
Total: ~1 second for first request
```

### Memory Usage

Preloading trades memory for speed:
- **Whisper base**: ~74MB RAM
- **Silero v3**: ~36MB RAM
- **VOSK small**: ~50MB RAM
- **Total impact**: ~160MB for all models

## Configuration Examples

### Minimal Setup (Default)
```python
# Lazy loading - models loaded on first use
{
    "whisper": {"model_size": "base"},
    "silero_v3": {"default_speaker": "xenia"}
}
```

### Performance Setup (Preloading)
```python
# Fast response - models ready immediately
{
    "whisper": {
        "model_size": "base",
        "preload_models": True
    },
    "silero_v3": {
        "default_speaker": "xenia", 
        "preload_models": True
    },
    "vosk": {
        "default_language": "ru",
        "preload_models": True
    }
}
```

### Production Setup (Selective)
```python
# Balance between memory and performance
{
    "whisper": {
        "model_size": "small",
        "preload_models": True  # Always used
    },
    "silero_v3": {
        "preload_models": True  # Primary TTS
    },
    "vosk": {
        "preload_models": False  # Backup ASR, load on demand
    }
}
```

## Monitoring and Logging

### Startup Logs
```
INFO: Warming up Whisper base model...
INFO: Whisper base model warmed up successfully
INFO: Warming up Silero v3 TTS model...
INFO: Silero v3 TTS model warmed up successfully
INFO: Warming up VOSK ASR model for default language: ru
INFO: VOSK ASR model for ru warmed up successfully
```

### Download Logs
```
INFO: Downloading silero/v3_ru (size: 36MB)
INFO: Successfully downloaded: /data/models/silero/v3_ru.pt
INFO: Downloading vosk/ru_small (size: 50MB)
INFO: Extracting archive to: /data/models/vosk/ru_small/
```

### Error Handling
```
ERROR: Failed to warm up Whisper model: ConnectionError
WARNING: Falling back to lazy loading for Whisper provider
```

## Troubleshooting

### Common Issues

1. **Slow startup**: Models downloading during initialization
   - **Solution**: Ensure good internet connection or pre-download models

2. **High memory usage**: Multiple large models preloaded
   - **Solution**: Enable preloading only for frequently used providers

3. **Download failures**: Network issues or incorrect URLs
   - **Solution**: Check asset registry URLs and network connectivity

4. **TTS synthesis errors**: Audio generation failures with SileroV4 or VoskTTS
   - **SileroV4**: Requires torch and soundfile dependencies
   - **VoskTTS**: Requires espeak/espeak-ng or pyttsx3 for fallback
   - **Solution**: Install dependencies or use SileroV3/PyttSX providers

### Debug Commands

```bash
# Check model availability
python -c "
from irene.core.assets import get_asset_manager
am = get_asset_manager()
print('Whisper base exists:', am.model_exists('whisper', 'base'))
print('Silero v3 exists:', am.model_exists('silero', 'v3_ru'))
"

# Test warm-up manually
python -c "
import asyncio
from irene.providers.asr.whisper import WhisperASRProvider
config = {'model_size': 'base', 'preload_models': True}
provider = WhisperASRProvider(config)
asyncio.run(provider.warm_up())
"
```

## Best Practices

1. **Development**: Disable preloading for faster iteration
2. **Testing**: Enable preloading to test production performance
3. **Production**: Enable preloading for critical providers only
4. **Docker**: Use volume mounts to persist downloaded models
5. **Memory**: Monitor RAM usage when enabling multiple providers

The warm-up system ensures your voice assistant is always ready to respond quickly while maintaining flexibility for different deployment scenarios. 