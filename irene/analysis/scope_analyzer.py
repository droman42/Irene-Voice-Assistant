"""
Scope Analysis Implementation

Detects scope creep and cross-domain attraction issues where intents
accumulate phrases or patterns that belong to other domains.
"""

import re
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict, Counter

from .base import ScopeAnalyzer
from .models import IntentUnit, ScopeIssue, BreadthAnalysis

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


class NLUScopeAnalyzer(ScopeAnalyzer):
    """
    Comprehensive scope analyzer for detecting domain boundary violations
    
    Identifies when intents accumulate content that belongs to other domains,
    creating unwanted cross-domain attraction and scope creep issues.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Scope analysis configuration
        self.semantic_similarity_threshold = config.get('semantic_similarity_threshold', 0.7)
        self.phrase_migration_threshold = config.get('phrase_migration_threshold', 0.6)
        self.domain_purity_threshold = config.get('domain_purity_threshold', 0.8)
        
        # Pattern breadth analysis
        self.overly_broad_pattern_threshold = config.get('overly_broad_pattern_threshold', 0.8)
        self.min_specificity_score = config.get('min_specificity_score', 0.5)
        self.max_pattern_width = config.get('max_pattern_width', 10)  # Max tokens in pattern
        
        # Cache for expensive operations
        self._domain_vocabularies = {}
        self._phrase_domain_affinities = {}
    
    def detect_cross_domain_attraction(self, intent: IntentUnit, corpus: List[IntentUnit]) -> List[ScopeIssue]:
        """
        Find phrases that belong to other domains
        
        Analyzes each phrase in the intent to determine if it has stronger
        affinity to other domains than its current domain.
        """
        issues = []
        intent_domain = self.extract_domain_from_intent(intent.intent_name)
        
        # Build domain vocabularies from corpus
        domain_vocabularies = self._build_domain_vocabularies(corpus)
        
        # Analyze each phrase in the intent
        all_phrases = intent.get_all_text_content()
        
        for phrase in all_phrases:
            # Calculate affinity to each domain
            domain_affinities = self._calculate_phrase_domain_affinities(phrase, domain_vocabularies)
            
            # Check if phrase has stronger affinity to other domains
            if intent_domain in domain_affinities:
                own_domain_affinity = domain_affinities[intent_domain]
                
                for other_domain, affinity in domain_affinities.items():
                    if (other_domain != intent_domain and 
                        affinity > own_domain_affinity and 
                        affinity > self.phrase_migration_threshold):
                        
                        # Found cross-domain attraction
                        issue = ScopeIssue(
                            intent_name=intent.intent_name,
                            language=intent.language,
                            issue_type="cross_domain_attraction",
                            severity=self._classify_scope_severity(affinity - own_domain_affinity),
                            score=affinity,
                            evidence={
                                "phrase": phrase,
                                "attracted_to_domain": other_domain,
                                "attraction_score": affinity,
                                "own_domain_score": own_domain_affinity,
                                "difference": affinity - own_domain_affinity
                            },
                            suggestions=self._generate_cross_domain_suggestions(
                                phrase, intent_domain, other_domain, affinity
                            )
                        )
                        issues.append(issue)
        
        # Analyze overall domain purity
        domain_purity_issue = self._analyze_domain_purity(intent, domain_vocabularies)
        if domain_purity_issue:
            issues.append(domain_purity_issue)
        
        return issues
    
    def analyze_pattern_breadth(self, intent: IntentUnit) -> BreadthAnalysis:
        """
        Detect overly broad patterns that steal traffic from other intents
        
        Analyzes patterns to identify those that are too generic and
        likely to match phrases intended for other intents.
        """
        all_patterns = self._extract_analyzable_patterns(intent)
        
        overly_broad_patterns = []
        pattern_scores = []
        recommendations = []
        
        for pattern_info in all_patterns:
            pattern = pattern_info['pattern']
            pattern_type = pattern_info['type']
            
            # Calculate breadth score
            breadth_score = self._calculate_pattern_breadth(pattern, pattern_type)
            pattern_scores.append(breadth_score)
            
            # Check if pattern is overly broad
            if breadth_score > self.overly_broad_pattern_threshold:
                overly_broad_patterns.append(pattern)
                
                # Generate specific recommendations
                recommendations.extend(
                    self._generate_pattern_specificity_recommendations(pattern, pattern_type, breadth_score)
                )
        
        # Calculate overall scores
        avg_breadth = sum(pattern_scores) / len(pattern_scores) if pattern_scores else 0.0
        specificity_score = 1.0 - avg_breadth  # Inverse of breadth
        
        # Generate general recommendations if needed
        if specificity_score < self.min_specificity_score:
            recommendations.extend(self._generate_general_specificity_recommendations(intent))
        
        return BreadthAnalysis(
            intent_name=intent.intent_name,
            language=intent.language,
            breadth_score=avg_breadth,
            specificity_score=specificity_score,
            pattern_count=len(all_patterns),
            overly_broad_patterns=overly_broad_patterns,
            recommendations=recommendations
        )
    
    def _build_domain_vocabularies(self, corpus: List[IntentUnit]) -> Dict[str, Set[str]]:
        """
        Build vocabulary sets for each domain from the corpus
        
        Args:
            corpus: Full corpus of intent units
            
        Returns:
            Dictionary mapping domains to their vocabulary sets
        """
        if hasattr(self, '_cached_domain_vocabularies'):
            return self._cached_domain_vocabularies
        
        domain_vocabularies = defaultdict(set)
        
        for unit in corpus:
            domain = self.extract_domain_from_intent(unit.intent_name)
            
            # Add all words from phrases, lemmas, and examples
            all_content = unit.get_all_text_content()
            
            for text in all_content:
                # Simple tokenization
                words = re.findall(r'\b\w+\b', text.lower())
                domain_vocabularies[domain].update(words)
        
        self._cached_domain_vocabularies = dict(domain_vocabularies)
        return self._cached_domain_vocabularies
    
    def _calculate_phrase_domain_affinities(self, phrase: str, domain_vocabularies: Dict[str, Set[str]]) -> Dict[str, float]:
        """
        Calculate how much a phrase belongs to each domain
        
        Args:
            phrase: Phrase to analyze
            domain_vocabularies: Domain vocabulary sets
            
        Returns:
            Dictionary mapping domains to affinity scores
        """
        cache_key = phrase
        if cache_key in self._phrase_domain_affinities:
            return self._phrase_domain_affinities[cache_key]
        
        phrase_words = set(re.findall(r'\b\w+\b', phrase.lower()))
        affinities = {}
        
        for domain, vocabulary in domain_vocabularies.items():
            if not phrase_words:
                affinities[domain] = 0.0
                continue
            
            # Calculate overlap ratio
            overlap = len(phrase_words & vocabulary)
            affinity = overlap / len(phrase_words)
            
            # Apply domain-specific weighting
            if len(vocabulary) > 0:
                # Boost affinity for domains with smaller vocabularies (more specialized)
                vocabulary_factor = 1.0 + (100 / (len(vocabulary) + 100))
                affinity *= vocabulary_factor
            
            affinities[domain] = min(1.0, affinity)
        
        self._phrase_domain_affinities[cache_key] = affinities
        return affinities
    
    def _analyze_domain_purity(self, intent: IntentUnit, domain_vocabularies: Dict[str, Set[str]]) -> ScopeIssue:
        """
        Analyze overall domain purity of an intent
        
        Args:
            intent: Intent unit to analyze
            domain_vocabularies: Domain vocabulary sets
            
        Returns:
            Scope issue if domain purity is low, None otherwise
        """
        intent_domain = self.extract_domain_from_intent(intent.intent_name)
        all_phrases = intent.get_all_text_content()
        
        if not all_phrases:
            return None
        
        # Calculate average domain affinity
        domain_affinity_sums = defaultdict(float)
        phrase_count = 0
        
        for phrase in all_phrases:
            affinities = self._calculate_phrase_domain_affinities(phrase, domain_vocabularies)
            for domain, affinity in affinities.items():
                domain_affinity_sums[domain] += affinity
            phrase_count += 1
        
        # Calculate average affinities
        avg_affinities = {
            domain: total / phrase_count 
            for domain, total in domain_affinity_sums.items()
        }
        
        own_domain_purity = avg_affinities.get(intent_domain, 0.0)
        
        if own_domain_purity < self.domain_purity_threshold:
            # Find the most attractive alternative domain
            other_domains = {d: a for d, a in avg_affinities.items() if d != intent_domain}
            max_other_domain = max(other_domains.items(), key=lambda x: x[1]) if other_domains else (None, 0.0)
            
            return ScopeIssue(
                intent_name=intent.intent_name,
                language=intent.language,
                issue_type="low_domain_purity",
                severity=self._classify_scope_severity(self.domain_purity_threshold - own_domain_purity),
                score=1.0 - own_domain_purity,
                evidence={
                    "own_domain_purity": own_domain_purity,
                    "most_attractive_domain": max_other_domain[0],
                    "max_other_affinity": max_other_domain[1],
                    "domain_affinities": avg_affinities
                },
                suggestions=self._generate_domain_purity_suggestions(intent, own_domain_purity, avg_affinities)
            )
        
        return None
    
    def _extract_analyzable_patterns(self, intent: IntentUnit) -> List[Dict[str, Any]]:
        """
        Extract patterns that can be analyzed for breadth
        
        Args:
            intent: Intent unit to extract patterns from
            
        Returns:
            List of pattern information dictionaries
        """
        patterns = []
        
        # Analyze phrases as literal patterns
        for phrase in intent.phrases:
            patterns.append({
                'pattern': phrase,
                'type': 'phrase',
                'source': 'phrases'
            })
        
        # Analyze lemmas as flexible patterns
        for lemma in intent.lemmas:
            patterns.append({
                'pattern': lemma,
                'type': 'lemma',
                'source': 'lemmas'
            })
        
        # Analyze token patterns
        for i, token_pattern in enumerate(intent.token_patterns):
            patterns.append({
                'pattern': f"token_pattern_{i}",
                'type': 'token_pattern',
                'source': 'token_patterns',
                'tokens': token_pattern
            })
        
        return patterns
    
    def _calculate_pattern_breadth(self, pattern: str, pattern_type: str) -> float:
        """
        Calculate breadth score for a pattern (0.0 = specific, 1.0 = broad)
        
        Args:
            pattern: Pattern to analyze
            pattern_type: Type of pattern
            
        Returns:
            Breadth score (0.0-1.0)
        """
        if pattern_type == 'phrase':
            return self._calculate_phrase_breadth(pattern)
        elif pattern_type == 'lemma':
            return self._calculate_lemma_breadth(pattern)
        elif pattern_type == 'token_pattern':
            return self._calculate_token_pattern_breadth(pattern)
        else:
            return 0.5  # Default moderate breadth
    
    def _calculate_phrase_breadth(self, phrase: str) -> float:
        """Calculate breadth score for a phrase pattern"""
        words = phrase.strip().split()
        
        # Short phrases are generally broader
        length_score = max(0.0, 1.0 - (len(words) / 5.0))
        
        # Common words make phrases broader
        common_words = {'get', 'set', 'show', 'tell', 'give', 'make', 'do', 'have', 'be', 'go', 'come'}
        common_word_ratio = sum(1 for word in words if word.lower() in common_words) / len(words) if words else 0
        
        # Generic terms make phrases broader
        generic_terms = {'time', 'something', 'anything', 'everything', 'thing', 'stuff', 'this', 'that'}
        generic_ratio = sum(1 for word in words if word.lower() in generic_terms) / len(words) if words else 0
        
        # Combine factors
        breadth_score = (length_score * 0.4) + (common_word_ratio * 0.3) + (generic_ratio * 0.3)
        return min(1.0, breadth_score)
    
    def _calculate_lemma_breadth(self, lemma: str) -> float:
        """Calculate breadth score for a lemma pattern"""
        # Lemmas are inherently broader than exact phrases
        phrase_breadth = self._calculate_phrase_breadth(lemma)
        return min(1.0, phrase_breadth + 0.2)  # Add base lemma broadness
    
    def _calculate_token_pattern_breadth(self, pattern: str) -> float:
        """Calculate breadth score for a token pattern"""
        # Token patterns are generally broad by nature
        # This is a simplified analysis - real implementation would analyze the token structure
        return 0.7  # Default high breadth for token patterns
    
    def _classify_scope_severity(self, score: float) -> str:
        """Classify scope issue severity based on score"""
        if score >= 0.3:
            return 'blocker'
        elif score >= 0.15:
            return 'warning'
        else:
            return 'info'
    
    def _generate_cross_domain_suggestions(self, phrase: str, own_domain: str, attracted_domain: str, attraction_score: float) -> List[str]:
        """Generate suggestions for resolving cross-domain attraction"""
        suggestions = []
        
        if attraction_score > 0.8:
            suggestions.append(f"Consider moving phrase '{phrase}' to {attracted_domain} domain where it has stronger affinity")
        else:
            suggestions.append(f"Make phrase '{phrase}' more specific to {own_domain} domain")
            suggestions.append(f"Add domain-specific context to '{phrase}' to reduce {attracted_domain} attraction")
        
        suggestions.append(f"Review if '{phrase}' truly belongs in {own_domain} domain")
        
        return suggestions
    
    def _generate_pattern_specificity_recommendations(self, pattern: str, pattern_type: str, breadth_score: float) -> List[str]:
        """Generate recommendations for making patterns more specific"""
        recommendations = []
        
        if pattern_type == 'phrase':
            if breadth_score > 0.8:
                recommendations.append(f"Phrase '{pattern}' is too broad - add more specific context")
                recommendations.append(f"Consider splitting '{pattern}' into more specific variations")
            elif breadth_score > 0.6:
                recommendations.append(f"Consider making '{pattern}' more specific with additional context")
        
        elif pattern_type == 'lemma':
            recommendations.append(f"Lemma '{pattern}' may be too broad - consider converting to specific phrases")
        
        elif pattern_type == 'token_pattern':
            recommendations.append("Token pattern may be overly broad - review pattern constraints")
        
        return recommendations
    
    def _generate_domain_purity_suggestions(self, intent: IntentUnit, own_purity: float, all_affinities: Dict[str, float]) -> List[str]:
        """Generate suggestions for improving domain purity"""
        suggestions = []
        intent_domain = self.extract_domain_from_intent(intent.intent_name)
        
        suggestions.append(f"Intent has low {intent_domain} domain purity ({own_purity:.2f})")
        
        # Find most attractive alternative domain
        other_domains = {d: a for d, a in all_affinities.items() if d != intent_domain}
        if other_domains:
            max_other = max(other_domains.items(), key=lambda x: x[1])
            suggestions.append(f"Consider moving some phrases to {max_other[0]} domain (affinity: {max_other[1]:.2f})")
        
        suggestions.append(f"Add more {intent_domain}-specific phrases to improve domain purity")
        suggestions.append("Review each phrase to ensure it belongs in this domain")
        
        return suggestions
    
    def _generate_general_specificity_recommendations(self, intent: IntentUnit) -> List[str]:
        """Generate general recommendations for improving pattern specificity"""
        return [
            "Consider making patterns more specific to reduce conflicts",
            "Add domain-specific context to broad patterns",
            "Split overly broad patterns into focused variations",
            "Review pattern necessity - remove if too generic"
        ]
