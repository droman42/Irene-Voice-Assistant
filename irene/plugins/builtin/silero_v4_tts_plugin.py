"""
Silero v4 TTS Plugin - Neural text-to-speech using Silero models v4

Replaces legacy plugin_tts_silero_v4.py with modern async architecture.
Provides high-quality Russian neural TTS using Silero v4 models.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List

from ...core.interfaces.tts import TTSPlugin
from ..base import BasePlugin

logger = logging.getLogger(__name__)


class SileroV4TTSPlugin(BasePlugin, TTSPlugin):
    """
    Silero v4 TTS plugin for high-quality neural text-to-speech.
    
    Features:
    - High-quality neural TTS using Silero v4 models
    - Multiple Russian speakers (xenia, aidar, baya, kseniya, eugene)
    - Updated models with improved quality
    - Text normalization and accent placement
    - Async model loading and speech generation
    - Speaker selection based on assistant name
    - Graceful handling of missing dependencies
    """
    
    @property
    def name(self) -> str:
        return "silero_v4_tts"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "High-quality Russian neural TTS using Silero v4 models"
        
    @property
    def optional_dependencies(self) -> List[str]:
        return ["torch"]
        
    def __init__(self):
        super().__init__()
        self._available = False
        self._model = None
        self._device = None
        self._model_url = 'https://models.silero.ai/models/tts/ru/v4_ru.pt'
        self._model_file = 'silero_model_v4.pt'
        
        # Default settings - v4 optimized
        self._settings = {
            "speaker": "xenia",
            "threads": 1,  # v4 optimized for single thread
            "sample_rate": 24000,
            "put_accent": True,
            "put_yo": True,
            "speaker_by_assname": {
                "николай|николаю": "aidar",
                "ирина|ирине": "xenia"
            }
        }
        
        # Available speakers
        self._speakers = ["xenia", "aidar", "baya", "kseniya", "eugene"]
        
        # Try to import dependencies
        try:
            import torch  # type: ignore
            
            # Check for minimum version (v4 requires PyTorch 2.0+)
            if hasattr(torch, '__version__'):
                version_parts = torch.__version__.split('.')
                major_version = int(version_parts[0])
                if major_version < 2:
                    logger.warning(f"Silero v4 requires PyTorch 2.0+, found: {torch.__version__}")
                    self._torch = None
                    return
                    
            self._torch = torch
            self._available = True
            logger.info(f"Silero v4 TTS backend available (PyTorch {torch.__version__})")
            
        except ImportError as e:
            logger.warning(f"Silero v4 dependencies not available: {e}")
            logger.info("Install with: uv add 'torch>=2.0.0'")
            self._torch = None
            
    def is_available(self) -> bool:
        """Check if Silero v4 backend is available"""
        return self._available
        
    async def initialize(self, core) -> None:
        """Initialize the TTS plugin"""
        await super().initialize(core)
        
        if not self._available:
            logger.warning("Silero v4 TTS plugin initialized but dependencies missing")
            return
            
        try:
            # Set device and threads
            if self._torch:
                self._device = self._torch.device('cpu')
                self._torch.set_num_threads(self._settings["threads"])
            
            # Load model asynchronously
            await self._load_model_async()
            
            logger.info("Silero v4 TTS plugin initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Silero v4 TTS: {e}")
            self._available = False
            
    async def speak(self, text: str, **kwargs) -> None:
        """
        Convert text to speech and play it.
        
        Args:
            text: Text to convert to speech
            **kwargs: speaker (str), sample_rate (int), put_accent (bool), put_yo (bool)
        """
        if not self._available or not self._model:
            raise RuntimeError("Silero v4 TTS backend not available")
            
        try:
            # Generate speech to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                
            try:
                await self.to_file(text, temp_path, **kwargs)
                
                # Play the generated audio file using audio plugins
                if self.core and hasattr(self.core, 'output_manager'):
                    # Get available audio plugins and play
                    audio_plugins = getattr(self.core.output_manager, '_audio_plugins', [])
                    if audio_plugins:
                        # Use first available audio plugin
                        for plugin in audio_plugins:
                            if plugin.is_available():
                                await plugin.play_file(temp_path)
                                break
                        else:
                            logger.warning("No audio plugins available for playback")
                    else:
                        logger.warning("No audio output system available")
                        
            finally:
                # Clean up temporary file
                if temp_path.exists():
                    temp_path.unlink()
                    
        except Exception as e:
            logger.error(f"Failed to speak text with Silero v4: {e}")
            raise RuntimeError(f"TTS failed: {e}")
            
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """
        Convert text to speech and save to file.
        
        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file
            **kwargs: speaker (str), sample_rate (int), put_accent (bool), put_yo (bool)
        """
        if not self._available or not self._model:
            raise RuntimeError("Silero v4 TTS backend not available")
            
        try:
            # Extract parameters
            speaker = kwargs.get('speaker', self._settings['speaker'])
            sample_rate = kwargs.get('sample_rate', self._settings['sample_rate'])
            put_accent = kwargs.get('put_accent', self._settings['put_accent'])
            put_yo = kwargs.get('put_yo', self._settings['put_yo'])
            
            # Resolve speaker by assistant name if configured
            if self.core and hasattr(self.core, 'cur_callname'):
                cur_callname = getattr(self.core, 'cur_callname', '')
                if cur_callname:
                    for name_pattern, mapped_speaker in self._settings['speaker_by_assname'].items():
                        name_variants = name_pattern.split('|')
                        if cur_callname.lower() in [n.lower() for n in name_variants]:
                            speaker = mapped_speaker
                            break
            
            # Validate speaker
            if speaker not in self._speakers:
                logger.warning(f"Unknown speaker: {speaker}, using default: {self._settings['speaker']}")
                speaker = self._settings['speaker']
                
            # Normalize text
            processed_text = await self._normalize_text_async(text)
            
            logger.debug(f"Generating TTS v4 with speaker: {speaker}, sample_rate: {sample_rate}")
            
            # Generate speech asynchronously
            await self._generate_speech_async(
                processed_text, output_path, speaker, sample_rate, put_accent, put_yo
            )
            
        except Exception as e:
            logger.error(f"Failed to generate speech file with Silero v4: {e}")
            raise RuntimeError(f"TTS file generation failed: {e}")
            
    def get_supported_voices(self) -> List[str]:
        """Get list of available voices"""
        if not self._available:
            return []
        return self._speakers.copy()
        
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes"""
        return ['ru-RU']
        
    def get_voice_settings(self) -> Dict[str, Any]:
        """Get current voice settings"""
        return self._settings.copy()
        
    async def set_voice_settings(self, **settings) -> None:
        """Update voice settings"""
        for key, value in settings.items():
            if key in self._settings:
                self._settings[key] = value
                logger.debug(f"Updated Silero v4 setting {key} = {value}")
            else:
                logger.warning(f"Unknown Silero v4 setting: {key}")
                
    async def test_speech(self) -> bool:
        """Test the TTS engine with a simple phrase"""
        if not self._available:
            return False
            
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                
            try:
                await self.to_file("Тест синтеза речи версии четыре", temp_path)
                # Check if file was created and has content
                return temp_path.exists() and temp_path.stat().st_size > 0
            finally:
                if temp_path.exists():
                    temp_path.unlink()
                    
        except Exception as e:
            logger.error(f"Silero v4 TTS test failed: {e}")
            return False
            
    async def _load_model_async(self) -> None:
        """Load Silero model asynchronously"""
        if not self._torch:
            return
            
        model_path = Path(self._model_file)
        
        # Download model if not present
        if not model_path.exists():
            logger.info("Downloading Silero v4 model...")
            await asyncio.to_thread(self._download_model, model_path)
            
        # Load model
        logger.info("Loading Silero v4 model...")
        await asyncio.to_thread(self._load_model, model_path)
        
    def _download_model(self, model_path: Path) -> None:
        """Download model (called from thread)"""
        if not self._torch:
            return
            
        try:
            self._torch.hub.download_url_to_file(self._model_url, str(model_path))
            logger.info(f"Silero v4 model downloaded to: {model_path}")
        except Exception as e:
            logger.error(f"Failed to download Silero v4 model: {e}")
            raise
            
    def _load_model(self, model_path: Path) -> None:
        """Load model from file (called from thread)"""
        if not self._torch:
            return
            
        try:
            self._model = self._torch.package.PackageImporter(str(model_path)).load_pickle("tts_models", "model")
            self._model.to(self._device)
            logger.info("Silero v4 model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Silero v4 model: {e}")
            raise
            
    async def _normalize_text_async(self, text: str) -> str:
        """Normalize text asynchronously"""
        # Basic text normalization
        normalized = text.replace("…", "...")
        
        # TODO: Add number-to-text conversion using core.all_num_to_text if available
        if self.core and hasattr(self.core, 'all_num_to_text'):
            try:
                normalized = await asyncio.to_thread(self.core.all_num_to_text, normalized)
            except Exception as e:
                logger.debug(f"Text normalization failed, using original: {e}")
                
        return normalized
        
    async def _generate_speech_async(self, text: str, output_path: Path, 
                                   speaker: str, sample_rate: int, 
                                   put_accent: bool, put_yo: bool) -> None:
        """Generate speech asynchronously"""
        await asyncio.to_thread(
            self._generate_speech_blocking, 
            text, output_path, speaker, sample_rate, put_accent, put_yo
        )
        
    def _generate_speech_blocking(self, text: str, output_path: Path,
                                speaker: str, sample_rate: int,
                                put_accent: bool, put_yo: bool) -> None:
        """Generate speech in blocking mode (called from thread)"""
        if not self._model:
            raise RuntimeError("Silero v4 model not loaded")
            
        try:
            # Generate audio
            generated_path = self._model.save_wav(
                text=text,
                speaker=speaker,
                put_accent=put_accent,
                put_yo=put_yo,
                sample_rate=sample_rate
            )
            
            # Move to desired location
            generated_path = Path(generated_path)
            if output_path.exists():
                output_path.unlink()
            generated_path.rename(output_path)
            
            logger.debug(f"Silero v4 speech generated: {output_path}")
            
        except Exception as e:
            logger.error(f"Silero v4 speech generation error: {e}")
            raise 