"""
Configuration Models - Pydantic models for type-safe configuration

Defines the configuration structure for the entire Irene system
with validation and schema support.
"""

from typing import Optional, Any
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ComponentConfig:
    """Configuration for optional components"""
    microphone: bool = False
    tts: bool = False
    audio_output: bool = False
    web_api: bool = True
    
    # Component-specific settings
    microphone_device: Optional[str] = None
    tts_voice: Optional[str] = None
    audio_device: Optional[str] = None
    web_port: int = 8000


@dataclass
class PluginConfig:
    """Plugin system configuration"""
    plugin_directories: list[Path] = field(default_factory=lambda: [Path("./plugins")])
    enabled_plugins: list[str] = field(default_factory=list)
    disabled_plugins: list[str] = field(default_factory=list)
    plugin_settings: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class SecurityConfig:
    """Security and access control configuration"""
    enable_authentication: bool = False
    api_keys: list[str] = field(default_factory=list)
    allowed_hosts: list[str] = field(default_factory=lambda: ["localhost", "127.0.0.1"])
    cors_origins: list[str] = field(default_factory=lambda: ["*"])


@dataclass
class CoreConfig:
    """Main configuration for the Irene core system"""
    # Basic settings
    name: str = "Irene"
    version: str = "13.0.0"
    debug: bool = False
    log_level: LogLevel = LogLevel.INFO
    
    # Component configuration
    components: ComponentConfig = field(default_factory=ComponentConfig)
    
    # Plugin configuration  
    plugins: PluginConfig = field(default_factory=PluginConfig)
    
    # Security configuration
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # System paths
    data_directory: Path = Path("./data")
    log_directory: Path = Path("./logs")
    cache_directory: Path = Path("./cache")
    
    # Runtime settings
    max_concurrent_commands: int = 10
    command_timeout_seconds: float = 30.0
    context_timeout_minutes: int = 30
    
    # Language and locale
    language: str = "en-US"
    timezone: Optional[str] = None
    
    # Advanced settings
    enable_metrics: bool = False
    metrics_port: int = 9090
    enable_profiling: bool = False


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