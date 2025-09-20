"""
Test Phase 1 NLU Improvements

Comprehensive test suite for Phase 1 NLU improvements including:
- HybridKeywordMatcher critical fixes (keyword collision resolution, language partitioning)
- SpaCy provider language awareness (multi-model management, language detection)
- Scoring scale consistency (0-1 normalization)
- Performance benchmarks and stress tests
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from irene.providers.nlu.hybrid_keyword_matcher import HybridKeywordMatcherProvider
from irene.providers.nlu.spacy_provider import SpaCyNLUProvider
from irene.intents.models import ConversationContext
from irene.core.donations import KeywordDonation, ParameterSpec, ParameterType


class TestHybridKeywordMatcherPhase1:
    """Test suite for Phase 1 HybridKeywordMatcher improvements"""
    
    @pytest.fixture
    def provider_config(self):
        """Standard test configuration for hybrid provider"""
        return {
            'confidence_threshold': 0.7,
            'fuzzy_threshold': 0.8,
            'pattern_confidence': 0.9,
            'fuzzy_enabled': True,
            'case_sensitive': False,
            'normalize_unicode': True
        }
    
    @pytest.fixture
    def sample_donations(self):
        """Sample donations for testing with potential collisions"""
        return [
            KeywordDonation(
                intent="timer.set",
                phrases=["установи таймер", "поставь будильник", "set timer"],
                lemmas=["таймер", "timer", "alarm"],
                examples=[],
                parameters=[]
            ),
            KeywordDonation(
                intent="timer.cancel",
                phrases=["отмени таймер", "убери будильник", "cancel timer"],
                lemmas=["отмена", "cancel", "stop"],
                examples=[],
                parameters=[]
            ),
            KeywordDonation(
                intent="alarm.set",
                phrases=["поставь будильник", "создай напоминание", "set alarm"],  # Collision with timer
                lemmas=["будильник", "alarm", "reminder"],
                examples=[],
                parameters=[]
            )
        ]
    
    @pytest.fixture
    async def initialized_provider(self, provider_config, sample_donations):
        """Initialized provider with sample donations"""
        provider = HybridKeywordMatcherProvider(provider_config)
        await provider._do_initialize()
        await provider._initialize_from_donations(sample_donations)
        return provider
    
    def test_keyword_collision_resolution(self, initialized_provider):
        """Test that keyword collisions are properly resolved using sets"""
        # Check that global keyword map uses sets instead of single strings
        global_map = initialized_provider.global_keyword_map
        
        # Find a keyword that should appear in multiple intents
        collision_keyword = "будильник"  # Should appear in both timer.set and alarm.set
        
        if collision_keyword in global_map:
            intents = global_map[collision_keyword]
            assert isinstance(intents, set), "Keyword mapping should use sets for collision resolution"
            assert len(intents) > 1, "Expected collision keyword to map to multiple intents"
            assert "timer.set" in intents or "alarm.set" in intents
    
    def test_language_partitioning(self, initialized_provider):
        """Test that keywords are properly partitioned by language"""
        # Check that language-specific maps are populated
        assert len(initialized_provider.global_keyword_map_ru) > 0, "Russian keyword map should be populated"
        assert len(initialized_provider.global_keyword_map_en) > 0, "English keyword map should be populated"
        
        # Check language detection for sample keywords
        assert initialized_provider._detect_language("таймер") == "ru"
        assert initialized_provider._detect_language("timer") == "en"
        assert initialized_provider._detect_language("поставь будильник") == "ru"
        
        # Verify keywords are in appropriate language maps
        ru_keywords = initialized_provider.fuzzy_keywords_ru
        en_keywords = initialized_provider.fuzzy_keywords_en
        
        assert any("таймер" in kw for kw in ru_keywords), "Russian keywords should be in RU map"
        assert any("timer" in kw for kw in en_keywords), "English keywords should be in EN map"
    
    def test_improved_normalization(self, initialized_provider):
        """Test improved Unicode normalization"""
        # Test with various Unicode forms
        test_cases = [
            ("café", "cafe"),  # NFC to NFD decomposition
            ("naïve", "naive"),  # Combining characters removal
            ("ПРИВЕТ", "привет"),  # Case folding
            ("  multiple   spaces  ", "multiple spaces")  # Whitespace normalization
        ]
        
        for input_text, expected_normalized in test_cases:
            normalized = initialized_provider._normalize_text(input_text)
            assert expected_normalized in normalized.lower(), f"Failed to normalize '{input_text}'"
    
    def test_token_based_partial_matching(self, initialized_provider):
        """Test token-based partial matching replaces regex explosion"""
        # Test partial matching logic
        input_tokens = ["установи", "таймер", "на", "пять", "минут"]
        phrase_tokens = ["установи", "таймер", "минут"]
        
        result = initialized_provider._check_partial_match(input_tokens, phrase_tokens)
        assert result, "Should match when 70% of phrase tokens are present"
        
        # Test insufficient match
        phrase_tokens_long = ["установи", "таймер", "на", "определенное", "время", "завтра"]
        result = initialized_provider._check_partial_match(input_tokens, phrase_tokens_long)
        assert not result, "Should not match when less than 70% of phrase tokens are present"
    
    def test_scoring_consistency(self, initialized_provider):
        """Test that all scores are in 0-1 range"""
        assert 0.0 <= initialized_provider.confidence_threshold <= 1.0
        assert 0.0 <= initialized_provider.fuzzy_threshold <= 1.0
        assert 0.0 <= initialized_provider.pattern_confidence <= 1.0
    
    def test_configuration_validation(self, provider_config):
        """Test configuration validation"""
        # Valid configuration should pass
        provider = HybridKeywordMatcherProvider(provider_config)
        assert provider.validate_config()
        
        # Invalid confidence threshold should fail
        invalid_config = provider_config.copy()
        invalid_config['confidence_threshold'] = 1.5
        provider = HybridKeywordMatcherProvider(invalid_config)
        assert not provider.validate_config()
    
    @pytest.mark.asyncio
    async def test_performance_benchmark(self, initialized_provider):
        """Performance benchmark for key operations"""
        context = ConversationContext(session_id="test", language="ru")
        
        # Benchmark pattern matching
        start_time = time.perf_counter()
        for _ in range(100):
            await initialized_provider.recognize("установи таймер на пять минут", context)
        pattern_time = time.perf_counter() - start_time
        
        # Should complete 100 recognitions in reasonable time
        assert pattern_time < 1.0, f"Pattern matching too slow: {pattern_time:.3f}s for 100 recognitions"
        
        # Benchmark language detection
        start_time = time.perf_counter()
        for _ in range(1000):
            initialized_provider._detect_language("установи таймер")
            initialized_provider._detect_language("set timer")
        detection_time = time.perf_counter() - start_time
        
        assert detection_time < 0.1, f"Language detection too slow: {detection_time:.3f}s for 1000 detections"
    
    @pytest.mark.asyncio
    async def test_stress_test_large_donation_set(self, provider_config):
        """Stress test with large donation set"""
        # Create large donation set with potential collisions
        large_donations = []
        for i in range(50):
            large_donations.append(KeywordDonation(
                intent=f"domain{i % 10}.action{i}",
                phrases=[f"phrase {i}", f"action {i}", f"команда {i}"],
                lemmas=[f"lemma{i}", f"key{i}"],
                examples=[],
                parameters=[]
            ))
        
        provider = HybridKeywordMatcherProvider(provider_config)
        await provider._do_initialize()
        
        # Should handle large donation set without issues
        start_time = time.perf_counter()
        await provider._initialize_from_donations(large_donations)
        init_time = time.perf_counter() - start_time
        
        assert init_time < 5.0, f"Initialization too slow for large dataset: {init_time:.3f}s"
        assert len(provider.exact_patterns) == 50, "Should process all donations"


class TestSpaCyProviderPhase1:
    """Test suite for Phase 1 SpaCy provider improvements"""
    
    @pytest.fixture
    def provider_config(self):
        """Standard test configuration for SpaCy provider"""
        return {
            'model_name': 'ru_core_news_sm',
            'fallback_model': 'en_core_web_sm',
            'confidence_threshold': 0.7
        }
    
    @pytest.fixture
    def mock_spacy_models(self):
        """Mock spaCy models for testing"""
        mock_ru_model = MagicMock()
        mock_ru_model.meta = {'name': 'ru_core_news_sm', 'version': '3.7.0'}
        mock_ru_model.lang = 'ru'
        
        mock_en_model = MagicMock()
        mock_en_model.meta = {'name': 'en_core_web_sm', 'version': '3.7.0'}
        mock_en_model.lang = 'en'
        
        return {'ru': mock_ru_model, 'en': mock_en_model}
    
    def test_language_detection(self, provider_config):
        """Test language detection based on script"""
        provider = SpaCyNLUProvider(provider_config)
        
        # Test Cyrillic detection
        assert provider._detect_language("Привет мир") == "ru"
        assert provider._detect_language("установи таймер") == "ru"
        
        # Test non-Cyrillic detection
        assert provider._detect_language("Hello world") == "en"
        assert provider._detect_language("set timer") == "en"
        assert provider._detect_language("123 numbers") == "en"
    
    def test_multi_model_configuration(self, provider_config):
        """Test multi-model management setup"""
        provider = SpaCyNLUProvider(provider_config)
        
        # Check language preferences are set up
        assert 'ru' in provider.language_preferences
        assert 'en' in provider.language_preferences
        assert isinstance(provider.available_models, dict)
    
    @patch('irene.providers.nlu.spacy_provider.safe_import')
    def test_model_availability_handling(self, mock_safe_import, provider_config):
        """Test handling of unavailable models"""
        # Mock spaCy import
        mock_spacy = MagicMock()
        mock_safe_import.return_value = mock_spacy
        
        # Mock model loading to simulate unavailable models
        def mock_load(model_name):
            if model_name == 'ru_core_news_md':
                raise OSError("Model not found")
            elif model_name == 'ru_core_news_sm':
                model = MagicMock()
                model.meta = {'name': model_name, 'version': '3.7.0'}
                return model
            raise OSError("Model not found")
        
        mock_spacy.load = mock_load
        
        provider = SpaCyNLUProvider(provider_config)
        
        # Should handle gracefully when preferred models are unavailable
        # This would be tested in full integration, here we test the structure
        assert provider.language_preferences['ru'][0] == 'ru_core_news_md'
        assert provider.language_preferences['ru'][1] == 'ru_core_news_sm'
    
    def test_updated_asset_configuration(self, provider_config):
        """Test that asset configuration reflects multi-model approach"""
        provider = SpaCyNLUProvider(provider_config)
        
        asset_config = provider.get_asset_config()
        
        # Should include all language models
        package_deps = asset_config["package_dependencies"]
        assert any("ru_core_news_md" in dep for dep in package_deps)
        assert any("ru_core_news_sm" in dep for dep in package_deps)
        assert any("en_core_web_md" in dep for dep in package_deps)
        assert any("en_core_web_sm" in dep for dep in package_deps)
        
        # Should include language support mapping
        assert "language_support" in asset_config
        assert "ru" in asset_config["language_support"]
        assert "en" in asset_config["language_support"]
    
    def test_updated_python_dependencies(self, provider_config):
        """Test that Python dependencies include all models"""
        provider = SpaCyNLUProvider(provider_config)
        
        python_deps = provider.get_python_dependencies()
        
        # Should include all language models
        assert any("ru_core_news_md" in dep for dep in python_deps)
        assert any("ru_core_news_sm" in dep for dep in python_deps)
        assert any("en_core_web_md" in dep for dep in python_deps)
        assert any("en_core_web_sm" in dep for dep in python_deps)
        
        # Should still include core dependencies
        assert any("spacy>=3.7.0" in dep for dep in python_deps)
        assert any("numpy>=1.20.0" in dep for dep in python_deps)
    
    @pytest.mark.asyncio
    async def test_runtime_language_rejection(self, provider_config, mock_spacy_models):
        """Test runtime language rejection when no model available"""
        provider = SpaCyNLUProvider(provider_config)
        provider.available_models = {'ru': mock_spacy_models['ru']}  # Only Russian available
        provider.nlp = mock_spacy_models['ru']
        
        context = ConversationContext(session_id="test", language="en")
        
        # Mock the language detection and model selection
        with patch.object(provider, '_detect_language', return_value='en'):
            # Should detect English but only have Russian model
            # The provider should handle this gracefully
            
            # Mock the models to avoid actual spaCy calls
            mock_spacy_models['ru'].return_value = MagicMock()
            
            result = await provider.recognize("Hello world", context)
            
            # Should still return an intent (likely general) rather than failing
            assert result is not None
            assert hasattr(result, 'confidence')
    
    def test_scoring_consistency(self, provider_config):
        """Test that SpaCy provider uses consistent 0-1 scoring"""
        provider = SpaCyNLUProvider(provider_config)
        
        assert 0.0 <= provider.confidence_threshold <= 1.0
        assert provider.validate_config()
        
        # Test invalid configuration
        provider.confidence_threshold = 1.5
        assert not provider.validate_config()
    
    @pytest.mark.asyncio
    async def test_language_specific_processing(self, provider_config, mock_spacy_models):
        """Test that different models are used for different languages"""
        provider = SpaCyNLUProvider(provider_config)
        provider.available_models = mock_spacy_models
        provider.nlp = mock_spacy_models['ru']  # Default to Russian
        
        context = ConversationContext(session_id="test")
        
        # Mock doc objects for different languages
        mock_ru_doc = MagicMock()
        mock_en_doc = MagicMock()
        
        mock_spacy_models['ru'].return_value = mock_ru_doc
        mock_spacy_models['en'].return_value = mock_en_doc
        
        # Test Russian text processing
        with patch.object(provider, '_detect_language', return_value='ru'):
            with patch.object(provider, '_extract_spacy_entities', return_value={}):
                with patch.object(provider, '_classify_intent_similarity', return_value=("test.intent", 0.8)):
                    with patch.object(provider, '_extract_domain_entities', return_value={}):
                        result = await provider.recognize("привет", context)
                        
                        # Should use Russian model
                        mock_spacy_models['ru'].assert_called_with("привет")
                        assert result.confidence == 0.8
        
        # Test English text processing
        with patch.object(provider, '_detect_language', return_value='en'):
            with patch.object(provider, '_extract_spacy_entities', return_value={}):
                with patch.object(provider, '_classify_intent_similarity', return_value=("test.intent", 0.8)):
                    with patch.object(provider, '_extract_domain_entities', return_value={}):
                        result = await provider.recognize("hello", context)
                        
                        # Should use English model
                        mock_spacy_models['en'].assert_called_with("hello")
                        assert result.confidence == 0.8


class TestCrossProviderConsistency:
    """Test consistency between HybridKeywordMatcher and SpaCy providers"""
    
    @pytest.fixture
    def consistent_config(self):
        """Configuration that should be consistent across providers"""
        return {
            'confidence_threshold': 0.7,  # Should be same default
            'case_sensitive': False,
            'normalize_unicode': True
        }
    
    def test_default_confidence_thresholds(self, consistent_config):
        """Test that both providers use consistent default thresholds"""
        hybrid_provider = HybridKeywordMatcherProvider(consistent_config)
        spacy_provider = SpaCyNLUProvider(consistent_config)
        
        assert hybrid_provider.confidence_threshold == spacy_provider.confidence_threshold
        assert hybrid_provider.confidence_threshold == 0.7
    
    def test_language_detection_consistency(self, consistent_config):
        """Test that both providers detect languages consistently"""
        hybrid_provider = HybridKeywordMatcherProvider(consistent_config)
        spacy_provider = SpaCyNLUProvider(consistent_config)
        
        test_texts = [
            "Привет мир",
            "установи таймер",
            "Hello world", 
            "set timer",
            "123 test"
        ]
        
        for text in test_texts:
            hybrid_lang = hybrid_provider._detect_language(text)
            spacy_lang = spacy_provider._detect_language(text)
            assert hybrid_lang == spacy_lang, f"Language detection mismatch for '{text}'"
    
    def test_configuration_validation_consistency(self, consistent_config):
        """Test that both providers validate configurations consistently"""
        # Valid config should pass for both
        hybrid_provider = HybridKeywordMatcherProvider(consistent_config)
        spacy_provider = SpaCyNLUProvider(consistent_config)
        
        assert hybrid_provider.validate_config()
        assert spacy_provider.validate_config()
        
        # Invalid confidence should fail for both
        invalid_config = consistent_config.copy()
        invalid_config['confidence_threshold'] = 1.5
        
        hybrid_provider_invalid = HybridKeywordMatcherProvider(invalid_config)
        spacy_provider_invalid = SpaCyNLUProvider(invalid_config)
        
        assert not hybrid_provider_invalid.validate_config()
        assert not spacy_provider_invalid.validate_config()


class TestPerformanceAndStress:
    """Performance and stress tests for Phase 1 improvements"""
    
    @pytest.mark.asyncio
    async def test_keyword_collision_performance(self):
        """Test that collision resolution doesn't significantly impact performance"""
        config = {'confidence_threshold': 0.7, 'fuzzy_enabled': True}
        
        # Create donations with many overlapping keywords
        collision_donations = []
        for i in range(20):
            collision_donations.append(KeywordDonation(
                intent=f"intent_{i}",
                phrases=["общий ключевое слово", f"уникальный {i}", "shared keyword"],
                lemmas=["общий", "shared", f"unique_{i}"],
                examples=[],
                parameters=[]
            ))
        
        provider = HybridKeywordMatcherProvider(config)
        await provider._do_initialize()
        
        # Time initialization with collisions
        start_time = time.perf_counter()
        await provider._initialize_from_donations(collision_donations)
        init_time = time.perf_counter() - start_time
        
        # Should handle collisions efficiently
        assert init_time < 2.0, f"Collision handling too slow: {init_time:.3f}s"
        
        # Verify collision resolution worked
        shared_keywords = [kw for kw in provider.global_keyword_map.keys() 
                          if "общий" in kw or "shared" in kw]
        if shared_keywords:
            for keyword in shared_keywords:
                intents = provider.global_keyword_map[keyword]
                assert isinstance(intents, set), "Should use sets for collision resolution"
    
    @pytest.mark.asyncio
    async def test_language_detection_performance(self):
        """Test language detection performance with various text lengths"""
        config = {'confidence_threshold': 0.7}
        provider = HybridKeywordMatcherProvider(config)
        
        test_texts = [
            "короткий",  # Short Russian
            "short",     # Short English
            "средний текст на русском языке",  # Medium Russian
            "medium text in english language", # Medium English
            " ".join(["длинный"] * 50),  # Long Russian (50 words)
            " ".join(["long"] * 50)      # Long English (50 words)
        ]
        
        # Time language detection for different text lengths
        for text in test_texts:
            start_time = time.perf_counter()
            for _ in range(1000):
                provider._detect_language(text)
            detection_time = time.perf_counter() - start_time
            
            # Should be very fast regardless of text length
            assert detection_time < 0.1, f"Language detection too slow for '{text[:20]}...': {detection_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_memory_usage_with_large_datasets(self):
        """Test memory efficiency with large donation datasets"""
        import psutil
        import os
        
        config = {'confidence_threshold': 0.7, 'fuzzy_enabled': True}
        provider = HybridKeywordMatcherProvider(config)
        await provider._do_initialize()
        
        # Measure initial memory
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create large dataset
        large_donations = []
        for i in range(200):
            phrases = [f"фраза {i} {j}" for j in range(10)]  # 10 phrases per intent
            lemmas = [f"лемма_{i}_{j}" for j in range(5)]   # 5 lemmas per intent
            
            large_donations.append(KeywordDonation(
                intent=f"domain{i % 20}.action{i}",
                phrases=phrases,
                lemmas=lemmas,
                examples=[],
                parameters=[]
            ))
        
        # Load large dataset
        await provider._initialize_from_donations(large_donations)
        
        # Measure final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Should not use excessive memory (less than 100MB for 200 intents with 10 phrases each)
        assert memory_increase < 100, f"Memory usage too high: {memory_increase:.1f}MB increase"
        
        # Verify all donations were processed
        assert len(provider.exact_patterns) == 200
        assert len(provider.global_keyword_map) > 0


if __name__ == "__main__":
    # Run specific test categories
    pytest.main([__file__ + "::TestHybridKeywordMatcherPhase1", "-v"])
    pytest.main([__file__ + "::TestSpaCyProviderPhase1", "-v"]) 
    pytest.main([__file__ + "::TestCrossProviderConsistency", "-v"])
    pytest.main([__file__ + "::TestPerformanceAndStress", "-v"])
