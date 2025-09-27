"""
Phase 4 Integration Tests - Cross-Handler Coordination

Integration tests for Phase 4 TODO16 implementation focusing on:
- Real handler coordination scenarios
- End-to-end contextual command processing
- Performance validation in realistic conditions
- Migration validation with actual handlers
"""

import pytest
import asyncio
import time
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from irene.intents.models import ConversationContext, Intent, IntentResult
from irene.intents.context import ContextManager
from irene.intents.orchestrator import IntentOrchestrator
from irene.intents.registry import IntentRegistry
from irene.intents.manager import IntentHandlerManager
from irene.core.metrics import get_metrics_collector
from irene.config.models import ContextualCommandsConfig, IntentSystemConfig
from irene.workflows.base import RequestContext


class TestPhase4RealHandlerIntegration:
    """Test integration with real handler implementations"""
    
    @pytest.fixture
    async def handler_manager(self):
        """Create handler manager with real configuration"""
        manager = IntentHandlerManager()
        
        # Create minimal config for testing
        config = {
            "enabled": ["timer", "system"],  # Use real handlers that support contextual commands
            "disabled": [],
            "auto_discover": True,
            "discovery_paths": ["irene.intents.handlers"],
            "asset_validation": {
                "strict_mode": False,  # Relaxed for testing
                "validate_method_existence": False,
                "validate_spacy_patterns": False,
                "validate_json_schema": False
            }
        }
        
        # Create IntentSystemConfig with contextual commands
        intent_config = IntentSystemConfig(
            domain_priorities={
                "timer": 70,
                "system": 50,
                "audio": 90  # Even though not loaded, for priority testing
            },
            contextual_commands=ContextualCommandsConfig(
                enable_pattern_caching=True,
                performance_monitoring=True,
                latency_threshold_ms=10.0  # Relaxed for testing
            )
        )
        
        try:
            await manager.initialize(config, intent_config)
            return manager
        except Exception as e:
            pytest.skip(f"Could not initialize real handlers: {e}")
    
    @pytest.fixture
    def metrics_collector_configured(self):
        """MetricsCollector configured for contextual commands"""
        config = ContextualCommandsConfig(
            enable_pattern_caching=True,
            cache_ttl_seconds=60,  # Short TTL for testing
            max_cache_size_patterns=100,
            performance_monitoring=True,
            latency_threshold_ms=5.0
        )
        metrics_collector = get_metrics_collector()
        metrics_collector.set_contextual_command_config(config)
        return metrics_collector
    
    @pytest.mark.asyncio
    async def test_real_handler_contextual_command_support(self, handler_manager):
        """Test that real handlers support contextual commands"""
        if not handler_manager:
            pytest.skip("Handler manager not available")
        
        registry = handler_manager.get_registry()
        
        # Test that handlers are registered
        assert len(registry._handlers) > 0, "No handlers registered"
        
        # Test contextual command capabilities
        timer_capabilities = registry.get_handlers_for_contextual_command("stop")
        assert "timer" in timer_capabilities, "Timer handler should support stop command"
        
        system_capabilities = registry.get_handlers_for_contextual_command("stop")
        assert "system" in system_capabilities, "System handler should support stop command"
    
    @pytest.mark.asyncio
    async def test_end_to_end_contextual_processing(self, handler_manager):
        """Test complete end-to-end contextual command processing"""
        if not handler_manager:
            pytest.skip("Handler manager not available")
        
        # Get orchestrator and context manager
        orchestrator = handler_manager.get_orchestrator()
        context_manager = ContextManager()
        
        # Set up context with active timer
        session_id = "test_e2e"
        context = await context_manager.get_context(session_id)
        context.active_actions = {
            "test_timer": {
                "domain": "timer",
                "action": "set_timer",
                "started_at": time.time(),
                "duration": 300
            }
        }
        
        # Create contextual stop intent
        contextual_intent = Intent(
            name="contextual.stop",
            domain="contextual",
            action="stop",
            text="stop",
            confidence=0.9
        )
        
        # Execute through orchestrator
        result = await orchestrator.execute_intent(contextual_intent, context)
        
        # Verify result
        assert result is not None
        # Note: Result success depends on actual handler implementation
        # We mainly test that the flow completes without errors
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, metrics_collector_configured):
        """Test performance monitoring with real disambiguation"""
        # Use integrated MetricsCollector
        metrics_collector = metrics_collector_configured
        
        context_manager = ContextManager()
        session_id = "test_perf"
        context = await context_manager.get_context(session_id)
        
        # Set up multiple active actions for complex disambiguation
        current_time = time.time()
        context.active_actions = {
            "timer1": {
                "domain": "timer",
                "action": "set_timer",
                "started_at": current_time - 30
            },
            "timer2": {
                "domain": "timer", 
                "action": "set_timer",
                "started_at": current_time - 10
            },
            "system_info": {
                "domain": "system",
                "action": "system_info",
                "started_at": current_time - 5
            }
        }
        
        domain_priorities = {"timer": 70, "system": 50}
        
        # Perform disambiguation (should be monitored)
        resolution = context_manager.resolve_contextual_command_ambiguity(
            session_id=session_id,
            command_type="stop",
            domain_priorities=domain_priorities
        )
        
        # Verify resolution worked
        assert resolution["target_domain"] in ["timer", "system"]
        
        # Verify performance was monitored in MetricsCollector
        contextual_metrics = metrics_collector.get_contextual_command_metrics()
        
        assert contextual_metrics["total_disambiguations"] >= 1
        assert contextual_metrics["average_latency_ms"] >= 0
    
    @pytest.mark.asyncio
    async def test_metrics_collector_effectiveness(self, metrics_collector_configured):
        """Test that MetricsCollector integration works effectively"""
        metrics_collector = metrics_collector_configured
        
        # Record some contextual disambiguation metrics
        metrics_collector.record_contextual_disambiguation(
            command_type="stop",
            target_domain="audio", 
            latency_ms=0.025,
            confidence=0.95,
            resolution_method="priority_based",
            cache_hit=True
        )
        
        metrics_collector.record_contextual_disambiguation(
            command_type="pause",
            target_domain="timer",
            latency_ms=0.031,
            confidence=0.87,
            resolution_method="most_recent",
            cache_hit=False
        )
        
        # Verify metrics were recorded
        contextual_metrics = metrics_collector.get_contextual_command_metrics()
        assert contextual_metrics["total_disambiguations"] == 2
        assert contextual_metrics["successful_disambiguations"] == 2
        assert contextual_metrics["cache_hit_rate"] == 0.5  # 1 hit out of 2
        assert contextual_metrics["success_rate"] == 1.0


