"""
Builtin Plugin Package - Plugin discovery via entry-points

Builtin plugins are now discovered dynamically via entry-points defined in pyproject.toml.
This module provides the base classes and utilities for builtin plugins.

Entry-points catalog in pyproject.toml:
[project.entry-points."irene.plugins.builtin"]
# Builtin plugins converted to intent handlers in Phase 3:
# - RandomPlugin → RandomIntentHandler (random_handler.py)  
# - AsyncServiceDemoPlugin → SystemServiceIntentHandler (system_service_handler.py)

The hardcoded plugin module lists have been eliminated in favor of dynamic discovery.
"""

# NOTE: The get_builtin_plugins() function has been replaced by dynamic discovery
# via entry-points. Plugins are now discovered using:
# dynamic_loader.discover_providers("irene.plugins.builtin", enabled_plugins)

# For backward compatibility, preserve base imports
from ..base import PluginInterface

__all__ = ["PluginInterface"] 