# Voice Activity Detection (VAD) Troubleshooting Guide

## Overview

This guide helps diagnose and resolve common VAD-related issues in Irene Voice Assistant v14.0.0+. Use this guide when experiencing speech detection problems, performance issues, or unexpected behavior.

## Quick Diagnosis

### Check VAD Status

First, verify VAD is working properly:

```bash
# Run with debug logging
uv run python -m irene.runners.voice_assistant --config your-config.toml --debug
```

Look for these key log messages:

✅ **VAD Working Properly:**
```
INFO - VAD audio processor initialized: threshold=0.01, sensitivity=0.5
INFO - Using universal VAD audio processing
INFO - VAD Configuration: threshold=0.01, sensitivity=0.5, max_segment_duration=10s
INFO - Final VAD Metrics: chunks_processed=120, voice_segments=3, silence_skipped=78, avg_processing_time=0.08ms
```

❌ **VAD Problems:**
```
ERROR - VAD configuration missing or disabled. VAD processing is required
ERROR - Failed to initialize VAD processor: [error details]
WARNING - VAD processing timeout exceeded: 25.2ms > 20ms limit
ERROR - Buffer overflow detected: segment exceeded maximum duration
```

## Common Issues and Solutions

### Issue 1: No Speech Detection

**Symptoms:**
- VAD never triggers on speech
- All audio treated as silence
- No voice segments generated

**Diagnosis:**

1. **Check microphone input:**
   ```bash
   # Test microphone levels
   arecord -d 5 -f cd test.wav && aplay test.wav
   ```

2. **Check VAD thresholds:**
   ```toml
   [vad]
   energy_threshold = 0.005  # Try lower threshold
   sensitivity = 0.8         # Increase sensitivity
   ```

3. **Verify audio format:**
   ```toml
   [inputs.microphone_config]
   sample_rate = 16000      # Must match VAD expectations
   channels = 1             # Mono recommended
   ```

**Solutions:**

#### Solution 1A: Lower Detection Threshold
```toml
[vad]
enabled = true
energy_threshold = 0.003     # Much lower threshold
sensitivity = 0.8            # Higher sensitivity
voice_duration_ms = 50       # Shorter minimum duration
voice_frames_required = 1    # Immediate detection
```

#### Solution 1B: Check Audio Levels
```python
# Add to debug audio levels
import numpy as np

def debug_audio_levels(audio_data):
    audio_array = np.frombuffer(audio_data.data, dtype=np.int16)
    rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
    normalized_rms = rms / 32768.0
    print(f"Audio RMS: {normalized_rms:.6f}, Threshold: 0.01")
```

#### Solution 1C: Disable Advanced Features
```toml
[vad]
use_zero_crossing_rate = false  # Disable ZCR
adaptive_threshold = false      # Use static threshold
```

### Issue 2: Too Many False Positives

**Symptoms:**
- VAD triggers on background noise
- Constant voice detection in silent environment
- Many short voice segments

**Diagnosis:**

Check your environment:
- Background noise levels
- Fan noise, air conditioning
- Electromagnetic interference
- Room acoustics

**Solutions:**

#### Solution 2A: Increase Thresholds
```toml
[vad]
enabled = true
energy_threshold = 0.02      # Higher threshold
sensitivity = 0.3            # Lower sensitivity
voice_duration_ms = 150      # Longer minimum duration
voice_frames_required = 3    # More confirmation frames
```

#### Solution 2B: Enable Adaptive Threshold
```toml
[vad]
adaptive_threshold = true    # Adapt to environment
noise_percentile = 20        # Higher noise floor
voice_multiplier = 4.0       # Higher voice threshold
```

#### Solution 2C: Add Noise Filtering
```toml
[vad]
use_zero_crossing_rate = true  # Enable ZCR filtering
silence_frames_required = 8    # More silence confirmation
```

### Issue 3: Choppy Speech Detection

**Symptoms:**
- Long speech broken into many short segments
- Unnatural speech boundaries
- Frequent voice start/stop

**Diagnosis:**

Monitor voice segment patterns:
```
# Good: Natural segments
Voice segment 1: 5 chunks, 2.3s duration
Voice segment 2: 8 chunks, 3.1s duration

# Bad: Choppy segments  
Voice segment 1: 2 chunks, 0.8s duration
Voice segment 2: 1 chunks, 0.4s duration
Voice segment 3: 3 chunks, 1.1s duration
```

**Solutions:**

#### Solution 3A: Adjust Timing Parameters
```toml
[vad]
silence_duration_ms = 100    # Shorter silence requirement
max_segment_duration_s = 15  # Allow longer segments
silence_frames_required = 3  # Less silence confirmation
```

