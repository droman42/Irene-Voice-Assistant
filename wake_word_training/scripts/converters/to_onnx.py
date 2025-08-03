#!/usr/bin/env python3
"""
Wake Word Model ONNX Conversion Utility

Converts trained TensorFlow Lite models to ONNX format for OpenWakeWord compatibility.
ONNX provides better cross-platform support and integration with Python providers.

Usage:
    python to_onnx.py model.tflite
    python to_onnx.py model.tflite --output_dir outputs/onnx/
"""

import argparse
import os
from pathlib import Path
import logging
from typing import Optional

def convert_to_onnx(model_path: str, output_dir: str = "outputs/onnx") -> str:
    """
    Convert TensorFlow Lite model to ONNX format
    
    Args:
        model_path: Path to .tflite model file
        output_dir: Output directory for ONNX file
    
    Returns:
        Path to generated ONNX file
    """
    model_path_obj = Path(model_path)
    output_dir_obj = Path(output_dir)
    output_dir_obj.mkdir(parents=True, exist_ok=True)
    
    if not model_path_obj.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    # Generate output filename
    onnx_name = f"{model_path_obj.stem}.onnx"
    output_path = output_dir_obj / onnx_name
    
    try:
        # Import conversion libraries
        import tensorflow as tf
        import tf2onnx
        
        # Load TensorFlow Lite model
        interpreter = tf.lite.Interpreter(model_path=str(model_path_obj))
        interpreter.allocate_tensors()
        
        # Get input and output details
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        print(f"📦 Converting {model_path_obj.name} to ONNX format...")
        print(f"📄 Input shape: {input_details[0]['shape']}")
        print(f"📄 Output shape: {output_details[0]['shape']}")
        
        # Note: Direct TFLite -> ONNX conversion is complex
        # This is a placeholder for the conversion logic
        # Real implementation would need TensorFlow model reconstruction
        
        print(f"⚠️  ONNX conversion requires TensorFlow model (not just TFLite)")
        print(f"💡 Consider training with ONNX export or converting via TensorFlow")
        print(f"📝 Would save to: {output_path}")
        
        # For now, create a placeholder file with conversion instructions
        with open(output_path.with_suffix('.txt'), 'w') as f:
            f.write(f"""ONNX Conversion Instructions for {model_path_obj.name}

To convert this TensorFlow Lite model to ONNX format:

1. Retrain the model with ONNX export enabled:
   ```python
   # During training, export to both TFLite and ONNX
   model.export(export_path + ".onnx", format="onnx")
   ```

2. Or use tf2onnx with the original TensorFlow model:
   ```bash
   python -m tf2onnx.convert --saved-model path/to/saved_model --output {onnx_name}
   ```

3. For microWakeWord models specifically:
   - Train with microWakeWord toolkit
   - Export as both .tflite (for ESP32) and .onnx (for Python)

Model Info:
- Source: {model_path_obj.name}
- Target: {onnx_name}
- Input shape: {input_details[0]['shape'] if 'input_details' in locals() else 'Unknown'}
- Output shape: {output_details[0]['shape'] if 'output_details' in locals() else 'Unknown'}
""")
        
        return str(output_path.with_suffix('.txt'))
        
    except ImportError as e:
        logging.error(f"Missing dependencies for ONNX conversion: {e}")
        print("❌ Missing dependencies. Install with:")
        print("   uv add tensorflow tf2onnx onnx")
        raise
    except Exception as e:
        logging.error(f"ONNX conversion failed: {e}")
        raise

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Convert wake word model to ONNX format")
    parser.add_argument("model_path", help="Path to TensorFlow Lite model file")
    parser.add_argument("--output_dir", default="outputs/onnx", 
                       help="Output directory for ONNX file (default: outputs/onnx)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    try:
        output_path = convert_to_onnx(args.model_path, args.output_dir)
        print(f"✅ ONNX conversion info saved to: {output_path}")
        
    except Exception as e:
        print(f"❌ ONNX conversion failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 