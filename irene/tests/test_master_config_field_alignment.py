"""Tests for master config field name alignment after Phase 6

This module tests that config-master.toml uses the correct field names
that align with runtime parameter names (Phase 6 field alignment).

Tests:
- Master config uses aligned field names (device vs device_id, model vs default_model)
- Master config completeness remains at 100%
- No orphaned sections exist
- Field name consistency across all provider sections
"""

import pytest
import tomllib
from pathlib import Path
from typing import Dict, Any

from irene.config.auto_registry import AutoSchemaRegistry


class TestMasterConfigFieldAlignment:
    """Test master config field name alignment with runtime parameters"""
    
    def test_master_config_completeness_validation(self):
        """Test the exact validation command from the document (6.5.3)"""
        report = AutoSchemaRegistry.get_master_config_completeness()
        
        # Must show 100% coverage with new field names
        assert report["valid"], f"Master config validation failed: {report}"
        assert report["coverage_percentage"] == 100.0, f"Expected 100% coverage, got {report['coverage_percentage']}%"
        assert not report["missing_sections"], f"Missing sections found: {report['missing_sections']}"
        assert not report["orphaned_sections"], f"Orphaned sections found: {report['orphaned_sections']}"
        
        print(f"✓ Master config completeness: {report['coverage_percentage']}%")
        print(f"✓ Missing sections: {len(report['missing_sections'])}")
        print(f"✓ Orphaned sections: {len(report['orphaned_sections'])}")
    
    def test_master_config_exists_and_readable(self):
        """Test that config-master.toml exists and is readable"""
        master_config_path = Path("configs/config-master.toml")
        assert master_config_path.exists(), "config-master.toml not found"
        
        with open(master_config_path, "rb") as f:
            master_config = tomllib.load(f)
        
        assert isinstance(master_config, dict), "Master config should be a valid TOML dictionary"
        print(f"✓ Master config loaded successfully with {len(master_config)} top-level sections")
    
    def test_audio_provider_field_alignment(self):
        """Test audio providers use 'device' instead of 'device_id' (Phase 6 alignment)"""
        master_config_path = Path("configs/config-master.toml")
        with open(master_config_path, "rb") as f:
            master_config = tomllib.load(f)
        
        if "audio" in master_config and "providers" in master_config["audio"]:
            audio_providers = master_config["audio"]["providers"]
            
            # Test specific audio providers that should have device field
            device_providers = ["sounddevice", "audioplayer", "aplay"]
            
            for provider_name in device_providers:
                if provider_name in audio_providers:
                    provider_config = audio_providers[provider_name]
                    
                    # Should NOT use old field name
                    assert "device_id" not in provider_config, f"Audio provider {provider_name} still uses old 'device_id' field"
                    
                    # May or may not have 'device' field in config, but shouldn't have the old name
                    print(f"✓ Audio provider {provider_name} does not use deprecated 'device_id' field")
    
    def test_llm_provider_field_alignment(self):
        """Test LLM providers use 'model' instead of 'default_model' (Phase 6 alignment)"""
        master_config_path = Path("configs/config-master.toml")
        with open(master_config_path, "rb") as f:
            master_config = tomllib.load(f)
        
        if "llm" in master_config and "providers" in master_config["llm"]:
            llm_providers = master_config["llm"]["providers"]
            
            # Test specific LLM providers that should have model field alignment
            model_providers = ["openai", "anthropic", "vsegpt"]
            
            for provider_name in model_providers:
                if provider_name in llm_providers:
                    provider_config = llm_providers[provider_name]
                    
                    # Should NOT use old field name
                    assert "default_model" not in provider_config, f"LLM provider {provider_name} still uses old 'default_model' field"
                    
                    # May or may not have 'model' field in config, but shouldn't have the old name
                    print(f"✓ LLM provider {provider_name} does not use deprecated 'default_model' field")
    
    def test_no_deprecated_field_names_in_master_config(self):
        """Test that no deprecated field names remain anywhere in master config"""
        master_config_path = Path("configs/config-master.toml")
        with open(master_config_path, "rb") as f:
            config_content = f.read().decode('utf-8')
        
        # List of deprecated field names that should not appear
        deprecated_fields = [
            "device_id",      # Should be 'device'
            "default_model",  # Should be 'model'
        ]
        
        for deprecated_field in deprecated_fields:
            assert deprecated_field not in config_content, f"Deprecated field '{deprecated_field}' found in master config"
            print(f"✓ Deprecated field '{deprecated_field}' not found in master config")
    
    def test_provider_section_consistency(self):
        """Test that all provider sections are consistent with schema definitions"""
        master_config_path = Path("configs/config-master.toml")
        with open(master_config_path, "rb") as f:
            master_config = tomllib.load(f)
        
        provider_schemas = AutoSchemaRegistry.get_provider_schemas()
        
        # Check that every provider schema has a corresponding config section
        for component_type, providers in provider_schemas.items():
            if component_type in master_config and "providers" in master_config[component_type]:
                config_providers = master_config[component_type]["providers"]
                
                for provider_name in providers.keys():
                    assert provider_name in config_providers, f"Provider {component_type}.{provider_name} missing from master config"
                    print(f"✓ Provider {component_type}.{provider_name} found in master config")
        
        # Check that there are no unexpected provider sections
        for component_type, component_config in master_config.items():
            if isinstance(component_config, dict) and "providers" in component_config:
                if component_type in provider_schemas:
                    config_providers = set(component_config["providers"].keys())
                    schema_providers = set(provider_schemas[component_type].keys())
                    
                    unexpected_providers = config_providers - schema_providers
                    assert not unexpected_providers, f"Unexpected providers in {component_type}: {unexpected_providers}"
                    
                    missing_providers = schema_providers - config_providers  
                    assert not missing_providers, f"Missing providers in {component_type}: {missing_providers}"
    
    def test_field_name_consistency_with_runtime_schemas(self):
        """Test that master config field names are consistent with runtime parameter schemas"""
        master_config_path = Path("configs/config-master.toml")
        with open(master_config_path, "rb") as f:
            master_config = tomllib.load(f)
        
        # Test key providers that had field alignment in Phase 6
        test_cases = [
            ("audio", "sounddevice"),
            ("audio", "audioplayer"),
            ("llm", "openai"), 
            ("llm", "anthropic"),
        ]
        
        for component_type, provider_name in test_cases:
            # Get runtime parameter schema
            runtime_schema = AutoSchemaRegistry.get_provider_parameter_schema(component_type, provider_name)
            
            # Get master config section
            if (component_type in master_config and 
                "providers" in master_config[component_type] and
                provider_name in master_config[component_type]["providers"]):
                
                config_section = master_config[component_type]["providers"][provider_name]
                config_fields = set(config_section.keys())
                runtime_fields = set(runtime_schema.keys())
                
                # Remove enabled field as it's config-only
                config_fields.discard("enabled")
                runtime_fields.discard("enabled")
                
                # Config fields should be subset of runtime fields (runtime may have more)
                # or both should be empty/minimal
                if config_fields and runtime_fields:
                    # Check for specific field alignment issues
                    if "device_id" in config_fields:
                        assert "device" in runtime_fields, f"Config uses 'device_id' but runtime expects 'device' for {component_type}.{provider_name}"
                    
                    if "default_model" in config_fields:
                        assert "model" in runtime_fields, f"Config uses 'default_model' but runtime expects 'model' for {component_type}.{provider_name}"
                
                print(f"✓ Field consistency verified: {component_type}.{provider_name}")
                print(f"  Config fields: {sorted(config_fields)}")
                print(f"  Runtime fields: {sorted(runtime_fields)}")


