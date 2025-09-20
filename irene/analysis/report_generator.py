"""
Report Generation Implementation

Converts raw analysis data into structured reports with actionable suggestions
and clear severity classifications for the NLU analysis system.
"""

import time
from typing import Dict, Any, List, Tuple
from .base import ReportGenerator
from .models import (
    IntentUnit,
    ConflictReport,
    ScopeIssue,
    OverlapScore,
    KeywordCollision,
    CrossHit
)


class NLUReportGenerator(ReportGenerator):
    """
    Comprehensive report generator for NLU analysis results
    
    Converts raw analysis data from conflict detectors and scope analyzers
    into structured, actionable reports with contextual suggestions.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Report generation configuration
        self.max_suggestions_per_conflict = config.get('max_suggestions_per_conflict', 5)
        self.include_technical_details = config.get('include_technical_details', True)
        self.suggestion_priority_weights = config.get('suggestion_priority_weights', {
            'blocking': 1.0,
            'warning': 0.7,
            'info': 0.4
        })
        
        # Template configurations
        self.conflict_templates = self._initialize_conflict_templates()
        self.suggestion_templates = self._initialize_suggestion_templates()
    
    def generate_conflict_report(
        self,
        intent_a: IntentUnit,
        intent_b: IntentUnit,
        analysis_data: Dict[str, Any]
    ) -> ConflictReport:
        """
        Generate a structured conflict report from analysis data
        
        Combines multiple types of analysis data into a comprehensive
        conflict report with appropriate severity and suggestions.
        """
        conflict_type = analysis_data.get('type', 'unknown')
        
        # Determine severity and score
        score = self._calculate_overall_conflict_score(analysis_data)
        severity = self._classify_conflict_severity(score)
        
        # Extract signals and evidence
        signals = self._extract_conflict_signals(analysis_data, intent_a, intent_b)
        
        # Generate context-aware suggestions
        suggestions = self.generate_suggestions(conflict_type, {
            'analysis_data': analysis_data,
            'intent_a': intent_a,
            'intent_b': intent_b,
            'score': score,
            'severity': severity
        })
        
        return ConflictReport(
            intent_a=intent_a.intent_name,
            intent_b=intent_b.intent_name,
            language=intent_a.language,  # Assume same language for conflicts
            severity=severity,
            score=score,
            conflict_type=conflict_type,
            signals=signals,
            suggestions=suggestions
        )
    
    def generate_suggestions(self, conflict_type: str, conflict_data: Dict[str, Any]) -> List[str]:
        """
        Generate actionable suggestions for resolving conflicts
        
        Creates prioritized, contextual suggestions based on conflict type,
        severity, and specific analysis evidence.
        """
        suggestions = []
        
        if conflict_type == 'phrase_overlap':
            suggestions.extend(self._generate_phrase_overlap_suggestions(conflict_data))
        elif conflict_type == 'keyword_collision':
            suggestions.extend(self._generate_keyword_collision_suggestions(conflict_data))
        elif conflict_type == 'pattern_crosshit':
            suggestions.extend(self._generate_pattern_crosshit_suggestions(conflict_data))
        elif conflict_type == 'scope_creep':
            suggestions.extend(self._generate_scope_creep_suggestions(conflict_data))
        else:
            suggestions.extend(self._generate_generic_suggestions(conflict_data))
        
        # Prioritize and limit suggestions
        prioritized = self._prioritize_suggestions(suggestions, conflict_data)
        return prioritized[:self.max_suggestions_per_conflict]
    
    def _calculate_overall_conflict_score(self, analysis_data: Dict[str, Any]) -> float:
        """
        Calculate overall conflict score from multiple analysis components
        
        Args:
            analysis_data: Raw analysis data
            
        Returns:
            Combined conflict score (0.0-1.0)
        """
        conflict_type = analysis_data.get('type', 'unknown')
        
        if conflict_type == 'phrase_overlap':
            overlap_data = analysis_data.get('overlap_score')
            if isinstance(overlap_data, OverlapScore):
                # Weight Jaccard and token F1 scores
                return (overlap_data.jaccard_similarity * 0.6) + (overlap_data.token_f1 * 0.4)
            elif isinstance(overlap_data, dict):
                jaccard = overlap_data.get('jaccard_similarity', 0.0)
                token_f1 = overlap_data.get('token_f1', 0.0)
                return (jaccard * 0.6) + (token_f1 * 0.4)
        
        elif conflict_type == 'keyword_collision':
            collision_data = analysis_data.get('collision')
            if isinstance(collision_data, KeywordCollision):
                return collision_data.severity
            elif isinstance(collision_data, dict):
                return collision_data.get('severity', 0.5)
        
        elif conflict_type == 'pattern_crosshit':
            crosshit_data = analysis_data.get('crosshit')
            if isinstance(crosshit_data, CrossHit):
                return crosshit_data.confidence
            elif isinstance(crosshit_data, dict):
                return crosshit_data.get('confidence', 0.5)
        
        # Default scoring
        return analysis_data.get('score', 0.5)
    
    def _classify_conflict_severity(self, score: float) -> str:
        """
        Classify conflict severity based on score
        
        Args:
            score: Conflict score (0.0-1.0)
            
        Returns:
            Severity level: 'blocker', 'warning', or 'info'
        """
        if score >= 0.8:
            return 'blocker'
        elif score >= 0.6:
            return 'warning'
        else:
            return 'info'
    
    def _extract_conflict_signals(
        self,
        analysis_data: Dict[str, Any],
        intent_a: IntentUnit,
        intent_b: IntentUnit
    ) -> Dict[str, Any]:
        """
        Extract structured signals and evidence from analysis data
        
        Args:
            analysis_data: Raw analysis data
            intent_a: First intent in conflict
            intent_b: Second intent in conflict
            
        Returns:
            Structured signals dictionary
        """
        signals = {
            'analysis_timestamp': time.time(),
            'intent_a_domain': self._extract_domain(intent_a.intent_name),
            'intent_b_domain': self._extract_domain(intent_b.intent_name),
            'cross_domain': self._extract_domain(intent_a.intent_name) != self._extract_domain(intent_b.intent_name)
        }
        
        conflict_type = analysis_data.get('type', 'unknown')
        
        if conflict_type == 'phrase_overlap':
            overlap_data = analysis_data.get('overlap_score')
            if isinstance(overlap_data, OverlapScore):
                signals.update({
                    'shared_phrases': overlap_data.shared_phrases,
                    'shared_tokens': overlap_data.shared_tokens,
                    'jaccard_similarity': overlap_data.jaccard_similarity,
                    'token_f1': overlap_data.token_f1,
                    'overlap_percentage': overlap_data.overlap_percentage,
                    'intent_a_unique_phrases': overlap_data.intent_a_unique,
                    'intent_b_unique_phrases': overlap_data.intent_b_unique
                })
            elif isinstance(overlap_data, dict):
                signals.update(overlap_data)
        
        elif conflict_type == 'keyword_collision':
            collision_data = analysis_data.get('collision')
            if isinstance(collision_data, KeywordCollision):
                signals.update({
                    'colliding_keyword': collision_data.keyword,
                    'collision_type': collision_data.collision_type,
                    'affected_intents': collision_data.colliding_intents
                })
            elif isinstance(collision_data, dict):
                signals.update(collision_data)
        
        elif conflict_type == 'pattern_crosshit':
            crosshit_data = analysis_data.get('crosshit')
            if isinstance(crosshit_data, CrossHit):
                signals.update({
                    'pattern': crosshit_data.pattern,
                    'matched_phrase': crosshit_data.matched_phrase,
                    'match_type': crosshit_data.match_type,
                    'confidence': crosshit_data.confidence
                })
            elif isinstance(crosshit_data, dict):
                signals.update(crosshit_data)
        
        # Add technical details if enabled
        if self.include_technical_details:
            signals['raw_analysis_data'] = analysis_data
        
        return signals
    
    def _generate_phrase_overlap_suggestions(self, conflict_data: Dict[str, Any]) -> List[str]:
        """Generate suggestions for phrase overlap conflicts"""
        suggestions = []
        analysis_data = conflict_data.get('analysis_data', {})
        overlap_score = analysis_data.get('overlap_score')
        
        if isinstance(overlap_score, (OverlapScore, dict)):
            if isinstance(overlap_score, OverlapScore):
                shared_phrases = overlap_score.shared_phrases
                jaccard = overlap_score.jaccard_similarity
            else:
                shared_phrases = overlap_score.get('shared_phrases', [])
                jaccard = overlap_score.get('jaccard_similarity', 0.0)
            
            if jaccard > 0.7:
                suggestions.append("High phrase overlap detected - consider merging these intents if they serve similar purposes")
                suggestions.append("If intents must remain separate, make their phrases more distinctive")
            elif jaccard > 0.4:
                suggestions.append("Moderate phrase overlap - review shared phrases for necessary distinctions")
            
            if shared_phrases:
                for phrase in shared_phrases[:3]:  # Limit to first 3
                    suggestions.append(f"Remove or modify shared phrase: '{phrase}'")
        
        # Add domain-specific suggestions
        intent_a = conflict_data.get('intent_a')
        intent_b = conflict_data.get('intent_b')
        if intent_a and intent_b:
            domain_a = self._extract_domain(intent_a.intent_name)
            domain_b = self._extract_domain(intent_b.intent_name)
            
            if domain_a != domain_b:
                suggestions.append(f"Cross-domain overlap between {domain_a} and {domain_b} - add domain-specific context")
            else:
                suggestions.append(f"Same-domain overlap in {domain_a} - consider intent consolidation")
        
        return suggestions
    
    def _generate_keyword_collision_suggestions(self, conflict_data: Dict[str, Any]) -> List[str]:
        """Generate suggestions for keyword collision conflicts"""
        suggestions = []
        analysis_data = conflict_data.get('analysis_data', {})
        collision = analysis_data.get('collision')
        
        if isinstance(collision, (KeywordCollision, dict)):
            if isinstance(collision, KeywordCollision):
                keyword = collision.keyword
                collision_type = collision.collision_type
                intents = collision.colliding_intents
            else:
                keyword = collision.get('keyword', 'unknown')
                collision_type = collision.get('collision_type', 'unknown')
                intents = collision.get('colliding_intents', [])
            
            if collision_type == 'exact':
                suggestions.append(f"Exact keyword collision on '{keyword}' - make keywords more specific")
                suggestions.append(f"Add domain prefixes to '{keyword}' in each intent")
            elif collision_type == 'fuzzy':
                suggestions.append(f"Fuzzy keyword collision on '{keyword}' - ensure keyword distinctiveness")
            
            if len(intents) > 2:
                suggestions.append(f"Multiple intent collision ({len(intents)} intents) - review keyword necessity")
            
            # Check for cross-domain collisions
            domains = set()
            for intent in intents:
                domains.add(self._extract_domain(intent))
            
            if len(domains) > 1:
                suggestions.append("Cross-domain keyword collision - add domain-specific context to keywords")
            else:
                suggestions.append("Same-domain collision - consider intent consolidation or keyword refinement")
        
        return suggestions
    
    def _generate_pattern_crosshit_suggestions(self, conflict_data: Dict[str, Any]) -> List[str]:
        """Generate suggestions for pattern crosshit conflicts"""
        suggestions = []
        analysis_data = conflict_data.get('analysis_data', {})
        crosshit = analysis_data.get('crosshit')
        
        if isinstance(crosshit, (CrossHit, dict)):
            if isinstance(crosshit, CrossHit):
                pattern = crosshit.pattern
                matched_phrase = crosshit.matched_phrase
                match_type = crosshit.match_type
                confidence = crosshit.confidence
            else:
                pattern = crosshit.get('pattern', 'unknown')
                matched_phrase = crosshit.get('matched_phrase', 'unknown')
                match_type = crosshit.get('match_type', 'unknown')
                confidence = crosshit.get('confidence', 0.0)
            
            suggestions.append(f"Pattern '{pattern}' incorrectly matches '{matched_phrase}'")
            
            if match_type == 'exact':
                suggestions.append("Pattern is too broad - add more specific constraints")
            elif match_type == 'partial':
                suggestions.append("Partial pattern match detected - review pattern specificity")
            elif match_type == 'fuzzy':
                suggestions.append("Fuzzy pattern match - ensure pattern distinctiveness")
            
            if confidence > 0.8:
                suggestions.append("High confidence crosshit - pattern revision strongly recommended")
            
            suggestions.append("Consider adding negative constraints to exclude unwanted matches")
        
        return suggestions
    
    def _generate_scope_creep_suggestions(self, conflict_data: Dict[str, Any]) -> List[str]:
        """Generate suggestions for scope creep issues"""
        suggestions = []
        analysis_data = conflict_data.get('analysis_data', {})
        
        suggestions.append("Scope creep detected - review intent boundaries")
        suggestions.append("Consider moving misplaced phrases to appropriate domains")
        suggestions.append("Add domain-specific context to reduce cross-domain attraction")
        
        return suggestions
    
    def _generate_generic_suggestions(self, conflict_data: Dict[str, Any]) -> List[str]:
        """Generate generic suggestions for unknown conflict types"""
        return [
            "Review intent definitions for potential conflicts",
            "Consider making intent patterns more specific",
            "Add contextual information to distinguish similar intents",
            "Test intent recognition with varied input phrases"
        ]
    
    def _prioritize_suggestions(self, suggestions: List[str], conflict_data: Dict[str, Any]) -> List[str]:
        """
        Prioritize suggestions based on conflict severity and context
        
        Args:
            suggestions: List of suggestions to prioritize
            conflict_data: Conflict context data
            
        Returns:
            Prioritized list of suggestions
        """
        severity = conflict_data.get('severity', 'info')
        weight = self.suggestion_priority_weights.get(severity, 0.5)
        
        # Simple prioritization - in practice could be more sophisticated
        # Priority keywords that boost suggestion ranking
        priority_keywords = {
            'blocking': ['merge', 'remove', 'revision strongly recommended'],
            'warning': ['review', 'consider', 'modify'],
            'info': ['test', 'add context']
        }
        
        def get_priority_score(suggestion: str) -> float:
            score = weight
            for priority_level, keywords in priority_keywords.items():
                for keyword in keywords:
                    if keyword.lower() in suggestion.lower():
                        if priority_level == 'blocking':
                            score += 0.3
                        elif priority_level == 'warning':
                            score += 0.2
                        else:
                            score += 0.1
            return score
        
        # Sort by priority score (descending)
        prioritized = sorted(suggestions, key=get_priority_score, reverse=True)
        return prioritized
    
    def _extract_domain(self, intent_name: str) -> str:
        """Extract domain from intent name"""
        return intent_name.split('.')[0] if '.' in intent_name else intent_name
    
    def _initialize_conflict_templates(self) -> Dict[str, Dict[str, str]]:
        """Initialize conflict report templates"""
        return {
            'phrase_overlap': {
                'title': 'Phrase Overlap Conflict',
                'description': 'Intents share similar phrases that may cause recognition conflicts'
            },
            'keyword_collision': {
                'title': 'Keyword Collision',
                'description': 'Multiple intents use the same keywords in their recognition patterns'
            },
            'pattern_crosshit': {
                'title': 'Pattern Cross-Hit',
                'description': 'Recognition pattern incorrectly matches phrases from other intents'
            },
            'scope_creep': {
                'title': 'Scope Creep',
                'description': 'Intent contains phrases that belong to other domains'
            }
        }
    
    def _initialize_suggestion_templates(self) -> Dict[str, List[str]]:
        """Initialize suggestion templates for different conflict types"""
        return {
            'phrase_overlap': [
                "Make phrases more distinctive between intents",
                "Remove shared phrases that cause ambiguity",
                "Add domain-specific context to shared phrases"
            ],
            'keyword_collision': [
                "Use unique keywords for each intent",
                "Add domain prefixes to keywords",
                "Review keyword necessity and specificity"
            ],
            'pattern_crosshit': [
                "Make patterns more specific with additional constraints",
                "Add negative patterns to exclude unwanted matches",
                "Review pattern scope and specificity"
            ],
            'scope_creep': [
                "Move misplaced phrases to appropriate domains",
                "Add domain-specific context",
                "Review intent boundaries and purpose"
            ]
        }
