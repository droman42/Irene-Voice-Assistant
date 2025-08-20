"""
Configuration Manager - Loading and saving configurations

Handles configuration file loading, saving, validation, and management
with support for multiple formats (TOML, JSON), environment variables,
hot-reload, and automatic default generation.

Requires: pydantic>=2.0.0, tomli-w>=1.0.0
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional, Union, Any, Callable

import tomllib

import tomli_w  # type: ignore
from pydantic import ValidationError  # type: ignore

from .models import (
    CoreConfig, SystemConfig, InputConfig, ComponentConfig, AssetConfig, WorkflowConfig,
    TTSConfig, AudioConfig, ASRConfig, LLMConfig, VoiceTriggerConfig, NLUConfig, 
    TextProcessorConfig, IntentSystemConfig,
    create_default_config, create_config_from_profile, EnvironmentVariableResolver
)
from .migration import migrate_config, ConfigurationCompatibilityChecker

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
        """Create V14 TOML content with clean architecture and comprehensive documentation"""
        
        # Generate V14 TOML content with clean architecture
        content = f"""# ============================================================
# IRENE VOICE ASSISTANT v{config.version} - CLEAN ARCHITECTURE
# ============================================================

name = "{config.name}"
version = "{config.version}"
debug = {str(config.debug).lower()}
log_level = "{config.log_level.value}"

# ============================================================
# SYSTEM CAPABILITIES - Hardware & Services
# ============================================================
[system]
microphone_enabled = {str(config.system.microphone_enabled).lower()}      # Hardware capability
audio_playback_enabled = {str(config.system.audio_playback_enabled).lower()}  # Hardware capability
web_api_enabled = {str(config.system.web_api_enabled).lower()}         # Service capability
web_port = {config.system.web_port}
metrics_enabled = {str(config.system.metrics_enabled).lower()}
metrics_port = {config.system.metrics_port}

# ============================================================
# INPUT SOURCES - Data Entry Points
# ============================================================
[inputs]
microphone = {str(config.inputs.microphone).lower()}              # Microphone input source
web = {str(config.inputs.web).lower()}                     # Web interface input
cli = {str(config.inputs.cli).lower()}                     # Command line input
default_input = "{config.inputs.default_input}"

# Microphone Input Configuration
[inputs.microphone_config]
enabled = {str(config.inputs.microphone_config.enabled).lower()}
# device_id = null   # Uncomment and set to specify audio device (null = default device)
sample_rate = {config.inputs.microphone_config.sample_rate}      # Audio sample rate (Hz)
channels = {config.inputs.microphone_config.channels}            # 1 = mono, 2 = stereo
chunk_size = {config.inputs.microphone_config.chunk_size}        # Audio buffer size

# Web Input Configuration
[inputs.web_config]
enabled = {str(config.inputs.web_config.enabled).lower()}
websocket_enabled = {str(config.inputs.web_config.websocket_enabled).lower()}
rest_api_enabled = {str(config.inputs.web_config.rest_api_enabled).lower()}

# CLI Input Configuration
[inputs.cli_config]
enabled = {str(config.inputs.cli_config.enabled).lower()}
prompt_prefix = "{config.inputs.cli_config.prompt_prefix}"
history_enabled = {str(config.inputs.cli_config.history_enabled).lower()}

