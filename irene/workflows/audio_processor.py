"""
Universal Audio Processor with VAD State Management

This module implements the universal audio processing layer that provides
voice activity detection and voice segment accumulation for the Irene
Voice Assistant. It works identically in both voice trigger modes.

Phase 2 Implementation: State Machine - Universal Audio Processing
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, AsyncIterator, Callable, Union
from pathlib import Path

from ..intents.models import AudioData, ConversationContext
from ..config.models import VADConfig
from ..utils.vad import SimpleVAD, AdvancedVAD, VADResult
from ..utils.audio_helpers import calculate_audio_energy, estimate_optimal_vad_threshold

logger = logging.getLogger(__name__)


class VoiceActivityState(Enum):
    """Voice activity detection states for the universal audio processor"""
    SILENCE = "silence"
    VOICE_ONSET = "voice_onset"
    VOICE_ACTIVE = "voice_active"
    VOICE_ENDED = "voice_ended"


@dataclass
class VoiceSegment:
    """Represents a complete voice segment with metadata"""
    audio_chunks: List[AudioData]
    start_timestamp: float
    end_timestamp: float
    total_duration_ms: float
    chunk_count: int
    combined_audio: Optional[AudioData] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds"""
        return self.total_duration_ms / 1000.0


@dataclass
class ProcessingMetrics:
    """Metrics for VAD processing performance"""
    total_chunks_processed: int = 0
    voice_segments_detected: int = 0
    silence_chunks_skipped: int = 0
    average_processing_time_ms: float = 0.0
    max_processing_time_ms: float = 0.0
    total_processing_time_ms: float = 0.0
    buffer_overflow_count: int = 0
    timeout_events: int = 0
    
    def update_processing_time(self, processing_time_ms: float):
        """Update processing time metrics"""
        self.total_processing_time_ms += processing_time_ms
        self.total_chunks_processed += 1
        
        if processing_time_ms > self.max_processing_time_ms:
            self.max_processing_time_ms = processing_time_ms
            
        self.average_processing_time_ms = (
            self.total_processing_time_ms / self.total_chunks_processed
        )


@dataclass 
class AdvancedMetrics:
    """Enhanced metrics for Phase 5 monitoring and optimization"""
    # Cache performance metrics
    cache_hit_rate: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    
    # Voice segment quality metrics
    total_voice_duration_ms: float = 0.0
    average_segment_duration_ms: float = 0.0
    min_segment_duration_ms: float = float('inf')
    max_segment_duration_ms: float = 0.0
    
    # Detection accuracy metrics
    false_positive_segments: int = 0  # Very short segments (likely noise)
    false_negative_gaps: int = 0      # Brief silence in continuous speech
    
    # Adaptive threshold tracking
    adaptive_threshold_adjustments: int = 0
    current_adaptive_threshold: float = 0.0
    average_energy_level: float = 0.0
    average_zcr_level: float = 0.0
    
    # Performance efficiency
    real_time_factor: float = 0.0
    memory_efficiency_score: float = 0.0
    
    def update_cache_metrics(self, cache_hit: bool):
        """Update cache performance metrics"""
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        
        total = self.cache_hits + self.cache_misses
        self.cache_hit_rate = self.cache_hits / total if total > 0 else 0.0
    
    def update_voice_segment_metrics(self, segment_duration_ms: float):
        """Update voice segment statistics"""
        self.total_voice_duration_ms += segment_duration_ms
        
        # Update duration statistics
        self.min_segment_duration_ms = min(self.min_segment_duration_ms, segment_duration_ms)
        self.max_segment_duration_ms = max(self.max_segment_duration_ms, segment_duration_ms)
        
        # Check for potential false positives
        if segment_duration_ms < 100:  # Less than 100ms might be noise
            self.false_positive_segments += 1
    
    def update_detection_quality(self, energy: float, zcr: float, adaptive_threshold: float, chunk_count: int):
        """Update detection quality metrics"""
        # Update running averages
        if chunk_count > 0:
            alpha = 1.0 / chunk_count
            self.average_energy_level = (1 - alpha) * self.average_energy_level + alpha * energy
            self.average_zcr_level = (1 - alpha) * self.average_zcr_level + alpha * zcr
        
        # Track threshold changes
        if abs(adaptive_threshold - self.current_adaptive_threshold) > 0.001:
            self.adaptive_threshold_adjustments += 1
            self.current_adaptive_threshold = adaptive_threshold
    
    def calculate_efficiency(self, audio_duration_ms: float, processing_time_ms: float, buffer_ratio: float):
        """Calculate efficiency metrics"""
        if processing_time_ms > 0:
            self.real_time_factor = audio_duration_ms / processing_time_ms
        self.memory_efficiency_score = 1.0 - buffer_ratio
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        return {
            'cache_performance': {
                'hit_rate': self.cache_hit_rate,
                'hits': self.cache_hits,
                'misses': self.cache_misses
            },
            'segment_quality': {
                'total_duration_ms': self.total_voice_duration_ms,
                'avg_duration_ms': self.average_segment_duration_ms,
                'min_duration_ms': self.min_segment_duration_ms,
                'max_duration_ms': self.max_segment_duration_ms,
                'false_positives': self.false_positive_segments
            },
            'detection_quality': {
                'avg_energy': self.average_energy_level,
                'avg_zcr': self.average_zcr_level,
                'threshold': self.current_adaptive_threshold,
                'adjustments': self.adaptive_threshold_adjustments
            },
            'efficiency': {
                'real_time_factor': self.real_time_factor,
                'memory_efficiency': self.memory_efficiency_score
            }
        }


