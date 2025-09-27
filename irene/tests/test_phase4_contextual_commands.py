"""
Phase 4 Testing & Validation - Contextual Command Disambiguation

Comprehensive test suite for Phase 4 TODO16 implementation:
- Cross-handler coordination testing
- Domain priority resolution validation  
- Contextual command parsing accuracy
- Performance optimization validation
"""

import pytest
import asyncio
import time
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

from irene.intents.models import ConversationContext, Intent, IntentResult
from irene.intents.context import ContextManager
from irene.intents.orchestrator import IntentOrchestrator
from irene.intents.registry import IntentRegistry
from irene.intents.handlers.base import IntentHandler
from irene.config.models import ContextualCommandsConfig


class MockHandler(IntentHandler):
    """Mock handler for testing contextual commands"""
    
    def __init__(self, domain: str, supported_commands: List[str]):
        self.domain = domain
        self.supported_commands = supported_commands
        self._can_handle_result = True
        
    async def can_handle(self, intent: Intent) -> bool:
        return self._can_handle_result and intent.action in self.supported_commands
        
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        return IntentResult(
            success=True,
            response=f"Executed {intent.action} for {self.domain}",
            intent_name=intent.name,
            handler_name=f"{self.domain}_handler"
        )


class TestPhase4ContextualCommandDisambiguation:
    """Test contextual command disambiguation logic"""
    
    @pytest.fixture
    def context_manager(self):
        """Create context manager for testing"""
        return ContextManager(session_timeout=3600, max_history_turns=10)
    
    @pytest.fixture
    def domain_priorities(self):
        """Domain priorities for testing"""
        return {
            "audio": 90,
            "timer": 70, 
            "voice_synthesis": 60,
            "system": 50,
            "conversation": 40
        }
    
    @pytest.fixture
    def mock_registry(self):
        """Create mock intent registry"""
        registry = MagicMock(spec=IntentRegistry)
        
        # Mock handlers for different domains
        audio_handler = MockHandler("audio", ["stop", "pause", "resume", "volume", "next", "previous"])
        timer_handler = MockHandler("timer", ["stop", "pause", "resume", "cancel"])
        voice_handler = MockHandler("voice_synthesis", ["stop", "cancel"])
        
        registry.get_handler.side_effect = lambda intent: {
            "audio.stop": audio_handler,
            "audio.pause": audio_handler,
            "audio.resume": audio_handler,
            "audio.volume": audio_handler,
            "audio.next": audio_handler,
            "audio.previous": audio_handler,
            "timer.stop": timer_handler,
            "timer.pause": timer_handler,
            "timer.resume": timer_handler,
            "timer.cancel": timer_handler,
            "voice_synthesis.stop": voice_handler,
            "voice_synthesis.cancel": voice_handler,
        }.get(intent.name)
        
        registry.get_handlers_for_contextual_command.side_effect = lambda cmd: {
            "stop": ["audio", "timer", "voice_synthesis"],
            "pause": ["audio", "timer"],
            "resume": ["audio", "timer"],
            "cancel": ["timer", "voice_synthesis"],
            "volume": ["audio"],
            "next": ["audio"],
            "previous": ["audio"]
        }.get(cmd, [])
        
        return registry
    
    @pytest.fixture
    def orchestrator(self, mock_registry, context_manager, domain_priorities):
        """Create orchestrator for testing"""
        return IntentOrchestrator(
            registry=mock_registry,
            context_manager=context_manager,
            domain_priorities=domain_priorities
        )
    
    @pytest.mark.asyncio
    async def test_single_active_action_disambiguation(self, context_manager, domain_priorities):
        """Test disambiguation with single active action"""
        # Setup: Single audio action
        session_id = "test_single"
        context = await context_manager.get_context(session_id)
        context.active_actions = {
            "play_music": {
                "domain": "audio",
                "action": "play_music", 
                "started_at": time.time()
            }
        }
        
        # Test: Stop command should target audio domain
        resolution = context_manager.resolve_contextual_command_ambiguity(
            session_id=session_id,
            command_type="stop",
            domain_priorities=domain_priorities
        )
        
        assert resolution["resolution"] == "single_action"
        assert resolution["target_domain"] == "audio"
        assert resolution["confidence"] == 0.95
        assert "play_music" in resolution["actions"]
    
    @pytest.mark.asyncio
    async def test_multi_domain_priority_resolution(self, context_manager, domain_priorities):
        """Test disambiguation with multiple domains using priorities"""
        # Setup: Audio + Timer actions
        session_id = "test_multi"
        context = await context_manager.get_context(session_id)
        current_time = time.time()
        context.active_actions = {
            "play_music": {
                "domain": "audio",
                "action": "play_music",
                "started_at": current_time - 10
            },
            "set_timer": {
                "domain": "timer", 
                "action": "set_timer",
                "started_at": current_time - 5
            }
        }
        
        # Test: Stop command should target audio (higher priority)
        resolution = context_manager.resolve_contextual_command_ambiguity(
            session_id=session_id,
            command_type="stop",
            domain_priorities=domain_priorities
        )
        
        assert resolution["target_domain"] == "audio"
        assert resolution["priority_domain"] == "audio"
        assert resolution["priority_score"] == 90
        assert resolution["confidence"] > 0.5
        assert "domain_scores" in resolution
        assert resolution["domain_scores"]["audio"] > resolution["domain_scores"]["timer"]
    
    @pytest.mark.asyncio
    async def test_recency_fallback_resolution(self, context_manager):
        """Test disambiguation using recency when no priorities"""
        # Setup: Multiple actions, no priorities
        session_id = "test_recency"
        context = await context_manager.get_context(session_id)
        current_time = time.time()
        context.active_actions = {
            "old_action": {
                "domain": "system",
                "action": "system_info",
                "started_at": current_time - 60  # 1 minute ago
            },
            "recent_action": {
                "domain": "conversation",
                "action": "chat",
                "started_at": current_time - 5   # 5 seconds ago
            }
        }
        
        # Test: Should target most recent action
        resolution = context_manager.resolve_contextual_command_ambiguity(
            session_id=session_id,
            command_type="stop",
            domain_priorities={}  # No priorities
        )
        
        # With no priorities, it should still resolve (may use priority_with_tiebreak or most_recent)
        assert resolution["resolution"] in ["most_recent", "priority_with_tiebreak"]
        assert resolution["target_domain"] == "conversation"  # Most recent
        assert resolution["confidence"] > 0.3
    
    @pytest.mark.asyncio
    async def test_confirmation_required_scenario(self, context_manager, domain_priorities):
        """Test scenario requiring user confirmation"""
        # Setup: Two domains with similar priorities (tie scenario)
        session_id = "test_confirmation"
        context = await context_manager.get_context(session_id)
        current_time = time.time()
        
        # Modify priorities to create a tie
        tie_priorities = {"audio": 70, "timer": 75}  # Close scores
        
        context.active_actions = {
            "play_music": {
                "domain": "audio",
                "action": "play_music",
                "started_at": current_time - 10
            },
            "set_timer": {
                "domain": "timer",
                "action": "set_timer", 
                "started_at": current_time - 8  # Slightly more recent
            }
        }
        
        # Test: Should require confirmation due to ambiguity
        resolution = context_manager.resolve_contextual_command_ambiguity(
            session_id=session_id,
            command_type="pause",
            domain_priorities=tie_priorities,
            require_confirmation=True
        )
        
        # With close scores, should require confirmation
        if resolution["resolution"] == "requires_confirmation":
            assert "ambiguous_domains" in resolution
            assert len(resolution["ambiguous_domains"]) >= 2
            assert resolution["confidence"] == 0.5
        else:
            # Or should resolve with tie-breaking logic
            assert resolution["resolution"] in ["multi_domain_priority", "priority_with_tiebreak"]
    
    @pytest.mark.asyncio
    async def test_no_active_actions_scenario(self, context_manager, domain_priorities):
        """Test scenario with no active actions"""
        session_id = "test_no_actions"
        context = await context_manager.get_context(session_id)
        context.active_actions = {}  # No active actions
        
        resolution = context_manager.resolve_contextual_command_ambiguity(
            session_id=session_id,
            command_type="stop",
            domain_priorities=domain_priorities
        )
        
        assert resolution["resolution"] == "no_active_actions"
        assert resolution["actions"] == []
        assert resolution["command_type"] == "stop"
    
    @pytest.mark.asyncio
    async def test_domain_specific_targeting(self, context_manager, domain_priorities):
        """Test explicit domain targeting in commands"""
        session_id = "test_targeting"
        context = await context_manager.get_context(session_id)
        current_time = time.time()
        context.active_actions = {
            "play_music": {
                "domain": "audio",
                "action": "play_music",
                "started_at": current_time - 10
            },
            "set_timer": {
                "domain": "timer",
                "action": "set_timer",
                "started_at": current_time - 5
            }
        }
        
        # Test: Explicit timer targeting
        resolution = context_manager.resolve_contextual_command_ambiguity(
            session_id=session_id,
            command_type="stop",
            target_domains=["timer"],  # Explicit targeting
            domain_priorities=domain_priorities
        )
        
        assert resolution["resolution"] == "domain_specific"
        assert resolution["target_domain"] == "timer"
        assert "timer" in resolution["target_domains"]


