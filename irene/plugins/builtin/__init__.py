"""
Built-in Plugins - Core functionality plugins

Contains essential plugins that provide core assistant functionality.
Replaces legacy v12 plugins with modern async v13 architecture.
"""

# Command plugins
from .core_commands import CoreCommandsPlugin
from .greetings_plugin import GreetingsPlugin
from .datetime_plugin import DateTimePlugin
from .random_plugin import RandomPlugin

# Timer plugins
from .timer_plugin import AsyncTimerPlugin

# TTS plugins
from .console_tts_plugin import ConsoleTTSPlugin
from .pyttsx_tts_plugin import PyttsTTSPlugin

# Audio plugins
from .sounddevice_audio_plugin import SoundDeviceAudioPlugin
from .audioplayer_audio_plugin import AudioPlayerAudioPlugin
from .aplay_audio_plugin import AplayAudioPlugin
from .simpleaudio_audio_plugin import SimpleAudioPlugin
from .console_audio_plugin import ConsoleAudioPlugin

# Service plugins
from .async_service_demo import AsyncServiceDemoPlugin

__all__ = [
    # Command plugins
    "CoreCommandsPlugin",
    "GreetingsPlugin",
    "DateTimePlugin", 
    "RandomPlugin",
    
    # Timer plugins
    "AsyncTimerPlugin",
    
    # TTS plugins
    "ConsoleTTSPlugin",
    "PyttsTTSPlugin",
    
    # Audio plugins
    "SoundDeviceAudioPlugin",
    "AudioPlayerAudioPlugin", 
    "AplayAudioPlugin",
    "SimpleAudioPlugin",
    "ConsoleAudioPlugin",
    
    # Service plugins
    "AsyncServiceDemoPlugin"
] 