# Voice Activity Detection (VAD) Configuration Guide

## Overview

This guide provides comprehensive information on configuring Voice Activity Detection (VAD) in Irene Voice Assistant v14.0.0+. VAD is now **enabled by default** and is essential for optimal speech processing performance.

## What is VAD?

Voice Activity Detection (VAD) is an intelligent audio processing system that:

- **Detects Speech Boundaries**: Automatically identifies when speech starts and ends
- **Filters Silence**: Skips processing during silent periods for efficiency
- **Accumulates Voice Segments**: Combines audio chunks into meaningful speech segments
- **Solves 23ms Chunk Problem**: Ensures ASR receives proper voice segments instead of tiny fragments

## Configuration Overview

VAD is configured in two places in your configuration file:

### 1. VAD Component Configuration

```toml
[vad]
enabled = true                # Enable/disable VAD processing
energy_threshold = 0.01       # RMS energy threshold for voice detection
sensitivity = 0.5             # Detection sensitivity multiplier
voice_duration_ms = 100       # Minimum voice duration in milliseconds
silence_duration_ms = 200     # Minimum silence duration to end voice segment
max_segment_duration_s = 10   # Maximum voice segment duration in seconds
use_zero_crossing_rate = true # Enable Zero Crossing Rate analysis
adaptive_threshold = false    # Enable adaptive threshold adjustment
```

### 2. Workflow VAD Processing

```toml
[workflows.unified_voice_assistant]
enable_vad_processing = true  # Enable VAD in audio processing pipeline
```

## Parameter Reference

### Core VAD Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `enabled` | `true` | boolean | Master switch for VAD processing |
| `energy_threshold` | `0.01` | 0.0-1.0 | RMS energy threshold for voice detection |
| `sensitivity` | `0.5` | 0.1-2.0 | Detection sensitivity multiplier |
| `voice_duration_ms` | `100` | 10-1000 | Minimum voice duration in milliseconds |
| `silence_duration_ms` | `200` | 50-2000 | Minimum silence to end voice segment |
| `max_segment_duration_s` | `10` | 1-60 | Maximum voice segment duration |

### Advanced Features

| Parameter | Default | Description |
|-----------|---------|-------------|
| `use_zero_crossing_rate` | `true` | Enable Zero Crossing Rate analysis for speech enhancement |
| `adaptive_threshold` | `false` | Enable adaptive threshold adjustment based on environment |
| `noise_percentile` | `15` | Percentile for noise floor estimation (1-50) |
| `voice_multiplier` | `3.0` | Multiplier above noise floor for voice threshold (1.0-10.0) |

### Performance Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `processing_timeout_ms` | `50` | Maximum processing time per frame (1-100) |
| `buffer_size_frames` | `100` | Maximum frames to buffer in voice segments (10-200) |
| `voice_frames_required` | `2` | Consecutive voice frames to confirm onset (1-10) |
| `silence_frames_required` | `5` | Consecutive silence frames to confirm end (1-20) |

## Environment-Specific Configurations

### Quiet Environment

For quiet home/office environments:

```toml
[vad]
enabled = true
energy_threshold = 0.005      # Lower threshold for quiet speech
sensitivity = 0.7             # Higher sensitivity
voice_duration_ms = 80        # Shorter minimum duration
silence_duration_ms = 150     # Shorter silence requirement
use_zero_crossing_rate = true
adaptive_threshold = false    # Consistent for quiet environments
```

### Noisy Environment

For noisy environments (traffic, open office, etc.):

```toml
[vad]
enabled = true
energy_threshold = 0.02       # Higher threshold to avoid noise
sensitivity = 0.3             # Lower sensitivity
voice_duration_ms = 150       # Longer minimum to filter noise
silence_duration_ms = 300     # Longer silence requirement
use_zero_crossing_rate = true
adaptive_threshold = true     # Enable adaptive thresholds
noise_percentile = 20         # Higher noise floor estimation
voice_multiplier = 4.0        # Higher multiplier above noise
```

### Low-Latency Setup

For minimal processing delay:

```toml
[vad]
enabled = true
energy_threshold = 0.01
sensitivity = 0.5
voice_duration_ms = 50        # Minimal duration for quick response
silence_duration_ms = 100     # Quick silence detection
max_segment_duration_s = 5    # Shorter maximum segments
processing_timeout_ms = 20    # Tight processing limits
buffer_size_frames = 50       # Smaller buffers
use_zero_crossing_rate = false # Disable for speed
adaptive_threshold = false
```

