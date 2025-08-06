# Wake Word Detector INT8 Upgrade

This document summarizes the upgrade of the ESP32 wake word detector to support INT8 quantized TensorFlow Lite models with MFCC frontend.

## Key Changes

### 1. MFCC Frontend Implementation
- **New files**: `mfcc_frontend.hpp` and `mfcc_frontend.cpp`
- **Parameters**: 16 kHz, 30ms window (480 samples), 10ms hop (160 samples)
- **Features**: 40 mel filters, 40 MFCCs, 49×40 feature matrix output
- **Memory**: PSRAM allocation with optimized ring buffer for overlapping windows

### 2. INT8 Tensor Support
- **Input handling**: Automatic quantization of MFCC features to INT8
- **Output handling**: Dequantization of INT8 outputs to float confidence scores
- **Validation**: Tensor shape verification and quantization parameter logging
- **Fallback**: Float32 compatibility maintained for development

### 3. Updated Processing Pipeline
```
Audio PCM → MFCC Frontend → Float Features → INT8 Quantization → TF Lite → INT8 Output → Float Confidence
```

### 4. Memory Optimizations
- **Tensor arena**: 160KB initial size (can be reduced to 128KB-96KB after testing)
- **MFCC buffers**: Allocated in PSRAM for optimal performance
- **Resolver ops**: Removed unused Softmax operation for binary classification

### 5. Threshold Tuning Notes
- INT8 quantization may shift confidence score distribution
- Threshold values may need empirical re-validation
- Consider using trainer-suggested defaults initially

## Compatibility
- Maintains backward compatibility with float32 models
- Legacy audio buffer processing preserved
- Existing detection callback interface unchanged

## Performance Benefits
- Reduced memory footprint with INT8 quantization
- Faster inference with optimized ESP-NN kernels (when enabled)
- Better feature matching with training pipeline (MFCC vs raw PCM)

## Configuration
Update your model configuration to specify:
- `use_psram = true` for optimal memory allocation
- Appropriate threshold values for INT8 model characteristics
- Consistent trigger duration based on new confidence distributions

## Validation
After deploying INT8 models:
1. Monitor tensor arena usage in logs
2. Validate detection accuracy with test audio
3. Adjust threshold based on empirical FAR/TPR measurements
4. Gradually reduce tensor arena size if memory usage allows 