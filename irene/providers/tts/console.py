"""
Console TTS Provider - Debug text output

Converted from irene/plugins/builtin/console_tts_plugin.py to provider pattern.
Provides text-to-speech by printing to console for debugging purposes.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List

from .base import TTSProvider

logger = logging.getLogger(__name__)


class ConsoleTTSProvider(TTSProvider):
    """
    Console TTS provider for debugging purposes.
    
    Features:
    - Prints text to console instead of speech synthesis
    - Colored output (if termcolor available)
    - Non-blocking async operation
    - No external dependencies required
    - Timing simulation for realistic testing
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ConsoleTTSProvider with configuration.
        
        Args:
            config: Provider configuration including color_output, timing_simulation
        """
        super().__init__(config)
        
        # Configuration values
        self.color_output = config.get("color_output", True)
        self.timing_simulation = config.get("timing_simulation", True)
        self.prefix = config.get("prefix", "TTS: ")
        self.simulate_delay = config.get("simulate_delay", 0.1)  # seconds per word
        
        # Settings dictionary for compatibility
        self._settings = {
            "use_color": self.color_output,
            "prefix": self.prefix,
            "timing_simulation": self.timing_simulation
        }
        
        # Try to import termcolor for colored output
        try:
            import termcolor  # type: ignore
            self._termcolor_available = True
            self._colored_print = termcolor.cprint
            logger.debug("Console TTS provider: termcolor available")
        except ImportError:
            self._termcolor_available = False
            self._colored_print = None
            logger.debug("Console TTS provider: termcolor not available, using plain text")
    
    async def is_available(self) -> bool:
        """Console TTS is always available"""
        return True
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """Console TTS doesn't use files"""
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Console TTS directory for logs/temp files"""
        return "console"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Console TTS doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Console TTS uses runtime cache for logging"""
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """Console TTS doesn't use models"""
        return {}
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Console TTS has no dependencies - pure Python"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Console TTS has no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Console TTS supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    async def synthesize_to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """
        Save text to file instead of audio.
        
        Args:
            text: Text to save
            output_path: Path where to save the text file
            **kwargs: format (txt or json)
        """
        format_type = kwargs.get("format", "txt")
        
        # Simulate file processing time
        if self.timing_simulation:
            await asyncio.sleep(0.05)
        
        try:
            if format_type == "json":
                import json
                data = {
                    "text": text,
                    "provider": "console",
                    "timestamp": str(asyncio.get_event_loop().time()),
                    "config": self.config
                }
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                # Save as plain text
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                    
            logger.info(f"Console TTS text saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Error saving console TTS text to file: {e}")
            raise RuntimeError(f"Failed to save TTS text: {e}")
    
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities information"""
        return {
            "languages": ["en-US", "ru-RU", "universal"],
            "voices": ["console", "colored", "plain"],
            "formats": ["txt", "json"],
            "features": [
                "debug_output",
                "colored_text" if self._termcolor_available else "plain_text",
                "timing_simulation",
                "file_output",
                "no_dependencies"
            ],
            "quality": "debug",
            "speed": "instant"
        }
    
    def get_provider_name(self) -> str:
        """Get unique provider identifier"""
        return "console"
    
    async def validate_parameters(self, **kwargs) -> bool:
        """Validate provider-specific parameters"""
        try:
            if "color" in kwargs:
                valid_colors = ["red", "green", "blue", "yellow", "magenta", "cyan", "white"]
                if kwargs["color"] not in valid_colors:
                    return False
                    
            if "style" in kwargs:
                valid_styles = ["console", "colored", "plain"]
                if kwargs["style"] not in valid_styles:
                    return False
                    
            if "format" in kwargs:
                valid_formats = ["txt", "json"]
                if kwargs["format"] not in valid_formats:
                    return False
                    
            return True
        except (ValueError, TypeError):
            return False
    
    async def configure(self, config: Dict[str, Any]) -> None:
        """Update provider configuration at runtime"""
        self.config.update(config)
        
        # Update settings
        if "color_output" in config:
            self.color_output = config["color_output"]
            self._settings["use_color"] = self.color_output
            
        if "prefix" in config:
            self.prefix = config["prefix"]
            self._settings["prefix"] = self.prefix
            
        if "timing_simulation" in config:
            self.timing_simulation = config["timing_simulation"]
            self._settings["timing_simulation"] = self.timing_simulation
            
        if "simulate_delay" in config:
            self.simulate_delay = config["simulate_delay"]
            
        logger.debug(f"Console TTS provider configuration updated: {config}") 