"""
Phase 6 Integration Tests - End-to-End NLU-Integrated Parameter Extraction

Tests the complete Phase 6 implementation after migration:
- NLU providers with integrated parameter extraction
- Intent orchestrator without separate parameter extraction
- Complete flow from NLU recognition → Intent execution → Handler response
- IntentHandlerManager without parameter extractor dependency
- IntentComponent integration with new architecture

This validates the final achievement: unified parameter extraction architecture
where NLU providers handle both recognition and parameter extraction.
"""

import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import time

# Import system components
from irene.intents.manager import IntentHandlerManager
from irene.intents.orchestrator import IntentOrchestrator
from irene.intents.models import Intent, UnifiedConversationContext, IntentResult
from irene.components.intent_component import IntentComponent
from irene.providers.nlu.hybrid_keyword_matcher import HybridKeywordMatcherProvider
from irene.core.donations import KeywordDonation, ParameterSpec, ParameterType

logger = logging.getLogger(__name__)


class MockTimerHandler:
    """Mock timer handler for testing intent execution."""
    
    def __init__(self):
        self.name = "MockTimerHandler"
    
    async def can_handle(self, intent):
        """Check if this handler can handle the given intent."""
        return intent.name.startswith('timer.')
    
    async def execute(self, intent, context):
        """Execute the timer intent with extracted parameters."""
        duration = intent.entities.get('duration', 'unknown')
        name = intent.entities.get('name', 'unnamed timer')
        
        response = f"Timer set for {duration} minutes with name '{name}'"
        
        return IntentResult(
            text=response,
            should_speak=True,
            success=True
        )


@pytest.fixture
async def intent_manager():
    """Create IntentHandlerManager for testing."""
    manager = IntentHandlerManager()
    
    # Mock the donation loading to avoid file dependencies
    manager._donations = {
        "timer": KeywordDonation(
            intent="timer.set",
            phrases=["установи таймер", "set timer"],
            handler_domain="timer",
            parameters=[
                ParameterSpec(
                    name="duration",
                    type=ParameterType.INTEGER,
                    required=True
                ),
                ParameterSpec(
                    name="name",
                    type=ParameterType.STRING,
                    required=False,
                    default_value="unnamed timer"
                )
            ],
            token_patterns=[],
            slot_patterns={},
            examples=[]
        )
    }
    
    # Mock handler registration
    manager._handler_instances = {"timer_handler": MockTimerHandler()}
    manager._registry.register_handler("timer.set", manager._handler_instances["timer_handler"])
    manager._initialized = True
    
    return manager


@pytest.fixture
async def orchestrator(intent_manager):
    """Create IntentOrchestrator for testing (new architecture without parameter extractor)."""
    registry = intent_manager.get_registry()
    # PHASE 6: Create orchestrator without parameter extractor
    orchestrator = IntentOrchestrator(registry)
    return orchestrator


@pytest.fixture
async def hybrid_provider():
    """Create hybrid NLU provider with parameter extraction capabilities."""
    donations = [
        KeywordDonation(
            intent="timer.set",
            phrases=["установи таймер", "set timer"],
            handler_domain="timer",
            parameters=[
                ParameterSpec(
                    name="duration",
                    type=ParameterType.INTEGER,
                    required=True
                ),
                ParameterSpec(
                    name="name",
                    type=ParameterType.STRING,
                    required=False,
                    default_value="unnamed timer"
                )
            ],
            token_patterns=[],
            slot_patterns={},
            examples=[]
        )
    ]
    
    provider = HybridKeywordMatcherProvider({
        'confidence_threshold': 0.7,
        'fuzzy_enabled': False  # Disable for predictable testing
    })
    
    await provider._initialize_from_donations(donations)
    return provider