### High-Accuracy Setup

For maximum speech recognition accuracy:

```toml
[vad]
enabled = true
energy_threshold = 0.01
sensitivity = 0.5
voice_duration_ms = 120       # Longer duration for stability
silence_duration_ms = 250     # Longer silence for natural boundaries
max_segment_duration_s = 15   # Allow longer speech segments
use_zero_crossing_rate = true # Enable all features
adaptive_threshold = true     # Environmental adaptation
voice_frames_required = 3     # More confirmation frames
silence_frames_required = 7   # More silence confirmation
```

### Production Environment

For production deployment:

```toml
[vad]
enabled = true
energy_threshold = 0.012      # Balanced for varied conditions
sensitivity = 0.5
voice_duration_ms = 100
silence_duration_ms = 200
max_segment_duration_s = 12   # Slightly longer for natural speech
use_zero_crossing_rate = true
adaptive_threshold = true     # Handle varied environments
processing_timeout_ms = 40    # Balanced performance
buffer_size_frames = 100
```

## Configuration Examples by Use Case

### 1. Voice Assistant (with Wake Word)

```toml
[vad]
enabled = true
energy_threshold = 0.01
sensitivity = 0.5
voice_duration_ms = 100
silence_duration_ms = 200
max_segment_duration_s = 10
use_zero_crossing_rate = true
adaptive_threshold = false

[workflows.unified_voice_assistant]
enable_vad_processing = true
voice_trigger_enabled = true    # Wake word detection enabled
```

### 2. VOSK Runner (continuous speech recognition)

```toml
[vad]
enabled = true
energy_threshold = 0.008      # More sensitive for continuous listening
sensitivity = 0.6
voice_duration_ms = 80
silence_duration_ms = 150
max_segment_duration_s = 8
use_zero_crossing_rate = true
adaptive_threshold = false

[workflows.unified_voice_assistant]
enable_vad_processing = true
# Note: voice_trigger_enabled typically false for VOSK runner
```

### 3. Web API Audio Processing

```toml
[vad]
enabled = true
energy_threshold = 0.01
sensitivity = 0.5
voice_duration_ms = 100
silence_duration_ms = 200
max_segment_duration_s = 10
use_zero_crossing_rate = true
adaptive_threshold = false

[workflows.unified_voice_assistant]
enable_vad_processing = true
# Used with skip_wake_word=True in API calls
```

## Tuning Guidelines

### Step 1: Start with Default Configuration

Begin with the default configuration and test in your environment:

```toml
[vad]
enabled = true
energy_threshold = 0.01
sensitivity = 0.5
voice_duration_ms = 100
silence_duration_ms = 200
max_segment_duration_s = 10
use_zero_crossing_rate = true
adaptive_threshold = false
```

### Step 2: Adjust Energy Threshold

**If VAD is too sensitive (triggers on background noise):**
- Increase `energy_threshold` to 0.015 or 0.02
- Decrease `sensitivity` to 0.3 or 0.4

**If VAD misses quiet speech:**
- Decrease `energy_threshold` to 0.005 or 0.008
- Increase `sensitivity` to 0.6 or 0.7

### Step 3: Fine-tune Timing Parameters

**For responsive interaction:**
- Decrease `voice_duration_ms` to 80
- Decrease `silence_duration_ms` to 150

**For stable detection:**
- Increase `voice_duration_ms` to 120
- Increase `silence_duration_ms` to 250

### Step 4: Enable Advanced Features

**For noisy environments:**
- Set `adaptive_threshold = true`
- Adjust `noise_percentile` and `voice_multiplier`

**For maximum accuracy:**
- Keep `use_zero_crossing_rate = true`
- Increase `voice_frames_required` and `silence_frames_required`

## Monitoring VAD Performance

### Log Messages to Watch

Look for these log messages to monitor VAD performance:

```
INFO - VAD audio processor initialized: threshold=0.01, sensitivity=0.5
INFO - VAD Configuration: threshold=0.01, sensitivity=0.5, max_segment_duration=10s
INFO - Final VAD Metrics: chunks_processed=150, voice_segments=4, silence_skipped=89, avg_processing_time=0.08ms
```

### Key Metrics

