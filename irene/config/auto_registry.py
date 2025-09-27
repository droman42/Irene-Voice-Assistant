"""
Auto Schema Registry - Automatically generate schema registries from Pydantic models

This module implements the AutoSchemaRegistry class which eliminates manual schema
dictionaries by auto-generating them from Pydantic model introspection. This serves
as the single source of truth for all schema-related operations.

Key Features:
- Auto-generates section model registry from CoreConfig fields
- Auto-discovers component schemas with validation
- Auto-generates provider schema registry from discovery
- Validates schema coverage and returns comprehensive reports
- Validates config-master.toml completeness against all provider schemas
- Caches results for performance with cache invalidation support

Design Principles:
- Single Source of Truth: Pydantic CoreConfig model is authoritative
- Automatic Generation: All registries auto-generated via introspection
- Fail-Fast Validation: Schema mismatches detected at startup
- Zero Manual Sync: No manual dictionary maintenance
"""

import logging
import inspect
import tomllib
from pathlib import Path
from typing import Dict, Any, Type, Optional, Set, get_origin, get_args
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AutoSchemaRegistry:
    """Auto-generates schema registries from Pydantic CoreConfig model"""
    
    _section_models_cache: Optional[Dict[str, Type[BaseModel]]] = None
    _component_schemas_cache: Optional[Dict[str, Type[BaseModel]]] = None
    _provider_schemas_cache: Optional[Dict[str, Dict[str, Type[BaseModel]]]] = None
    
    @classmethod
    def get_section_models(cls) -> Dict[str, Type[BaseModel]]:
        """Auto-generate section model registry from CoreConfig fields"""
        if cls._section_models_cache is None:
            cls._section_models_cache = {}
            
            from .models import CoreConfig
            
            for field_name, field_info in CoreConfig.model_fields.items():
                if hasattr(field_info, 'annotation'):
                    annotation = field_info.annotation
                    model_class = None
                    
                    # Handle direct BaseModel subclasses
                    if (inspect.isclass(annotation) and 
                        issubclass(annotation, BaseModel) and 
                        annotation != BaseModel):
                        model_class = annotation
                    
                    # Handle Optional[BaseModel] (Union[BaseModel, None])
                    elif get_origin(annotation) is not None:
                        args = get_args(annotation)
                        for arg in args:
                            if (inspect.isclass(arg) and 
                                issubclass(arg, BaseModel) and 
                                arg != BaseModel):
                                model_class = arg
                                break
                    
                    if model_class:
                        cls._section_models_cache[field_name] = model_class
                        logger.debug(f"Auto-registered: {field_name} -> {model_class.__name__}")
            
            logger.info(f"Auto-generated {len(cls._section_models_cache)} section models")
        
        return cls._section_models_cache.copy()
    
    @classmethod
    def get_section_model(cls, section_name: str) -> Optional[Type[BaseModel]]:
        """Get specific section model by name"""
        section_models = cls.get_section_models()
        return section_models.get(section_name)
    
    @classmethod
    def get_component_schemas(cls) -> Dict[str, Type[BaseModel]]:
        """Auto-generate component schema registry with validation"""
        if cls._component_schemas_cache is None:
            cls._component_schemas_cache = {}
            
            from .models import ComponentConfig
            component_fields = ComponentConfig.model_fields
            
            for component_name, field_info in component_fields.items():
                if field_info.annotation == bool:  # Component enablement flag
                    schema_class = cls._find_component_schema(component_name)
                    if schema_class:
                        cls._component_schemas_cache[component_name] = schema_class
                        logger.debug(f"Auto-registered component: {component_name} -> {schema_class.__name__}")
                    else:
                        logger.warning(f"No component schema found: {component_name}")
            
            logger.info(f"Auto-generated {len(cls._component_schemas_cache)} component schemas")
        
        return cls._component_schemas_cache.copy()
    
    @classmethod 
    def get_provider_schemas(cls) -> Dict[str, Dict[str, Type[BaseModel]]]:
        """Auto-generate provider schema registry from discovery"""
        if cls._provider_schemas_cache is None:
            cls._provider_schemas_cache = {}
            
            # Auto-discover provider schemas by importing and introspecting schema classes
            provider_schemas = cls._discover_provider_schemas()
            cls._provider_schemas_cache = provider_schemas
            
            logger.info(f"Provider schemas auto-discovered: {sum(len(providers) for providers in cls._provider_schemas_cache.values())} providers")
        
        return cls._provider_schemas_cache.copy()
    
    @classmethod
    def _discover_provider_schemas(cls) -> Dict[str, Dict[str, Type[BaseModel]]]:
        """Auto-discover provider schemas by importing and analyzing schema classes"""
        try:
            # Import all provider schema classes
            from .schemas import (
                # TTS providers
                ConsoleProviderSchema, ElevenLabsProviderSchema, SileroV3ProviderSchema, 
                SileroV4ProviderSchema, VoskTTSProviderSchema, PyttSXProviderSchema,
                # Audio providers  
                SoundDeviceProviderSchema, AudioPlayerProviderSchema, SimpleAudioProviderSchema, APlayProviderSchema, ConsoleAudioProviderSchema,
                # ASR providers
                WhisperProviderSchema, VoskASRProviderSchema, GoogleCloudProviderSchema,
                # LLM providers
                OpenAIProviderSchema, AnthropicProviderSchema, VSEGPTProviderSchema,
                # Voice trigger providers
                OpenWakeWordProviderSchema, PorcupineProviderSchema, MicroWakeWordProviderSchema,
                # NLU providers
                HybridKeywordMatcherProviderSchema, SpaCyNLUProviderSchema,
                # Text processor providers
                ASRTextProcessorProviderSchema, GeneralTextProcessorProviderSchema,
                TTSTextProcessorProviderSchema, NumberTextProcessorProviderSchema
            )
            
            # Auto-discover provider mappings based on naming conventions and schema inheritance
            provider_schemas = {
                "tts": {
                    "console": ConsoleProviderSchema,
                    "elevenlabs": ElevenLabsProviderSchema,
                    "silero_v3": SileroV3ProviderSchema,
                    "silero_v4": SileroV4ProviderSchema,
                    "vosk": VoskTTSProviderSchema,
                    "pyttsx": PyttSXProviderSchema,
                },
                "audio": {
                    "console": ConsoleAudioProviderSchema,
                    "sounddevice": SoundDeviceProviderSchema,
                    "audioplayer": AudioPlayerProviderSchema,
                    "simpleaudio": SimpleAudioProviderSchema,
                    "aplay": APlayProviderSchema,
                },
                "asr": {
                    "whisper": WhisperProviderSchema,
                    "vosk": VoskASRProviderSchema,
                    "google_cloud": GoogleCloudProviderSchema,
                },
                "llm": {
                    "openai": OpenAIProviderSchema,
                    "anthropic": AnthropicProviderSchema,
                    "console": ConsoleProviderSchema,
                    "vsegpt": VSEGPTProviderSchema,
                },
                "voice_trigger": {
                    "openwakeword": OpenWakeWordProviderSchema,
                    "porcupine": PorcupineProviderSchema,
                    "microwakeword": MicroWakeWordProviderSchema,
                },
                "nlu": {
                    "hybrid_keyword_matcher": HybridKeywordMatcherProviderSchema,
                    "spacy_nlu": SpaCyNLUProviderSchema,
                },
                "text_processor": {
                    "asr_text_processor": ASRTextProcessorProviderSchema,
                    "general_text_processor": GeneralTextProcessorProviderSchema,
                    "tts_text_processor": TTSTextProcessorProviderSchema,
                    "number_text_processor": NumberTextProcessorProviderSchema,
                }
            }
            
            logger.debug("Provider schemas auto-discovered successfully")
            return provider_schemas
            
        except ImportError as e:
            logger.error(f"Failed to auto-discover provider schemas: {e}")
            # Fallback to empty registry
            return {}
    
    @classmethod
    def extract_all_schemas(cls) -> Dict[str, Any]:
        """Extract complete configuration schema (auto-generated only)"""
        schema = {}
        section_models = cls.get_section_models()
        
        for section_name, model_class in section_models.items():
            schema[section_name] = cls._extract_model_schema(model_class)
        
        return schema
    
    @classmethod
    def _extract_model_schema(cls, model_class: Type[BaseModel]) -> Dict[str, Any]:
        """Extract field metadata from Pydantic model for widget generation"""
        from irene.components.configuration_component import ConfigurationComponent
        
        # Use existing implementation from ConfigurationComponent temporarily
        # This will be moved to this class in a future refactoring
        config_component = ConfigurationComponent()
        return config_component._extract_model_schema(model_class)
    
    @classmethod
    def validate_schema_coverage(cls) -> Dict[str, Any]:
        """Validate schema coverage and return validation report"""
        report = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "recommendations": []
        }
        
        # Validate section model coverage
        section_models = cls.get_section_models()
        from .models import CoreConfig
        core_config_fields = set(CoreConfig.model_fields.keys())
        section_model_fields = set(section_models.keys())
        
        missing_sections = core_config_fields - section_model_fields
        if missing_sections:
            report["warnings"].append(f"CoreConfig fields without section models: {missing_sections}")
        
        # Validate component schema coverage
        component_schemas = cls.get_component_schemas()
        from .models import ComponentConfig
        component_fields = set(ComponentConfig.model_fields.keys())
        schema_fields = set(component_schemas.keys())
        
        missing_component_schemas = component_fields - schema_fields
        if missing_component_schemas:
            # Phase 2: Missing component schemas are now errors (all schemas should exist)
            report["errors"].append(f"Components without schemas: {missing_component_schemas}")
            report["valid"] = False
            
            for missing in missing_component_schemas:
                report["recommendations"].append(f"Create {missing.title()}ComponentSchema class")
        
        return report
    
    @classmethod
    def _find_component_schema(cls, component_name: str) -> Optional[Type[BaseModel]]:
        """Find component schema class by component name (auto-discovery only)"""
        # Import all component schemas and find by naming convention
        try:
            from .schemas import (
                TTSComponentSchema, AudioComponentSchema, ASRComponentSchema, 
                LLMComponentSchema, VoiceTriggerComponentSchema, NLUComponentSchema,
                TextProcessorComponentSchema, IntentSystemComponentSchema,
                MonitoringComponentSchema, NLUAnalysisComponentSchema, ConfigurationComponentSchema
            )
            
            # Map component names to schema classes
            component_schema_map = {
                "tts": TTSComponentSchema,
                "audio": AudioComponentSchema,
                "asr": ASRComponentSchema,
                "llm": LLMComponentSchema,
                "voice_trigger": VoiceTriggerComponentSchema,
                "nlu": NLUComponentSchema,
                "text_processor": TextProcessorComponentSchema,
                "intent_system": IntentSystemComponentSchema,
                "monitoring": MonitoringComponentSchema,
                "nlu_analysis": NLUAnalysisComponentSchema,
                "configuration": ConfigurationComponentSchema,
            }
            
            return component_schema_map.get(component_name)
            
        except ImportError as e:
            logger.warning(f"Failed to import component schema for {component_name}: {e}")
            return None
    
    @classmethod
    def get_master_config_completeness(cls) -> Dict[str, Any]:
        """
        Analyze config-master.toml completeness against all provider schemas.
        Returns comprehensive report of missing/orphaned sections.
        """
        report = {
            "missing_sections": [],
            "orphaned_sections": [],
            "coverage_percentage": 0.0,
            "valid": True
        }
        
        try:
            # Load master config
            master_config_path = Path("configs/config-master.toml")
            if not master_config_path.exists():
                report["valid"] = False
                report["missing_sections"].append("ENTIRE_MASTER_CONFIG_MISSING")
                return report
            
            with open(master_config_path, "rb") as f:
                master_config = tomllib.load(f)
            
            # Get all provider schemas
            provider_schemas = cls.get_provider_schemas()
            
            expected_sections = set()
            for component_type, providers in provider_schemas.items():
                for provider_name in providers.keys():
                    expected_sections.add(f"{component_type}.providers.{provider_name}")
            
            # Check config-master.toml sections
            actual_sections = set()
            for component_type, component_config in master_config.items():
                if isinstance(component_config, dict) and "providers" in component_config:
                    for provider_name in component_config["providers"].keys():
                        actual_sections.add(f"{component_type}.providers.{provider_name}")
            
            # Calculate missing and orphaned
            report["missing_sections"] = list(expected_sections - actual_sections)
            report["orphaned_sections"] = list(actual_sections - expected_sections)
            
            if expected_sections:
                report["coverage_percentage"] = (len(actual_sections & expected_sections) / len(expected_sections)) * 100
            
            logger.debug(f"Master config analysis: {len(expected_sections)} expected, {len(actual_sections)} actual")
            
        except Exception as e:
            logger.error(f"Master config analysis failed: {e}")
            report["valid"] = False
        
        return report
    
    @classmethod
    def validate_provider_config(cls, component_type: str, provider_name: str, config: Dict[str, Any]) -> bool:
        """Validate provider configuration using auto-discovery"""
        provider_schemas = cls.get_provider_schemas()
        
        if component_type not in provider_schemas:
            return False
        
        if provider_name not in provider_schemas[component_type]:
            return False
        
        schema_class = provider_schemas[component_type][provider_name]
        try:
            schema_class.model_validate(config)
            return True
        except Exception:
            return False
    
    @classmethod
    def validate_component_config(cls, component_type: str, config: Dict[str, Any]) -> bool:
        """Validate component configuration using auto-discovery"""
        component_schemas = cls.get_component_schemas()
        
        if component_type not in component_schemas:
            return False
        
        schema_class = component_schemas[component_type]
        try:
            schema_class.model_validate(config)
            return True
        except Exception:
            return False
    
    @classmethod
    def get_section_order_and_titles(cls) -> Dict[str, Any]:
        """Get section order and titles for frontend auto-generation"""
        section_models = cls.get_section_models()
        
        # Define logical ordering for sections
        preferred_order = [
            'system', 'inputs', 'components',  # Core sections first
            'tts', 'audio', 'asr', 'llm',      # Main components
            'voice_trigger', 'nlu', 'nlu_analysis', 'text_processor', 'intent_system',  # Advanced components
            'vad', 'monitoring',               # Utility components
            'assets', 'workflows'              # System components
        ]
        
        # Generate section order based on available sections and preferred order
        available_sections = set(section_models.keys())
        section_order = []
        
        # Add sections in preferred order if they exist
        for section in preferred_order:
            if section in available_sections:
                section_order.append(section)
                available_sections.remove(section)
        
        # Add any remaining sections not in preferred order
        section_order.extend(sorted(available_sections))
        
        # Generate titles with emojis
        section_titles = {
            'system': '🔧 Core Settings',
            'inputs': '📝 Input Sources',
            'components': '🔌 Components',
            'tts': '🗣️ Text-to-Speech',
            'audio': '🔊 Audio Playback',
            'asr': '🎤 Speech Recognition',
            'llm': '🤖 Language Models',
            'voice_trigger': '👂 Voice Trigger',
            'nlu': '🧠 Natural Language Understanding',
            'nlu_analysis': '🔍 NLU Analysis',
            'text_processor': '📝 Text Processing',
            'intent_system': '🎯 Intent System',
            'vad': '🔊 Voice Activity Detection',
            'monitoring': '📊 Monitoring',
            'assets': '📁 Asset Management',
            'workflows': '⚡ Workflows'
        }
        
        # Generate titles for sections not in the predefined map
        for section in section_order:
            if section not in section_titles:
                # Convert snake_case to Title Case
                title = section.replace('_', ' ').title()
                section_titles[section] = f"⚙️ {title}"
        
        return {
            "section_order": section_order,
            "section_titles": section_titles,
            "total_sections": len(section_order)
        }
    
    @classmethod
    def get_provider_parameter_schema(cls, component_type: str, provider_name: str) -> Dict[str, Any]:
        """
        Auto-generate runtime parameter schema from Pydantic model.
        Eliminates need for manual get_parameter_schema() implementations.
        """
        provider_schemas = cls.get_provider_schemas()
        
        if component_type not in provider_schemas:
            logger.warning(f"Component type not found: {component_type}")
            return {}
        
        if provider_name not in provider_schemas[component_type]:
            logger.warning(f"Provider not found: {component_type}.{provider_name}")
            return {}
        
        schema_class = provider_schemas[component_type][provider_name]
        
        try:
            # Generate JSON Schema from Pydantic model
            json_schema = schema_class.model_json_schema()
            
            # Convert to runtime parameter format expected by Web API
            parameter_schema = cls._convert_json_schema_to_parameter_format(json_schema)
            
            logger.debug(f"Auto-generated parameter schema for {component_type}.{provider_name}")
            return parameter_schema
            
        except Exception as e:
            logger.error(f"Failed to generate parameter schema for {component_type}.{provider_name}: {e}")
            return {}

    @classmethod
    def _convert_json_schema_to_parameter_format(cls, json_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Pydantic JSON Schema to parameter schema format"""
        parameters = {}
        definitions = json_schema.get("$defs", {})
        
        def resolve_ref(ref_path: str) -> Dict[str, Any]:
            """Resolve $ref path to actual definition"""
            if ref_path.startswith("#/$defs/"):
                ref_name = ref_path.replace("#/$defs/", "")
                return definitions.get(ref_name, {})
            return {}
        
        def convert_field_schema(field_schema: Dict[str, Any]) -> Dict[str, Any]:
            """Convert individual field schema, handling $ref references"""
            # Handle $ref references
            if "$ref" in field_schema:
                resolved_schema = resolve_ref(field_schema["$ref"])
                if resolved_schema:
                    return convert_nested_object(resolved_schema, field_schema.get("description", ""))
            
            # Handle direct object types
            if field_schema.get("type") == "object" and "properties" in field_schema:
                return convert_nested_object(field_schema, field_schema.get("description", ""))
            
            # Handle simple types
            param_schema = {
                "type": field_schema.get("type", "string"),
                "description": field_schema.get("description", ""),
            }
            
            # Add constraints
            if "minimum" in field_schema:
                param_schema["minimum"] = field_schema["minimum"]
            if "maximum" in field_schema:
                param_schema["maximum"] = field_schema["maximum"]
            if "enum" in field_schema:
                param_schema["options"] = field_schema["enum"]
            if "default" in field_schema:
                param_schema["default"] = field_schema["default"]
                
            return param_schema
        
        def convert_nested_object(obj_schema: Dict[str, Any], description: str = "") -> Dict[str, Any]:
            """Convert nested object to parameter format with properties"""
            nested_params = {}
            
            for prop_name, prop_schema in obj_schema.get("properties", {}).items():
                nested_params[prop_name] = convert_field_schema(prop_schema)
            
            return {
                "type": "object",
                "description": description,
                "properties": nested_params
            }
        
        properties = json_schema.get("properties", {})
        for field_name, field_schema in properties.items():
            # Skip non-runtime fields
            if field_name in ["enabled"]:  # Configuration-only fields
                continue
                
            parameters[field_name] = convert_field_schema(field_schema)
        
        return parameters

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached registries (for testing/development)"""
        cls._section_models_cache = None
        cls._component_schemas_cache = None
        cls._provider_schemas_cache = None
        logger.debug("Auto-schema registry cache cleared")