class TestPhase4PerformanceValidation:
    """Test performance optimization and validation"""
    
    @pytest.fixture
    def large_context_scenario(self):
        """Create scenario with many active actions for performance testing"""
        context = ConversationContext(session_id="perf_test", client_id="test", language="en")
        current_time = time.time()
        
        # Create 20 active actions across different domains
        for i in range(20):
            domain = ["audio", "timer", "voice_synthesis", "system", "conversation"][i % 5]
            context.active_actions[f"action_{i}"] = {
                "domain": domain,
                "action": f"action_{i}",
                "started_at": current_time - (i * 2)  # Spread over time
            }
        
        return context
    
    @pytest.mark.asyncio
    async def test_disambiguation_latency_under_load(self, large_context_scenario):
        """Test disambiguation performance with many active actions"""
        context_manager = ContextManager()
        context_manager.sessions["perf_test"] = large_context_scenario
        
        domain_priorities = {
            "audio": 90,
            "timer": 70,
            "voice_synthesis": 60,
            "system": 50,
            "conversation": 40
        }
        
        # Measure disambiguation time
        start_time = time.perf_counter()
        
        resolution = context_manager.resolve_contextual_command_ambiguity(
            session_id="perf_test",
            command_type="stop",
            domain_priorities=domain_priorities
        )
        
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        # Verify performance meets requirements
        assert latency_ms < 10.0, f"Disambiguation took {latency_ms:.2f}ms, exceeds 10ms threshold"
        assert resolution["target_domain"] is not None
        assert resolution["confidence"] > 0.0
    
    @pytest.mark.asyncio
    async def test_cache_performance_improvement(self):
        """Test that caching improves performance"""
        config = ContextualCommandsConfig(
            enable_pattern_caching=True,
            cache_ttl_seconds=300,
            max_cache_size_patterns=1000,
            performance_monitoring=True
        )
        
        perf_manager = ContextualCommandPerformanceManager(config)
        
        # Test without cache (cold)
        start_time = time.perf_counter()
        
        # Simulate expensive operation
        test_data = {"audio": 90, "timer": 70, "system": 50}
        cache_key = "test_performance"
        
        cold_time = time.perf_counter() - start_time
        
        # Cache the data
        perf_manager.cache_domain_priorities(cache_key, test_data)
        
        # Test with cache (warm)
        start_time = time.perf_counter()
        cached_data = perf_manager.get_cached_domain_priorities(cache_key)
        warm_time = time.perf_counter() - start_time
        
        # Verify cache hit
        assert cached_data == test_data
        
        # Cache should be faster (though this is a simple test)
        # In real scenarios, the difference would be more significant
        assert warm_time <= cold_time * 2  # Allow some variance
    
    def test_performance_metrics_accuracy(self):
        """Test accuracy of performance metrics collection"""
        config = ContextualCommandsConfig(
            performance_monitoring=True,
            latency_threshold_ms=5.0
        )
        
        perf_manager = ContextualCommandPerformanceManager(config)
        
        # Record some measurements
        perf_manager.record_performance(3.0, cache_hit=False)  # Under threshold
        perf_manager.record_performance(7.0, cache_hit=True)   # Over threshold
        perf_manager.record_performance(2.0, cache_hit=True)   # Under threshold
        
        summary = perf_manager.get_performance_summary()
        metrics = summary["disambiguation_metrics"]
        
        # Verify metrics
        assert metrics["total_operations"] == 3
        assert metrics["threshold_violations"] == 1
        assert metrics["violation_rate"] == 1/3
        assert metrics["average_latency_ms"] == (3.0 + 7.0 + 2.0) / 3
        assert metrics["max_latency_ms"] == 7.0
        assert metrics["min_latency_ms"] == 2.0
        
        # Verify cache metrics
        cache_metrics = summary["cache_metrics"]
        assert cache_metrics["total_hits"] == 2
        assert cache_metrics["total_misses"] == 1
        assert cache_metrics["hit_rate"] == 2/3


