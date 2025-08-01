"""
Text Output Target - Console/text-only output

Provides simple text output to console for headless operation
and debugging.
"""

import sys
from .base import LegacyOutputTarget


class TextOutput(LegacyOutputTarget):
    """
    Simple text output to console.
    
    Suitable for headless operation, testing, and debugging.
    """
    
    def __init__(self, prefix: str = "IRENE: "):
        self.prefix = prefix
        self.output_type = "text"
        
    async def send(self, text: str) -> None:
        """Send text to console"""
        print(f"{self.prefix}{text}")
        
    async def send_error(self, error: str) -> None:
        """Send error to console"""
        print(f"ERROR: {error}", file=sys.stderr)
        
    def is_available(self) -> bool:
        """Text output is always available"""
        return True 