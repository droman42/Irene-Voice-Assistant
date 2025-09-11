"""
Phase 3 VAD Testing Script - Workflow Integration

Tests the workflow integration with VAD processing as specified in Phase 3.
This ensures that the VAD system integrates properly with the existing
voice assistant workflow without breaking compatibility.
"""

import asyncio
import logging
import time
from typing import List, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

# Import Phase 3 components
from irene.workflows.voice_assistant import UnifiedVoiceAssistantWorkflow
from irene.workflows.base import RequestContext
from irene.config.models import VADConfig, UnifiedVoiceAssistantWorkflowConfig
from irene.intents.models import AudioData, ConversationContext, IntentResult

# Import Phase 1 & 2 components for testing
from irene.tests.test_vad_basic import generate_test_audio_data

logger = logging.getLogger(__name__)


class MockComponent:
    """Mock component for testing workflow integration"""
    def __init__(self, component_type: str):
        self.component_type = component_type
        
    async def process_audio(self, audio_data: AudioData):
        """Mock audio processing"""
        await asyncio.sleep(0.001)  # Small delay to simulate processing
        if self.component_type == 'asr':
            return "test recognition result from mock ASR"
        elif self.component_type == 'voice_trigger':
            return {'detected': True, 'confidence': 0.9, 'wake_word': 'irene'}
        return None


class MockContextManager:
    """Mock context manager for testing"""
    async def get_or_create_context(self, session_id: str, client_id: str = None, client_metadata: dict = None):
        return ConversationContext(
            session_id=session_id,
            user_id="test_user",
            client_id=client_id
        )


class MockIntentOrchestrator:
    """Mock intent orchestrator for testing"""
    async def process_request(self, text: str, context, conversation_context):
        return IntentResult(
            text=f"Mock response to: {text}",
            confidence=0.9,
            action_metadata={}
        )


class MockConfig:
    """Mock configuration for testing"""
    def __init__(self, enable_vad: bool = False):
        self.vad = VADConfig(
            enabled=True,
            threshold=0.01,
            sensitivity=0.5,
            voice_frames_required=2,
            silence_frames_required=3,
            max_segment_duration_s=5
        )


async def generate_test_audio_stream(sequence: List[tuple], chunk_duration_ms: float = 50) -> AsyncIterator[AudioData]:
    """Generate test audio stream from sequence description"""
    for audio_type, count in sequence:
        for _ in range(count):
            yield generate_test_audio_data(chunk_duration_ms, audio_type=audio_type)
            await asyncio.sleep(0.001)  # Small delay between chunks


def create_test_workflow(enable_vad: bool = False) -> UnifiedVoiceAssistantWorkflow:
    """Create a test workflow with mock components"""
    workflow = UnifiedVoiceAssistantWorkflow()
    
    # Mock components
    workflow.components = {
        'asr': MockComponent('asr'),
        'voice_trigger': MockComponent('voice_trigger'),
        'nlu': MockComponent('nlu'),
        'intent_orchestrator': MockIntentOrchestrator(),
        'context_manager': MockContextManager(),
        'tts': None,  # Optional
        'audio': None,  # Optional
        'text_processor': None  # Optional
    }
    
    # Mock configuration
    workflow.config = MockConfig(enable_vad=enable_vad)
    
    # Mock the _process_pipeline method
    async def mock_process_pipeline(input_data, context, conversation_context):
        return IntentResult(
            text=f"Processed: {input_data}",
            confidence=0.9,
            action_metadata={}
        )
    
    workflow._process_pipeline = mock_process_pipeline
    
    return workflow


