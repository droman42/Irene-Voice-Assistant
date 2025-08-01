"""
Input Abstraction Layer - Multiple input source support

Provides abstraction for different input sources: microphone, web, CLI, etc.
"""

from .base import InputManager
from .cli import CLIInput

__all__ = [
    "InputManager",
    "CLIInput"
] 