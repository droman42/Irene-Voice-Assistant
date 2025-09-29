"""
Voice Synthesis Intent Handler - TTS with specific voices

Handles voice synthesis commands that were previously hardcoded
in TTSComponent. Delegates to TTSComponent for actual functionality.
"""

import logging
import time
from typing import List, Dict, Any, TYPE_CHECKING

from .base import IntentHandler
from ..models import Intent, IntentResult, UnifiedConversationContext

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)


class VoiceSynthesisIntentHandler(IntentHandler):
    """
    Handles voice synthesis intents - TTS with specific voices.
    
    Features:
    - Text-to-speech with specific voice selection
    - Voice listing and information
    - TTS provider management
    """
    
    def __init__(self):
        super().__init__()
        self._tts_component = None

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Voice synthesis handler needs no external dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Voice synthesis handler has no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Voice synthesis handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process voice synthesis intents"""
        if not self.has_donation():
            raise RuntimeError(f"VoiceSynthesisIntentHandler: Missing JSON donation file - voice_synthesis_handler.json is required")
        
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
        
    async def execute(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Execute voice synthesis intent"""
        # Use donation-driven routing exclusively
        return await self.execute_with_donation_routing(intent, context)
        
    async def _handle_speak_with_voice(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle speak with specific voice request with fire-and-forget TTS generation"""
        tts_component = await self._get_tts_component()
        if not tts_component:
            return self._create_error_result(intent, context, "TTS component not available")
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Extract text and voice parameters from command
        text_to_speak, voice_name = self._extract_speech_parameters(intent.text)
        
        if not text_to_speak:
            return self._create_error_result(intent, context, "No text to speak found")
        
        # Use fire-and-forget action execution for TTS generation
        synthesis_id = f"tts_{int(time.time() * 1000)}"  # Unique ID based on timestamp
        action_metadata = await self.execute_fire_and_forget_with_context(
            self._synthesize_speech_action,
            action_name=synthesis_id,
            domain="voice_synthesis",
            context=context,
            text_to_speak=text_to_speak,
            voice_name=voice_name,
            language=language,
            tts_component=tts_component
        )
        
        # Immediate response while TTS runs in background
        if voice_name:
            response_text = self._get_template("synthesis_with_voice", language, text=text_to_speak, voice=voice_name)
        else:
            response_text = self._get_template("synthesis_without_voice", language, text=text_to_speak)
        
        return self.create_action_result(
            response_text=response_text,
            action_name=synthesis_id,
            domain="voice_synthesis",
            should_speak=True,
            action_metadata=action_metadata
        )
        
    async def _handle_list_voices(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle list available voices request"""
        tts_component = await self._get_tts_component()
        if not tts_component:
            return self._create_error_result(intent, context, "TTS component not available")
        
        # Get TTS providers information
        response = tts_component.get_providers_info()
        success = True
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        self.logger.info(f"List voices request - success: {success}")
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={
                "action": "list_voices",
                "success": success,
                "language": language
            },
            success=success
        )
        
    async def _handle_speak_text(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle basic text-to-speech request with fire-and-forget synthesis"""
        tts_component = await self._get_tts_component()
        if not tts_component:
            return self._create_error_result(intent, context, "TTS component not available")
        
        # Extract text to speak from intent entities
        text_to_speak = intent.entities.get("text", intent.text)
        if not text_to_speak.strip():
            return self._create_error_result(intent, context, "No text to speak")
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Use fire-and-forget action execution for basic TTS
        synthesis_id = f"tts_basic_{int(time.time() * 1000)}"
        action_metadata = await self.execute_fire_and_forget_with_context(
            self._synthesize_speech_action,
            action_name=synthesis_id,
            domain="voice_synthesis",
            context=context,
            text_to_speak=text_to_speak,
            voice_name=None,  # Use default voice
            language=language,
            tts_component=tts_component
        )
        
        # Immediate response
        response_text = self._get_template("synthesis_basic", language, text=text_to_speak)
        
        return self.create_action_result(
            response_text=response_text,
            action_name=synthesis_id,
            domain="voice_synthesis",
            should_speak=False,  # Don't speak the confirmation since we're about to speak the actual text
            action_metadata=action_metadata
        )
            
    async def _handle_switch_tts_provider(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle TTS provider switching request"""
        tts_component = await self._get_tts_component()
        if not tts_component:
            return self._create_error_result(intent, context, "TTS component not available")
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Parse provider name from text and switch
        provider_name = self._parse_tts_provider_name(intent.text)
        success = tts_component.set_default_provider(provider_name) if provider_name else False
        
        if success:
            response = self._get_template("provider_switch_success", language, provider=provider_name)
        else:
            response = self._get_template("provider_switch_failed", language, provider=provider_name or "unknown")
        
        self.logger.info(f"TTS provider switch request - success: {success}")
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={
                "action": "switch_provider",
                "success": success,
                "language": language,
                "original_text": intent.text
            },
            success=success
        )
    
    async def _handle_stop_synthesis(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """
        Handle domain-specific voice synthesis stop intent (voice_synthesis.stop).
        
        Phase 2 TODO16: Standardized stop handling - only receives resolved intents.
        """
        # Determine language
        language = self._get_language_from_context(context)
        
        # Use fire-and-forget action execution for stopping synthesis
        stop_id = f"tts_stop_all_{int(time.time() * 1000)}"
        action_metadata = await self.execute_fire_and_forget_with_context(
            self._stop_synthesis_action,
            action_name=stop_id,
            domain="voice_synthesis",
            context=context,
            language=language
        )
        
        return self.create_action_result(
            response_text=self._get_template("stop_synthesis", language),
            action_name=stop_id,
            domain="voice_synthesis",
            should_speak=True,
            action_metadata=action_metadata
        )
    
    async def _handle_cancel_synthesis(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """
        Handle domain-specific voice synthesis cancel intent (voice_synthesis.cancel).
        
        Phase 2 TODO16: Standardized cancel handling - only receives resolved intents.
        """
        # Determine language
        language = self._get_language_from_context(context)
        
        # Use fire-and-forget action execution for canceling synthesis
        cancel_id = f"tts_cancel_all_{int(time.time() * 1000)}"
        action_metadata = await self.execute_fire_and_forget_with_context(
            self._cancel_synthesis_action,
            action_name=cancel_id,
            domain="voice_synthesis",
            context=context,
            language=language
        )
        
        return self.create_action_result(
            response_text=self._get_template("cancel_synthesis", language),
            action_name=cancel_id,
            domain="voice_synthesis",
            should_speak=True,
            action_metadata=action_metadata
        )
    
    async def _get_tts_component(self):
        """Get TTS component from core"""
        if self._tts_component is None:
            try:
                from ...core.engine import get_core
                core = get_core()
                if core and hasattr(core, 'component_manager'):
                    self._tts_component = await core.component_manager.get_component('tts')
            except Exception as e:
                self.logger.error(f"Failed to get TTS component: {e}")
                return None
        
        return self._tts_component
        
    def _get_template(self, template_name: str, language: str = "ru", **format_args) -> str:
        """Get template from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"VoiceSynthesisIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - voice synthesis templates must be externalized."
            )
        
        # Get template directly from asset loader (template_name is the key from YAML)
        template_content = self.asset_loader.get_template("voice_synthesis", template_name, language)
        if template_content is None:
            raise RuntimeError(
                f"VoiceSynthesisIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/voice_synthesis/{language}/synthesis_status.yaml. "
                f"This is a fatal error - all voice synthesis templates must be externalized."
            )
        
        # Format template with provided arguments
        try:
            return template_content.format(**format_args)
        except KeyError as e:
            raise RuntimeError(
                f"VoiceSynthesisIntentHandler: Template '{template_name}' missing required format argument: {e}. "
                f"Check assets/templates/voice_synthesis/{language}/synthesis_status.yaml for correct placeholders."
            )
    
    def _get_provider_mappings(self, language: str = "ru") -> Dict[str, Any]:
        """Get provider mappings from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"VoiceSynthesisIntentHandler: Asset loader not initialized. "
                f"Cannot access provider mappings for language '{language}'. "
                f"This is a fatal configuration error - voice synthesis mappings must be externalized."
            )
        
        # Get localization data from asset loader
        mappings_data = self.asset_loader.get_localization("voice_synthesis", language)
        if mappings_data is None:
            raise RuntimeError(
                f"VoiceSynthesisIntentHandler: Required provider mappings for language '{language}' "
                f"not found in assets/localization/voice_synthesis/{language}.yaml. "
                f"This is a fatal error - all voice synthesis mappings must be externalized."
            )
        
        provider_mappings = mappings_data.get("provider_mappings", {})
        if not provider_mappings:
            raise RuntimeError(
                f"VoiceSynthesisIntentHandler: Empty provider_mappings in "
                f"assets/localization/voice_synthesis/{language}.yaml. "
                f"Provider mappings must be defined for language '{language}'."
            )
        
        return provider_mappings
        
    def _create_error_result(self, intent: Intent, context: UnifiedConversationContext, error: str) -> IntentResult:
        """Create error result with language awareness"""
        language = context.language or "ru"
        error_text = self._get_template("synthesis_error", language, error=error)
        
        return IntentResult(
            text=error_text,
            should_speak=True,
            metadata={
                "error": error,
                "language": language
            },
            success=False
        )
        
    async def _parse_and_speak_with_voice(self, tts_component, command: str, language: str) -> tuple[bool, str]:
        """Parse voice synthesis command and execute speech"""
        parts = command.lower().split()
        
        if "скажи" in parts and "голосом" in parts:
            try:
                speak_idx = parts.index("скажи")
                voice_idx = parts.index("голосом")
                
                # Extract text between "скажи" and "голосом"
                text_parts = parts[speak_idx + 1:voice_idx]
                text = " ".join(text_parts)
                
                # Extract voice/provider after "голосом"
                if voice_idx + 1 < len(parts):
                    voice_name = parts[voice_idx + 1]
                    
                    # Get voice name mappings from localization
                    mappings = self._get_provider_mappings(language)
                    voice_mappings = mappings.get("voice_names", {})
                    
                    if voice_name in voice_mappings:
                        voice_config = voice_mappings[voice_name]
                        provider = voice_config.get("provider")
                        params = voice_config.get("params", {})
                        if provider in tts_component.providers:
                            await tts_component.speak(text, provider=provider, **params)
                            if language == "ru":
                                return True, f"Сказал '{text}' голосом {voice_name}"
                            else:
                                return True, f"Spoke '{text}' with voice {voice_name}"
                        else:
                            if language == "ru":
                                return False, f"Голос {voice_name} недоступен"
                            else:
                                return False, f"Voice {voice_name} not available"
                    else:
                        # Use default provider
                        await tts_component.speak(text)
                        if language == "ru":
                            return True, f"Сказал '{text}' обычным голосом"
                        else:
                            return True, f"Spoke '{text}' with default voice"
                else:
                    # No voice specified, use default
                    await tts_component.speak(text)
                    if language == "ru":
                        return True, f"Сказал '{text}'"
                    else:
                        return True, f"Spoke '{text}'"
                        
            except Exception as e:
                if language == "ru":
                    return False, f"Ошибка обработки команды: {e}"
                else:
                    return False, f"Command processing error: {e}"
        
        if language == "ru":
            return False, "Не удалось распознать команду"
        else:
            return False, "Could not recognize command"
    
    def _parse_tts_provider_name(self, command: str) -> str:
        """Extract TTS provider name from command"""
        command_lower = command.lower()
        
        # Get provider name mappings from localization (try Russian first, then English)
        try:
            mappings_ru = self._get_provider_mappings("ru")
            provider_names_ru = mappings_ru.get("provider_names", {})
            
            for name, provider in provider_names_ru.items():
                if name in command_lower:
                    return provider
            
            # Try English mappings if Russian doesn't match
            mappings_en = self._get_provider_mappings("en")
            provider_names_en = mappings_en.get("provider_names", {})
            
            for name, provider in provider_names_en.items():
                if name in command_lower:
                    return provider
        except RuntimeError:
            # Fallback to hardcoded if assets not available
            provider_mapping = {
                "силеро": "silero_v3",
                "силеро3": "silero_v3", 
                "силеро4": "silero_v4",
                "консоль": "console",
                "системный": "pyttsx",
                "воск": "vosk_tts"
            }
            
            for name, provider in provider_mapping.items():
                if name in command_lower:
                    return provider
        
        return ""
    
    def _extract_speech_parameters(self, command: str) -> tuple[str, str]:
        """Extract text to speak and voice name from command"""
        parts = command.lower().split()
        
        if "скажи" in parts and "голосом" in parts:
            try:
                speak_idx = parts.index("скажи")
                voice_idx = parts.index("голосом")
                
                # Extract text between "скажи" and "голосом"
                text_parts = parts[speak_idx + 1:voice_idx]
                text = " ".join(text_parts)
                
                # Extract voice/provider after "голосом"
                voice_name = None
                if voice_idx + 1 < len(parts):
                    voice_name = parts[voice_idx + 1]
                
                return text, voice_name
            except (ValueError, IndexError):
                pass
        
        # Fallback: if no specific voice syntax, treat entire command as text
        # Remove command words
        for cmd_word in ["скажи", "произнеси", "speak", "say"]:
            if cmd_word in command.lower():
                text = command.lower().replace(cmd_word, "").strip()
                return text, None
        
        return command, None
    
    async def _synthesize_speech_action(
        self, 
        text_to_speak: str, 
        voice_name: str, 
        language: str, 
        tts_component
    ) -> bool:
        """Fire-and-forget TTS synthesis action"""
        try:
            if voice_name:
                # Get voice name mappings from localization (try Russian first)
                try:
                    mappings = self._get_provider_mappings("ru")
                    voice_mappings = mappings.get("voice_names", {})
                    
                    # Try English if not found in Russian
                    if voice_name not in voice_mappings:
                        mappings = self._get_provider_mappings("en")
                        voice_mappings = mappings.get("voice_names", {})
                except RuntimeError:
                    # Fallback to hardcoded if assets not available
                    voice_mappings = {
                        "ксении": {"provider": "silero_v3", "params": {"speaker": "xenia"}},
                        "кcении": {"provider": "silero_v3", "params": {"speaker": "xenia"}},
                        "айдара": {"provider": "silero_v3", "params": {"speaker": "aidar"}},
                        "силеро": {"provider": "silero_v3", "params": {}},
                        "консоли": {"provider": "console", "params": {}},
                        "системным": {"provider": "pyttsx", "params": {}}
                    }
                
                if voice_name in voice_mappings:
                    voice_config = voice_mappings[voice_name]
                    provider = voice_config.get("provider")
                    params = voice_config.get("params", {})
                    if provider in tts_component.providers:
                        await tts_component.speak(text_to_speak, provider=provider, **params)
                        self.logger.info(f"🔊 TTS synthesis completed with voice {voice_name}: '{text_to_speak}'")
                        return True
                    else:
                        self.logger.warning(f"Voice {voice_name} not available, using default")
                        await tts_component.speak(text_to_speak)
                        return True
                else:
                    # Voice name not recognized, use default
                    self.logger.warning(f"Voice name '{voice_name}' not recognized, using default")
                    await tts_component.speak(text_to_speak)
                    return True
            else:
                # Use default provider
                await tts_component.speak(text_to_speak)
                self.logger.info(f"🔊 TTS synthesis completed with default voice: '{text_to_speak}'")
                return True
                
        except Exception as e:
            self.logger.error(f"TTS synthesis action failed: {e}")
            # TODO: Could trigger failure notification here
            return False
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Voice synthesis handler has no external dependencies - uses TTS component"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Voice synthesis handler has no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
    
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Voice synthesis handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    # Configuration metadata: No configuration needed
    # This handler delegates to TTS component and uses asset loader for voice mappings
    # No get_config_schema() method = no configuration required
    
    def _get_language_from_context(self, context: UnifiedConversationContext) -> str:
        """Get language from conversation context with fallback"""
        return context.language or "ru"
    
    async def _stop_synthesis_action(self, language: str) -> bool:
        """Stop voice synthesis action"""
        tts_component = await self._get_tts_component()
        if not tts_component:
            logger.error("TTS component not available for stop action")
            return False
        
        try:
            # Stop current synthesis
            await tts_component.stop_synthesis()
            logger.info("Voice synthesis stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to stop voice synthesis: {e}")
            return False
    
    async def _cancel_synthesis_action(self, language: str) -> bool:
        """Cancel voice synthesis action"""
        tts_component = await self._get_tts_component()
        if not tts_component:
            logger.error("TTS component not available for cancel action")
            return False
        
        try:
            # Cancel current synthesis (same as stop for TTS)
            await tts_component.cancel_synthesis()
            logger.info("Voice synthesis cancelled successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel voice synthesis: {e}")
            return False
