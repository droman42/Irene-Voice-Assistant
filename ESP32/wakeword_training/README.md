# Wake Word Model Training

This directory contains everything needed to train custom wake word models for ESP32-S3 nodes using the microWakeWord "medium-12-bn" architecture.

## Quick Start

1. **Setup environment**: `cd ESP32/wakeword_training && uv sync`
2. **Prepare training data**: Use `uv run record-samples` to collect audio samples
3. **Train model**: Run `scripts/train_model.sh` with your wake word
4. **Validate**: Use `uv run validate-model` to test performance
5. **Convert**: Use `uv run convert-for-firmware` to generate firmware headers

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
wakeword_training/
├── data/                    # Training data organization
│   ├── positive/           # Wake word samples
│   ├── negative/           # Background noise and speech
│   └── validation/         # Test sets
├── models/                 # Trained models output
├── scripts/               # Training and utility scripts
├── configs/               # Training configurations
└── firmware/              # Converted firmware headers
```

## Resource Budget

- **Flash impact**: ~140kB for medium model
- **PSRAM usage**: ~160kB for model weights
- **Training time**: ~2-4 hours on modern GPU

## Setup

This is an independent Python project managed with `uv`. It has its own virtual environment and dependencies separate from the main Irene project.

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
# Navigate to the wake word training directory
cd ESP32/wakeword_training

# Install all dependencies (creates virtual environment automatically)
uv sync

# Install microWakeWord training tool (external dependency)
# Note: May fail due to webrtcvad compilation issues on some systems
# Alternative: Use TensorFlow directly for training
uv pip install git+https://github.com/kahrendt/microWakeWord.git || echo "microWakeWord install failed, using TensorFlow directly"

# Verify installation
uv run python -c "import tensorflow; print('TensorFlow:', tensorflow.__version__)"
```

## Next Steps

1. Review the complete workflow in `USAGE_EXAMPLE.md`
2. Run `uv run record-samples --help` for data collection options
3. Follow the guided recording process to gather training data
4. Train and validate your custom wake word model 