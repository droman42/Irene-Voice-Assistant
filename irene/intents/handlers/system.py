"""
System Intent Handler - Essential system commands for Intent System

Provides system control and information commands.
Adapted from core_commands.py for the new intent architecture.
"""

import logging
import time
from datetime import datetime
from typing import List, Optional, Dict, Any

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class SystemIntentHandler(IntentHandler):
    """
    Handles system control and status intents.
    
    Features:
    - System shutdown/restart
    - Status queries
    - Volume control
    - Time/date queries
    """
    
    def __init__(self):
        super().__init__()
        self.start_time = time.time()

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """System handler needs no external dependencies - pure Python logic"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """System handler has no system dependencies - pure Python logic"""
        return {
            "ubuntu": [],
            "alpine": [],
            "centos": [],
            "macos": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """System handler supports all platforms"""
        return ["linux", "windows", "macos"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process system intents"""
        # Handle system domain intents
        if intent.domain == "system":
            return True
        
        # Handle specific system intents
        if intent.name in ["system.status", "system.help", "system.version", "system.info"]:
            return True
        
        # Handle system-related actions
        if intent.action in ["status", "help", "version", "info", "statistics"]:
            return True
        
        return False
    
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Execute system intent"""
        try:
            # Determine language preference
            language = self._detect_language(intent.raw_text, context)
            
            if intent.action == "help" or intent.name == "system.help":
                return await self._handle_help_request(intent, context, language)
            elif intent.action == "status" or intent.name == "system.status":
                return await self._handle_status_request(intent, context, language)
            elif intent.action == "version" or intent.name == "system.version":
                return await self._handle_version_request(intent, context, language)
            elif intent.action == "info" or intent.name == "system.info":
                return await self._handle_info_request(intent, context, language)
            else:
                # Default: provide general system information
                return await self._handle_general_info(intent, context, language)
                
        except Exception as e:
            logger.error(f"System intent execution failed: {e}")
            return IntentResult(
                text="Извините, произошла ошибка при выполнении системной команды." if self._detect_language(intent.raw_text, context) == "ru" else "Sorry, there was an error executing the system command.",
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    async def is_available(self) -> bool:
        """System commands are always available"""
        return True
    
    def _detect_language(self, text: str, context: ConversationContext) -> str:
        """Detect language from text or context"""
        text_lower = text.lower()
        
        english_indicators = ["help", "status", "version", "info", "system"]
        russian_indicators = ["помощь", "справка", "статус", "версия", "система", "информация"]
        
        english_count = sum(1 for word in english_indicators if word in text_lower)
        russian_count = sum(1 for word in russian_indicators if word in text_lower)
        
        # Check context metadata for language preference
        if hasattr(context, 'metadata') and 'language' in context.metadata:
            return context.metadata['language']
        
        # Default to Russian if unclear
        return "en" if english_count > russian_count else "ru"
    
    async def _handle_help_request(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle help/assistance request"""
        if language == "en":
            help_text = """I'm Irene, your voice assistant. Here's what I can help you with:

🗣️ **Conversation**: Just talk to me naturally
⏰ **Timers**: "Set timer for 5 minutes"
📅 **Date & Time**: "What time is it?" or "What's today's date?"
👋 **Greetings**: Say hello or goodbye
🔧 **System**: Ask for status, version, or help

You can speak to me in Russian or English. How can I help you today?"""
        else:
            help_text = """Я Ирина, ваш голосовой помощник. Вот что я умею:

🗣️ **Разговор**: Просто говорите со мной естественно
⏰ **Таймеры**: "Поставь таймер на 5 минут"
📅 **Дата и время**: "Сколько времени?" или "Какая сегодня дата?"
👋 **Приветствия**: Поздоровайтесь или попрощайтесь
🔧 **Система**: Спросите статус, версию или помощь

Вы можете говорить со мной на русском или английском языке. Чем могу помочь?"""
        
        return IntentResult(
            text=help_text,
            should_speak=True,
            metadata={
                "help_type": "general",
                "language": language,
                "capabilities_listed": True
            }
        )
    
    async def _handle_status_request(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle system status request"""
        uptime_seconds = time.time() - self.start_time
        uptime_hours = int(uptime_seconds // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)
        
        if language == "en":
            if uptime_hours > 0:
                uptime_str = f"{uptime_hours} hours and {uptime_minutes} minutes"
            else:
                uptime_str = f"{uptime_minutes} minutes"
            
            status_text = f"""System Status: ✅ Running
Uptime: {uptime_str}
Version: Irene v13.0.0
Mode: Intent-based processing
Language: Bilingual (Russian/English)

All systems operational!"""
        else:
            if uptime_hours > 0:
                uptime_str = f"{uptime_hours} часов и {uptime_minutes} минут"
            else:
                uptime_str = f"{uptime_minutes} минут"
            
            status_text = f"""Статус системы: ✅ Работает
Время работы: {uptime_str}
Версия: Ирина v13.0.0
Режим: Обработка интентов
Язык: Двуязычная (русский/английский)

Все системы работают нормально!"""
        
        return IntentResult(
            text=status_text,
            should_speak=True,
            metadata={
                "status": "running",
                "uptime_seconds": uptime_seconds,
                "version": "13.0.0",
                "language": language
            }
        )
    
    async def _handle_version_request(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle version information request"""
        if language == "en":
            version_text = """Irene Voice Assistant v13.0.0
🤖 Modern async voice assistant
🧠 Intent-based natural language processing
🗣️ Bilingual support (Russian/English)
🔧 Component-based architecture

Built with modern Python async/await patterns."""
        else:
            version_text = """Голосовой помощник Ирина v13.0.0
🤖 Современный асинхронный голосовой помощник
🧠 Обработка естественного языка на основе интентов
🗣️ Двуязычная поддержка (русский/английский)
🔧 Компонентная архитектура

Создано с использованием современных асинхронных паттернов Python."""
        
        return IntentResult(
            text=version_text,
            should_speak=True,
            metadata={
                "version": "13.0.0",
                "architecture": "intent-based",
                "language": language
            }
        )
    
    async def _handle_info_request(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle general information request"""
        session_stats = self._get_session_stats(context)
        
        if language == "en":
            info_text = f"""System Information:
💻 Assistant: Irene v13.0.0
🕐 Session started: {datetime.fromtimestamp(context.created_at).strftime('%H:%M')}
💬 Messages exchanged: {len(context.history)}
🎯 Current session: {context.session_id}
🧠 Processing mode: Intent-based NLU

Ready to assist you!"""
        else:
            info_text = f"""Информация о системе:
💻 Помощник: Ирина v13.0.0
🕐 Сессия начата: {datetime.fromtimestamp(context.created_at).strftime('%H:%M')}
💬 Сообщений обменено: {len(context.history)}
🎯 Текущая сессия: {context.session_id}
🧠 Режим обработки: NLU на основе интентов

Готова помочь вам!"""
        
        return IntentResult(
            text=info_text,
            should_speak=True,
            metadata={
                "session_info": session_stats,
                "language": language
            }
        )
    
    async def _handle_general_info(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle general system information request"""
        if language == "en":
            info_text = """I'm Irene, your intelligent voice assistant running on v13.0.0.
I use modern intent-based processing to understand and respond to your requests.
Ask me for help to learn about my capabilities!"""
        else:
            info_text = """Я Ирина, ваш интеллектуальный голосовой помощник версии 13.0.0.
Я использую современную обработку на основе интентов для понимания ваших запросов.
Спросите у меня помощь, чтобы узнать о моих возможностях!"""
        
        return IntentResult(
            text=info_text,
            should_speak=True,
            metadata={
                "type": "general_info",
                "language": language
            }
        )
    
    def _get_session_stats(self, context: ConversationContext) -> Dict[str, Any]:
        """Get session statistics"""
        return {
            "session_id": context.session_id,
            "created_at": context.created_at,
            "last_updated": context.last_updated,
            "message_count": len(context.history),
            "session_duration": time.time() - context.created_at
        }
    
    def get_system_patterns(self) -> List[str]:
        """Get patterns that indicate system intent"""
        return [
            # Help patterns
            r"помощь|справка|что умеешь|как работать",
            r"help|assistance|what can you do|how to use",
            
            # Status patterns
            r"статус|состояние|как дела|работаешь",
            r"status|state|how are you|running",
            
            # Version patterns
            r"версия|какая версия|номер версии",
            r"version|what version|build number",
            
            # Info patterns
            r"информация|данные|о себе|кто ты",
            r"information|info|about yourself|who are you",
        ] 