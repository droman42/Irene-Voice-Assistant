"""
Conversation Intent Handler - Interactive LLM Chat for Intent System

Provides conversational interactions using LLM components.
Adapted from conversation_plugin.py for the new intent architecture.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Type, TYPE_CHECKING

from .base import IntentHandler
from ..models import Intent, IntentResult, UnifiedConversationContext

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ConversationSession class removed - functionality moved to UnifiedConversationContext.handler_contexts


class ConversationIntentHandler(IntentHandler):
    """
    Handles conversational intents with LLM integration.
    
    Manages conversation flow, maintains context, and provides 
    intelligent responses using Large Language Models.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.conversation_context: List[Dict[str, str]] = []
# Session management now handled by UnifiedConversationContext handler_contexts
        self.llm_component = None
        
        # Phase 5: Configuration injection via Pydantic ConversationHandlerConfig
        if config:
            self.config = config
            self.max_context_length = config.get("max_context_length", 10)
            logger.info(f"ConversationIntentHandler initialized with config: session_timeout={config.get('session_timeout')}, max_sessions={config.get('max_sessions')}, max_context_length={self.max_context_length}")
        else:
            # Fallback defaults (should not be used in production with proper config)
            self.config = {
                "session_timeout": 1800,  # 30 minutes
                "max_sessions": 50,
                "max_context_length": 10,
                "default_conversation_confidence": 0.6  # Lower confidence for fallback
            }
            self.max_context_length = 10
            logger.warning("ConversationIntentHandler initialized without configuration - using fallback defaults")
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Conversation handler needs no external dependencies - uses LLM providers through components"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Conversation handler has no system dependencies - uses LLM providers through components"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Conversation handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    # Configuration metadata methods
    @classmethod
    def get_config_schema(cls) -> Type["BaseModel"]:
        """Return configuration schema for conversation handler"""
        from ...config.models import ConversationHandlerConfig
        return ConversationHandlerConfig
    
    @classmethod
    def get_config_defaults(cls) -> Dict[str, Any]:
        """Return default configuration values matching TOML"""
        return {
            "session_timeout": 1800,  # matches config-master.toml line 414
            "max_sessions": 50,       # matches config-master.toml line 415
            "max_context_length": 10, # matches config-master.toml line 416
            "default_conversation_confidence": 0.6  # matches config-master.toml line 417
        }
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process conversation intents"""
        if not self.has_donation():
            raise RuntimeError(f"ConversationIntentHandler: Missing JSON donation file - conversation.json is required")
        
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
        
        # Check fallback conditions
        if hasattr(donation, 'fallback_conditions'):
            for condition in donation.fallback_conditions:
                if (intent.domain == condition.get('domain') and 
                    intent.confidence < condition.get('confidence_threshold', 1.0)):
                    return True
        
        return False
    
    async def execute(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Execute conversation intent using LLM or fallback handling"""
        try:
            # Check if this is a fallback scenario (when NLU failed to recognize intent)
            is_fallback = intent.entities.get("_recognition_provider") == "fallback"
            
            # For fallback scenarios, check if LLM is available before deciding on fallback approach
            if is_fallback:
                llm_component = await self._get_llm_component()
                if llm_component and await llm_component.is_available():
                    # LLM is available - treat as conversation.general and use LLM
                    logger.info(f"NLU fallback detected but LLM available - using LLM for: {intent.raw_text}")
                    return await self._handle_continue_conversation(intent, context)
                else:
                    # LLM not available - use template-based fallback
                    logger.info(f"NLU fallback detected and LLM unavailable - using templates for: {intent.raw_text}")
                    return await self._handle_fallback_without_llm(intent, context)
            
            # Handle specific conversation actions using unified context
            if intent.action == "start":
                return await self._handle_start_conversation(intent, context)
            elif intent.action == "end":
                return await self._handle_end_conversation(intent, context)
            elif intent.action == "clear":
                return await self._handle_clear_conversation(intent, context)
            elif intent.action == "reference":
                return await self._handle_reference_query(intent, context)
            else:
                # Default: continue conversation
                return await self._handle_continue_conversation(intent, context)
                
        except Exception as e:
            logger.error(f"Conversation intent execution failed: {e}")
            return IntentResult(
                text="Извините, произошла ошибка в обработке диалога.",
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    def set_llm_component(self, llm_component):
        """Set the LLM component reference"""
        self.llm_component = llm_component
    
    async def _get_llm_component(self):
        """Get LLM component from core (dynamic access pattern)"""
        if self.llm_component is None:
            try:
                from ...core.engine import get_core
                core = get_core()
                if core and hasattr(core, 'component_manager'):
                    self.llm_component = await core.component_manager.get_component('llm')
            except Exception as e:
                self.logger.error(f"Failed to get LLM component: {e}")
                return None
        
        return self.llm_component
    
    def _get_prompt(self, prompt_type: str, language: str = "ru") -> str:
        """Get prompt from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"ConversationIntentHandler: Asset loader not initialized. "
                f"Cannot access prompt '{prompt_type}' for language '{language}'. "
                f"This is a fatal configuration error - prompts must be externalized."
            )
        
        # Get prompt from asset loader
        prompt = self.asset_loader.get_prompt("conversation", prompt_type, language)
        if prompt is None:
            raise RuntimeError(
                f"ConversationIntentHandler: Required prompt '{prompt_type}' for language '{language}' "
                f"not found in assets/prompts/conversation/{language}/conversation_prompts.yaml. "
                f"This is a fatal error - all conversation prompts must be externalized."
            )
        
        return prompt

    def _get_template_data(self, template_name: str, language: str = "ru") -> List[str]:
        """Get template data (arrays) from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"ConversationIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - templates must be externalized."
            )
        
        # Get template from asset loader
        template_data = self.asset_loader.get_template("conversation", template_name, language)
        if template_data is None:
            raise RuntimeError(
                f"ConversationIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/conversation/{language}/responses.yaml. "
                f"This is a fatal error - all conversation templates must be externalized."
            )
        
        # Ensure it's a list
        if not isinstance(template_data, list):
            raise RuntimeError(
                f"ConversationIntentHandler: Template '{template_name}' should be a list but got {type(template_data)}. "
                f"Check assets/templates/conversation/{language}/responses.yaml"
            )
        
        return template_data

    def _get_template(self, template_name: str, language: str = "ru", **format_args) -> str:
        """Get template string from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"ConversationIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - templates must be externalized."
            )
        
        # Get template from asset loader
        template_content = self.asset_loader.get_template("conversation", template_name, language)
        if template_content is None:
            raise RuntimeError(
                f"ConversationIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/conversation/{language}/responses.yaml. "
                f"This is a fatal error - all conversation templates must be externalized."
            )
        
        # Format template with provided arguments if any
        if format_args:
            try:
                return template_content.format(**format_args)
            except KeyError as e:
                raise RuntimeError(
                    f"ConversationIntentHandler: Template '{template_name}' missing required format argument: {e}. "
                    f"Check assets/templates/conversation/{language}/responses.yaml for correct placeholders."
                )
        
        return template_content
    
    async def is_available(self) -> bool:
        """Check if LLM component is available for conversation"""
        llm_component = await self._get_llm_component()
        if not llm_component:
            return False
        return await llm_component.is_available()
    
# Session management removed - now handled by UnifiedConversationContext handler_contexts
    
    async def _handle_start_conversation(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle conversation start intent"""
        # Clear any existing conversation history in unified context
        conversation_type = "reference" if intent.action == "reference" else "chat"
        system_prompt = (self._get_prompt("reference_system") if conversation_type == "reference" 
                        else self._get_prompt("chat_system"))
        
        # Initialize or reset handler context for conversation
        handler_context = context.get_handler_context("conversation")
        handler_context["conversation_type"] = conversation_type
        handler_context["model_preference"] = ""
        
        # Clear and set system message if needed
        context.clear_handler_context("conversation", keep_system=True)
        if system_prompt and not handler_context["messages"]:
            handler_context["messages"] = [{"role": "system", "content": system_prompt}]
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Get greeting templates from asset loader
        greetings = self._get_template_data("start_greetings", language)
        
        import random
        response = random.choice(greetings)
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={
                "conversation_type": conversation_type,
                "session_id": context.session_id
            }
        )
    
    async def _handle_end_conversation(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle conversation end intent"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Get farewell templates from asset loader
        farewells = self._get_template_data("end_farewells", language)
        
        import random
        response = random.choice(farewells)
        
        # Clear conversation handler context
        context.clear_handler_context("conversation", keep_system=False)
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={"conversation_ended": True}
        )
    
    async def _handle_clear_conversation(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle conversation clear/reset intent"""
        # Clear conversation handler context but keep system message
        context.clear_handler_context("conversation", keep_system=True)
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Get clear response template from asset loader
        response = self._get_template("clear_response", language)
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={"conversation_cleared": True}
        )
    
    async def _handle_reference_query(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle reference/factual query intent"""
        llm_component = await self._get_llm_component()
        if not llm_component:
            return IntentResult(
                text="Извините, справочный режим недоступен.",
                should_speak=True,
                success=False
            )
        
        # Format query for reference mode
        query = intent.raw_text
        template = self._get_prompt("reference_template")
        formatted_prompt = template.format(query)
        
        try:
            # Use LLM component's default model for factual queries
            response = await llm_component.generate_response(
                messages=[{"role": "user", "content": formatted_prompt}],
                trace_context=self._trace_context
            )
            
            return IntentResult(
                text=response,
                should_speak=True,
                metadata={
                    "conversation_type": "reference",
                    "query": query
                }
            )
            
        except Exception as e:
            logger.error(f"Reference query failed: {e}")
            return IntentResult(
                text="Извините, не удалось получить справочную информацию.",
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    async def _handle_continue_conversation(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle ongoing conversation intent - donation-compatible method signature"""
        # Note: Fallback logic is now handled in execute() method, not here
        
        # For conversation (including NLU fallback when LLM is available), require LLM
        llm_component = await self._get_llm_component()
        if not llm_component:
            return IntentResult(
                text="Извините, диалоговый режим недоступен.",
                should_speak=True,
                success=False
            )
        
        try:
            # Get or create conversation handler context
            handler_context = context.get_handler_context("conversation")
            
            # Check if this was an NLU fallback that we're now handling with LLM
            is_fallback = intent.entities.get("_recognition_provider") == "fallback"
            if is_fallback:
                logger.debug(f"Processing NLU fallback with LLM: '{intent.raw_text}' -> conversation.general")
            
            # Add user message to handler context (LLM-specific conversation management)
            handler_context["messages"].append({"role": "user", "content": intent.raw_text})
            
            # Get conversation history from handler context (properly formatted for LLM)
            messages = handler_context["messages"].copy()
            
            # Generate response using LLM component's default model
            response = await llm_component.generate_response(
                messages=messages,
                trace_context=self._trace_context
            )
            
            # Add assistant response to handler context
            handler_context["messages"].append({"role": "assistant", "content": response})
            
            return IntentResult(
                text=response,
                should_speak=True,
                metadata={
                    "conversation_type": handler_context.get("conversation_type", "chat"),
                    "message_count": len(handler_context["messages"]),
                    "session_id": context.session_id,
                    "nlu_fallback_handled_by_llm": is_fallback,
                    "original_recognition_provider": intent.entities.get("_recognition_provider"),
                    "cascade_attempts": intent.entities.get("_cascade_attempts", 0)
                }
            )
            
        except Exception as e:
            logger.error(f"Conversation continuation failed: {e}")
            return IntentResult(
                text="Извините, произошла ошибка в диалоге. Попробуйте ещё раз.",
                should_speak=True,
                success=False,
                error=str(e)
            )
    async def _handle_fallback_without_llm(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """
        Handle fallback scenario when NLU failed to recognize intent.
        
        This method works without LLM and provides helpful feedback to the user
        about their unrecognized input, encouraging them to rephrase or use specific commands.
        
        Args:
            intent: The fallback intent containing original user text
            context: Conversation context with language information
            
        Returns:
            IntentResult with helpful fallback response and suggestions
        """
        try:
            # Use language from context (detected by NLU) or default to Russian
            language = context.language or "ru"
            
            # Get the original text that couldn't be recognized
            original_text = intent.raw_text or intent.entities.get("original_text", "")
            
            # Get fallback response templates
            fallback_responses = self._get_template_data("fallback_no_llm_responses", language)
            help_suggestions = self._get_template_data("fallback_help_suggestions", language)
            
            # Select random responses
            import random
            fallback_response = random.choice(fallback_responses)
            help_suggestion = random.choice(help_suggestions)
            
            # Format the response with the original text
            formatted_response = fallback_response.format(original_text=original_text)
            
            # Combine response with helpful suggestion
            full_response = f"{formatted_response} {help_suggestion}"
            
            # Get cascade attempt information if available
            cascade_attempts = intent.entities.get("_cascade_attempts", 0)
            
            logger.info(f"Handled fallback without LLM: original_text='{original_text}', "
                       f"cascade_attempts={cascade_attempts}, language={language}")
            
            return IntentResult(
                text=full_response,
                should_speak=True,
                success=True,  # This is successful fallback handling, not an error
                metadata={
                    "conversation_type": "fallback",
                    "original_text": original_text,
                    "cascade_attempts": cascade_attempts,
                    "language": language,
                    "recognition_provider": "fallback",
                    "llm_required": False
                }
            )
            
        except Exception as e:
            logger.error(f"Fallback handling failed: {e}")
            
            # Final emergency fallback - hardcoded message
            language = context.language or "ru"
            if language == "en":
                emergency_response = f"I couldn't understand '{intent.raw_text}'. Please try using simpler commands."
            else:
                emergency_response = f"Я не понимаю '{intent.raw_text}'. Попробуйте использовать более простые команды."
            
            return IntentResult(
                text=emergency_response,
                should_speak=True,
                success=True,
                metadata={
                    "conversation_type": "emergency_fallback",
                    "error": str(e)
                }
            )

    
    async def cleanup(self) -> None:
        """Clean up conversation sessions - now handled by ContextManager"""
        # Session cleanup is now handled by the ContextManager for UnifiedConversationContext
        # No local session management needed
        logger.debug("Conversation handler cleanup completed - session management delegated to ContextManager") 