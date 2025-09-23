"""
Configuration Component - WebAPI-based configuration management

Provides WebAPI endpoints for real-time configuration management with file-based 
hot-reload integration. Leverages existing ConfigManager infrastructure and 
Pydantic model introspection for automatic widget generation.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Type, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError, Field

from .base import Component
from ..core.interfaces.webapi import WebAPIPlugin
from ..config.manager import ConfigManager
from ..config.models import CoreConfig
from ..config.auto_registry import AutoSchemaRegistry
from ..config.schemas import AudioDevicesResponse, AudioDeviceInfo
from ..api.schemas import (
    BaseAPIResponse, ErrorResponse, ValidationError as APIValidationError,
    ConfigUpdateResponse, ConfigValidationResponse, ConfigStatusResponse,
    RawTomlRequest, RawTomlResponse, RawTomlSaveResponse,
    RawTomlValidationRequest, RawTomlValidationResponse,
    SectionToTomlRequest, SectionToTomlResponse
)

logger = logging.getLogger(__name__)


class ConfigurationComponent(Component, WebAPIPlugin):
    """
    Configuration Component - File-Based Hot-Reload Integration
    
    Provides WebAPI endpoints for configuration management while leveraging
    existing ConfigManager infrastructure and hot-reload mechanisms.
    """
    
    def __init__(self):
        super().__init__()
        self.config_manager = None
        self.active_config_path = None
        
    @property
    def name(self) -> str:
        return "configuration"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Configuration management component with WebAPI interface"
        
    @property
    def enabled_by_default(self) -> bool:
        return True  # Essential system functionality
        
    @property
    def category(self) -> str:
        return "system"
        
    @property
    def platforms(self) -> List[str]:
        return []  # All platforms
    
    def get_python_dependencies(self) -> list[str]:
        """Return list of required Python modules for ConfigurationComponent"""
        return ["fastapi", "pydantic", "tomlkit"]  # Required for WebAPI, configuration validation, and comment preservation
    
    def get_service_dependencies(self) -> Dict[str, type]:
        """Get list of required service dependencies."""
        return {}  # No service dependencies
    
    @property
    def optional_dependencies(self) -> list[str]:
        """Optional Python dependencies for enhanced functionality"""
        return []  # No optional dependencies
        
    async def initialize(self, core):
        """Initialize with reference to ConfigManager and active config path"""
        # Create ConfigManager instance (or reuse from core if available)
        self.config_manager = ConfigManager()
        
        # Get the active config path used by the running system
        self.active_config_path = getattr(core, 'config_path', None)
        if not self.active_config_path:
            logger.warning("ConfigurationComponent: active_config_path not available from core")
            # Fallback to auto-detection
            self.active_config_path = self.config_manager._find_config_file()
            
        self.initialized = True
        logger.info(f"ConfigurationComponent initialized with config path: {self.active_config_path}")
    
    async def shutdown(self) -> None:
        """Shutdown the configuration component"""
        self.initialized = False
        logger.info("ConfigurationComponent shutdown completed")
    
    def get_providers_info(self) -> str:
        """Configuration management - no providers needed"""
        return "Configuration management component - no providers"
    
    @classmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """No own configuration - manages other components' configs"""
        return None
    
    @classmethod  
    def get_config_path(cls) -> str:
        """No config path - manages system configuration"""
        return ""
    
    def get_router(self) -> APIRouter:
        """Configuration WebAPI endpoints with file-based hot-reload and proper response documentation"""
        router = APIRouter()
        
        @router.get("/config", response_model=CoreConfig)
        async def get_current_config():
            """
            Get current TOML configuration
            
            Returns the complete system configuration using the CoreConfig model.
            This includes all sections: system, inputs, components, assets, workflows,
            and component-specific configurations (TTS, Audio, ASR, LLM, etc.).
            """
            try:
                config = await self.config_manager.load_config(self.active_config_path)
                return config
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to load configuration: {str(e)}")
        
        @router.get("/config/schema", response_model=Dict[str, Any])
        async def get_config_schema():
            """
            Get Pydantic field metadata for auto-generating widgets
            
            Returns schema information for all configuration sections including:
            - Field types (boolean, string, integer, etc.)
            - Default values
            - Validation constraints
            - Field descriptions for UI tooltips
            - Required vs optional fields
            """
            try:
                schema = self._extract_config_schema()
                return schema
            except Exception as e:
                logger.error(f"Failed to extract config schema: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to extract config schema: {str(e)}")
        
        @router.get("/config/schema/sections", response_model=Dict[str, Any])
        async def get_section_order_and_titles():
            """
            Get section order and titles for frontend auto-generation
            
            Returns:
            - section_order: Array of section names in logical display order
            - section_titles: Mapping of section names to display titles with emojis
            - total_sections: Total number of available sections
            
            This endpoint enables the frontend to auto-generate section lists
            instead of using hardcoded arrays.
            """
            try:
                return AutoSchemaRegistry.get_section_order_and_titles()
            except Exception as e:
                logger.error(f"Failed to get section order and titles: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get section order and titles: {str(e)}")
        
        @router.get("/config/schema/{section_name}", response_model=Dict[str, Any])
        async def get_section_schema(section_name: str):
            """
            Get specific section schema with field types, defaults, constraints
            
            Parameters:
            - section_name: Configuration section (tts, audio, asr, llm, system, etc.)
            
            Returns detailed schema information for the specified section
            including field metadata needed for automatic widget generation.
            """
            try:
                section_model = self._get_section_model(section_name)
                if not section_model:
                    raise HTTPException(status_code=404, detail=f"Configuration section '{section_name}' not found")
                
                schema = self._extract_model_schema(section_model)
                return schema
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get section schema for {section_name}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get section schema: {str(e)}")
        
        @router.put("/config/sections/{section_name}", response_model=ConfigUpdateResponse)
        async def update_config_section(section_name: str, data: dict):
            """
            Update specific TOML section with file-based hot-reload trigger
            
            Parameters:
            - section_name: Configuration section to update (tts, audio, asr, etc.)
            - data: Section configuration data (validated against Pydantic model)
            
            This endpoint:
            1. Validates data against the section's Pydantic model
            2. Creates a timestamped backup of current configuration
            3. Updates the configuration file
            4. Triggers automatic hot-reload via file modification
            """
            try:
                # 1. Load current configuration
                current_config = await self.config_manager.load_config(self.active_config_path)
                
                # 2. Validate new section data against Pydantic model
                section_model = self._get_section_model(section_name)
                if not section_model:
                    raise HTTPException(status_code=404, detail=f"Configuration section '{section_name}' not found")
                
                validated_data = section_model(**data)
                
                # 3. Update section in current config
                setattr(current_config, section_name, validated_data)
                
                # 4. Create backup before saving changes
                backup_path = await self._create_config_backup(self.active_config_path)
                
                # 5. Save updated configuration to file
                # This triggers existing hot-reload via file modification
                success = await self.config_manager.save_config(current_config, self.active_config_path)
                
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to save configuration")
                
                return ConfigUpdateResponse(
                    success=True,
                    message=f"Configuration section '{section_name}' updated successfully",
                    reload_triggered=True,
                    backup_created=str(backup_path) if backup_path else None
                )
                
            except ValidationError as e:
                logger.error(f"Validation error for section {section_name}: {e}")
                # Return validation errors in API format
                raise HTTPException(
                    status_code=422, 
                    detail={
                        "error": "Validation error",
                        "validation_errors": e.errors()
                    }
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to update section {section_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.post("/config/sections/{section_name}/validate", response_model=ConfigValidationResponse)
        async def validate_config_section(section_name: str, data: dict):
            """
            Validate section configuration using existing Pydantic models
            
            Parameters:
            - section_name: Configuration section to validate
            - data: Configuration data to validate
            
            Performs dry-run validation without saving changes.
            Returns validation results with detailed error information if validation fails.
            """
            try:
                section_model = self._get_section_model(section_name)
                if not section_model:
                    raise HTTPException(status_code=404, detail=f"Configuration section '{section_name}' not found")
                
                validated_data = section_model(**data)
                return ConfigValidationResponse(
                    success=True,
                    valid=True,
                    data=validated_data.model_dump()
                )
            except ValidationError as e:
                return ConfigValidationResponse(
                    success=True,
                    valid=False,
                    validation_errors=e.errors()
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to validate section {section_name}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @router.get("/config/providers/{component_name}", response_model=Dict[str, Any])
        async def get_available_providers(component_name: str):
            """
            Get available providers for dynamic dropdown population
            
            Parameters:
            - component_name: Component type (tts, audio, asr, llm, voice_trigger, nlu, text_processor)
            
            Returns provider information including:
            - Provider names and descriptions
            - Version information
            - Default enablement status
            - Provider capabilities
            """
            try:
                # Use dynamic loader to discover available providers
                from ..utils.loader import dynamic_loader
                
                # Map component names to provider entry-point groups
                provider_groups = {
                    "tts": "irene.providers.tts",
                    "audio": "irene.providers.audio", 
                    "asr": "irene.providers.asr",
                    "llm": "irene.providers.llm",
                    "voice_trigger": "irene.providers.voice_trigger",
                    "nlu": "irene.providers.nlu",
                    "text_processor": "irene.providers.text_processing"
                }
                
                entry_point_group = provider_groups.get(component_name)
                if not entry_point_group:
                    raise HTTPException(status_code=404, detail=f"Component '{component_name}' not found")
                
                providers = dynamic_loader.discover_providers(entry_point_group)
                
                # Return provider names and metadata
                provider_info = {}
                for name, provider_class in providers.items():
                    provider_info[name] = {
                        "name": name,
                        "description": getattr(provider_class, "description", f"{name} provider"),
                        "version": getattr(provider_class, "version", "unknown"),
                        "enabled_by_default": getattr(provider_class, "enabled_by_default", False)
                    }
                
                return provider_info
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get providers for {component_name}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get providers: {str(e)}")
        
        @router.get("/config/audio/devices", response_model=AudioDevicesResponse)
        async def get_available_audio_devices():
            """
            Get available audio input devices for microphone configuration
            
            Returns comprehensive device information including capabilities,
            formatted according to the AudioDevicesResponse schema.
            """
            try:
                from ..utils.audio_devices import list_audio_input_devices, is_audio_available
                
                if not is_audio_available():
                    return AudioDevicesResponse(
                        success=False,
                        devices=[],
                        total_count=0,
                        message="Audio device detection not available. Install audio dependencies with: uv add irene-voice-assistant[audio-input]"
                    )
                
                device_data = list_audio_input_devices()
                
                # Convert to Pydantic models
                devices = [AudioDeviceInfo(**device) for device in device_data]
                
                return AudioDevicesResponse(
                    success=True,
                    devices=devices,
                    total_count=len(devices),
                    message=f"Found {len(devices)} audio input device(s)" if devices else "No audio input devices found"
                )
                
            except Exception as e:
                logger.error(f"Failed to get audio devices: {e}")
                return AudioDevicesResponse(
                    success=False,
                    devices=[],
                    total_count=0,
                    message=f"Failed to get audio devices: {str(e)}"
                )

        @router.get("/config/audio/output-devices", response_model=AudioDevicesResponse)
        async def get_available_audio_output_devices():
            """
            Get available audio output devices for audio provider configuration
            
            Returns comprehensive device information including capabilities,
            formatted according to the AudioDevicesResponse schema.
            """
            try:
                from ..utils.audio_devices import list_audio_output_devices, is_audio_available
                
                if not is_audio_available():
                    return AudioDevicesResponse(
                        success=False,
                        devices=[],
                        total_count=0,
                        message="Audio device detection not available. Install audio dependencies with: uv add irene-voice-assistant[audio-input]"
                    )
                
                device_data = list_audio_output_devices()
                
                # Convert to Pydantic models
                devices = [AudioDeviceInfo(**device) for device in device_data]
                
                return AudioDevicesResponse(
                    success=True,
                    devices=devices,
                    total_count=len(devices),
                    message=f"Found {len(devices)} audio output device(s)" if devices else "No audio output devices found"
                )
                
            except Exception as e:
                logger.error(f"Failed to get audio output devices: {e}")
                return AudioDevicesResponse(
                    success=False,
                    devices=[],
                    total_count=0,
                    message=f"Failed to get audio output devices: {str(e)}"
                )

        @router.get("/config/status", response_model=ConfigStatusResponse)
        async def get_configuration_status():
            """
            Get configuration system status and health
            
            Returns comprehensive status information including:
            - Configuration file location and existence
            - Hot-reload monitoring status
            - Component initialization status
            - File metadata (size, last modified)
            """
            try:
                config_exists = self.active_config_path and self.active_config_path.exists()
                
                status_data = {
                    "success": True,
                    "config_path": str(self.active_config_path) if self.active_config_path else None,
                    "config_exists": config_exists,
                    "hot_reload_active": len(self.config_manager._file_watchers) > 0,
                    "component_initialized": self.initialized
                }
                
                if config_exists:
                    stat = self.active_config_path.stat()
                    status_data.update({
                        "last_modified": stat.st_mtime,
                        "file_size": stat.st_size
                    })
                
                return ConfigStatusResponse(**status_data)
                
            except Exception as e:
                logger.error(f"Failed to get configuration status: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")
        
        # ============================================================
        # RAW TOML ENDPOINTS (Phase 4)
        # ============================================================
        
        @router.get("/config/raw", response_model=RawTomlResponse)
        async def get_raw_toml():
            """
            Get raw TOML configuration content with comments preserved
            
            Returns the original TOML file content exactly as stored on disk,
            including all comments, formatting, and whitespace. This is used
            for the TOML preview functionality in the frontend.
            """
            try:
                # Load raw TOML with comments
                doc = await self.config_manager.load_raw_toml(self.active_config_path)
                
                # Convert to string with formatting preserved
                import tomlkit
                toml_content = tomlkit.dumps(doc)
                
                # Get file metadata
                config_exists = self.active_config_path and self.active_config_path.exists()
                if not config_exists:
                    raise HTTPException(status_code=404, detail="Configuration file not found")
                    
                stat = self.active_config_path.stat()
                
                return RawTomlResponse(
                    success=True,
                    toml_content=toml_content,
                    config_path=str(self.active_config_path),
                    file_size=stat.st_size,
                    last_modified=stat.st_mtime
                )
                
            except Exception as e:
                logger.error(f"Failed to get raw TOML: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get raw TOML: {str(e)}")
        
        @router.put("/config/raw", response_model=RawTomlSaveResponse)
        async def save_raw_toml(request: RawTomlRequest):
            """
            Save raw TOML content with comment preservation
            
            Saves the provided TOML content directly to the configuration file,
            preserving all comments and formatting. Optionally validates the
            content before saving and creates automatic backups.
            """
            try:
                # Optionally validate before saving
                if request.validate_before_save:
                    validation_result = await self.config_manager.validate_raw_toml(request.toml_content)
                    if not validation_result["valid"]:
                        raise HTTPException(
                            status_code=400, 
                            detail=f"TOML validation failed: {validation_result.get('errors', [])}"
                        )
                
                # Save raw TOML with backup
                success = await self.config_manager.save_raw_toml(
                    request.toml_content, 
                    self.active_config_path
                )
                
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to save TOML content")
                
                # Get backup path from logs or assume created
                backup_path = f"{self.active_config_path.parent}/backups/{self.active_config_path.stem}_backup_*.toml"
                
                return RawTomlSaveResponse(
                    success=True,
                    message="Raw TOML configuration saved successfully",
                    backup_created=backup_path,
                    config_cached=True
                )
                
            except Exception as e:
                logger.error(f"Failed to save raw TOML: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to save raw TOML: {str(e)}")
        
        @router.post("/config/raw/validate", response_model=RawTomlValidationResponse)
        async def validate_raw_toml(request: RawTomlValidationRequest):
            """
            Validate raw TOML content without saving
            
            Validates the provided TOML content for:
            - TOML syntax correctness
            - Pydantic model validation against CoreConfig
            - Configuration completeness and consistency
            """
            try:
                validation_result = await self.config_manager.validate_raw_toml(request.toml_content)
                
                return RawTomlValidationResponse(
                    success=True,
                    valid=validation_result["valid"],
                    data=validation_result.get("data"),
                    errors=validation_result.get("errors")
                )
                
            except Exception as e:
                logger.error(f"Failed to validate raw TOML: {e}")
                return RawTomlValidationResponse(
                    success=False,
                    valid=False,
                    data=None,
                    errors=[{"msg": f"Validation error: {str(e)}", "type": "validation_error"}]
                )
        
        @router.post("/config/sections/{section_name}/toml", response_model=SectionToTomlResponse)
        async def apply_section_to_toml(section_name: str, request: SectionToTomlRequest):
            """
            Apply section changes to raw TOML while preserving comments
            
            Takes changes to a specific configuration section and applies them
            to the current TOML file while preserving all comments and formatting.
            Returns the updated TOML content without saving to disk.
            """
            try:
                # Apply section to TOML with comments preserved
                updated_toml = await self.config_manager.apply_section_to_raw_toml(
                    section_name,
                    request.section_data,
                    self.active_config_path
                )
                
                return SectionToTomlResponse(
                    success=True,
                    toml_content=updated_toml,
                    section_name=section_name,
                    comments_preserved=True
                )
                
            except Exception as e:
                logger.error(f"Failed to apply section {section_name} to TOML: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to apply section to TOML: {str(e)}")
        
        return router
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for configuration API endpoints"""
        return "/configuration"
    
    def get_api_tags(self) -> List[str]:
        """Get OpenAPI tags for configuration endpoints"""
        return ["Configuration Management"]
    
    def _get_section_model(self, section_name: str) -> Optional[Type[BaseModel]]:
        """Get Pydantic model for configuration section (auto-generated)"""
        return AutoSchemaRegistry.get_section_model(section_name)
    
    def _extract_config_schema(self) -> Dict[str, Any]:
        """Extract complete configuration schema (auto-generated)"""
        return AutoSchemaRegistry.extract_all_schemas()
    
    def _extract_model_schema(self, model_class: Type[BaseModel]) -> Dict[str, Any]:
        """Extract field metadata from Pydantic model for widget generation"""
        if not model_class:
            return {}
        
        try:
            from pydantic_core import PydanticUndefined
        except ImportError:
            # Fallback for older Pydantic versions
            PydanticUndefined = None
            
        schema = {
            "fields": {},
            "title": getattr(model_class, "__name__", "Configuration"),
            "description": getattr(model_class, "__doc__", "").strip() if getattr(model_class, "__doc__", "") else ""
        }
        
        # Get Pydantic model fields
        model_fields = model_class.model_fields if hasattr(model_class, 'model_fields') else {}
        
        for field_name, field_info in model_fields.items():
            try:
                # Safely extract field information
                field_type = self._get_field_type(field_info)
                
                # Get field description - check multiple possible locations
                description = ""
                if hasattr(field_info, 'description') and field_info.description:
                    description = field_info.description
                elif hasattr(field_info, 'json_schema_extra') and field_info.json_schema_extra:
                    description = field_info.json_schema_extra.get('description', '')
                
                # For Pydantic v2, check if field is required by looking at default value
                is_required = True
                default_value = None
                
                if hasattr(field_info, 'default') and PydanticUndefined is not None:
                    if field_info.default is not PydanticUndefined:
                        is_required = False
                        default_value = field_info.default
                elif hasattr(field_info, 'default'):
                    # Fallback for when PydanticUndefined is not available
                    try:
                        if field_info.default is not ...:  # Ellipsis is often used as undefined
                            is_required = False
                            default_value = field_info.default
                    except:
                        pass
                
                field_schema = {
                    "type": field_type,
                    "description": description,
                    "required": is_required,
                    "default": default_value
                }
                
                # For object types (nested models), extract nested schema
                if field_type == "object" and hasattr(field_info, 'annotation'):
                    nested_schema = self._extract_nested_object_schema(field_info.annotation)
                    if nested_schema:
                        field_schema["properties"] = nested_schema
                
                # Add constraints if available (from field annotations)
                if hasattr(field_info, 'json_schema_extra') and field_info.json_schema_extra:
                    field_schema.update(field_info.json_schema_extra)
                
                schema["fields"][field_name] = field_schema
                
            except Exception as e:
                logger.warning(f"Failed to extract schema for field {field_name}: {e}")
                # Add a basic fallback schema
                schema["fields"][field_name] = {
                    "type": "string",
                    "description": f"Field {field_name}",
                    "required": False,
                    "default": None
                }
        
        return schema
    
    def _get_field_type(self, field_info) -> str:
        """Determine field type for widget generation"""
        try:
            # Extract type from Pydantic field info
            field_type = field_info.annotation if hasattr(field_info, 'annotation') else str
            
            return self._get_field_type_from_annotation(field_type)
        except Exception as e:
            logger.warning(f"Failed to determine field type: {e}")
            return "string"  # Safe fallback
    
    def _get_field_type_from_annotation(self, annotation) -> str:
        """Helper to get field type from type annotation"""
        try:
            # Handle direct types
            if annotation == bool:
                return "boolean"
            elif annotation == int:
                return "integer"
            elif annotation == float:
                return "number"
            elif annotation == str:
                return "string"
            elif hasattr(annotation, '__origin__'):
                # Handle generic types like List, Dict, Optional
                from typing import Union
                origin = annotation.__origin__
                if origin == list:
                    return "array"
                elif origin == dict:
                    return "object"
                elif origin == Union:
                    # Handle Optional types
                    args = annotation.__args__
                    if len(args) == 2 and type(None) in args:
                        # Optional type - get the non-None type
                        non_none_type = next(arg for arg in args if arg != type(None))
                        return self._get_field_type_from_annotation(non_none_type)
            
            # Check if it's a Pydantic BaseModel (nested configuration)
            if hasattr(annotation, '__bases__') and any(
                issubclass(base, BaseModel) for base in annotation.__bases__ 
                if hasattr(base, '__name__')
            ):
                return "object"  # Nested Pydantic models should be objects
            
            # Check if it's an Enum
            if hasattr(annotation, '__bases__') and any(base.__name__ == 'Enum' for base in annotation.__bases__):
                return "string"  # Enums are represented as string choices
                
            return "string"  # Default fallback
        except Exception as e:
            logger.warning(f"Failed to parse annotation {annotation}: {e}")
            return "string"
    
    def _extract_nested_object_schema(self, annotation) -> Optional[Dict[str, Any]]:
        """Extract schema for nested Pydantic models"""
        try:
            # Handle Optional[Model] types
            from typing import Union
            if hasattr(annotation, '__origin__') and annotation.__origin__ == Union:
                args = annotation.__args__
                if len(args) == 2 and type(None) in args:
                    # Optional type - get the non-None type
                    annotation = next(arg for arg in args if arg != type(None))
            
            # Check if it's a Pydantic BaseModel
            if (hasattr(annotation, '__bases__') and 
                any(issubclass(base, BaseModel) for base in annotation.__bases__ if hasattr(base, '__name__'))):
                
                # Recursively extract schema for the nested model
                nested_model_schema = self._extract_model_schema(annotation)
                return nested_model_schema.get("fields", {})
            
            return None
        except Exception as e:
            logger.warning(f"Failed to extract nested schema for {annotation}: {e}")
            return None
    
    async def _create_config_backup(self, config_path: Path) -> Optional[Path]:
        """Create timestamped backup of current configuration in backups subfolder"""
        if not config_path or not config_path.exists():
            return None
            
        # Create backups directory if it doesn't exist
        backups_dir = config_path.parent / "backups"
        backups_dir.mkdir(exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{config_path.stem}_backup_{timestamp}{config_path.suffix}"
        backup_path = backups_dir / backup_filename
        
        try:
            shutil.copy2(config_path, backup_path)
            logger.info(f"Created configuration backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create config backup: {e}")
            return None
