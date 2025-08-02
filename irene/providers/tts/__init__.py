"""
TTS Providers - Text-to-Speech implementation modules

This package contains TTS provider implementations managed by UniversalTTSPlugin.
Each provider implements the TTSProvider abstract base class defined in base.py.

Available Providers:
- ConsoleTTSProvider: Console-based text output for testing
- PyttsTTSProvider: Cross-platform TTS using pyttsx3
- SileroV3TTSProvider: Neural TTS using Silero v3 models
- SileroV4TTSProvider: Neural TTS using Silero v4 models
- VoskTTSProvider: TTS functionality from Vosk backend
- ElevenLabsTTSProvider: High-quality neural TTS using ElevenLabs API (Phase 4)
"""

from .base import TTSProvider
from .console import ConsoleTTSProvider
from .pyttsx import PyttsTTSProvider
from .silero_v3 import SileroV3TTSProvider
from .silero_v4 import SileroV4TTSProvider
from .vosk import VoskTTSProvider
from .elevenlabs import ElevenLabsTTSProvider  # Phase 4 addition

__all__ = [
    "TTSProvider",
    "ConsoleTTSProvider",
    "PyttsTTSProvider", 
    "SileroV3TTSProvider",
    "SileroV4TTSProvider",
    "VoskTTSProvider",
    "ElevenLabsTTSProvider"  # Phase 4 addition
] 