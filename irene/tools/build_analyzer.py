"""
Irene Voice Assistant - Runtime Build Analyzer Tool

This module provides the core analysis engine for creating minimal builds
by analyzing TOML configuration + entry-points metadata to determine
precisely which modules and dependencies are required.

Usage:
    python -m irene.tools.build_analyzer --config configs/minimal.toml
    python -m irene.tools.build_analyzer --list-profiles
    python -m irene.tools.build_analyzer --validate-all-profiles
"""

import argparse
import logging
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
import json

from irene.utils.loader import dynamic_loader

logger = logging.getLogger(__name__)


@dataclass
class BuildRequirements:
    """Container for analyzed build requirements."""
    # Python modules that need to be included
    python_modules: Set[str] = field(default_factory=set)
    
    # System packages that need to be installed
    system_packages: Dict[str, Set[str]] = field(default_factory=dict)  # platform -> packages
    
    # Python dependencies from entry-point metadata
    python_dependencies: Set[str] = field(default_factory=set)
    
    # Entry-points namespaces and enabled providers
    enabled_providers: Dict[str, List[str]] = field(default_factory=dict)
    
    # Intent JSON configuration files that must be included and validated
    intent_json_files: Set[str] = field(default_factory=set)
    
    # Configuration profile name
    profile_name: str = ""
    
    # Validation results
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of build profile validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_dependencies: Set[str] = field(default_factory=set)
    conflicting_providers: List[Tuple[str, str]] = field(default_factory=list)


