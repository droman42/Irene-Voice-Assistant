#!/usr/bin/env python3
"""
Configuration Validator CLI - Standalone CI/CD Tool

A lightweight, standalone tool focused exclusively on configuration file validation,
making it perfect for CI/CD pipelines, Docker builds, and development workflows.

Architectural Principle: Single Responsibility - Configuration Validation Only

Features:
- AutoSchemaRegistry Integration: Use unified schema system for validation
- Master Config Completeness: Validate against config-master.toml reference
- Schema Coverage Validation: Ensure all sections have valid schemas
- JSON Output for CI/CD: Machine-readable reports for automation
- Multi-Config Validation: Batch validation of configuration directories
- Security Validation: Basic security checks (no exposed secrets, etc.)
- Deployment Profile Validation: Validate specific deployment profiles

Exit Codes:
- 0: Valid configuration(s)
- 1: Invalid configuration(s) 
- 2: Tool error (file not found, permission issues, etc.)
"""

import argparse
import json
import logging
import sys
import tomllib
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import re

# Setup logging before imports to avoid config loading side effects
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from irene.config.auto_registry import AutoSchemaRegistry
    from irene.config.models import CoreConfig
    from irene.config.manager import ConfigManager
except ImportError as e:
    print(f"Error: Failed to import Irene configuration modules: {e}", file=sys.stderr)
    print("Make sure you're running this from the project root and all dependencies are installed.", file=sys.stderr)
    sys.exit(2)


class ConfigValidationResult:
    """Container for validation results"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.security_issues: List[str] = []
        self.schema_coverage_issues: List[str] = []
        self.file_size = 0
        self.sections_validated = 0
        self.providers_validated = 0
    
    def add_error(self, message: str):
        """Add validation error"""
        self.errors.append(message)
        self.valid = False
    
    def add_warning(self, message: str):
        """Add validation warning"""
        self.warnings.append(message)
    
    def add_security_issue(self, message: str):
        """Add security issue"""
        self.security_issues.append(message)
        # Security issues are treated as errors
        self.valid = False
    
    def add_schema_coverage_issue(self, message: str):
        """Add schema coverage issue"""
        self.schema_coverage_issues.append(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON output"""
        return {
            "file_path": self.file_path,
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "security_issues": self.security_issues,
            "schema_coverage_issues": self.schema_coverage_issues,
            "file_size": self.file_size,
            "sections_validated": self.sections_validated,
            "providers_validated": self.providers_validated
        }


