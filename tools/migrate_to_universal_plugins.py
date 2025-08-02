#!/usr/bin/env python3
"""
Configuration Migration Tool for Universal Plugin Architecture

This tool migrates old plugin configurations to the new Universal Plugin + Provider
architecture introduced in the Irene Voice Assistant refactoring.

Usage:
    python tools/migrate_to_universal_plugins.py config.toml
    python tools/migrate_to_universal_plugins.py --directory ~/.config/irene/
    python tools/migrate_to_universal_plugins.py --help
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import toml

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ConfigMigrator:
    """Tool to migrate old plugin configs to new universal format"""
    
    def __init__(self, backup: bool = True, dry_run: bool = False):
        self.backup = backup
        self.dry_run = dry_run
        
        # Define mapping from old plugin names to new provider names
        self.tts_plugin_mapping = {
            "silero_v3_tts": "silero_v3",
            "silero_v4_tts": "silero_v4", 
            "pyttsx_tts": "pyttsx",
            "console_tts": "console",
            "vosk_tts": "vosk_tts",
            "elevenlabs_tts": "elevenlabs"
        }
        
        self.audio_plugin_mapping = {
            "sounddevice_audio": "sounddevice",
            "audioplayer_audio": "audioplayer",
            "aplay_audio": "aplay",
            "simpleaudio_audio": "simpleaudio",
            "console_audio": "console"
        }
        
        # List of old plugins to remove after migration
        self.plugins_to_remove = (
            list(self.tts_plugin_mapping.keys()) +
            list(self.audio_plugin_mapping.keys())
        )
    
    def migrate_config_file(self, config_path: Path) -> bool:
        """
        Migrate entire config file from old format to new universal format
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            True if migration was successful, False otherwise
        """
        try:
            if not config_path.exists():
                logger.error(f"Configuration file not found: {config_path}")
                return False
            
            logger.info(f"Migrating configuration file: {config_path}")
            
            # Load existing config
            config = toml.load(config_path)
            
            # Check if migration is needed
            if not self._needs_migration(config):
                logger.info("Configuration file is already in new format or no migration needed")
                return True
            
            # Create backup if requested
            if self.backup and not self.dry_run:
                backup_path = config_path.with_suffix(f"{config_path.suffix}.backup")
                shutil.copy2(config_path, backup_path)
                logger.info(f"Created backup: {backup_path}")
            
            # Perform migration
            migrated_config = self._migrate_config(config)
            
            if self.dry_run:
                logger.info("DRY RUN: Would save migrated configuration to disk")
                self._log_migration_summary(config, migrated_config)
                return True
            
            # Save migrated config
            with open(config_path, 'w', encoding='utf-8') as f:
                toml.dump(migrated_config, f)
            
            logger.info(f"Successfully migrated configuration file: {config_path}")
            self._log_migration_summary(config, migrated_config)
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate configuration file {config_path}: {e}")
            return False
    
    def migrate_directory(self, directory: Path) -> bool:
        """
        Migrate all configuration files in a directory
        
        Args:
            directory: Directory containing configuration files
            
        Returns:
            True if all migrations were successful, False otherwise
        """
        if not directory.exists():
            logger.error(f"Directory not found: {directory}")
            return False
        
        # Find all .toml and .ini configuration files
        config_files = list(directory.glob("*.toml")) + list(directory.glob("*.ini"))
        
        if not config_files:
            logger.warning(f"No configuration files found in: {directory}")
            return True
        
        logger.info(f"Found {len(config_files)} configuration files to migrate")
        
        success_count = 0
        for config_file in config_files:
            if self.migrate_config_file(config_file):
                success_count += 1
        
        logger.info(f"Successfully migrated {success_count}/{len(config_files)} files")
        return success_count == len(config_files)
    
    def _needs_migration(self, config: Dict[str, Any]) -> bool:
        """Check if configuration needs migration"""
        plugins_config = config.get("plugins", {})
        
        # Check for old plugin format
        has_old_plugins = any(
            plugin_name in plugins_config 
            for plugin_name in self.plugins_to_remove
        )
        
        # Check for missing universal plugins
        has_universal_tts = "universal_tts" in plugins_config
        has_universal_audio = "universal_audio" in plugins_config
        
        return has_old_plugins or not (has_universal_tts or has_universal_audio)
    
    def _migrate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual configuration migration"""
        migrated_config = config.copy()
        
        # Ensure plugins section exists
        if "plugins" not in migrated_config:
            migrated_config["plugins"] = {}
        
        plugins = migrated_config["plugins"]
        
        # Migrate TTS plugins
        tts_config = self._migrate_tts_plugins(plugins)
        if tts_config:
            plugins["universal_tts"] = tts_config
        
        # Migrate audio plugins
        audio_config = self._migrate_audio_plugins(plugins)
        if audio_config:
            plugins["universal_audio"] = audio_config
        
        # Remove old plugin configurations
        self._remove_old_plugin_configs(plugins)
        
        return migrated_config
    
    def _migrate_tts_plugins(self, plugins: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert old TTS plugin configs to universal format"""
        tts_config = {
            "enabled": True,
            "providers": {},
            "load_balancing": False,
            "auto_retry": True
        }
        
        enabled_providers = []
        
        for old_name, provider_name in self.tts_plugin_mapping.items():
            if old_name in plugins and plugins[old_name].get("enabled", False):
                # Copy provider config, excluding the 'enabled' field
                provider_config = plugins[old_name].copy()
                provider_config["enabled"] = True
                
                # Remove plugin-specific fields that don't belong to providers
                provider_config.pop("enabled", None)
                
                tts_config["providers"][provider_name] = provider_config
                enabled_providers.append(provider_name)
                
                logger.info(f"Migrated TTS plugin {old_name} -> universal_tts.providers.{provider_name}")
        
        # Set default provider and fallbacks
        if enabled_providers:
            # Prioritize certain providers for default
            priority_providers = ["silero_v3", "pyttsx", "console"]
            default_provider = None
            
            for preferred in priority_providers:
                if preferred in enabled_providers:
                    default_provider = preferred
                    break
            
            if not default_provider:
                default_provider = enabled_providers[0]
            
            tts_config["default_provider"] = default_provider
            
            # Set fallback providers (exclude default, max 2 fallbacks)
            fallbacks = [p for p in enabled_providers if p != default_provider][:2]
            if fallbacks:
                tts_config["fallback_providers"] = fallbacks
            
            return tts_config
        
        return None
    
    def _migrate_audio_plugins(self, plugins: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert old audio plugin configs to universal format"""
        audio_config = {
            "enabled": True,
            "providers": {},
            "concurrent_playback": False
        }
        
        enabled_providers = []
        
        for old_name, provider_name in self.audio_plugin_mapping.items():
            if old_name in plugins and plugins[old_name].get("enabled", False):
                # Copy provider config, excluding the 'enabled' field
                provider_config = plugins[old_name].copy()
                provider_config["enabled"] = True
                
                # Remove plugin-specific fields that don't belong to providers
                provider_config.pop("enabled", None)
                
                audio_config["providers"][provider_name] = provider_config
                enabled_providers.append(provider_name)
                
                logger.info(f"Migrated audio plugin {old_name} -> universal_audio.providers.{provider_name}")
        
        # Set default provider
        if enabled_providers:
            # Prioritize certain providers for default
            priority_providers = ["sounddevice", "audioplayer", "console"]
            default_provider = None
            
            for preferred in priority_providers:
                if preferred in enabled_providers:
                    default_provider = preferred
                    break
            
            if not default_provider:
                default_provider = enabled_providers[0]
            
            audio_config["default_provider"] = default_provider
            
            return audio_config
        
        return None
    
    def _remove_old_plugin_configs(self, plugins: Dict[str, Any]) -> None:
        """Remove old plugin configurations"""
        for plugin_name in self.plugins_to_remove:
            if plugin_name in plugins:
                del plugins[plugin_name]
                logger.info(f"Removed old plugin configuration: {plugin_name}")
    
    def _log_migration_summary(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> None:
        """Log a summary of the migration changes"""
        old_plugins = old_config.get("plugins", {})
        new_plugins = new_config.get("plugins", {})
        
        logger.info("=== Migration Summary ===")
        
        # TTS migration
        if "universal_tts" in new_plugins:
            tts_providers = list(new_plugins["universal_tts"]["providers"].keys())
            default_provider = new_plugins["universal_tts"].get("default_provider", "none")
            logger.info(f"TTS: {len(tts_providers)} providers -> default: {default_provider}")
            logger.info(f"TTS providers: {', '.join(tts_providers)}")
        
        # Audio migration
        if "universal_audio" in new_plugins:
            audio_providers = list(new_plugins["universal_audio"]["providers"].keys())
            default_provider = new_plugins["universal_audio"].get("default_provider", "none")
            logger.info(f"Audio: {len(audio_providers)} providers -> default: {default_provider}")
            logger.info(f"Audio providers: {', '.join(audio_providers)}")
        
        # Removed plugins
        removed_plugins = [name for name in self.plugins_to_remove if name in old_plugins]
        if removed_plugins:
            logger.info(f"Removed {len(removed_plugins)} legacy plugins: {', '.join(removed_plugins)}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Migrate Irene Voice Assistant plugin configurations to Universal Plugin architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate a single config file
  python migrate_to_universal_plugins.py config.toml
  
  # Migrate all configs in a directory
  python migrate_to_universal_plugins.py --directory ~/.config/irene/
  
  # Dry run (preview changes without modifying files)
  python migrate_to_universal_plugins.py --dry-run config.toml
  
  # Don't create backup files
  python migrate_to_universal_plugins.py --no-backup config.toml
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "config_file", 
        nargs='?',
        type=Path,
        help="Configuration file to migrate"
    )
    group.add_argument(
        "--directory", 
        type=Path,
        help="Directory containing configuration files to migrate"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create backup files before migration"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create migrator
    migrator = ConfigMigrator(
        backup=not args.no_backup,
        dry_run=args.dry_run
    )
    
    # Perform migration
    success = False
    if args.config_file:
        success = migrator.migrate_config_file(args.config_file)
    elif args.directory:
        success = migrator.migrate_directory(args.directory)
    
    if success:
        if args.dry_run:
            logger.info("Migration preview completed successfully")
        else:
            logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main() 