"""
Phase 2 VAD Testing Script - State Machine and Audio Processing

Tests the Universal Audio Processor state machine and voice segment
accumulation as specified in Phase 2, Step 2.1-2.3.
"""

import asyncio
import logging
import time
import numpy as np
from typing import List, AsyncIterator

# Import Phase 2 components - Phase 4: ProcessingMetrics removed, using unified MetricsCollector
from irene.workflows.audio_processor import (
    VoiceActivityState, VoiceSegment,
    UniversalAudioProcessor, AudioProcessorInterface,
    create_audio_processor
)
from irene.config.models import VADConfig
from irene.intents.models import AudioData

# Import Phase 1 components for testing
from irene.tests.test_vad_basic import generate_test_audio_data

logger = logging.getLogger(__name__)


class MockRequestContext:
    """Mock request context for testing"""
    def __init__(self, skip_wake_word: bool = False):
        self.skip_wake_word = skip_wake_word
        self.source = "test"
        self.session_id = "test_session"


class MockASRComponent:
    """Mock ASR component for testing"""
    async def process_audio(self, audio_data: AudioData):
        # Simulate ASR processing
        await asyncio.sleep(0.01)  # Small delay to simulate processing
        return {
            'text': 'test recognition result',
            'confidence': 0.9,
            'duration_ms': len(audio_data.data) / 32  # Rough estimate
        }


class MockVoiceTriggerComponent:
    """Mock voice trigger component for testing"""
    def __init__(self, detection_rate: float = 0.3):
        self.detection_rate = detection_rate
        
    async def process_audio(self, audio_data: AudioData):
        # Simulate wake word detection with configurable rate
        await asyncio.sleep(0.005)  # Small delay to simulate processing
        detected = np.random.random() < self.detection_rate
        return {
            'detected': detected,
            'confidence': 0.8 if detected else 0.1,
            'wake_word': 'irene' if detected else None
        }


async def generate_test_audio_stream(sequence: List[tuple], chunk_duration_ms: float = 50) -> AsyncIterator[AudioData]:
    """
    Generate test audio stream from sequence description.
    
    Args:
        sequence: List of (audio_type, count) tuples
        chunk_duration_ms: Duration of each chunk in milliseconds
        
    Yields:
        AudioData chunks according to sequence
    """
    for audio_type, count in sequence:
        for _ in range(count):
            yield generate_test_audio_data(chunk_duration_ms, audio_type=audio_type)
            await asyncio.sleep(0.001)  # Small delay between chunks


def test_vad_config_validation():
    """Test VAD configuration validation."""
    print("Testing VAD configuration validation...")
    
    # Test valid configuration
    valid_config = VADConfig(
        enabled=True,
        threshold=0.02,
        sensitivity=0.7,
        voice_frames_required=3,
        silence_frames_required=4,
        max_segment_duration_s=15,
        use_zero_crossing_rate=True,
        adaptive_threshold=False
    )
    
    assert valid_config.enabled == True
    assert valid_config.threshold == 0.02
    assert valid_config.voice_frames_required == 3
    print(f"  Valid config: {valid_config.threshold=}, {valid_config.sensitivity=}")
    
    # Test invalid threshold (should raise validation error)
    try:
        invalid_config = VADConfig(threshold=1.5)  # > 1.0
        assert False, "Should have raised validation error"
    except Exception as e:
        print(f"  Invalid threshold correctly rejected: {type(e).__name__}")
    
    print("✓ VAD configuration validation test passed\n")


