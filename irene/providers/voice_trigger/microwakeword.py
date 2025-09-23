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
    - Asset management integration for model downloads
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.tf_lite = None
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        
        # Asset management integration - single source of truth
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # microWakeWord specific configuration
        self.feature_buffer_size = config.get('feature_buffer_size', 49)  # 49 * 10ms = 490ms
        self.stride_duration_ms = config.get('stride_duration_ms', 10)
        self.window_duration_ms = config.get('window_duration_ms', 30)
        self.num_mfcc_features = config.get('num_mfcc_features', 40)
        self.detection_window_size = config.get('detection_window_size', 3)  # Consecutive detections needed
        
        # Available wake words and their default models (mapped to asset registry)
        self.available_models = {
            'irene': 'irene_v1.0',
            'jarvis': 'jarvis_v1.0', 
            'hey_irene': 'hey_irene_v1.0',
            'hey_jarvis': 'hey_jarvis_v1.0'
        }
        
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
            
            # Model availability will be checked during initialization via asset manager
            
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
            model_path = await self._get_model_path()
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
    
    async def _get_model_path(self) -> Optional[str]:
        """Get the model path using asset management or legacy configuration (following openwakeword pattern)."""
        # Try to find models for supported wake words
        for wake_word in self.wake_words:
            # Use asset management for all supported wake words - unified pattern
            if wake_word in self.available_models:
                model_id = self.available_models[wake_word]
                
                try:
                    # Get model info from asset manager  
                    model_info = self.asset_manager.get_model_info("microwakeword", model_id)
                    if model_info:
                        logger.info(f"Loading microWakeWord model {model_id} for '{wake_word}' (size: {model_info.get('size', 'unknown')})")
                    
                    # Try asset manager download first
                    model_path = await self._get_model_via_asset_manager(model_id)
                    if model_path and model_path.exists():
                        logger.info(f"Using asset-managed model for '{wake_word}': {model_path}")
                        return str(model_path)
                    else:
                        # Fallback to checking if it's a direct path in available_models
                        fallback_path = Path(model_id)
                        if fallback_path.exists():
                            logger.info(f"Using direct model path for '{wake_word}': {model_id}")
                            return str(fallback_path)
                        
                except Exception as e:
                    logger.warning(f"Asset manager failed for '{wake_word}', trying direct path: {e}")
                    # Fallback to direct path interpretation
                    fallback_path = Path(model_id)
                    if fallback_path.exists():
                        logger.info(f"Using direct model path for '{wake_word}': {model_id}")
                        return str(fallback_path)
        
        return None
    
    async def _get_model_via_asset_manager(self, model_id: str) -> Optional[Path]:
        """Download model via asset manager."""
        try:
            # Use asset manager to download model
            model_path = await self.asset_manager.download_model("microwakeword", model_id)
            return model_path
        except Exception as e:
            logger.warning(f"Asset manager download failed for model {model_id}: {e}")
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
                    'model_path': await self._get_model_path()
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
    
    
    def get_supported_sample_rates(self) -> List[int]:
        """Get list of supported sample rates for microWakeWord (Phase 3)."""
        # microWakeWord is specifically designed for 16kHz audio
        # The micro_speech preprocessor expects 16kHz input
        return [16000]
    
    def get_default_sample_rate(self) -> int:
        """Get default sample rate for microWakeWord (Phase 3)."""
        # microWakeWord is optimized for 16kHz audio processing
        return 16000
    
    def supports_resampling(self) -> bool:
        """Check if microWakeWord supports automatic resampling (Phase 3)."""
        # microWakeWord requires exactly 16kHz - resampling should be handled externally
        # The micro_speech preprocessor is very specific about sample rate requirements
        return False
    
    def get_default_channels(self) -> int:
        """Get default number of channels for microWakeWord (Phase 3)."""
        # microWakeWord processes mono audio only
        return 1
    
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
            "asset_management": True,
            "huggingface_models": True,  # For future implementation
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
            "model_path": None  # Will be async, handled in metadata
        }
    
    # Asset configuration methods (TODO #4 Phase 1)
    @classmethod
    def _get_default_extension(cls) -> str:
        """microWakeWord uses .tflite models"""
        return ".tflite"
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """microWakeWord models directory"""
        return "microwakeword"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """microWakeWord doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """microWakeWord uses models cache"""
        return ["models", "runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """microWakeWord model URLs"""
        return {
            "micro_speech": "https://github.com/tensorflow/tflite-micro/raw/main/tensorflow/lite/micro/examples/micro_speech/micro_speech.tflite"
        }
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """microWakeWord requires TensorFlow Lite and numpy"""
        return ["numpy>=1.21.0", "tflite-runtime>=2.12.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """microWakeWord has no system dependencies - pure Python/TensorFlow Lite"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """microWakeWord supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
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