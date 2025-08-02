# Wake Word Training - Usage Example

This guide walks through the complete process of training a custom wake word model for ESP32-S3 nodes.

## Prerequisites

1. **Install system dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get update && sudo apt-get install portaudio19-dev python3-dev gcc
   
   # macOS (with Homebrew)
   brew install portaudio
   
   # Fedora/CentOS/RHEL
   sudo dnf install portaudio-devel python3-devel gcc
   ```

2. **Setup project environment**:
   ```bash
   cd ESP32/wakeword_training
   uv sync  # Install all dependencies
   # Try to install microWakeWord (may fail on some systems due to webrtcvad)
   uv pip install git+https://github.com/kahrendt/microWakeWord.git || echo "Using TensorFlow directly"
   ```

3. **Verify audio setup**:
   ```bash
   uv run python -c "import sounddevice; print(sounddevice.query_devices())"
   ```

## Step 1: Record Training Data

### Record positive samples (multiple speakers)

```bash
# Speaker 1 (50 samples)
uv run record-samples --wake_word jarvis --speaker_name alice --num_samples 50

# Speaker 2 (50 samples)  
uv run record-samples --wake_word jarvis --speaker_name bob --num_samples 50

# Speaker 3 (50 samples)
uv run record-samples --wake_word jarvis --speaker_name charlie --num_samples 50

# Speaker 4 (50 samples)
uv run record-samples --wake_word jarvis --speaker_name diana --num_samples 50
```

### Record negative samples (background noise)

```bash
# Record 2 hours of idle room noise
uv run record-samples --wake_word jarvis --record_negatives --duration 7200

# Record 2 hours of conversational speech (avoid saying "jarvis")
uv run record-samples --wake_word jarvis --record_negatives --duration 7200
```

### Check data readiness

```bash
uv run record-samples --wake_word jarvis --summary
```

**Expected output:**
```
=== Training Data Summary ===
📁 alice: 50 samples
📁 bob: 50 samples  
📁 charlie: 50 samples
📁 diana: 50 samples

📊 Totals:
   Positive samples: 200 (target: ≥200)
   Speakers: 4 (target: ≥4)
   Negative duration: 4.0h (target: ≥4h)

🎯 Training readiness:
   ✅ Positive samples: True
   ✅ Multiple speakers: True
   ✅ Negative duration: True
```

## Step 2: Train the Model

```bash
# Train with default parameters (recommended)
./scripts/train_model.sh jarvis

# Or train with custom parameters
./scripts/train_model.sh jarvis --epochs 60 --batch_size 32
```

**Expected output:**
```
🎯 Wake Word Training - microWakeWord medium-12-bn
==================================================

🔍 Checking training data...
✅ Found 200 positive samples
✅ Found 4 speakers
✅ Found 2 negative sample files

📁 Preparing training environment...
📝 Model will be saved to: models/jarvis_medium_20250131_143022.tflite

🚀 Starting model training...
[Training progress...]

🎉 Training completed successfully!
📁 Model saved: models/jarvis_medium_20250131_143022.tflite
📏 Model size: 138 KB
✅ Model size fits ESP32 flash budget
```

## Step 3: Validate the Model

```bash
uv run validate-model models/jarvis_medium_20250131_143022.tflite
```

**Expected output:**
```
🔍 Wake Word Model Validation
========================================

📁 Model loaded: models/jarvis_medium_20250131_143022.tflite

🎯 Testing Recall (target: ≥95%)
📊 Recall Results:
   Detected: 192/200 (96.0%)
   Target: ≥95% - ✅ PASS

🚫 Testing False Accept Rate (target: ≤2 per hour)
📊 False Accept Results:
   Rate: 1.2 per hour
   Target: ≤2/hour - ✅ PASS

⚡ Testing Inference Latency
📊 Latency Results (Python/TensorFlow):
   Average: 12.3ms

🏁 Validation Complete: ✅ PASS
   Model is ready for firmware integration!
```

## Step 4: Convert for ESP32 Firmware

```bash
# Convert for kitchen node
uv run convert-for-firmware \
  models/jarvis_medium_20250131_143022.tflite \
  --node_name kitchen \
  --output_dir firmware/
```

**Expected output:**
```
🔄 Converting model for ESP32 firmware...
   Input: models/jarvis_medium_20250131_143022.tflite
   Node: kitchen

✅ Conversion complete!
   📁 Header file: firmware/kitchen_ww_model.h
   📏 Model size: 138.0 KB
✅ Model size fits ESP32 flash budget
📋 Integration guide: firmware/kitchen_ww_model_integration_guide.md

🔄 Next steps:
1. Copy header file to ESP32 project: kitchen_ww_model.h
2. Follow integration guide for implementation details
3. Build and flash to ESP32-S3 node
4. Test wake word detection in target environment
```

## Step 5: ESP32 Integration

1. **Copy generated files to ESP32 project**:
   ```bash
   cp firmware/kitchen_ww_model.h /path/to/esp32-project/components/wakeword/include/
   ```

2. **Follow the integration guide**:
   ```bash
   cat firmware/kitchen_ww_model_integration_guide.md
   ```

3. **Build and flash**:
   ```bash
   cd /path/to/esp32-project
   idf.py build
   idf.py flash
   ```

## Troubleshooting

### Low Recall (<95%)
- **Record more positive samples** from different speakers
- **Improve recording quality** (reduce background noise)
- **Train longer** (increase epochs to 70-80)

### High False Accept Rate (>2/hour)
- **Record more negative samples** with diverse audio content
- **Increase confidence threshold** in validation (try 0.95)
- **Add more conversational speech** to negative samples

### Model Too Large (>140KB)
- **Use quantization** during training
- **Reduce model complexity** (consider "small" model size)
- **Post-training optimization** with TensorFlow Lite tools

### Training Fails
- **Check dependencies**: `uv sync` to reinstall all dependencies
- **Verify data format**: All WAV files should be 16kHz, 16-bit mono
- **Check disk space**: Training requires ~1GB temporary space

## File Structure After Training

```
wakeword_training/
├── data/
│   ├── positive/
│   │   ├── alice/          # 50 samples
│   │   ├── bob/            # 50 samples  
│   │   ├── charlie/        # 50 samples
│   │   └── diana/          # 50 samples
│   └── negative/           # 4+ hours of audio
├── models/
│   ├── jarvis_medium_20250131_143022.tflite
│   └── jarvis_medium_20250131_143022.log
├── configs/
│   └── jarvis_medium_20250131_143022.yaml
├── firmware/
│   ├── kitchen_ww_model.h
│   └── kitchen_ww_model_integration_guide.md
└── validation_report_20250131_143500.txt
```

## Performance Targets Met

- ✅ **Recall**: 96.0% (target: ≥95%)
- ✅ **False Accepts**: 1.2/hour (target: ≤2/hour)  
- ✅ **Model Size**: 138KB (target: ≤140KB)
- ✅ **Latency**: ~20-40ms on ESP32-S3 (target: ≤140ms)

Your custom wake word model is now ready for production deployment on ESP32-S3 nodes! 