1. **Processing Time**: Should be < 1ms per chunk for real-time performance
2. **Voice Segments**: Should correspond to actual speech periods
3. **Silence Skipped**: Higher percentage indicates good efficiency
4. **Buffer Overflows**: Should be 0 in normal operation

### Performance Indicators

**Good Performance:**
- Average processing time < 0.5ms
- 20-40% silence chunks skipped
- Voice segments match actual speech patterns
- No buffer overflows or timeouts

**Tuning Needed:**
- Processing time > 1ms consistently
- Very few or too many voice segments detected
- High buffer overflow count
- Frequent timeout events

## Testing Your Configuration

### 1. Test with Different Speech Patterns

```bash
# Test with various speech types
uv run python -m irene.runners.voice_assistant --config your-config.toml --debug
```

Try:
- Quiet speech
- Loud speech
- Fast speech
- Speech with pauses
- Background noise scenarios

### 2. Monitor Metrics

Check the log output for VAD metrics:

```
INFO - VAD Pipeline Performance: 2 results, 4.32s total duration
INFO - Final VAD Metrics: chunks_processed=180, voice_segments=2, silence_skipped=98, avg_processing_time=0.06ms
```

### 3. Verify Speech Recognition Quality

Compare speech recognition accuracy before and after VAD tuning:
- Test with the same audio samples
- Measure recognition accuracy
- Check for missed speech or false detections

## Common Configuration Patterns

### Pattern 1: Maximize Responsiveness

```toml
[vad]
enabled = true
energy_threshold = 0.01
sensitivity = 0.6
voice_duration_ms = 60
silence_duration_ms = 120
max_segment_duration_s = 8
processing_timeout_ms = 30
```

### Pattern 2: Maximize Accuracy

```toml
[vad]
enabled = true
energy_threshold = 0.01
sensitivity = 0.5
voice_duration_ms = 150
silence_duration_ms = 300
max_segment_duration_s = 15
use_zero_crossing_rate = true
adaptive_threshold = true
voice_frames_required = 3
silence_frames_required = 8
```

### Pattern 3: Minimize Resource Usage

```toml
[vad]
enabled = true
energy_threshold = 0.02
sensitivity = 0.4
voice_duration_ms = 100
silence_duration_ms = 200
max_segment_duration_s = 8
processing_timeout_ms = 20
buffer_size_frames = 50
use_zero_crossing_rate = false
adaptive_threshold = false
```

## Troubleshooting

### Issue: No Speech Detected

**Symptoms:** VAD never triggers, all audio treated as silence

**Solutions:**
1. Lower `energy_threshold` to 0.005
2. Increase `sensitivity` to 0.7
3. Check microphone levels and configuration
4. Verify audio input is working

### Issue: Too Many False Positives

**Symptoms:** VAD triggers on background noise, fan noise, etc.

**Solutions:**
1. Increase `energy_threshold` to 0.02
2. Decrease `sensitivity` to 0.3
3. Enable `adaptive_threshold = true`
4. Increase `voice_duration_ms` to filter short noise bursts

### Issue: Choppy Speech Detection

**Symptoms:** Long speech is broken into many short segments

**Solutions:**
1. Decrease `silence_duration_ms` to 150
2. Increase `max_segment_duration_s` to 15
3. Decrease `silence_frames_required` to 3

### Issue: Poor Performance

**Symptoms:** High CPU usage, slow processing

**Solutions:**
1. Disable `use_zero_crossing_rate`
2. Disable `adaptive_threshold`
3. Reduce `buffer_size_frames`
4. Increase `processing_timeout_ms`

## Advanced Configuration

### Custom VAD Algorithms

For specialized use cases, you can extend the VAD system:

```python
# Custom VAD implementation
class CustomVAD(SimpleVAD):
    def process_frame(self, audio_data: AudioData) -> VADResult:
        # Custom detection logic
        return super().process_frame(audio_data)
```

### Runtime Calibration

VAD can be calibrated at runtime based on environment:

```python
# Calibrate VAD threshold
calibrated_threshold = await audio_processor.calibrate(calibration_samples)
```

### Integration with External VAD

For production deployments, consider integrating with external VAD libraries:

- WebRTC VAD (for web-based applications)
- Silero VAD (for high accuracy)
- Custom ML-based VAD models

---

*This configuration guide helps you optimize VAD for your specific environment and use case. For additional help, see the Performance Tuning and Troubleshooting guides.*
