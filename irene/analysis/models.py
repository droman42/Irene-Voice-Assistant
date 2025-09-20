"""
Data Models for NLU Analysis System

Contains all Pydantic models and dataclasses used by the analysis system
for representing conflicts, validation results, and analysis reports.
"""

import time
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass
from pydantic import BaseModel, Field


# ============================================================
# CORE ANALYSIS DATA STRUCTURES
# ============================================================

@dataclass
class IntentUnit:
    """Unit of analysis representing an intent's donation data"""
    intent_name: str
    handler_name: str
    language: str
    
    # Donation content
    phrases: List[str]
    lemmas: List[str]
    token_patterns: List[List[Dict[str, Any]]]
    slot_patterns: Dict[str, List[List[Dict[str, Any]]]]
    examples: List[Dict[str, Any]]
    parameters: List[Dict[str, Any]]
    
    # Metadata
    boost: float = 1.0
    method_name: str = ""
    intent_suffix: str = ""
    
    def get_all_text_content(self) -> List[str]:
        """Get all textual content for analysis"""
        content = self.phrases.copy()
        content.extend(self.lemmas)
        
        # Extract text from examples
        for example in self.examples:
            if isinstance(example, dict) and 'text' in example:
                content.append(example['text'])
            elif isinstance(example, str):
                content.append(example)
        
        return content
    
    def get_keywords(self) -> List[str]:
        """Extract keywords similar to HybridKeywordMatcher logic"""
        keywords = []
        
        # Add phrases as keywords
        keywords.extend(self.phrases)
        
        # Add lemmas as keywords 
        keywords.extend(self.lemmas)
        
        # Extract keywords from token patterns (simplified)
        for pattern in self.token_patterns:
            for token in pattern:
                if 'LOWER' in token:
                    keywords.append(token['LOWER'])
                elif 'TEXT' in token:
                    keywords.append(token['TEXT'])
        
        return keywords


@dataclass
class OverlapScore:
    """Result of phrase overlap analysis between two intents"""
    jaccard_similarity: float
    token_f1: float
    shared_phrases: List[str]
    shared_tokens: List[str]
    intent_a_unique: List[str]
    intent_b_unique: List[str]
    overlap_percentage: float


@dataclass
class KeywordCollision:
    """Represents a keyword collision in the global keyword map"""
    keyword: str
    colliding_intents: List[str]
    collision_type: str  # "exact", "fuzzy", "pattern"
    severity: float  # 0.0-1.0


@dataclass
class CrossHit:
    """Represents a pattern that matches phrases from another intent"""
    pattern: str
    pattern_intent: str
    matched_phrase: str
    target_intent: str
    match_type: str  # "exact", "partial", "fuzzy"
    confidence: float


# ============================================================
# CONFLICT REPORTS AND ANALYSIS RESULTS
# ============================================================

class ConflictReport(BaseModel):
    """Report of a conflict between two intents"""
    intent_a: str = Field(description="First intent in conflict")
    intent_b: str = Field(description="Second intent in conflict")
    language: str = Field(description="Language where conflict occurs")
    severity: Literal['blocker', 'warning', 'info'] = Field(description="Conflict severity")
    score: float = Field(description="Conflict strength score (0.0-1.0)", ge=0.0, le=1.0)
    conflict_type: str = Field(description="Type of conflict detected")
    signals: Dict[str, Any] = Field(description="Evidence and analysis details")
    suggestions: List[str] = Field(description="Suggested resolutions")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "intent_a": "timer.set",
                    "intent_b": "datetime.current_time",
                    "language": "en",
                    "severity": "warning",
                    "score": 0.75,
                    "conflict_type": "phrase_overlap",
                    "signals": {
                        "shared_phrases": ["set time", "time setting"],
                        "overlap_percentage": 0.4
                    },
                    "suggestions": [
                        "Make 'timer.set' phrases more specific: 'set timer for X'",
                        "Consider removing generic 'set time' from timer domain"
                    ]
                }
            ]
        }


class ScopeIssue(BaseModel):
    """Report of scope creep or cross-domain attraction"""
    intent_name: str = Field(description="Intent with scope issue")
    language: str = Field(description="Language where issue occurs")
    issue_type: str = Field(description="Type of scope issue")
    severity: Literal['blocker', 'warning', 'info'] = Field(description="Issue severity")
    score: float = Field(description="Issue strength score (0.0-1.0)", ge=0.0, le=1.0)
    evidence: Dict[str, Any] = Field(description="Evidence of scope issue")
    suggestions: List[str] = Field(description="Suggested fixes")


class BreadthAnalysis(BaseModel):
    """Analysis of pattern breadth and specificity"""
    intent_name: str = Field(description="Analyzed intent")
    language: str = Field(description="Analysis language")
    breadth_score: float = Field(description="Breadth score (0.0-1.0)", ge=0.0, le=1.0)
    specificity_score: float = Field(description="Specificity score (0.0-1.0)", ge=0.0, le=1.0)
    pattern_count: int = Field(description="Number of patterns")
    overly_broad_patterns: List[str] = Field(description="Patterns that are too broad")
    recommendations: List[str] = Field(description="Recommendations for improvement")


# ============================================================
# VALIDATION AND ANALYSIS RESULTS
# ============================================================

class ValidationResult(BaseModel):
    """Result of pre-save validation"""
    is_valid: bool = Field(description="Whether donation is valid for saving")
    has_blocking_conflicts: bool = Field(description="Whether there are blocking conflicts")
    has_warnings: bool = Field(description="Whether there are warning-level issues")
    conflicts: List[ConflictReport] = Field(description="All detected conflicts")
    suggestions: List[str] = Field(description="General improvement suggestions")
    validation_time_ms: float = Field(description="Time taken for validation")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "is_valid": False,
                    "has_blocking_conflicts": True,
                    "has_warnings": False,
                    "conflicts": [
                        {
                            "intent_a": "timer.set",
                            "intent_b": "timer.cancel",
                            "severity": "blocker",
                            "conflict_type": "keyword_collision"
                        }
                    ],
                    "suggestions": ["Resolve keyword collisions before saving"],
                    "validation_time_ms": 15.2
                }
            ]
        }


