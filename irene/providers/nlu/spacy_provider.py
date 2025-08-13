"""
spaCy NLU Provider

Advanced NLU provider using spaCy for intent classification and entity extraction.
Provides more sophisticated natural language understanding than rule-based approach.
"""

import logging
from typing import Dict, Any, List, Optional

from .base import NLUProvider
from ...intents.models import Intent, ConversationContext
from ...utils.loader import safe_import

logger = logging.getLogger(__name__)


class SpaCyNLUProvider(NLUProvider):
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
        self.asset_manager = None
        
    def get_provider_name(self) -> str:
        return "spacy_nlu"
    
    async def is_available(self) -> bool:
        """Check if spaCy is available, models can be loaded, and patterns are loaded from JSON donations"""
        try:
            spacy = safe_import('spacy')
            if spacy is None:
                self._set_status(self.status.__class__.UNAVAILABLE, "spaCy package not installed")
                return False
            
            if not self.nlp:
                if self.asset_manager:
                    await self._initialize_spacy_with_assets()
                else:
                    await self._initialize_spacy()
            
            # Phase 4: Also check that intent patterns are loaded from JSON donations
            return self.nlp is not None and len(self.intent_patterns) > 0
            
        except Exception as e:
            self._set_status(self.status.__class__.ERROR, f"spaCy NLU initialization failed: {e}")
            return False
    
    async def _do_initialize(self) -> None:
        """Initialize spaCy NLU with asset management"""
        # Get asset manager
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Initialize spaCy with asset management
        await self._initialize_spacy_with_assets()
    
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
    
    async def _initialize_spacy_with_assets(self):
        """Initialize spaCy model using asset management system"""
        try:
            spacy = safe_import('spacy')
            if spacy is None:
                raise ImportError("spaCy not available")
            
            # Try to ensure model is available through asset manager
            if self.asset_manager:
                try:
                    model_path = await self.asset_manager.ensure_model_available(
                        provider_name="spacy",
                        model_name=self.model_name,
                        asset_config=self.get_asset_config()
                    )
                    
                    if model_path:
                        logger.info(f"Asset manager ensured spaCy model: {self.model_name} -> {model_path}")
                        # For spaCy models, the asset manager handles installation
                        # We don't need to install wheel files manually
                    else:
                        logger.warning(f"Asset manager could not ensure model: {self.model_name}")
                        
                except Exception as e:
                    logger.warning(f"Asset manager failed to provide model {self.model_name}: {e}")
                    # Fall back to standard loading
            
            # Try to load the specified model
            try:
                self.nlp = spacy.load(self.model_name)
                logger.info(f"Loaded spaCy model: {self.model_name}")
            except OSError:
                logger.warning(f"Model {self.model_name} not found, trying fallback {self.fallback_model}")
                try:
                    # Try asset manager for fallback model
                    if self.asset_manager:
                        try:
                            fallback_path = await self.asset_manager.ensure_model_available(
                                provider_name="spacy",
                                model_name=self.fallback_model,
                                asset_config=self.get_asset_config()
                            )
                            
                            if fallback_path:
                                logger.info(f"Asset manager ensured fallback spaCy model: {self.fallback_model} -> {fallback_path}")
                            else:
                                logger.warning(f"Asset manager could not ensure fallback model: {self.fallback_model}")
                        except Exception as e:
                            logger.warning(f"Asset manager failed to provide fallback model {self.fallback_model}: {e}")
                    
                    self.nlp = spacy.load(self.fallback_model)
                    logger.info(f"Loaded fallback spaCy model: {self.fallback_model}")
                except OSError:
                    logger.error("No spaCy models available")
                    raise RuntimeError("No spaCy models found. Install with: python -m spacy download ru_core_news_sm")
            
            # Initialize intent patterns for semantic matching
            await self._initialize_intent_patterns()
            
            logger.info("spaCy NLU initialized successfully with asset management")
            
        except Exception as e:
            logger.error(f"Failed to initialize spaCy NLU with assets: {e}")
            self.nlp = None
            raise
    
    async def _install_spacy_model(self, model_path: str):
        """Install spaCy model from wheel file using pip"""
        import subprocess
        import sys
        
        try:
            logger.info(f"Installing spaCy model from: {model_path}")
            cmd = [sys.executable, "-m", "pip", "install", model_path, "--no-deps", "--force-reinstall"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to install spaCy model: {result.stderr}")
            
            logger.info(f"Successfully installed spaCy model: {model_path}")
            
        except Exception as e:
            logger.error(f"Error installing spaCy model {model_path}: {e}")
            raise
    
    async def _initialize_from_donations(self, keyword_donations: List[Any]) -> None:
        """
        Initialize provider with JSON donation patterns (Phase 2 integration).
        
        This replaces hardcoded patterns with donation-driven patterns.
        """
        try:
            logger.info(f"Initializing SpaCyNLU with {len(keyword_donations)} donations")
            
            # Clear existing hardcoded patterns
            self.intent_patterns = {}
            
            # Convert keyword donations to semantic examples for spaCy
            for donation in keyword_donations:
                intent_name = donation.intent_name
                
                # Use donation phrases as semantic examples
                semantic_examples = []
                
                # Add original phrases
                semantic_examples.extend(donation.phrases)
                
                # Add training examples if available
                if hasattr(donation, 'training_examples'):
                    for example in donation.training_examples:
                        if hasattr(example, 'text'):
                            semantic_examples.append(example.text)
                
                # Store patterns for spaCy semantic matching
                self.intent_patterns[intent_name] = semantic_examples
                
                logger.debug(f"Added {len(semantic_examples)} semantic examples for intent '{intent_name}'")
            
            logger.info(f"SpaCyNLU initialized with donation patterns for {len(self.intent_patterns)} intents")
            
        except Exception as e:
            logger.error(f"Failed to initialize SpaCyNLU from donations: {e}")
            # Phase 4: No fallback patterns - fail fast
            raise RuntimeError(f"SpaCyNLUProvider: JSON donation initialization failed: {e}. "
                             "Provider cannot operate without valid donations.")
    

    
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
            if self.asset_manager:
                await self._initialize_spacy_with_assets()
            else:
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
    
    async def extract_entities(self, text: str, intent_name: str) -> Dict[str, Any]:
        """Extract entities for a given intent using spaCy NLP"""
        if not self.nlp:
            return {}
        
        # Process text with spaCy
        doc = self.nlp(text)
        
        # Extract entities using spaCy
        entities = self._extract_spacy_entities(doc)
        
        # Parse domain and action from intent name
        domain, action = self._parse_intent_name(intent_name)
        
        # Add domain-specific entity extraction
        entities.update(self._extract_domain_entities(doc, domain))
        
        return entities
    
    def get_supported_intents(self) -> List[str]:
        """Return list of intents this provider can recognize"""
        return list(self.intent_patterns.keys())
    
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
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """spaCy NLU uses wheel files for model distribution"""
        return ".whl"
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """spaCy NLU models directory"""
        return "spacy"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """spaCy NLU doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """spaCy NLU uses models and runtime cache"""
        return ["models", "runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """spaCy NLU model URLs - updated for asset management integration"""
        return {
            "ru_core_news_sm": "https://github.com/explosion/spacy-models/releases/download/ru_core_news_sm-3.7.0/ru_core_news_sm-3.7.0-py3-none-any.whl",
            "ru_core_news_md": "https://github.com/explosion/spacy-models/releases/download/ru_core_news_md-3.7.0/ru_core_news_md-3.7.0-py3-none-any.whl",
            "ru_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/ru_core_news_lg-3.7.0/ru_core_news_lg-3.7.0-py3-none-any.whl",
            "en_core_web_sm": "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0-py3-none-any.whl",
            "en_core_web_md": "https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.7.0/en_core_web_md-3.7.0-py3-none-any.whl",
            "en_core_web_lg": "https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.0/en_core_web_lg-3.7.0-py3-none-any.whl"
        }
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """spaCy NLU requires spacy library and models"""
        return ["spacy>=3.4.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """spaCy NLU system dependencies for Cython/C++ compilation"""
        return {
            "linux.ubuntu": ["build-essential", "python3-dev"],
            "linux.alpine": ["build-base", "python3-dev"],
            "macos": [],  # Xcode Command Line Tools provide build tools
            "windows": []  # Windows build tools handled differently
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """spaCy NLU supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    async def process_intent(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Process text for intent recognition using spaCy NLP pipeline.
        
        Args:
            text: Input text to analyze
            **kwargs: Additional processing parameters
            
        Returns:
            Intent analysis results
        """
        return await self.extract_intent(text) 