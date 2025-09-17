#!/usr/bin/env python3
"""
Batch Cross-Language Validation for All Donation Pairs

This script validates all donation handlers for cross-language consistency
between Russian and English versions. It identifies parameter mismatches,
missing methods, type inconsistencies, and other structural differences.
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Set
from dataclasses import asdict

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from irene.core.cross_language_validator import CrossLanguageValidator, ValidationReport, CompletenessReport
from irene.core.intent_asset_loader import IntentAssetLoader, AssetLoaderConfig


class BatchValidationReport:
    """Comprehensive batch validation report"""
    def __init__(self):
        self.validation_reports: Dict[str, ValidationReport] = {}
        self.completeness_reports: Dict[str, CompletenessReport] = {}
        self.summary = {
            'total_handlers': 0,
            'handlers_with_issues': 0,
            'handlers_consistent': 0,
            'total_parameter_issues': 0,
            'total_method_issues': 0,
            'critical_issues': [],
            'warnings': []
        }
        self.timestamp = time.time()

    def add_validation_report(self, handler_name: str, param_report: ValidationReport, completeness_report: CompletenessReport):
        """Add validation reports for a handler"""
        self.validation_reports[handler_name] = param_report
        self.completeness_reports[handler_name] = completeness_report
        
        # Update summary
        self.summary['total_handlers'] += 1
        
        has_issues = False
        
        # Check parameter consistency issues
        if not param_report.parameter_consistency:
            has_issues = True
            self.summary['total_parameter_issues'] += len(param_report.missing_parameters) + len(param_report.type_mismatches)
            
            if param_report.missing_parameters:
                self.summary['critical_issues'].append(f"{handler_name}: Missing parameters - {param_report.missing_parameters}")
            if param_report.type_mismatches:
                self.summary['critical_issues'].append(f"{handler_name}: Type mismatches - {param_report.type_mismatches}")
        
        # Check method completeness issues
        if not completeness_report.method_completeness:
            has_issues = True
            self.summary['total_method_issues'] += len(completeness_report.missing_methods) + len(completeness_report.extra_methods)
            
            if completeness_report.missing_methods:
                self.summary['critical_issues'].append(f"{handler_name}: Missing methods - {completeness_report.missing_methods}")
            if completeness_report.extra_methods:
                self.summary['critical_issues'].append(f"{handler_name}: Extra methods - {completeness_report.extra_methods}")
        
        # Update counters
        if has_issues:
            self.summary['handlers_with_issues'] += 1
        else:
            self.summary['handlers_consistent'] += 1
        
        # Add warnings
        if param_report.warnings:
            self.summary['warnings'].extend([f"{handler_name}: {w}" for w in param_report.warnings])
        if completeness_report.warnings:
            self.summary['warnings'].extend([f"{handler_name}: {w}" for w in completeness_report.warnings])

    def print_summary(self):
        """Print a summary of validation results"""
        print("=" * 80)
        print("BATCH CROSS-LANGUAGE VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Total Handlers Checked: {self.summary['total_handlers']}")
        print(f"Handlers with Issues: {self.summary['handlers_with_issues']}")
        print(f"Handlers Consistent: {self.summary['handlers_consistent']}")
        print(f"Total Parameter Issues: {self.summary['total_parameter_issues']}")
        print(f"Total Method Issues: {self.summary['total_method_issues']}")
        print()
        
        if self.summary['critical_issues']:
            print("CRITICAL ISSUES:")
            print("-" * 40)
            for issue in self.summary['critical_issues']:
                print(f"❌ {issue}")
            print()
        
        if self.summary['warnings']:
            print("WARNINGS:")
            print("-" * 40)
            for warning in self.summary['warnings']:
                print(f"⚠️  {warning}")
            print()
        
        print("=" * 80)

    def print_detailed_report(self):
        """Print detailed validation results for each handler"""
        print("\nDETAILED VALIDATION RESULTS")
        print("=" * 80)
        
        for handler_name in sorted(self.validation_reports.keys()):
            param_report = self.validation_reports[handler_name]
            completeness_report = self.completeness_reports[handler_name]
            
            print(f"\n📁 {handler_name}")
            print("-" * 60)
            print(f"Languages: {', '.join(param_report.languages_checked)}")
            
            # Parameter consistency
            if param_report.parameter_consistency:
                print("✅ Parameter consistency: PASS")
            else:
                print("❌ Parameter consistency: FAIL")
                if param_report.missing_parameters:
                    print(f"   Missing parameters: {param_report.missing_parameters}")
                if param_report.type_mismatches:
                    print(f"   Type mismatches: {param_report.type_mismatches}")
            
            # Method completeness
            if completeness_report.method_completeness:
                print("✅ Method completeness: PASS")
            else:
                print("❌ Method completeness: FAIL")
                if completeness_report.missing_methods:
                    print(f"   Missing methods: {completeness_report.missing_methods}")
                if completeness_report.extra_methods:
                    print(f"   Extra methods: {completeness_report.extra_methods}")
            
            # Method counts by language
            print(f"   Method counts: {completeness_report.method_counts_by_language}")

    def export_json_report(self, output_path: Path):
        """Export detailed report as JSON"""
        
        # Helper function to convert sets to lists for JSON serialization
        def make_json_serializable(obj):
            if isinstance(obj, set):
                return list(obj)
            elif isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_json_serializable(item) for item in obj]
            else:
                return obj
        
        report_data = {
            'summary': self.summary,
            'timestamp': self.timestamp,
            'validation_reports': {
                handler: make_json_serializable(asdict(report)) for handler, report in self.validation_reports.items()
            },
            'completeness_reports': {
                handler: make_json_serializable(asdict(report)) for handler, report in self.completeness_reports.items()
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Detailed JSON report exported to: {output_path}")


def discover_donation_handlers(assets_root: Path) -> List[str]:
    """Discover all donation handlers with both Russian and English versions"""
    donations_dir = assets_root / "donations"
    if not donations_dir.exists():
        raise FileNotFoundError(f"Donations directory not found: {donations_dir}")
    
    handlers_with_both_languages = []
    
    for handler_dir in donations_dir.iterdir():
        if handler_dir.is_dir():
            en_file = handler_dir / "en.json"
            ru_file = handler_dir / "ru.json"
            
            if en_file.exists() and ru_file.exists():
                handlers_with_both_languages.append(handler_dir.name)
            else:
                print(f"⚠️  Skipping {handler_dir.name}: Missing language files")
                if not en_file.exists():
                    print(f"   Missing: en.json")
                if not ru_file.exists():
                    print(f"   Missing: ru.json")
    
    return sorted(handlers_with_both_languages)


def main():
    """Run batch cross-language validation"""
    print("Starting Batch Cross-Language Validation...")
    print("=" * 80)
    
    # Setup paths
    project_root = Path(__file__).parent.parent
    assets_root = project_root / "assets"
    
    # Initialize validator
    asset_config = AssetLoaderConfig()
    asset_loader = IntentAssetLoader(assets_root, asset_config)
    validator = CrossLanguageValidator(assets_root, asset_loader)
    
    # Discover handlers
    print("Discovering donation handlers...")
    try:
        handlers = discover_donation_handlers(assets_root)
        print(f"Found {len(handlers)} handlers with both Russian and English versions:")
        for handler in handlers:
            print(f"  - {handler}")
        print()
    except Exception as e:
        print(f"❌ Error discovering handlers: {e}")
        return 1
    
    # Initialize batch report
    batch_report = BatchValidationReport()
    
    # Validate each handler
    print("Running cross-language validation...")
    for i, handler_name in enumerate(handlers, 1):
        print(f"[{i}/{len(handlers)}] Validating {handler_name}...")
        
        try:
            # Convert handler directory name to handler name for the validator
            # (remove "_handler" suffix if present)
            validator_handler_name = handler_name.replace("_handler", "")
            
            # Run validation
            param_report = validator.validate_parameter_consistency(validator_handler_name)
            completeness_report = validator.validate_method_completeness(validator_handler_name)
            
            # Add to batch report
            batch_report.add_validation_report(handler_name, param_report, completeness_report)
            
            # Quick status
            if param_report.parameter_consistency and completeness_report.method_completeness:
                print(f"  ✅ {handler_name}: PASS")
            else:
                print(f"  ❌ {handler_name}: ISSUES FOUND")
        
        except Exception as e:
            print(f"  ❌ {handler_name}: ERROR - {e}")
            batch_report.summary['warnings'].append(f"{handler_name}: Validation error - {e}")
    
    print()
    
    # Display results
    batch_report.print_summary()
    
    # Ask for detailed report
    try:
        show_details = input("Show detailed report? (y/N): ").strip().lower()
        if show_details in ('y', 'yes'):
            batch_report.print_detailed_report()
    except (KeyboardInterrupt, EOFError):
        pass
    
    # Export JSON report
    output_dir = project_root / "validation_reports"
    output_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    json_report_path = output_dir / f"cross_language_validation_{timestamp}.json"
    
    try:
        batch_report.export_json_report(json_report_path)
    except Exception as e:
        print(f"⚠️  Could not export JSON report: {e}")
    
    # Return exit code based on results
    if batch_report.summary['handlers_with_issues'] > 0:
        print(f"\n❌ Validation completed with {batch_report.summary['handlers_with_issues']} handlers having issues.")
        return 1
    else:
        print(f"\n✅ All {batch_report.summary['handlers_consistent']} handlers are consistent!")
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
