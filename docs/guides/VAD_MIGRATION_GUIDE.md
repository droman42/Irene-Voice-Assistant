# Voice Activity Detection (VAD) Migration Guide

## Overview

This guide helps existing Irene Voice Assistant installations migrate to VAD-enabled processing. VAD is now **enabled by default** in all configurations to solve the critical 23ms audio chunk processing issue.

## What Changed in Phase 6

### 🔄 **Automatic Migration (v14.0.0+)**

Starting with v14.0.0, VAD processing is **enabled by default** in all configurations:

- **New Installations**: VAD is automatically enabled, no action required
- **Existing Installations**: Follow the migration steps below

### 🏆 **Benefits of VAD Processing**

- **Fixes 23ms Audio Chunks**: VOSK now receives meaningful voice segments instead of tiny fragments
- **Improved Speech Recognition**: Better accuracy and response times
- **Reduced CPU Usage**: Silence periods are automatically skipped
- **Natural Speech Boundaries**: Automatic detection of speech start/end
- **Universal Compatibility**: Works with and without voice trigger enabled

## Migration Steps

### Step 1: Check Your Current Configuration

First, determine your current configuration file location:

```bash
# Common configuration files:
ls -la configs/
# Look for: development.toml, voice.toml, full.toml, minimal.toml, or your custom config
```

### Step 2: Enable VAD in Your Configuration

#### Option A: Update Existing Configuration File

Add the following sections to your existing configuration file:

```toml
# ============================================================
# VAD CONFIGURATION - Voice Activity Detection
# ============================================================
[vad]
enabled = true                # Enable VAD to solve 23ms chunk problem
energy_threshold = 0.01       # RMS energy threshold for voice detection
sensitivity = 0.5             # Detection sensitivity multiplier
voice_duration_ms = 100       # Minimum voice duration in milliseconds
silence_duration_ms = 200     # Minimum silence duration to end voice segment
max_segment_duration_s = 10   # Maximum voice segment duration in seconds
use_zero_crossing_rate = true # Enable Zero Crossing Rate analysis
adaptive_threshold = false    # Disable for consistent testing

# ============================================================
# WORKFLOW VAD PROCESSING
# ============================================================
[workflows.unified_voice_assistant]
enable_vad_processing = true  # Enable VAD processing to solve chunk problem
```

#### Option B: Use Updated Configuration Files

Copy one of the updated configuration files:

```bash
# For voice assistant usage:
cp configs/voice.toml my-config.toml

# For development:
cp configs/development.toml my-config.toml

# For full features:
cp configs/full.toml my-config.toml

# For minimal setup:
cp configs/minimal.toml my-config.toml
```

### Step 3: Test VAD Processing

Start Irene with your updated configuration:

```bash
# Test with your configuration
uv run python -m irene.runners.voice_assistant --config my-config.toml

# Or test with development config
uv run python -m irene.runners.voice_assistant --config configs/development.toml
```

Look for VAD-related log messages:

```
INFO - VAD audio processor initialized: threshold=0.01, sensitivity=0.5
INFO - VAD enabled, using universal audio processing
INFO - VAD processing enabled for workflow pipeline
```

### Step 4: Verify VOSK Processing (if applicable)

If you're using VOSK ASR, test that it now receives proper voice segments:

```bash
# Test VOSK with VAD
uv run python -m irene.runners.voice_assistant --config configs/vosk-test.toml
```

Expected improvements:
- No more "23ms chunk" errors
- Better speech recognition accuracy
- Natural conversation flow

## Troubleshooting

### Issue: VAD Not Working

**Symptoms:**
- Still seeing 23ms chunk processing
- Log shows "VAD disabled, using legacy audio processing"

**Solutions:**
1. Check both VAD configuration sections are present:
   - `[vad]` section with `enabled = true`
   - `[workflows.unified_voice_assistant]` section with `enable_vad_processing = true`

2. Verify configuration file is being loaded:
   ```bash
   uv run python -m irene.runners.voice_assistant --config your-config.toml --debug
   ```

