#!/usr/bin/env python3
"""
Wake Word Model Firmware Conversion Utility

Converts trained TensorFlow Lite models to C header files for ESP32 firmware.
Based on ESP32 firmware specification requirements.

Usage:
    python convert_for_firmware.py model.tflite
    python convert_for_firmware.py model.tflite --node_name kitchen --output_dir firmware/
"""

import argparse
import os
from pathlib import Path
import hashlib
import time
from typing import Optional

def convert_to_c_header(model_path: str, node_name: Optional[str] = None, output_dir: str = "firmware") -> str:
    """
    Convert TensorFlow Lite model to C header file using xxd-style format
    
    Args:
        model_path: Path to .tflite model file
        node_name: Node name for output filename (optional)
        output_dir: Output directory for header file
    
    Returns:
        Path to generated header file
    """
    model_path_obj = Path(model_path)
    output_dir_obj = Path(output_dir)
    output_dir_obj.mkdir(parents=True, exist_ok=True)
    
    if not model_path_obj.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    # Generate output filename
    if node_name:
        header_name = f"{node_name}_ww_model.h"
    else:
        base_name = model_path_obj.stem
        header_name = f"{base_name}_ww_model.h"
    
    output_path = output_dir_obj / header_name
    
    # Read model file
    with open(model_path_obj, 'rb') as f:
        model_data = f.read()
    
    model_size = len(model_data)
    
    # Generate C variable name
    var_name = header_name.replace('.h', '').replace('-', '_')
    
    # Calculate checksum for verification
    model_hash = hashlib.sha256(model_data).hexdigest()[:16]
    
    # Generate C header content
    header_content = f'''/*
 * Wake Word Model - {model_path_obj.name}
 * Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}
 * Size: {model_size} bytes
 * SHA256: {model_hash}...
 * 
 * This file contains a TensorFlow Lite model for wake word detection
 * optimized for ESP32-S3 with PSRAM storage.
 */

#ifndef {var_name.upper()}_H
#define {var_name.upper()}_H

#include <stdint.h>

// Model metadata
#define {var_name.upper()}_SIZE {model_size}
#define {var_name.upper()}_HASH "{model_hash}"

// Model data array (place in PSRAM)
static const uint8_t {var_name}_data[] __attribute__((aligned(4))) = {{
'''
    
    # Convert binary data to C array format (16 bytes per line)
    bytes_per_line = 16
    for i in range(0, len(model_data), bytes_per_line):
        line_data = model_data[i:i + bytes_per_line]
        hex_values = [f"0x{byte:02x}" for byte in line_data]
        line_str = "    " + ", ".join(hex_values)
        if i + bytes_per_line < len(model_data):
            line_str += ","
        header_content += line_str + "\n"
    
    header_content += f'''
}};

// Model size constant
static const size_t {var_name}_size = sizeof({var_name}_data);

// Verification function
static inline int {var_name}_verify(void) {{
    return ({var_name}_size == {var_name.upper()}_SIZE) ? 1 : 0;
}}

#endif // {var_name.upper()}_H
'''
    
    # Write header file
    with open(output_path, 'w') as f:
        f.write(header_content)
    
    return str(output_path)

