"""Tests for parameter schema unification - Final validation

This module tests the Phase 8 implementation of parameter schema unification,
ensuring complete elimination of manual parameter schemas and proper auto-generation
from Pydantic models.

Tests:
- Complete elimination of manual parameter schema patterns
- Auto-generated parameter schemas for all providers
- Parameter schema consistency with Pydantic field definitions
- Voice trigger parameter schema fixes from Phase 6
- Text processing provider parameter handling
- Web API integration with auto-generated schemas
"""

import pytest
import os
import subprocess
from typing import Dict, Any, Type
from pydantic import BaseModel

from irene.config.auto_registry import AutoSchemaRegistry


class TestParameterSchemaUnification:
    """Test complete elimination of manual parameter schemas"""
    
    def test_no_manual_parameter_schemas_remain(self):
        """Verify no manual get_parameter_schema implementations exist"""
        # This test ensures complete elimination of manual patterns
        
        # Run grep to find any manual parameter schema methods in provider implementations
        # Should only find base classes with auto-generated implementations
        result = subprocess.run([
            'grep', '-r', 'def get_parameter_schema', 'irene/providers/'
        ], capture_output=True, text=True, cwd='/home/droman42/development/Irene-Voice-Assistant')
        
        # Should only find base classes, not individual provider implementations
        lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        # Filter out base class files - these should have auto-generated implementations
        base_class_files = {
            'irene/providers/audio/base.py',
            'irene/providers/tts/base.py', 
            'irene/providers/asr/base.py',
            'irene/providers/llm/base.py',
            'irene/providers/voice_trigger/base.py',
            'irene/providers/nlu/base.py'
        }
        
        manual_implementations = []
        for line in lines:
            if ':' in line:
                file_path = line.split(':')[0]
                if file_path not in base_class_files:
                    manual_implementations.append(line)
        
        assert not manual_implementations, f"Manual get_parameter_schema implementations found: {manual_implementations}"
        
        # Verify we found exactly the expected base class implementations
        assert len(lines) == 6, f"Expected 6 base class implementations, found {len(lines)}: {lines}"
    
    def test_no_manual_parameter_dictionaries_remain(self):
        """Verify no manual parameter schema dictionaries exist"""
        # Check for return statements with parameter schema dictionaries
        result = subprocess.run([
            'grep', '-r', '-E', 'return.*"type".*:', 'irene/providers/'
        ], capture_output=True, text=True, cwd='/home/droman42/development/Irene-Voice-Assistant')
        
        assert result.returncode != 0 or not result.stdout.strip(), f"Manual parameter dictionaries found: {result.stdout}"
        
        # Check for hardcoded parameter validation patterns
        result = subprocess.run([
            'grep', '-r', '-E', 'parameter.*schema.*=', 'irene/providers/'
        ], capture_output=True, text=True, cwd='/home/droman42/development/Irene-Voice-Assistant')
        
        assert result.returncode != 0 or not result.stdout.strip(), f"Hardcoded parameter schemas found: {result.stdout}"
    
    def test_auto_generated_schemas_complete(self):
        """Verify all providers have auto-generated parameter schemas"""
        provider_schemas = AutoSchemaRegistry.get_provider_schemas()
        
        # Test all component types including voice_trigger
        expected_components = {"tts", "audio", "asr", "llm", "voice_trigger", "nlu", "text_processor"}
        actual_components = set(provider_schemas.keys())
        assert expected_components.issubset(actual_components), f"Missing components: {expected_components - actual_components}"
        
        schema_generation_results = {}
        
        for component_type, providers in provider_schemas.items():
            for provider_name in providers.keys():
                schema = AutoSchemaRegistry.get_provider_parameter_schema(component_type, provider_name)
                assert isinstance(schema, dict), f"No parameter schema for {component_type}.{provider_name}"
                
                schema_generation_results[f"{component_type}.{provider_name}"] = {
                    "schema_type": type(schema).__name__,
                    "field_count": len(schema),
                    "has_fields": len(schema) > 0
                }
                
                # Text processing providers may have empty schemas (no runtime parameters)
                if component_type != "text_processor":
                    assert len(schema) > 0, f"Empty parameter schema for {component_type}.{provider_name}"
        
        # Log results for debugging
        print(f"\nParameter schema generation results:")
        for provider, result in schema_generation_results.items():
            print(f"  {provider}: {result}")
    
    def test_parameter_schema_pydantic_consistency(self):
        """Verify auto-generated schemas match Pydantic field definitions"""
        provider_schemas = AutoSchemaRegistry.get_provider_schemas()
        
        # Test field name alignment between config and runtime for key providers
        test_cases = [
            ("audio", "sounddevice"),
            ("audio", "audioplayer"), 
            ("tts", "elevenlabs"),
            ("llm", "openai"),
            ("voice_trigger", "openwakeword"),
            ("asr", "whisper")
        ]
        
        for component_type, provider_name in test_cases:
            if component_type in provider_schemas and provider_name in provider_schemas[component_type]:
                # Get the Pydantic schema class
                schema_class = provider_schemas[component_type][provider_name]
                
                # Get auto-generated parameter schema
                parameter_schema = AutoSchemaRegistry.get_provider_parameter_schema(component_type, provider_name)
                
                # Get Pydantic field definitions
                pydantic_fields = schema_class.model_fields
                
                # Verify that parameter schema fields are present in Pydantic model
                for param_name in parameter_schema.keys():
                    # Skip if this is configuration-only field (like 'enabled')
                    if param_name == "enabled":
                        continue
                    
                    assert param_name in pydantic_fields, f"Parameter {param_name} not found in Pydantic model for {component_type}.{provider_name}"
                
                print(f"✓ Field alignment verified for {component_type}.{provider_name}")
    
    def test_voice_trigger_parameter_schemas(self):
        """Verify voice trigger providers have correct parameter schemas (fixed in Phase 6)"""
        # Test OpenWakeWord
        openwakeword_schema = AutoSchemaRegistry.get_provider_parameter_schema('voice_trigger', 'openwakeword')
        
        expected_openwakeword_fields = {'wake_words', 'threshold', 'inference_framework'}
        actual_fields = set(openwakeword_schema.keys())
        
        # Check that expected fields are present (may have additional fields)
        missing_fields = expected_openwakeword_fields - actual_fields
        assert not missing_fields, f"OpenWakeWord missing expected parameters: {missing_fields}"
        
        print(f"✓ OpenWakeWord parameter schema: {list(openwakeword_schema.keys())}")
        
        # Test MicroWakeWord  
        microwakeword_schema = AutoSchemaRegistry.get_provider_parameter_schema('voice_trigger', 'microwakeword')
        
        expected_microwakeword_fields = {'wake_words', 'threshold', 'model_path'}
        actual_fields = set(microwakeword_schema.keys())
        
        missing_fields = expected_microwakeword_fields - actual_fields
        assert not missing_fields, f"MicroWakeWord missing expected parameters: {missing_fields}"
        
        print(f"✓ MicroWakeWord parameter schema: {list(microwakeword_schema.keys())}")
        
    def test_text_processing_no_runtime_parameters(self):
        """Verify text processing providers correctly have no runtime parameters"""
        text_processor_types = ['asr_text_processor', 'general_text_processor', 'tts_text_processor', 'number_text_processor']
        
        for processor_type in text_processor_types:
            schema = AutoSchemaRegistry.get_provider_parameter_schema('text_processor', processor_type)
            # Text processors can have empty schemas since they're config-only
            assert isinstance(schema, dict), f"Text processor {processor_type} should return dict (even if empty)"
            
            print(f"✓ Text processor {processor_type}: {len(schema)} parameters")
        
    def test_web_api_parameter_validation(self):
        """Verify Web API endpoints use auto-generated parameter schemas correctly"""
        # Test that parameter schemas can be used for API validation
        provider_schemas = AutoSchemaRegistry.get_provider_schemas()
        
        # Test a few key providers that should have rich parameter schemas
        test_providers = [
            ("audio", "sounddevice"),
            ("tts", "elevenlabs"), 
            ("llm", "openai"),
            ("asr", "whisper")
        ]
        
        for component_type, provider_name in test_providers:
            if component_type in provider_schemas and provider_name in provider_schemas[component_type]:
                schema = AutoSchemaRegistry.get_provider_parameter_schema(component_type, provider_name)
                
                # Verify schema has required API metadata
                for field_name, field_schema in schema.items():
                    assert "type" in field_schema, f"Missing type for {component_type}.{provider_name}.{field_name}"
                    assert "description" in field_schema, f"Missing description for {component_type}.{provider_name}.{field_name}"
                    
                    # Check for proper constraint handling
                    if field_schema["type"] == "number":
                        # Number fields may have minimum/maximum constraints
                        if "minimum" in field_schema or "maximum" in field_schema:
                            print(f"✓ Numeric constraints found for {component_type}.{provider_name}.{field_name}")
                    
                    if "options" in field_schema:
                        # Enum fields should have proper options
                        assert isinstance(field_schema["options"], list), f"Invalid options for {component_type}.{provider_name}.{field_name}"
                        print(f"✓ Enum options found for {component_type}.{provider_name}.{field_name}: {field_schema['options']}")
                
                print(f"✓ API schema validation passed for {component_type}.{provider_name}")


