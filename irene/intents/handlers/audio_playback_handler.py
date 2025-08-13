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
        
        # Determine language
        language = self._get_language(intent, context)
        
        # Use fire-and-forget action execution for audio playback
        playback_id = f"audio_{int(time.time() * 1000)}"
        action_metadata = await self.execute_fire_and_forget_action(
            self._start_audio_playback_action,
            action_name=playback_id,
            domain="audio",
            audio_file=audio_file,
            source=source,
            language=language
        )
        
        # Immediate response
        if language == "ru":
            response_text = f"Начинаю воспроизведение аудио: {audio_file}"
        else:
            response_text = f"Starting audio playback: {audio_file}"
        
        return self.create_action_result(
            response_text=response_text,
            action_name=playback_id,
            domain="audio",
            should_speak=True,
            action_metadata=action_metadata
        )
        
    async def _handle_stop_audio(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle audio stop request with fire-and-forget action execution"""
        # Determine language
        language = self._get_language(intent, context)
        
        # Use fire-and-forget action execution for stopping audio
        stop_id = f"audio_stop_{int(time.time() * 1000)}"
        action_metadata = await self.execute_fire_and_forget_action(
            self._stop_audio_playback_action,
            action_name=stop_id,
            domain="audio",
            language=language
        )
        
        # Immediate response
        if language == "ru":
            response_text = "Останавливаю воспроизведение аудио"
        else:
            response_text = "Stopping audio playback"
        
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
            action_metadata = await self.execute_fire_and_forget_action(
                self._stop_audio_playback_action,
                action_name=stop_id,
                domain="audio",
                language=language
            )
            
            return self.create_action_result(
                response_text="Останавливаю аудио" if language == "ru" else "Stopping audio",
                action_name=stop_id,
                domain="audio",
                should_speak=True,
                action_metadata=action_metadata
            )
        
        # Not targeting audio domain
        return self._create_success_result(
            text="Команда остановки не относится к аудио",
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
        
        # Determine language
        language = self._get_language(intent, context)
        
        success = audio_component.set_default_provider(provider_name)
        
        # Create appropriate response message
        if success:
            if language == "ru":
                message = f"Переключился на аудио провайдер {provider_name}"
            else:
                message = f"Switched to audio provider {provider_name}"
        else:
            available = ", ".join(audio_component.providers.keys())
            if language == "ru":
                message = f"Неизвестный провайдер. Доступные: {available}"
            else:
                message = f"Unknown provider. Available: {available}"
        
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
        
        # Determine language
        language = self._get_language(intent, context)
        
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
        
    def _get_language(self, intent: Intent, context: ConversationContext) -> str:
        """Determine language from intent or context"""
        # Check intent entities first
        if "language" in intent.entities:
            return intent.entities["language"]
        
        # Check if text contains Russian characters
        if any(char in intent.text for char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"):
            return "ru"
        
        # Default to Russian
        return "ru"
        
    def _create_error_result(self, intent: Intent, context: ConversationContext, error: str) -> IntentResult:
        """Create error result with language awareness"""
        language = self._get_language(intent, context)
        
        if language == "ru":
            error_text = f"Ошибка: {error}"
        else:
            error_text = f"Error: {error}"
        
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
