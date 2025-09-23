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
- Auto-generated schema registries (Phase 1 implementation)
"""

import logging

logger = logging.getLogger(__name__)


def validate_schema_integrity() -> None:
    """
    Validate schema integrity at module import.
    Fails fast if critical synchronization issues detected.
    """
    try:
        from .auto_registry import AutoSchemaRegistry
        
        report = AutoSchemaRegistry.validate_schema_coverage()
        
        if not report["valid"]:
            error_msg = f"Schema validation failed: {report['errors']}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        if report["warnings"]:
            for warning in report["warnings"]:
                logger.warning(f"Schema warning: {warning}")
        
        logger.info("Configuration schema validation passed")
        
    except Exception as e:
        logger.error(f"Schema validation failed: {e}")
        raise


def validate_master_config_completeness() -> None:
    """
    Validate that config-master.toml contains sections for ALL provider schemas.
    Ensures master config serves as comprehensive reference database.
    """
    try:
        from .auto_registry import AutoSchemaRegistry
        
        completeness_report = AutoSchemaRegistry.get_master_config_completeness()
        
        if completeness_report["missing_sections"]:
            logger.warning(f"config-master.toml missing provider sections: {completeness_report['missing_sections']}")
            logger.warning("These sections should be added (disabled by default) for comprehensive reference coverage")
        
        if completeness_report["orphaned_sections"]:
            logger.warning(f"config-master.toml has sections without schemas: {completeness_report['orphaned_sections']}")
        
        logger.info(f"Master config completeness: {completeness_report['coverage_percentage']:.1f}%")
        
    except Exception as e:
        logger.error(f"Master config validation failed: {e}")
        # Non-fatal - don't block startup, but log the issue


# Validate schemas on module import
validate_schema_integrity()
validate_master_config_completeness()

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