class TestPhase6Integration:
    """Test the complete Phase 6 architecture integration."""
    
    async def test_orchestrator_without_parameter_extractor(self, intent_manager):
        """Test that orchestrator works without parameter extractor."""
        registry = intent_manager.get_registry()
        
        # PHASE 6: Test new constructor signature (no parameter extractor)
        orchestrator = IntentOrchestrator(registry)
        
        # Verify orchestrator is functional
        assert orchestrator.registry is not None
        
        # Test capabilities reflect new architecture
        capabilities = await orchestrator.get_capabilities()
        assert "parameter_extraction_integrated" in capabilities
        assert capabilities["parameter_extraction_integrated"] is True
    
    async def test_nlu_integrated_parameter_extraction(self, hybrid_provider):
        """Test that NLU provider extracts parameters during recognition."""
        context = ConversationContext(session_id="test")
        
        # Test parameter extraction integrated into recognition
        intent = await hybrid_provider.recognize_with_parameters(
            "установи таймер на 15 минут", 
            context
        )
        
        assert intent is not None
        assert intent.name == "timer.set"
        assert "duration" in intent.entities
        assert intent.entities["duration"] == 15
        
    async def test_end_to_end_flow_without_parameter_extractor(self, hybrid_provider, orchestrator):
        """Test complete flow: NLU recognition → Intent execution → Handler response."""
        context = ConversationContext(session_id="test")
        
        # Step 1: NLU recognition with integrated parameter extraction
        intent = await hybrid_provider.recognize_with_parameters(
            "установи таймер на 30 минут", 
            context
        )
        
        assert intent is not None
        assert intent.name == "timer.set"
        assert intent.entities.get("duration") == 30
        
        # Step 2: Intent execution (no separate parameter extraction)
        result = await orchestrator.execute_intent(intent, context)
        
        assert result.success is True
        assert "Timer set for 30 minutes" in result.text
        assert result.should_speak is True
    
    async def test_intent_component_capabilities(self):
        """Test that IntentComponent reports correct capabilities for new architecture."""
        component = IntentComponent()
        
        # Mock the internal dependencies
        component._manager = MagicMock()
        component._manager.get_orchestrator.return_value = MagicMock()
        component._manager.get_orchestrator.return_value.get_capabilities.return_value = {
            "parameter_extraction_integrated": True,
            "donation_routing_enabled": True
        }
        component._manager.get_donations.return_value = {"timer": {}}
        component._manager.get_registry.return_value.get_handlers.return_value = {"timer.set": MockTimerHandler()}
        
        # Test capabilities
        status = await component.get_system_status()
        
        assert "parameter_extraction_integrated" in status
        assert status["parameter_extraction_integrated"] is True
    
    async def test_graceful_degradation_no_parameters(self, orchestrator):
        """Test that system works when intent has no parameters."""
        context = ConversationContext(session_id="test")
        
        # Create intent without parameters
        intent = Intent(
            name="timer.set",
            entities={},  # No parameters
            confidence=0.9,
            raw_text="установи таймер",
            timestamp=time.time()
        )
        
        # Should still execute successfully
        result = await orchestrator.execute_intent(intent, context)
        
        assert result.success is True
        assert "Timer set for unknown minutes" in result.text
    
    async def test_provider_parameter_storage(self, hybrid_provider):
        """Test that providers store parameter specifications correctly."""
        # Verify parameter specs are stored
        assert "timer.set" in hybrid_provider.parameter_specs
        specs = hybrid_provider.parameter_specs["timer.set"]
        
        assert len(specs) == 2  # duration and name
        duration_spec = next(spec for spec in specs if spec.name == "duration")
        name_spec = next(spec for spec in specs if spec.name == "name")
        
        assert duration_spec.type == ParameterType.INTEGER
        assert duration_spec.required is True
        assert name_spec.type == ParameterType.STRING
        assert name_spec.required is False
        assert name_spec.default_value == "unnamed timer"


@pytest.mark.asyncio
async def test_phase6_comprehensive_integration():
    """Comprehensive test of the complete Phase 6 architecture."""
    print("=== Phase 6 Comprehensive Integration Test ===")
    
    # Test all components work together in new architecture
    manager = IntentHandlerManager()
    
    # Setup mock data
    manager._donations = {
        "timer": KeywordDonation(
            intent="timer.set",
            phrases=["установи таймер"],
            handler_domain="timer",
            parameters=[
                ParameterSpec(
                    name="duration",
                    type=ParameterType.INTEGER,
                    required=True
                )
            ],
            token_patterns=[],
            slot_patterns={},
            examples=[]
        )
    }
    
    handler = MockTimerHandler()
    manager._handler_instances = {"timer_handler": handler}
    manager._registry.register_handler("timer.set", handler)
    manager._initialized = True
    
    # PHASE 6: Create orchestrator without parameter extractor
    orchestrator = IntentOrchestrator(manager.get_registry())
    
    # Create NLU provider with integrated parameter extraction
    provider = HybridKeywordMatcherProvider({'confidence_threshold': 0.7, 'fuzzy_enabled': False})
    await provider._initialize_from_donations(list(manager._donations.values()))
    
    # Test complete flow
    context = ConversationContext(session_id="test")
    
    # NLU recognition with parameter extraction
    intent = await provider.recognize_with_parameters("установи таймер на 45 минут", context)
    
    # Intent execution without separate parameter extraction
    result = await orchestrator.execute_intent(intent, context)
    
    # Verify success
    assert intent.name == "timer.set"
    assert intent.entities["duration"] == 45
    assert result.success is True
    assert "Timer set for 45 minutes" in result.text
    
    print("✅ Phase 6 architecture validation successful!")
    print("   - NLU providers handle integrated parameter extraction")
    print("   - Orchestrator works without parameter extractor")
    print("   - End-to-end flow works correctly")
    print("   - Parameters flow from NLU → Intent → Handler")


if __name__ == "__main__":
    asyncio.run(test_phase6_comprehensive_integration())