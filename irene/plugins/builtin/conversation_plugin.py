"""
Conversation Plugin - Interactive LLM Chat

Provides conversational interactions using LLM providers from UniversalLLMPlugin.
Manages conversation state, multi-turn dialogs, and specialized chat modes.

Extracted from legacy plugin_boltalka_vsegpt.py and modernized for v13 architecture.
"""

import json
import time
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio
import logging

from ...core.interfaces.plugin import PluginInterface
from ...core.interfaces.command import CommandPlugin
from ...core.interfaces.webapi import WebAPIPlugin
from ...core.context import Context
from ...core.commands import CommandResult

from fastapi import APIRouter, HTTPException
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
        if keep_system and self.messages and self.messages[0]["role"] == "system":
            system_msg = self.messages[0]
            self.messages = [system_msg]
        else:
            self.messages = []
        self.last_activity = time.time()
    
    def save_to_file(self, base_dir: Path = Path("models")) -> str:
        """Save conversation to JSON file"""
        try:
            base_dir.mkdir(exist_ok=True)
            ts = time.time()
            filename_prefix = "conversation"
            if self.messages:
                # Use first user message or system message for filename
                first_content = ""
                for msg in self.messages:
                    if msg["role"] in ["user", "system"]:
                        first_content = msg["content"][:30]
                        break
                filename_prefix = re.sub('[^0-9a-zA-Z]+', '-', f"{first_content}_{ts}")
            
            filename = f"chat_model_{filename_prefix}.json"
            filepath = base_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as outfile:
                json.dump(self.messages, outfile, indent=4, ensure_ascii=False)
            
            return str(filepath)
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            return ""


class ConversationRequest(BaseModel):
    """Request model for conversation API"""
    message: str
    session_id: Optional[str] = None
    conversation_type: str = "chat"  # "chat" or "reference" 
    model_preference: str = ""
    system_prompt: str = ""


class ConversationResponse(BaseModel):
    """Response model for conversation API"""
    response: str
    session_id: str
    conversation_type: str
    message_count: int
    created_at: float