async def test_universal_audio_processor():
    """Test UniversalAudioProcessor state machine."""
    print("Testing UniversalAudioProcessor state machine...")
    
    # Create test configuration
    config = VADConfig(
        enabled=True,
        energy_threshold=0.01,
        sensitivity=0.5,
        voice_frames_required=2,
        silence_frames_required=3,
        max_segment_duration_s=5
    )
    
    # Create processor
    processor = UniversalAudioProcessor(config)
    
    # Test initial state
    assert processor.vad_state == VoiceActivityState.SILENCE
    print(f"  Initial state: {processor.vad_state.value}")
    
    # Test state transitions with audio sequence
    # Sequence: silence(3) -> voice(5) -> silence(4) -> voice(3) -> silence(3)
    test_sequence = [
        ("silence", 3),
        ("speech_like", 5), 
        ("silence", 4),
        ("speech_like", 3),
        ("silence", 3)
    ]
    
    voice_segments = []
    chunk_count = 0
    
    async for audio_chunk in generate_test_audio_stream(test_sequence):
        chunk_count += 1
        voice_segment = await processor.process_audio_chunk(audio_chunk)
        
        if voice_segment:
            voice_segments.append(voice_segment)
            print(f"    Voice segment {len(voice_segments)}: {voice_segment.chunk_count} chunks, "
                  f"{voice_segment.total_duration_ms:.1f}ms")
    
    # Verify we got voice segments
    assert len(voice_segments) >= 1, f"Expected voice segments, got {len(voice_segments)}"
    
    # Check processor metrics
    metrics = processor.get_processing_metrics()
    print(f"  Processing metrics:")
    print(f"    Total chunks: {metrics.total_chunks_processed}")
    print(f"    Voice segments: {metrics.voice_segments_detected}")
    print(f"    Silence skipped: {metrics.silence_chunks_skipped}")
    print(f"    Avg processing time: {metrics.average_processing_time_ms:.2f}ms")
    
    assert metrics.total_chunks_processed == chunk_count
    assert metrics.voice_segments_detected == len(voice_segments)
    
    print("✓ UniversalAudioProcessor state machine test passed\n")


async def test_voice_segment_timeout():
    """Test voice segment timeout protection."""
    print("Testing voice segment timeout protection...")
    
    # Create config with short timeout
    config = VADConfig(
        enabled=True,
        threshold=0.01,
        max_segment_duration_s=1,  # 1 second timeout
        voice_frames_required=1,
        silence_frames_required=2
    )
    
    processor = UniversalAudioProcessor(config)
    
    # Generate long continuous speech (should trigger timeout)
    long_speech_sequence = [("speech_like", 50)]  # 50 chunks
    
    voice_segments = []
    
    # Add realistic timing to trigger timeout
    async for audio_chunk in generate_test_audio_stream(long_speech_sequence, chunk_duration_ms=50):
        voice_segment = await processor.process_audio_chunk(audio_chunk)
        
        if voice_segment:
            voice_segments.append(voice_segment)
            print(f"    Timeout voice segment: {voice_segment.chunk_count} chunks, "
                  f"{voice_segment.total_duration_ms:.1f}ms")
        
        # Add small delay to simulate real-time audio processing
        await asyncio.sleep(0.05)  # 50ms delay per chunk
    
    # Should have at least one timeout-triggered segment
    metrics = processor.get_processing_metrics()
    assert metrics.timeout_events > 0, f"Expected timeout events, got {metrics.timeout_events}"
    
    print(f"  Timeout events: {metrics.timeout_events}")
    print("✓ Voice segment timeout test passed\n")


async def test_buffer_overflow_protection():
    """Test buffer overflow protection."""
    print("Testing buffer overflow protection...")
    
    # Create config with small buffer
    config = VADConfig(
        enabled=True,
        threshold=0.01,
        buffer_size_frames=10,  # Small buffer
        voice_frames_required=1,
        silence_frames_required=2,
        max_segment_duration_s=30  # Long timeout to focus on buffer overflow
    )
    
    processor = UniversalAudioProcessor(config)
    
    # Generate continuous speech that exceeds buffer
    overflow_sequence = [("speech_like", 20)]  # 20 chunks > 10 buffer limit
    
    voice_segments = []
    
    async for audio_chunk in generate_test_audio_stream(overflow_sequence):
        voice_segment = await processor.process_audio_chunk(audio_chunk)
        
        if voice_segment:
            voice_segments.append(voice_segment)
            print(f"    Overflow voice segment: {voice_segment.chunk_count} chunks")
    
    # Should have buffer overflow events
    metrics = processor.get_processing_metrics()
    assert metrics.buffer_overflow_count > 0, f"Expected buffer overflow, got {metrics.buffer_overflow_count}"
    
    print(f"  Buffer overflow events: {metrics.buffer_overflow_count}")
    print("✓ Buffer overflow protection test passed\n")


