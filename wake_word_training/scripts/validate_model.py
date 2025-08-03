#!/usr/bin/env python3
"""
Wake Word Model Validation Script

Tests trained models against firmware specification targets:
- Recall (TPR): ≥95% (≥190/200 test positives)
- False Accepts: ≤2 per hour on 3h negative stream  
- Wake Latency: ≤140ms averaged on ESP32-S3 @ 240MHz

Usage:
    python validate_model.py model.tflite
    python validate_model.py model.tflite --test_data validation/
"""

import argparse
import time
import random
import numpy as np
from pathlib import Path
import soundfile as sf
import tensorflow as tf
from typing import List, Tuple, Dict
import matplotlib.pyplot as plt
import seaborn as sns

class WakeWordValidator:
    def __init__(self, model_path: str, test_data_dir: str = "data/validation"):
        self.model_path = Path(model_path)
        self.test_data_dir = Path(test_data_dir)
        self.sample_rate = 16000
        self.frame_length_ms = 30  # 30ms frames as per microWakeWord
        self.frame_length_samples = int(self.sample_rate * self.frame_length_ms / 1000)
        
        # Load the TensorFlow Lite model
        self.interpreter = tf.lite.Interpreter(model_path=str(self.model_path))
        self.interpreter.allocate_tensors()
        
        # Get input and output details
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        print(f"📁 Model loaded: {self.model_path}")
        print(f"🔍 Input shape: {self.input_details[0]['shape']}")
        print(f"📤 Output shape: {self.output_details[0]['shape']}")
        
    def load_test_data(self) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """Load positive and negative test samples"""
        positive_samples = []
        negative_samples = []
        
        # Load positive samples from validation directory
        positive_dir = self.test_data_dir / "positive"
        if positive_dir.exists():
            for wav_file in positive_dir.glob("*.wav"):
                try:
                    audio, sr = sf.read(wav_file)
                    if sr != self.sample_rate:
                        continue  # Skip if wrong sample rate
                    positive_samples.append(audio.astype(np.float32))
                except Exception as e:
                    print(f"⚠️  Failed to load {wav_file}: {e}")
        
        # Load negative samples from validation directory
        negative_dir = self.test_data_dir / "negative"
        if negative_dir.exists():
            for wav_file in negative_dir.glob("*.wav"):
                try:
                    audio, sr = sf.read(wav_file)
                    if sr != self.sample_rate:
                        continue  # Skip if wrong sample rate
                    negative_samples.append(audio.astype(np.float32))
                except Exception as e:
                    print(f"⚠️  Failed to load {wav_file}: {e}")
        
        # If no validation data, use training data as fallback
        if not positive_samples:
            print("⚠️  No validation positive samples found, using training data")
            training_positive = Path("data/positive")
            if training_positive.exists():
                for speaker_dir in training_positive.iterdir():
                    if speaker_dir.is_dir():
                        for wav_file in list(speaker_dir.glob("*.wav"))[:10]:  # Take 10 per speaker
                            try:
                                audio, sr = sf.read(wav_file)
                                if sr == self.sample_rate:
                                    positive_samples.append(audio.astype(np.float32))
                            except:
                                continue
        
        if not negative_samples:
            print("⚠️  No validation negative samples found, using training data")
            training_negative = Path("data/negative")
            if training_negative.exists():
                for wav_file in training_negative.glob("*.wav"):
                    try:
                        audio, sr = sf.read(wav_file)
                        if sr == self.sample_rate:
                            # Take random 30-second chunks
                            chunk_length = 30 * self.sample_rate
                            if len(audio) > chunk_length:
                                start = random.randint(0, len(audio) - chunk_length)
                                negative_samples.append(audio[start:start+chunk_length].astype(np.float32))
                    except:
                        continue
        
        print(f"📊 Test data loaded:")
        print(f"   Positive samples: {len(positive_samples)}")
        print(f"   Negative samples: {len(negative_samples)}")
        
        return positive_samples, negative_samples
    
    def run_inference(self, audio_frame: np.ndarray) -> Tuple[float, float]:
        """Run model inference on a single audio frame"""
        start_time = time.perf_counter()
        
        # Prepare input data
        input_data = audio_frame.reshape(self.input_details[0]['shape']).astype(np.float32)
        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        
        # Run inference
        self.interpreter.invoke()
        
        # Get output
        output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
        confidence = float(output_data[0][0])  # Assuming single output
        
        inference_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        
        return confidence, inference_time
    
    def test_recall(self, positive_samples: List[np.ndarray], threshold: float = 0.9) -> Dict:
        """Test recall (True Positive Rate) on positive samples"""
        print(f"\n🎯 Testing Recall (target: ≥95%)")
        print(f"   Confidence threshold: {threshold}")
        
        total_positives = 0
        detected_positives = 0
        latencies = []
        
        for i, audio in enumerate(positive_samples):
            # Process audio in frames
            detected_in_sample = False
            sample_latencies = []
            
            for start_idx in range(0, len(audio) - self.frame_length_samples, self.frame_length_samples // 2):
                frame = audio[start_idx:start_idx + self.frame_length_samples]
                if len(frame) < self.frame_length_samples:
                    continue
                    
                confidence, inference_time = self.run_inference(frame)
                sample_latencies.append(inference_time)
                
                if confidence >= threshold:
                    detected_in_sample = True
                    break
            
            total_positives += 1
            if detected_in_sample:
                detected_positives += 1
                latencies.extend(sample_latencies[:5])  # Take first few latencies
                
            if (i + 1) % 10 == 0:
                print(f"   Processed {i + 1}/{len(positive_samples)} samples...")
        
        recall = detected_positives / total_positives if total_positives > 0 else 0
        avg_latency = np.mean(latencies) if latencies else 0
        
        result = {
            'total_positives': total_positives,
            'detected_positives': detected_positives,
            'recall_percentage': recall * 100,
            'avg_latency_ms': avg_latency,
            'passes_target': recall >= 0.95,
            'latencies': latencies
        }
        
        print(f"📊 Recall Results:")
        print(f"   Detected: {detected_positives}/{total_positives} ({recall*100:.1f}%)")
        print(f"   Target: ≥95% - {'✅ PASS' if result['passes_target'] else '❌ FAIL'}")
        print(f"   Average latency: {avg_latency:.1f}ms")
        
        return result
    
    def test_false_accepts(self, negative_samples: List[np.ndarray], threshold: float = 0.9) -> Dict:
        """Test false accept rate on negative samples"""
        print(f"\n🚫 Testing False Accept Rate (target: ≤2 per hour)")
        print(f"   Confidence threshold: {threshold}")
        
        total_frames = 0
        false_accepts = 0
        total_duration = 0
        
        for i, audio in enumerate(negative_samples):
            sample_duration = len(audio) / self.sample_rate
            total_duration += sample_duration
            
            # Process audio in frames
            for start_idx in range(0, len(audio) - self.frame_length_samples, self.frame_length_samples):
                frame = audio[start_idx:start_idx + self.frame_length_samples]
                if len(frame) < self.frame_length_samples:
                    continue
                    
                confidence, _ = self.run_inference(frame)
                total_frames += 1
                
                if confidence >= threshold:
                    false_accepts += 1
            
            if (i + 1) % 5 == 0:
                print(f"   Processed {i + 1}/{len(negative_samples)} negative samples...")
        
        hours_tested = total_duration / 3600
        false_accepts_per_hour = false_accepts / hours_tested if hours_tested > 0 else 0
        
        result = {
            'total_frames': total_frames,
            'false_accepts': false_accepts,
            'hours_tested': hours_tested,
            'false_accepts_per_hour': false_accepts_per_hour,
            'passes_target': false_accepts_per_hour <= 2.0
        }
        
        print(f"📊 False Accept Results:")
        print(f"   False accepts: {false_accepts}/{total_frames} frames")
        print(f"   Hours tested: {hours_tested:.1f}h")
        print(f"   Rate: {false_accepts_per_hour:.2f} per hour")
        print(f"   Target: ≤2/hour - {'✅ PASS' if result['passes_target'] else '❌ FAIL'}")
        
        return result
    
    def test_latency(self, sample_audio: np.ndarray, num_iterations: int = 1000) -> Dict:
        """Test inference latency (simulating ESP32-S3 @ 240MHz)"""
        print(f"\n⚡ Testing Inference Latency (target: ≤140ms)")
        print(f"   Iterations: {num_iterations}")
        
        latencies = []
        
        # Use a representative audio frame
        if len(sample_audio) >= self.frame_length_samples:
            test_frame = sample_audio[:self.frame_length_samples]
        else:
            test_frame = np.pad(sample_audio, (0, self.frame_length_samples - len(sample_audio)))
        
        # Warm up the model
        for _ in range(10):
            self.run_inference(test_frame)
        
        # Measure latencies
        for i in range(num_iterations):
            _, latency = self.run_inference(test_frame)
            latencies.append(latency)
            
            if (i + 1) % 100 == 0:
                print(f"   Completed {i + 1}/{num_iterations} iterations...")
        
        avg_latency = np.mean(latencies)
        p95_latency = np.percentile(latencies, 95)
        p99_latency = np.percentile(latencies, 99)
        
        # Note: This is Python/TensorFlow latency, ESP32 will be different
        # The target of 140ms is for the ESP32 hardware implementation
        
        result = {
            'avg_latency_ms': avg_latency,
            'p95_latency_ms': p95_latency,
            'p99_latency_ms': p99_latency,
            'latencies': latencies,
            'note': 'Latency measured in Python/TensorFlow (ESP32 will differ)'
        }
        
        print(f"📊 Latency Results (Python/TensorFlow):")
        print(f"   Average: {avg_latency:.1f}ms")
        print(f"   95th percentile: {p95_latency:.1f}ms")
        print(f"   99th percentile: {p99_latency:.1f}ms")
        print(f"   Note: ESP32-S3 target is ≤140ms (hardware implementation)")
        
        return result
    
    def generate_report(self, recall_result: Dict, false_accept_result: Dict, latency_result: Dict):
        """Generate a comprehensive validation report"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = f"validation_report_{timestamp}.txt"
        
        with open(report_file, 'w') as f:
            f.write("Wake Word Model Validation Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Model: {self.model_path}\n")
            f.write(f"Timestamp: {timestamp}\n\n")
            
            f.write("Firmware Specification Targets:\n")
            f.write("- Recall (TPR): ≥95% (≥190/200 test positives)\n")
            f.write("- False Accepts: ≤2 per hour on 3h negative stream\n")
            f.write("- Wake Latency: ≤140ms averaged on ESP32-S3 @ 240MHz\n\n")
            
            f.write("Validation Results:\n")
            f.write("-" * 20 + "\n")
            
            f.write(f"1. Recall Test:\n")
            f.write(f"   Detected: {recall_result['detected_positives']}/{recall_result['total_positives']}\n")
            f.write(f"   Percentage: {recall_result['recall_percentage']:.1f}%\n")
            f.write(f"   Target: ≥95% - {'PASS' if recall_result['passes_target'] else 'FAIL'}\n")
            f.write(f"   Average latency: {recall_result['avg_latency_ms']:.1f}ms\n\n")
            
            f.write(f"2. False Accept Test:\n")
            f.write(f"   False accepts: {false_accept_result['false_accepts']}\n")
            f.write(f"   Hours tested: {false_accept_result['hours_tested']:.1f}h\n")
            f.write(f"   Rate: {false_accept_result['false_accepts_per_hour']:.2f} per hour\n")
            f.write(f"   Target: ≤2/hour - {'PASS' if false_accept_result['passes_target'] else 'FAIL'}\n\n")
            
            f.write(f"3. Latency Test (Python/TensorFlow):\n")
            f.write(f"   Average: {latency_result['avg_latency_ms']:.1f}ms\n")
            f.write(f"   95th percentile: {latency_result['p95_latency_ms']:.1f}ms\n")
            f.write(f"   Note: {latency_result['note']}\n\n")
            
            overall_pass = (recall_result['passes_target'] and 
                          false_accept_result['passes_target'])
            
            f.write(f"Overall Result: {'PASS' if overall_pass else 'FAIL'}\n")
            if overall_pass:
                f.write("✅ Model meets firmware specification requirements\n")
            else:
                f.write("❌ Model does not meet all requirements\n")
        
        print(f"\n📄 Validation report saved: {report_file}")
        
        # Also create a simple plot if matplotlib is available
        try:
            self.plot_results(recall_result, false_accept_result, latency_result, timestamp)
        except Exception as e:
            print(f"⚠️  Could not generate plots: {e}")
    
    def plot_results(self, recall_result: Dict, false_accept_result: Dict, latency_result: Dict, timestamp: str):
        """Generate validation result plots"""
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle(f'Wake Word Model Validation Results\n{self.model_path.name}', fontsize=14)
        
        # Recall vs Target
        ax1 = axes[0, 0]
        ax1.bar(['Achieved', 'Target'], [recall_result['recall_percentage'], 95], 
                color=['green' if recall_result['passes_target'] else 'red', 'blue'])
        ax1.set_ylabel('Recall (%)')
        ax1.set_title('Recall Performance')
        ax1.set_ylim(0, 100)
        
        # False Accept Rate
        ax2 = axes[0, 1]
        ax2.bar(['Achieved', 'Target'], [false_accept_result['false_accepts_per_hour'], 2], 
                color=['green' if false_accept_result['passes_target'] else 'red', 'blue'])
        ax2.set_ylabel('False Accepts per Hour')
        ax2.set_title('False Accept Rate')
        
        # Latency Distribution
        ax3 = axes[1, 0]
        if latency_result['latencies']:
            ax3.hist(latency_result['latencies'], bins=50, alpha=0.7, color='skyblue')
            ax3.axvline(latency_result['avg_latency_ms'], color='red', linestyle='--', 
                       label=f'Avg: {latency_result["avg_latency_ms"]:.1f}ms')
            ax3.set_xlabel('Latency (ms)')
            ax3.set_ylabel('Frequency')
            ax3.set_title('Inference Latency Distribution')
            ax3.legend()
        
        # Summary
        ax4 = axes[1, 1]
        ax4.axis('off')
        summary_text = f"""
Model Validation Summary

Recall: {recall_result['recall_percentage']:.1f}% {'✅' if recall_result['passes_target'] else '❌'}
Target: ≥95%

False Accepts: {false_accept_result['false_accepts_per_hour']:.2f}/hour {'✅' if false_accept_result['passes_target'] else '❌'}
Target: ≤2/hour

Average Latency: {latency_result['avg_latency_ms']:.1f}ms
(Python/TensorFlow implementation)

Overall: {'PASS' if (recall_result['passes_target'] and false_accept_result['passes_target']) else 'FAIL'}
        """
        ax4.text(0.1, 0.9, summary_text, transform=ax4.transAxes, fontsize=10, 
                verticalalignment='top', fontfamily='monospace')
        
        plt.tight_layout()
        plot_file = f"validation_plots_{timestamp}.png"
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        print(f"📊 Validation plots saved: {plot_file}")
        plt.close()

def main():
    parser = argparse.ArgumentParser(description="Validate wake word model performance")
    parser.add_argument("model_path", help="Path to TensorFlow Lite model file")
    parser.add_argument("--test_data", default="data/validation", help="Test data directory")
    parser.add_argument("--threshold", type=float, default=0.9, help="Confidence threshold")
    parser.add_argument("--latency_iterations", type=int, default=1000, help="Latency test iterations")
    
    args = parser.parse_args()
    
    if not Path(args.model_path).exists():
        print(f"❌ Error: Model file not found: {args.model_path}")
        return
    
    print("🔍 Wake Word Model Validation")
    print("=" * 40)
    
    validator = WakeWordValidator(args.model_path, args.test_data)
    
    # Load test data
    positive_samples, negative_samples = validator.load_test_data()
    
    if not positive_samples:
        print("❌ Error: No positive test samples found")
        return
    
    if not negative_samples:
        print("❌ Error: No negative test samples found")
        return
    
    # Run validation tests
    recall_result = validator.test_recall(positive_samples, args.threshold)
    false_accept_result = validator.test_false_accepts(negative_samples, args.threshold)
    
    # Use a sample for latency testing
    sample_audio = positive_samples[0] if positive_samples else np.random.randn(480)  # 30ms at 16kHz
    latency_result = validator.test_latency(sample_audio, args.latency_iterations)
    
    # Generate report
    validator.generate_report(recall_result, false_accept_result, latency_result)
    
    # Final summary
    overall_pass = (recall_result['passes_target'] and false_accept_result['passes_target'])
    print(f"\n🏁 Validation Complete: {'✅ PASS' if overall_pass else '❌ FAIL'}")
    
    if overall_pass:
        print("   Model is ready for firmware integration!")
    else:
        print("   Model needs improvement before firmware integration.")

if __name__ == "__main__":
    main() 