class ConversationPlugin(PluginInterface, CommandPlugin, WebAPIPlugin):
    """
    Conversation Plugin - Interactive LLM Chat
    
    Provides conversational interactions using LLM providers from UniversalLLMPlugin.
    Manages conversation state, multi-turn dialogs, and specialized chat modes.
    
    Voice Commands:
    - "поболтаем|поговорим" - Start casual conversation
    - "справка" - Start factual reference mode  
    - "новый диалог" - Start new conversation
    - "пока|отмена" - End conversation
    - "сохрани диалог" - Save current conversation
    """
    
    def __init__(self):
        super().__init__()
        self.sessions: Dict[str, ConversationSession] = {}
        self.active_context_session: Optional[str] = None
        self.llm_plugin = None
        
        # Default configuration
        self.config = {
            "chat_system_prompt": "Ты - Ирина, голосовой помощник, помогающий человеку. Давай ответы кратко и по существу.",
            "reference_system_prompt": "Ты помощник для получения точных фактов. Отвечай максимально кратко и точно на русском языке.",
            "reference_prompt_template": "Вопрос: {0}. Ответь на русском языке максимально кратко - только запрошенные данные.",
            "chat_model": "openai/gpt-4o-mini",
            "reference_model": "perplexity/latest-large-online",
            "session_timeout": 1800,  # 30 minutes
            "max_sessions": 50
        }
    
    @property
    def name(self) -> str:
        return "conversation"
    
    @property
    def version(self) -> str:
        return "2.0.0"
    
    @property
    def description(self) -> str:
        return "Interactive LLM conversation with state management"
    
    async def initialize(self, core) -> None:
        """Initialize the conversation plugin"""
        self.core = core
        
        # Get reference to UniversalLLMPlugin
        self.llm_plugin = core.plugin_manager.get_plugin("universal_llm")
        if not self.llm_plugin:
            logger.warning("UniversalLLMPlugin not found - conversation functionality limited")
        
        # Load configuration from core config if available
        try:
            plugin_config = getattr(core.config.plugins, 'conversation', {})
            self.config.update(plugin_config)
        except AttributeError:
            logger.info("Using default conversation configuration")
        
        logger.info("ConversationPlugin initialized")
    
    async def shutdown(self) -> None:
        """Cleanup on shutdown"""
        # Save active sessions
        for session in self.sessions.values():
            session.save_to_file()
        self.sessions.clear()
    
    # CommandPlugin interface
    def get_triggers(self) -> List[str]:
        """Get command triggers for conversation control"""
        return [
            "поболтаем", "поговорим", "давай поговорим",
            "справка", "справочный режим", 
            "новый диалог", "новая беседа", "начать заново",
            "пока", "отмена", "закончить", "стоп",
            "сохрани диалог", "сохрани беседу"
        ]
    
    async def can_handle(self, command: str, context: Context) -> bool:
        """Check if this command starts or continues a conversation"""
        triggers = self.get_triggers()
        command_lower = command.lower().strip()
        
        # Check for explicit triggers
        if any(trigger in command_lower for trigger in triggers):
            return True
        
        # Check if we're in active conversation context
        if self.active_context_session:
            return True
            
        return False
    
    async def handle_command(self, command: str, context: Context) -> CommandResult:
        """Handle conversation voice commands"""
        command_lower = command.lower().strip()
        
        try:
            # Start casual conversation
            if any(trigger in command_lower for trigger in ["поболтаем", "поговорим", "давай поговорим"]):
                return await self._start_conversation("chat", command, context)
            
            # Start reference mode
            elif "справка" in command_lower or "справочный режим" in command_lower:
                return await self._start_conversation("reference", command, context)
            
            # New dialog
            elif any(trigger in command_lower for trigger in ["новый диалог", "новая беседа", "начать заново"]):
                return await self._new_dialog(context)
            
            # End conversation
            elif any(trigger in command_lower for trigger in ["пока", "отмена", "закончить", "стоп"]):
                return await self._end_conversation(context)
            
            # Save dialog
            elif any(trigger in command_lower for trigger in ["сохрани диалог", "сохрани беседу"]):
                return await self._save_conversation(context)
            
            # Continue active conversation
            elif self.active_context_session:
                return await self._continue_conversation(command, context)
            
            else:
                return CommandResult(
                    success=False, 
                    error="Неизвестная команда беседы"
                )
                
        except Exception as e:
            logger.error(f"Error in conversation handling: {e}")
            return CommandResult(
                success=False,
                error=f"Ошибка в беседе: {str(e)}"
            )
    
    async def _start_conversation(self, conversation_type: str, initial_message: str, context: Context) -> CommandResult:
        """Start a new conversation session"""
        # Check if LLM plugin is available
        if not self.llm_plugin:
            return CommandResult(
                success=False,
                error="LLM plugin недоступен для беседы"
            )
        
        # Create new session
        session_id = f"voice_{int(time.time())}"
        
        # Choose system prompt and model based on conversation type
        if conversation_type == "reference":
            system_prompt = self.config["reference_system_prompt"]
            model = self.config["reference_model"]
        else:
            system_prompt = self.config["chat_system_prompt"]
            model = self.config["chat_model"]
        
        session = ConversationSession(
            session_id=session_id,
            conversation_type=conversation_type,
            system_prompt=system_prompt,
            model_preference=model
        )
        
        self.sessions[session_id] = session
        self.active_context_session = session_id
        
        # Clean up old sessions
        await self._cleanup_old_sessions()
        
        # Extract actual message from command
        message = self._extract_message_from_command(initial_message, conversation_type)
        
        if message:
            # Start with a message
            return await self._continue_conversation(message, context)
        else:
            # Just start the conversation
            if conversation_type == "reference":
                response = "Задайте вопрос для справки"
            else:
                response = "Да, давай поболтаем!"
            
            # Set context for continuation
            await self._set_conversation_context(context)
            
            return CommandResult(
                success=True,
                response=response,
                metadata={"session_id": session_id, "conversation_type": conversation_type}
            )
    
    async def _continue_conversation(self, message: str, context: Context) -> CommandResult:
        """Continue an active conversation"""
        if not self.active_context_session or self.active_context_session not in self.sessions:
            return CommandResult(
                success=False,
                error="Нет активной беседы"
            )
        
        session = self.sessions[self.active_context_session]
        
        # Prepare message for reference mode
        if session.conversation_type == "reference":
            message = self.config["reference_prompt_template"].format(message)
        
        # Add user message to session
        session.add_message("user", message)
        
        try:
            # Get LLM response
            llm_response = await self.llm_plugin.chat_completion(
                messages=session.get_messages(),
                provider=self._get_provider_for_model(session.model_preference),
                model=session.model_preference
            )
            
            # Add assistant response to session
            session.add_message("assistant", llm_response)
            
            # Continue context for multi-turn conversation
            await self._set_conversation_context(context)
            
            return CommandResult(
                success=True,
                response=llm_response,
                metadata={
                    "session_id": session.session_id,
                    "conversation_type": session.conversation_type,
                    "message_count": len(session.messages)
                }
            )
            
        except Exception as e:
            logger.error(f"LLM conversation error: {e}")
            return CommandResult(
                success=False,
                error="Проблемы с доступом к LLM. Посмотрите логи"
            )
    
    async def _new_dialog(self, context: Context) -> CommandResult:
        """Start a new dialog, clearing current session"""
        if self.active_context_session and self.active_context_session in self.sessions:
            session = self.sessions[self.active_context_session]
            session.clear_history(keep_system=True)
            
            await self._set_conversation_context(context)
            
            return CommandResult(
                success=True,
                response="Начинаю новый диалог",
                metadata={"session_id": session.session_id}
            )
        else:
            return CommandResult(
                success=False,
                error="Нет активной беседы для сброса"
            )
    
    async def _end_conversation(self, context: Context) -> CommandResult:
        """End the current conversation"""
        if self.active_context_session:
            # Save conversation before ending
            if self.active_context_session in self.sessions:
                session = self.sessions[self.active_context_session]
                filepath = session.save_to_file()
                if filepath:
                    logger.info(f"Conversation saved to {filepath}")
            
            self.active_context_session = None
            
            return CommandResult(
                success=True,
                response="До свидания!"
            )
        else:
            return CommandResult(
                success=True,
                response="Пока!"
            )
    
    async def _save_conversation(self, context: Context) -> CommandResult:
        """Save current conversation to file"""
        if not self.active_context_session or self.active_context_session not in self.sessions:
            return CommandResult(
                success=False,
                error="Нет активной беседы для сохранения"
            )
        
        session = self.sessions[self.active_context_session]
        filepath = session.save_to_file()
        
        if filepath:
            await self._set_conversation_context(context)
            return CommandResult(
                success=True,
                response=f"Диалог сохранён"
            )
        else:
            return CommandResult(
                success=False,
                error="Не удалось сохранить диалог"
            )
    
    def _extract_message_from_command(self, command: str, conversation_type: str) -> str:
        """Extract actual message from voice command"""
        command_lower = command.lower().strip()
        
        # Remove trigger words to get the actual message
        triggers = {
            "chat": ["поболтаем", "поговорим", "давай поговорим"],
            "reference": ["справка", "справочный режим"]
        }
        
        message = command
        for trigger in triggers.get(conversation_type, triggers["chat"]):
            if trigger in command_lower:
                # Remove trigger and extract remaining text
                parts = command_lower.split(trigger, 1)
                if len(parts) > 1 and parts[1].strip():
                    message = parts[1].strip()
                    # Capitalize first letter
                    if message:
                        message = message[0].upper() + message[1:]
                    return message
                break
        
        return ""
    
    def _get_provider_for_model(self, model: str) -> str:
        """Map model name to provider name"""
        if model.startswith("openai/") or model.startswith("gpt-"):
            return "openai"
        elif model.startswith("perplexity/"):
            return "vsegpt"  # VseGPT provides access to Perplexity
        elif model.startswith("claude-") or model.startswith("anthropic/"):
            return "anthropic"
        else:
            return "openai"  # Default fallback
    
    async def _set_conversation_context(self, context: Context) -> None:
        """Set context for conversation continuation"""
        if hasattr(context, 'set_continuation'):
            await context.set_continuation(
                handler=self.handle_command,
                timeout=self.config["session_timeout"]
            )
    
    async def _cleanup_old_sessions(self) -> None:
        """Remove old inactive sessions"""
        current_time = time.time()
        timeout = self.config["session_timeout"]
        
        expired_sessions = []
        for session_id, session in self.sessions.items():
            if current_time - session.last_activity > timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            if session_id == self.active_context_session:
                self.active_context_session = None
            del self.sessions[session_id]
        
        # Limit total sessions
        if len(self.sessions) > self.config["max_sessions"]:
            # Remove oldest sessions
            sorted_sessions = sorted(
                self.sessions.items(),
                key=lambda x: x[1].last_activity
            )
            excess_count = len(self.sessions) - self.config["max_sessions"]
            for session_id, _ in sorted_sessions[:excess_count]:
                if session_id == self.active_context_session:
                    self.active_context_session = None
                del self.sessions[session_id]
    
    # WebAPIPlugin interface
    def get_router(self) -> APIRouter:
        """Get FastAPI router for conversation endpoints"""
        router = APIRouter()
        
        @router.post("/start")
        async def start_conversation(request: ConversationRequest):
            """Start a new conversation via API"""
            if not self.llm_plugin:
                raise HTTPException(500, "LLM plugin not available")
            
            # Create new session
            session_id = request.session_id or f"api_{int(time.time())}"
            
            # Choose system prompt and model
            if request.conversation_type == "reference":
                system_prompt = request.system_prompt or self.config["reference_system_prompt"]
                model = request.model_preference or self.config["reference_model"]
            else:
                system_prompt = request.system_prompt or self.config["chat_system_prompt"]
                model = request.model_preference or self.config["chat_model"]
            
            session = ConversationSession(
                session_id=session_id,
                conversation_type=request.conversation_type,
                system_prompt=system_prompt,
                model_preference=model
            )
            
            self.sessions[session_id] = session
            
            # Process initial message if provided
            if request.message.strip():
                message = request.message
                if request.conversation_type == "reference":
                    message = self.config["reference_prompt_template"].format(message)
                
                session.add_message("user", message)
                
                try:
                    llm_response = await self.llm_plugin.chat_completion(
                        messages=session.get_messages(),
                        provider=self._get_provider_for_model(model),
                        model=model
                    )
                    session.add_message("assistant", llm_response)
                    
                    return ConversationResponse(
                        response=llm_response,
                        session_id=session_id,
                        conversation_type=request.conversation_type,
                        message_count=len(session.messages),
                        created_at=session.created_at
                    )
                except Exception as e:
                    raise HTTPException(500, f"LLM error: {str(e)}")
            
            # No initial message
            response_text = "Готов к беседе" if request.conversation_type == "chat" else "Готов отвечать на вопросы"
            return ConversationResponse(
                response=response_text,
                session_id=session_id,
                conversation_type=request.conversation_type,
                message_count=len(session.messages),
                created_at=session.created_at
            )
        
        @router.post("/{session_id}/message")
        async def send_message(session_id: str, request: ConversationRequest):
            """Send a message to existing conversation"""
            if session_id not in self.sessions:
                raise HTTPException(404, "Session not found")
            
            if not self.llm_plugin:
                raise HTTPException(500, "LLM plugin not available")
            
            session = self.sessions[session_id]
            
            # Prepare message
            message = request.message
            if session.conversation_type == "reference":
                message = self.config["reference_prompt_template"].format(message)
            
            session.add_message("user", message)
            
            try:
                llm_response = await self.llm_plugin.chat_completion(
                    messages=session.get_messages(),
                    provider=self._get_provider_for_model(session.model_preference),
                    model=session.model_preference
                )
                session.add_message("assistant", llm_response)
                
                return ConversationResponse(
                    response=llm_response,
                    session_id=session_id,
                    conversation_type=session.conversation_type,
                    message_count=len(session.messages),
                    created_at=session.created_at
                )
            except Exception as e:
                raise HTTPException(500, f"LLM error: {str(e)}")
        
        @router.get("/{session_id}/history")
        async def get_conversation_history(session_id: str):
            """Get conversation history"""
            if session_id not in self.sessions:
                raise HTTPException(404, "Session not found")
            
            session = self.sessions[session_id]
            return {
                "session_id": session_id,
                "conversation_type": session.conversation_type,
                "messages": session.get_messages(),
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "message_count": len(session.messages)
            }
        
        @router.delete("/{session_id}")
        async def end_conversation(session_id: str):
            """End and save conversation"""
            if session_id not in self.sessions:
                raise HTTPException(404, "Session not found")
            
            session = self.sessions[session_id]
            filepath = session.save_to_file()
            
            if session_id == self.active_context_session:
                self.active_context_session = None
            
            del self.sessions[session_id]
            
            return {
                "message": "Conversation ended",
                "saved_to": filepath if filepath else None
            }
        
        @router.get("/sessions")
        async def list_sessions():
            """List active conversation sessions"""
            sessions_info = []
            for session_id, session in self.sessions.items():
                sessions_info.append({
                    "session_id": session_id,
                    "conversation_type": session.conversation_type,
                    "message_count": len(session.messages),
                    "created_at": session.created_at,
                    "last_activity": session.last_activity,
                    "is_active": session_id == self.active_context_session
                })
            
            return {
                "sessions": sessions_info,
                "active_session": self.active_context_session,
                "total_sessions": len(self.sessions)
            }
        
        return router 