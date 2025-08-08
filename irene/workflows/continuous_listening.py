"""
Continuous Listening Workflow - Backward compatibility workflow

This workflow maintains the current behavior for users who don't want wake words.
It processes audio directly: Audio → ASR → Intent → Response (no wake word detection).
"""

import logging
from typing import AsyncIterator, Optional, Dict, Any, List

from .base import Workflow, RequestContext
from ..intents.models import AudioData, ConversationContext, Intent, IntentResult
from ..utils.audio_helpers import test_audio_playback_capability, calculate_audio_buffer_size
from ..config.manager import ConfigurationError

logger = logging.getLogger(__name__)


class ContinuousListeningWorkflow(Workflow):
    """Backward compatibility - direct ASR without wake word"""
    
    def __init__(self):
        super().__init__()
        self.asr = None
        self.text_processor = None
        self.nlu = None
        self.intent_orchestrator = None
        self.tts = None
        self.audio = None
        self.context_manager = None
        self.buffer_size = None
        
    async def initialize(self):
        """Initialize continuous listening workflow"""
        if self.initialized:
            return
            
        self.logger.info("Initializing ContinuousListeningWorkflow...")
        
        # Validate audio capability
        try:
            capabilities = await test_audio_playback_capability()  # From audio_helpers.py
            if not capabilities.get('devices_available', False):
                self.logger.warning("No audio devices available - text-only mode")
            else:
                self.logger.info(f"Audio capabilities validated: {capabilities}")
                
        except Exception as e:
            self.logger.warning(f"Audio capability check failed: {e} - continuing with text-only mode")
            
        # Configure buffer for ASR pipeline (no wake word processing)
        self.buffer_size = calculate_audio_buffer_size(16000, 200.0)  # Larger buffer for ASR
        self.logger.info(f"Configured audio buffer size: {self.buffer_size}")
        
        # Validate required components
        required_components = ['asr', 'nlu', 'intent_orchestrator', 'context_manager']
        for comp_name in required_components:
            if comp_name not in self.components:
                raise ConfigurationError(f"Required component '{comp_name}' not available")
        
        # Get component references (no voice trigger)
        self.asr = self.components['asr']
        self.text_processor = self.components.get('text_processor')  # Optional
        self.nlu = self.components['nlu'] 
        self.intent_orchestrator = self.components['intent_orchestrator']
        self.tts = self.components.get('tts')  # Optional
        self.audio = self.components.get('audio')  # Optional
        self.context_manager = self.components['context_manager']
        
        self.logger.info("ContinuousListeningWorkflow initialized successfully")
        self.initialized = True
    
    async def process_audio_stream(self, audio_stream: AsyncIterator[AudioData], context: RequestContext) -> AsyncIterator[IntentResult]:
        """
        Legacy workflow: Audio → ASR → Intent → Response (no wake word)
        
        Args:
            audio_stream: Async iterator of audio data from input source
            context: Request context
            
        Yields:
            IntentResult objects as they are generated
        """
        if not self.initialized:
            await self.initialize()
            
        self.logger.info(f"Starting continuous listening workflow for session {context.session_id}")
        
        # Get or create conversation context
        conv_context = await self.context_manager.get_context(context.session_id)
        
        # Audio processing without wake word detection
        audio_buffer = []
        silence_counter = 0
        max_silence_chunks = 20  # Adjust based on requirements
        
        try:
            async for audio_data in audio_stream:
                # Collect audio data continuously
                audio_buffer.append(audio_data)
                
                # Simple voice activity detection (replace with more sophisticated VAD if needed)
                audio_level = self._calculate_audio_level(audio_data)
                
                if audio_level < 0.01:  # Threshold for silence
                    silence_counter += 1
                else:
                    silence_counter = 0
                
                # Process when we have enough audio and detect end of speech
                if len(audio_buffer) >= 5 and (silence_counter >= max_silence_chunks or len(audio_buffer) >= 50):
                    # Combine audio data
                    combined_audio = self._combine_audio_data(audio_buffer)
                    
                    # Process through ASR → Intent pipeline
                    try:
                        text = await self._transcribe_audio(combined_audio)
                        
                        if text and text.strip():
                            self.logger.info(f"Transcribed: '{text}'")
                            
                            # Process the recognized text through intent system
                            result = await self._process_text_pipeline(text, conv_context, context)
                            if result:
                                yield result
                        
                        # Reset buffer for next utterance
                        audio_buffer = []
                        silence_counter = 0
                        
                    except Exception as e:
                        self.logger.error(f"ASR processing error: {e}")
                        yield IntentResult(
                            text="Sorry, I couldn't understand that.",
                            should_speak=True,
                            success=False,
                            error=str(e)
                        )
                        
                        # Reset state
                        audio_buffer = []
                        silence_counter = 0
                        
        except Exception as e:
            self.logger.error(f"Audio stream processing error: {e}")
            yield IntentResult(
                text="Sorry, there was an audio processing error.",
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    async def process_text_input(self, text: str, context: RequestContext) -> IntentResult:
        """
        Process text input through the workflow.
        
        Args:
            text: Input text to process
            context: Request context
            
        Returns:
            IntentResult from processing
        """
        if not self.initialized:
            await self.initialize()
            
        self.logger.info(f"Processing text input: '{text[:50]}...' for session {context.session_id}")
        
        # Get or create conversation context
        conv_context = await self.context_manager.get_context(context.session_id)
        
        return await self._process_text_pipeline(text, conv_context, context)
    
    async def _transcribe_audio(self, audio_data: AudioData) -> Optional[str]:
        """Transcribe audio using ASR component."""
        if not self.asr or not await self.asr.is_available():
            raise RuntimeError("ASR component not available")
        
        try:
            # Use the ASR component to transcribe
            return await self.asr.transcribe(audio_data.data,
                                           sample_rate=audio_data.sample_rate,
                                           channels=audio_data.channels)
        except Exception as e:
            self.logger.error(f"ASR transcription failed: {e}")
            return None
    
    async def _process_text_pipeline(self, text: str, conv_context: ConversationContext, request_context: RequestContext) -> IntentResult:
        """
        Process text through: Text Processing → Intent Recognition → Intent Execution → Response
        
        Args:
            text: Recognized or input text
            conv_context: Conversation context
            request_context: Request context
            
        Returns:
            IntentResult from processing
        """
        try:
            # Text Processing (using existing irene/utils/text_processing.py)
            improved_text = text
            if self.text_processor and await self.text_processor.is_available():
                try:
                    improved_text = await self.text_processor.improve(text, conv_context, stage="asr_output")
                    if improved_text != text:
                        self.logger.debug(f"Text improved: '{text}' → '{improved_text}'")
                except Exception as e:
                    self.logger.warning(f"Text processing failed, using original: {e}")
                    improved_text = text
            
            # Intent Recognition
            intent = await self.nlu.recognize(improved_text, conv_context)
            self.logger.info(f"Intent recognized: {intent.name} (confidence: {intent.confidence:.2f})")
            
            # Intent Execution
            result = await self.intent_orchestrator.execute_intent(intent, conv_context)
            
            # Response Output
            await self._route_response(result, request_context, conv_context)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Text processing pipeline failed: {e}")
            return IntentResult(
                text="Sorry, I encountered an error processing your request.",
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    async def _route_response(self, result: IntentResult, request_context: RequestContext, conv_context: ConversationContext):
        """Route response through appropriate output channels."""
        try:
            # Update conversation context
            conv_context.add_assistant_turn(result)
            
            # Handle TTS if requested and available
            if result.should_speak and request_context.wants_audio:
                if self.tts and await self.tts.is_available():
                    try:
                        # Generate speech
                        audio_data = await self.tts.synthesize(result.text)
                        
                        # Play audio if audio component available
                        if self.audio and await self.audio.is_available():
                            await self.audio.play(audio_data)
                            
                    except Exception as e:
                        self.logger.error(f"TTS/Audio output failed: {e}")
                        # Continue without audio output
            
            # Handle additional actions
            for action in result.actions:
                try:
                    await self._execute_action(action, conv_context)
                except Exception as e:
                    self.logger.error(f"Action execution failed for '{action}': {e}")
                    
        except Exception as e:
            self.logger.error(f"Response routing failed: {e}")
    
    async def _execute_action(self, action: str, conv_context: ConversationContext):
        """Execute additional actions from intent result."""
        # TODO: Implement action execution system
        self.logger.debug(f"Action execution not yet implemented for: {action}")
    
    def _calculate_audio_level(self, audio_data: AudioData) -> float:
        """Calculate simple audio level for voice activity detection."""
        try:
            if isinstance(audio_data.data, bytes):
                import numpy as np
                audio_array = np.frombuffer(audio_data.data, dtype=np.int16)
                return float(np.abs(audio_array).mean()) / 32768.0
            return 0.0
        except Exception:
            return 0.0
    
    def _combine_audio_data(self, audio_buffer: list) -> AudioData:
        """Combine multiple AudioData objects into one."""
        if not audio_buffer:
            return AudioData(data=b'', timestamp=0.0)
        
        # Combine audio data
        combined_data = b''.join(audio.data for audio in audio_buffer)
        
        # Use properties from first audio data
        first_audio = audio_buffer[0]
        return AudioData(
            data=combined_data,
            timestamp=first_audio.timestamp,
            sample_rate=first_audio.sample_rate,
            channels=first_audio.channels,
            format=first_audio.format
        ) 
    
    def __repr__(self) -> str:
        return f"ContinuousListeningWorkflow(initialized={self.initialized}, listening={self.listening})"
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Continuous listening workflow needs audio processing and async support"""
        return ["sounddevice>=0.4.0", "soundfile>=0.12.0"] 