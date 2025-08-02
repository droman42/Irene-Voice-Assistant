"""
Text Output Target - Console/text-only output

Provides simple text output to console for headless operation
and debugging. Supports the modern Response-based interface.
"""

import sys
import logging
from typing import Dict, Any
from .base import OutputTarget, Response

logger = logging.getLogger(__name__)


class TextOutput(OutputTarget):
    """
    Modern text output to console using Response interface.
    
    Suitable for headless operation, testing, and debugging.
    Handles all response types with appropriate formatting.
    """
    
    def __init__(self, prefix: str = "IRENE: ", use_colors: bool = True):
        self.prefix = prefix
        self.use_colors = use_colors
        
        # Try to import colorama for colored output
        try:
            import colorama  # type: ignore
            colorama.init()
            self._colors_available = True
        except ImportError:
            self._colors_available = False
            
    def is_available(self) -> bool:
        """Text output is always available"""
        return True
        
    def get_output_type(self) -> str:
        """Get output type identifier"""
        return "text"
        
    def supports_response_type(self, response_type: str) -> bool:
        """Text output supports all response types"""
        return True
        
    def get_settings(self) -> Dict[str, Any]:
        """Get current text output settings"""
        return {
            "prefix": self.prefix,
            "use_colors": self.use_colors,
            "colors_available": self._colors_available
        }
        
    async def configure_output(self, **settings) -> None:
        """Configure text output settings"""
        if "prefix" in settings:
            self.prefix = settings["prefix"]
        if "use_colors" in settings:
            self.use_colors = settings["use_colors"]
            
    async def test_output(self) -> bool:
        """Test text output functionality"""
        try:
            test_response = Response("Text output test", response_type="test")
            await self.send(test_response)
            return True
        except Exception as e:
            logger.error(f"Text output test failed: {e}")
            return False
        
    async def send(self, response: Response) -> None:
        """Send Response object to console"""
        try:
            # Format the response based on type
            formatted_text = self._format_response(response)
            
            # Output to console
            if response.response_type == "error":
                print(formatted_text, file=sys.stderr)
            else:
                print(formatted_text)
                
            # Flush to ensure immediate output
            sys.stdout.flush()
            if response.response_type == "error":
                sys.stderr.flush()
                
        except Exception as e:
            logger.error(f"Error sending text output: {e}")
            # Fallback to basic output
            print(f"ERROR: {e}", file=sys.stderr)
            
    async def send_error(self, error: str) -> None:
        """Send error message to console"""
        error_response = Response(error, response_type="error")
        await self.send(error_response)
        
    def _format_response(self, response: Response) -> str:
        """Format response based on type and settings"""
        text = response.text
        
        # Add prefix for non-system messages
        if response.response_type not in ["system", "debug"]:
            text = f"{self.prefix}{text}"
            
        # Add color formatting if available and enabled
        if self.use_colors and self._colors_available:
            text = self._add_colors(text, response.response_type)
            
        # Add metadata if available and response type is debug
        if response.response_type == "debug" and response.metadata:
            metadata_str = ", ".join(f"{k}={v}" for k, v in response.metadata.items())
            text = f"{text} [{metadata_str}]"
            
        return text
        
    def _add_colors(self, text: str, response_type: str) -> str:
        """Add ANSI color codes based on response type"""
        try:
            import colorama  # type: ignore
            
            color_map = {
                "error": colorama.Fore.RED,
                "warning": colorama.Fore.YELLOW,
                "success": colorama.Fore.GREEN,
                "info": colorama.Fore.CYAN,
                "debug": colorama.Fore.MAGENTA,
                "tts": colorama.Fore.BLUE,
                "system": colorama.Fore.WHITE,
            }
            
            color = color_map.get(response_type, colorama.Fore.WHITE)
            return f"{color}{text}{colorama.Style.RESET_ALL}"
            
        except ImportError:
            # Fallback to no colors
            return text
            
    def get_color_status(self) -> Dict[str, bool]:
        """Get color support status"""
        return {
            "colors_enabled": self.use_colors,
            "colors_available": self._colors_available,
            "colorama_installed": self._colors_available
        } 