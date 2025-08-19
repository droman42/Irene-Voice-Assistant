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
    
    V14 Architecture: Direct mapping to components section:
    - "tts" → components.tts
    - "audio" → components.audio  
    - "asr" → components.asr
    - "llm" → components.llm
    - "nlu" → components.nlu
    - "text_processor" → components.text_processor
    - "intent_system" → components.intent_system
    - "voice_trigger" → components.voice_trigger
    
    Args:
        component_name: Entry-point name (e.g., "tts", "asr", "llm")
        config: Root configuration object
        
    Returns:
        True if component is enabled, False otherwise
    """
    
    # V14 Direct component mapping
    try:
        return getattr(config.components, component_name, False)
    except (AttributeError, TypeError):
        # Component config not found or malformed
        return False

def get_component_config_by_name(component_name: str, config: CoreConfig) -> Optional[BaseModel]:
    """
    Get component configuration using entry-point name.
    
    V14 Architecture: Direct access to component-specific configurations:
    - "tts" → config.tts
    - "audio" → config.audio
    - "asr" → config.asr
    - "llm" → config.llm
    - "nlu" → config.nlu
    - "text_processor" → config.text_processor
    - "intent_system" → config.intent_system
    - "voice_trigger" → config.voice_trigger
    
    Args:
        component_name: Entry-point name
        config: Core configuration object
        
    Returns:
        Component config instance if found, None otherwise
    """
    try:
        # V14 Direct config access
        return getattr(config, component_name, None)
    except (AttributeError, TypeError):
        return None
