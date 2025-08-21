"""
Conversation Intent Handler - Interactive LLM Chat for Intent System

Provides conversational interactions using LLM components.
Adapted from conversation_plugin.py for the new intent architecture.
"""

import logging
import time
from typing import Dict, List, Optional, Any

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

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
    
    def __init__(self):
        super().__init__()
        self.conversation_context: List[Dict[str, str]] = []
        self.max_context_length = 10  # Keep last 10 exchanges
        self.sessions: Dict[str, ConversationSession] = {}
        self.llm_component = None
        
        # TODO #15: Move configuration to TOML and prompts to external files (not JSON donations)
        # - LLM prompts should be in prompts/chat_system.txt and prompts/reference_system.txt  
        # - Configuration values should be in main TOML config
        # Configuration for conversation modes
        self.config = {
            "chat_system_prompt": "Ты - Ирина, голосовой помощник, помогающий человеку. Давай ответы кратко и по существу.",
            "reference_system_prompt": "Ты помощник для получения точных фактов. Отвечай максимально кратко и точно на русском языке.",
            "reference_prompt_template": "Вопрос: {0}. Ответь на русском языке максимально кратко - только запрошенные данные.",
            "chat_model": "openai/gpt-4o-mini",
            "reference_model": "perplexity/latest-large-online", 
            "session_timeout": 1800,  # 30 minutes
            "max_sessions": 50,
            "default_conversation_confidence": 0.6  # Lower confidence for fallback
        }
    
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
        """Execute conversation intent using LLM"""
        try:
            # Get or create conversation session
            session = self._get_or_create_session(context.session_id, intent)
            
            # Handle specific conversation actions
            if intent.action == "start":
                return await self._handle_start_conversation(intent, session)
            elif intent.action == "end":
                return await self._handle_end_conversation(intent, session)
            elif intent.action == "clear":
                return await self._handle_clear_conversation(intent, session)
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
            system_prompt = (self.config["reference_system_prompt"] if conversation_type == "reference" 
                           else self.config["chat_system_prompt"])
            
            self.sessions[session_id] = ConversationSession(
                session_id=session_id,
                conversation_type=conversation_type,
                system_prompt=system_prompt
            )
            
        return self.sessions[session_id]
    
    async def _handle_start_conversation(self, intent: Intent, session: ConversationSession) -> IntentResult:
        """Handle conversation start intent"""
        # Clear any existing history
        session.clear_history(keep_system=True)
        
        greetings = [
            "Давайте поговорим! О чём хотите поболтать?",
            "Отлично! Я готова к беседе. О чём поговорим?",
            "Хорошо, начинаем диалог. Что вас интересует?",
            "Замечательно! Я вас слушаю."
        ]
        
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
    
    async def _handle_end_conversation(self, intent: Intent, session: ConversationSession) -> IntentResult:
        """Handle conversation end intent"""
        farewells = [
            "До свидания! Было приятно поговорить.",
            "Пока! Обращайтесь ещё.",
            "До встречи! Хорошего дня.",
            "Всего доброго!"
        ]
        
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
    
    async def _handle_clear_conversation(self, intent: Intent, session: ConversationSession) -> IntentResult:
        """Handle conversation clear/reset intent"""
        session.clear_history(keep_system=True)
        
        return IntentResult(
            text="Хорошо, начинаем диалог заново. О чём поговорим?",
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
        formatted_prompt = self.config["reference_prompt_template"].format(query)
        
        try:
            # Use reference model for factual queries
            response = await self.llm_component.generate_response(
                messages=[{"role": "user", "content": formatted_prompt}],
                model=self.config["reference_model"]
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
            
            # Generate response using LLM
            response = await self.llm_component.generate_response(
                messages=messages,
                model=self.config["chat_model"]
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