"""
Text Enhancement Intent Handler - Text improvement commands

Handles text enhancement/improvement commands that were previously hardcoded
in LLMComponent. Delegates to LLMComponent for actual functionality.
"""

import logging
from typing import List, Dict, Any

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class TextEnhancementIntentHandler(IntentHandler):
    """
    Handles text enhancement intents - text improvement via LLM.
    
    Features:
    - Text improvement and correction
    - Text reformulation
    - Grammar and style enhancement
    """
    
    def __init__(self):
        super().__init__()
        self._llm_component = None

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Text enhancement handler needs no external dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Text enhancement handler has no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Text enhancement handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process text enhancement intents"""
        if not self.has_donation():
            raise RuntimeError(f"TextEnhancementIntentHandler: Missing JSON donation file - text_enhancement_handler.json is required")
        
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
        """Execute text enhancement intent"""
        # Use donation-driven routing exclusively
        return await self.execute_with_donation_routing(intent, context)
        
    async def _handle_enhance_text(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle text enhancement request"""
        llm_component = await self._get_llm_component()
        if not llm_component:
            return self._create_error_result(intent, context, "LLM component not available")
        
        # Extract text to enhance from command using LLM component helper method
        text_to_enhance = llm_component.extract_text_from_command(intent.text)
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        if text_to_enhance:
            try:
                enhanced = await llm_component.enhance_text(text_to_enhance, task="improve")
                response_text = self._get_template("enhanced_text", language, enhanced=enhanced)
                    
                self.logger.info(f"Text enhancement completed")
                
                return IntentResult(
                    text=response_text,
                    should_speak=True,
                    metadata={
                        "action": "enhance",
                        "original_text": text_to_enhance,
                        "enhanced_text": enhanced,
                        "language": language
                    },
                    success=True
                )
            except Exception as e:
                self.logger.error(f"Text enhancement error: {e}")
                return self._create_error_result(intent, context, f"Text enhancement failed: {e}")
        else:
            return self._create_error_result(intent, context, "Could not extract text to enhance")
        
    async def _handle_improve_text(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle text improvement request"""
        llm_component = await self._get_llm_component()
        if not llm_component:
            return self._create_error_result(intent, context, "LLM component not available")
        
        # Extract text to improve from intent entities
        text_to_improve = intent.entities.get("text")
        
        if not text_to_improve:
            # Try to extract from original command using LLM component
            text_to_improve = llm_component.extract_text_from_command(intent.text)
            
        if not text_to_improve:
            return self._create_error_result(intent, context, "Text to improve not found")
        
        try:
            improved = await llm_component.enhance_text(text_to_improve, task="improve")
            
            # Use language from context (detected by NLU)
            language = context.language or "ru"
            
            response_text = self._get_template("improved_text", language, improved=improved)
            
            self.logger.info(f"Text improvement completed")
            
            return IntentResult(
                text=response_text,
                should_speak=True,
                metadata={
                    "action": "improve",
                    "original_text": text_to_improve,
                    "improved_text": improved,
                    "language": language
                },
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Text improvement error: {e}")
            return self._create_error_result(intent, context, f"Text improvement failed: {e}")
            
    async def _handle_correct_text(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle text correction request"""
        llm_component = await self._get_llm_component()
        if not llm_component:
            return self._create_error_result(intent, context, "LLM component not available")
        
        # Extract text to correct from intent entities
        text_to_correct = intent.entities.get("text")
        
        if not text_to_correct:
            # Try to extract from original command using LLM component
            text_to_correct = llm_component.extract_text_from_command(intent.text)
            
        if not text_to_correct:
            return self._create_error_result(intent, context, "Text to correct not found")
        
        try:
            corrected = await llm_component.enhance_text(text_to_correct, task="correct")
            
            # Use language from context (detected by NLU)
            language = context.language or "ru"
            
            response_text = self._get_template("corrected_text", language, corrected=corrected)
            
            self.logger.info(f"Text correction completed")
            
            return IntentResult(
                text=response_text,
                should_speak=True,
                metadata={
                    "action": "correct",
                    "original_text": text_to_correct,
                    "corrected_text": corrected,
                    "language": language
                },
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Text correction error: {e}")
            return self._create_error_result(intent, context, f"Text correction failed: {e}")
    
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
                f"TextEnhancementIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - text enhancement templates must be externalized."
            )
        
        # Get template from asset loader
        template_content = self.asset_loader.get_template("text_enhancement", template_name, language)
        if template_content is None:
            raise RuntimeError(
                f"TextEnhancementIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/text_enhancement/{language}/result_messages.yaml. "
                f"This is a fatal error - all text enhancement templates must be externalized."
            )
        
        # Format template with provided arguments
        try:
            return template_content.format(**format_args)
        except KeyError as e:
            raise RuntimeError(
                f"TextEnhancementIntentHandler: Template '{template_name}' missing required format argument: {e}. "
                f"Check assets/templates/text_enhancement/{language}/result_messages.yaml for correct placeholders."
            )
    
    def _create_error_result(self, intent: Intent, context: ConversationContext, error: str) -> IntentResult:
        """Create error result with language awareness"""
        language = context.language or "ru"
        
        error_text = self._get_template("error_enhancement", language, error=error)
        
        return IntentResult(
            text=error_text,
            should_speak=True,
            metadata={
                "error": error,
                "language": language
            },
            success=False
        )
