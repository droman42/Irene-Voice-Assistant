"""
VOSK TTS Plugin - Text-to-speech using VOSK TTS models

Replaces legacy plugin_tts_vosk.py with modern async architecture.
Provides Russian TTS using VOSK TTS models with optional GPU acceleration.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from time import time

from ...core.interfaces.tts import TTSPlugin
from ..base import BasePlugin

logger = logging.getLogger(__name__)


class VoskTTSPlugin(BasePlugin, TTSPlugin):
    """
    VOSK TTS plugin for Russian text-to-speech.
    
    Features:
    - Russian TTS using VOSK TTS models
    - Multiple speaker IDs (0-4)
    - Optional GPU acceleration with CUDA
    - Text normalization
    - Async model loading and speech generation
    - Graceful handling of missing dependencies
    """
    
    @property
    def name(self) -> str:
        return "vosk_tts"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Russian TTS using VOSK with GPU acceleration support"
        
    @property
    def dependencies(self) -> list[str]:
        """No required dependencies (vosk-tts is optional)"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """Requires vosk-tts for Russian TTS"""
        return ["vosk-tts"]
        
    # Additional metadata for PluginRegistry discovery
    @property
    def enabled_by_default(self) -> bool:
        """VOSK TTS not enabled by default (requires dependency)"""
        return False
        
    @property  
    def category(self) -> str:
        """Plugin category"""
        return "tts"
        
    @property
    def platforms(self) -> list[str]:
        """Supported platforms (empty = all platforms)"""
        return []
        
    def __init__(self):
        super().__init__()
        self._available = False
        self._model = None
        self._synth = None
        self._gpu_available = False
        
        # Default settings
        self._settings = {
            "modelId": "vosk-model-tts-ru-0.7-multi",
            "speakerId": 2,  # Irina voice (0,1,2,3,4 available)
            "useGPU": False
        }
        
        # Available speaker IDs
        self._speaker_ids = [0, 1, 2, 3, 4]
        self._speaker_names = {
            0: "Speaker 0",
            1: "Speaker 1", 
            2: "Irina",
            3: "Speaker 3",
            4: "Speaker 4"
        }
        
        # Try to import dependencies
        try:
            from vosk_tts.model import Model  # type: ignore
            from vosk_tts.synth import Synth  # type: ignore
            
            self._Model = Model
            self._Synth = Synth
            self._available = True
            logger.info("VOSK TTS backend available")
            
            # Check for GPU dependencies
            self._check_gpu_support()
            
        except ImportError as e:
            logger.warning(f"VOSK TTS dependencies not available: {e}")
            logger.info("Install with: uv add vosk-tts")
            self._Model = None
            self._Synth = None
            
    def _check_gpu_support(self) -> None:
        """Check if GPU acceleration is available"""
        try:
            import torch  # type: ignore
            import onnxruntime  # type: ignore
            from importlib.metadata import distributions  # type: ignore
            
            # Check for onnxruntime-gpu
            installed = {
                dist.metadata['Name'].lower() 
                for dist in distributions() 
                if dist.metadata['Name'].lower().startswith('onnxruntime-gpu')
            }
            
            if installed and torch.cuda.is_available():
                self._gpu_available = True
                logger.info("GPU acceleration available for VOSK TTS")
            else:
                logger.info("GPU acceleration not available for VOSK TTS")
                
        except ImportError:
            logger.debug("GPU dependencies not available")
            
    def is_available(self) -> bool:
        """Check if VOSK TTS backend is available"""
        return self._available
        
    async def initialize(self, core) -> None:
        """Initialize the TTS plugin"""
        await super().initialize(core)
        
        if not self._available:
            logger.warning("VOSK TTS plugin initialized but dependencies missing")
            return
            
        try:
            # Load model asynchronously
            await self._load_model_async()
            
            logger.info("VOSK TTS plugin initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize VOSK TTS: {e}")
            self._available = False
            
    async def speak(self, text: str, **kwargs) -> None:
        """
        Convert text to speech and play it.
        
        Args:
            text: Text to convert to speech
            **kwargs: speaker_id (int), model_id (str)
        """
        if not self._available or not self._model or not self._synth:
            raise RuntimeError("VOSK TTS backend not available")
            
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
            logger.error(f"Failed to speak text with VOSK TTS: {e}")
            raise RuntimeError(f"TTS failed: {e}")
            
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """
        Convert text to speech and save to file.
        
        Args:
            text: Text to convert to speech
            output_path: Where to save the audio file
            **kwargs: speaker_id (int)
        """
        if not self._available or not self._model or not self._synth:
            raise RuntimeError("VOSK TTS backend not available")
            
        try:
            # Extract parameters
            speaker_id = kwargs.get('speaker_id', self._settings['speakerId'])
            
            # Validate speaker ID
            if speaker_id not in self._speaker_ids:
                logger.warning(f"Invalid speaker ID: {speaker_id}, using default: {self._settings['speakerId']}")
                speaker_id = self._settings['speakerId']
                
            # Normalize text
            processed_text = await self._normalize_text_async(text)
            
            logger.debug(f"Generating VOSK TTS with speaker_id: {speaker_id}")
            
            # Generate speech asynchronously
            await self._generate_speech_async(processed_text, output_path, speaker_id)
            
        except Exception as e:
            logger.error(f"Failed to generate speech file with VOSK TTS: {e}")
            raise RuntimeError(f"TTS file generation failed: {e}")
            
    def get_supported_voices(self) -> List[str]:
        """Get list of available voices"""
        if not self._available:
            return []
        return [f"{idx}: {name}" for idx, name in self._speaker_names.items()]
        
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes"""
        return ['ru-RU']
        
    def get_voice_settings(self) -> Dict[str, Any]:
        """Get current voice settings"""
        settings = self._settings.copy()
        settings['gpu_available'] = self._gpu_available
        return settings
        
    async def set_voice_settings(self, **settings) -> None:
        """Update voice settings"""
        for key, value in settings.items():
            if key in self._settings:
                if key == 'useGPU' and value and not self._gpu_available:
                    logger.warning("GPU acceleration requested but not available")
                    continue
                    
                self._settings[key] = value
                logger.debug(f"Updated VOSK TTS setting {key} = {value}")
                
                # Reload model if critical settings changed
                if key in ['modelId', 'useGPU']:
                    logger.info("Reloading VOSK TTS model due to setting change")
                    await self._load_model_async()
                    
            else:
                logger.warning(f"Unknown VOSK TTS setting: {key}")
                
    async def test_speech(self) -> bool:
        """Test the TTS engine with a simple phrase"""
        if not self._available:
            return False
            
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                
            try:
                await self.to_file("Тест синтеза речи VOSK", temp_path)
                # Check if file was created and has content
                return temp_path.exists() and temp_path.stat().st_size > 0
            finally:
                if temp_path.exists():
                    temp_path.unlink()
                    
        except Exception as e:
            logger.error(f"VOSK TTS test failed: {e}")
            return False
            
    async def _load_model_async(self) -> None:
        """Load VOSK TTS model asynchronously"""
        if not self._Model or not self._Synth:
            return
            
        model_id = self._settings['modelId']
        use_gpu = self._settings['useGPU'] and self._gpu_available
        
        logger.info(f"Loading VOSK TTS model: {model_id} (GPU: {use_gpu})")
        
        start_time = time()
        await asyncio.to_thread(self._load_model_blocking, model_id, use_gpu)
        end_time = time()
        
        logger.info(f"VOSK TTS model loaded in {end_time - start_time:.1f} seconds")
        
    def _load_model_blocking(self, model_id: str, use_gpu: bool) -> None:
        """Load model in blocking mode (called from thread)"""
        if not self._Model or not self._Synth:
            return
            
        try:
            # Create model
            self._model = self._Model(model_name=model_id)
            
            # Log GPU providers if available
            if use_gpu and hasattr(self._model, 'onnx') and hasattr(self._model.onnx, '_providers'):
                logger.debug(f"VOSK TTS providers: {self._model.onnx._providers}")
                
            # Create synthesizer
            self._synth = self._Synth(self._model)
            
            logger.info("VOSK TTS model and synthesizer ready")
            
        except Exception as e:
            logger.error(f"Failed to load VOSK TTS model: {e}")
            raise
            
    async def _normalize_text_async(self, text: str) -> str:
        """Normalize text asynchronously"""
        # Basic text normalization
        normalized = text
        
        # Use core normalization if available
        if self.core and hasattr(self.core, 'normalize'):
            try:
                normalized = await asyncio.to_thread(self.core.normalize, text)
            except Exception as e:
                logger.debug(f"Text normalization failed, using original: {e}")
                
        return normalized
        
    async def _generate_speech_async(self, text: str, output_path: Path, speaker_id: int) -> None:
        """Generate speech asynchronously"""
        await asyncio.to_thread(self._generate_speech_blocking, text, output_path, speaker_id)
        
    def _generate_speech_blocking(self, text: str, output_path: Path, speaker_id: int) -> None:
        """Generate speech in blocking mode (called from thread)"""
        if not self._synth:
            raise RuntimeError("VOSK TTS synthesizer not loaded")
            
        try:
            # Generate speech to file
            self._synth.synth(text, str(output_path), speaker_id=speaker_id)
            
            logger.debug(f"VOSK TTS speech generated: {output_path}")
            
        except Exception as e:
            logger.error(f"VOSK TTS speech generation error: {e}")
            raise 