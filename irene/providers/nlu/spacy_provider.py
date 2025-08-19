"""
spaCy NLU Provider

Advanced NLU provider using spaCy for intent classification and entity extraction.
Provides more sophisticated natural language understanding than rule-based approach.
"""

import logging
import hashlib
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

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
        
        # Pattern storage for semantic matching
        self.intent_patterns: Dict[str, List[str]] = {}  # intent -> example strings
        self.pattern_docs: Dict[str, List[Any]] = {}     # intent -> spaCy Doc objects
        self.intent_centroids: Dict[str, np.ndarray] = {} # intent -> vector centroids
        
        # Fast matching components
        self.phrase_matcher = None
        self.entity_ruler = None
        
        # Asset management for caching
        self.asset_manager = None
        self._donations_hash = None
        
        # Telemetry and versioning
        self._donation_versions = []
        self._handler_domains = []
        self._spacy_model_version = None
        
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
            
            # Check that intent patterns and compiled artifacts are loaded
            return (self.nlp is not None and 
                   len(self.intent_patterns) > 0 and 
                   len(self.pattern_docs) > 0)
            
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
                
                # Capture model version for cache validation
                if hasattr(self.nlp, 'meta') and 'version' in self.nlp.meta:
                    self._spacy_model_version = self.nlp.meta['version']
                else:
                    # Fallback to spaCy library version
                    self._spacy_model_version = spacy.__version__
                
                logger.info(f"Loaded spaCy model: {self.model_name} (version: {self._spacy_model_version})")
            except OSError:
                logger.warning(f"Model {self.model_name} not found, trying fallback {self.fallback_model}")
                try:
                    self.nlp = spacy.load(self.fallback_model)
                    
                    # Capture fallback model version
                    if hasattr(self.nlp, 'meta') and 'version' in self.nlp.meta:
                        self._spacy_model_version = self.nlp.meta['version']
                    else:
                        self._spacy_model_version = spacy.__version__
                    
                    logger.info(f"Loaded fallback spaCy model: {self.fallback_model} (version: {self._spacy_model_version})")
                except OSError:
                    logger.error("No spaCy models available")
                    raise RuntimeError("No spaCy models found. Install with: python -m spacy download ru_core_news_sm")
            
            # Initialize intent patterns if donations are available
            if len(self.intent_patterns) > 0:
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
                
                # Capture model version for cache validation
                if hasattr(self.nlp, 'meta') and 'version' in self.nlp.meta:
                    self._spacy_model_version = self.nlp.meta['version']
                else:
                    # Fallback to spaCy library version
                    self._spacy_model_version = spacy.__version__
                
                logger.info(f"Loaded spaCy model: {self.model_name} (version: {self._spacy_model_version})")
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
                    
                    # Capture fallback model version
                    if hasattr(self.nlp, 'meta') and 'version' in self.nlp.meta:
                        self._spacy_model_version = self.nlp.meta['version']
                    else:
                        self._spacy_model_version = spacy.__version__
                    
                    logger.info(f"Loaded fallback spaCy model: {self.fallback_model} (version: {self._spacy_model_version})")
                except OSError:
                    logger.error("No spaCy models available")
                    raise RuntimeError("No spaCy models found. Install with: python -m spacy download ru_core_news_sm")
            
            # Initialize intent patterns if donations are available
            if len(self.intent_patterns) > 0:
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
            
            # Calculate donations hash for caching (including version information)
            donations_data = []
            donation_versions = set()
            handler_domains = set()
            
            for d in keyword_donations:
                donation_versions.add(getattr(d, 'donation_version', '1.0'))
                handler_domains.add(getattr(d, 'handler_domain', 'unknown'))
                donations_data.append((d.intent_name, sorted(d.phrases), getattr(d, 'donation_version', '1.0')))
            
            # Create comprehensive hash including versions
            donations_str = str(sorted(donations_data))
            self._donations_hash = hashlib.md5(donations_str.encode()).hexdigest()[:8]
            
            # Store telemetry data
            self._donation_versions = sorted(donation_versions)
            self._handler_domains = sorted(handler_domains)
            
            logger.info(f"Donation telemetry - Versions: {self._donation_versions}, Domains: {self._handler_domains}")
            
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
            
            # Initialize pattern docs and other compiled artifacts if spaCy is loaded
            if self.nlp is not None:
                await self._initialize_intent_patterns()
            
            logger.info(f"SpaCyNLU initialized with donation patterns for {len(self.intent_patterns)} intents")
            
        except Exception as e:
            logger.error(f"Failed to initialize SpaCyNLU from donations: {e}")
            # Phase 4: No fallback patterns - fail fast
            raise RuntimeError(f"SpaCyNLUProvider: JSON donation initialization failed: {e}. "
                             "Provider cannot operate without valid donations.")
    
    async def _initialize_intent_patterns(self) -> None:
        """
        Initialize spaCy-specific artifacts from intent patterns.
        
        Builds:
        - pattern_docs: Doc objects for similarity matching
        - intent_centroids: Vector centroids for fast similarity
        - phrase_matcher: Fast phrase matching
        - entity_ruler: Enhanced entity extraction
        """
        if not self.nlp or not self.intent_patterns:
            logger.warning("Cannot initialize patterns: spaCy not loaded or no patterns available")
            return
        
        try:
            # Check if we can load from cache
            if self.asset_manager and await self._try_load_cached_artifacts():
                logger.info("Loaded spaCy artifacts from cache")
                return
            
            logger.info("Building spaCy artifacts from donations...")
            
            # Import spaCy components
            spacy = safe_import('spacy')
            if spacy is None:
                raise ImportError("spaCy not available")
            
            # Clear existing artifacts
            self.pattern_docs = {}
            self.intent_centroids = {}
            
            # Build pattern docs and centroids for each intent
            all_phrases_for_matcher = []
            phrase_to_intent = {}
            
            for intent_name, examples in self.intent_patterns.items():
                if not examples:
                    continue
                
                # Create Doc objects using nlp.pipe for efficiency
                docs = list(self.nlp.pipe(examples))
                self.pattern_docs[intent_name] = docs
                
                # Compute centroid if model has vectors
                if self.nlp.vocab.vectors.size > 0:
                    vectors = []
                    for doc in docs:
                        if doc.has_vector:
                            vectors.append(doc.vector)
                    
                    if vectors:
                        centroid = np.mean(vectors, axis=0)
                        self.intent_centroids[intent_name] = centroid
                
                # Collect phrases for PhraseMatcher
                for phrase in examples:
                    normalized = phrase.lower().strip()
                    if normalized:
                        all_phrases_for_matcher.append(normalized)
                        phrase_to_intent[normalized] = intent_name
            
            # Build PhraseMatcher for fast phrase matching
            if all_phrases_for_matcher:
                try:
                    phrase_patterns = list(self.nlp.pipe(all_phrases_for_matcher))
                    self.phrase_matcher = spacy.matcher.PhraseMatcher(self.nlp.vocab, attr="LOWER")
                    
                    # Add patterns grouped by intent
                    for intent_name in self.intent_patterns.keys():
                        intent_patterns = [doc for phrase, doc in zip(all_phrases_for_matcher, phrase_patterns) 
                                         if phrase_to_intent.get(phrase) == intent_name]
                        if intent_patterns:
                            self.phrase_matcher.add(intent_name, intent_patterns)
                    
                    logger.info(f"Built PhraseMatcher with {len(all_phrases_for_matcher)} phrases")
                except Exception as e:
                    logger.warning(f"Failed to build PhraseMatcher: {e}")
                    self.phrase_matcher = None
            
            # Build EntityRuler for enhanced entity extraction
            try:
                self.entity_ruler = self.nlp.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": True})
                # Add any domain-specific entity patterns here if needed
                logger.info("Added EntityRuler to pipeline")
            except Exception as e:
                logger.warning(f"Failed to add EntityRuler: {e}")
                self.entity_ruler = None
            
            # Cache artifacts if asset manager available
            if self.asset_manager:
                await self._cache_artifacts()
            
            logger.info(f"Successfully initialized spaCy artifacts for {len(self.pattern_docs)} intents")
            
        except Exception as e:
            logger.error(f"Failed to initialize intent patterns: {e}")
            # Clear partial state
            self.pattern_docs = {}
            self.intent_centroids = {}
            self.phrase_matcher = None
            self.entity_ruler = None
            raise

    async def _try_load_cached_artifacts(self) -> bool:
        """Try to load cached spaCy artifacts from asset manager"""
        if not self.asset_manager or not self._donations_hash:
            return False
        
        try:
            # Create cache key based on model, model version, and donations
            model_version = self._spacy_model_version or "unknown"
            cache_key = f"spacy_artifacts_{self.model_name}_{model_version}_{self._donations_hash}"
            
            # Try to load cached artifacts from spaCy cache directory
            cached_data = await self.asset_manager.get_cached_data(cache_key, provider_name="spacy")
            if not cached_data:
                return False
            
            # Validate cache against current model version
            if cached_data.get('model_version') != self._spacy_model_version:
                logger.info(f"Cache invalidated: model version mismatch ({cached_data.get('model_version')} != {self._spacy_model_version})")
                return False
            
            # Restore artifacts from cache using DocBin for efficient deserialization
            await self._restore_artifacts_from_cache(cached_data)
            
            # Note: PhraseMatcher and EntityRuler need to be rebuilt as they can't be easily serialized
            return len(self.pattern_docs) > 0
            
        except Exception as e:
            logger.warning(f"Failed to load cached artifacts: {e}")
            return False
    
    async def _restore_artifacts_from_cache(self, cached_data: Dict[str, Any]) -> None:
        """Restore spaCy artifacts from cached data using DocBin"""
        spacy = safe_import('spacy')
        if spacy is None:
            raise ImportError("spaCy not available for cache restoration")
        
        # Restore intent centroids (simple numpy arrays)
        self.intent_centroids = cached_data.get('intent_centroids', {})
        
        # Restore pattern docs using DocBin for efficient deserialization
        docbin_data = cached_data.get('pattern_docs_docbin')
        if docbin_data and self.nlp:
            try:
                # Import DocBin
                from spacy.tokens import DocBin
                
                # Deserialize DocBin
                docbin = DocBin().from_bytes(docbin_data)
                docs = list(docbin.get_docs(self.nlp.vocab))
                
                # Reconstruct pattern_docs mapping
                intent_doc_counts = cached_data.get('intent_doc_counts', {})
                self.pattern_docs = {}
                
                doc_idx = 0
                for intent_name, doc_count in intent_doc_counts.items():
                    self.pattern_docs[intent_name] = docs[doc_idx:doc_idx + doc_count]
                    doc_idx += doc_count
                
                logger.debug(f"Restored {len(docs)} pattern docs for {len(self.pattern_docs)} intents from DocBin")
                
            except Exception as e:
                logger.warning(f"Failed to restore pattern docs from DocBin: {e}")
                self.pattern_docs = {}
        else:
            # Fallback to direct deserialization (less efficient)
            self.pattern_docs = cached_data.get('pattern_docs', {})
    
    async def _serialize_pattern_docs(self) -> Tuple[Optional[bytes], Dict[str, int]]:
        """Serialize pattern docs using DocBin for efficient storage"""
        if not self.pattern_docs or not self.nlp:
            return None, {}
        
        try:
            spacy = safe_import('spacy')
            if spacy is None:
                raise ImportError("spaCy not available")
            
            # Import DocBin
            from spacy.tokens import DocBin
            
            # Create DocBin and collect all docs
            docbin = DocBin(attrs=["LEMMA", "POS", "TAG", "DEP", "ENT_IOB", "ENT_TYPE"])
            intent_doc_counts = {}
            
            for intent_name, docs in self.pattern_docs.items():
                intent_doc_counts[intent_name] = len(docs)
                for doc in docs:
                    docbin.add(doc)
            
            # Serialize to bytes
            docbin_data = docbin.to_bytes()
            
            logger.debug(f"Serialized {sum(intent_doc_counts.values())} docs to DocBin ({len(docbin_data)} bytes)")
            return docbin_data, intent_doc_counts
            
        except Exception as e:
            logger.warning(f"Failed to serialize pattern docs with DocBin: {e}")
            return None, {}
    
    async def _cache_artifacts(self) -> None:
        """Cache compiled spaCy artifacts to asset manager"""
        if not self.asset_manager or not self._donations_hash:
            return
        
        try:
            # Create cache key based on model, model version, and donations
            model_version = self._spacy_model_version or "unknown"
            cache_key = f"spacy_artifacts_{self.model_name}_{model_version}_{self._donations_hash}"
            
            # Serialize pattern docs using DocBin for efficiency
            pattern_docs_docbin, intent_doc_counts = await self._serialize_pattern_docs()
            
            # Prepare data for caching with telemetry
            cache_data = {
                'pattern_docs_docbin': pattern_docs_docbin,
                'intent_doc_counts': intent_doc_counts,
                'intent_centroids': self.intent_centroids,
                'model_name': self.model_name,
                'model_version': self._spacy_model_version,
                'donations_hash': self._donations_hash,
                'donation_versions': self._donation_versions,
                'handler_domains': self._handler_domains,
                'cached_at': datetime.now().isoformat()
            }
            
            # Store in spaCy cache directory
            await self.asset_manager.set_cached_data(cache_key, cache_data, provider_name="spacy")
            logger.info(f"Cached spaCy artifacts with key: {cache_key}")
            
            # Telemetry logging
            logger.info(f"spaCy asset cache telemetry - Model: {self.model_name} v{model_version}, "
                       f"Donations: {len(self._donation_versions)} versions from {len(self._handler_domains)} domains, "
                       f"Artifacts: {len(self.pattern_docs)} intents, {len(self.intent_centroids)} centroids")
            
        except Exception as e:
            logger.warning(f"Failed to cache artifacts: {e}")
    
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
    
    async def _classify_intent_similarity(self, doc) -> Tuple[str, float]:
        """Classify intent using enhanced semantic similarity with centroids and separation"""
        if not self.pattern_docs:
            return "conversation.general", 0.6
        
        # Check for phrase matcher hits first (fast path)
        phrase_boost = 0.0
        phrase_intent = None
        if self.phrase_matcher:
            matches = self.phrase_matcher(doc)
            if matches:
                # Get the first match intent
                match_id, start, end = matches[0]
                phrase_intent = self.nlp.vocab.strings[match_id]
                phrase_boost = 1.0
        
        # Calculate similarities for all intents
        intent_scores = {}
        
        for intent_name, pattern_docs in self.pattern_docs.items():
            # Doc-level similarity (best match against examples)
            doc_similarities = [doc.similarity(pattern_doc) for pattern_doc in pattern_docs]
            s_doc = max(doc_similarities) if doc_similarities else 0.0
            
            # Centroid similarity (if available)
            s_centroid = 0.0
            if intent_name in self.intent_centroids and doc.has_vector:
                centroid = self.intent_centroids[intent_name]
                s_centroid = np.dot(doc.vector, centroid) / (np.linalg.norm(doc.vector) * np.linalg.norm(centroid))
                s_centroid = max(0.0, s_centroid)  # Ensure non-negative
            
            # Phrase matcher boost
            m_phrase = phrase_boost if phrase_intent == intent_name else 0.0
            
            # Combined score
            score = 0.55 * s_doc + 0.25 * s_centroid + 0.05 * m_phrase
            intent_scores[intent_name] = score
        
        # Find best and second-best scores
        sorted_scores = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        
        if not sorted_scores:
            return "conversation.general", 0.6
        
        best_intent, best_score = sorted_scores[0]
        second_best_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
        
        # Add separation bonus (reduces overconfidence when intents are close)
        separation = max(0, best_score - second_best_score)
        
        # Entity alignment (basic implementation - can be enhanced)
        e_align = 0.5  # Default neutral value
        
        # Final confidence calculation
        confidence = 0.7 * (best_score + 0.15 * separation) + 0.3 * e_align
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        
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
        if self.nlp is not None:
            # Use actual model language if available
            primary_lang = getattr(self.nlp, 'lang', 'en')
            if primary_lang == 'ru':
                return ['ru', 'en']
            elif primary_lang == 'en':
                return ['en', 'ru']
            else:
                return [primary_lang, 'en']
        else:
            # Fallback to model name parsing
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
        self.intent_centroids.clear()
        self.phrase_matcher = None
        self.entity_ruler = None
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
        """spaCy NLU requires spacy library and specific model"""
        return [
            "spacy>=3.7.0",
            "numpy>=1.20.0",  # For centroids and vector operations
            "ru_core_news_sm @ https://github.com/explosion/spacy-models/releases/download/ru_core_news_sm-3.7.0/ru_core_news_sm-3.7.0-py3-none-any.whl"
        ]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """spaCy NLU system dependencies - minimal for wheel installations"""
        return {
            "linux.ubuntu": [],  # No build tools needed with prebuilt wheels
            "linux.alpine": ["build-base", "python3-dev"],  # Alpine needs build tools
            "macos": [],  # Prebuilt wheels available
            "windows": []  # Prebuilt wheels available
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
        from ...intents.models import ConversationContext
        context = kwargs.get('context', ConversationContext())
        intent = await self.recognize(text, context)
        
        return {
            'intent_name': intent.name,
            'entities': intent.entities,
            'confidence': intent.confidence,
            'domain': intent.domain,
            'action': intent.action
        } 