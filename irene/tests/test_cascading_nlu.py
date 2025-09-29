"""
Test Cascading NLU Provider Coordination

Test suite for validating the cascading NLU provider coordination 
functionality implemented in Phase 2.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from irene.intents.models import UnifiedConversationContext, Intent
from irene.components.nlu_component import NLUComponent
from irene.providers.nlu.base import NLUProvider
from irene.core.donations import ParameterSpec


class MockNLUProvider(NLUProvider):
    """Mock NLU provider for testing cascading behavior"""
    
    def __init__(self, name: str, success_rate: float = 1.0, confidence: float = 0.8, 
                 should_fail: bool = False):
        # Initialize with empty config for base class
        super().__init__({})
        self.name = name
        self.success_rate = success_rate
        self.confidence = confidence
        self.should_fail = should_fail
        self.call_count = 0
    
    async def recognize(self, text: str, context: UnifiedConversationContext) -> Intent:
        """Mock recognition with configurable behavior"""
        self.call_count += 1
        
        if self.should_fail:
            raise Exception(f"Mock provider {self.name} failed")
        
        # Simulate success/failure based on success rate
        import random
        if random.random() > self.success_rate:
            # Return low confidence intent
            confidence = 0.3
        else:
            confidence = self.confidence
        
        return Intent(
            name=f"test.intent",
            entities={"provider": self.name, "call_count": self.call_count},
            confidence=confidence,
            raw_text=text,
            session_id=context.session_id
        )
    
    async def is_available(self) -> bool:
        return True
    
    async def extract_entities(self, text: str, intent_name: str) -> Dict[str, Any]:
        """Mock entity extraction"""
        return {"mock_entity": "mock_value"}
    
    async def extract_parameters(self, text: str, intent_name: str, parameter_specs: List[ParameterSpec]) -> Dict[str, Any]:
        """Mock parameter extraction for testing"""
        # Return simple mock parameters based on specs
        extracted = {}
        for spec in parameter_specs:
            if spec.required or spec.default_value is not None:
                extracted[spec.name] = spec.default_value or f"mock_{spec.name}"
        return extracted
    
    async def recognize_with_parameters(self, text: str, context: UnifiedConversationContext) -> Intent:
        """Override to ensure mock entities are preserved in integrated recognition"""
        # Call the regular recognize method to get base intent
        intent = await self.recognize(text, context)
        
        # Since we don't have stored parameter specs in the mock, just return the original intent
        # This ensures that mock entities like 'provider' and 'call_count' are preserved
        return intent
    
    def get_supported_intents(self) -> List[str]:
        """Mock supported intents"""
        return ["test.intent"]
    
    def get_provider_name(self) -> str:
        """Return provider name"""
        return self.name


class TestCascadingNLU:
    """Test suite for cascading NLU provider coordination"""
    
    @pytest.fixture
    def mock_core_config(self):
        """Create mock core configuration"""
        mock_config = MagicMock()
        mock_config.components.nlu = {
            "enabled": True,
            "confidence_threshold": 0.7,
            "provider_cascade_order": ["fast_provider", "medium_provider", "slow_provider"],
            "fallback_intent": "conversation.general",
            "max_cascade_attempts": 4,
            "cascade_timeout_ms": 200,
            "cache_recognition_results": True,
            "cache_ttl_seconds": 300,
            "providers": {
                "fast_provider": {
                    "enabled": True,
                    "confidence_threshold": 0.8
                },
                "medium_provider": {
                    "enabled": True, 
                    "confidence_threshold": 0.7
                },
                "slow_provider": {
                    "enabled": True,
                    "confidence_threshold": 0.6
                },

            }
        }
        return mock_config
    
    @pytest.fixture
    def nlu_component(self, mock_core_config):
        """Create NLU component with mock providers"""
        component = NLUComponent()
        component.core = MagicMock()
        component.core.config = mock_core_config
        
        # Set up configuration manually since we're not calling initialize()
        config = mock_core_config.components.nlu
        component.confidence_threshold = config.get("confidence_threshold", 0.7)
        component.fallback_intent = config.get("fallback_intent", "conversation.general")
        component.provider_cascade_order = config.get("provider_cascade_order", [])
        component.max_cascade_attempts = config.get("max_cascade_attempts", 4)
        component.cascade_timeout_ms = config.get("cascade_timeout_ms", 200)
        component.cache_recognition_results = config.get("cache_recognition_results", False)
        component.cache_ttl_seconds = config.get("cache_ttl_seconds", 300)
        
        # Add mock providers
        component.providers = {
            "fast_provider": MockNLUProvider("fast", confidence=0.9),
            "medium_provider": MockNLUProvider("medium", confidence=0.8),
            "slow_provider": MockNLUProvider("slow", confidence=0.7),

        }
        
        return component
    
    @pytest.fixture
    def sample_context(self):
        """Create sample conversation context"""
        return UnifiedConversationContext(
            session_id="test_session",
            user_id="test_user",
            client_id="test_client",
            language="ru"
        )

    @pytest.mark.asyncio
    async def test_successful_first_provider(self, nlu_component, sample_context):
        """Test successful recognition by first provider in cascade"""
        result = await nlu_component.recognize("test input", sample_context)
        
        # Should succeed with fast provider
        assert result.entities["provider"] == "fast"
        assert result.entities["_recognition_provider"] == "fast_provider"
        assert result.entities["_cascade_attempts"] == 1
        
        # Other providers should not be called
        assert nlu_component.providers["fast_provider"].call_count == 1
        assert nlu_component.providers["medium_provider"].call_count == 0
        assert nlu_component.providers["slow_provider"].call_count == 0

    @pytest.mark.asyncio
    async def test_cascade_to_second_provider(self, nlu_component, sample_context):
        """Test cascading to second provider when first fails confidence"""
        # Make fast provider return low confidence
        nlu_component.providers["fast_provider"].confidence = 0.5  # Below 0.8 threshold
        
        result = await nlu_component.recognize("test input", sample_context)
        
        # Should cascade to medium provider
        assert result.entities["provider"] == "medium"
        assert result.entities["_recognition_provider"] == "medium_provider"
        assert result.entities["_cascade_attempts"] == 2
        
        # Fast provider called but failed, medium provider succeeded
        assert nlu_component.providers["fast_provider"].call_count == 1
        assert nlu_component.providers["medium_provider"].call_count == 1
        assert nlu_component.providers["slow_provider"].call_count == 0

    @pytest.mark.asyncio
    async def test_cascade_through_all_providers(self, nlu_component, sample_context):
        """Test cascading through all providers until success"""
        # Make first three providers return low confidence
        nlu_component.providers["fast_provider"].confidence = 0.5
        nlu_component.providers["medium_provider"].confidence = 0.4
        nlu_component.providers["slow_provider"].confidence = 0.3
        
        result = await nlu_component.recognize("test input", sample_context)
        
        # Should cascade to slow_provider (now the last provider)
        assert result.entities["provider"] == "slow"
        assert result.entities["_recognition_provider"] == "slow_provider"
        assert result.entities["_cascade_attempts"] == 3
        
        # All providers should be called
        assert nlu_component.providers["fast_provider"].call_count == 1
        assert nlu_component.providers["medium_provider"].call_count == 1
        assert nlu_component.providers["slow_provider"].call_count == 1

    @pytest.mark.asyncio
    async def test_fallback_when_all_providers_fail(self, nlu_component, sample_context):
        """Test fallback intent when all providers fail or return low confidence"""
        # Make all providers return very low confidence
        for provider in nlu_component.providers.values():
            provider.confidence = 0.2
        
        result = await nlu_component.recognize("test input", sample_context)
        
        # Should return fallback intent
        assert result.name == "conversation.general"
        assert result.entities["_recognition_provider"] == "fallback"
        assert result.entities["_cascade_attempts"] == 4
        assert result.confidence == 1.0  # Fallback has high confidence

    @pytest.mark.asyncio
    async def test_provider_specific_thresholds(self, nlu_component, sample_context):
        """Test that providers use their specific confidence thresholds"""
        # Set medium provider confidence to 0.75 (above its 0.7 threshold, below fast's 0.8)
        nlu_component.providers["fast_provider"].confidence = 0.75  # Below 0.8 threshold
        nlu_component.providers["medium_provider"].confidence = 0.75  # Above 0.7 threshold
        
        result = await nlu_component.recognize("test input", sample_context)
        
        # Should cascade from fast to medium and succeed
        assert result.entities["provider"] == "medium"
        assert result.entities["_recognition_provider"] == "medium_provider"
        assert result.entities["_cascade_attempts"] == 2

    @pytest.mark.asyncio
    async def test_provider_exception_handling(self, nlu_component, sample_context):
        """Test proper handling of provider exceptions"""
        # Make fast provider throw exception
        nlu_component.providers["fast_provider"].should_fail = True
        
        result = await nlu_component.recognize("test input", sample_context)
        
        # Should cascade to medium provider
        assert result.entities["provider"] == "medium"
        assert result.entities["_recognition_provider"] == "medium_provider"
        assert result.entities["_cascade_attempts"] == 2
        
        # Fast provider called and failed, medium provider succeeded
        assert nlu_component.providers["fast_provider"].call_count == 1
        assert nlu_component.providers["medium_provider"].call_count == 1

    @pytest.mark.asyncio
    async def test_max_cascade_attempts_limit(self, nlu_component, sample_context):
        """Test that cascading respects max_cascade_attempts limit"""
        # Set max attempts to 2
        nlu_component.max_cascade_attempts = 2
        
        # Make all providers return low confidence
        for provider in nlu_component.providers.values():
            provider.confidence = 0.2
        
        result = await nlu_component.recognize("test input", sample_context)
        
        # Should stop after 2 attempts
        assert result.entities["_cascade_attempts"] == 2
        assert nlu_component.providers["fast_provider"].call_count == 1
        assert nlu_component.providers["medium_provider"].call_count == 1
        assert nlu_component.providers["slow_provider"].call_count == 0  # Not reached

    @pytest.mark.asyncio
    async def test_recognition_caching(self, nlu_component, sample_context):
        """Test recognition result caching functionality"""
        # Enable caching
        nlu_component.cache_recognition_results = True
        
        # First recognition
        result1 = await nlu_component.recognize("test input", sample_context)
        
        # Second recognition with same input
        result2 = await nlu_component.recognize("test input", sample_context)
        
        # Should get same result
        assert result1.entities["provider"] == result2.entities["provider"]
        
        # Fast provider should only be called once (cached second time)
        assert nlu_component.providers["fast_provider"].call_count == 1

    @pytest.mark.asyncio
    async def test_unavailable_provider_skipping(self, nlu_component, sample_context):
        """Test that unavailable providers are skipped"""
        # Remove medium provider to simulate unavailable
        del nlu_component.providers["medium_provider"]
        
        # Make fast provider return low confidence
        nlu_component.providers["fast_provider"].confidence = 0.5
        
        result = await nlu_component.recognize("test input", sample_context)
        
        # Should skip missing medium provider and go to slow provider
        assert result.entities["provider"] == "slow"
        assert result.entities["_recognition_provider"] == "slow_provider"
        assert result.entities["_cascade_attempts"] == 2  # Fast failed, medium skipped, slow succeeded

    @pytest.mark.asyncio
    async def test_context_aware_recognition_cascading(self, nlu_component, sample_context):
        """Test that context-aware recognition also uses cascading"""
        # Test the recognize_with_context method
        result = await nlu_component.recognize_with_context("test input", sample_context)
        
        # Should use cascading and succeed with first provider
        assert result.entities["_recognition_provider"] == "fast_provider"
        assert result.entities["_cascade_attempts"] == 1


def run_simple_cascading_test():
    """
    Simple test function that can be run independently to validate 
    basic cascading functionality for Phase 2.
    """
    print("🧪 Running simple cascading NLU test...")
    
    import asyncio
    
    async def test_basic_cascading():
        # Create mock component
        component = NLUComponent()
        component.confidence_threshold = 0.7
        component.provider_cascade_order = ["fast", "slow", "fallback"]
        component.max_cascade_attempts = 3
        component.fallback_intent = "conversation.general"
        
        # Mock core config
        component.core = MagicMock()
        component.core.config.components.nlu = {
            "providers": {
                "fast": {"confidence_threshold": 0.8},
                "slow": {"confidence_threshold": 0.6},
                "fallback": {"confidence_threshold": 0.5}
            }
        }
        
        # Add mock providers
        component.providers = {
            "fast": MockNLUProvider("fast", confidence=0.5),  # Will fail threshold
            "slow": MockNLUProvider("slow", confidence=0.8),  # Will succeed
            "fallback": MockNLUProvider("fallback", confidence=0.7)
        }
        
        # Test context
        context = UnifiedConversationContext(session_id="test")
        
        # Test cascading
        result = await component.recognize("test", context)
        
        # Should cascade from fast to slow
        assert result.entities["provider"] == "slow"
        assert result.entities["_cascade_attempts"] == 2
        
        print("✅ Basic cascading test passed!")
        print(f"   Provider used: {result.entities['provider']}")
        print(f"   Cascade attempts: {result.entities['_cascade_attempts']}")
        
        # Test provider thresholds
        fast_threshold = component._get_provider_confidence_threshold("fast")
        slow_threshold = component._get_provider_confidence_threshold("slow")
        
        assert fast_threshold == 0.8
        assert slow_threshold == 0.6
        
        print("✅ Provider-specific thresholds test passed!")
        print(f"   Fast provider threshold: {fast_threshold}")
        print(f"   Slow provider threshold: {slow_threshold}")
    
    # Run the test
    asyncio.run(test_basic_cascading())
    
    print("🎉 Phase 2 cascading NLU coordination is working correctly!")


if __name__ == "__main__":
    # Run simple test
    run_simple_cascading_test() 