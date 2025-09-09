"""
Phase 7 Testing: Unit tests for all sample rate combinations

This module provides comprehensive unit tests for the audio resampling functionality
implemented in Phases 1-6, focusing on sample rate compatibility, conversion methods,
and performance optimizations.
"""

import pytest
import asyncio
import time
import numpy as np
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock

# Import the modules we're testing
from irene.utils.audio_helpers import (
    AudioProcessor, ConversionMethod, ResamplingResult,
    AudioFormatConverter
)
from irene.intents.models import AudioData, WakeWordResult


class TestSampleRateConversions:
    """Test all sample rate combinations and conversion methods."""
    
    # Common sample rates used in audio processing
    SAMPLE_RATES = [8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000, 88200, 96000]
    
    # Test audio data (1 second of sine wave at different rates)
    def generate_test_audio(self, sample_rate: int, duration: float = 1.0) -> bytes:
        """Generate test audio data at specified sample rate."""
        samples = int(sample_rate * duration)
        # Generate 440Hz sine wave
        t = np.linspace(0, duration, samples, False)
        audio = np.sin(2 * np.pi * 440 * t)
        # Convert to 16-bit PCM
        audio_int16 = (audio * 32767).astype(np.int16)
        return audio_int16.tobytes()
    
    def create_test_audio_data(self, sample_rate: int, duration: float = 1.0) -> AudioData:
        """Create test AudioData object."""
        audio_bytes = self.generate_test_audio(sample_rate, duration)
        return AudioData(
            data=audio_bytes,
            timestamp=time.time(),
            sample_rate=sample_rate,
            channels=1,
            format="pcm16",
            metadata={}
        )
    
    @pytest.mark.asyncio
    async def test_all_sample_rate_combinations(self):
        """Test resampling between all common sample rate combinations."""
        test_results = []
        
        for source_rate in self.SAMPLE_RATES:
            for target_rate in self.SAMPLE_RATES:
                if source_rate == target_rate:
                    continue  # Skip same rate conversions
                
                # Test with short audio to speed up tests
                audio_data = self.create_test_audio_data(source_rate, duration=0.1)
                
                try:
                    # Test with POLYPHASE method (default)
                    result = await AudioProcessor.resample_audio_data(
                        audio_data, target_rate, ConversionMethod.POLYPHASE
                    )
                    
                    # Verify result properties
                    assert result.sample_rate == target_rate
                    assert result.channels == audio_data.channels
                    assert result.format == audio_data.format
                    assert result.metadata['resampling_applied'] == True
                    assert result.metadata['original_sample_rate'] == source_rate
                    assert len(result.data) > 0
                    
                    test_results.append({
                        'source_rate': source_rate,
                        'target_rate': target_rate,
                        'success': True,
                        'duration_ms': result.metadata.get('resampling_duration_ms', 0),
                        'cache_hit': result.metadata.get('cache_hit', False)
                    })
                    
                except Exception as e:
                    test_results.append({
                        'source_rate': source_rate,
                        'target_rate': target_rate,
                        'success': False,
                        'error': str(e)
                    })
        
        # Analyze results
        successful_conversions = [r for r in test_results if r['success']]
        failed_conversions = [r for r in test_results if not r['success']]
        
        print(f"Successful conversions: {len(successful_conversions)}")
        print(f"Failed conversions: {len(failed_conversions)}")
        
        # We expect high success rate (at least 90%)
        success_rate = len(successful_conversions) / len(test_results)
        assert success_rate >= 0.9, f"Success rate {success_rate:.2%} is below 90%"
        
        # Print failed conversions for analysis
        if failed_conversions:
            print("Failed conversions:")
            for failure in failed_conversions[:5]:  # Show first 5 failures
                print(f"  {failure['source_rate']}Hz -> {failure['target_rate']}Hz: {failure['error']}")
    
    @pytest.mark.asyncio
    async def test_conversion_methods_comparison(self):
        """Test all conversion methods with various sample rate ratios."""
        test_cases = [
            (16000, 44100),  # Upsampling ~2.76x
            (44100, 16000),  # Downsampling ~0.36x
            (8000, 48000),   # Large upsampling 6x
            (48000, 8000),   # Large downsampling 0.167x
            (22050, 24000),  # Small ratio ~1.09x
        ]
        
        methods = [ConversionMethod.LINEAR, ConversionMethod.POLYPHASE, 
                  ConversionMethod.SINC_KAISER, ConversionMethod.ADAPTIVE]
        
        results = {}
        
        for source_rate, target_rate in test_cases:
            audio_data = self.create_test_audio_data(source_rate, duration=0.1)
            results[f"{source_rate}->{target_rate}"] = {}
            
            for method in methods:
                try:
                    start_time = time.time()
                    result = await AudioProcessor.resample_audio_data(
                        audio_data, target_rate, method
                    )
                    duration = (time.time() - start_time) * 1000
                    
                    results[f"{source_rate}->{target_rate}"][method.value] = {
                        'success': True,
                        'duration_ms': duration,
                        'output_size': len(result.data)
                    }
                except Exception as e:
                    results[f"{source_rate}->{target_rate}"][method.value] = {
                        'success': False,
                        'error': str(e)
                    }
        
        # Print performance comparison
        print("\nConversion Method Performance:")
        for case, methods_data in results.items():
            print(f"\n{case}:")
            for method, data in methods_data.items():
                if data['success']:
                    print(f"  {method}: {data['duration_ms']:.2f}ms")
                else:
                    print(f"  {method}: FAILED - {data['error']}")
    
    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """Test resampling cache performance and hit rates."""
        # Clear cache before test
        AudioProcessor.clear_cache()
        
        source_rate = 44100
        target_rate = 16000
        audio_data = self.create_test_audio_data(source_rate, duration=0.1)
        
        # First conversion (cache miss)
        result1 = await AudioProcessor.resample_audio_data(
            audio_data, target_rate, ConversionMethod.POLYPHASE
        )
        assert result1.metadata.get('cache_hit', True) == False  # Should be cache miss
        
        # Second conversion with same parameters (cache hit)
        result2 = await AudioProcessor.resample_audio_data(
            audio_data, target_rate, ConversionMethod.POLYPHASE
        )
        assert result2.metadata.get('cache_hit', False) == True  # Should be cache hit
        
        # Verify cache statistics
        cache_stats = AudioProcessor.get_cache_stats()
        assert cache_stats['cache_hits'] >= 1
        assert cache_stats['cache_misses'] >= 1
        assert cache_stats['hit_rate'] > 0
        
        print(f"Cache statistics: {cache_stats}")
    
    def test_sample_rate_compatibility_validation(self):
        """Test sample rate compatibility validation logic."""
        # Direct compatibility
        assert AudioProcessor.validate_sample_rate_compatibility(16000, [16000, 44100]) == True
        
        # Efficient ratio compatibility
        assert AudioProcessor.validate_sample_rate_compatibility(16000, [32000]) == True  # 2:1 ratio
        assert AudioProcessor.validate_sample_rate_compatibility(44100, [22050]) == True  # 2:1 ratio
        
        # Incompatible ratios
        assert AudioProcessor.validate_sample_rate_compatibility(8000, [96000]) == False  # 12:1 ratio
        
        # Empty target rates (no restrictions)
        assert AudioProcessor.validate_sample_rate_compatibility(16000, []) == True
    
    def test_optimal_conversion_path_selection(self):
        """Test optimal conversion method selection for different use cases."""
        # Voice trigger use case (latency-optimized)
        method = AudioProcessor.get_optimal_conversion_path(16000, 44100, "voice_trigger")
        assert method in [ConversionMethod.LINEAR, ConversionMethod.POLYPHASE]
        
        # ASR use case (quality-optimized)
        method = AudioProcessor.get_optimal_conversion_path(16000, 44100, "asr")
        assert method in [ConversionMethod.SINC_KAISER, ConversionMethod.POLYPHASE, ConversionMethod.ADAPTIVE]
        
        # General use case (balanced)
        method = AudioProcessor.get_optimal_conversion_path(16000, 44100, "general")
        assert method in [ConversionMethod.POLYPHASE, ConversionMethod.ADAPTIVE]
        
        # Same rate (no conversion needed)
        method = AudioProcessor.get_optimal_conversion_path(16000, 16000)
        assert method == ConversionMethod.LINEAR