### Issue: Audio Not Detected

**Symptoms:**
- VAD enabled but no speech detection
- Log shows all silence

**Solutions:**
1. Lower energy threshold:
   ```toml
   [vad]
   energy_threshold = 0.005  # Lower threshold for quieter environments
   sensitivity = 0.7         # Higher sensitivity
   ```

2. Check microphone configuration:
   ```toml
   [inputs.microphone_config]
   sample_rate = 16000  # Ensure compatibility
   channels = 1         # Mono recommended
   ```

### Issue: False Voice Detection

**Symptoms:**
- VAD triggers on background noise
- Frequent false positive detections

**Solutions:**
1. Increase energy threshold:
   ```toml
   [vad]
   energy_threshold = 0.02   # Higher threshold for noisy environments
   sensitivity = 0.3         # Lower sensitivity
   ```

2. Enable adaptive threshold:
   ```toml
   [vad]
   adaptive_threshold = true  # Automatically adjust to environment
   noise_percentile = 15      # Background noise estimation
   ```

### Issue: Performance Problems

**Symptoms:**
- High CPU usage
- Processing delays

**Solutions:**
1. Optimize VAD configuration:
   ```toml
   [vad]
   processing_timeout_ms = 30     # Reduce processing time limit
   use_zero_crossing_rate = false # Disable if not needed
   buffer_size_frames = 50        # Reduce buffer size
   ```

2. Check real-time processing:
   ```bash
   # Look for processing time logs
   grep "processing time" logs/irene.log
   ```

## Configuration Reference

### VAD Configuration Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `enabled` | `true` | bool | Enable/disable VAD processing |
| `energy_threshold` | `0.01` | 0.0-1.0 | RMS energy threshold for voice detection |
| `sensitivity` | `0.5` | 0.1-2.0 | Detection sensitivity multiplier |
| `voice_duration_ms` | `100` | 10-1000 | Minimum voice duration in milliseconds |
| `silence_duration_ms` | `200` | 50-2000 | Minimum silence to end voice segment |
| `max_segment_duration_s` | `10` | 1-60 | Maximum voice segment duration |
| `use_zero_crossing_rate` | `true` | bool | Enable ZCR analysis for speech enhancement |
| `adaptive_threshold` | `false` | bool | Enable adaptive threshold adjustment |

### Environment-Specific Recommendations

#### Quiet Environment
```toml
[vad]
energy_threshold = 0.005
sensitivity = 0.7
voice_duration_ms = 80
```

#### Noisy Environment
```toml
[vad]
energy_threshold = 0.02
sensitivity = 0.3
adaptive_threshold = true
```

#### Low-Latency Setup
```toml
[vad]
voice_duration_ms = 50
silence_duration_ms = 150
processing_timeout_ms = 30
```

#### High-Accuracy Setup
```toml
[vad]
use_zero_crossing_rate = true
adaptive_threshold = true
voice_duration_ms = 120
```

## Rollback Instructions (Emergency)

If you need to temporarily disable VAD and revert to legacy processing:

```toml
[vad]
enabled = false

[workflows.unified_voice_assistant]
enable_vad_processing = false
```

**Warning**: Disabling VAD will restore the 23ms chunk problem. This should only be used for emergency situations.

## Support and Further Information

- **Documentation**: See `docs/vad_improvements.md` for technical details
- **Configuration Guide**: See `docs/VAD_CONFIGURATION_GUIDE.md` (created in Phase 6.3)
- **Performance Tuning**: See `docs/VAD_PERFORMANCE_GUIDE.md` (created in Phase 6.3)
- **Troubleshooting**: See `docs/VAD_TROUBLESHOOTING_GUIDE.md` (created in Phase 6.3)

## Version Compatibility

- **v14.0.0+**: VAD enabled by default, full feature support
- **v13.x**: VAD available but disabled by default, manual configuration required
- **v12.x and below**: VAD not available, requires upgrade

---

*Migration completed successfully! Your Irene Voice Assistant now uses advanced Voice Activity Detection for optimal speech processing.*
