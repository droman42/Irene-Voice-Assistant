"""
Irene Voice Assistant - Dependency Validation Tool

This module provides intelligent validation of entry-point metadata for:
- Import analysis and dynamic loading verification
- Python dependency validation against pyproject.toml
- System package validation for target platforms  
- Cross-platform consistency checking
- Performance testing of metadata methods
- External package metadata compliance

Usage:
    python -m irene.tools.dependency_validator --file irene/providers/audio/sounddevice.py --class SoundDeviceAudioProvider --platform ubuntu
    python -m irene.tools.dependency_validator --validate-all --platform alpine
    python -m irene.tools.dependency_validator --validate-all --platforms ubuntu,alpine,centos,macos
"""

import argparse
import importlib.util
import json
import logging
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple, Type
import subprocess

from irene.utils.loader import dynamic_loader

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of entry-point validation."""
    entry_point: str
    platform: str
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    performance_ms: float = 0.0
    
    # Detailed validation results
    import_successful: bool = False
    metadata_methods_exist: bool = False
    python_deps_valid: bool = False
    system_packages_valid: bool = False
    platform_consistency_valid: bool = False


@dataclass
class ValidationReport:
    """Comprehensive validation report for multiple entry-points."""
    total_entry_points: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    validation_results: Dict[str, ValidationResult] = field(default_factory=dict)
    platform_summary: Dict[str, Dict[str, int]] = field(default_factory=dict)


class DependencyValidator:
    """
    Smart dependency validation for entry-point metadata.
    
    Validates entry-point classes for:
    - Dynamic import and instantiation capability
    - Metadata method existence and performance  
    - Python dependency declaration accuracy
    - System package validation per platform
    - Cross-platform consistency
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the dependency validator.
        
        Args:
            project_root: Path to project root. If None, auto-detect from current directory.
        """
        self.project_root = project_root or self._find_project_root()
        self.pyproject_path = self.project_root / "pyproject.toml"
        
        # Cache for loaded configurations and package data
        self._pyproject_cache: Optional[Dict[str, Any]] = None
        self._platform_repos_cache: Dict[str, Set[str]] = {}
        
        # Known package repositories per platform (subset for validation)
        self._known_packages = {
            "ubuntu": {
                "libportaudio2", "libsndfile1", "libffi-dev", "ffmpeg", "espeak", "espeak-data",
                "alsa-utils", "libavformat58", "libavcodec58", "libasound2-dev", "libatomic1"
            },
            "alpine": {
                "portaudio-dev", "libsndfile-dev", "libffi-dev", "ffmpeg", "espeak", "espeak-data",
                "alsa-utils", "ffmpeg-dev", "alsa-lib-dev", "libatomic", "ffmpeg-libs"
            },
            "centos": {
                "portaudio-devel", "libsndfile-devel", "libffi-devel", "ffmpeg", "espeak", "espeak-data",
                "alsa-utils", "ffmpeg-devel", "alsa-lib-devel", "libatomic"
            },
            "macos": {
                "portaudio", "libsndfile", "libffi", "ffmpeg", "espeak"
            }
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
    
    def _load_pyproject(self) -> Dict[str, Any]:
        """Load and cache pyproject.toml configuration."""
        if self._pyproject_cache is not None:
            return self._pyproject_cache
        
        try:
            with open(self.pyproject_path, "rb") as f:
                self._pyproject_cache = tomllib.load(f)
            return self._pyproject_cache
        except Exception as e:
            logger.error(f"Failed to load pyproject.toml: {e}")
            return {}
    
    def validate_entry_point(self, file_path: str, class_name: str, platform: str) -> ValidationResult:
        """
        Validate single entry-point's metadata for target platform.
        
        Args:
            file_path: Path to Python file containing the entry-point class
            class_name: Name of the entry-point class
            platform: Target platform (ubuntu, alpine, centos, macos)
            
        Returns:
            ValidationResult with detailed validation status
        """
        result = ValidationResult(
            entry_point=f"{file_path}:{class_name}",
            platform=platform,
            is_valid=False
        )
        
        try:
            # 1. Dynamic import and instantiation
            entry_point_class = self._import_entry_point_class(file_path, class_name, result)
            if not entry_point_class:
                return result
            
            result.import_successful = True
            
            # 2. Validate metadata methods exist and work
            start_time = time.time()
            metadata_valid = self._validate_metadata_methods(entry_point_class, result)
            result.performance_ms = (time.time() - start_time) * 1000
            result.metadata_methods_exist = metadata_valid
            
            if not metadata_valid:
                return result
            
            # 3. Verify Python dependencies exist in pyproject.toml
            result.python_deps_valid = self._validate_python_dependencies(entry_point_class, result)
            
            # 4. Check system packages exist in platform package repos
            result.system_packages_valid = self._validate_system_packages(entry_point_class, platform, result)
            
            # 5. Validate platform consistency
            result.platform_consistency_valid = self._validate_platform_consistency(entry_point_class, result)
            
            # 6. Performance validation
            if result.performance_ms > 100:
                result.warnings.append(f"Metadata methods took {result.performance_ms:.1f}ms (> 100ms threshold)")
            
            # Overall validation result
            result.is_valid = (
                result.import_successful and 
                result.metadata_methods_exist and
                result.python_deps_valid and
                result.system_packages_valid and
                result.platform_consistency_valid and
                len(result.errors) == 0
            )
            
        except Exception as e:
            result.errors.append(f"Validation failed with exception: {str(e)}")
            logger.exception(f"Exception during validation of {file_path}:{class_name}")
        
        return result
    
    def validate_all_entry_points(self, platforms: List[str]) -> ValidationReport:
        """
        Validate all entry-points across specified platforms.
        
        Args:
            platforms: List of platforms to validate against
            
        Returns:
            ValidationReport with comprehensive results
        """
        report = ValidationReport()
        
        # Initialize platform summaries
        for platform in platforms:
            report.platform_summary[platform] = {
                "total": 0, "passed": 0, "failed": 0, "errors": 0, "warnings": 0
            }
        
        # Discover all entry-points using dynamic loader
        pyproject = self._load_pyproject()
        entry_points = pyproject.get("project", {}).get("entry-points", {})
        
        total_combinations = 0
        for namespace, providers in entry_points.items():
            if not namespace.startswith("irene."):
                continue
            total_combinations += len(providers) * len(platforms)
        
        report.total_entry_points = total_combinations
        
        # Validate each entry-point for each platform
        for namespace, providers in entry_points.items():
            if not namespace.startswith("irene."):
                continue
                
            logger.info(f"Validating namespace: {namespace}")
            
            for provider_name, entry_point_spec in providers.items():
                # Parse entry-point specification: "module.path:ClassName"
                try:
                    module_path, class_name = entry_point_spec.split(":")
                    file_path = module_path.replace(".", "/") + ".py"
                    
                    for platform in platforms:
                        result_key = f"{namespace}.{provider_name}@{platform}"
                        
                        logger.debug(f"Validating {result_key}")
                        result = self.validate_entry_point(file_path, class_name, platform)
                        
                        report.validation_results[result_key] = result
                        
                        # Update statistics
                        platform_stats = report.platform_summary[platform]
                        platform_stats["total"] += 1
                        
                        if result.is_valid:
                            report.successful_validations += 1
                            platform_stats["passed"] += 1
                        else:
                            report.failed_validations += 1
                            platform_stats["failed"] += 1
                        
                        platform_stats["errors"] += len(result.errors)
                        platform_stats["warnings"] += len(result.warnings)
                        report.total_errors += len(result.errors)
                        report.total_warnings += len(result.warnings)
                        
                except ValueError as e:
                    logger.error(f"Invalid entry-point specification '{entry_point_spec}': {e}")
                    continue
                except Exception as e:
                    logger.error(f"Failed to validate {namespace}.{provider_name}: {e}")
                    continue
        
        logger.info(f"Validation complete: {report.successful_validations}/{report.total_entry_points} passed")
        return report
    
    def _import_entry_point_class(self, file_path: str, class_name: str, result: ValidationResult) -> Optional[Type]:
        """Import entry-point class dynamically."""
        try:
            # Convert file path to module path
            if file_path.endswith(".py"):
                file_path = file_path[:-3]
            module_path = file_path.replace("/", ".")
            
            # Try to import the module
            module = importlib.import_module(module_path)
            
            # Get the class from the module
            if not hasattr(module, class_name):
                result.errors.append(f"Class '{class_name}' not found in module '{module_path}'")
                return None
            
            entry_point_class = getattr(module, class_name)
            
            # Verify it's a class
            if not isinstance(entry_point_class, type):
                result.errors.append(f"'{class_name}' is not a class")
                return None
            
            return entry_point_class
            
        except ImportError as e:
            result.errors.append(f"Failed to import module '{module_path}': {str(e)}")
            return None
        except Exception as e:
            result.errors.append(f"Import error: {str(e)}")
            return None
    
    def _validate_metadata_methods(self, entry_point_class: Type, result: ValidationResult) -> bool:
        """Validate that metadata methods exist and return correct types."""
        required_methods = [
            "get_python_dependencies",
            "get_platform_dependencies", 
            "get_platform_support"
        ]
        
        methods_valid = True
        
        for method_name in required_methods:
            if not hasattr(entry_point_class, method_name):
                result.errors.append(f"Missing required method: {method_name}")
                methods_valid = False
                continue
            
            try:
                method = getattr(entry_point_class, method_name)
                
                # Call the method and validate return type
                if method_name == "get_python_dependencies":
                    deps = method()
                    if not isinstance(deps, list):
                        result.errors.append(f"{method_name}() must return list, got {type(deps).__name__}")
                        methods_valid = False
                    elif not all(isinstance(dep, str) for dep in deps):
                        result.errors.append(f"{method_name}() must return list of strings")
                        methods_valid = False
                
                elif method_name == "get_platform_dependencies":
                    deps = method()
                    if not isinstance(deps, dict):
                        result.errors.append(f"{method_name}() must return dict, got {type(deps).__name__}")
                        methods_valid = False
                    elif not all(isinstance(k, str) and isinstance(v, list) for k, v in deps.items()):
                        result.errors.append(f"{method_name}() must return dict[str, list[str]]")
                        methods_valid = False
                
                elif method_name == "get_platform_support":
                    platforms = method()
                    if not isinstance(platforms, list):
                        result.errors.append(f"{method_name}() must return list, got {type(platforms).__name__}")
                        methods_valid = False
                    elif not all(isinstance(p, str) for p in platforms):
                        result.errors.append(f"{method_name}() must return list of strings")
                        methods_valid = False
                
            except Exception as e:
                result.errors.append(f"Error calling {method_name}(): {str(e)}")
                methods_valid = False
        
        return methods_valid
    
    def _validate_python_dependencies(self, entry_point_class: Type, result: ValidationResult) -> bool:
        """Validate Python dependencies exist in pyproject.toml optional-dependencies."""
        try:
            python_deps = entry_point_class.get_python_dependencies()
            if not python_deps:
                return True  # No dependencies to validate
            
            pyproject = self._load_pyproject()
            optional_deps = pyproject.get("project", {}).get("optional-dependencies", {})
            
            # Build set of all available packages from all dependency groups
            all_available_packages = set()
            for group_name, packages in optional_deps.items():
                for package in packages:
                    # Extract package name (before version specifiers or git URLs)
                    if " @ " in package:  # Git URL dependency
                        pkg_name = package.split(" @ ")[0]
                    elif ">=" in package:
                        pkg_name = package.split(">=")[0]
                    elif "==" in package:
                        pkg_name = package.split("==")[0] 
                    elif "[" in package:  # Package with extras
                        pkg_name = package.split("[")[0]
                    else:
                        pkg_name = package
                    
                    all_available_packages.add(pkg_name.strip())
            
            # Check each declared dependency
            deps_valid = True
            for dep in python_deps:
                # Extract package name from dependency specification
                if " @ " in dep:  # Git URL dependency  
                    pkg_name = dep.split(" @ ")[0]
                elif ">=" in dep:
                    pkg_name = dep.split(">=")[0]
                elif "==" in dep:
                    pkg_name = dep.split("==")[0]
                elif "[" in dep:  # Package with extras
                    pkg_name = dep.split("[")[0]
                else:
                    pkg_name = dep
                
                pkg_name = pkg_name.strip()
                
                if pkg_name not in all_available_packages:
                    result.warnings.append(f"Python dependency '{pkg_name}' not found in pyproject.toml optional-dependencies")
                    # Don't mark as invalid for missing packages - they might be external
            
            return deps_valid
            
        except Exception as e:
            result.errors.append(f"Python dependency validation failed: {str(e)}")
            return False
    
    def _validate_system_packages(self, entry_point_class: Type, platform: str, result: ValidationResult) -> bool:
        """Validate system packages exist for target platform."""
        try:
            platform_deps = entry_point_class.get_platform_dependencies()
            packages = platform_deps.get(platform, [])
            
            if not packages:
                return True  # No system packages to validate
            
            # Use known packages for validation (in real implementation, could query actual repos)
            known_packages = self._known_packages.get(platform, set())
            
            packages_valid = True
            for package in packages:
                if package not in known_packages:
                    result.warnings.append(f"System package '{package}' not in known {platform} packages (may need verification)")
                    # Don't mark as invalid - package might exist but not in our known set
            
            return packages_valid
            
        except Exception as e:
            result.errors.append(f"System package validation failed: {str(e)}")
            return False
    
    def _validate_platform_consistency(self, entry_point_class: Type, result: ValidationResult) -> bool:
        """Validate platform-specific dependencies are logically consistent."""
        try:
            platform_deps = entry_point_class.get_platform_dependencies()
            platform_support = entry_point_class.get_platform_support()
            
            consistency_valid = True
            
            # Check that all supported platforms have dependency mappings
            for platform in platform_support:
                if platform not in platform_deps:
                    result.warnings.append(f"Platform '{platform}' in support list but no dependencies defined")
            
            # Check for empty dependency lists (might be intentional)
            empty_platforms = [p for p, deps in platform_deps.items() if not deps]
            if empty_platforms:
                result.warnings.append(f"Platforms with no system dependencies: {empty_platforms}")
            
            # Check for common package naming patterns
            ubuntu_packages = set(platform_deps.get("ubuntu", []))
            alpine_packages = set(platform_deps.get("alpine", []))
            
            if ubuntu_packages and alpine_packages:
                # Look for potential naming inconsistencies
                ubuntu_dev_packages = {p for p in ubuntu_packages if p.endswith("-dev")}
                alpine_non_dev_packages = {p for p in alpine_packages if not p.endswith("-dev")}
                
                if ubuntu_dev_packages and alpine_non_dev_packages:
                    result.warnings.append("Potential naming inconsistency: Ubuntu has -dev packages but Alpine doesn't")
            
            return consistency_valid
            
        except Exception as e:
            result.errors.append(f"Platform consistency validation failed: {str(e)}")
            return False
    
    def generate_validation_report(self, report: ValidationReport, output_format: str = "text") -> str:
        """Generate formatted validation report."""
        if output_format == "json":
            # Convert ValidationResult objects to dictionaries for JSON serialization
            json_report = {
                "summary": {
                    "total_entry_points": report.total_entry_points,
                    "successful_validations": report.successful_validations,
                    "failed_validations": report.failed_validations,
                    "total_errors": report.total_errors,
                    "total_warnings": report.total_warnings
                },
                "platform_summary": report.platform_summary,
                "validation_results": {
                    key: {
                        "entry_point": result.entry_point,
                        "platform": result.platform,
                        "is_valid": result.is_valid,
                        "errors": result.errors,
                        "warnings": result.warnings,
                        "performance_ms": result.performance_ms,
                        "import_successful": result.import_successful,
                        "metadata_methods_exist": result.metadata_methods_exist,
                        "python_deps_valid": result.python_deps_valid,
                        "system_packages_valid": result.system_packages_valid,
                        "platform_consistency_valid": result.platform_consistency_valid
                    }
                    for key, result in report.validation_results.items()
                }
            }
            return json.dumps(json_report, indent=2)
        
        else:  # text format
            lines = []
            lines.append("🔍 Dependency Validation Report")
            lines.append("=" * 50)
            lines.append(f"📊 Summary: {report.successful_validations}/{report.total_entry_points} validations passed")
            lines.append(f"❌ Errors: {report.total_errors}")
            lines.append(f"⚠️  Warnings: {report.total_warnings}")
            lines.append("")
            
            # Platform summary
            lines.append("🖥️  Platform Summary:")
            for platform, stats in report.platform_summary.items():
                status = "✅" if stats["failed"] == 0 else "❌"
                lines.append(f"  {status} {platform}: {stats['passed']}/{stats['total']} passed, "
                           f"{stats['errors']} errors, {stats['warnings']} warnings")
            lines.append("")
            
            # Failed validations
            if report.failed_validations > 0:
                lines.append("❌ Failed Validations:")
                for key, result in report.validation_results.items():
                    if not result.is_valid:
                        lines.append(f"  {key}:")
                        for error in result.errors:
                            lines.append(f"    ERROR: {error}")
                        for warning in result.warnings:
                            lines.append(f"    WARNING: {warning}")
                lines.append("")
            
            # Performance issues
            slow_validations = [(k, r) for k, r in report.validation_results.items() if r.performance_ms > 100]
            if slow_validations:
                lines.append("⏱️  Performance Issues:")
                for key, result in slow_validations:
                    lines.append(f"  {key}: {result.performance_ms:.1f}ms")
                lines.append("")
            
            return "\n".join(lines)


def main():
    """Command-line interface for the dependency validator."""
    parser = argparse.ArgumentParser(
        description="Irene Voice Assistant - Dependency Validation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate single entry-point for specific platform
  python -m irene.tools.dependency_validator \\
      --file irene/providers/audio/sounddevice.py \\
      --class SoundDeviceAudioProvider \\
      --platform ubuntu

  # Validate all entry-points for specific platform
  python -m irene.tools.dependency_validator \\
      --validate-all --platform alpine

  # Cross-platform validation for CI/CD
  python -m irene.tools.dependency_validator \\
      --validate-all --platforms ubuntu,alpine,centos,macos

  # Generate JSON report for automation
  python -m irene.tools.dependency_validator \\
      --validate-all --platform ubuntu --json
        """
    )
    
    parser.add_argument(
        "--file",
        help="Path to Python file containing entry-point class"
    )
    parser.add_argument(
        "--class",
        dest="class_name",
        help="Name of the entry-point class to validate"
    )
    parser.add_argument(
        "--platform",
        choices=["ubuntu", "alpine", "centos", "macos"],
        help="Target platform for validation"
    )
    parser.add_argument(
        "--platforms",
        help="Comma-separated list of platforms for cross-platform validation"
    )
    parser.add_argument(
        "--validate-all",
        action="store_true",
        help="Validate all entry-points in the project"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
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
        validator = DependencyValidator()
        
        if args.validate_all:
            # Multi-platform validation
            if args.platforms:
                platforms = [p.strip() for p in args.platforms.split(",")]
            elif args.platform:
                platforms = [args.platform]
            else:
                platforms = ["ubuntu"]  # Default platform
            
            logger.info(f"Validating all entry-points for platforms: {platforms}")
            report = validator.validate_all_entry_points(platforms)
            
            output_format = "json" if args.json else "text"
            print(validator.generate_validation_report(report, output_format))
            
            return 0 if report.failed_validations == 0 else 1
        
        elif args.file and args.class_name and args.platform:
            # Single entry-point validation
            logger.info(f"Validating {args.file}:{args.class_name} for platform {args.platform}")
            result = validator.validate_entry_point(args.file, args.class_name, args.platform)
            
            if args.json:
                result_dict = {
                    "entry_point": result.entry_point,
                    "platform": result.platform,
                    "is_valid": result.is_valid,
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "performance_ms": result.performance_ms,
                    "import_successful": result.import_successful,
                    "metadata_methods_exist": result.metadata_methods_exist,
                    "python_deps_valid": result.python_deps_valid,
                    "system_packages_valid": result.system_packages_valid,
                    "platform_consistency_valid": result.platform_consistency_valid
                }
                print(json.dumps(result_dict, indent=2))
            else:
                status = "✅ VALID" if result.is_valid else "❌ INVALID"
                print(f"🔍 Validation Result: {status}")
                print(f"📁 Entry-point: {result.entry_point}")
                print(f"🖥️  Platform: {result.platform}")
                print(f"⏱️  Performance: {result.performance_ms:.1f}ms")
                
                if result.errors:
                    print("❌ Errors:")
                    for error in result.errors:
                        print(f"  - {error}")
                
                if result.warnings:
                    print("⚠️  Warnings:")
                    for warning in result.warnings:
                        print(f"  - {warning}")
            
            return 0 if result.is_valid else 1
        
        else:
            parser.error("Must specify either --validate-all or --file/--class/--platform")
            
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 