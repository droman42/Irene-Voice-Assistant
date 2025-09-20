"""
SpaCy Provider Analysis Mirror

Mirrors the behavior and logic of the SpaCy NLU provider to detect
semantic conflicts and language processing issues.
"""

import time
from typing import Dict, Any, List, Set, Optional, Tuple
from collections import defaultdict

from .base import BaseAnalyzer
from .models import IntentUnit

# SpaCy is optional - analysis works without it but with reduced capabilities
try:
    import spacy
    from spacy.matcher import Matcher
    from spacy.tokens import Doc, Token
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False


class SpacyProviderAnalyzer(BaseAnalyzer):
    """
    Analysis mirror of SpaCy NLU provider
    
    Simulates SpaCy's semantic analysis capabilities to detect conflicts
    and issues that may not be caught by keyword-based analysis.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Mirror SpaCy provider configuration
        self.confidence_threshold = config.get('confidence_threshold', 0.7)
        self.similarity_threshold = config.get('similarity_threshold', 0.8)
        self.max_entities_per_intent = config.get('max_entities_per_intent', 10)
        
        # Model configuration (mirror Phase 1 improvements)
        self.language_models = config.get('language_models', {
            'ru': ['ru_core_news_md', 'ru_core_news_sm'],
            'en': ['en_core_web_md', 'en_core_web_sm']
        })
        
        # Analysis-specific settings
        self.semantic_analysis_enabled = config.get('semantic_analysis_enabled', True)
        self.entity_analysis_enabled = config.get('entity_analysis_enabled', True)
        self.similarity_analysis_enabled = config.get('similarity_analysis_enabled', True)
        self.pattern_validation_enabled = config.get('pattern_validation_enabled', True)
        
        # Initialize SpaCy models if available
        self.available_models = {}
        self.matchers = {}
        
        if SPACY_AVAILABLE:
            self._initialize_models()
        else:
            self.logger.warning("SpaCy not available - analysis will be limited")
    
    def _initialize_models(self):
        """Initialize SpaCy models for available languages"""
        for language, model_names in self.language_models.items():
            for model_name in model_names:
                try:
                    nlp = spacy.load(model_name)
                    self.available_models[language] = nlp
                    self.matchers[language] = Matcher(nlp.vocab)
                    self.logger.info(f"Loaded SpaCy model {model_name} for {language}")
                    break  # Use first available model
                except OSError:
                    continue
            
            if language not in self.available_models:
                self.logger.warning(f"No SpaCy model available for {language}")
    
    async def analyze_intent_unit(self, unit: IntentUnit, context: List[IntentUnit]) -> Dict[str, Any]:
        """
        Analyze intent unit using SpaCy semantic capabilities
        
        Performs semantic similarity analysis, entity extraction validation,
        and pattern matching analysis.
        """
        start_time = time.time()
        analysis_results = {}
        
        # Check if we have a model for this language
        if unit.language not in self.available_models:
            analysis_results['model_availability'] = {
                'available': False,
                'language': unit.language,
                'fallback_analysis': True
            }
            # Perform limited analysis without SpaCy
            return self._fallback_analysis(unit, context, start_time)
        
        nlp = self.available_models[unit.language]
        
        # 1. Semantic similarity analysis
        if self.semantic_analysis_enabled:
            similarity_analysis = self._analyze_semantic_similarity(unit, context, nlp)
            analysis_results['similarity_analysis'] = similarity_analysis
        
        # 2. Entity extraction analysis
        if self.entity_analysis_enabled:
            entity_analysis = self._analyze_entity_extraction(unit, nlp)
            analysis_results['entity_analysis'] = entity_analysis
        
        # 3. Pattern validation analysis
        if self.pattern_validation_enabled:
            pattern_analysis = self._analyze_pattern_validity(unit, nlp)
            analysis_results['pattern_analysis'] = pattern_analysis
        
        # 4. Language quality analysis
        language_analysis = self._analyze_language_quality(unit, nlp)
        analysis_results['language_analysis'] = language_analysis
        
        # 5. Cross-intent semantic conflicts
        conflict_analysis = self._analyze_semantic_conflicts(unit, context, nlp)
        analysis_results['conflict_analysis'] = conflict_analysis
        
        analysis_time_ms = (time.time() - start_time) * 1000
        self.update_stats(analysis_time_ms)
        
        analysis_results.update({
            'analyzer': 'spacy_provider',
            'model_used': nlp.meta.get('name', 'unknown') if nlp else None,
            'language': unit.language,
            'analysis_time_ms': analysis_time_ms,
            'capabilities_used': self.get_analysis_capabilities()
        })
        
        return analysis_results
    
    def get_analysis_capabilities(self) -> List[str]:
        """Get list of analysis capabilities"""
        capabilities = [
            'semantic_similarity_analysis',
            'entity_extraction_validation',
            'pattern_validity_checking',
            'language_quality_analysis',
            'cross_intent_semantic_conflicts'
        ]
        
        if not SPACY_AVAILABLE:
            capabilities.append('limited_fallback_analysis')
        
        return capabilities
    
    def _analyze_semantic_similarity(self, unit: IntentUnit, context: List[IntentUnit], nlp) -> Dict[str, Any]:
        """
        Analyze semantic similarity between intents using SpaCy vectors
        
        Detects intents that are semantically similar and may cause confusion.
        """
        analysis = {
            'similar_intents': [],
            'similarity_matrix': {},
            'average_similarity': 0.0,
            'max_similarity': 0.0
        }
        
        if not nlp.meta.get('vectors', 0):
            analysis['vectors_available'] = False
            return analysis
        
        # Get document vectors for this unit
        unit_texts = unit.get_all_text_content()
        unit_docs = [nlp(text) for text in unit_texts if text.strip()]
        
        if not unit_docs:
            return analysis
        
        # Calculate average vector for this intent
        unit_vector = self._calculate_average_vector(unit_docs)
        
        similarities = []
        
        # Compare with context intents in the same language
        same_language_context = [u for u in context if u.language == unit.language]
        
        for context_unit in same_language_context:
            context_texts = context_unit.get_all_text_content()
            context_docs = [nlp(text) for text in context_texts if text.strip()]
            
            if not context_docs:
                continue
            
            context_vector = self._calculate_average_vector(context_docs)
            
            if unit_vector is not None and context_vector is not None:
                similarity = unit_vector.similarity(context_vector)
                similarities.append(similarity)
                
                analysis['similarity_matrix'][context_unit.intent_name] = similarity
                
                if similarity >= self.similarity_threshold:
                    analysis['similar_intents'].append({
                        'intent': context_unit.intent_name,
                        'similarity': similarity,
                        'domain_match': self._extract_domain(unit.intent_name) == self._extract_domain(context_unit.intent_name)
                    })
        
        if similarities:
            analysis['average_similarity'] = sum(similarities) / len(similarities)
            analysis['max_similarity'] = max(similarities)
        
        return analysis
    
    def _analyze_entity_extraction(self, unit: IntentUnit, nlp) -> Dict[str, Any]:
        """
        Analyze entity extraction patterns and parameter alignment
        
        Validates that SpaCy patterns will correctly extract the intended entities.
        """
        analysis = {
            'valid_patterns': 0,
            'invalid_patterns': [],
            'entity_coverage': {},
            'parameter_alignment': [],
            'extraction_test_results': []
        }
        
        # Test token patterns
        for i, token_pattern in enumerate(unit.token_patterns):
            try:
                # Validate pattern structure
                pattern_valid = self._validate_token_pattern(token_pattern, nlp)
                if pattern_valid:
                    analysis['valid_patterns'] += 1
                else:
                    analysis['invalid_patterns'].append({
                        'pattern_index': i,
                        'pattern': token_pattern,
                        'error': 'Invalid pattern structure'
                    })
            except Exception as e:
                analysis['invalid_patterns'].append({
                    'pattern_index': i,
                    'pattern': token_pattern,
                    'error': str(e)
                })
        
        # Test slot patterns
        for slot_name, slot_patterns in unit.slot_patterns.items():
            slot_results = []
            for pattern in slot_patterns:
                try:
                    pattern_valid = self._validate_token_pattern(pattern, nlp)
                    slot_results.append(pattern_valid)
                except Exception:
                    slot_results.append(False)
            
            analysis['entity_coverage'][slot_name] = {
                'total_patterns': len(slot_patterns),
                'valid_patterns': sum(slot_results),
                'coverage_ratio': sum(slot_results) / len(slot_patterns) if slot_patterns else 0
            }
        
        # Test parameter extraction with examples
        for example in unit.examples:
            if isinstance(example, dict) and 'text' in example:
                extraction_result = self._test_parameter_extraction(
                    example['text'], 
                    example.get('parameters', {}), 
                    unit, 
                    nlp
                )
                analysis['extraction_test_results'].append(extraction_result)
        
        return analysis
    
    def _analyze_pattern_validity(self, unit: IntentUnit, nlp) -> Dict[str, Any]:
        """
        Analyze validity and efficiency of SpaCy patterns
        
        Checks pattern syntax, performance implications, and match accuracy.
        """
        analysis = {
            'pattern_count': len(unit.token_patterns) + sum(len(patterns) for patterns in unit.slot_patterns.values()),
            'syntax_errors': [],
            'performance_warnings': [],
            'pattern_efficiency': {},
            'match_test_results': []
        }
        
        # Test token patterns
        for i, pattern in enumerate(unit.token_patterns):
            pattern_analysis = self._analyze_single_pattern(pattern, f"token_pattern_{i}", nlp)
            
            if pattern_analysis['syntax_error']:
                analysis['syntax_errors'].append({
                    'pattern_type': 'token_pattern',
                    'pattern_index': i,
                    'error': pattern_analysis['syntax_error']
                })
            
            if pattern_analysis['performance_warning']:
                analysis['performance_warnings'].append({
                    'pattern_type': 'token_pattern',
                    'pattern_index': i,
                    'warning': pattern_analysis['performance_warning']
                })
            
            analysis['pattern_efficiency'][f"token_pattern_{i}"] = pattern_analysis['efficiency_score']
        
        # Test slot patterns
        for slot_name, slot_patterns in unit.slot_patterns.items():
            for i, pattern in enumerate(slot_patterns):
                pattern_analysis = self._analyze_single_pattern(pattern, f"{slot_name}_{i}", nlp)
                
                if pattern_analysis['syntax_error']:
                    analysis['syntax_errors'].append({
                        'pattern_type': 'slot_pattern',
                        'slot_name': slot_name,
                        'pattern_index': i,
                        'error': pattern_analysis['syntax_error']
                    })
                
                analysis['pattern_efficiency'][f"{slot_name}_{i}"] = pattern_analysis['efficiency_score']
        
        # Test patterns against example texts
        for example in unit.examples:
            if isinstance(example, dict) and 'text' in example:
                match_result = self._test_pattern_matching(example['text'], unit, nlp)
                analysis['match_test_results'].append(match_result)
        
        return analysis
    
    def _analyze_language_quality(self, unit: IntentUnit, nlp) -> Dict[str, Any]:
        """
        Analyze language quality and linguistic issues
        
        Checks for grammar, vocabulary, and linguistic consistency issues.
        """
        analysis = {
            'grammar_issues': [],
            'vocabulary_quality': {},
            'linguistic_consistency': {},
            'pos_distribution': {},
            'readability_score': 0.0
        }
        
        all_texts = unit.get_all_text_content()
        docs = [nlp(text) for text in all_texts if text.strip()]
        
        if not docs:
            return analysis
        
        # Analyze POS distribution
        pos_counts = defaultdict(int)
        total_tokens = 0
        
        for doc in docs:
            for token in doc:
                if not token.is_space and not token.is_punct:
                    pos_counts[token.pos_] += 1
                    total_tokens += 1
        
        if total_tokens > 0:
            analysis['pos_distribution'] = {
                pos: count / total_tokens 
                for pos, count in pos_counts.items()
            }
        
        # Check for grammar issues (simplified)
        for i, doc in enumerate(docs):
            text = all_texts[i]
            grammar_issues = self._check_grammar_issues(doc, text)
            if grammar_issues:
                analysis['grammar_issues'].extend(grammar_issues)
        
        # Vocabulary quality analysis
        unique_lemmas = set()
        total_words = 0
        
        for doc in docs:
            for token in doc:
                if token.is_alpha and not token.is_stop:
                    unique_lemmas.add(token.lemma_)
                    total_words += 1
        
        analysis['vocabulary_quality'] = {
            'unique_lemmas': len(unique_lemmas),
            'total_words': total_words,
            'vocabulary_diversity': len(unique_lemmas) / total_words if total_words > 0 else 0,
            'average_word_length': sum(len(text.split()) for text in all_texts) / len(all_texts) if all_texts else 0
        }
        
        return analysis
    
    def _analyze_semantic_conflicts(self, unit: IntentUnit, context: List[IntentUnit], nlp) -> Dict[str, Any]:
        """
        Analyze semantic conflicts between intents
        
        Uses SpaCy's semantic understanding to detect conflicts that keyword
        analysis might miss.
        """
        analysis = {
            'semantic_overlaps': [],
            'conceptual_conflicts': [],
            'domain_boundary_issues': []
        }
        
        if not nlp.meta.get('vectors', 0):
            analysis['vectors_available'] = False
            return analysis
        
        unit_texts = unit.get_all_text_content()
        unit_docs = [nlp(text) for text in unit_texts if text.strip()]
        
        same_language_context = [u for u in context if u.language == unit.language]
        
        for context_unit in same_language_context:
            context_texts = context_unit.get_all_text_content()
            context_docs = [nlp(text) for text in context_texts if text.strip()]
            
            # Check for semantic overlaps at phrase level
            for unit_doc in unit_docs:
                for context_doc in context_docs:
                    if unit_doc.similarity(context_doc) >= self.similarity_threshold:
                        analysis['semantic_overlaps'].append({
                            'unit_phrase': unit_doc.text,
                            'context_phrase': context_doc.text,
                            'context_intent': context_unit.intent_name,
                            'similarity': unit_doc.similarity(context_doc)
                        })
            
            # Check for conceptual conflicts
            unit_domain = self._extract_domain(unit.intent_name)
            context_domain = self._extract_domain(context_unit.intent_name)
            
            if unit_domain != context_domain:
                # Cross-domain semantic similarity indicates potential confusion
                avg_similarity = self._calculate_average_similarity(unit_docs, context_docs)
                if avg_similarity > 0.6:  # Lower threshold for cross-domain
                    analysis['domain_boundary_issues'].append({
                        'unit_domain': unit_domain,
                        'context_domain': context_domain,
                        'context_intent': context_unit.intent_name,
                        'average_similarity': avg_similarity
                    })
        
        return analysis
    
    def _fallback_analysis(self, unit: IntentUnit, context: List[IntentUnit], start_time: float) -> Dict[str, Any]:
        """
        Perform limited analysis when SpaCy is not available
        
        Uses basic text analysis techniques as fallback.
        """
        analysis_time_ms = (time.time() - start_time) * 1000
        
        return {
            'analyzer': 'spacy_provider_fallback',
            'spacy_available': False,
            'language': unit.language,
            'analysis_time_ms': analysis_time_ms,
            'basic_analysis': {
                'phrase_count': len(unit.phrases),
                'lemma_count': len(unit.lemmas),
                'example_count': len(unit.examples),
                'pattern_count': len(unit.token_patterns),
                'parameter_count': len(unit.parameters)
            },
            'recommendations': [
                "Install SpaCy and language models for comprehensive analysis",
                f"Recommended models for {unit.language}: {self.language_models.get(unit.language, ['unknown'])}"
            ],
            'capabilities_used': ['basic_text_analysis']
        }
    
    # Helper methods
    
    def _calculate_average_vector(self, docs: List) -> Optional[Any]:
        """Calculate average vector from list of SpaCy docs"""
        if not docs or not hasattr(docs[0], 'vector'):
            return None
        
        vectors = [doc.vector for doc in docs if doc.has_vector]
        if not vectors:
            return None
        
        # Simple average - could be improved with weighted averaging
        import numpy as np
        avg_vector = np.mean(vectors, axis=0)
        
        # Create a mock doc with the average vector for similarity calculation
        # This is a simplified approach - in practice would need more sophisticated handling
        return type('MockDoc', (), {'vector': avg_vector, 'similarity': lambda self, other: np.dot(self.vector, other.vector) / (np.linalg.norm(self.vector) * np.linalg.norm(other.vector))})()
    
    def _calculate_average_similarity(self, docs_a: List, docs_b: List) -> float:
        """Calculate average similarity between two sets of documents"""
        if not docs_a or not docs_b:
            return 0.0
        
        similarities = []
        for doc_a in docs_a:
            for doc_b in docs_b:
                if hasattr(doc_a, 'similarity') and hasattr(doc_b, 'similarity'):
                    similarities.append(doc_a.similarity(doc_b))
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _validate_token_pattern(self, pattern: List[Dict[str, Any]], nlp) -> bool:
        """Validate SpaCy token pattern syntax"""
        try:
            # Create a temporary matcher to test pattern
            matcher = Matcher(nlp.vocab)
            matcher.add("test_pattern", [pattern])
            return True
        except Exception:
            return False
    
    def _analyze_single_pattern(self, pattern: List[Dict[str, Any]], pattern_id: str, nlp) -> Dict[str, Any]:
        """Analyze a single SpaCy pattern for issues"""
        analysis = {
            'syntax_error': None,
            'performance_warning': None,
            'efficiency_score': 1.0
        }
        
        try:
            # Test pattern syntax
            matcher = Matcher(nlp.vocab)
            matcher.add("test_pattern", [pattern])
            
            # Check for performance issues
            if len(pattern) > 10:
                analysis['performance_warning'] = "Very long pattern may be slow"
                analysis['efficiency_score'] *= 0.8
            
            # Check for overly broad patterns
            broad_tokens = sum(1 for token in pattern if len(token) <= 1)
            if broad_tokens > len(pattern) * 0.5:
                analysis['performance_warning'] = "Pattern may be too broad"
                analysis['efficiency_score'] *= 0.7
            
        except Exception as e:
            analysis['syntax_error'] = str(e)
            analysis['efficiency_score'] = 0.0
        
        return analysis
    
    def _test_parameter_extraction(self, text: str, expected_params: Dict[str, Any], unit: IntentUnit, nlp) -> Dict[str, Any]:
        """Test parameter extraction accuracy"""
        result = {
            'text': text,
            'expected_parameters': expected_params,
            'extraction_success': False,
            'extracted_parameters': {},
            'missing_parameters': [],
            'extra_parameters': []
        }
        
        # This is a simplified test - real implementation would use the actual
        # parameter extraction logic from the SpaCy provider
        doc = nlp(text)
        
        # For now, just check if the expected parameters could theoretically be extracted
        # based on entities found in the text
        for param_name, param_value in expected_params.items():
            # Simple entity matching
            found = False
            for ent in doc.ents:
                if str(param_value).lower() in ent.text.lower():
                    result['extracted_parameters'][param_name] = ent.text
                    found = True
                    break
            
            if not found:
                result['missing_parameters'].append(param_name)
        
        result['extraction_success'] = len(result['missing_parameters']) == 0
        
        return result
    
    def _test_pattern_matching(self, text: str, unit: IntentUnit, nlp) -> Dict[str, Any]:
        """Test pattern matching against text"""
        result = {
            'text': text,
            'pattern_matches': 0,
            'total_patterns': len(unit.token_patterns),
            'match_success': False
        }
        
        doc = nlp(text)
        matcher = Matcher(nlp.vocab)
        
        # Test each token pattern
        for i, pattern in enumerate(unit.token_patterns):
            try:
                pattern_id = f"pattern_{i}"
                matcher.add(pattern_id, [pattern])
                matches = matcher(doc)
                if matches:
                    result['pattern_matches'] += 1
                matcher.remove(pattern_id)
            except Exception:
                pass  # Skip invalid patterns
        
        result['match_success'] = result['pattern_matches'] > 0
        
        return result
    
    def _check_grammar_issues(self, doc, text: str) -> List[Dict[str, Any]]:
        """Check for basic grammar issues (simplified)"""
        issues = []
        
        # Very basic checks - real implementation would be more sophisticated
        
        # Check for missing punctuation
        if not text.strip().endswith(('.', '!', '?')):
            issues.append({
                'type': 'missing_punctuation',
                'text': text,
                'suggestion': 'Consider adding proper punctuation'
            })
        
        # Check for very short or long sentences
        if len(text.split()) < 2:
            issues.append({
                'type': 'too_short',
                'text': text,
                'suggestion': 'Very short phrase may be ambiguous'
            })
        elif len(text.split()) > 20:
            issues.append({
                'type': 'too_long',
                'text': text,
                'suggestion': 'Very long phrase may be hard to match'
            })
        
        return issues
    
    def _extract_domain(self, intent_name: str) -> str:
        """Extract domain from intent name"""
        return intent_name.split('.')[0] if '.' in intent_name else intent_name