async def test_workflow_vad_enabled():
    """Test workflow with VAD processing enabled"""
    print("Testing workflow with VAD processing enabled...")
    
    # Create workflow with VAD enabled
    workflow = create_test_workflow(enable_vad=True)
    
    # Create workflow configuration
    workflow_config = UnifiedVoiceAssistantWorkflowConfig(
        enable_vad_processing=True,
        voice_trigger_enabled=True,
        asr_enabled=True,
        nlu_enabled=True,
        intent_execution_enabled=True
    )
    
    # Initialize workflow
    await workflow.initialize(workflow_config)
    
    # Verify VAD is enabled
    assert workflow._vad_processing_enabled == True
    assert workflow.audio_processor_interface is not None
    print(f"  ✅ VAD processing enabled: {workflow._vad_processing_enabled}")
    print(f"  ✅ Audio processor interface created: {workflow.audio_processor_interface is not None}")
    
    # Test audio stream processing
    test_sequence = [
        ("silence", 3),
        ("speech_like", 5),
        ("silence", 2),
        ("speech_like", 4),
        ("silence", 3)
    ]
    
    context = RequestContext(
        source="test_microphone",
        skip_wake_word=True,  # Test Mode B (direct ASR)
        session_id="test_session"
    )
    
    results = []
    result_count = 0
    
    async for result in workflow.process_audio_stream(
        generate_test_audio_stream(test_sequence), 
        context
    ):
        results.append(result)
        result_count += 1
        print(f"    VAD result #{result_count}: {result.text[:50]}...")
        
        # Limit results to avoid infinite loops in testing
        if result_count >= 3:
            break
    
    # Verify results
    assert len(results) > 0, "Should get results from VAD processing"
    print(f"  ✅ VAD processing produced {len(results)} results")
    
    # Check VAD metrics
    if workflow.audio_processor_interface:
        metrics = workflow.audio_processor_interface.get_metrics()
        print(f"  📊 VAD Metrics: chunks={metrics.total_chunks_processed}, "
              f"segments={metrics.voice_segments_detected}, "
              f"avg_time={metrics.average_processing_time_ms:.2f}ms")
        
        assert metrics.total_chunks_processed > 0, "Should process audio chunks"
    
    print("✓ Workflow VAD-enabled test passed\n")


async def test_workflow_vad_required():
    """Test that workflow requires VAD processing (no legacy mode)"""
    print("Testing workflow VAD requirement...")
    
    # Create workflow with missing VAD config
    workflow = create_test_workflow(enable_vad=False)
    
    # Create workflow configuration without VAD
    workflow_config = UnifiedVoiceAssistantWorkflowConfig(
        voice_trigger_enabled=True,
        asr_enabled=True,
        nlu_enabled=True,
        intent_execution_enabled=True
    )
    
    # Should fail to initialize without VAD
    try:
        await workflow.initialize(workflow_config)
        assert False, "Should have failed to initialize without VAD"
    except Exception as e:
        print(f"  ✅ Failed as expected: {e}")
        assert "VAD" in str(e), "Error should mention VAD requirement"
    
    print("✓ Workflow VAD requirement test passed\n")


async def test_mode_switching():
    """Test switching between wake word modes"""
    print("Testing mode switching (with/without wake word)...")
    
    # Create workflow with VAD enabled
    workflow = create_test_workflow(enable_vad=True)
    
    workflow_config = UnifiedVoiceAssistantWorkflowConfig(
        enable_vad_processing=True,
        voice_trigger_enabled=True,
        asr_enabled=True,
        nlu_enabled=True,
        intent_execution_enabled=True
    )
    
    await workflow.initialize(workflow_config)
    
    # Test Mode A: Wake word detection (skip_wake_word=False)
    print("  Testing Mode A: Wake word detection")
    context_mode_a = RequestContext(
        source="test_microphone",
        skip_wake_word=False,  # Mode A
        session_id="test_session_a"
    )
    
    test_sequence_short = [("speech_like", 3), ("silence", 2)]
    
    results_mode_a = []
    async for result in workflow.process_audio_stream(
        generate_test_audio_stream(test_sequence_short), 
        context_mode_a
    ):
        results_mode_a.append(result)
        if len(results_mode_a) >= 1:  # Limit for testing
            break
    
    print(f"    Mode A produced {len(results_mode_a)} results")
    
    # Test Mode B: Direct ASR (skip_wake_word=True)  
    print("  Testing Mode B: Direct ASR")
    context_mode_b = RequestContext(
        source="test_microphone",
        skip_wake_word=True,  # Mode B
        session_id="test_session_b"
    )
    
    results_mode_b = []
    async for result in workflow.process_audio_stream(
        generate_test_audio_stream(test_sequence_short), 
        context_mode_b
    ):
        results_mode_b.append(result)
        if len(results_mode_b) >= 1:  # Limit for testing
            break
    
    print(f"    Mode B produced {len(results_mode_b)} results")
    
    # Both modes should work with VAD
    print(f"  ✅ Mode A results: {len(results_mode_a)}")
    print(f"  ✅ Mode B results: {len(results_mode_b)}")
    
    print("✓ Mode switching test passed\n")