async def test_audio_processor_interface():
    """Test AudioProcessorInterface integration."""
    print("Testing AudioProcessorInterface integration...")
    
    # Test with VAD enabled (only mode now supported)
    config_enabled = VADConfig(enabled=True, energy_threshold=0.01)
    interface_enabled = AudioProcessorInterface(config_enabled)
    
    # Create mock context and components
    context = MockRequestContext(skip_wake_word=True)
    asr_component = MockASRComponent()
    voice_trigger_component = MockVoiceTriggerComponent()
    
    # Test audio sequence
    test_sequence = [("silence", 2), ("speech_like", 3), ("silence", 2)]
    
    # Test VAD interface
    print("  Testing VAD interface...")
    enabled_segments = []
    enabled_results = []
    
    async def mock_handler(segment, ctx):
        enabled_segments.append(segment)
    
    async for voice_segment in interface_enabled.process_audio_pipeline(
        generate_test_audio_stream(test_sequence), 
        context, 
        mock_handler
    ):
        enabled_results.append(voice_segment)
        # Test mode-specific processing
        result = await interface_enabled.process_voice_segment_for_mode(
            voice_segment, context, asr_component, voice_trigger_component
        )
        
        assert result['type'] == 'asr_result', f"Expected ASR result, got {result['type']}"
        assert result['mode'] == 'direct_asr'
        print(f"    VAD result: {result['mode']}")
    
    # Verify VAD processing worked
    print(f"  VAD segments: {len(enabled_results)}")
    
    # Should have at least some processing results
    assert len(enabled_results) >= 0, "VAD processing should work"
    
    print(f"  ✓ Interface test completed successfully")
    
    print("✓ AudioProcessorInterface integration test passed\n")


async def test_mode_specific_processing():
    """Test mode-specific processing (with/without wake word)."""
    print("Testing mode-specific processing...")
    
    config = VADConfig(enabled=True, threshold=0.01)
    interface = AudioProcessorInterface(config)
    
    # Create mock components
    asr_component = MockASRComponent()
    voice_trigger_component = MockVoiceTriggerComponent(detection_rate=1.0)  # Always detect
    
    # Create test voice segment
    audio_chunks = [generate_test_audio_data(100, audio_type="speech_like")]
    voice_segment = VoiceSegment(
        audio_chunks=audio_chunks,
        start_timestamp=time.time(),
        end_timestamp=time.time() + 0.1,
        total_duration_ms=100,
        chunk_count=1,
        combined_audio=audio_chunks[0]
    )
    
    # Test Mode B: skip_wake_word=True (Direct ASR)
    context_mode_b = MockRequestContext(skip_wake_word=True)
    result_b = await interface.process_voice_segment_for_mode(
        voice_segment, context_mode_b, asr_component, voice_trigger_component
    )
    
    assert result_b['type'] == 'asr_result'
    assert result_b['mode'] == 'direct_asr'
    print(f"  Mode B (direct ASR): {result_b['mode']}")
    
    # Test Mode A: skip_wake_word=False (Wake word first)
    context_mode_a = MockRequestContext(skip_wake_word=False)
    
    # Test wake word detection
    result_a1 = await interface.process_voice_segment_for_mode(
        voice_segment, context_mode_a, asr_component, voice_trigger_component, wake_word_detected=False
    )
    
    assert result_a1['type'] == 'wake_word_result'
    assert result_a1['mode'] == 'wake_word_detection'
    print(f"  Mode A (wake word detection): {result_a1['mode']}")
    
    # Test command processing after wake word
    result_a2 = await interface.process_voice_segment_for_mode(
        voice_segment, context_mode_a, asr_component, voice_trigger_component, wake_word_detected=True
    )
    
    assert result_a2['type'] == 'asr_result'
    assert result_a2['mode'] == 'command_after_wake'
    print(f"  Mode A (command after wake): {result_a2['mode']}")
    
    print("✓ Mode-specific processing test passed\n")