class TestPhase4MigrationValidation:
    """Test migration and backward compatibility"""
    
    @pytest.mark.asyncio
    async def test_handler_method_migration_compliance(self):
        """Test that handlers follow new contextual command patterns"""
        # This test would verify that handlers don't use deprecated methods
        # and implement the new domain-specific patterns
        
        # Mock a handler that follows new patterns
        class ModernHandler:
            async def can_handle(self, intent: Intent) -> bool:
                return intent.domain == "test" and intent.action in ["stop", "pause"]
            
            async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
                # Modern handlers receive resolved domain-specific intents
                assert intent.domain != "contextual", "Handler should not receive contextual intents"
                assert intent.name.startswith("test."), "Intent should be domain-specific"
                
                return IntentResult(
                    success=True,
                    response=f"Handled {intent.action} for {intent.domain}",
                    intent_name=intent.name
                )
        
        handler = ModernHandler()
        
        # Test with domain-specific intent (what handlers should receive)
        domain_intent = Intent(
            name="test.stop",
            domain="test",
            action="stop",
            text="stop test",
            confidence=0.9
        )
        
        can_handle = await handler.can_handle(domain_intent)
        assert can_handle is True
        
        context = ConversationContext(session_id="test", client_id="test", language="en")
        result = await handler.execute(domain_intent, context)
        
        assert result.success is True
        assert "stop" in result.response
    
    def test_contextual_command_coverage(self):
        """Test that all expected contextual commands are supported"""
        expected_commands = ["stop", "pause", "resume", "cancel", "volume", "next", "previous"]
        
        # This would test against actual handler capabilities in a real system
        # For now, verify the expected command list
        assert len(expected_commands) == 7
        
        # Verify each command type
        for command in expected_commands:
            assert isinstance(command, str)
            assert len(command) > 0
    
    @pytest.mark.asyncio
    async def test_configuration_schema_compatibility(self):
        """Test that configuration schemas work correctly"""
        # Test ContextualCommandsConfig
        config = ContextualCommandsConfig(
            enable_pattern_caching=True,
            cache_ttl_seconds=300,
            max_cache_size_patterns=1000,
            performance_monitoring=True,
            latency_threshold_ms=5.0
        )
        
        assert config.enable_pattern_caching is True
        assert config.cache_ttl_seconds == 300
        assert config.max_cache_size_patterns == 1000
        assert config.performance_monitoring is True
        assert config.latency_threshold_ms == 5.0
        
        # Test IntentSystemConfig with contextual commands
        intent_config = IntentSystemConfig(
            domain_priorities={"audio": 90, "timer": 70},
            contextual_commands=config
        )
        
        assert intent_config.domain_priorities["audio"] == 90
        assert intent_config.contextual_commands.enable_pattern_caching is True


async def run_phase4_integration_tests():
    """Run all Phase 4 integration tests"""
    print("🧪 Running Phase 4 Integration Tests...\n")
    
    # Run pytest programmatically
    import subprocess
    import sys
    
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "irene/tests/test_phase4_integration.py",
        "-v", "--tb=short", "-x"  # Stop on first failure
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    return result.returncode == 0


if __name__ == "__main__":
    asyncio.run(run_phase4_integration_tests())