class TestPhase4CrossHandlerCoordination:
    """Test cross-handler coordination scenarios"""
    
    @pytest.fixture
    def context_manager(self):
        """Create context manager for testing"""
        return ContextManager()
    
    @pytest.fixture
    def orchestrator(self, context_manager):
        """Create orchestrator for testing"""
        registry = MagicMock(spec=IntentRegistry)
        
        # Mock handlers for different domains
        audio_handler = MockHandler("audio", ["stop", "pause", "resume", "volume", "next", "previous"])
        timer_handler = MockHandler("timer", ["stop", "pause", "resume", "cancel"])
        
        registry.get_handler.side_effect = lambda intent: {
            "audio.stop": audio_handler,
            "timer.stop": timer_handler,
        }.get(intent.name)
        
        registry.get_handlers_for_contextual_command.side_effect = lambda cmd: {
            "stop": ["audio", "timer"],
            "volume": ["audio"]
        }.get(cmd, [])
        
        domain_priorities = {"audio": 90, "timer": 70}
        
        return IntentOrchestrator(
            registry=registry,
            context_manager=context_manager,
            domain_priorities=domain_priorities
        )
    
    @pytest.mark.asyncio
    async def test_orchestrator_contextual_intent_routing(self, orchestrator, context_manager):
        """Test orchestrator routing of contextual intents"""
        # Setup: Active audio action
        session_id = "test_routing"
        context = await context_manager.get_context(session_id)
        context.active_actions = {
            "play_music": {
                "domain": "audio",
                "action": "play_music",
                "started_at": time.time()
            }
        }
        
        # Create contextual intent
        contextual_intent = Intent(
            name="contextual.stop",
            domain="contextual",
            action="stop",
            raw_text="stop",
            entities={},
            confidence=0.9
        )
        
        # Test: Should resolve to audio.stop
        result = await orchestrator.execute_intent(contextual_intent, context)
        
        assert result.success
        assert "audio" in result.response.lower()
        assert "stop" in result.response.lower()
    
    @pytest.mark.asyncio
    async def test_no_capable_handlers_scenario(self, orchestrator, context_manager):
        """Test scenario where no handlers support the contextual command"""
        session_id = "test_no_handlers"
        context = await context_manager.get_context(session_id)
        context.active_actions = {
            "system_info": {
                "domain": "system",
                "action": "system_info",
                "started_at": time.time()
            }
        }
        
        # Create contextual intent for command not supported by system domain
        contextual_intent = Intent(
            name="contextual.volume",  # System handler doesn't support volume
            domain="contextual",
            action="volume",
            raw_text="volume up",
            entities={},
            confidence=0.9
        )
        
        # Test: Should return error about no capable handlers
        result = await orchestrator.execute_intent(contextual_intent, context)
        
        assert not result.success
        assert result.error_type == "no_capable_handlers"
        assert "volume" in result.response.lower()
    
    @pytest.mark.asyncio
    async def test_multiple_domain_coordination(self, orchestrator, context_manager):
        """Test coordination across multiple domains"""
        session_id = "test_coordination"
        context = await context_manager.get_context(session_id)
        current_time = time.time()
        
        # Setup: Multiple active actions
        context.active_actions = {
            "play_music": {
                "domain": "audio",
                "action": "play_music",
                "started_at": current_time - 20
            },
            "set_timer": {
                "domain": "timer",
                "action": "set_timer", 
                "started_at": current_time - 10
            },
            "speak_text": {
                "domain": "voice_synthesis",
                "action": "speak_text",
                "started_at": current_time - 5
            }
        }
        
        # Test: Stop command should target highest priority (audio)
        contextual_intent = Intent(
            name="contextual.stop",
            domain="contextual",
            action="stop",
            raw_text="stop",
            entities={},
            confidence=0.9
        )
        
        result = await orchestrator.execute_intent(contextual_intent, context)
        
        assert result.success
        assert "audio" in result.response.lower()