class ConfigValidatorCLI:
    """Standalone configuration validator for CI/CD pipelines"""
    
    def __init__(self, ci_mode: bool = False, json_output: bool = False):
        self.ci_mode = ci_mode
        self.json_output = json_output
        self.config_manager = ConfigManager()
        
        # Configure logging for CI mode
        if ci_mode:
            # Suppress debug/info logs in CI mode
            logging.getLogger().setLevel(logging.ERROR)
    
    def validate_single_config(self, config_path: Path, profile: Optional[str] = None) -> ConfigValidationResult:
        """Validate a single configuration file"""
        result = ConfigValidationResult(str(config_path))
        
        try:
            # Check file existence and accessibility
            if not config_path.exists():
                result.add_error(f"Configuration file not found: {config_path}")
                return result
            
            if not config_path.is_file():
                result.add_error(f"Path is not a file: {config_path}")
                return result
            
            # Get file metadata
            stat = config_path.stat()
            result.file_size = stat.st_size
            
            # Load and validate TOML syntax
            try:
                with open(config_path, "rb") as f:
                    toml_data = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                result.add_error(f"TOML syntax error: {e}")
                return result
            except Exception as e:
                result.add_error(f"Failed to read configuration file: {e}")
                return result
            
            # Validate against Pydantic schema
            try:
                # Use synchronous validation for CLI tool
                from irene.config.models import CoreConfig
                config = CoreConfig.model_validate(toml_data)
                result.sections_validated = len([k for k in toml_data.keys() if k in AutoSchemaRegistry.get_section_models()])
            except Exception as e:
                result.add_error(f"Configuration validation failed: {e}")
                return result
            
            # Validate profile-specific requirements
            if profile:
                self._validate_profile_requirements(config, profile, result)
            
            # Security validation
            self._validate_security(toml_data, result)
            
            # Schema coverage validation
            self._validate_schema_coverage(toml_data, result)
            
            # Provider validation
            self._validate_providers(toml_data, result)
            
        except Exception as e:
            result.add_error(f"Unexpected validation error: {e}")
        
        return result
    
    def validate_config_directory(self, config_dir: Path) -> List[ConfigValidationResult]:
        """Validate all configuration files in a directory"""
        results = []
        
        if not config_dir.exists():
            result = ConfigValidationResult(str(config_dir))
            result.add_error(f"Configuration directory not found: {config_dir}")
            return [result]
        
        if not config_dir.is_dir():
            result = ConfigValidationResult(str(config_dir))
            result.add_error(f"Path is not a directory: {config_dir}")
            return [result]
        
        # Find all TOML files
        toml_files = list(config_dir.glob("*.toml"))
        
        if not toml_files:
            result = ConfigValidationResult(str(config_dir))
            result.add_warning(f"No TOML configuration files found in: {config_dir}")
            results.append(result)
            return results
        
        # Validate each file
        for config_file in sorted(toml_files):
            result = self.validate_single_config(config_file)
            results.append(result)
        
        return results
    
    def validate_master_config_completeness(self) -> Dict[str, Any]:
        """Validate master config completeness against all provider schemas"""
        try:
            return AutoSchemaRegistry.get_master_config_completeness()
        except Exception as e:
            logger.error(f"Master config completeness validation failed: {e}")
            return {
                "valid": False,
                "error": str(e),
                "missing_sections": [],
                "orphaned_sections": [],
                "coverage_percentage": 0.0
            }
    
    def validate_schema_coverage_global(self) -> Dict[str, Any]:
        """Validate global schema coverage"""
        try:
            return AutoSchemaRegistry.validate_schema_coverage()
        except Exception as e:
            logger.error(f"Schema coverage validation failed: {e}")
            return {
                "valid": False,
                "error": str(e),
                "warnings": [],
                "errors": [str(e)],
                "recommendations": []
            }
    
    def _validate_profile_requirements(self, config: CoreConfig, profile: str, result: ConfigValidationResult):
        """Validate profile-specific requirements"""
        try:
            # Define profile requirements
            profile_requirements = {
                "voice-assistant": {
                    "required_components": ["tts", "audio", "asr", "voice_trigger", "nlu"],
                    "required_providers": {
                        "tts": ["elevenlabs", "silero_v3", "silero_v4"],
                        "audio": ["sounddevice", "audioplayer"],
                        "asr": ["whisper", "vosk"],
                        "voice_trigger": ["openwakeword", "porcupine", "microwakeword"]
                    }
                },
                "api-only": {
                    "required_components": ["tts", "llm"],
                    "optional_components": ["audio", "asr"],
                    "required_providers": {
                        "tts": ["console", "elevenlabs"],
                        "llm": ["openai", "anthropic"]
                    }
                },
                "minimal": {
                    "required_components": ["tts"],
                    "required_providers": {
                        "tts": ["console"]
                    }
                }
            }
            
            requirements = profile_requirements.get(profile)
            if not requirements:
                result.add_warning(f"Unknown profile '{profile}' - skipping profile validation")
                return
            
            # Check required components
            for component in requirements.get("required_components", []):
                if not getattr(config.components, component, False):
                    result.add_error(f"Profile '{profile}' requires component '{component}' to be enabled")
            
            # Check required providers
            for component, providers in requirements.get("required_providers", {}).items():
                component_config = getattr(config, component, None)
                if component_config and hasattr(component_config, 'providers'):
                    available_providers = list(component_config.providers.keys())
                    missing_providers = [p for p in providers if p not in available_providers]
                    if missing_providers:
                        result.add_warning(f"Profile '{profile}' recommends providers {missing_providers} for component '{component}'")
        
        except Exception as e:
            result.add_error(f"Profile validation failed: {e}")
    
    def _validate_security(self, toml_data: Dict[str, Any], result: ConfigValidationResult):
        """Validate security aspects of configuration"""
        try:
            # Convert to JSON string for pattern matching
            config_str = json.dumps(toml_data, default=str)
            
            # Check for exposed secrets
            secret_patterns = [
                (r'["\']?api_key["\']?\s*[:=]\s*["\'][^"\']{10,}["\']', "Potential API key exposure"),
                (r'["\']?access_key["\']?\s*[:=]\s*["\'][^"\']{10,}["\']', "Potential access key exposure"),
                (r'["\']?secret["\']?\s*[:=]\s*["\'][^"\']{10,}["\']', "Potential secret exposure"),
                (r'["\']?password["\']?\s*[:=]\s*["\'][^"\']{1,}["\']', "Potential password exposure"),
                (r'["\']?token["\']?\s*[:=]\s*["\'][^"\']{10,}["\']', "Potential token exposure"),
                (r'sk-[a-zA-Z0-9]{20,}', "OpenAI API key pattern detected"),
                (r'claude-[a-zA-Z0-9-]{20,}', "Anthropic API key pattern detected")
            ]
            
            for pattern, message in secret_patterns:
                if re.search(pattern, config_str, re.IGNORECASE):
                    # Check if it's likely a placeholder/environment variable
                    if "${" in config_str or "PLACEHOLDER" in config_str.upper():
                        result.add_warning(f"Security: {message} (appears to be placeholder/env var)")
                    else:
                        result.add_security_issue(f"Security: {message}")
            
            # Check for insecure configurations
            self._check_insecure_configs(toml_data, result)
        
        except Exception as e:
            result.add_warning(f"Security validation failed: {e}")
    
    def _check_insecure_configs(self, toml_data: Dict[str, Any], result: ConfigValidationResult):
        """Check for insecure configuration patterns"""
        try:
            # Check for debug modes in production
            if toml_data.get("system", {}).get("debug", False):
                result.add_warning("Security: Debug mode is enabled - consider disabling for production")
            
            # Check for development settings
            if toml_data.get("system", {}).get("environment") == "development":
                result.add_warning("Security: Environment set to 'development' - ensure this is intentional")
            
            # Check for permissive CORS settings
            if toml_data.get("system", {}).get("allow_cors", False):
                result.add_warning("Security: CORS is enabled - ensure proper origin restrictions")
        
        except Exception as e:
            result.add_warning(f"Insecure configuration check failed: {e}")
    
    def _validate_schema_coverage(self, toml_data: Dict[str, Any], result: ConfigValidationResult):
        """Validate schema coverage for the configuration"""
        try:
            # Get available section models
            section_models = AutoSchemaRegistry.get_section_models()
            
            # System-level fields that are part of CoreConfig but not separate sections
            system_level_fields = {
                'name', 'version', 'debug', 'log_level', 'language', 'timezone',
                'context_timeout_minutes', 'command_timeout_seconds', 'max_concurrent_commands',
                'testing'  # Used in some test configs
            }
            
            # Check coverage of sections in config
            config_sections = set(toml_data.keys())
            available_sections = set(section_models.keys())
            
            # Find unknown sections (excluding system-level fields)
            unknown_sections = config_sections - available_sections - system_level_fields
            if unknown_sections:
                for section in unknown_sections:
                    result.add_schema_coverage_issue(f"Unknown configuration section: '{section}' (no schema available)")
            
            # Check for sections that should have schemas but don't
            missing_schemas = available_sections - config_sections
            if missing_schemas:
                result.add_warning(f"Available sections not used in config: {list(missing_schemas)}")
        
        except Exception as e:
            result.add_warning(f"Schema coverage validation failed: {e}")
    
    def _validate_providers(self, toml_data: Dict[str, Any], result: ConfigValidationResult):
        """Validate provider configurations"""
        try:
            provider_count = 0
            
            # Get provider schemas
            provider_schemas = AutoSchemaRegistry.get_provider_schemas()
            
            # Validate each component's providers
            for component_type, component_config in toml_data.items():
                if isinstance(component_config, dict) and "providers" in component_config:
                    providers = component_config["providers"]
                    
                    for provider_name, provider_config in providers.items():
                        provider_count += 1
                        
                        # Check if provider schema exists
                        if component_type not in provider_schemas:
                            result.add_warning(f"No provider schemas available for component type: {component_type}")
                            continue
                        
                        if provider_name not in provider_schemas[component_type]:
                            result.add_warning(f"Unknown provider '{provider_name}' for component '{component_type}'")
                            continue
                        
                        # Validate provider configuration
                        if not AutoSchemaRegistry.validate_provider_config(component_type, provider_name, provider_config):
                            result.add_error(f"Invalid configuration for provider '{provider_name}' in component '{component_type}'")
            
            result.providers_validated = provider_count
        
        except Exception as e:
            result.add_warning(f"Provider validation failed: {e}")
    
    def generate_report(self, results: List[ConfigValidationResult], 
                       master_config_report: Optional[Dict[str, Any]] = None,
                       schema_coverage_report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        
        total_files = len(results)
        valid_files = sum(1 for r in results if r.valid)
        total_errors = sum(len(r.errors) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)
        total_security_issues = sum(len(r.security_issues) for r in results)
        
        report = {
            "summary": {
                "total_files": total_files,
                "valid_files": valid_files,
                "invalid_files": total_files - valid_files,
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "total_security_issues": total_security_issues,
                "overall_valid": total_errors == 0 and total_security_issues == 0
            },
            "files": [result.to_dict() for result in results]
        }
        
        if master_config_report:
            report["master_config_completeness"] = master_config_report
        
        if schema_coverage_report:
            report["schema_coverage"] = schema_coverage_report
        
        return report
    
    def print_results(self, results: List[ConfigValidationResult], 
                     master_config_report: Optional[Dict[str, Any]] = None,
                     schema_coverage_report: Optional[Dict[str, Any]] = None):
        """Print validation results in human-readable format"""
        
        if self.json_output:
            report = self.generate_report(results, master_config_report, schema_coverage_report)
            print(json.dumps(report, indent=2))
            return
        
        # Human-readable output
        print("Configuration Validation Results")
        print("=" * 50)
        
        overall_valid = True
        
        for result in results:
            print(f"\nFile: {result.file_path}")
            print(f"Status: {'✓ Valid' if result.valid else '✗ Invalid'}")
            print(f"Size: {result.file_size} bytes")
            print(f"Sections: {result.sections_validated}, Providers: {result.providers_validated}")
            
            if result.errors:
                print(f"Errors ({len(result.errors)}):")
                for error in result.errors:
                    print(f"  ✗ {error}")
                overall_valid = False
            
            if result.security_issues:
                print(f"Security Issues ({len(result.security_issues)}):")
                for issue in result.security_issues:
                    print(f"  ⚠ {issue}")
                overall_valid = False
            
            if result.warnings:
                print(f"Warnings ({len(result.warnings)}):")
                for warning in result.warnings:
                    print(f"  ⚠ {warning}")
            
            if result.schema_coverage_issues:
                print(f"Schema Coverage Issues ({len(result.schema_coverage_issues)}):")
                for issue in result.schema_coverage_issues:
                    print(f"  ⚠ {issue}")
        
        # Master config completeness
        if master_config_report:
            print(f"\nMaster Config Completeness")
            print("-" * 30)
            print(f"Coverage: {master_config_report.get('coverage_percentage', 0):.1f}%")
            
            if master_config_report.get('missing_sections'):
                print(f"Missing sections ({len(master_config_report['missing_sections'])}):")
                for section in master_config_report['missing_sections']:
                    print(f"  ✗ {section}")
            
            if master_config_report.get('orphaned_sections'):
                print(f"Orphaned sections ({len(master_config_report['orphaned_sections'])}):")
                for section in master_config_report['orphaned_sections']:
                    print(f"  ⚠ {section}")
        
        # Schema coverage
        if schema_coverage_report:
            print(f"\nSchema Coverage")
            print("-" * 20)
            print(f"Valid: {'✓' if schema_coverage_report.get('valid', False) else '✗'}")
            
            if schema_coverage_report.get('errors'):
                print("Errors:")
                for error in schema_coverage_report['errors']:
                    print(f"  ✗ {error}")
                overall_valid = False
            
            if schema_coverage_report.get('warnings'):
                print("Warnings:")
                for warning in schema_coverage_report['warnings']:
                    print(f"  ⚠ {warning}")
        
        print(f"\nOverall Result: {'✓ All configurations valid' if overall_valid else '✗ Validation failed'}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Standalone configuration validator for CI/CD pipelines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate single configuration file
  python -m irene.tools.config_validator_cli --config-file configs/production.toml
  
  # CI/CD mode with JSON output
  python -m irene.tools.config_validator_cli --config-file configs/api-only.toml --json --ci-mode
  
  # Validate all configs in directory
  python -m irene.tools.config_validator_cli --config-dir configs/ --json
  
  # Profile-specific validation
  python -m irene.tools.config_validator_cli --config-file configs/voice.toml --profile voice-assistant
  
  # Generate validation report
  python -m irene.tools.config_validator_cli --config-file configs/production.toml --output-report report.json

Exit Codes:
  0 - All configurations are valid
  1 - One or more configurations are invalid
  2 - Tool error (file not found, permission issues, etc.)
        """
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--config-file", "-f",
        type=Path,
        help="Single configuration file to validate"
    )
    input_group.add_argument(
        "--config-dir", "-d", 
        type=Path,
        help="Directory containing configuration files to validate"
    )
    
    # Validation options
    parser.add_argument(
        "--profile", "-p",
        choices=["voice-assistant", "api-only", "minimal"],
        help="Validate against specific deployment profile requirements"
    )
    
    # Output options
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results in JSON format for automation"
    )
    parser.add_argument(
        "--output-report", "-o",
        type=Path,
        help="Save validation report to file (JSON format)"
    )
    
    # CI/CD options
    parser.add_argument(
        "--ci-mode",
        action="store_true", 
        help="CI/CD mode: suppress verbose logging, optimized for automation"
    )
    
    # Global validation options
    parser.add_argument(
        "--skip-master-config",
        action="store_true",
        help="Skip master config completeness validation"
    )
    parser.add_argument(
        "--skip-schema-coverage", 
        action="store_true",
        help="Skip global schema coverage validation"
    )
    
    # Verbosity
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose and not args.ci_mode:
        logging.getLogger().setLevel(logging.INFO)
    elif args.ci_mode:
        logging.getLogger().setLevel(logging.ERROR)
    
    try:
        # Initialize validator
        validator = ConfigValidatorCLI(ci_mode=args.ci_mode, json_output=args.json)
        
        # Validate configurations
        if args.config_file:
            results = [validator.validate_single_config(args.config_file, args.profile)]
        else:
            results = validator.validate_config_directory(args.config_dir)
        
        # Global validations
        master_config_report = None
        if not args.skip_master_config:
            master_config_report = validator.validate_master_config_completeness()
        
        schema_coverage_report = None
        if not args.skip_schema_coverage:
            schema_coverage_report = validator.validate_schema_coverage_global()
        
        # Generate and output results
        if args.output_report:
            report = validator.generate_report(results, master_config_report, schema_coverage_report)
            with open(args.output_report, 'w') as f:
                json.dump(report, f, indent=2)
            
            if not args.json:
                print(f"Validation report saved to: {args.output_report}")
        
        # Print results
        validator.print_results(results, master_config_report, schema_coverage_report)
        
        # Determine exit code
        has_errors = any(not result.valid for result in results)
        has_master_config_errors = master_config_report and not master_config_report.get('valid', True)
        has_schema_coverage_errors = schema_coverage_report and not schema_coverage_report.get('valid', True)
        
        if has_errors or has_master_config_errors or has_schema_coverage_errors:
            sys.exit(1)
        else:
            sys.exit(0)
    
    except KeyboardInterrupt:
        print("\nValidation interrupted by user", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()