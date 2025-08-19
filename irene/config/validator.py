"""
Configuration Validation System - Comprehensive configuration validation

This module provides comprehensive validation for the Irene Voice Assistant
configuration system, implementing the validation requirements from Phase 4.

Features:
- System architecture validation
- Component consistency checks
- Provider availability validation
- Workflow dependency validation
- Asset accessibility validation
- Environment variable validation
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum

from .models import CoreConfig


logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation severity levels"""
    ERROR = "error"      # Configuration is invalid and will cause failures
    WARNING = "warning"  # Configuration issues that may cause problems
    INFO = "info"        # Informational notes about configuration


@dataclass
class ValidationResult:
    """Result of a configuration validation check"""
    level: ValidationLevel
    category: str
    message: str
    component: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationSummary:
    """Summary of all validation results"""
    results: List[ValidationResult]
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    
    def __post_init__(self):
        """Calculate counts after initialization"""
        self.errors = sum(1 for r in self.results if r.level == ValidationLevel.ERROR)
        self.warnings = sum(1 for r in self.results if r.level == ValidationLevel.WARNING)
        self.infos = sum(1 for r in self.results if r.level == ValidationLevel.INFO)
    
    @property
    def is_valid(self) -> bool:
        """Check if configuration is valid (no errors)"""
        return self.errors == 0
    
    @property
    def has_issues(self) -> bool:
        """Check if configuration has any issues"""
        return len(self.results) > 0


