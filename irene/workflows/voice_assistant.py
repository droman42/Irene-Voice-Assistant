"""
Unified Voice Assistant Workflow - Single workflow for all entry points

This workflow implements the unified pipeline design with conditional stages:
Audio → Voice Trigger → ASR → Text Processing → NLU → Intent → Response (+TTS)

Supports all three entry points with stage skipping:
- Voice Assistant: Full pipeline (skip_wake_word=False)
- CLI/Text: Skip voice trigger + ASR stages (text input only)
- WebAPI Audio: Skip voice trigger only (skip_wake_word=True)
"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import AsyncIterator, Optional, Dict, Any, List

from .base import Workflow, RequestContext
from ..intents.models import AudioData, ConversationContext, Intent, IntentResult, WakeWordResult
from ..utils.audio_helpers import test_audio_playback_capability, calculate_audio_buffer_size
from ..utils.loader import safe_import
from ..config.manager import ConfigValidationError

logger = logging.getLogger(__name__)



class UnifiedVoiceAssistantWorkflow(Workflow):
    """
    Unified Voice Assistant Workflow - Single workflow for all entry points
    
    This workflow implements the unified pipeline design with conditional stages:
    Audio → Voice Trigger → ASR → Text Processing → NLU → Intent → Response (+TTS)
    
    Supports all three entry points with stage skipping:
    - Voice Assistant: Full pipeline (skip_wake_word=False)
    - CLI/Text: Skip voice trigger + ASR stages (text input only)
    - WebAPI Audio: Skip voice trigger only (skip_wake_word=True)
    
    Features:
    - Conditional pipeline stages based on input type
    - Universal TTS output via wants_audio parameter
    - Action execution framework with fire-and-forget patterns
    - Action context tracking for disambiguation
    """
    
    def __init__(self):
        super().__init__()
        # Component references
        self.voice_trigger = None
        self.asr = None
        self.text_processor = None
        self.nlu = None
        self.intent_orchestrator = None
        self.tts = None
        self.audio = None
        self.context_manager = None
        self.buffer_size = None
        
        # Pipeline stage flags - will be configured from config in initialize()
        self._voice_trigger_enabled = False
        self._asr_enabled = False
        self._text_processing_enabled = False
        self._nlu_enabled = False
        self._intent_execution_enabled = False
        self._llm_enabled = False
        self._tts_enabled = False
        self._audio_enabled = False

    @classmethod
    def get_dependencies(cls) -> Dict[str, Any]:
        """
        Define workflow dependencies - replaces hardcoded dependency mapping
        
        Returns:
            Dict containing dependency information for this workflow
        """
        return {
            "required_components": ["intent_system"],  # Essential for intent execution
            "optional_components": ["tts", "asr", "audio", "voice_trigger", "nlu", "text_processor", "llm"],  # Pipeline stages
            "required_providers": [],  # No specific provider requirements
            "description": "Unified workflow supporting voice, text, and audio processing with conditional pipeline stages"
        }
    
    async def initialize(self, workflow_config=None):
        """Initialize unified workflow with all required components and configuration"""
        if self.initialized:
            return
            
        self.logger.info("Initializing UnifiedVoiceAssistantWorkflow...")
        
        # Configure pipeline stages from configuration
        if workflow_config:
            self._voice_trigger_enabled = workflow_config.voice_trigger_enabled
            self._asr_enabled = workflow_config.asr_enabled  
            self._text_processing_enabled = workflow_config.text_processing_enabled
            self._nlu_enabled = workflow_config.nlu_enabled
            self._intent_execution_enabled = workflow_config.intent_execution_enabled
            self._llm_enabled = workflow_config.llm_enabled
            self._tts_enabled = workflow_config.tts_enabled
            self._audio_enabled = workflow_config.audio_enabled
            
            self.logger.info(f"Pipeline stages configured: voice_trigger={self._voice_trigger_enabled}, "
                           f"asr={self._asr_enabled}, text_processing={self._text_processing_enabled}, "
                           f"nlu={self._nlu_enabled}, intent_execution={self._intent_execution_enabled}, "
                           f"llm={self._llm_enabled}, tts={self._tts_enabled}, audio={self._audio_enabled}")
        else:
            self.logger.error("No workflow configuration provided - pipeline stages remain disabled")
            raise ValueError("UnifiedVoiceAssistantWorkflow requires configuration for pipeline stages")
        
        # Validate audio capability
        try:
            capabilities = await test_audio_playback_capability()
            if not capabilities.get('devices_available', False):
                self.logger.warning("No audio devices available - audio features limited")
            else:
                self.logger.info(f"Audio capabilities validated: {capabilities}")
        except Exception as e:
            self.logger.warning(f"Audio capability validation failed: {e}")
        
        # Configure audio buffer
        self.buffer_size = calculate_audio_buffer_size(16000, 100.0)
        self.logger.info(f"Configured audio buffer size: {self.buffer_size}")
        
        # Validate required components for unified workflow
        required_components = ['nlu', 'intent_orchestrator', 'context_manager']
        for comp_name in required_components:
            if comp_name not in self.components:
                raise ConfigValidationError(f"Required component '{comp_name}' not available")
        
        # TTS-Audio dependency validation (Phase 2 implementation)
        if self.components.get('tts') and not self.components.get('audio'):
            raise ConfigValidationError(
                "TTS component requires Audio component. "
                "Either disable TTS or enable Audio component."
            )
        
        # Get component references (some are optional for different entry points)
        self.voice_trigger = self.components.get('voice_trigger')  # Optional - for voice entry only
        self.asr = self.components.get('asr')  # Optional - for audio input only  
        self.text_processor = self.components.get('text_processor')  # Optional but recommended
        self.nlu = self.components['nlu']  # Required
        self.intent_orchestrator = self.components['intent_orchestrator']  # Required
        self.tts = self.components.get('tts')  # Optional - for audio output
        self.audio = self.components.get('audio')  # Optional - for audio output
        self.context_manager = self.components['context_manager']  # Required
        
        self.logger.info("UnifiedVoiceAssistantWorkflow initialized successfully")
        self.initialized = True
    
    async def process_text_input(self, text: str, context: RequestContext) -> IntentResult:
        """
        Process text input through unified pipeline (skips audio stages)
        
        Pipeline: Text → Text Processing → NLU → Intent → Response (+optional TTS)
        
        Args:
            text: Input text to process
            context: Request context with client info and preferences
            
        Returns:
            IntentResult with response and optional action metadata
        """
        if not self.initialized:
            await self.initialize()
        
        self.logger.debug(f"Processing text input: '{text[:50]}...' from {context.source}")
        
        try:
            # Create conversation context
            conversation_context = await self._create_conversation_context(context)
            
            # Process pipeline starting from text processing
            result = await self._process_pipeline(
                input_data=text,
                context=context,
                conversation_context=conversation_context,
                skip_wake_word=True,    # Always skip for text input
                skip_asr=True          # Always skip for text input
            )
            
            # Handle TTS if requested
            if context.wants_audio and result.should_speak:
                await self._handle_tts_output(result, context)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Text processing error: {e}")
            return IntentResult(
                text="Sorry, there was an error processing your request.",
                success=False,
                error=str(e),
                confidence=0.0
            )
    
    async def process_audio_stream(self, audio_stream: AsyncIterator[AudioData], context: RequestContext) -> AsyncIterator[IntentResult]:
        """
        Process audio stream through unified pipeline
        
        Pipeline: Audio → [Voice Trigger] → ASR → Text Processing → NLU → Intent → Response (+TTS)
        
        Args:
            audio_stream: Async iterator of audio data
            context: Request context with skip_wake_word flag and client info
            
        Yields:
            IntentResult objects as they are generated
        """
        if not self.initialized:
            await self.initialize()
        
        self.logger.debug(f"Processing audio stream from {context.source}, skip_wake_word={context.skip_wake_word}")
        
        try:
            # Create conversation context
            conversation_context = await self._create_conversation_context(context)
            
            # Process audio stream through pipeline
            async for result in self._process_audio_pipeline(
                audio_stream=audio_stream,
                context=context,
                conversation_context=conversation_context
            ):
                yield result
                
        except Exception as e:
            self.logger.error(f"Audio processing error: {e}")
            yield IntentResult(
                text="Sorry, there was an error processing the audio.",
                success=False,
                error=str(e),
                confidence=0.0
            )
    
    async def _process_pipeline(self, input_data: str, context: RequestContext, 
                              conversation_context: ConversationContext,
                              skip_wake_word: bool = False, skip_asr: bool = False) -> IntentResult:
        """
        Core unified pipeline processing with conditional stages
        
        Args:
            input_data: Text input (from direct text or ASR output)
            context: Request context
            conversation_context: Conversation context for tracking
            skip_wake_word: Whether wake word detection was skipped
            skip_asr: Whether ASR processing was skipped
            
        Returns:
            IntentResult with response and action metadata
        """
        processed_text = input_data
        
        # Stage 1: Text Processing (if enabled and component available)
        if self._text_processing_enabled and self.text_processor:
            self.logger.debug("Stage: Text Processing")
            processed_text = await self.text_processor.process(processed_text)
        
        # Stage 2: NLU (Natural Language Understanding)
        self.logger.debug("Stage: NLU")
        intent = await self.nlu.process(processed_text, conversation_context)
        
        # Stage 3: Intent Execution
        self.logger.debug(f"Stage: Intent Execution - {intent.name}")
        result = await self.intent_orchestrator.execute(intent, conversation_context)
        
        # Stage 4: Action Metadata Processing (fire-and-forget)
        if result.action_metadata:
            await self._process_action_metadata(result.action_metadata, conversation_context)
        
        # Update conversation history
        conversation_context.add_to_history(
            user_text=input_data,
            response=result.text,
            intent=intent.name
        )
        
        return result
    
    async def _process_audio_pipeline(self, audio_stream: AsyncIterator[AudioData], 
                                    context: RequestContext, conversation_context: ConversationContext) -> AsyncIterator[IntentResult]:
        """
        Process audio stream through conditional pipeline stages
        
        Pipeline stages based on context.skip_wake_word:
        - False (Voice): Audio → Voice Trigger → ASR → Text Processing → NLU → Intent → Response
        - True (WebAPI): Audio → ASR → Text Processing → NLU → Intent → Response
        """
        audio_buffer = []
        wake_word_detected = context.skip_wake_word  # If skipping, assume already "detected"
        
        async for audio_data in audio_stream:
            audio_buffer.append(audio_data)
            
            # Stage 1: Voice Trigger Detection (conditional)
            if not wake_word_detected and self.voice_trigger:
                wake_result = await self.voice_trigger.process_audio(audio_data)
                if wake_result.detected:
                    self.logger.debug("Wake word detected, starting ASR processing")
                    wake_word_detected = True
                    audio_buffer = []  # Clear buffer, start fresh for ASR
                continue
            
            # If no wake word detected yet, continue buffering
            if not wake_word_detected:
                continue
            
            # Stage 2: ASR (Automatic Speech Recognition)
            if self.asr:
                # Process buffered audio through ASR
                if audio_buffer:
                    combined_audio = await self._combine_audio_buffer(audio_buffer)
                    audio_buffer = []
                    
                    asr_result = await self.asr.process_audio(combined_audio)
                    if asr_result and asr_result.strip():
                        self.logger.debug(f"ASR result: {asr_result}")
                        
                        # Process through unified pipeline
                        result = await self._process_pipeline(
                            input_data=asr_result,
                            context=context,
                            conversation_context=conversation_context,
                            skip_wake_word=True,  # Already processed
                            skip_asr=True        # Already processed
                        )
                        
                        # Handle TTS if requested
                        if context.wants_audio and result.should_speak:
                            await self._handle_tts_output(result, context)
                        
                        yield result
                        
                        # Reset for next interaction
                        wake_word_detected = context.skip_wake_word
    
    async def _create_conversation_context(self, context: RequestContext) -> ConversationContext:
        """Create or retrieve conversation context from context manager"""
        return await self.context_manager.get_or_create_context(
            session_id=context.session_id,
            client_id=context.client_id,
            client_metadata=context.metadata
        )
    
    async def _process_action_metadata(self, action_metadata: Dict[str, Any], 
                                     conversation_context: ConversationContext):
        """Process action metadata and update conversation context"""
        if 'active_action' in action_metadata:
            active_action = action_metadata['active_action']
            for domain, action_info in active_action.items():
                conversation_context.add_active_action(domain, action_info)
        
        # Additional action metadata processing can be added here
        # (e.g., action completion callbacks, error handling, etc.)
    
    async def _handle_tts_output(self, result: IntentResult, context: RequestContext):
        """Handle TTS output using temp file coordination"""
        if not (self.tts and self.audio and result.text):
            return
            
        # Generate unique temporary file path
        temp_filename = f"tts_{uuid.uuid4().hex}.wav"
        temp_path = self.temp_audio_dir / temp_filename
        
        try:
            # Step 1: TTS generates audio file
            self.logger.debug(f"Generating TTS audio: {temp_path}")
            await self.tts.synthesize_to_file(result.text, temp_path)
            
            # Step 2: Audio plays the file
            self.logger.debug(f"Playing audio file: {temp_path}")
            await self.audio.play_file(temp_path)
            
            self.logger.info(f"Successfully played TTS audio for: {result.text[:50]}...")
            
        except Exception as e:
            self.logger.warning(f"TTS-Audio coordination failed: {e}")
            
        finally:
            # Step 3: MANDATORY cleanup
            if temp_path.exists():
                temp_path.unlink()
                self.logger.debug(f"Cleaned up temp file: {temp_path}")
    
    async def _combine_audio_buffer(self, audio_buffer: List[AudioData]) -> AudioData:
        """Combine multiple AudioData objects into a single object"""
        if not audio_buffer:
            raise ValueError("Cannot combine empty audio buffer")
        
        if len(audio_buffer) == 1:
            return audio_buffer[0]
        
        # Combine audio data
        first_audio = audio_buffer[0]
        combined_data = b''.join(audio.data for audio in audio_buffer)
        
        return AudioData(
            data=combined_data,
            timestamp=first_audio.timestamp,
            sample_rate=first_audio.sample_rate,
            channels=first_audio.channels,
            format=first_audio.format
        )
    
    def __repr__(self) -> str:
        return f"UnifiedVoiceAssistantWorkflow(initialized={self.initialized}, components={len(self.components)})"
    
    @property
    def temp_audio_dir(self) -> Path:
        """Get temp audio directory from injected configuration"""
        config = self.get_component('config')
        if not config:
            raise ConfigValidationError("Configuration not available in workflow")
        return Path(config.storage.temp_audio_dir)
    
    # Build dependency methods
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Workflows coordinate components - minimal direct dependencies"""
        return [] 