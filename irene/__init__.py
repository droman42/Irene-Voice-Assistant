"""
Irene Voice Assistant v13 - Modern Async Architecture

A modular, async-first voice assistant framework with optional audio components.
"""

__version__ = "13.0.0-dev"
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