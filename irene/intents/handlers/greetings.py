"""
Greetings Intent Handler - Greeting and farewell responses

Provides random greeting responses and welcome messages.
Adapted from greetings_plugin.py for the new intent architecture.
"""

import random
import logging
from typing import List, Optional

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class GreetingsIntentHandler(IntentHandler):
    """
    Handles greeting and farewell intents with bilingual support.
    
    Features:
    - Random greeting selection
    - Multiple greeting variations
    - Friendly welcome messages
    - Russian language support
    - Time-based greetings
    """
    
    def __init__(self):
        super().__init__()
        
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
    
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process greeting intents"""
        # Handle greeting domain intents
        if intent.domain == "greetings":
            return True
        
        # Handle specific greeting intents
        if intent.name in ["greeting.hello", "greeting.goodbye", "greeting.welcome"]:
            return True
        
        # Handle greeting-related actions
        if intent.action in ["hello", "goodbye", "welcome", "greet"]:
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
    
    def get_greeting_patterns(self) -> List[str]:
        """Get patterns that indicate greeting intent"""
        return [
            # Russian greetings
            r"привет|здравствуй|добро пожаловать",
            r"доброе утро|добрый день|добрый вечер|доброй ночи",
            r"приветствую|салют|хай",
            
            # Russian farewells
            r"пока|до свидания|прощай",
            r"до встречи|всего доброго|удачи",
            r"до скорого|пока-пока|бывай",
            
            # English greetings
            r"hello|hi|hey|greetings",
            r"good morning|good afternoon|good evening|good night",
            r"welcome|nice to meet",
            
            # English farewells
            r"goodbye|bye|farewell|see you",
            r"take care|good luck|until next time",
            r"bye-bye|catch you later|so long",
        ] 