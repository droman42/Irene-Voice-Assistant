"""
Configuration Management - Pydantic-based configuration

Provides type-safe configuration management with validation
and schema support.
"""

from .models import CoreConfig, ComponentConfig
from .manager import ConfigManager

__all__ = [
    "CoreConfig",
    "ComponentConfig", 
    "ConfigManager"
] 