class IreneBuildAnalyzer:
    """
    Core build analyzer for Irene Voice Assistant.
    
    Analyzes TOML configuration + entry-points metadata to generate
    minimal build requirements for different deployment scenarios.
    
    Phase 3 Implementation (TODO #5): Dynamic metadata queries replace all hardcoded mappings.
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the build analyzer.
        
        Args:
            project_root: Path to project root. If None, auto-detect from current directory.
        """
        self.project_root = project_root or self._find_project_root()
        self.configs_dir = self.project_root / "configs"
        self.pyproject_path = self.project_root / "pyproject.toml"
        
        # Cache for loaded configurations and entry-points
        self._config_cache: Dict[str, Dict[str, Any]] = {}
        self._entry_points_cache: Optional[Dict[str, List[str]]] = None
        self._metadata_cache: Dict[str, Any] = {}  # Cache for provider metadata
        
        # Platform mapping for backward compatibility
        self._platform_mapping = {
            "ubuntu": "linux.ubuntu",
            "alpine": "linux.alpine",
            "centos": None,  # Removed - will error
            "macos": "macos",
            "windows": "windows"
        }
        
    def _find_project_root(self) -> Path:
        """Find the project root directory by looking for pyproject.toml."""
        current = Path.cwd()
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent
        
        # Fallback to current directory
        return Path.cwd()
    
    def _normalize_platform_name(self, platform: str) -> str:
        """
        Normalize platform name for backward compatibility.
        
        Args:
            platform: Original platform name (may be old format)
            
        Returns:
            Normalized platform name (new format)
            
        Raises:
            ValueError: If platform is not supported
        """
        if platform in ["linux.ubuntu", "linux.alpine", "macos", "windows"]:
            # Already using new format
            return platform
        
        if platform in self._platform_mapping:
            mapped = self._platform_mapping[platform]
            if mapped is None:
                raise ValueError(f"Platform '{platform}' is no longer supported (removed in Phase 2)")
            
            logger.warning(f"Platform '{platform}' is deprecated, use '{mapped}' instead")
            return mapped
        
        raise ValueError(f"Unknown platform '{platform}'. Supported platforms: linux.ubuntu, linux.alpine, macos, windows")
    
    def analyze_runtime_requirements(self, config_path: str) -> BuildRequirements:
        """
        Analyze a configuration file to determine runtime requirements.
        
        Args:
            config_path: Path to TOML configuration file
            
        Returns:
            BuildRequirements object with analyzed dependencies
        """
        config_file = Path(config_path)
        if not config_file.exists():
            # Try relative to configs directory
            config_file = self.configs_dir / config_path
            if not config_file.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        # Load and parse configuration
        config = self._load_config(config_file)
        
        # Initialize requirements
        requirements = BuildRequirements(profile_name=config_file.stem)
        
        # Analyze enabled providers across all namespaces
        self._analyze_providers(config, requirements)
        
        # Analyze enabled components
        self._analyze_components(config, requirements)
        
        # Analyze enabled workflows
        self._analyze_workflows(config, requirements)
        
        # Analyze enabled plugins
        self._analyze_plugins(config, requirements)
        
        # Analyze enabled intent handlers
        self._analyze_intent_handlers(config, requirements)
        
        # Generate dependency mappings using dynamic metadata queries
        self._generate_dependencies_from_metadata(requirements)
        
        logger.info(f"Analyzed requirements for profile '{requirements.profile_name}': "
                   f"{len(requirements.python_modules)} modules, "
                   f"{sum(len(pkgs) for pkgs in requirements.system_packages.values())} system packages, "
                   f"{len(requirements.python_dependencies)} Python deps")
        
        return requirements
    
    def list_available_profiles(self) -> List[str]:
        """
        Scan configs/ directory for available configuration profiles.
        
        Returns:
            List of available profile names (without .toml extension)
        """
        if not self.configs_dir.exists():
            logger.warning(f"Configs directory not found: {self.configs_dir}")
            return []
        
        profiles = []
        for config_file in self.configs_dir.glob("*.toml"):
            profiles.append(config_file.stem)
        
        logger.info(f"Found {len(profiles)} configuration profiles: {profiles}")
        return sorted(profiles)
    
    def validate_build_profile(self, requirements: BuildRequirements) -> ValidationResult:
        """
        Validate a build profile for completeness and conflicts.
        
        Args:
            requirements: BuildRequirements to validate
            
        Returns:
            ValidationResult with validation status and issues
        """
        result = ValidationResult(is_valid=True)
        
        # Check for missing critical providers
        self._validate_critical_providers(requirements, result)
        
        # Check for dependency conflicts
        self._validate_dependency_conflicts(requirements, result)
        
        # Check for missing entry-points
        self._validate_entry_points(requirements, result)
        
        # Validate provider compatibility using metadata
        self._validate_provider_metadata(requirements, result)
        
        # Validate intent JSON configurations
        self._validate_intent_json_files(requirements, result)
        
        # Set overall validation status
        result.is_valid = len(result.errors) == 0
        
        if result.is_valid:
            logger.info(f"Profile '{requirements.profile_name}' validation: PASSED")
        else:
            logger.error(f"Profile '{requirements.profile_name}' validation: FAILED "
                        f"({len(result.errors)} errors, {len(result.warnings)} warnings)")
        
        return result
    
    def generate_docker_commands(self, requirements: BuildRequirements, platform: str = "linux.ubuntu") -> List[str]:
        """
        Generate Docker commands for installing system dependencies.
        
        Args:
            requirements: BuildRequirements with system packages
            platform: Target platform (linux.ubuntu, linux.alpine, macos, windows)
            
        Returns:
            List of Docker RUN commands
        """
        # Normalize platform name for backward compatibility
        normalized_platform = self._normalize_platform_name(platform)
        packages = requirements.system_packages.get(normalized_platform, set())
        if not packages:
            return []
        
        # Sort packages for consistent output
        sorted_packages = sorted(packages)
        
        if normalized_platform == "linux.alpine":
            commands = [
                "# Install system dependencies for enabled providers",
                "RUN apk update && apk add --no-cache \\",
            ]
            
            # Add packages with proper line continuation
            for i, package in enumerate(sorted_packages):
                is_last = (i == len(sorted_packages) - 1)
                line = f"    {package}"
                if not is_last:
                    line += " \\"
                commands.append(line)
                
        elif normalized_platform == "linux.ubuntu":  # ubuntu/debian
            commands = [
                "# Install system dependencies for enabled providers",
                "RUN apt-get update && apt-get install -y \\",
            ]
            
            # Add packages with proper line continuation
            for i, package in enumerate(sorted_packages):
                is_last = (i == len(sorted_packages) - 1)
                line = f"    {package}"
                if not is_last:
                    line += " \\"
                commands.append(line)
            
            # Clean up apt cache
            commands.extend([
                "    && apt-get clean \\",
                "    && rm -rf /var/lib/apt/lists/*"
            ])
        
        else:
            # For macos and windows, Docker commands are not typically used
            commands = [
                f"# Docker installation not supported for platform: {normalized_platform}",
                f"# System packages needed: {', '.join(sorted_packages)}"
            ]
        
        return commands
    
    def generate_system_install_commands(self, requirements: BuildRequirements, platform: str = "linux.ubuntu") -> List[str]:
        """
        Generate system installation commands for different platforms.
        
        Args:
            requirements: BuildRequirements with system packages
            platform: Target platform (linux.ubuntu, linux.alpine, macos, windows)
            
        Returns:
            List of installation commands
        """
        # Normalize platform name for backward compatibility
        normalized_platform = self._normalize_platform_name(platform)
        packages = requirements.system_packages.get(normalized_platform, set())
        if not packages:
            return []
        
        sorted_packages = sorted(packages)
        package_list = " ".join(sorted_packages)
        
        if normalized_platform == "linux.ubuntu":
            return [
                "# Install system dependencies",
                f"sudo apt-get update",
                f"sudo apt-get install -y {package_list}",
            ]
        elif normalized_platform == "linux.alpine":
            return [
                "# Install system dependencies",
                f"sudo apk update",
                f"sudo apk add {package_list}",
            ]
        elif normalized_platform == "macos":
            return [
                "# Install system dependencies",
                f"brew update",
                f"brew install {package_list}",
            ]
        elif normalized_platform == "windows":
            return [
                "# Install system dependencies",
                f"# Windows system package installation varies by package manager",
                f"# Required packages: {package_list}",
                f"# Consider using chocolatey, winget, or vcpkg",
            ]
        else:
            return [f"# Unknown platform: {normalized_platform}"]
    
    def generate_python_requirements(self, requirements: BuildRequirements) -> List[str]:
        """
        Generate Python requirements for UV installation.
        
        Args:
            requirements: BuildRequirements with Python dependencies
            
        Returns:
            List of specific Python package requirements
        """
        return sorted(requirements.python_dependencies)
    
    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load and cache TOML configuration."""
        cache_key = str(config_path)
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        try:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            self._config_cache[cache_key] = config
            return config
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration {config_path}: {e}")
    
    def _discover_entry_point_namespaces(self) -> List[str]:
        """
        Dynamically discover all entry-point namespaces from pyproject.toml.
        
        Replaces hardcoded namespace list (lines 364-379 in original).
        """
        if not self.pyproject_path.exists():
            logger.warning(f"pyproject.toml not found at {self.pyproject_path}")
            return []
        
        try:
            with open(self.pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)
            
            # Extract all namespaces from entry-points sections
            entry_points = pyproject.get("project", {}).get("entry-points", {})
            namespaces = [ns for ns in entry_points.keys() if ns.startswith("irene.")]
            
            logger.debug(f"Discovered {len(namespaces)} entry-point namespaces: {namespaces}")
            return sorted(namespaces)
            
        except Exception as e:
            logger.error(f"Failed to discover entry-point namespaces: {e}")
            # Fallback to known namespaces to prevent complete failure
            return [
                "irene.providers.audio", "irene.providers.tts", "irene.providers.asr",
                "irene.providers.llm", "irene.providers.voice_trigger", "irene.providers.nlu",
                "irene.providers.text_processing", "irene.components", "irene.workflows",
                "irene.intents.handlers", "irene.inputs", "irene.outputs",
                "irene.plugins.builtin", "irene.runners"
            ]
    
    def _get_entry_points_catalog(self) -> Dict[str, List[str]]:
        """Get all entry-points from dynamic discovery."""
        if self._entry_points_cache is not None:
            return self._entry_points_cache
        
        # Use dynamic discovery instead of hardcoded list
        namespaces = self._discover_entry_point_namespaces()
        
        catalog = {}
        for namespace in namespaces:
            providers = dynamic_loader.list_available_providers(namespace)
            catalog[namespace] = providers
        
        self._entry_points_cache = catalog
        return catalog
    
    def _get_provider_metadata(self, namespace: str, provider_name: str) -> Optional[Any]:
        """
        Get provider class metadata using dynamic loading.
        
        Args:
            namespace: Entry-point namespace
            provider_name: Provider name
            
        Returns:
            Provider class with metadata methods or None if not found
        """
        cache_key = f"{namespace}.{provider_name}"
        if cache_key in self._metadata_cache:
            return self._metadata_cache[cache_key]
        
        try:
            provider_class = dynamic_loader.get_provider_class(namespace, provider_name)
            if provider_class is None:
                logger.warning(f"Provider class not found: {namespace}.{provider_name}")
                return None
                
            # Verify the class has metadata methods
            if not hasattr(provider_class, 'get_python_dependencies'):
                logger.warning(f"Provider {provider_name} missing metadata methods")
                return None
                
            self._metadata_cache[cache_key] = provider_class
            return provider_class
            
        except Exception as e:
            logger.error(f"Failed to load provider metadata for {namespace}.{provider_name}: {e}")
            return None
    
    def _analyze_providers(self, config: Dict[str, Any], requirements: BuildRequirements):
        """
        Analyze enabled providers from configuration.
        
        Supports both array-based and object-based configurations:
        Array-based: providers.tts.enabled = ["elevenlabs", "console"]
        Object-based: providers.tts.elevenlabs.enabled = true
        """
        providers_config = config.get("providers", {})
        
        for provider_type, type_config in providers_config.items():
            if not isinstance(type_config, dict):
                continue
            
            enabled_providers = []
            
            # Method 1: Array-based enabled list (e.g., providers.tts.enabled = ["elevenlabs"])
            enabled_list = type_config.get("enabled", [])
            if enabled_list and isinstance(enabled_list, list):
                enabled_providers.extend(enabled_list)
            
            # Method 2: Object-based individual provider configs (e.g., providers.tts.elevenlabs.enabled = true)
            for key, value in type_config.items():
                if key in ["enabled", "disabled", "default", "fallback_providers"]:
                    continue  # Skip meta-configuration keys
                
                if isinstance(value, dict) and value.get("enabled", False):
                    enabled_providers.append(key)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_enabled = []
            for provider in enabled_providers:
                if provider not in seen:
                    seen.add(provider)
                    unique_enabled.append(provider)
            
            if unique_enabled:
                namespace = f"irene.providers.{provider_type}"
                requirements.enabled_providers[namespace] = unique_enabled
                
                # Add provider modules to requirements
                for provider_name in unique_enabled:
                    module_path = f"irene.providers.{provider_type}.{provider_name}"
                    requirements.python_modules.add(module_path)
                
                logger.debug(f"Standard providers found: {namespace} -> {unique_enabled}")
    
    def _analyze_components(self, config: Dict[str, Any], requirements: BuildRequirements):
        """
        Analyze enabled components from configuration.
        
        Structure uses individual component sections:
        [tts]
        enabled = true
        
        [audio] 
        enabled = false
        """
        # Check individual component sections for enabled status
        component_names = [
            "tts", "asr", "audio", "llm", "voice_trigger", 
            "nlu", "text_processor", "intent_system"
        ]
        
        enabled_components = []
        for component_name in component_names:
            component_config = config.get(component_name, {})
            if isinstance(component_config, dict) and component_config.get("enabled", False):
                enabled_components.append(component_name)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_enabled = []
        for component in enabled_components:
            if component not in seen:
                seen.add(component)
                unique_enabled.append(component)
        
        if unique_enabled:
            requirements.enabled_providers["irene.components"] = unique_enabled
            for component_name in unique_enabled:
                module_path = f"irene.components.{component_name}_component"
                requirements.python_modules.add(module_path)
            
            logger.debug(f"Components found: {unique_enabled}")
        
        # Analyze component-based providers (e.g., tts.providers.*, nlu.providers.*)
        self._analyze_component_providers(config, requirements)
    
    def _analyze_component_providers(self, config: Dict[str, Any], requirements: BuildRequirements):
        """
        Analyze component-based providers from configuration.
        
        Structure uses individual component sections:
        [tts]
        enabled = true
        default_provider = "elevenlabs"
        
        [tts.providers.elevenlabs]
        enabled = true
        api_key = "${ELEVENLABS_API_KEY}"
        """
        component_names = [
            "tts", "asr", "audio", "llm", "voice_trigger", 
            "nlu", "text_processor", "intent_system"
        ]
        
        for component_name in component_names:
            component_config = config.get(component_name, {})
            if not isinstance(component_config, dict):
                continue
            
            # Only analyze providers if the component itself is enabled
            if not component_config.get("enabled", False):
                continue
                
            # Extract enabled providers from multiple sources
            enabled_providers = []
            
            # Method 1: Explicit provider subsections with enabled flags
            providers_config = component_config.get("providers", {})
            for provider_name, provider_config in providers_config.items():
                if isinstance(provider_config, dict) and provider_config.get("enabled", False):
                    enabled_providers.append(provider_name)
            
            # Method 2: default_provider (always considered enabled if component is enabled)
            default_provider = component_config.get("default_provider")
            if default_provider and default_provider not in enabled_providers:
                enabled_providers.append(default_provider)
                
            # Method 3: fallback_providers (always considered enabled if component is enabled)
            fallback_providers = component_config.get("fallback_providers", [])
            for provider in fallback_providers:
                if provider not in enabled_providers:
                    enabled_providers.append(provider)
            
            # Method 4: provider_cascade_order (if specified, these are enabled)
            cascade_order = component_config.get("provider_cascade_order", [])
            for provider in cascade_order:
                if provider not in enabled_providers:
                    enabled_providers.append(provider)
            
            # Add to requirements if we found enabled providers
            if enabled_providers:
                namespace = f"irene.providers.{component_name}"
                requirements.enabled_providers[namespace] = enabled_providers
                
                # Add provider modules to requirements
                for provider_name in enabled_providers:
                    module_path = f"irene.providers.{component_name}.{provider_name}"
                    requirements.python_modules.add(module_path)
                
                logger.debug(f"Component-based providers found: {namespace} -> {enabled_providers}")
    

    
    def _analyze_workflows(self, config: Dict[str, Any], requirements: BuildRequirements):
        """Analyze enabled workflows from configuration."""
        workflows_config = config.get("workflows", {})
        enabled = workflows_config.get("enabled", [])
        
        if enabled:
            requirements.enabled_providers["irene.workflows"] = enabled
            for workflow_name in enabled:
                module_path = f"irene.workflows.{workflow_name}"
                requirements.python_modules.add(module_path)
    
    def _analyze_plugins(self, config: Dict[str, Any], requirements: BuildRequirements):
        """Analyze enabled plugins from configuration."""
        plugins_config = config.get("plugins", {})
        enabled = plugins_config.get("enabled", [])
        
        if enabled:
            requirements.enabled_providers["irene.plugins.builtin"] = enabled
            for plugin_name in enabled:
                module_path = f"irene.plugins.builtin.{plugin_name}"
                requirements.python_modules.add(module_path)
        
        # Analyze plugin-based providers (e.g., plugins.universal_tts.providers.*)
        self._analyze_plugin_providers(config, requirements)
    
    def _analyze_plugin_providers(self, config: Dict[str, Any], requirements: BuildRequirements):
        """
        Analyze plugin-based providers from configuration.
        
        Handles patterns like:
        [plugins.universal_tts.providers.elevenlabs]
        enabled = true
        voice = "Rachel"
        
        [plugins.universal_tts]
        default_provider = "elevenlabs"
        """
        plugins_config = config.get("plugins", {})
        
        for plugin_name, plugin_config in plugins_config.items():
            if not isinstance(plugin_config, dict):
                continue
            
            # Look for universal_* plugins with provider subsections
            if not plugin_name.startswith("universal_"):
                continue
            
            # Extract provider type from plugin name (universal_tts -> tts)
            provider_type = plugin_name.replace("universal_", "")
            
            # Look for plugin.providers.* subsections
            providers_config = plugin_config.get("providers", {})
            if not providers_config:
                continue
            
            # Extract enabled providers from individual provider configurations
            enabled_providers = []
            for provider_name, provider_config in providers_config.items():
                if isinstance(provider_config, dict) and provider_config.get("enabled", False):
                    enabled_providers.append(provider_name)
            
            # Add to requirements if we found enabled providers
            if enabled_providers:
                namespace = f"irene.providers.{provider_type}"  # e.g., irene.providers.tts
                
                # Merge with existing providers from the standard providers.* section
                existing_providers = requirements.enabled_providers.get(namespace, [])
                all_providers = list(set(existing_providers + enabled_providers))
                requirements.enabled_providers[namespace] = all_providers
                
                # Add provider modules to requirements
                for provider_name in enabled_providers:
                    module_path = f"irene.providers.{provider_type}.{provider_name}"
                    requirements.python_modules.add(module_path)
                
                logger.debug(f"Plugin-based providers found: {namespace} -> {enabled_providers}")
    
    def _analyze_intent_handlers(self, config: Dict[str, Any], requirements: BuildRequirements):
        """
        Analyze enabled intent handlers from configuration.
        
        Handles patterns like:
        [intents]
        enabled = true
        
        [intents.handlers]
        enabled = ["timer", "greetings", "conversation"]
        disabled = ["train_schedule"]
        """
        intents_config = config.get("intents", {})
        
        # Check if intents are enabled at all
        if not intents_config.get("enabled", False):
            logger.debug("Intent system is disabled, skipping intent handler analysis")
            return
        
        handlers_config = intents_config.get("handlers", {})
        enabled_handlers = []
        
        # Method 1: Array-based enabled list (e.g., intents.handlers.enabled = ["timer", "greetings"])
        enabled_list = handlers_config.get("enabled", [])
        if enabled_list and isinstance(enabled_list, list):
            enabled_handlers.extend(enabled_list)
        
        # Method 2: Object-based individual handler configs (e.g., intents.handlers.timer = true)
        for key, value in handlers_config.items():
            if key in ["enabled", "disabled", "auto_discover", "discovery_paths"]:
                continue  # Skip meta-configuration keys
            
            # Direct boolean configuration (e.g., timer = true)
            if isinstance(value, bool) and value:
                enabled_handlers.append(key)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_enabled = []
        for handler in enabled_handlers:
            if handler not in seen:
                seen.add(handler)
                unique_enabled.append(handler)
        
        # Remove explicitly disabled handlers
        disabled_handlers = handlers_config.get("disabled", [])
        if disabled_handlers:
            unique_enabled = [h for h in unique_enabled if h not in disabled_handlers]
        
        if unique_enabled:
            namespace = "irene.intents.handlers"
            requirements.enabled_providers[namespace] = unique_enabled
            
            # Add intent handler modules to requirements
            for handler_name in unique_enabled:
                module_path = f"irene.intents.handlers.{handler_name}"
                requirements.python_modules.add(module_path)
            
            # Add JSON configuration files to requirements - these must be included and validated
            for handler_name in unique_enabled:
                json_config_path = f"assets/donations/{handler_name}.json"
                # Store JSON files as a special requirement category
                if not hasattr(requirements, 'intent_json_files'):
                    requirements.intent_json_files = set()
                requirements.intent_json_files.add(json_config_path)
            
            logger.debug(f"Intent handlers found: {namespace} -> {unique_enabled}")
            logger.debug(f"Intent JSON configs required: {getattr(requirements, 'intent_json_files', set())}")
    
    def _generate_dependencies_from_metadata(self, requirements: BuildRequirements):
        """
        Generate dependencies using dynamic metadata queries.
        
        Replaces hardcoded PROVIDER_SYSTEM_DEPENDENCIES and PROVIDER_PYTHON_DEPENDENCIES.
        """
        # Initialize platform containers
        platforms = ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        for platform in platforms:
            requirements.system_packages[platform] = set()
        
        for namespace, providers in requirements.enabled_providers.items():
            for provider_name in providers:
                provider_class = self._get_provider_metadata(namespace, provider_name)
                if provider_class is None:
                    logger.warning(f"Skipping dependency analysis for {namespace}.{provider_name}")
                    continue
                
                try:
                    # Get Python dependencies from metadata
                    python_deps = provider_class.get_python_dependencies()
                    requirements.python_dependencies.update(python_deps)
                    
                    # Get platform-specific system dependencies
                    platform_deps = provider_class.get_platform_dependencies()
                    for platform, packages in platform_deps.items():
                        if platform in requirements.system_packages:
                            requirements.system_packages[platform].update(packages)
                    
                    logger.debug(f"Loaded dependencies for {namespace}.{provider_name}: "
                               f"python={python_deps}, platforms={list(platform_deps.keys())}")
                               
                except Exception as e:
                    logger.error(f"Failed to query metadata for {namespace}.{provider_name}: {e}")
                    continue
    
    def _validate_critical_providers(self, requirements: BuildRequirements, result: ValidationResult):
        """Validate that critical providers are available."""
        # Check for audio output if TTS is enabled
        tts_providers = requirements.enabled_providers.get("irene.providers.tts", [])
        audio_providers = requirements.enabled_providers.get("irene.providers.audio", [])
        
        if tts_providers and not audio_providers:
            result.errors.append("TTS providers enabled but no audio output providers configured")
        
        # Check for ASR if microphone input is expected
        components = requirements.enabled_providers.get("irene.components", [])
        asr_providers = requirements.enabled_providers.get("irene.providers.asr", [])
        
        if "asr" in components and not asr_providers:
            result.errors.append("ASR component enabled but no ASR providers configured")
    
    def _validate_dependency_conflicts(self, requirements: BuildRequirements, result: ValidationResult):
        """Check for conflicting provider dependencies."""
        # Example: Check for conflicting audio systems
        audio_providers = requirements.enabled_providers.get("irene.providers.audio", [])
        
        # ALSA vs PulseAudio conflicts (example)
        has_alsa = any(p in audio_providers for p in ["aplay"])
        has_pulse = any(p in audio_providers for p in ["sounddevice", "audioplayer"])
        
        if has_alsa and has_pulse:
            result.warnings.append("Both ALSA and PulseAudio providers enabled - may cause conflicts")
    
    def _validate_entry_points(self, requirements: BuildRequirements, result: ValidationResult):
        """Validate that all enabled providers have corresponding entry-points."""
        catalog = self._get_entry_points_catalog()
        
        for namespace, providers in requirements.enabled_providers.items():
            available_providers = catalog.get(namespace, [])
            for provider_name in providers:
                if provider_name not in available_providers:
                    result.errors.append(f"Provider '{provider_name}' not found in namespace '{namespace}'")
    
    def _validate_provider_metadata(self, requirements: BuildRequirements, result: ValidationResult):
        """Validate provider metadata compatibility and requirements."""
        for namespace, providers in requirements.enabled_providers.items():
            for provider_name in providers:
                provider_class = self._get_provider_metadata(namespace, provider_name)
                if provider_class is None:
                    result.warnings.append(f"Could not load metadata for provider '{provider_name}'")
                    continue
                
                try:
                    # Validate metadata methods exist and work
                    python_deps = provider_class.get_python_dependencies()
                    platform_deps = provider_class.get_platform_dependencies()
                    platform_support = provider_class.get_platform_support()
                    
                    # Validate return types
                    if not isinstance(python_deps, list):
                        result.errors.append(f"Provider '{provider_name}' get_python_dependencies() must return list")
                    if not isinstance(platform_deps, dict):
                        result.errors.append(f"Provider '{provider_name}' get_platform_dependencies() must return dict")
                    if not isinstance(platform_support, list):
                        result.errors.append(f"Provider '{provider_name}' get_platform_support() must return list")
                        
                except Exception as e:
                    result.errors.append(f"Provider '{provider_name}' metadata validation failed: {e}")
    
    def _validate_intent_json_files(self, requirements: BuildRequirements, result: ValidationResult):
        """Validate that all required intent JSON files exist and are valid."""
        if not requirements.intent_json_files:
            return  # No intent handlers enabled, nothing to validate
        
        # Import the intent validator - only when needed to avoid circular imports
        try:
            from irene.tools.intent_validator import IntentJSONValidator
        except ImportError:
            result.warnings.append("Could not import intent validator - JSON validation skipped")
            return
        
        try:
            validator = IntentJSONValidator(self.project_root)
            
            for json_file_path in requirements.intent_json_files:
                file_path = self.project_root / json_file_path
                
                # Check if file exists
                if not file_path.exists():
                    result.errors.append(f"Required intent JSON file not found: {json_file_path}")
                    continue
                
                # Validate the JSON file
                validation_result = validator.validate_intent_file(file_path)
                
                if not validation_result.is_valid:
                    result.errors.append(f"Intent JSON validation failed for {json_file_path}:")
                    for error in validation_result.errors + validation_result.schema_errors:
                        result.errors.append(f"  - {error}")
                
                # Add warnings as well
                for warning in validation_result.warnings:
                    result.warnings.append(f"Intent JSON warning for {json_file_path}: {warning}")
                    
        except Exception as e:
            result.warnings.append(f"Intent JSON validation failed: {e}")


def main():
    """Command-line interface for the build analyzer."""
    parser = argparse.ArgumentParser(
        description="Irene Voice Assistant - Runtime Build Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a specific configuration profile
  python -m irene.tools.build_analyzer --config configs/minimal.toml

  # List all available profiles
  python -m irene.tools.build_analyzer --list-profiles

  # Validate all profiles
  python -m irene.tools.build_analyzer --validate-all-profiles

  # Generate Docker commands for specific platform
  python -m irene.tools.build_analyzer --config minimal.toml --docker --platform alpine

  # Generate system install commands
  python -m irene.tools.build_analyzer --config minimal.toml --system-install --platform ubuntu
        """
    )
    
    parser.add_argument(
        "--config", 
        help="Path to configuration file (relative to configs/ or absolute path)"
    )
    parser.add_argument(
        "--list-profiles", 
        action="store_true",
        help="List all available configuration profiles in configs/"
    )
    parser.add_argument(
        "--validate-all-profiles", 
        action="store_true",
        help="Validate all configuration profiles"
    )
    parser.add_argument(
        "--docker", 
        action="store_true",
        help="Generate Docker installation commands"
    )
    parser.add_argument(
        "--system-install", 
        action="store_true",
        help="Generate system installation commands"
    )
    parser.add_argument(
        "--python-deps", 
        action="store_true",
        help="Generate Python dependency requirements"
    )
    parser.add_argument(
        "--platform",
        choices=["linux.ubuntu", "linux.alpine", "macos", "windows"],
        default="linux.ubuntu",
        help="Target platform for system dependencies"
    )
    parser.add_argument(
        "--json", 
        action="store_true",
        help="Output results in JSON format"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Analyze but don't generate actual commands"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(levelname)s: %(message)s'
    )
    
    try:
        analyzer = IreneBuildAnalyzer()
        
        if args.list_profiles:
            profiles = analyzer.list_available_profiles()
            if args.json:
                print(json.dumps(profiles))
            else:
                print("Available configuration profiles:")
                for profile in profiles:
                    print(f"  - {profile}")
            return 0
        
        if args.validate_all_profiles:
            profiles = analyzer.list_available_profiles()
            if not profiles:
                print("No configuration profiles found in configs/")
                return 1
            
            results = {}
            for profile in profiles:
                try:
                    config_path = f"configs/{profile}.toml"
                    requirements = analyzer.analyze_runtime_requirements(config_path)
                    validation = analyzer.validate_build_profile(requirements)
                    results[profile] = {
                        "valid": validation.is_valid,
                        "errors": validation.errors,
                        "warnings": validation.warnings
                    }
                except Exception as e:
                    results[profile] = {
                        "valid": False,
                        "errors": [str(e)],
                        "warnings": []
                    }
            
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                for profile, result in results.items():
                    status = "✅ VALID" if result["valid"] else "❌ INVALID"
                    print(f"{profile}: {status}")
                    for error in result["errors"]:
                        print(f"  ERROR: {error}")
                    for warning in result["warnings"]:
                        print(f"  WARNING: {warning}")
            
            return 0
        
        if not args.config:
            parser.error("--config is required unless using --list-profiles or --validate-all-profiles")
        
        # Analyze specific configuration
        requirements = analyzer.analyze_runtime_requirements(args.config)
        validation = analyzer.validate_build_profile(requirements)
        
        if args.json:
            # Convert sets to lists for JSON serialization
            output = {
                "profile": requirements.profile_name,
                "python_modules": sorted(requirements.python_modules),
                "system_packages": {
                    platform: sorted(packages) 
                    for platform, packages in requirements.system_packages.items()
                },
                "python_dependencies": sorted(requirements.python_dependencies),
                "enabled_providers": requirements.enabled_providers,
                "intent_json_files": sorted(requirements.intent_json_files),
                "validation": {
                    "valid": validation.is_valid,
                    "errors": validation.errors,
                    "warnings": validation.warnings
                }
            }
            print(json.dumps(output, indent=2))
            return 0
        
        # Human-readable output
        print(f"🔍 Build Analysis for Profile: {requirements.profile_name}")
        print(f"📦 Python Modules: {len(requirements.python_modules)}")
        for module in sorted(requirements.python_modules):
            print(f"  - {module}")
        
        print(f"🖥️  System Packages ({args.platform}): {len(requirements.system_packages.get(args.platform, set()))}")
        for package in sorted(requirements.system_packages.get(args.platform, set())):
            print(f"  - {package}")
        
        print(f"🐍 Python Dependencies: {len(requirements.python_dependencies)}")
        for dep in sorted(requirements.python_dependencies):
            print(f"  - {dep}")
        
        print(f"📄 Intent JSON Files: {len(requirements.intent_json_files)}")
        for json_file in sorted(requirements.intent_json_files):
            print(f"  - {json_file}")
        
        # Generate commands if requested
        if args.docker:
            print(f"\n🐳 Docker Commands ({args.platform}):")
            commands = analyzer.generate_docker_commands(requirements, args.platform)
            if commands:
                for cmd in commands:
                    print(cmd)
            else:
                print("# No system dependencies required")
        
        if args.system_install:
            print(f"\n💻 System Install Commands ({args.platform}):")
            commands = analyzer.generate_system_install_commands(requirements, args.platform)
            if commands:
                for cmd in commands:
                    print(cmd)
            else:
                print("# No system dependencies required")
        
        if args.python_deps:
            print("\n🐍 Python Dependencies:")
            deps = analyzer.generate_python_requirements(requirements)
            if deps:
                for dep in deps:
                    print(f"  - {dep}")
            else:
                print("# No additional Python dependencies required")
        
        # Show validation results
        print(f"\n✅ Validation: {'PASSED' if validation.is_valid else 'FAILED'}")
        for error in validation.errors:
            print(f"  ❌ ERROR: {error}")
        for warning in validation.warnings:
            print(f"  ⚠️  WARNING: {warning}")
        
        return 0 if validation.is_valid else 1
        
    except Exception as e:
        logger.error(f"Build analysis failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 