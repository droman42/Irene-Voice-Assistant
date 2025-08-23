"""
OpenWakeWord Voice Trigger Provider

Primary voice trigger provider using OpenWakeWord for wake word detection.
Supports multiple wake words and custom models with asset management integration.
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional
import time
from pathlib import Path

from .base import VoiceTriggerProvider
from ...intents.models import AudioData, WakeWordResult
from ...utils.loader import safe_import

logger = logging.getLogger(__name__)


class OpenWakeWordProvider(VoiceTriggerProvider):
    """OpenWakeWord provider - recommended for general use"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.oww = None
        self.model = None
        self.inference_framework = config.get('inference_framework', 'tflite')
        self.chunk_size = config.get('chunk_size', 1280)  # 80ms at 16kHz
        self.n_samples_per_prediction = self.chunk_size
        
        # Asset management integration - single source of truth
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Available wake words and their default models (mapped to asset registry)
        self.available_models = {
            'alexa': 'alexa_v0.1',
            'hey_jarvis': 'hey_jarvis_v0.1', 
            'hey_mycroft': 'hey_mycroft_v0.1',
            'jarvis': 'hey_jarvis_v0.1'    # Alias for hey_jarvis
        }
    
    def get_provider_name(self) -> str:
        return "openwakeword"
    
    async def is_available(self) -> bool:
        """Check if OpenWakeWord is available and can be initialized."""
        try:
            # Try importing OpenWakeWord
            openwakeword = safe_import('openwakeword')
            if openwakeword is None:
                self._set_status(self.status.__class__.UNAVAILABLE, "openwakeword package not installed")
                return False
            
            # Try importing numpy (required dependency)
            numpy = safe_import('numpy')
            if numpy is None:
                self._set_status(self.status.__class__.UNAVAILABLE, "numpy package not installed")
                return False
            
            # Check if we can initialize the model
            if self.oww is None:
                await self._initialize_model()
            
            return self.oww is not None
            
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"OpenWakeWord initialization failed: {e}")
            return False
    
    async def _do_initialize(self) -> None:
        """Initialize OpenWakeWord model."""
        await self._initialize_model()
    
    async def _initialize_model(self):
        """Initialize the OpenWakeWord model with selected wake words using asset management."""
        try:
            # Import OpenWakeWord
            openwakeword = safe_import('openwakeword')
            if openwakeword is None:
                raise ImportError("openwakeword not available")
            
            from openwakeword import Model
            
            # Determine which models to load using asset management - unified pattern
            models_to_load = []
            for wake_word in self.wake_words:
                if wake_word in self.available_models:
                    # Use asset management for all models
                    model_id = self.available_models[wake_word]
                    try:
                        # Get model info and attempt download
                        model_info = self.asset_manager.get_model_info("openwakeword", model_id)
                        if model_info:
                            logger.info(f"Loading OpenWakeWord model {model_id} for '{wake_word}' (size: {model_info.get('size', 'unknown')})")
                        
                        # Try asset manager download first (will handle 'auto' URLs properly)
                        model_path = await self._get_model_via_asset_manager(model_id)
                        if model_path and model_path.exists():
                            models_to_load.append(str(model_path))
                            logger.info(f"Using asset-managed model for '{wake_word}': {model_path}")
                        else:
                            # Fallback to OpenWakeWord's built-in download
                            # Try the model_id directly first (OpenWakeWord might handle extensions automatically)
                            models_to_load.append(model_id)
                            logger.info(f"Falling back to OpenWakeWord auto-download for '{wake_word}': {model_id}")
                            
                    except Exception as e:
                        logger.warning(f"Asset manager failed for '{wake_word}', using OpenWakeWord auto-download: {e}")
                        # Fallback to OpenWakeWord's built-in download
                        # Try the model_id directly first (OpenWakeWord might handle extensions automatically)
                        models_to_load.append(model_id)
                else:
                    logger.warning(f"Wake word '{wake_word}' not supported by OpenWakeWord")
                    # For unsupported wake words like 'irene', suggest alternatives or provide fallback
                    if wake_word.lower() == 'irene':
                        logger.info("Suggestion: Consider using 'hey_jarvis' or 'alexa' as wake words, or switch to microwakeword provider for custom models")
            
            if not models_to_load:
                raise ValueError("No valid wake word models found")
            
            # Initialize OpenWakeWord model
            logger.info(f"Initializing OpenWakeWord with models: {models_to_load}")
            self.oww = Model(
                wakeword_models=models_to_load,
                inference_framework=self.inference_framework
            )
            
            logger.info("OpenWakeWord model initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenWakeWord: {e}")
            self.oww = None
            raise
    
    async def _get_model_via_asset_manager(self, model_id: str) -> Optional[Path]:
        """Get model via asset manager with fallback to OpenWakeWord's auto downloads."""
        try:
            # Try to download using asset manager (provider has real URLs configured)
            return await self.asset_manager.download_model("openwakeword", model_id)
        except Exception as e:
            logger.debug(f"Asset manager download failed for {model_id}: {e}")
            # Return None to trigger OpenWakeWord's own fallback download mechanism
            return None
    
    async def detect_wake_word(self, audio_data: AudioData) -> WakeWordResult:
        """
        Detect wake word in audio data using OpenWakeWord.
        
        Args:
            audio_data: Audio data to analyze
            
        Returns:
            WakeWordResult with detection status and metadata
        """
        if not self.oww:
            return WakeWordResult(
                detected=False,
                confidence=0.0,
                timestamp=audio_data.timestamp
            )
        
        try:
            # Convert audio data to numpy array
            if isinstance(audio_data.data, bytes):
                audio_array = np.frombuffer(audio_data.data, dtype=np.int16)
            else:
                audio_array = np.array(audio_data.data, dtype=np.int16)
            
            # Ensure we have the right sample rate
            if audio_data.sample_rate != 16000:
                self.logger.warning(f"Audio sample rate {audio_data.sample_rate} != 16000, resampling may be needed")
            
            # Convert to float32 and normalize
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # Process audio chunk by chunk
            predictions = []
            for i in range(0, len(audio_float), self.chunk_size):
                chunk = audio_float[i:i + self.chunk_size]
                
                # Pad chunk if too short
                if len(chunk) < self.chunk_size:
                    chunk = np.pad(chunk, (0, self.chunk_size - len(chunk)), mode='constant')
                
                # Get prediction from OpenWakeWord
                prediction = self.oww.predict(chunk)
                predictions.append(prediction)
            
            # Find the highest confidence detection
            best_score = 0.0
            detected_word = None
            
            for prediction in predictions:
                for wake_word in self.wake_words:
                    # Map wake word to model key
                    model_key = self._get_model_key(wake_word)
                    if model_key in prediction:
                        score = prediction[model_key]
                        if score > best_score:
                            best_score = score
                            detected_word = wake_word
            
            # Check if detection exceeds threshold
            detected = best_score > self.threshold
            
            if detected:
                logger.debug(f"Wake word '{detected_word}' detected with confidence {best_score:.3f}")
            
            return WakeWordResult(
                detected=detected,
                confidence=best_score,
                word=detected_word if detected else None,
                timestamp=audio_data.timestamp
            )
            
        except Exception as e:
            logger.error(f"Wake word detection failed: {e}")
            return WakeWordResult(
                detected=False,
                confidence=0.0,
                timestamp=audio_data.timestamp
            )
    
    def _get_model_key(self, wake_word: str) -> str:
        """Get the model key for a wake word."""
        # OpenWakeWord uses model names as keys in predictions
        if wake_word in self.available_models:
            # Model IDs are now clean without extensions, but OpenWakeWord still might use filename-based keys
            model_id = self.available_models[wake_word]
            # Return the model_id which should match OpenWakeWord's internal key format
            return model_id
        return wake_word
    
    def get_supported_wake_words(self) -> List[str]:
        """Get list of wake words supported by OpenWakeWord."""
        return list(self.available_models.keys())
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get parameter schema for OpenWakeWord provider."""
        return {
            "wake_words": {
                "type": "array",
                "items": {"type": "string", "enum": self.get_supported_wake_words()},
                "default": ["alexa", "jarvis"],
                "description": "List of wake words to detect"
            },
            "threshold": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.8,
                "description": "Detection threshold (0.0 - 1.0)"
            },
            "inference_framework": {
                "type": "string",
                "enum": ["tflite", "onnx"],
                "default": "tflite",
                "description": "Inference framework to use"
            },
            "model_paths": {
                "type": "object",
                "description": "Custom model paths for wake words",
                "additionalProperties": {"type": "string"}
            },
            "chunk_size": {
                "type": "integer",
                "minimum": 160,
                "maximum": 3200,
                "default": 1280,
                "description": "Audio chunk size for processing (samples)"
            }
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get OpenWakeWord provider capabilities."""
        capabilities = super().get_capabilities()
        capabilities.update({
            "custom_models": True,
            "multiple_frameworks": True,
            "frameworks": ["tflite", "onnx"],
            "streaming": True,
            "offline": True,
            "languages": ["en"],  # Most OpenWakeWord models are English
            "model_download": True  # OpenWakeWord can auto-download models
        })
        return capabilities
    
    async def cleanup(self) -> None:
        """Clean up OpenWakeWord resources."""
        if self.oww:
            # OpenWakeWord doesn't have explicit cleanup, but we can clear the reference
            self.oww = None
            logger.info("OpenWakeWord cleaned up") 
    
    # Asset configuration methods (TODO #4 Phase 1)
    @classmethod
    def _get_default_extension(cls) -> str:
        """OpenWakeWord uses .onnx or .tflite models"""
        return ".tflite"
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """OpenWakeWord models directory"""
        return "openwakeword"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """OpenWakeWord doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """OpenWakeWord uses models cache"""
        return ["models", "runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """OpenWakeWord model URLs"""
        return {
            "alexa_v0.1": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/alexa_v0.1.tflite",
            "hey_jarvis_v0.1": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_jarvis_v0.1.tflite",
            "hey_mycroft_v0.1": "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_mycroft_v0.1.tflite"
        }
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """OpenWakeWord requires specific voice trigger libraries"""
        return ["openwakeword>=0.6.0", "numpy>=1.21.0", "aiohttp>=3.8.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """OpenWakeWord has no system dependencies - pure Python/TensorFlow"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """OpenWakeWord supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    async def initialize(self) -> None:
        """Initialize OpenWakeWord detection"""
        if not await self.is_available():
            raise RuntimeError("OpenWakeWord dependencies not available")
        
        logger.info("OpenWakeWord provider initialized") 