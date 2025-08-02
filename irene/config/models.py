"""
Configuration Models - Pydantic models for type-safe configuration

Defines the configuration structure for the entire Irene system
with validation, schema support, and environment variable integration.

Requires: pydantic>=2.0.0, pydantic-settings>=2.0.0
"""

import os
from typing import Optional, Any, Dict, List
from pathlib import Path
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


def _get_default_builtin_plugins() -> dict[str, bool]:
    """Get default builtin plugin configuration dynamically"""
    try:
        # Use direct import but extract metadata like the registry does
        from ..plugins.builtin import get_builtin_plugins
        builtin_plugins = get_builtin_plugins()
        
        defaults = {}
        for plugin_name, plugin_class in builtin_plugins.items():
            try:
                # Extract metadata the same way PluginRegistry does
                temp_instance = plugin_class()
                defaults[plugin_name] = getattr(temp_instance, 'enabled_by_default', False)
            except Exception:
                # Safe fallback if plugin can't be instantiated
                defaults[plugin_name] = False
                
        return defaults
        
    except Exception:
        # Fallback to minimal safe defaults if anything fails
        return {
            "CoreCommandsPlugin": True,
            "GreetingsPlugin": True,
            "DateTimePlugin": True,
            "RandomPlugin": True,
            "AsyncTimerPlugin": True,
            # Universal plugins (Phase 1 & 2)
            "UniversalTTSPlugin": True,
            "UniversalAudioPlugin": True,
            # Legacy TTS plugins (backward compatibility - disabled by default in favor of universal)
            "ConsoleTTSPlugin": False,
            "PyttsTTSPlugin": False,
            "SileroV3TTSPlugin": False,
            "SileroV4TTSPlugin": False,
            "VoskTTSPlugin": False,
            # Legacy Audio plugins (Phase 2 - disabled in favor of universal)
            "ConsoleAudioPlugin": False,
            "SoundDeviceAudioPlugin": False,
            "AudioPlayerAudioPlugin": False,
            "AplayAudioPlugin": False,
            "SimpleAudioPlugin": False,
        }


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ComponentConfig(BaseModel):
    """Configuration for optional components"""
    microphone: bool = Field(default=False, description="Enable microphone input")
    tts: bool = Field(default=False, description="Enable TTS output")
    audio_output: bool = Field(default=False, description="Enable audio playback")
    web_api: bool = Field(default=True, description="Enable web API server")
    
    # Component-specific settings
    microphone_device: Optional[str] = Field(default=None, description="Microphone device ID")
    tts_voice: Optional[str] = Field(default=None, description="TTS voice name")
    audio_device: Optional[str] = Field(default=None, description="Audio output device ID")
    web_port: int = Field(default=8000, ge=1, le=65535, description="Web API server port")
    
    @field_validator('web_port')
    @classmethod
    def validate_web_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError('Web port must be between 1 and 65535')
        return v


class UniversalTTSConfig(BaseModel):
    """Universal TTS plugin configuration"""
    enabled: bool = Field(default=True, description="Enable Universal TTS plugin")
    default_provider: str = Field(default="console", description="Default TTS provider")
    fallback_providers: list[str] = Field(
        default_factory=lambda: ["console"],
        description="Fallback providers in order of preference"
    )
    providers: dict[str, dict[str, Any]] = Field(
        default_factory=lambda: {
            "console": {
                "enabled": True,
                "color_output": True,
                "timing_simulation": False
            }
        },
        description="Provider-specific configurations"
    )


class UniversalAudioConfig(BaseModel):
    """Universal Audio plugin configuration"""
    enabled: bool = Field(default=True, description="Enable Universal Audio plugin")
    default_provider: str = Field(default="console", description="Default audio provider")
    fallback_providers: list[str] = Field(
        default_factory=lambda: ["console"],
        description="Fallback providers in order of preference"
    )
    concurrent_playback: bool = Field(default=False, description="Allow concurrent audio playback")
    providers: dict[str, dict[str, Any]] = Field(
        default_factory=lambda: {
            "console": {
                "enabled": True,
                "color_output": True,
                "timing_simulation": False
            },
            "sounddevice": {
                "enabled": False,
                "device_id": -1,
                "sample_rate": 44100,
                "channels": 2,
                "buffer_size": 1024
            },
            "audioplayer": {
                "enabled": False,
                "volume": 0.8,
                "fade_in": False,
                "fade_out": True
            },
            "aplay": {
                "enabled": False,
                "device": "default",
                "volume": 1.0
            },
            "simpleaudio": {
                "enabled": False,
                "volume": 1.0
            }
        },
        description="Provider-specific configurations"
    )