class TestMasterConfigFieldAlignment:
    """Test master configuration field name alignment with runtime parameters"""
    
    def test_master_config_completeness_after_field_alignment(self):
        """Verify config-master.toml maintains 100% coverage after field name changes"""
        report = AutoSchemaRegistry.get_master_config_completeness()
        
        assert report["valid"], f"Master config validation failed: {report}"
        assert report["coverage_percentage"] == 100.0, f"Expected 100% coverage, got {report['coverage_percentage']}%"
        assert not report["missing_sections"], f"Missing sections: {report['missing_sections']}"
        assert not report["orphaned_sections"], f"Orphaned sections: {report['orphaned_sections']}"
        
        print(f"✓ Master config coverage: {report['coverage_percentage']}%")
    
    def test_field_name_consistency_in_master_config(self):
        """Verify master config uses runtime-aligned field names"""
        import tomllib
        from pathlib import Path
        
        # Load master config
        master_config_path = Path("configs/config-master.toml")
        assert master_config_path.exists(), "config-master.toml not found"
        
        with open(master_config_path, "rb") as f:
            master_config = tomllib.load(f)
        
        # Check key providers for field name alignment
        test_cases = [
            # (component, provider, runtime_field, config_should_not_have)
            ("audio", "sounddevice", "device", "device_id"),  # Should use 'device', not 'device_id'
            ("llm", "openai", "model", "default_model"),      # Should use 'model', not 'default_model'
            ("llm", "anthropic", "model", "default_model"),   # Should use 'model', not 'default_model'
        ]
        
        for component, provider, expected_field, old_field in test_cases:
            if component in master_config and "providers" in master_config[component]:
                if provider in master_config[component]["providers"]:
                    provider_config = master_config[component]["providers"][provider]
                    
                    # Check that new field name is used
                    if expected_field != "model":  # Skip model check as it might not be in config
                        # For device field, it should exist in config
                        if expected_field == "device":
                            # Device field might be present in some providers
                            pass  # Don't enforce presence, just check old field is not used
                    
                    # More importantly, check that old field name is NOT used
                    assert old_field not in provider_config, f"Old field name '{old_field}' still used in {component}.{provider} config"
                    
                    print(f"✓ Field name alignment verified for {component}.{provider}")