# ============================================================
# COMPONENT CONFIGURATIONS - Provider Management
# ============================================================"""

        # Add component-specific configurations
        # Generate all component sections, using ComponentConfig booleans for enabled status
        content += self._generate_tts_config_section(config.tts, config.components.tts)
        content += self._generate_audio_config_section(config.audio, config.components.audio)
        content += self._generate_asr_config_section(config.asr, config.components.asr)
        content += self._generate_llm_config_section(config.llm, config.components.llm)
        content += self._generate_voice_trigger_config_section(config.voice_trigger, config.components.voice_trigger)
        content += self._generate_nlu_config_section(config.nlu, config.components.nlu)
        content += self._generate_text_processor_config_section(config.text_processor, config.components.text_processor)
            
        # Add workflows section
        content += f"""

# ============================================================
# WORKFLOWS - Processing Pipelines
# ============================================================
[workflows]
enabled = {str(config.workflows.enabled)}
default = "{config.workflows.default}"

# ============================================================
# ASSET MANAGEMENT - Environment-Driven
# ============================================================
[assets]
auto_create_dirs = {str(config.assets.auto_create_dirs).lower()}
# Paths use environment variable defaults:
# IRENE_ASSETS_ROOT (default: ~/.cache/irene)

# Language and locale
language = "{config.language}"
"""
        
        if config.timezone:
            content += f'timezone = "{config.timezone}"\n'
        
        # Runtime settings
        content += f"""
# Runtime settings
max_concurrent_commands = {config.max_concurrent_commands}
command_timeout_seconds = {config.command_timeout_seconds}
context_timeout_minutes = {config.context_timeout_minutes}
"""
        
        return content
    
    def _generate_tts_config_section(self, tts_config, enabled: bool) -> str:
        """Generate TTS component configuration section"""
        return f"""
[tts]
enabled = {str(enabled).lower()}
default_provider = "{tts_config.default_provider}"
fallback_providers = {str(tts_config.fallback_providers)}

{self._generate_provider_sections("tts.providers", tts_config.providers)}"""

    def _generate_audio_config_section(self, audio_config, enabled: bool) -> str:
        """Generate Audio component configuration section"""
        return f"""
[audio]
enabled = {str(enabled).lower()}
default_provider = "{audio_config.default_provider}"
fallback_providers = {str(audio_config.fallback_providers)}
concurrent_playback = {str(audio_config.concurrent_playback).lower()}

{self._generate_provider_sections("audio.providers", audio_config.providers)}"""

    def _generate_asr_config_section(self, asr_config, enabled: bool) -> str:
        """Generate ASR component configuration section"""
        return f"""
[asr]
enabled = {str(enabled).lower()}
default_provider = "{asr_config.default_provider}"
fallback_providers = {str(asr_config.fallback_providers)}

{self._generate_provider_sections("asr.providers", asr_config.providers)}"""

    def _generate_llm_config_section(self, llm_config, enabled: bool) -> str:
        """Generate LLM component configuration section"""
        return f"""
[llm]
enabled = {str(enabled).lower()}
default_provider = "{llm_config.default_provider}"
fallback_providers = {str(llm_config.fallback_providers)}

{self._generate_provider_sections("llm.providers", llm_config.providers)}"""

    def _generate_voice_trigger_config_section(self, vt_config, enabled: bool) -> str:
        """Generate Voice Trigger component configuration section"""
        return f"""
[voice_trigger]
enabled = {str(enabled).lower()}
default_provider = "{vt_config.default_provider}"
wake_words = {str(vt_config.wake_words)}
confidence_threshold = {vt_config.confidence_threshold}
buffer_seconds = {vt_config.buffer_seconds}
timeout_seconds = {vt_config.timeout_seconds}

{self._generate_provider_sections("voice_trigger.providers", vt_config.providers)}"""

    def _generate_nlu_config_section(self, nlu_config, enabled: bool) -> str:
        """Generate NLU component configuration section"""
        return f"""
[nlu]
enabled = {str(enabled).lower()}
default_provider = "{nlu_config.default_provider}"
confidence_threshold = {nlu_config.confidence_threshold}
fallback_intent = "{nlu_config.fallback_intent}"
provider_cascade_order = {str(nlu_config.provider_cascade_order)}
max_cascade_attempts = {nlu_config.max_cascade_attempts}
cascade_timeout_ms = {nlu_config.cascade_timeout_ms}
cache_recognition_results = {str(nlu_config.cache_recognition_results).lower()}
cache_ttl_seconds = {nlu_config.cache_ttl_seconds}

{self._generate_provider_sections("nlu.providers", nlu_config.providers)}"""

    def _generate_text_processor_config_section(self, tp_config, enabled: bool) -> str:
        """Generate Text Processor component configuration section"""
        return f"""
[text_processor]
enabled = {str(enabled).lower()}
stages = {str(tp_config.stages)}

{self._generate_normalizer_sections("text_processor.normalizers", tp_config.normalizers)}"""

    def _generate_provider_sections(self, base_path: str, providers: dict) -> str:
        """Generate provider configuration sections"""
        sections = []
        for provider_name, provider_config in providers.items():
            section = f"[{base_path}.{provider_name}]"
            for key, value in provider_config.items():
                if isinstance(value, bool):
                    sections.append(f"{key} = {str(value).lower()}")
                elif isinstance(value, str):
                    sections.append(f'{key} = "{value}"')
                elif isinstance(value, (int, float)):
                    sections.append(f"{key} = {value}")
                elif isinstance(value, list):
                    sections.append(f"{key} = {str(value)}")
                else:
                    sections.append(f"{key} = {str(value)}")
            sections.append("")
        return "\n".join([section] + sections) if sections else ""

    def _generate_normalizer_sections(self, base_path: str, normalizers: dict) -> str:
        """Generate normalizer configuration sections"""
        sections = []
        for normalizer_name, normalizer_config in normalizers.items():
            section = f"[{base_path}.{normalizer_name}]"
            for key, value in normalizer_config.items():
                if isinstance(value, bool):
                    sections.append(f"{key} = {str(value).lower()}")
                elif isinstance(value, str):
                    sections.append(f'{key} = "{value}"')
                elif isinstance(value, (int, float)):
                    sections.append(f"{key} = {value}")
                elif isinstance(value, list):
                    sections.append(f"{key} = {str(value)}")
                else:
                    sections.append(f"{key} = {str(value)}")
            sections.append("")
        return "\n".join([section] + sections) if sections else ""
        
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
        """Convert dictionary to CoreConfig with validation and v13→v14 migration"""
        try:
            # Check if migration is needed
            if ConfigurationCompatibilityChecker.requires_migration(data):
                logger.info("Detected v13 configuration format, performing automatic migration to v14")
                config = await asyncio.to_thread(migrate_config, data)
                logger.info("Configuration migration completed successfully")
                return config
            
            # Resolve environment variables if needed (enablement-aware)
            resolved_data = EnvironmentVariableResolver.substitute_env_vars(data)
            
            # Use getattr to work around type checker limitations with Pydantic v2
            model_validate = getattr(CoreConfig, 'model_validate', None)
            if model_validate:
                return model_validate(resolved_data)
            else:
                raise RuntimeError("CoreConfig.model_validate not available")
        except ValidationError as e:
            raise ConfigValidationError(f"Configuration validation failed: {e}")
        except Exception as e:
            raise ConfigValidationError(f"Configuration processing failed: {e}")
        
    def _config_to_dict(self, config: CoreConfig) -> dict[str, Any]:
        """Convert CoreConfig to dictionary"""
        # Use getattr to work around type checker limitations with Pydantic v2
        model_dump = getattr(config, 'model_dump', None)
        if model_dump:
            return model_dump()
        else:
            raise RuntimeError("CoreConfig.model_dump not available") 