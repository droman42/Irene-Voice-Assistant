#!/usr/bin/env python3
"""
Wake Word Data Collection Script

Records positive and negative audio samples for wake word model training.
Based on ESP32 firmware specification requirements.

Usage:
    python record_samples.py --wake_word jarvis --speaker_name john
    python record_samples.py --record_negatives --duration 7200  # 2 hours
"""

import argparse
import os
import sys
import time
import wave
import numpy as np
from pathlib import Path
import sounddevice as sd
import soundfile as sf

# Audio configuration matching ESP32 spec
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.int16
BITS_PER_SAMPLE = 16

class WakeWordRecorder:
    def __init__(self, wake_word, speaker_name=None, output_dir="data"):
        self.wake_word = wake_word.lower()
        self.speaker_name = speaker_name
        self.output_dir = Path(output_dir)
        self.setup_directories()
        
    def setup_directories(self):
        """Create directory structure for training data"""
        self.positive_dir = self.output_dir / "positive"
        self.negative_dir = self.output_dir / "negative"
        self.validation_dir = self.output_dir / "validation"
        
        for dir_path in [self.positive_dir, self.negative_dir, self.validation_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            
        if self.speaker_name:
            self.speaker_dir = self.positive_dir / self.speaker_name
            self.speaker_dir.mkdir(exist_ok=True)
    
    def record_positive_samples(self, num_samples=50):
        """
        Record positive wake word samples following the specification guidelines:
        - Say wake word 5 times normal voice
        - Say wake word 5 times softly  
        - Turn away and say it 2 times
        - Repeat pattern until target reached
        """
        print(f"\n=== Recording {num_samples} positive samples for '{self.wake_word}' ===")
        print(f"Speaker: {self.speaker_name}")
        print(f"Target: 16kHz, 16-bit mono WAV files")
        print("\nRecording instructions will guide you through different scenarios:")
        print("- Normal voice (5x)")
        print("- Soft voice (5x)")
        print("- Turned away (2x)")
        print("- Different distances and angles")
        
        if not self.speaker_name:
            print("Error: Speaker name required for positive samples")
            return
            
        recorded = 0
        pattern_cycle = 0
        
        while recorded < num_samples:
            pattern_cycle += 1
            print(f"\n--- Pattern Cycle {pattern_cycle} ---")
            
            # Normal voice (5 times)
            for i in range(5):
                if recorded >= num_samples:
                    break
                self._record_single_sample(
                    f"Say '{self.wake_word}' in NORMAL voice (clear, facing microphone)",
                    f"{self.wake_word}_{recorded+1:03d}_normal.wav"
                )
                recorded += 1
            
            # Soft voice (5 times)
            for i in range(5):
                if recorded >= num_samples:
                    break
                self._record_single_sample(
                    f"Say '{self.wake_word}' in SOFT voice (quiet, but clear)",
                    f"{self.wake_word}_{recorded+1:03d}_soft.wav"
                )
                recorded += 1
                
            # Turned away (2 times)
            for i in range(2):
                if recorded >= num_samples:
                    break
                self._record_single_sample(
                    f"Turn AWAY from microphone and say '{self.wake_word}'",
                    f"{self.wake_word}_{recorded+1:03d}_away.wav"
                )
                recorded += 1
                
        print(f"\n✅ Completed recording {recorded} positive samples!")
        
    def _record_single_sample(self, instruction, filename):
        """Record a single wake word sample"""
        output_path = self.speaker_dir / filename
        
        print(f"\n📹 Recording: {filename}")
        print(f"📋 {instruction}")
        input("Press Enter when ready, then say the wake word...")
        
        # Record for 2 seconds to capture the wake word plus context
        duration = 2.0
        print("🔴 Recording... (2 seconds)")
        
        try:
            audio_data = sd.rec(
                int(duration * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE
            )
            sd.wait()  # Wait for recording to complete
            
            # Save as WAV file
            sf.write(output_path, audio_data, SAMPLE_RATE, subtype='PCM_16')
            print(f"✅ Saved: {output_path}")
            
        except Exception as e:
            print(f"❌ Recording failed: {e}")
            
    def record_negative_samples(self, duration_seconds):
        """
        Record negative samples (background noise and conversational speech)
        Target: 2 hours idle room noise + 2 hours conversational speech
        """
        print(f"\n=== Recording {duration_seconds/3600:.1f} hours of negative samples ===")
        print("This will record background audio without the wake word")
        print("Suggested content:")
        print("- Room ambient noise (AC, fans, etc.)")
        print("- Normal conversation (avoid saying the wake word!)")
        print("- TV/radio in background")
        print("- Keyboard typing, paper rustling")
        
        timestamp = int(time.time())
        filename = f"negative_{timestamp}_{duration_seconds}s.wav"
        output_path = self.negative_dir / filename
        
        input(f"Press Enter to start recording {duration_seconds} seconds...")
        print(f"🔴 Recording negative samples... ({duration_seconds} seconds)")
        print("💡 Tip: Engage in normal activities, just avoid saying the wake word")
        
        try:
            audio_data = sd.rec(
                int(duration_seconds * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE
            )
            
            # Show progress every 30 seconds
            for i in range(0, duration_seconds, 30):
                sd.sleep(min(30, duration_seconds - i) * 1000)
                remaining = duration_seconds - i - 30
                if remaining > 0:
                    print(f"⏱️  Still recording... {remaining} seconds remaining")
            
            sd.wait()  # Wait for recording to complete
            
            # Save as WAV file
            sf.write(output_path, audio_data, SAMPLE_RATE, subtype='PCM_16')
            print(f"✅ Saved negative samples: {output_path}")
            
        except Exception as e:
            print(f"❌ Recording failed: {e}")
    
    def show_data_summary(self):
        """Display current training data statistics"""
        print("\n=== Training Data Summary ===")
        
        # Count positive samples
        positive_count = 0
        speakers = []
        if self.positive_dir.exists():
            for speaker_dir in self.positive_dir.iterdir():
                if speaker_dir.is_dir():
                    speakers.append(speaker_dir.name)
                    speaker_files = list(speaker_dir.glob("*.wav"))
                    positive_count += len(speaker_files)
                    print(f"📁 {speaker_dir.name}: {len(speaker_files)} samples")
        
        # Count negative samples
        negative_duration = 0
        negative_files = list(self.negative_dir.glob("*.wav"))
        for neg_file in negative_files:
            try:
                with sf.SoundFile(neg_file) as f:
                    duration = len(f) / f.samplerate
                    negative_duration += duration
            except:
                pass
        
        print(f"\n📊 Totals:")
        print(f"   Positive samples: {positive_count} (target: ≥200)")
        print(f"   Speakers: {len(speakers)} (target: ≥4)")
        print(f"   Negative duration: {negative_duration/3600:.1f}h (target: ≥4h)")
        
        print(f"\n🎯 Training readiness:")
        readiness_positive = "✅" if positive_count >= 200 else "⏳"
        readiness_speakers = "✅" if len(speakers) >= 4 else "⏳" 
        readiness_negative = "✅" if negative_duration >= 14400 else "⏳"  # 4 hours
        
        print(f"   {readiness_positive} Positive samples: {positive_count >= 200}")
        print(f"   {readiness_speakers} Multiple speakers: {len(speakers) >= 4}")
        print(f"   {readiness_negative} Negative duration: {negative_duration >= 14400}")

def main():
    parser = argparse.ArgumentParser(description="Record wake word training data")
    parser.add_argument("--wake_word", required=True, help="Wake word to train (e.g. 'jarvis')")
    parser.add_argument("--speaker_name", help="Speaker name for positive samples")
    parser.add_argument("--num_samples", type=int, default=50, help="Number of positive samples to record")
    parser.add_argument("--record_negatives", action="store_true", help="Record negative samples instead")
    parser.add_argument("--duration", type=int, default=1800, help="Duration in seconds for negative recording (default: 30min)")
    parser.add_argument("--output_dir", default="data", help="Output directory for training data")
    parser.add_argument("--summary", action="store_true", help="Show training data summary")
    
    args = parser.parse_args()
    
    recorder = WakeWordRecorder(args.wake_word, args.speaker_name, args.output_dir)
    
    if args.summary:
        recorder.show_data_summary()
    elif args.record_negatives:
        recorder.record_negative_samples(args.duration)
    else:
        if not args.speaker_name:
            print("Error: --speaker_name required for recording positive samples")
            sys.exit(1)
        recorder.record_positive_samples(args.num_samples)
    
    # Always show summary at the end
    recorder.show_data_summary()

if __name__ == "__main__":
    main() 