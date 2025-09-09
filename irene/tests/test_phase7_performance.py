"""
Phase 7 Testing: Performance benchmarks for resampling overhead

This module provides comprehensive performance benchmarks for the audio resampling
system, measuring latency, throughput, memory usage, and cache effectiveness.
"""

import pytest
import asyncio
import time
import statistics
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from irene.utils.audio_helpers import (
    AudioProcessor, ConversionMethod, AudioFormatConverter
)
from irene.intents.models import AudioData


def create_test_audio(sample_rate: int, duration: float = 1.0, channels: int = 1) -> AudioData:
    """Generate test audio data at specified sample rate."""
    samples = int(sample_rate * duration * channels)
    # Generate 440Hz sine wave
    t = np.linspace(0, duration, samples, False)
    audio = np.sin(2 * np.pi * 440 * t)
    # Convert to 16-bit PCM
    audio_int16 = (audio * 32767).astype(np.int16)
    
    return AudioData(
        data=audio_int16.tobytes(),
        timestamp=time.time(),
        sample_rate=sample_rate,
        channels=channels,
        format="pcm16",
        metadata={'test_data': True}
    )


def measure_memory_usage() -> Dict[str, float]:
    """Measure current memory usage."""
    if not PSUTIL_AVAILABLE:
        return {'rss_mb': 0.0, 'vms_mb': 0.0}
    
    process = psutil.Process()
    memory_info = process.memory_info()
    return {
        'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size
        'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size
    }