# Phase 4 configuration classes
class UniversalASRConfig(BaseModel):
    """Universal ASR plugin configuration"""
    enabled: bool = Field(default=True, description="Enable Universal ASR plugin")
    default_provider: str = Field(default="vosk", description="Default ASR provider")
    default_language: str = Field(default="ru", description="Default recognition language")
    confidence_threshold: float = Field(default=0.7, description="Minimum confidence threshold")
    providers: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "vosk": {
                "enabled": True,
                "model_paths": {"ru": "./models/vosk-model-ru-0.22", "en": "./models/vosk-model-en-us-0.22"},
                "sample_rate": 16000,
                "confidence_threshold": 0.7
            },
            "whisper": {
                "enabled": False,
                "model_size": "base",
                "device": "cpu",
                "download_root": "~/.cache/irene/whisper"
            },
            "google_cloud": {
                "enabled": False,
                "credentials_path": "path/to/credentials.json",
                "project_id": "your-project-id",
                "default_language": "ru-RU"
            }
        },
        description="ASR provider configurations"
    )


class UniversalLLMConfig(BaseModel):
    """Universal LLM plugin configuration"""
    enabled: bool = Field(default=True, description="Enable Universal LLM plugin")
    default_provider: str = Field(default="openai", description="Default LLM provider")
    default_task: str = Field(default="improve_speech_recognition", description="Default enhancement task")
    providers: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "openai": {
                "enabled": True,
                "api_key_env": "OPENAI_API_KEY",
                "default_model": "gpt-4",
                "max_tokens": 150,
                "temperature": 0.3
            },
            "vsegpt": {
                "enabled": False,
                "api_key_env": "VSEGPT_API_KEY",
                "default_model": "openai/gpt-4o-mini",
                "max_tokens": 150,
                "temperature": 0.3
            },
            "anthropic": {
                "enabled": False,
                "api_key_env": "ANTHROPIC_API_KEY",
                "default_model": "claude-3-haiku-20240307",
                "max_tokens": 150
            }
        },
        description="LLM provider configurations"
    )


class TextProcessingConfig(BaseModel):
    """Text processing pipeline configuration"""
    enabled: bool = Field(default=True, description="Enable text processing pipeline")
    stages: List[str] = Field(
        default_factory=lambda: ["asr_output", "tts_input", "command_input", "general"],
        description="Processing stages"
    )
    normalizers: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "numbers": {
                "enabled": True,
                "stages": ["asr_output", "general", "tts_input"]
            },
            "prepare": {
                "enabled": True,
                "stages": ["tts_input", "general"],
                "latin_to_cyrillic": True,
                "symbol_replacement": True
            },
            "runorm": {
                "enabled": True,
                "stages": ["tts_input"],
                "model_size": "small",
                "device": "cpu"
            }
        },
        description="Text normalizer configurations"
    )


class PluginConfig(BaseModel):
    """Plugin system configuration"""
    plugin_directories: list[Path] = Field(
        default_factory=lambda: [Path("./plugins")],
        description="Directories to scan for plugins"
    )
    enabled_plugins: list[str] = Field(
        default_factory=list,
        description="List of explicitly enabled plugins"
    )
    disabled_plugins: list[str] = Field(
        default_factory=list,
        description="List of explicitly disabled plugins"
    )
    builtin_plugins: dict[str, bool] = Field(
        default_factory=_get_default_builtin_plugins,
        description="Built-in plugin enable/disable configuration"
    )
    plugin_settings: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Plugin-specific settings"
    )
    auto_discover: bool = Field(
        default=True,
        description="Automatically discover plugins in plugin directories"
    )
    
    # Universal plugin configurations
    universal_tts: UniversalTTSConfig = Field(
        default_factory=UniversalTTSConfig,
        description="Universal TTS plugin configuration"
    )
    universal_audio: UniversalAudioConfig = Field(
        default_factory=UniversalAudioConfig,
        description="Universal Audio plugin configuration"
    )
    # Phase 4 additions
    universal_asr: "UniversalASRConfig" = Field(
        default_factory=lambda: UniversalASRConfig(),
        description="Universal ASR plugin configuration"
    )
    universal_llm: "UniversalLLMConfig" = Field(
        default_factory=lambda: UniversalLLMConfig(),
        description="Universal LLM plugin configuration"
    )
    text_processing: "TextProcessingConfig" = Field(
        default_factory=lambda: TextProcessingConfig(),
        description="Text processing pipeline configuration"
    )
    
    @field_validator('plugin_directories')
    @classmethod
    def convert_paths(cls, v):
        if isinstance(v, list):
            return [Path(p) if not isinstance(p, Path) else p for p in v]
        return v


