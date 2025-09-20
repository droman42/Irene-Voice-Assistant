"""
Base Interfaces for NLU Analysis System

Defines abstract base classes and interfaces for analysis components,
ensuring consistent API across all analyzers and detectors.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from .models import (
    IntentUnit,
    ConflictReport,
    ScopeIssue,
    BreadthAnalysis,
    OverlapScore,
    KeywordCollision,
    CrossHit,
    AnalysisResult,
    ValidationResult,
    BatchAnalysisResult
)

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """
    Base class for NLU provider analyzers
    
    Analyzers mirror the behavior of actual NLU providers to detect
    conflicts and issues without affecting the live system.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Performance tracking
        self.analysis_stats = {
            'total_analyses': 0,
            'avg_time_ms': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    @abstractmethod
    async def analyze_intent_unit(self, unit: IntentUnit, context: List[IntentUnit]) -> Dict[str, Any]:
        """
        Analyze a single intent unit in the context of other intents
        
        Args:
            unit: Intent unit to analyze
            context: Other intent units for comparison
            
        Returns:
            Analysis results specific to this analyzer
        """
        pass
    
    @abstractmethod
    def get_analysis_capabilities(self) -> List[str]:
        """
        Get list of analysis capabilities provided by this analyzer
        
        Returns:
            List of capability names
        """
        pass
    
    def update_stats(self, analysis_time_ms: float, used_cache: bool = False):
        """Update performance statistics"""
        self.analysis_stats['total_analyses'] += 1
        
        # Update running average
        current_avg = self.analysis_stats['avg_time_ms']
        n = self.analysis_stats['total_analyses']
        self.analysis_stats['avg_time_ms'] = ((current_avg * (n - 1)) + analysis_time_ms) / n
        
        if used_cache:
            self.analysis_stats['cache_hits'] += 1
        else:
            self.analysis_stats['cache_misses'] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer performance statistics"""
        return self.analysis_stats.copy()


class ConflictDetector(ABC):
    """
    Base class for conflict detection algorithms
    
    Implements various strategies for detecting conflicts between intents,
    including phrase overlap, keyword collisions, and pattern cross-hits.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Conflict detection thresholds
        self.blocker_threshold = config.get('blocker_threshold', 0.8)
        self.warning_threshold = config.get('warning_threshold', 0.6)
        self.info_threshold = config.get('info_threshold', 0.4)
    
    @abstractmethod
    def detect_phrase_overlap(self, intent_a: IntentUnit, intent_b: IntentUnit) -> OverlapScore:
        """
        Detect phrase overlap between two intents using Jaccard similarity and token F1
        
        Args:
            intent_a: First intent unit
            intent_b: Second intent unit
            
        Returns:
            Overlap score with detailed metrics
        """
        pass
    
    @abstractmethod
    def detect_keyword_collisions(self, units: List[IntentUnit]) -> List[KeywordCollision]:
        """
        Detect keyword collisions by mirroring hybrid provider's keyword mapping logic
        
        Args:
            units: List of intent units to analyze
            
        Returns:
            List of detected keyword collisions
        """
        pass
    
    @abstractmethod
    def detect_pattern_crosshits(self, intent_a: IntentUnit, intent_b: IntentUnit) -> List[CrossHit]:
        """
        Test flexible/partial patterns against rival phrases
        
        Args:
            intent_a: Intent with patterns to test
            intent_b: Intent with phrases to test against
            
        Returns:
            List of detected cross-hits
        """
        pass
    
    def calculate_ambiguity_score(self, conflicts: List[Dict[str, Any]]) -> float:
        """
        Calculate weighted ambiguity score from multiple conflict types
        
        Weighted scoring: 0.4*surface + 0.3*hybrid + 0.3*spacy
        
        Args:
            conflicts: List of conflict analysis results
            
        Returns:
            Weighted ambiguity score (0.0-1.0)
        """
        if not conflicts:
            return 0.0
        
        weights = {
            'surface': 0.4,
            'hybrid': 0.3,
            'spacy': 0.3
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for conflict in conflicts:
            conflict_type = conflict.get('type', 'surface')
            score = conflict.get('score', 0.0)
            weight = weights.get(conflict_type, 0.1)
            
            weighted_sum += score * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def classify_severity(self, score: float) -> str:
        """
        Classify conflict severity based on score
        
        Args:
            score: Conflict score (0.0-1.0)
            
        Returns:
            Severity level: 'blocker', 'warning', or 'info'
        """
        if score >= self.blocker_threshold:
            return 'blocker'
        elif score >= self.warning_threshold:
            return 'warning'
        else:
            return 'info'


class ScopeAnalyzer(ABC):
    """
    Base class for scope creep and domain boundary analysis
    
    Detects when intents accumulate phrases or patterns that belong
    to other domains, creating unwanted cross-domain attraction.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Scope analysis thresholds
        self.cross_domain_threshold = config.get('cross_domain_threshold', 0.7)
        self.breadth_threshold = config.get('breadth_threshold', 0.8)
    
    @abstractmethod
    def detect_cross_domain_attraction(self, intent: IntentUnit, corpus: List[IntentUnit]) -> List[ScopeIssue]:
        """
        Find phrases that belong to other domains
        
        Args:
            intent: Intent unit to analyze
            corpus: Full corpus of intent units for comparison
            
        Returns:
            List of detected scope issues
        """
        pass
    
    @abstractmethod
    def analyze_pattern_breadth(self, intent: IntentUnit) -> BreadthAnalysis:
        """
        Detect overly broad patterns that steal traffic from other intents
        
        Args:
            intent: Intent unit to analyze
            
        Returns:
            Breadth analysis with specificity recommendations
        """
        pass
    
    def extract_domain_from_intent(self, intent_name: str) -> str:
        """
        Extract domain from intent name (e.g., 'timer.set' -> 'timer')
        
        Args:
            intent_name: Full intent name
            
        Returns:
            Domain portion of intent name
        """
        return intent_name.split('.')[0] if '.' in intent_name else intent_name
    
    def calculate_domain_affinity(self, phrase: str, domain_corpus: List[str]) -> float:
        """
        Calculate how much a phrase belongs to a specific domain
        
        Args:
            phrase: Phrase to analyze
            domain_corpus: List of phrases from the domain
            
        Returns:
            Affinity score (0.0-1.0)
        """
        # Simple implementation - can be enhanced with semantic similarity
        phrase_tokens = set(phrase.lower().split())
        
        total_overlap = 0
        for corpus_phrase in domain_corpus:
            corpus_tokens = set(corpus_phrase.lower().split())
            overlap = len(phrase_tokens & corpus_tokens)
            total_overlap += overlap
        
        max_possible = len(phrase_tokens) * len(domain_corpus)
        return total_overlap / max_possible if max_possible > 0 else 0.0


class ReportGenerator(ABC):
    """
    Base class for analysis result formatting and report generation
    
    Converts raw analysis data into structured reports with actionable
    suggestions and clear severity classifications.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def generate_conflict_report(
        self,
        intent_a: IntentUnit,
        intent_b: IntentUnit,
        analysis_data: Dict[str, Any]
    ) -> ConflictReport:
        """
        Generate a structured conflict report from analysis data
        
        Args:
            intent_a: First intent in conflict
            intent_b: Second intent in conflict
            analysis_data: Raw analysis results
            
        Returns:
            Structured conflict report
        """
        pass
    
    @abstractmethod
    def generate_suggestions(self, conflict_type: str, conflict_data: Dict[str, Any]) -> List[str]:
        """
        Generate actionable suggestions for resolving conflicts
        
        Args:
            conflict_type: Type of conflict detected
            conflict_data: Conflict analysis data
            
        Returns:
            List of actionable suggestions
        """
        pass
    
    def format_analysis_result(
        self,
        conflicts: List[ConflictReport],
        scope_issues: List[ScopeIssue],
        performance_metrics: Dict[str, float],
        analysis_time_ms: float
    ) -> AnalysisResult:
        """
        Format comprehensive analysis result
        
        Args:
            conflicts: List of detected conflicts
            scope_issues: List of detected scope issues
            performance_metrics: Analysis performance metrics
            analysis_time_ms: Time taken for analysis
            
        Returns:
            Formatted analysis result
        """
        # Calculate language coverage from conflicts and scope issues
        language_coverage = {}
        all_languages = set()
        
        for conflict in conflicts:
            all_languages.add(conflict.language)
        for issue in scope_issues:
            all_languages.add(issue.language)
        
        # Simple coverage calculation - can be enhanced
        for lang in all_languages:
            lang_conflicts = [c for c in conflicts if c.language == lang]
            lang_issues = [i for i in scope_issues if i.language == lang]
            
            # Coverage = 1 - (conflicts + issues) / total_possible_issues
            total_issues = len(lang_conflicts) + len(lang_issues)
            coverage = max(0.0, 1.0 - (total_issues * 0.1))  # Simple heuristic
            language_coverage[lang] = coverage
        
        return AnalysisResult(
            conflicts=conflicts,
            scope_issues=scope_issues,
            performance_metrics=performance_metrics,
            language_coverage=language_coverage,
            analysis_time_ms=analysis_time_ms
        )
