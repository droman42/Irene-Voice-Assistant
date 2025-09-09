"""
Configuration Validation System - Comprehensive configuration validation

This module provides comprehensive validation for the Irene Voice Assistant
configuration system, implementing the validation requirements from Phase 5.

Features:
- System architecture validation
- Component consistency checks
- Provider availability validation
- Workflow dependency validation
- Asset accessibility validation
- Environment variable validation
- Phase 5: Audio configuration validation with fatal error conditions
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
        """Validate workflow configuration and two-level hierarchy dependencies"""
        workflows = config.workflows
        
        # Check default workflow is in enabled list
        if workflows.default not in workflows.enabled:
            self._add_result(
                ValidationLevel.ERROR,
                "workflow_dependencies",
                f"Default workflow '{workflows.default}' is not in enabled workflows list",
                suggestion=f"Add '{workflows.default}' to workflows.enabled or change default workflow"
            )
        
        # Validate unified_voice_assistant workflow if enabled
        if "unified_voice_assistant" in workflows.enabled:
            self._validate_unified_voice_assistant_workflow(config)

    def _validate_unified_voice_assistant_workflow(self, config: CoreConfig) -> None:
        """Validate unified voice assistant workflow two-level configuration"""
        workflow_config = config.workflows.unified_voice_assistant
        components = config.components
        
        # Define stage-to-component mapping
        stage_component_mapping = {
            "voice_trigger_enabled": ("voice_trigger", "Voice Trigger"),
            "asr_enabled": ("asr", "ASR"),
            "text_processing_enabled": ("text_processor", "Text Processing"),
            "nlu_enabled": ("nlu", "NLU"),
            "intent_execution_enabled": ("intent_system", "Intent System"),
            "llm_enabled": ("llm", "LLM"),
            "tts_enabled": ("tts", "TTS"),
            "audio_enabled": ("audio", "Audio")
        }
        
        # Validate each stage against component availability
        for stage_attr, (component_attr, component_display_name) in stage_component_mapping.items():
            stage_enabled = getattr(workflow_config, stage_attr, False)
            component_enabled = getattr(components, component_attr, False)
            
            if stage_enabled and not component_enabled:
                # FATAL ERROR: Workflow stage enabled but component disabled
                self._add_result(
                    ValidationLevel.ERROR,
                    "workflow_component_conflict",
                    f"Unified voice assistant workflow enables '{stage_attr}' but component '{component_attr}' is disabled",
                    suggestion=f"Either enable components.{component_attr} = true or set workflows.unified_voice_assistant.{stage_attr} = false"
                )
            elif not stage_enabled and component_enabled:
                # WARNING: Component loaded but workflow won't use it (wasteful but valid)
                self._add_result(
                    ValidationLevel.WARNING,
                    "workflow_component_waste",
                    f"Component '{component_attr}' is enabled but unified voice assistant workflow has '{stage_attr}' disabled",
                    suggestion=f"Consider setting components.{component_attr} = false to save resources, or enable workflows.unified_voice_assistant.{stage_attr} = true"
                )
        
        # Validate essential components for workflow functionality
        if not workflow_config.intent_execution_enabled:
            self._add_result(
                ValidationLevel.ERROR,
                "workflow_essential_components",
                "Unified voice assistant workflow has intent_execution_enabled = false, but this stage is essential for functionality",
                suggestion="Set workflows.unified_voice_assistant.intent_execution_enabled = true"
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


# ============================================================
# PHASE 5: AUDIO CONFIGURATION VALIDATION
# ============================================================

class ConfigurationError(Exception):
    """Fatal configuration error that prevents startup"""
    pass


class FatalConfigurationError(ConfigurationError):
    """Fatal configuration error that requires immediate shutdown"""
    pass


@dataclass
class AudioConfig:
    """Audio configuration container for resolution logic"""
    sample_rate: Optional[int] = None
    channels: int = 1
    allow_resampling: bool = True
    resample_quality: str = "medium"
    explicit: bool = False  # Whether values were explicitly set by user


class AudioConfigurationValidator:
    """
    Phase 5 audio configuration validator with fatal error conditions
    
    Implements the complete Phase 5 validation workflow:
    - FATAL ERROR VALIDATION: Configuration contradictions cause immediate startup failure
    - Provider Requirement Conflicts: Hard stop if provider requirements contradict config
    - Missing Provider Defaults: Auto-resolve using provider defaults when config is unspecified
    - Cross-component Compatibility: Ensure microphone, ASR, and voice trigger configurations are consistent
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_startup_configuration(self, config: CoreConfig, providers: Dict[str, Any] = None) -> ValidationSummary:
        """
        Perform startup validation with fatal error detection
        
        Args:
            config: Complete system configuration
            providers: Available providers for validation (optional)
            
        Returns:
            ValidationSummary with fatal errors marked
            
        Raises:
            FatalConfigurationError: If configuration has fatal errors
        """
        results = []
        
        # Extract audio configurations
        microphone_config = self._extract_microphone_config(config)
        asr_config = self._extract_asr_config(config)
        voice_trigger_config = self._extract_voice_trigger_config(config)
        
        # Validate individual component configurations
        results.extend(self._validate_individual_configs(microphone_config, asr_config, voice_trigger_config))
        
        # Cross-component compatibility validation
        results.extend(self._validate_cross_component_compatibility(microphone_config, asr_config, voice_trigger_config))
        
        # Provider requirement validation (if providers available)
        if providers:
            results.extend(self._validate_provider_requirements(asr_config, voice_trigger_config, providers))
        
        # Create summary
        summary = ValidationSummary(results)
        summary._calculate_counts()
        
        # Check for fatal errors
        fatal_errors = [r for r in results if r.level == ValidationLevel.ERROR]
        if fatal_errors:
            error_messages = [r.message for r in fatal_errors]
            raise FatalConfigurationError(
                f"Fatal configuration errors detected:\n" + "\n".join(f"- {msg}" for msg in error_messages)
            )
        
        return summary
    
    def resolve_audio_config(self, component_config: Dict[str, Any], provider = None) -> AudioConfig:
        """
        Resolve audio configuration using Phase 5 priority order:
        1. Explicit Configuration: User-defined values are AUTHORITATIVE
        2. Provider Defaults: Used only when configuration is missing/unspecified
        3. System Defaults: Fallback when both config and provider defaults are unavailable
        
        Args:
            component_config: Component configuration dict
            provider: Provider instance with Phase 3 methods (optional)
            
        Returns:
            Resolved AudioConfig
            
        Raises:
            FatalConfigurationError: If configuration cannot be resolved
        """
        resolved = AudioConfig()
        
        # Extract explicit configuration
        resolved.sample_rate = component_config.get('sample_rate')
        resolved.channels = component_config.get('channels', 1)
        resolved.allow_resampling = component_config.get('allow_resampling', True)
        resolved.resample_quality = component_config.get('resample_quality', 'medium')
        resolved.explicit = resolved.sample_rate is not None
        
        if resolved.sample_rate:
            # Configuration is explicit and authoritative
            if provider and hasattr(provider, 'supports_sample_rate'):
                if provider.supports_sample_rate(resolved.sample_rate):
                    return resolved
                elif resolved.allow_resampling:
                    # Will resample from provider's default
                    self.logger.info(f"Configuration specifies {resolved.sample_rate}Hz, will resample from provider default")
                    return resolved
                else:
                    raise FatalConfigurationError(
                        f"Rate mismatch: {resolved.sample_rate}Hz not supported by provider and resampling disabled"
                    )
            return resolved
        else:
            # Use provider defaults if available
            if provider:
                try:
                    if hasattr(provider, 'get_default_sample_rate'):
                        resolved.sample_rate = provider.get_default_sample_rate()
                    if hasattr(provider, 'get_default_channels'):
                        resolved.channels = provider.get_default_channels()
                        
                    self.logger.info(f"Using provider defaults: {resolved.sample_rate}Hz, {resolved.channels} channels")
                    return resolved
                except Exception as e:
                    self.logger.warning(f"Could not get provider defaults: {e}")
            
            # System defaults fallback
            if not resolved.sample_rate:
                resolved.sample_rate = 16000  # Most common default
                self.logger.info("Using system default sample rate: 16000Hz")
            
            return resolved
    
    def _extract_microphone_config(self, config: CoreConfig) -> Dict[str, Any]:
        """Extract microphone configuration"""
        if hasattr(config, 'inputs') and hasattr(config.inputs, 'microphone_config'):
            mic_config = config.inputs.microphone_config
            if hasattr(mic_config, 'model_dump'):
                return mic_config.model_dump()
            elif hasattr(mic_config, 'dict'):
                return mic_config.dict()
        return {}
    
    def _extract_asr_config(self, config: CoreConfig) -> Dict[str, Any]:
        """Extract ASR configuration"""
        if hasattr(config, 'asr'):
            asr_config = config.asr
            if hasattr(asr_config, 'model_dump'):
                return asr_config.model_dump()
            elif hasattr(asr_config, 'dict'):
                return asr_config.dict()
        return {}
    
    def _extract_voice_trigger_config(self, config: CoreConfig) -> Dict[str, Any]:
        """Extract voice trigger configuration"""
        if hasattr(config, 'voice_trigger'):
            vt_config = config.voice_trigger
            if hasattr(vt_config, 'model_dump'):
                return vt_config.model_dump()
            elif hasattr(vt_config, 'dict'):
                return vt_config.dict()
        return {}
    
    def _validate_individual_configs(self, mic_config: Dict[str, Any], asr_config: Dict[str, Any], 
                                   vt_config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate individual component configurations"""
        results = []
        
        # Validate sample rates
        for component_name, component_config in [("microphone", mic_config), ("asr", asr_config), ("voice_trigger", vt_config)]:
            sample_rate = component_config.get('sample_rate')
            if sample_rate and (sample_rate < 8000 or sample_rate > 192000):
                results.append(ValidationResult(
                    level=ValidationLevel.ERROR,
                    category="audio_config",
                    message=f"{component_name}: Invalid sample rate {sample_rate}Hz (must be 8000-192000Hz)",
                    component=component_name,
                    suggestion="Use a sample rate between 8000 and 192000 Hz"
                ))
            
            # Validate channels
            channels = component_config.get('channels')
            if channels and (channels < 1 or channels > 8):
                results.append(ValidationResult(
                    level=ValidationLevel.ERROR,
                    category="audio_config",
                    message=f"{component_name}: Invalid channel count {channels} (must be 1-8)",
                    component=component_name,
                    suggestion="Use between 1 and 8 audio channels"
                ))
        
        return results
    
    def _validate_cross_component_compatibility(self, mic_config: Dict[str, Any], asr_config: Dict[str, Any], 
                                              vt_config: Dict[str, Any]) -> List[ValidationResult]:
        """Validate cross-component compatibility"""
        results = []
        
        # Use Phase 2 validation function
        try:
            from ..utils.audio_helpers import validate_cross_component_compatibility
            
            compatibility = validate_cross_component_compatibility(mic_config, asr_config, vt_config)
            
            # Convert to ValidationResult format
            for error in compatibility['errors']:
                results.append(ValidationResult(
                    level=ValidationLevel.ERROR,
                    category="cross_component",
                    message=error,
                    suggestion="Enable resampling or align sample rates across components"
                ))
            
            for warning in compatibility['warnings']:
                results.append(ValidationResult(
                    level=ValidationLevel.WARNING,
                    category="cross_component", 
                    message=warning,
                    suggestion="Consider standardizing sample rates for optimal performance"
                ))
                
        except ImportError:
            results.append(ValidationResult(
                level=ValidationLevel.WARNING,
                category="validation",
                message="Phase 2 audio validation not available",
                suggestion="Ensure audio_helpers module is properly installed"
            ))
        
        return results
    
    def _validate_provider_requirements(self, asr_config: Dict[str, Any], vt_config: Dict[str, Any], 
                                      providers: Dict[str, Any]) -> List[ValidationResult]:
        """Validate provider requirements against configuration"""
        results = []
        
        # Validate ASR providers
        asr_providers = providers.get('asr', {})
        for provider_name, provider in asr_providers.items():
            try:
                if hasattr(provider, 'supports_sample_rate'):
                    asr_sample_rate = asr_config.get('sample_rate', 16000)
                    if not provider.supports_sample_rate(asr_sample_rate):
                        allow_resampling = asr_config.get('allow_resampling', True)
                        if not allow_resampling:
                            results.append(ValidationResult(
                                level=ValidationLevel.ERROR,
                                category="provider_requirements",
                                message=f"ASR provider {provider_name} doesn't support {asr_sample_rate}Hz and resampling is disabled",
                                component="asr",
                                suggestion="Enable resampling or use a compatible sample rate"
                            ))
                        else:
                            results.append(ValidationResult(
                                level=ValidationLevel.INFO,
                                category="provider_requirements",
                                message=f"ASR provider {provider_name} will use resampling for {asr_sample_rate}Hz",
                                component="asr"
                            ))
            except Exception as e:
                results.append(ValidationResult(
                    level=ValidationLevel.WARNING,
                    category="provider_validation",
                    message=f"Could not validate ASR provider {provider_name}: {e}",
                    component="asr"
                ))
        
        # Validate voice trigger providers
        vt_providers = providers.get('voice_trigger', {})
        for provider_name, provider in vt_providers.items():
            try:
                if hasattr(provider, 'get_supported_sample_rates'):
                    vt_sample_rate = vt_config.get('sample_rate', 16000)
                    supported_rates = provider.get_supported_sample_rates()
                    if vt_sample_rate not in supported_rates:
                        supports_resampling = getattr(provider, 'supports_resampling', lambda: True)()
                        allow_resampling = vt_config.get('allow_resampling', True)
                        
                        if not supports_resampling and not allow_resampling:
                            results.append(ValidationResult(
                                level=ValidationLevel.ERROR,
                                category="provider_requirements",
                                message=f"Voice trigger provider {provider_name} requires {supported_rates} but configured for {vt_sample_rate}Hz",
                                component="voice_trigger",
                                suggestion="Use a supported sample rate or enable resampling"
                            ))
                        else:
                            results.append(ValidationResult(
                                level=ValidationLevel.INFO,
                                category="provider_requirements",
                                message=f"Voice trigger provider {provider_name} will handle {vt_sample_rate}Hz via resampling",
                                component="voice_trigger"
                            ))
            except Exception as e:
                results.append(ValidationResult(
                    level=ValidationLevel.WARNING,
                    category="provider_validation",
                    message=f"Could not validate voice trigger provider {provider_name}: {e}",
                    component="voice_trigger"
                ))
        
        return results


def validate_startup_audio_configuration(config: CoreConfig, providers: Dict[str, Any] = None) -> ValidationSummary:
    """
    Convenience function for startup audio configuration validation
    
    Args:
        config: System configuration
        providers: Available providers (optional)
        
    Returns:
        ValidationSummary
        
    Raises:
        FatalConfigurationError: If configuration has fatal errors
    """
    validator = AudioConfigurationValidator()
    return validator.validate_startup_configuration(config, providers)
