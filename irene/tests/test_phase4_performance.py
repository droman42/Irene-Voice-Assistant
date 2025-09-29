"""
Phase 4 Performance Tests - Latency Impact Measurement

Performance tests for Phase 4 TODO16 implementation focusing on:
- <5ms latency threshold validation
- Performance optimization effectiveness
- Caching performance improvements
- Memory usage optimization
- Scalability under load
"""

import pytest
import asyncio
import time
import gc
import os
from typing import Dict, Any, List
from unittest.mock import MagicMock
from concurrent.futures import ThreadPoolExecutor

from irene.intents.models import UnifiedConversationContext, Intent
from irene.intents.context import ContextManager
from irene.core.metrics import get_metrics_collector
from irene.config.models import ContextualCommandsConfig


class TestPhase4LatencyValidation:
    """Test latency requirements and thresholds"""
    
    @pytest.fixture
    def performance_config(self):
        """Performance configuration for testing"""
        return ContextualCommandsConfig(
            enable_pattern_caching=True,
            cache_ttl_seconds=300,
            max_cache_size_patterns=1000,
            performance_monitoring=True,
            latency_threshold_ms=5.0
        )
    
    @pytest.fixture
    def context_manager_with_monitoring(self, performance_config):
        """Context manager with performance monitoring enabled"""
        # Configure integrated MetricsCollector
        metrics_collector = get_metrics_collector()
        metrics_collector.set_contextual_command_config(performance_config)
        return ContextManager()
    
    @pytest.mark.asyncio
    async def test_single_action_disambiguation_latency(self, context_manager_with_monitoring):
        """Test disambiguation latency with single active action"""
        context_manager = context_manager_with_monitoring
        session_id = "latency_single"
        context = await context_manager.get_context(session_id)
        
        # Single active action
        context.active_actions = {
            "single_action": {
                "domain": "audio",
                "action": "play_music",
                "started_at": time.time()
            }
        }
        
        domain_priorities = {"audio": 90}
        
        # Measure latency over multiple runs
        latencies = []
        for _ in range(10):
            start_time = time.perf_counter()
            
            resolution = context_manager.resolve_contextual_command_ambiguity(
                session_id=session_id,
                command_type="stop",
                domain_priorities=domain_priorities
            )
            
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
            
            # Verify resolution worked
            assert resolution["target_domain"] == "audio"
        
        # Verify latency requirements
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        assert avg_latency < 2.0, f"Average latency {avg_latency:.2f}ms exceeds 2ms for single action"
        assert max_latency < 5.0, f"Max latency {max_latency:.2f}ms exceeds 5ms threshold"
        
        print(f"Single action disambiguation - Avg: {avg_latency:.2f}ms, Max: {max_latency:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_multi_domain_disambiguation_latency(self, context_manager_with_monitoring):
        """Test disambiguation latency with multiple domains"""
        context_manager = context_manager_with_monitoring
        session_id = "latency_multi"
        context = await context_manager.get_context(session_id)
        
        # Multiple active actions across domains
        current_time = time.time()
        context.active_actions = {
            "audio_action": {
                "domain": "audio",
                "action": "play_music",
                "started_at": current_time - 30
            },
            "timer_action": {
                "domain": "timer",
                "action": "set_timer",
                "started_at": current_time - 20
            },
            "voice_action": {
                "domain": "voice_synthesis",
                "action": "speak_text",
                "started_at": current_time - 10
            }
        }
        
        domain_priorities = {"audio": 90, "timer": 70, "voice_synthesis": 60}
        
        # Measure latency over multiple runs
        latencies = []
        for _ in range(10):
            start_time = time.perf_counter()
            
            resolution = context_manager.resolve_contextual_command_ambiguity(
                session_id=session_id,
                command_type="stop",
                domain_priorities=domain_priorities
            )
            
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
            
            # Verify resolution worked
            assert resolution["target_domain"] == "audio"  # Highest priority
        
        # Verify latency requirements
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        assert avg_latency < 4.0, f"Average latency {avg_latency:.2f}ms exceeds 4ms for multi-domain"
        assert max_latency < 5.0, f"Max latency {max_latency:.2f}ms exceeds 5ms threshold"
        
        print(f"Multi-domain disambiguation - Avg: {avg_latency:.2f}ms, Max: {max_latency:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_complex_scenario_latency(self, context_manager_with_monitoring):
        """Test disambiguation latency with complex scenario (many actions)"""
        context_manager = context_manager_with_monitoring
        session_id = "latency_complex"
        context = await context_manager.get_context(session_id)
        
        # Many active actions for complex disambiguation
        current_time = time.time()
        for i in range(15):  # 15 active actions
            domain = ["audio", "timer", "voice_synthesis", "system", "conversation"][i % 5]
            context.active_actions[f"action_{i}"] = {
                "domain": domain,
                "action": f"action_{i}",
                "started_at": current_time - (i * 3)
            }
        
        domain_priorities = {
            "audio": 90,
            "timer": 70,
            "voice_synthesis": 60,
            "system": 50,
            "conversation": 40
        }
        
        # Measure latency over multiple runs
        latencies = []
        for _ in range(5):  # Fewer runs for complex scenario
            start_time = time.perf_counter()
            
            resolution = context_manager.resolve_contextual_command_ambiguity(
                session_id=session_id,
                command_type="stop",
                domain_priorities=domain_priorities
            )
            
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
            
            # Verify resolution worked
            assert resolution["target_domain"] is not None
        
        # Verify latency requirements (more relaxed for complex scenarios)
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        assert avg_latency < 5.0, f"Average latency {avg_latency:.2f}ms exceeds 5ms for complex scenario"
        assert max_latency < 8.0, f"Max latency {max_latency:.2f}ms exceeds 8ms for complex scenario"
        
        print(f"Complex scenario disambiguation - Avg: {avg_latency:.2f}ms, Max: {max_latency:.2f}ms")


class TestPhase4CachingPerformance:
    """Test caching performance improvements"""
    
    @pytest.fixture
    def cache_config(self):
        """Cache configuration for testing"""
        return ContextualCommandsConfig(
            enable_pattern_caching=True,
            cache_ttl_seconds=60,  # Short TTL for testing
            max_cache_size_patterns=100,
            performance_monitoring=True,
            latency_threshold_ms=5.0
        )
    
    def test_ttl_cache_performance(self, cache_config):
        """Test TTL cache performance characteristics"""
        cache = TTLCache(max_size=100, ttl_seconds=60)
        
        # Test cache miss performance
        start_time = time.perf_counter()
        result = cache.get("nonexistent_key")
        miss_time = time.perf_counter() - start_time
        
        assert result is None
        assert miss_time < 0.001, f"Cache miss took {miss_time*1000:.2f}ms, too slow"
        
        # Test cache put performance
        test_data = {"domain": "audio", "priority": 90}
        start_time = time.perf_counter()
        cache.put("test_key", test_data)
        put_time = time.perf_counter() - start_time
        
        assert put_time < 0.001, f"Cache put took {put_time*1000:.2f}ms, too slow"
        
        # Test cache hit performance
        start_time = time.perf_counter()
        result = cache.get("test_key")
        hit_time = time.perf_counter() - start_time
        
        assert result == test_data
        assert hit_time < 0.0005, f"Cache hit took {hit_time*1000:.2f}ms, too slow"
        
        print(f"Cache performance - Miss: {miss_time*1000:.3f}ms, Put: {put_time*1000:.3f}ms, Hit: {hit_time*1000:.3f}ms")
    
    def test_cache_scalability(self, cache_config):
        """Test cache performance with many entries"""
        cache = TTLCache(max_size=1000, ttl_seconds=300)
        
        # Fill cache with many entries
        start_time = time.perf_counter()
        for i in range(500):
            cache.put(f"key_{i}", {"value": i, "data": f"test_data_{i}"})
        bulk_put_time = time.perf_counter() - start_time
        
        # Test retrieval performance with full cache
        start_time = time.perf_counter()
        for i in range(0, 500, 10):  # Sample every 10th entry
            result = cache.get(f"key_{i}")
            assert result is not None
        bulk_get_time = time.perf_counter() - start_time
        
        # Performance should still be good with many entries
        avg_put_time = (bulk_put_time / 500) * 1000
        avg_get_time = (bulk_get_time / 50) * 1000
        
        assert avg_put_time < 0.1, f"Average put time {avg_put_time:.3f}ms too slow with many entries"
        assert avg_get_time < 0.1, f"Average get time {avg_get_time:.3f}ms too slow with many entries"
        
        print(f"Cache scalability - Avg put: {avg_put_time:.3f}ms, Avg get: {avg_get_time:.3f}ms")
    
    def test_metrics_collector_integration_performance(self, cache_config):
        """Test that MetricsCollector integration maintains performance"""
        metrics_collector = get_metrics_collector()
        metrics_collector.set_contextual_command_config(cache_config)
        
        # Test contextual command metrics recording performance
        start_time = time.perf_counter()
        
        # Record multiple metrics to test performance
        for i in range(100):
            metrics_collector.record_contextual_disambiguation(
                command_type="stop",
                target_domain="audio",
                latency_ms=0.025,
                confidence=0.95,
                resolution_method="priority_based",
                cache_hit=(i % 2 == 0)  # Alternate cache hits
            )
        
        total_time = time.perf_counter() - start_time
        avg_time_per_record = (total_time / 100) * 1000  # Convert to ms
        
        assert avg_time_per_record < 0.1, f"Metrics recording took {avg_time_per_record:.3f}ms per record, too slow"
        
        # Verify metrics were recorded correctly
        contextual_metrics = metrics_collector.get_contextual_command_metrics()
        assert contextual_metrics["total_disambiguations"] >= 100
        assert contextual_metrics["cache_hit_rate"] == 0.5  # 50% cache hits
        
        print(f"MetricsCollector integration - Avg record time: {avg_time_per_record:.3f}ms")


class TestPhase4MemoryOptimization:
    """Test memory usage optimization"""
    
    def get_memory_usage(self):
        """Get current memory usage in MB (simplified version without psutil)"""
        # Simple memory tracking using gc
        import tracemalloc
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        current, peak = tracemalloc.get_traced_memory()
        return current / 1024 / 1024  # Convert to MB
    
    def test_cache_memory_efficiency(self):
        """Test that cache doesn't use excessive memory"""
        initial_memory = self.get_memory_usage()
        
        # Create cache with many entries
        cache = TTLCache(max_size=1000, ttl_seconds=300)
        
        # Add 1000 entries with moderate-sized data
        for i in range(1000):
            data = {
                "domain": f"domain_{i % 5}",
                "priority": i % 100,
                "patterns": [f"pattern_{j}" for j in range(10)],
                "metadata": {"created": time.time(), "index": i}
            }
            cache.put(f"key_{i}", data)
        
        after_cache_memory = self.get_memory_usage()
        memory_increase = after_cache_memory - initial_memory
        
        # Cache should not use excessive memory (allow up to 50MB for 1000 entries)
        assert memory_increase < 50, f"Cache used {memory_increase:.1f}MB, exceeds 50MB limit"
        
        # Test cache cleanup
        cache.clear()
        gc.collect()  # Force garbage collection
        
        after_clear_memory = self.get_memory_usage()
        memory_after_clear = after_clear_memory - initial_memory
        
        # Memory should be mostly freed (allow some overhead)
        assert memory_after_clear < memory_increase * 0.3, "Cache memory not properly freed"
        
        print(f"Memory usage - Cache: +{memory_increase:.1f}MB, After clear: +{memory_after_clear:.1f}MB")
    
    def test_performance_manager_memory_efficiency(self):
        """Test performance manager memory usage"""
        config = ContextualCommandsConfig(
            enable_pattern_caching=True,
            cache_ttl_seconds=300,
            max_cache_size_patterns=500,
            performance_monitoring=True
        )
        
        initial_memory = self.get_memory_usage()
        
        # Create performance manager and use it extensively
        perf_manager = ContextualCommandPerformanceManager(config)
        
        # Add many cached items
        for i in range(100):
            priorities = {f"domain_{j}": j * 10 for j in range(5)}
            patterns = [f"pattern_{j}_{i}" for j in range(20)]
            
            perf_manager.cache_domain_priorities(f"priorities_{i}", priorities)
            perf_manager.cache_command_patterns(f"patterns_{i}", patterns)
        
        # Record many performance measurements
        for i in range(1000):
            perf_manager.record_performance(
                latency_ms=float(i % 10),
                cache_hit=(i % 3 == 0)
            )
        
        after_usage_memory = self.get_memory_usage()
        memory_increase = after_usage_memory - initial_memory
        
        # Performance manager should be memory efficient (allow up to 20MB)
        assert memory_increase < 20, f"Performance manager used {memory_increase:.1f}MB, exceeds 20MB limit"
        
        print(f"Performance manager memory usage: +{memory_increase:.1f}MB")


class TestPhase4ConcurrencyPerformance:
    """Test performance under concurrent load"""
    
    @pytest.mark.asyncio
    async def test_concurrent_disambiguation_performance(self):
        """Test disambiguation performance under concurrent load"""
        config = ContextualCommandsConfig(
            enable_pattern_caching=True,
            performance_monitoring=True,
            latency_threshold_ms=10.0  # Relaxed for concurrent testing
        )
        
        initialize_performance_manager(config)
        context_manager = ContextManager()
        
        # Set up contexts for concurrent testing
        domain_priorities = {"audio": 90, "timer": 70, "system": 50}
        
        async def disambiguation_task(session_id: str, command_type: str):
            """Single disambiguation task"""
            context = await context_manager.get_context(session_id)
            context.active_actions = {
                "test_action": {
                    "domain": "audio",
                    "action": "play_music",
                    "started_at": time.time()
                }
            }
            
            start_time = time.perf_counter()
            resolution = context_manager.resolve_contextual_command_ambiguity(
                session_id=session_id,
                command_type=command_type,
                domain_priorities=domain_priorities
            )
            end_time = time.perf_counter()
            
            return (end_time - start_time) * 1000, resolution["target_domain"]
        
        # Run concurrent disambiguation tasks
        tasks = []
        for i in range(20):  # 20 concurrent tasks
            task = disambiguation_task(f"session_{i}", "stop")
            tasks.append(task)
        
        start_time = time.perf_counter()
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_time
        
        # Analyze results
        latencies = [result[0] for result in results]
        domains = [result[1] for result in results]
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        # Verify all tasks completed successfully
        assert all(domain == "audio" for domain in domains), "All tasks should resolve to audio domain"
        
        # Verify performance under concurrent load
        assert avg_latency < 15.0, f"Average concurrent latency {avg_latency:.2f}ms exceeds 15ms"
        assert max_latency < 25.0, f"Max concurrent latency {max_latency:.2f}ms exceeds 25ms"
        assert total_time < 2.0, f"Total concurrent execution time {total_time:.2f}s exceeds 2s"
        
        print(f"Concurrent performance - Avg: {avg_latency:.2f}ms, Max: {max_latency:.2f}ms, Total: {total_time:.2f}s")
    
    def test_cache_thread_safety(self):
        """Test cache thread safety under concurrent access"""
        cache = TTLCache(max_size=100, ttl_seconds=60)
        
        def cache_worker(worker_id: int, num_operations: int):
            """Worker function for concurrent cache operations"""
            for i in range(num_operations):
                key = f"worker_{worker_id}_key_{i}"
                value = {"worker": worker_id, "operation": i, "data": f"test_data_{i}"}
                
                # Put and get operations
                cache.put(key, value)
                result = cache.get(key)
                
                if result is not None:
                    assert result["worker"] == worker_id
                    assert result["operation"] == i
        
        # Run concurrent cache operations
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for worker_id in range(5):
                future = executor.submit(cache_worker, worker_id, 50)
                futures.append(future)
            
            # Wait for all workers to complete
            for future in futures:
                future.result()  # This will raise if any worker failed
        
        # Verify cache state is consistent
        stats = cache.get_stats()
        assert stats["size"] <= 100  # Should not exceed max size
        assert stats["hits"] > 0  # Should have some hits
        
        print(f"Cache thread safety test completed - Final size: {stats['size']}, Hits: {stats['hits']}")


async def run_phase4_performance_tests():
    """Run all Phase 4 performance tests"""
    print("🧪 Running Phase 4 Performance Tests...\n")
    
    # Run pytest programmatically
    import subprocess
    import sys
    
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "irene/tests/test_phase4_performance.py",
        "-v", "--tb=short", "-x"  # Stop on first failure
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    return result.returncode == 0


if __name__ == "__main__":
    asyncio.run(run_phase4_performance_tests())