class SecurityConfig(BaseModel):
    """Security and access control configuration"""
    enable_authentication: bool = Field(default=False, description="Enable API authentication")
    api_keys: list[str] = Field(default_factory=list, description="Valid API keys")
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1"],
        description="Allowed host addresses"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="CORS allowed origins"
    )


class CoreConfig(BaseSettings):
    """Main configuration for the Irene core system with environment variable support"""
    
    # Basic settings
    name: str = Field(default="Irene", description="Assistant name")
    version: str = Field(default="13.0.0", description="Version")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    
    # Component configuration
    components: ComponentConfig = Field(default_factory=ComponentConfig)
    
    # Plugin configuration  
    plugins: PluginConfig = Field(default_factory=PluginConfig)
    
    # Security configuration
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    # System paths
    data_directory: Path = Field(default=Path("./data"), description="Data storage directory")
    log_directory: Path = Field(default=Path("./logs"), description="Log storage directory")
    cache_directory: Path = Field(default=Path("./cache"), description="Cache directory")
    
    # Runtime settings
    max_concurrent_commands: int = Field(default=10, ge=1, description="Maximum concurrent commands")
    command_timeout_seconds: float = Field(default=30.0, gt=0, description="Command timeout in seconds")
    context_timeout_minutes: int = Field(default=30, ge=1, description="Context timeout in minutes")
    
    # Language and locale
    language: str = Field(default="en-US", description="Primary language")
    timezone: Optional[str] = Field(default=None, description="Timezone (e.g., UTC, America/New_York)")
    
    # Advanced settings
    enable_metrics: bool = Field(default=False, description="Enable metrics collection")
    metrics_port: int = Field(default=9090, ge=1, le=65535, description="Metrics server port")
    enable_profiling: bool = Field(default=False, description="Enable performance profiling")
    
    model_config = {
        "env_prefix": "IRENE_",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
    }
        
    @field_validator('data_directory', 'log_directory', 'cache_directory')
    @classmethod
    def convert_path_fields(cls, v):
        return Path(v) if not isinstance(v, Path) else v
        
    @model_validator(mode='after')
    def validate_component_plugin_consistency(self):
        """Ensure component configuration is consistent with plugin availability"""
        components = self.components
        plugins = self.plugins
        
        if components and plugins:
            # Auto-enable audio plugins if audio_output is enabled
            if components.audio_output:
                plugins.builtin_plugins["ConsoleAudioPlugin"] = True
                
            # Auto-enable TTS plugins if tts is enabled
            if components.tts:
                plugins.builtin_plugins["ConsoleTTSPlugin"] = True
                
        return self


# Deployment profile presets
VOICE_PROFILE = ComponentConfig(
    microphone=True, 
    tts=True, 
    audio_output=True, 
    web_api=True
)

API_PROFILE = ComponentConfig(
    microphone=False, 
    tts=False, 
    audio_output=False, 
    web_api=True
)

HEADLESS_PROFILE = ComponentConfig(
    microphone=False, 
    tts=False, 
    audio_output=False, 
    web_api=False
)


def create_default_config() -> CoreConfig:
    """Create a default configuration with sensible defaults"""
    return CoreConfig()


def create_config_from_profile(profile_name: str) -> CoreConfig:
    """Create configuration from a deployment profile"""
    profiles = {
        "voice": VOICE_PROFILE,
        "api": API_PROFILE, 
        "headless": HEADLESS_PROFILE
    }
    
    if profile_name not in profiles:
        raise ValueError(f"Unknown profile: {profile_name}. Available: {list(profiles.keys())}")
        
    config = CoreConfig()
    config.components = profiles[profile_name]
    return config 