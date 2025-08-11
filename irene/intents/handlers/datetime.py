"""
DateTime Intent Handler - Date and time information for Intent System

Provides current date and time with natural language formatting.
Adapted from datetime_plugin.py for the new intent architecture.
"""

import logging
from datetime import datetime
from typing import List, Optional

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class DateTimeIntentHandler(IntentHandler):
    """
    Handles date and time intents with natural language formatting.
    
    Features:
    - Current date with weekday
    - Current time with natural language
    - Configurable time format options
    - Russian language support
    """
    
    def __init__(self):
        super().__init__()
        
        # TODO #15: Move response formatting arrays to localization system
        # These arrays are for OUTPUT FORMATTING, not NLU input recognition
        # They should be extracted to localization/datetime/ru.yaml and en.yaml
        
        # Russian weekdays
        self.weekdays_ru = [
            "понедельник", "вторник", "среда", "четверг", 
            "пятница", "суббота", "воскресенье"
        ]
        
        # Russian months in genitive case (for date)
        self.months_ru = [
            "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря"
        ]
        
        # Russian day names (ordinal numbers)
        self.days_ru = [
            "первое", "второе", "третье", "четвёртое", "пятое", "шестое", 
            "седьмое", "восьмое", "девятое", "десятое", "одиннадцатое", 
            "двенадцатое", "тринадцатое", "четырнадцатое", "пятнадцатое", 
            "шестнадцатое", "семнадцатое", "восемнадцатое", "девятнадцатое", 
            "двадцатое", "двадцать первое", "двадцать второе", "двадцать третье",
            "двадцать четвёртое", "двадцать пятое", "двадцать шестое",
            "двадцать седьмое", "двадцать восьмое", "двадцать девятое",
            "тридцатое", "тридцать первое"
        ]
        
        # Russian times (hours)
        self.hours_ru = [
            "двенадцать", "час", "два", "три", "четыре", "пять", "шесть",
            "семь", "восемь", "девять", "десять", "одиннадцать"
        ]
        
        # English weekdays
        self.weekdays_en = [
            "Monday", "Tuesday", "Wednesday", "Thursday", 
            "Friday", "Saturday", "Sunday"
        ]
        
        # English months
        self.months_en = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
    
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process datetime intents"""
        if not self.has_donation():
            raise RuntimeError(f"DateTimeIntentHandler: Missing JSON donation file - datetime.json is required")
        
        # Use JSON donation patterns exclusively
        donation = self.get_donation()
        
        # Check domain patterns (fallback)
        if intent.domain == "datetime":
            return True
        
        # Check intent name patterns
        if hasattr(donation, 'intent_name_patterns') and intent.name in donation.intent_name_patterns:
            return True
        
        # Check action patterns
        if hasattr(donation, 'action_patterns') and intent.action in donation.action_patterns:
            return True
        
        return False
    
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Execute datetime intent"""
        try:
            # Determine language preference
            language = self._detect_language(intent.raw_text, context)
            
            if intent.action == "current_date" or intent.name == "datetime.current_date":
                return await self._handle_date_request(intent, context, language)
            elif intent.action == "current_time" or intent.name == "datetime.current_time":
                return await self._handle_time_request(intent, context, language)
            else:
                # Default: provide both date and time
                return await self._handle_datetime_request(intent, context, language)
                
        except Exception as e:
            logger.error(f"DateTime intent execution failed: {e}")
            return IntentResult(
                text="Извините, произошла ошибка при получении времени.",
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    async def is_available(self) -> bool:
        """DateTime functionality is always available"""
        return True
    
    def _detect_language(self, text: str, context: ConversationContext) -> str:
        """Detect language from text or context"""
        text_lower = text.lower()
        
        # TODO: These language detection arrays are now migrated to datetime.json language_detection
        english_indicators = ["time", "date", "what time", "what date", "current"]
        russian_indicators = ["время", "дата", "который", "какая", "сколько", "число"]
        
        english_count = sum(1 for word in english_indicators if word in text_lower)
        russian_count = sum(1 for word in russian_indicators if word in text_lower)
        
        # Check context metadata for language preference
        if hasattr(context, 'metadata') and 'language' in context.metadata:
            return context.metadata['language']
        
        # Default to Russian if unclear
        return "en" if english_count > russian_count else "ru"
    
    async def _handle_date_request(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle current date request"""
        now = datetime.now()
        
        if language == "en":
            weekday = self.weekdays_en[now.weekday()]
            month = self.months_en[now.month - 1]
            date_str = f"Today is {weekday}, {month} {now.day}, {now.year}"
        else:
            weekday = self.weekdays_ru[now.weekday()]
            month = self.months_ru[now.month - 1]
            day_ordinal = self.days_ru[now.day - 1] if now.day <= len(self.days_ru) else str(now.day)
            date_str = f"Сегодня {weekday}, {day_ordinal} {month} {now.year} года"
        
        return IntentResult(
            text=date_str,
            should_speak=True,
            metadata={
                "date": now.strftime("%Y-%m-%d"),
                "weekday": now.weekday(),
                "language": language
            }
        )
    
    async def _handle_time_request(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle current time request"""
        now = datetime.now()
        
        if language == "en":
            time_str = f"It's {now.strftime('%I:%M %p')}"
        else:
            hour = now.hour
            minute = now.minute
            
            # Convert to 12-hour format for natural language
            if hour == 0:
                hour_text = "двенадцать"
                period = "ночи"
            elif hour < 12:
                hour_text = self.hours_ru[hour % 12] if hour <= 11 else str(hour)
                period = "утра" if hour < 6 else "утра" if hour < 12 else "дня"
            elif hour == 12:
                hour_text = "двенадцать"
                period = "дня"
            else:
                hour_text = self.hours_ru[(hour - 12) % 12] if (hour - 12) <= 11 else str(hour - 12)
                period = "дня" if hour < 18 else "вечера"
            
            if minute == 0:
                time_str = f"Сейчас {hour_text} часов {period}"
            elif minute < 10:
                time_str = f"Сейчас {hour_text} ноль {minute} {period}"
            else:
                time_str = f"Сейчас {hour_text} {minute} {period}"
        
        return IntentResult(
            text=time_str,
            should_speak=True,
            metadata={
                "time": now.strftime("%H:%M:%S"),
                "hour": now.hour,
                "minute": now.minute,
                "language": language
            }
        )
    
    async def _handle_datetime_request(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle combined date and time request"""
        now = datetime.now()
        
        if language == "en":
            weekday = self.weekdays_en[now.weekday()]
            month = self.months_en[now.month - 1]
            date_time_str = f"Today is {weekday}, {month} {now.day}, {now.year}. The time is {now.strftime('%I:%M %p')}"
        else:
            weekday = self.weekdays_ru[now.weekday()]
            month = self.months_ru[now.month - 1]
            day_ordinal = self.days_ru[now.day - 1] if now.day <= len(self.days_ru) else str(now.day)
            
            hour = now.hour
            minute = now.minute
            
            # Time formatting (same as time request)
            if hour == 0:
                hour_text = "двенадцать"
                period = "ночи"
            elif hour < 12:
                hour_text = self.hours_ru[hour % 12] if hour <= 11 else str(hour)
                period = "утра" if hour < 6 else "утра" if hour < 12 else "дня"
            elif hour == 12:
                hour_text = "двенадцать"
                period = "дня"
            else:
                hour_text = self.hours_ru[(hour - 12) % 12] if (hour - 12) <= 11 else str(hour - 12)
                period = "дня" if hour < 18 else "вечера"
            
            if minute == 0:
                time_part = f"{hour_text} часов {period}"
            elif minute < 10:
                time_part = f"{hour_text} ноль {minute} {period}"
            else:
                time_part = f"{hour_text} {minute} {period}"
            
            date_time_str = f"Сегодня {weekday}, {day_ordinal} {month} {now.year} года. Время: {time_part}"
        
        return IntentResult(
            text=date_time_str,
            should_speak=True,
            metadata={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "datetime": now.isoformat(),
                "language": language
            }
        )
    
 
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """DateTime handler needs date utilities"""
        return ["python-dateutil>=2.8.0"] 