#!/usr/bin/env python3
"""
Wake Word Model Training Script

Trains a microWakeWord "medium-12-bn" model using the collected audio data.
Python port of train_model.sh with improved error handling and logging.

Usage:
    python train_model.py jarvis
    python train_model.py jarvis --epochs 60 --batch_size 32
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
import logging
import yaml

# Default parameters from firmware spec
DEFAULT_EPOCHS = 55
DEFAULT_BATCH_SIZE = 16
DEFAULT_MODEL_SIZE = "medium"
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_LEARNING_RATE = 0.001

class WakeWordTrainer:
    """Wake word model trainer using microWakeWord toolkit"""
    
    def __init__(self, wake_word: str, **kwargs):
        self.wake_word = wake_word.lower()
        self.epochs = kwargs.get('epochs', DEFAULT_EPOCHS)
        self.batch_size = kwargs.get('batch_size', DEFAULT_BATCH_SIZE)
        self.model_size = kwargs.get('model_size', DEFAULT_MODEL_SIZE)
        self.sample_rate = kwargs.get('sample_rate', DEFAULT_SAMPLE_RATE)
        self.learning_rate = kwargs.get('learning_rate', DEFAULT_LEARNING_RATE)
        self.use_batch_norm = kwargs.get('use_batch_norm', True)
        
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
    
    def check_data(self) -> bool:
        """Check if training data is available and sufficient"""
        print("🔍 Checking training data...")
        
        positive_dir = self.data_dir / "positive"
        negative_dir = self.data_dir / "negative"
        
        if not positive_dir.exists():
            print(f"❌ Error: Positive samples directory not found: {positive_dir}")
            return False
        
        if not negative_dir.exists():
            print(f"❌ Error: Negative samples directory not found: {negative_dir}")
            return False
        
        # Count positive samples
        positive_files = list(positive_dir.rglob("*.wav"))
        print(f"📄 Found {len(positive_files)} positive samples")
        
        if len(positive_files) < 200:
            print(f"⚠️  Warning: Only {len(positive_files)} positive samples found.")
            print("   Recommendation: ≥200 samples for best results")
        
        # Count negative samples
        negative_files = list(negative_dir.rglob("*.wav"))
        print(f"📄 Found {len(negative_files)} negative samples")
        
        if len(negative_files) < 100:
            print(f"⚠️  Warning: Only {len(negative_files)} negative samples found.")
            print("   Recommendation: ≥4 hours of negative samples")
        
        return True
    
    def check_dependencies(self) -> bool:
        """Check if required training tools are available"""
        print("🔧 Checking dependencies...")
        
        try:
            # Check for microwakeword-train command
            result = subprocess.run(['microwakeword-train', '--help'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, 'microwakeword-train')
            print("✅ microwakeword-train available")
            return True
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Error: microwakeword-train command not found")
            print("Please install microWakeWord training tools:")
            print("   uv add git+https://github.com/kahrendt/microWakeWord.git")
            print("   # or pip install git+https://github.com/kahrendt/microWakeWord.git")
            return False
    
    def prepare_training_config(self) -> Path:
        """Generate training configuration file"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        config_file = self.configs_dir / f"{self.wake_word}_{self.model_size}_{timestamp}.yaml"
        
        config = {
            'wake_word': self.wake_word,
            'model_size': self.model_size,
            'sample_rate': self.sample_rate,
            'epochs': self.epochs,
            'batch_size': self.batch_size,
            'learning_rate': self.learning_rate,
            'use_batch_norm': self.use_batch_norm,
            'data_dir': str(self.data_dir),
            'models_dir': str(self.models_dir),
            'timestamp': timestamp
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        print(f"📝 Training config saved: {config_file}")
        return config_file
    
    def train_model(self) -> Optional[Path]:
        """Execute model training using microWakeWord"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        model_output = self.models_dir / f"{self.wake_word}_{self.model_size}_{timestamp}.tflite"
        log_file = self.models_dir / f"{self.wake_word}_{self.model_size}_{timestamp}.log"
        
        print("🎯 Starting model training...")
        print(f"Wake word: {self.wake_word}")
        print(f"Model size: {self.model_size}")
        print(f"Epochs: {self.epochs}")
        print(f"Batch size: {self.batch_size}")
        print(f"Learning rate: {self.learning_rate}")
        print(f"Batch normalization: {self.use_batch_norm}")
        print("")
        
        # Build microwakeword-train command
        cmd = [
            'microwakeword-train',
            '--wake_word', self.wake_word,
            '--model_size', self.model_size,
            '--epochs', str(self.epochs),
            '--batch_size', str(self.batch_size),
            '--learning_rate', str(self.learning_rate),
            '--data_dir', str(self.data_dir),
            '--output_path', str(model_output)
        ]
        
        if not self.use_batch_norm:
            cmd.append('--no_batch_norm')
        
        print(f"🚀 Running: {' '.join(cmd)}")
        print("")
        
        try:
            # Run training with real-time output
            with open(log_file, 'w') as f:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                if process.stdout:
                    for line in process.stdout:
                        print(line.rstrip())
                        f.write(line)
                
                process.wait()
                
            if process.returncode == 0:
                print(f"✅ Training completed successfully!")
                print(f"📦 Model saved: {model_output}")
                print(f"📝 Log saved: {log_file}")
                return model_output
            else:
                print(f"❌ Training failed with exit code {process.returncode}")
                print(f"📝 Check log file: {log_file}")
                return None
                
        except Exception as e:
            print(f"❌ Training failed: {e}")
            return None
    
    def run_training_pipeline(self) -> bool:
        """Execute the complete training pipeline"""
        print("🎯 Wake Word Training - microWakeWord medium-12-bn")
        print("=" * 50)
        print("")
        
        # Validation steps
        if not self.check_dependencies():
            return False
        
        if not self.check_data():
            return False
        
        # Prepare training
        config_file = self.prepare_training_config()
        
        # Execute training
        model_path = self.train_model()
        
        if model_path:
            print("")
            print("🏁 Training pipeline completed successfully!")
            print(f"📦 Next steps:")
            print(f"   1. Validate model: irene-validate-model {model_path}")
            print(f"   2. Convert for ESP32: irene-convert-to-esp32 {model_path}")
            print(f"   3. Convert for Python: irene-convert-to-onnx {model_path}")
            return True
        else:
            print("")
            print("❌ Training pipeline failed!")
            return False

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Train wake word model using microWakeWord")
    parser.add_argument("wake_word", help="Wake word to train (e.g., 'jarvis')")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS,
                       help=f"Number of training epochs (default: {DEFAULT_EPOCHS})")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE,
                       help=f"Batch size for training (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--learning_rate", type=float, default=DEFAULT_LEARNING_RATE,
                       help=f"Learning rate (default: {DEFAULT_LEARNING_RATE})")
    parser.add_argument("--no_batch_norm", action="store_true",
                       help="Disable batch normalization")
    parser.add_argument("--model_size", default=DEFAULT_MODEL_SIZE,
                       choices=["small", "medium", "large"],
                       help=f"Model size (default: {DEFAULT_MODEL_SIZE})")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    # Validate inputs
    if args.epochs < 1:
        print(f"❌ Error: Invalid epochs value: {args.epochs}")
        return 1
    
    if args.batch_size < 1:
        print(f"❌ Error: Invalid batch size value: {args.batch_size}")
        return 1
    
    # Initialize trainer
    trainer = WakeWordTrainer(
        wake_word=args.wake_word,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        use_batch_norm=not args.no_batch_norm,
        model_size=args.model_size
    )
    
    # Run training pipeline
    success = trainer.run_training_pipeline()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main()) 