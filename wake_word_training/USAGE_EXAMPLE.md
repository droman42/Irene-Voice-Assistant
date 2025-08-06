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
   # Install wake word training dependencies (if working in project directory)
   uv sync --extra wake-word-training
   
   # Or if installing as external package
   # uv add irene-voice-assistant[wake-word-training]
   
   # Verify TensorFlow installation
   python -c "import tensorflow; print('TensorFlow:', tensorflow.__version__)"
   python -c "import librosa; print('Librosa:', librosa.__version__)"
   ```

3. **Verify audio setup**:
   ```bash
   python -c "import sounddevice; print(sounddevice.query_devices())"
   ```

## Step 1: Record Training Data

### Record positive samples (multiple speakers)

```bash
# Speaker 1 (50 samples)
irene-record-samples --wake_word jarvis --speaker_name alice --num_samples 50

# Speaker 2 (50 samples)  
irene-record-samples --wake_word jarvis --speaker_name bob --num_samples 50

# Speaker 3 (50 samples)
irene-record-samples --wake_word jarvis --speaker_name charlie --num_samples 50

# Speaker 4 (50 samples)
irene-record-samples --wake_word jarvis --speaker_name diana --num_samples 50
```

### Record negative samples (background noise)

```bash
# Record 2 hours of idle room noise
irene-record-samples --wake_word jarvis --record_negatives --duration 7200

# Record 2 hours of conversational speech (avoid saying "jarvis")
irene-record-samples --wake_word jarvis --record_negatives --duration 7200
```

### Check data readiness

```bash
irene-record-samples --wake_word jarvis --summary
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
irene-train-wake-word jarvis

# Or train with custom parameters
irene-train-wake-word jarvis --epochs 60 --batch_size 32

# Or run directly with python
python scripts/tensorflow_trainer.py jarvis --epochs 55 --batch_size 16
```

**Expected output:**
```
🎯 ESP32-Compatible Wake Word Training
====================================

🔍 Checking training data...
📄 Found 200 positive samples
📄 Found 500 negative samples

📊 Loading and preprocessing training data...
Training set: 560 samples
Validation set: 140 samples
Feature shape: (560, 49, 40)

🏗️ Building ESP32-compatible model architecture...
Model parameters: 45,234
Estimated size: 176.9 KB
⚠️  Warning: Model size (176.9 KB) exceeds ESP32 limit (140 KB)

🚀 Starting training...
Epoch 1/55: loss: 0.6234 - accuracy: 0.6429 - val_loss: 0.5891 - val_accuracy: 0.7143
...
Epoch 55/55: loss: 0.1234 - accuracy: 0.9643 - val_loss: 0.1456 - val_accuracy: 0.9500

🔄 Converting to TensorFlow Lite for ESP32 with INT8 quantization...
📏 TFLite INT8 model size: 132.1 KB
✅ TFLite model fits ESP32 constraints (140 KB limit)

✅ ESP32-compatible training completed successfully!
📦 TFLite model: models/jarvis_medium_20250113_143000.tflite
📦 Keras model: models/jarvis_medium_20250113_143000.h5
📝 Config: configs/jarvis_medium_20250113_143000_config.yaml
🎯 Validation accuracy: 0.950
📏 Model size: 132.1 KB (ESP32 limit: 140 KB)

🚀 ESP32 Integration:
   1. Convert to C header: python converters/to_esp32.py models/jarvis_medium_20250113_143000.tflite
   2. Copy header to ESP32 firmware
   3. Expected inference time: ~15-25ms on ESP32-S3 (INT8 optimized)
   4. Expected memory usage: ~80KB PSRAM tensor arena
   5. Device sanity checks will validate INT8 tensor types and quantization parameters
```

## Step 3: Validate the Model

```bash
irene-validate-model models/jarvis_medium_20250131_143022.tflite
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

Note: INT8 models may require threshold re-tuning for optimal performance.
The ESP32 firmware includes automatic sanity checks to validate quantization.
```

## Step 4: Convert for Target Platforms

### Convert for ESP32 Firmware

```bash
# Convert for kitchen node
irene-convert-to-esp32 \
  models/jarvis_medium_20250131_143022.tflite \
  --node_name kitchen \
  --output_dir outputs/esp32/
```

### Convert for Python VoiceTrigger (Optional)

```bash
# Convert to ONNX for OpenWakeWord provider
irene-convert-to-onnx \
  models/jarvis_medium_20250131_143022.tflite \
  --output_dir outputs/onnx/

# Optimize TFLite for Python microWakeWord provider
irene-convert-to-tflite \
  models/jarvis_medium_20250131_143022.tflite \
  --optimize --quantize \
  --output_dir outputs/python/
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

2. **Follow the integration guide** (includes INT8 quantization examples):
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

### INT8 Quantization Issues
- **Low confidence scores**: INT8 models may have different output distributions - adjust threshold
- **Sanity check failures**: Check ESP32 device logs for tensor type and quantization parameter validation
- **Memory usage higher than expected**: Verify 80KB tensor arena allocation in ESP32 firmware

## File Structure After Training

```
wake_word_training/
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
- ✅ **Latency**: ~15-25ms on ESP32-S3 (target: ≤140ms, INT8 optimized)
- ✅ **Memory Usage**: 80KB PSRAM tensor arena (INT8 optimized)

Your custom wake word model is now ready for production deployment on ESP32-S3 nodes! 