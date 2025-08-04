"""
spaCy NLU Provider

Advanced NLU provider using spaCy for intent classification and entity extraction.
Provides more sophisticated natural language understanding than rule-based approach.
"""

import logging
from typing import Dict, Any, List, Optional

from ..base import ProviderBase
from ...intents.models import Intent, ConversationContext
from ...utils.loader import safe_import

logger = logging.getLogger(__name__)


class SpaCyNLUProvider(ProviderBase):
    """
    spaCy-based NLU with entity recognition and intent classification.
    
    Uses spaCy's natural language processing capabilities for:
    - Named entity recognition
    - Semantic similarity matching
    - Advanced text classification
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.nlp = None
        self.model_name = config.get('model_name', 'ru_core_news_sm')
        self.fallback_model = config.get('fallback_model', 'en_core_web_sm')
        self.confidence_threshold = config.get('confidence_threshold', 0.7)
        self.entity_types = config.get('entity_types', ['PERSON', 'ORG', 'GPE', 'DATE', 'TIME', 'MONEY', 'QUANTITY'])
        self.intent_patterns = {}
        
    def get_provider_name(self) -> str:
        return "spacy_nlu"
    
    async def is_available(self) -> bool:
        """Check if spaCy is available and models can be loaded"""
        try:
            spacy = safe_import('spacy')
            if spacy is None:
                self._set_status(self.status.__class__.UNAVAILABLE, "spaCy package not installed")
                return False
            
            if not self.nlp:
                await self._initialize_spacy()
            
            return self.nlp is not None
            
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"spaCy NLU initialization failed: {e}")
            return False
    
    async def _do_initialize(self) -> None:
        """Initialize spaCy NLU"""
        await self._initialize_spacy()
    
    async def _initialize_spacy(self):
        """Initialize spaCy model and intent patterns"""
        try:
            spacy = safe_import('spacy')
            if spacy is None:
                raise ImportError("spaCy not available")
            
            # Try to load the specified model
            try:
                self.nlp = spacy.load(self.model_name)
                logger.info(f"Loaded spaCy model: {self.model_name}")
            except OSError:
                logger.warning(f"Model {self.model_name} not found, trying fallback {self.fallback_model}")
                try:
                    self.nlp = spacy.load(self.fallback_model)
                    logger.info(f"Loaded fallback spaCy model: {self.fallback_model}")
                except OSError:
                    logger.error("No spaCy models available")
                    raise RuntimeError("No spaCy models found. Install with: python -m spacy download ru_core_news_sm")
            
            # Initialize intent patterns for semantic matching
            await self._initialize_intent_patterns()
            
            logger.info("spaCy NLU initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize spaCy NLU: {e}")
            self.nlp = None
            raise
    
    async def _initialize_intent_patterns(self):
        """Initialize intent patterns with semantic examples"""
        # These are semantic examples that spaCy can use for similarity matching
        self.intent_patterns = {
            "greeting.hello": [
                "привет как дела",
                "здравствуйте добро пожаловать",
                "приветствую рада видеть",
                "hello how are you",
                "hi there good morning"
            ],
            
            "greeting.goodbye": [
                "пока до свидания",
                "прощай всего доброго",
                "до встречи удачи",
                "goodbye see you later",
                "bye take care"
            ],
            
            "timer.set": [
                "поставь таймер на пять минут",
                "установи будильник через час",
                "засеки время десять секунд",
                "set timer for five minutes",
                "start alarm in one hour"
            ],
            
            "timer.cancel": [
                "отмени таймер убери будильник",
                "стоп остановить время",
                "cancel timer remove alarm",
                "stop the timer"
            ],
            
            "conversation.start": [
                "давай поговорим поболтаем",
                "хочу с тобой общаться",
                "let's have a conversation",
                "I want to chat with you"
            ],
            
            "conversation.reference": [
                "что такое расскажи про",
                "объясни мне про это",
                "what is tell me about",
                "explain this to me"
            ],
            
            "system.status": [
                "как дела что нового",
                "какой статус состояние",
                "how are you doing",
                "what's your status"
            ],
            
            "datetime.current_time": [
                "сколько времени который час",
                "скажи время сейчас",
                "what time is it now",
                "tell me the current time"
            ]
        }
        
        # Pre-process pattern documents for faster similarity matching
        self.pattern_docs = {}
        for intent, patterns in self.intent_patterns.items():
            self.pattern_docs[intent] = [self.nlp(pattern) for pattern in patterns]
    
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        """
        Recognize intent using spaCy's NLP capabilities.
        
        Args:
            text: Input text to classify
            context: Conversation context
            
        Returns:
            Intent with classification result
        """
        if not self.nlp:
            await self._initialize_spacy()
        
        if not self.nlp:
            # Fallback to basic intent if spaCy unavailable
            return Intent(
                name="conversation.general",
                entities={},
                confidence=0.5,
                raw_text=text,
                domain="conversation",
                action="general",
                session_id=context.session_id
            )
        
        # Process text with spaCy
        doc = self.nlp(text)
        
        # Extract entities
        entities = self._extract_spacy_entities(doc)
        
        # Classify intent using semantic similarity
        intent_name, confidence = await self._classify_intent_similarity(doc)
        
        # Parse domain and action
        domain, action = self._parse_intent_name(intent_name)
        
        # Enhance entities with domain-specific extraction
        entities.update(self._extract_domain_entities(doc, domain))
        
        return Intent(
            name=intent_name,
            entities=entities,
            confidence=confidence,
            raw_text=text,
            domain=domain,
            action=action,
            session_id=context.session_id
        )
    
    def _extract_spacy_entities(self, doc) -> Dict[str, Any]:
        """Extract named entities using spaCy"""
        entities = {}
        
        # Extract named entities
        for ent in doc.ents:
            if ent.label_ in self.entity_types:
                entity_key = ent.label_.lower()
                if entity_key not in entities:
                    entities[entity_key] = []
                entities[entity_key].append({
                    "text": ent.text,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "confidence": getattr(ent, 'score', 1.0)
                })
        
        # Extract numbers
        numbers = []
        for token in doc:
            if token.like_num:
                try:
                    numbers.append(float(token.text))
                except ValueError:
                    pass
        
        if numbers:
            entities["numbers"] = numbers
        
        return entities
    
    async def _classify_intent_similarity(self, doc) -> tuple[str, float]:
        """Classify intent using semantic similarity"""
        best_intent = "conversation.general"
        best_similarity = 0.0
        
        for intent, pattern_docs in self.pattern_docs.items():
            max_similarity = 0.0
            
            for pattern_doc in pattern_docs:
                similarity = doc.similarity(pattern_doc)
                max_similarity = max(max_similarity, similarity)
            
            if max_similarity > best_similarity:
                best_similarity = max_similarity
                best_intent = intent
        
        # Convert similarity to confidence (spaCy similarity ranges 0-1)
        confidence = min(best_similarity * 1.2, 1.0)  # Slight boost for good matches
        
        # Use fallback if confidence too low
        if confidence < self.confidence_threshold:
            return "conversation.general", 0.6
        
        return best_intent, confidence
    
    def _extract_domain_entities(self, doc, domain: str) -> Dict[str, Any]:
        """Extract domain-specific entities"""
        entities = {}
        
        if domain == "timer":
            # Extract time expressions
            for token in doc:
                # Look for time units
                if token.text.lower() in ['секунд', 'сек', 'минут', 'мин', 'час', 'часа', 'часов']:
                    # Find associated number
                    for neighbor in [doc[max(0, token.i-2):token.i], doc[token.i+1:min(len(doc), token.i+3)]]:
                        for t in neighbor:
                            if t.like_num:
                                entities["duration"] = int(t.text)
                                entities["unit"] = self._normalize_time_unit(token.text.lower())
                                break
        
        elif domain == "datetime":
            # Extract temporal expressions
            time_words = []
            for token in doc:
                if token.pos_ in ['NOUN', 'ADV'] and token.text.lower() in ['сегодня', 'завтра', 'вчера', 'сейчас', 'now', 'today', 'tomorrow']:
                    time_words.append(token.text.lower())
            
            if time_words:
                entities["time_reference"] = time_words
        
        return entities
    
    def _normalize_time_unit(self, unit: str) -> str:
        """Normalize time unit to standard form"""
        unit_map = {
            'секунд': 'seconds', 'сек': 'seconds',
            'минут': 'minutes', 'мин': 'minutes',
            'час': 'hours', 'часа': 'hours', 'часов': 'hours'
        }
        return unit_map.get(unit, unit)
    
    def _parse_intent_name(self, intent_name: str) -> tuple[str, str]:
        """Parse intent name into domain and action"""
        if "." in intent_name:
            parts = intent_name.split(".", 1)
            return parts[0], parts[1]
        else:
            return "general", intent_name
    
    def get_supported_languages(self) -> List[str]:
        """Get supported languages based on loaded model"""
        if self.model_name.startswith('ru_'):
            return ['ru', 'en']
        elif self.model_name.startswith('en_'):
            return ['en', 'ru']
        else:
            return ['en']
    
    def get_supported_domains(self) -> List[str]:
        """Get supported intent domains"""
        domains = set()
        for intent_name in self.intent_patterns.keys():
            domain, _ = self._parse_intent_name(intent_name)
            domains.add(domain)
        return list(domains)
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Get parameter schema for spaCy NLU"""
        return {
            "model_name": {
                "type": "string",
                "default": "ru_core_news_sm",
                "description": "Primary spaCy model to use",
                "enum": ["ru_core_news_sm", "en_core_web_sm", "en_core_web_md", "en_core_web_lg"]
            },
            "fallback_model": {
                "type": "string", 
                "default": "en_core_web_sm",
                "description": "Fallback model if primary is unavailable"
            },
            "confidence_threshold": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.7,
                "description": "Minimum confidence for intent acceptance"
            },
            "entity_types": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["PERSON", "ORG", "GPE", "DATE", "TIME", "MONEY", "QUANTITY"],
                "description": "spaCy entity types to extract"
            }
        }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get spaCy NLU capabilities"""
        return {
            "supported_languages": self.get_supported_languages(),
            "supported_domains": self.get_supported_domains(),
            "model_name": self.model_name,
            "features": {
                "semantic_similarity": True,
                "named_entity_recognition": True,
                "pos_tagging": True,
                "dependency_parsing": True,
                "multilingual": True,
                "context_aware": True,
                "machine_learning": True
            }
        }
    
    def validate_config(self) -> bool:
        """Validate spaCy NLU configuration"""
        if not 0.0 <= self.confidence_threshold <= 1.0:
            self.logger.error("confidence_threshold must be between 0.0 and 1.0")
            return False
        
        if not isinstance(self.entity_types, list):
            self.logger.error("entity_types must be a list")
            return False
        
        return True
    
    async def cleanup(self) -> None:
        """Clean up spaCy NLU resources"""
        if self.nlp:
            # spaCy models don't need explicit cleanup
            self.nlp = None
        self.intent_patterns.clear()
        self.pattern_docs.clear()
        logger.info("spaCy NLU cleaned up") 