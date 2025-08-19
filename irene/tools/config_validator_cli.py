#!/usr/bin/env python3
"""
Configuration Validator CLI - Command-line interface for configuration validation

This tool provides a command-line interface for validating Irene Voice Assistant
configuration files using the comprehensive validation system.

Usage:
    python -m irene.tools.config_validator_cli --config-file ./configs/voice.toml
    python -m irene.tools.config_validator_cli --config-dir ./configs
    python -m irene.tools.config_validator_cli --config-file ./configs/voice.toml --verbose
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

import tomllib

from ..config.models import CoreConfig
from ..config.validator import validate_configuration, print_validation_results


logger = logging.getLogger(__name__)


class ConfigValidatorCLI:
    """Command-line interface for configuration validation"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
        # Setup logging
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(levelname)s: %(message)s',
            stream=sys.stdout
        )
    
    def validate_file(self, config_file: Path) -> bool:
        """
        Validate a single configuration file
        
        Args:
            config_file: Path to configuration file
            
        Returns:
            bool: True if validation passed (no errors)
        """
        if not config_file.exists():
            logger.error(f"Configuration file not found: {config_file}")
            return False
        
        try:
            logger.info(f"Validating configuration file: {config_file.name}")
            
            # Load configuration
            with open(config_file, "rb") as f:
                config_data = tomllib.load(f)
            
            # Parse with Pydantic
            try:
                config = CoreConfig.model_validate(config_data)
            except Exception as e:
                logger.error(f"Configuration parsing failed: {e}")
                return False
            
            # Run validation
            summary = validate_configuration(config)
            
            # Print results
            print_validation_results(summary, verbose=self.verbose)
            
            # Return validation status
            return summary.is_valid
            
        except Exception as e:
            logger.error(f"Validation failed for {config_file.name}: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def validate_directory(self, config_dir: Path) -> bool:
        """
        Validate all configuration files in a directory
        
        Args:
            config_dir: Path to directory containing configuration files
            
        Returns:
            bool: True if all validations passed (no errors)
        """
        if not config_dir.exists():
            logger.error(f"Configuration directory not found: {config_dir}")
            return False
        
        # Find all TOML files
        config_files = list(config_dir.glob("*.toml"))
        
        if not config_files:
            logger.warning(f"No TOML configuration files found in {config_dir}")
            return True
        
        logger.info(f"Found {len(config_files)} configuration files in {config_dir}")
        
        all_valid = True
        results = {}
        
        # Validate each file
        for config_file in sorted(config_files):
            # Skip backup files
            if config_file.name.endswith('.backup'):
                continue
                
            logger.info(f"\n{'='*60}")
            logger.info(f"VALIDATING: {config_file.name}")
            logger.info(f"{'='*60}")
            
            is_valid = self.validate_file(config_file)
            results[config_file.name] = is_valid
            
            if not is_valid:
                all_valid = False
        
        # Print summary
        self._print_directory_summary(results)
        
        return all_valid
    
    def _print_directory_summary(self, results: dict) -> None:
        """Print validation summary for directory validation"""
        print(f"\n{'='*60}")
        print("DIRECTORY VALIDATION SUMMARY")
        print(f"{'='*60}")
        
        valid_files = [name for name, valid in results.items() if valid]
        invalid_files = [name for name, valid in results.items() if not valid]
        
        print(f"Total files processed: {len(results)}")
        print(f"Valid configurations: {len(valid_files)}")
        print(f"Invalid configurations: {len(invalid_files)}")
        
        if valid_files:
            print(f"\n✅ Valid files:")
            for name in valid_files:
                print(f"  ✓ {name}")
        
        if invalid_files:
            print(f"\n❌ Invalid files:")
            for name in invalid_files:
                print(f"  ✗ {name}")
        
        if len(invalid_files) == 0:
            print(f"\n🎉 All configuration files are valid!")
        else:
            print(f"\n⚠️  {len(invalid_files)} configuration files have validation errors")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Validate Irene Voice Assistant configuration files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a single configuration file
  python -m irene.tools.config_validator_cli --config-file ./configs/voice.toml
  
  # Validate all configurations in a directory
  python -m irene.tools.config_validator_cli --config-dir ./configs
  
  # Verbose validation with detailed output
  python -m irene.tools.config_validator_cli --config-file ./configs/voice.toml --verbose
  
  # Check specific profile configurations
  python -m irene.tools.config_validator_cli --config-file ./configs/api-only.toml
"""
    )
    
    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--config-file", 
        type=Path,
        help="Single configuration file to validate"
    )
    input_group.add_argument(
        "--config-dir", 
        type=Path,
        help="Directory containing configuration files to validate"
    )
    
    # Output options
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true",
        help="Enable verbose output with detailed validation results"
    )
    
    args = parser.parse_args()
    
    try:
        # Create CLI instance
        cli = ConfigValidatorCLI(verbose=args.verbose)
        
        # Run validation
        if args.config_file:
            success = cli.validate_file(args.config_file)
        else:
            success = cli.validate_directory(args.config_dir)
        
        # Exit with appropriate code
        if success:
            logger.info("\n🎉 Configuration validation completed successfully!")
            sys.exit(0)
        else:
            logger.error("\n❌ Configuration validation failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("\nValidation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Validation tool failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
