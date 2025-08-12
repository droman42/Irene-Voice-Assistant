"""
Irene Core Module - Async Engine and Core Components

This module contains the main AsyncVACore engine and core system components.
"""

from .engine import AsyncVACore
from .context import Context, ContextManager
from .timers import AsyncTimerManager
# CommandResult removed - use IntentResult instead
from .components import ComponentManager, ComponentNotAvailable, Component
from .metadata import EntryPointMetadata

__all__ = [
    "AsyncVACore",
    "Context",
    "ContextManager", 
    "AsyncTimerManager",


    "ComponentManager",
    "ComponentNotAvailable",
    "Component",
    "EntryPointMetadata"
] 