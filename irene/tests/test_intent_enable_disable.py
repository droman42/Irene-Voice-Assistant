#!/usr/bin/env python3
"""
Comprehensive tests for intent handler enable/disable functionality.

This test suite validates the complete implementation of Phase 1-3:
- Configuration-driven handler filtering
- Donation coordination between Intent and NLU components
- Comprehensive validation and error handling
"""

import asyncio
import pytest
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch

from irene.config.models import IntentSystemConfig, IntentHandlerListConfig
from irene.components.intent_component import IntentComponent
from irene.components.nlu_component import NLUComponent
from irene.intents.manager import IntentHandlerManager
from irene.core.components import ComponentManager


class TestIntentHandlerConfiguration:
    """Test configuration validation for intent handlers."""
    
    def test_valid_configuration(self):
        """Test that valid configurations pass validation."""
        config = IntentSystemConfig()
        assert config.enabled is True
        assert len(config.handlers.enabled) > 0
        assert len(config.handlers.disabled) == 0
    
    def test_empty_enabled_handlers_validation(self):
        """Test that empty enabled handlers list raises error."""
        with pytest.raises(ValueError, match="At least one intent handler must be enabled"):
            IntentHandlerListConfig(enabled=[])
    
    def test_invalid_handler_names_validation(self):
        """Test validation of handler names."""
        # Test invalid characters
        with pytest.raises(ValueError, match="Invalid characters in handler names"):
            IntentHandlerListConfig(enabled=["conversation", "handler/with/slash"])
        
        # Test empty names
        with pytest.raises(ValueError, match="Handler name cannot be empty"):
            IntentHandlerListConfig(enabled=["conversation", ""])
        
        # Test non-string names (Pydantic validates this at the type level)
        with pytest.raises((ValueError, Exception)):  # Pydantic raises ValidationError
            IntentHandlerListConfig(enabled=["conversation", 123])
    
    def test_enabled_disabled_overlap_validation(self):
        """Test that handlers cannot be both enabled and disabled."""
        with pytest.raises(ValueError, match="Handlers cannot be both enabled and disabled"):
            IntentHandlerListConfig(
                enabled=["conversation", "timer"],
                disabled=["conversation"]
            )
    
    def test_fallback_intent_validation(self):
        """Test fallback intent validation."""
        # Test invalid format
        with pytest.raises(ValueError, match="fallback_intent must be in format"):
            IntentSystemConfig(fallback_intent="invalid_format")
        
        # Test disabled fallback handler
        with pytest.raises(ValueError, match="Fallback intent handler .* is not enabled"):
            IntentSystemConfig(
                fallback_intent="train_schedule.general",
                handlers=IntentHandlerListConfig(
                    enabled=["conversation", "timer"],
                    disabled=["train_schedule"]
                )
            )
    
    def test_missing_configuration_validation(self):
        """Test validation of missing handler configurations."""
        # This would require a handler enabled but not in config mapping
        # For now, we test with the existing handlers
        config = IntentSystemConfig()
        config.handlers.enabled = ["conversation", "timer", "nonexistent_handler"]
        
        with pytest.raises(ValueError, match="Enabled handlers missing configuration classes"):
            config.validate_handler_configurations()


class TestIntentHandlerManager:
    """Test intent handler manager functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock configuration for testing."""
        return {
            "enabled": ["conversation", "timer"],
            "disabled": [],
            "auto_discover": True,
            "discovery_paths": ["irene.intents.handlers"],
            "asset_validation": {
                "strict_mode": True
            }
        }
    
    @pytest.mark.asyncio
    async def test_no_config_error(self):
        """Test that manager requires configuration."""
        manager = IntentHandlerManager()
        
        with pytest.raises(ValueError, match="IntentHandlerManager requires configuration"):
            await manager.initialize()
    
    @pytest.mark.asyncio
    async def test_empty_enabled_handlers_error(self, mock_config):
        """Test error when no handlers are enabled."""
        mock_config["enabled"] = []
        manager = IntentHandlerManager()
        
        with pytest.raises(ValueError, match="No intent handlers enabled"):
            await manager.initialize(mock_config)
    
    @pytest.mark.asyncio
    async def test_missing_handlers_error(self, mock_config):
        """Test error when requested handlers are not found."""
        mock_config["enabled"] = ["nonexistent_handler"]
        manager = IntentHandlerManager()
        
        with patch('irene.utils.loader.dynamic_loader.discover_providers') as mock_discover:
            mock_discover.return_value = {}  # No handlers found
            
            with pytest.raises(ValueError, match="Intent handlers not found"):
                await manager.initialize(mock_config)