class UniversalAudioProcessor:
    """
    Handles VAD state management and voice segment accumulation.
    
    This processor provides a universal audio processing layer that works
    identically in both voice trigger modes:
    - With Voice Trigger: VAD → Wake Word Detection → VAD → ASR Processing
    - Without Voice Trigger: VAD → Direct ASR Processing
    
    Key Features:
    - Voice activity detection with hysteresis
    - Voice segment accumulation and buffering
    - Timeout protection for long speech segments
    - Edge case handling (short bursts, continuous speech, cutoffs)
    - Performance monitoring and metrics
    """
    
    def __init__(self, vad_config: VADConfig):
        """
        Initialize the universal audio processor.
        
        Args:
            vad_config: VAD configuration object
        """
        self.config = vad_config
        self.vad_state = VoiceActivityState.SILENCE
        
        # Initialize VAD engine based on configuration
        if vad_config.use_zero_crossing_rate or vad_config.adaptive_threshold:
            self.vad_engine = AdvancedVAD(
                threshold=vad_config.energy_threshold,
                sensitivity=vad_config.sensitivity,
                voice_frames_required=vad_config.voice_frames_required,
                silence_frames_required=vad_config.silence_frames_required,
                use_zcr=vad_config.use_zero_crossing_rate
            )
        else:
            self.vad_engine = SimpleVAD(
                threshold=vad_config.energy_threshold,
                sensitivity=vad_config.sensitivity,
                voice_frames_required=vad_config.voice_frames_required,
                silence_frames_required=vad_config.silence_frames_required
            )
        
        # Voice segment buffering
        self.voice_buffer: List[AudioData] = []
        self.voice_segment_start_time: Optional[float] = None
        self.voice_segment_start_timestamp: Optional[float] = None
        
        # Timeout and buffer management
        self.max_segment_duration_s = vad_config.max_segment_duration_s
        self.buffer_size_limit = vad_config.buffer_size_frames
        
        # Performance metrics
        self.metrics = ProcessingMetrics()
        
        # Phase 5: Advanced metrics for monitoring & optimization
        self.advanced_metrics = AdvancedMetrics()
        
        # Callbacks for voice segment processing
        self.voice_segment_callback: Optional[Callable] = None
        
        logger.info(f"UniversalAudioProcessor initialized with VAD config: "
                   f"threshold={vad_config.threshold}, "
                   f"sensitivity={vad_config.sensitivity}, "
                   f"advanced_features={vad_config.use_zero_crossing_rate}")
    
    def set_voice_segment_callback(self, callback: Callable[[VoiceSegment], None]):
        """
        Set callback function for voice segment processing.
        
        Args:
            callback: Async function to call when voice segment is complete
        """
        self.voice_segment_callback = callback
    
    async def process_audio_chunk(self, audio_data: AudioData) -> Optional[VoiceSegment]:
        """
        Process a single audio chunk and return complete voice segment if available.
        
        This is the main entry point for audio processing. It handles VAD state
        management and voice segment accumulation.
        
        Args:
            audio_data: AudioData chunk to process
            
        Returns:
            VoiceSegment if a complete voice segment is ready, None otherwise
        """
        start_time = time.time()
        
        try:
            # Perform VAD on the audio chunk
            vad_result = self.vad_engine.process_frame(audio_data)
            
            # Update metrics
            processing_time = (time.time() - start_time) * 1000
            self.metrics.update_processing_time(processing_time)
            
            # Debug logging every 50 chunks to see activity
            if self.metrics.total_chunks_processed % 50 == 0:
                logger.debug(f"VAD processed {self.metrics.total_chunks_processed} chunks, "
                           f"current energy: {vad_result.energy_level:.6f}, "
                           f"threshold: {vad_result.adaptive_threshold:.6f}, "
                           f"voice detected: {vad_result.is_voice}")
                           
            # Log voice detection events
            if vad_result.is_voice and self.vad_state == VoiceActivityState.SILENCE:
                logger.info(f"🎤 Voice activity detected! Energy: {vad_result.energy_level:.6f}, "
                          f"threshold: {vad_result.adaptive_threshold:.6f}, "
                          f"confidence: {vad_result.confidence:.3f}")
            
            # Phase 5: Update advanced metrics
            self.advanced_metrics.update_cache_metrics(getattr(vad_result, 'cache_hit', False))
            self.advanced_metrics.update_detection_quality(
                vad_result.energy_level,
                getattr(vad_result, 'zcr_value', 0.0),
                getattr(vad_result, 'adaptive_threshold', self.config.energy_threshold),
                self.metrics.total_chunks_processed
            )
            
            # Handle state transitions based on VAD result
            voice_segment = await self._handle_vad_state_transition(audio_data, vad_result)
            
            # Check for timeout protection
            if self.voice_buffer and self._is_segment_timeout():
                logger.warning(f"Voice segment timeout after {self.max_segment_duration_s}s, forcing completion")
                self.metrics.timeout_events += 1
                voice_segment = await self._force_voice_segment_completion()
            
            # Check for buffer overflow protection
            if len(self.voice_buffer) > self.buffer_size_limit:
                logger.warning(f"Voice buffer overflow ({len(self.voice_buffer)} > {self.buffer_size_limit}), forcing completion")
                self.metrics.buffer_overflow_count += 1
                voice_segment = await self._force_voice_segment_completion()
            
            return voice_segment
            
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            # Reset state on error to prevent corruption
            await self._reset_voice_state()
            return None
    
    async def _handle_vad_state_transition(self, audio_data: AudioData, vad_result: VADResult) -> Optional[VoiceSegment]:
        """
        Handle VAD state transitions and voice segment management.
        
        Args:
            audio_data: Current audio data chunk
            vad_result: VAD detection result
            
        Returns:
            VoiceSegment if voice segment is complete, None otherwise
        """
        previous_state = self.vad_state
        
        # State transition logic (same for both voice trigger modes)
        if self.vad_state == VoiceActivityState.SILENCE and vad_result.is_voice:
            # Voice onset detected
            self.vad_state = VoiceActivityState.VOICE_ONSET
            await self._handle_voice_onset(audio_data, vad_result)
            
        elif self.vad_state in [VoiceActivityState.VOICE_ONSET, VoiceActivityState.VOICE_ACTIVE] and vad_result.is_voice:
            # Voice continues
            self.vad_state = VoiceActivityState.VOICE_ACTIVE
            await self._handle_voice_active(audio_data, vad_result)
            
        elif self.vad_state == VoiceActivityState.VOICE_ACTIVE and not vad_result.is_voice:
            # Voice ended
            self.vad_state = VoiceActivityState.VOICE_ENDED
            voice_segment = await self._handle_voice_ended()
            self.vad_state = VoiceActivityState.SILENCE
            return voice_segment
            
        elif self.vad_state == VoiceActivityState.SILENCE and not vad_result.is_voice:
            # Continue silence - skip processing
            self.metrics.silence_chunks_skipped += 1
        
        # Log state changes for debugging
        if previous_state != self.vad_state:
            logger.debug(f"VAD state transition: {previous_state.value} → {self.vad_state.value} "
                        f"(voice={vad_result.is_voice}, confidence={vad_result.confidence:.3f})")
        
        return None
    
    async def _handle_voice_onset(self, audio_data: AudioData, vad_result: VADResult):
        """
        Handle voice onset - start new voice segment.
        
        Args:
            audio_data: Audio data chunk
            vad_result: VAD detection result
        """
        # Start new voice segment
        self.voice_buffer = [audio_data]
        self.voice_segment_start_time = time.time()
        self.voice_segment_start_timestamp = audio_data.timestamp
        
        logger.debug(f"Voice onset detected: energy={vad_result.energy_level:.4f}, "
                    f"confidence={vad_result.confidence:.3f}")
    
    async def _handle_voice_active(self, audio_data: AudioData, vad_result: VADResult):
        """
        Handle ongoing voice activity - accumulate audio data.
        
        Args:
            audio_data: Audio data chunk
            vad_result: VAD detection result
        """
        # Accumulate voice data
        self.voice_buffer.append(audio_data)
        
        # Log periodic status for long segments
        if len(self.voice_buffer) % 20 == 0:  # Every ~500ms at 25ms chunks
            duration = time.time() - self.voice_segment_start_time if self.voice_segment_start_time else 0
            logger.debug(f"Voice segment active: {len(self.voice_buffer)} chunks, {duration:.1f}s duration")
    
    async def _handle_voice_ended(self) -> VoiceSegment:
        """
        Handle voice end - create complete voice segment.
        
        Returns:
            Complete VoiceSegment object
        """
        if not self.voice_buffer:
            logger.warning("Voice ended but no audio buffer available")
            return None
        
        # Calculate segment metadata
        end_time = time.time()
        end_timestamp = self.voice_buffer[-1].timestamp
        
        total_duration_ms = (end_time - self.voice_segment_start_time) * 1000 if self.voice_segment_start_time else 0
        chunk_count = len(self.voice_buffer)
        
        # Create voice segment
        voice_segment = VoiceSegment(
            audio_chunks=self.voice_buffer.copy(),
            start_timestamp=self.voice_segment_start_timestamp or 0,
            end_timestamp=end_timestamp,
            total_duration_ms=total_duration_ms,
            chunk_count=chunk_count,
            metadata={
                'vad_state_transitions': True,
                'chunk_size_bytes': sum(len(chunk.data) for chunk in self.voice_buffer),
                'average_energy': sum(calculate_audio_energy(chunk) for chunk in self.voice_buffer) / chunk_count,
                'processing_mode': 'universal_vad'
            }
        )
        
        # Combine audio chunks into single AudioData
        voice_segment.combined_audio = await self._combine_audio_buffer(self.voice_buffer)
        
        # Update metrics
        self.metrics.voice_segments_detected += 1
        
        # Phase 5: Update advanced voice segment metrics
        self.advanced_metrics.update_voice_segment_metrics(total_duration_ms)
        if hasattr(self.advanced_metrics, 'voice_segments_detected') and self.advanced_metrics.voice_segments_detected < self.metrics.voice_segments_detected:
            self.advanced_metrics.average_segment_duration_ms = (
                self.advanced_metrics.total_voice_duration_ms / self.metrics.voice_segments_detected
            )
        
        # Reset voice state
        await self._reset_voice_state()
        
        logger.info(f"Voice segment completed: {chunk_count} chunks, {total_duration_ms:.1f}ms duration, "
                   f"{len(voice_segment.combined_audio.data)} bytes")
        
        return voice_segment
    
    async def _force_voice_segment_completion(self) -> Optional[VoiceSegment]:
        """
        Force completion of current voice segment (timeout/overflow protection).
        
        Returns:
            VoiceSegment if buffer contains data, None otherwise
        """
        if not self.voice_buffer:
            return None
        
        logger.debug("Forcing voice segment completion due to timeout/overflow")
        
        # Temporarily set state to VOICE_ENDED to trigger completion
        original_state = self.vad_state
        self.vad_state = VoiceActivityState.VOICE_ENDED
        
        voice_segment = await self._handle_voice_ended()
        
        # Return to SILENCE state
        self.vad_state = VoiceActivityState.SILENCE
        
        return voice_segment
    
    async def _reset_voice_state(self):
        """Reset voice processing state."""
        self.voice_buffer.clear()
        self.voice_segment_start_time = None
        self.voice_segment_start_timestamp = None
        self.vad_state = VoiceActivityState.SILENCE
    
    def _is_segment_timeout(self) -> bool:
        """Check if current voice segment has exceeded timeout."""
        if not self.voice_segment_start_time:
            return False
        
        duration = time.time() - self.voice_segment_start_time
        return duration > self.max_segment_duration_s
    
    async def _combine_audio_buffer(self, audio_chunks: List[AudioData]) -> AudioData:
        """
        Combine multiple audio chunks into a single AudioData object.
        
        Args:
            audio_chunks: List of AudioData chunks to combine
            
        Returns:
            Combined AudioData object
        """
        if not audio_chunks:
            raise ValueError("Cannot combine empty audio buffer")
        
        if len(audio_chunks) == 1:
            return audio_chunks[0]
        
        # Combine audio data
        combined_data = b''.join(chunk.data for chunk in audio_chunks)
        
        # Use metadata from first chunk as base
        first_chunk = audio_chunks[0]
        last_chunk = audio_chunks[-1]
        
        # Calculate total duration
        duration_ms = (last_chunk.timestamp - first_chunk.timestamp) * 1000
        
        return AudioData(
            data=combined_data,
            timestamp=first_chunk.timestamp,
            sample_rate=first_chunk.sample_rate,
            channels=first_chunk.channels,
            format=first_chunk.format,
            metadata={
                **first_chunk.metadata,
                'combined_chunks': len(audio_chunks),
                'total_duration_ms': duration_ms,
                'chunk_timestamps': [chunk.timestamp for chunk in audio_chunks],
                'vad_processed': True
            }
        )
    
    async def process_audio_stream(self, audio_stream: AsyncIterator[AudioData]) -> AsyncIterator[VoiceSegment]:
        """
        Process an entire audio stream and yield voice segments.
        
        Args:
            audio_stream: Async iterator of AudioData chunks
            
        Yields:
            VoiceSegment objects when complete voice segments are detected
        """
        async for audio_data in audio_stream:
            voice_segment = await self.process_audio_chunk(audio_data)
            
            if voice_segment:
                yield voice_segment
                
                # Call callback if configured
                if self.voice_segment_callback:
                    try:
                        await self.voice_segment_callback(voice_segment)
                    except Exception as e:
                        logger.error(f"Error in voice segment callback: {e}")
    
    def get_processing_metrics(self) -> ProcessingMetrics:
        """Get current processing metrics."""
        return self.metrics
    
    def reset_metrics(self):
        """Reset processing metrics."""
        self.metrics = ProcessingMetrics()
    
    def get_current_state(self) -> Dict[str, Any]:
        """
        Get current processor state for debugging/monitoring.
        
        Returns:
            Dictionary with current state information
        """
        return {
            'vad_state': self.vad_state.value,
            'buffer_size': len(self.voice_buffer),
            'segment_duration_s': (
                time.time() - self.voice_segment_start_time 
                if self.voice_segment_start_time else 0
            ),
            'metrics': {
                'chunks_processed': self.metrics.total_chunks_processed,
                'voice_segments': self.metrics.voice_segments_detected,
                'silence_skipped': self.metrics.silence_chunks_skipped,
                'avg_processing_ms': self.metrics.average_processing_time_ms,
                'buffer_overflows': self.metrics.buffer_overflow_count,
                'timeouts': self.metrics.timeout_events
            },
            'config': {
                'threshold': self.config.threshold,
                'sensitivity': self.config.sensitivity,
                'max_duration_s': self.config.max_segment_duration_s,
                'buffer_limit': self.config.buffer_size_frames
            }
        }
    
    def get_advanced_metrics(self) -> AdvancedMetrics:
        """Get Phase 5 advanced metrics for monitoring and optimization."""
        # Update efficiency metrics before returning
        audio_duration_ms = self.metrics.total_chunks_processed * 23  # Assuming 23ms chunks
        buffer_ratio = len(self.voice_buffer) / max(1, self.config.buffer_size_frames)
        
        self.advanced_metrics.calculate_efficiency(
            audio_duration_ms,
            self.metrics.total_processing_time_ms,
            buffer_ratio
        )
        
        return self.advanced_metrics
    
    def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics combining basic and advanced metrics (Phase 5)."""
        basic_metrics = self.get_processing_metrics()
        advanced_metrics = self.get_advanced_metrics()
        
        return {
            'basic_metrics': {
                'total_chunks_processed': basic_metrics.total_chunks_processed,
                'voice_segments_detected': basic_metrics.voice_segments_detected,
                'silence_chunks_skipped': basic_metrics.silence_chunks_skipped,
                'average_processing_time_ms': basic_metrics.average_processing_time_ms,
                'max_processing_time_ms': basic_metrics.max_processing_time_ms,
                'buffer_overflow_count': basic_metrics.buffer_overflow_count,
                'timeout_events': basic_metrics.timeout_events
            },
            'advanced_metrics': advanced_metrics.get_summary(),
            'performance_overview': {
                'efficiency_score': advanced_metrics.memory_efficiency_score,
                'real_time_factor': advanced_metrics.real_time_factor,
                'cache_effectiveness': advanced_metrics.cache_hit_rate,
                'detection_stability': max(0, 1.0 - (advanced_metrics.false_positive_segments / max(1, basic_metrics.voice_segments_detected)))
            }
        }
    
    def reset_advanced_metrics(self):
        """Reset advanced metrics (Phase 5)."""
        self.advanced_metrics = AdvancedMetrics()
    
    async def calibrate_threshold(self, calibration_audio: List[AudioData], 
                                noise_percentile: int = None) -> float:
        """
        Calibrate VAD threshold based on environment audio samples.
        
        Args:
            calibration_audio: List of audio samples for calibration
            noise_percentile: Percentile for noise estimation (uses config default if None)
            
        Returns:
            Suggested optimal threshold
        """
        if noise_percentile is None:
            noise_percentile = self.config.noise_percentile
        
        optimal_threshold = estimate_optimal_vad_threshold(
            calibration_audio, 
            noise_percentile=noise_percentile,
            voice_multiplier=self.config.voice_multiplier
        )
        
        logger.info(f"VAD threshold calibration: current={self.config.threshold:.4f}, "
                   f"suggested={optimal_threshold:.4f}")
        
        return optimal_threshold
    
    def update_threshold(self, new_threshold: float):
        """
        Update VAD threshold dynamically.
        
        Args:
            new_threshold: New threshold value (0.0-1.0)
        """
        if not 0.0 <= new_threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {new_threshold}")
        
        old_threshold = self.config.threshold
        self.config.threshold = new_threshold
        
        # Update VAD engine threshold
        self.vad_engine.threshold = new_threshold
        
        logger.info(f"VAD threshold updated: {old_threshold:.4f} → {new_threshold:.4f}")


# Integration interface for workflows

class AudioProcessorInterface:
    """
    Interface for workflow integration with the universal audio processor.
    
    This provides a clean handoff to existing ASR/voice trigger components
    while maintaining backward compatibility.
    """
    
    def __init__(self, vad_config: VADConfig):
        """
        Initialize audio processor interface.
        
        Args:
            vad_config: VAD configuration object
        """
        self.processor = UniversalAudioProcessor(vad_config)
        
    async def process_audio_pipeline(self, 
                                   audio_stream: AsyncIterator[AudioData],
                                   context: Any,  # RequestContext
                                   voice_segment_handler: Callable[[VoiceSegment, Any], None]) -> AsyncIterator[VoiceSegment]:
        """
        Process audio pipeline with VAD integration.
        
        This method provides the main integration point for workflows to use
        VAD processing with clean handoff to existing components.
        
        Args:
            audio_stream: Input audio stream 
            context: Request context from workflow
            voice_segment_handler: Handler function for complete voice segments
            
        Yields:
            VoiceSegment objects for further processing
        """
        # Use VAD processing (always enabled)
        logger.debug("Using universal VAD audio processing")
        async for voice_segment in self.processor.process_audio_stream(audio_stream):
            # Call workflow handler
            try:
                await voice_segment_handler(voice_segment, context)
            except Exception as e:
                logger.error(f"Error in voice segment handler: {e}")
            
            yield voice_segment
    
    async def process_voice_segment_for_mode(self, 
                                           voice_segment: VoiceSegment, 
                                           context: Any,  # RequestContext
                                           asr_component = None,
                                           voice_trigger_component = None,
                                           wake_word_detected: bool = False) -> Dict[str, Any]:
        """
        Process voice segment according to the current mode (with/without wake word).
        
        This implements the mode-specific processing logic from the VAD design:
        - Mode A (skip_wake_word=False): Wake word detection first, then ASR
        - Mode B (skip_wake_word=True): Direct ASR processing
        
        Args:
            voice_segment: Complete voice segment to process
            context: Request context
            asr_component: ASR component instance
            voice_trigger_component: Voice trigger component instance  
            wake_word_detected: Current wake word detection state
            
        Returns:
            Processing result dictionary
        """
        combined_audio = voice_segment.combined_audio
        
        if context.skip_wake_word:
            # Mode B: Direct ASR processing
            logger.debug("Mode B: Direct ASR processing of voice segment")
            
            if asr_component:
                try:
                    asr_result = await asr_component.process_audio(combined_audio)
                    return {
                        'type': 'asr_result',
                        'result': asr_result,
                        'voice_segment': voice_segment,
                        'mode': 'direct_asr'
                    }
                except Exception as e:
                    logger.error(f"ASR processing failed: {e}")
                    return {
                        'type': 'error',
                        'error': str(e),
                        'voice_segment': voice_segment
                    }
            else:
                logger.warning("ASR component not available for Mode B processing")
                return {
                    'type': 'error',
                    'error': 'ASR component not available',
                    'voice_segment': voice_segment
                }
        else:
            # Mode A: Wake word detection first
            if not wake_word_detected:
                logger.debug("Mode A: Wake word detection on voice segment")
                
                if voice_trigger_component:
                    try:
                        wake_result = await voice_trigger_component.process_audio(combined_audio)
                        return {
                            'type': 'wake_word_result',
                            'result': wake_result,
                            'voice_segment': voice_segment,
                            'mode': 'wake_word_detection'
                        }
                    except Exception as e:
                        logger.error(f"Wake word detection failed: {e}")
                        return {
                            'type': 'error',
                            'error': str(e),
                            'voice_segment': voice_segment
                        }
                else:
                    logger.warning("Voice trigger component not available for Mode A processing")
                    return {
                        'type': 'error',
                        'error': 'Voice trigger component not available',
                        'voice_segment': voice_segment
                    }
            else:
                # Wake word already detected, process as command
                logger.debug("Mode A: ASR processing of command after wake word")
                
                if asr_component:
                    try:
                        asr_result = await asr_component.process_audio(combined_audio)
                        return {
                            'type': 'asr_result',
                            'result': asr_result,
                            'voice_segment': voice_segment,
                            'mode': 'command_after_wake'
                        }
                    except Exception as e:
                        logger.error(f"ASR processing failed: {e}")
                        return {
                            'type': 'error',
                            'error': str(e),
                            'voice_segment': voice_segment
                        }
                else:
                    logger.warning("ASR component not available for command processing")
                    return {
                        'type': 'error',
                        'error': 'ASR component not available',
                        'voice_segment': voice_segment
                    }
    
    def get_metrics(self) -> ProcessingMetrics:
        """Get processing metrics from the audio processor."""
        return self.processor.get_processing_metrics()
    
    def get_state(self) -> Dict[str, Any]:
        """Get current processor state."""
        return self.processor.get_current_state()
    
    async def calibrate(self, calibration_audio: List[AudioData]) -> float:
        """Calibrate VAD threshold based on environment."""
        return await self.processor.calibrate_threshold(calibration_audio)


# Utility functions for audio processor integration

def create_audio_processor(vad_config: VADConfig) -> UniversalAudioProcessor:
    """
    Factory function to create UniversalAudioProcessor with validated config.
    
    Args:
        vad_config: VAD configuration object
        
    Returns:
        Configured UniversalAudioProcessor instance
    """
    return UniversalAudioProcessor(vad_config)


async def process_audio_with_vad(audio_stream: AsyncIterator[AudioData], 
                                vad_config: VADConfig,
                                segment_callback: Optional[Callable] = None) -> AsyncIterator[VoiceSegment]:
    """
    Convenience function to process audio stream with VAD.
    
    Args:
        audio_stream: Input audio stream
        vad_config: VAD configuration
        segment_callback: Optional callback for voice segments
        
    Yields:
        VoiceSegment objects when complete voice segments are detected
    """
    processor = create_audio_processor(vad_config)
    
    if segment_callback:
        processor.set_voice_segment_callback(segment_callback)
    
    async for voice_segment in processor.process_audio_stream(audio_stream):
        yield voice_segment


# Export public interface
__all__ = [
    'VoiceActivityState',
    'VoiceSegment', 
    'ProcessingMetrics',
    'UniversalAudioProcessor',
    'AudioProcessorInterface',
    'create_audio_processor',
    'process_audio_with_vad'
]
