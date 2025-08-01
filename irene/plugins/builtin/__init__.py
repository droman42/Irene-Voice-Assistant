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
    plugin_modules = [
        ("core_commands", "CoreCommandsPlugin"),
        ("greetings_plugin", "GreetingsPlugin"), 
        ("datetime_plugin", "DateTimePlugin"),
        ("random_plugin", "RandomPlugin"),
        ("timer_plugin", "AsyncTimerPlugin"),
        ("console_tts_plugin", "ConsoleTTSPlugin"),
        ("pyttsx_tts_plugin", "PyttsTTSPlugin"),
        ("silero_v3_tts_plugin", "SileroV3TTSPlugin"),
        ("silero_v4_tts_plugin", "SileroV4TTSPlugin"),
        ("vosk_tts_plugin", "VoskTTSPlugin"),
        ("console_audio_plugin", "ConsoleAudioPlugin"),
        ("sounddevice_audio_plugin", "SoundDeviceAudioPlugin"),
        ("audioplayer_audio_plugin", "AudioPlayerAudioPlugin"),
        ("aplay_audio_plugin", "AplayAudioPlugin"),
        ("simpleaudio_audio_plugin", "SimpleAudioPlugin"),
        ("async_service_demo", "AsyncServiceDemoPlugin"),
    ]
    
    plugins = {}
    
    for module_name, class_name in plugin_modules:
        try:
            # Import the plugin module
            module = importlib.import_module(f".{module_name}", package=__name__)
            
            # Get the plugin class
            plugin_class = getattr(module, class_name, None)
            if plugin_class:
                plugins[class_name] = plugin_class
                
        except Exception as e:
            # Skip plugins that can't be imported (missing dependencies, etc.)
            print(f"Warning: Could not load builtin plugin {class_name}: {e}")
            continue
            
    return plugins


# Backward compatibility for existing imports
__all__ = ["get_builtin_plugins"] 