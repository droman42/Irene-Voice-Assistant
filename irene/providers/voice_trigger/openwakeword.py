"""
OpenWakeWord Voice Trigger Provider

Primary voice trigger provider using OpenWakeWord for wake word detection.
Supports multiple wake words and custom models.
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional
import time

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
        self.model_paths = config.get('model_paths', {})
        self.chunk_size = config.get('chunk_size', 1280)  # 80ms at 16kHz
        self.n_samples_per_prediction = self.chunk_size
        
        # Available wake words and their default models
        self.available_models = {
            'alexa': 'alexa_v0.1.onnx',
            'hey_jarvis': 'hey_jarvis_v0.1.onnx', 
            'irene': 'custom_irene_v0.1.onnx',  # Custom model
            'jarvis': 'hey_jarvis_v0.1.onnx'    # Alias for hey_jarvis
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
        """Initialize the OpenWakeWord model with selected wake words."""
        try:
            # Import OpenWakeWord
            openwakeword = safe_import('openwakeword')
            if openwakeword is None:
                raise ImportError("openwakeword not available")
            
            from openwakeword import Model
            
            # Determine which models to load
            models_to_load = []
            for wake_word in self.wake_words:
                if wake_word in self.available_models:
                    model_name = self.available_models[wake_word]
                    if wake_word in self.model_paths:
                        # Use custom model path
                        models_to_load.append(self.model_paths[wake_word])
                    else:
                        # Use default model name (OpenWakeWord will download if needed)
                        models_to_load.append(model_name)
                else:
                    self.logger.warning(f"Wake word '{wake_word}' not supported by OpenWakeWord")
            
            if not models_to_load:
                raise ValueError("No valid wake word models found")
            
            # Initialize OpenWakeWord model
            self.logger.info(f"Initializing OpenWakeWord with models: {models_to_load}")
            self.oww = Model(
                wakeword_models=models_to_load,
                inference_framework=self.inference_framework
            )
            
            self.logger.info("OpenWakeWord model initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenWakeWord: {e}")
            self.oww = None
            raise
    
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
                self.logger.debug(f"Wake word '{detected_word}' detected with confidence {best_score:.3f}")
            
            return WakeWordResult(
                detected=detected,
                confidence=best_score,
                word=detected_word if detected else None,
                timestamp=audio_data.timestamp
            )
            
        except Exception as e:
            self.logger.error(f"Wake word detection failed: {e}")
            return WakeWordResult(
                detected=False,
                confidence=0.0,
                timestamp=audio_data.timestamp
            )
    
    def _get_model_key(self, wake_word: str) -> str:
        """Get the model key for a wake word."""
        # OpenWakeWord uses model names as keys in predictions
        if wake_word in self.available_models:
            return self.available_models[wake_word].replace('.onnx', '').replace('.tflite', '')
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
                "default": ["irene", "jarvis"],
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
            self.logger.info("OpenWakeWord cleaned up") 