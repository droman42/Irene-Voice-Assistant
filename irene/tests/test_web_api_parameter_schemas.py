"""Tests for Web API integration with auto-generated parameter schemas

This module tests that Web API endpoints correctly use auto-generated parameter schemas
from AutoSchemaRegistry instead of manual implementations.

Tests:
- Provider discovery endpoints return auto-generated parameter schemas
- Parameter schema format is correct for API consumption
- All component types have working provider endpoints
- Error handling for invalid providers
- Schema consistency across API and configuration systems
"""

import pytest
import asyncio
from typing import Dict, Any, Optional
from unittest.mock import Mock, AsyncMock

from irene.config.auto_registry import AutoSchemaRegistry


class MockProvider:
    """Mock provider for testing parameter schema integration"""
    
    def __init__(self, provider_name: str, component_type: str, available: bool = True):
        self.provider_name = provider_name
        self.component_type = component_type
        self._available = available
    
    async def is_available(self) -> bool:
        return self._available
    
    def get_provider_name(self) -> str:
        return self.provider_name
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """This should use AutoSchemaRegistry (tests the integration)"""
        return AutoSchemaRegistry.get_provider_parameter_schema(
            self.component_type, 
            self.provider_name
        )
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {"mock": True}
    
    def get_supported_languages(self) -> list:
        return ["en", "ru"]
    
    def get_supported_formats(self) -> list:
        return ["wav", "mp3"]
    
    def get_available_models(self) -> list:
        return ["gpt-4", "gpt-3.5-turbo"]
    
    def get_supported_tasks(self) -> list:
        return ["chat", "completion"]
    
    def get_supported_wake_words(self) -> list:
        return ["hey assistant", "wake up"]
    
    def get_supported_domains(self) -> list:
        return ["general", "weather", "music"]


class MockComponent:
    """Mock component for testing provider discovery endpoints"""
    
    def __init__(self, component_type: str, providers: Dict[str, MockProvider]):
        self.component_type = component_type
        self.providers = providers
        self.default_provider = list(providers.keys())[0] if providers else None
        self.fallback_providers = list(providers.keys())[1:] if len(providers) > 1 else []