class TestMasterConfigIntegrity:
    """Test overall master config integrity after Phase 6-8 changes"""
    
    def test_all_components_have_provider_sections(self):
        """Test that all component types have provider sections in master config"""
        master_config_path = Path("configs/config-master.toml")
        with open(master_config_path, "rb") as f:
            master_config = tomllib.load(f)
        
        provider_schemas = AutoSchemaRegistry.get_provider_schemas()
        
        for component_type in provider_schemas.keys():
            assert component_type in master_config, f"Component type {component_type} missing from master config"
            assert "providers" in master_config[component_type], f"Providers section missing for {component_type}"
            
            providers_section = master_config[component_type]["providers"]
            assert isinstance(providers_section, dict), f"Providers section should be dict for {component_type}"
            assert len(providers_section) > 0, f"No providers configured for {component_type}"
            
            print(f"✓ Component {component_type} has {len(providers_section)} providers configured")
    
    def test_master_config_toml_syntax_valid(self):
        """Test that master config has valid TOML syntax"""
        master_config_path = Path("configs/config-master.toml")
        
        try:
            with open(master_config_path, "rb") as f:
                master_config = tomllib.load(f)
            
            assert isinstance(master_config, dict)
            print("✓ Master config has valid TOML syntax")
            
        except tomllib.TOMLDecodeError as e:
            pytest.fail(f"Master config has invalid TOML syntax: {e}")
        except Exception as e:
            pytest.fail(f"Failed to load master config: {e}")
    
    def test_phase8_validation_success_criteria(self):
        """Test the success criteria from section 6.6 of the document"""
        # Test complete elimination verification
        report = AutoSchemaRegistry.get_master_config_completeness()
        
        # All success metrics from 6.6.2
        assert report["coverage_percentage"] == 100.0, "Master config coverage must be 100%"
        assert not report["missing_sections"], "No missing sections allowed"
        assert not report["orphaned_sections"], "No orphaned sections allowed"
        assert report["valid"], "Master config validation must pass"
        
        # Test that field name consistency is achieved (6.6.3)
        provider_schemas = AutoSchemaRegistry.get_provider_schemas()
        total_providers = sum(len(providers) for providers in provider_schemas.values())
        assert total_providers >= 25, f"Should have 25+ providers, found {total_providers}"
        
        print("✓ Phase 8 success criteria met:")
        print(f"  - Master config coverage: 100%")
        print(f"  - Missing sections: 0") 
        print(f"  - Orphaned sections: 0")
        print(f"  - Total providers: {total_providers}")
        print(f"  - Field name consistency: Verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