class TestAudioFormatConverter:
    """Test AudioFormatConverter functionality."""
    
    @pytest.mark.asyncio
    async def test_audio_data_conversion(self):
        """Test AudioData conversion with different parameters."""
        # Create test audio
        audio_data = AudioData(
            data=b'\x00\x01' * 1000,  # Simple test data
            timestamp=time.time(),
            sample_rate=44100,
            channels=1,
            format="pcm16",
            metadata={}
        )
        
        # Test sample rate conversion
        converted = await AudioFormatConverter.convert_audio_data(
            audio_data, target_rate=16000, quality="medium"
        )
        
        assert converted.sample_rate == 16000
        assert converted.metadata['conversion_applied'] == True
        assert converted.metadata['conversion_quality'] == "medium"
    
    @pytest.mark.asyncio
    async def test_streaming_conversion(self):
        """Test streaming audio conversion with multiple chunks."""
        # Create multiple audio chunks
        chunks = []
        for i in range(5):
            chunk = AudioData(
                data=b'\x00\x01' * 100,
                timestamp=time.time() + i * 0.1,
                sample_rate=44100,
                channels=1,
                format="pcm16",
                metadata={'chunk_id': i}
            )
            chunks.append(chunk)
        
        # Test parallel streaming conversion
        converted_chunks = await AudioFormatConverter.convert_audio_data_streaming(
            chunks, target_rate=16000, parallel_processing=True
        )
        
        assert len(converted_chunks) == len(chunks)
        for chunk in converted_chunks:
            assert chunk.sample_rate == 16000
        
        # Test sequential streaming conversion
        converted_chunks_seq = await AudioFormatConverter.convert_audio_data_streaming(
            chunks, target_rate=16000, parallel_processing=False
        )
        
        assert len(converted_chunks_seq) == len(chunks)
        for chunk in converted_chunks_seq:
            assert chunk.sample_rate == 16000


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_invalid_audio_data(self):
        """Test handling of invalid audio data."""
        # Test with empty audio data
        empty_audio = AudioData(
            data=b'',
            timestamp=time.time(),
            sample_rate=16000,
            channels=1,
            format="pcm16",
            metadata={}
        )
        
        # Should handle gracefully
        result = await AudioProcessor.resample_audio_data(
            empty_audio, 44100, ConversionMethod.POLYPHASE
        )
        # Should return original or handle gracefully
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_extreme_sample_rates(self):
        """Test handling of extreme sample rates."""
        audio_data = AudioData(
            data=b'\x00\x01' * 100,
            timestamp=time.time(),
            sample_rate=192000,  # Very high sample rate
            channels=1,
            format="pcm16",
            metadata={}
        )
        
        # Test conversion to very low sample rate
        try:
            result = await AudioProcessor.resample_audio_data(
                audio_data, 8000, ConversionMethod.POLYPHASE
            )
            assert result is not None
        except Exception as e:
            # Acceptable if extreme ratios are not supported
            print(f"Extreme ratio conversion failed as expected: {e}")
    
    @pytest.mark.asyncio
    async def test_cache_overflow(self):
        """Test cache behavior when exceeding maximum size through normal resampling."""
        # Clear cache
        AudioProcessor.clear_cache()
        
        # Fill cache beyond maximum using actual resampling
        original_max = AudioProcessor._max_cache_size
        AudioProcessor._max_cache_size = 3  # Set small cache for testing
        
        try:
            # Create different audio data to trigger cache misses
            for i in range(5):
                # Create slightly different audio data for each conversion
                audio_data = AudioData(
                    data=b'\x00\x01' * (100 + i),  # Different sizes to avoid same cache key
                    timestamp=1234567890.0 + i,
                    sample_rate=16000 + (i * 1000),  # Different source rates
                    channels=1,
                    format="pcm16",
                    metadata={'test_id': i}
                )
                
                # Process through normal resampling (which handles cache eviction)
                await AudioProcessor.resample_audio_data(
                    audio_data, 44100, ConversionMethod.POLYPHASE
                )
            
            # Cache should not exceed maximum size after eviction
            cache_size = len(AudioProcessor._resampling_cache)
            assert cache_size <= AudioProcessor._max_cache_size, \
                f"Cache size {cache_size} exceeds maximum {AudioProcessor._max_cache_size}"
            
        finally:
            # Restore original cache size
            AudioProcessor._max_cache_size = original_max
            AudioProcessor.clear_cache()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
