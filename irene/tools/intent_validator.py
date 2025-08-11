"""
Irene Voice Assistant - Intent JSON Validation Tool

This module provides validation functionality for intent handler JSON configurations
against their JSON schema to ensure correctness during build time and deployment.

Usage:
    python -m irene.tools.intent_validator --validate-all
    python -m irene.tools.intent_validator --file irene/intents/handlers/timer.json
    python -m irene.tools.intent_validator --handler timer
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
import jsonschema
from jsonschema import ValidationError

logger = logging.getLogger(__name__)


class IntentValidationResult:
    """Container for intent validation results."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.schema_errors: List[str] = []
        self.intent_data: Optional[Dict[str, Any]] = None


class IntentJSONValidator:
    """
    Validator for intent handler JSON configurations.
    
    Validates JSON files against the donation schema and performs
    additional semantic validation for intent-specific requirements.
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the intent validator.
        
        Args:
            project_root: Path to project root. If None, auto-detect from current directory.
        """
        self.project_root = project_root or self._find_project_root()
        self.schema_path = self.project_root / "schemas" / "donation" / "v1.0.json"
        self.intents_dir = self.project_root / "irene" / "intents" / "handlers"
        
        # Cache for loaded schema
        self._schema_cache: Optional[Dict[str, Any]] = None
        
    def _find_project_root(self) -> Path:
        """Find the project root directory by looking for pyproject.toml."""
        current = Path.cwd()
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent
        
        # Fallback to current directory
        return Path.cwd()
    
    def _load_schema(self) -> Dict[str, Any]:
        """Load and cache the JSON schema for intent donations."""
        if self._schema_cache is not None:
            return self._schema_cache
        
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")
        
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            self._schema_cache = schema
            return schema
        except Exception as e:
            raise RuntimeError(f"Failed to load schema from {self.schema_path}: {e}")
    
    def discover_intent_files(self) -> List[Path]:
        """
        Discover all intent JSON files in the handlers directory.
        
        Returns:
            List of Path objects for JSON files found
        """
        if not self.intents_dir.exists():
            logger.warning(f"Intents directory not found: {self.intents_dir}")
            return []
        
        json_files = []
        for json_file in self.intents_dir.glob("*.json"):
            # Check if corresponding Python handler exists
            py_file = json_file.with_suffix('.py')
            if py_file.exists():
                json_files.append(json_file)
            else:
                logger.warning(f"JSON file {json_file.name} has no corresponding Python handler {py_file.name}")
        
        logger.info(f"Discovered {len(json_files)} intent JSON files: {[f.name for f in json_files]}")
        return sorted(json_files)
    
    def validate_intent_file(self, file_path: Path) -> IntentValidationResult:
        """
        Validate a single intent JSON file.
        
        Args:
            file_path: Path to the JSON file to validate
            
        Returns:
            IntentValidationResult with validation status and details
        """
        result = IntentValidationResult(str(file_path))
        
        # Check if file exists
        if not file_path.exists():
            result.is_valid = False
            result.errors.append(f"File not found: {file_path}")
            return result
        
        # Load JSON data
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                intent_data = json.load(f)
            result.intent_data = intent_data
        except json.JSONDecodeError as e:
            result.is_valid = False
            result.errors.append(f"Invalid JSON syntax: {e}")
            return result
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Failed to read file: {e}")
            return result
        
        # Validate against JSON schema
        try:
            schema = self._load_schema()
            jsonschema.validate(intent_data, schema)
            logger.debug(f"Schema validation passed for {file_path.name}")
        except ValidationError as e:
            result.is_valid = False
            result.schema_errors.append(f"Schema validation error: {e.message}")
            if hasattr(e, 'path') and e.path:
                result.schema_errors.append(f"  Path: {' -> '.join(str(p) for p in e.path)}")
        except Exception as e:
            result.is_valid = False
            result.schema_errors.append(f"Schema validation failed: {e}")
        
        # Perform semantic validation
        self._validate_intent_semantics(intent_data, result)
        
        # Check for corresponding Python handler
        self._validate_handler_correspondence(file_path, result)
        
        return result
    
    def _validate_intent_semantics(self, intent_data: Dict[str, Any], result: IntentValidationResult):
        """
        Perform semantic validation beyond JSON schema.
        
        Args:
            intent_data: Parsed JSON data
            result: Validation result to update
        """
        # Validate handler domain matches filename
        handler_domain = intent_data.get('handler_domain', '')
        file_stem = Path(result.file_path).stem
        
        if handler_domain != file_stem:
            result.warnings.append(f"Handler domain '{handler_domain}' doesn't match filename '{file_stem}'")
        
        # Validate method donations
        method_donations = intent_data.get('method_donations', [])
        if not method_donations:
            result.errors.append("No method donations found - at least one method donation is required")
            result.is_valid = False
        
        # Check for duplicate method names
        method_names = [donation.get('method_name', '') for donation in method_donations]
        duplicates = set([name for name in method_names if method_names.count(name) > 1])
        if duplicates:
            result.errors.append(f"Duplicate method names found: {duplicates}")
            result.is_valid = False
        
        # Check for duplicate intent suffixes
        intent_suffixes = [donation.get('intent_suffix', '') for donation in method_donations]
        duplicates = set([suffix for suffix in intent_suffixes if intent_suffixes.count(suffix) > 1])
        if duplicates:
            result.errors.append(f"Duplicate intent suffixes found: {duplicates}")
            result.is_valid = False
        
        # Validate intent name patterns against domain
        intent_patterns = intent_data.get('intent_name_patterns', [])
        for pattern in intent_patterns:
            if not pattern.startswith(f"{handler_domain}."):
                result.warnings.append(f"Intent pattern '{pattern}' should start with domain '{handler_domain}.'")
        
        # Validate parameter specifications
        for i, donation in enumerate(method_donations):
            self._validate_method_donation(donation, i, result)
    
    def _validate_method_donation(self, donation: Dict[str, Any], index: int, result: IntentValidationResult):
        """
        Validate a single method donation.
        
        Args:
            donation: Method donation data
            index: Index of the donation in the list
            result: Validation result to update
        """
        method_name = donation.get('method_name', f'<method_{index}>')
        
        # Validate required phrases
        phrases = donation.get('phrases', [])
        if not phrases:
            result.warnings.append(f"Method '{method_name}' has no trigger phrases")
        
        # Validate parameters
        parameters = donation.get('parameters', [])
        param_names = set()
        
        for param in parameters:
            param_name = param.get('name', '')
            if not param_name:
                result.errors.append(f"Method '{method_name}' has parameter with no name")
                result.is_valid = False
                continue
            
            if param_name in param_names:
                result.errors.append(f"Method '{method_name}' has duplicate parameter name '{param_name}'")
                result.is_valid = False
            param_names.add(param_name)
            
            # Validate parameter type
            param_type = param.get('type', '')
            valid_types = ['string', 'integer', 'float', 'duration', 'datetime', 'boolean', 'choice', 'entity']
            if param_type not in valid_types:
                result.errors.append(f"Method '{method_name}' parameter '{param_name}' has invalid type '{param_type}'")
                result.is_valid = False
            
            # Validate choice parameters have choices
            if param_type == 'choice':
                choices = param.get('choices', [])
                if not choices:
                    result.errors.append(f"Method '{method_name}' parameter '{param_name}' of type 'choice' must have choices")
                    result.is_valid = False
        
        # Validate examples reference actual parameters
        examples = donation.get('examples', [])
        for example in examples:
            example_params = example.get('parameters', {})
            for param_name in example_params.keys():
                if param_name not in param_names:
                    result.warnings.append(f"Method '{method_name}' example references undefined parameter '{param_name}'")
    
    def _validate_handler_correspondence(self, json_path: Path, result: IntentValidationResult):
        """
        Validate that the JSON file has a corresponding Python handler.
        
        Args:
            json_path: Path to the JSON file
            result: Validation result to update
        """
        py_path = json_path.with_suffix('.py')
        if not py_path.exists():
            result.errors.append(f"No corresponding Python handler found: {py_path}")
            result.is_valid = False
        else:
            # Check if Python handler imports correctly
            try:
                # Basic syntax check by reading the file
                with open(py_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for basic handler class structure
                handler_domain = json_path.stem
                expected_class = f"{handler_domain.title()}IntentHandler"
                
                if expected_class not in content:
                    result.warnings.append(f"Expected handler class '{expected_class}' not found in {py_path.name}")
                    
            except Exception as e:
                result.warnings.append(f"Could not read Python handler {py_path.name}: {e}")
    
    def validate_all_intents(self) -> Dict[str, IntentValidationResult]:
        """
        Validate all intent JSON files in the handlers directory.
        
        Returns:
            Dictionary mapping file names to validation results
        """
        json_files = self.discover_intent_files()
        results = {}
        
        for json_file in json_files:
            result = self.validate_intent_file(json_file)
            results[json_file.name] = result
        
        return results
    
    def validate_handler(self, handler_name: str) -> IntentValidationResult:
        """
        Validate a specific intent handler by name.
        
        Args:
            handler_name: Name of the handler (without .json extension)
            
        Returns:
            IntentValidationResult for the specified handler
        """
        json_file = self.intents_dir / f"{handler_name}.json"
        return self.validate_intent_file(json_file)
    
    def get_validation_summary(self, results: Dict[str, IntentValidationResult]) -> Dict[str, Any]:
        """
        Generate a summary of validation results.
        
        Args:
            results: Dictionary of validation results
            
        Returns:
            Summary dictionary with counts and overall status
        """
        total_files = len(results)
        valid_files = sum(1 for r in results.values() if r.is_valid)
        invalid_files = total_files - valid_files
        
        total_errors = sum(len(r.errors) + len(r.schema_errors) for r in results.values())
        total_warnings = sum(len(r.warnings) for r in results.values())
        
        return {
            'total_files': total_files,
            'valid_files': valid_files,
            'invalid_files': invalid_files,
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'overall_valid': invalid_files == 0,
            'files': {name: r.is_valid for name, r in results.items()}
        }


def main():
    """Command-line interface for the intent validator."""
    parser = argparse.ArgumentParser(
        description="Irene Voice Assistant - Intent JSON Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all intent JSON files
  python -m irene.tools.intent_validator --validate-all

  # Validate a specific JSON file
  python -m irene.tools.intent_validator --file irene/intents/handlers/timer.json

  # Validate a specific handler by name
  python -m irene.tools.intent_validator --handler timer

  # Validate with JSON output
  python -m irene.tools.intent_validator --validate-all --json

  # Validate with detailed output
  python -m irene.tools.intent_validator --validate-all --verbose
        """
    )
    
    parser.add_argument(
        "--validate-all", 
        action="store_true",
        help="Validate all intent JSON files in the handlers directory"
    )
    parser.add_argument(
        "--file", 
        help="Path to specific JSON file to validate"
    )
    parser.add_argument(
        "--handler", 
        help="Name of specific handler to validate (without .json extension)"
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
    parser.add_argument(
        "--quiet", 
        action="store_true",
        help="Only show errors and warnings"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    if args.quiet:
        log_level = logging.WARNING
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
        
    logging.basicConfig(
        level=log_level,
        format='%(levelname)s: %(message)s'
    )
    
    try:
        validator = IntentJSONValidator()
        
        # Determine what to validate
        if args.validate_all:
            results = validator.validate_all_intents()
            summary = validator.get_validation_summary(results)
            
            if args.json:
                output = {
                    'summary': summary,
                    'results': {
                        name: {
                            'valid': result.is_valid,
                            'errors': result.errors + result.schema_errors,
                            'warnings': result.warnings,
                            'file_path': result.file_path
                        }
                        for name, result in results.items()
                    }
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"🔍 Intent JSON Validation Summary")
                print(f"Total files: {summary['total_files']}")
                print(f"Valid files: {summary['valid_files']}")
                print(f"Invalid files: {summary['invalid_files']}")
                print(f"Total errors: {summary['total_errors']}")
                print(f"Total warnings: {summary['total_warnings']}")
                print(f"Overall status: {'✅ PASSED' if summary['overall_valid'] else '❌ FAILED'}")
                
                if not args.quiet:
                    print("\n📋 File Details:")
                    for name, result in results.items():
                        status = "✅ VALID" if result.is_valid else "❌ INVALID"
                        print(f"  {name}: {status}")
                        
                        for error in result.errors + result.schema_errors:
                            print(f"    ❌ ERROR: {error}")
                        for warning in result.warnings:
                            print(f"    ⚠️  WARNING: {warning}")
            
            return 0 if summary['overall_valid'] else 1
            
        elif args.file:
            file_path = Path(args.file)
            result = validator.validate_intent_file(file_path)
            
            if args.json:
                output = {
                    'valid': result.is_valid,
                    'errors': result.errors + result.schema_errors,
                    'warnings': result.warnings,
                    'file_path': result.file_path
                }
                print(json.dumps(output, indent=2))
            else:
                status = "✅ VALID" if result.is_valid else "❌ INVALID"
                print(f"🔍 Validation Result for {file_path.name}: {status}")
                
                for error in result.errors + result.schema_errors:
                    print(f"  ❌ ERROR: {error}")
                for warning in result.warnings:
                    print(f"  ⚠️  WARNING: {warning}")
            
            return 0 if result.is_valid else 1
            
        elif args.handler:
            result = validator.validate_handler(args.handler)
            
            if args.json:
                output = {
                    'valid': result.is_valid,
                    'errors': result.errors + result.schema_errors,
                    'warnings': result.warnings,
                    'file_path': result.file_path
                }
                print(json.dumps(output, indent=2))
            else:
                status = "✅ VALID" if result.is_valid else "❌ INVALID"
                print(f"🔍 Validation Result for handler '{args.handler}': {status}")
                
                for error in result.errors + result.schema_errors:
                    print(f"  ❌ ERROR: {error}")
                for warning in result.warnings:
                    print(f"  ⚠️  WARNING: {warning}")
            
            return 0 if result.is_valid else 1
            
        else:
            parser.error("Must specify one of: --validate-all, --file, or --handler")
            
    except Exception as e:
        logger.error(f"Intent validation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