class ConfigValidator:
    """Comprehensive configuration validation"""
    
    def __init__(self):
        self.results: List[ValidationResult] = []
        
    def validate_architecture(self, config: CoreConfig) -> ValidationSummary:
        """
        Validate entire configuration architecture
        
        Args:
            config: CoreConfig object to validate
            
        Returns:
            ValidationSummary: Complete validation results
        """
        self.results.clear()
        
        # Run all validation checks
        self._validate_system_capabilities(config)
        self._validate_component_consistency(config)
        self._validate_provider_availability(config)
        self._validate_workflow_dependencies(config)
        self._validate_asset_accessibility(config)
        self._validate_input_configuration(config)
        self._validate_environment_variables(config)
        
        # Create summary
        summary = ValidationSummary(results=self.results.copy())
        
        logger.info(f"Configuration validation completed: {summary.errors} errors, "
                   f"{summary.warnings} warnings, {summary.infos} info messages")
        
        return summary
    
    def _validate_system_capabilities(self, config: CoreConfig) -> None:
        """Validate system capability configuration"""
        system = config.system
        inputs = config.inputs
        components = config.components
        
        # Check microphone capability consistency
        if system.microphone_enabled and not inputs.microphone:
            self._add_result(
                ValidationLevel.WARNING,
                "system_capabilities",
                "Microphone hardware is enabled but microphone input source is disabled",
                suggestion="Either disable system.microphone_enabled or enable inputs.microphone"
            )
        
        if inputs.microphone and not system.microphone_enabled:
            self._add_result(
                ValidationLevel.ERROR,
                "system_capabilities", 
                "Microphone input source is enabled but microphone hardware capability is disabled",
                suggestion="Enable system.microphone_enabled for microphone input"
            )
        
        # Check audio playback capability consistency
        if components.tts and not system.audio_playback_enabled:
            self._add_result(
                ValidationLevel.ERROR,
                "system_capabilities",
                "TTS component is enabled but audio playback capability is disabled",
                suggestion="Enable system.audio_playback_enabled for TTS output"
            )
        
        if components.audio and not system.audio_playback_enabled:
            self._add_result(
                ValidationLevel.ERROR,
                "system_capabilities",
                "Audio component is enabled but audio playback capability is disabled", 
                suggestion="Enable system.audio_playback_enabled for audio output"
            )
        
        # Check web API service consistency
        if inputs.web and not system.web_api_enabled:
            self._add_result(
                ValidationLevel.ERROR,
                "system_capabilities",
                "Web input source is enabled but web API service is disabled",
                suggestion="Enable system.web_api_enabled for web interface"
            )
        
        # Port conflict checks
        if system.web_api_enabled and system.metrics_enabled:
            if system.web_port == system.metrics_port:
                self._add_result(
                    ValidationLevel.ERROR,
                    "system_capabilities", 
                    f"Web API and metrics services cannot use the same port: {system.web_port}",
                    suggestion="Configure different ports for web_port and metrics_port"
                )
    
    def _validate_component_consistency(self, config: CoreConfig) -> None:
        """Validate component configuration consistency"""
        components = config.components
        
        # Check component dependencies
        if components.tts and not components.audio:
            self._add_result(
                ValidationLevel.WARNING,
                "component_dependencies",
                "TTS component is enabled but Audio component is disabled",
                component="tts",
                suggestion="Enable Audio component for TTS output, or use console TTS provider"
            )
        
        if components.voice_trigger and not (components.asr and config.inputs.microphone):
            self._add_result(
                ValidationLevel.WARNING,
                "component_dependencies",
                "Voice trigger component is enabled but ASR component or microphone input is disabled",
                component="voice_trigger",
                suggestion="Enable ASR component and microphone input for voice trigger functionality"
            )
        
        if components.asr and not config.inputs.microphone:
            self._add_result(
                ValidationLevel.WARNING,
                "component_dependencies",
                "ASR component is enabled but microphone input is disabled",
                component="asr",
                suggestion="Enable microphone input for ASR functionality"
            )
        
        # Check essential components
        if not components.intent_system:
            self._add_result(
                ValidationLevel.WARNING,
                "component_consistency",
                "Intent system component is disabled - this may break core functionality",
                component="intent_system",
                suggestion="Consider enabling intent_system for full functionality"
            )
        
        # Check profile consistency 
        voice_components = [components.tts, components.asr, components.audio, components.voice_trigger]
        api_components = [components.llm, components.nlu, components.text_processor]
        
        if any(voice_components) and not config.inputs.microphone and not config.inputs.web:
            self._add_result(
                ValidationLevel.WARNING,
                "component_consistency",
                "Voice components are enabled but no suitable input sources are configured",
                suggestion="Enable microphone or web input for voice components"
            )
    
    def _validate_provider_availability(self, config: CoreConfig) -> None:
        """Validate provider configuration and availability"""
        try:
            from ..core.components import discover_providers
            
            # Discover available providers for each component type
            available_providers = {}
            for component_type in ["tts", "audio", "asr", "llm", "voice_trigger", "nlu"]:
                try:
                    providers = discover_providers(f"irene.providers.{component_type}")
                    available_providers[component_type] = set(providers.keys())
                except Exception as e:
                    logger.debug(f"Could not discover {component_type} providers: {e}")
                    available_providers[component_type] = set()
            
            # Validate TTS providers
            if config.components.tts:
                self._validate_component_providers(
                    "tts", config.tts, available_providers.get("tts", set())
                )
            
            # Validate Audio providers
            if config.components.audio:
                self._validate_component_providers(
                    "audio", config.audio, available_providers.get("audio", set())
                )
            
            # Validate ASR providers
            if config.components.asr:
                self._validate_component_providers(
                    "asr", config.asr, available_providers.get("asr", set())
                )
            
            # Validate LLM providers
            if config.components.llm:
                self._validate_component_providers(
                    "llm", config.llm, available_providers.get("llm", set())
                )
            
            # Validate Voice Trigger providers
            if config.components.voice_trigger:
                self._validate_component_providers(
                    "voice_trigger", config.voice_trigger, available_providers.get("voice_trigger", set())
                )
            
        except ImportError as e:
            self._add_result(
                ValidationLevel.WARNING,
                "provider_availability",
                f"Could not validate provider availability: {e}",
                suggestion="Provider validation skipped - ensure system is properly installed"
            )
    
    def _validate_component_providers(self, component_name: str, component_config: Any, available_providers: Set[str]) -> None:
        """Validate providers for a specific component"""
        if not hasattr(component_config, 'default_provider') or not hasattr(component_config, 'providers'):
            return
        
        default_provider = component_config.default_provider
        configured_providers = set(component_config.providers.keys())
        fallback_providers = getattr(component_config, 'fallback_providers', [])
        
        # Check if default provider is available
        if default_provider not in available_providers:
            self._add_result(
                ValidationLevel.ERROR,
                "provider_availability",
                f"Default {component_name} provider '{default_provider}' is not available",
                component=component_name,
                suggestion=f"Choose from available providers: {sorted(available_providers)}"
            )
        
        # Check if default provider is configured
        if default_provider not in configured_providers:
            self._add_result(
                ValidationLevel.WARNING,
                "provider_configuration",
                f"Default {component_name} provider '{default_provider}' is not configured",
                component=component_name,
                suggestion=f"Add configuration section for {component_name}.providers.{default_provider}"
            )
        
        # Check fallback providers
        for fallback in fallback_providers:
            if fallback not in available_providers:
                self._add_result(
                    ValidationLevel.WARNING,
                    "provider_availability",
                    f"Fallback {component_name} provider '{fallback}' is not available",
                    component=component_name
                )
        
        # Check for unused configured providers
        unused_providers = configured_providers - available_providers
        if unused_providers:
            self._add_result(
                ValidationLevel.INFO,
                "provider_configuration",
                f"Configured {component_name} providers not available: {sorted(unused_providers)}",
                component=component_name,
                suggestion="Remove unused provider configurations or check installation"
            )
    
    def _validate_workflow_dependencies(self, config: CoreConfig) -> None:
        """Validate workflow configuration and dependencies"""
        workflows = config.workflows
        
        # Check default workflow is in enabled list
        if workflows.default not in workflows.enabled:
            self._add_result(
                ValidationLevel.ERROR,
                "workflow_dependencies",
                f"Default workflow '{workflows.default}' is not in enabled workflows list",
                suggestion=f"Add '{workflows.default}' to workflows.enabled or change default workflow"
            )
        
        # Check for workflow-component dependencies
        if "voice_assistant" in workflows.enabled or workflows.default == "voice_assistant":
            voice_components_enabled = any([
                config.components.tts,
                config.components.asr, 
                config.components.audio,
                config.components.voice_trigger
            ])
            
            if not voice_components_enabled:
                self._add_result(
                    ValidationLevel.WARNING,
                    "workflow_dependencies",
                    "Voice assistant workflow is enabled but no voice components are configured",
                    suggestion="Enable TTS, ASR, Audio, or Voice Trigger components for voice workflows"
                )
        
        if "unified_voice_assistant" in workflows.enabled or workflows.default == "unified_voice_assistant":
            if not config.components.intent_system:
                self._add_result(
                    ValidationLevel.WARNING,
                    "workflow_dependencies",
                    "Unified voice assistant workflow requires intent system component",
                    suggestion="Enable intent_system component for unified workflows"
                )
    
    def _validate_asset_accessibility(self, config: CoreConfig) -> None:
        """Validate asset configuration and accessibility"""
        assets = config.assets
        
        # Check if assets root directory exists or can be created
        assets_root = assets.assets_root
        
        if not assets_root.exists():
            if assets.auto_create_dirs:
                self._add_result(
                    ValidationLevel.INFO,
                    "asset_accessibility",
                    f"Assets root directory will be created: {assets_root}",
                    suggestion="Ensure the parent directory has write permissions"
                )
            else:
                self._add_result(
                    ValidationLevel.WARNING,
                    "asset_accessibility",
                    f"Assets root directory does not exist: {assets_root}",
                    suggestion="Create the directory or enable auto_create_dirs"
                )
        else:
            # Check directory permissions
            if not assets_root.is_dir():
                self._add_result(
                    ValidationLevel.ERROR,
                    "asset_accessibility",
                    f"Assets root path exists but is not a directory: {assets_root}"
                )
            elif not os.access(assets_root, os.R_OK | os.W_OK):
                self._add_result(
                    ValidationLevel.ERROR,
                    "asset_accessibility",
                    f"Assets root directory lacks read/write permissions: {assets_root}"
                )
        
        # Check subdirectory access
        for subdir_name in ["models", "cache", "credentials"]:
            subdir = getattr(assets, f"{subdir_name}_root")
            if subdir.exists() and not subdir.is_dir():
                self._add_result(
                    ValidationLevel.ERROR,
                    "asset_accessibility",
                    f"Asset {subdir_name} path exists but is not a directory: {subdir}"
                )
    
    def _validate_input_configuration(self, config: CoreConfig) -> None:
        """Validate input source configuration"""
        inputs = config.inputs
        
        # Check default input is enabled
        if inputs.default_input not in ["microphone", "web", "cli"]:
            self._add_result(
                ValidationLevel.ERROR,
                "input_configuration",
                f"Invalid default input source: {inputs.default_input}",
                suggestion="Set default_input to 'microphone', 'web', or 'cli'"
            )
        
        default_enabled = getattr(inputs, inputs.default_input, False)
        if not default_enabled:
            self._add_result(
                ValidationLevel.ERROR,
                "input_configuration",
                f"Default input source '{inputs.default_input}' is not enabled",
                suggestion=f"Enable inputs.{inputs.default_input} or change default_input"
            )
        
        # Check at least one input is enabled
        enabled_inputs = [inputs.microphone, inputs.web, inputs.cli]
        if not any(enabled_inputs):
            self._add_result(
                ValidationLevel.ERROR,
                "input_configuration",
                "No input sources are enabled",
                suggestion="Enable at least one input source (microphone, web, or cli)"
            )
        
        # Check microphone configuration consistency
        if inputs.microphone:
            mic_config = inputs.microphone_config
            if mic_config.sample_rate <= 0:
                self._add_result(
                    ValidationLevel.ERROR,
                    "input_configuration",
                    f"Invalid microphone sample rate: {mic_config.sample_rate}",
                    suggestion="Set a positive sample rate (e.g., 16000)"
                )
            
            if mic_config.channels not in [1, 2]:
                self._add_result(
                    ValidationLevel.WARNING,
                    "input_configuration",
                    f"Unusual microphone channel count: {mic_config.channels}",
                    suggestion="Typically use 1 (mono) or 2 (stereo) channels"
                )
    
    def _validate_environment_variables(self, config: CoreConfig) -> None:
        """Validate environment variable configuration and availability"""
        import os
        import re
        
        # Find all environment variable references in the configuration
        env_var_pattern = r'\$\{([^}]+)\}'
        required_env_vars = set()
        
        def extract_env_vars(obj: Any, path: str = "") -> None:
            """Recursively extract environment variable references"""
            if isinstance(obj, str):
                matches = re.findall(env_var_pattern, obj)
                for match in matches:
                    required_env_vars.add((match, path))
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    extract_env_vars(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    extract_env_vars(item, f"{path}[{i}]" if path else f"[{i}]")
            elif hasattr(obj, '__dict__'):
                extract_env_vars(obj.__dict__, path)
        
        # Extract environment variables from configuration
        extract_env_vars(config.model_dump())
        
        # Check each required environment variable
        missing_vars = []
        for env_var, config_path in required_env_vars:
            if os.getenv(env_var) is None:
                missing_vars.append((env_var, config_path))
        
        # Report missing environment variables
        for env_var, config_path in missing_vars:
            self._add_result(
                ValidationLevel.ERROR,
                "environment_variables",
                f"Required environment variable '{env_var}' is not set (used in {config_path})",
                suggestion=f"Set environment variable {env_var} or update configuration"
            )
        
        # Report found environment variables
        found_vars = len(required_env_vars) - len(missing_vars)
        if found_vars > 0:
            self._add_result(
                ValidationLevel.INFO,
                "environment_variables",
                f"Found {found_vars} configured environment variables",
                suggestion=f"Missing {len(missing_vars)} required environment variables" if missing_vars else None
            )
    
    def _add_result(
        self, 
        level: ValidationLevel, 
        category: str, 
        message: str, 
        component: Optional[str] = None,
        suggestion: Optional[str] = None
    ) -> None:
        """Add a validation result"""
        result = ValidationResult(
            level=level,
            category=category,
            message=message,
            component=component,
            suggestion=suggestion
        )
        self.results.append(result)


def validate_configuration(config: CoreConfig) -> ValidationSummary:
    """
    Convenience function to validate a configuration
    
    Args:
        config: CoreConfig object to validate
        
    Returns:
        ValidationSummary: Validation results
    """
    validator = ConfigValidator()
    return validator.validate_architecture(config)


def print_validation_results(summary: ValidationSummary, verbose: bool = False) -> None:
    """
    Print validation results in a human-readable format
    
    Args:
        summary: ValidationSummary to print
        verbose: Whether to show info-level messages
    """
    print(f"\n{'='*60}")
    print("CONFIGURATION VALIDATION RESULTS")
    print(f"{'='*60}")
    
    if summary.is_valid:
        print("✅ Configuration is VALID")
    else:
        print("❌ Configuration has ERRORS")
    
    print(f"Summary: {summary.errors} errors, {summary.warnings} warnings, {summary.infos} info messages")
    
    if not summary.results:
        print("No validation issues found.")
        return
    
    # Group results by level
    errors = [r for r in summary.results if r.level == ValidationLevel.ERROR]
    warnings = [r for r in summary.results if r.level == ValidationLevel.WARNING]
    infos = [r for r in summary.results if r.level == ValidationLevel.INFO]
    
    # Print errors
    if errors:
        print(f"\n🚨 ERRORS ({len(errors)}):")
        for result in errors:
            print(f"  ❌ [{result.category}] {result.message}")
            if result.component:
                print(f"     Component: {result.component}")
            if result.suggestion:
                print(f"     Suggestion: {result.suggestion}")
            print()
    
    # Print warnings
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for result in warnings:
            print(f"  ⚠️  [{result.category}] {result.message}")
            if result.component:
                print(f"     Component: {result.component}")
            if result.suggestion:
                print(f"     Suggestion: {result.suggestion}")
            print()
    
    # Print info messages (only if verbose)
    if infos and verbose:
        print(f"\n💡 INFO ({len(infos)}):")
        for result in infos:
            print(f"  💡 [{result.category}] {result.message}")
            if result.suggestion:
                print(f"     Note: {result.suggestion}")
            print()


# Import os for file permission checks
import os
