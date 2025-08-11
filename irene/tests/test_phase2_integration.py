"""
Phase 2 Integration Tests - NLU Component JSON Donation Integration

Comprehensive tests for the critical bridge between JSON donations (Phase 0)
and NLU provider coordination (Phase 2).
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, List

from irene.components.nlu_component import NLUComponent
from irene.providers.nlu.rule_based import RuleBasedNLUProvider
from irene.providers.nlu.spacy_provider import SpaCyNLUProvider
from irene.core.donation_loader import DonationLoader
from irene.core.donations import DonationValidationConfig, HandlerDonation, MethodDonation
from irene.intents.models import ConversationContext


class TestPhase2DonationIntegration:
    """Test JSON donation integration with NLU providers"""
    
    @pytest.fixture
    def sample_json_donations(self):
        """Create sample JSON donation files for testing"""
        donations = {
            "greetings": {
                "handler_domain": "greeting",
                "handler_description": "Greeting intent handler",
                "global_parameters": [],
                "method_donations": [
                    {
                        "method_name": "handle_hello",
                        "intent_suffix": "hello",
                        "description": "Handle hello greetings",
                        "phrases": [
                            "привет",
                            "здравствуй", 
                            "доброе утро",
                            "hello",
                            "hi there"
                        ],
                        "lemmas": ["привет", "здравствовать", "hello"],
                        "parameters": [],
                        "examples": [
                            {"text": "привет как дела", "parameters": {}},
                            {"text": "hello there", "parameters": {}}
                        ],
                        "boost": 1.2
                    },
                    {
                        "method_name": "handle_goodbye", 
                        "intent_suffix": "goodbye",
                        "description": "Handle goodbye farewells",
                        "phrases": [
                            "пока",
                            "до свидания",
                            "goodbye",
                            "bye bye"
                        ],
                        "lemmas": ["пока", "свидание", "goodbye"],
                        "parameters": [],
                        "examples": [
                            {"text": "пока увидимся", "parameters": {}},
                            {"text": "goodbye for now", "parameters": {}}
                        ],
                        "boost": 1.0
                    }
                ]
            },
            "timer": {
                "handler_domain": "timer",
                "handler_description": "Timer management handler",
                "global_parameters": [],
                "method_donations": [
                    {
                        "method_name": "set_timer",
                        "intent_suffix": "set", 
                        "description": "Set a new timer",
                        "phrases": [
                            "поставь таймер",
                            "установи таймер",
                            "set timer",
                            "start timer"
                        ],
                        "lemmas": ["поставить", "установить", "set", "start"],
                        "parameters": [
                            {
                                "name": "duration",
                                "type": "duration",
                                "required": True,
                                "description": "Timer duration",
                                "extraction_patterns": [r"(\d+)\s*(минут|секунд|часов)", r"(\d+)\s*(minutes?|seconds?|hours?)"]
                            }
                        ],
                        "examples": [
                            {"text": "поставь таймер на 5 минут", "parameters": {"duration": "5 минут"}},
                            {"text": "set timer for 10 seconds", "parameters": {"duration": "10 seconds"}}
                        ],
                        "boost": 1.5
                    }
                ]
            }
        }
        return donations
    
    @pytest.fixture
    def temp_handler_dir(self, sample_json_donations):
        """Create temporary handler directory with JSON donation files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            handler_dir = Path(temp_dir) / "handlers"
            handler_dir.mkdir()
            
            # Create JSON files
            for handler_name, donation_data in sample_json_donations.items():
                json_file = handler_dir / f"{handler_name}.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(donation_data, f, indent=2, ensure_ascii=False)
                
                # Create corresponding Python file (empty for testing)
                py_file = handler_dir / f"{handler_name}.py"
                with open(py_file, 'w') as f:
                    f.write(f"# {handler_name} handler placeholder\n")
            
            yield handler_dir

    @pytest.mark.asyncio
    async def test_donation_loader_integration(self, temp_handler_dir):
        """Test that DonationLoader works with created JSON files"""
        # Create donation loader
        config = DonationValidationConfig(strict_mode=False)
        loader = DonationLoader(config)
        
        # Discover handler files
        handler_paths = []
        for py_file in temp_handler_dir.glob("*.py"):
            handler_paths.append(py_file)
        
        # Load donations
        donations = await loader.discover_and_load_donations(handler_paths)
        
        # Verify donations loaded
        assert len(donations) == 2
        assert "greetings" in donations
        assert "timer" in donations
        
        # Verify greeting donation
        greeting_donation = donations["greetings"]
        assert greeting_donation.handler_domain == "greeting"
        assert len(greeting_donation.method_donations) == 2
        
        # Verify method donations
        hello_method = greeting_donation.method_donations[0]
        assert hello_method.method_name == "handle_hello"
        assert hello_method.intent_suffix == "hello"
        assert len(hello_method.phrases) == 5
        assert "привет" in hello_method.phrases
        assert "hello" in hello_method.phrases
        
        print("✅ DonationLoader integration test passed!")

    @pytest.mark.asyncio 
    async def test_keyword_donation_conversion(self, temp_handler_dir):
        """Test conversion from JSON donations to KeywordDonation objects"""
        # Load donations
        config = DonationValidationConfig(strict_mode=False)
        loader = DonationLoader(config)
        
        handler_paths = list(temp_handler_dir.glob("*.py"))
        donations = await loader.discover_and_load_donations(handler_paths)
        
        # Convert to keyword donations
        keyword_donations = loader.convert_to_keyword_donations(donations)
        
        # Verify conversion
        assert len(keyword_donations) >= 3  # greeting.hello, greeting.goodbye, timer.set
        
        # Find specific donations
        hello_donation = None
        timer_donation = None
        
        for kd in keyword_donations:
            if kd.intent_name == "greeting.hello":
                hello_donation = kd
            elif kd.intent_name == "timer.set":
                timer_donation = kd
        
        # Verify hello donation
        assert hello_donation is not None
        assert len(hello_donation.phrases) == 5
        assert "привет" in hello_donation.phrases
        assert hello_donation.boost == 1.2
        
        # Verify timer donation
        assert timer_donation is not None
        assert len(timer_donation.phrases) == 4
        assert "поставь таймер" in timer_donation.phrases
        assert len(timer_donation.parameters) == 1
        assert timer_donation.parameters[0].name == "duration"
        
        print("✅ Keyword donation conversion test passed!")

    @pytest.mark.asyncio
    async def test_rule_based_provider_donation_initialization(self, temp_handler_dir):
        """Test RuleBasedNLUProvider initialization with donations"""
        # Create provider
        provider = RuleBasedNLUProvider({})
        
        # Load donations and convert
        config = DonationValidationConfig(strict_mode=False)
        loader = DonationLoader(config)
        
        handler_paths = list(temp_handler_dir.glob("*.py"))
        donations = await loader.discover_and_load_donations(handler_paths)
        keyword_donations = loader.convert_to_keyword_donations(donations)
        
        # Initialize provider with donations
        await provider._initialize_from_donations(keyword_donations)
        
        # Verify patterns were created
        assert len(provider.patterns) >= 3
        assert "greeting.hello" in provider.patterns
        assert "greeting.goodbye" in provider.patterns
        assert "timer.set" in provider.patterns
        
        # Verify pattern structure
        hello_patterns = provider.patterns["greeting.hello"]
        assert len(hello_patterns) == 5  # 5 phrases converted to regex
        
        # Verify patterns are regex objects
        import re
        for pattern in hello_patterns:
            assert isinstance(pattern, re.Pattern)
        
        print("✅ RuleBasedNLU donation initialization test passed!")

    @pytest.mark.asyncio
    async def test_spacy_provider_donation_initialization(self, temp_handler_dir):
        """Test SpaCyNLUProvider initialization with donations"""
        # Create provider (without spaCy model for testing)
        provider = SpaCyNLUProvider({})
        
        # Load donations and convert
        config = DonationValidationConfig(strict_mode=False)
        loader = DonationLoader(config)
        
        handler_paths = list(temp_handler_dir.glob("*.py"))
        donations = await loader.discover_and_load_donations(handler_paths)
        keyword_donations = loader.convert_to_keyword_donations(donations)
        
        # Initialize provider with donations
        await provider._initialize_from_donations(keyword_donations)
        
        # Verify semantic examples were created
        assert len(provider.intent_patterns) >= 3
        assert "greeting.hello" in provider.intent_patterns
        assert "greeting.goodbye" in provider.intent_patterns
        assert "timer.set" in provider.intent_patterns
        
        # Verify semantic examples
        hello_examples = provider.intent_patterns["greeting.hello"]
        assert len(hello_examples) >= 5  # Original phrases
        assert "привет" in hello_examples
        assert "hello" in hello_examples
        
        print("✅ SpaCyNLU donation initialization test passed!")

    @pytest.mark.asyncio
    async def test_nlu_component_donation_integration(self, temp_handler_dir, monkeypatch):
        """Test full NLUComponent integration with donations"""
        # Create NLU component
        nlu_component = NLUComponent()
        
        # Mock handler directory discovery to use our temp directory
        def mock_discover_handler_files(self, handler_dir):
            return list(temp_handler_dir.glob("*.py"))
        
        monkeypatch.setattr(NLUComponent, '_discover_handler_files', mock_discover_handler_files)
        
        # Add a test provider
        rule_provider = RuleBasedNLUProvider({})
        nlu_component.providers["rule_based"] = rule_provider
        
        # Test donation initialization
        await nlu_component.initialize_providers_from_json_donations()
        
        # Verify provider was initialized with donations
        assert len(rule_provider.patterns) >= 3
        assert "greeting.hello" in rule_provider.patterns
        
        print("✅ NLUComponent donation integration test passed!")

    @pytest.mark.asyncio
    async def test_end_to_end_donation_flow(self, temp_handler_dir, monkeypatch):
        """Test complete end-to-end flow: JSON → Donations → Providers → Recognition"""
        # Setup NLU component with mocked handler discovery
        nlu_component = NLUComponent()
        
        def mock_discover_handler_files(self, handler_dir):
            return list(temp_handler_dir.glob("*.py"))
        
        monkeypatch.setattr(NLUComponent, '_discover_handler_files', mock_discover_handler_files)
        
        # Add providers
        rule_provider = RuleBasedNLUProvider({})
        nlu_component.providers["rule_based"] = rule_provider
        nlu_component.provider_cascade_order = ["rule_based"]
        
        # Initialize with donations
        await nlu_component.initialize_providers_from_json_donations()
        
        # Test recognition with donation-driven patterns
        context = ConversationContext(session_id="test", language="ru")
        
        # Test Russian greeting
        intent = await nlu_component.recognize("привет", context)
        assert intent.name == "greeting.hello"
        assert intent.confidence > 0.0
        
        # Test English greeting  
        intent = await nlu_component.recognize("hello", context)
        assert intent.name == "greeting.hello"
        assert intent.confidence > 0.0
        
        # Test timer intent
        intent = await nlu_component.recognize("поставь таймер", context)
        assert intent.name == "timer.set"
        assert intent.confidence > 0.0
        
        print("✅ End-to-end donation flow test passed!")
        print(f"   Recognized intents using donation-driven patterns")
        print(f"   Provider patterns loaded: {len(rule_provider.patterns)}")