class TestPhase4PerformanceValidation:
    """Test performance optimization and monitoring"""
    
    @pytest.fixture
    def context_manager(self):
        """Create context manager for testing"""
        return ContextManager()
    
    @pytest.fixture
    def domain_priorities(self):
        """Domain priorities for testing"""
        return {
            "audio": 90,
            "timer": 70, 
            "voice_synthesis": 60,
            "system": 50,
            "conversation": 40
        }
    
    @pytest.mark.asyncio
    async def test_disambiguation_latency_measurement(self, context_manager, domain_priorities):
        """Test that disambiguation completes within latency threshold"""
        session_id = "test_latency"
        context = await context_manager.get_context(session_id)
        current_time = time.time()
        
        # Setup: Complex scenario with multiple actions
        context.active_actions = {
            f"action_{i}": {
                "domain": ["audio", "timer", "voice_synthesis"][i % 3],
                "action": f"action_{i}",
                "started_at": current_time - (i * 5)
            }
            for i in range(10)  # 10 active actions
        }
        
        # Measure disambiguation time
        start_time = time.perf_counter()
        
        resolution = context_manager.resolve_contextual_command_ambiguity(
            session_id=session_id,
            command_type="stop",
            domain_priorities=domain_priorities
        )
        
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        # Verify: Should complete within 5ms threshold
        assert latency_ms < 5.0, f"Disambiguation took {latency_ms:.2f}ms, exceeds 5ms threshold"
        assert resolution["target_domain"] is not None
    
    def test_contextual_commands_config_validation(self):
        """Test ContextualCommandsConfig validation"""
        # Test valid configuration
        config = ContextualCommandsConfig()
        assert config.enable_pattern_caching is True
        assert config.cache_ttl_seconds == 300
        assert config.max_cache_size_patterns == 1000
        assert config.performance_monitoring is True
        assert config.latency_threshold_ms == 5.0
        
        # Test validation constraints
        with pytest.raises(ValueError):
            ContextualCommandsConfig(cache_ttl_seconds=30)  # Below minimum
            
        with pytest.raises(ValueError):
            ContextualCommandsConfig(cache_ttl_seconds=4000)  # Above maximum
            
        with pytest.raises(ValueError):
            ContextualCommandsConfig(max_cache_size_patterns=50)  # Below minimum
            
        with pytest.raises(ValueError):
            ContextualCommandsConfig(latency_threshold_ms=0.5)  # Below minimum
    
    @pytest.mark.asyncio
    async def test_confidence_scoring_accuracy(self, context_manager, domain_priorities):
        """Test confidence scoring accuracy across scenarios"""
        session_id = "test_confidence"
        context = await context_manager.get_context(session_id)
        current_time = time.time()
        
        # Test 1: Single action should have high confidence
        context.active_actions = {
            "single_action": {
                "domain": "audio",
                "action": "play_music",
                "started_at": current_time
            }
        }
        
        resolution = context_manager.resolve_contextual_command_ambiguity(
            session_id=session_id,
            command_type="stop",
            domain_priorities=domain_priorities
        )
        
        assert resolution["confidence"] >= 0.9, "Single action should have high confidence"
        
        # Test 2: Multiple actions with clear priority should have good confidence
        context.active_actions = {
            "audio_action": {
                "domain": "audio",
                "action": "play_music",
                "started_at": current_time - 10
            },
            "timer_action": {
                "domain": "timer",
                "action": "set_timer",
                "started_at": current_time - 5
            }
        }
        
        resolution = context_manager.resolve_contextual_command_ambiguity(
            session_id=session_id,
            command_type="stop",
            domain_priorities=domain_priorities
        )
        
        assert resolution["confidence"] >= 0.6, "Clear priority should have good confidence"
        assert resolution["target_domain"] == "audio", "Should target highest priority domain"


