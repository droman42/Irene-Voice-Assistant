# Audio Hardware Compatibility Configuration Guide

This guide provides comprehensive instructions for configuring Irene Voice Assistant to work optimally with various audio hardware configurations, sample rates, and provider combinations.

## Table of Contents

1. [Overview](#overview)
2. [Basic Audio Configuration](#basic-audio-configuration)
3. [Sample Rate Configuration](#sample-rate-configuration)
4. [Provider-Specific Settings](#provider-specific-settings)
5. [Hardware Scenarios](#hardware-scenarios)
6. [Performance Optimization](#performance-optimization)
7. [Troubleshooting](#troubleshooting)

## Overview

Irene Voice Assistant supports a wide range of audio hardware configurations through its flexible audio processing pipeline. The system automatically handles sample rate mismatches through intelligent resampling, but proper configuration ensures optimal performance and quality.

### Key Features

- **Automatic Sample Rate Detection**: Detects microphone capabilities and adjusts processing accordingly
- **Intelligent Resampling**: Context-aware conversion methods optimized for voice trigger vs ASR scenarios
- **Provider Fallbacks**: Automatic fallback to compatible providers when sample rate mismatches occur
- **Performance Optimization**: Caching and parallel processing for real-time performance
- **Quality Control**: Configurable quality vs performance trade-offs

## Basic Audio Configuration

### Microphone Input Configuration

Configure your microphone input in the `[inputs.microphone_config]` section:

```toml
[inputs.microphone_config]
# Primary audio settings
sample_rate = 16000          # Microphone sample rate (8000-192000 Hz)
channels = 1                 # Number of audio channels (1-8)
chunk_size = 1024           # Audio buffer size in samples

# Resampling settings
auto_resample = true         # Enable automatic resampling
resample_quality = "medium"  # Global quality: "fast", "medium", "high", "best"

# Device selection
device_id = -1              # Audio device ID (-1 = default)
```

### Component Audio Configuration

Each component can have specific audio requirements:

```toml
[asr]
# ASR-specific audio settings
sample_rate = 16000          # AUTHORITATIVE: overrides provider preferences
channels = 1                 # AUTHORITATIVE: explicit channel requirement
allow_resampling = true      # Enable resampling for this component
resample_quality = "high"    # Component-specific quality setting

[voice_trigger]
# Voice trigger audio settings
sample_rate = 16000          # AUTHORITATIVE: configuration takes precedence
channels = 1                 # AUTHORITATIVE: explicit channel requirement
allow_resampling = true      # Enable resampling for voice triggers
resample_quality = "fast"    # Optimized for low-latency real-time processing
strict_validation = true     # Fatal error on provider conflicts
```

## Sample Rate Configuration

### Common Sample Rates

| Sample Rate | Use Case | Pros | Cons |
|-------------|----------|------|------|
| 8 kHz | Telephony, basic speech | Low bandwidth, fast processing | Lower quality |
| 16 kHz | Voice recognition, commands | Good speech quality, efficient | Limited music quality |
| 22.05 kHz | Basic multimedia | Reasonable quality | Non-standard |
| 44.1 kHz | CD quality, music | High quality, standard | Higher processing overhead |
| 48 kHz | Professional audio | Very high quality | Highest processing overhead |

### Sample Rate Selection Guidelines

#### For Voice Trigger Components
```toml
[voice_trigger]
sample_rate = 16000          # Recommended: 16kHz for best balance
resample_quality = "fast"    # Prioritize low latency
```

**Recommendations:**
- **16 kHz**: Optimal for most voice trigger scenarios (balance of quality and performance)
- **8 kHz**: Use for very low-power devices or when latency is critical
- **44.1+ kHz**: Only if using high-quality microphones and latency is not critical

#### For ASR Components
```toml
[asr]
sample_rate = 16000          # Good default for most providers
resample_quality = "high"    # Prioritize transcription quality
```

**Recommendations:**
- **16 kHz**: Universal compatibility, good quality
- **44.1 kHz**: Use with high-quality providers like Whisper for best results
- **8 kHz**: Only for basic transcription needs

### Provider Compatibility Matrix

| Provider | Supported Rates | Preferred Rate | Notes |
|----------|----------------|----------------|-------|
| VOSK | 8-48 kHz | 16 kHz | Model-dependent limitations |
| Whisper | 8-96 kHz | 16 kHz | Internal resampling to 16kHz |
| Google Cloud | 8, 16, 22, 44, 48 kHz | 16 kHz | Strict rate requirements |
| OpenWakeWord | 8-44 kHz | 16 kHz | Flexible with resampling |
| MicroWakeWord | 16 kHz only | 16 kHz | Strict 16kHz requirement |

## Provider-Specific Settings

### ASR Provider Configuration

#### VOSK Configuration
```toml
[asr.providers.vosk]
enabled = true
model_path = "/path/to/vosk/model"
sample_rate = 16000          # Should match model requirements
```

#### Whisper Configuration
```toml
[asr.providers.whisper]
enabled = true
model_size = "base"
sample_rate = 16000          # Whisper handles resampling internally
device = "auto"              # "cpu", "cuda", or "auto"
```

#### Google Cloud Configuration
```toml
[asr.providers.google_cloud]
enabled = true
credentials_path = "/path/to/credentials.json"
sample_rate = 16000          # Must match exactly
language_code = "en-US"
```

### Voice Trigger Provider Configuration

#### OpenWakeWord Configuration
```toml
[voice_trigger.providers.openwakeword]
enabled = true
model_path = "/path/to/models"
inference_framework = "onnx"  # or "tflite"
chunk_size = 1280            # Samples per chunk
sample_rate = 16000          # Flexible with resampling
```

#### MicroWakeWord Configuration
```toml
[voice_trigger.providers.microwakeword]
enabled = true
model_path = "/path/to/micro_speech_model"
sample_rate = 16000          # STRICT: Must be exactly 16kHz
chunk_size = 320             # Fixed for micro_speech compatibility
```

## Hardware Scenarios

### Scenario 1: USB Microphone (48 kHz)

**Hardware:** High-quality USB microphone with 48 kHz sample rate

```toml
[inputs.microphone_config]
sample_rate = 48000
channels = 1
auto_resample = true
resample_quality = "high"

[asr]
sample_rate = 16000          # Downsample for provider compatibility
allow_resampling = true
resample_quality = "high"    # Maintain quality during downsampling

[voice_trigger]
sample_rate = 16000          # Downsample for real-time performance
allow_resampling = true
resample_quality = "fast"    # Prioritize low latency
```

### Scenario 2: Embedded Device (16 kHz)

**Hardware:** Embedded device with fixed 16 kHz microphone

```toml
[inputs.microphone_config]
sample_rate = 16000
channels = 1
auto_resample = false        # No resampling needed

[asr]
sample_rate = 16000          # Direct compatibility
allow_resampling = false     # Not needed

[voice_trigger]
sample_rate = 16000          # Direct compatibility
allow_resampling = false     # Not needed
strict_validation = true     # Ensure exact match
```

### Scenario 3: Multi-Channel Audio Interface

**Hardware:** Professional audio interface with multiple inputs

```toml
[inputs.microphone_config]
sample_rate = 44100
channels = 2                 # Stereo input
auto_resample = true
resample_quality = "high"

[asr]
sample_rate = 16000          # Convert for efficiency
channels = 1                 # Convert to mono
allow_resampling = true
resample_quality = "high"

[voice_trigger]
sample_rate = 16000          # Convert for performance
channels = 1                 # Convert to mono
allow_resampling = true
resample_quality = "fast"
```

### Scenario 4: Low-Power IoT Device

**Hardware:** Constrained device with limited processing power

```toml
[inputs.microphone_config]
sample_rate = 8000           # Low sample rate for efficiency
channels = 1
auto_resample = true
resample_quality = "fast"    # Minimal processing overhead

[asr]
sample_rate = 8000           # Use lowest compatible rate
allow_resampling = true
resample_quality = "fast"

[voice_trigger]
sample_rate = 8000           # Minimize processing
allow_resampling = true
resample_quality = "fast"
```

## Performance Optimization

### Resampling Quality Trade-offs

#### Fast Processing (Voice Trigger Priority)
```toml
[voice_trigger]
resample_quality = "fast"    # Linear interpolation
```
- **Pros**: Lowest latency (~0.1x real-time), minimal CPU usage
- **Cons**: Some quality loss, potential artifacts
- **Use Case**: Real-time voice trigger detection

#### Balanced Processing (General Use)
```toml
[asr]
resample_quality = "medium"  # Polyphase filtering
```
- **Pros**: Good quality/performance balance (~0.3x real-time)
- **Cons**: Moderate CPU usage
- **Use Case**: Most ASR applications

#### High Quality (Accuracy Priority)
```toml
[asr]
resample_quality = "high"    # Kaiser windowed sinc
```
- **Pros**: Highest quality, minimal artifacts
- **Cons**: Higher CPU usage (~0.5x real-time)
- **Use Case**: High-accuracy transcription

#### Adaptive Processing
```toml
[asr]
resample_quality = "adaptive" # Dynamic method selection
```
- **Pros**: Optimal method based on sample rate ratio
- **Cons**: Variable performance characteristics
- **Use Case**: Mixed sample rate environments

### Cache Configuration

The resampling cache improves performance for repeated conversions:

```python
# Cache statistics monitoring
from irene.utils.audio_helpers import AudioProcessor

# Get cache performance metrics
cache_stats = AudioProcessor.get_cache_stats()
print(f"Cache hit rate: {cache_stats['hit_rate']:.2%}")

# Clear cache if memory usage becomes too high
if cache_stats['cache_size'] > 50:
    AudioProcessor.clear_cache()
```

### Memory Optimization

For memory-constrained devices:

```toml
[inputs.microphone_config]
chunk_size = 512             # Smaller chunks for lower memory usage
auto_resample = true
resample_quality = "fast"    # Minimal memory allocation

[asr]
allow_resampling = true
resample_quality = "fast"    # Reduce memory overhead

[voice_trigger]
allow_resampling = true
resample_quality = "fast"    # Minimize latency and memory
```

## Troubleshooting

### Common Issues and Solutions

#### 1. "Sample rate mismatch" errors
**Problem**: Configuration contradicts provider requirements
```
ConfigurationError: Provider vosk doesn't support 48000Hz
```

**Solution**: Enable resampling or adjust configuration
```toml
[asr]
allow_resampling = true      # Enable automatic resampling
resample_quality = "medium"  # Balance quality and performance
```

#### 2. High latency in voice trigger
**Problem**: Voice trigger response is too slow

**Solution**: Optimize for low latency
```toml
[voice_trigger]
sample_rate = 16000          # Use optimal rate
resample_quality = "fast"    # Prioritize speed
```

#### 3. Poor transcription quality
**Problem**: ASR results are inaccurate

**Solution**: Increase quality settings
```toml
[asr]
sample_rate = 16000          # Use provider's preferred rate
resample_quality = "high"    # Maximize quality
```

#### 4. Cache not improving performance
**Problem**: No performance improvement from caching

**Solution**: Verify cache effectiveness
```python
# Monitor cache usage
cache_stats = AudioProcessor.get_cache_stats()
if cache_stats['hit_rate'] < 0.3:
    # Review sample rate consistency
    print("Low cache hit rate - check for consistent audio parameters")
```

### Validation Commands

Test your configuration with validation commands:

```bash
# Test microphone configuration
uv run python -m irene.tools.audio_test microphone

# Test provider compatibility
uv run python -m irene.tools.audio_test providers

# Benchmark resampling performance
uv run python -m irene.tools.audio_test benchmark
```

### Debug Logging

Enable detailed audio processing logs:

```toml
[logging]
level = "DEBUG"
modules = ["irene.utils.audio_helpers", "irene.components.asr_component", "irene.components.voice_trigger_component"]
```

This will provide detailed information about:
- Sample rate conversions
- Provider fallbacks
- Cache hits/misses
- Performance metrics

## Best Practices Summary

1. **Start with 16 kHz**: Universal compatibility and good performance
2. **Enable resampling**: Provides flexibility for hardware changes
3. **Use quality settings appropriately**: "fast" for voice trigger, "high" for ASR
4. **Monitor cache performance**: Ensure consistent audio parameters for cache effectiveness
5. **Test thoroughly**: Validate configuration with actual hardware before deployment
6. **Plan for fallbacks**: Configure multiple providers for robust operation
7. **Consider device constraints**: Adjust quality settings based on available processing power

For additional support, see the [Troubleshooting Guide](AUDIO_TROUBLESHOOTING.md) and [Performance Tuning Guide](AUDIO_PERFORMANCE_TUNING.md).