class PerformanceBenchmarkBase:
    """Base class for performance benchmarks."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
    
    def create_test_audio(self, sample_rate: int, duration: float, channels: int = 1) -> AudioData:
        """Create test audio data of specified parameters."""
        samples = int(sample_rate * duration * channels)
        # Create realistic audio data (not just zeros)
        audio_array = np.random.randint(-32768, 32767, samples, dtype=np.int16)
        
        return AudioData(
            data=audio_array.tobytes(),
            timestamp=time.time(),
            sample_rate=sample_rate,
            channels=channels,
            format="pcm16",
            metadata={'test_data': True}
        )
    
    def measure_memory_usage(self) -> Dict[str, float]:
        """Measure current memory usage."""
        if not PSUTIL_AVAILABLE:
            return {'rss_mb': 0.0, 'vms_mb': 0.0}
        
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size
            'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size
        }
    
    def print_results_table(self, title: str):
        """Print benchmark results in a formatted table."""
        print(f"\n{title}")
        print("=" * len(title))
        
        if not self.results:
            print("No results to display")
            return
        
        # Print header
        headers = list(self.results[0].keys())
        header_line = " | ".join(f"{h:>12}" for h in headers)
        print(header_line)
        print("-" * len(header_line))
        
        # Print data rows
        for result in self.results:
            data_line = " | ".join(f"{str(result[h]):>12}" for h in headers)
            print(data_line)


class TestResamplingLatency:
    """Test resampling latency for real-time processing."""
    
    @pytest.mark.asyncio
    async def test_voice_trigger_latency_requirements(self):
        """Test that voice trigger resampling meets real-time latency requirements."""
        # Voice trigger scenarios: prioritize low latency
        test_cases = [
            {'name': 'VT_16k_to_16k', 'source': 16000, 'target': 16000, 'duration': 0.1},
            {'name': 'VT_44k_to_16k', 'source': 44100, 'target': 16000, 'duration': 0.1},
            {'name': 'VT_48k_to_16k', 'source': 48000, 'target': 16000, 'duration': 0.1},
        ]
        
        # Test with voice trigger optimized methods
        methods = [ConversionMethod.LINEAR, ConversionMethod.POLYPHASE]
        
        self.results = []
        
        for case in test_cases:
            audio_data = self.create_test_audio(case['source'], case['duration'])
            
            for method in methods:
                times = []
                
                # Multiple runs for statistical significance
                for _ in range(20):
                    start_time = time.perf_counter()
                    await AudioProcessor.resample_audio_data(audio_data, case['target'], method)
                    end_time = time.perf_counter()
                    times.append((end_time - start_time) * 1000)  # Convert to ms
                
                avg_time = statistics.mean(times)
                max_time = max(times)
                std_dev = statistics.stdev(times)
                
                # Calculate real-time performance ratio
                audio_duration_ms = case['duration'] * 1000
                real_time_ratio = avg_time / audio_duration_ms
                
                self.results.append({
                    'scenario': case['name'],
                    'method': method.value,
                    'avg_ms': f"{avg_time:.2f}",
                    'max_ms': f"{max_time:.2f}",
                    'std_ms': f"{std_dev:.2f}",
                    'rt_ratio': f"{real_time_ratio:.3f}",
                    'realtime': "✓" if real_time_ratio < 0.1 else "✗"
                })
        
        self.print_results_table("Voice Trigger Latency Benchmarks")
        
        # Assert real-time performance for voice trigger
        for result in self.results:
            rt_ratio = float(result['rt_ratio'])
            assert rt_ratio < 0.2, f"Voice trigger latency too high: {rt_ratio:.3f}x real-time"
    
    @pytest.mark.asyncio
    async def test_asr_quality_vs_performance(self):
        """Test ASR resampling quality vs performance trade-offs."""
        # ASR scenarios: balance quality and performance
        test_cases = [
            {'name': 'ASR_16k_to_44k', 'source': 16000, 'target': 44100, 'duration': 1.0},
            {'name': 'ASR_44k_to_16k', 'source': 44100, 'target': 16000, 'duration': 1.0},
            {'name': 'ASR_48k_to_16k', 'source': 48000, 'target': 16000, 'duration': 1.0},
        ]
        
        # Test all conversion methods for quality comparison
        methods = [
            ConversionMethod.LINEAR,
            ConversionMethod.POLYPHASE,
            ConversionMethod.SINC_KAISER,
            ConversionMethod.ADAPTIVE
        ]
        
        self.results = []
        
        for case in test_cases:
            audio_data = self.create_test_audio(case['source'], case['duration'])
            
            for method in methods:
                times = []
                
                # Multiple runs for statistical significance
                for _ in range(10):
                    start_time = time.perf_counter()
                    result = await AudioProcessor.resample_audio_data(audio_data, case['target'], method)
                    end_time = time.perf_counter()
                    times.append((end_time - start_time) * 1000)
                
                avg_time = statistics.mean(times)
                audio_duration_ms = case['duration'] * 1000
                real_time_ratio = avg_time / audio_duration_ms
                
                self.results.append({
                    'scenario': case['name'],
                    'method': method.value,
                    'avg_ms': f"{avg_time:.1f}",
                    'rt_ratio': f"{real_time_ratio:.3f}",
                    'quality': self._get_quality_rating(method),
                    'use_case': 'ASR' if real_time_ratio < 1.0 else 'Offline'
                })
        
        self.print_results_table("ASR Quality vs Performance Trade-offs")
    
    def _get_quality_rating(self, method: ConversionMethod) -> str:
        """Get subjective quality rating for conversion method."""
        quality_map = {
            ConversionMethod.LINEAR: "Low",
            ConversionMethod.POLYPHASE: "Medium",
            ConversionMethod.SINC_KAISER: "High",
            ConversionMethod.ADAPTIVE: "Variable"
        }
        return quality_map.get(method, "Unknown")


class TestThroughputBenchmarks(PerformanceBenchmarkBase):
    """Test audio processing throughput under load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_resampling_throughput(self):
        """Test throughput with concurrent resampling operations."""
        # Simulate multiple concurrent audio streams
        concurrent_streams = [2, 4, 8, 16]
        audio_duration = 0.5  # 500ms chunks
        source_rate = 44100
        target_rate = 16000
        
        self.results = []
        
        for num_streams in concurrent_streams:
            # Create audio data for each stream
            audio_streams = [
                self.create_test_audio(source_rate, audio_duration)
                for _ in range(num_streams)
            ]
            
            # Measure concurrent processing
            start_time = time.perf_counter()
            
            tasks = [
                AudioProcessor.resample_audio_data(audio, target_rate, ConversionMethod.POLYPHASE)
                for audio in audio_streams
            ]
            
            results = await asyncio.gather(*tasks)
            
            end_time = time.perf_counter()
            total_time = end_time - start_time
            
            # Calculate throughput metrics
            total_audio_duration = audio_duration * num_streams
            throughput_ratio = total_audio_duration / total_time
            
            self.results.append({
                'streams': num_streams,
                'total_time': f"{total_time:.2f}s",
                'audio_duration': f"{total_audio_duration:.2f}s",
                'throughput': f"{throughput_ratio:.2f}x",
                'per_stream': f"{total_time/num_streams:.3f}s"
            })
        
        self.print_results_table("Concurrent Resampling Throughput")
        
        # Assert reasonable throughput scaling
        for result in self.results:
            throughput = float(result['throughput'].rstrip('x'))
            assert throughput > 1.0, f"Throughput {throughput:.2f}x is below real-time"
    
    @pytest.mark.asyncio
    async def test_streaming_chunk_processing(self):
        """Test performance with streaming audio chunks."""
        chunk_sizes = [0.05, 0.1, 0.2, 0.5]  # 50ms to 500ms chunks
        sample_rate = 16000
        
        self.results = []
        
        for chunk_duration in chunk_sizes:
            # Create multiple chunks to simulate streaming
            num_chunks = 20
            chunks = [
                self.create_test_audio(sample_rate, chunk_duration)
                for _ in range(num_chunks)
            ]
            
            # Measure streaming processing performance
            start_time = time.perf_counter()
            
            # Process chunks sequentially (simulating real-time stream)
            for chunk in chunks:
                await AudioProcessor.resample_audio_data(chunk, 44100, ConversionMethod.POLYPHASE)
            
            end_time = time.perf_counter()
            total_time = end_time - start_time
            
            # Calculate metrics
            total_audio_duration = chunk_duration * num_chunks
            processing_ratio = total_time / total_audio_duration
            avg_chunk_time = (total_time / num_chunks) * 1000  # ms
            
            self.results.append({
                'chunk_ms': f"{chunk_duration*1000:.0f}",
                'chunks': num_chunks,
                'total_time': f"{total_time:.2f}s",
                'avg_chunk': f"{avg_chunk_time:.2f}ms",
                'processing': f"{processing_ratio:.3f}x",
                'realtime': "✓" if processing_ratio < 0.8 else "✗"
            })
        
        self.print_results_table("Streaming Chunk Processing Performance")


