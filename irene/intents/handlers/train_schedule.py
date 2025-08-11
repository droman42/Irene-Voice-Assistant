"""
Train Schedule Intent Handler - Yandex Schedules integration

Provides train schedule information through Yandex.Schedules API.
Supports Russian voice commands for train departures.
"""

import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import asyncio

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests library not available, train schedule functionality disabled")


class TrainScheduleIntentHandler(IntentHandler):
    """
    Handles train schedule intents using Yandex.Schedules API.
    
    Features:
    - Get next train departures
    - Support for Russian voice commands
    - Configurable API key and stations
    - Natural language time formatting
    
    Requirements:
    - API key from https://yandex.ru/dev/rasp/raspapi/
    - Station IDs for departure and destination
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        
        # TODO #15: Move configuration defaults to TOML configuration (not JSON donations)
        # Default configuration
        self.config = config or {}
        self.api_key = self.config.get("api_key", "")
        self.default_from_station = self.config.get("from_station", "s9600681")  # Default Moscow station
        self.default_to_station = self.config.get("to_station", "s2000002")     # Default destination
        self.max_results = self.config.get("max_results", 3)
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process train schedule intents"""
        if not self.has_donation():
            raise RuntimeError(f"TrainScheduleIntentHandler: Missing JSON donation file - train_schedule.json is required")
        
        # Use JSON donation patterns exclusively
        donation = self.get_donation()
        
        # Check domain/action combinations
        if intent.domain == "transport" and intent.action in ["train_schedule", "get_trains"]:
            return True
        
        # Check intent name patterns
        if hasattr(donation, 'intent_name_patterns') and intent.name in donation.intent_name_patterns:
            return True
        
        # Check action patterns
        if hasattr(donation, 'action_patterns') and intent.action in donation.action_patterns:
            return True
        
        # Check train keywords in raw text
        if hasattr(donation, 'train_keywords'):
            if any(keyword in intent.raw_text.lower() for keyword in donation.train_keywords):
                return True
        
        return False
    
    async def is_available(self) -> bool:
        """Check if handler is available (has API key and requests library)"""
        if not REQUESTS_AVAILABLE:
            return False
        
        if not self.api_key:
            logger.warning("Train schedule handler unavailable: missing API key")
            return False
        
        return True
    
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Execute train schedule intent"""
        try:
            # Check availability
            if not await self.is_available():
                if not REQUESTS_AVAILABLE:
                    return self._create_error_result(
                        "Функция расписания поездов недоступна. Отсутствует библиотека requests.",
                        "missing_dependency"
                    )
                else:
                    return self._create_error_result(
                        "Нужен ключ API для получения расписания",
                        "missing_api_key"
                    )
            
            # Extract stations from entities or use defaults
            from_station = self.extract_entity(intent, "from_station", self.default_from_station)
            to_station = self.extract_entity(intent, "to_station", self.default_to_station)
            
            # Get train schedule
            schedule_text = await self._get_train_schedule(from_station, to_station)
            
            if schedule_text:
                return self._create_success_result(
                    schedule_text,
                    should_speak=True,
                    metadata={
                        "from_station": from_station,
                        "to_station": to_station,
                        "provider": "yandex_schedules"
                    }
                )
            else:
                return self._create_error_result(
                    "Не удалось получить расписание поездов",
                    "schedule_unavailable"
                )
        
        except Exception as e:
            logger.exception(f"Error in train schedule handler: {e}")
            return self._create_error_result(
                "Проблемы с расписанием. Посмотрите логи",
                f"execution_error: {str(e)}"
            )
    
    async def _get_train_schedule(self, from_station: str, to_station: str) -> Optional[str]:
        """Get train schedule from Yandex API"""
        try:
            # Current date
            current_date = date.today().isoformat()
            current_time = datetime.now()
            
            # Make API request in thread pool to avoid blocking
            response = await asyncio.to_thread(
                self._make_schedule_request,
                from_station,
                to_station,
                current_date
            )
            
            if not response:
                return None
            
            # Parse response and format
            return self._format_schedule_response(response, current_time)
        
        except Exception as e:
            logger.exception(f"Error getting train schedule: {e}")
            return None
    
    def _make_schedule_request(self, from_station: str, to_station: str, date_str: str) -> Optional[Dict[str, Any]]:
        """Make synchronous request to Yandex API"""
        try:
            url = "https://api.rasp.yandex.net/v3.0/search/"
            params = {
                'from': from_station,
                'to': to_station,
                'format': 'json',
                'date': date_str,
                'apikey': self.api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Yandex API response: {data}")
            
            return data
        
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return None
    
    def _format_schedule_response(self, data: Dict[str, Any], current_time: datetime) -> str:
        """Format schedule data into natural language Russian text"""
        try:
            segments = data.get("segments", [])
            if not segments:
                return "Расписание не найдено"
            
            current_time_str = current_time.isoformat()
            results = []
            count = 0
            
            for segment in segments:
                if count >= self.max_results:
                    break
                
                departure_str = str(segment.get("departure", ""))
                departure_time = departure_str.replace("T", " ")
                
                # Only include future departures
                if departure_time > current_time_str:
                    # Extract hours and minutes
                    hours = departure_time[11:13]
                    minutes = departure_time[14:16]
                    
                    if count == 0:
                        results.append(f"Ближайшая электричка в {hours} {minutes}")
                    elif count == 1:
                        results.append(f"Следующая в {hours} {minutes}")
                    elif count == 2:
                        results.append(f"Дальше в {hours} {minutes}")
                    
                    count += 1
            
            if results:
                return ". ".join(results) + "."
            else:
                return "Не найдено поездов на сегодня"
        
        except Exception as e:
            logger.error(f"Error formatting schedule: {e}")
            return "Ошибка обработки расписания"
    
    def get_supported_domains(self) -> List[str]:
        """Get supported domains"""
        return ["transport"]
    
    def get_supported_actions(self) -> List[str]:
        """Get supported actions"""
        return ["train_schedule", "get_trains"]
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get handler capabilities"""
        return {
            "name": self.name,
            "domains": self.get_supported_domains(),
            "actions": self.get_supported_actions(),
            "available": REQUESTS_AVAILABLE and bool(self.api_key),
            "features": [
                "yandex_schedules_api",
                "russian_language",
                "train_departures",
                "natural_language_formatting"
            ],
            "requirements": [
                "yandex_api_key",
                "station_ids",
                "requests_library"
            ]
        }


    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Train schedule handler needs HTTP client for API requests"""
        return ["httpx>=0.25.0"] 
    
def create_handler(config: Optional[Dict[str, Any]] = None) -> TrainScheduleIntentHandler:
    """Factory function to create train schedule handler with configuration"""
    return TrainScheduleIntentHandler(config) 
