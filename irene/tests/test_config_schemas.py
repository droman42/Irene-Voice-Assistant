"""Tests for configuration schema synchronization

This module tests the Phase 2 implementation of configuration schema
synchronization and auto-generation functionality.

Tests:
- Schema synchronization across all registries
- Component schema coverage completeness
- Auto-generated registry functionality
- Configuration widget generation for all sections
- Schema validation report generation
"""

import pytest
import inspect
from typing import Type
from pydantic import BaseModel

from irene.config.auto_registry import AutoSchemaRegistry
from irene.config.models import CoreConfig, ComponentConfig


class TestSchemaSync:
    """Test schema synchronization across all registries"""
    
    def test_section_models_completeness(self):
        """Verify all CoreConfig fields have corresponding section models"""
        section_models = AutoSchemaRegistry.get_section_models()
        core_config_fields = set(CoreConfig.model_fields.keys())
        
        expected_sections = set()
        for field_name, field_info in CoreConfig.model_fields.items():
            if hasattr(field_info, 'annotation'):
                annotation = field_info.annotation
                if (inspect.isclass(annotation) and 
                    issubclass(annotation, BaseModel) and 
                    annotation != BaseModel):
                    expected_sections.add(field_name)
        
        section_model_fields = set(section_models.keys())
        
        missing_sections = expected_sections - section_model_fields
        assert not missing_sections, f"Missing section models: {missing_sections}"
        
        extra_sections = section_model_fields - expected_sections
        assert not extra_sections, f"Extra section models: {extra_sections}"
    
    def test_component_schema_coverage(self):
        """Verify all components have corresponding schemas"""
        component_schemas = AutoSchemaRegistry.get_component_schemas()
        component_fields = set(ComponentConfig.model_fields.keys())
        schema_fields = set(component_schemas.keys())
        
        missing_schemas = component_fields - schema_fields
        assert not missing_schemas, f"Components without schemas: {missing_schemas}"
    
    def test_no_manual_sync_required(self):
        """Verify auto-generated registries work correctly"""
        section_models = AutoSchemaRegistry.get_section_models()
        
        # Verify critical sections are auto-discovered
        assert "vad" in section_models, "VADConfig should be auto-discovered"
        assert "monitoring" in section_models, "MonitoringConfig should be auto-discovered"
        assert "nlu_analysis" in section_models, "NLUAnalysisConfig should be auto-discovered"
    
    def test_schema_validation_report(self):
        """Verify schema validation report generation"""
        report = AutoSchemaRegistry.validate_schema_coverage()
        
        assert isinstance(report, dict)
        assert "valid" in report
        assert "warnings" in report
        assert "errors" in report
        assert "recommendations" in report
        
        # After Phase 2, schema validation should pass
        assert report["valid"], f"Schema validation failed: {report}"


class TestConfigurationWidgetGeneration:
    """Test configuration widget generation for all sections"""
    
    def test_widget_generation_coverage(self):
        """Verify widgets can be generated for all configuration sections"""
        from irene.components.configuration_component import ConfigurationComponent
        
        config_component = ConfigurationComponent()
        section_models = AutoSchemaRegistry.get_section_models()
        
        for section_name in section_models.keys():
            model = config_component._get_section_model(section_name)
            assert model is not None, f"Widget generation failed for: {section_name}"
    
    def test_schema_extraction(self):
        """Verify schema extraction works for all sections"""
        from irene.components.configuration_component import ConfigurationComponent
        
        config_component = ConfigurationComponent()
        schema = config_component._extract_config_schema()
        
        assert isinstance(schema, dict)
        assert len(schema) > 0, "Schema extraction returned empty result"
        
        # Verify critical sections are present
        required_sections = ["system", "vad", "monitoring", "nlu_analysis"]
        for section in required_sections:
            assert section in schema, f"Required section missing: {section}"