class TestMemoryUsageBenchmarks(PerformanceBenchmarkBase):
    """Test memory usage and efficiency."""
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available for memory monitoring")
    @pytest.mark.asyncio
    async def test_memory_usage_scaling(self):
        """Test memory usage with increasing audio duration."""
        durations = [0.1, 0.5, 1.0, 2.0, 5.0]  # 100ms to 5 seconds
        sample_rate = 44100
        
        self.results = []
        
        for duration in durations:
            # Clear cache to get baseline memory usage
            AudioProcessor.clear_cache()
            
            # Measure memory before processing
            memory_before = self.measure_memory_usage()
            
            # Create and process audio data
            audio_data = self.create_test_audio(sample_rate, duration)
            audio_size_mb = len(audio_data.data) / 1024 / 1024
            
            await AudioProcessor.resample_audio_data(audio_data, 16000, ConversionMethod.POLYPHASE)
            
            # Measure memory after processing
            memory_after = self.measure_memory_usage()
            memory_delta = memory_after['rss_mb'] - memory_before['rss_mb']
            
            self.results.append({
                'duration': f"{duration:.1f}s",
                'audio_mb': f"{audio_size_mb:.2f}",
                'mem_before': f"{memory_before['rss_mb']:.1f}",
                'mem_after': f"{memory_after['rss_mb']:.1f}",
                'mem_delta': f"{memory_delta:.2f}",
                'efficiency': f"{audio_size_mb/max(memory_delta, 0.01):.1f}"
            })
        
        self.print_results_table("Memory Usage Scaling")
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available for memory monitoring")
    @pytest.mark.asyncio
    async def test_cache_memory_efficiency(self):
        """Test memory efficiency of resampling cache."""
        # Clear cache and measure baseline
        AudioProcessor.clear_cache()
        memory_baseline = self.measure_memory_usage()
        
        # Fill cache with various conversions
        cache_test_cases = [
            (16000, 44100), (44100, 16000), (48000, 16000),
            (8000, 16000), (22050, 44100), (32000, 48000)
        ]
        
        self.results = []
        
        for i, (source_rate, target_rate) in enumerate(cache_test_cases):
            audio_data = self.create_test_audio(source_rate, 0.1)
            
            # Process audio (should add to cache)
            await AudioProcessor.resample_audio_data(audio_data, target_rate, ConversionMethod.POLYPHASE)
            
            # Measure memory usage
            memory_current = self.measure_memory_usage()
            cache_stats = AudioProcessor.get_cache_stats()
            
            memory_delta = memory_current['rss_mb'] - memory_baseline['rss_mb']
            
            self.results.append({
                'conversion': f"{source_rate}->{target_rate}",
                'cache_size': cache_stats['cache_size'],
                'memory_mb': f"{memory_current['rss_mb']:.1f}",
                'delta_mb': f"{memory_delta:.2f}",
                'hit_rate': f"{cache_stats['hit_rate']:.2%}",
                'efficiency': f"{cache_stats['cache_size']/max(memory_delta, 0.01):.1f}"
            })
        
        self.print_results_table("Cache Memory Efficiency")


