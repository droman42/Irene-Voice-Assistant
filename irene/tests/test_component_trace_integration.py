"""
Test suite for Component Trace Integration (Phase 6)
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from ..core.trace_context import TraceContext
from ..components.text_processor_component import TextProcessorComponent
from ..components.nlu_component import NLUComponent
from ..components.asr_component import ASRComponent
from ..components.tts_component import TTSComponent
from ..components.voice_trigger_component import VoiceTriggerComponent
from ..components.audio_component import AudioComponent
from ..components.llm_component import LLMComponent
from ..intents.orchestrator import IntentOrchestrator
from ..intents.models import Intent, IntentResult, ConversationContext, AudioData, WakeWordResult
from ..intents.registry import IntentRegistry


class TestComponentTraceIntegration(unittest.IsolatedAsyncioTestCase):
    """Test trace integration with all major components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.trace_context = TraceContext(enabled=True)
        self.conversation_context = ConversationContext(
            session_id="test_session",
            user_id="test_user",
            conversation_history=[]
        )
    
    async def test_text_processor_component_trace(self):
        """Test TextProcessorComponent with trace context"""
        component = TextProcessorComponent()
        component.providers = {}  # No providers for test
        
        # Test with trace context
        result = await component.process("test text", self.trace_context)
        
        # Verify the result is correct
        self.assertEqual(result, "test text")
        
        # Verify trace was recorded
        self.assertEqual(len(self.trace_context.stages), 1)
        stage = self.trace_context.stages[0]
        self.assertEqual(stage["stage"], "text_processing")
        self.assertEqual(stage["input"], "test text")
        self.assertEqual(stage["output"], "test text")
        self.assertIn("component_name", stage["metadata"])
        self.assertEqual(stage["metadata"]["component_name"], "TextProcessorComponent")
    
    async def test_nlu_component_trace(self):
        """Test NLUComponent with trace context"""
        component = NLUComponent()
        
        # Mock the recognize_with_context method
        test_intent = Intent(
            name="test.intent",
            entities={},
            confidence=0.95,
            raw_text="test input",
            domain="test",
            action="test_action"
        )
        component.recognize_with_context = AsyncMock(return_value=test_intent)
        component.providers = {"mock": MagicMock()}
        
        # Test with trace context
        result = await component.process("test input", self.conversation_context, self.trace_context)
        
        # Verify the result is correct
        self.assertEqual(result.name, "test.intent")
        self.assertEqual(result.confidence, 0.95)
        
        # Verify trace was recorded
        self.assertEqual(len(self.trace_context.stages), 1)
        stage = self.trace_context.stages[0]
        self.assertEqual(stage["stage"], "nlu_cascade")
        self.assertEqual(stage["input"], "test input")
        self.assertIn("component_name", stage["metadata"])
        self.assertEqual(stage["metadata"]["component_name"], "NLUComponent")
    
    async def test_asr_component_trace(self):
        """Test ASRComponent with trace context"""
        component = ASRComponent()
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.transcribe = AsyncMock(return_value="transcribed text")
        component.providers = {"test_provider": mock_provider}
        component.default_provider = "test_provider"
        
        # Create test audio data
        audio_data = AudioData(
            data=b"fake audio data",
            timestamp=1234567890.0,
            sample_rate=16000,
            channels=1,
            format="wav"
        )
        
        # Test with trace context
        result = await component.process_audio(audio_data, self.trace_context)
        
        # Verify the result is correct
        self.assertEqual(result, "transcribed text")
        
        # Verify trace was recorded
        self.assertEqual(len(self.trace_context.stages), 1)
        stage = self.trace_context.stages[0]
        self.assertEqual(stage["stage"], "asr_transcription")
        self.assertIn("component_name", stage["metadata"])
        self.assertEqual(stage["metadata"]["component_name"], "ASRComponent")
    
    async def test_tts_component_trace(self):
        """Test TTSComponent with trace context"""
        component = TTSComponent()
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.synthesize_to_file = AsyncMock()
        component._get_provider = AsyncMock(return_value=mock_provider)
        
        output_path = Path("/tmp/test_output.wav")
        
        # Test with trace context
        await component.synthesize_to_file("test text", output_path, self.trace_context)
        
        # Verify trace was recorded
        self.assertEqual(len(self.trace_context.stages), 1)
        stage = self.trace_context.stages[0]
        self.assertEqual(stage["stage"], "tts_synthesis")
        self.assertEqual(stage["input"], "test text")
        self.assertIn("component_name", stage["metadata"])
        self.assertEqual(stage["metadata"]["component_name"], "TTSComponent")
    
    async def test_voice_trigger_component_trace(self):
        """Test VoiceTriggerComponent with trace context"""
        component = VoiceTriggerComponent()
        
        # Mock the detect method
        test_result = WakeWordResult(detected=True, word="test", confidence=0.9)
        component.detect = AsyncMock(return_value=test_result)
        component.wake_words = ["test"]
        component.threshold = 0.8
        component.default_provider = "test_provider"
        
        # Create test audio data
        audio_data = AudioData(
            data=b"fake audio data",
            timestamp=1234567890.0,
            sample_rate=16000,
            channels=1,
            format="wav"
        )
        
        # Test with trace context
        result = await component.process_audio(audio_data, self.trace_context)
        
        # Verify the result is correct
        self.assertTrue(result.detected)
        self.assertEqual(result.word, "test")
        self.assertEqual(result.confidence, 0.9)
        
        # Verify trace was recorded
        self.assertEqual(len(self.trace_context.stages), 1)
        stage = self.trace_context.stages[0]
        self.assertEqual(stage["stage"], "voice_trigger_detection")
        self.assertIn("component_name", stage["metadata"])
        self.assertEqual(stage["metadata"]["component_name"], "VoiceTriggerComponent")
    
    async def test_audio_component_trace(self):
        """Test AudioComponent with trace context"""
        component = AudioComponent()
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.play_file = AsyncMock()
        component.providers = {"test_provider": mock_provider}
        component.default_provider = "test_provider"
        
        # Create test file path
        test_file = Path("/tmp/test_audio.wav")
        
        # Mock the file existence check
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'stat') as mock_stat:
            mock_stat.return_value.st_size = 1024
            
            # Test with trace context
            await component.play_file(test_file, self.trace_context)
        
        # Verify trace was recorded
        self.assertEqual(len(self.trace_context.stages), 1)
        stage = self.trace_context.stages[0]
        self.assertEqual(stage["stage"], "audio_playback")
        self.assertIn("component_name", stage["metadata"])
        self.assertEqual(stage["metadata"]["component_name"], "AudioComponent")
    
    async def test_intent_orchestrator_trace(self):
        """Test IntentOrchestrator with trace context"""
        registry = IntentRegistry()
        orchestrator = IntentOrchestrator(registry)
        
        # Mock the execute_intent method
        test_result = IntentResult(
            text="Test response",
            success=True,
            confidence=0.95
        )
        orchestrator.execute_intent = AsyncMock(return_value=test_result)
        
        # Create test intent
        test_intent = Intent(
            name="test.intent",
            entities={},
            confidence=0.95,
            raw_text="test input",
            domain="test",
            action="test_action"
        )
        
        # Test with trace context
        result = await orchestrator.execute(test_intent, self.conversation_context, self.trace_context)
        
        # Verify the result is correct
        self.assertTrue(result.success)
        self.assertEqual(result.text, "Test response")
        
        # Verify trace was recorded
        self.assertEqual(len(self.trace_context.stages), 1)
        stage = self.trace_context.stages[0]
        self.assertEqual(stage["stage"], "intent_execution")
        self.assertIn("component_name", stage["metadata"])
        self.assertEqual(stage["metadata"]["component_name"], "IntentOrchestrator")
    
    async def test_llm_component_enhance_text_trace(self):
        """Test LLMComponent enhance_text method with trace context"""
        component = LLMComponent()
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.enhance_text = AsyncMock(return_value="Enhanced text output")
        component.providers = {"test_provider": mock_provider}
        component.default_provider = "test_provider"
        
        # Test with trace context
        result = await component.enhance_text("test input text", "improve", self.trace_context)
        
        # Verify the result is correct
        self.assertEqual(result, "Enhanced text output")
        
        # Verify trace was recorded
        self.assertEqual(len(self.trace_context.stages), 1)
        stage = self.trace_context.stages[0]
        self.assertEqual(stage["stage"], "llm_enhancement")
        self.assertEqual(stage["input"], "test input text")
        self.assertEqual(stage["output"], "Enhanced text output")
        self.assertIn("component_name", stage["metadata"])
        self.assertEqual(stage["metadata"]["component_name"], "LLMComponent")
        self.assertEqual(stage["metadata"]["task"], "improve")
        self.assertTrue(stage["metadata"]["enhancement_success"])
    
    async def test_llm_component_generate_response_trace(self):
        """Test LLMComponent generate_response method with trace context"""
        component = LLMComponent()
        
        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.chat_completion = AsyncMock(return_value="Generated response")
        component.providers = {"test_provider": mock_provider}
        component.default_provider = "test_provider"
        
        # Test messages
        test_messages = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well, thank you!"}
        ]
        
        # Test with trace context
        result = await component.generate_response(test_messages, trace_context=self.trace_context)
        
        # Verify the result is correct
        self.assertEqual(result, "Generated response")
        
        # Verify trace was recorded
        self.assertEqual(len(self.trace_context.stages), 1)
        stage = self.trace_context.stages[0]
        self.assertEqual(stage["stage"], "llm_conversation")
        self.assertEqual(stage["output"], "Generated response")
        self.assertIn("component_name", stage["metadata"])
        self.assertEqual(stage["metadata"]["component_name"], "LLMComponent")
        self.assertEqual(stage["metadata"]["message_count"], 2)
        self.assertTrue(stage["metadata"]["generation_success"])
    
    async def test_zero_overhead_when_disabled(self):
        """Test that components have zero overhead when trace is disabled"""
        import time
        
        # Create disabled trace context
        disabled_trace = TraceContext(enabled=False)
        
        # Test with TextProcessorComponent
        text_component = TextProcessorComponent()
        text_component.providers = {}
        
        # Test with LLMComponent
        llm_component = LLMComponent()
        mock_provider = AsyncMock()
        mock_provider.enhance_text = AsyncMock(return_value="enhanced")
        llm_component.providers = {"test": mock_provider}
        llm_component.default_provider = "test"
        
        # Measure with disabled trace
        start_time = time.perf_counter()
        for _ in range(50):
            await text_component.process("test", disabled_trace)
            await llm_component.enhance_text("test", trace_context=disabled_trace)
        disabled_time = time.perf_counter() - start_time
        
        # Measure without trace
        start_time = time.perf_counter()
        for _ in range(50):
            await text_component.process("test")
            await llm_component.enhance_text("test")
        no_trace_time = time.perf_counter() - start_time
        
        # Disabled trace should have minimal overhead
        overhead = disabled_time - no_trace_time
        self.assertLess(overhead, no_trace_time * 0.5, 
                       f"Disabled trace overhead ({overhead:.6f}s) too high compared to no trace ({no_trace_time:.6f}s)")
        
        # Verify no trace data was collected
        self.assertEqual(len(disabled_trace.stages), 0)


if __name__ == "__main__":
    unittest.main()
