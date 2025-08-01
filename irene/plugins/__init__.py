"""
Irene Plugin System - Async plugin management and discovery

This module provides the async plugin management system that replaces
the legacy synchronous plugin architecture.
"""

from .manager import AsyncPluginManager
from .registry import PluginRegistry
from .base import BasePlugin

__all__ = [
    "AsyncPluginManager",
    "PluginRegistry", 
    "BasePlugin"
] 