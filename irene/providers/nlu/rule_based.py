"""
Rule-Based NLU Provider

Simple rule-based NLU for fallback intent recognition.
Uses regex patterns and keyword matching for basic intent classification.
"""

import re
import logging
from typing import Dict, Any, List, Pattern

from .base import NLUProvider
from ...intents.models import Intent, ConversationContext

logger = logging.getLogger(__name__)


class RuleBasedNLUProvider(NLUProvider):
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
        """Rule-based NLU is available when patterns are loaded from JSON donations"""
        return len(self.patterns) > 0
    
    async def _do_initialize(self) -> None:
        """Initialize NLU patterns - JSON donations required"""
        if not self.patterns:
            raise RuntimeError("RuleBasedNLUProvider requires JSON donations for pattern initialization. "
                             "Call _initialize_from_donations() first.")
    
    async def _initialize_from_donations(self, keyword_donations: List[Any]) -> None:
        """
        Initialize provider with JSON donation patterns (Phase 2 integration).
        
        This replaces hardcoded patterns with donation-driven patterns.
        """
        try:
            logger.info(f"Initializing RuleBasedNLU with {len(keyword_donations)} donations")
            
            # Clear existing hardcoded patterns
            self.patterns = {}
            self.intent_patterns = {}
            
            # Convert keyword donations to regex patterns
            for donation in keyword_donations:
                intent_name = donation.intent_name
                
                # Convert phrases to regex patterns
                regex_patterns = []
                for phrase in donation.phrases:
                    # Create case-insensitive regex pattern from phrase
                    # Escape special regex characters and add word boundaries
                    escaped_phrase = re.escape(phrase)
                    # Replace escaped spaces with flexible whitespace
                    flexible_phrase = escaped_phrase.replace(r'\ ', r'\s+')
                    pattern = re.compile(r'\b' + flexible_phrase + r'\b', re.IGNORECASE)
                    regex_patterns.append(pattern)
                
                # Add to patterns dictionary
                self.patterns[intent_name] = regex_patterns
                
                # Also store for intent_patterns (legacy compatibility)
                self.intent_patterns[intent_name] = donation.phrases
                
                logger.debug(f"Added {len(regex_patterns)} patterns for intent '{intent_name}'")
            
            logger.info(f"RuleBasedNLU initialized with donation patterns for {len(self.patterns)} intents")
            
        except Exception as e:
            logger.error(f"Failed to initialize RuleBasedNLU from donations: {e}")
            # Phase 4: No fallback patterns - fail fast
            raise RuntimeError(f"RuleBasedNLUProvider: JSON donation initialization failed: {e}. "
                             "Provider cannot operate without valid donations.")
    

    
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
    
    async def extract_entities(self, text: str, intent_name: str) -> Dict[str, Any]:
        """Extract entities for a given intent using regex patterns"""
        entities = {}
        
        # Basic entity extraction using regex patterns
        # This is a simplified implementation - full implementation would use
        # the parameter extraction system from Phase 0
        
        # Extract common entities
        import re
        
        # Numbers
        numbers = re.findall(r'\b\d+\b', text)
        if numbers:
            entities['numbers'] = numbers
        
        # Time expressions
        time_patterns = [
            r'\b(\d+)\s*(минут|секунд|часов|мин|сек|час)\b',
            r'\b(\d+)\s*(minutes?|seconds?|hours?)\b'
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                entities['duration'] = matches
                break
        
        return entities
    
    def get_supported_intents(self) -> List[str]:
        """Get list of intents this provider can recognize"""
        return list(self.patterns.keys())
    
    def validate_config(self) -> bool:
        """Validate rule-based NLU configuration"""
        if not 0.0 <= self.confidence_threshold <= 1.0:
            self.logger.error("confidence_threshold must be between 0.0 and 1.0")
            return False
        
        if not 0.0 <= self.default_confidence <= 1.0:
            self.logger.error("default_confidence must be between 0.0 and 1.0")
            return False
        
        return True
    
    # Asset configuration methods (TODO #4 Phase 1)
    @classmethod
    def _get_default_extension(cls) -> str:
        """Rule-based NLU doesn't use files"""
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Rule-based NLU directory for pattern storage"""
        return "rule_based"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Rule-based NLU doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Rule-based NLU uses runtime cache for patterns"""
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """Rule-based NLU doesn't use external models"""
        return {}
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Rule-based NLU uses only pure Python regex - no external dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Rule-based NLU has no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Rule-based NLU supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    async def cleanup(self) -> None:
        """Clean up rule-based NLU resources"""
        self.patterns.clear()
        logger.info("Rule-based NLU cleaned up") 