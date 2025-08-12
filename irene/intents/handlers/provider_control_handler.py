"""
Provider Control Intent Handler - Provider switching across components

Handles provider switching commands that were previously hardcoded
across multiple components. Provides unified provider management.
"""

import logging
from typing import List, Dict, Any

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class ProviderControlIntentHandler(IntentHandler):
    """
    Handles provider control intents - switching providers across components.
    
    Features:
    - Provider switching for all components (Audio, LLM, ASR, TTS)
    - Provider information display
    - Unified provider management
    """
    
    def __init__(self):
        super().__init__()
        self._components = {}

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Provider control handler needs no external dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Provider control handler has no system dependencies"""
        return {
            "ubuntu": [],
            "alpine": [],
            "centos": [],
            "macos": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Provider control handler supports all platforms"""
        return ["linux", "windows", "macos"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process provider control intents"""
        if not self.has_donation():
            raise RuntimeError(f"ProviderControlIntentHandler: Missing JSON donation file - provider_control_handler.json is required")
        
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
        """Execute provider control intent"""
        # Use donation-driven routing exclusively
        return await self.execute_with_donation_routing(intent, context)
        
    async def _handle_switch_provider(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle provider switching request"""
        # Extract component and provider from intent entities
        component_type = intent.entities.get("component", "").lower()
        provider_name = intent.entities.get("provider", "")
        
        # If not in entities, try to extract from text
        if not component_type or not provider_name:
            component_type, provider_name = self._parse_provider_switch_command(intent.text)
        
        if not component_type or not provider_name:
            return self._create_error_result(intent, context, "Component type or provider name not specified")
        
        # Get the appropriate component
        component = await self._get_component(component_type)
        if not component:
            return self._create_error_result(intent, context, f"Component {component_type} not available")
        
        # Determine language
        language = self._get_language(intent, context)
        
        # Switch provider based on component type
        success, message = self._switch_component_provider(component, component_type, provider_name, language)
        
        self.logger.info(f"Provider switch {component_type} -> {provider_name} - success: {success}")
        
        return IntentResult(
            text=message,
            should_speak=True,
            metadata={
                "action": "switch_provider",
                "component": component_type,
                "provider": provider_name,
                "success": success,
                "language": language
            },
            success=success
        )
        
    async def _handle_list_providers(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle list providers request"""
        # Extract component type from intent entities
        component_type = intent.entities.get("component", "").lower()
        
        # If not in entities, try to extract from text
        if not component_type:
            component_type = self._parse_list_providers_command(intent.text)
        
        if not component_type:
            # List all providers from all components
            return await self._list_all_providers(intent, context)
        
        # Get the appropriate component
        component = await self._get_component(component_type)
        if not component:
            return self._create_error_result(intent, context, f"Component {component_type} not available")
        
        # Get provider info based on component type
        info = self._get_component_providers_info(component, component_type)
        
        # Determine language
        language = self._get_language(intent, context)
        
        self.logger.info(f"List providers request for {component_type}")
        
        return IntentResult(
            text=info,
            should_speak=True,
            metadata={
                "action": "list_providers",
                "component": component_type,
                "language": language
            },
            success=True
        )
        
    async def _list_all_providers(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """List providers from all components"""
        info_parts = []
        
        # Determine language
        language = self._get_language(intent, context)
        
        if language == "ru":
            info_parts.append("Все доступные провайдеры:")
        else:
            info_parts.append("All available providers:")
        
        info_parts.append("")
        
        # Check each component type
        for component_type in ["audio", "llm", "asr", "tts"]:
            component = await self._get_component(component_type)
            if component:
                component_info = self._get_component_providers_info(component, component_type)
                if component_info:
                    info_parts.append(component_info)
                    info_parts.append("")
        
        final_info = "\n".join(info_parts).strip()
        
        return IntentResult(
            text=final_info,
            should_speak=True,
            metadata={
                "action": "list_all_providers",
                "language": language
            },
            success=True
        )
    
    def _switch_component_provider(self, component, component_type: str, provider_name: str, language: str) -> tuple[bool, str]:
        """Switch provider for specific component"""
        try:
            # All components now use set_default_provider()
            success = component.set_default_provider(provider_name)
            
            if success:
                if language == "ru":
                    message = f"Переключился на {component_type} провайдер {provider_name}"
                else:
                    message = f"Switched to {component_type} provider {provider_name}"
            else:
                available = ", ".join(component.providers.keys()) if hasattr(component, 'providers') else "unknown"
                if language == "ru":
                    message = f"Провайдер {provider_name} недоступен. Доступные: {available}"
                else:
                    message = f"Provider {provider_name} not available. Available: {available}"
                    
            return success, message
            
        except Exception as e:
            logger.error(f"Error switching {component_type} provider to {provider_name}: {e}")
            if language == "ru":
                return False, f"Ошибка переключения провайдера: {e}"
            else:
                return False, f"Error switching provider: {e}"
    
    def _get_component_providers_info(self, component, component_type: str) -> str:
        """Get provider info for specific component"""
        try:
            if component_type in ["audio", "llm", "asr", "tts"]:
                return component.get_providers_info()
            else:
                return f"Unknown component type: {component_type}"
        except Exception as e:
            logger.error(f"Error getting {component_type} provider info: {e}")
            return f"Error getting provider info: {e}"
    
    def _parse_provider_switch_command(self, text: str) -> tuple[str, str]:
        """Parse component type and provider name from text"""
        text_lower = text.lower()
        
        # Component type mapping
        component_mapping = {
            "аудио": "audio",
            "audio": "audio",
            "звук": "audio",
            "llm": "llm",
            "лл": "llm", 
            "модель": "llm",
            "распознавание": "asr",
            "asr": "asr",
            "распознавание речи": "asr",
            "голос": "tts",
            "tts": "tts",
            "синтез": "tts",
            "речь": "tts"
        }
        
        component_type = ""
        provider_name = ""
        
        # Find component type
        for key, value in component_mapping.items():
            if key in text_lower:
                component_type = value
                break
        
        # Extract provider name after "на"
        if "переключись на" in text_lower:
            parts = text_lower.split("переключись на", 1)
            if len(parts) > 1:
                provider_part = parts[1].strip()
                # Remove component type from provider name
                for key in component_mapping.keys():
                    provider_part = provider_part.replace(key, "").strip()
                provider_name = provider_part.split()[0] if provider_part else ""
        
        return component_type, provider_name
    
    def _parse_list_providers_command(self, text: str) -> str:
        """Parse component type from list providers command"""
        text_lower = text.lower()
        
        # Component type mapping
        component_mapping = {
            "аудио": "audio",
            "audio": "audio",
            "звук": "audio",
            "llm": "llm",
            "модель": "llm",
            "распознавание": "asr",
            "asr": "asr",
            "голос": "tts",
            "tts": "tts",
            "синтез": "tts"
        }
        
        # Find component type
        for key, value in component_mapping.items():
            if key in text_lower:
                return value
        
        return ""
    
    async def _get_component(self, component_type: str):
        """Get component from core"""
        if component_type not in self._components:
            try:
                from ...core.engine import get_core
                core = get_core()
                if core and hasattr(core, 'component_manager'):
                    self._components[component_type] = await core.component_manager.get_component(component_type)
            except Exception as e:
                self.logger.error(f"Failed to get {component_type} component: {e}")
                return None
        
        return self._components[component_type]
        
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
            error_text = f"Ошибка управления провайдерами: {error}"
        else:
            error_text = f"Provider control error: {error}"
        
        return IntentResult(
            text=error_text,
            should_speak=True,
            metadata={
                "error": error,
                "language": language
            },
            success=False
        )