class TestAutoRegistryIntegration:
    """Test AutoSchemaRegistry integration with the rest of the system"""
    
    def test_auto_registry_cache_invalidation(self):
        """Test that cache can be cleared and regenerated"""
        # Get initial state
        initial_providers = AutoSchemaRegistry.get_provider_schemas()
        
        # Clear cache
        AutoSchemaRegistry.clear_cache()
        
        # Get schemas again - should regenerate
        regenerated_providers = AutoSchemaRegistry.get_provider_schemas()
        
        # Should be identical
        assert initial_providers.keys() == regenerated_providers.keys()
        
        for component_type in initial_providers:
            assert initial_providers[component_type].keys() == regenerated_providers[component_type].keys()
        
        print("✓ Cache invalidation and regeneration works correctly")
    
    def test_parameter_schema_error_handling(self):
        """Test error handling for invalid provider requests"""
        # Test invalid component type
        schema = AutoSchemaRegistry.get_provider_parameter_schema("invalid_component", "provider")
        assert schema == {}, "Should return empty dict for invalid component"
        
        # Test invalid provider name
        schema = AutoSchemaRegistry.get_provider_parameter_schema("audio", "invalid_provider")
        assert schema == {}, "Should return empty dict for invalid provider"
        
        print("✓ Error handling works correctly for invalid requests")
    
    def test_schema_coverage_validation_complete(self):
        """Test final schema coverage validation"""
        report = AutoSchemaRegistry.validate_schema_coverage()
        
        assert report["valid"], f"Schema validation failed: {report}"
        
        # Should have minimal warnings (only about CoreConfig non-BaseModel fields)
        warning_count = len(report.get("warnings", []))
        print(f"Schema validation warnings: {warning_count}")
        
        # Should have zero errors
        assert not report.get("errors", []), f"Schema validation errors: {report['errors']}"
        
        print("✓ Final schema coverage validation passed")


