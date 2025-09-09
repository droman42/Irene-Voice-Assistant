# Audio Troubleshooting Guide

This guide helps diagnose and resolve common audio-related issues in Irene Voice Assistant, particularly those related to sample rate compatibility, provider failures, and performance problems.

## Table of Contents

1. [Quick Diagnosis](#quick-diagnosis)
2. [Sample Rate Issues](#sample-rate-issues)
3. [Provider Problems](#provider-problems)
4. [Performance Issues](#performance-issues)
5. [Hardware Problems](#hardware-problems)
6. [Configuration Errors](#configuration-errors)
7. [Debug Tools](#debug-tools)
8. [Advanced Diagnostics](#advanced-diagnostics)

## Quick Diagnosis

### Symptom Checklist

Use this checklist to quickly identify the category of your issue:

**Audio Processing Issues:**
- [ ] No audio input detected
- [ ] Distorted or garbled audio
- [ ] Voice trigger not responding
- [ ] ASR transcription failing
- [ ] High latency/delays
- [ ] Poor transcription quality

**Error Messages:**
- [ ] "Sample rate mismatch"
- [ ] "Provider not available"
- [ ] "Resampling failed"
- [ ] "Configuration error"
- [ ] "Device not found"

**Performance Issues:**
- [ ] Slow processing
- [ ] High CPU usage
- [ ] Memory leaks
- [ ] Cache not working

### Quick Fixes

Try these common solutions first:

1. **Restart the service**: `sudo systemctl restart irene`
2. **Check microphone**: `arecord -l` (Linux) or system audio settings
3. **Verify configuration**: Check for syntax errors in TOML files
4. **Enable resampling**: Set `allow_resampling = true` in component configs
5. **Clear cache**: Restart service or clear audio processing cache

## Sample Rate Issues

### Error: "Sample rate mismatch"

#### Symptoms
```
ConfigurationError: Provider vosk doesn't support 48000Hz
AudioProcessingError: Sample rate 44100Hz not compatible with provider requirements
```

#### Diagnosis
```bash
# Check current audio device capabilities
arecord -l
pactl list sources

# Test microphone sample rate
arecord -d 2 -f cd -t raw | hexdump -C | head
```

#### Solutions

**1. Enable Automatic Resampling**
```toml
[asr]
allow_resampling = true
resample_quality = "medium"

[voice_trigger]
allow_resampling = true
resample_quality = "fast"
```

**2. Configure Explicit Sample Rate**
```toml
[inputs.microphone_config]
sample_rate = 16000          # Force microphone to 16kHz
auto_resample = true
```

**3. Provider-Specific Fix**
```toml
# For VOSK (check model requirements)
[asr.providers.vosk]
sample_rate = 16000          # Must match model

# For Whisper (flexible)
[asr.providers.whisper]
sample_rate = 16000          # Whisper handles resampling internally

# For Google Cloud (strict requirements)
[asr.providers.google_cloud]
sample_rate = 16000          # Must be exactly 8, 16, 22, 44, or 48 kHz
```

### Error: "Resampling failed"

#### Symptoms
```
ResamplingError: Audio resampling failed: librosa not available
ResamplingError: Invalid audio format for resampling
```

#### Diagnosis
```python
# Check available audio libraries
python -c "import librosa; print('librosa available')"
python -c "import numpy; print('numpy available')"
python -c "import soundfile; print('soundfile available')"
```

#### Solutions

**1. Install Missing Dependencies**
```bash
# Install audio processing libraries
uv add librosa numpy soundfile

# For development
uv add --dev librosa[complete]
```

**2. Fallback to Basic Resampling**
```toml
[asr]
resample_quality = "fast"    # Uses basic interpolation if librosa unavailable
```

**3. Check Audio Format**
```python
# Verify audio data format
from irene.utils.audio_helpers import get_audio_info

info = get_audio_info("test_audio.wav")
print(f"Format: {info}")
```

### Error: "No compatible providers found"

#### Symptoms
```
ProviderError: No compatible providers found for 96000Hz audio
FallbackError: All ASR providers failed sample rate validation
```

#### Solutions

**1. Add Flexible Provider**
```toml
[asr.providers.whisper]
enabled = true               # Whisper supports wide range of rates

[voice_trigger.providers.openwakeword]
enabled = true               # OpenWakeWord supports resampling
```

**2. Configure Provider Fallbacks**
```toml
[asr]
fallback_providers = ["whisper", "vosk"]  # Order of preference

[voice_trigger]
fallback_providers = ["openwakeword", "microwakeword"]
```

## Provider Problems

### Error: "Provider not available"

#### Symptoms
```
ProviderError: ASR provider 'vosk' not available (dependencies missing)
InitializationError: Voice trigger provider failed to load
```

#### Diagnosis
```bash
# Check provider dependencies
uv run python -c "from irene.providers.asr.vosk import VoskASRProvider; print('VOSK OK')"
uv run python -c "from irene.providers.voice_trigger.openwakeword import OpenWakeWordProvider; print('OWW OK')"

# Check model files
ls -la /path/to/models/
```

#### Solutions

**1. Install Provider Dependencies**
```bash
# For VOSK
uv add vosk

# For OpenWakeWord
uv add openwakeword

# For Whisper
uv add openai-whisper
```

**2. Check Model Paths**
```toml
[asr.providers.vosk]
enabled = true
model_path = "/correct/path/to/vosk/model"  # Verify this path exists

[voice_trigger.providers.openwakeword]
enabled = true
model_path = "/correct/path/to/openwakeword/models"
```

**3. Verify Model Compatibility**
```python
# Test VOSK model
import vosk
model = vosk.Model("/path/to/model")  # Should not raise exception

# Test OpenWakeWord model
import openwakeword
model = openwakeword.Model(model_path="/path/to/models")
```

### Error: "Provider initialization failed"

#### Symptoms
```
TypeError: VoskASRProvider missing required abstract methods
ConfigurationError: Invalid provider configuration
```

#### Solutions

**1. Update Provider Configuration**
```toml
[asr.providers.vosk]
enabled = true
model_path = "/path/to/model"
sample_rate = 16000
language = "en"
```

**2. Check Abstract Method Implementation**
```bash
# Update to latest provider version
uv update vosk openwakeword openai-whisper
```

**3. Reset to Default Configuration**
```toml
# Use minimal working configuration
[asr.providers.vosk]
enabled = true
model_path = "/path/to/model"
# Remove all other optional parameters
```

## Performance Issues

### High Latency in Voice Trigger

#### Symptoms
- Voice trigger takes >500ms to respond
- Real-time factor >0.5 (processing slower than real-time)

#### Diagnosis
```python
# Enable performance monitoring
from irene.components.voice_trigger_component import VoiceTriggerComponent

vt = VoiceTriggerComponent()
metrics = vt.get_runtime_metrics()
print(f"Average resampling time: {metrics['average_resampling_time_ms']:.2f}ms")
print(f"Detection success rate: {metrics['detection_success_rate']:.2%}")
```

#### Solutions

**1. Optimize Voice Trigger Settings**
```toml
[voice_trigger]
sample_rate = 16000          # Use optimal rate
resample_quality = "fast"    # Prioritize speed over quality
strict_validation = false    # Allow graceful degradation
```

**2. Use Efficient Provider**
```toml
[voice_trigger.providers.microwakeword]
enabled = true               # Optimized for speed
sample_rate = 16000          # No resampling needed

[voice_trigger.providers.openwakeword]
enabled = false              # Disable if not needed for speed
```

**3. Reduce Audio Chunk Size**
```toml
[inputs.microphone_config]
chunk_size = 512             # Smaller chunks = lower latency
```

### Poor ASR Performance

#### Symptoms
- Transcription takes >2x real-time
- High CPU usage during transcription
- Memory usage constantly increasing

#### Diagnosis
```python
# Monitor ASR performance
from irene.components.asr_component import ASRComponent

asr = ASRComponent()
metrics = asr.get_runtime_metrics()
print(f"Cache hit rate: {metrics['cache_statistics']['hit_rate']:.2%}")
print(f"Provider fallbacks: {metrics['provider_fallbacks']}")
```

#### Solutions

**1. Enable Caching**
```python
# Verify cache is working
from irene.utils.audio_helpers import AudioProcessor

cache_stats = AudioProcessor.get_cache_stats()
if cache_stats['hit_rate'] < 0.3:
    print("Consider using more consistent audio parameters")
```

**2. Optimize Provider Settings**
```toml
[asr.providers.whisper]
model_size = "base"          # Use smaller model for speed
device = "cpu"               # Or "cuda" if GPU available

[asr.providers.vosk]
sample_rate = 16000          # Match input exactly to avoid resampling
```

**3. Adjust Quality Settings**
```toml
[asr]
resample_quality = "medium"  # Balance quality and performance
allow_resampling = true      # Enable for flexibility
```

### Memory Leaks

#### Symptoms
- Memory usage increases over time
- System becomes unresponsive
- Out of memory errors

#### Diagnosis
```python
# Monitor memory usage
import psutil
import time

process = psutil.Process()
for i in range(10):
    memory = process.memory_info()
    print(f"RSS: {memory.rss/1024/1024:.1f}MB, VMS: {memory.vms/1024/1024:.1f}MB")
    time.sleep(30)  # Monitor every 30 seconds
```

#### Solutions

**1. Clear Audio Cache Periodically**
```python
# Clear cache when it gets too large
from irene.utils.audio_helpers import AudioProcessor

cache_stats = AudioProcessor.get_cache_stats()
if cache_stats['cache_size'] > 100:
    AudioProcessor.clear_cache()
```

**2. Reduce Buffer Sizes**
```toml
[inputs.microphone_config]
chunk_size = 1024            # Smaller chunks
```

**3. Monitor and Restart Service**
```bash
# Add memory monitoring to systemd service
[Service]
MemoryMax=512M
Restart=on-failure
```

## Hardware Problems

### Microphone Not Detected

#### Symptoms
```
DeviceError: No audio input devices found
OSError: [Errno -9996] Invalid device
```

#### Diagnosis
```bash
# List audio devices
arecord -l                   # ALSA devices
pactl list sources           # PulseAudio sources
lsusb                        # USB devices

# Test microphone directly
arecord -d 5 test.wav
aplay test.wav
```

#### Solutions

**1. Fix Device Permissions**
```bash
# Add user to audio group
sudo usermod -a -G audio $USER

# Check device permissions
ls -la /dev/snd/
```

**2. Configure Specific Device**
```toml
[inputs.microphone_config]
device_id = 1               # Use specific device ID
# Or
device_name = "USB Audio Device"  # Use device name
```

**3. Update Audio Drivers**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade alsa-utils pulseaudio

# Restart audio services
sudo systemctl restart alsa-state
sudo systemctl restart pulseaudio
```

### Audio Dropouts/Distortion

#### Symptoms
- Choppy or distorted audio
- Missing audio chunks
- Voice trigger false positives/negatives

#### Diagnosis
```bash
# Check audio system load
top -p $(pgrep -f pulseaudio)

# Test with different buffer sizes
arecord -D hw:0,0 -f S16_LE -r 16000 -c 1 -B 1000 test.wav
```

#### Solutions

**1. Increase Buffer Sizes**
```toml
[inputs.microphone_config]
chunk_size = 2048            # Larger buffer for stability
```

**2. Adjust Audio Priority**
```bash
# Set real-time priority for audio
sudo systemctl edit irene
[Service]
Nice=-10
IOSchedulingClass=1
```

**3. Check System Resources**
```bash
# Monitor system load
iostat 1
vmstat 1

# Reduce other audio applications
sudo systemctl stop bluetooth
```

## Configuration Errors

### Invalid TOML Syntax

#### Symptoms
```
TOMLDecodeError: Invalid escape sequence
ConfigurationError: Unable to parse configuration file
```

#### Diagnosis
```bash
# Validate TOML syntax
python -c "import tomli; tomli.load(open('config.toml', 'rb'))"

# Check for common issues
grep -n '\\\|".*".*"' config.toml
```

#### Solutions

**1. Fix Escape Sequences**
```toml
# Wrong
model_path = "C:\path\to\model"

# Correct
model_path = "C:/path/to/model"
# Or
model_path = """C:\path\to\model"""
```

**2. Fix Quote Issues**
```toml
# Wrong
language = "en-US with "quotes""

# Correct
language = 'en-US with "quotes"'
# Or
language = """en-US with "quotes" """
```

### Configuration Conflicts

#### Symptoms
```
ConfigurationError: Voice trigger requires 16000Hz but microphone provides 44100Hz with resampling disabled
ValidationError: Conflicting sample rate requirements
```

#### Solutions

**1. Enable Consistent Resampling**
```toml
[inputs.microphone_config]
auto_resample = true

[asr]
allow_resampling = true

[voice_trigger]
allow_resampling = true
```

**2. Use Common Sample Rate**
```toml
# Set everything to 16kHz for compatibility
[inputs.microphone_config]
sample_rate = 16000

[asr]
sample_rate = 16000

[voice_trigger]
sample_rate = 16000
```

## Debug Tools

### Enable Debug Logging

```toml
[logging]
level = "DEBUG"
modules = [
    "irene.utils.audio_helpers",
    "irene.components.asr_component",
    "irene.components.voice_trigger_component",
    "irene.providers.asr",
    "irene.providers.voice_trigger"
]
```

### Audio Test Commands

```bash
# Test microphone input
uv run python -m irene.tools.audio_test microphone

# Test provider compatibility
uv run python -m irene.tools.audio_test providers

# Benchmark performance
uv run python -m irene.tools.audio_test benchmark

# Test sample rate conversion
uv run python -m irene.tools.audio_test resample --source 44100 --target 16000
```

### Performance Monitoring

```python
# Monitor resampling performance
from irene.utils.audio_helpers import AudioProcessor

# Get cache statistics
stats = AudioProcessor.get_cache_stats()
print(f"Cache hit rate: {stats['hit_rate']:.2%}")
print(f"Cache size: {stats['cache_size']}")

# Monitor component performance
from irene.components.asr_component import ASRComponent
asr = ASRComponent()
metrics = asr.get_runtime_metrics()
print(f"Average resampling time: {metrics['average_resampling_time_ms']:.2f}ms")
```

## Advanced Diagnostics

### Audio Processing Pipeline Debug

```python
# Test complete pipeline
from irene.intents.models import AudioData
from irene.utils.audio_helpers import AudioProcessor, ConversionMethod
import time

# Create test audio
audio_data = AudioData(
    data=b'\x00\x01' * 1600,  # 100ms at 16kHz
    timestamp=time.time(),
    sample_rate=16000,
    channels=1,
    format="pcm16",
    metadata={}
)

# Test resampling
try:
    result = await AudioProcessor.resample_audio_data(
        audio_data, 44100, ConversionMethod.POLYPHASE
    )
    print(f"Resampling successful: {result.metadata}")
except Exception as e:
    print(f"Resampling failed: {e}")
```

### Provider Chain Testing

```python
# Test provider fallback chain
from irene.components.asr_component import ASRComponent

asr = ASRComponent()
# Simulate provider failure and test fallback
# (Implementation depends on specific test requirements)
```

### System Resource Monitoring

```bash
# Monitor during audio processing
watch -n 1 'ps aux | grep irene'
watch -n 1 'free -h'
iostat 1

# Monitor audio-specific resources
watch -n 1 'cat /proc/asound/cards'
pactl list sources short
```

## Getting Help

If these troubleshooting steps don't resolve your issue:

1. **Check logs**: Look for specific error messages in system logs
2. **Test with minimal config**: Use the simplest possible configuration
3. **Report issue**: Include:
   - Complete error messages
   - Configuration files
   - System information (`uname -a`, audio device info)
   - Debug logs with audio processing enabled

For additional support, see:
- [Audio Hardware Compatibility Guide](AUDIO_HARDWARE_COMPATIBILITY.md)
- [Performance Tuning Guide](AUDIO_PERFORMANCE_TUNING.md)
- [Provider-Specific Requirements](AUDIO_PROVIDER_REQUIREMENTS.md)
