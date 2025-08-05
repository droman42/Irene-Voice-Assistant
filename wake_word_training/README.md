# Wake Word Model Training

This directory contains everything needed to train custom wake word models for multiple target platforms using an ESP32-compatible TensorFlow implementation.

**Supported Targets:**
- **ESP32-S3**: C header files for firmware integration  
- **Python**: ONNX/TFLite models for OpenWakeWord and microWakeWord providers
- **Multi-platform**: Optimized models for different deployment scenarios

## Quick Start

1. **Setup environment**: `uv add tensorflow librosa numpy pyyaml`
2. **Prepare training data**: Use `irene-record-samples` to collect audio samples
3. **Train model**: Run `irene-train-wake-word <wake_word>`
4. **Validate**: Use `irene-validate-model <model.tflite>` to test performance
5. **Convert for target platforms**:
   - ESP32: `irene-convert-to-esp32 model.tflite`
   - Python/ONNX: `irene-convert-to-onnx model.tflite`
   - Python/TFLite: Already generated during training

## Training Requirements

Based on the ESP32 firmware specification, we need:

- **Positive samples**: ≥200 clips (4+ speakers × 50+ clips each)
- **Negative samples**: ≥4 hours total (2h idle room noise + 2h conversational speech)  
- **Audio format**: 16 kHz, 16-bit mono WAV files
- **Model architecture**: medium-12-bn (12 × Conv1D + BatchNorm)

## ESP32 Compatibility Guarantees

Our TensorFlow trainer ensures 100% ESP32 compatibility:

| **Requirement** | **Value** | **Status** |
|-----------------|-----------|------------|
| **Input Shape** | `[1, 49, 40]` | ✅ Enforced |
| **Model Size** | ≤140KB | ✅ Validated |
| **Inference Time** | ≤25ms | ✅ Optimized |
| **Memory Usage** | ≤70KB PSRAM | ✅ Targeted |
| **Architecture** | medium-12-bn | ✅ Implemented |

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
│   ├── tensorflow_trainer.py  # ESP32-compatible TensorFlow trainer
│   ├── validate_model.py  # Model validation
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

- **Flash impact**: ~140kB for medium model (ESP32 limit enforced)
- **PSRAM usage**: ~70kB for model weights during inference
- **Training time**: ~1-2 hours on modern GPU

## Setup

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
# Install core dependencies
uv add tensorflow librosa numpy pyyaml

# Optional: For audio validation and visualization
uv add soundfile matplotlib seaborn

# Verify installation
python -c "import tensorflow; print('TensorFlow:', tensorflow.__version__)"
python -c "import librosa; print('Librosa:', librosa.__version__)"
```

## Training a Model

```bash
# 1. Collect training data
irene-record-samples --wake_word jarvis --speaker_name your_name

# 2. Record negative samples
irene-record-samples --wake_word jarvis --record_negatives --duration 7200

# 3. Train ESP32-compatible model
irene-train-wake-word jarvis --epochs 55 --batch_size 16

# 4. Validate model performance
irene-validate-model models/jarvis_medium_20250113_143000.tflite

# 5. Convert for ESP32 deployment
irene-convert-to-esp32 models/jarvis_medium_20250113_143000.tflite
```

## Advantages Over microWakeWord

| **Aspect** | **microWakeWord** | **TensorFlow Trainer** |
|------------|-------------------|-------------------------|
| **Dependencies** | Complex C++ builds, `pymicro-features` | Pure Python, widely supported |
| **Python Versions** | Locked to 3.10 only | Modern Python 3.10+ |
| **Training Process** | Subprocess spawning | Native TensorFlow APIs |
| **ESP32 Validation** | Manual size checking | Automatic size enforcement |
| **Integration** | External dependency | Integrated with Irene |
| **Maintenance** | External project | Full control |

## Next Steps

1. Review the complete workflow in `USAGE_EXAMPLE.md`
2. Collect training data using `irene-record-samples`
3. Train your first model with `irene-train-wake-word`
4. Deploy to ESP32 firmware using `irene-convert-to-esp32`

## Integration with Irene Voice Assistant

This wake word training toolkit is fully integrated with the main Irene project:

- **VoiceTrigger Component**: Trained models work directly with microWakeWord and OpenWakeWord providers
- **ESP32 Compatibility**: Guaranteed compatibility with Irene's ESP32 firmware
- **Native Training**: No external dependencies or process spawning
- **Modern Tooling**: Built on TensorFlow 2.x with proper callbacks and monitoring 