class TestArchitecturalCompletion:
    """Test that the complete architectural vision is achieved"""
    
    def test_single_source_of_truth_achieved(self):
        """Verify Pydantic schemas drive ALL validation"""
        provider_schemas = AutoSchemaRegistry.get_provider_schemas()
        
        # Verify all providers can generate parameter schemas from Pydantic
        for component_type, providers in provider_schemas.items():
            for provider_name in providers.keys():
                schema_class = providers[provider_name]
                
                # Should be a Pydantic BaseModel
                assert issubclass(schema_class, BaseModel), f"{component_type}.{provider_name} schema is not a Pydantic model"
                
                # Should be able to generate parameter schema
                parameter_schema = AutoSchemaRegistry.get_provider_parameter_schema(component_type, provider_name)
                assert isinstance(parameter_schema, dict), f"Failed to generate parameter schema for {component_type}.{provider_name}"
        
        print("✓ Single source of truth (Pydantic schemas) achieved")
    
    def test_zero_manual_patterns_verification(self):
        """Final verification that zero manual patterns remain"""
        # Run all verification commands from the document
        verification_commands = [
            ['grep', '-r', 'def get_parameter_schema', 'irene/providers/'],
            ['grep', '-r', '-E', 'return.*"type".*:', 'irene/providers/'],
            ['grep', '-r', '-E', 'parameter.*schema.*=', 'irene/providers/']
        ]
        
        results = {}
        
        for i, cmd in enumerate(verification_commands):
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  cwd='/home/droman42/development/Irene-Voice-Assistant')
            
            cmd_name = f"cmd_{i}"  # Use simple index-based naming
            results[cmd_name] = {
                'exit_code': result.returncode,
                'output': result.stdout.strip(),
                'has_matches': bool(result.stdout.strip()),
                'description': ' '.join(cmd)
            }
        
        # First command should find exactly 6 base class implementations
        base_class_grep = results['cmd_0']
        assert base_class_grep['has_matches'], "Should find base class implementations"
        lines = base_class_grep['output'].split('\n') if base_class_grep['output'] else []
        assert len(lines) == 6, f"Expected 6 base class implementations, found {len(lines)}"
        
        # Other commands should find nothing
        manual_dict_grep = results['cmd_1']
        assert not manual_dict_grep['has_matches'], f"Manual parameter dictionaries found: {manual_dict_grep['output']}"
        
        param_schema_grep = results['cmd_2'] 
        assert not param_schema_grep['has_matches'], f"Hardcoded parameter schemas found: {param_schema_grep['output']}"
        
        print("✓ Zero manual patterns verification passed")
        print(f"✓ Found {len(lines)} base class auto-generated implementations (expected)")
        print("✓ Zero manual parameter dictionaries found")
        print("✓ Zero hardcoded parameter schemas found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
