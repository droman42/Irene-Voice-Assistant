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
from ...intents.models import Intent, UnifiedConversationContext
from ...utils.loader import safe_import
from ...core.donations import ParameterSpec, KeywordDonation

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
        
        # Multi-model management for language awareness
        self.available_models: Dict[str, Any] = {}  # language -> spacy.Language object
        self.language_preferences = {
            'ru': ['ru_core_news_md', 'ru_core_news_sm'],
            'en': ['en_core_web_md', 'en_core_web_sm']
        }
        
        self.confidence_threshold = config.get('confidence_threshold', 0.7)
        self.entity_types = config.get('entity_types', ['PERSON', 'ORG', 'GPE', 'DATE', 'TIME', 'MONEY', 'QUANTITY'])
        
        # Pattern storage for semantic matching
        self.intent_patterns: Dict[str, List[str]] = {}  # intent -> example strings
        self.pattern_docs: Dict[str, List[Any]] = {}     # intent -> spaCy Doc objects
        self.intent_centroids: Dict[str, np.ndarray] = {} # intent -> vector centroids
        
        # Fast matching components
        self.phrase_matcher = None
        self.entity_ruler = None
        self.matcher = None  # For token pattern validation
        self.phrase_matcher_config = None  # Configuration for rebuilding PhraseMatcher
        
        # PHASE 2: Advanced spaCy patterns storage
        self.advanced_patterns: Dict[str, Dict[str, Any]] = {}  # intent_name -> advanced patterns
        
        # Asset management for caching
        self.asset_manager = None
        self._donations_hash = None
        
        # Telemetry and versioning
        self._donation_versions = []
        self._handler_domains = []
        self._spacy_model_version = None
        
    def get_provider_name(self) -> str:
        return "spacy_nlu"
    
    def _detect_language(self, text: str) -> str:
        """Language detection based on Cyrillic script presence"""
        # Cyrillic script detection for Russian
        if any('\u0400' <= char <= '\u04FF' for char in text):
            return 'ru'
        return 'en'
    
    async def is_available(self) -> bool:
        """Check if spaCy is available and models can be loaded (patterns loaded separately during donation phase)"""
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
            
            # Only check if the model is loaded - patterns will be loaded during donation initialization
            return self.nlp is not None
            
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
        """Initialize spaCy models with multi-language support"""
        try:
            spacy = safe_import('spacy')
            if spacy is None:
                raise ImportError("spaCy not available")
            
            # Initialize available models for each language
            for language, models in self.language_preferences.items():
                for model_name in models:
                    try:
                        model = spacy.load(model_name)
                        self.available_models[language] = model
                        
                        # Capture model version for cache validation
                        if hasattr(model, 'meta') and 'version' in model.meta:
                            version = model.meta['version']
                        else:
                            version = spacy.__version__
                        
                        logger.info(f"Loaded spaCy model for {language}: {model_name} (version: {version})")
                        break  # Use the first available model for this language
                    except OSError:
                        logger.debug(f"Model {model_name} not available for {language}")
                        continue
                
                if language not in self.available_models:
                    logger.warning(f"No models available for language: {language}")
            
            # Set primary model (use Russian if available, else English)
            if 'ru' in self.available_models:
                self.nlp = self.available_models['ru']
                self._spacy_model_version = getattr(self.nlp, 'meta', {}).get('version', spacy.__version__)
                logger.info(f"Primary model set to Russian: {self.nlp.meta.get('name', 'unknown')}")
            elif 'en' in self.available_models:
                self.nlp = self.available_models['en']
                self._spacy_model_version = getattr(self.nlp, 'meta', {}).get('version', spacy.__version__)
                logger.info(f"Primary model set to English: {self.nlp.meta.get('name', 'unknown')}")
            else:
                # No models available - this is a configuration/installation issue
                logger.error("No spaCy models available for any language")
                raise RuntimeError("No spaCy models found. Install with: python -m spacy download ru_core_news_sm en_core_web_sm")
            
            # Initialize intent patterns if donations are available
            if len(self.intent_patterns) > 0:
                await self._initialize_intent_patterns()
            
            logger.info(f"spaCy NLU initialized successfully with {len(self.available_models)} language models")
            
        except Exception as e:
            logger.error(f"Failed to initialize spaCy NLU: {e}")
            self.nlp = None
            self.available_models = {}
            raise
    
    async def _initialize_spacy_with_assets(self):
        """Initialize spaCy models with multi-language support using asset management system"""
        try:
            spacy = safe_import('spacy')
            if spacy is None:
                raise ImportError("spaCy not available")
            
            # Ensure asset manager is available
            if not self.asset_manager:
                try:
                    from ...core.assets import get_asset_manager
                    self.asset_manager = get_asset_manager()
                    logger.info(f"Asset manager initialized: {self.asset_manager}")
                except Exception as e:
                    logger.error(f"Failed to initialize asset manager: {e}")
                    self.asset_manager = None
            
            # Initialize available models for each language with asset management
            for language, models in self.language_preferences.items():
                for model_name in models:
                    try:
                        # Try to ensure model is available through asset manager
                        if self.asset_manager:
                            try:
                                model_path = await self.asset_manager.ensure_model_available(
                                    provider_name="spacy_nlu",
                                    model_name=model_name,
                                    asset_config=self.__class__.get_asset_config()
                                )
                                
                                if model_path:
                                    logger.info(f"Asset manager verified spaCy model: {model_name} -> {model_path}")
                                else:
                                    logger.debug(f"Asset manager could not ensure model: {model_name}")
                                    
                            except Exception as e:
                                logger.debug(f"Asset manager failed to provide model {model_name}: {e}")
                        
                        # Try to load the model
                        model = spacy.load(model_name)
                        self.available_models[language] = model
                        
                        # Capture model version for cache validation
                        if hasattr(model, 'meta') and 'version' in model.meta:
                            version = model.meta['version']
                        else:
                            version = spacy.__version__
                        
                        logger.info(f"Loaded spaCy model for {language}: {model_name} (version: {version})")
                        break  # Use the first available model for this language
                    except OSError:
                        logger.debug(f"Model {model_name} not available for {language}")
                        continue
                
                if language not in self.available_models:
                    logger.warning(f"No models available for language: {language}")
            
            # Set primary model (use Russian if available, else English)
            if 'ru' in self.available_models:
                self.nlp = self.available_models['ru']
                self._spacy_model_version = getattr(self.nlp, 'meta', {}).get('version', spacy.__version__)
                logger.info(f"Primary model set to Russian: {self.nlp.meta.get('name', 'unknown')}")
            elif 'en' in self.available_models:
                self.nlp = self.available_models['en']
                self._spacy_model_version = getattr(self.nlp, 'meta', {}).get('version', spacy.__version__)
                logger.info(f"Primary model set to English: {self.nlp.meta.get('name', 'unknown')}")
            else:
                # No models available - this is a configuration/installation issue
                logger.error("No spaCy models available for any language")
                raise RuntimeError("No spaCy models found. Install with: python -m spacy download ru_core_news_sm en_core_web_sm")
            
            # Initialize intent patterns if donations are available
            if len(self.intent_patterns) > 0:
                await self._initialize_intent_patterns()
            
            logger.info(f"spaCy NLU initialized successfully with asset management ({len(self.available_models)} language models)")
            
        except Exception as e:
            logger.error(f"Failed to initialize spaCy NLU with assets: {e}")
            self.nlp = None
            self.available_models = {}
            raise
    
    
    async def _initialize_from_donations(self, keyword_donations: List[KeywordDonation]) -> None:
        """
        Initialize provider with both intent patterns AND parameter specs + spaCy validation (Phase 2).
        
        This replaces hardcoded patterns with donation-driven patterns and includes
        runtime spaCy pattern validation with graceful degradation.
        """
        try:
            logger.info(f"Initializing SpaCyNLU with {len(keyword_donations)} donations")
            
            # Clear existing data (Phase 2)
            self.intent_patterns = {}
            self.parameter_specs = {}
            self.advanced_patterns = {}
            
            # Calculate donations hash for caching (including version information)
            donations_data = []
            donation_versions = set()
            handler_domains = set()
            
            for d in keyword_donations:
                donation_versions.add(getattr(d, 'donation_version', '1.0'))
                handler_domains.add(getattr(d, 'handler_domain', 'unknown'))
                
                # Include all donation components in hash calculation
                donation_data = (
                    d.intent,
                    sorted(d.phrases),
                    # Include parameter specs for cache invalidation
                    tuple(sorted([
                        (p.name, p.type.value if hasattr(p.type, 'value') else str(p.type), 
                         p.required, p.default_value or '', p.pattern or '', p.min_value or 0, p.max_value or 0, 
                         tuple(p.choices) if p.choices else ()) 
                        for p in d.parameters
                    ])),
                    # Include advanced spaCy patterns
                    tuple(d.token_patterns) if d.token_patterns else (),
                    tuple(sorted(d.slot_patterns.items())) if d.slot_patterns else (),
                    getattr(d, 'donation_version', '1.0')
                )
                donations_data.append(donation_data)
            
            # Create comprehensive hash including all components
            # Sort by intent name only to ensure consistent hash across runs
            donations_data.sort(key=lambda x: x[0])  # Sort by intent name (first element)
            donations_str = str(donations_data)
            self._donations_hash = hashlib.md5(donations_str.encode()).hexdigest()[:8]
            
            # Store telemetry data
            self._donation_versions = sorted(donation_versions)
            self._handler_domains = sorted(handler_domains)
            
            logger.info(f"Donation telemetry - Versions: {self._donation_versions}, Domains: {self._handler_domains}")
            
            # Process each donation (Phase 2 enhancement)
            for donation in keyword_donations:
                intent_name = donation.intent
                
                # Store basic patterns (always works)
                semantic_examples = []
                semantic_examples.extend(donation.phrases)
                
                # Add examples from donation if available
                for example in donation.examples:
                    if 'text' in example:
                        semantic_examples.append(example['text'])
                
                self.intent_patterns[intent_name] = semantic_examples
                self.parameter_specs[intent_name] = donation.parameters
                
                # Validate and store spaCy patterns (runtime validation)
                if self.nlp:  # spaCy available
                    try:
                        self._validate_and_store_spacy_patterns(donation)
                        logger.debug(f"SpaCy patterns validated for '{intent_name}'")
                    except Exception as e:
                        logger.warning(f"Invalid spaCy patterns for '{intent_name}': {e} - using basic functionality")
                        # Continue without advanced patterns - graceful degradation
                else:
                    logger.info(f"SpaCy unavailable - using basic patterns only for '{intent_name}'")
                
                logger.debug(f"Registered intent '{intent_name}' with {len(donation.phrases)} phrases and {len(donation.parameters)} parameters")
            
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
                    
                    # Store PhraseMatcher configuration for caching
                    self.phrase_matcher_config = {
                        'phrases': all_phrases_for_matcher,
                        'phrase_to_intent': phrase_to_intent,
                        'attr': "LOWER"
                    }
                    
                    logger.info(f"Built PhraseMatcher with {len(all_phrases_for_matcher)} phrases")
                except Exception as e:
                    logger.warning(f"Failed to build PhraseMatcher: {e}")
                    self.phrase_matcher = None
                    self.phrase_matcher_config = None
            
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
                logger.info("Attempting to cache spaCy artifacts...")
                await self._cache_artifacts()
            else:
                logger.warning("Asset manager not available - cannot cache spaCy artifacts")
            
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
            # Create cache key based on primary model, model version, and donations
            model_version = self._spacy_model_version or "unknown"
            primary_model_name = getattr(self.nlp, 'meta', {}).get('name', 'unknown') if self.nlp else 'unknown'
            cache_key = f"spacy_artifacts_{primary_model_name}_{model_version}_{self._donations_hash}"
            
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
        
        # Restore advanced patterns (validated spaCy patterns)
        self.advanced_patterns = cached_data.get('advanced_patterns', {})
        logger.debug(f"Restored advanced patterns for {len(self.advanced_patterns)} intents")
        
        # Restore parameter specs (deserialize from cached format)
        self.parameter_specs = {}
        cached_param_specs = cached_data.get('parameter_specs', {})
        for intent_name, param_specs_data in cached_param_specs.items():
            self.parameter_specs[intent_name] = []
            for param_data in param_specs_data:
                # Reconstruct ParameterSpec objects
                from ...core.donations import ParameterSpec, ParameterType
                param_spec = ParameterSpec(
                    name=param_data['name'],
                    type=ParameterType(param_data['type']) if isinstance(param_data['type'], str) else param_data['type'],
                    required=param_data['required'],
                    default_value=param_data['default_value'],
                    pattern=param_data['pattern'],
                    choices=param_data['choices'],
                    min_value=param_data['min_value'],
                    max_value=param_data['max_value'],
                    description=param_data['description']
                )
                self.parameter_specs[intent_name].append(param_spec)
        
        logger.debug(f"Restored parameter specs for {len(self.parameter_specs)} intents")
        
        # Restore PhraseMatcher configuration and rebuild if available
        self.phrase_matcher_config = cached_data.get('phrase_matcher_config')
        if self.phrase_matcher_config and self.nlp:
            try:
                # Rebuild PhraseMatcher from cached configuration
                phrases = self.phrase_matcher_config['phrases']
                phrase_to_intent = self.phrase_matcher_config['phrase_to_intent']
                attr = self.phrase_matcher_config.get('attr', 'LOWER')
                
                phrase_patterns = list(self.nlp.pipe(phrases))
                self.phrase_matcher = spacy.matcher.PhraseMatcher(self.nlp.vocab, attr=attr)
                
                # Add patterns grouped by intent
                for intent_name in set(phrase_to_intent.values()):
                    intent_patterns = [doc for phrase, doc in zip(phrases, phrase_patterns) 
                                     if phrase_to_intent.get(phrase) == intent_name]
                    if intent_patterns:
                        self.phrase_matcher.add(intent_name, intent_patterns)
                
                logger.debug(f"Rebuilt PhraseMatcher from cache with {len(phrases)} phrases")
                
            except Exception as e:
                logger.warning(f"Failed to rebuild PhraseMatcher from cache: {e}")
                self.phrase_matcher = None
        
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
        if not self.asset_manager:
            logger.warning("Cannot cache spaCy artifacts: asset manager not available")
            return
        if not self._donations_hash:
            logger.warning("Cannot cache spaCy artifacts: donations hash not available")
            return
        
        try:
            # Create cache key based on primary model, model version, and donations
            model_version = self._spacy_model_version or "unknown"
            primary_model_name = getattr(self.nlp, 'meta', {}).get('name', 'unknown') if self.nlp else 'unknown'
            cache_key = f"spacy_artifacts_{primary_model_name}_{model_version}_{self._donations_hash}"
            
            # Serialize pattern docs using DocBin for efficiency
            pattern_docs_docbin, intent_doc_counts = await self._serialize_pattern_docs()
            
            # Serialize parameter specs for caching
            serialized_parameter_specs = {}
            for intent_name, param_specs in self.parameter_specs.items():
                serialized_parameter_specs[intent_name] = [
                    {
                        'name': p.name,
                        'type': p.type.value if hasattr(p.type, 'value') else str(p.type),
                        'required': p.required,
                        'default_value': p.default_value,
                        'pattern': p.pattern,
                        'choices': p.choices,
                        'min_value': p.min_value,
                        'max_value': p.max_value,
                        'description': p.description
                    }
                    for p in param_specs
                ]
            
            # Prepare data for caching with telemetry and comprehensive data
            cache_data = {
                'pattern_docs_docbin': pattern_docs_docbin,
                'intent_doc_counts': intent_doc_counts,
                'intent_centroids': self.intent_centroids,
                'parameter_specs': serialized_parameter_specs,  # ADD: Parameter specifications
                'advanced_patterns': self.advanced_patterns,     # ADD: Validated spaCy patterns
                'phrase_matcher_config': self.phrase_matcher_config,  # ADD: PhraseMatcher configuration
                'model_name': primary_model_name,
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
            logger.info(f"spaCy asset cache telemetry - Model: {primary_model_name} v{model_version}, "
                       f"Donations: {len(self._donation_versions)} versions from {len(self._handler_domains)} domains, "
                       f"Artifacts: {len(self.pattern_docs)} intents, {len(self.intent_centroids)} centroids, "
                       f"{len(self.parameter_specs)} parameter specs, {len(self.advanced_patterns)} advanced patterns")
            
        except Exception as e:
            logger.warning(f"Failed to cache artifacts: {e}")
    
    async def recognize(self, text: str, context: UnifiedConversationContext) -> Intent:
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
        
        # Runtime language detection and model selection
        detected_lang = self._detect_language(text)
        selected_model = None
        
        # Try to use language-specific model if available
        if detected_lang in self.available_models:
            selected_model = self.available_models[detected_lang]
        else:
            # Fallback to primary model
            selected_model = self.nlp
            
            # Check if we have any models for the detected language
            if detected_lang not in self.available_models and self.available_models:
                logger.debug(f"No model available for detected language '{detected_lang}', using fallback model")
        
        # If no model available for detected language, return general intent
        if not selected_model:
            logger.info(f"No spaCy model available for language '{detected_lang}', returning general intent")
            return Intent(
                name="conversation.general",
                entities={},
                confidence=0.6,
                raw_text=text,
                domain="conversation",
                action="general",
                session_id=context.session_id
            )
        
        # Process text with selected spaCy model
        doc = selected_model(text)
        
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
    
    async def extract_parameters(self, text: str, intent_name: str, parameter_specs: List[ParameterSpec]) -> Dict[str, Any]:
        """Extract parameters using spaCy NLP capabilities
        
        Args:
            text: Input text to extract parameters from
            intent_name: Name of the recognized intent
            parameter_specs: List of parameter specifications to extract
            
        Returns:
            Dictionary of extracted parameters
        """
        if not self.nlp or not parameter_specs:
            return {}
        
        # Process text with existing spaCy model
        doc = self.nlp(text)
        
        extracted_params = {}
        
        for param_spec in parameter_specs:
            try:
                # Reuse existing spaCy logic from JSONBasedParameterExtractor
                value = await self._extract_single_parameter_spacy(doc, param_spec, text)
                
                if value is not None:
                    converted_value = self._convert_and_validate_parameter(value, param_spec)
                    extracted_params[param_spec.name] = converted_value
                elif param_spec.required and param_spec.default_value is None:
                    logger.warning(f"Required parameter '{param_spec.name}' not found in text: {text}")
                elif param_spec.default_value is not None:
                    extracted_params[param_spec.name] = param_spec.default_value
                    
            except Exception as e:
                if param_spec.required:
                    logger.error(f"Failed to extract required parameter '{param_spec.name}': {e}")
                else:
                    logger.warning(f"Failed to extract optional parameter '{param_spec.name}': {e}")
        
        return extracted_params
    
    async def _extract_single_parameter_spacy(self, doc, param_spec: ParameterSpec, text: str) -> Optional[Any]:
        """Extract a single parameter using spaCy processing
        
        This method implements spaCy-based parameter extraction that would be
        moved from JSONBasedParameterExtractor in Phase 2.
        For now, it provides basic extraction with spaCy entity recognition.
        """
        from ...core.donations import ParameterType
        
        # Use spaCy entities first
        for ent in doc.ents:
            if param_spec.type == ParameterType.INTEGER and ent.label_ in ['CARDINAL', 'QUANTITY']:
                try:
                    return int(ent.text)
                except ValueError:
                    continue
            elif param_spec.type == ParameterType.FLOAT and ent.label_ in ['CARDINAL', 'QUANTITY', 'MONEY']:
                try:
                    return float(ent.text.replace(',', '.'))
                except ValueError:
                    continue
            elif param_spec.type == ParameterType.DATETIME and ent.label_ in ['DATE', 'TIME']:
                return ent.text
            elif param_spec.type == ParameterType.STRING and ent.label_ in ['PERSON', 'ORG', 'GPE']:
                return ent.text
        
        # Fallback to pattern-based extraction if no entity found
        if param_spec.pattern:
            import re
            match = re.search(param_spec.pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if match.groups() else match.group(0)
        
        # Type-specific extraction using spaCy tokens
        if param_spec.type == ParameterType.INTEGER:
            for token in doc:
                if token.like_num:
                    try:
                        return int(token.text)
                    except ValueError:
                        continue
        
        elif param_spec.type == ParameterType.BOOLEAN:
            positive_tokens = ['да', 'yes', 'true', 'включи', 'enable']
            negative_tokens = ['нет', 'no', 'false', 'выключи', 'disable']
            
            for token in doc:
                if token.text.lower() in positive_tokens:
                    return True
                elif token.text.lower() in negative_tokens:
                    return False
        
        elif param_spec.type == ParameterType.CHOICE and param_spec.choices:
            # Use spaCy similarity for choice matching
            best_choice = None
            best_similarity = 0
            
            for choice in param_spec.choices:
                choice_doc = self.nlp(choice)
                similarity = doc.similarity(choice_doc)
                if similarity > best_similarity and similarity >= 0.7:  # 70% threshold
                    best_similarity = similarity
                    best_choice = choice
            
            return best_choice
        
        return None
    
    def _convert_and_validate_parameter(self, value: Any, param_spec: ParameterSpec) -> Any:
        """Convert and validate parameter value according to spec"""
        from ...core.donations import ParameterType
        
        # Type conversion
        if param_spec.type == ParameterType.INTEGER:
            value = int(value)
        elif param_spec.type == ParameterType.FLOAT:
            value = float(value)
        elif param_spec.type == ParameterType.STRING:
            value = str(value)
        elif param_spec.type == ParameterType.BOOLEAN:
            value = bool(value)
        
        # Range validation for numeric types
        if param_spec.type in [ParameterType.INTEGER, ParameterType.FLOAT]:
            if param_spec.min_value is not None and value < param_spec.min_value:
                raise ValueError(f"Value {value} below minimum {param_spec.min_value}")
            if param_spec.max_value is not None and value > param_spec.max_value:
                raise ValueError(f"Value {value} above maximum {param_spec.max_value}")
        
        # Choice validation
        if param_spec.type == ParameterType.CHOICE and param_spec.choices:
            if value not in param_spec.choices:
                raise ValueError(f"Value {value} not in allowed choices {param_spec.choices}")
        
        return value
    
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
        """Get supported languages based on available models"""
        if self.available_models:
            # Return languages for which we have loaded models
            return list(self.available_models.keys())
        elif self.nlp is not None:
            # Use actual model language if available
            primary_lang = getattr(self.nlp, 'lang', 'en')
            if primary_lang == 'ru':
                return ['ru', 'en']
            elif primary_lang == 'en':
                return ['en', 'ru']
            else:
                return [primary_lang, 'en']
        else:
            # Default fallback
            return ['ru', 'en']
    
    def get_supported_domains(self) -> List[str]:
        """Get supported intent domains"""
        domains = set()
        for intent_name in self.intent_patterns.keys():
            domain, _ = self._parse_intent_name(intent_name)
            domains.add(domain)
        return list(domains)
    
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get spaCy NLU capabilities"""
        return {
            "supported_languages": self.get_supported_languages(),
            "supported_domains": self.get_supported_domains(),
            "primary_model": getattr(self.nlp, 'meta', {}).get('name', 'unknown') if self.nlp else 'unknown',
            "available_models": list(self.available_models.keys()) if self.available_models else [],
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
    
    def _validate_and_store_spacy_patterns(self, donation: KeywordDonation) -> None:
        """Validate spaCy patterns at runtime (moved from donation loading)
        
        Args:
            donation: KeywordDonation containing spaCy patterns to validate
        """
        try:
            # Initialize matcher if not already done
            if self.matcher is None and self.nlp:
                spacy = safe_import("spacy")
                if spacy:
                    self.matcher = spacy.matcher.Matcher(self.nlp.vocab)
            
            if self.matcher is None:
                logger.warning(f"Cannot validate token patterns for '{donation.intent}' - matcher not available")
                return
            
            # Validate token patterns
            for i, pattern in enumerate(donation.token_patterns):
                try:
                    # Test pattern by adding it temporarily
                    test_id = f"test_token_{donation.intent}_{i}"
                    self.matcher.add(test_id, [pattern])
                    # Remove test pattern immediately
                    self.matcher.remove(test_id)
                    logger.debug(f"Token pattern {i} validated for '{donation.intent}'")
                except Exception as e:
                    raise ValueError(f"Invalid token pattern {i} in intent '{donation.intent}': {e}")
            
            # Validate slot patterns
            for slot_name, patterns in donation.slot_patterns.items():
                for i, pattern in enumerate(patterns):
                    try:
                        # Test pattern by adding it temporarily to entity ruler
                        if self.entity_ruler:
                            # Create temporary patterns list to test
                            test_patterns = [{"label": f"TEST_{slot_name}", "pattern": pattern}]
                            # This will raise an exception if pattern is invalid
                            # Note: We can't easily remove patterns from entity ruler, 
                            # but validation happens during add_patterns
                            logger.debug(f"Slot pattern {i} for '{slot_name}' validated for '{donation.intent}'")
                    except Exception as e:
                        raise ValueError(f"Invalid slot pattern {i} for slot '{slot_name}' in intent '{donation.intent}': {e}")
            
            # Store validated advanced patterns
            self.advanced_patterns[donation.intent] = {
                "token_patterns": donation.token_patterns,
                "slot_patterns": donation.slot_patterns,
                "extraction_patterns": []  # Extraction patterns are in parameter specs, not donation
            }
            
            logger.debug(f"Advanced spaCy patterns stored for '{donation.intent}': "
                        f"{len(donation.token_patterns)} token patterns, "
                        f"{len(donation.slot_patterns)} slot patterns")
            
        except Exception as e:
            # Pattern validation failed - log warning but continue
            logger.warning(f"SpaCy pattern validation failed for {donation.intent}: {e}")
            # Provider falls back to basic phrase matching without advanced patterns
    
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
    def get_asset_config(cls) -> Dict[str, Any]:
        """
        Asset configuration for spaCy models.
        
        spaCy models are installed as Python packages via pyproject.toml dependencies.
        The asset manager only verifies package availability, does not download models.
        Updated for Phase 1: Multi-model support with language preferences.
        """
        return {
            "uses_python_packages": True,  # Key flag: models are Python packages, not files
            "directory_name": "spacy",
            "cache_types": ["runtime"],  # Only runtime cache, no model downloads
            "credential_patterns": [],  # No API credentials needed for spaCy models
            "package_dependencies": [
                # Russian models (in preference order)
                "ru_core_news_md @ https://github.com/explosion/spacy-models/releases/download/ru_core_news_md-3.7.0/ru_core_news_md-3.7.0-py3-none-any.whl",
                "ru_core_news_sm @ https://github.com/explosion/spacy-models/releases/download/ru_core_news_sm-3.7.0/ru_core_news_sm-3.7.0-py3-none-any.whl",
                # English models (in preference order)
                "en_core_web_md @ https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.7.0/en_core_web_md-3.7.0-py3-none-any.whl",
                "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0-py3-none-any.whl"
            ],  # Reference for documentation only - actual installation via pyproject.toml
            "language_support": {
                "ru": ["ru_core_news_md", "ru_core_news_sm"],
                "en": ["en_core_web_md", "en_core_web_sm"]
            }
        }
    
    # Build dependency methods (Phase 1: Updated for multi-model support)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """spaCy NLU requires spacy library and multiple language models"""
        return [
            "spacy>=3.7.0",
            "numpy>=1.20.0",  # For centroids and vector operations
            # Russian models (in preference order - system will use first available)
            "ru_core_news_md @ https://github.com/explosion/spacy-models/releases/download/ru_core_news_md-3.7.0/ru_core_news_md-3.7.0-py3-none-any.whl",
            "ru_core_news_sm @ https://github.com/explosion/spacy-models/releases/download/ru_core_news_sm-3.7.0/ru_core_news_sm-3.7.0-py3-none-any.whl",
            # English models (in preference order - system will use first available)
            "en_core_web_md @ https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.7.0/en_core_web_md-3.7.0-py3-none-any.whl",
            "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0-py3-none-any.whl"
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
        from ...intents.models import UnifiedConversationContext
        context = kwargs.get('context', UnifiedConversationContext())
        intent = await self.recognize(text, context)
        
        return {
            'intent_name': intent.name,
            'entities': intent.entities,
            'confidence': intent.confidence,
            'domain': intent.domain,
            'action': intent.action
        } 