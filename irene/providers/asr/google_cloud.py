"""
Google Cloud ASR Provider

Google Cloud Speech-to-Text API provider implementation.
Requires Google Cloud credentials and supports high-quality cloud-based recognition.
"""

import asyncio
import tempfile
import os
from typing import Dict, Any, List, AsyncIterator
from pathlib import Path
import logging

from .base import ASRProvider

logger = logging.getLogger(__name__)


class GoogleCloudASRProvider(ASRProvider):
    """Google Cloud Speech-to-Text Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Google Cloud provider with configuration
        
        Args:
            config: Provider configuration containing:
                - credentials_path: Path to Google Cloud service account JSON (deprecated - uses asset manager)
                - project_id: Google Cloud project ID
                - default_language: Default language code (e.g., 'ru-RU', 'en-US')
                - sample_rate_hertz: Audio sample rate
                - encoding: Audio encoding format
        """
        super().__init__(config)  # Proper ABC inheritance
        
        # Asset management integration - single source of truth
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Use asset manager for credentials - unified pattern
        credentials = self.asset_manager.get_credentials("google_cloud")
        
        # Credentials from asset manager/environment
        self.credentials_path = credentials.get("google_application_credentials")
        if not self.credentials_path:
            # Fallback to asset manager credentials directory
            creds_file = self.asset_manager.get_credentials_path("google_cloud", "credentials.json")
            self.credentials_path = str(creds_file) if creds_file.exists() else None
            
        self.project_id = credentials.get("google_cloud_project_id") or config.get("project_id")
        self.default_language = config.get("default_language", "ru-RU")
        self.sample_rate_hertz = config.get("sample_rate_hertz", 16000)
        self.encoding = config.get("encoding", "LINEAR16")
        self._client: Any = None  # Lazy-loaded Google Cloud Speech client
        
    async def is_available(self) -> bool:
        """Check if Google Cloud dependencies and credentials are available"""
        try:
            from google.cloud import speech  # type: ignore
            
            # Check if credentials file exists
            if self.credentials_path and Path(self.credentials_path).exists():
                return True
            
            # Check if application default credentials are available
            try:
                import google.auth  # type: ignore
                credentials, project = google.auth.default()
                return credentials is not None
            except Exception:
                logger.warning("Google Cloud credentials not found")
                return False
                
        except ImportError:
            logger.warning("Google Cloud Speech library not available")
            return False
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """Google Cloud ASR is API-based, no persistent files"""
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Google Cloud ASR directory for temp files"""
        return "google_cloud"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Google Cloud ASR needs service account credentials"""
        return ["GOOGLE_CLOUD_CREDENTIALS", "GOOGLE_APPLICATION_CREDENTIALS"]
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Google Cloud ASR uses runtime cache for API responses"""
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """Google Cloud ASR is API-based, no model downloads"""
        return {}
    
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        """Transcribe audio using Google Cloud Speech-to-Text"""
        language = kwargs.get("language", self.default_language)
        
        try:
            # Initialize client if not already done
            if self._client is None:
                await self._initialize_client()
            
            # Configure recognition request
            config = {
                "encoding": self.encoding,
                "sample_rate_hertz": self.sample_rate_hertz,
                "language_code": language,
                "enable_automatic_punctuation": True,
                "use_enhanced": True,  # Use enhanced model if available
            }
            
            audio = {"content": audio_data}
            
            # Perform transcription
            response = await asyncio.to_thread(
                self._client.recognize,
                config=config,
                audio=audio
            )
            
            # Extract text from response
            if response.results:
                transcript = ""
                for result in response.results:
                    if result.alternatives:
                        transcript += result.alternatives[0].transcript + " "
                return transcript.strip()
            
            return ""
        
        except Exception as e:
            logger.error(f"Google Cloud ASR error: {e}")
            return ""
    
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Transcribe streaming audio using Google Cloud Speech-to-Text"""
        try:
            # Initialize client if not already done
            if self._client is None:
                await self._initialize_client()
            
            # Configure streaming recognition
            config = {
                "encoding": self.encoding,
                "sample_rate_hertz": self.sample_rate_hertz,
                "language_code": self.default_language,
                "enable_automatic_punctuation": True,
                "interim_results": True,  # Get partial results
            }
            
            streaming_config = {
                "config": config,
                "interim_results": True,
            }
            
            # Create audio generator
            async def audio_generator():
                async for chunk in audio_stream:
                    yield {"audio_content": chunk}
            
            # Perform streaming recognition
            requests = audio_generator()
            responses = await asyncio.to_thread(
                self._client.streaming_recognize,
                config=streaming_config,
                requests=requests
            )
            
            # Process streaming responses
            for response in responses:
                for result in response.results:
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript
                        if result.is_final:
                            yield transcript.strip()
                        else:
                            yield f"[partial] {transcript.strip()}"
        
        except Exception as e:
            logger.error(f"Google Cloud streaming ASR error: {e}")
    
    async def _initialize_client(self) -> None:
        """Initialize Google Cloud Speech client"""
        try:
            from google.cloud import speech  # type: ignore
            
            # Set up credentials if provided
            if self.credentials_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path
            
            # Create client in thread to avoid blocking
            self._client = await asyncio.to_thread(speech.SpeechClient)
            logger.info("Initialized Google Cloud Speech client")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud Speech client: {e}")
            raise
    
    
    def get_provider_name(self) -> str:
        """Return provider identifier"""
        return "google_cloud"
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Google Cloud ASR requires specific Google Cloud libraries"""
        return ["google-cloud-speech>=2.20.0", "google-auth>=2.17.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Google Cloud ASR is cloud-based, no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Google Cloud ASR supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    def get_supported_languages(self) -> List[str]:
        """Return list of supported language codes"""
        return [
            "ru-RU", "en-US", "en-GB", "es-ES", "es-US", "fr-FR", "de-DE",
            "it-IT", "ja-JP", "ko-KR", "zh-CN", "zh-TW", "pt-BR", "pt-PT",
            "ar-SA", "hi-IN", "th-TH", "tr-TR", "pl-PL", "cs-CZ", "sk-SK",
            "hu-HU", "ro-RO", "bg-BG", "hr-HR", "sl-SI", "et-EE", "lv-LV",
            "lt-LT", "fi-FI", "da-DK", "sv-SE", "no-NO", "nl-NL", "he-IL"
        ]
    
    def get_supported_formats(self) -> List[str]:
        """Return list of supported audio formats"""
        return ["wav", "flac", "mp3", "ogg", "amr", "webm"]
    
    def get_preferred_sample_rates(self) -> List[int]:
        """Return list of preferred sample rates for Google Cloud (Phase 3)"""
        # Google Cloud performs best at specific sample rates
        # 16kHz is optimal for telephony, 44.1/48kHz for high quality
        return [16000, 48000, 44100, 22050, 8000]
    
    def supports_sample_rate(self, rate: int) -> bool:
        """Check if Google Cloud supports specific sample rate (Phase 3)"""
        # Google Cloud Speech API supports specific sample rates
        # Must match exactly what's configured in sample_rate_hertz parameter
        supported_rates = [8000, 16000, 22050, 44100, 48000]
        return rate in supported_rates
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return Google Cloud provider capabilities"""
        return {
            "languages": self.get_supported_languages(),
            "formats": self.get_supported_formats(),
            "streaming": True,
            "real_time": True,  # Supports real-time streaming
            "confidence_scores": False,  # Not implemented in current transcribe_audio method
            "offline": False,  # Requires internet connection
            "cloud_based": True,
            "high_accuracy": True,  # Generally high accuracy
            "punctuation": True,  # Automatic punctuation
            "enhanced_models": True,  # Access to enhanced models
            "custom_models": True  # Supports custom model training
        } 