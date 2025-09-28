"""
Context-Based Entity Resolution System

This module implements context-aware entity resolution capabilities that use
client identification, device context, and conversation history to enhance
entity extraction and provide better understanding of user intents.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass
from ..intents.models import UnifiedConversationContext, Intent

# Required rapidfuzz import for fuzzy matching
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


@dataclass
class EntityResolutionResult:
    """Result of entity resolution with confidence and metadata"""
    resolved_value: Any
    original_value: str
    confidence: float
    resolution_type: str  # "exact", "fuzzy", "contextual", "inferred"
    metadata: Dict[str, Any]


class ContextualEntityResolver:
    """
    Context-aware entity resolver that uses client identification, device
    capabilities, and conversation history to resolve entity references.
    
    This implements the entity resolution capabilities described in the 
    Intent Keyword Donation Architecture document.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ContextualEntityResolver")
        
        # Entity type resolvers
        self.device_resolver = DeviceEntityResolver()
        self.location_resolver = LocationEntityResolver()
        self.temporal_resolver = TemporalEntityResolver()
        self.quantity_resolver = QuantityEntityResolver()
    
    async def resolve_entities(self, intent: Intent, context: UnifiedConversationContext) -> Dict[str, Any]:
        """
        Resolve all entities in the intent using context-aware resolution.
        
        Args:
            intent: Intent with entities to resolve
            context: UnifiedConversationContext with client and device information
            
        Returns:
            Dictionary with resolved entities and resolution metadata
        """
        resolved_entities = intent.entities.copy()
        resolution_metadata = {}
        
        for entity_name, entity_value in intent.entities.items():
            if isinstance(entity_value, str) and entity_value.strip():
                # Try different resolution strategies
                resolution_result = await self._resolve_single_entity(
                    entity_name, entity_value, intent, context
                )
                
                if resolution_result:
                    resolved_entities[f"{entity_name}_resolved"] = resolution_result.resolved_value
                    resolved_entities[f"{entity_name}_confidence"] = resolution_result.confidence
                    resolved_entities[f"{entity_name}_resolution_type"] = resolution_result.resolution_type
                    
                    resolution_metadata[entity_name] = resolution_result.metadata
                    
                    self.logger.debug(f"Resolved entity '{entity_name}': '{entity_value}' -> "
                                    f"{resolution_result.resolved_value} ({resolution_result.resolution_type})")
        
        # Add resolution metadata
        if resolution_metadata:
            resolved_entities["_resolution_metadata"] = resolution_metadata
        
        return resolved_entities
    
    async def _resolve_single_entity(self, entity_name: str, entity_value: str, 
                                   intent: Intent, context: UnifiedConversationContext) -> Optional[EntityResolutionResult]:
        """
        Resolve a single entity using appropriate resolution strategy.
        """
        entity_lower = entity_value.lower().strip()
        
        # Device entity resolution
        if self._is_device_entity(entity_name, entity_value, intent):
            return await self.device_resolver.resolve(entity_value, context)
        
        # Location entity resolution
        if self._is_location_entity(entity_name, entity_value, intent):
            return await self.location_resolver.resolve(entity_value, context)
        
        # Temporal entity resolution
        if self._is_temporal_entity(entity_name, entity_value, intent):
            return await self.temporal_resolver.resolve(entity_value, context)
        
        # Quantity entity resolution
        if self._is_quantity_entity(entity_name, entity_value, intent):
            return await self.quantity_resolver.resolve(entity_value, context)
        
        return None
    
    def _is_device_entity(self, entity_name: str, entity_value: str, intent: Intent) -> bool:
        """Check if entity is a device reference"""
        device_indicators = [
            # Russian device terms
            "устройство", "прибор", "свет", "лампа", "лампочка", "светильник", 
            "выключатель", "розетка", "телевизор", "тв", "колонка", "динамик",
            "датчик", "сенсор", "камера", "термостат", "вентилятор", "кондиционер",
            # English device terms  
            "device", "light", "lamp", "switch", "tv", "television", "speaker", 
            "sensor", "camera", "thermostat", "fan", "outlet", "plug"
        ]
        
        # Check entity name
        if any(indicator in entity_name.lower() for indicator in device_indicators):
            return True
        
        # Check entity value
        if any(indicator in entity_value.lower() for indicator in device_indicators):
            return True
        
        # Check intent domain for device-related intents
        if intent.domain in ["device", "smart_home", "iot"]:
            return True
        
        return False
    
    def _is_location_entity(self, entity_name: str, entity_value: str, intent: Intent) -> bool:
        """Check if entity is a location reference"""
        location_indicators = [
            # Russian location terms
            "комната", "место", "локация", "расположение", "где", "куда", "в", "на",
            "помещение", "зал", "зона", "область",
            # English location terms
            "room", "location", "place", "where", "in", "at"
        ]
        
        return (any(indicator in entity_name.lower() for indicator in location_indicators) or
                entity_name.lower() in ["location", "room", "place", "комната", "место", "локация"])
    
    def _is_temporal_entity(self, entity_name: str, entity_value: str, intent: Intent) -> bool:
        """Check if entity is a time/date reference"""
        temporal_indicators = [
            # Russian temporal terms
            "время", "дата", "когда", "в", "через", "на", "длительность", "продолжительность",
            "таймаут", "минута", "час", "секунда", "день", "неделя", "месяц",
            # English temporal terms
            "time", "date", "when", "at", "duration", "timeout"
        ]
        
        # Russian and English time patterns
        time_patterns = r'\d+:\d+|\d+\s*(hours?|minutes?|seconds?|часов?|часа|минут?|мин|секунд?|сек)'
        
        return (any(indicator in entity_name.lower() for indicator in temporal_indicators) or
                bool(re.search(time_patterns, entity_value.lower())))
    
    def _is_quantity_entity(self, entity_name: str, entity_value: str, intent: Intent) -> bool:
        """Check if entity is a quantity/number reference"""
        quantity_indicators = [
            # Russian quantity terms
            "число", "количество", "сумма", "объем", "размер", "счет", "номер",
            "длительность", "продолжительность", "таймаут",
            # English quantity terms
            "number", "count", "amount", "quantity", "duration", "timeout"
        ]
        
        return (any(indicator in entity_name.lower() for indicator in quantity_indicators) or
                bool(re.search(r'\d+', entity_value)))