#### Solution 3B: Reduce Sensitivity
```toml
[vad]
energy_threshold = 0.008     # Lower threshold
sensitivity = 0.6            # Moderate sensitivity
voice_duration_ms = 80       # Shorter minimum
```

### Issue 4: Performance Problems

**Symptoms:**
- High CPU usage during VAD processing
- Audio processing delays
- System becomes unresponsive

**Diagnosis:**

Check performance metrics:
```
# Look for high processing times
INFO - Final VAD Metrics: avg_processing_time=1.25ms  # Too high!
WARNING - VAD processing timeout exceeded: 25.2ms > 20ms limit
```

**Solutions:**

#### Solution 4A: Use Fast Configuration
```toml
[vad]
enabled = true
energy_threshold = 0.015     # Higher for speed
use_zero_crossing_rate = false  # Disable expensive features
adaptive_threshold = false   # Static thresholds
processing_timeout_ms = 20   # Tight timeout
buffer_size_frames = 50      # Smaller buffers
```

#### Solution 4B: Optimize System
```bash
# Linux: Set CPU governor to performance
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Increase process priority
nice -n -10 uv run python -m irene.runners.voice_assistant
```

### Issue 5: Memory Issues

**Symptoms:**
- High memory usage (>200MB)
- Out of memory errors
- System swapping

**Solutions:**

#### Solution 5A: Reduce Memory Usage
```toml
[vad]
buffer_size_frames = 30      # Smaller buffers
max_segment_duration_s = 5   # Shorter segments
```

#### Solution 5B: Disable Caching
```python
# Modify VAD cache settings in vad.py
@lru_cache(maxsize=32)  # Reduce from default 256
```

### Issue 6: Poor Speech Recognition

**Symptoms:**
- VOSK still receives small chunks
- Poor ASR accuracy
- "No meaningful speech content" errors

**Diagnosis:**

Check voice segment sizes:
```
# Good: Proper segments
Voice segment 1: 45 chunks, 2048ms duration  # >1 second
Voice segment 2: 62 chunks, 2816ms duration

# Bad: Still too small
Voice segment 1: 2 chunks, 92ms duration    # <1 second
Voice segment 2: 1 chunks, 46ms duration
```

**Solutions:**

#### Solution 6A: Ensure Proper Segments
```toml
[vad]
voice_duration_ms = 200      # Longer minimum
silence_duration_ms = 300    # Longer silence requirement
max_segment_duration_s = 12  # Allow longer speech
```

#### Solution 6B: Verify VAD is Active
```toml
[workflows.unified_voice_assistant]
enable_vad_processing = true  # Must be enabled!
```

### Issue 7: VAD Configuration Errors

**Symptoms:**
- "VAD configuration missing" errors
- Workflow fails to initialize
- Audio processing not working

**Solutions:**

#### Solution 7A: Complete VAD Configuration
```toml
# Ensure both sections are present
[vad]
enabled = true
energy_threshold = 0.01
# ... other VAD parameters

[workflows.unified_voice_assistant]
enable_vad_processing = true
```

#### Solution 7B: Check Configuration Syntax
```bash
# Validate TOML syntax
python -c "import tomllib; tomllib.load(open('your-config.toml', 'rb'))"
```

## Diagnostic Tools

### 1. VAD Debug Mode

Add debug logging to your configuration:

```toml
debug = true
log_level = "DEBUG"
```

### 2. Audio Level Monitor

Create a simple audio level monitor:

```python
#!/usr/bin/env python3
import asyncio
import numpy as np
from irene.inputs.microphone import MicrophoneInput

async def monitor_audio_levels():
    """Monitor real-time audio levels for VAD tuning"""
    microphone = MicrophoneInput()
    await microphone.initialize()
    
    print("Monitoring audio levels (Ctrl+C to stop):")
    print("RMS Level | Energy | Status")
    print("-" * 30)
    
    async for audio_data in microphone.get_audio_stream():
        audio_array = np.frombuffer(audio_data.data, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        energy = rms / 32768.0
        
        status = "VOICE" if energy > 0.01 else "SILENCE"
        print(f"{rms:8.0f} | {energy:.6f} | {status}")

if __name__ == "__main__":
    asyncio.run(monitor_audio_levels())
```

### 3. VAD Test Script

