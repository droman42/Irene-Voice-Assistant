"""
Conversation Intent Handler - Interactive LLM Chat for Intent System

Provides conversational interactions using LLM components.
Adapted from conversation_plugin.py for the new intent architecture.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Type, TYPE_CHECKING

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ConversationSession:
    """Manages a single conversation session with message history"""
    
    def __init__(self, session_id: str, conversation_type: str = "chat", 
                 system_prompt: str = "", model_preference: str = ""):
        self.session_id = session_id
        self.conversation_type = conversation_type  # "chat" or "reference"
        self.messages: List[Dict[str, str]] = []
        self.created_at = time.time()
        self.last_activity = time.time()
        self.model_preference = model_preference
        
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history"""
        self.messages.append({"role": role, "content": content})
        self.last_activity = time.time()
    
    def get_messages(self) -> List[Dict[str, str]]:
        """Get the complete message history"""
        return self.messages.copy()
    
    def clear_history(self, keep_system: bool = True) -> None:
        """Clear conversation history, optionally keeping system message"""
        if keep_system and self.messages and self.messages[0].get("role") == "system":
            system_msg = self.messages[0]
            self.messages = [system_msg]
        else:
            self.messages = []


class ConversationIntentHandler(IntentHandler):
    """
    Handles conversational intents with LLM integration.
    
    Manages conversation flow, maintains context, and provides 
    intelligent responses using Large Language Models.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.conversation_context: List[Dict[str, str]] = []
        self.sessions: Dict[str, ConversationSession] = {}
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
    
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Execute conversation intent using LLM or fallback handling"""
        try:
            # Check if this is a fallback scenario (when NLU failed to recognize intent)
            is_fallback = intent.entities.get("_recognition_provider") == "fallback"
            
            # For fallback scenarios, use the fallback handler regardless of action
            if is_fallback:
                return await self._handle_fallback_without_llm(intent, context)
            
            # Get or create conversation session for normal conversation actions
            session = self._get_or_create_session(context.session_id, intent)
            
            # Handle specific conversation actions
            if intent.action == "start":
                return await self._handle_start_conversation(intent, context, session)
            elif intent.action == "end":
                return await self._handle_end_conversation(intent, context, session)
            elif intent.action == "clear":
                return await self._handle_clear_conversation(intent, context, session)
            elif intent.action == "reference":
                return await self._handle_reference_query(intent, session)
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
        if not self.llm_component:
            return False
        return await self.llm_component.is_available()
    
    def _get_or_create_session(self, session_id: str, intent: Intent) -> ConversationSession:
        """Get existing session or create new one"""
        if session_id not in self.sessions:
            # Determine conversation type from intent
            conversation_type = "reference" if intent.action == "reference" else "chat"
            system_prompt = (self._get_prompt("reference_system") if conversation_type == "reference" 
                           else self._get_prompt("chat_system"))
            
            self.sessions[session_id] = ConversationSession(
                session_id=session_id,
                conversation_type=conversation_type,
                system_prompt=system_prompt
            )
            
        return self.sessions[session_id]
    
    async def _handle_start_conversation(self, intent: Intent, context: ConversationContext, session: ConversationSession) -> IntentResult:
        """Handle conversation start intent"""
        # Clear any existing history
        session.clear_history(keep_system=True)
        
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
                "conversation_type": session.conversation_type,
                "session_id": session.session_id
            }
        )
    
    async def _handle_end_conversation(self, intent: Intent, context: ConversationContext, session: ConversationSession) -> IntentResult:
        """Handle conversation end intent"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Get farewell templates from asset loader
        farewells = self._get_template_data("end_farewells", language)
        
        import random
        response = random.choice(farewells)
        
        # Clean up session
        if session.session_id in self.sessions:
            del self.sessions[session.session_id]
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={"conversation_ended": True}
        )
    
    async def _handle_clear_conversation(self, intent: Intent, context: ConversationContext, session: ConversationSession) -> IntentResult:
        """Handle conversation clear/reset intent"""
        session.clear_history(keep_system=True)
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Get clear response template from asset loader
        response = self._get_template("clear_response", language)
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={"conversation_cleared": True}
        )
    
    async def _handle_reference_query(self, intent: Intent, session: ConversationSession) -> IntentResult:
        """Handle reference/factual query intent"""
        if not self.llm_component:
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
            response = await self.llm_component.generate_response(
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
    
    async def _handle_continue_conversation(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle ongoing conversation intent - donation-compatible method signature"""
        
        # Check if this is a fallback scenario (when NLU failed to recognize intent)
        is_fallback = intent.entities.get("_recognition_provider") == "fallback"
        
        if is_fallback:
            # Handle fallback scenario - works even without LLM
            return await self._handle_fallback_without_llm(intent, context)
        
        # For normal conversation (not fallback), require LLM
        if not self.llm_component:
            return IntentResult(
                text="Извините, диалоговый режим недоступен.",
                should_speak=True,
                success=False
            )
        
        try:
            # Get or create conversation session using context session_id
            session = self._get_or_create_session(context.session_id, intent)
            
            # Add user message to session (LLM-specific conversation management)
            session.add_message("user", intent.raw_text)
            
            # Get conversation history from session (properly formatted for LLM)
            messages = session.get_messages()
            
            # Generate response using LLM component's default model
            response = await self.llm_component.generate_response(
                messages=messages,
                trace_context=self._trace_context
            )
            
            # Add assistant response to session
            session.add_message("assistant", response)
            
            return IntentResult(
                text=response,
                should_speak=True,
                metadata={
                    "conversation_type": session.conversation_type,
                    "message_count": len(session.messages),
                    "session_id": session.session_id
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
    async def _handle_fallback_without_llm(self, intent: Intent, context: ConversationContext) -> IntentResult:
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
        """Clean up conversation sessions"""
        # Clean up old sessions
        current_time = time.time()
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if current_time - session.last_activity > self.config["session_timeout"]
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            
        logger.info(f"Cleaned up {len(expired_sessions)} expired conversation sessions") 