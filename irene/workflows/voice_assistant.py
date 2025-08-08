"""
Voice Assistant Workflow - Complete voice assistant workflow with intent system

This workflow implements the main pipeline:
Audio → Voice Trigger → ASR → Text Processing → Intent Recognition → Intent Execution → Response

Enhanced with existing audio_helpers.py utilities for optimal performance.
"""

import asyncio
import logging
from typing import AsyncIterator, Optional, Dict, Any, List

from .base import Workflow, RequestContext
from ..intents.models import AudioData, ConversationContext, Intent, IntentResult, WakeWordResult
from ..utils.audio_helpers import test_audio_playback_capability, calculate_audio_buffer_size
from ..utils.loader import safe_import
from ..config.manager import ConfigurationError

logger = logging.getLogger(__name__)


class VoiceAssistantWorkflow(Workflow):
    """Complete voice assistant workflow with intent system"""
    
    def __init__(self):
        super().__init__()
        self.voice_trigger = None
        self.asr = None
        self.text_processor = None
        self.nlu = None
        self.intent_orchestrator = None
        self.tts = None
        self.audio = None
        self.context_manager = None
        self.buffer_size = None
        
    async def initialize(self):
        """Initialize audio pipeline using existing audio_helpers.py utilities"""
        if self.initialized:
            return
            
        self.logger.info("Initializing VoiceAssistantWorkflow...")
        
        # Validate audio capability before starting
        try:
            capabilities = await test_audio_playback_capability()  # From audio_helpers.py
            if not capabilities.get('devices_available', False):
                raise ConfigurationError("No audio devices available")
            
            self.logger.info(f"Audio capabilities validated: {capabilities}")
            
        except Exception as e:
            self.logger.error(f"Audio capability validation failed: {e}")
            raise ConfigurationError(f"Audio system not available: {e}")
            
        # Configure optimal buffer for voice trigger + ASR pipeline
        self.buffer_size = calculate_audio_buffer_size(16000, 100.0)  # From audio_helpers.py
        self.logger.info(f"Configured audio buffer size: {self.buffer_size}")
        
        # Validate required components
        required_components = ['asr', 'nlu', 'intent_orchestrator', 'context_manager']
        for comp_name in required_components:
            if comp_name not in self.components:
                raise ConfigurationError(f"Required component '{comp_name}' not available")
        
        # Get component references
        self.voice_trigger = self.components.get('voice_trigger')  # Optional
        self.asr = self.components['asr']
        self.text_processor = self.components.get('text_processor')  # Optional but recommended
        self.nlu = self.components['nlu']
        self.intent_orchestrator = self.components['intent_orchestrator']
        self.tts = self.components.get('tts')  # Optional
        self.audio = self.components.get('audio')  # Optional
        self.context_manager = self.components['context_manager']
        
        self.logger.info("VoiceAssistantWorkflow initialized successfully")
        self.initialized = True
    
    async def process_audio_stream(self, audio_stream: AsyncIterator[AudioData], context: RequestContext) -> AsyncIterator[IntentResult]:
        """
        Main workflow: Audio → Wake Word → ASR → NLU → Intent Execution → Response
        
        Args:
            audio_stream: Async iterator of audio data from input source
            context: Request context with session info and preferences
            
        Yields:
            IntentResult objects as they are generated
        """
        if not self.initialized:
            await self.initialize()
            
        self.logger.info(f"Starting voice assistant workflow for session {context.session_id}")
        
        # Get or create conversation context
        conv_context = await self.context_manager.get_context(context.session_id)
        
        # Track audio processing state
        listening_for_wake_word = not context.skip_wake_word and self.voice_trigger
        audio_buffer = []
        wake_word_detected = False
        
        try:
            async for audio_data in audio_stream:
                # 1. Voice Trigger Detection (if enabled and not skipped)
                if listening_for_wake_word and not wake_word_detected:
                    if self.voice_trigger and await self.voice_trigger.is_available():
                        try:
                            wake_result = await self.voice_trigger.detect(audio_data)
                            
                            if wake_result.detected:
                                self.logger.info(f"Wake word detected: {wake_result.word} (confidence: {wake_result.confidence:.2f})")
                                wake_word_detected = True
                                audio_buffer = []  # Start fresh after wake word
                                
                                # Yield wake word confirmation if requested
                                if context.metadata.get('notify_wake_word', False):
                                    yield IntentResult(
                                        text=f"Wake word '{wake_result.word}' detected",
                                        should_speak=False,
                                        metadata={'type': 'wake_word_detected', 'word': wake_result.word}
                                    )
                            else:
                                continue  # Keep listening for wake word
                                
                        except Exception as e:
                            self.logger.error(f"Voice trigger error: {e}")
                            # Continue without voice trigger
                            wake_word_detected = True
                    else:
                        # Voice trigger not available, skip wake word detection
                        wake_word_detected = True
                
                # 2. Collect audio for ASR (after wake word or if wake word skipped)
                if wake_word_detected or context.skip_wake_word:
                    audio_buffer.append(audio_data)
                    
                    # Process when we have enough audio or silence detected
                    if len(audio_buffer) >= 10:  # Adjust based on buffer_size
                        # Combine audio data
                        combined_audio = self._combine_audio_data(audio_buffer)
                        
                        # 3. Speech Recognition
                        try:
                            text = await self._transcribe_audio(combined_audio)
                            
                            if text and text.strip():
                                # Process the recognized text
                                result = await self._process_text_pipeline(text, conv_context, context)
                                if result:
                                    yield result
                                
                                # Reset for next interaction
                                audio_buffer = []
                                wake_word_detected = False if listening_for_wake_word else True
                                
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
                            wake_word_detected = False if listening_for_wake_word else True
                            
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
        Process text input through the workflow (no audio components).
        
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
            # 3. Text Processing (using existing irene/utils/text_processing.py)
            improved_text = text
            if self.text_processor and await self.text_processor.is_available():
                try:
                    improved_text = await self.text_processor.improve(text, conv_context, stage="asr_output")
                    if improved_text != text:
                        self.logger.debug(f"Text improved: '{text}' → '{improved_text}'")
                except Exception as e:
                    self.logger.warning(f"Text processing failed, using original: {e}")
                    improved_text = text
            
            # 4. Intent Recognition (NEW!)
            intent = await self.nlu.recognize(improved_text, conv_context)
            self.logger.info(f"Intent recognized: {intent.name} (confidence: {intent.confidence:.2f})")
            
            # 5. Intent Execution (NEW!)
            result = await self.intent_orchestrator.execute_intent(intent, conv_context)
            
            # 6. Response Output
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
        """
        Route response through appropriate output channels.
        
        Args:
            result: Intent execution result
            request_context: Request context
            conv_context: Conversation context
        """
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
        # This could include things like setting timers, playing music, etc.
        self.logger.debug(f"Action execution not yet implemented for: {action}")
    
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
        return f"VoiceAssistantWorkflow(initialized={self.initialized}, components={len(self.components)})"
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Voice assistant workflow needs core audio processing libraries"""
        return ["sounddevice>=0.4.0", "soundfile>=0.12.0"] 