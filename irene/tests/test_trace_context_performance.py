"""
Test suite for TraceContext performance and zero overhead validation
"""

import time
import unittest
from unittest.mock import MagicMock

from ..core.trace_context import TraceContext
from ..intents.models import UnifiedConversationContext


class TestTraceContextPerformance(unittest.TestCase):
    """Test TraceContext performance characteristics"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_conversation_context = MagicMock(spec=ConversationContext)
        self.mock_conversation_context.active_actions = {"test": {"action": "test_action"}}
        self.mock_conversation_context.conversation_history = []
        self.mock_conversation_context.session_id = "test_session"
        self.mock_conversation_context.user_id = "test_user"
    
    def test_zero_overhead_when_disabled(self):
        """Test that TraceContext has zero overhead when disabled"""
        trace_context = TraceContext(enabled=False)
        
        # Measure time for disabled trace operations
        start_time = time.perf_counter()
        
        # Perform operations that should have zero overhead
        for _ in range(1000):
            trace_context.record_stage(
                stage_name="test_stage",
                input_data="test_input",
                output_data="test_output",
                metadata={"test": "metadata"},
                processing_time_ms=1.0
            )
            
            trace_context.record_context_snapshot("before", self.mock_conversation_context)
        
        disabled_time = time.perf_counter() - start_time
        
        # Measure time for enabled trace operations
        trace_context_enabled = TraceContext(enabled=True)
        start_time = time.perf_counter()
        
        for _ in range(1000):
            trace_context_enabled.record_stage(
                stage_name="test_stage",
                input_data="test_input",
                output_data="test_output",
                metadata={"test": "metadata"},
                processing_time_ms=1.0
            )
            
            trace_context_enabled.record_context_snapshot("before", self.mock_conversation_context)
        
        enabled_time = time.perf_counter() - start_time
        
        # Disabled should be significantly faster (at least 10x faster)
        self.assertLess(disabled_time, enabled_time / 10, 
                       f"Disabled time ({disabled_time:.6f}s) should be much less than enabled time ({enabled_time:.6f}s)")
        
        # Disabled should be very fast (under 1ms for 1000 operations)
        self.assertLess(disabled_time, 0.001, 
                       f"Disabled operations should be under 1ms, got {disabled_time:.6f}s")
    
    def test_disabled_trace_no_data_collection(self):
        """Test that disabled trace context doesn't collect any data"""
        trace_context = TraceContext(enabled=False)
        
        # Attempt to record data
        trace_context.record_stage(
            stage_name="test_stage",
            input_data="test_input", 
            output_data="test_output",
            metadata={"test": "metadata"},
            processing_time_ms=1.0
        )
        
        trace_context.record_context_snapshot("before", self.mock_conversation_context)
        trace_context.record_context_snapshot("after", self.mock_conversation_context)
        
        # Verify no data was collected
        self.assertEqual(len(trace_context.stages), 0)
        self.assertIsNone(trace_context.context_snapshots["before"])
        self.assertIsNone(trace_context.context_snapshots["after"])
        
        # Verify trace export reflects disabled state
        export = trace_context.export_trace()
        self.assertFalse(export["enabled"])
        self.assertIn("disabled", export["message"])
    
    def test_enabled_trace_data_collection(self):
        """Test that enabled trace context properly collects data"""
        trace_context = TraceContext(enabled=True)
        
        # Record test data
        trace_context.record_stage(
            stage_name="test_stage",
            input_data="test_input",
            output_data="test_output", 
            metadata={"test": "metadata"},
            processing_time_ms=1.5
        )
        
        trace_context.record_context_snapshot("before", self.mock_conversation_context)
        trace_context.record_context_snapshot("after", self.mock_conversation_context)
        
        # Verify data was collected
        self.assertEqual(len(trace_context.stages), 1)
        self.assertIsNotNone(trace_context.context_snapshots["before"])
        self.assertIsNotNone(trace_context.context_snapshots["after"])
        
        # Verify stage data
        stage = trace_context.stages[0]
        self.assertEqual(stage["stage"], "test_stage")
        self.assertEqual(stage["input"], "test_input")
        self.assertEqual(stage["output"], "test_output")
        self.assertEqual(stage["processing_time_ms"], 1.5)
        
        # Verify trace export contains data
        export = trace_context.export_trace()
        self.assertEqual(len(export["pipeline_stages"]), 1)
        self.assertIsNotNone(export["context_evolution"]["before"])
        self.assertIsNotNone(export["context_evolution"]["after"])
    
    def test_binary_data_sanitization(self):
        """Test that binary data is properly converted to base64"""
        trace_context = TraceContext(enabled=True)
        
        # Test binary data handling
        binary_data = b"test binary audio data"
        
        trace_context.record_stage(
            stage_name="test_stage",
            input_data=binary_data,
            output_data="test_output",
            metadata={},
            processing_time_ms=1.0
        )
        
        # Verify binary data was converted
        stage = trace_context.stages[0]
        input_data = stage["input"]
        
        self.assertIsInstance(input_data, dict)
        self.assertEqual(input_data["type"], "binary_audio_data")
        self.assertEqual(input_data["size_bytes"], len(binary_data))
        self.assertIn("base64_data", input_data)
    
    def test_audio_data_object_handling(self):
        """Test that AudioData objects are properly handled"""
        trace_context = TraceContext(enabled=True)
        
        # Mock AudioData object
        mock_audio_data = MagicMock()
        mock_audio_data.data = b"audio data bytes"
        mock_audio_data.sample_rate = 16000
        mock_audio_data.channels = 1
        mock_audio_data.format = "wav"
        
        trace_context.record_stage(
            stage_name="test_stage",
            input_data=mock_audio_data,
            output_data="test_output",
            metadata={},
            processing_time_ms=1.0
        )
        
        # Verify AudioData was properly converted
        stage = trace_context.stages[0]
        input_data = stage["input"]
        
        self.assertIsInstance(input_data, dict)
        self.assertEqual(input_data["type"], "audio_data_object")
        self.assertEqual(input_data["sample_rate"], 16000)
        self.assertEqual(input_data["channels"], 1)
        self.assertEqual(input_data["format"], "wav")
        self.assertIn("base64_data", input_data)


if __name__ == "__main__":
    unittest.main()