class TestCachePerformance(PerformanceBenchmarkBase):
    """Test cache performance and effectiveness."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_performance_gain(self):
        """Measure performance gain from cache hits."""
        # Test with common conversion
        source_rate = 44100
        target_rate = 16000
        audio_data = self.create_test_audio(source_rate, 0.1)
        
        # Clear cache and measure cold performance
        AudioProcessor.clear_cache()
        
        cold_times = []
        for _ in range(5):
            start_time = time.perf_counter()
            await AudioProcessor.resample_audio_data(audio_data, target_rate, ConversionMethod.POLYPHASE)
            end_time = time.perf_counter()
            cold_times.append((end_time - start_time) * 1000)
        
        avg_cold_time = statistics.mean(cold_times)
        
        # Now measure warm (cached) performance
        warm_times = []
        for _ in range(5):
            start_time = time.perf_counter()
            result = await AudioProcessor.resample_audio_data(audio_data, target_rate, ConversionMethod.POLYPHASE)
            end_time = time.perf_counter()
            warm_times.append((end_time - start_time) * 1000)
            
            # Verify it's a cache hit
            assert result.metadata.get('cache_hit', False), "Expected cache hit"
        
        avg_warm_time = statistics.mean(warm_times)
        speedup = avg_cold_time / avg_warm_time
        
        self.results = [{
            'metric': 'Cold (no cache)',
            'avg_time_ms': f"{avg_cold_time:.3f}",
            'std_dev': f"{statistics.stdev(cold_times):.3f}",
            'cache_hit': "No",
            'speedup': "1.00x"
        }, {
            'metric': 'Warm (cached)',
            'avg_time_ms': f"{avg_warm_time:.3f}",
            'std_dev': f"{statistics.stdev(warm_times):.3f}",
            'cache_hit': "Yes",
            'speedup': f"{speedup:.2f}x"
        }]
        
        self.print_results_table("Cache Performance Comparison")
        
        # Assert significant speedup from caching
        assert speedup > 2.0, f"Cache speedup {speedup:.2f}x is insufficient"
    
    @pytest.mark.asyncio
    async def test_cache_eviction_performance(self):
        """Test performance when cache reaches capacity and eviction occurs."""
        # Set small cache size for testing
        original_max_size = AudioProcessor._max_cache_size
        AudioProcessor._max_cache_size = 5
        AudioProcessor.clear_cache()
        
        try:
            conversion_times = []
            cache_sizes = []
            
            # Generate many different conversions to trigger eviction
            for i in range(15):  # More than cache size
                source_rate = 16000 + (i * 1000)  # Varying source rates
                target_rate = 44100
                
                audio_data = self.create_test_audio(source_rate, 0.05)
                
                start_time = time.perf_counter()
                await AudioProcessor.resample_audio_data(audio_data, target_rate, ConversionMethod.POLYPHASE)
                end_time = time.perf_counter()
                
                conversion_time = (end_time - start_time) * 1000
                conversion_times.append(conversion_time)
                
                cache_stats = AudioProcessor.get_cache_stats()
                cache_sizes.append(cache_stats['cache_size'])
            
            # Analyze performance during cache eviction
            avg_time_before_eviction = statistics.mean(conversion_times[:5])
            avg_time_during_eviction = statistics.mean(conversion_times[5:10])
            avg_time_after_eviction = statistics.mean(conversion_times[10:])
            
            self.results = [{
                'phase': 'Before eviction',
                'avg_time_ms': f"{avg_time_before_eviction:.3f}",
                'cache_size': f"{statistics.mean(cache_sizes[:5]):.1f}",
                'performance': "Baseline"
            }, {
                'phase': 'During eviction',
                'avg_time_ms': f"{avg_time_during_eviction:.3f}",
                'cache_size': f"{statistics.mean(cache_sizes[5:10]):.1f}",
                'performance': f"{avg_time_during_eviction/avg_time_before_eviction:.2f}x"
            }, {
                'phase': 'After eviction',
                'avg_time_ms': f"{avg_time_after_eviction:.3f}",
                'cache_size': f"{statistics.mean(cache_sizes[10:]):.1f}",
                'performance': f"{avg_time_after_eviction/avg_time_before_eviction:.2f}x"
            }]
            
            self.print_results_table("Cache Eviction Performance Impact")
            
        finally:
            # Restore original cache size
            AudioProcessor._max_cache_size = original_max_size
            AudioProcessor.clear_cache()


class TestStressTests(PerformanceBenchmarkBase):
    """Stress tests for edge cases and extreme loads."""
    
    @pytest.mark.asyncio
    async def test_extreme_sample_rate_ratios(self):
        """Test performance with extreme sample rate conversion ratios."""
        extreme_cases = [
            {'name': 'Large_Upsample', 'source': 8000, 'target': 96000},  # 12x
            {'name': 'Large_Downsample', 'source': 96000, 'target': 8000},  # 0.083x
            {'name': 'Extreme_Upsample', 'source': 8000, 'target': 192000},  # 24x
            {'name': 'Odd_Ratio', 'source': 11025, 'target': 48000},  # ~4.35x
        ]
        
        self.results = []
        
        for case in extreme_cases:
            audio_data = self.create_test_audio(case['source'], 0.1)
            
            try:
                start_time = time.perf_counter()
                result = await AudioProcessor.resample_audio_data(
                    audio_data, case['target'], ConversionMethod.ADAPTIVE
                )
                end_time = time.perf_counter()
                
                processing_time = (end_time - start_time) * 1000
                ratio = case['target'] / case['source']
                
                self.results.append({
                    'case': case['name'],
                    'ratio': f"{ratio:.2f}x",
                    'time_ms': f"{processing_time:.2f}",
                    'success': "✓",
                    'output_size': f"{len(result.data)/1024:.1f}KB"
                })
                
            except Exception as e:
                self.results.append({
                    'case': case['name'],
                    'ratio': f"{case['target']/case['source']:.2f}x",
                    'time_ms': "N/A",
                    'success': "✗",
                    'output_size': str(e)[:20]
                })
        
        self.print_results_table("Extreme Sample Rate Ratio Performance")
    
    @pytest.mark.asyncio
    async def test_long_duration_audio_processing(self):
        """Test performance with long-duration audio files."""
        durations = [10.0, 30.0, 60.0]  # 10s, 30s, 1 minute
        sample_rate = 44100
        target_rate = 16000
        
        self.results = []
        
        for duration in durations:
            # Create large audio file
            audio_data = self.create_test_audio(sample_rate, duration)
            input_size_mb = len(audio_data.data) / 1024 / 1024
            
            # Measure memory before processing
            memory_before = self.measure_memory_usage()
            
            try:
                start_time = time.perf_counter()
                result = await AudioProcessor.resample_audio_data(
                    audio_data, target_rate, ConversionMethod.POLYPHASE
                )
                end_time = time.perf_counter()
                
                processing_time = end_time - start_time
                memory_after = self.measure_memory_usage()
                memory_used = memory_after['rss_mb'] - memory_before['rss_mb']
                
                # Calculate performance metrics
                real_time_ratio = processing_time / duration
                throughput_mbps = input_size_mb / processing_time
                
                self.results.append({
                    'duration': f"{duration:.0f}s",
                    'input_mb': f"{input_size_mb:.1f}",
                    'proc_time': f"{processing_time:.1f}s",
                    'rt_ratio': f"{real_time_ratio:.3f}x",
                    'throughput': f"{throughput_mbps:.1f}MB/s",
                    'memory_mb': f"{memory_used:.1f}",
                    'success': "✓"
                })
                
            except Exception as e:
                self.results.append({
                    'duration': f"{duration:.0f}s",
                    'input_mb': f"{input_size_mb:.1f}",
                    'proc_time': "Failed",
                    'rt_ratio': "N/A",
                    'throughput': "N/A",
                    'memory_mb': "N/A",
                    'success': f"✗ {str(e)[:20]}"
                })
        
        self.print_results_table("Long Duration Audio Processing")


if __name__ == "__main__":
    # Run performance benchmarks
    pytest.main([__file__, "-v", "-s"])  # -s to show print output
