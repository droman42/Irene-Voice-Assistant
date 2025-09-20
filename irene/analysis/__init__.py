"""
NLU Analysis System - Phase 2 Implementation

Real-time analysis and conflict detection for the Irene Voice Assistant's
Natural Language Understanding system.

Provides:
- Analysis interfaces and base classes
- Provider-faithful analysis mirrors (HybridKeywordMatcher, SpaCy)
- Conflict detection algorithms
- Scope creep analysis
- Report generation and formatting
"""

from .models import (
    ConflictReport,
    ValidationResult,
    AnalysisResult,
    ChangeImpactAnalysis,
    BatchAnalysisResult,
    SystemHealthReport,
    ScopeIssue,
    BreadthAnalysis,
    OverlapScore,
    KeywordCollision,
    CrossHit,
    IntentUnit
)

from .base import (
    BaseAnalyzer,
    ConflictDetector,
    ScopeAnalyzer,
    ReportGenerator
)

__all__ = [
    # Data models
    'ConflictReport',
    'ValidationResult', 
    'AnalysisResult',
    'ChangeImpactAnalysis',
    'BatchAnalysisResult',
    'SystemHealthReport',
    'ScopeIssue',
    'BreadthAnalysis',
    'OverlapScore',
    'KeywordCollision',
    'CrossHit',
    'IntentUnit',
    
    # Base interfaces
    'BaseAnalyzer',
    'ConflictDetector',
    'ScopeAnalyzer',
    'ReportGenerator'
]
