"""
Silero v3 TTS Provider - Neural text-to-speech using Silero models v3

Converted from irene/plugins/builtin/silero_v3_tts_plugin.py to provider pattern.
Provides high-quality Russian neural TTS using Silero v3.1 models.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import TTSProvider

logger = logging.getLogger(__name__)


class SileroV3TTSProvider(TTSProvider):
    """
    Silero v3 TTS provider for high-quality neural text-to-speech.
    
    Features:
    - High-quality neural TTS using Silero v3.1 models
    - Multiple Russian speakers (xenia, aidar, baya, kseniya, eugene)
    - Text normalization and accent placement
    - Async model loading and speech generation
    - Speaker selection based on configuration
    - Graceful handling of missing dependencies
    - Model caching optimization for performance
    
    Enhanced in TODO #4 Phase 1 with intelligent asset defaults.
    """
    
    # Class-level model cache for sharing across instances
    _model_cache: Dict[str, Any] = {}
    _cache_lock = asyncio.Lock()  # Protect concurrent access to cache
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize SileroV3TTSProvider with configuration.
        
        Args:
            config: Provider configuration including model_path, default_speaker, etc.
        """
        super().__init__(config)
        self._available = False
        self._model = None
        self._device = None
        self._torch = None
        
        # Asset management integration
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Configuration values with asset management
        legacy_model_path = config.get("model_path")
        if legacy_model_path:
            self.model_path = Path(legacy_model_path).expanduser()
            logger.warning("Using legacy model_path config. Consider using IRENE_MODELS_ROOT environment variable.")
        else:
            self.model_path = self.asset_manager.config.silero_models_dir
            
        self.model_url = config.get("model_url", "https://models.silero.ai/models/tts/ru/v3_1_ru.pt")
        self.model_file = self.model_path / config.get("model_file", "v3_ru.pt")
        self.default_speaker = config.get("default_speaker", "xenia")
        self.sample_rate = config.get("sample_rate", 24000)
        self.torch_device = config.get("torch_device", "cpu")
        self.put_accent = config.get("put_accent", True)
        self.put_yo = config.get("put_yo", True)
        self.threads = config.get("threads", 4)
        
        # Speaker mapping based on assistant name
        self.speaker_by_assname = config.get("speaker_by_assname", {
            "николай|николаю": "aidar",
            "ирина|ирине": "xenia"
        })
        
        # Available speakers
        self._speakers = ["xenia", "aidar", "baya", "kseniya", "eugene"]
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """Silero v3 models use PyTorch .pt format"""
        return ".pt"
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Silero v3 models stored in dedicated silero directory"""
        return "silero"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Silero v3 is open source, no credentials needed"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Uses models cache for PyTorch models and runtime cache for temporary audio"""
        return ["models", "runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """Default Silero v3 model URLs"""
        return {
            "v3_ru": "https://models.silero.ai/models/tts/ru/v3_1_ru.pt",
            "v3_en": "https://models.silero.ai/models/tts/en/v3_en.pt",
            "v3_de": "https://models.silero.ai/models/tts/de/v3_de.pt",
            "v3_es": "https://models.silero.ai/models/tts/es/v3_es.pt"
        }
        
        # Try to import dependencies
        try:
            import torch  # type: ignore
            self._torch = torch
            self._device = torch.device(self.torch_device)
            self._available = True
            logger.info("Silero v3 TTS provider dependencies available")
        except ImportError:
            self._available = False
            logger.warning("Silero v3 TTS provider dependencies not available (torch required)")
        
        # Initialize model on startup if requested
        preload_models = config.get("preload_models", False)
        if preload_models and self._available:
            # Schedule model loading for startup
            import asyncio
            asyncio.create_task(self.warm_up())
    
    async def is_available(self) -> bool:
        """Check if provider dependencies are available and functional"""
        if not self._available or not self._torch:
            return False
            
        # Check if model file exists or can be downloaded
        model_path = Path(self.model_file)
        if model_path.exists():
            return True
            
        # Check if we can access the download URL
        try:
            import requests
            response = requests.head(self.model_url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    async def speak(self, text: str, **kwargs) -> None:
        """
        Convert text to speech and play it.
        
        Args:
            text: Text to convert to speech
            **kwargs: speaker, sample_rate, put_accent, put_yo, core (for audio playback)
        """
        if not self._available or not self._model:
            await self._ensure_model_loaded()
            
        # Create temporary file for audio
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            
        try:
            await self.to_file(text, temp_path, **kwargs)
            
            # Play the generated audio file using audio plugins
            core = kwargs.get('core')
            if core and hasattr(core, 'output_manager'):
                # Get available audio plugins and play
                audio_plugins = getattr(core.output_manager, '_audio_plugins', [])
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
    
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """
        Convert text to speech and save to audio file.
        
        Args:
            text: Text to convert to speech
            output_path: Path where to save the audio file
            **kwargs: speaker, sample_rate, put_accent, put_yo, core
        """
        if not self._available or not self._model:
            await self._ensure_model_loaded()
            
        try:
            # Extract parameters
            speaker = kwargs.get('speaker', self.default_speaker)
            sample_rate = kwargs.get('sample_rate', self.sample_rate)
            put_accent = kwargs.get('put_accent', self.put_accent)
            put_yo = kwargs.get('put_yo', self.put_yo)
            
            # Resolve speaker by assistant name if configured
            core = kwargs.get('core')
            if core and hasattr(core, 'cur_callname'):
                cur_callname = getattr(core, 'cur_callname', '')
                if cur_callname:
                    for name_pattern, mapped_speaker in self.speaker_by_assname.items():
                        name_variants = name_pattern.split('|')
                        if cur_callname.lower() in [n.lower() for n in name_variants]:
                            speaker = mapped_speaker
                            break
            
            # Validate speaker
            if speaker not in self._speakers:
                logger.warning(f"Unknown speaker: {speaker}, using default: {self.default_speaker}")
                speaker = self.default_speaker
                
            # Normalize text
            processed_text = await self._normalize_text_async(text)
            
            logger.debug(f"Generating TTS with speaker: {speaker}, sample_rate: {sample_rate}")
            
            # Generate speech asynchronously
            await self._generate_speech_async(
                processed_text, output_path, speaker, sample_rate, put_accent, put_yo
            )
            
        except Exception as e:
            logger.error(f"Failed to generate speech file with Silero v3: {e}")
            raise RuntimeError(f"TTS file generation failed: {e}")
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for provider-specific parameters"""
        return {
            "speaker": {
                "type": "string",
                "description": "Voice speaker to use",
                "options": self._speakers,
                "default": self.default_speaker
            },
            "sample_rate": {
                "type": "integer",
                "description": "Audio sample rate in Hz",
                "options": [8000, 24000, 48000],
                "default": self.sample_rate
            },
            "put_accent": {
                "type": "boolean",
                "description": "Apply automatic stress marks",
                "default": self.put_accent
            },
            "put_yo": {
                "type": "boolean", 
                "description": "Convert 'е' to 'ё' where appropriate",
                "default": self.put_yo
            },
            "torch_device": {
                "type": "string",
                "description": "PyTorch device for inference",
                "options": ["cpu", "cuda"],
                "default": self.torch_device
            }
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities information"""
        return {
            "languages": ["ru-RU"],
            "voices": self._speakers,
            "formats": ["wav"],
            "features": [
                "neural_synthesis",
                "multi_speaker", 
                "stress_placement",
                "text_normalization",
                "async_generation"
            ],
            "quality": "high",
            "speed": "medium"
        }
    
    def get_provider_name(self) -> str:
        """Get unique provider identifier"""
        return "silero_v3"
    
    async def _ensure_model_loaded(self) -> None:
        """Ensure model is loaded and ready with caching optimization"""
        if not self._available:
            raise RuntimeError("Silero v3 TTS provider not available (torch dependency missing)")
            
        if not self._model:
            # Try to get model from cache first
            cache_key = f"{self.model_file}:{self.torch_device}"
            await self._get_or_load_cached_model(cache_key)
            
        if not self._model:
            raise RuntimeError("Failed to load Silero v3 model")
    
    async def _get_or_load_cached_model(self, cache_key: str) -> None:
        """Get model from cache or load it if not cached"""
        async with self._cache_lock:
            # Check if model is already cached
            if cache_key in self._model_cache:
                self._model = self._model_cache[cache_key]
                logger.info(f"Using cached Silero v3 model: {cache_key}")
                return
            
            # Model not in cache, load it
            await self._load_model_async()
            
            # Cache the loaded model
            if self._model:
                self._model_cache[cache_key] = self._model
                logger.info(f"Cached Silero v3 model: {cache_key}")
    
    async def _load_model_async(self) -> None:
        """Load Silero model asynchronously using asset management"""
        if not self._torch:
            return
            
        # Ensure model directory exists
        self.model_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Download model if not present using asset manager or legacy method
        if not self.model_file.exists():
            logger.info("Downloading Silero v3 model...")
            
            # Get model info from asset manager
            model_info = self.asset_manager.get_model_info("silero", "v3_ru")
            if model_info:
                logger.info(f"Downloading Silero v3 model (size: {model_info.get('size', 'unknown')})")
            
            try:
                # Try asset manager download first
                downloaded_path = await self.asset_manager.download_model("silero", "v3_ru")
                if downloaded_path != self.model_file:
                    # Copy to expected location if different
                    import shutil
                    shutil.copy2(downloaded_path, self.model_file)
            except Exception as e:
                logger.warning(f"Asset manager download failed, using legacy method: {e}")
                await asyncio.to_thread(self._download_model, self.model_file)
            
        # Load model
        logger.info(f"Loading Silero v3 model from {self.model_file}...")
        await asyncio.to_thread(self._load_model, self.model_file)
        
    def _download_model(self, model_path: Path) -> None:
        """Download model using legacy method (called from thread)"""
        if not self._torch:
            return
            
        try:
            self._torch.hub.download_url_to_file(self.model_url, str(model_path))
            logger.info(f"Silero v3 model downloaded to: {model_path}")
        except Exception as e:
            logger.error(f"Failed to download Silero v3 model: {e}")
            raise
            raise
            
    def _load_model(self, model_path: Path) -> None:
        """Load model from file (called from thread)"""
        if not self._torch:
            return
            
        try:
            self._model = self._torch.package.PackageImporter(str(model_path)).load_pickle("tts_models", "model")
            self._model.to(self._device)
            logger.info("Silero v3 model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Silero v3 model: {e}")
            raise
    
    async def warm_up(self) -> None:
        """Warm up by preloading the Silero v3 model"""
        try:
            logger.info("Warming up Silero v3 TTS model...")
            await self._ensure_model_loaded()
            logger.info("Silero v3 TTS model warmed up successfully")
        except Exception as e:
            logger.error(f"Failed to warm up Silero v3 model: {e}")
            # Don't raise - let the provider work with lazy loading
            
    async def _normalize_text_async(self, text: str) -> str:
        """Normalize text asynchronously"""
        # Basic text normalization
        normalized = text.replace("…", "...")
        
        # Modern number-to-text conversion using migrated utilities
        try:
            from ...utils.text_processing import all_num_to_text_async
            normalized = await all_num_to_text_async(normalized, language="ru")
            logger.debug("Applied number-to-text normalization")
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
            raise RuntimeError("Silero v3 model not loaded")
            
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
            
            logger.debug(f"Silero v3 speech generated: {output_path}")
            
        except Exception as e:
            logger.error(f"Silero v3 speech generation error: {e}")
            raise 