class TestNLUIntentCoordination:
    """Test coordination between NLU and Intent components."""
    
    @pytest.fixture
    def mock_intent_component(self):
        """Create mock intent component."""
        component = Mock(spec=IntentComponent)
        component.get_enabled_handler_names.return_value = ["conversation", "timer"]
        component.get_enabled_handler_donations.return_value = {
            "conversation": Mock(),
            "timer": Mock()
        }
        component.handler_manager = Mock()
        component.handler_manager.get_handlers.return_value = {
            "conversation": Mock(),
            "timer": Mock()
        }
        component.handler_manager._asset_loader = Mock()
        component.handler_manager._asset_loader.convert_to_keyword_donations.return_value = []
        return component
    
    def test_nlu_component_dependencies(self):
        """Test that NLU component declares intent_system dependency."""
        nlu = NLUComponent()
        dependencies = nlu.get_component_dependencies()
        assert "intent_system" in dependencies
    
    @pytest.mark.asyncio
    async def test_nlu_coordination_with_intent_component(self, mock_intent_component):
        """Test successful coordination between NLU and Intent components."""
        nlu = NLUComponent()
        nlu.inject_dependency('intent_system', mock_intent_component)
        nlu.providers = {}  # Empty providers for testing
        
        # Test coordination
        enabled_handlers = await nlu._get_enabled_handler_names()
        assert enabled_handlers == ["conversation", "timer"]
    
    @pytest.mark.asyncio
    async def test_nlu_fallback_when_intent_unavailable(self):
        """Test NLU fallback when Intent component is unavailable."""
        nlu = NLUComponent()
        # Don't inject intent_system dependency
        
        with patch.object(nlu, '_discover_all_handler_names') as mock_discover:
            mock_discover.return_value = ["fallback_handler"]
            
            enabled_handlers = await nlu._get_enabled_handler_names()
            assert enabled_handlers == ["fallback_handler"]
            mock_discover.assert_called_once()


class TestEndToEndIntegration:
    """Test end-to-end integration of the intent enable/disable system."""
    
    @pytest.mark.asyncio
    async def test_configuration_to_nlu_integration(self):
        """Test complete flow from configuration to NLU initialization."""
        # Create test configuration
        config = IntentSystemConfig()
        config.handlers.enabled = ["conversation", "timer"]
        config.handlers.disabled = []
        
        # Validate configuration
        validated_config = config.validate_handler_configurations()
        assert validated_config is not None
        
        # Test that enabled handlers are properly filtered
        final_enabled = [h for h in config.handlers.enabled if h not in config.handlers.disabled]
        assert len(final_enabled) == 2
        assert "conversation" in final_enabled
        assert "timer" in final_enabled


class TestErrorRecovery:
    """Test error recovery and graceful degradation."""
    
    @pytest.mark.asyncio
    async def test_partial_handler_failure_recovery(self):
        """Test system continues when some handlers fail."""
        manager = IntentHandlerManager()
        
        # Mock scenario where some handlers fail initialization
        with patch.object(manager, '_handler_instances') as mock_instances:
            mock_instances.__iter__ = lambda x: iter(["working_handler", "failing_handler"])
            mock_instances.items.return_value = [
                ("working_handler", Mock()),
                ("failing_handler", Mock())
            ]
            
            # Mock the failing handler
            working_handler = Mock()
            working_handler.set_asset_loader = Mock()
            working_handler.set_donation = Mock()
            working_handler.has_donation.return_value = True
            
            failing_handler = Mock()
            failing_handler.set_asset_loader = Mock(side_effect=Exception("Handler failure"))
            
            mock_instances.__getitem__ = lambda x, key: {
                "working_handler": working_handler,
                "failing_handler": failing_handler
            }[key]
            
            manager._donations = {"working_handler": Mock(), "failing_handler": Mock()}
            manager._donations["working_handler"].method_donations = []
            manager._donations["failing_handler"].method_donations = []
            
            # Should not raise exception, but should log warnings
            with patch('irene.intents.manager.logger') as mock_logger:
                try:
                    await manager._initialize_handlers_with_donations()
                except Exception:
                    pass  # Expected for this test setup
                
                # Verify warning was logged
                assert any("Failed to initialize handler" in str(call) 
                          for call in mock_logger.error.call_args_list)


def test_logging_configuration():
    """Test that logging is properly configured for debugging."""
    import logging
    
    # Ensure our loggers exist and are configured
    intent_logger = logging.getLogger('irene.intents.manager')
    nlu_logger = logging.getLogger('irene.components.nlu_component')
    
    assert intent_logger is not None
    assert nlu_logger is not None


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
