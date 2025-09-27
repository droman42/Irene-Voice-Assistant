"""
Translation Intent Handler - Text translation commands

Handles text translation commands that were previously hardcoded
in LLMComponent. Delegates to LLMComponent for actual functionality.
"""

import logging
from typing import List, Dict, Any, TYPE_CHECKING

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TranslationIntentHandler(IntentHandler):
    """
    Handles translation intents - text translation via LLM.
    
    Features:
    - Text translation between languages
    - Language detection and specification
    - Translation request parsing
    """
    
    def __init__(self):
        super().__init__()
        self._llm_component = None

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Translation handler needs no external dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Translation handler has no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Translation handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process translation intents"""
        if not self.has_donation():
            raise RuntimeError(f"TranslationIntentHandler: Missing JSON donation file - translation_handler.json is required")
        
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
        """Execute translation intent"""
        # Use donation-driven routing exclusively
        return await self.execute_with_donation_routing(intent, context)
        
    async def _handle_translate_text(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle text translation request"""
        llm_component = await self._get_llm_component()
        if not llm_component:
            return self._create_error_result(intent, context, "LLM component not available")
        
        # Extract text and target language from command using LLM component helper methods
        text_and_lang = llm_component.extract_translation_request(intent.text)
        
        # Use language from context (detected by NLU) for response
        language = context.language or "ru"
        
        if text_and_lang:
            text, target_lang = text_and_lang
            try:
                translated = await llm_component.enhance_text(text, task="translation", target_language=target_lang, trace_context=self._trace_context)
                response_text = self._get_template("translation_result", language, translated=translated)
                    
                self.logger.info(f"Translation completed: {text} -> {target_lang}")
                
                return IntentResult(
                    text=response_text,
                    should_speak=True,
                    metadata={
                        "action": "translate",
                        "original_text": text,
                        "target_language": target_lang,
                        "translated_text": translated,
                        "language": language
                    },
                    success=True
                )
            except Exception as e:
                self.logger.error(f"Translation error: {e}")
                return self._create_error_result(intent, context, f"Translation failed: {e}")
        else:
            return self._create_error_result(intent, context, "Could not extract text to translate")
        
    async def _handle_translate_specific(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle specific text translation with extracted entities"""
        llm_component = await self._get_llm_component()
        if not llm_component:
            return self._create_error_result(intent, context, "LLM component not available")
        
        # Use language from context (detected by NLU) first
        language = context.language or "ru"
        
        # Extract text and target language from intent entities
        text_to_translate = intent.entities.get("text")
        target_language = intent.entities.get("target_language", self._get_template("default_target_language", language))
        
        if not text_to_translate:
            # Try to extract from original command using LLM component
            extraction_result = llm_component.extract_translation_request(intent.text)
            if extraction_result:
                text_to_translate, target_language = extraction_result
            else:
                return self._create_error_result(intent, context, "Text to translate not found")
        
        try:
            translated = await llm_component.enhance_text(
                text_to_translate, 
                task="translation", 
                target_language=target_language,
                trace_context=self._trace_context
            )
            
            response_text = self._get_template("translation_result", language, translated=translated)
            
            self.logger.info(f"Specific translation: {text_to_translate} -> {target_language}")
            
            return IntentResult(
                text=response_text,
                should_speak=True,
                metadata={
                    "action": "translate_specific",
                    "original_text": text_to_translate,
                    "target_language": target_language,
                    "translated_text": translated,
                    "language": language
                },
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Translation error: {e}")
            return self._create_error_result(intent, context, f"Translation failed: {e}")
    
    async def _get_llm_component(self):
        """Get LLM component from core"""
        if self._llm_component is None:
            try:
                from ...core.engine import get_core
                core = get_core()
                if core and hasattr(core, 'component_manager'):
                    self._llm_component = await core.component_manager.get_component('llm')
            except Exception as e:
                self.logger.error(f"Failed to get LLM component: {e}")
                return None
        
        return self._llm_component
        

        
    def _get_template(self, template_name: str, language: str = "ru", **format_args) -> str:
        """Get template from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"TranslationIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - translation templates must be externalized."
            )
        
        # Get template from asset loader
        template_content = self.asset_loader.get_template("translation", template_name, language)
        if template_content is None:
            raise RuntimeError(
                f"TranslationIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/translation/{language}/result_messages.yaml. "
                f"This is a fatal error - all translation templates must be externalized."
            )
        
        # Format template with provided arguments
        try:
            return template_content.format(**format_args)
        except KeyError as e:
            raise RuntimeError(
                f"TranslationIntentHandler: Template '{template_name}' missing required format argument: {e}. "
                f"Check assets/templates/translation/{language}/result_messages.yaml for correct placeholders."
            )
    
    def _create_error_result(self, intent: Intent, context: ConversationContext, error: str) -> IntentResult:
        """Create error result with language awareness"""
        language = context.language or "ru"
        
        error_text = self._get_template("error_translation", language, error=error)
        
        return IntentResult(
            text=error_text,
            should_speak=True,
            metadata={
                "error": error,
                "language": language
            },
            success=False
        )
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Translation handler has no external dependencies - uses LLM component"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Translation handler has no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
    
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Translation handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    # Configuration metadata: No configuration needed
    # This handler delegates to LLM component and uses asset loader for language mappings
    # No get_config_schema() method = no configuration required
