"""
Test spaCy Asset Management Integration

Test suite for validating that spaCy providers properly integrate with 
the standard asset management system.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from typing import Dict, Any

from irene.providers.nlu.spacy_provider import SpaCyNLUProvider
from irene.intents.models import UnifiedConversationContext


class TestSpaCyAssetIntegration:
    """Test suite for spaCy asset management integration"""
    
    @pytest.fixture
    def mock_asset_manager(self):
        """Create mock asset manager"""
        manager = AsyncMock()
        
        # Mock ensure_model_available to return a test wheel path
        async def mock_ensure_model(provider_name, model_name, asset_config):
            if model_name in ['ru_core_news_sm', 'en_core_web_sm']:
                return Path(f"/tmp/test/{model_name}-3.7.0-py3-none-any.whl")
            return None
        
        manager.ensure_model_available = mock_ensure_model
        return manager
    
    @pytest.fixture
    def spacy_provider(self):
        """Create spaCy provider with test config"""
        config = {
            'model_name': 'ru_core_news_sm',
            'fallback_model': 'en_core_web_sm',
            'confidence_threshold': 0.7
        }
        return SpaCyNLUProvider(config)
    
    @pytest.fixture
    def sample_context(self):
        """Create sample conversation context"""
        return UnifiedConversationContext(
            session_id="test_session",
            language="ru"
        )
    
    def test_asset_config_methods(self, spacy_provider):
        """Test that spaCy provider has correct asset configuration methods"""
        # Test that asset configuration methods exist and return correct values
        assert hasattr(spacy_provider, 'get_asset_config')
        
        # Test default asset configuration
        asset_config = spacy_provider.get_asset_config()
        
        assert isinstance(asset_config, dict)
        assert asset_config['file_extension'] == '.whl'
        assert asset_config['directory_name'] == 'spacy'
        assert asset_config['cache_types'] == ['models', 'runtime']
        assert isinstance(asset_config['model_urls'], dict)
        
        print("✅ Asset configuration methods test passed!")
        print(f"   File extension: {asset_config['file_extension']}")
        print(f"   Directory: {asset_config['directory_name']}")
        print(f"   Available models: {list(asset_config['model_urls'].keys())}")
    
    def test_model_urls_updated(self, spacy_provider):
        """Test that model URLs are updated to new wheel format"""
        model_urls = spacy_provider._get_default_model_urls()
        
        # Check that we have the expected models
        expected_models = [
            'ru_core_news_sm', 'ru_core_news_md', 'ru_core_news_lg',
            'en_core_web_sm', 'en_core_web_md', 'en_core_web_lg'
        ]
        
        for model in expected_models:
            assert model in model_urls
            assert model_urls[model].endswith('.whl')
            assert '3.7.0' in model_urls[model]
        
        print("✅ Model URLs update test passed!")
        print(f"   Available models: {len(model_urls)} models")
        print(f"   Example URL: {model_urls['ru_core_news_sm']}")
    
    @pytest.mark.asyncio
    async def test_asset_manager_integration(self, spacy_provider, mock_asset_manager):
        """Test that spaCy provider integrates with asset manager"""
        # Set up asset manager
        spacy_provider.asset_manager = mock_asset_manager
        
        # Mock spacy module and pip installation
        mock_spacy = MagicMock()
        mock_nlp = MagicMock()
        mock_spacy.load.return_value = mock_nlp
        
        with patch('irene.utils.loader.safe_import', return_value=mock_spacy):
            with patch('subprocess.run') as mock_subprocess:
                # Mock successful pip install
                mock_subprocess.return_value.returncode = 0
                mock_subprocess.return_value.stderr = ""
                
                # Initialize with assets
                await spacy_provider._initialize_spacy_with_assets()
                
                # Verify asset manager was called
                mock_asset_manager.ensure_model_available.assert_called()
                call_args = mock_asset_manager.ensure_model_available.call_args
                
                assert call_args[1]['provider_name'] == 'spacy'
                assert call_args[1]['model_name'] == 'ru_core_news_sm'
                assert 'asset_config' in call_args[1]
                
                # Verify pip install was called
                mock_subprocess.assert_called()
                pip_call = mock_subprocess.call_args[0][0]
                assert 'pip' in pip_call
                assert 'install' in pip_call
                assert any('.whl' in arg for arg in pip_call)
                
                # Verify spaCy model was loaded
                mock_spacy.load.assert_called_with('ru_core_news_sm')
                assert spacy_provider.nlp is not None
        
        print("✅ Asset manager integration test passed!")
        print("   Asset manager called for model download")
        print("   Pip install called for wheel file")
        print("   spaCy model loaded successfully")
    
    @pytest.mark.asyncio
    async def test_fallback_model_with_assets(self, spacy_provider, mock_asset_manager):
        """Test fallback model handling with asset manager"""
        # Set up asset manager
        spacy_provider.asset_manager = mock_asset_manager
        
        # Mock spacy module
        mock_spacy = MagicMock()
        mock_nlp = MagicMock()
        
        # First load call fails, second succeeds (fallback)
        mock_spacy.load.side_effect = [OSError("Model not found"), mock_nlp]
        
        with patch('irene.utils.loader.safe_import', return_value=mock_spacy):
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value.returncode = 0
                mock_subprocess.return_value.stderr = ""
                
                # Initialize with assets
                await spacy_provider._initialize_spacy_with_assets()
                
                # Verify asset manager was called for both models
                assert mock_asset_manager.ensure_model_available.call_count == 2
                
                # Verify fallback model was loaded
                assert mock_spacy.load.call_count == 2
                mock_spacy.load.assert_any_call('ru_core_news_sm')  # Primary
                mock_spacy.load.assert_any_call('en_core_web_sm')   # Fallback
                
                assert spacy_provider.nlp is not None
        
        print("✅ Fallback model with assets test passed!")
        print("   Primary model failed as expected")
        print("   Fallback model loaded successfully")
        print("   Asset manager called for both models")
    
    @pytest.mark.asyncio
    async def test_asset_manager_failure_graceful_degradation(self, spacy_provider):
        """Test graceful degradation when asset manager fails"""
        # Create failing asset manager
        failing_manager = AsyncMock()
        failing_manager.ensure_model_available.side_effect = Exception("Asset download failed")
        spacy_provider.asset_manager = failing_manager
        
        # Mock spacy module to succeed with standard loading
        mock_spacy = MagicMock()
        mock_nlp = MagicMock()
        mock_spacy.load.return_value = mock_nlp
        
        with patch('irene.utils.loader.safe_import', return_value=mock_spacy):
            # Initialize with assets (should fall back gracefully)
            await spacy_provider._initialize_spacy_with_assets()
            
            # Verify it fell back to standard spaCy loading
            mock_spacy.load.assert_called_with('ru_core_news_sm')
            assert spacy_provider.nlp is not None
        
        print("✅ Asset manager failure graceful degradation test passed!")
        print("   Asset manager failed as expected")
        print("   Provider fell back to standard spaCy loading")
        print("   Model loaded successfully")
    
    def test_no_asset_manager_backwards_compatibility(self, spacy_provider):
        """Test that provider works without asset manager (backwards compatibility)"""
        # Don't set asset manager (should be None)
        assert spacy_provider.asset_manager is None
        
        # Mock spacy module
        mock_spacy = MagicMock()
        mock_nlp = MagicMock()
        mock_spacy.load.return_value = mock_nlp
        
        with patch('irene.utils.loader.safe_import', return_value=mock_spacy):
            # This should call the old _initialize_spacy method
            asyncio.run(spacy_provider._initialize_spacy())
            
            # Verify standard spaCy loading was used
            mock_spacy.load.assert_called_with('ru_core_news_sm')
            assert spacy_provider.nlp is not None
        
        print("✅ Backwards compatibility test passed!")
        print("   Provider works without asset manager")
        print("   Uses standard spaCy loading")


def run_simple_spacy_asset_test():
    """
    Simple test function that can be run independently to validate 
    basic spaCy asset management integration for Phase 3.
    """
    print("🧪 Running simple spaCy asset management test...")
    
    # Test asset configuration
    config = {'model_name': 'ru_core_news_sm'}
    provider = SpaCyNLUProvider(config)
    
    # Test asset config
    asset_config = provider.get_asset_config()
    
    assert asset_config['file_extension'] == '.whl'
    assert asset_config['directory_name'] == 'spacy'
    assert 'ru_core_news_sm' in asset_config['model_urls']
    assert asset_config['model_urls']['ru_core_news_sm'].endswith('.whl')
    
    print("✅ Asset configuration test passed!")
    print(f"   File extension: {asset_config['file_extension']}")
    print(f"   Directory: {asset_config['directory_name']}")
    print(f"   Model URL format: {asset_config['model_urls']['ru_core_news_sm'][-20:]}")
    
    # Test model URL format
    model_urls = provider._get_default_model_urls()
    for model_name, url in model_urls.items():
        assert url.endswith('.whl'), f"Model {model_name} URL should end with .whl"
        assert '3.7.0' in url, f"Model {model_name} should use version 3.7.0"
    
    print("✅ Model URL format test passed!")
    print(f"   Available models: {len(model_urls)}")
    
    # Test inheritance and method availability  
    assert hasattr(provider, '_install_spacy_model')
    assert hasattr(provider, '_initialize_spacy_with_assets')
    assert callable(provider.get_asset_config)
    
    print("✅ Method availability test passed!")
    print("   Asset management methods available")
    print("   Installation methods available")
    
    print("🎉 Phase 3 spaCy asset management integration is working correctly!")


if __name__ == "__main__":
    # Run simple test
    run_simple_spacy_asset_test() 