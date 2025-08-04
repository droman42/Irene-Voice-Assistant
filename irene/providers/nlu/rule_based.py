"""
Rule-Based NLU Provider

Simple rule-based NLU for fallback intent recognition.
Uses regex patterns and keyword matching for basic intent classification.
"""

import re
import logging
from typing import Dict, Any, List, Pattern

from ..base import ProviderBase
from ...intents.models import Intent, ConversationContext

logger = logging.getLogger(__name__)


class RuleBasedNLUProvider(ProviderBase):
    """
    Simple rule-based NLU for fallback intent recognition.
    
    Uses regex patterns and keyword matching to classify basic intents.
    Provides reliable fallback when more advanced NLU is unavailable.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.patterns: Dict[str, List[Pattern]] = {}
        self.confidence_threshold = config.get('confidence_threshold', 0.7)
        self.default_confidence = config.get('default_confidence', 0.8)
        self.fallback_intent = config.get('fallback_intent', 'conversation.general')
        
    def get_provider_name(self) -> str:
        return "rule_based_nlu"
    
    async def is_available(self) -> bool:
        """Rule-based NLU is always available"""
        if not self.patterns:
            await self._initialize_patterns()
        return True
    
    async def _do_initialize(self) -> None:
        """Initialize NLU patterns"""
        await self._initialize_patterns()
    
    async def _initialize_patterns(self):
        """Initialize regex patterns for intent recognition"""
        try:
            # Define intent patterns
            self.patterns = {
                # Greeting intents
                "greeting.hello": [
                    re.compile(r"\b(привет|здравствуй|добро пожаловать|приветствую)\b", re.IGNORECASE),
                    re.compile(r"\b(hello|hi|hey|greetings)\b", re.IGNORECASE),
                    re.compile(r"\b(доброе утро|добрый день|добрый вечер)\b", re.IGNORECASE),
                    re.compile(r"\b(good morning|good afternoon|good evening)\b", re.IGNORECASE),
                ],
                
                "greeting.goodbye": [
                    re.compile(r"\b(пока|до свидания|прощай|бывай)\b", re.IGNORECASE),
                    re.compile(r"\b(goodbye|bye|farewell|see you)\b", re.IGNORECASE),
                    re.compile(r"\b(до встречи|всего доброго)\b", re.IGNORECASE),
                    re.compile(r"\b(take care|good luck)\b", re.IGNORECASE),
                ],
                
                # Timer intents
                "timer.set": [
                    re.compile(r"\b(поставь|установи|засеки)\s+(таймер|время)\b", re.IGNORECASE),
                    re.compile(r"\b(set|start)\s+(timer|alarm)\b", re.IGNORECASE),
                    re.compile(r"\bтаймер\s+на\s+\d+", re.IGNORECASE),
                    re.compile(r"\bнапомни\s+через\s+\d+", re.IGNORECASE),
                ],
                
                "timer.cancel": [
                    re.compile(r"\b(отмени|убери|стоп)\s+(таймер|время)\b", re.IGNORECASE),
                    re.compile(r"\b(cancel|stop|remove)\s+(timer|alarm)\b", re.IGNORECASE),
                ],
                
                "timer.list": [
                    re.compile(r"\b(покажи|список)\s+таймер", re.IGNORECASE),
                    re.compile(r"\b(list|show)\s+timer", re.IGNORECASE),
                    re.compile(r"\bмои таймеры\b", re.IGNORECASE),
                ],
                
                # Conversation intents
                "conversation.start": [
                    re.compile(r"\b(поболтаем|поговорим|давай поговорим)\b", re.IGNORECASE),
                    re.compile(r"\b(let's talk|let's chat)\b", re.IGNORECASE),
                    re.compile(r"\bначинаем диалог\b", re.IGNORECASE),
                ],
                
                "conversation.reference": [
                    re.compile(r"\b(справка|что такое|кто такой)\b", re.IGNORECASE),
                    re.compile(r"\b(расскажи о|объясни)\b", re.IGNORECASE),
                    re.compile(r"\b(what is|who is|tell me about)\b", re.IGNORECASE),
                ],
                
                # System intents
                "system.status": [
                    re.compile(r"\b(статус|состояние|как дела)\b", re.IGNORECASE),
                    re.compile(r"\b(status|state|how are you)\b", re.IGNORECASE),
                ],
                
                "system.help": [
                    re.compile(r"\b(помощь|справка|что умеешь)\b", re.IGNORECASE),
                    re.compile(r"\b(help|commands|what can you do)\b", re.IGNORECASE),
                ],
                
                # Time/Date intents
                "datetime.current_time": [
                    re.compile(r"\b(сколько времени|который час|время)\b", re.IGNORECASE),
                    re.compile(r"\b(what time|current time)\b", re.IGNORECASE),
                ],
                
                "datetime.current_date": [
                    re.compile(r"\b(какое число|какая дата|сегодня)\b", re.IGNORECASE),
                    re.compile(r"\b(what date|today's date)\b", re.IGNORECASE),
                ],
            }
            
            logger.info(f"Initialized {len(self.patterns)} intent patterns")
            
        except Exception as e:
            logger.error(f"Failed to initialize NLU patterns: {e}")
            raise
    
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        """
        Recognize intent from text using pattern matching.
        
        Args:
            text: Input text to classify
            context: Conversation context
            
        Returns:
            Intent with classification result
        """
        text_clean = text.strip()
        
        # Find best matching intent
        best_intent = None
        best_confidence = 0.0
        
        for intent_name, patterns in self.patterns.items():
            confidence = self._calculate_pattern_confidence(text_clean, patterns)
            
            if confidence > best_confidence and confidence >= self.confidence_threshold:
                best_confidence = confidence
                best_intent = intent_name
        
        # If no pattern matches well enough, use fallback
        if not best_intent:
            best_intent = self.fallback_intent
            best_confidence = 0.5  # Lower confidence for fallback
        
        # Extract basic entities
        entities = self._extract_entities(text_clean, best_intent)
        
        # Parse domain and action
        domain, action = self._parse_intent_name(best_intent)
        
        return Intent(
            name=best_intent,
            entities=entities,
            confidence=best_confidence,
            raw_text=text,
            domain=domain,
            action=action,
            session_id=context.session_id
        )
    
    def _calculate_pattern_confidence(self, text: str, patterns: List[Pattern]) -> float:
        """Calculate confidence based on pattern matches"""
        matches = 0
        total_patterns = len(patterns)
        
        for pattern in patterns:
            if pattern.search(text):
                matches += 1
        
        # Base confidence on match ratio
        if matches == 0:
            return 0.0
        
        # Higher confidence for more pattern matches
        confidence = (matches / total_patterns) * self.default_confidence
        
        # Boost confidence for exact/strong matches
        if matches == total_patterns:
            confidence *= 1.1
        
        return min(confidence, 1.0)
    
    def _extract_entities(self, text: str, intent_name: str) -> Dict[str, Any]:
        """Extract basic entities based on intent type"""
        entities = {}
        
        # Timer-specific entity extraction
        if intent_name.startswith("timer."):
            # Extract duration and units
            duration_pattern = re.compile(r"(\d+)\s*(секунд|сек|минут|мин|час|часа|часов|seconds?|minutes?|hours?)", re.IGNORECASE)
            match = duration_pattern.search(text)
            if match:
                entities["duration"] = int(match.group(1))
                unit_text = match.group(2).lower()
                
                # Map to standard units
                if unit_text in ['секунд', 'сек', 'seconds', 'second']:
                    entities["unit"] = "seconds"
                elif unit_text in ['минут', 'мин', 'minutes', 'minute']:
                    entities["unit"] = "minutes"
                elif unit_text in ['час', 'часа', 'часов', 'hours', 'hour']:
                    entities["unit"] = "hours"
        
        # Date/time specific extraction
        elif intent_name.startswith("datetime."):
            # Could extract specific time references
            time_refs = re.findall(r"\b(сейчас|now|today|завтра|tomorrow)\b", text, re.IGNORECASE)
            if time_refs:
                entities["time_reference"] = time_refs[0].lower()
        
        # General entity extraction
        # Extract numbers
        numbers = re.findall(r"\b\d+\b", text)
        if numbers:
            entities["numbers"] = [int(n) for n in numbers]
        
        return entities
    
    def _parse_intent_name(self, intent_name: str) -> tuple[str, str]:
        """Parse intent name into domain and action"""
        if "." in intent_name:
            parts = intent_name.split(".", 1)
            return parts[0], parts[1]
        else:
            return "general", intent_name
    
    def get_supported_languages(self) -> List[str]:
        """Get supported languages"""
        return ["ru", "en"]
    
    def get_supported_domains(self) -> List[str]:
        """Get supported intent domains"""
        domains = set()
        for intent_name in self.patterns.keys():
            domain, _ = self._parse_intent_name(intent_name)
            domains.add(domain)
        return list(domains)
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get parameter schema for rule-based NLU"""
        return {
            "confidence_threshold": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.7,
                "description": "Minimum confidence for intent acceptance"
            },
            "default_confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.8,
                "description": "Base confidence for pattern matches"
            },
            "fallback_intent": {
                "type": "string",
                "default": "conversation.general",
                "description": "Fallback intent when no patterns match"
            }
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get rule-based NLU capabilities"""
        return {
            "supported_languages": self.get_supported_languages(),
            "supported_domains": self.get_supported_domains(),
            "pattern_count": len(self.patterns),
            "features": {
                "pattern_matching": True,
                "entity_extraction": True,
                "multilingual": True,
                "fast_processing": True,
                "no_dependencies": True,
                "offline": True
            }
        }
    
    def validate_config(self) -> bool:
        """Validate rule-based NLU configuration"""
        if not 0.0 <= self.confidence_threshold <= 1.0:
            self.logger.error("confidence_threshold must be between 0.0 and 1.0")
            return False
        
        if not 0.0 <= self.default_confidence <= 1.0:
            self.logger.error("default_confidence must be between 0.0 and 1.0")
            return False
        
        return True
    
    async def cleanup(self) -> None:
        """Clean up rule-based NLU resources"""
        self.patterns.clear()
        logger.info("Rule-based NLU cleaned up") 