```python
#!/usr/bin/env python3
"""Test VAD configuration with sample audio"""
import asyncio
from irene.config.models import VADConfig
from irene.workflows.audio_processor import UniversalAudioProcessor
from irene.intents.models import AudioData

async def test_vad_config():
    # Your configuration
    config = VADConfig(
        enabled=True,
        energy_threshold=0.01,
        sensitivity=0.5,
        # ... other parameters
    )
    
    # Create processor
    processor = UniversalAudioProcessor(config)
    
    # Test with sample audio
    # (Replace with actual audio data)
    test_audio = AudioData(
        data=b'\x00' * 1024,  # Sample audio
        sample_rate=16000,
        channels=1
    )
    
    # Process and check results
    result = await processor.process_audio_chunk(test_audio)
    print(f"VAD Result: {result}")
    
    # Check metrics
    metrics = processor.get_processing_metrics()
    print(f"Processing time: {metrics.average_processing_time_ms:.2f}ms")

if __name__ == "__main__":
    asyncio.run(test_vad_config())
```

## Environment-Specific Issues

### Quiet Environments

**Problem:** VAD too sensitive, triggers on minimal noise

**Solution:**
```toml
[vad]
energy_threshold = 0.005     # Very low threshold
sensitivity = 0.8            # High sensitivity
adaptive_threshold = false   # Consistent behavior
```

### Noisy Environments

**Problem:** VAD misses speech due to background noise

**Solution:**
```toml
[vad]
energy_threshold = 0.02      # Higher threshold
adaptive_threshold = true    # Adapt to noise
noise_percentile = 25        # Account for noise floor
voice_multiplier = 5.0       # Strong voice signal required
```

### Reverberant Rooms

**Problem:** Echo and reverb confuse VAD

**Solution:**
```toml
[vad]
voice_duration_ms = 150      # Longer confirmation
silence_duration_ms = 400    # Account for reverb decay
use_zero_crossing_rate = true # Help distinguish speech
```

### Multiple Speakers

**Problem:** VAD segments overlap between speakers

**Solution:**
```toml
[vad]
max_segment_duration_s = 6   # Shorter segments
silence_duration_ms = 150    # Quick speaker changes
voice_frames_required = 2    # Fast detection
```

## Hardware-Specific Issues

### USB Microphones

**Common Issues:**
- Inconsistent sample rates
- Buffer size limitations
- Driver compatibility

**Solutions:**
```toml
[inputs.microphone_config]
chunk_size = 2048           # Larger chunks for USB
sample_rate = 16000         # Fixed rate
auto_resample = true        # Handle rate mismatches
```

### Bluetooth Audio

**Common Issues:**
- Audio latency
- Compression artifacts
- Connection drops

**Solutions:**
```toml
[vad]
energy_threshold = 0.015    # Account for compression
voice_duration_ms = 120     # Account for latency
adaptive_threshold = true   # Handle artifacts
```

### Built-in Microphones

**Common Issues:**
- Low sensitivity
- Background noise
- AGC interference

**Solutions:**
```toml
[vad]
energy_threshold = 0.005    # Very sensitive
sensitivity = 0.9           # High sensitivity
use_zero_crossing_rate = true # Filter noise
```

## Advanced Troubleshooting

### 1. Network Audio Issues

For network-based audio input:

```toml
[vad]
processing_timeout_ms = 100  # Account for network latency
buffer_size_frames = 150     # Larger buffers
```

### 2. Real-time Audio Issues

For real-time streaming:

```toml
[vad]
voice_duration_ms = 50      # Quick response
silence_duration_ms = 100   # Minimal delay
processing_timeout_ms = 15  # Tight constraints
```

### 3. Multi-language Issues

For multi-language environments:

```toml
[vad]
use_zero_crossing_rate = true  # Language-agnostic
adaptive_threshold = true      # Adapt to different speakers
voice_duration_ms = 80         # Quick language switching
```

## Getting Help

### 1. Collect Debug Information

Before seeking help, collect this information:

```bash
# System information
uname -a
python --version

# Audio system information
arecord -l
aplay -l

# VAD configuration
cat your-config.toml | grep -A 20 "\[vad\]"

# Debug logs
uv run python -m irene.runners.voice_assistant --config your-config.toml --debug 2>&1 | tee vad-debug.log
```

### 2. Performance Metrics

Collect performance data:

```bash
# CPU and memory usage during VAD processing
top -p $(pgrep -f "irene") -d 1

# Audio system status
pulseaudio --check -v  # Linux
```

### 3. Create Minimal Test Case

Create a minimal reproduction:

```toml
# minimal-vad-test.toml
[vad]
enabled = true
energy_threshold = 0.01
sensitivity = 0.5

[workflows.unified_voice_assistant]
enable_vad_processing = true

# Minimal other configuration
# ...
```

### 4. Report Issues

When reporting VAD issues, include:

1. Complete VAD configuration
2. Hardware specifications
3. Operating system details
4. Debug logs showing the problem
5. Performance metrics
6. Steps to reproduce
7. Expected vs actual behavior

---

*This troubleshooting guide covers most common VAD issues. For additional help, check the Configuration Guide and Performance Guide, or report issues with detailed information.*