class TestComponentSchemas:
    """Test specific component schema functionality"""
    
    def test_new_component_schemas_exist(self):
        """Verify that the new component schemas were created"""
        from irene.config.schemas import (
            MonitoringComponentSchema, 
            NLUAnalysisComponentSchema, 
            ConfigurationComponentSchema
        )
        
        # Test schema instantiation
        monitoring_schema = MonitoringComponentSchema()
        assert monitoring_schema.enabled is True
        assert monitoring_schema.metrics_enabled is True
        assert monitoring_schema.dashboard_enabled is True
        
        nlu_analysis_schema = NLUAnalysisComponentSchema()
        assert nlu_analysis_schema.enabled is True
        assert nlu_analysis_schema.conflict_detection_enabled is True
        assert nlu_analysis_schema.performance_analysis_enabled is True
        
        config_schema = ConfigurationComponentSchema()
        assert config_schema.enabled is False  # Disabled by default
        assert config_schema.web_api_enabled is True
        assert config_schema.hot_reload_enabled is True
    
    # NOTE: test_component_schemas_in_registry removed in Phase 4.4.5 
    # Manual COMPONENT_SCHEMAS registry eliminated - only auto-discovery remains
    
    def test_component_schemas_auto_discovery(self):
        """Verify new component schemas are auto-discovered"""
        component_schemas = AutoSchemaRegistry.get_component_schemas()
        
        # Test that new schemas are auto-discovered
        assert "monitoring" in component_schemas
        assert "nlu_analysis" in component_schemas
        assert "configuration" in component_schemas
    
    def test_component_validation(self):
        """Test component configuration validation"""
        from irene.config.schemas import SchemaValidator
        
        # Test valid configuration
        valid_config = {
            "enabled": True,
            "default_provider": "console",
            "fallback_providers": ["console"],
            "metrics_enabled": True,
            "dashboard_enabled": False
        }
        
        assert SchemaValidator.validate_component_config("monitoring", valid_config)
        
        # Test invalid configuration
        invalid_config = {
            "enabled": "not_a_boolean",  # Invalid type
            "metrics_enabled": True
        }
        
        assert not SchemaValidator.validate_component_config("monitoring", invalid_config)


class TestAutoRegistryIntegration:
    """Test auto-registry integration with SchemaValidator"""
    
    def test_get_component_schemas_method(self):
        """Test SchemaValidator.get_component_schemas() uses auto-registry"""
        from irene.config.schemas import SchemaValidator
        
        auto_schemas = AutoSchemaRegistry.get_component_schemas()
        validator_schemas = SchemaValidator.get_component_schemas()
        
        # Should be identical
        assert auto_schemas.keys() == validator_schemas.keys()
        
        # Should include all new schemas
        assert "monitoring" in validator_schemas
        assert "nlu_analysis" in validator_schemas
        assert "configuration" in validator_schemas
    
    def test_validate_component_config_uses_auto_registry(self):
        """Test that component validation uses auto-generated schemas"""
        from irene.config.schemas import SchemaValidator
        
        # This should work for the new schemas
        test_config = {
            "enabled": True,
            "default_provider": "console",
            "fallback_providers": ["console"],
            "web_api_enabled": True,
            "hot_reload_enabled": False
        }
        
        # Should validate using auto-discovered schema
        assert SchemaValidator.validate_component_config("configuration", test_config)


class TestMasterConfigCompleteness:
    """Test master configuration completeness validation"""
    
    def test_master_config_coverage_reporting(self):
        """Test master config completeness reporting"""
        report = AutoSchemaRegistry.get_master_config_completeness()
        
        assert isinstance(report, dict)
        assert "missing_sections" in report
        assert "orphaned_sections" in report
        assert "coverage_percentage" in report
        assert "valid" in report
        
        # Coverage should be a valid percentage
        assert 0 <= report["coverage_percentage"] <= 100
    
    def test_schema_coverage_after_phase2(self):
        """Test that schema coverage improves after Phase 2"""
        report = AutoSchemaRegistry.validate_schema_coverage()
        
        # After Phase 2, component schema coverage should be complete
        assert report["valid"], f"Schema validation should pass after Phase 2: {report}"
        
        # Should not have component schema errors anymore
        for error in report.get("errors", []):
            assert "Components without schemas" not in error, f"Component schema error still exists: {error}"


if __name__ == "__main__":
    pytest.main([__file__])