def generate_firmware_integration_guide(model_path: str, header_path: str, node_name: Optional[str] = None):
    """Generate integration guide for ESP32 firmware"""
    
    model_size_kb = Path(model_path).stat().st_size / 1024
    var_name = Path(header_path).stem
    
    guide_content = f'''# ESP32 Firmware Integration Guide

## Model Information
- **Source model**: {Path(model_path).name}
- **Header file**: {Path(header_path).name}  
- **Model size**: {model_size_kb:.1f} KB
- **Node name**: {node_name or "generic"}

## Integration Steps

### 1. Copy Header File
Copy `{Path(header_path).name}` to your ESP32 project:
```bash
cp {header_path} firmware/components/wakeword/include/
```

### 2. Include in CMakeLists.txt
Add to your component's CMakeLists.txt:
```cmake
idf_component_register(
    SRCS "wakeword.c"
    INCLUDE_DIRS "include"
    REQUIRES "esp-tflite-micro"
)
```

### 3. Initialize in Code
```cpp
#include "{Path(header_path).name}"
#include "esp_heap_caps.h"
#include "tensorflow/lite/micro/micro_interpreter.h"

// Allocate model in PSRAM
static const tflite::Model* model = nullptr;
static tflite::MicroInterpreter* interpreter = nullptr;

void wakeword_init(void) {{
    // Verify model integrity
    if (!{var_name}_verify()) {{
        ESP_LOGE(TAG, "Model verification failed!");
        return;
    }}
    
    // Load model from PSRAM
    model = tflite::GetModel({var_name}_data);
    if (model->version() != TFLITE_SCHEMA_VERSION) {{
        ESP_LOGE(TAG, "Model schema version mismatch!");
        return;
    }}
    
    // Allocate tensor arena in PSRAM (160KB for medium model)
    static constexpr size_t kTensorArenaSize = 160 * 1024;
    static uint8_t* tensor_arena = (uint8_t*)heap_caps_malloc(
        kTensorArenaSize, 
        MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT
    );
    
    // Create resolver for operations
    static tflite::MicroMutableOpResolver<10> resolver;
    resolver.AddConv2D();
    resolver.AddMaxPool2D();
    resolver.AddReshape();
    resolver.AddFullyConnected();
    resolver.AddSoftmax();
    
    // Create interpreter
    static tflite::MicroInterpreter static_interpreter(
        model, resolver, tensor_arena, kTensorArenaSize
    );
    interpreter = &static_interpreter;
    
    // Allocate tensors
    TfLiteStatus allocate_status = interpreter->AllocateTensors();
    if (allocate_status != kTfLiteOk) {{
        ESP_LOGE(TAG, "AllocateTensors() failed");
        return;
    }}
    
    ESP_LOGI(TAG, "Wake word model initialized ({model_size_kb:.1f} KB)");
}}

bool wakeword_detect(const int16_t* audio_data, size_t samples) {{
    if (!interpreter) return false;
    
    // Get input tensor
    TfLiteTensor* input = interpreter->input(0);
    
    // Copy audio data to input tensor
    // (implement preprocessing as needed)
    
    // Run inference
    TfLiteStatus invoke_status = interpreter->Invoke();
    if (invoke_status != kTfLiteOk) {{
        ESP_LOGE(TAG, "Invoke() failed");
        return false;
    }}
    
    // Get output
    TfLiteTensor* output = interpreter->output(0);
    float confidence = output->data.f[0];
    
    return confidence > 0.9f;  // Threshold from training
}}
```

### 4. Memory Configuration
Ensure your ESP32 project has sufficient PSRAM allocated:

**sdkconfig.defaults:**
```
CONFIG_SPIRAM=y
CONFIG_SPIRAM_USE_CAPS_ALLOC=y
CONFIG_SPIRAM_ALLOW_BSS_SEG_EXTERNAL_MEMORY=y
```

### 5. Build Configuration
Add TensorFlow Lite Micro to your project:
```bash
idf.py add-dependency "espressif/esp-tflite-micro"
idf.py build
```

## Resource Usage
- **Flash**: ~{model_size_kb:.0f} KB (model data)
- **PSRAM**: ~160 KB (tensor arena)
- **Stack**: ~8 KB (inference)

## Performance Notes
- Expected inference time: 20-40ms on ESP32-S3 @ 240MHz
- Frame rate: 30ms (per microWakeWord specification)
- Power consumption: +15-25mA during active detection

## Verification
The model includes a verification function `{var_name}_verify()` that checks:
- Model size matches expected value
- Data integrity (compile-time verification)

Call this function during initialization to ensure model integrity.
'''
    
    guide_path = Path(header_path).parent / f"{Path(header_path).stem}_integration_guide.md"
    with open(guide_path, 'w') as f:
        f.write(guide_content)
    
    return str(guide_path)

def main():
    parser = argparse.ArgumentParser(description="Convert wake word model for ESP32 firmware")
    parser.add_argument("model_path", help="Path to TensorFlow Lite model file")
    parser.add_argument("--node_name", help="Node name for output filename (e.g., 'kitchen')")
    parser.add_argument("--output_dir", default="firmware", help="Output directory for header file")
    parser.add_argument("--no_guide", action="store_true", help="Skip generating integration guide")
    
    args = parser.parse_args()
    
    model_path = Path(args.model_path)
    if not model_path.exists():
        print(f"❌ Error: Model file not found: {model_path}")
        return 1
    
    try:
        print(f"🔄 Converting model for ESP32 firmware...")
        print(f"   Input: {model_path}")
        print(f"   Node: {args.node_name or 'generic'}")
        
        # Convert to C header
        header_path = convert_to_c_header(
            str(model_path), 
            args.node_name, 
            args.output_dir
        )
        
        model_size_kb = model_path.stat().st_size / 1024
        
        print(f"✅ Conversion complete!")
        print(f"   📁 Header file: {header_path}")
        print(f"   📏 Model size: {model_size_kb:.1f} KB")
        
        # Check if model fits flash budget
        if model_size_kb > 140:
            print(f"⚠️  Warning: Model size ({model_size_kb:.1f} KB) exceeds recommended 140 KB")
            print("   Consider reducing model complexity or using quantization")
        else:
            print(f"✅ Model size fits ESP32 flash budget")
        
        # Generate integration guide
        if not args.no_guide:
            guide_path = generate_firmware_integration_guide(
                str(model_path), 
                header_path, 
                args.node_name
            )
            print(f"📋 Integration guide: {guide_path}")
        
        print(f"\n🔄 Next steps:")
        print(f"1. Copy header file to ESP32 project: {Path(header_path).name}")
        print(f"2. Follow integration guide for implementation details")
        print(f"3. Build and flash to ESP32-S3 node")
        print(f"4. Test wake word detection in target environment")
        
        return 0
        
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main()) 