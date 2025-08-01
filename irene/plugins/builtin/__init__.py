"""
Built-in Plugins - Core functionality plugins

Contains essential plugins that provide core assistant functionality.
"""

from .core_commands import CoreCommandsPlugin
from .timer_plugin import AsyncTimerPlugin
from .async_service_demo import AsyncServiceDemoPlugin

__all__ = [
    "CoreCommandsPlugin",
    "AsyncTimerPlugin", 
    "AsyncServiceDemoPlugin"
] 