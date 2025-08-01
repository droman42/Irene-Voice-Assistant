"""
Plugin Interfaces - Interface definitions for all plugin types

This module defines the contracts that plugins must implement to integrate
with the Irene v13 async architecture.
"""

from .plugin import PluginInterface, PluginManager
from .command import CommandPlugin  
from .tts import TTSPlugin
from .audio import AudioPlugin
from .input import InputPlugin

__all__ = [
    "PluginInterface",
    "PluginManager", 
    "CommandPlugin",
    "TTSPlugin",
    "AudioPlugin", 
    "InputPlugin"
] 