"""
Configuration resolution utilities for component-driven config discovery.
"""

from typing import Type, Optional, Any
from pydantic import BaseModel
from .models import CoreConfig

def extract_config_by_path(config: CoreConfig, path: str, config_class: Type[BaseModel]) -> Optional[BaseModel]:
    """
    Extract config from nested TOML structure using dot notation.
    
    Args:
        config: Root configuration object
        path: Dot-separated path (e.g., "plugins.universal_tts", "components.nlu", "intents")
        config_class: Expected Pydantic model class
        
    Returns:
        Config instance if found and valid, None otherwise
        
    Examples:
        - path="plugins.universal_tts" → config.plugins.universal_tts
        - path="components.nlu" → config.components.nlu  
        - path="intents" → config.intents
    """
    try:
        current = config
        for part in path.split('.'):
            current = getattr(current, part, None)
            if current is None:
                return None
        
        # Validate against expected config model
        if isinstance(current, config_class):
            return current
        elif isinstance(current, dict):
            # Try to construct from dict (for dynamic configs)
            return config_class(**current)
        else:
            # Invalid config type
            return None
            
    except (AttributeError, TypeError, ValueError) as e:
        # Config path not found or invalid
        return None

def is_component_enabled_by_name(component_name: str, config: CoreConfig) -> bool:
    """
    Check if a component is enabled using entry-point name.
    
    Args:
        component_name: Entry-point name (e.g., "tts", "voice_trigger", "nlu")
        config: Core configuration object
        
    Returns:
        True if component is enabled, False otherwise
    """
    # Essential components always enabled (required for core functionality)
    essential_components = ["intent_system", "nlu", "text_processor"]
    if component_name in essential_components:
        return True
    
    try:
        # Get component class from entry-points
        from ..utils.loader import dynamic_loader
        component_class = dynamic_loader.get_provider_class("irene.components", component_name)
        
        # Use component's own config resolution
        return component_class.is_enabled_in_config(config)
        
    except Exception:
        # Component not found or config resolution failed
        return False

def get_component_config_by_name(component_name: str, config: CoreConfig) -> Optional[BaseModel]:
    """
    Get component configuration using entry-point name.
    
    Args:
        component_name: Entry-point name
        config: Core configuration object
        
    Returns:
        Component config instance if found, None otherwise
    """
    try:
        from ..utils.loader import dynamic_loader
        component_class = dynamic_loader.get_provider_class("irene.components", component_name)
        
        config_class = component_class.get_config_class()
        config_path = component_class.get_config_path()
        
        return extract_config_by_path(config, config_path, config_class)
        
    except Exception:
        return None
