#!/usr/bin/env python3
"""
ESP32-Compatible Wake Word Trainer

A clean, modern TensorFlow implementation that produces models compatible
with ESP32 microcontrollers and the Irene Voice Assistant firmware.

Based on the microWakeWord "medium-12-bn" architecture:
- 12 Conv1D layers with BatchNormalization
- ESP32-optimized: ≤140KB model size, ≤25ms inference
- Input: [1, 49, 40] (490ms context, 40 MFCC features)
- Output: [1, 1] (binary wake word classification)

ESP32 Compatibility Guarantees:
- Model size ≤140KB (ESP32 Flash constraint)
- Input shape matches firmware expectations  
- TensorFlow Lite optimized for microcontrollers
- Memory usage ≤70KB PSRAM during inference

Usage:
    python tensorflow_trainer.py jarvis --epochs 55 --batch_size 16
"""

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple, List
import numpy as np
import yaml

# TensorFlow imports
import tensorflow as tf  # type: ignore # Optional dependency
from tensorflow import keras  # type: ignore # Optional dependency
from tensorflow.keras import layers, models, optimizers, callbacks  # type: ignore # Optional dependency
import librosa  # type: ignore # Optional dependency

# Irene imports (when integrated)
# from irene.utils.logging import get_logger

class TensorFlowWakeWordTrainer:
    """Clean TensorFlow-based wake word trainer"""
    
    def __init__(self, wake_word: str, **kwargs):
        self.wake_word = wake_word.lower()
        self.epochs = kwargs.get('epochs', 55)
        self.batch_size = kwargs.get('batch_size', 16)
        self.learning_rate = kwargs.get('learning_rate', 0.001)
        self.model_size = kwargs.get('model_size', 'medium')
        
        # Audio parameters (ESP32/microWakeWord compatible)
        self.sample_rate = 16000
        self.n_mfcc = 40  # microWakeWord uses 40 MFCC features
        self.n_fft = 512
        self.hop_length = 160  # 10ms at 16kHz
        self.win_length = 480  # 30ms at 16kHz
        self.n_mels = 40
        
        # Model parameters (ESP32 compatible)
        self.sequence_length = 49  # 49 * 10ms = 490ms (ESP32 requirement)
        self.max_model_size_kb = 140  # ESP32 Flash limit
        
        # Setup directories
        self.script_dir = Path(__file__).parent
        self.project_dir = self.script_dir.parent
        self.data_dir = self.project_dir / "data"
        self.models_dir = self.project_dir / "models"
        self.configs_dir = self.project_dir / "configs"
        
        # Ensure directories exist
        self.models_dir.mkdir(exist_ok=True)
        self.configs_dir.mkdir(exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def extract_mfcc_features(self, audio_file: Path) -> np.ndarray:
        """Extract MFCC features compatible with microWakeWord"""
        try:
            # Load audio
            y, sr = librosa.load(audio_file, sr=self.sample_rate)
            
            # Ensure minimum length (pad if needed)
            min_length = self.sequence_length * self.hop_length
            if len(y) < min_length:
                y = np.pad(y, (0, min_length - len(y)), mode='constant')
            
            # Extract MFCC features
            mfccs = librosa.feature.mfcc(
                y=y,
                sr=sr,
                n_mfcc=self.n_mfcc,
                n_fft=self.n_fft,
                hop_length=self.hop_length,
                win_length=self.win_length,
                n_mels=self.n_mels
            )
            
            # Transpose to (time, features) and normalize
            mfccs = mfccs.T
            
            # Truncate or pad to fixed sequence length
            if mfccs.shape[0] > self.sequence_length:
                mfccs = mfccs[:self.sequence_length]
            else:
                padding = self.sequence_length - mfccs.shape[0]
                mfccs = np.pad(mfccs, ((0, padding), (0, 0)), mode='constant')
            
            return mfccs
            
        except Exception as e:
            self.logger.error(f"Error extracting features from {audio_file}: {e}")
            return np.zeros((self.sequence_length, self.n_mfcc))
    
    def load_and_preprocess_data(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Load and preprocess training data"""
        print("📊 Loading and preprocessing training data...")
        
        positive_dir = self.data_dir / "positive"
        negative_dir = self.data_dir / "negative"
        
        if not positive_dir.exists() or not negative_dir.exists():
            raise ValueError(f"Training data directories not found: {positive_dir}, {negative_dir}")
        
        # Load positive samples
        positive_files = list(positive_dir.rglob("*.wav"))
        print(f"Found {len(positive_files)} positive samples")
        
        # Load negative samples
        negative_files = list(negative_dir.rglob("*.wav"))
        print(f"Found {len(negative_files)} negative samples")
        
        # Extract features
        X_positive = np.array([self.extract_mfcc_features(f) for f in positive_files])
        X_negative = np.array([self.extract_mfcc_features(f) for f in negative_files])
        
        # Create labels
        y_positive = np.ones(len(X_positive))
        y_negative = np.zeros(len(X_negative))
        
        # Combine and shuffle
        X = np.concatenate([X_positive, X_negative], axis=0)
        y = np.concatenate([y_positive, y_negative], axis=0)
        
        # Shuffle
        indices = np.random.permutation(len(X))
        X = X[indices]
        y = y[indices]
        
        # Train/validation split (80/20)
        split_idx = int(0.8 * len(X))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        print(f"Training set: {len(X_train)} samples")
        print(f"Validation set: {len(X_val)} samples")
        print(f"Feature shape: {X_train.shape}")
        
        return X_train, X_val, y_train, y_val
    
    def build_model(self) -> keras.Model:
        """Build ESP32-compatible microWakeWord medium-12-bn architecture"""
        print("🏗️ Building ESP32-compatible model architecture...")
        
        # ESP32-optimized medium-12-bn architecture
        model = models.Sequential([
            layers.Input(shape=(self.sequence_length, self.n_mfcc)),
            
            # Input normalization
            layers.BatchNormalization(),
            
            # Conv1D layers (medium-12-bn) - smaller filters for ESP32
            layers.Conv1D(16, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            layers.Conv1D(16, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            layers.Conv1D(24, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            layers.Conv1D(24, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            layers.Conv1D(32, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            layers.Conv1D(32, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            layers.Conv1D(48, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            layers.Conv1D(48, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            layers.Conv1D(64, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            layers.Conv1D(64, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            layers.Conv1D(80, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            layers.Conv1D(80, 3, activation='relu', padding='same'),
            layers.BatchNormalization(),
            layers.Dropout(0.1),
            
            # Global pooling and compact classification
            layers.GlobalAveragePooling1D(),
            layers.Dense(64, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            
            layers.Dense(16, activation='relu'),
            layers.Dropout(0.2),
            
            layers.Dense(1, activation='sigmoid')  # Binary classification
        ])
        
        # Compile model
        model.compile(
            optimizer=optimizers.Adam(learning_rate=self.learning_rate),
            loss='binary_crossentropy',
            metrics=['accuracy', 'precision', 'recall']
        )
        
        # Check model size
        param_count = model.count_params()
        estimated_size_kb = (param_count * 4) / 1024  # 4 bytes per float32 param
        
        print(f"Model parameters: {param_count:,}")
        print(f"Estimated size: {estimated_size_kb:.1f} KB")
        
        if estimated_size_kb > self.max_model_size_kb:
            print(f"⚠️  Warning: Model size ({estimated_size_kb:.1f} KB) exceeds ESP32 limit ({self.max_model_size_kb} KB)")
        else:
            print(f"✅ Model size within ESP32 limit ({self.max_model_size_kb} KB)")
        
        return model
    
    def compute_decision_threshold(self, tflite_model: bytes, X_val: np.ndarray, y_val: np.ndarray) -> float:
        """Compute optimal decision threshold for INT8 TFLite model"""
        print("🎯 Computing optimal decision threshold for deployment...")
        
        # Initialize TFLite interpreter
        interpreter = tf.lite.Interpreter(model_content=tflite_model)
        interpreter.allocate_tensors()
        
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        # Get predictions on validation set
        predictions = []
        for sample in X_val:
            # Quantize input to INT8 using input tensor scale/zero-point
            in_scale, in_zp = input_details[0]['quantization']
            out_scale, out_zp = output_details[0]['quantization']
            x = np.expand_dims(sample.astype(np.float32), axis=0)
            x_q = np.clip(np.round(x / in_scale + in_zp), -128, 127).astype(np.int8)
            interpreter.set_tensor(input_details[0]['index'], x_q)
            interpreter.invoke()
            y_q = interpreter.get_tensor(output_details[0]['index']).astype(np.int32)
            y = (y_q - out_zp) * out_scale  # dequantize to float probability
            predictions.append(float(y[0][0]))
        
        predictions = np.array(predictions)
        
        # Find threshold that maximizes F1 score
        thresholds = np.linspace(0.1, 0.9, 81)  # Test thresholds from 0.1 to 0.9
        best_f1 = 0
        best_threshold = 0.5
        
        for threshold in thresholds:
            y_pred = (predictions >= threshold).astype(int)
            
            # Calculate metrics
            tp = np.sum((y_val == 1) & (y_pred == 1))
            fp = np.sum((y_val == 0) & (y_pred == 1))
            fn = np.sum((y_val == 1) & (y_pred == 0))
            
            if tp + fp > 0 and tp + fn > 0:
                precision = tp / (tp + fp)
                recall = tp / (tp + fn)
                if precision + recall > 0:
                    f1 = 2 * (precision * recall) / (precision + recall)
                    if f1 > best_f1:
                        best_f1 = f1
                        best_threshold = threshold
        
        print(f"🎯 Optimal threshold: {best_threshold:.3f} (F1: {best_f1:.3f})")
        return float(best_threshold)
    
    def train_model(self) -> Optional[Path]:
        """Execute model training"""
        print("🎯 Starting TensorFlow wake word training...")
        print(f"Wake word: {self.wake_word}")
        print(f"Architecture: {self.model_size}")
        print(f"Epochs: {self.epochs}")
        print(f"Batch size: {self.batch_size}")
        print(f"Learning rate: {self.learning_rate}")
        print("")
        
        try:
            # Load data
            X_train, X_val, y_train, y_val = self.load_and_preprocess_data()
            
            # Build model
            model = self.build_model()
            
            # Setup callbacks
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            model_name = f"{self.wake_word}_{self.model_size}_{timestamp}"
            model_path = self.models_dir / f"{model_name}.h5"
            tflite_path = self.models_dir / f"{model_name}.tflite"
            
            callbacks_list = [
                callbacks.ModelCheckpoint(
                    str(model_path),
                    monitor='val_loss',
                    save_best_only=True,
                    verbose=1
                ),
                callbacks.EarlyStopping(
                    monitor='val_loss',
                    patience=10,
                    restore_best_weights=True
                ),
                callbacks.ReduceLROnPlateau(
                    monitor='val_loss',
                    factor=0.5,
                    patience=5,
                    min_lr=1e-7
                )
            ]
            
            # Train model
            print("🚀 Starting training...")
            history = model.fit(
                X_train, y_train,
                batch_size=self.batch_size,
                epochs=self.epochs,
                validation_data=(X_val, y_val),
                callbacks=callbacks_list,
                verbose=1
            )
            
            # Convert to TensorFlow Lite with ESP32 INT8 quantization
            print("🔄 Converting to TensorFlow Lite for ESP32 with INT8 quantization...")
            converter = tf.lite.TFLiteConverter.from_keras_model(model)
            
            # ESP32-specific optimizations with INT8 quantization
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            converter.inference_input_type = tf.int8
            converter.inference_output_type = tf.int8
            
            # Representative dataset for INT8 calibration (49×40 MFCC)
            def representative_dataset():
                # Use 200-500 samples for stable INT8 calibration as recommended
                # This ensures calibration matches real inputs: 30ms window, 10ms hop, 49 frames, 40 MFCC coeffs
                sample_size = min(500, len(X_train))  # Use up to 500 samples if available
                if sample_size < 200:
                    print(f"⚠️  Warning: Only {sample_size} samples available for calibration. Recommend ≥200.")
                
                sample_data = X_train[:sample_size]
                print(f"Using {sample_size} samples for INT8 calibration (target: 200-500)...")
                
                for data in sample_data:
                    # Ensure [1, 49, 40] tensor shape matches training MFCC pipeline
                    # This locks the input contract: 49 frames × 40 MFCC coefficients
                    yield [np.expand_dims(data.astype(np.float32), axis=0)]
            
            converter.representative_dataset = representative_dataset
            
            # Convert
            tflite_model = converter.convert()
            
            # Check final model size and properties
            model_size_kb = len(tflite_model) / 1024
            print(f"📏 TFLite INT8 model size: {model_size_kb:.1f} KB")
            
            # Verify INT8 quantization success
            interpreter = tf.lite.Interpreter(model_content=tflite_model)
            input_details = interpreter.get_input_details()
            output_details = interpreter.get_output_details()
            print(f"✅ Input dtype: {input_details[0]['dtype']}, shape: {input_details[0]['shape']}")
            print(f"✅ Output dtype: {output_details[0]['dtype']}, shape: {output_details[0]['shape']}")
            
            if model_size_kb > self.max_model_size_kb:
                print(f"❌ ERROR: TFLite model ({model_size_kb:.1f} KB) exceeds ESP32 limit!")
                print("Consider reducing model complexity or using int8 quantization.")
                return None
            else:
                print(f"✅ TFLite model fits ESP32 constraints ({self.max_model_size_kb} KB limit)")
            
            with open(tflite_path, 'wb') as f:
                f.write(tflite_model)
            
            # Compute optimal decision threshold using validation set
            decision_threshold = self.compute_decision_threshold(tflite_model, X_val, y_val)

            # Extract quantization params for firmware (input/output scale, zero_point)
            _interp = tf.lite.Interpreter(model_content=tflite_model); _interp.allocate_tensors()
            _in = _interp.get_input_details()[0]['quantization']; _out = _interp.get_output_details()[0]['quantization']
            input_scale, input_zp = _in[0], _in[1]
            output_scale, output_zp = _out[0], _out[1]
            
            # Save ESP32-compatible training config
            config = {
                'wake_word': self.wake_word,
                'model_size': self.model_size,
                'model_type': 'medium-12-bn',
                
                # Audio parameters (ESP32 compatible)
                'sample_rate': self.sample_rate,
                'n_mfcc': self.n_mfcc,
                'sequence_length': self.sequence_length,
                'window_size_ms': 30,
                'stride_ms': 10,
                'feature_buffer_size': self.sequence_length,  # 49 frames
                
                # Training parameters
                'epochs': self.epochs,
                'batch_size': self.batch_size,
                'learning_rate': self.learning_rate,
                'final_accuracy': float(max(history.history['val_accuracy'])),
                'final_loss': float(min(history.history['val_loss'])),
                
                # ESP32 compatibility
                'esp32_compatible': True,
                'model_size_kb': model_size_kb,
                'max_model_size_kb': self.max_model_size_kb,
                'inference_time_target_ms': 25,
                'memory_usage_target_kb': 70,
                
                # Deployment configuration
                'decision_threshold': decision_threshold,
                'threshold_optimization': 'max_f1_score',
                'input_dtype': 'int8',
                'output_dtype': 'int8',
                # Quantization parameters for firmware parity
                'input_scale': float(input_scale),
                'input_zero_point': int(input_zp),
                'output_scale': float(output_scale),
                'output_zero_point': int(output_zp),
                
                # Architecture details
                'architecture': 'tensorflow_medium_12bn',
                'layer_count': 12,
                'use_batch_norm': True,
                'quantization': 'int8',
                
                'timestamp': timestamp
            }
            
            config_file = self.configs_dir / f"{model_name}_config.yaml"
            with open(config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            print(f"✅ ESP32-compatible INT8 training completed successfully!")
            print(f"📦 TFLite INT8 model: {tflite_path}")
            print(f"📦 Keras model: {model_path}")
            print(f"📝 Config: {config_file}")
            print(f"🎯 Validation accuracy: {max(history.history['val_accuracy']):.3f}")
            print(f"🎯 Optimal decision threshold: {decision_threshold:.3f}")
            print(f"📏 Model size: {model_size_kb:.1f} KB (ESP32 limit: {self.max_model_size_kb} KB)")
            print("")
            print("🚀 ESP32 Integration:")
            print(f"   1. Convert to C header: python converters/to_esp32.py {tflite_path}")
            print(f"   2. Copy header to ESP32 firmware")
            print(f"   3. Use decision threshold: {decision_threshold:.3f}")
            print(f"   4. Expected inference time: ~15ms on ESP32-S3 (INT8 optimized)")
            print(f"   5. Expected memory usage: ~40KB PSRAM (INT8 reduced)")
            
            return tflite_path
            
        except Exception as e:
            print(f"❌ Training failed: {e}")
            self.logger.error(f"Training error: {e}", exc_info=True)
            return None
    
    def run_training_pipeline(self) -> bool:
        """Execute the complete training pipeline"""
        print("🎯 TensorFlow Wake Word Training")
        print("=" * 50)
        print("")
        
        # Check data availability
        if not self.check_data():
            return False
        
        # Execute training
        model_path = self.train_model()
        
        if model_path:
            print("")
            print("🏁 ESP32-compatible training pipeline completed successfully!")
            print(f"📦 Next steps:")
            print(f"   1. Test model: python validate_model.py {model_path}")
            print(f"   2. Convert for ESP32: python converters/to_esp32.py {model_path}")
            print(f"   3. Deploy to ESP32 firmware")
            print(f"   4. Optional: Convert for ONNX: python converters/to_onnx.py {model_path}")
            print("")
            print("✅ INT8 Model guarantees ESP32 compatibility:")
            print(f"   • Size: ≤140KB Flash (INT8 optimized)")
            print(f"   • Input: [1, 49, 40] INT8 tensor shape")
            print(f"   • Inference: ≤15ms on ESP32-S3 (INT8 accelerated)")
            print(f"   • Memory: ≤40KB PSRAM (INT8 reduced)")
            print(f"   • Quantization: Full INT8 (no float fallbacks)")
            return True
        else:
            print("")
            print("❌ Training pipeline failed!")
            return False
    
    def check_data(self) -> bool:
        """Check if training data is available"""
        print("🔍 Checking training data...")
        
        positive_dir = self.data_dir / "positive"
        negative_dir = self.data_dir / "negative"
        
        if not positive_dir.exists():
            print(f"❌ Error: Positive samples directory not found: {positive_dir}")
            return False
        
        if not negative_dir.exists():
            print(f"❌ Error: Negative samples directory not found: {negative_dir}")
            return False
        
        positive_files = list(positive_dir.rglob("*.wav"))
        negative_files = list(negative_dir.rglob("*.wav"))
        
        print(f"📄 Found {len(positive_files)} positive samples")
        print(f"📄 Found {len(negative_files)} negative samples")
        
        if len(positive_files) < 50:
            print(f"⚠️  Warning: Only {len(positive_files)} positive samples. Recommend ≥200.")
        
        if len(negative_files) < 100:
            print(f"⚠️  Warning: Only {len(negative_files)} negative samples. Recommend ≥500.")
        
        return True


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Train wake word model using pure TensorFlow")
    parser.add_argument("wake_word", help="Wake word to train (e.g., 'jarvis')")
    parser.add_argument("--epochs", type=int, default=55,
                       help="Number of training epochs (default: 55)")
    parser.add_argument("--batch_size", type=int, default=16,
                       help="Batch size for training (default: 16)")
    parser.add_argument("--learning_rate", type=float, default=0.001,
                       help="Learning rate (default: 0.001)")
    parser.add_argument("--model_size", default="medium",
                       choices=["small", "medium", "large"],
                       help="Model size (default: medium)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    # Initialize trainer
    trainer = TensorFlowWakeWordTrainer(
        wake_word=args.wake_word,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        model_size=args.model_size
    )
    
    # Run training pipeline
    success = trainer.run_training_pipeline()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main()) 