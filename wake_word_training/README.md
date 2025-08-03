# Wake Word Model Training

This directory contains everything needed to train custom wake word models for multiple target platforms using the microWakeWord "medium-12-bn" architecture.

**Supported Targets:**
- **ESP32-S3**: C header files for firmware integration
- **Python**: ONNX/TFLite models for OpenWakeWord and microWakeWord providers
- **Multi-platform**: Optimized models for different deployment scenarios

## Quick Start

1. **Setup environment**: `uv add irene-voice-assistant[wake-word-training]`
2. **Prepare training data**: Use `irene-record-samples` to collect audio samples
3. **Train model**: Run `irene-train-wake-word` with your wake word
4. **Validate**: Use `irene-validate-model` to test performance
5. **Convert for target platforms**:
   - ESP32: `irene-convert-to-esp32 model.tflite`
   - Python/ONNX: `irene-convert-to-onnx model.tflite`
   - Python/TFLite: `irene-convert-to-tflite model.tflite`

## Training Requirements

Based on the firmware specification, we need:

- **Positive samples**: ≥200 clips (4+ speakers × 50+ clips each)
- **Negative samples**: ≥4 hours total (2h idle room noise + 2h conversational speech)
- **Audio format**: 16 kHz, 16-bit mono WAV files
- **Model architecture**: medium-12-bn (12 × Conv1D + BatchNorm)

## Validation Targets

| Metric | Target |
|--------|--------|
| **Recall (TPR)** | ≥95% (≥190/200 test positives) |
| **False Accepts** | ≤2 per hour on 3h negative stream |
| **Wake Latency** | ≤140ms averaged on ESP32-S3 @ 240MHz |

## Directory Structure

```
wake_word_training/
├── data/                    # Training data organization
│   ├── positive/           # Wake word samples
│   ├── negative/           # Background noise and speech
│   └── validation/         # Test sets
├── models/                 # Trained models output
├── scripts/               # Training and utility scripts
│   ├── record_samples.py  # Audio data collection
│   ├── validate_model.py  # Model validation
│   ├── train_model.py     # Model training (Python port)
│   └── converters/        # Multi-target model conversion
│       ├── to_esp32.py    # → ESP32 C headers
│       ├── to_onnx.py     # → ONNX for OpenWakeWord
│       └── to_tflite.py   # → Optimized TFLite
├── configs/               # Training configurations
├── outputs/               # Multi-target outputs
│   ├── esp32/            # ESP32 firmware headers
│   ├── python/           # Python model files
│   └── onnx/             # ONNX model files
└── firmware/             # Legacy ESP32 outputs (deprecated)
```

## Resource Budget

- **Flash impact**: ~140kB for medium model
- **PSRAM usage**: ~160kB for model weights
- **Training time**: ~2-4 hours on modern GPU

## Setup

This is now integrated with the main Irene Voice Assistant project. No separate environment needed!

### System Dependencies

Install required system packages for audio processing:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install portaudio19-dev python3-dev gcc

# macOS (with Homebrew)
brew install portaudio

# Fedora/CentOS/RHEL
sudo dnf install portaudio-devel python3-devel gcc
```

### Python Environment Setup

```bash
# Install Irene with wake word training tools
uv add irene-voice-assistant[wake-word-training]

# Install microWakeWord training tool (external dependency)
# Note: May fail due to webrtcvad compilation issues on some systems
uv add git+https://github.com/kahrendt/microWakeWord.git

# Verify installation
python -c "import tensorflow; print('TensorFlow:', tensorflow.__version__)"

# Test the integrated tools
irene-record-samples --help
irene-train-wake-word --help
```

## Next Steps

1. Review the complete workflow in `USAGE_EXAMPLE.md`
2. Run `irene-record-samples --help` for data collection options
3. Follow the guided recording process to gather training data
4. Train and validate your custom wake word model

## Integration with Irene Voice Assistant

This wake word training toolkit is now integrated with the main Irene project:

- **VoiceTrigger Component**: Trained models can be used with the planned VoiceTrigger component
- **Multiple Providers**: Models work with microWakeWord and OpenWakeWord providers
- **ESP32 Compatibility**: Same training pipeline supports both Python and ESP32 deployments
- **Unified Commands**: All tools available as `irene-*` commands globally 