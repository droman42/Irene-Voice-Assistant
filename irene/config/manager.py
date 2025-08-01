"""
Configuration Manager - Loading and saving configurations

Handles configuration file loading, saving, validation, and management
with support for multiple formats (TOML, JSON).
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Union, Any
import dataclasses

try:
    import tomllib
    TOML_AVAILABLE = True
except ImportError:
    try:
        import tomli as tomllib
        TOML_AVAILABLE = True
    except ImportError:
        TOML_AVAILABLE = False

from .models import CoreConfig, ComponentConfig, PluginConfig, SecurityConfig

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Manages configuration loading, saving, and validation.
    
    Features:
    - TOML and JSON format support
    - Async file operations
    - Configuration validation
    - Default value handling
    - Environment variable overrides
    """
    
    def __init__(self):
        self._config_cache: dict[str, CoreConfig] = {}
        
    async def load_config(self, config_path: Path) -> CoreConfig:
        """
        Load configuration from file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Loaded CoreConfig instance
        """
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return CoreConfig()
            
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
                
            # Convert to CoreConfig
            config = self._dict_to_config(data)
            
            # Cache the config
            self._config_cache[str(config_path)] = config
            
            logger.info(f"Loaded configuration from: {config_path}")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            logger.info("Using default configuration")
            return CoreConfig()
            
    async def save_config(self, config: CoreConfig, config_path: Path) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: CoreConfig instance to save
            config_path: Path where to save the configuration
            
        Returns:
            True if saved successfully
        """
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
            
    def get_default_config(self) -> CoreConfig:
        """Get default configuration"""
        return CoreConfig()
        
    async def _parse_toml(self, content: str) -> dict[str, Any]:
        """Parse TOML content"""
        if not TOML_AVAILABLE:
            raise ImportError("TOML support not available. Install with: pip install tomli")
        return await asyncio.to_thread(tomllib.loads, content)
        
    async def _parse_json(self, content: str) -> dict[str, Any]:
        """Parse JSON content"""
        return await asyncio.to_thread(json.loads, content)
        
    async def _format_toml(self, data: dict[str, Any]) -> str:
        """Format data as TOML"""
        try:
            import tomli_w
            return await asyncio.to_thread(tomli_w.dumps, data)
        except ImportError:
            raise ImportError("TOML writing support not available. Install with: pip install tomli-w")
            
    async def _format_json(self, data: dict[str, Any]) -> str:
        """Format data as JSON"""
        return await asyncio.to_thread(json.dumps, data, indent=2)
        
    def _dict_to_config(self, data: dict[str, Any]) -> CoreConfig:
        """Convert dictionary to CoreConfig"""
        # Extract components section
        components_data = data.get('components', {})
        components = ComponentConfig(
            microphone=components_data.get('microphone', False),
            tts=components_data.get('tts', False),
            audio_output=components_data.get('audio_output', False),
            web_api=components_data.get('web_api', True),
            microphone_device=components_data.get('microphone_device'),
            tts_voice=components_data.get('tts_voice'),
            audio_device=components_data.get('audio_device'),
            web_port=components_data.get('web_port', 8000)
        )
        
        # Extract plugins section
        plugins_data = data.get('plugins', {})
        plugins = PluginConfig(
            plugin_directories=[Path(p) for p in plugins_data.get('plugin_directories', ['./plugins'])],
            enabled_plugins=plugins_data.get('enabled_plugins', []),
            disabled_plugins=plugins_data.get('disabled_plugins', []),
            plugin_settings=plugins_data.get('plugin_settings', {})
        )
        
        # Extract security section
        security_data = data.get('security', {})
        security = SecurityConfig(
            enable_authentication=security_data.get('enable_authentication', False),
            api_keys=security_data.get('api_keys', []),
            allowed_hosts=security_data.get('allowed_hosts', ['localhost', '127.0.0.1']),
            cors_origins=security_data.get('cors_origins', ['*'])
        )
        
        # Create CoreConfig
        return CoreConfig(
            name=data.get('name', 'Irene'),
            version=data.get('version', '13.0.0'),
            debug=data.get('debug', False),
            components=components,
            plugins=plugins,
            security=security,
            data_directory=Path(data.get('data_directory', './data')),
            log_directory=Path(data.get('log_directory', './logs')),
            cache_directory=Path(data.get('cache_directory', './cache')),
            language=data.get('language', 'en-US'),
            timezone=data.get('timezone')
        )
        
    def _config_to_dict(self, config: CoreConfig) -> dict[str, Any]:
        """Convert CoreConfig to dictionary"""
        return {
            'name': config.name,
            'version': config.version,
            'debug': config.debug,
            'log_level': config.log_level.value,
            'components': {
                'microphone': config.components.microphone,
                'tts': config.components.tts,
                'audio_output': config.components.audio_output,
                'web_api': config.components.web_api,
                'microphone_device': config.components.microphone_device,
                'tts_voice': config.components.tts_voice,
                'audio_device': config.components.audio_device,
                'web_port': config.components.web_port
            },
            'plugins': {
                'plugin_directories': [str(p) for p in config.plugins.plugin_directories],
                'enabled_plugins': config.plugins.enabled_plugins,
                'disabled_plugins': config.plugins.disabled_plugins,
                'plugin_settings': config.plugins.plugin_settings
            },
            'security': {
                'enable_authentication': config.security.enable_authentication,
                'api_keys': config.security.api_keys,
                'allowed_hosts': config.security.allowed_hosts,
                'cors_origins': config.security.cors_origins
            },
            'data_directory': str(config.data_directory),
            'log_directory': str(config.log_directory),
            'cache_directory': str(config.cache_directory),
            'language': config.language,
            'timezone': config.timezone
        } 