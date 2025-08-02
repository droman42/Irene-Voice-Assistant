"""
Audio Providers - Audio playback implementation modules

This package contains audio provider implementations managed by UniversalAudioPlugin.

Available Providers:
- ConsoleAudioProvider: Console-based output for testing
- SoundDeviceAudioProvider: High-quality audio using sounddevice
- AudioPlayerAudioProvider: Cross-platform audio using audioplayer
- AplayAudioProvider: Linux ALSA audio using aplay
- SimpleAudioProvider: Simple audio playback using simpleaudio
"""

from .base import AudioProvider
from .console import ConsoleAudioProvider
from .sounddevice import SoundDeviceAudioProvider
from .audioplayer import AudioPlayerAudioProvider
from .aplay import AplayAudioProvider
from .simpleaudio import SimpleAudioProvider

__all__ = [
    "AudioProvider",
    "ConsoleAudioProvider", 
    "SoundDeviceAudioProvider",
    "AudioPlayerAudioProvider",
    "AplayAudioProvider",
    "SimpleAudioProvider"
] 