"""
Voice Synthesis Intent Handler - TTS with specific voices

Handles voice synthesis commands that were previously hardcoded
in TTSComponent. Delegates to TTSComponent for actual functionality.
"""

import logging
import time
from typing import List, Dict, Any

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

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
        
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Execute voice synthesis intent"""
        # Use donation-driven routing exclusively
        return await self.execute_with_donation_routing(intent, context)
        
    async def _handle_speak_with_voice(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle speak with specific voice request with fire-and-forget TTS generation"""
        tts_component = await self._get_tts_component()
        if not tts_component:
            return self._create_error_result(intent, context, "TTS component not available")
        
        # Determine language
        language = self._get_language(intent, context)
        
        # Extract text and voice parameters from command
        text_to_speak, voice_name = self._extract_speech_parameters(intent.text)
        
        if not text_to_speak:
            return self._create_error_result(intent, context, "No text to speak found")
        
        # Use fire-and-forget action execution for TTS generation
        synthesis_id = f"tts_{int(time.time() * 1000)}"  # Unique ID based on timestamp
        action_metadata = await self.execute_fire_and_forget_action(
            self._synthesize_speech_action,
            action_name=synthesis_id,
            domain="voice_synthesis",
            text_to_speak=text_to_speak,
            voice_name=voice_name,
            language=language,
            tts_component=tts_component
        )
        
        # Immediate response while TTS runs in background
        if language == "ru":
            response_text = f"Синтезирую речь '{text_to_speak}'"
            if voice_name:
                response_text += f" голосом {voice_name}"
        else:
            response_text = f"Synthesizing speech '{text_to_speak}'"
            if voice_name:
                response_text += f" with voice {voice_name}"
        
        return self.create_action_result(
            response_text=response_text,
            action_name=synthesis_id,
            domain="voice_synthesis",
            should_speak=True,
            action_metadata=action_metadata
        )
        
    async def _handle_list_voices(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle list available voices request"""
        tts_component = await self._get_tts_component()
        if not tts_component:
            return self._create_error_result(intent, context, "TTS component not available")
        
        # Get TTS providers information
        response = tts_component.get_providers_info()
        success = True
        
        # Determine language
        language = self._get_language(intent, context)
        
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
        
    async def _handle_speak_text(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle basic text-to-speech request with fire-and-forget synthesis"""
        tts_component = await self._get_tts_component()
        if not tts_component:
            return self._create_error_result(intent, context, "TTS component not available")
        
        # Extract text to speak from intent entities
        text_to_speak = intent.entities.get("text", intent.text)
        if not text_to_speak.strip():
            return self._create_error_result(intent, context, "No text to speak")
        
        # Determine language
        language = self._get_language(intent, context)
        
        # Use fire-and-forget action execution for basic TTS
        synthesis_id = f"tts_basic_{int(time.time() * 1000)}"
        action_metadata = await self.execute_fire_and_forget_action(
            self._synthesize_speech_action,
            action_name=synthesis_id,
            domain="voice_synthesis",
            text_to_speak=text_to_speak,
            voice_name=None,  # Use default voice
            language=language,
            tts_component=tts_component
        )
        
        # Immediate response
        if language == "ru":
            response_text = f"Синтезирую: {text_to_speak}"
        else:
            response_text = f"Synthesizing: {text_to_speak}"
        
        return self.create_action_result(
            response_text=response_text,
            action_name=synthesis_id,
            domain="voice_synthesis",
            should_speak=False,  # Don't speak the confirmation since we're about to speak the actual text
            action_metadata=action_metadata
        )
            
    async def _handle_switch_tts_provider(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle TTS provider switching request"""
        tts_component = await self._get_tts_component()
        if not tts_component:
            return self._create_error_result(intent, context, "TTS component not available")
        
        # Determine language
        language = self._get_language(intent, context)
        
        # Parse provider name from text and switch
        provider_name = self._parse_tts_provider_name(intent.text)
        success = tts_component.set_default_provider(provider_name) if provider_name else False
        
        if success:
            if language == "ru":
                response = f"Переключился на TTS провайдер {provider_name}"
            else:
                response = f"Switched to TTS provider {provider_name}"
        else:
            if language == "ru":
                response = f"TTS провайдер {provider_name or 'неизвестный'} недоступен"
            else:
                response = f"TTS provider {provider_name or 'unknown'} not available"
        
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
            error_text = f"Ошибка синтеза речи: {error}"
        else:
            error_text = f"Speech synthesis error: {error}"
        
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
                    
                    # Map voice names to providers
                    provider_mapping = {
                        "ксении": ("silero_v3", {"speaker": "xenia"}),
                        "кcении": ("silero_v3", {"speaker": "xenia"}),
                        "айдара": ("silero_v3", {"speaker": "aidar"}),
                        "силеро": ("silero_v3", {}),
                        "консоли": ("console", {}),
                        "системным": ("pyttsx", {})
                    }
                    
                    if voice_name in provider_mapping:
                        provider, params = provider_mapping[voice_name]
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
        
        # Simple provider name mapping
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
                # Map voice names to providers
                provider_mapping = {
                    "ксении": ("silero_v3", {"speaker": "xenia"}),
                    "кcении": ("silero_v3", {"speaker": "xenia"}),
                    "айдара": ("silero_v3", {"speaker": "aidar"}),
                    "силеро": ("silero_v3", {}),
                    "консоли": ("console", {}),
                    "системным": ("pyttsx", {})
                }
                
                if voice_name in provider_mapping:
                    provider, params = provider_mapping[voice_name]
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
