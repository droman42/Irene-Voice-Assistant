"""
DateTime Plugin - Date and time information

Replaces legacy plugin_datetime.py with modern async architecture.
Provides current date and time with natural language formatting.
"""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any

from ...core.context import Context
from ...core.commands import CommandResult
from ..base import BaseCommandPlugin


class DateTimePlugin(BaseCommandPlugin):
    """
    DateTime plugin providing date and time information.
    
    Features:
    - Current date with weekday
    - Current time with natural language
    - Configurable time format options
    - Russian language support
    """
    
    @property
    def name(self) -> str:
        return "datetime"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Date and time queries with natural language formatting"
        
    @property
    def dependencies(self) -> list[str]:
        """No dependencies for datetime"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """No optional dependencies for datetime"""
        return []
        
    # Additional metadata for PluginRegistry discovery
    @property
    def enabled_by_default(self) -> bool:
        """DateTime should be enabled by default"""
        return True
        
    @property  
    def category(self) -> str:
        """Plugin category"""
        return "command"
        
    @property
    def platforms(self) -> list[str]:
        """Supported platforms (empty = all platforms)"""
        return []
        
    def __init__(self):
        super().__init__()
        # Date triggers
        self.add_trigger("дата")
        self.add_trigger("какая дата")
        self.add_trigger("какое число")
        self.add_trigger("date")
        
        # Time triggers
        self.add_trigger("время")
        self.add_trigger("сколько времени")
        self.add_trigger("который час")
        self.add_trigger("time")
        self.add_trigger("what time")
        
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
        
        # Time formatting options (can be made configurable later)
        self.time_options = {
            "say_noon": False,  # Say "полдень"/"полночь" instead of 12/0 hours
            "skip_units": False,  # Don't say "час"/"минуты"
            "units_separator": ", ",  # Separator between hours and minutes
            "skip_minutes_when_zero": True  # Don't say minutes if zero
        }
        
    async def _handle_command_impl(self, command: str, context: Context) -> CommandResult:
        """Handle datetime commands"""
        command_lower = command.lower().strip()
        
        # Add small delay to simulate async operation
        await asyncio.sleep(0.05)
        
        if any(trigger in command_lower for trigger in ["дата", "число", "date"]):
            return await self._handle_date_request(context)
        elif any(trigger in command_lower for trigger in ["время", "час", "time"]):
            return await self._handle_time_request(context)
        else:
            return CommandResult.error_result("Неизвестная команда даты/времени")
            
    async def _handle_date_request(self, context: Context) -> CommandResult:
        """Handle date request"""
        now = datetime.now()
        weekday = self.weekdays_ru[now.weekday()]
        
        # Format date in natural Russian
        day = self.days_ru[now.day - 1]
        month = self.months_ru[now.month - 1]
        
        date_text = f"сегодня {weekday}, {day} {month}"
        
        return CommandResult.success_result(
            response=date_text,
            should_continue_listening=True
        )
        
    async def _handle_time_request(self, context: Context) -> CommandResult:
        """Handle time request"""
        now = datetime.now()
        hours = now.hour
        minutes = now.minute
        
        # Special cases for noon and midnight
        if self.time_options["say_noon"]:
            if hours == 0 and minutes == 0:
                return CommandResult.success_result("Сейчас ровно полночь")
            elif hours == 12 and minutes == 0:
                return CommandResult.success_result("Сейчас ровно полдень")
        
        # Convert to natural language
        time_text = self._format_time_natural(hours, minutes)
        
        return CommandResult.success_result(
            response=time_text,
            should_continue_listening=True
        )
        
    def _format_time_natural(self, hours: int, minutes: int) -> str:
        """Format time in natural Russian language"""
        # Simple number to text conversion for hours and minutes
        # This is a simplified version - in a full implementation, 
        # you'd import the num2text utility from the legacy system
        
        hour_text = self._number_to_text_hours(hours)
        minute_text = self._number_to_text_minutes(minutes)
        
        if self.time_options["skip_units"]:
            units_minutes = ""
            units_hours = ""
        else:
            units_hours = self._get_hour_units(hours)
            units_minutes = self._get_minute_units(minutes)
        
        if minutes > 0 or not self.time_options["skip_minutes_when_zero"]:
            time_text = f"Сейчас {hour_text}{units_hours}"
            if not self.time_options["skip_units"]:
                time_text += self.time_options["units_separator"]
            time_text += f"{minute_text}{units_minutes}"
        else:
            time_text = f"Сейчас ровно {hour_text}{units_hours}"
            
        return time_text
        
    def _number_to_text_hours(self, hour: int) -> str:
        """Convert hour number to text"""
        hour_names = [
            "ноль", "один", "два", "три", "четыре", "пять",
            "шесть", "семь", "восемь", "девять", "десять",
            "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
            "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать", "двадцать",
            "двадцать один", "двадцать два", "двадцать три"
        ]
        return hour_names[hour] if hour < len(hour_names) else str(hour)
        
    def _number_to_text_minutes(self, minute: int) -> str:
        """Convert minute number to text"""
        if minute == 0:
            return "ноль"
        elif minute < 20:
            minute_names = [
                "", "одна", "две", "три", "четыре", "пять",
                "шесть", "семь", "восемь", "девять", "десять",
                "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
                "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"
            ]
            return minute_names[minute]
        else:
            # Simplified for 20-59 minutes
            return str(minute)  # In full implementation, would be more sophisticated
            
    def _get_hour_units(self, hours: int) -> str:
        """Get proper hour units based on number"""
        if hours % 10 == 1 and hours % 100 != 11:
            return " час"
        elif hours % 10 in [2, 3, 4] and hours % 100 not in [12, 13, 14]:
            return " часа"
        else:
            return " часов"
            
    def _get_minute_units(self, minutes: int) -> str:
        """Get proper minute units based on number"""
        if minutes % 10 == 1 and minutes % 100 != 11:
            return " минута"
        elif minutes % 10 in [2, 3, 4] and minutes % 100 not in [12, 13, 14]:
            return " минуты"
        else:
            return " минут" 