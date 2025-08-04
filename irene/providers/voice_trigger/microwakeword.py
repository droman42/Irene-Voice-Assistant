"""
microWakeWord Voice Trigger Provider

Voice trigger provider using microWakeWord for custom wake word detection.
Optimized for low-power devices with TensorFlow Lite for Microcontrollers support.

Based on: https://github.com/kahrendt/microWakeWord
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional
import tempfile
import os
from pathlib import Path

from .base import VoiceTriggerProvider
from ...intents.models import AudioData, WakeWordResult
from ...utils.loader import safe_import

logger = logging.getLogger(__name__)


class MicroWakeWordProvider(VoiceTriggerProvider):
    """
    microWakeWord provider for custom wake word detection.
    
    Features:
    - TensorFlow Lite streaming inference
    - 40 spectrogram features every 10ms
    - Low-power optimized for microcontrollers
    - Custom model support
    - Real-time audio processing at 16kHz
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.tf_lite = None
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        
        # microWakeWord specific configuration
        self.model_path = config.get('model_path')
        self.feature_buffer_size = config.get('feature_buffer_size', 49)  # 49 * 10ms = 490ms
        self.stride_duration_ms = config.get('stride_duration_ms', 10)
        self.window_duration_ms = config.get('window_duration_ms', 30)
        self.num_mfcc_features = config.get('num_mfcc_features', 40)
        self.detection_window_size = config.get('detection_window_size', 3)  # Consecutive detections needed
        
        # Model configuration
        self.available_models = config.get('available_models', {
            'irene': 'irene_model.tflite',
            'jarvis': 'jarvis_model.tflite',
            'hey_irene': 'hey_irene_model.tflite'
        })
        
        # Audio preprocessing
        self.feature_buffer = np.zeros((self.feature_buffer_size, self.num_mfcc_features), dtype=np.float32)
        self.detection_buffer = []
        
        # Performance tracking
        self.inference_time_ms = 0
        self.total_inferences = 0
    
    def get_provider_name(self) -> str:
        return "microwakeword"
    
    async def is_available(self) -> bool:
        """Check if microWakeWord dependencies are available."""
        try:
            # Check TensorFlow Lite Runtime (lightweight)
            tflite = safe_import('tflite_runtime.interpreter')
            if tflite is None:
                # Fallback to full tensorflow if available
                tflite = safe_import('tensorflow.lite')
                if tflite is None:
                    self._set_status(self.status.__class__.UNAVAILABLE, "tflite-runtime or tensorflow package not installed")
                    return False
            
            # Check numpy
            numpy = safe_import('numpy')
            if numpy is None:
                self._set_status(self.status.__class__.UNAVAILABLE, "numpy package not installed")
                return False
            
            # Check if model file exists
            if self.model_path and not Path(self.model_path).exists():
                self._set_status(self.status.__class__.UNAVAILABLE, f"Model file not found: {self.model_path}")
                return False
            
            # Try to initialize the model
            if self.interpreter is None:
                await self._initialize_model()
            
            return self.interpreter is not None
            
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"microWakeWord initialization failed: {e}")
            return False
    
    async def _do_initialize(self) -> None:
        """Initialize microWakeWord model."""
        await self._initialize_model()
    
    async def _initialize_model(self):
        """Initialize the TensorFlow Lite model."""
        try:
            # Import TensorFlow Lite (prefer lightweight runtime)
            tflite_module = safe_import('tflite_runtime.interpreter')
            if tflite_module is not None:
                # Use lightweight tflite-runtime
                Interpreter = tflite_module.Interpreter
                logger.info("Using tflite-runtime (lightweight ~50MB)")
            else:
                # Fallback to full tensorflow
                tf = safe_import('tensorflow')
                if tf is None:
                    raise ImportError("Neither tflite-runtime nor tensorflow available")
                Interpreter = tf.lite.Interpreter
                logger.info("Using tensorflow.lite (full package ~800MB)")
            
            # Load model
            model_path = self._get_model_path()
            if not model_path or not Path(model_path).exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")
            
            logger.info(f"Loading microWakeWord model from: {model_path}")
            
            # Initialize TensorFlow Lite interpreter
            self.interpreter = Interpreter(model_path=str(model_path))
            self.interpreter.allocate_tensors()
            
            # Get input and output details
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            # Validate model input/output shapes
            expected_input_shape = [1, self.feature_buffer_size, self.num_mfcc_features]
            actual_input_shape = self.input_details[0]['shape'].tolist()
            
            if actual_input_shape != expected_input_shape:
                logger.warning(f"Model input shape {actual_input_shape} != expected {expected_input_shape}")
                # Update buffer size to match model
                if len(actual_input_shape) >= 2:
                    self.feature_buffer_size = actual_input_shape[1]
                    self.num_mfcc_features = actual_input_shape[2] if len(actual_input_shape) >= 3 else 40
                    self.feature_buffer = np.zeros((self.feature_buffer_size, self.num_mfcc_features), dtype=np.float32)
            
            logger.info(f"microWakeWord model initialized successfully")
            logger.info(f"Input shape: {self.input_details[0]['shape']}")
            logger.info(f"Output shape: {self.output_details[0]['shape']}")
            
        except Exception as e:
            logger.error(f"Failed to initialize microWakeWord model: {e}")
            self.interpreter = None
            raise
    
    def _get_model_path(self) -> Optional[str]:
        """Get the model path for the current wake words."""
        if self.model_path:
            return self.model_path
        
        # Try to find a model for the first wake word
        for wake_word in self.wake_words:
            if wake_word in self.available_models:
                return self.available_models[wake_word]
        
        return None
    
    async def detect_wake_word(self, audio_data: AudioData) -> WakeWordResult:
        """
        Detect wake word using microWakeWord streaming inference.
        
        Args:
            audio_data: Audio data to analyze (16kHz, 16-bit PCM)
            
        Returns:
            WakeWordResult with detection status and metadata
        """
        if not self.interpreter:
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
            
            # Ensure correct sample rate
            if audio_data.sample_rate != 16000:
                logger.warning(f"Audio sample rate {audio_data.sample_rate} != 16000, resampling needed")
                # For now, just log warning - proper resampling would require additional deps
            
            # Convert to float32 and normalize
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # Extract MFCC features (simplified - in production would use micro_speech preprocessor)
            features = self._extract_features(audio_float)
            
            if features is None:
                return WakeWordResult(detected=False, confidence=0.0, timestamp=audio_data.timestamp)
            
            # Update feature buffer (sliding window)
            self.feature_buffer = np.roll(self.feature_buffer, -1, axis=0)
            self.feature_buffer[-1] = features
            
            # Run inference
            confidence = await self._run_inference()
            
            # Apply detection logic (require multiple consecutive detections)
            self.detection_buffer.append(confidence > self.threshold)
            if len(self.detection_buffer) > self.detection_window_size:
                self.detection_buffer.pop(0)
            
            # Check if we have enough consecutive detections
            detected = (len(self.detection_buffer) >= self.detection_window_size and 
                       all(self.detection_buffer))
            
            if detected:
                logger.debug(f"Wake word detected with confidence {confidence:.3f}")
                # Clear detection buffer to avoid repeated triggers
                self.detection_buffer.clear()
            
            return WakeWordResult(
                detected=detected,
                confidence=confidence,
                word=self.wake_words[0] if detected and self.wake_words else None,
                timestamp=audio_data.timestamp,
                metadata={
                    'provider': 'microwakeword',
                    'inference_time_ms': self.inference_time_ms,
                    'consecutive_detections': sum(self.detection_buffer),
                    'model_path': self._get_model_path()
                }
            )
            
        except Exception as e:
            logger.error(f"microWakeWord detection failed: {e}")
            return WakeWordResult(
                detected=False,
                confidence=0.0,
                timestamp=audio_data.timestamp
            )
    
    def _extract_features(self, audio: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract MFCC features from audio.
        
        Note: This is a simplified implementation. Production usage should use
        the micro_speech preprocessor for consistency with microWakeWord training.
        """
        try:
            # This is a placeholder - real implementation would use:
            # - micro_speech preprocessor from TensorFlow
            # - 40 MFCC features over 30ms windows
            # - 10ms stride
            # - Noise suppression and AGC
            
            # For now, return dummy features matching expected shape
            # In production, integrate with tensorflow/lite/micro/examples/micro_speech
            if len(audio) < 480:  # 30ms at 16kHz
                return None
            
            # Simplified feature extraction (placeholder)
            # Real implementation should use micro_speech preprocessor
            features = np.random.random(self.num_mfcc_features).astype(np.float32)
            
            # Apply some basic processing to make it more realistic
            features = features * 0.1 - 0.05  # Center around 0
            
            return features
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return None
    
    async def _run_inference(self) -> float:
        """Run TensorFlow Lite inference on current feature buffer."""
        import time
        
        start_time = time.time()
        
        try:
            # Prepare input tensor
            input_data = np.expand_dims(self.feature_buffer, axis=0)  # Add batch dimension
            
            # Set input tensor
            self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
            
            # Run inference
            self.interpreter.invoke()
            
            # Get output
            output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
            
            # Extract confidence (assuming output is probability)
            confidence = float(output_data[0][0]) if output_data.size > 0 else 0.0
            
            # Update performance metrics
            self.inference_time_ms = (time.time() - start_time) * 1000
            self.total_inferences += 1
            
            return confidence
            
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return 0.0
    
    def get_supported_wake_words(self) -> List[str]:
        """Get list of wake words supported by available models."""
        return list(self.available_models.keys())
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get parameter schema for microWakeWord provider."""
        return {
            "wake_words": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["irene"],
                "description": "List of wake words to detect (must have corresponding models)"
            },
            "threshold": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.8,
                "description": "Detection threshold (0.0 - 1.0)"
            },
            "model_path": {
                "type": "string",
                "description": "Path to TensorFlow Lite model file (.tflite)"
            },
            "available_models": {
                "type": "object",
                "description": "Mapping of wake words to model files",
                "additionalProperties": {"type": "string"}
            },
            "feature_buffer_size": {
                "type": "integer",
                "minimum": 10,
                "maximum": 100,
                "default": 49,
                "description": "Size of feature buffer (number of 10ms windows)"
            },
            "detection_window_size": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "default": 3,
                "description": "Number of consecutive detections required"
            },
            "num_mfcc_features": {
                "type": "integer",
                "minimum": 10,
                "maximum": 80,
                "default": 40,
                "description": "Number of MFCC features"
            }
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get microWakeWord provider capabilities."""
        capabilities = super().get_capabilities()
        capabilities.update({
            "custom_models": True,
            "tensorflow_lite": True,
            "microcontroller_optimized": True,
            "streaming": True,
            "offline": True,
            "low_power": True,
            "feature_extraction": "mfcc",
            "sample_rates": [16000],
            "formats": ["pcm16"],
            "languages": ["custom"],  # Depends on trained models
            "inference_framework": "tensorflow_lite",
            "model_format": ".tflite",
            "quantization": True,
            "real_time": True
        })
        return capabilities
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            "total_inferences": self.total_inferences,
            "average_inference_time_ms": self.inference_time_ms,
            "feature_buffer_size": self.feature_buffer_size,
            "model_loaded": self.interpreter is not None,
            "model_path": self._get_model_path()
        }
    
    async def cleanup(self) -> None:
        """Clean up microWakeWord resources."""
        if self.interpreter:
            # TensorFlow Lite interpreter doesn't need explicit cleanup
            self.interpreter = None
            self.input_details = None
            self.output_details = None
            
        # Clear buffers
        self.feature_buffer = np.zeros((self.feature_buffer_size, self.num_mfcc_features), dtype=np.float32)
        self.detection_buffer.clear()
        
        logger.info("microWakeWord cleaned up") 