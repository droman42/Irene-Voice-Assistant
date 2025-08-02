"""
ElevenLabs TTS Provider

ElevenLabs neural voice synthesis provider implementation.
Provides high-quality text-to-speech using cloud-based AI models.
"""

import asyncio
import tempfile
import os
from typing import Dict, Any, List
from pathlib import Path
import logging

from .base import TTSProvider

logger = logging.getLogger(__name__)


class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs TTS Provider - High-quality neural voice synthesis"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize ElevenLabs provider with configuration
        
        Args:
            config: Provider configuration containing:
                - api_key_env: Environment variable name for API key
                - voice_id: Default voice ID to use
                - model: Model to use for synthesis
                - stability: Voice stability setting (0-1)
                - similarity_boost: Voice similarity boost (0-1)
        """
        super().__init__(config)  # Proper ABC inheritance
        self.api_key = os.getenv(config["api_key_env"])
        self.voice_id = config.get("voice_id", "default")
        self.model = config.get("model", "eleven_monolingual_v1")
        self.stability = config.get("stability", 0.5)
        self.similarity_boost = config.get("similarity_boost", 0.5)
        self.base_url = "https://api.elevenlabs.io/v1"
        
    async def is_available(self) -> bool:
        """Check if ElevenLabs API is available"""
        if not self.api_key:
            logger.warning("ElevenLabs API key not found")
            return False
            
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/voices",
                    headers={"xi-api-key": self.api_key},
                    timeout=5.0
                )
                return response.status_code == 200
        except ImportError:
            logger.warning("httpx library not available for ElevenLabs")
            return False
        except Exception as e:
            logger.warning(f"ElevenLabs API check failed: {e}")
            return False
    
    async def speak(self, text: str, **kwargs) -> None:
        """Generate and play speech using ElevenLabs"""
        voice_id = kwargs.get("voice_id", self.voice_id)
        stability = kwargs.get("stability", self.stability)
        similarity_boost = kwargs.get("similarity_boost", self.similarity_boost)
        
        try:
            # Generate audio
            audio_data = await self._generate_audio(
                text, voice_id, stability, similarity_boost
            )
            
            # Play using audio plugin (if available)
            if hasattr(self, 'audio_plugin') and self.audio_plugin:
                # Save to temporary file and play
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    temp_file.write(audio_data)
                    temp_path = Path(temp_file.name)
                
                try:
                    await self.audio_plugin.play_file(temp_path)
                finally:
                    # Clean up temporary file
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
            else:
                logger.warning("No audio plugin available for ElevenLabs playback")
                
        except Exception as e:
            logger.error(f"ElevenLabs speech generation failed: {e}")
    
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """Generate audio file using ElevenLabs"""
        voice_id = kwargs.get("voice_id", self.voice_id)
        stability = kwargs.get("stability", self.stability)
        similarity_boost = kwargs.get("similarity_boost", self.similarity_boost)
        
        try:
            audio_data = await self._generate_audio(
                text, voice_id, stability, similarity_boost
            )
            
            with open(output_path, "wb") as f:
                f.write(audio_data)
                
            logger.info(f"ElevenLabs audio saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"ElevenLabs file generation failed: {e}")
    
    async def _generate_audio(self, text: str, voice_id: str, 
                            stability: float, similarity_boost: float) -> bytes:
        """Call ElevenLabs API to generate audio"""
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost
            }
        }
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, 
                    json=payload, 
                    headers=headers,
                    timeout=30.0  # Longer timeout for audio generation
                )
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"ElevenLabs API call failed: {e}")
            raise
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for ElevenLabs-specific parameters"""
        return {
            "voice_id": {
                "type": "string",
                "description": "ElevenLabs voice ID",
                "default": self.voice_id
            },
            "stability": {
                "type": "float",
                "min": 0.0,
                "max": 1.0,
                "description": "Voice stability (0-1)",
                "default": self.stability
            },
            "similarity_boost": {
                "type": "float", 
                "min": 0.0,
                "max": 1.0,
                "description": "Voice similarity boost (0-1)",
                "default": self.similarity_boost
            },
            "model": {
                "type": "string",
                "options": ["eleven_monolingual_v1", "eleven_multilingual_v1", "eleven_multilingual_v2"],
                "default": self.model,
                "description": "ElevenLabs model to use"
            }
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities"""
        return {
            "languages": ["en", "ru", "es", "fr", "de", "it", "pt", "pl", "hi", "ar"],
            "formats": ["mp3"],
            "quality": "high",
            "real_time": True,
            "custom_voices": True,
            "cloud_based": True,
            "neural": True,
            "emotional_range": True,
            "voice_cloning": True
        }
    
    def get_provider_name(self) -> str:
        return "elevenlabs" 