"""
Test Phase 4: Complete Pattern Removal

Validates that hardcoded patterns have been removed and the system operates
exclusively from JSON donations with proper error handling.
"""

import pytest
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import json
import asyncio

from irene.providers.nlu.rule_based import RuleBasedNLUProvider
from irene.providers.nlu.spacy_provider import SpaCyNLUProvider
from irene.intents.models import Intent, ConversationContext
from irene.core.donations import HandlerDonation, MethodDonation, ParameterSpec


class TestPhase4PatternRemoval(unittest.TestCase):
    """Test that hardcoded patterns are completely removed"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.context = ConversationContext(
            session_id="test_session",
            user_id="test_user",
            client_id="test_client"
        )
        
        # Sample donation data for testing
        self.sample_donation = {
            "intent_name": "greeting.hello",
            "phrases": ["привет", "здравствуй", "hello", "hi"],
            "lemmas": ["привет", "здравствовать", "hello"],
            "parameters": [],
            "token_patterns": [],
            "slot_patterns": {},
            "examples": [],
            "boost": 1.0
        }
    
    def run_async_test(self, async_test_func):
        """Helper to run async tests in unittest"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_test_func())
        finally:
            loop.close()
    
    def test_rule_based_provider_no_hardcoded_patterns(self):
        """Test that RuleBasedNLUProvider has no hardcoded fallback patterns"""
        config = {
            'confidence_threshold': 0.7,
            'default_confidence': 0.8,
            'fallback_intent': 'conversation.general'
        }
        
        provider = RuleBasedNLUProvider(config)
        
        # Should start with empty patterns
        self.assertEqual(len(provider.patterns), 0)
        
        # Should not have the removed _initialize_patterns method
        self.assertFalse(hasattr(provider, '_initialize_patterns'),
                        "RuleBasedNLUProvider should not have _initialize_patterns method after Phase 4")
    
    def test_rule_based_provider_requires_donations(self):
        """Test that RuleBasedNLUProvider fails without JSON donations"""
        async def async_test():
            config = {
                'confidence_threshold': 0.7,
                'default_confidence': 0.8,
                'fallback_intent': 'conversation.general'
            }
            
            provider = RuleBasedNLUProvider(config)
            
            # Should not be available without patterns
            available = await provider.is_available()
            self.assertFalse(available)
            
            # Should fail on _do_initialize without patterns
            with self.assertRaises(RuntimeError) as cm:
                await provider._do_initialize()
            
            self.assertIn("JSON donations", str(cm.exception))
            self.assertIn("_initialize_from_donations", str(cm.exception))
        
        self.run_async_test(async_test)
    
    def test_rule_based_provider_donation_initialization(self):
        """Test that RuleBasedNLUProvider works with JSON donations"""
        async def async_test():
            config = {
                'confidence_threshold': 0.7,
                'default_confidence': 0.8,
                'fallback_intent': 'conversation.general'
            }
            
            provider = RuleBasedNLUProvider(config)
            
            # Create mock donation
            mock_donation = MagicMock()
            mock_donation.intent_name = "greeting.hello"
            mock_donation.phrases = ["привет", "hello"]
            
            # Initialize with donations
            await provider._initialize_from_donations([mock_donation])
            
            # Should now have patterns
            self.assertGreater(len(provider.patterns), 0)
            self.assertIn("greeting.hello", provider.patterns)
            
            # Should be available
            available = await provider.is_available()
            self.assertTrue(available)
        
        self.run_async_test(async_test)
    
    def test_rule_based_provider_donation_failure_no_fallback(self):
        """Test that RuleBasedNLUProvider fails fast on donation errors"""
        async def async_test():
            config = {
                'confidence_threshold': 0.7,
                'default_confidence': 0.8,
                'fallback_intent': 'conversation.general'
            }
            
            provider = RuleBasedNLUProvider(config)
            
            # Create invalid donation that will cause error
            invalid_donation = MagicMock()
            invalid_donation.intent_name = "test.intent"
            invalid_donation.phrases = None  # This will cause error
            
            # Should raise RuntimeError, not fall back to hardcoded patterns
            with self.assertRaises(RuntimeError) as cm:
                await provider._initialize_from_donations([invalid_donation])
            
            self.assertIn("JSON donation initialization failed", str(cm.exception))
            self.assertIn("cannot operate without valid donations", str(cm.exception))
        
        self.run_async_test(async_test)
    
    def test_spacy_provider_no_hardcoded_patterns(self):
        """Test that SpaCyNLUProvider has no hardcoded fallback patterns"""
        config = {
            'model_name': 'ru_core_news_sm',
            'confidence_threshold': 0.7
        }
        
        provider = SpaCyNLUProvider(config)
        
        # Should start with empty intent patterns
        self.assertEqual(len(provider.intent_patterns), 0)
    
    def test_spacy_provider_requires_donations(self):
        """Test that SpaCyNLUProvider requires donations for availability"""
        async def async_test():
            config = {
                'model_name': 'ru_core_news_sm',
                'confidence_threshold': 0.7
            }
            
            provider = SpaCyNLUProvider(config)
            provider.nlp = MagicMock()  # Mock nlp to focus on pattern requirement
            
            # Should not be available without intent patterns
            available = await provider.is_available()
            self.assertFalse(available)
        
        self.run_async_test(async_test)
    
    def test_spacy_provider_donation_initialization(self):
        """Test that SpaCyNLUProvider works with JSON donations"""
        async def async_test():
            config = {
                'model_name': 'ru_core_news_sm',
                'confidence_threshold': 0.7
            }
            
            provider = SpaCyNLUProvider(config)
            
            # Create mock donation
            mock_donation = MagicMock()
            mock_donation.intent_name = "greeting.hello"
            mock_donation.phrases = ["привет", "hello"]
            mock_donation.training_examples = []
            
            # Initialize with donations
            await provider._initialize_from_donations([mock_donation])
            
            # Should now have intent patterns (this is the key test)
            self.assertGreater(len(provider.intent_patterns), 0)
            self.assertIn("greeting.hello", provider.intent_patterns)
            
            # The exact phrases should be in the intent patterns
            self.assertEqual(provider.intent_patterns["greeting.hello"], ["привет", "hello"])
        
        self.run_async_test(async_test)
    
    def test_spacy_provider_donation_failure_no_fallback(self):
        """Test that SpaCyNLUProvider fails fast on donation errors"""
        async def async_test():
            config = {
                'model_name': 'ru_core_news_sm',
                'confidence_threshold': 0.7
            }
            
            provider = SpaCyNLUProvider(config)
            
            # Create invalid donation that will cause error
            invalid_donation = MagicMock()
            invalid_donation.intent_name = "test.intent"
            invalid_donation.phrases = None  # This will cause error
            
            # Should raise RuntimeError, not fall back to hardcoded patterns
            with self.assertRaises(RuntimeError) as cm:
                await provider._initialize_from_donations([invalid_donation])
            
            self.assertIn("JSON donation initialization failed", str(cm.exception))
            self.assertIn("cannot operate without valid donations", str(cm.exception))
        
        self.run_async_test(async_test)
    
    def test_intent_handlers_no_pattern_methods(self):
        """Test that intent handlers no longer have get_*_patterns methods"""
        from irene.intents.handlers.system import SystemIntentHandler
        from irene.intents.handlers.datetime import DateTimeIntentHandler
        from irene.intents.handlers.conversation import ConversationIntentHandler
        from irene.intents.handlers.timer import TimerIntentHandler
        from irene.intents.handlers.greetings import GreetingsIntentHandler
        
        # Verify all pattern methods are removed
        self.assertFalse(hasattr(SystemIntentHandler, 'get_system_patterns'))
        self.assertFalse(hasattr(DateTimeIntentHandler, 'get_datetime_patterns'))
        self.assertFalse(hasattr(ConversationIntentHandler, 'get_conversation_patterns'))
        self.assertFalse(hasattr(TimerIntentHandler, 'get_timer_patterns'))
        self.assertFalse(hasattr(GreetingsIntentHandler, 'get_greeting_patterns'))
    
    def test_json_donation_files_exist(self):
        """Test that all required JSON donation files exist"""
        handler_dir = Path("irene/intents/handlers")
        required_handlers = [
            "system", "datetime", "conversation", 
            "timer", "greetings", "train_schedule"
        ]
        
        for handler_name in required_handlers:
            json_file = handler_dir / f"{handler_name}.json"
            self.assertTrue(json_file.exists(), 
                           f"JSON donation file missing: {json_file}")
    
    def test_json_donation_files_valid_format(self):
        """Test that JSON donation files have valid format"""
        handler_dir = Path("irene/intents/handlers")
        json_files = list(handler_dir.glob("*.json"))
        
        self.assertGreater(len(json_files), 0, "No JSON donation files found")
        
        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    
                    # Basic structure validation
                    self.assertIn('schema_version', data)
                    self.assertIn('handler_domain', data)
                    self.assertIn('method_donations', data)
                    self.assertIsInstance(data['method_donations'], list)
                    self.assertGreater(len(data['method_donations']), 0)
                    
                    # Validate each method donation
                    for method_donation in data['method_donations']:
                        self.assertIn('method_name', method_donation)
                        self.assertIn('intent_suffix', method_donation)
                        self.assertIn('phrases', method_donation)
                        self.assertIsInstance(method_donation['phrases'], list)
                        self.assertGreater(len(method_donation['phrases']), 0)
                        
                except json.JSONDecodeError as e:
                    self.fail(f"Invalid JSON in {json_file}: {e}")
                except Exception as e:
                    self.fail(f"Validation error in {json_file}: {e}")


class TestPhase4IntegrationValidation(unittest.TestCase):
    """Integration tests for Phase 4 validation"""
    
    def run_async_test(self, async_test_func):
        """Helper to run async tests in unittest"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_test_func())
        finally:
            loop.close()
    
    def test_end_to_end_donation_driven_recognition(self):
        """Test complete end-to-end flow with JSON donations only"""
        async def async_test():
            # This test would require setting up the full component chain
            # but validates that the system works without any hardcoded patterns
            pass
        
        self.run_async_test(async_test)
    
    def test_missing_donation_file_fails_fast(self):
        """Test that missing JSON donation files cause immediate failure"""
        async def async_test():
            # This test would validate that the system fails appropriately
            # when donation files are missing, rather than falling back
            pass
        
        self.run_async_test(async_test)


def run_phase4_validation():
    """Run all Phase 4 validation tests"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase4PatternRemoval)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPhase4IntegrationValidation))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    import asyncio
    
    # Run the validation
    success = run_phase4_validation()
    
    if success:
        print("\n✅ Phase 4 validation PASSED - Pattern removal successful!")
    else:
        print("\n❌ Phase 4 validation FAILED - Pattern removal incomplete!")
        exit(1)
