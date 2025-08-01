"""
Configuration Manager - Loading and saving configurations

Handles configuration file loading, saving, validation, and management
with support for multiple formats (TOML, JSON), environment variables,
hot-reload, and automatic default generation.

Requires: pydantic>=2.0.0, tomli>=1.2.0, tomli-w>=1.0.0
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional, Union, Any, Callable

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

import tomli_w  # type: ignore
from pydantic import ValidationError  # type: ignore

from .models import (
    CoreConfig, ComponentConfig, PluginConfig, SecurityConfig, 
    create_default_config, create_config_from_profile  # type: ignore[attr-defined]
)

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    pass


class ConfigManager:
    """
    Manages configuration loading, saving, and validation.
    
    Features:
    - TOML and JSON format support
    - Async file operations
    - Configuration validation with Pydantic
    - Default value handling
    - Environment variable overrides
    - Hot-reload configuration changes
    - Automatic default config generation
    """
    
    def __init__(self):
        self._config_cache: dict[str, CoreConfig] = {}
        self._reload_callbacks: list[Callable[[CoreConfig], None]] = []
        self._file_watchers: dict[str, asyncio.Task] = {}
        
    async def load_config(self, config_path: Optional[Path] = None, create_default: bool = True) -> CoreConfig:
        """
        Load configuration from file with automatic default generation.
        
        Args:
            config_path: Path to configuration file (auto-detect if None)
            create_default: Create default config file if not found
            
        Returns:
            Loaded CoreConfig instance
        """
        # Auto-detect config file if not specified
        if config_path is None:
            config_path = self._find_config_file()
            
        # Check if config file exists
        if not config_path.exists():
            if create_default:
                logger.info(f"Config file not found at {config_path}, creating default configuration")
                default_config = await self._generate_default_config(config_path)
                return default_config
            else:
                logger.warning(f"Config file not found: {config_path}, using in-memory defaults")
                return self._load_from_environment()
            
        try:
            # Read file content
            content = await asyncio.to_thread(config_path.read_text, encoding='utf-8')
            
            # Parse based on file extension
            if config_path.suffix.lower() == '.toml':
                data = await self._parse_toml(content)
            elif config_path.suffix.lower() == '.json':
                data = await self._parse_json(content)
            else:
                raise ValueError(f"Unsupported config format: {config_path.suffix}")
                
            # Convert to CoreConfig with validation
            config = await self._dict_to_config_validated(data)
            
            # Apply environment variable overrides (Pydantic handles this automatically)
            
            # Cache the config
            self._config_cache[str(config_path)] = config
            
            logger.info(f"Loaded configuration from: {config_path}")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            if isinstance(e, ValidationError):
                logger.error(f"Configuration validation errors:\n{e}")
            logger.info("Using default configuration with environment overrides")
            return self._load_from_environment()
            
    async def save_config(self, config: CoreConfig, config_path: Optional[Path] = None) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: CoreConfig instance to save
            config_path: Path where to save the configuration (auto-detect if None)
            
        Returns:
            True if saved successfully
        """
        if config_path is None:
            config_path = self._find_config_file()
            
        try:
            # Convert config to dictionary
            data = self._config_to_dict(config)
            
            # Format based on file extension
            if config_path.suffix.lower() == '.toml':
                content = await self._format_toml(data)
            elif config_path.suffix.lower() == '.json':
                content = await self._format_json(data)
            else:
                raise ValueError(f"Unsupported config format: {config_path.suffix}")
                
            # Ensure directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            await asyncio.to_thread(config_path.write_text, content, encoding='utf-8')
            
            # Update cache
            self._config_cache[str(config_path)] = config
            
            logger.info(f"Saved configuration to: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config to {config_path}: {e}")
            return False
            
    async def generate_default_config_file(self, config_path: Optional[Path] = None, profile: str = "headless") -> Path:
        """
        Generate a default configuration file with documentation.
        
        Args:
            config_path: Where to save the config (default: ./config.toml)
            profile: Deployment profile to use as base
            
        Returns:
            Path to generated config file
        """
        if config_path is None:
            config_path = Path("./config.toml")
            
        # Create config from profile
        config = create_config_from_profile(profile)
        
        # Save with rich comments and documentation
        await self._save_documented_config(config, config_path)
        
        logger.info(f"Generated default configuration file: {config_path}")
        return config_path
        
    def start_hot_reload(self, config_path: Path, callback: Optional[Callable[[CoreConfig], None]] = None) -> None:
        """
        Start monitoring config file for changes and auto-reload.
        
        Args:
            config_path: Configuration file to monitor
            callback: Function to call when config reloads
        """
        if callback:
            self._reload_callbacks.append(callback)
            
        # Start file watcher
        watcher_task = asyncio.create_task(self._watch_config_file(config_path))
        self._file_watchers[str(config_path)] = watcher_task
        logger.info(f"Started hot-reload monitoring for: {config_path}")
        
    def stop_hot_reload(self, config_path: Optional[Path] = None) -> None:
        """Stop hot-reload monitoring"""
        if config_path is None:
            # Stop all watchers
            for path, task in self._file_watchers.items():
                task.cancel()
                logger.info(f"Stopped hot-reload monitoring for: {path}")
            self._file_watchers.clear()
        else:
            path_str = str(config_path)
            if path_str in self._file_watchers:
                self._file_watchers[path_str].cancel()
                del self._file_watchers[path_str]
                logger.info(f"Stopped hot-reload monitoring for: {config_path}")
                
    def add_reload_callback(self, callback: Callable[[CoreConfig], None]) -> None:
        """Add callback to be called when config reloads"""
        self._reload_callbacks.append(callback)
        
    def get_default_config(self) -> CoreConfig:
        """Get default configuration"""
        return create_default_config()
        
    def _find_config_file(self) -> Path:
        """Find configuration file in standard locations"""
        search_paths = [
            Path("./config.toml"),
            Path("./config.json"),
            Path("./irene.toml"),
            Path("./irene.json"),
            Path.home() / ".config" / "irene" / "config.toml",
            Path("/etc/irene/config.toml"),
        ]
        
        for path in search_paths:
            if path.exists():
                return path
                
        # Return default location for creation
        return Path("./config.toml")
        
    def _load_from_environment(self) -> CoreConfig:
        """Create configuration from environment variables only"""
        try:
            # Use Pydantic's environment loading
            return CoreConfig()
        except Exception as e:
            logger.error(f"Failed to load config from environment: {e}")
            return create_default_config()
            
    async def _generate_default_config(self, config_path: Path) -> CoreConfig:
        """Generate and save default configuration file"""
        config = create_default_config()
        await self.save_config(config, config_path)
        return config
        
    async def _save_documented_config(self, config: CoreConfig, config_path: Path) -> None:
        """Save configuration with rich documentation and comments"""
        if config_path.suffix.lower() != '.toml':
            # Fall back to regular save for non-TOML formats
            await self.save_config(config, config_path)
            return
            
        # Create documented TOML content
        toml_content = self._create_documented_toml(config)
        
        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write documented content
        await asyncio.to_thread(config_path.write_text, toml_content, encoding='utf-8')
        
    def _create_documented_toml(self, config: CoreConfig) -> str:
        """Create TOML content with documentation and comments"""
        
        # Get plugin metadata using direct extraction (simpler and more reliable)
        plugin_metadata = {}
        try:
            from ..plugins.builtin import get_builtin_plugins
            builtin_plugins_classes = get_builtin_plugins()
            
            for plugin_name, plugin_class in builtin_plugins_classes.items():
                try:
                    temp_instance = plugin_class()
                    plugin_metadata[plugin_name] = {
                        "description": temp_instance.description,
                        "dependencies": temp_instance.dependencies,
                        "optional_dependencies": temp_instance.optional_dependencies,
                        "category": getattr(temp_instance, 'category', 'unknown'),
                        "platforms": getattr(temp_instance, 'platforms', [])
                    }
                except Exception:
                    # Fallback for plugins that can't be instantiated
                    plugin_metadata[plugin_name] = {
                        "description": f"{plugin_name}",
                        "dependencies": [],
                        "optional_dependencies": [],
                        "category": "unknown",
                        "platforms": []
                    }
        except Exception:
            plugin_metadata = {}
        
        # Generate plugin sections dynamically
        plugin_sections = {}
        builtin_plugins = getattr(config.plugins, 'builtin_plugins', {})
        
        for plugin_name, enabled in builtin_plugins.items():
            metadata = plugin_metadata.get(plugin_name, {})
            description = metadata.get("description", plugin_name)
            dependencies = metadata.get("dependencies", []) + metadata.get("optional_dependencies", [])
            platforms = metadata.get("platforms", [])
            
            comment = f"# {description}"
            if dependencies:
                deps_str = ", ".join(dependencies)
                comment += f" (requires {deps_str})"
            if platforms:
                plat_str = ", ".join(platforms)
                comment += f" ({plat_str} only)"
                
            plugin_sections[plugin_name] = {
                'enabled': str(enabled).lower(),
                'comment': comment
            }
        
        # Generate TOML content
        content = """# Irene Voice Assistant v13 Configuration
# This file configures all aspects of the Irene voice assistant
# See: https://github.com/irene-voice-assistant/irene for documentation

# Basic assistant settings
name = "{name}"
version = "{version}"
debug = {debug}
log_level = "{log_level}"
language = "{language}"

# System directories
data_directory = "{data_directory}"
log_directory = "{log_directory}"
cache_directory = "{cache_directory}"

# Runtime settings
max_concurrent_commands = {max_concurrent_commands}
command_timeout_seconds = {command_timeout_seconds}
context_timeout_minutes = {context_timeout_minutes}

# Component configuration - Enable/disable major features
[components]
microphone = {components_microphone}      # Enable voice input
tts = {components_tts}                   # Enable text-to-speech
audio_output = {components_audio_output}  # Enable audio playback
web_api = {components_web_api}           # Enable web API server
web_port = {components_web_port}

# Plugin system configuration
[plugins]
auto_discover = {plugins_auto_discover}
plugin_directories = {plugins_plugin_directories}
enabled_plugins = {plugins_enabled_plugins}
disabled_plugins = {plugins_disabled_plugins}

# Built-in plugin configuration
[plugins.builtin_plugins]
""".format(
    name=config.name,
    version=config.version,
    debug=str(config.debug).lower(),
    log_level=config.log_level.value,
    language=config.language,
    data_directory=str(config.data_directory),
    log_directory=str(config.log_directory),
    cache_directory=str(config.cache_directory),
    max_concurrent_commands=config.max_concurrent_commands,
    command_timeout_seconds=config.command_timeout_seconds,
    context_timeout_minutes=config.context_timeout_minutes,
    components_microphone=str(config.components.microphone).lower(),
    components_tts=str(config.components.tts).lower(),
    components_audio_output=str(config.components.audio_output).lower(),
    components_web_api=str(config.components.web_api).lower(),
    components_web_port=config.components.web_port,
    plugins_auto_discover=str(getattr(config.plugins, 'auto_discover', True)).lower(),
    plugins_plugin_directories=str([str(p) for p in config.plugins.plugin_directories]),
    plugins_enabled_plugins=str(config.plugins.enabled_plugins),
    plugins_disabled_plugins=str(config.plugins.disabled_plugins),
)

        # Add plugin sections dynamically
        for plugin_name, plugin_info in plugin_sections.items():
            content += f"{plugin_info['comment']}\n"
            content += f"{plugin_name} = {plugin_info['enabled']}\n\n"
        
        # Add remaining sections
        content += f"""
# Security and access control
[security]
enable_authentication = {str(config.security.enable_authentication).lower()}
api_keys = {str(config.security.api_keys)}
allowed_hosts = {str(config.security.allowed_hosts)}
cors_origins = {str(config.security.cors_origins)}

# Advanced settings
enable_metrics = {str(config.enable_metrics).lower()}
metrics_port = {config.metrics_port}
enable_profiling = {str(config.enable_profiling).lower()}
"""
        return content
        
    async def _watch_config_file(self, config_path: Path) -> None:
        """Watch configuration file for changes and reload"""
        last_modified = None
        
        try:
            while True:
                if config_path.exists():
                    current_modified = config_path.stat().st_mtime
                    
                    if last_modified is not None and current_modified != last_modified:
                        logger.info(f"Configuration file changed, reloading: {config_path}")
                        try:
                            new_config = await self.load_config(config_path, create_default=False)
                            
                            # Call reload callbacks
                            for callback in self._reload_callbacks:
                                try:
                                    if asyncio.iscoroutinefunction(callback):
                                        await callback(new_config)
                                    else:
                                        callback(new_config)
                                except Exception as e:
                                    logger.error(f"Error in reload callback: {e}")
                                    
                        except Exception as e:
                            logger.error(f"Failed to reload configuration: {e}")
                            
                    last_modified = current_modified
                    
                await asyncio.sleep(1.0)  # Check every second
                
        except asyncio.CancelledError:
            logger.debug(f"Stopped watching config file: {config_path}")
            
    async def _parse_toml(self, content: str) -> dict[str, Any]:
        """Parse TOML content"""
        return await asyncio.to_thread(tomllib.loads, content)
        
    async def _parse_json(self, content: str) -> dict[str, Any]:
        """Parse JSON content"""
        return await asyncio.to_thread(json.loads, content)
        
    async def _format_toml(self, data: dict[str, Any]) -> str:
        """Format data as TOML"""
        return await asyncio.to_thread(tomli_w.dumps, data)
            
    async def _format_json(self, data: dict[str, Any]) -> str:
        """Format data as JSON"""
        return await asyncio.to_thread(json.dumps, data, indent=2)
        
    async def _dict_to_config_validated(self, data: dict[str, Any]) -> CoreConfig:
        """Convert dictionary to CoreConfig with validation"""
        try:
            # Use getattr to work around type checker limitations with Pydantic v2
            model_validate = getattr(CoreConfig, 'model_validate', None)
            if model_validate:
                return model_validate(data)
            else:
                raise RuntimeError("CoreConfig.model_validate not available")
        except ValidationError as e:
            raise ConfigValidationError(f"Configuration validation failed: {e}")
        
    def _config_to_dict(self, config: CoreConfig) -> dict[str, Any]:
        """Convert CoreConfig to dictionary"""
        # Use getattr to work around type checker limitations with Pydantic v2
        model_dump = getattr(config, 'model_dump', None)
        if model_dump:
            return model_dump()
        else:
            raise RuntimeError("CoreConfig.model_dump not available") 