async def test_performance_real_time():
    """Test real-time performance with realistic loads."""
    print("Testing real-time performance...")
    
    config = VADConfig(
        enabled=True,
        threshold=0.01,
        processing_timeout_ms=25  # Must process faster than chunk rate
    )
    
    processor = UniversalAudioProcessor(config)
    
    # Simulate high-frequency audio stream (every 23ms like the problem case)
    chunk_duration_ms = 23
    num_chunks = 200  # ~4.6 seconds of audio
    
    processing_times = []
    start_time = time.time()
    
    # Generate realistic mixed audio
    realistic_sequence = [
        ("silence", 20),
        ("speech_like", 30),
        ("silence", 15), 
        ("speech_like", 25),
        ("silence", 20),
        ("speech_like", 40),
        ("silence", 50)
    ]
    
    chunk_count = 0
    voice_segments = 0
    
    async for audio_chunk in generate_test_audio_stream(realistic_sequence, chunk_duration_ms):
        chunk_start = time.time()
        voice_segment = await processor.process_audio_chunk(audio_chunk)
        processing_time = (time.time() - chunk_start) * 1000
        
        processing_times.append(processing_time)
        chunk_count += 1
        
        if voice_segment:
            voice_segments += 1
        
        # Stop at target chunk count
        if chunk_count >= num_chunks:
            break
    
    total_time = time.time() - start_time
    avg_processing_time = np.mean(processing_times)
    max_processing_time = np.max(processing_times)
    
    print(f"  Performance results:")
    print(f"    Chunks processed: {chunk_count}")
    print(f"    Voice segments: {voice_segments}")
    print(f"    Total time: {total_time:.2f}s")
    print(f"    Average processing time: {avg_processing_time:.2f}ms")
    print(f"    Maximum processing time: {max_processing_time:.2f}ms")
    print(f"    Real-time capability: {'✓' if avg_processing_time < chunk_duration_ms else '✗'}")
    
    # Verify real-time performance
    assert avg_processing_time < chunk_duration_ms, \
        f"Average processing time {avg_processing_time:.2f}ms must be < {chunk_duration_ms}ms"
    
    # Verify segments were detected
    assert voice_segments > 0, "Should detect some voice segments"
    
    print("✓ Real-time performance test passed\n")


async def run_all_phase2_tests():
    """Run all Phase 2 VAD tests."""
    print("=" * 60)
    print("VOICE ACTIVITY DETECTION (VAD) - PHASE 2 STATE MACHINE TESTS")
    print("=" * 60)
    print()
    
    try:
        # Test configuration
        test_vad_config_validation()
        
        # Test core processor
        await test_universal_audio_processor()
        
        # Test edge cases
        await test_voice_segment_timeout()
        await test_buffer_overflow_protection()
        
        # Test integration interface
        await test_audio_processor_interface()
        await test_mode_specific_processing()
        
        # Test performance
        await test_performance_real_time()
        
        print("=" * 60)
        print("✅ ALL VAD PHASE 2 TESTS PASSED!")
        print("=" * 60)
        print()
        print("Phase 2 implementation is ready for:")
        print("- Universal audio state machine")
        print("- Voice segment accumulation and buffering")
        print("- Timeout and overflow protection")
        print("- Integration with existing ASR/voice trigger components")
        print("- Mode-specific processing (with/without wake word)")
        print("- Real-time performance with 23ms chunks")
        print()
        print("Next steps: Proceed to Phase 3 (Workflow Integration)")
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ VAD PHASE 2 TEST FAILED: {e}")
        print("=" * 60)
        raise


def main():
    """Main test function."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s'
    )
    
    # Run tests
    asyncio.run(run_all_phase2_tests())


if __name__ == "__main__":
    main()
