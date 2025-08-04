# Voice Trigger Documentation

## Overview

The voice trigger system provides wake word detection capabilities using multiple provider backends. It supports both OpenWakeWord and microWakeWord providers for flexible deployment scenarios.

## Providers

### OpenWakeWord Provider

Uses the OpenWakeWord library for general-purpose wake word detection with pre-trained models.

**Features:**
- Pre-trained models for common wake words
- ONNX and TensorFlow Lite support
- Automatic model downloading
- Multiple wake words support

**Configuration:**
```yaml
voice_trigger:
  enabled: true
  default_provider: "openwakeword"
  providers:
    openwakeword:
      enabled: true
      inference_framework: "tflite"
      chunk_size: 1280
      wake_words: ["irene", "jarvis"]
      threshold: 0.8
```

### microWakeWord Provider (NEW)

Uses the microWakeWord framework for custom wake word detection optimized for microcontrollers.

**Features:**
- Custom trained models using TensorFlow Lite
- Optimized for low-power devices
- Streaming inference with 40 MFCC features
- 16kHz audio processing
- Consecutive detection logic for robustness
- **Lightweight runtime**: Uses `tflite-runtime` (~50MB) instead of full TensorFlow (~800MB)

**Based on:** [microWakeWord](https://github.com/kahrendt/microWakeWord)

**Runtime Dependencies:**
- `tflite-runtime>=2.12.0` (preferred, lightweight ~50MB)
- `numpy>=1.21.0`
- Fallback to `tensorflow>=2.12.0` if tflite-runtime unavailable

**Configuration:**
```yaml
voice_trigger:
  enabled: true
  default_provider: "microwakeword"
  providers:
    microwakeword:
      enabled: true
      model_path: "/path/to/your/model.tflite"
      wake_words: ["irene"]
      threshold: 0.8
      feature_buffer_size: 49  # 49 * 10ms = 490ms
      detection_window_size: 3  # Consecutive detections needed
      num_mfcc_features: 40
      available_models:
        irene: "irene_model.tflite"
        jarvis: "jarvis_model.tflite"
        hey_irene: "hey_irene_model.tflite"
```

## Model Training for microWakeWord

To use microWakeWord effectively, you need trained models. See the [microWakeWord repository](https://github.com/kahrendt/microWakeWord) for training instructions.

### Training Process Overview:

1. **Sample Generation**: Use Piper or record audio samples
2. **Feature Extraction**: Generate MFCC spectrograms using micro_speech preprocessor
3. **Model Training**: Train streaming models with TensorFlow
4. **Quantization**: Convert to TensorFlow Lite for optimization
5. **Validation**: Test false accept/reject rates

### Model Requirements:

- **Input**: `[1, 49, 40]` (batch_size, time_steps, features)
- **Output**: `[1, 1]` (probability score)
- **Format**: TensorFlow Lite (.tflite)
- **Sample Rate**: 16kHz
- **Features**: 40 MFCC features every 10ms

## Usage Examples

### Basic Configuration

```python
# Enable voice trigger with OpenWakeWord
config = {
    "voice_trigger": {
        "enabled": True,
        "default_provider": "openwakeword",
        "wake_words": ["irene", "jarvis"],
        "threshold": 0.8,
        "providers": {
            "openwakeword": {
                "enabled": True,
                "inference_framework": "tflite"
            }
        }
    }
}
```

### Custom microWakeWord Setup

```python
# Enable voice trigger with custom microWakeWord model
config = {
    "voice_trigger": {
        "enabled": True,
        "default_provider": "microwakeword",
        "wake_words": ["irene"],
        "threshold": 0.85,
        "providers": {
            "microwakeword": {
                "enabled": True,
                "model_path": "/models/custom_irene.tflite",
                "feature_buffer_size": 49,
                "detection_window_size": 3
            }
        }
    }
}
```

### Runtime Provider Switching

```python
# Switch between providers at runtime
await voice_trigger_component.default_provider = "microwakeword"

# Or via Web API
POST /voice_trigger/switch_provider?provider_name=microwakeword
```

## Performance Considerations

### OpenWakeWord
- **Memory**: ~50MB for model loading
- **CPU**: Moderate (depends on model complexity)
- **Accuracy**: Good for general wake words
- **Latency**: ~30-50ms per inference

### microWakeWord
- **Memory**: ~1-5MB (optimized for microcontrollers)
- **CPU**: Low (quantized TensorFlow Lite)
- **Accuracy**: Excellent for custom trained words
- **Latency**: ~10-20ms per inference
- **Power**: Optimized for battery-powered devices

## API Endpoints

### GET /voice_trigger/status
Get current voice trigger status and configuration.

### POST /voice_trigger/configure
Update wake words and threshold.

### GET /voice_trigger/providers
List available providers and their capabilities.

### POST /voice_trigger/switch_provider
Switch the active provider.

## Dependencies

### OpenWakeWord Provider
```bash
pip install openwakeword numpy
```

### microWakeWord Provider
```bash
pip install tensorflow numpy
# Note: Use tensorflow-lite-runtime for production deployments
```

## Troubleshooting

### Common Issues

1. **Model Not Found**: Ensure the model path is correct and the file exists
2. **TensorFlow Errors**: Check TensorFlow installation and model compatibility
3. **Audio Format**: Ensure audio is 16kHz, mono, 16-bit PCM
4. **Low Detection Rate**: Adjust threshold or retrain model with more samples
5. **False Positives**: Increase threshold or add more negative training samples

### Debug Configuration

```yaml
logging:
  loggers:
    irene.components.voice_trigger_component:
      level: DEBUG
    irene.providers.voice_trigger:
      level: DEBUG
```

This will provide detailed logging for voice trigger operations and help diagnose issues. 