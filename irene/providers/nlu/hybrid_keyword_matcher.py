"""
Hybrid Keyword Matcher NLU Provider

High-performance NLU provider implementing keyword-first strategy with:
- Fast regex pattern matching (exact, flexible, partial variants)
- rapidfuzz Levenshtein fuzzy matching for typos and variations
- Donation-driven pattern loading with performance caching
- Configurable confidence thresholds and performance tuning
"""

import re
import logging
import time
from typing import Dict, Any, List, Pattern, Optional, Tuple, Set
from dataclasses import dataclass

from .base import NLUProvider
from ...intents.models import Intent, ConversationContext

logger = logging.getLogger(__name__)


@dataclass
class KeywordMatchResult:
    """Result of keyword matching operation"""
    intent_name: str
    confidence: float
    method: str  # "pattern_match" or "fuzzy_match"
    matched_pattern: Optional[str] = None
    matched_keywords: Optional[List[str]] = None
    fuzzy_score: Optional[float] = None
    cached: bool = False


class HybridKeywordMatcherProvider(NLUProvider):
    """
    Hybrid keyword matcher with patterns + Levenshtein fuzzy matching.
    
    Implements the keyword-first strategy described in the architecture:
    - Fast path: Hybrid keyword matching (patterns + fuzzy) handles 80-90% of common intents
    - Performance: ~0.5ms pattern matching, ~2-5ms fuzzy matching
    - Memory efficient: ~15MB pattern storage, +5MB fuzzy cache
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Pattern matching configuration
        self.exact_patterns: Dict[str, List[Pattern]] = {}
        self.flexible_patterns: Dict[str, List[Pattern]] = {}
        self.partial_patterns: Dict[str, List[Pattern]] = {}
        self.pattern_confidence = config.get('pattern_confidence', 0.9)
        self.exact_match_boost = config.get('exact_match_boost', 1.2)
        self.flexible_match_boost = config.get('flexible_match_boost', 0.9)
        self.partial_match_boost = config.get('partial_match_boost', 0.8)
        
        # Fuzzy matching configuration
        self.fuzzy_enabled = config.get('fuzzy_enabled', True)
        self.fuzzy_keywords: Dict[str, List[str]] = {}
        self.fuzzy_keywords_lc: Dict[str, List[str]] = {}  # Precomputed lowercase keywords
        self.global_keyword_map: Dict[str, str] = {}  # keyword -> intent mapping for global shortlisting
        self.fuzzy_threshold = config.get('fuzzy_threshold', 0.8)
        self.fuzzy_confidence_base = config.get('fuzzy_confidence_base', 0.7)
        self.max_fuzzy_keywords_per_intent = config.get('max_fuzzy_keywords_per_intent', 50)
        self.max_text_length_for_fuzzy = config.get('max_text_length_for_fuzzy', 100)
        
        # Performance optimization
        self.cache_fuzzy_results = config.get('cache_fuzzy_results', True)
        self.fuzzy_cache_size = config.get('fuzzy_cache_size', 1000)
        self.fuzzy_cache: Dict[str, Dict[str, float]] = {}
        self.case_sensitive = config.get('case_sensitive', False)
        self.normalize_unicode = config.get('normalize_unicode', True)
        
        # Recognition thresholds
        self.confidence_threshold = config.get('confidence_threshold', 0.8)
        self.min_pattern_length = config.get('min_pattern_length', 2)
        self.max_pattern_combinations = config.get('max_pattern_combinations', 100)
        
        # Performance tracking
        self.stats = {
            'pattern_matches': 0,
            'fuzzy_matches': 0,
            'cache_hits': 0,
            'total_recognitions': 0,
            'avg_pattern_time_ms': 0.0,
            'avg_fuzzy_time_ms': 0.0,
            'global_shortlist_hits': 0,
            'enhanced_confidence_calculations': 0,
            'total_global_keywords': 0
        }
        
        # Import rapidfuzz for fuzzy matching (lazy import to handle optional dependency)
        self._rapidfuzz_available = False
        self._fuzz = None
        self._process = None
    
    def get_provider_name(self) -> str:
        return "hybrid_keyword_matcher"
    
    async def is_available(self) -> bool:
        """Hybrid keyword matcher is available when basic dependencies are met"""
        # During initialization, check if we can function (rapidfuzz is optional)
        # Patterns will be loaded later via _initialize_from_donations()
        
        # Check if we have donation patterns loaded
        has_patterns = len(self.exact_patterns) > 0 or len(self.fuzzy_keywords) > 0
        
        # If patterns are loaded, we're definitely available
        if has_patterns:
            return True
        
        # During initialization phase, we're available if basic requirements are met
        # The provider will be initialized with donations after this check
        return True  # Hybrid keyword matcher has no hard dependencies
    
    async def _do_initialize(self) -> None:
        """Initialize hybrid keyword matcher - JSON donations required"""
        if not self.exact_patterns and not self.fuzzy_keywords:
            raise RuntimeError("HybridKeywordMatcherProvider requires JSON donations for pattern initialization. "
                             "Call _initialize_from_donations() first.")
        
        # Try to import rapidfuzz for fuzzy matching
        if self.fuzzy_enabled:
            await self._initialize_rapidfuzz()
    
    async def _initialize_rapidfuzz(self):
        """Initialize rapidfuzz for fuzzy matching if available"""
        try:
            from rapidfuzz import fuzz, process
            self._fuzz = fuzz
            self._process = process
            self._rapidfuzz_available = True
            logger.info("rapidfuzz available for fuzzy matching")
        except ImportError:
            logger.warning("rapidfuzz not available - fuzzy matching disabled")
            self._rapidfuzz_available = False
            self.fuzzy_enabled = False
    
    async def _initialize_from_donations(self, keyword_donations: List[Any]) -> None:
        """
        Initialize provider with JSON donation patterns.
        
        Builds both regex patterns and fuzzy keyword lists from donations.
        """
        try:
            logger.info(f"Initializing HybridKeywordMatcher with {len(keyword_donations)} donations")
            
            # Clear existing patterns
            self.exact_patterns = {}
            self.flexible_patterns = {}
            self.partial_patterns = {}
            self.fuzzy_keywords = {}
            self.fuzzy_keywords_lc = {}
            self.global_keyword_map = {}
            
            # Collect telemetry data
            donation_versions = set()
            handler_domains = set()
            for d in keyword_donations:
                donation_versions.add(getattr(d, 'donation_version', '1.0'))
                handler_domains.add(getattr(d, 'handler_domain', 'unknown'))
            
            total_patterns = 0
            total_keywords = 0
            
            # Build patterns and fuzzy keywords from donations
            for donation in keyword_donations:
                intent_name = donation.intent
                
                if not donation.phrases:
                    logger.warning(f"No phrases found for intent '{intent_name}' - skipping")
                    continue
                
                # Build regex patterns (for exact matching)
                exact_patterns = []
                flexible_patterns = []
                partial_patterns = []
                
                for phrase in donation.phrases:
                    if len(phrase) >= self.min_pattern_length:
                        # Create pattern variants
                        exact_pattern = self._build_exact_pattern(phrase)
                        flexible_pattern = self._build_flexible_pattern(phrase)
                        partial_pattern = self._build_partial_pattern(phrase)
                        
                        exact_patterns.append(exact_pattern)
                        flexible_patterns.append(flexible_pattern)
                        partial_patterns.append(partial_pattern)
                
                self.exact_patterns[intent_name] = exact_patterns
                self.flexible_patterns[intent_name] = flexible_patterns  
                self.partial_patterns[intent_name] = partial_patterns
                total_patterns += len(exact_patterns)
                
                # Build fuzzy keyword lists (for similarity matching)
                if self.fuzzy_enabled:
                    keywords = self._build_fuzzy_keywords(donation)
                    self.fuzzy_keywords[intent_name] = keywords
                    
                    # Precompute lowercase keywords for performance
                    keywords_lc = [k.lower() for k in keywords]
                    self.fuzzy_keywords_lc[intent_name] = keywords_lc
                    
                    # Build global keyword mapping for shortlisting
                    for keyword in keywords_lc:
                        self.global_keyword_map[keyword] = intent_name
                    
                    total_keywords += len(keywords)
                
                logger.debug(f"Added patterns for intent '{intent_name}': "
                           f"{len(exact_patterns)} patterns, {len(keywords) if self.fuzzy_enabled else 0} fuzzy keywords")
            
            # Update global keyword stats
            self.stats['total_global_keywords'] = len(self.global_keyword_map)
            
            logger.info(f"HybridKeywordMatcher initialized: {total_patterns} patterns, "
                       f"{total_keywords} fuzzy keywords ({len(self.global_keyword_map)} global) for {len(self.exact_patterns)} intents")
            
            # Telemetry logging
            logger.info(f"HybridKeywordMatcher telemetry - Donations: {sorted(donation_versions)} from domains: {sorted(handler_domains)}")
            
            # Initialize rapidfuzz if needed
            if self.fuzzy_enabled:
                await self._initialize_rapidfuzz()
                
        except Exception as e:
            logger.error(f"Failed to initialize HybridKeywordMatcher from donations: {e}")
            # Phase 4: No fallback patterns - fail fast
            raise RuntimeError(f"HybridKeywordMatcherProvider: JSON donation initialization failed: {e}. "
                             "Provider cannot operate without valid donations.")
    
    def _build_fuzzy_keywords(self, donation) -> List[str]:
        """Build fuzzy keyword list from donation with smart pruning"""
        keywords = []
        
        # Add phrases as keywords
        keywords.extend(donation.phrases)
        
        # Add individual lemmas as keywords if available
        if hasattr(donation, 'lemmas') and donation.lemmas:
            keywords.extend(donation.lemmas)
        
        # Add word combinations from phrases
        for phrase in donation.phrases:
            words = phrase.split()
            if len(words) > 1:
                # Add 2-word combinations
                for i in range(len(words) - 1):
                    keywords.append(f"{words[i]} {words[i+1]}")
                
                # Add 3-word combinations for longer phrases
                if len(words) > 2:
                    for i in range(len(words) - 2):
                        keywords.append(f"{words[i]} {words[i+1]} {words[i+2]}")
        
        # Add training examples if available
        if hasattr(donation, 'examples') and donation.examples:
            for example in donation.examples:
                if hasattr(example, 'text'):
                    keywords.append(example.text)
        
        # Remove duplicates
        keywords = list(set(keywords))
        
        # Smart pruning: prioritize by entropy and signal strength instead of just length
        if len(keywords) > self.max_fuzzy_keywords_per_intent:
            keywords = self._smart_prune_keywords(keywords)
        
        return keywords
    
    def _smart_prune_keywords(self, keywords: List[str]) -> List[str]:
        """Prune keywords using entropy and signal strength instead of just length"""
        import math
        from collections import Counter
        
        # Calculate keyword scores based on multiple factors
        keyword_scores = []
        
        for keyword in keywords:
            # Factor 1: Character n-gram entropy (higher is better for fuzzy matching)
            chars = keyword.lower()
            char_counts = Counter(chars)
            total_chars = len(chars)
            entropy = -sum((count/total_chars) * math.log2(count/total_chars) 
                          for count in char_counts.values() if count > 0)
            
            # Factor 2: Word count (2-3 words often optimal for matching)
            word_count = len(keyword.split())
            word_score = 1.0 if word_count in [2, 3] else 0.8 if word_count == 1 else 0.6
            
            # Factor 3: Length penalty for very short/long keywords
            length_score = 1.0
            if len(keyword) < 3:  # Keep short high-signal keywords like "rm", "ok"
                length_score = 0.9
            elif len(keyword) > 50:  # Penalize very long keywords
                length_score = 0.7
            
            # Factor 4: Avoid common stop words but keep technical terms
            common_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by'}
            word_tokens = set(keyword.lower().split())
            if word_tokens.issubset(common_words):
                stop_word_penalty = 0.3
            else:
                stop_word_penalty = 1.0
            
            # Combined score
            total_score = entropy * word_score * length_score * stop_word_penalty
            keyword_scores.append((keyword, total_score))
        
        # Sort by score and take top keywords
        keyword_scores.sort(key=lambda x: x[1], reverse=True)
        return [kw for kw, _ in keyword_scores[:self.max_fuzzy_keywords_per_intent]]
    
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        """
        Hybrid recognition: patterns first, then fuzzy matching.
        
        Implements the keyword-first strategy with performance tracking.
        """
        start_time = time.perf_counter()
        self.stats['total_recognitions'] += 1
        
        # Skip fuzzy matching for very long texts (performance)
        use_fuzzy = self.fuzzy_enabled and len(text) <= self.max_text_length_for_fuzzy
        
        # Strategy 1: Pattern matching (fastest, highest confidence)
        pattern_start = time.perf_counter()
        pattern_result = await self._pattern_matching(text, context)
        pattern_time = (time.perf_counter() - pattern_start) * 1000
        
        if pattern_result:
            self.stats['pattern_matches'] += 1
            self._update_avg_time('pattern', pattern_time)
            logger.debug(f"Pattern match for '{text[:30]}...' -> {pattern_result.intent_name} ({pattern_result.confidence:.2f})")
            return self._create_intent_from_result(pattern_result, text, context)
        
        # Strategy 2: Fuzzy keyword matching (slower, lower confidence)
        if use_fuzzy and self._rapidfuzz_available:
            fuzzy_start = time.perf_counter()
            fuzzy_result = await self._fuzzy_matching(text, context)
            fuzzy_time = (time.perf_counter() - fuzzy_start) * 1000
            
            if fuzzy_result:
                self.stats['fuzzy_matches'] += 1
                self._update_avg_time('fuzzy', fuzzy_time)
                logger.debug(f"Fuzzy match for '{text[:30]}...' -> {fuzzy_result.intent_name} ({fuzzy_result.confidence:.2f})")
                return self._create_intent_from_result(fuzzy_result, text, context)
        
        # No match found
        total_time = (time.perf_counter() - start_time) * 1000
        logger.debug(f"No match for '{text[:30]}...' (pattern: {pattern_time:.1f}ms, total: {total_time:.1f}ms)")
        return None
    
    async def _pattern_matching(self, text: str, context: ConversationContext) -> Optional[KeywordMatchResult]:
        """Fast regex pattern matching with enhanced confidence calculation"""
        normalized_text = self._normalize_text(text)
        
        # Collect all pattern matches with their raw scores
        pattern_matches = []
        
        # Try exact patterns first (highest confidence)
        for intent_name, patterns in self.exact_patterns.items():
            for pattern in patterns:
                if pattern.search(normalized_text):
                    raw_score = self.pattern_confidence * self.exact_match_boost
                    pattern_matches.append((intent_name, raw_score, "exact_pattern", pattern.pattern))
        
        # Try flexible patterns
        for intent_name, patterns in self.flexible_patterns.items():
            for pattern in patterns:
                if pattern.search(normalized_text):
                    raw_score = self.pattern_confidence * self.flexible_match_boost
                    pattern_matches.append((intent_name, raw_score, "flexible_pattern", pattern.pattern))
        
        # Try partial patterns
        for intent_name, patterns in self.partial_patterns.items():
            for pattern in patterns:
                if pattern.search(normalized_text):
                    raw_score = self.pattern_confidence * self.partial_match_boost
                    pattern_matches.append((intent_name, raw_score, "partial_pattern", pattern.pattern))
        
        if not pattern_matches:
            return None
        
        # Find best and second-best for enhanced confidence calculation
        pattern_matches.sort(key=lambda x: x[1], reverse=True)
        best_intent, best_raw_score, best_method, best_pattern = pattern_matches[0]
        second_best_score = pattern_matches[1][1] if len(pattern_matches) > 1 else 0.0
        
        # Calculate enhanced confidence
        if best_intent in self.fuzzy_keywords:
            enhanced_confidence = self._calculate_enhanced_confidence(
                best_raw_score, second_best_score, normalized_text,
                self.fuzzy_keywords[best_intent], best_method
            )
            self.stats['enhanced_confidence_calculations'] += 1
        else:
            # Fallback to raw score if no fuzzy keywords available
            enhanced_confidence = best_raw_score
        
        if enhanced_confidence >= self.confidence_threshold:
            return KeywordMatchResult(
                intent_name=best_intent,
                confidence=enhanced_confidence,
                method=best_method,
                matched_pattern=best_pattern
            )
        
        return None
    
    async def _fuzzy_matching(self, text: str, context: ConversationContext) -> Optional[KeywordMatchResult]:
        """Optimized fuzzy matching with global shortlisting and batch operations"""
        if not self._rapidfuzz_available:
            return None
        
        normalized_text = self._normalize_text(text)
        
        # Check cache first
        cache_key = normalized_text
        if self.cache_fuzzy_results and cache_key in self.fuzzy_cache:
            self.stats['cache_hits'] += 1
            cached_results = self.fuzzy_cache[cache_key]
            best_intent, best_score, second_best_score = self._find_best_and_runner_up(cached_results)
            
            if best_score >= self.fuzzy_threshold:
                confidence = self._calculate_enhanced_confidence(
                    best_score, second_best_score, normalized_text, 
                    self.fuzzy_keywords[best_intent], "fuzzy_match"
                )
                return KeywordMatchResult(
                    intent_name=best_intent,
                    confidence=confidence,
                    method="fuzzy_match",
                    fuzzy_score=best_score,
                    matched_keywords=self._get_matched_keywords_optimized(normalized_text, self.fuzzy_keywords_lc[best_intent]),
                    cached=True
                )
        
        # Global shortlisting: find best candidates across ALL keywords first
        intent_scores = self._calculate_intent_scores_optimized(normalized_text)
        
        if not intent_scores:
            return None
        
        # Find best and second-best intents for confidence calculation
        best_intent, best_score, second_best_score = self._find_best_and_runner_up(intent_scores)
        
        if best_score >= self.fuzzy_threshold:
            confidence = self._calculate_enhanced_confidence(
                best_score, second_best_score, normalized_text,
                self.fuzzy_keywords[best_intent], "fuzzy_match"
            )
            self.stats['enhanced_confidence_calculations'] += 1
            
            result = KeywordMatchResult(
                intent_name=best_intent,
                confidence=confidence,
                method="fuzzy_match",
                fuzzy_score=best_score,
                matched_keywords=self._get_matched_keywords_optimized(normalized_text, self.fuzzy_keywords_lc[best_intent]),
                cached=False
            )
            
            # Cache results
            if self.cache_fuzzy_results:
                self._update_fuzzy_cache(cache_key, intent_scores)
            
            return result
        
        return None
    
    def _calculate_intent_scores_optimized(self, normalized_text: str) -> Dict[str, float]:
        """Calculate intent scores using global shortlisting for optimal performance"""
        if not self.global_keyword_map:
            return {}
        
        # Step 1: Global shortlisting - get top candidates across ALL keywords
        all_keywords = list(self.global_keyword_map.keys())
        
        # Use batch extract for efficiency with score cutoff
        top_matches = self._process.extract(
            normalized_text,
            all_keywords,
            scorer=self._fuzz.WRatio,
            processor=None,  # Keywords already lowercase
            score_cutoff=60,  # Early pruning
            limit=30  # Limit global candidates
        )
        
        if top_matches:
            self.stats['global_shortlist_hits'] += 1
        
        # Step 2: Aggregate scores by intent
        intent_candidate_scores = {}
        for keyword, score in top_matches:
            intent_name = self.global_keyword_map[keyword]
            if intent_name not in intent_candidate_scores:
                intent_candidate_scores[intent_name] = []
            intent_candidate_scores[intent_name].append((keyword, score / 100.0))
        
        # Step 3: Calculate final intent scores using multiple strategies
        final_intent_scores = {}
        for intent_name, candidates in intent_candidate_scores.items():
            if not candidates:
                continue
                
            # Get all keywords for this intent
            intent_keywords_lc = self.fuzzy_keywords_lc[intent_name]
            
            # Strategy 1: Best single keyword match
            best_keyword_score = max(score for _, score in candidates)
            
            # Strategy 2: Token set ratio for best keyword
            best_keyword = max(candidates, key=lambda x: x[1])[0]
            token_set_score = self._fuzz.token_set_ratio(normalized_text, best_keyword) / 100.0
            
            # Strategy 3: Coverage - how many keywords contributed
            coverage_bonus = min(len(candidates) / len(intent_keywords_lc), 0.3)
            
            # Weighted combination
            final_score = (best_keyword_score * 0.6) + (token_set_score * 0.3) + coverage_bonus
            final_intent_scores[intent_name] = final_score
        
        return final_intent_scores
    
    def _find_best_and_runner_up(self, intent_scores: Dict[str, float]) -> Tuple[str, float, float]:
        """Find best and second-best intent scores for confidence calculation"""
        if not intent_scores:
            return "", 0.0, 0.0
        
        sorted_scores = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        best_intent, best_score = sorted_scores[0]
        second_best_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
        
        return best_intent, best_score, second_best_score
    
    def _calculate_enhanced_confidence(self, best_score: float, second_best_score: float, 
                                     text: str, keywords: List[str], method: str) -> float:
        """Calculate enhanced confidence using separation, coverage, and method prior"""
        # Factor 1: Absolute score strength (0-1)
        score_factor = best_score
        
        # Factor 2: Separation from runner-up (0-1)
        separation = max(0, best_score - second_best_score)
        
        # Factor 3: Coverage - estimate how much of input was matched
        text_words = set(text.lower().split())
        keyword_words = set()
        for keyword in keywords:
            keyword_words.update(keyword.lower().split())
        
        if text_words:
            coverage = len(text_words.intersection(keyword_words)) / len(text_words)
        else:
            coverage = 0.0
        
        # Factor 4: Method prior (confidence based on matching type)
        method_priors = {
            "exact_pattern": 1.0,
            "flexible_pattern": 0.9,
            "partial_pattern": 0.8,
            "fuzzy_match": 0.7
        }
        method_prior = method_priors.get(method, 0.7)
        
        # Weighted combination as suggested by GPT-5
        confidence = (0.55 * score_factor + 
                     0.25 * separation + 
                     0.15 * coverage + 
                     0.05 * method_prior)
        
        # Clamp to [0, 1] range
        return max(0.0, min(1.0, confidence))
    
    def _get_matched_keywords_optimized(self, text: str, keywords_lc: List[str]) -> List[str]:
        """Optimized version of keyword matching for debugging"""
        if not self._rapidfuzz_available or not keywords_lc:
            return []
        
        # Use batch extract for efficiency
        matches = self._process.extract(
            text,
            keywords_lc,
            scorer=self._fuzz.WRatio,
            processor=None,
            score_cutoff=70,
            limit=3
        )
        
        return [f"{keyword} ({score}%)" for keyword, score in matches]
    

    

    
    def _update_fuzzy_cache(self, cache_key: str, intent_scores: Dict[str, float]):
        """Update fuzzy matching cache with size limits"""
        self.fuzzy_cache[cache_key] = intent_scores
        
        # Limit cache size
        if len(self.fuzzy_cache) > self.fuzzy_cache_size:
            # Remove oldest entries (simple FIFO)
            cache_keys = list(self.fuzzy_cache.keys())
            for key in cache_keys[:100]:
                del self.fuzzy_cache[key]
    
    def _create_intent_from_result(self, result: KeywordMatchResult, text: str, context: ConversationContext) -> Intent:
        """Create Intent object from match result"""
        # Parse domain and action from intent name
        domain, action = self._parse_intent_name(result.intent_name)
        
        # Create Intent object without metadata (Intent class doesn't support it)
        intent = Intent(
            name=result.intent_name,
            entities={},  # Will be filled by parameter extraction
            confidence=result.confidence,
            raw_text=text,
            domain=domain,
            action=action,
            session_id=context.session_id
        )
        
        # Store metadata as a special entity for debugging/tracking
        metadata = {
            "method": result.method,
            "confidence": result.confidence,
            "provider": self.get_provider_name()
        }
        
        if result.matched_pattern:
            metadata["matched_pattern"] = result.matched_pattern
        if result.matched_keywords:
            metadata["matched_keywords"] = result.matched_keywords
        if result.fuzzy_score is not None:
            metadata["fuzzy_score"] = result.fuzzy_score
        if result.cached:
            metadata["cached"] = result.cached
        
        # Store metadata in entities for access by tests and debugging
        intent.entities["_provider_metadata"] = metadata
        
        return intent
    
    def _build_exact_pattern(self, phrase: str) -> Pattern:
        """Build exact regex pattern for phrase"""
        escaped_phrase = re.escape(phrase)
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile(rf"\b{escaped_phrase}\b", flags)
    
    def _build_flexible_pattern(self, phrase: str) -> Pattern:
        """Build flexible pattern allowing any word order"""
        words = phrase.split()
        if len(words) <= 1:
            return self._build_exact_pattern(phrase)
        
        # Create pattern that matches all words in any order using positive lookahead
        escaped_words = [re.escape(word) for word in words]
        lookaheads = []
        for word in escaped_words:
            lookaheads.append(f"(?=.*\\b{word}\\b)")
        
        # Combine all lookaheads and ensure they all match somewhere in the text
        pattern = "^" + "".join(lookaheads) + ".*$"
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile(pattern, flags)
    
    def _build_partial_pattern(self, phrase: str) -> Pattern:
        """Build partial pattern matching subset of distinct words"""
        words = phrase.split()
        if len(words) <= 2:
            return self._build_flexible_pattern(phrase)
        
        # Require at least 70% of words to match, but ensure they are distinct
        min_words = max(1, int(len(words) * 0.7))
        escaped_words = [re.escape(word) for word in words]
        
        # Create pattern with lookaheads to ensure distinct word matches
        # This prevents repeated single words from satisfying the pattern
        lookaheads = []
        for word in escaped_words:
            # Each lookahead ensures the word appears at least once
            lookaheads.append(f"(?=.*\\b{word}\\b)")
        
        # Combine lookaheads to require at least min_words distinct matches
        # Use a more sophisticated approach than simple alternation
        if min_words == len(words):
            # All words required - use flexible pattern approach
            pattern = "^" + "".join(lookaheads) + ".*$"
        else:
            # Partial match - require at least min_words different words
            # Create pattern that counts distinct word boundaries
            word_patterns = [f"\\b{word}\\b" for word in escaped_words]
            
            # Use positive lookahead to ensure we have enough different words
            distinct_count_patterns = []
            from itertools import combinations
            
            # Generate combinations of min_words from the available words
            for combo in combinations(escaped_words, min_words):
                combo_lookaheads = [f"(?=.*\\b{word}\\b)" for word in combo]
                distinct_count_patterns.append("^" + "".join(combo_lookaheads) + ".*$")
            
            # Match any of the valid combinations
            pattern = f"(?:{'|'.join(distinct_count_patterns)})"
        
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile(pattern, flags)
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching"""
        if not self.case_sensitive:
            text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Unicode normalization if enabled
        if self.normalize_unicode:
            import unicodedata
            text = unicodedata.normalize('NFKD', text)
        
        return text
    
    def _parse_intent_name(self, intent_name: str) -> Tuple[str, str]:
        """Parse intent name into domain and action"""
        if "." in intent_name:
            parts = intent_name.split(".", 1)
            return parts[0], parts[1]
        else:
            return "general", intent_name
    
    def _update_avg_time(self, operation: str, time_ms: float):
        """Update average timing statistics"""
        if operation == 'pattern':
            current_avg = self.stats['avg_pattern_time_ms']
            count = self.stats['pattern_matches']
            self.stats['avg_pattern_time_ms'] = ((current_avg * (count - 1)) + time_ms) / count
        elif operation == 'fuzzy':
            current_avg = self.stats['avg_fuzzy_time_ms']
            count = self.stats['fuzzy_matches']
            self.stats['avg_fuzzy_time_ms'] = ((current_avg * (count - 1)) + time_ms) / count
    
    def get_supported_languages(self) -> List[str]:
        """Get supported languages"""
        return ["ru", "en"]
    
    def get_supported_domains(self) -> List[str]:
        """Get supported intent domains"""
        domains = set()
        for intent_name in self.exact_patterns.keys():
            domain, _ = self._parse_intent_name(intent_name)
            domains.add(domain)
        return list(domains)
    
    def get_supported_intents(self) -> List[str]:
        """Get list of intents this provider can recognize"""
        return list(self.exact_patterns.keys())
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        total = self.stats['total_recognitions']
        if total == 0:
            return self.stats.copy()
        
        stats = self.stats.copy()
        stats['pattern_success_rate'] = (self.stats['pattern_matches'] / total) * 100
        stats['fuzzy_success_rate'] = (self.stats['fuzzy_matches'] / total) * 100
        stats['cache_hit_rate'] = (self.stats['cache_hits'] / total) * 100 if self.cache_fuzzy_results else 0
        stats['global_shortlist_success_rate'] = (self.stats['global_shortlist_hits'] / max(1, self.stats['fuzzy_matches'])) * 100
        stats['enhanced_confidence_rate'] = (self.stats['enhanced_confidence_calculations'] / total) * 100
        stats['total_patterns'] = sum(len(patterns) for patterns in self.exact_patterns.values())
        stats['total_fuzzy_keywords'] = sum(len(keywords) for keywords in self.fuzzy_keywords.values())
        stats['optimization_metrics'] = {
            'global_keywords_count': self.stats['total_global_keywords'],
            'avg_keywords_per_intent': stats['total_fuzzy_keywords'] / max(1, len(self.fuzzy_keywords)),
            'shortlist_efficiency': stats['global_shortlist_success_rate']
        }
        
        return stats
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get hybrid keyword matcher capabilities"""
        return {
            "supported_languages": self.get_supported_languages(),
            "supported_domains": self.get_supported_domains(),
            "pattern_count": sum(len(patterns) for patterns in self.exact_patterns.values()),
            "fuzzy_keyword_count": sum(len(keywords) for keywords in self.fuzzy_keywords.values()),
            "features": {
                "pattern_matching": True,
                "fuzzy_matching": self.fuzzy_enabled and self._rapidfuzz_available,
                "performance_caching": self.cache_fuzzy_results,
                "multilingual": True,
                "fast_processing": True,
                "donation_driven": True,
                "configurable_thresholds": True,
                "performance_tracking": True
            },
            "performance": self.get_performance_stats()
        }
    
    # Asset configuration methods
    @classmethod
    def _get_default_extension(cls) -> str:
        """Hybrid keyword matcher doesn't use files"""
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Hybrid keyword matcher directory for cache storage"""
        return "keyword_matcher"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Hybrid keyword matcher doesn't need credentials"""
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Hybrid keyword matcher uses runtime cache for patterns and fuzzy results"""
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """Hybrid keyword matcher doesn't use external models"""
        return {}
    
    # Build dependency methods
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Hybrid keyword matcher dependencies"""
        return ["rapidfuzz>=3.0.0"]  # Optional but recommended for fuzzy matching
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Hybrid keyword matcher system dependencies for rapidfuzz compilation"""
        return {
            "linux.ubuntu": ["build-essential", "python3-dev"],
            "linux.alpine": ["build-base", "python3-dev"],
            "macos": [],  # Xcode Command Line Tools provide build tools
            "windows": []  # Windows build tools handled differently
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Hybrid keyword matcher supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    async def extract_entities(self, text: str, intent_name: str) -> Dict[str, Any]:
        """Extract entities for a given intent using basic patterns"""
        entities = {}
        
        # Basic entity extraction using regex patterns
        # This is a simplified implementation - full implementation would use
        # the parameter extraction system from Phase 0
        
        # Extract common entities
        import re
        
        # Numbers
        numbers = re.findall(r'\b\d+\b', text)
        if numbers:
            entities['numbers'] = [int(n) for n in numbers]
        
        # Time expressions for timer intents
        if intent_name.startswith("timer."):
            time_patterns = [
                r'\b(\d+)\s*(минут|секунд|часов|мин|сек|час)\b',
                r'\b(\d+)\s*(minutes?|seconds?|hours?)\b'
            ]
            
            for pattern in time_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    entities['duration'] = []
                    for value, unit in matches:
                        entities['duration'].append({
                            'value': int(value),
                            'unit': unit.lower()
                        })
                    break
        
        # Date expressions for datetime intents
        elif intent_name.startswith("datetime."):
            time_refs = re.findall(r"\b(сейчас|now|today|завтра|tomorrow|вчера|yesterday)\b", text, re.IGNORECASE)
            if time_refs:
                entities["time_reference"] = time_refs[0].lower()
        
        return entities
    
    async def cleanup(self) -> None:
        """Clean up hybrid keyword matcher resources"""
        self.exact_patterns.clear()
        self.flexible_patterns.clear()
        self.partial_patterns.clear()
        self.fuzzy_keywords.clear()
        self.fuzzy_keywords_lc.clear()
        self.global_keyword_map.clear()
        self.fuzzy_cache.clear()
        logger.info("Hybrid keyword matcher cleaned up")
