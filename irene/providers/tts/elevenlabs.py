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
    """
    ElevenLabs TTS Provider - High-quality neural voice synthesis
    
    Enhanced in TODO #4 Phase 1 with intelligent asset defaults.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize ElevenLabs provider with configuration
        
        Args:
            config: Provider configuration containing:
                - api_key_env: Environment variable name for API key (deprecated - uses asset manager)
                - voice_id: Default voice ID to use
                - model: Model to use for synthesis
                - stability: Voice stability setting (0-1)
                - similarity_boost: Voice similarity boost (0-1)
        """
        super().__init__(config)  # Proper ABC inheritance
        
        # Asset management integration for credentials
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Get API key through asset manager or fallback to config
        credentials = self.asset_manager.get_credentials("elevenlabs")
        self.api_key = credentials.get("elevenlabs_api_key") or os.getenv(config.get("api_key_env", "ELEVENLABS_API_KEY"))
        
        if not self.api_key and config.get("api_key_env"):
            logger.warning("Using legacy api_key_env config. Consider using ELEVENLABS_API_KEY environment variable.")
            
        self.voice_id = config.get("voice_id", "default")
        self.model = config.get("model", "eleven_monolingual_v1")
        self.stability = config.get("stability", 0.5)
        self.similarity_boost = config.get("similarity_boost", 0.5)
        self.base_url = "https://api.elevenlabs.io/v1"
        
    @classmethod
    def _get_default_extension(cls) -> str:
        """ElevenLabs provides audio streams, no persistent files"""
        return ".mp3"
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """ElevenLabs uses runtime cache only"""
        return "elevenlabs"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """ElevenLabs requires API key credential"""
        return ["ELEVENLABS_API_KEY"]
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Uses runtime cache for temporary audio data only"""
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """ElevenLabs is API-based, no model downloads"""
        return {}
    
    async def is_available(self) -> bool:
        """Check if ElevenLabs API is available"""
        if not self.api_key:
            logger.warning("ElevenLabs API key not found")
            return False
            
        try:
            import httpx  # type: ignore
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
    
    async def synthesize_to_file(self, text: str, output_path: Path, **kwargs) -> None:
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
            import httpx  # type: ignore
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
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """ElevenLabs TTS requires elevenlabs API client and httpx"""
        return ["elevenlabs>=1.0.3", "httpx>=0.25.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """ElevenLabs is cloud-based, no system dependencies"""
        return {
            "ubuntu": [],
            "alpine": [],
            "centos": [],
            "macos": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """ElevenLabs supports all platforms"""
        return ["linux", "windows", "macos"] 