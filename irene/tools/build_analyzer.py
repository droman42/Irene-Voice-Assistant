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
    system_packages: Set[str] = field(default_factory=set)
    
    # Python dependencies from pyproject.toml optional-dependencies
    python_dependencies: Set[str] = field(default_factory=set)
    
    # Entry-points namespaces and enabled providers
    enabled_providers: Dict[str, List[str]] = field(default_factory=dict)
    
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
    """
    
    # Mapping of providers to system packages they require
    PROVIDER_SYSTEM_DEPENDENCIES = {
        # Audio providers
        "sounddevice": ["libportaudio2", "libsndfile1"],
        "aplay": ["alsa-utils"],
        "audioplayer": ["libavformat58", "libavcodec58"],
        "simpleaudio": ["libasound2-dev"],
        
        # TTS providers  
        "pyttsx": ["espeak", "espeak-data"],
        "silero_v3": ["libsndfile1"],
        "silero_v4": ["libsndfile1"],
        
        # ASR providers
        "vosk": ["libffi-dev"],
        "whisper": ["ffmpeg"],
        "google_cloud": [],  # Cloud-based, no local deps
        
        # Voice trigger providers
        "openwakeword": [],  # Pure Python
        "microwakeword": [],  # TensorFlow Lite runtime
        
        # LLM providers (cloud-based)
        "openai": [],
        "anthropic": [],
        "vsegpt": [],
        
        # NLU providers
        "rule_based": [],  # Pure Python
        "spacy": [],  # Python packages only
        
        # Text processing providers
        "asr_text_processor": [],
        "general_text_processor": [],
        "tts_text_processor": [],
        "number_text_processor": [],
    }
    
    # Mapping of providers to Python dependency groups from pyproject.toml
    PROVIDER_PYTHON_DEPENDENCIES = {
        # Audio providers
        "sounddevice": ["audio-input", "audio-output"],
        "audioplayer": ["audio-output"],
        "simpleaudio": ["audio-output"],
        "aplay": [],  # System tool
        "console": [],  # No dependencies
        
        # TTS providers
        "pyttsx": ["tts"],
        "elevenlabs": ["tts"],
        "silero_v3": ["tts"],
        "silero_v4": ["tts"],
        "vosk_tts": ["tts"],
        "console": [],  # Console TTS has no deps
        
        # ASR providers
        "vosk": ["audio-input"],
        "whisper": ["advanced-asr"],
        "google_cloud": ["cloud-asr"],
        
        # Voice trigger providers
        "openwakeword": ["voice-trigger"],
        "microwakeword": ["voice-trigger"],
        
        # LLM providers
        "openai": ["llm"],
        "anthropic": ["llm"],
        "vsegpt": ["llm"],
        
        # NLU providers
        "rule_based": [],  # No extra dependencies
        "spacy": ["text-multilingual"],  # SpaCy models
        
        # Text processing (all use text-multilingual for full functionality)
        "asr_text_processor": [],  # Basic functionality
        "general_text_processor": ["text-multilingual"],
        "tts_text_processor": ["text-multilingual"],
        "number_text_processor": ["text-multilingual"],
    }
    
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
        
    def _find_project_root(self) -> Path:
        """Find the project root directory by looking for pyproject.toml."""
        current = Path.cwd()
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent
        
        # Fallback to current directory
        return Path.cwd()
    
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
        
        # Generate dependency mappings
        self._generate_system_dependencies(requirements)
        self._generate_python_dependencies(requirements)
        
        logger.info(f"Analyzed requirements for profile '{requirements.profile_name}': "
                   f"{len(requirements.python_modules)} modules, "
                   f"{len(requirements.system_packages)} system packages, "
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
        
        # Validate provider compatibility
        self._validate_provider_compatibility(requirements, result)
        
        # Set overall validation status
        result.is_valid = len(result.errors) == 0
        
        if result.is_valid:
            logger.info(f"Profile '{requirements.profile_name}' validation: PASSED")
        else:
            logger.error(f"Profile '{requirements.profile_name}' validation: FAILED "
                        f"({len(result.errors)} errors, {len(result.warnings)} warnings)")
        
        return result
    
    def generate_docker_commands(self, requirements: BuildRequirements) -> List[str]:
        """
        Generate Docker commands for installing system dependencies.
        
        Args:
            requirements: BuildRequirements with system packages
            
        Returns:
            List of Docker RUN commands
        """
        if not requirements.system_packages:
            return []
        
        # Group packages for efficient installation
        packages = sorted(requirements.system_packages)
        
        commands = [
            "# Install system dependencies for enabled providers",
            "RUN apt-get update && apt-get install -y \\",
        ]
        
        # Add packages with proper line continuation
        for i, package in enumerate(packages):
            is_last = (i == len(packages) - 1)
            line = f"    {package}"
            if not is_last:
                line += " \\"
            commands.append(line)
        
        # Clean up apt cache
        commands.extend([
            "    && apt-get clean \\",
            "    && rm -rf /var/lib/apt/lists/*"
        ])
        
        return commands
    
    def generate_system_install_commands(self, requirements: BuildRequirements) -> List[str]:
        """
        Generate system installation commands for different platforms.
        
        Args:
            requirements: BuildRequirements with system packages
            
        Returns:
            List of installation commands
        """
        if not requirements.system_packages:
            return []
        
        packages = sorted(requirements.system_packages)
        package_list = " ".join(packages)
        
        return [
            "# Install system dependencies",
            f"sudo apt-get update",
            f"sudo apt-get install -y {package_list}",
        ]
    
    def generate_python_requirements(self, requirements: BuildRequirements) -> List[str]:
        """
        Generate Python requirements for UV installation.
        
        Args:
            requirements: BuildRequirements with Python dependencies
            
        Returns:
            List of dependency group names for UV
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
    
    def _get_entry_points_catalog(self) -> Dict[str, List[str]]:
        """Get all entry-points from pyproject.toml."""
        if self._entry_points_cache is not None:
            return self._entry_points_cache
        
        # Use dynamic loader to discover all namespaces
        namespaces = [
            "irene.providers.audio",
            "irene.providers.tts", 
            "irene.providers.asr",
            "irene.providers.llm",
            "irene.providers.voice_trigger",
            "irene.providers.nlu",
            "irene.providers.text_processing",
            "irene.components",
            "irene.workflows",
            "irene.intents.handlers",
            "irene.inputs",
            "irene.outputs",
            "irene.plugins.builtin",
            "irene.runners",
        ]
        
        catalog = {}
        for namespace in namespaces:
            providers = dynamic_loader.list_available_providers(namespace)
            catalog[namespace] = providers
        
        self._entry_points_cache = catalog
        return catalog
    
    def _analyze_providers(self, config: Dict[str, Any], requirements: BuildRequirements):
        """Analyze enabled providers from configuration."""
        providers_config = config.get("providers", {})
        
        for provider_type, type_config in providers_config.items():
            if not isinstance(type_config, dict):
                continue
                
            enabled = type_config.get("enabled", [])
            if enabled:
                namespace = f"irene.providers.{provider_type}"
                requirements.enabled_providers[namespace] = enabled
                
                # Add provider modules to requirements
                for provider_name in enabled:
                    module_path = f"irene.providers.{provider_type}.{provider_name}"
                    requirements.python_modules.add(module_path)
    
    def _analyze_components(self, config: Dict[str, Any], requirements: BuildRequirements):
        """Analyze enabled components from configuration."""
        components_config = config.get("components", {})
        enabled = components_config.get("enabled", [])
        
        if enabled:
            requirements.enabled_providers["irene.components"] = enabled
            for component_name in enabled:
                module_path = f"irene.components.{component_name}_component"
                requirements.python_modules.add(module_path)
    
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
    
    def _generate_system_dependencies(self, requirements: BuildRequirements):
        """Generate system package dependencies from enabled providers."""
        for namespace, providers in requirements.enabled_providers.items():
            for provider_name in providers:
                system_deps = self.PROVIDER_SYSTEM_DEPENDENCIES.get(provider_name, [])
                requirements.system_packages.update(system_deps)
    
    def _generate_python_dependencies(self, requirements: BuildRequirements):
        """Generate Python dependency groups from enabled providers."""
        for namespace, providers in requirements.enabled_providers.items():
            for provider_name in providers:
                python_deps = self.PROVIDER_PYTHON_DEPENDENCIES.get(provider_name, [])
                requirements.python_dependencies.update(python_deps)
    
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
    
    def _validate_provider_compatibility(self, requirements: BuildRequirements, result: ValidationResult):
        """Validate provider compatibility and system requirements."""
        # Check system dependencies are mappable
        for namespace, providers in requirements.enabled_providers.items():
            for provider_name in providers:
                if provider_name not in self.PROVIDER_SYSTEM_DEPENDENCIES:
                    result.warnings.append(f"No system dependency mapping for provider '{provider_name}'")
                    
                if provider_name not in self.PROVIDER_PYTHON_DEPENDENCIES:
                    result.warnings.append(f"No Python dependency mapping for provider '{provider_name}'")


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

  # Generate Docker commands
  python -m irene.tools.build_analyzer --config minimal.toml --docker

  # Generate system install commands
  python -m irene.tools.build_analyzer --config minimal.toml --system-install
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
        help="Generate Python dependency groups"
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
            output = {
                "profile": requirements.profile_name,
                "python_modules": sorted(requirements.python_modules),
                "system_packages": sorted(requirements.system_packages),
                "python_dependencies": sorted(requirements.python_dependencies),
                "enabled_providers": requirements.enabled_providers,
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
        
        print(f"🖥️  System Packages: {len(requirements.system_packages)}")
        for package in sorted(requirements.system_packages):
            print(f"  - {package}")
        
        print(f"🐍 Python Dependencies: {len(requirements.python_dependencies)}")
        for dep in sorted(requirements.python_dependencies):
            print(f"  - {dep}")
        
        # Generate commands if requested
        if args.docker:
            print("\n🐳 Docker Commands:")
            commands = analyzer.generate_docker_commands(requirements)
            for cmd in commands:
                print(cmd)
        
        if args.system_install:
            print("\n💻 System Install Commands:")
            commands = analyzer.generate_system_install_commands(requirements)
            for cmd in commands:
                print(cmd)
        
        if args.python_deps:
            print("\n🐍 UV Python Dependencies:")
            deps = analyzer.generate_python_requirements(requirements)
            if deps:
                print(f"uv sync --extra {' --extra '.join(deps)}")
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