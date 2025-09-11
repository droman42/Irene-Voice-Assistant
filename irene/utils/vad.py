"""
Voice Activity Detection (VAD) Module

Provides standalone VAD implementation with energy-based detection
for the Irene Voice Assistant audio processing pipeline.

Phase 5 Optimizations:
- Efficient numpy operations with pre-allocated arrays
- Caching for repeated calculations
- Memory management for audio buffers
- Real-time processing optimizations
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Union, Dict, List
from functools import lru_cache
import numpy as np

from ..intents.models import AudioData

logger = logging.getLogger(__name__)

# Phase 5: Performance optimization constants
NUMPY_DTYPE = np.float32  # Use float32 for better performance
CACHE_SIZE = 256  # LRU cache size for repeated calculations
MAX_ENERGY_HISTORY = 100  # Maximum history for adaptive algorithms


@dataclass
class VADResult:
    """Voice activity detection result with Phase 5 optimizations"""
    is_voice: bool
    confidence: float
    energy_level: float
    timestamp: float = 0.0
    processing_time_ms: float = 0.0
    
    # Phase 5: Additional metrics for optimization tracking
    zcr_value: float = 0.0
    adaptive_threshold: float = 0.0
    cache_hit: bool = False


@dataclass
class VADPerformanceCache:
    """Cache for VAD performance optimizations"""
    energy_cache: Dict[int, float] = field(default_factory=dict)
    zcr_cache: Dict[int, float] = field(default_factory=dict)
    array_cache: Dict[int, np.ndarray] = field(default_factory=dict)
    cache_hits: int = 0
    cache_misses: int = 0
    
    def get_cache_efficiency(self) -> float:
        """Calculate cache hit efficiency"""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


# Phase 5: Optimized calculation functions with caching
@lru_cache(maxsize=CACHE_SIZE)
def _calculate_rms_energy_cached(data_hash: int, data_length: int) -> float:
    """Cached RMS energy calculation for repeated audio patterns"""
    # This is a placeholder for the actual cached calculation
    # The real calculation is done in calculate_rms_energy_optimized
    pass


def calculate_rms_energy_optimized(audio_data: bytes, cache: Optional[VADPerformanceCache] = None) -> tuple[float, bool]:
    """
    Optimized RMS energy calculation with caching and efficient numpy operations.
    
    Phase 5 optimizations:
    - Pre-allocated numpy arrays
    - Caching for repeated patterns
    - Efficient float32 operations
    - Memory management
    
    Args:
        audio_data: Raw audio bytes
        cache: Optional performance cache
        
    Returns:
        Tuple of (energy_value, cache_hit)
    """
    # Create hash for caching
    data_hash = hash(audio_data) if len(audio_data) < 1024 else hash(audio_data[:512] + audio_data[-512:])
    cache_hit = False
    
    # Check cache first
    if cache and data_hash in cache.energy_cache:
        cache.cache_hits += 1
        return cache.energy_cache[data_hash], True
    
    if cache:
        cache.cache_misses += 1
    
    try:
        # Efficient numpy conversion with optimized dtype
        if data_hash in (cache.array_cache if cache else {}):
            audio_array = cache.array_cache[data_hash]
        else:
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(NUMPY_DTYPE)
            if cache and len(cache.array_cache) < CACHE_SIZE:
                cache.array_cache[data_hash] = audio_array
        
        if len(audio_array) == 0:
            return 0.0, cache_hit
        
        # Optimized RMS calculation using numpy vectorization
        # Use float32 for better performance on most systems
        rms = np.sqrt(np.mean(np.square(audio_array)))
        
        # Normalize to 0.0-1.0 range
        normalized_energy = min(1.0, rms / 32768.0)
        
        # Cache result
        if cache and len(cache.energy_cache) < CACHE_SIZE:
            cache.energy_cache[data_hash] = normalized_energy
        
        return normalized_energy, cache_hit
        
    except Exception as e:
        logger.warning(f"Optimized energy calculation failed: {e}")
        return 0.0, cache_hit


def calculate_zcr_optimized(audio_data: bytes, cache: Optional[VADPerformanceCache] = None) -> tuple[float, bool]:
    """
    Optimized Zero Crossing Rate calculation with caching.
    
    Phase 5 optimizations:
    - Efficient numpy operations
    - Caching for repeated patterns
    - Vectorized sign computation
    
    Args:
        audio_data: Raw audio bytes
        cache: Optional performance cache
        
    Returns:
        Tuple of (zcr_value, cache_hit)
    """
    data_hash = hash(audio_data) if len(audio_data) < 1024 else hash(audio_data[:512] + audio_data[-512:])
    cache_hit = False
    
    # Check cache first
    if cache and data_hash in cache.zcr_cache:
        cache.cache_hits += 1
        return cache.zcr_cache[data_hash], True
    
    if cache:
        cache.cache_misses += 1
    
    try:
        # Reuse cached array if available
        if cache and data_hash in cache.array_cache:
            audio_array = cache.array_cache[data_hash]
        else:
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(NUMPY_DTYPE)
            if cache and len(cache.array_cache) < CACHE_SIZE:
                cache.array_cache[data_hash] = audio_array
        
        if len(audio_array) <= 1:
            return 0.0, cache_hit
        
        # Optimized ZCR calculation using numpy vectorization
        # Use efficient sign changes detection
        sign_changes = np.diff(np.sign(audio_array))
        zero_crossings = np.count_nonzero(sign_changes)
        
        # Normalize by frame length
        zcr = zero_crossings / (len(audio_array) - 1)
        
        # Cache result
        if cache and len(cache.zcr_cache) < CACHE_SIZE:
            cache.zcr_cache[data_hash] = zcr
        
        return zcr, cache_hit
        
    except Exception as e:
        logger.warning(f"Optimized ZCR calculation failed: {e}")
        return 0.0, cache_hit


class SimpleVAD:
    """
    Energy-based VAD with hysteresis for stable voice detection.
    
    Uses RMS energy analysis with configurable thresholds and hysteresis
    to detect voice activity while minimizing false positives from noise.
    """
    
    def __init__(self, threshold: float = 0.01, sensitivity: float = 0.5, 
                 voice_frames_required: int = 2, silence_frames_required: int = 5,
                 enable_caching: bool = True):
        """
        Initialize VAD with configurable parameters and Phase 5 optimizations.
        
        Args:
            threshold: RMS energy threshold for voice detection (0.0-1.0)
            sensitivity: Detection sensitivity multiplier (0.1-2.0)
            voice_frames_required: Consecutive voice frames to confirm voice onset
            silence_frames_required: Consecutive silence frames to confirm voice end
            enable_caching: Enable performance caching (Phase 5 optimization)
        """
        self.threshold = threshold
        self.sensitivity = sensitivity
        self.voice_frames_required = voice_frames_required
        self.silence_frames_required = silence_frames_required
        
        # Phase 5: Performance optimization components
        self.enable_caching = enable_caching
        self.performance_cache = VADPerformanceCache() if enable_caching else None
        
        # State tracking for hysteresis
        self._consecutive_voice_frames = 0
        self._consecutive_silence_frames = 0
        self._current_state = False  # False = silence, True = voice
        self._last_energy = 0.0
        
        # Adaptive threshold with memory management
        self._energy_history = []
        self._max_history_length = MAX_ENERGY_HISTORY
        
    def process_frame(self, audio_data: AudioData) -> VADResult:
        """
        Process a single audio frame and detect voice activity.
        
        Args:
            audio_data: AudioData object containing audio frame
            
        Returns:
            VADResult with detection results and confidence
        """
        start_time = time.time()
        
        # Phase 5: Use optimized energy calculation with caching
        energy_level, cache_hit = calculate_rms_energy_optimized(
            audio_data.data, 
            self.performance_cache
        )
        
        # Update energy history for adaptive threshold (future enhancement)
        self._energy_history.append(energy_level)
        if len(self._energy_history) > self._max_history_length:
            self._energy_history.pop(0)
        
        # Apply sensitivity adjustment
        adjusted_threshold = self.threshold * (2.0 - self.sensitivity)
        
        # Basic energy-based detection
        raw_detection = energy_level > adjusted_threshold
        
        # Apply hysteresis logic
        final_detection = self.apply_hysteresis(raw_detection)
        
        # Calculate confidence based on energy ratio
        if energy_level > 0:
            confidence = min(1.0, energy_level / adjusted_threshold)
        else:
            confidence = 0.0
        
        processing_time = (time.time() - start_time) * 1000
        
        return VADResult(
            is_voice=final_detection,
            confidence=confidence,
            energy_level=energy_level,
            timestamp=audio_data.timestamp,
            processing_time_ms=processing_time,
            cache_hit=cache_hit,
            adaptive_threshold=adjusted_threshold
        )
    
    def apply_hysteresis(self, current_detection: bool) -> bool:
        """
        Apply hysteresis logic to reduce false positives/negatives.
        
        Args:
            current_detection: Raw detection result for current frame
            
        Returns:
            Filtered detection result with hysteresis applied
        """
        if current_detection:
            # Voice detected in current frame
            self._consecutive_voice_frames += 1
            self._consecutive_silence_frames = 0
            
            if not self._current_state:
                # Currently in silence state, check if we have enough voice frames
                if self._consecutive_voice_frames >= self.voice_frames_required:
                    self._current_state = True
                    logger.debug(f"Voice onset detected after {self._consecutive_voice_frames} frames")
        else:
            # Silence detected in current frame  
            self._consecutive_silence_frames += 1
            self._consecutive_voice_frames = 0
            
            if self._current_state:
                # Currently in voice state, check if we have enough silence frames
                if self._consecutive_silence_frames >= self.silence_frames_required:
                    self._current_state = False
                    logger.debug(f"Voice end detected after {self._consecutive_silence_frames} frames")
        
        return self._current_state
    
    def _calculate_energy(self, audio_data: AudioData) -> float:
        """
        Calculate RMS energy of audio frame.
        
        Args:
            audio_data: AudioData object
            
        Returns:
            Normalized RMS energy (0.0-1.0)
        """
        try:
            # Convert bytes to numpy array (assuming 16-bit PCM)
            audio_array = np.frombuffer(audio_data.data, dtype=np.int16)
            
            if len(audio_array) == 0:
                return 0.0
            
            # Calculate RMS energy
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
            
            # Normalize to 0.0-1.0 range (16-bit audio range is -32768 to 32767)
            normalized_energy = rms / 32768.0
            
            return min(1.0, normalized_energy)
            
        except Exception as e:
            logger.warning(f"Error calculating audio energy: {e}")
            return 0.0
    
    def reset_state(self):
        """Reset VAD state (useful for new audio sessions)."""
        self._consecutive_voice_frames = 0
        self._consecutive_silence_frames = 0
        self._current_state = False
        self._energy_history.clear()
        logger.debug("VAD state reset")
    
    def get_adaptive_threshold(self) -> float:
        """
        Calculate adaptive threshold based on recent audio energy history.
        
        Returns:
            Suggested threshold value based on environment
        """
        if len(self._energy_history) < 10:
            return self.threshold
        
        # Calculate background noise level (10th percentile)
        sorted_history = sorted(self._energy_history)
        noise_level = sorted_history[len(sorted_history) // 10]
        
        # Set threshold at 3x background noise level
        adaptive_threshold = max(self.threshold, noise_level * 3.0)
        
        return min(1.0, adaptive_threshold)


def detect_voice_activity(audio_data: AudioData, threshold: float = 0.01) -> bool:
    """
    Main VAD function for quick integration.
    
    Simple energy-based voice activity detection without state management.
    Use this for basic VAD needs or quick testing.
    
    Args:
        audio_data: AudioData object containing audio frame
        threshold: RMS energy threshold for voice detection (0.0-1.0)
        
    Returns:
        True if voice activity detected, False otherwise
    """
    try:
        # Convert bytes to numpy array (assuming 16-bit PCM)
        audio_array = np.frombuffer(audio_data.data, dtype=np.int16)
        
        if len(audio_array) == 0:
            return False
        
        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        
        # Normalize to 0.0-1.0 range
        normalized_energy = rms / 32768.0
        
        return normalized_energy > threshold
        
    except Exception as e:
        logger.warning(f"Error in VAD detection: {e}")
        return False


def calculate_zero_crossing_rate(audio_data: AudioData) -> float:
    """
    Calculate Zero Crossing Rate for speech detection enhancement.
    
    ZCR is useful for distinguishing between voiced/unvoiced speech
    and can improve VAD accuracy when combined with energy analysis.
    
    Args:
        audio_data: AudioData object containing audio frame
        
    Returns:
        Zero crossing rate as ratio (0.0-1.0)
    """
    try:
        # Convert bytes to numpy array (assuming 16-bit PCM)
        audio_array = np.frombuffer(audio_data.data, dtype=np.int16)
        
        if len(audio_array) <= 1:
            return 0.0
        
        # Calculate zero crossings
        zero_crossings = np.sum(np.diff(np.sign(audio_array)) != 0)
        
        # Normalize by frame length
        zcr = zero_crossings / (len(audio_array) - 1)
        
        return zcr
        
    except Exception as e:
        logger.warning(f"Error calculating ZCR: {e}")
        return 0.0


class AdvancedVAD(SimpleVAD):
    """
    Advanced VAD with spectral features and adaptive thresholding.
    
    Extends SimpleVAD with additional features:
    - Zero Crossing Rate analysis
    - Spectral centroid calculation
    - Adaptive threshold adjustment
    - Environmental noise estimation
    """
    
    def __init__(self, threshold: float = 0.01, sensitivity: float = 0.5,
                 voice_frames_required: int = 2, silence_frames_required: int = 5,
                 use_zcr: bool = True, use_spectral_features: bool = False,
                 enable_caching: bool = True):
        """
        Initialize advanced VAD with additional features and Phase 5 optimizations.
        
        Args:
            threshold: Base RMS energy threshold
            sensitivity: Detection sensitivity 
            voice_frames_required: Frames needed to confirm voice onset
            silence_frames_required: Frames needed to confirm voice end
            use_zcr: Enable Zero Crossing Rate analysis
            use_spectral_features: Enable spectral feature analysis (future)
            enable_caching: Enable performance caching (Phase 5 optimization)
        """
        super().__init__(threshold, sensitivity, voice_frames_required, silence_frames_required, enable_caching)
        
        self.use_zcr = use_zcr
        self.use_spectral_features = use_spectral_features
        
        # ZCR state
        self._zcr_threshold = 0.1  # Typical ZCR threshold for speech
        
        # Adaptive threshold state
        self._noise_estimate = 0.0
        self._adaptation_rate = 0.01
        
        # Phase 5: Multi-frame smoothing for stability
        self._smoothing_window_size = 5  # Number of frames for smoothing
        self._energy_smoothing_buffer = []
        self._zcr_smoothing_buffer = []
        self._detection_smoothing_buffer = []
        
    def process_frame(self, audio_data: AudioData) -> VADResult:
        """
        Process frame with advanced features.
        
        Args:
            audio_data: AudioData object
            
        Returns:
            VADResult with enhanced detection
        """
        start_time = time.time()
        
        # Phase 5: Use optimized energy calculation with caching
        energy_level, energy_cache_hit = calculate_rms_energy_optimized(
            audio_data.data, 
            self.performance_cache
        )
        
        # Update noise estimate for adaptive threshold
        self._update_noise_estimate(energy_level)
        
        # Calculate adaptive threshold
        adaptive_threshold = max(self.threshold, self._noise_estimate * 3.0)
        
        # Apply sensitivity
        adjusted_threshold = adaptive_threshold * (2.0 - self.sensitivity)
        
        # Basic energy detection
        energy_detection = energy_level > adjusted_threshold
        
        # Phase 5: Enhance with optimized ZCR if enabled
        zcr_value = 0.0
        zcr_cache_hit = False
        if self.use_zcr:
            zcr_value, zcr_cache_hit = calculate_zcr_optimized(
                audio_data.data,
                self.performance_cache
            )
            zcr_detection = zcr_value > self._zcr_threshold
            
            # Combine energy and ZCR (AND logic for more precision)
            combined_detection = energy_detection and zcr_detection
        else:
            combined_detection = energy_detection
        
        # Phase 5: Apply multi-frame smoothing for stability
        smoothed_detection = self._apply_multi_frame_smoothing(combined_detection, energy_level, zcr_value)
        
        # Apply hysteresis
        final_detection = self.apply_hysteresis(smoothed_detection)
        
        # Enhanced confidence calculation
        confidence = self._calculate_enhanced_confidence(energy_level, adjusted_threshold)
        
        processing_time = (time.time() - start_time) * 1000
        
        return VADResult(
            is_voice=final_detection,
            confidence=confidence,
            energy_level=energy_level,
            timestamp=audio_data.timestamp,
            processing_time_ms=processing_time,
            zcr_value=zcr_value,
            adaptive_threshold=adaptive_threshold,
            cache_hit=energy_cache_hit or zcr_cache_hit
        )
    
    def _update_noise_estimate(self, current_energy: float):
        """Update background noise estimate using exponential smoothing."""
        if not self._current_state:  # Only update during silence
            self._noise_estimate = (1 - self._adaptation_rate) * self._noise_estimate + \
                                 self._adaptation_rate * current_energy
    
    def _calculate_enhanced_confidence(self, energy: float, threshold: float) -> float:
        """Calculate enhanced confidence with multiple factors."""
        if energy <= 0:
            return 0.0
        
        # Base confidence from energy ratio
        energy_confidence = min(1.0, energy / threshold)
        
        # Future: Add spectral confidence when implemented
        
        return energy_confidence
    
    def _apply_multi_frame_smoothing(self, detection: bool, energy: float, zcr: float) -> bool:
        """
        Apply multi-frame smoothing for more stable detection.
        
        Phase 5 advanced feature: Uses moving averages of energy, ZCR, and detection
        results to smooth out momentary fluctuations and improve stability.
        
        Args:
            detection: Current frame detection result
            energy: Current frame energy level
            zcr: Current frame ZCR value
            
        Returns:
            Smoothed detection result
        """
        # Update smoothing buffers
        self._energy_smoothing_buffer.append(energy)
        self._zcr_smoothing_buffer.append(zcr)
        self._detection_smoothing_buffer.append(detection)
        
        # Maintain buffer size
        if len(self._energy_smoothing_buffer) > self._smoothing_window_size:
            self._energy_smoothing_buffer.pop(0)
            self._zcr_smoothing_buffer.pop(0)
            self._detection_smoothing_buffer.pop(0)
        
        # If we don't have enough frames yet, return current detection
        if len(self._detection_smoothing_buffer) < self._smoothing_window_size:
            return detection
        
        # Calculate smoothed values
        avg_energy = np.mean(self._energy_smoothing_buffer)
        avg_zcr = np.mean(self._zcr_smoothing_buffer) if self.use_zcr else 0.0
        
        # Calculate percentage of frames that detected voice
        voice_percentage = sum(self._detection_smoothing_buffer) / len(self._detection_smoothing_buffer)
        
        # Smoothed detection: majority vote with energy/ZCR confirmation
        # Require at least 60% of frames to agree for stable detection
        smoothed_detection = voice_percentage >= 0.6
        
        # Additional validation with averaged features
        if smoothed_detection:
            # Confirm with smoothed energy
            adaptive_threshold = max(self.threshold, self._noise_estimate * 3.0)
            energy_confirms = avg_energy > adaptive_threshold
            
            # Confirm with smoothed ZCR if enabled
            zcr_confirms = True
            if self.use_zcr:
                zcr_confirms = avg_zcr > self._zcr_threshold
            
            smoothed_detection = energy_confirms and zcr_confirms
        
        return smoothed_detection


# Utility functions for audio energy analysis

def calculate_audio_energy(audio_data: AudioData) -> float:
    """
    Calculate RMS energy like ESP32 VAD.
    
    This function provides RMS energy calculation compatible with
    the ESP32 firmware VAD implementation for consistency.
    
    Args:
        audio_data: AudioData object
        
    Returns:
        Normalized RMS energy (0.0-1.0)
    """
    try:
        # Convert bytes to numpy array (assuming 16-bit PCM)
        audio_array = np.frombuffer(audio_data.data, dtype=np.int16)
        
        if len(audio_array) == 0:
            return 0.0
        
        # Calculate RMS energy (same method as ESP32)
        sum_squares = np.sum(audio_array.astype(np.float64) ** 2)
        rms = np.sqrt(sum_squares / len(audio_array))
        
        # Normalize to 0.0-1.0 range
        normalized_energy = rms / 32768.0
        
        return min(1.0, normalized_energy)
        
    except Exception as e:
        logger.warning(f"Error calculating audio energy: {e}")
        return 0.0


def estimate_background_noise(audio_history: list[AudioData], percentile: int = 10) -> float:
    """
    Estimate background noise level from audio history.
    
    Args:
        audio_history: List of recent AudioData frames
        percentile: Percentile to use for noise estimation (lower = less noise)
        
    Returns:
        Estimated background noise level
    """
    if not audio_history:
        return 0.0
    
    try:
        # Calculate energy for all frames
        energies = [calculate_audio_energy(frame) for frame in audio_history]
        
        # Return specified percentile as noise estimate
        sorted_energies = sorted(energies)
        index = max(0, (len(sorted_energies) * percentile) // 100)
        
        return sorted_energies[index]
        
    except Exception as e:
        logger.warning(f"Error estimating background noise: {e}")
        return 0.0


# Export public interface
__all__ = [
    'VADResult',
    'SimpleVAD', 
    'AdvancedVAD',
    'detect_voice_activity',
    'calculate_audio_energy',
    'calculate_zero_crossing_rate',
    'estimate_background_noise'
]
