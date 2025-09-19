"""
Irene Voice Assistant v15 - Modern Async Architecture

A modular, async-first voice assistant framework with optional audio components.
"""

from .__version__ import __version__, __version_info__, VERSION

__author__ = "Irene Voice Assistant Project"

# Core imports - always available
from .core.engine import AsyncVACore
from .config.models import CoreConfig, ComponentConfig

# Optional imports with graceful fallback
try:
    from .inputs.microphone import MicrophoneInput
    MICROPHONE_AVAILABLE = True
except ImportError:
    MICROPHONE_AVAILABLE = False

# TTS availability is now handled through component system
TTS_AVAILABLE = True  # Components handle their own availability

__all__ = [
    "AsyncVACore",
    "CoreConfig", 
    "ComponentConfig",
    "MICROPHONE_AVAILABLE",
    "TTS_AVAILABLE"
] 