class AnalysisResult(BaseModel):
    """Result of real-time donation analysis"""
    conflicts: List[ConflictReport] = Field(description="Detected conflicts")
    scope_issues: List[ScopeIssue] = Field(description="Scope creep issues")
    performance_metrics: Dict[str, Any] = Field(description="Detailed analysis performance metrics from analyzers")
    language_coverage: Dict[str, float] = Field(description="Language coverage analysis")
    analysis_time_ms: float = Field(description="Time taken for analysis")
    timestamp: float = Field(default_factory=time.time, description="Analysis timestamp")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "conflicts": [],
                    "scope_issues": [],
                    "performance_metrics": {
                        "hybrid": {
                            "keyword_analysis": {
                                "collision_count": 2,
                                "efficiency_score": 0.95
                            },
                            "pattern_analysis": {
                                "complexity_score": 0.8
                            }
                        },
                        "spacy": {
                            "similarity_analysis": {
                                "semantic_conflicts": [],
                                "confidence_scores": [0.92, 0.87]
                            }
                        }
                    },
                    "language_coverage": {
                        "ru": 0.9,
                        "en": 0.85
                    },
                    "analysis_time_ms": 8.5,
                    "timestamp": 1704067200.123
                }
            ]
        }


class ChangeImpactAnalysis(BaseModel):
    """Analysis of impact from proposed changes"""
    changes: Dict[str, Any] = Field(description="Summary of proposed changes")
    affected_intents: List[str] = Field(description="Intents affected by changes")
    new_conflicts: List[ConflictReport] = Field(description="New conflicts introduced")
    resolved_conflicts: List[ConflictReport] = Field(description="Conflicts resolved by changes")
    impact_score: float = Field(description="Overall impact score (0.0-1.0)", ge=0.0, le=1.0)
    recommendations: List[str] = Field(description="Recommendations based on impact")
    analysis_time_ms: float = Field(description="Time taken for impact analysis")


class BatchAnalysisResult(BaseModel):
    """Result of full system batch analysis"""
    summary: Dict[str, int] = Field(description="Summary statistics")
    conflicts: List[ConflictReport] = Field(description="All detected conflicts")
    scope_issues: List[ScopeIssue] = Field(description="All scope issues")
    system_health: Dict[str, float] = Field(description="System health metrics")
    language_breakdown: Dict[str, Dict[str, int]] = Field(description="Per-language statistics")
    performance_metrics: Dict[str, Any] = Field(description="Detailed system performance metrics from analyzers")
    recommendations: List[str] = Field(description="System-wide recommendations")
    analysis_time_ms: float = Field(description="Total analysis time")
    timestamp: float = Field(default_factory=time.time, description="Analysis timestamp")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "summary": {
                        "total_intents": 45,
                        "total_conflicts": 3,
                        "blockers": 1,
                        "warnings": 2,
                        "scope_issues": 1
                    },
                    "conflicts": [],
                    "scope_issues": [],
                    "system_health": {
                        "overall_score": 0.87,
                        "conflict_ratio": 0.067,
                        "coverage_ratio": 0.92
                    },
                    "language_breakdown": {
                        "ru": {"intents": 22, "conflicts": 2},
                        "en": {"intents": 23, "conflicts": 1}
                    },
                    "performance_metrics": {
                        "system_wide": {
                            "avg_analysis_time": 12.5,
                            "memory_usage_mb": 28.4,
                            "total_patterns_analyzed": 156
                        },
                        "analyzer_breakdown": {
                            "hybrid": {
                                "total_keyword_matches": 1240,
                                "avg_match_time_ms": 2.3
                            },
                            "spacy": {
                                "total_semantic_comparisons": 89,
                                "avg_similarity_score": 0.73
                            }
                        }
                    },
                    "recommendations": [
                        "Resolve blocking conflict in timer domain",
                        "Consider splitting broad patterns in conversation handler"
                    ],
                    "analysis_time_ms": 156.7,
                    "timestamp": 1704067200.123
                }
            ]
        }


class SystemHealthReport(BaseModel):
    """Overall NLU system health report"""
    status: Literal['healthy', 'degraded', 'critical'] = Field(description="Overall system status")
    health_score: float = Field(description="Overall health score (0.0-1.0)", ge=0.0, le=1.0)
    component_status: Dict[str, str] = Field(description="Status of individual components")
    conflict_summary: Dict[str, int] = Field(description="Conflict summary by severity")
    performance_summary: Dict[str, float] = Field(description="Performance metrics summary")
    recommendations: List[str] = Field(description="Health improvement recommendations")
    last_analysis: float = Field(description="Timestamp of last analysis")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "status": "healthy",
                    "health_score": 0.87,
                    "component_status": {
                        "hybrid_analyzer": "operational",
                        "spacy_analyzer": "operational",
                        "conflict_detector": "operational"
                    },
                    "conflict_summary": {
                        "blockers": 0,
                        "warnings": 2,
                        "info": 5
                    },
                    "performance_summary": {
                        "avg_analysis_time": 12.5,
                        "memory_usage_mb": 28.4,
                        "success_rate": 0.98
                    },
                    "recommendations": [
                        "Monitor warning-level conflicts",
                        "Consider optimization for large datasets"
                    ],
                    "last_analysis": 1704067200.123
                }
            ]
        }
