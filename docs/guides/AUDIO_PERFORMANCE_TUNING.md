# Audio Performance Tuning Guide

This guide provides detailed recommendations for optimizing audio processing performance in Irene Voice Assistant, covering latency optimization, throughput maximization, memory efficiency, and quality trade-offs.

## Table of Contents

1. [Performance Overview](#performance-overview)
2. [Latency Optimization](#latency-optimization)
3. [Throughput Maximization](#throughput-maximization)
4. [Memory Efficiency](#memory-efficiency)
5. [Quality vs Performance Trade-offs](#quality-vs-performance-trade-offs)
6. [Cache Optimization](#cache-optimization)
7. [Hardware-Specific Tuning](#hardware-specific-tuning)
8. [Monitoring and Benchmarking](#monitoring-and-benchmarking)
9. [Advanced Optimization](#advanced-optimization)

## Performance Overview

Irene Voice Assistant's audio processing pipeline is designed for real-time performance with configurable quality trade-offs. Understanding the performance characteristics helps optimize for your specific use case.

### Key Performance Metrics

| Metric | Voice Trigger Target | ASR Target | Description |
|--------|---------------------|------------|-------------|
| **Real-time Factor** | < 0.1x | < 1.0x | Processing time vs audio duration |
| **Latency** | < 100ms | < 500ms | End-to-end processing delay |
| **Memory Usage** | < 50MB | < 200MB | Peak memory consumption |
| **Cache Hit Rate** | > 30% | > 60% | Resampling cache effectiveness |
| **Throughput** | > 10x real-time | > 2x real-time | Concurrent processing capability |

### Performance Bottlenecks

Common bottlenecks and their solutions:

1. **Resampling Overhead**: Use appropriate quality settings and caching
2. **Provider Switching**: Minimize fallbacks through proper configuration
3. **Memory Allocation**: Use buffer pooling and cache management
4. **I/O Latency**: Optimize chunk sizes and buffering
5. **Provider Latency**: Choose efficient providers and configurations

## Latency Optimization

### Voice Trigger Optimization

Voice triggers require the lowest latency for responsive user experience.

#### Optimal Configuration
```toml
[voice_trigger]
sample_rate = 16000          # Optimal for most providers
resample_quality = "fast"    # Linear interpolation for speed
allow_resampling = true      # Enable flexibility
strict_validation = false    # Allow graceful degradation

[inputs.microphone_config]
chunk_size = 512             # Smaller chunks = lower latency
sample_rate = 16000          # Match voice trigger rate
```

#### Provider Selection
```toml
# Use latency-optimized providers
[voice_trigger.providers.microwakeword]
enabled = true               # Optimized for speed
sample_rate = 16000          # No resampling overhead

[voice_trigger.providers.openwakeword]
enabled = true               # Good balance of speed and accuracy
inference_framework = "tflite"  # Faster than ONNX on some hardware
```

#### Latency Measurement
```python
import time
from irene.components.voice_trigger_component import VoiceTriggerComponent
from irene.intents.models import AudioData

# Create test audio
audio_data = AudioData(
    data=b'\x00\x01' * 800,  # 50ms at 16kHz
    timestamp=time.time(),
    sample_rate=16000,
    channels=1,
    format="pcm16",
    metadata={}
)

# Measure latency
vt_component = VoiceTriggerComponent()
start_time = time.perf_counter()
result = await vt_component.detect(audio_data)
latency = (time.perf_counter() - start_time) * 1000

print(f"Voice trigger latency: {latency:.2f}ms")
print(f"Real-time factor: {latency / 50:.3f}x")  # 50ms audio
```

#### Advanced Latency Reduction

**1. Minimize Resampling**
```toml
# Match all components to same sample rate
[inputs.microphone_config]
sample_rate = 16000

[voice_trigger]
sample_rate = 16000          # No resampling needed

[asr]
sample_rate = 16000          # Consistent across components
```

**2. Use Hardware-Optimized Paths**
```toml
[voice_trigger.providers.microwakeword]
chunk_size = 320             # Optimized for micro_speech
sample_rate = 16000          # Hardware-optimized rate
```

**3. Buffer Pool Optimization**
```python
# Pre-allocate buffers for consistent performance
from irene.utils.audio_helpers import AudioProcessor

# Clear and pre-warm buffer pool
AudioProcessor.clear_cache()
# Process dummy audio to initialize buffers
# (Implementation would pre-allocate common buffer sizes)
```

### ASR Latency Optimization

For interactive applications, ASR should complete within 500ms.

#### Streaming Configuration
```toml
[asr]
sample_rate = 16000          # Efficient processing rate
resample_quality = "medium"  # Balance quality and speed
allow_resampling = true      # Enable flexibility

[asr.providers.whisper]
model_size = "base"          # Faster than larger models
device = "cuda"              # GPU acceleration if available
```

#### Chunked Processing
```python
# Process audio in chunks for lower latency
from irene.utils.audio_helpers import AudioFormatConverter

async def process_audio_stream(audio_chunks):
    # Use parallel processing for chunks
    converted_chunks = await AudioFormatConverter.convert_audio_data_streaming(
        audio_chunks, 
        target_rate=16000, 
        parallel_processing=True  # Enable parallel processing
    )
    return converted_chunks
```

## Throughput Maximization

### Concurrent Processing

For high-throughput scenarios (multiple simultaneous users or batch processing):

#### Configuration for Throughput
```toml
[asr]
resample_quality = "medium"  # Balance for batch processing
allow_resampling = true

# Enable multiple providers for load distribution
[asr.providers.whisper]
enabled = true
device = "cuda"              # GPU for high throughput

[asr.providers.vosk]
enabled = true               # CPU fallback

[voice_trigger.providers.openwakeword]
enabled = true
```

#### Parallel Processing Example
```python
import asyncio
from irene.components.asr_component import ASRComponent

async def process_multiple_audio_streams(audio_streams):
    """Process multiple audio streams concurrently."""
    asr_component = ASRComponent()
    
    # Create tasks for parallel processing
    tasks = [
        asr_component.process_audio(audio_data) 
        for audio_data in audio_streams
    ]
    
    # Process all streams concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return results

# Benchmark throughput
import time

start_time = time.time()
results = await process_multiple_audio_streams(test_audio_streams)
total_time = time.time() - start_time

audio_duration = len(test_audio_streams) * 1.0  # Assume 1s per stream
throughput_factor = audio_duration / total_time

print(f"Throughput: {throughput_factor:.2f}x real-time")
```

### Load Balancing

Distribute load across multiple providers:

```python
class LoadBalancedASR:
    def __init__(self):
        self.providers = ["whisper", "vosk", "google_cloud"]
        self.current_provider_index = 0
    
    async def process_audio_round_robin(self, audio_data):
        """Distribute requests across providers using round-robin."""
        provider = self.providers[self.current_provider_index]
        self.current_provider_index = (self.current_provider_index + 1) % len(self.providers)
        
        return await self.asr_component.process_audio(audio_data, provider=provider)
```

## Memory Efficiency

### Memory Usage Optimization

#### Buffer Management
```toml
[inputs.microphone_config]
chunk_size = 1024            # Balance latency and memory usage

# Avoid large audio chunks unless necessary
# Large chunks = higher memory usage but potentially better efficiency
```

#### Cache Size Management
```python
from irene.utils.audio_helpers import AudioProcessor

# Monitor and manage cache size
def manage_cache():
    cache_stats = AudioProcessor.get_cache_stats()
    
    if cache_stats['cache_size'] > 50:  # Limit cache size
        AudioProcessor.clear_cache()
        print("Cache cleared due to size limit")
    
    memory_usage = cache_stats['cache_size'] * 0.1  # Estimate MB per entry
    print(f"Estimated cache memory: {memory_usage:.1f}MB")

# Call periodically
manage_cache()
```

#### Memory-Efficient Streaming
```python
async def memory_efficient_processing(large_audio_file):
    """Process large audio files without loading entirely into memory."""
    chunk_size = 16000  # 1 second at 16kHz
    
    # Process in chunks to limit memory usage
    for chunk_start in range(0, len(large_audio_file), chunk_size):
        chunk_end = min(chunk_start + chunk_size, len(large_audio_file))
        chunk_data = large_audio_file[chunk_start:chunk_end]
        
        # Process chunk
        audio_chunk = AudioData(
            data=chunk_data,
            timestamp=time.time(),
            sample_rate=16000,
            channels=1,
            format="pcm16",
            metadata={'chunk_index': chunk_start // chunk_size}
        )
        
        result = await process_audio_chunk(audio_chunk)
        yield result
        
        # Optional: explicit cleanup
        del audio_chunk, chunk_data
```

### Memory Monitoring

```python
import psutil

def monitor_memory_usage():
    """Monitor memory usage during audio processing."""
    process = psutil.Process()
    memory_info = process.memory_info()
    
    return {
        'rss_mb': memory_info.rss / 1024 / 1024,
        'vms_mb': memory_info.vms / 1024 / 1024,
        'percent': process.memory_percent()
    }

# Monitor before and after processing
memory_before = monitor_memory_usage()
# ... audio processing ...
memory_after = monitor_memory_usage()

memory_delta = memory_after['rss_mb'] - memory_before['rss_mb']
print(f"Memory usage increased by {memory_delta:.1f}MB")
```

## Quality vs Performance Trade-offs

### Resampling Quality Levels

Understanding the trade-offs helps choose the right quality level:

| Quality Level | Method | CPU Usage | Latency | Quality | Use Case |
|---------------|--------|-----------|---------|---------|----------|
| **fast** | Linear | Very Low | ~0.1ms | Basic | Voice trigger, real-time |
| **medium** | Polyphase | Low | ~0.3ms | Good | General purpose |
| **high** | Kaiser Sinc | Medium | ~0.8ms | Excellent | ASR transcription |
| **adaptive** | Dynamic | Variable | Variable | Optimal | Mixed scenarios |

#### Configuration Examples

**Real-time Priority (Voice Trigger)**
```toml
[voice_trigger]
resample_quality = "fast"    # Minimize latency
sample_rate = 16000          # Optimal rate
```

**Quality Priority (High-accuracy ASR)**
```toml
[asr]
resample_quality = "high"    # Maximize transcription quality
sample_rate = 16000          # Provider optimal rate
```

**Balanced (General Use)**
```toml
[asr]
resample_quality = "medium"  # Good balance
[voice_trigger]
resample_quality = "fast"    # Still prioritize responsiveness
```

**Adaptive (Mixed Environment)**
```toml
[asr]
resample_quality = "adaptive"  # Automatic optimization based on sample rate ratio
```

### Quality Measurement

```python
# Measure quality impact
import time

async def quality_benchmark():
    """Benchmark different quality levels."""
    from irene.utils.audio_helpers import AudioProcessor, ConversionMethod
    
    audio_data = create_test_audio(44100, 1.0)  # 1 second of test audio
    methods = [
        (ConversionMethod.LINEAR, "fast"),
        (ConversionMethod.POLYPHASE, "medium"), 
        (ConversionMethod.SINC_KAISER, "high"),
        (ConversionMethod.ADAPTIVE, "adaptive")
    ]
    
    results = []
    for method, name in methods:
        times = []
        for _ in range(5):  # Average over 5 runs
            start_time = time.perf_counter()
            result = await AudioProcessor.resample_audio_data(audio_data, 16000, method)
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)
        
        avg_time = sum(times) / len(times)
        results.append({
            'method': name,
            'avg_time_ms': avg_time,
            'real_time_factor': avg_time / 1000  # 1 second audio
        })
    
    return results

# Run benchmark
benchmark_results = await quality_benchmark()
for result in benchmark_results:
    print(f"{result['method']}: {result['avg_time_ms']:.2f}ms ({result['real_time_factor']:.3f}x)")
```

## Cache Optimization

### Cache Configuration

The resampling cache significantly improves performance for repeated operations:

#### Monitoring Cache Effectiveness
```python
from irene.utils.audio_helpers import AudioProcessor

def analyze_cache_performance():
    """Analyze cache performance and provide recommendations."""
    stats = AudioProcessor.get_cache_stats()
    
    print(f"Cache Statistics:")
    print(f"  Hit rate: {stats['hit_rate']:.2%}")
    print(f"  Cache size: {stats['cache_size']}")
    print(f"  Total hits: {stats['cache_hits']}")
    print(f"  Total misses: {stats['cache_misses']}")
    
    # Recommendations
    if stats['hit_rate'] < 0.3:
        print("Recommendation: Low hit rate suggests inconsistent audio parameters")
    elif stats['hit_rate'] > 0.8:
        print("Recommendation: High hit rate - cache is very effective")
    
    if stats['cache_size'] > 50:
        print("Recommendation: Consider clearing cache to free memory")

# Call periodically to monitor cache performance
analyze_cache_performance()
```

#### Cache Tuning
```python
# Tune cache size based on usage patterns
def tune_cache_size(target_hit_rate=0.6):
    """Adjust cache size to achieve target hit rate."""
    stats = AudioProcessor.get_cache_stats()
    
    if stats['hit_rate'] < target_hit_rate and stats['cache_size'] < 100:
        # Increase cache size (in application logic)
        AudioProcessor._max_cache_size = min(100, AudioProcessor._max_cache_size * 1.5)
        print(f"Increased cache size to {AudioProcessor._max_cache_size}")
    elif stats['hit_rate'] > 0.8 and stats['cache_size'] > 20:
        # Can reduce cache size
        AudioProcessor._max_cache_size = max(20, AudioProcessor._max_cache_size * 0.8)
        print(f"Reduced cache size to {AudioProcessor._max_cache_size}")
```

### Cache Usage Patterns

#### Optimal Cache Usage
```python
# Use consistent audio parameters for better cache hits
def process_audio_batch(audio_files):
    """Process multiple files with consistent parameters for cache efficiency."""
    target_rate = 16000
    quality = ConversionMethod.POLYPHASE
    
    for audio_file in audio_files:
        # Consistent parameters improve cache hit rate
        result = await AudioProcessor.resample_audio_data(audio_file, target_rate, quality)
        yield result

# Pre-warm cache with common conversions
async def warm_cache():
    """Pre-warm cache with common conversion patterns."""
    common_conversions = [
        (44100, 16000),
        (48000, 16000),
        (16000, 44100)
    ]
    
    for source_rate, target_rate in common_conversions:
        dummy_audio = create_test_audio(source_rate, 0.1)  # 100ms
        await AudioProcessor.resample_audio_data(dummy_audio, target_rate)
    
    print("Cache pre-warmed with common conversions")
```

## Hardware-Specific Tuning

### CPU Optimization

#### Multi-core Utilization
```toml
# Enable parallel processing where possible
[asr]
parallel_processing = true   # Use multiple cores for batch processing

[voice_trigger]
parallel_processing = false  # Keep single-threaded for latency
```

#### CPU-Specific Settings
```python
import multiprocessing

# Adjust based on CPU cores
cpu_count = multiprocessing.cpu_count()

if cpu_count >= 8:
    # High-end CPU: Enable all features
    parallel_chunks = 4
    cache_size = 100
elif cpu_count >= 4:
    # Mid-range CPU: Balanced settings
    parallel_chunks = 2
    cache_size = 50
else:
    # Low-end CPU: Conservative settings
    parallel_chunks = 1
    cache_size = 20

print(f"Configured for {cpu_count} CPU cores")
```

### GPU Optimization

#### GPU-Accelerated Providers
```toml
[asr.providers.whisper]
device = "cuda"              # Use GPU if available
model_size = "large"         # Can use larger models with GPU

[asr.providers.vosk]
device = "cpu"               # Fallback to CPU
```

#### GPU Memory Management
```python
# Monitor GPU memory usage for Whisper
def check_gpu_memory():
    try:
        import torch
        if torch.cuda.is_available():
            memory_allocated = torch.cuda.memory_allocated() / 1024**3  # GB
            memory_cached = torch.cuda.memory_reserved() / 1024**3
            print(f"GPU Memory - Allocated: {memory_allocated:.1f}GB, Cached: {memory_cached:.1f}GB")
    except ImportError:
        print("PyTorch not available for GPU monitoring")

check_gpu_memory()
```

### Memory-Constrained Devices

#### Low-Memory Configuration
```toml
[inputs.microphone_config]
chunk_size = 512             # Smaller chunks
sample_rate = 16000          # Efficient rate

[asr]
resample_quality = "fast"    # Minimal memory allocation
cache_size = 10              # Small cache

[voice_trigger]
resample_quality = "fast"    # Minimal processing
```

#### Memory Pressure Handling
```python
def handle_memory_pressure():
    """Handle low memory situations."""
    import psutil
    
    memory = psutil.virtual_memory()
    if memory.percent > 85:  # High memory usage
        print("High memory usage detected, clearing caches")
        AudioProcessor.clear_cache()
        
        # Force garbage collection
        import gc
        gc.collect()
        
        return True
    return False

# Monitor memory and clear caches when needed
if handle_memory_pressure():
    print("Memory pressure handled")
```

## Monitoring and Benchmarking

### Performance Metrics Collection

#### Comprehensive Monitoring
```python
import time
from typing import Dict, List

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'resampling_times': [],
            'cache_hit_rates': [],
            'memory_usage': [],
            'latencies': []
        }
    
    def record_resampling(self, duration_ms: float, cache_hit: bool):
        """Record resampling performance."""
        self.metrics['resampling_times'].append(duration_ms)
        
        # Update cache hit rate
        hits = sum(1 for _, hit in self.metrics.get('cache_hits', []) if hit)
        total = len(self.metrics.get('cache_hits', [])) + 1
        self.metrics['cache_hits'].append((time.time(), cache_hit))
        
    def record_latency(self, component: str, latency_ms: float):
        """Record component latency."""
        self.metrics['latencies'].append({
            'component': component,
            'latency_ms': latency_ms,
            'timestamp': time.time()
        })
    
    def get_summary(self) -> Dict:
        """Get performance summary."""
        if not self.metrics['resampling_times']:
            return {}
        
        return {
            'avg_resampling_ms': sum(self.metrics['resampling_times']) / len(self.metrics['resampling_times']),
            'max_resampling_ms': max(self.metrics['resampling_times']),
            'cache_hit_rate': sum(1 for _, hit in self.metrics.get('cache_hits', []) if hit) / max(1, len(self.metrics.get('cache_hits', []))),
            'avg_latency_ms': sum(m['latency_ms'] for m in self.metrics['latencies']) / max(1, len(self.metrics['latencies']))
        }

# Usage
monitor = PerformanceMonitor()

# Record metrics during processing
start_time = time.perf_counter()
result = await AudioProcessor.resample_audio_data(audio_data, 16000)
duration = (time.perf_counter() - start_time) * 1000

monitor.record_resampling(duration, result.metadata.get('cache_hit', False))

# Get summary
summary = monitor.get_summary()
print(f"Performance Summary: {summary}")
```

### Automated Benchmarking

#### Benchmark Suite
```python
async def run_performance_benchmark():
    """Run comprehensive performance benchmark."""
    from irene.tests.test_phase7_performance import (
        TestResamplingLatency, TestThroughputBenchmarks, 
        TestMemoryUsageBenchmarks, TestCachePerformance
    )
    
    benchmarks = [
        TestResamplingLatency(),
        TestThroughputBenchmarks(),
        TestMemoryUsageBenchmarks(),
        TestCachePerformance()
    ]
    
    results = {}
    for benchmark in benchmarks:
        print(f"Running {benchmark.__class__.__name__}...")
        
        # Run benchmark methods
        if hasattr(benchmark, 'test_voice_trigger_latency_requirements'):
            await benchmark.test_voice_trigger_latency_requirements()
            
        if hasattr(benchmark, 'results'):
            results[benchmark.__class__.__name__] = benchmark.results
    
    return results

# Run full benchmark suite
benchmark_results = await run_performance_benchmark()
```

### Continuous Monitoring

#### Production Monitoring
```python
def setup_production_monitoring():
    """Set up continuous performance monitoring for production."""
    import threading
    import time
    
    def monitor_performance():
        while True:
            # Check cache performance
            cache_stats = AudioProcessor.get_cache_stats()
            
            # Check memory usage
            memory = monitor_memory_usage()
            
            # Log metrics (integrate with your logging system)
            print(f"Cache hit rate: {cache_stats['hit_rate']:.2%}, Memory: {memory['rss_mb']:.1f}MB")
            
            time.sleep(60)  # Monitor every minute
    
    # Start monitoring thread
    monitor_thread = threading.Thread(target=monitor_performance, daemon=True)
    monitor_thread.start()
    
    print("Performance monitoring started")

# Enable in production
setup_production_monitoring()
```

## Advanced Optimization

### Custom Conversion Methods

For specialized use cases, you can implement custom conversion methods:

```python
from irene.utils.audio_helpers import ConversionMethod, AudioProcessor

# Custom high-speed conversion for specific hardware
class CustomAudioProcessor(AudioProcessor):
    @staticmethod
    async def fast_hardware_resample(audio_data, target_rate):
        """Custom resampling optimized for specific hardware."""
        # Implement hardware-specific optimization
        # This could use specialized libraries or hardware acceleration
        pass

# Use custom processor
processor = CustomAudioProcessor()
```

### Profile-Guided Optimization

Use profiling to identify bottlenecks:

```python
import cProfile
import pstats

def profile_audio_processing():
    """Profile audio processing to identify bottlenecks."""
    profiler = cProfile.Profile()
    
    profiler.enable()
    # Run audio processing workload
    # ... audio processing code ...
    profiler.disable()
    
    # Analyze results
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # Top 20 functions

# Run profiling
profile_audio_processing()
```

### System-Level Optimization

#### Linux-Specific Optimizations
```bash
# Set real-time priorities
sudo chrt -f 50 python -m irene

# Optimize CPU governor
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Increase audio buffer sizes
echo 'options snd-hda-intel bdl_pos_adj=32' | sudo tee -a /etc/modprobe.d/alsa-base.conf
```

#### Docker Optimization
```dockerfile
# Optimize Docker container for audio processing
FROM python:3.11-slim

# Install audio libraries
RUN apt-get update && apt-get install -y \
    libasound2-dev \
    pulseaudio \
    --no-install-recommends

# Set real-time capabilities
RUN setcap cap_sys_nice+ep /usr/local/bin/python

# Optimize for audio workload
ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=4
```

This comprehensive performance tuning guide provides the foundation for optimizing Irene Voice Assistant's audio processing pipeline for your specific requirements and hardware constraints.
