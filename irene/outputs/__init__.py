"""
Output Abstraction Layer - Multiple output target support

Provides abstraction for different output targets: TTS, text, web, etc.
"""

from .base import OutputManager
from .text import TextOutput

__all__ = [
    "OutputManager",
    "TextOutput"
] 