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
import time
import uuid
from pathlib import Path
from typing import AsyncIterator, Optional, Dict, Any, List

from .base import Workflow, RequestContext
from .audio_processor import AudioProcessorInterface, VoiceSegment
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
        
        # VAD processing components (always enabled)
        self.audio_processor_interface = None
        
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
                           f"llm={self._llm_enabled}, tts={self._tts_enabled}, audio={self._audio_enabled}, "
                           f"vad_processing=enabled")
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
        
        # Initialize VAD processor interface (required for all audio processing)
        try:
            # Get VAD configuration from injected config component
            config = self.get_component('config')
            if not config:
                raise ConfigValidationError("Configuration not available in workflow")
            
            vad_config = config.vad if hasattr(config, 'vad') else None
            if vad_config and vad_config.enabled:
                self.audio_processor_interface = AudioProcessorInterface(vad_config)
                self.logger.info(f"VAD audio processor initialized: threshold={vad_config.energy_threshold}, "
                               f"sensitivity={vad_config.sensitivity}")
            else:
                self.logger.error("VAD configuration missing or disabled. VAD processing is required for audio workflows.")
                raise ConfigValidationError("VAD configuration is required for audio processing")
        except Exception as e:
            self.logger.error(f"Failed to initialize VAD processor: {e}")
            raise
        
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
            
            # Use VAD-enabled audio processing pipeline (now the default)
            if not self.audio_processor_interface:
                raise RuntimeError("Audio processor interface not available. VAD processing is required.")
            
            self.logger.info("🔄 Using VAD-enabled audio processing pipeline")
            self.logger.info(f"📊 VAD Configuration: threshold={self.audio_processor_interface.processor.config.energy_threshold}, "
                           f"sensitivity={self.audio_processor_interface.processor.config.sensitivity}, "
                           f"max_segment_duration={self.audio_processor_interface.processor.config.max_segment_duration_s}s")
            
            pipeline_start_time = time.time()
            result_count = 0
            
            async for result in self._process_audio_pipeline(
                audio_stream=audio_stream,
                context=context,
                conversation_context=conversation_context
            ):
                result_count += 1
                yield result
            
            pipeline_duration = time.time() - pipeline_start_time
            self.logger.info(f"📊 VAD Pipeline Performance: {result_count} results, "
                           f"{pipeline_duration:.2f}s total duration")
            
            # Log VAD metrics for performance monitoring
            if self.audio_processor_interface:
                metrics = self.audio_processor_interface.get_metrics()
                state = self.audio_processor_interface.get_state()
                self.logger.info(f"📊 Final VAD Metrics: "
                               f"chunks_processed={metrics.total_chunks_processed}, "
                               f"voice_segments={metrics.voice_segments_detected}, "
                               f"silence_skipped={metrics.silence_chunks_skipped}, "
                               f"avg_processing_time={metrics.average_processing_time_ms:.2f}ms, "
                               f"buffer_overflows={metrics.buffer_overflow_count}, "
                               f"timeouts={metrics.timeout_events}")
                
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
        VAD-enabled audio processing pipeline
        
        This method implements the universal VAD design that works identically
        in both voice trigger modes by accumulating voice segments before processing.
        
        Pipeline: Audio Stream → VAD Filter → Voice Segments → Mode-Specific Processing
        """
        self.logger.info(f"🎙️ Starting VAD-enabled audio pipeline - skip_wake_word={context.skip_wake_word}")
        
        wake_word_detected = context.skip_wake_word  # If skipping, assume already "detected"
        voice_segment_count = 0
        
        # Voice segment handler for the audio processor interface
        async def voice_segment_handler(voice_segment: VoiceSegment, ctx):
            """Handle completed voice segments from VAD processor"""
            nonlocal voice_segment_count
            voice_segment_count += 1
            
            self.logger.info(f"🎯 Voice segment #{voice_segment_count} received: "
                           f"{voice_segment.chunk_count} chunks, {voice_segment.total_duration_ms:.1f}ms, "
                           f"{len(voice_segment.combined_audio.data)} bytes")
        
        try:
            # Process audio stream through VAD interface
            async for voice_segment in self.audio_processor_interface.process_audio_pipeline(
                audio_stream, context, voice_segment_handler
            ):
                # Process voice segment according to current mode
                result = await self.audio_processor_interface.process_voice_segment_for_mode(
                    voice_segment, context, self.asr, self.voice_trigger, wake_word_detected
                )
                
                # Handle different result types
                if result['type'] == 'asr_result':
                    asr_text = result['result']
                    if asr_text and asr_text.strip():
                        self.logger.info(f"✅ VAD-ASR result: '{asr_text}'")
                        
                        # Process through unified pipeline
                        pipeline_result = await self._process_pipeline(
                            input_data=asr_text,
                            context=context,
                            conversation_context=conversation_context
                        )
                        
                        yield pipeline_result
                        
                        # Reset wake word state for next interaction
                        if result['mode'] == 'command_after_wake':
                            wake_word_detected = False
                    else:
                        self.logger.debug("📭 VAD-ASR returned empty result")
                        # Reset ASR provider state after empty result to ensure clean state
                        if self.asr and hasattr(self.asr, 'reset_provider_state'):
                            self.asr.reset_provider_state()
                            self.logger.debug("Reset ASR provider state after empty result")
                        
                elif result['type'] == 'wake_word_result':
                    wake_result = result['result']
                    if wake_result.get('detected', False):
                        self.logger.info(f"✅ VAD-Wake word detected: {wake_result.get('wake_word', 'unknown')}")
                        wake_word_detected = True
                    else:
                        self.logger.debug("🔍 VAD-Wake word not detected in segment")
                        
                elif result['type'] == 'error':
                    self.logger.error(f"❌ VAD processing error: {result['error']}")
                    
        except Exception as e:
            self.logger.error(f"❌ VAD audio pipeline error: {e}")
            
        # Log final metrics
        if self.audio_processor_interface:
            metrics = self.audio_processor_interface.get_metrics()
            self.logger.info(f"📊 VAD Pipeline completed: {voice_segment_count} voice segments, "
                           f"{metrics.total_chunks_processed} chunks processed, "
                           f"{metrics.silence_chunks_skipped} silence chunks skipped, "
                           f"avg processing time: {metrics.average_processing_time_ms:.2f}ms")
    
    
    async def _process_voice_segment(self, voice_segment: VoiceSegment, context: RequestContext) -> Optional[str]:
        """
        Mode-agnostic voice segment processing
        
        This method handles voice segments according to the universal VAD design:
        - Mode A (skip_wake_word=False): Wake word detection first, then ASR
        - Mode B (skip_wake_word=True): Direct ASR processing
        """
        if not self.audio_processor_interface:
            self.logger.error("Audio processor interface not available for voice segment processing")
            return None
            
        # Use the audio processor interface for mode-specific processing
        result = await self.audio_processor_interface.process_voice_segment_for_mode(
            voice_segment, context, self.asr, self.voice_trigger, context.skip_wake_word
        )
        
        if result['type'] == 'asr_result':
            return result['result']
        elif result['type'] == 'wake_word_result':
            # Wake word results don't produce text
            return None
        else:
            self.logger.error(f"Voice segment processing error: {result.get('error', 'Unknown error')}")
            return None
    
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
        """Get temp audio directory from asset configuration"""
        config = self.get_component('config')
        if not config:
            raise ConfigValidationError("Configuration not available in workflow")
        return Path(config.assets.temp_audio_dir)
    
    # Build dependency methods
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Workflows coordinate components - minimal direct dependencies"""
        return [] 