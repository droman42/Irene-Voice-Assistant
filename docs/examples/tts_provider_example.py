#!/usr/bin/env python3
"""
Custom TTS Provider Example

This example demonstrates how to create a custom TTS provider for the
Universal Plugin architecture in Irene Voice Assistant.

A provider is a pure implementation that follows the TTSProvider interface
and is managed by the UniversalTTSPlugin coordinator.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

# Import the base TTSProvider class
from irene.providers.tts.base import TTSProvider

logger = logging.getLogger(__name__)


class CustomTTSProvider(TTSProvider):
    """
    Example custom TTS provider implementing the TTSProvider interface.
    
    This example shows a simple custom TTS implementation that:
    - Follows the ABC inheritance pattern for type safety
    - Implements all required abstract methods
    - Provides proper error handling and availability checking
    - Supports configuration-driven parameters
    - Includes parameter schema and capabilities reporting
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the custom TTS provider with configuration.
        
        Args:
            config: Provider configuration dictionary from TOML config
        """
        super().__init__(config)  # Proper ABC inheritance
        
        # Extract configuration parameters
        self.api_endpoint = config.get("api_endpoint", "https://api.example.com/tts")
        self.api_key = config.get("api_key", "")
        self.default_voice = config.get("default_voice", "english-male")
        self.default_speed = config.get("default_speed", 1.0)
        self.output_format = config.get("output_format", "wav")
        self.timeout = config.get("timeout", 30.0)
        
        # Available voices for this provider
        self._voices = ["english-male", "english-female", "spanish-male", "spanish-female"]
        
        # Available languages
        self._languages = ["en", "es"]
        
        # Initialize state
        self._available = self._check_dependencies()
        
        logger.info(f"Custom TTS provider initialized with endpoint: {self.api_endpoint}")
    
    async def is_available(self) -> bool:
        """
        Check if the provider is available and functional.
        
        This method should verify:
        - Required dependencies are installed
        - External services are reachable (if applicable)
        - Configuration is valid
        
        Returns:
            True if provider is ready to use, False otherwise
        """
        if not self._available:
            return False
        
        # Check if API endpoint is reachable (example)
        try:
            if self.api_key:
                # In a real implementation, you might test the API connection
                # For this example, we'll just check if the key is provided
                return True
            else:
                logger.warning("Custom TTS provider: API key not provided")
                return False
        except Exception as e:
            logger.error(f"Custom TTS provider availability check failed: {e}")
            return False
    
    async def speak(self, text: str, **kwargs) -> None:
        """
        Convert text to speech and play the audio.
        
        Args:
            text: Text to convert to speech
            **kwargs: Additional parameters like voice, speed, etc.
        """
        if not await self.is_available():
            raise RuntimeError("Custom TTS provider not available")
        
        # Extract parameters with defaults
        voice = kwargs.get("voice", self.default_voice)
        speed = kwargs.get("speed", self.default_speed)
        language = kwargs.get("language", "en")
        
        # Validate parameters
        if voice not in self._voices:
            logger.warning(f"Unknown voice '{voice}', using default '{self.default_voice}'")
            voice = self.default_voice
        
        logger.info(f"Custom TTS speaking: '{text}' (voice: {voice}, speed: {speed})")
        
        try:
            # Generate audio file
            with tempfile.NamedTemporaryFile(suffix=f'.{self.output_format}', delete=False) as temp_file:
                temp_path = Path(temp_file.name)
            
            await self.to_file(text, temp_path, voice=voice, speed=speed, language=language)
            
            # Play the generated audio file using the core's audio system
            core = kwargs.get('core')
            if core and hasattr(core, 'output_manager'):
                # Try to get universal audio plugin
                audio_plugin = core.plugin_manager.get_plugin("universal_audio")
                if audio_plugin:
                    await audio_plugin.play_file(temp_path)
                else:
                    # Fallback to output manager
                    await core.output_manager.play_audio_file(temp_path)
            else:
                logger.warning("No audio playback system available")
                
        except Exception as e:
            logger.error(f"Custom TTS speak failed: {e}")
            raise RuntimeError(f"TTS generation failed: {e}")
        finally:
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
    
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """
        Convert text to speech and save to file.
        
        Args:
            text: Text to convert to speech
            output_path: Path where to save the audio file
            **kwargs: Additional parameters like voice, speed, etc.
        """
        if not await self.is_available():
            raise RuntimeError("Custom TTS provider not available")
        
        # Extract parameters
        voice = kwargs.get("voice", self.default_voice)
        speed = kwargs.get("speed", self.default_speed)
        language = kwargs.get("language", "en")
        
        logger.info(f"Custom TTS generating file: {output_path}")
        
        try:
            # In a real implementation, this would:
            # 1. Call your TTS API/library
            # 2. Handle authentication
            # 3. Process the response
            # 4. Save audio data to file
            
            # For this example, we'll create a placeholder
            await self._generate_audio(text, output_path, voice, speed, language)
            
            logger.info(f"Custom TTS file generated successfully: {output_path}")
            
        except Exception as e:
            logger.error(f"Custom TTS file generation failed: {e}")
            raise RuntimeError(f"TTS file generation failed: {e}")
    
    async def _generate_audio(self, text: str, output_path: Path, 
                            voice: str, speed: float, language: str) -> None:
        """
        Generate audio using your custom TTS implementation.
        
        This is where you would implement the actual TTS logic:
        - Call external API
        - Use local TTS library
        - Process audio data
        """
        # Example implementation using asyncio to simulate API call
        await asyncio.sleep(0.1)  # Simulate processing time
        
        # Placeholder: In real implementation, generate actual audio
        # For example, using an HTTP client to call TTS API:
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "text": text,
                    "voice": voice,
                    "speed": speed,
                    "language": language,
                    "format": self.output_format
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Save audio data to file
            with open(output_path, "wb") as f:
                f.write(response.content)
        """
        
        # Placeholder implementation - creates a text file instead
        placeholder_content = f"Custom TTS Audio: {text}\nVoice: {voice}\nSpeed: {speed}\nLanguage: {language}"
        with open(output_path.with_suffix('.txt'), 'w', encoding='utf-8') as f:
            f.write(placeholder_content)
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """
        Return schema for provider-specific parameters.
        
        This helps the Universal Plugin understand what parameters
        this provider accepts and their types/constraints.
        
        Returns:
            Dictionary describing parameter schema
        """
        return {
            "voice": {
                "type": "string",
                "options": self._voices,
                "default": self.default_voice,
                "description": "Voice to use for speech synthesis"
            },
            "speed": {
                "type": "float",
                "min": 0.5,
                "max": 2.0,
                "default": self.default_speed,
                "description": "Speech speed multiplier"
            },
            "language": {
                "type": "string",
                "options": self._languages,
                "default": "en",
                "description": "Language for speech synthesis"
            },
            "format": {
                "type": "string",
                "options": ["wav", "mp3", "ogg"],
                "default": self.output_format,
                "description": "Audio output format"
            }
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return provider capabilities and metadata.
        
        This information is used for:
        - Provider discovery
        - Feature detection
        - User interface generation
        
        Returns:
            Dictionary describing provider capabilities
        """
        return {
            "languages": self._languages,
            "voices": self._voices,
            "formats": ["wav", "mp3", "ogg"],
            "quality": "high",
            "real_time": True,
            "offline": False,  # Requires internet for API
            "streaming": False,  # Doesn't support streaming
            "custom_voices": True,  # Supports voice selection
            "ssml": False,  # Doesn't support SSML markup
            "neural": True,  # Uses neural TTS technology
            "max_text_length": 5000,  # Maximum characters per request
            "supported_sample_rates": [22050, 44100, 48000]
        }
    
    def get_provider_name(self) -> str:
        """
        Return unique provider identifier.
        
        This name is used in configuration and API calls.
        """
        return "custom_tts"
    
    def _check_dependencies(self) -> bool:
        """
        Check if required dependencies are available.
        
        Returns:
            True if all dependencies are satisfied
        """
        try:
            # Check for required packages
            import httpx  # Example dependency for HTTP API calls
            return True
        except ImportError as e:
            logger.warning(f"Custom TTS provider dependency missing: {e}")
            return False


# Configuration example for this provider
EXAMPLE_CONFIG = {
    "custom_tts": {
        "enabled": True,
        "api_endpoint": "https://api.example.com/tts",
        "api_key": "your-api-key-here",
        "default_voice": "english-female",
        "default_speed": 1.0,
        "output_format": "wav",
        "timeout": 30.0
    }
}


# Integration example - how to register this provider
def register_custom_provider():
    """
    Example of how to register this custom provider with UniversalTTSPlugin.
    
    In practice, you would add this to the UniversalTTSPlugin's
    _provider_classes dictionary.
    """
    from irene.plugins.builtin.universal_tts_plugin import UniversalTTSPlugin
    
    # Add to provider classes mapping
    UniversalTTSPlugin._provider_classes["custom_tts"] = CustomTTSProvider
    
    print("Custom TTS provider registered!")


if __name__ == "__main__":
    """
    Example usage and testing of the custom provider.
    """
    
    async def test_custom_provider():
        """Test the custom TTS provider"""
        
        # Create provider with example config
        config = EXAMPLE_CONFIG["custom_tts"]
        provider = CustomTTSProvider(config)
        
        # Test availability
        available = await provider.is_available()
        print(f"Provider available: {available}")
        
        # Test capabilities
        capabilities = provider.get_capabilities()
        print(f"Capabilities: {capabilities}")
        
        # Test parameter schema
        schema = provider.get_parameter_schema()
        print(f"Parameter schema: {schema}")
        
        # Test file generation (if available)
        if available:
            test_file = Path("test_output.wav")
            try:
                await provider.to_file("Hello, this is a test!", test_file, voice="english-female")
                print(f"Test file generated: {test_file}")
            except Exception as e:
                print(f"Test failed: {e}")
    
    # Run test
    asyncio.run(test_custom_provider()) 