class DeviceEntityResolver:
    """Resolver for device-related entities using client context"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.DeviceEntityResolver")
    
    async def resolve(self, device_reference: str, context: UnifiedConversationContext) -> Optional[EntityResolutionResult]:
        """
        Resolve device reference using client context and fuzzy matching.
        """
        available_devices = context.get_device_capabilities()
        if not available_devices:
            return None
        
        device_reference_lower = device_reference.lower().strip()
        
        # 1. Exact name match
        for device in available_devices:
            device_name = device.get("name", "").lower()
            if device_name == device_reference_lower:
                return EntityResolutionResult(
                    resolved_value=device,
                    original_value=device_reference,
                    confidence=1.0,
                    resolution_type="exact",
                    metadata={"match_type": "exact_name", "device_id": device.get("id")}
                )
        
        # 2. Fuzzy name matching using rapidfuzz
        device_names = [device.get("name", "") for device in available_devices]
        best_match = process.extractOne(device_reference, device_names, scorer=fuzz.ratio)
        
        if best_match and best_match[1] >= 70:  # 70% similarity threshold
            for device in available_devices:
                if device.get("name", "") == best_match[0]:
                    return EntityResolutionResult(
                        resolved_value=device,
                        original_value=device_reference,
                        confidence=best_match[1] / 100.0,
                        resolution_type="fuzzy",
                        metadata={"match_type": "fuzzy_name", "similarity": best_match[1]}
                    )
        
        # 3. Type-based matching (Russian + English)
        device_types = {
            "light": [
                # Russian terms
                "свет", "лампа", "лампочка", "светильник", "освещение", "подсветка",
                # English terms
                "light", "lamp", "bulb"
            ],
            "switch": [
                # Russian terms
                "выключатель", "переключатель", "розетка", "штепсель",
                # English terms
                "switch", "outlet", "plug"
            ],
            "speaker": [
                # Russian terms
                "колонка", "динамик", "аудио", "звук", "музыка",
                # English terms
                "speaker", "audio"
            ],
            "tv": [
                # Russian terms
                "телевизор", "тв", "экран", "дисплей", "монитор",
                # English terms
                "tv", "television", "display"
            ],
            "sensor": [
                # Russian terms
                "датчик", "сенсор", "детектор", "измеритель",
                # English terms
                "sensor", "detector"
            ],
            "camera": [
                # Russian terms
                "камера", "видеокамера", "веб-камера", "вебкамера",
                # English terms
                "camera", "cam"
            ]
        }
        
        for device_type, keywords in device_types.items():
            if any(keyword in device_reference_lower for keyword in keywords):
                # Find devices of this type
                matching_devices = [d for d in available_devices 
                                  if d.get("type", "").lower() == device_type]
                
                if matching_devices:
                    # If only one device of this type, return it
                    if len(matching_devices) == 1:
                        return EntityResolutionResult(
                            resolved_value=matching_devices[0],
                            original_value=device_reference,
                            confidence=0.8,
                            resolution_type="contextual",
                            metadata={"match_type": "type_inference", "device_type": device_type}
                        )
                    else:
                        # Multiple devices, return list
                        return EntityResolutionResult(
                            resolved_value=matching_devices,
                            original_value=device_reference,
                            confidence=0.6,
                            resolution_type="contextual",
                            metadata={"match_type": "type_multiple", "device_type": device_type, 
                                    "count": len(matching_devices)}
                        )
        
        return None


class LocationEntityResolver:
    """Resolver for location-related entities using client context"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.LocationEntityResolver")
    
    async def resolve(self, location_reference: str, context: UnifiedConversationContext) -> Optional[EntityResolutionResult]:
        """
        Resolve location reference using client and room context.
        """
        location_lower = location_reference.lower().strip()
        
        # 1. Current room inference (Russian + English)
        current_room = context.get_room_name()
        here_keywords = ["here", "this room", "здесь", "тут", "в этой комнате", "в комнате", "сюда"]
        
        if current_room and any(keyword in location_lower for keyword in here_keywords):
            return EntityResolutionResult(
                resolved_value=current_room,
                original_value=location_reference,
                confidence=0.9,
                resolution_type="contextual",
                metadata={"match_type": "current_room", "room_name": current_room}
            )
        
        # 2. Room name matching from client metadata
        available_rooms = context.client_metadata.get("available_rooms", [])
        if available_rooms:
            # Exact match
            for room in available_rooms:
                if isinstance(room, dict):
                    room_name = room.get("name", "").lower()
                else:
                    room_name = str(room).lower()
                
                if room_name == location_lower:
                    return EntityResolutionResult(
                        resolved_value=room,
                        original_value=location_reference,
                        confidence=1.0,
                        resolution_type="exact",
                        metadata={"match_type": "room_name"}
                    )
            
            # Fuzzy match using rapidfuzz
            room_names = [r.get("name", str(r)) if isinstance(r, dict) else str(r) 
                        for r in available_rooms]
            best_match = process.extractOne(location_reference, room_names, scorer=fuzz.ratio)
            
            if best_match and best_match[1] >= 75:
                return EntityResolutionResult(
                    resolved_value=best_match[0],
                    original_value=location_reference,
                    confidence=best_match[1] / 100.0,
                    resolution_type="fuzzy",
                    metadata={"match_type": "room_fuzzy", "similarity": best_match[1]}
                )
        
        return None