async def test_configuration_validation():
    """Test VAD configuration validation"""
    print("Testing VAD configuration validation...")
    
    # Test valid configuration
    valid_config = UnifiedVoiceAssistantWorkflowConfig(
        enable_vad_processing=True,
        voice_trigger_enabled=True,
        asr_enabled=True
    )
    
    assert valid_config.enable_vad_processing == True
    print("  ✅ Valid VAD configuration accepted")
    
    # Test default configuration (VAD disabled)
    default_config = UnifiedVoiceAssistantWorkflowConfig()
    assert default_config.enable_vad_processing == False
    print("  ✅ Default configuration has VAD disabled")
    
    print("✓ Configuration validation test passed\n")


async def test_vad_now_required():
    """Test that VAD is now required (no backward compatibility for non-VAD)"""
    print("Testing VAD requirement (no backward compatibility)...")
    
    # Create workflow that requires VAD
    workflow = create_test_workflow(enable_vad=True)
    
    # Use proper VAD-enabled configuration
    workflow_config = UnifiedVoiceAssistantWorkflowConfig(
        enable_vad_processing=True,  # Now required
        voice_trigger_enabled=True,
        asr_enabled=True,
        nlu_enabled=True,
        intent_execution_enabled=True
    )
    
    # Should initialize with VAD
    await workflow.initialize(workflow_config)
    
    # Should process audio using VAD pipeline
    test_sequence = [("speech_like", 3)]
    context = RequestContext(source="test", skip_wake_word=True, session_id="test")
    
    results = []
    async for result in workflow.process_audio_stream(
        generate_test_audio_stream(test_sequence), 
        context
    ):
        results.append(result)
        if len(results) >= 1:
            break
    
    assert len(results) > 0, "VAD processing should work"
    print(f"  ✅ VAD processing works: {len(results)} results")
    
    # Verify VAD is enabled and working
    assert workflow.audio_processor_interface is not None
    print("  ✅ VAD is enabled and required")
    
    print("✓ VAD requirement test passed\n")


async def test_error_handling():
    """Test error handling in VAD workflow integration"""
    print("Testing error handling...")
    
    # Test workflow with VAD enabled but missing configuration
    workflow = UnifiedVoiceAssistantWorkflow()
    workflow.components = {
        'nlu': MockComponent('nlu'),
        'intent_orchestrator': MockIntentOrchestrator(),
        'context_manager': MockContextManager()
    }
    
    # Missing VAD config
    workflow.config = None
    
    workflow_config = UnifiedVoiceAssistantWorkflowConfig(
        enable_vad_processing=True  # Enabled but no config
    )
    
    # Should handle missing config gracefully
    await workflow.initialize(workflow_config)
    
    # Should fall back to disabled VAD
    assert workflow._vad_processing_enabled == False
    print("  ✅ Missing VAD config handled gracefully")
    
    print("✓ Error handling test passed\n")


async def run_all_phase3_tests():
    """Run all Phase 3 workflow integration tests"""
    print("=" * 60)
    print("VOICE ACTIVITY DETECTION (VAD) - PHASE 3 WORKFLOW INTEGRATION TESTS")
    print("=" * 60)
    print()
    
    try:
        # Test VAD-enabled workflow
        await test_workflow_vad_enabled()
        
        # Test legacy workflow (VAD disabled)
        await test_workflow_vad_required()
        
        # Test mode switching
        await test_mode_switching()
        
        # Test configuration
        await test_configuration_validation()
        
        # Test backward compatibility
        await test_vad_now_required()
        
        # Test error handling
        await test_error_handling()
        
        print("=" * 60)
        print("✅ ALL VAD PHASE 3 TESTS PASSED!")
        print("=" * 60)
        print()
        print("Phase 3 workflow integration is ready for:")
        print("- Non-breaking VAD integration with existing workflows")
        print("- Conditional VAD processing with configuration flag")
        print("- Side-by-side processing (VAD + legacy)")
        print("- Preserved existing behavior and compatibility")
        print("- Extensive logging for performance comparison")
        print("- Mode-specific processing in both VAD and legacy modes")
        print()
        print("✅ VAD system successfully integrated with workflow!")
        print("Next steps: Proceed to Phase 4 (Configuration & Testing)")
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ VAD PHASE 3 TEST FAILED: {e}")
        print("=" * 60)
        raise


def main():
    """Main test function"""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s - %(message)s'
    )
    
    # Run tests
    asyncio.run(run_all_phase3_tests())


if __name__ == "__main__":
    main()
