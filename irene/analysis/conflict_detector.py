"""
Conflict Detection Implementation

Implements comprehensive conflict detection algorithms that mirror the behavior
of actual NLU providers to identify overlaps, collisions, and cross-hits.
"""

import re
import math
import unicodedata
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict, Counter

from .base import ConflictDetector
from .models import (
    IntentUnit,
    OverlapScore,
    KeywordCollision,
    CrossHit
)

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


class NLUConflictDetector(ConflictDetector):
    """
    Comprehensive conflict detector implementing multiple detection strategies
    
    Mirrors the behavior of HybridKeywordMatcher and SpaCy providers to detect
    conflicts without affecting the live system.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Configure detection parameters
        self.fuzzy_threshold = config.get('fuzzy_threshold', 0.8)
        self.jaccard_threshold = config.get('jaccard_threshold', 0.3)
        self.token_f1_threshold = config.get('token_f1_threshold', 0.5)
        self.normalize_unicode = config.get('normalize_unicode', True)
        
        # Pattern matching configuration (mirror HybridKeywordMatcher)
        self.partial_match_threshold = config.get('partial_match_threshold', 0.7)
        self.exact_match_weight = config.get('exact_match_weight', 1.0)
        self.fuzzy_match_weight = config.get('fuzzy_match_weight', 0.8)
        self.partial_match_weight = config.get('partial_match_weight', 0.6)
        
        # Cache for expensive operations
        self._phrase_tokens_cache = {}
        self._normalized_text_cache = {}
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text using the same logic as HybridKeywordMatcher
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        if text in self._normalized_text_cache:
            return self._normalized_text_cache[text]
        
        if self.normalize_unicode:
            # Enhanced Unicode normalization (matching Phase 1 improvements)
            text = unicodedata.normalize('NFKD', text.casefold())
            text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        else:
            text = text.lower().strip()
        
        self._normalized_text_cache[text] = text
        return text
    
    def _get_phrase_tokens(self, phrase: str) -> Set[str]:
        """
        Tokenize phrase and return normalized tokens
        
        Args:
            phrase: Phrase to tokenize
            
        Returns:
            Set of normalized tokens
        """
        if phrase in self._phrase_tokens_cache:
            return self._phrase_tokens_cache[phrase]
        
        normalized = self._normalize_text(phrase)
        # Simple tokenization - split on whitespace and punctuation
        tokens = set(re.findall(r'\b\w+\b', normalized))
        
        self._phrase_tokens_cache[phrase] = tokens
        return tokens
    
    def detect_phrase_overlap(self, intent_a: IntentUnit, intent_b: IntentUnit) -> OverlapScore:
        """
        Detect phrase overlap using Jaccard similarity and token F1
        
        Implements comprehensive overlap detection considering both exact
        phrase matches and token-level similarities.
        """
        # Get all text content from both intents
        content_a = intent_a.get_all_text_content()
        content_b = intent_b.get_all_text_content()
        
        # Normalize phrases
        normalized_a = [self._normalize_text(phrase) for phrase in content_a]
        normalized_b = [self._normalize_text(phrase) for phrase in content_b]
        
        # Find exact phrase overlaps
        set_a = set(normalized_a)
        set_b = set(normalized_b)
        shared_phrases = list(set_a & set_b)
        
        # Calculate Jaccard similarity for phrases
        union_phrases = set_a | set_b
        jaccard_similarity = len(shared_phrases) / len(union_phrases) if union_phrases else 0.0
        
        # Get all tokens for token-level analysis
        all_tokens_a = set()
        all_tokens_b = set()
        
        for phrase in content_a:
            all_tokens_a.update(self._get_phrase_tokens(phrase))
        
        for phrase in content_b:
            all_tokens_b.update(self._get_phrase_tokens(phrase))
        
        # Calculate token F1 score
        shared_tokens = list(all_tokens_a & all_tokens_b)
        
        if not all_tokens_a and not all_tokens_b:
            token_f1 = 0.0
        elif not shared_tokens:
            token_f1 = 0.0
        else:
            precision = len(shared_tokens) / len(all_tokens_a) if all_tokens_a else 0.0
            recall = len(shared_tokens) / len(all_tokens_b) if all_tokens_b else 0.0
            token_f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Calculate overlap percentage
        total_phrases = len(content_a) + len(content_b)
        overlap_percentage = (2 * len(shared_phrases)) / total_phrases if total_phrases > 0 else 0.0
        
        return OverlapScore(
            jaccard_similarity=jaccard_similarity,
            token_f1=token_f1,
            shared_phrases=shared_phrases,
            shared_tokens=shared_tokens,
            intent_a_unique=[p for p in normalized_a if p not in set_b],
            intent_b_unique=[p for p in normalized_b if p not in set_a],
            overlap_percentage=overlap_percentage
        )
    
    def detect_keyword_collisions(self, units: List[IntentUnit]) -> List[KeywordCollision]:
        """
        Mirror HybridKeywordMatcher's keyword mapping logic to detect collisions
        
        Simulates the global keyword map building process to identify
        where keywords would overwrite each other.
        """
        collisions = []
        
        # Build global keyword maps per language (mirror Phase 1 improvements)
        keyword_maps = {
            'ru': defaultdict(set),
            'en': defaultdict(set)
        }
        
        # Process each intent unit
        for unit in units:
            keywords = unit.get_keywords()
            lang_map = keyword_maps.get(unit.language, defaultdict(set))
            
            for keyword in keywords:
                normalized_keyword = self._normalize_text(keyword)
                if normalized_keyword:  # Skip empty keywords
                    lang_map[normalized_keyword].add(unit.intent_name)
        
        # Detect collisions in each language
        for language, keyword_map in keyword_maps.items():
            for keyword, intent_set in keyword_map.items():
                if len(intent_set) > 1:
                    # Multiple intents using the same keyword = collision
                    collision = KeywordCollision(
                        keyword=keyword,
                        colliding_intents=list(intent_set),
                        collision_type="exact",
                        severity=self._calculate_collision_severity(intent_set, keyword)
                    )
                    collisions.append(collision)
        
        # Detect fuzzy collisions if rapidfuzz is available
        if RAPIDFUZZ_AVAILABLE:
            fuzzy_collisions = self._detect_fuzzy_keyword_collisions(units)
            collisions.extend(fuzzy_collisions)
        
        return collisions
    
    def _calculate_collision_severity(self, intent_set: Set[str], keyword: str) -> float:
        """
        Calculate severity of a keyword collision
        
        Args:
            intent_set: Set of intents sharing the keyword
            keyword: The colliding keyword
            
        Returns:
            Severity score (0.0-1.0)
        """
        # Base severity increases with number of colliding intents
        base_severity = min(0.9, 0.3 + (len(intent_set) - 2) * 0.2)
        
        # Increase severity for cross-domain collisions
        domains = set()
        for intent in intent_set:
            domain = intent.split('.')[0] if '.' in intent else intent
            domains.add(domain)
        
        if len(domains) > 1:
            base_severity += 0.2  # Cross-domain collision is more severe
        
        # Increase severity for short, common keywords
        if len(keyword) <= 3:
            base_severity += 0.1
        
        return min(1.0, base_severity)
    
    def _detect_fuzzy_keyword_collisions(self, units: List[IntentUnit]) -> List[KeywordCollision]:
        """
        Detect fuzzy keyword collisions using rapidfuzz
        
        Args:
            units: List of intent units to analyze
            
        Returns:
            List of fuzzy keyword collisions
        """
        if not RAPIDFUZZ_AVAILABLE:
            return []
        
        collisions = []
        
        # Group keywords by language
        language_keywords = defaultdict(list)
        keyword_to_intents = defaultdict(list)
        
        for unit in units:
            keywords = unit.get_keywords()
            for keyword in keywords:
                normalized = self._normalize_text(keyword)
                if normalized and len(normalized) > 2:  # Skip very short keywords
                    language_keywords[unit.language].append(normalized)
                    keyword_to_intents[normalized].append(unit.intent_name)
        
        # Find fuzzy matches within each language
        for language, keywords in language_keywords.items():
            unique_keywords = list(set(keywords))
            
            for i, keyword_a in enumerate(unique_keywords):
                for keyword_b in unique_keywords[i+1:]:
                    # Calculate fuzzy similarity
                    similarity = fuzz.ratio(keyword_a, keyword_b) / 100.0
                    
                    if similarity >= self.fuzzy_threshold:
                        # Check if these keywords belong to different intents
                        intents_a = set(keyword_to_intents[keyword_a])
                        intents_b = set(keyword_to_intents[keyword_b])
                        
                        if intents_a != intents_b:  # Different intents with similar keywords
                            all_intents = intents_a | intents_b
                            collision = KeywordCollision(
                                keyword=f"{keyword_a} ~ {keyword_b}",
                                colliding_intents=list(all_intents),
                                collision_type="fuzzy",
                                severity=similarity * 0.8  # Fuzzy collisions slightly less severe
                            )
                            collisions.append(collision)
        
        return collisions
    
    def detect_pattern_crosshits(self, intent_a: IntentUnit, intent_b: IntentUnit) -> List[CrossHit]:
        """
        Test patterns from intent_a against phrases from intent_b
        
        Simulates pattern matching to detect when patterns are too broad
        and would incorrectly match phrases from other intents.
        """
        crosshits = []
        
        # Get patterns from intent_a and phrases from intent_b
        patterns_a = self._extract_patterns(intent_a)
        phrases_b = intent_b.get_all_text_content()
        
        for pattern_info in patterns_a:
            pattern = pattern_info['pattern']
            pattern_type = pattern_info['type']
            
            for phrase in phrases_b:
                # Test if pattern matches phrase
                match_result = self._test_pattern_match(pattern, phrase, pattern_type)
                
                if match_result['matches']:
                    crosshit = CrossHit(
                        pattern=pattern,
                        pattern_intent=intent_a.intent_name,
                        matched_phrase=phrase,
                        target_intent=intent_b.intent_name,
                        match_type=pattern_type,
                        confidence=match_result['confidence']
                    )
                    crosshits.append(crosshit)
        
        return crosshits
    
    def _extract_patterns(self, intent: IntentUnit) -> List[Dict[str, Any]]:
        """
        Extract patterns from intent unit for cross-hit testing
        
        Args:
            intent: Intent unit to extract patterns from
            
        Returns:
            List of pattern information dictionaries
        """
        patterns = []
        
        # Extract phrase patterns (treat phrases as exact patterns)
        for phrase in intent.phrases:
            patterns.append({
                'pattern': phrase,
                'type': 'exact',
                'source': 'phrases'
            })
        
        # Extract lemma patterns (more flexible)
        for lemma in intent.lemmas:
            patterns.append({
                'pattern': lemma,
                'type': 'flexible',
                'source': 'lemmas'
            })
        
        # Convert token patterns to regex patterns (simplified)
        for token_pattern in intent.token_patterns:
            regex_pattern = self._token_pattern_to_regex(token_pattern)
            if regex_pattern:
                patterns.append({
                    'pattern': regex_pattern,
                    'type': 'token_pattern',
                    'source': 'token_patterns'
                })
        
        return patterns
    
    def _token_pattern_to_regex(self, token_pattern: List[Dict[str, Any]]) -> str:
        """
        Convert spaCy token pattern to regex pattern (simplified)
        
        Args:
            token_pattern: spaCy token pattern
            
        Returns:
            Regex pattern string
        """
        regex_parts = []
        
        for token in token_pattern:
            if 'LOWER' in token:
                regex_parts.append(re.escape(token['LOWER']))
            elif 'TEXT' in token:
                regex_parts.append(re.escape(token['TEXT']))
            elif 'LEMMA' in token:
                regex_parts.append(re.escape(token['LEMMA']))
            elif 'POS' in token:
                # Very simplified POS handling
                if token['POS'] in ['NOUN', 'VERB', 'ADJ']:
                    regex_parts.append(r'\w+')
                else:
                    regex_parts.append(r'\w*')
            else:
                regex_parts.append(r'\w+')  # Default wildcard
        
        return r'\b' + r'\s+'.join(regex_parts) + r'\b' if regex_parts else ''
    
    def _test_pattern_match(self, pattern: str, phrase: str, pattern_type: str) -> Dict[str, Any]:
        """
        Test if a pattern matches a phrase
        
        Args:
            pattern: Pattern to test
            phrase: Phrase to test against
            pattern_type: Type of pattern ('exact', 'flexible', 'token_pattern')
            
        Returns:
            Match result with confidence
        """
        normalized_pattern = self._normalize_text(pattern)
        normalized_phrase = self._normalize_text(phrase)
        
        if pattern_type == 'exact':
            # Exact match
            matches = normalized_pattern == normalized_phrase
            confidence = 1.0 if matches else 0.0
            
        elif pattern_type == 'flexible':
            # Flexible match using token overlap
            pattern_tokens = self._get_phrase_tokens(pattern)
            phrase_tokens = self._get_phrase_tokens(phrase)
            
            if not pattern_tokens:
                matches = False
                confidence = 0.0
            else:
                overlap = len(pattern_tokens & phrase_tokens)
                required_hits = math.ceil(len(pattern_tokens) * self.partial_match_threshold)
                matches = overlap >= required_hits
                confidence = overlap / len(pattern_tokens) if pattern_tokens else 0.0
            
        elif pattern_type == 'token_pattern':
            # Regex pattern match
            try:
                match = re.search(pattern, normalized_phrase, re.IGNORECASE)
                matches = match is not None
                confidence = 0.8 if matches else 0.0  # Fixed confidence for regex matches
            except re.error:
                matches = False
                confidence = 0.0
        
        else:
            # Unknown pattern type
            matches = False
            confidence = 0.0
        
        return {
            'matches': matches,
            'confidence': confidence,
            'pattern_type': pattern_type
        }