class TemporalEntityResolver:
    """Resolver for time and date entities"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.TemporalEntityResolver")
    
    async def resolve(self, temporal_reference: str, context: UnifiedConversationContext) -> Optional[EntityResolutionResult]:
        """
        Resolve temporal references using context and patterns.
        """
        temporal_lower = temporal_reference.lower().strip()
        
        # Time pattern matching
        time_pattern = re.search(r'(\d{1,2}):(\d{2})', temporal_reference)
        if time_pattern:
            hours, minutes = time_pattern.groups()
            return EntityResolutionResult(
                resolved_value={"hours": int(hours), "minutes": int(minutes)},
                original_value=temporal_reference,
                confidence=0.95,
                resolution_type="exact",
                metadata={"match_type": "time_pattern", "format": "HH:MM"}
            )
        
        # Duration pattern matching (Russian + English)
        duration_patterns = [
            # Russian patterns
            (r'(\d+)\s*(часов?|часа|ч)', "hours"),
            (r'(\d+)\s*(минут?|мин)', "minutes"),
            (r'(\d+)\s*(секунд?|сек)', "seconds"),
            # English patterns
            (r'(\d+)\s*hours?', "hours"),
            (r'(\d+)\s*minutes?', "minutes"),
            (r'(\d+)\s*seconds?', "seconds"),
            (r'(\d+)\s*hrs?', "hours"),
            (r'(\d+)\s*mins?', "minutes"),
            (r'(\d+)\s*secs?', "seconds")
        ]
        
        for pattern, unit in duration_patterns:
            match = re.search(pattern, temporal_lower)
            if match:
                value = int(match.group(1))
                return EntityResolutionResult(
                    resolved_value={"value": value, "unit": unit},
                    original_value=temporal_reference,
                    confidence=0.9,
                    resolution_type="exact",
                    metadata={"match_type": "duration_pattern", "unit": unit}
                )
        
        # Relative time references (Russian + English)
        relative_times = {
            # Russian terms
            "сейчас": {"relative": "now", "offset": 0},
            "потом": {"relative": "future", "offset": None},
            "позже": {"relative": "future", "offset": None},
            "скоро": {"relative": "future", "offset": "short"},
            "вскоре": {"relative": "future", "offset": "short"},
            "сегодня": {"relative": "today", "offset": 0},
            "завтра": {"relative": "tomorrow", "offset": 1},
            "вчера": {"relative": "yesterday", "offset": -1},
            # English terms
            "now": {"relative": "now", "offset": 0},
            "later": {"relative": "future", "offset": None},
            "soon": {"relative": "future", "offset": "short"},
            "today": {"relative": "today", "offset": 0},
            "tomorrow": {"relative": "tomorrow", "offset": 1},
            "yesterday": {"relative": "yesterday", "offset": -1}
        }
        
        for keyword, time_info in relative_times.items():
            if keyword in temporal_lower:
                return EntityResolutionResult(
                    resolved_value=time_info,
                    original_value=temporal_reference,
                    confidence=0.8,
                    resolution_type="contextual",
                    metadata={"match_type": "relative_time", "keyword": keyword}
                )
        
        return None


class QuantityEntityResolver:
    """Resolver for quantity and number entities"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.QuantityEntityResolver")
    
    async def resolve(self, quantity_reference: str, context: UnifiedConversationContext) -> Optional[EntityResolutionResult]:
        """
        Resolve quantity references with unit inference.
        """
        quantity_lower = quantity_reference.lower().strip()
        
        # Number extraction
        number_pattern = re.search(r'(\d+(?:\.\d+)?)', quantity_reference)
        if number_pattern:
            number = float(number_pattern.group(1))
            
            # Unit inference (Russian + English)
            unit_patterns = {
                "percent": [
                    # Russian
                    "%", "процент", "процента", "процентов",
                    # English
                    "percent", "percentage"
                ],
                "degrees": [
                    # Russian
                    "градус", "градуса", "градусов", "°",
                    # English
                    "degrees", "degree"
                ],
                "minutes": [
                    # Russian
                    "минут", "минута", "минуты", "мин",
                    # English
                    "minutes", "minute", "mins", "min"
                ],
                "seconds": [
                    # Russian
                    "секунд", "секунда", "секунды", "сек",
                    # English
                    "seconds", "second", "secs", "sec"
                ],
                "hours": [
                    # Russian
                    "часов", "час", "часа", "ч",
                    # English
                    "hours", "hour", "hrs", "hr"
                ],
                "times": [
                    # Russian
                    "раз", "раза", "x",
                    # English
                    "times", "time", "x"
                ],
                "count": [
                    # Russian
                    "штук", "штука", "штуки", "элемент", "элемента", "элементов",
                    "предмет", "предмета", "предметов", "вещь", "вещи", "вещей",
                    # English
                    "items", "things", "pieces"
                ]
            }
            
            inferred_unit = "count"  # default
            for unit, keywords in unit_patterns.items():
                if any(keyword in quantity_lower for keyword in keywords):
                    inferred_unit = unit
                    break
            
            return EntityResolutionResult(
                resolved_value={"value": number, "unit": inferred_unit},
                original_value=quantity_reference,
                confidence=0.85,
                resolution_type="exact",
                metadata={"match_type": "number_with_unit", "inferred_unit": inferred_unit}
            )
        
        # Word numbers (Russian + English)
        word_numbers = {
            # Russian numbers
            "ноль": 0, "один": 1, "одна": 1, "одно": 1, "два": 2, "две": 2, 
            "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, 
            "восемь": 8, "девять": 9, "десять": 10,
            # English numbers
            "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "none": 0, "a": 1, "an": 1
        }
        
        for word, number in word_numbers.items():
            if word in quantity_lower:
                return EntityResolutionResult(
                    resolved_value={"value": number, "unit": "count"},
                    original_value=quantity_reference,
                    confidence=0.8,
                    resolution_type="contextual",
                    metadata={"match_type": "word_number", "word": word}
                )
        
        return None 