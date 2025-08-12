"""
Speech Recognition Intent Handler - ASR configuration

Handles speech recognition configuration commands that were previously hardcoded
in ASRComponent. Delegates to ASRComponent for actual functionality.
"""

import logging
from typing import List, Dict, Any

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class SpeechRecognitionIntentHandler(IntentHandler):
    """
    Handles speech recognition intents - ASR configuration.
    
    Features:
    - ASR provider switching
    - ASR provider information display
    - Language switching for ASR
    - ASR configuration management
    """
    
    def __init__(self):
        super().__init__()
        self._asr_component = None

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Speech recognition handler needs no external dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Speech recognition handler has no system dependencies"""
        return {
            "ubuntu": [],
            "alpine": [],
            "centos": [],
            "macos": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Speech recognition handler supports all platforms"""
        return ["linux", "windows", "macos"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process speech recognition intents"""
        if not self.has_donation():
            raise RuntimeError(f"SpeechRecognitionIntentHandler: Missing JSON donation file - speech_recognition_handler.json is required")
        
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
        """Execute speech recognition intent"""
        # Use donation-driven routing exclusively
        return await self.execute_with_donation_routing(intent, context)
        
    async def _handle_show_recognition(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle show ASR providers request"""
        asr_component = await self._get_asr_component()
        if not asr_component:
            return self._create_error_result(intent, context, "ASR component not available")
        
        info = asr_component.get_providers_info()
        
        # Determine language
        language = self._get_language(intent, context)
        
        self.logger.info(f"ASR providers info requested")
        
        return IntentResult(
            text=info,
            should_speak=True,
            metadata={
                "action": "show_recognition",
                "language": language
            },
            success=True
        )
        
    async def _handle_switch_asr_provider(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle ASR provider switching request"""
        asr_component = await self._get_asr_component()
        if not asr_component:
            return self._create_error_result(intent, context, "ASR component not available")
        
        # Extract provider name from intent entities or text
        provider_name = intent.entities.get("provider")
        if not provider_name:
            provider_name = asr_component.parse_provider_name_from_text(intent.text)
        
        if not provider_name:
            return self._create_error_result(intent, context, "Provider name not specified")
        
        # Determine language
        language = self._get_language(intent, context)
        
        success = asr_component.set_default_provider(provider_name)
        
        if success:
            if language == "ru":
                message = f"Переключился на {provider_name}"
            else:
                message = f"Switched to {provider_name}"
        else:
            if language == "ru":
                message = f"Провайдер {provider_name} недоступен"
            else:
                message = f"Provider {provider_name} not available"
        
        self.logger.info(f"ASR provider switch to {provider_name} - success: {success}")
        
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
        
    async def _handle_switch_language(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle ASR language switching request"""
        asr_component = await self._get_asr_component()
        if not asr_component:
            return self._create_error_result(intent, context, "ASR component not available")
        
        # Extract language from intent entities
        target_language = intent.entities.get("language", "русский")
        
        success, message = await asr_component.switch_language(target_language)
        
        # Determine language
        language = self._get_language(intent, context)
        
        self.logger.info(f"ASR language switch to {target_language} - success: {success}")
        
        return IntentResult(
            text=message,
            should_speak=True,
            metadata={
                "action": "switch_language",
                "target_language": target_language,
                "success": success,
                "language": language
            },
            success=success
        )
        
    async def _handle_configure_quality(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle ASR quality configuration request"""
        # Extract quality setting from intent entities
        quality = intent.entities.get("quality", "high")
        
        # Determine language
        language = self._get_language(intent, context)
        
        # TODO: Implement quality configuration logic
        if language == "ru":
            response_text = f"Настройка качества распознавания речи ({quality}) пока не реализована"
        else:
            response_text = f"Speech recognition quality configuration ({quality}) not yet implemented"
        
        self.logger.info(f"ASR quality configuration request: {quality}")
        
        return IntentResult(
            text=response_text,
            should_speak=True,
            metadata={
                "action": "configure_quality",
                "quality": quality,
                "language": language,
                "implemented": False
            },
            success=False
        )
        
    async def _handle_configure_microphone(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle microphone configuration request"""
        # Extract microphone device from intent entities
        microphone = intent.entities.get("microphone", "default")
        
        # Determine language
        language = self._get_language(intent, context)
        
        # TODO: Implement microphone configuration logic
        if language == "ru":
            response_text = f"Настройка микрофона ({microphone}) пока не реализована"
        else:
            response_text = f"Microphone configuration ({microphone}) not yet implemented"
        
        self.logger.info(f"Microphone configuration request: {microphone}")
        
        return IntentResult(
            text=response_text,
            should_speak=True,
            metadata={
                "action": "configure_microphone",
                "microphone": microphone,
                "language": language,
                "implemented": False
            },
            success=False
        )
    
    async def _get_asr_component(self):
        """Get ASR component from core"""
        if self._asr_component is None:
            try:
                from ...core.engine import get_core
                core = get_core()
                if core and hasattr(core, 'component_manager'):
                    self._asr_component = await core.component_manager.get_component('asr')
            except Exception as e:
                self.logger.error(f"Failed to get ASR component: {e}")
                return None
        
        return self._asr_component
        
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
            error_text = f"Ошибка настройки распознавания речи: {error}"
        else:
            error_text = f"Speech recognition configuration error: {error}"
        
        return IntentResult(
            text=error_text,
            should_speak=True,
            metadata={
                "error": error,
                "language": language
            },
            success=False
        )
