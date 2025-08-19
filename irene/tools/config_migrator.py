#!/usr/bin/env python3
"""
Configuration Migration Tool - v13→v14 Migration Utility

This tool provides command-line and programmatic interfaces for migrating
v13 configuration files to the new v14 clean architecture.

Usage:
    python -m irene.tools.config_migrator --config-dir ./configs
    python -m irene.tools.config_migrator --single-file ./configs/voice.toml
    python -m irene.tools.config_migrator --backup-only ./configs
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

import tomllib

import tomli_w

from ..config.migration import (
    migrate_config, 
    create_migration_backup, 
    V13ToV14Migrator,
    ConfigurationCompatibilityChecker,
    ConfigurationMigrationError
)
from ..config.manager import ConfigManager


logger = logging.getLogger(__name__)


class ConfigMigrationTool:
    """Tool for migrating v13 configuration files to v14 structure"""
    
    def __init__(self, config_dir: Path, backup: bool = True, dry_run: bool = False):
        self.config_dir = Path(config_dir).resolve()
        self.backup = backup
        self.dry_run = dry_run
        self.migrator = V13ToV14Migrator()
        self.migration_results: List[Dict[str, Any]] = []
        
        # Ensure config directory exists
        if not self.config_dir.exists():
            raise FileNotFoundError(f"Configuration directory not found: {self.config_dir}")
    
    def discover_config_files(self) -> List[Path]:
        """Discover all TOML configuration files in the config directory"""
        config_files = []
        
        for toml_file in self.config_dir.glob("*.toml"):
            if toml_file.is_file():
                config_files.append(toml_file)
        
        # Sort for consistent processing order
        config_files.sort()
        
        logger.info(f"Discovered {len(config_files)} TOML files: {[f.name for f in config_files]}")
        return config_files
    
    def check_migration_needed(self, config_file: Path) -> bool:
        """Check if a configuration file needs migration"""
        try:
            with open(config_file, "rb") as f:
                config_data = tomllib.load(f)
            
            return ConfigurationCompatibilityChecker.requires_migration(config_data)
            
        except Exception as e:
            logger.warning(f"Failed to check migration status for {config_file.name}: {e}")
            return False
    
    def migrate_single_file(self, config_file: Path) -> Dict[str, Any]:
        """
        Migrate a single configuration file from v13 to v14
        
        Returns:
            Dict with migration result information
        """
        result = {
            "file": config_file.name,
            "path": str(config_file),
            "success": False,
            "backup_created": False,
            "backup_path": None,
            "migration_log": [],
            "error": None
        }
        
        try:
            logger.info(f"Processing {config_file.name}...")
            
            # Check if migration is needed
            if not self.check_migration_needed(config_file):
                logger.info(f"  ✓ {config_file.name} is already v14 format or unknown version, skipping")
                result["success"] = True
                result["migration_log"] = ["No migration needed - already v14 format"]
                return result
            
            # Create backup if enabled and not dry run
            if self.backup and not self.dry_run:
                backup_path = create_migration_backup(config_file)
                result["backup_created"] = True
                result["backup_path"] = str(backup_path)
                logger.info(f"  ✓ Created backup: {backup_path.name}")
            
            # Load and migrate configuration
            with open(config_file, "rb") as f:
                v13_config = tomllib.load(f)
            
            logger.info(f"  → Migrating v13 structure to v14...")
            v14_config = self.migrator.migrate(v13_config)
            
            # Generate new v14 TOML content
            config_manager = ConfigManager()
            v14_toml_content = config_manager._create_documented_toml(v14_config)
            
            if self.dry_run:
                logger.info(f"  ✓ Dry run - would write {len(v14_toml_content)} characters to {config_file.name}")
            else:
                # Write new v14 configuration
                config_file.write_text(v14_toml_content, encoding='utf-8')
                logger.info(f"  ✓ Successfully migrated {config_file.name} to v14 format")
            
            result["success"] = True
            result["migration_log"] = self.migrator.get_migration_log()
            
        except ConfigurationMigrationError as e:
            logger.error(f"  ✗ Migration failed for {config_file.name}: {e}")
            result["error"] = str(e)
        except Exception as e:
            logger.error(f"  ✗ Unexpected error migrating {config_file.name}: {e}")
            result["error"] = f"Unexpected error: {e}"
        
        return result
    
    def migrate_all_configs(self) -> Dict[str, Any]:
        """
        Migrate all configuration files in the config directory
        
        Returns:
            Summary of migration results
        """
        logger.info(f"Starting migration of configuration files in {self.config_dir}")
        if self.dry_run:
            logger.info("Running in DRY RUN mode - no files will be modified")
        
        config_files = self.discover_config_files()
        
        if not config_files:
            logger.warning("No TOML configuration files found")
            return {
                "total_files": 0,
                "migrated": 0,
                "skipped": 0,
                "failed": 0,
                "results": []
            }
        
        # Process each configuration file
        for config_file in config_files:
            result = self.migrate_single_file(config_file)
            self.migration_results.append(result)
        
        # Generate summary
        summary = self._generate_summary()
        self._log_summary(summary)
        
        return summary
    
    def migrate_specific_file(self, config_file: Path) -> Dict[str, Any]:
        """Migrate a specific configuration file"""
        logger.info(f"Migrating specific file: {config_file}")
        
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        result = self.migrate_single_file(config_file)
        self.migration_results = [result]
        
        summary = self._generate_summary()
        self._log_summary(summary)
        
        return summary
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate migration summary from results"""
        total = len(self.migration_results)
        migrated = sum(1 for r in self.migration_results if r["success"] and r.get("migration_log"))
        skipped = sum(1 for r in self.migration_results if r["success"] and not r.get("migration_log"))
        failed = sum(1 for r in self.migration_results if not r["success"])
        
        return {
            "total_files": total,
            "migrated": migrated,
            "skipped": skipped,
            "failed": failed,
            "results": self.migration_results.copy()
        }
    
    def _log_summary(self, summary: Dict[str, Any]) -> None:
        """Log migration summary"""
        logger.info("\n" + "="*60)
        logger.info("MIGRATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Total files processed: {summary['total_files']}")
        logger.info(f"Successfully migrated: {summary['migrated']}")
        logger.info(f"Already v14 (skipped): {summary['skipped']}")
        logger.info(f"Failed migrations: {summary['failed']}")
        
        if summary['failed'] > 0:
            logger.warning("\nFailed migrations:")
            for result in summary['results']:
                if not result['success']:
                    logger.warning(f"  ✗ {result['file']}: {result['error']}")
        
        if summary['migrated'] > 0:
            logger.info("\nSuccessful migrations:")
            for result in summary['results']:
                if result['success'] and result.get('migration_log'):
                    backup_info = f" (backup: {Path(result['backup_path']).name})" if result.get('backup_path') else ""
                    logger.info(f"  ✓ {result['file']}{backup_info}")


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(levelname)s: %(message)s',
        stream=sys.stdout
    )
    
    # Reduce noise from other libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Migrate Irene Voice Assistant configuration files from v13 to v14",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate all configs in ./configs directory
  python -m irene.tools.config_migrator --config-dir ./configs
  
  # Migrate specific file only
  python -m irene.tools.config_migrator --single-file ./configs/voice.toml
  
  # Dry run to see what would be changed
  python -m irene.tools.config_migrator --config-dir ./configs --dry-run
  
  # Migrate without creating backups
  python -m irene.tools.config_migrator --config-dir ./configs --no-backup
"""
    )
    
    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--config-dir", 
        type=Path,
        help="Directory containing configuration files to migrate"
    )
    input_group.add_argument(
        "--single-file", 
        type=Path,
        help="Single configuration file to migrate"
    )
    
    # Migration options
    parser.add_argument(
        "--no-backup", 
        action="store_true",
        help="Skip creating backup files (not recommended)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be changed without modifying files"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    try:
        if args.config_dir:
            # Migrate all configs in directory
            tool = ConfigMigrationTool(
                config_dir=args.config_dir,
                backup=not args.no_backup,
                dry_run=args.dry_run
            )
            summary = tool.migrate_all_configs()
            
        else:
            # Migrate single file
            tool = ConfigMigrationTool(
                config_dir=args.single_file.parent,
                backup=not args.no_backup,
                dry_run=args.dry_run
            )
            summary = tool.migrate_specific_file(args.single_file)
        
        # Exit with appropriate code
        if summary['failed'] > 0:
            logger.error(f"\nMigration completed with {summary['failed']} failures")
            sys.exit(1)
        else:
            logger.info(f"\nMigration completed successfully!")
            sys.exit(0)
            
    except KeyboardInterrupt:
        logger.warning("\nMigration cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Migration tool failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
