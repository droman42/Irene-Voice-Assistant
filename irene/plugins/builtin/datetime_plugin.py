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
from ...core.interfaces.webapi import WebAPIPlugin
from ..base import BaseCommandPlugin


class DateTimePlugin(BaseCommandPlugin, WebAPIPlugin):
    """
    DateTime plugin providing date and time information.
    
    Features:
    - Current date with weekday
    - Current time with natural language
    - Configurable time format options
    - Russian language support
    - Web API endpoints for datetime operations
    """
    
    @property
    def name(self) -> str:
        return "datetime"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Date and time queries with natural language formatting and web API"
        
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
        
    # BaseCommandPlugin interface - existing voice functionality    
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
    
    # DateTime functionality methods (used by both voice and API)
    def get_current_datetime_info(self) -> Dict[str, Any]:
        """Get comprehensive current datetime information"""
        now = datetime.now()
        weekday_en = now.strftime("%A")
        weekday_ru = self.weekdays_ru[now.weekday()]
        
        return {
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "timezone": str(now.astimezone().tzinfo),
            "weekday": weekday_en,
            "weekday_ru": weekday_ru,
            "unix_timestamp": now.timestamp(),
            "day": now.day,
            "month": now.month,
            "year": now.year,
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "formatted_date_ru": self._format_date_russian(now),
            "formatted_time_ru": self._format_time_natural(now.hour, now.minute)
        }
    
    def format_datetime_custom(self, timestamp: Optional[float] = None, format_str: str = "%Y-%m-%d %H:%M:%S") -> Dict[str, Any]:
        """Format datetime with custom format string"""
        dt = datetime.fromtimestamp(timestamp) if timestamp else datetime.now()
        
        return {
            "formatted": dt.strftime(format_str),
            "original": dt.isoformat(),
            "timestamp": dt.timestamp()
        }
    
    def get_time_in_timezone(self, timezone_name: str) -> Dict[str, Any]:
        """Get current time in specified timezone"""
        try:
            import pytz  # type: ignore
            tz = pytz.timezone(timezone_name)
            now = datetime.now(tz)
            
            return {
                "datetime": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timezone": timezone_name,
                "utc_offset": str(now.utcoffset()),
                "unix_timestamp": now.timestamp()
            }
        except ImportError:
            raise ValueError("pytz library not available for timezone operations")
        except Exception as e:
            raise ValueError(f"Invalid timezone '{timezone_name}': {str(e)}")
    
    # WebAPIPlugin interface - unified API
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with datetime endpoints"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter, HTTPException  # type: ignore
            from pydantic import BaseModel  # type: ignore
            
            router = APIRouter()
            
            # Response models
            class DateTimeResponse(BaseModel):
                datetime: str
                date: str
                time: str
                timezone: str
                weekday: str
                weekday_ru: str
                unix_timestamp: float
                day: int
                month: int
                year: int
                hour: int
                minute: int
                second: int
                formatted_date_ru: str
                formatted_time_ru: str
                
            class FormatResponse(BaseModel):
                formatted: str
                original: str
                timestamp: float
                
            class TimezoneResponse(BaseModel):
                datetime: str
                date: str
                time: str
                timezone: str
                utc_offset: str
                unix_timestamp: float
            
            @router.get("/current", response_model=DateTimeResponse)
            async def get_current_datetime():
                """Get current date and time with comprehensive information"""
                info = self.get_current_datetime_info()
                return DateTimeResponse(**info)
            
            @router.get("/format", response_model=FormatResponse)
            async def format_datetime(
                timestamp: Optional[float] = None, 
                format_str: str = "%Y-%m-%d %H:%M:%S"
            ):
                """Format datetime with custom format string"""
                try:
                    result = self.format_datetime_custom(timestamp, format_str)
                    return FormatResponse(**result)
                except Exception as e:
                    raise HTTPException(400, f"Invalid format or timestamp: {str(e)}")
            
            @router.get("/timezone/{timezone_name}", response_model=TimezoneResponse)
            async def get_time_in_timezone(timezone_name: str):
                """Get current time in specified timezone"""
                try:
                    result = self.get_time_in_timezone(timezone_name)
                    return TimezoneResponse(**result)
                except ValueError as e:
                    raise HTTPException(400, str(e))
                except Exception as e:
                    raise HTTPException(500, f"Error getting timezone info: {str(e)}")
            
            @router.get("/timezones")
            async def list_common_timezones():
                """List commonly used timezones"""
                common_timezones = [
                    "UTC",
                    "Europe/Moscow",
                    "Europe/London", 
                    "America/New_York",
                    "America/Los_Angeles",
                    "Asia/Tokyo",
                    "Asia/Shanghai",
                    "Australia/Sydney",
                    "Europe/Paris",
                    "Europe/Berlin"
                ]
                return {"timezones": common_timezones}
            
            return router
            
        except ImportError:
            self.logger.warning("FastAPI not available for datetime web API")
            return None
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for datetime API endpoints"""
        return "/datetime"
    
    def get_api_tags(self) -> list[str]:
        """Get OpenAPI tags for datetime endpoints"""
        return ["DateTime", "Time", "Date"]

    # Internal helper methods
    def _format_date_russian(self, dt: datetime) -> str:
        """Format date in natural Russian"""
        weekday = self.weekdays_ru[dt.weekday()]
        day = self.days_ru[dt.day - 1]
        month = self.months_ru[dt.month - 1]
        return f"сегодня {weekday}, {day} {month}"
            
    async def _handle_date_request(self, context: Context) -> CommandResult:
        """Handle date request"""
        now = datetime.now()
        date_text = self._format_date_russian(now)
        
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