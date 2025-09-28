"""
DateTime Intent Handler - Date and time information for Intent System

Provides current date and time with natural language formatting.
Adapted from datetime_plugin.py for the new intent architecture.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from .base import IntentHandler
from ..models import Intent, IntentResult, UnifiedConversationContext

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
        
        # TODO #15: Phase 2 - Temporal formatting arrays now externalized to assets/localization/datetime/
        # All temporal data is loaded from localization files with fallback to hardcoded defaults
    
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
    
    async def execute(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Execute datetime intent"""
        try:
            # Use language from context (detected by NLU)
            language = context.language or "ru"
            
            if intent.action == "current_date" or intent.name == "datetime.current_date":
                return await self._handle_date_request(intent, context)
            elif intent.action == "current_time" or intent.name == "datetime.current_time":
                return await self._handle_time_request(intent, context)
            else:
                # Default: provide both date and time
                return await self._handle_datetime_request(intent, context)
                
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
    
    def _get_localization_data(self, language: str = "ru") -> Dict[str, List[str]]:
        """Get localization data from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"DateTimeIntentHandler: Asset loader not initialized. "
                f"Cannot access temporal data for language '{language}'. "
                f"This is a fatal configuration error - temporal data must be externalized."
            )
        
        # Get localization data from asset loader
        locale_data = self.asset_loader.get_localization("datetime", language)
        if locale_data is None:
            raise RuntimeError(
                f"DateTimeIntentHandler: Required temporal localization for language '{language}' "
                f"not found in assets/localization/datetime/{language}.yaml. "
                f"This is a fatal error - all temporal data must be externalized."
            )
        
        return locale_data
    
    async def _handle_date_request(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle current date request"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        now = datetime.now()
        locale_data = self._get_localization_data(language)
        
        weekdays = locale_data.get("weekdays", [])
        months = locale_data.get("months", [])
        templates = locale_data.get("templates", {})
        
        if language == "en":
            weekday = weekdays[now.weekday()] if now.weekday() < len(weekdays) else "Unknown"
            month = months[now.month - 1] if now.month - 1 < len(months) else "Unknown"
            template = templates.get("date_full", "Today is {weekday}, {month} {day}, {year}")
            date_str = template.format(weekday=weekday, month=month, day=now.day, year=now.year)
        else:
            days_ordinal = locale_data.get("days_ordinal", [])
            weekday = weekdays[now.weekday()] if now.weekday() < len(weekdays) else "неизвестно"
            month = months[now.month - 1] if now.month - 1 < len(months) else "неизвестно"
            day_ordinal = days_ordinal[now.day - 1] if now.day <= len(days_ordinal) else str(now.day)
            template = templates.get("date_full", "Сегодня {weekday}, {day_ordinal} {month} {year} года")
            date_str = template.format(weekday=weekday, day_ordinal=day_ordinal, month=month, year=now.year)
        
        return IntentResult(
            text=date_str,
            should_speak=True,
            metadata={
                "date": now.strftime("%Y-%m-%d"),
                "weekday": now.weekday(),
                "language": language
            }
        )
    
    async def _handle_time_request(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle current time request"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        now = datetime.now()
        locale_data = self._get_localization_data(language)
        
        if language == "en":
            time_str = f"It's {now.strftime('%I:%M %p')}"
        else:
            hour = now.hour
            minute = now.minute
            hours = locale_data.get("hours", [])
            periods = locale_data.get("periods", {})
            special_hours = locale_data.get("special_hours", {})
            templates = locale_data.get("templates", {})
            
            # Convert to 12-hour format for natural language
            if hour == 0:
                hour_text = special_hours.get("midnight", "двенадцать")
                period = periods.get("night", "ночи")
            elif hour < 6:
                hour_text = hours[hour % 12] if hour <= len(hours) else str(hour)
                period = periods.get("night", "ночи")
            elif hour < 12:
                hour_text = hours[hour % 12] if hour <= len(hours) else str(hour)
                period = periods.get("morning", "утра")
            elif hour == 12:
                hour_text = special_hours.get("noon", "двенадцать")
                period = periods.get("day", "дня")
            elif hour < 18:
                hour_12 = (hour - 12) % 12
                hour_text = hours[hour_12] if hour_12 < len(hours) else str(hour - 12)
                period = periods.get("day", "дня")
            else:
                hour_12 = (hour - 12) % 12
                hour_text = hours[hour_12] if hour_12 < len(hours) else str(hour - 12)
                period = periods.get("evening", "вечера")
            
            # Use templates for time formatting
            if minute == 0:
                template = templates.get("time_exact", "Сейчас {hour_text} часов {period}")
                time_str = template.format(hour_text=hour_text, period=period)
            elif minute < 10:
                template = templates.get("time_with_minutes_zero", "Сейчас {hour_text} ноль {minute} {period}")
                time_str = template.format(hour_text=hour_text, minute=minute, period=period)
            else:
                template = templates.get("time_with_minutes", "Сейчас {hour_text} {minute} {period}")
                time_str = template.format(hour_text=hour_text, minute=minute, period=period)
        
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
    
    async def _handle_datetime_request(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle combined date and time request"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        now = datetime.now()
        
        locale_data = self._get_localization_data(language)
        
        weekdays = locale_data.get("weekdays", [])
        months = locale_data.get("months", [])
        templates = locale_data.get("templates", {})
        
        if language == "en":
            weekday = weekdays[now.weekday()] if now.weekday() < len(weekdays) else "Unknown"
            month = months[now.month - 1] if now.month - 1 < len(months) else "Unknown"
            time_part = now.strftime('%I:%M %p')
            template = templates.get("datetime_full", "Today is {weekday}, {month} {day}, {year}. The time is {time_part}")
            date_time_str = template.format(weekday=weekday, month=month, day=now.day, year=now.year, time_part=time_part)
        else:
            days_ordinal = locale_data.get("days_ordinal", [])
            hours = locale_data.get("hours", [])
            periods = locale_data.get("periods", {})
            special_hours = locale_data.get("special_hours", {})
            
            weekday = weekdays[now.weekday()] if now.weekday() < len(weekdays) else "неизвестно"
            month = months[now.month - 1] if now.month - 1 < len(months) else "неизвестно"
            day_ordinal = days_ordinal[now.day - 1] if now.day <= len(days_ordinal) else str(now.day)
            
            hour = now.hour
            minute = now.minute
            
            # Time formatting using localized periods and special hours
            if hour == 0:
                hour_text = special_hours.get("midnight", "двенадцать")
                period = periods.get("night", "ночи")
            elif hour < 6:
                hour_text = hours[hour % 12] if hour <= len(hours) else str(hour)
                period = periods.get("night", "ночи")
            elif hour < 12:
                hour_text = hours[hour % 12] if hour <= len(hours) else str(hour)
                period = periods.get("morning", "утра")
            elif hour == 12:
                hour_text = special_hours.get("noon", "двенадцать")
                period = periods.get("day", "дня")
            elif hour < 18:
                hour_12 = (hour - 12) % 12
                hour_text = hours[hour_12] if hour_12 < len(hours) else str(hour - 12)
                period = periods.get("day", "дня")
            else:
                hour_12 = (hour - 12) % 12
                hour_text = hours[hour_12] if hour_12 < len(hours) else str(hour - 12)
                period = periods.get("evening", "вечера")
            
            # Format time part using templates
            if minute == 0:
                time_template = templates.get("time_exact", "Сейчас {hour_text} часов {period}")
                time_part = time_template.format(hour_text=hour_text, period=period).replace("Сейчас ", "")
            elif minute < 10:
                time_template = templates.get("time_with_minutes_zero", "Сейчас {hour_text} ноль {minute} {period}")
                time_part = time_template.format(hour_text=hour_text, minute=minute, period=period).replace("Сейчас ", "")
            else:
                time_template = templates.get("time_with_minutes", "Сейчас {hour_text} {minute} {period}")
                time_part = time_template.format(hour_text=hour_text, minute=minute, period=period).replace("Сейчас ", "")
            
            # Format combined datetime using template
            datetime_template = templates.get("datetime_full", "Сегодня {weekday}, {day_ordinal} {month} {year} года. Время: {time_part}")
            date_time_str = datetime_template.format(weekday=weekday, day_ordinal=day_ordinal, month=month, year=now.year, time_part=time_part)
        
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
    
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """DateTime handler has no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
    
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """DateTime handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    # Configuration metadata: No configuration needed
    # This handler uses asset loader for localization data only
    # No get_config_schema() method = no configuration required 