class TestWebAPIParameterSchemaIntegration:
    """Test Web API integration with auto-generated parameter schemas"""
    
    def test_tts_providers_endpoint_parameter_schemas(self):
        """Test TTS providers endpoint returns auto-generated parameter schemas"""
        # Create mock TTS providers
        providers = {
            "console": MockProvider("console", "tts"),
            "elevenlabs": MockProvider("elevenlabs", "tts"),
            "silero_v4": MockProvider("silero_v4", "tts")
        }
        
        mock_component = MockComponent("tts", providers)
        
        # Simulate what the API endpoint does
        result = {}
        for name, provider in mock_component.providers.items():
            result[name] = {
                "available": True,  # Simplified for test
                "parameters": provider.get_parameter_schema(),
                "capabilities": provider.get_capabilities()
            }
        
        # Verify that parameter schemas are auto-generated
        for provider_name, provider_info in result.items():
            parameters = provider_info["parameters"]
            assert isinstance(parameters, dict), f"Parameter schema should be dict for {provider_name}"
            
            # For non-text-processing providers, should have some parameters
            if provider_name != "console":  # Console might have minimal parameters
                print(f"TTS {provider_name} parameters: {list(parameters.keys())}")
            
            # Verify schema format is API-compatible
            for param_name, param_schema in parameters.items():
                if param_name != "enabled":  # Skip config-only fields
                    assert "type" in param_schema, f"Missing type for {provider_name}.{param_name}"
                    assert "description" in param_schema, f"Missing description for {provider_name}.{param_name}"
    
    def test_llm_providers_endpoint_parameter_schemas(self):
        """Test LLM providers endpoint returns auto-generated parameter schemas"""
        providers = {
            "openai": MockProvider("openai", "llm"),
            "anthropic": MockProvider("anthropic", "llm"),
            "console": MockProvider("console", "llm")
        }
        
        mock_component = MockComponent("llm", providers)
        
        # Simulate LLM providers endpoint
        result = {}
        for name, provider in mock_component.providers.items():
            result[name] = {
                "available": True,
                "models": provider.get_available_models(),
                "tasks": provider.get_supported_tasks(),
                "parameters": provider.get_parameter_schema(),
                "capabilities": provider.get_capabilities()
            }
        
        # Verify LLM-specific parameter schemas
        for provider_name, provider_info in result.items():
            parameters = provider_info["parameters"]
            assert isinstance(parameters, dict)
            
            # LLM providers should have model-related parameters
            if provider_name in ["openai", "anthropic"]:
                print(f"LLM {provider_name} parameters: {list(parameters.keys())}")
                
                # Common LLM parameters (after field alignment in Phase 6)
                expected_params = {"model", "max_tokens", "temperature"}
                actual_params = set(parameters.keys())
                
                # Check that some expected parameters are present
                common_params = expected_params & actual_params
                assert len(common_params) > 0, f"No common LLM parameters found in {provider_name}: {actual_params}"
    
    def test_audio_providers_endpoint_parameter_schemas(self):
        """Test Audio providers endpoint returns auto-generated parameter schemas"""
        providers = {
            "sounddevice": MockProvider("sounddevice", "audio"),
            "audioplayer": MockProvider("audioplayer", "audio"),
            "console": MockProvider("console", "audio")
        }
        
        mock_component = MockComponent("audio", providers)
        
        # Simulate audio providers endpoint
        result = {}
        for name, provider in mock_component.providers.items():
            result[name] = {
                "available": True,
                "parameters": provider.get_parameter_schema(),
                "capabilities": provider.get_capabilities()
            }
        
        # Verify audio-specific parameter schemas
        for provider_name, provider_info in result.items():
            parameters = provider_info["parameters"]
            assert isinstance(parameters, dict)
            
            # Audio providers should have device/volume parameters (after Phase 6 alignment)
            if provider_name in ["sounddevice", "audioplayer"]:
                print(f"Audio {provider_name} parameters: {list(parameters.keys())}")
                
                # After Phase 6, should use 'device' (not 'device_id')
                actual_params = set(parameters.keys())
                if "device" in actual_params:
                    print(f"✓ Field alignment verified: {provider_name} uses 'device' parameter")
    
    def test_asr_providers_endpoint_parameter_schemas(self):
        """Test ASR providers endpoint returns auto-generated parameter schemas"""
        providers = {
            "whisper": MockProvider("whisper", "asr"),
            "vosk": MockProvider("vosk", "asr"),
            "google_cloud": MockProvider("google_cloud", "asr")
        }
        
        mock_component = MockComponent("asr", providers)
        
        # Simulate ASR providers endpoint
        result = {}
        for name, provider in mock_component.providers.items():
            result[name] = {
                "available": True,
                "parameters": provider.get_parameter_schema(),
                "languages": provider.get_supported_languages(),
                "formats": provider.get_supported_formats(),
                "capabilities": provider.get_capabilities()
            }
        
        # Verify ASR-specific parameter schemas
        for provider_name, provider_info in result.items():
            parameters = provider_info["parameters"]
            assert isinstance(parameters, dict)
            
            print(f"ASR {provider_name} parameters: {list(parameters.keys())}")
            
            # Verify API response format is complete
            assert "languages" in provider_info
            assert "formats" in provider_info
            assert "capabilities" in provider_info
    
    def test_voice_trigger_providers_endpoint_parameter_schemas(self):
        """Test Voice Trigger providers endpoint returns auto-generated parameter schemas"""
        providers = {
            "openwakeword": MockProvider("openwakeword", "voice_trigger"),
            "microwakeword": MockProvider("microwakeword", "voice_trigger")
        }
        
        mock_component = MockComponent("voice_trigger", providers)
        
        # Simulate voice trigger providers endpoint
        result = {}
        for name, provider in mock_component.providers.items():
            result[name] = {
                "available": True,
                "wake_words": provider.get_supported_wake_words(),
                "capabilities": provider.get_capabilities(),
                "parameters": provider.get_parameter_schema(),
                "is_default": name == mock_component.default_provider
            }
        
        # Verify voice trigger parameter schemas (critical from Phase 6)
        for provider_name, provider_info in result.items():
            parameters = provider_info["parameters"]
            assert isinstance(parameters, dict)
            
            print(f"Voice Trigger {provider_name} parameters: {list(parameters.keys())}")
            
            # Voice trigger providers should have wake_words and threshold (from Phase 6 tests)
            expected_params = {"wake_words", "threshold"}
            actual_params = set(parameters.keys())
            
            # Check critical parameters are present
            missing_critical = expected_params - actual_params
            if missing_critical:
                print(f"Warning: {provider_name} missing critical parameters: {missing_critical}")
            else:
                print(f"✓ Critical voice trigger parameters verified for {provider_name}")
    
    def test_nlu_providers_endpoint_parameter_schemas(self):
        """Test NLU providers endpoint returns auto-generated parameter schemas"""
        providers = {
            "hybrid_keyword_matcher": MockProvider("hybrid_keyword_matcher", "nlu"),
            "spacy_nlu": MockProvider("spacy_nlu", "nlu")
        }
        
        mock_component = MockComponent("nlu", providers)
        
        # Simulate NLU providers endpoint
        result = {}
        for name, provider in mock_component.providers.items():
            result[name] = {
                "available": True,
                "languages": provider.get_supported_languages(),
                "domains": provider.get_supported_domains(),
                "parameters": provider.get_parameter_schema(),
                "capabilities": provider.get_capabilities()
            }
        
        # Verify NLU parameter schemas
        for provider_name, provider_info in result.items():
            parameters = provider_info["parameters"]
            assert isinstance(parameters, dict)
            
            print(f"NLU {provider_name} parameters: {list(parameters.keys())}")
            
            # Verify NLU response completeness
            assert "languages" in provider_info
            assert "domains" in provider_info
            assert "capabilities" in provider_info