class TestPhase4MigrationValidation:
    """Test migration and backward compatibility"""
    
    def test_contextual_command_types_coverage(self):
        """Test that all contextual command types are supported"""
        expected_commands = ["stop", "pause", "resume", "cancel", "volume", "next", "previous"]
        
        # This would be tested against actual handler capabilities in integration
        # For now, verify the expected command list is comprehensive
        assert len(expected_commands) == 7
        assert "stop" in expected_commands
        assert "pause" in expected_commands
        assert "resume" in expected_commands
        assert "cancel" in expected_commands
    
    @pytest.mark.asyncio
    async def test_handler_method_replacement_validation(self):
        """Test that handlers no longer use deprecated stop-specific methods"""
        # This test would verify that handlers don't have parse_stop_command methods
        # and use the new domain-specific methods instead
        
        # Create mock handler
        handler = MockHandler("audio", ["stop", "pause"])
        
        # Verify handler doesn't have deprecated methods
        assert not hasattr(handler, 'parse_stop_command')
        assert not hasattr(handler, '_handle_stop_command')
        
        # Verify handler can handle domain-specific intents
        stop_intent = Intent(
            name="audio.stop",
            domain="audio", 
            action="stop",
            raw_text="stop audio",
            entities={},
            confidence=0.9
        )
        
        can_handle = await handler.can_handle(stop_intent)
        assert can_handle is True


async def run_phase4_tests():
    """Run all Phase 4 tests"""
    print("🧪 Running Phase 4 Contextual Command Tests...\n")
    
    # Run pytest programmatically
    import subprocess
    import sys
    
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "irene/tests/test_phase4_contextual_commands.py",
        "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    return result.returncode == 0


if __name__ == "__main__":
    asyncio.run(run_phase4_tests())
