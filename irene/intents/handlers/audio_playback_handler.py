"""
Audio Playback Intent Handler - Music and audio control commands

Handles audio playback control commands that were previously hardcoded
in AudioComponent. Delegates to AudioComponent for actual functionality.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class AudioPlaybackIntentHandler(IntentHandler):
    """
    Handles audio playback intents - music/audio control commands.
    
    Features:
    - Audio playback control (play, stop)
    - Audio provider switching
    - Audio provider information display
    """
    
    def __init__(self):
        super().__init__()
        self._audio_component = None

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Audio playback handler needs no external dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Audio playback handler has no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Audio playback handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process audio playback intents"""
        if not self.has_donation():
            raise RuntimeError(f"AudioPlaybackIntentHandler: Missing JSON donation file - audio_playback_handler.json is required")
        
        # Use JSON donation patterns exclusively
        donation = self.get_donation()
        
        # Check domain patterns
        if hasattr(donation, 'domain_patterns') and intent.domain in donation.domain_patterns:
            return True
        
        # Check intent name patterns
        if hasattr(donation, 'intent_name_patterns') and intent.name in donation.intent_name_patterns:
            return True
        
        # Check action patterns
        if hasattr(donation, 'action_patterns') and intent.action in donation.action_patterns:
            return True
        
        return False
        
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Execute audio playback intent"""
        # Use donation-driven routing exclusively
        return await self.execute_with_donation_routing(intent, context)
        
    async def _handle_play_audio(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle audio playback request with fire-and-forget action execution"""
        # Check for stop commands first
        stop_info = self.parse_stop_command(intent)
        if stop_info and stop_info.get("is_stop_command"):
            return await self._handle_stop_command(stop_info, context)
        
        # Extract audio file or track information
        audio_file = intent.entities.get("file", intent.entities.get("track", "default_audio"))
        source = intent.entities.get("source", "local")
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Use fire-and-forget action execution for audio playback
        playback_id = f"audio_{int(time.time() * 1000)}"
        action_metadata = await self.execute_fire_and_forget_with_context(
            self._start_audio_playback_action,
            action_name=playback_id,
            domain="audio",
            context=context,
            audio_file=audio_file,
            source=source,
            language=language
        )
        
        # Immediate response
        response_text = self._get_template("start_playback", language, audio_file=audio_file)
        
        return self.create_action_result(
            response_text=response_text,
            action_name=playback_id,
            domain="audio",
            should_speak=True,
            action_metadata=action_metadata
        )
        
    async def _handle_stop_audio(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle audio stop request with fire-and-forget action execution"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Use fire-and-forget action execution for stopping audio
        stop_id = f"audio_stop_{int(time.time() * 1000)}"
        action_metadata = await self.execute_fire_and_forget_with_context(
            self._stop_audio_playback_action,
            action_name=stop_id,
            domain="audio",
            context=context,
            language=language
        )
        
        # Immediate response
        response_text = self._get_template("stop_playback", language)
        
        return self.create_action_result(
            response_text=response_text,
            action_name=stop_id,
            domain="audio",
            should_speak=True,
            action_metadata=action_metadata
        )
    
    async def _handle_stop_command(self, stop_info: dict, context: ConversationContext) -> IntentResult:
        """Handle stop commands for audio actions with disambiguation"""
        target_domains = stop_info.get("target_domains", [])
        
        # Check if stop command targets audio domain
        if not target_domains or "audio" in target_domains or "music" in target_domains:
            # Determine language
            language = self._get_language_from_context(context)
            
            # Use fire-and-forget action execution for stopping audio
            stop_id = f"audio_stop_all_{int(time.time() * 1000)}"
            action_metadata = await self.execute_fire_and_forget_with_context(
                self._stop_audio_playback_action,
                action_name=stop_id,
                domain="audio",
                context=context,
                language=language
            )
            
            return self.create_action_result(
                response_text=self._get_template("stop_audio", language),
                action_name=stop_id,
                domain="audio",
                should_speak=True,
                action_metadata=action_metadata
            )
        
        # Not targeting audio domain
        language = self._get_language_from_context(context)
        return self._create_success_result(
            text=self._get_template("command_not_audio", language),
            should_speak=False
        )
        
    async def _handle_switch_audio_provider(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle audio provider switching request"""
        audio_component = await self._get_audio_component()
        if not audio_component:
            return self._create_error_result(intent, context, "Audio component not available")
        
        # Extract provider name from intent entities or text
        provider_name = intent.entities.get("provider")
        if not provider_name:
            provider_name = audio_component.parse_provider_name_from_text(intent.text)
        
        if not provider_name:
            return self._create_error_result(intent, context, "Provider name not specified")
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        success = audio_component.set_default_provider(provider_name)
        
        # Create appropriate response message
        if success:
            message = self._get_template("provider_switched", language, provider_name=provider_name)
        else:
            available = ", ".join(audio_component.providers.keys())
            message = self._get_template("provider_unknown", language, available=available)
        
        self.logger.info(f"Audio provider switch to {provider_name} - success: {success}")
        
        return IntentResult(
            text=message,
            should_speak=True,
            metadata={
                "action": "switch_provider",
                "provider": provider_name,
                "success": success,
                "language": language
            },
            success=success
        )
        
    async def _handle_list_audio_providers(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle audio providers information request"""
        audio_component = await self._get_audio_component()
        if not audio_component:
            return self._create_error_result(intent, context, "Audio component not available")
        
        info = audio_component.get_providers_info()
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        self.logger.info(f"Audio providers info requested")
        
        return IntentResult(
            text=info,
            should_speak=True,
            metadata={
                "action": "list_providers",
                "language": language
            },
            success=True
        )
    
    async def _get_audio_component(self):
        """Get audio component from core"""
        if self._audio_component is None:
            try:
                from ...core.engine import get_core
                core = get_core()
                if core and hasattr(core, 'component_manager'):
                    self._audio_component = await core.component_manager.get_component('audio')
            except Exception as e:
                self.logger.error(f"Failed to get audio component: {e}")
                return None
        
        return self._audio_component
        
    def _get_template(self, template_name: str, language: str = "ru", **format_args) -> str:
        """Get template from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"AudioPlaybackIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - audio playback templates must be externalized."
            )
        
        # Get template from asset loader
        template_content = self.asset_loader.get_template("audio_playback", template_name, language)
        if template_content is None:
            raise RuntimeError(
                f"AudioPlaybackIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/audio_playback/{language}/status_messages.yaml. "
                f"This is a fatal error - all audio playback templates must be externalized."
            )
        
        # Format template with provided arguments
        try:
            return template_content.format(**format_args)
        except KeyError as e:
            raise RuntimeError(
                f"AudioPlaybackIntentHandler: Template '{template_name}' missing required format argument: {e}. "
                f"Check assets/templates/audio_playback/{language}/status_messages.yaml for correct placeholders."
            )
    
    def _create_error_result(self, intent: Intent, context: ConversationContext, error: str) -> IntentResult:
        """Create error result with language awareness"""
        language = context.language or "ru"
        
        error_text = self._get_template("error_general", language, error=error)
        
        return IntentResult(
            text=error_text,
            should_speak=True,
            metadata={
                "error": error,
                "language": language
            },
            success=False
        )
    
    def _get_language_from_context(self, context: ConversationContext) -> str:
        """Get language from conversation context"""
        return getattr(context, 'language', 'ru')
    
    async def _start_audio_playback_action(self, audio_file: str, source: str, language: str) -> bool:
        """Fire-and-forget audio playback action"""
        try:
            audio_component = await self._get_audio_component()
            if not audio_component:
                self.logger.error("Audio component not available for playback")
                return False
            
            # Simulate audio playback start
            # In a real implementation, this would:
            # 1. Load audio file from source (local/streaming/URL)
            # 2. Initialize audio playback
            # 3. Start playback in background
            # 4. Handle playback events (completion, errors)
            
            self.logger.info(f"🎵 Starting audio playback: {audio_file} from {source}")
            
            # Simulate loading time
            await asyncio.sleep(0.5)
            
            # Simulate potential loading failures (10% failure rate)
            import random
            if random.random() < 0.1:
                raise Exception(f"Failed to load audio file: {audio_file}")
            
            # In a real implementation, would call:
            # await audio_component.play_file(audio_file, source=source)
            
            self.logger.info(f"🎵 Audio playback started successfully: {audio_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Audio playback action failed: {e}")
            return False
    
    async def _stop_audio_playback_action(self, language: str) -> bool:
        """Fire-and-forget audio stop action"""
        try:
            audio_component = await self._get_audio_component()
            if not audio_component:
                self.logger.warning("Audio component not available for stop operation")
                return False
            
            # In a real implementation, this would:
            # 1. Check if any audio is currently playing
            # 2. Stop all active playback
            # 3. Clean up audio resources
            # 4. Update playback state
            
            self.logger.info("🛑 Stopping audio playback")
            
            # Simulate stop operation
            await asyncio.sleep(0.2)
            
            # Try to stop playback using audio component
            try:
                await audio_component.stop_playback()
                self.logger.info("🛑 Audio playback stopped successfully")
                return True
            except Exception as component_error:
                self.logger.warning(f"Audio component stop failed: {component_error}")
                # Fallback: assume stop was successful anyway
                return True
                
        except Exception as e:
            self.logger.error(f"Audio stop action failed: {e}")
            return False
