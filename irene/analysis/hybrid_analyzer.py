"""
HybridKeywordMatcher Analysis Mirror

Mirrors the behavior and logic of the HybridKeywordMatcher provider
to detect conflicts and performance issues without affecting live recognition.
"""

import re
import math
import time
import unicodedata
from typing import Dict, Any, List, Set, Tuple, Optional
from collections import defaultdict

from .base import BaseAnalyzer
from .models import IntentUnit

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


class HybridKeywordAnalyzer(BaseAnalyzer):
    """
    Analysis mirror of HybridKeywordMatcher provider
    
    Simulates the exact behavior of the HybridKeywordMatcher to detect
    conflicts, performance issues, and recognition problems.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Mirror HybridKeywordMatcher configuration exactly
        self.pattern_confidence = config.get('pattern_confidence', 0.9)
        self.exact_match_boost = config.get('exact_match_boost', 1.2)
        self.flexible_match_boost = config.get('flexible_match_boost', 0.9)
        self.partial_match_boost = config.get('partial_match_boost', 0.8)
        
        # Fuzzy matching configuration
        self.fuzzy_enabled = config.get('fuzzy_enabled', True)
        self.fuzzy_threshold = config.get('fuzzy_threshold', 0.8)
        self.fuzzy_confidence_base = config.get('fuzzy_confidence_base', 0.7)
        self.max_fuzzy_keywords_per_intent = config.get('max_fuzzy_keywords_per_intent', 50)
        self.max_text_length_for_fuzzy = config.get('max_text_length_for_fuzzy', 100)
        
        # Recognition thresholds
        self.confidence_threshold = config.get('confidence_threshold', 0.7)
        self.min_pattern_length = config.get('min_pattern_length', 2)
        self.max_pattern_combinations = config.get('max_pattern_combinations', 100)
        
        # Performance settings
        self.cache_fuzzy_results = config.get('cache_fuzzy_results', True)
        self.case_sensitive = config.get('case_sensitive', False)
        self.normalize_unicode = config.get('normalize_unicode', True)
        
        # Analysis-specific settings
        self.detect_keyword_collisions = config.get('detect_keyword_collisions', True)
        self.detect_pattern_explosion = config.get('detect_pattern_explosion', True)
        self.detect_performance_issues = config.get('detect_performance_issues', True)
        
        # Internal state for simulation
        self._simulated_keyword_maps = {}
        self._simulated_patterns = {}
        self._performance_metrics = {}
    
    async def analyze_intent_unit(self, unit: IntentUnit, context: List[IntentUnit]) -> Dict[str, Any]:
        """
        Analyze intent unit by simulating HybridKeywordMatcher behavior
        
        Performs comprehensive analysis including keyword collision detection,
        pattern efficiency analysis, and performance impact assessment.
        """
        start_time = time.time()
        analysis_results = {}
        
        # 1. Keyword mapping analysis
        if self.detect_keyword_collisions:
            keyword_analysis = self._analyze_keyword_mapping(unit, context)
            analysis_results['keyword_analysis'] = keyword_analysis
        
        # 2. Pattern efficiency analysis
        if self.detect_pattern_explosion:
            pattern_analysis = self._analyze_pattern_efficiency(unit)
            analysis_results['pattern_analysis'] = pattern_analysis
        
        # 3. Performance impact analysis
        if self.detect_performance_issues:
            performance_analysis = self._analyze_performance_impact(unit, context)
            analysis_results['performance_analysis'] = performance_analysis
        
        # 4. Recognition accuracy simulation
        accuracy_analysis = self._simulate_recognition_accuracy(unit, context)
        analysis_results['accuracy_analysis'] = accuracy_analysis
        
        # 5. Cross-language consistency check
        if unit.language in ['ru', 'en']:
            consistency_analysis = self._analyze_language_consistency(unit, context)
            analysis_results['consistency_analysis'] = consistency_analysis
        
        analysis_time_ms = (time.time() - start_time) * 1000
        self.update_stats(analysis_time_ms)
        
        analysis_results.update({
            'analyzer': 'hybrid_keyword_matcher',
            'analysis_time_ms': analysis_time_ms,
            'capabilities_used': self.get_analysis_capabilities()
        })
        
        return analysis_results
    
    def get_analysis_capabilities(self) -> List[str]:
        """Get list of analysis capabilities"""
        return [
            'keyword_collision_detection',
            'pattern_efficiency_analysis',
            'performance_impact_assessment',
            'recognition_accuracy_simulation',
            'language_consistency_checking',
            'fuzzy_matching_analysis'
        ]
    
    def _analyze_keyword_mapping(self, unit: IntentUnit, context: List[IntentUnit]) -> Dict[str, Any]:
        """
        Analyze keyword mapping conflicts by simulating the global keyword map
        
        Mirrors the exact logic of HybridKeywordMatcher's keyword processing
        to detect collisions and overwrites.
        """
        analysis = {
            'collisions': [],
            'overwrites': [],
            'language_conflicts': [],
            'keyword_efficiency': {}
        }
        
        # Build simulated keyword maps per language (mirror Phase 1 improvements)
        keyword_maps = {
            'ru': defaultdict(set),
            'en': defaultdict(set)
        }
        
        # Process all units to build the global map
        all_units = [unit] + context
        for current_unit in all_units:
            keywords = self._extract_keywords_like_hybrid(current_unit)
            lang_map = keyword_maps.get(current_unit.language, defaultdict(set))
            
            for keyword in keywords:
                normalized_keyword = self._normalize_text_like_hybrid(keyword)
                if normalized_keyword:
                    lang_map[normalized_keyword].add(current_unit.intent_name)
        
        # Analyze collisions for the target unit
        target_keywords = self._extract_keywords_like_hybrid(unit)
        lang_map = keyword_maps.get(unit.language, defaultdict(set))
        
        for keyword in target_keywords:
            normalized = self._normalize_text_like_hybrid(keyword)
            if normalized in lang_map:
                conflicting_intents = lang_map[normalized]
                if len(conflicting_intents) > 1:
                    analysis['collisions'].append({
                        'keyword': normalized,
                        'original_keyword': keyword,
                        'conflicting_intents': list(conflicting_intents),
                        'severity': self._calculate_collision_severity(conflicting_intents, normalized)
                    })
        
        # Analyze keyword efficiency
        analysis['keyword_efficiency'] = self._analyze_keyword_efficiency(unit, target_keywords)
        
        return analysis
    
    def _analyze_pattern_efficiency(self, unit: IntentUnit) -> Dict[str, Any]:
        """
        Analyze pattern efficiency and potential regex explosion
        
        Simulates pattern compilation and matching to detect performance issues.
        """
        analysis = {
            'pattern_count': 0,
            'complex_patterns': [],
            'explosion_risk': False,
            'estimated_compile_time_ms': 0.0,
            'estimated_match_time_ms': 0.0
        }
        
        # Simulate pattern generation from phrases
        patterns = self._generate_patterns_like_hybrid(unit)
        analysis['pattern_count'] = len(patterns)
        
        total_compile_time = 0.0
        total_match_time = 0.0
        
        for pattern_info in patterns:
            pattern = pattern_info['pattern']
            pattern_type = pattern_info['type']
            
            # Estimate compilation complexity
            compile_time = self._estimate_pattern_compile_time(pattern)
            total_compile_time += compile_time
            
            # Estimate matching complexity
            match_time = self._estimate_pattern_match_time(pattern, pattern_type)
            total_match_time += match_time
            
            # Check for complex patterns
            if compile_time > 5.0 or match_time > 2.0:  # ms thresholds
                analysis['complex_patterns'].append({
                    'pattern': pattern,
                    'type': pattern_type,
                    'compile_time_ms': compile_time,
                    'match_time_ms': match_time,
                    'complexity_reason': self._analyze_pattern_complexity(pattern)
                })
        
        analysis['estimated_compile_time_ms'] = total_compile_time
        analysis['estimated_match_time_ms'] = total_match_time
        
        # Check for explosion risk
        if len(patterns) > self.max_pattern_combinations or total_compile_time > 50.0:
            analysis['explosion_risk'] = True
            analysis['explosion_reasons'] = []
            
            if len(patterns) > self.max_pattern_combinations:
                analysis['explosion_reasons'].append(f"Too many patterns: {len(patterns)} > {self.max_pattern_combinations}")
            
            if total_compile_time > 50.0:
                analysis['explosion_reasons'].append(f"High compile time: {total_compile_time:.1f}ms")
        
        return analysis
    
    def _analyze_performance_impact(self, unit: IntentUnit, context: List[IntentUnit]) -> Dict[str, Any]:
        """
        Analyze performance impact of this intent on the overall system
        
        Simulates memory usage, processing time, and system load impact.
        """
        analysis = {
            'memory_impact_bytes': 0,
            'processing_overhead_ms': 0.0,
            'fuzzy_cache_impact': {},
            'scale_factor': 1.0
        }
        
        # Estimate memory impact
        keywords = self._extract_keywords_like_hybrid(unit)
        phrases = unit.get_all_text_content()
        
        # Rough memory estimates (simplified)
        keyword_memory = sum(len(k.encode('utf-8')) for k in keywords) * 2  # overhead factor
        phrase_memory = sum(len(p.encode('utf-8')) for p in phrases) * 3  # pattern storage
        analysis['memory_impact_bytes'] = keyword_memory + phrase_memory
        
        # Estimate processing overhead
        base_processing = len(keywords) * 0.1 + len(phrases) * 0.5  # ms per keyword/phrase
        
        if self.fuzzy_enabled and RAPIDFUZZ_AVAILABLE:
            # Fuzzy matching adds significant overhead
            fuzzy_overhead = min(len(keywords), self.max_fuzzy_keywords_per_intent) * 2.0
            analysis['processing_overhead_ms'] = base_processing + fuzzy_overhead
            
            # Analyze fuzzy cache impact
            analysis['fuzzy_cache_impact'] = {
                'cache_entries': min(len(keywords), self.max_fuzzy_keywords_per_intent),
                'estimated_cache_size_bytes': min(len(keywords), self.max_fuzzy_keywords_per_intent) * 100
            }
        else:
            analysis['processing_overhead_ms'] = base_processing
        
        # Calculate scale factor based on corpus size
        corpus_size = len(context) + 1
        if corpus_size > 100:
            analysis['scale_factor'] = math.log(corpus_size / 100) + 1.0
        
        return analysis
    
    def _simulate_recognition_accuracy(self, unit: IntentUnit, context: List[IntentUnit]) -> Dict[str, Any]:
        """
        Simulate recognition accuracy by testing phrases against other intents
        
        Runs simulated recognition to detect accuracy problems.
        """
        analysis = {
            'accuracy_score': 1.0,
            'false_positives': [],
            'false_negatives': [],
            'confidence_distribution': [],
            'recognition_tests': []
        }
        
        # Test phrases from this intent
        test_phrases = unit.get_all_text_content()
        false_positives = 0
        false_negatives = 0
        confidences = []
        
        for phrase in test_phrases[:10]:  # Limit testing
            # Simulate recognition for this phrase
            recognition_result = self._simulate_phrase_recognition(phrase, unit, context)
            
            analysis['recognition_tests'].append({
                'phrase': phrase,
                'expected_intent': unit.intent_name,
                'recognized_intent': recognition_result['intent'],
                'confidence': recognition_result['confidence'],
                'correct': recognition_result['intent'] == unit.intent_name
            })
            
            if recognition_result['intent'] != unit.intent_name:
                if recognition_result['confidence'] > self.confidence_threshold:
                    false_positives += 1
                    analysis['false_positives'].append({
                        'phrase': phrase,
                        'incorrect_intent': recognition_result['intent'],
                        'confidence': recognition_result['confidence']
                    })
                else:
                    false_negatives += 1
                    analysis['false_negatives'].append({
                        'phrase': phrase,
                        'low_confidence': recognition_result['confidence']
                    })
            
            confidences.append(recognition_result['confidence'])
        
        # Calculate accuracy metrics
        total_tests = len(analysis['recognition_tests'])
        if total_tests > 0:
            correct_recognitions = total_tests - false_positives - false_negatives
            analysis['accuracy_score'] = correct_recognitions / total_tests
        
        if confidences:
            analysis['confidence_distribution'] = {
                'mean': sum(confidences) / len(confidences),
                'min': min(confidences),
                'max': max(confidences),
                'std': self._calculate_std(confidences)
            }
        
        return analysis
    
    def _analyze_language_consistency(self, unit: IntentUnit, context: List[IntentUnit]) -> Dict[str, Any]:
        """
        Analyze language consistency and cross-language conflicts
        
        Checks for issues specific to multi-language processing.
        """
        analysis = {
            'language_purity': 1.0,
            'mixed_script_issues': [],
            'cross_language_conflicts': [],
            'normalization_issues': []
        }
        
        # Check for mixed scripts in phrases
        all_content = unit.get_all_text_content()
        for content in all_content:
            script_analysis = self._analyze_script_mixing(content)
            if script_analysis['mixed_scripts']:
                analysis['mixed_script_issues'].append({
                    'content': content,
                    'detected_scripts': script_analysis['scripts'],
                    'primary_script': script_analysis['primary_script']
                })
        
        # Check for cross-language keyword conflicts
        other_language_units = [u for u in context if u.language != unit.language]
        unit_keywords = set(self._extract_keywords_like_hybrid(unit))
        
        for other_unit in other_language_units:
            other_keywords = set(self._extract_keywords_like_hybrid(other_unit))
            conflicts = unit_keywords & other_keywords
            
            if conflicts:
                analysis['cross_language_conflicts'].append({
                    'conflicting_unit': other_unit.intent_name,
                    'other_language': other_unit.language,
                    'conflicting_keywords': list(conflicts)
                })
        
        # Check normalization consistency
        for content in all_content:
            normalized = self._normalize_text_like_hybrid(content)
            if normalized != content.lower().strip():
                analysis['normalization_issues'].append({
                    'original': content,
                    'normalized': normalized,
                    'significant_change': len(content) != len(normalized)
                })
        
        return analysis
    
    # Helper methods that mirror HybridKeywordMatcher behavior
    
    def _extract_keywords_like_hybrid(self, unit: IntentUnit) -> List[str]:
        """Extract keywords using the same logic as HybridKeywordMatcher"""
        keywords = []
        
        # Add phrases as keywords
        keywords.extend(unit.phrases)
        
        # Add lemmas as keywords
        keywords.extend(unit.lemmas)
        
        # Extract from token patterns (simplified)
        for pattern in unit.token_patterns:
            for token in pattern:
                if 'LOWER' in token:
                    keywords.append(token['LOWER'])
                elif 'TEXT' in token:
                    keywords.append(token['TEXT'])
        
        return keywords
    
    def _normalize_text_like_hybrid(self, text: str) -> str:
        """Normalize text using the same logic as HybridKeywordMatcher"""
        if self.normalize_unicode:
            text = unicodedata.normalize('NFKD', text.casefold())
            text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        else:
            text = text.lower().strip()
        
        return text
    
    def _generate_patterns_like_hybrid(self, unit: IntentUnit) -> List[Dict[str, Any]]:
        """Generate patterns using logic similar to HybridKeywordMatcher"""
        patterns = []
        
        # Exact patterns from phrases
        for phrase in unit.phrases:
            patterns.append({
                'pattern': re.escape(phrase),
                'type': 'exact',
                'boost': self.exact_match_boost,
                'source': 'phrase'
            })
        
        # Flexible patterns from lemmas
        for lemma in unit.lemmas:
            # Create flexible pattern allowing word variations
            words = lemma.split()
            flexible_pattern = r'\b' + r'\s+'.join(re.escape(word) for word in words) + r'\b'
            patterns.append({
                'pattern': flexible_pattern,
                'type': 'flexible',
                'boost': self.flexible_match_boost,
                'source': 'lemma'
            })
        
        # Partial patterns (simplified)
        for phrase in unit.phrases:
            words = phrase.split()
            if len(words) > 2:
                # Create partial match patterns
                partial_pattern = r'\b' + r'.*?'.join(re.escape(word) for word in words) + r'\b'
                patterns.append({
                    'pattern': partial_pattern,
                    'type': 'partial',
                    'boost': self.partial_match_boost,
                    'source': 'phrase_partial'
                })
        
        return patterns
    
    def _estimate_pattern_compile_time(self, pattern: str) -> float:
        """Estimate regex compilation time in milliseconds"""
        # Simple heuristic based on pattern complexity
        base_time = 0.1  # Base compilation overhead
        
        # Add time for special characters
        special_chars = len(re.findall(r'[.*+?^${}()|[\]\\]', pattern))
        special_time = special_chars * 0.05
        
        # Add time for alternations
        alternations = pattern.count('|')
        alternation_time = alternations * 0.2
        
        # Add time for quantifiers
        quantifiers = len(re.findall(r'[*+?{}]', pattern))
        quantifier_time = quantifiers * 0.1
        
        return base_time + special_time + alternation_time + quantifier_time
    
    def _estimate_pattern_match_time(self, pattern: str, pattern_type: str) -> float:
        """Estimate pattern matching time in milliseconds"""
        base_time = 0.05
        
        if pattern_type == 'exact':
            return base_time
        elif pattern_type == 'flexible':
            return base_time * 2
        elif pattern_type == 'partial':
            return base_time * 4  # Partial matches are expensive
        else:
            return base_time * 1.5
    
    def _analyze_pattern_complexity(self, pattern: str) -> List[str]:
        """Analyze what makes a pattern complex"""
        complexity_reasons = []
        
        if len(pattern) > 100:
            complexity_reasons.append("Very long pattern")
        
        if pattern.count('.*') > 3:
            complexity_reasons.append("Many wildcard matches")
        
        if pattern.count('|') > 5:
            complexity_reasons.append("Many alternations")
        
        if len(re.findall(r'[*+?{}]', pattern)) > 10:
            complexity_reasons.append("Many quantifiers")
        
        return complexity_reasons
    
    def _simulate_phrase_recognition(self, phrase: str, target_unit: IntentUnit, context: List[IntentUnit]) -> Dict[str, Any]:
        """Simulate phrase recognition using simplified HybridKeywordMatcher logic"""
        best_match = None
        best_confidence = 0.0
        
        # Test against target unit and context
        all_units = [target_unit] + context
        
        for unit in all_units:
            confidence = self._calculate_match_confidence(phrase, unit)
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = unit.intent_name
        
        return {
            'intent': best_match or 'unknown',
            'confidence': best_confidence
        }
    
    def _calculate_match_confidence(self, phrase: str, unit: IntentUnit) -> float:
        """Calculate matching confidence using simplified logic"""
        phrase_normalized = self._normalize_text_like_hybrid(phrase)
        
        # Check exact phrase matches
        for unit_phrase in unit.phrases:
            unit_phrase_normalized = self._normalize_text_like_hybrid(unit_phrase)
            if phrase_normalized == unit_phrase_normalized:
                return self.pattern_confidence * self.exact_match_boost
        
        # Check lemma matches (simplified)
        phrase_words = set(phrase_normalized.split())
        for lemma in unit.lemmas:
            lemma_words = set(self._normalize_text_like_hybrid(lemma).split())
            if lemma_words.issubset(phrase_words):
                return self.pattern_confidence * self.flexible_match_boost
        
        # Check fuzzy matches if enabled
        if self.fuzzy_enabled and RAPIDFUZZ_AVAILABLE:
            keywords = self._extract_keywords_like_hybrid(unit)
            for keyword in keywords[:self.max_fuzzy_keywords_per_intent]:
                similarity = fuzz.ratio(phrase_normalized, self._normalize_text_like_hybrid(keyword)) / 100.0
                if similarity >= self.fuzzy_threshold:
                    return self.fuzzy_confidence_base * similarity
        
        return 0.0
    
    def _analyze_script_mixing(self, text: str) -> Dict[str, Any]:
        """Analyze script mixing in text"""
        scripts = set()
        
        for char in text:
            if '\u0400' <= char <= '\u04FF':  # Cyrillic
                scripts.add('cyrillic')
            elif 'A' <= char <= 'Z' or 'a' <= char <= 'z':  # Latin
                scripts.add('latin')
            elif '\u4e00' <= char <= '\u9fff':  # CJK
                scripts.add('cjk')
        
        primary_script = max(scripts, key=lambda s: sum(1 for c in text if self._char_in_script(c, s))) if scripts else 'unknown'
        
        return {
            'scripts': list(scripts),
            'mixed_scripts': len(scripts) > 1,
            'primary_script': primary_script
        }
    
    def _char_in_script(self, char: str, script: str) -> bool:
        """Check if character belongs to script"""
        if script == 'cyrillic':
            return '\u0400' <= char <= '\u04FF'
        elif script == 'latin':
            return 'A' <= char <= 'Z' or 'a' <= char <= 'z'
        elif script == 'cjk':
            return '\u4e00' <= char <= '\u9fff'
        return False
    
    def _calculate_collision_severity(self, intents: Set[str], keyword: str) -> float:
        """Calculate severity of keyword collision"""
        base_severity = min(0.9, 0.3 + (len(intents) - 2) * 0.2)
        
        # Cross-domain collisions are more severe
        domains = set()
        for intent in intents:
            domain = intent.split('.')[0] if '.' in intent else intent
            domains.add(domain)
        
        if len(domains) > 1:
            base_severity += 0.2
        
        # Short keywords are more problematic
        if len(keyword) <= 3:
            base_severity += 0.1
        
        return min(1.0, base_severity)
    
    def _analyze_keyword_efficiency(self, unit: IntentUnit, keywords: List[str]) -> Dict[str, Any]:
        """Analyze keyword efficiency metrics"""
        return {
            'keyword_count': len(keywords),
            'unique_keywords': len(set(keywords)),
            'average_keyword_length': sum(len(k) for k in keywords) / len(keywords) if keywords else 0,
            'short_keywords': len([k for k in keywords if len(k) <= 3]),
            'efficiency_score': len(set(keywords)) / len(keywords) if keywords else 1.0
        }
    
    def _calculate_std(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)