async def run_phase2_tests():
    """Run all Phase 2 integration tests"""
    print("🧪 Running Phase 2 NLU-Donation Integration Tests...\n")
    
    import tempfile
    import json
    from pathlib import Path
    
    # Create sample donations
    donations = {
        "greetings": {
            "handler_domain": "greeting",
            "handler_description": "Greeting intent handler",
            "global_parameters": [],
            "method_donations": [
                {
                    "method_name": "handle_hello",
                    "intent_suffix": "hello",
                    "description": "Handle hello greetings",
                    "phrases": ["привет", "здравствуй", "hello", "hi"],
                    "lemmas": ["привет", "здравствовать", "hello"],
                    "parameters": [],
                    "examples": [{"text": "привет как дела", "parameters": {}}],
                    "boost": 1.2
                }
            ]
        }
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        handler_dir = Path(temp_dir) / "handlers"
        handler_dir.mkdir()
        
        # Create test files
        json_file = handler_dir / "greetings.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(donations["greetings"], f, indent=2, ensure_ascii=False)
        
        py_file = handler_dir / "greetings.py"
        with open(py_file, 'w') as f:
            f.write("# greetings handler\n")
        
        # Test donation loading
        print("📝 Testing Donation Loading...")
        from irene.core.donation_loader import DonationLoader
        from irene.core.donations import DonationValidationConfig
        
        config = DonationValidationConfig(strict_mode=False)
        loader = DonationLoader(config)
        
        loaded_donations = await loader.discover_and_load_donations([py_file])
        assert len(loaded_donations) == 1
        print("✅ Donation loading test passed!")
        
        # Test keyword conversion
        print("\n🔄 Testing Keyword Conversion...")
        keyword_donations = loader.convert_to_keyword_donations(loaded_donations)
        assert len(keyword_donations) == 1
        assert keyword_donations[0].intent_name == "greeting.hello"
        print("✅ Keyword conversion test passed!")
        
        # Test provider initialization
        print("\n🔗 Testing Provider Initialization...")
        from irene.providers.nlu.rule_based import RuleBasedNLUProvider
        
        provider = RuleBasedNLUProvider({})
        await provider._initialize_from_donations(keyword_donations)
        
        assert "greeting.hello" in provider.patterns
        assert len(provider.patterns["greeting.hello"]) == 4
        print("✅ Provider initialization test passed!")
        
        # Test NLU component integration
        print("\n🎯 Testing NLU Component Integration...")
        from irene.components.nlu_component import NLUComponent
        
        nlu_component = NLUComponent()
        nlu_component.providers["rule_based"] = provider
        
        # Test recognition
        from irene.intents.models import ConversationContext
        context = ConversationContext(session_id="test", language="ru")
        
        intent = await nlu_component.recognize("привет", context)
        assert intent.name == "greeting.hello"
        print("✅ NLU component integration test passed!")
    
    print("\n🎉 All Phase 2 Integration Tests Passed!")
    print("✅ JSON donations → NLU providers bridge working")
    print("✅ Donation-driven pattern loading functional") 
    print("✅ End-to-end recognition with donations successful")
    print("\n📈 Phase 2 implementation is complete and functional!")


if __name__ == "__main__":
    asyncio.run(run_phase2_tests())
