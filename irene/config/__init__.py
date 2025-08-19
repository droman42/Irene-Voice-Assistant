"""
Configuration Management - V14 Clean Architecture

Provides type-safe configuration management with validation,
schema support, and clean separation of concerns.

V14 Features:
- Clean architecture with system/inputs/components/workflows/assets
- Component-specific configurations
- Environment variable integration  
- Automatic v13→v14 migration
- Schema validation and versioning
"""

# Core configuration models
from .models import (
    CoreConfig, 
    SystemConfig, InputConfig, ComponentConfig, AssetConfig, WorkflowConfig,
    MicrophoneInputConfig, WebInputConfig, CLIInputConfig,
    TTSConfig, AudioConfig, ASRConfig, LLMConfig, 
    VoiceTriggerConfig, NLUConfig, TextProcessorConfig, IntentSystemConfig,
    create_default_config, create_config_from_profile,
    create_voice_profile, create_api_profile, create_headless_profile,
    EnvironmentVariableResolver, ComponentLoader, ComponentRegistry
)

# Configuration management
from .manager import ConfigManager, ConfigValidationError

# Configuration resolution utilities
from .resolver import (
    extract_config_by_path, 
    is_component_enabled_by_name, 
    get_component_config_by_name
)

# Schema validation and versioning
from .schemas import (
    SchemaValidator, SchemaVersion, CURRENT_SCHEMA_VERSION,
    get_schema_version, validate_schema_compatibility
)

# Migration utilities
from .migration import (
    migrate_config, 
    V13ToV14Migrator, 
    ConfigurationCompatibilityChecker,
    ConfigurationMigrationError,
    create_migration_backup
)

__all__ = [
    # Core configuration
    "CoreConfig",
    "SystemConfig",
    "MicrophoneInputConfig",
    "WebInputConfig", 
    "CLIInputConfig", "InputConfig", "ComponentConfig", "AssetConfig", "WorkflowConfig",
    
    # Component-specific configurations
    "TTSConfig", "AudioConfig", "ASRConfig", "LLMConfig", 
    "VoiceTriggerConfig", "NLUConfig", "TextProcessorConfig", "IntentSystemConfig",
    
    # Configuration creation utilities
    "create_default_config", "create_config_from_profile",
    "create_voice_profile", "create_api_profile", "create_headless_profile",
    
    # Environment and component utilities
    "EnvironmentVariableResolver", "ComponentLoader", "ComponentRegistry",
    
    # Configuration management
    "ConfigManager", "ConfigValidationError",
    
    # Configuration resolution
    "extract_config_by_path", "is_component_enabled_by_name", "get_component_config_by_name",
    
    # Schema validation
    "SchemaValidator", "SchemaVersion", "CURRENT_SCHEMA_VERSION",
    "get_schema_version", "validate_schema_compatibility",
    
    # Migration support
    "migrate_config", "V13ToV14Migrator", "ConfigurationCompatibilityChecker",
    "ConfigurationMigrationError", "create_migration_backup"
] 