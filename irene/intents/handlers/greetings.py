"""
Greetings Intent Handler - Greeting and farewell responses

Provides random greeting responses and welcome messages.
Adapted from greetings_plugin.py for the new intent architecture.
"""

import random
import logging
from typing import List, Optional, Dict

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class GreetingsIntentHandler(IntentHandler):
    """
    Handles greeting and farewell intents.
    
    Features:
    - Welcome messages
    - Farewell responses 
    - Random greeting variations
    - Context-aware responses
    """
    
    def __init__(self):
        super().__init__()
        
        # TODO #15: Move response arrays to localization system (not JSON donations)
        # These arrays are for OUTPUT GENERATION, not NLU input recognition
        # They should be extracted to localization/greetings/ru.yaml and en.yaml
        
        # Russian greetings
        self.greetings_ru = [
            "Привет! Как дела?",
            "Здравствуйте! Чем могу помочь?",
            "Добро пожаловать! Я готова к работе.",
            "Приветствую! Что будем делать?",
            "Привет! Рада вас видеть.",
            "Здравствуйте! Готова к выполнению команд.",
            "Добрый день! Чем займёмся?",
            "Привет! Я здесь и готова помочь.",
            "Здравствуйте! Давайте работать вместе.",
            "Приветствую! Какие у вас планы?"
        ]
        
        # English greetings
        self.greetings_en = [
            "Hello! How are you today?",
            "Hi there! What can I do for you?",
            "Welcome! I'm ready to help.",
            "Greetings! What shall we do?",
            "Hello! Nice to see you.",
            "Hi! I'm here and ready to assist.",
            "Good day! How can I help?",
            "Welcome back! What's on the agenda?",
            "Hello! Let's get started.",
            "Hi! Ready for some assistance?"
        ]
        
        # Farewell messages
        self.farewells_ru = [
            "До свидания! Хорошего дня!",
            "Пока! Обращайтесь ещё.",
            "До встречи! Было приятно помочь.",
            "Всего доброго! Увидимся позже.",
            "До свидания! Удачи во всех делах.",
            "Пока-пока! Хорошего настроения.",
            "До новых встреч! Берегите себя.",
            "Всего хорошего! До скорого.",
            "Прощайте! Отличного дня.",
            "До свидания! Рада была помочь."
        ]
        
        self.farewells_en = [
            "Goodbye! Have a great day!",
            "See you later! Take care.",
            "Farewell! It was nice helping you.",
            "Bye! Hope to see you again soon.",
            "Goodbye! Wishing you all the best.",
            "Take care! Have a wonderful time.",
            "See you next time! Stay safe.",
            "Bye-bye! Until we meet again.",
            "Farewell! Enjoy your day.",
            "Goodbye! It was a pleasure helping."
        ]
        
        # Welcome messages for first interaction
        self.welcome_messages_ru = [
            "Добро пожаловать! Я Ирина, ваш голосовой помощник. Чем могу помочь?",
            "Здравствуйте! Меня зовут Ирина. Готова выполнять ваши команды.",
            "Приветствую! Я ваш персональный помощник Ирина. Что будем делать?",
            "Добро пожаловать в систему! Я Ирина, готова помочь вам в работе.",
            "Здравствуйте! Ирина к вашим услугам. Какие задачи решаем?"
        ]
        
        self.welcome_messages_en = [
            "Welcome! I'm Irene, your voice assistant. How can I help you?",
            "Hello! My name is Irene. I'm ready to assist you.",
            "Greetings! I'm your personal assistant Irene. What shall we do?",
            "Welcome to the system! I'm Irene, ready to help with your tasks.",
            "Hello! Irene at your service. What can I do for you today?"
        ]
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Greetings handler needs no external dependencies - pure Python logic"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Greetings handler has no system dependencies - pure Python logic"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Greetings handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process greeting intents"""
        if not self.has_donation():
            raise RuntimeError(f"GreetingsIntentHandler: Missing JSON donation file - greetings.json is required")
        
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
        """Execute greeting intent"""
        try:
            # Determine language preference (default to Russian)
            language = self._detect_language(intent.raw_text, context)
            
            if intent.action == "goodbye" or intent.name == "greeting.goodbye":
                return await self._handle_farewell(intent, context, language)
            elif intent.action == "welcome" or intent.name == "greeting.welcome":
                return await self._handle_welcome(intent, context, language)
            else:
                # Default: handle hello greeting
                return await self._handle_greeting(intent, context, language)
                
        except Exception as e:
            logger.error(f"Greeting intent execution failed: {e}")
            return IntentResult(
                text="Привет! Как дела?",  # Fallback greeting
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    async def is_available(self) -> bool:
        """Greetings are always available"""
        return True
    
    def _detect_language(self, text: str, context: ConversationContext) -> str:
        """Detect language from text or context"""
        # Simple language detection based on common words
        text_lower = text.lower()
        
        english_indicators = ["hello", "hi", "good", "morning", "evening", "bye", "goodbye"]
        russian_indicators = ["привет", "здравствуй", "добро", "пока", "до свидания", "утро", "день", "вечер"]
        
        english_count = sum(1 for word in english_indicators if word in text_lower)
        russian_count = sum(1 for word in russian_indicators if word in text_lower)
        
        # Check context metadata for language preference
        if hasattr(context, 'metadata') and 'language' in context.metadata:
            return context.metadata['language']
        
        # Default to Russian if unclear
        return "en" if english_count > russian_count else "ru"
    
    async def _handle_greeting(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle hello greeting intent"""
        if language == "en":
            greeting = random.choice(self.greetings_en)
        else:
            greeting = random.choice(self.greetings_ru)
        
        # Add time-based greeting if possible
        time_greeting = self._get_time_based_greeting(language)
        if time_greeting:
            greeting = f"{time_greeting} {greeting}"
        
        return IntentResult(
            text=greeting,
            should_speak=True,
            metadata={
                "greeting_type": "hello",
                "language": language,
                "random_selection": True
            }
        )
    
    async def _handle_farewell(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle goodbye farewell intent"""
        if language == "en":
            farewell = random.choice(self.farewells_en)
        else:
            farewell = random.choice(self.farewells_ru)
        
        return IntentResult(
            text=farewell,
            should_speak=True,
            metadata={
                "greeting_type": "farewell",
                "language": language,
                "conversation_ending": True
            }
        )
    
    async def _handle_welcome(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle welcome message intent"""
        if language == "en":
            welcome = random.choice(self.welcome_messages_en)
        else:
            welcome = random.choice(self.welcome_messages_ru)
        
        return IntentResult(
            text=welcome,
            should_speak=True,
            metadata={
                "greeting_type": "welcome",
                "language": language,
                "first_interaction": True
            }
        )
    
    def _get_time_based_greeting(self, language: str) -> Optional[str]:
        """Get time-based greeting prefix"""
        try:
            import datetime
            current_hour = datetime.datetime.now().hour
            
            if language == "en":
                if 5 <= current_hour < 12:
                    return "Good morning!"
                elif 12 <= current_hour < 18:
                    return "Good afternoon!"
                elif 18 <= current_hour < 22:
                    return "Good evening!"
                else:
                    return "Good night!"
            else:  # Russian
                if 5 <= current_hour < 12:
                    return "Доброе утро!"
                elif 12 <= current_hour < 18:
                    return "Добрый день!"
                elif 18 <= current_hour < 22:
                    return "Добрый вечер!"
                else:
                    return "Доброй ночи!"
                    
        except Exception:
            return None
    
 