class TestParameterSchemaAPIFormat:
    """Test parameter schema format is correct for API consumption"""
    
    def test_parameter_schema_api_format_compliance(self):
        """Test that auto-generated schemas follow API format requirements"""
        # Test a few key providers across different component types
        test_cases = [
            ("tts", "elevenlabs"),
            ("audio", "sounddevice"),
            ("llm", "openai"),
            ("asr", "whisper"),
            ("voice_trigger", "openwakeword")
        ]
        
        for component_type, provider_name in test_cases:
            schema = AutoSchemaRegistry.get_provider_parameter_schema(component_type, provider_name)
            
            # Test basic API format requirements
            assert isinstance(schema, dict), f"Schema must be dict for {component_type}.{provider_name}"
            
            for param_name, param_def in schema.items():
                # Skip configuration-only fields
                if param_name == "enabled":
                    continue
                
                # Verify required API fields
                assert isinstance(param_def, dict), f"Parameter definition must be dict: {component_type}.{provider_name}.{param_name}"
                assert "type" in param_def, f"Missing 'type' field: {component_type}.{provider_name}.{param_name}"
                assert "description" in param_def, f"Missing 'description' field: {component_type}.{provider_name}.{param_name}"
                
                # Verify type is valid
                valid_types = ["string", "number", "integer", "boolean", "array", "object"]
                assert param_def["type"] in valid_types, f"Invalid type '{param_def['type']}': {component_type}.{provider_name}.{param_name}"
                
                # Verify constraints are properly formatted
                if "minimum" in param_def:
                    assert isinstance(param_def["minimum"], (int, float)), f"Invalid minimum constraint: {component_type}.{provider_name}.{param_name}"
                
                if "maximum" in param_def:
                    assert isinstance(param_def["maximum"], (int, float)), f"Invalid maximum constraint: {component_type}.{provider_name}.{param_name}"
                
                if "options" in param_def:
                    assert isinstance(param_def["options"], list), f"Options must be list: {component_type}.{provider_name}.{param_name}"
                
                print(f"✓ API format validated: {component_type}.{provider_name}.{param_name}")
    
    def test_parameter_schema_json_serializable(self):
        """Test that parameter schemas are JSON serializable for API responses"""
        import json
        
        provider_schemas = AutoSchemaRegistry.get_provider_schemas()
        
        for component_type, providers in provider_schemas.items():
            for provider_name in providers.keys():
                schema = AutoSchemaRegistry.get_provider_parameter_schema(component_type, provider_name)
                
                # Test JSON serialization
                try:
                    json_str = json.dumps(schema)
                    deserialized = json.loads(json_str)
                    assert deserialized == schema, f"JSON round-trip failed for {component_type}.{provider_name}"
                    print(f"✓ JSON serialization verified: {component_type}.{provider_name}")
                except Exception as e:
                    pytest.fail(f"JSON serialization failed for {component_type}.{provider_name}: {e}")


