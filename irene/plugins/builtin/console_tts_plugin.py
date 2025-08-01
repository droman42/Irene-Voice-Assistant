"""
Console TTS Plugin - Debug text output

Replaces legacy plugin_tts_console.py with modern async architecture.
Provides text-to-speech by printing to console for debugging purposes.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from ...core.interfaces.tts import TTSPlugin


class ConsoleTTSPlugin(TTSPlugin):
    """
    Console TTS plugin for debugging purposes.
    
    Features:
    - Prints text to console instead of speech synthesis
    - Colored output (if termcolor available)
    - Non-blocking async operation
    - No external dependencies required
    """
    
    @property
    def name(self) -> str:
        return "console_tts"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Console text output for TTS debugging (no actual speech)"
        
    def __init__(self):
        super().__init__()
        self._settings = {
            "use_color": True,
            "prefix": "TTS: "
        }
        
        # Try to import termcolor for colored output
        try:
            import termcolor  # type: ignore
            self._termcolor_available = True
            self._colored_print = termcolor.cprint
        except ImportError:
            self._termcolor_available = False
            self._colored_print = None
            
    async def speak(self, text: str, **kwargs) -> None:
        """
        'Speak' text by printing to console.
        
        Args:
            text: Text to display
            **kwargs: Additional parameters (ignored for console output)
        """
        # Small delay to simulate async operation
        await asyncio.sleep(0.01)
        
        output_text = f"{self._settings['prefix']}{text}"
        
        if self._termcolor_available and self._settings["use_color"] and self._colored_print:
            # Print in blue color for TTS output
            self._colored_print(output_text, "blue")
        else:
            # Plain text output
            print(output_text)
            
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """
        Save text to file instead of audio.
        
        Args:
            text: Text to save
            output_path: File path for text output
            **kwargs: Additional parameters
        """
        await asyncio.sleep(0.01)
        
        try:
            # Save text to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"TTS text saved to: {output_path}")
        except Exception as e:
            print(f"Error saving TTS text to file: {e}")
            
    def get_supported_voices(self) -> list[str]:
        """Get list of available 'voices' (console output styles)"""
        return ["console", "colored", "plain"]
        
    def get_supported_languages(self) -> list[str]:
        """Get supported languages (all text is supported)"""
        return ["en-US", "ru-RU", "universal"]
        
    def get_voice_settings(self) -> Dict[str, Any]:
        """Get current console output settings"""
        return self._settings.copy()
        
    async def set_voice_settings(self, **settings) -> None:
        """
        Update console output settings.
        
        Args:
            **settings: Settings to update (use_color, prefix)
        """
        for key, value in settings.items():
            if key in self._settings:
                self._settings[key] = value
                
        # Update color availability if needed
        if "use_color" in settings and settings["use_color"]:
            if not self._termcolor_available:
                print("Warning: termcolor not available, color output disabled")
                self._settings["use_color"] = False
                
    def is_available(self) -> bool:
        """Console TTS is always available"""
        return True
        
    async def test_speech(self) -> bool:
        """Test console TTS output"""
        try:
            await self.speak("Console TTS test successful - this is debug output")
            return True
        except Exception as e:
            print(f"Console TTS test failed: {e}")
            return False 