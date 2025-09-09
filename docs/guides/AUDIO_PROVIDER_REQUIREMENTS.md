# Provider-Specific Audio Requirements

This document details the audio requirements, capabilities, and optimization recommendations for each ASR and Voice Trigger provider supported by Irene Voice Assistant.

## Table of Contents

1. [ASR Providers](#asr-providers)
   - [VOSK](#vosk-asr)
   - [Whisper](#whisper-asr)
   - [Google Cloud Speech](#google-cloud-speech)
2. [Voice Trigger Providers](#voice-trigger-providers)
   - [OpenWakeWord](#openwakeword)
   - [MicroWakeWord](#microwakeword)
3. [Provider Comparison](#provider-comparison)
4. [Configuration Examples](#configuration-examples)
5. [Performance Characteristics](#performance-characteristics)

## ASR Providers

### VOSK ASR

VOSK is a lightweight speech recognition toolkit with offline capabilities.

#### Audio Requirements

| Parameter | Requirement | Notes |
|-----------|-------------|-------|
| **Sample Rates** | 8000, 16000, 44100, 48000 Hz | Model-dependent |
| **Channels** | 1 (mono) | Stereo not supported |
| **Format** | 16-bit PCM | Little-endian |
| **Chunk Size** | Variable | Optimized for streaming |
| **Resampling** | Manual | No internal resampling |

#### Supported Sample Rates by Model Type

```toml
# Different VOSK models support different sample rates
[asr.providers.vosk]
enabled = true
model_path = "/path/to/vosk/model"

# Check model documentation for supported rates:
# - Most models: 16000 Hz
# - Some models: 8000 Hz (telephony)
# - Few models: 44100 Hz, 48000 Hz (high quality)
sample_rate = 16000  # Most common and recommended
```

#### Configuration Examples

**Standard Configuration (16 kHz)**
```toml
[asr.providers.vosk]
enabled = true
model_path = "/opt/vosk/models/vosk-model-en-us-0.22"
sample_rate = 16000
language = "en"
confidence_threshold = 0.8
```

**High-Quality Configuration (48 kHz)**
```toml
[asr.providers.vosk]
enabled = true
model_path = "/opt/vosk/models/vosk-model-en-us-0.22-hq"
sample_rate = 48000  # Only if model supports it
language = "en"
confidence_threshold = 0.9
```

#### Performance Characteristics

- **Latency**: Very low (real-time streaming)
- **CPU Usage**: Low to medium
- **Memory**: 100-500 MB depending on model
- **Accuracy**: Good for general speech
- **Offline**: Full offline support

#### Optimization Tips

1. **Model Selection**: Choose model size based on accuracy vs performance needs
2. **Sample Rate**: Use 16 kHz for best balance
3. **Streaming**: Enable streaming for real-time applications
4. **Memory**: Preload models to avoid initialization delays

```python
# Performance optimization example
vosk_config = {
    "sample_rate": 16000,           # Optimal rate
    "model_path": "/path/to/model",
    "streaming": True,              # Enable streaming
    "preload": True,                # Preload model
    "confidence_threshold": 0.8     # Filter low-confidence results
}
```

### Whisper ASR

OpenAI's Whisper provides high-accuracy speech recognition with broad language support.

#### Audio Requirements

| Parameter | Requirement | Notes |
|-----------|-------------|-------|
| **Sample Rates** | 8000-96000 Hz | Internal resampling to 16 kHz |
| **Channels** | 1-2 | Automatically converts to mono |
| **Format** | 16-bit PCM, 32-bit float | Flexible format support |
| **Chunk Size** | Variable | Optimized for 30-second segments |
| **Resampling** | Automatic | Built-in resampling |

#### Model Sizes and Performance

| Model | Parameters | Speed | Accuracy | Memory | Use Case |
|-------|------------|-------|----------|--------|----------|
| tiny | 39M | ~10x | Basic | ~1GB | Real-time, low-resource |
| base | 74M | ~7x | Good | ~1GB | Balanced |
| small | 244M | ~4x | Better | ~2GB | Higher accuracy |
| medium | 769M | ~2x | High | ~5GB | High accuracy |
| large | 1550M | ~1x | Highest | ~10GB | Best accuracy |

#### Configuration Examples

**Real-time Configuration**
```toml
[asr.providers.whisper]
enabled = true
model_size = "base"              # Good balance for real-time
device = "cuda"                  # GPU acceleration if available
sample_rate = 16000              # Whisper's native rate
temperature = 0.0                # Deterministic output
language = "auto"                # Auto-detect language
```

**High-Accuracy Configuration**
```toml
[asr.providers.whisper]
enabled = true
model_size = "large"             # Best accuracy
device = "cuda"                  # GPU recommended for large models
sample_rate = 16000              
temperature = 0.0                
language = "en"                  # Specify language for better performance
beam_size = 5                    # Better accuracy, slower processing
```

**CPU-Optimized Configuration**
```toml
[asr.providers.whisper]
enabled = true
model_size = "tiny"              # Fastest on CPU
device = "cpu"                   
sample_rate = 16000              
fp16 = false                     # CPU doesn't support FP16
```

#### Performance Characteristics

- **Latency**: Medium to high (depends on model size)
- **CPU Usage**: High (especially larger models)
- **Memory**: 1-10 GB depending on model
- **Accuracy**: Excellent, especially for diverse languages
- **Offline**: Full offline support after model download

#### Optimization Tips

1. **Model Size**: Balance accuracy needs with performance requirements
2. **GPU Acceleration**: Use CUDA for significant speedup
3. **Language Specification**: Set specific language to avoid auto-detection overhead
4. **Temperature**: Use 0.0 for consistent results
5. **Batch Processing**: Process longer audio segments for efficiency

```python
# Whisper optimization example
whisper_config = {
    "model_size": "base",           # Balanced choice
    "device": "cuda",               # GPU acceleration
    "language": "en",               # Avoid auto-detection
    "temperature": 0.0,             # Deterministic
    "fp16": True,                   # GPU FP16 acceleration
    "beam_size": 1,                 # Faster greedy decoding
}
```

### Google Cloud Speech

Google Cloud Speech-to-Text API provides cloud-based ASR with high accuracy.

#### Audio Requirements

| Parameter | Requirement | Notes |
|-----------|-------------|-------|
| **Sample Rates** | 8000, 16000, 22050, 44100, 48000 Hz | Exact rates only |
| **Channels** | 1-2 | Supports stereo |
| **Format** | 16-bit PCM, FLAC, OGG | Multiple formats |
| **Chunk Size** | Variable | Streaming or batch |
| **Resampling** | None | Must match exactly |

#### Supported Configurations

**Standard Configuration**
```toml
[asr.providers.google_cloud]
enabled = true
credentials_path = "/path/to/credentials.json"
sample_rate = 16000              # Most common rate
language_code = "en-US"          # Specific locale
encoding = "LINEAR16"            # 16-bit PCM
enable_automatic_punctuation = true
model = "default"                # or "latest_long" for long audio
```

**High-Quality Configuration**
```toml
[asr.providers.google_cloud]
enabled = true
credentials_path = "/path/to/credentials.json"
sample_rate = 48000              # High quality
language_code = "en-US"          
encoding = "LINEAR16"            
enable_automatic_punctuation = true
enable_word_time_offsets = true  # Word-level timestamps
model = "latest_long"            # Best model for long audio
use_enhanced = true              # Enhanced model
```

**Streaming Configuration**
```toml
[asr.providers.google_cloud]
enabled = true
credentials_path = "/path/to/credentials.json"
sample_rate = 16000              
language_code = "en-US"          
encoding = "LINEAR16"            
streaming = true                 # Enable streaming
interim_results = true           # Partial results
single_utterance = false         # Continue listening
```

#### Performance Characteristics

- **Latency**: Low to medium (network dependent)
- **CPU Usage**: Very low (cloud processing)
- **Memory**: Minimal
- **Accuracy**: Excellent
- **Offline**: No (requires internet)

#### Optimization Tips

1. **Sample Rate**: Use exactly supported rates (no resampling)
2. **Model Selection**: Choose appropriate model for use case
3. **Language Code**: Be specific for better accuracy
4. **Enhanced Models**: Use for critical applications
5. **Streaming**: Enable for real-time applications

```python
# Google Cloud optimization example
google_config = {
    "sample_rate": 16000,           # Exact rate required
    "language_code": "en-US",       # Specific locale
    "model": "latest_short",        # Optimized for short audio
    "use_enhanced": True,           # Better accuracy
    "enable_automatic_punctuation": True,
    "profanity_filter": False,      # Disable if not needed
}
```

## Voice Trigger Providers

### OpenWakeWord

OpenWakeWord is a flexible wake word detection system supporting custom models.

#### Audio Requirements

| Parameter | Requirement | Notes |
|-----------|-------------|-------|
| **Sample Rates** | 8000-44100 Hz | Flexible with resampling |
| **Channels** | 1 (mono) | Stereo converted to mono |
| **Format** | 16-bit PCM | Standard PCM format |
| **Chunk Size** | 1280 samples | Optimized chunk size |
| **Resampling** | Automatic | Built-in resampling support |

#### Supported Inference Frameworks

| Framework | Performance | Compatibility | Use Case |
|-----------|-------------|---------------|----------|
| **ONNX** | High | Broad | General purpose |
| **TensorFlow Lite** | Medium | ARM-optimized | Embedded devices |
| **TensorFlow** | Medium | Full features | Development |

#### Configuration Examples

**Standard Configuration**
```toml
[voice_trigger.providers.openwakeword]
enabled = true
model_path = "/opt/openwakeword/models"
inference_framework = "onnx"     # Best performance
chunk_size = 1280                # Optimal for OpenWakeWord
sample_rate = 16000              # Recommended rate
threshold = 0.8                  # Detection threshold
```

**High-Performance Configuration**
```toml
[voice_trigger.providers.openwakeword]
enabled = true
model_path = "/opt/openwakeword/models"
inference_framework = "onnx"     
chunk_size = 1280                
sample_rate = 16000              
threshold = 0.9                  # Higher threshold for fewer false positives
prediction_frequency = 25        # Faster predictions
vad_threshold = 0.5              # Voice activity detection
```

**Embedded Device Configuration**
```toml
[voice_trigger.providers.openwakeword]
enabled = true
model_path = "/opt/openwakeword/models"
inference_framework = "tflite"   # Optimized for ARM
chunk_size = 1280                
sample_rate = 16000              
threshold = 0.7                  # Lower threshold for responsiveness
enable_speex_noise_suppression = true  # Noise reduction
```

#### Performance Characteristics

- **Latency**: Low (~50-100ms)
- **CPU Usage**: Low to medium
- **Memory**: 50-200 MB
- **Accuracy**: Good with proper training
- **Offline**: Full offline support

#### Custom Models

OpenWakeWord supports custom wake word models:

```python
# Custom model configuration
custom_model_config = {
    "model_path": "/path/to/custom/models",
    "custom_models": [
        "jarvis.onnx",              # Custom wake word
        "computer.onnx"             # Additional wake word
    ],
    "threshold": 0.8,               # Per-model thresholds
    "inference_framework": "onnx"
}
```

### MicroWakeWord

MicroWakeWord is optimized for ultra-low power and latency applications.

#### Audio Requirements

| Parameter | Requirement | Notes |
|-----------|-------------|-------|
| **Sample Rates** | 16000 Hz only | Fixed requirement |
| **Channels** | 1 (mono) | Mono only |
| **Format** | 16-bit PCM | Fixed format |
| **Chunk Size** | 320 samples | Fixed for micro_speech |
| **Resampling** | None | Strict 16 kHz requirement |

#### Configuration Examples

**Standard Configuration**
```toml
[voice_trigger.providers.microwakeword]
enabled = true
model_path = "/opt/microwakeword/micro_speech_model"
sample_rate = 16000              # MUST be exactly 16000
chunk_size = 320                 # Fixed requirement
threshold = 0.8                  # Detection threshold
```

**Optimized Configuration**
```toml
[voice_trigger.providers.microwakeword]
enabled = true
model_path = "/opt/microwakeword/micro_speech_model"
sample_rate = 16000              # STRICT requirement
chunk_size = 320                 # Fixed requirement
threshold = 0.9                  # Higher threshold for accuracy
preemphasis = 0.97               # Audio preprocessing
```

#### Performance Characteristics

- **Latency**: Ultra-low (~10-50ms)
- **CPU Usage**: Very low
- **Memory**: <50 MB
- **Accuracy**: Good for "yes"/"no" detection
- **Offline**: Full offline support

#### Optimization Tips

1. **Sample Rate**: Must be exactly 16 kHz (no flexibility)
2. **Chunk Size**: Must be exactly 320 samples
3. **Preprocessing**: Tune preemphasis for audio quality
4. **Threshold**: Adjust for environment noise levels

```python
# MicroWakeWord optimization
microwakeword_config = {
    "sample_rate": 16000,           # STRICT requirement
    "chunk_size": 320,              # STRICT requirement
    "threshold": 0.85,              # Tuned for environment
    "preemphasis": 0.97,            # Audio preprocessing
    "window_length": 30,            # Processing window
}
```

## Provider Comparison

### ASR Provider Comparison

| Feature | VOSK | Whisper | Google Cloud |
|---------|------|---------|--------------|
| **Accuracy** | Good | Excellent | Excellent |
| **Speed** | Fast | Medium | Fast |
| **Languages** | Limited | 100+ | 125+ |
| **Offline** | ✓ | ✓ | ✗ |
| **Real-time** | ✓ | Limited | ✓ |
| **Memory** | Low | High | Very Low |
| **Setup** | Easy | Easy | Complex |
| **Cost** | Free | Free | Paid |

### Voice Trigger Provider Comparison

| Feature | OpenWakeWord | MicroWakeWord |
|---------|--------------|---------------|
| **Latency** | Low | Ultra-low |
| **Flexibility** | High | Very Low |
| **Custom Models** | ✓ | Limited |
| **Sample Rates** | Flexible | 16 kHz only |
| **Memory** | Medium | Very Low |
| **CPU Usage** | Medium | Very Low |
| **Accuracy** | Good | Basic |

## Configuration Examples

### Multi-Provider Setup

Configure multiple providers with fallbacks:

```toml
# ASR with multiple providers
[asr]
default_provider = "whisper"
fallback_providers = ["vosk", "google_cloud"]
sample_rate = 16000
allow_resampling = true

[asr.providers.whisper]
enabled = true
model_size = "base"
device = "cuda"

[asr.providers.vosk]
enabled = true
model_path = "/opt/vosk/model"

[asr.providers.google_cloud]
enabled = true
credentials_path = "/path/to/credentials.json"

# Voice Trigger with fallback
[voice_trigger]
default_provider = "openwakeword"
fallback_providers = ["microwakeword"]
sample_rate = 16000
allow_resampling = true

[voice_trigger.providers.openwakeword]
enabled = true
model_path = "/opt/openwakeword/models"
inference_framework = "onnx"

[voice_trigger.providers.microwakeword]
enabled = true
model_path = "/opt/microwakeword/model"
```

### Environment-Specific Configurations

#### High-Performance Workstation
```toml
[asr.providers.whisper]
enabled = true
model_size = "large"             # Best accuracy
device = "cuda"                  # GPU acceleration
sample_rate = 16000

[voice_trigger.providers.openwakeword]
enabled = true
inference_framework = "onnx"     # Best performance
sample_rate = 16000
threshold = 0.9                  # High accuracy
```

#### Embedded Device
```toml
[asr.providers.vosk]
enabled = true
model_path = "/opt/vosk/small-model"  # Small model
sample_rate = 16000

[voice_trigger.providers.microwakeword]
enabled = true
sample_rate = 16000              # Only supported rate
threshold = 0.8                  # Balanced for embedded
```

#### Cloud-Connected Device
```toml
[asr.providers.google_cloud]
enabled = true
sample_rate = 16000
language_code = "en-US"
streaming = true                 # Real-time

[asr.providers.vosk]
enabled = true                   # Offline fallback
model_path = "/opt/vosk/model"

[voice_trigger.providers.openwakeword]
enabled = true
inference_framework = "onnx"
sample_rate = 16000
```

## Performance Characteristics

### Latency Comparison

| Provider | Component | Typical Latency | Real-time Factor |
|----------|-----------|----------------|------------------|
| VOSK | ASR | 100-300ms | 0.2-0.5x |
| Whisper (tiny) | ASR | 200-500ms | 0.3-0.8x |
| Whisper (base) | ASR | 500-1000ms | 0.5-1.5x |
| Google Cloud | ASR | 200-800ms | 0.3-1.0x |
| OpenWakeWord | Voice Trigger | 50-100ms | 0.05-0.1x |
| MicroWakeWord | Voice Trigger | 10-50ms | 0.01-0.05x |

### Memory Usage

| Provider | Component | RAM Usage | Model Size |
|----------|-----------|-----------|------------|
| VOSK | ASR | 100-500MB | 50-1500MB |
| Whisper (tiny) | ASR | ~1GB | ~39MB |
| Whisper (base) | ASR | ~1GB | ~74MB |
| Whisper (large) | ASR | ~10GB | ~1550MB |
| Google Cloud | ASR | <50MB | N/A |
| OpenWakeWord | Voice Trigger | 50-200MB | 10-100MB |
| MicroWakeWord | Voice Trigger | <50MB | <10MB |

### Accuracy Guidelines

Based on typical use cases:

- **VOSK**: 85-95% accuracy for clear speech
- **Whisper**: 90-98% accuracy across languages
- **Google Cloud**: 90-98% accuracy with enhanced models
- **OpenWakeWord**: 90-95% wake word detection
- **MicroWakeWord**: 80-90% wake word detection

### Recommendation Matrix

| Use Case | ASR Provider | Voice Trigger | Rationale |
|----------|--------------|---------------|-----------|
| **High Accuracy** | Whisper (large) + Google Cloud | OpenWakeWord | Best transcription quality |
| **Real-time** | VOSK + Whisper (tiny) | MicroWakeWord | Lowest latency |
| **Offline** | VOSK + Whisper | OpenWakeWord | No internet required |
| **Embedded** | VOSK (small) | MicroWakeWord | Resource constrained |
| **Multi-language** | Whisper + Google Cloud | OpenWakeWord | Broad language support |
| **Cost-sensitive** | VOSK + Whisper | OpenWakeWord | No API costs |

This comprehensive guide provides the foundation for selecting and configuring the optimal providers for your specific Irene Voice Assistant deployment requirements.