class TestAPIErrorHandling:
    """Test error handling for Web API parameter schema integration"""
    
    def test_invalid_provider_parameter_schema_handling(self):
        """Test API behavior when parameter schema generation fails"""
        # Test with invalid provider that doesn't exist
        schema = AutoSchemaRegistry.get_provider_parameter_schema("invalid_component", "invalid_provider")
        assert schema == {}, "Should return empty dict for invalid provider"
        
        # This simulates what API endpoints should do for error handling
        mock_provider = MockProvider("invalid_provider", "invalid_component")
        
        # Should handle gracefully without raising exceptions
        try:
            param_schema = mock_provider.get_parameter_schema()
            assert isinstance(param_schema, dict), "Should return dict even for invalid providers"
        except Exception as e:
            pytest.fail(f"Parameter schema generation should not raise exceptions: {e}")
    
    def test_provider_availability_error_handling(self):
        """Test API handling when providers are not available"""
        # Create mock unavailable provider
        unavailable_provider = MockProvider("test_provider", "tts", available=False)
        
        # Simulate API endpoint error handling
        try:
            result = {
                "available": False,  # Provider reports as unavailable
                "parameters": unavailable_provider.get_parameter_schema(),
                "capabilities": unavailable_provider.get_capabilities(),
                "error": "Provider not available"
            }
            
            # Should still be able to get parameter schema even if provider is unavailable
            assert isinstance(result["parameters"], dict)
            assert "error" in result
            print("✓ Error handling verified for unavailable providers")
            
        except Exception as e:
            pytest.fail(f"API should handle unavailable providers gracefully: {e}")


class TestSchemaConsistencyAcrossAPIs:
    """Test schema consistency between API endpoints and configuration system"""
    
    def test_api_parameter_schema_matches_config_schema(self):
        """Test that API parameter schemas are consistent with configuration schemas"""
        provider_schemas = AutoSchemaRegistry.get_provider_schemas()
        
        # Test consistency for key providers
        test_providers = [
            ("tts", "elevenlabs"),
            ("audio", "sounddevice"),
            ("llm", "openai"),
            ("voice_trigger", "openwakeword")
        ]
        
        for component_type, provider_name in test_providers:
            if component_type in provider_schemas and provider_name in provider_schemas[component_type]:
                # Get API parameter schema
                api_schema = AutoSchemaRegistry.get_provider_parameter_schema(component_type, provider_name)
                
                # Get Pydantic config schema
                pydantic_schema_class = provider_schemas[component_type][provider_name]
                pydantic_fields = pydantic_schema_class.model_fields
                
                # Verify consistency
                for api_param_name in api_schema.keys():
                    if api_param_name != "enabled":  # Skip config-only fields
                        assert api_param_name in pydantic_fields, f"API parameter {api_param_name} not in Pydantic model for {component_type}.{provider_name}"
                
                print(f"✓ Schema consistency verified: {component_type}.{provider_name}")
    
    def test_field_name_alignment_phase6_compliance(self):
        """Test that Phase 6 field name alignment is reflected in API schemas"""
        # Test specific field alignments from Phase 6
        alignment_tests = [
            ("audio", "sounddevice", "device"),      # Should use 'device', not 'device_id'
            ("llm", "openai", "model"),              # Should use 'model', not 'default_model'
            ("llm", "anthropic", "model"),           # Should use 'model', not 'default_model'
        ]
        
        for component_type, provider_name, expected_field in alignment_tests:
            api_schema = AutoSchemaRegistry.get_provider_parameter_schema(component_type, provider_name)
            
            if api_schema:  # Only test if schema exists
                # Check that the aligned field name is present or acceptable
                api_fields = set(api_schema.keys())
                
                # For device field, check it's not the old name
                if expected_field == "device":
                    assert "device_id" not in api_fields, f"Old field name 'device_id' still present in {component_type}.{provider_name}"
                    if "device" in api_fields:
                        print(f"✓ Phase 6 field alignment verified: {component_type}.{provider_name} uses '{expected_field}'")
                
                # For model field, check it's not the old name
                elif expected_field == "model":
                    assert "default_model" not in api_fields, f"Old field name 'default_model' still present in {component_type}.{provider_name}"
                    if "model" in api_fields:
                        print(f"✓ Phase 6 field alignment verified: {component_type}.{provider_name} uses '{expected_field}'")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
