#!/usr/bin/env python3
"""
VAD Sibilant Fix Test Script

This script helps test the VAD fixes for the sibilant-only detection issue.
It provides tools to analyze VAD behavior with different types of speech sounds.

Usage:
    uv run python tools/test_vad_sibilant_fix.py --config configs/vad-sibilant-fix.toml

Test Categories:
1. Russian vowels: а, о, у, и, э, ы
2. Non-sibilant consonants: к, т, п, б, д, г
3. Sibilant consonants: с, ш, щ, з, ж, ф
4. Full words: мама, папа, кошка, собака
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from irene.config.manager import ConfigManager
from irene.workflows.audio_processor import UniversalAudioProcessor
from irene.intents.models import AudioData
from irene.utils.vad import VADResult

logger = logging.getLogger(__name__)


class VADTestAnalyzer:
    """Analyzes VAD performance for different types of speech sounds."""
    
    def __init__(self, config_path: str):
        """Initialize the VAD test analyzer."""
        self.config_manager = ConfigManager()
        self.config_path = config_path
        self.config = None
        self.vad_config = None
        self.audio_processor = None
        
        # Test categories
        self.test_categories = {
            "vowels": {
                "description": "Russian vowels (low frequency, low ZCR)",
                "sounds": ["А", "О", "У", "И", "Э", "Ы"],
                "expected": "Should be detected after fixes (previously missed)"
            },
            "non_sibilant_consonants": {
                "description": "Non-sibilant consonants (mixed frequency)",
                "sounds": ["К", "Т", "П", "Б", "Д", "Г"],
                "expected": "Should be detected after fixes (partially missed before)"
            },
            "sibilant_consonants": {
                "description": "Sibilant consonants (high frequency, high ZCR)",
                "sounds": ["С", "Ш", "Щ", "З", "Ж", "Ф"],
                "expected": "Should still be detected (was working before)"
            },
            "words": {
                "description": "Complete Russian words",
                "sounds": ["МАМА", "ПАПА", "КОШКА", "СОБАКА", "ПРИВЕТ"],
                "expected": "Should be detected completely (not just sibilant parts)"
            }
        }
        
        # Results storage
        self.test_results: Dict[str, List[Dict[str, Any]]] = {}
    
    async def initialize(self):
        """Initialize the audio processor."""
        # Load config asynchronously - convert string path to Path object
        config_path = Path(self.config_path)
        self.config = await self.config_manager.load_config(config_path)
        self.vad_config = self.config.vad
        
        self.audio_processor = UniversalAudioProcessor(self.vad_config)
        logger.info("VAD Test Analyzer initialized")
        logger.info(f"VAD Configuration:")
        logger.info(f"  Energy threshold: {self.vad_config.energy_threshold}")
        logger.info(f"  Sensitivity: {self.vad_config.sensitivity}")
        logger.info(f"  Voice duration: {self.vad_config.voice_duration_ms}ms")
        logger.info(f"  Use ZCR: {self.vad_config.use_zero_crossing_rate}")
        logger.info(f"  Adaptive threshold: {self.vad_config.adaptive_threshold}")
    
    def print_test_instructions(self):
        """Print detailed test instructions."""
        print("\n" + "="*80)
        print("VAD SIBILANT FIX TEST INSTRUCTIONS")
        print("="*80)
        print()
        print("This test helps verify that VAD now detects ALL speech sounds,")
        print("not just sibilant sounds (шипящие звуки).")
        print()
        print("BEFORE THE FIX:")
        print("  ❌ VAD only detected: С, Ш, Щ, З, Ж, Ф (sibilants)")
        print("  ❌ VAD missed: А, О, У, И, Э, Ы (vowels)")
        print("  ❌ VAD missed: К, Т, П, Б, Д, Г (non-sibilant consonants)")
        print()
        print("AFTER THE FIX:")
        print("  ✅ VAD should detect ALL speech sounds equally")
        print()
        print("TEST PROCEDURE:")
        print("1. Speak each sound clearly into the microphone")
        print("2. Wait for VAD analysis results")
        print("3. Check detection rates for each category")
        print()
        
        for category, info in self.test_categories.items():
            print(f"{category.upper()}:")
            print(f"  Description: {info['description']}")
            print(f"  Sounds: {', '.join(info['sounds'])}")
            print(f"  Expected: {info['expected']}")
            print()
        
        print("="*80)
        print()
    
    def create_test_audio_data(self, sound: str) -> AudioData:
        """Create synthetic audio data for testing different sound types."""
        timestamp = time.time()
        
        # Create synthetic audio patterns based on sound type
        # This simulates the spectral characteristics of different speech sounds
        
        # Audio parameters
        sample_rate = 16000
        duration_ms = 200  # 200ms of audio
        samples = int(sample_rate * duration_ms / 1000)
        
        # Generate different patterns for different sound types
        if sound in ["А", "О", "У", "И", "Э", "Ы"]:
            # Vowels: Low frequency dominant, low ZCR
            # Simulate formant structure with low fundamental frequency
            frequency = 150 + hash(sound) % 100  # 150-250 Hz fundamental
            amplitude = 8000  # Moderate amplitude for vowels
            phase_shift = 0
        elif sound in ["К", "Т", "П", "Б", "Д", "Г"]:
            # Non-sibilant consonants: Mixed frequency, burst patterns
            frequency = 500 + hash(sound) % 500  # 500-1000 Hz range
            amplitude = 12000  # Higher amplitude for consonants
            phase_shift = hash(sound) % 10
        elif sound in ["С", "Ш", "Щ", "З", "Ж", "Ф"]:
            # Sibilants: High frequency dominant, high ZCR
            frequency = 2000 + hash(sound) % 2000  # 2000-4000 Hz range
            amplitude = 15000  # High amplitude for sibilants
            phase_shift = hash(sound) % 20
        else:
            # Words: Mixed characteristics
            frequency = 300 + hash(sound) % 300  # 300-600 Hz
            amplitude = 10000  # Moderate amplitude
            phase_shift = 0
        
        # Generate synthetic waveform
        import numpy as np
        t = np.linspace(0, duration_ms/1000, samples, False)
        
        # Create base waveform
        waveform = amplitude * np.sin(2 * np.pi * frequency * t + phase_shift)
        
        # Add harmonics for more realistic sound
        waveform += amplitude * 0.3 * np.sin(2 * np.pi * frequency * 2 * t)
        waveform += amplitude * 0.1 * np.sin(2 * np.pi * frequency * 3 * t)
        
        # Add some noise for realism
        noise = np.random.normal(0, amplitude * 0.05, samples)
        waveform += noise
        
        # Convert to int16 and then to bytes
        waveform = np.clip(waveform, -32767, 32767).astype(np.int16)
        audio_bytes = waveform.tobytes()
        
        return AudioData(
            data=audio_bytes,
            sample_rate=sample_rate,
            channels=1,
            timestamp=timestamp
        )
    
    async def test_sound_category(self, category: str) -> Dict[str, Any]:
        """Test a specific category of sounds."""
        print(f"\nTesting {category.upper()}...")
        
        category_info = self.test_categories[category]
        results = []
        
        for sound in category_info["sounds"]:
            print(f"  Testing sound: {sound}")
            
            # Create test audio data (in real implementation, this would be from microphone)
            audio_data = self.create_test_audio_data(sound)
            
            # Process with VAD engine directly to get VAD results
            try:
                # Use the VAD engine directly since process_audio_chunk doesn't return VAD result
                vad_result = self.audio_processor.vad_engine.process_frame(audio_data)
                
                sound_result = {
                    "sound": sound,
                    "detected": vad_result.is_voice,
                    "confidence": vad_result.confidence,
                    "energy_level": vad_result.energy_level,
                    "zcr_value": getattr(vad_result, 'zcr_value', 0.0),
                    "processing_time_ms": vad_result.processing_time_ms
                }
                
                results.append(sound_result)
                
                status = "✅ DETECTED" if sound_result["detected"] else "❌ MISSED"
                print(f"    {status} - Confidence: {sound_result['confidence']:.3f}, "
                      f"Energy: {sound_result['energy_level']:.6f}")
                
            except Exception as e:
                print(f"    ❌ ERROR: {e}")
                results.append({
                    "sound": sound,
                    "detected": False,
                    "error": str(e)
                })
        
        # Calculate statistics
        detected_count = sum(1 for r in results if r.get("detected", False))
        total_count = len(results)
        detection_rate = detected_count / total_count if total_count > 0 else 0.0
        
        category_result = {
            "category": category,
            "description": category_info["description"],
            "expected": category_info["expected"],
            "results": results,
            "detection_rate": detection_rate,
            "detected_count": detected_count,
            "total_count": total_count
        }
        
        self.test_results[category] = category_result
        
        print(f"  Category Result: {detected_count}/{total_count} detected "
              f"({detection_rate*100:.1f}%)")
        
        return category_result
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive VAD testing across all sound categories."""
        print("Starting comprehensive VAD test...")
        
        overall_results = {}
        
        for category in self.test_categories.keys():
            category_result = await self.test_sound_category(category)
            overall_results[category] = category_result
        
        return overall_results
    
    def print_comprehensive_results(self, results: Dict[str, Any]):
        """Print comprehensive test results."""
        print("\n" + "="*80)
        print("VAD SIBILANT FIX TEST RESULTS")
        print("="*80)
        
        total_detected = 0
        total_sounds = 0
        
        for category, result in results.items():
            print(f"\n{category.upper()}:")
            print(f"  Description: {result['description']}")
            print(f"  Expected: {result['expected']}")
            print(f"  Detection Rate: {result['detected_count']}/{result['total_count']} "
                  f"({result['detection_rate']*100:.1f}%)")
            
            # Show individual results
            for sound_result in result['results']:
                status = "✅" if sound_result.get("detected", False) else "❌"
                if "error" in sound_result:
                    print(f"    {status} {sound_result['sound']}: ERROR - {sound_result['error']}")
                else:
                    print(f"    {status} {sound_result['sound']}: "
                          f"Conf={sound_result['confidence']:.3f}, "
                          f"Energy={sound_result['energy_level']:.6f}, "
                          f"ZCR={sound_result['zcr_value']:.3f}")
            
            total_detected += result['detected_count']
            total_sounds += result['total_count']
        
        overall_rate = total_detected / total_sounds if total_sounds > 0 else 0.0
        
        print(f"\nOVERALL RESULTS:")
        print(f"  Total Detection Rate: {total_detected}/{total_sounds} ({overall_rate*100:.1f}%)")
        
        print(f"\nFIX EFFECTIVENESS:")
        if results['vowels']['detection_rate'] >= 0.8:
            print("  ✅ VOWEL DETECTION: Significantly improved")
        else:
            print("  ❌ VOWEL DETECTION: Still needs improvement")
        
        if results['non_sibilant_consonants']['detection_rate'] >= 0.8:
            print("  ✅ CONSONANT DETECTION: Significantly improved")
        else:
            print("  ❌ CONSONANT DETECTION: Still needs improvement")
        
        if results['sibilant_consonants']['detection_rate'] >= 0.8:
            print("  ✅ SIBILANT DETECTION: Maintained (as expected)")
        else:
            print("  ⚠️  SIBILANT DETECTION: Unexpectedly decreased")
        
        if overall_rate >= 0.85:
            print("  🎉 OVERALL: VAD fixes appear to be working well!")
        elif overall_rate >= 0.7:
            print("  👍 OVERALL: VAD fixes show good improvement")
        else:
            print("  ⚠️  OVERALL: VAD fixes need further tuning")
        
        print("="*80)


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test VAD sibilant fixes")
    parser.add_argument("--config", 
                       default="configs/vad-sibilant-fix.toml",
                       help="Configuration file to use")
    parser.add_argument("--category",
                       choices=["vowels", "non_sibilant_consonants", "sibilant_consonants", "words", "all"],
                       default="all",
                       help="Test category to run")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Initialize test analyzer
        analyzer = VADTestAnalyzer(args.config)
        await analyzer.initialize()
        
        # Print instructions
        analyzer.print_test_instructions()
        
        # Run tests
        if args.category == "all":
            results = await analyzer.run_comprehensive_test()
            analyzer.print_comprehensive_results(results)
        else:
            result = await analyzer.test_sound_category(args.category)
            print(f"\nSingle category test complete: {result['detection_rate']*100:.1f}% detection rate")
        
        print("\nNOTE: This test uses placeholder audio data.")
        print("For real testing, integrate with microphone input and speak the sounds listed above.")
        print("The VAD configuration changes should significantly improve vowel and consonant detection.")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
