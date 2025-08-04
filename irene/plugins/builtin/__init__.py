"""
Builtin Plugin Discovery - Direct import system for builtin plugins

Provides direct access to builtin plugin classes for the unified PluginRegistry system.
This eliminates hardcoding while maintaining simplicity for builtin plugins.
"""

import importlib
from typing import Type, Dict
from pathlib import Path

from ..base import PluginInterface


def get_builtin_plugins() -> Dict[str, Type[PluginInterface]]:
    """
    Get all builtin plugin classes through direct imports.
    
    This avoids filesystem scanning for builtin plugins while still
    allowing the unified PluginRegistry to extract metadata from
    plugin instances.
    """
    
    # Define plugin modules and their main plugin classes
    # Note: Universal plugins moved to components/, intent plugins moved to intents/handlers/
    plugin_modules = [
        ("random_plugin", "RandomPlugin"),               # Keep as true plugin
        ("async_service_demo", "AsyncServiceDemoPlugin"), # Keep as demo plugin
    ]
    
    plugins = {}
    
    for module_name, class_name in plugin_modules:
        try:
            # Import module
            module = importlib.import_module(f".{module_name}", package=__package__)
            
            # Get plugin class
            plugin_class = getattr(module, class_name)
            
            # Add to plugins dict using class name as key
            plugins[class_name] = plugin_class
            
        except (ImportError, AttributeError) as e:
            # Log warning but continue - optional plugins might not be available
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not load builtin plugin {module_name}.{class_name}: {e}")
            continue
    
    return plugins


# Backward compatibility for existing imports
__all__ = ["get_builtin_plugins"] 