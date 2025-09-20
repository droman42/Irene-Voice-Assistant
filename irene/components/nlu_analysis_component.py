"""
NLU Analysis Component

Main component providing real-time analysis and conflict detection
for the Irene Voice Assistant's Natural Language Understanding system.
"""

import time
import logging
import asyncio
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel

from .base import Component
from ..core.interfaces.webapi import WebAPIPlugin
from ..analysis.models import (
    IntentUnit,
    ConflictReport,
    ValidationResult,
    AnalysisResult,
    ChangeImpactAnalysis,
    BatchAnalysisResult,
    SystemHealthReport
)
from ..analysis.conflict_detector import NLUConflictDetector
from ..analysis.scope_analyzer import NLUScopeAnalyzer
from ..analysis.report_generator import NLUReportGenerator
from ..analysis.hybrid_analyzer import HybridKeywordAnalyzer
from ..analysis.spacy_analyzer import SpacyProviderAnalyzer
from ..core.donations import HandlerDonation
from ..config.models import CoreConfig, NLUAnalysisConfig

logger = logging.getLogger(__name__)


class NLUAnalysisComponent(Component, WebAPIPlugin):
    """
    NLU Analysis Component providing real-time conflict detection and validation
    
    Integrates multiple analysis strategies to provide comprehensive insights
    into NLU system health and potential conflicts.
    """
    
    @property
    def name(self) -> str:
        return "nlu_analysis"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "NLU Analysis component providing real-time conflict detection and validation"
    
    def __init__(self):
        super().__init__()
        
        # Analysis components
        self.conflict_detector: Optional[NLUConflictDetector] = None
        self.scope_analyzer: Optional[NLUScopeAnalyzer] = None
        self.report_generator: Optional[NLUReportGenerator] = None
        self.hybrid_analyzer: Optional[HybridKeywordAnalyzer] = None
        self.spacy_analyzer: Optional[SpacyProviderAnalyzer] = None
        
        # Component state
        self.analysis_cache: Dict[str, Any] = {}
        self.last_batch_analysis: Optional[BatchAnalysisResult] = None
        self.system_health: Optional[SystemHealthReport] = None
        
        # Performance tracking
        self.analysis_stats = {
            'total_analyses': 0,
            'successful_analyses': 0,
            'failed_analyses': 0,
            'avg_analysis_time_ms': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # Concurrency control
        self._analysis_semaphore: Optional[asyncio.Semaphore] = None
    
    @classmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the configuration model for this component"""
        return NLUAnalysisConfig
    
    @classmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to this component's config"""
        return "nlu_analysis"
    
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Return list of required Python modules"""
        return [
            "pydantic>=2.0.0",
            "rapidfuzz>=3.0.0",  # Optional but recommended for fuzzy matching
            "spacy>=3.4.0",      # Optional but recommended for semantic analysis
        ]
    
    def get_providers_info(self) -> str:
        """Get human-readable information about analysis capabilities"""
        info_lines = [
            "NLU Analysis Component Status:",
            f"- Conflict Detector: {'✓' if self.conflict_detector else '✗'}",
            f"- Scope Analyzer: {'✓' if self.scope_analyzer else '✗'}",
            f"- Report Generator: {'✓' if self.report_generator else '✗'}",
            f"- Hybrid Analyzer: {'✓' if self.hybrid_analyzer else '✗'}",
            f"- SpaCy Analyzer: {'✓' if self.spacy_analyzer else '✗'}",
            "",
            f"Analysis Statistics:",
            f"- Total Analyses: {self.analysis_stats['total_analyses']}",
            f"- Success Rate: {self._calculate_success_rate():.1%}",
            f"- Average Time: {self.analysis_stats['avg_analysis_time_ms']:.1f}ms",
            f"- Cache Hit Rate: {self._calculate_cache_hit_rate():.1%}"
        ]
        return "\n".join(info_lines)
    
    async def initialize(self, core=None):
        """Initialize the NLU analysis component and its analyzers"""
        await super().initialize(core)
        
        # Get configuration
        if core:
            config = self.get_config(core.config)
        else:
            config = NLUAnalysisConfig()
        
        if not config.enabled:
            self.logger.info("NLU Analysis component disabled")
            return
        
        # Initialize concurrency control
        self._analysis_semaphore = asyncio.Semaphore(config.performance.max_concurrent_analyses)
        
        # Initialize analysis components
        try:
            self.conflict_detector = NLUConflictDetector(config.conflict_detector.dict())
            self.scope_analyzer = NLUScopeAnalyzer(config.scope_analyzer.dict())
            self.report_generator = NLUReportGenerator(config.report_generator.dict())
            self.hybrid_analyzer = HybridKeywordAnalyzer(config.hybrid_analyzer.dict())
            self.spacy_analyzer = SpacyProviderAnalyzer(config.spacy_analyzer.dict())
            
            self.logger.info("NLU Analysis component initialized successfully")
            
            # Perform initial system health check
            await self._update_system_health()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize NLU Analysis component: {e}")
            raise
    
    async def analyze_donation_realtime(
        self, 
        handler_name: str, 
        language: str, 
        donation_data: Dict[str, Any]
    ) -> AnalysisResult:
        """
        Real-time analysis of single donation
        
        Performs comprehensive analysis of a donation's content to detect
        conflicts, scope issues, and potential problems.
        """
        start_time = time.time()
        cache_key = f"realtime:{handler_name}:{language}:{hash(str(donation_data))}"
        
        # Check cache first
        if cache_key in self.analysis_cache:
            self.analysis_stats['cache_hits'] += 1
            cached_result = self.analysis_cache[cache_key]
            self.logger.debug(f"Cache hit for {handler_name}:{language}")
            return cached_result
        
        self.analysis_stats['cache_misses'] += 1
        
        async with self._analysis_semaphore:
            try:
                # Convert donation data to IntentUnit
                intent_unit = self._donation_to_intent_unit(handler_name, language, donation_data)
                
                # Get context from other existing donations
                context_units = await self._get_context_units(language, exclude_handler=handler_name)
                
                # Perform comprehensive analysis
                conflicts = []
                scope_issues = []
                performance_metrics = {}
                
                # 1. Conflict detection
                if self.conflict_detector:
                    await self._analyze_conflicts(intent_unit, context_units, conflicts)
                
                # 2. Scope analysis
                if self.scope_analyzer:
                    await self._analyze_scope(intent_unit, context_units, scope_issues)
                
                # 3. Provider-specific analysis
                if self.hybrid_analyzer:
                    hybrid_results = await self.hybrid_analyzer.analyze_intent_unit(intent_unit, context_units)
                    performance_metrics['hybrid'] = hybrid_results
                
                if self.spacy_analyzer:
                    spacy_results = await self.spacy_analyzer.analyze_intent_unit(intent_unit, context_units)
                    performance_metrics['spacy'] = spacy_results
                
                # Generate analysis result
                analysis_time_ms = (time.time() - start_time) * 1000
                
                result = AnalysisResult(
                    conflicts=conflicts,
                    scope_issues=scope_issues,
                    performance_metrics=performance_metrics,
                    language_coverage={language: 1.0},  # Single language analysis
                    analysis_time_ms=analysis_time_ms
                )
                
                # Cache result
                self.analysis_cache[cache_key] = result
                
                # Update statistics
                self._update_analysis_stats(analysis_time_ms, success=True)
                
                return result
                
            except Exception as e:
                self.logger.error(f"Real-time analysis failed for {handler_name}:{language}: {e}")
                self._update_analysis_stats(time.time() - start_time, success=False)
                raise
    
    async def analyze_changes_impact(
        self, 
        changes: Dict[str, Dict[str, Any]]
    ) -> ChangeImpactAnalysis:
        """
        Analyze impact of proposed changes across system
        
        Evaluates how proposed changes would affect the overall NLU system
        and existing intents.
        """
        start_time = time.time()
        
        try:
            affected_intents = []
            new_conflicts = []
            resolved_conflicts = []
            
            # Analyze each change
            for change_key, change_data in changes.items():
                handler_name = change_data.get('handler_name')
                language = change_data.get('language')
                donation_data = change_data.get('donation_data')
                
                if not all([handler_name, language, donation_data]):
                    continue
                
                # Get current state for comparison
                current_analysis = await self.analyze_donation_realtime(handler_name, language, donation_data)
                
                # Track affected intents
                affected_intents.append(f"{handler_name}:{language}")
                
                # Collect new conflicts
                for conflict in current_analysis.conflicts:
                    if conflict.severity in ['blocker', 'warning']:
                        new_conflicts.append(conflict)
            
            # Calculate impact score
            impact_score = self._calculate_impact_score(new_conflicts, resolved_conflicts)
            
            # Generate recommendations
            recommendations = self._generate_impact_recommendations(new_conflicts, resolved_conflicts)
            
            analysis_time_ms = (time.time() - start_time) * 1000
            
            return ChangeImpactAnalysis(
                changes=changes,
                affected_intents=affected_intents,
                new_conflicts=new_conflicts,
                resolved_conflicts=resolved_conflicts,
                impact_score=impact_score,
                recommendations=recommendations,
                analysis_time_ms=analysis_time_ms
            )
            
        except Exception as e:
            self.logger.error(f"Change impact analysis failed: {e}")
            raise
    
    async def validate_before_save(
        self, 
        handler_name: str, 
        language: str, 
        donation_data: Dict[str, Any]
    ) -> ValidationResult:
        """
        Pre-save validation with blocking/warning classification
        
        Performs validation to determine if donation can be safely saved
        or if there are blocking issues that must be resolved first.
        """
        start_time = time.time()
        
        try:
            # Perform real-time analysis
            analysis_result = await self.analyze_donation_realtime(handler_name, language, donation_data)
            
            # Classify conflicts by severity
            blocking_conflicts = [c for c in analysis_result.conflicts if c.severity == 'blocker']
            warning_conflicts = [c for c in analysis_result.conflicts if c.severity == 'warning']
            
            # Generate validation result
            is_valid = len(blocking_conflicts) == 0
            has_blocking_conflicts = len(blocking_conflicts) > 0
            has_warnings = len(warning_conflicts) > 0
            
            # Generate suggestions
            suggestions = []
            if blocking_conflicts:
                suggestions.append(f"Resolve {len(blocking_conflicts)} blocking conflicts before saving")
            if warning_conflicts:
                suggestions.append(f"Consider addressing {len(warning_conflicts)} warnings")
            
            # Add specific conflict suggestions
            for conflict in blocking_conflicts[:3]:  # Limit to first 3
                suggestions.extend(conflict.suggestions[:2])  # Top 2 suggestions per conflict
            
            validation_time_ms = (time.time() - start_time) * 1000
            
            return ValidationResult(
                is_valid=is_valid,
                has_blocking_conflicts=has_blocking_conflicts,
                has_warnings=has_warnings,
                conflicts=analysis_result.conflicts,
                suggestions=suggestions,
                validation_time_ms=validation_time_ms
            )
            
        except Exception as e:
            self.logger.error(f"Validation failed for {handler_name}:{language}: {e}")
            raise
    
    async def run_batch_analysis(self, language: Optional[str] = None) -> BatchAnalysisResult:
        """
        Full system analysis for reporting/CI
        
        Performs comprehensive analysis of the entire NLU system to generate
        a complete health report with all conflicts and issues.
        """
        start_time = time.time()
        
        try:
            # Get all donation units for analysis
            all_units = await self._get_all_intent_units(language)
            
            summary = {
                'total_intents': len(all_units),
                'total_conflicts': 0,
                'blockers': 0,
                'warnings': 0,
                'info': 0,
                'scope_issues': 0
            }
            
            all_conflicts = []
            all_scope_issues = []
            language_breakdown = {}
            performance_metrics = {}
            
            # Group units by language for analysis
            units_by_language = {}
            for unit in all_units:
                if unit.language not in units_by_language:
                    units_by_language[unit.language] = []
                units_by_language[unit.language].append(unit)
            
            # Analyze each language group
            for lang, units in units_by_language.items():
                lang_conflicts = []
                lang_scope_issues = []
                
                # Analyze conflicts within language
                for i, unit in enumerate(units):
                    context = units[:i] + units[i+1:]  # All other units in same language
                    
                    # Conflict detection
                    if self.conflict_detector:
                        await self._analyze_conflicts(unit, context, lang_conflicts)
                    
                    # Scope analysis
                    if self.scope_analyzer:
                        await self._analyze_scope(unit, context, lang_scope_issues)
                
                all_conflicts.extend(lang_conflicts)
                all_scope_issues.extend(lang_scope_issues)
                
                # Language breakdown
                language_breakdown[lang] = {
                    'intents': len(units),
                    'conflicts': len(lang_conflicts),
                    'scope_issues': len(lang_scope_issues)
                }
            
            # Update summary statistics
            summary['total_conflicts'] = len(all_conflicts)
            summary['scope_issues'] = len(all_scope_issues)
            
            for conflict in all_conflicts:
                if conflict.severity == 'blocker':
                    summary['blockers'] += 1
                elif conflict.severity == 'warning':
                    summary['warnings'] += 1
                else:
                    summary['info'] += 1
            
            # Calculate system health metrics
            system_health = self._calculate_system_health_metrics(summary, all_units)
            
            # Generate recommendations
            recommendations = self._generate_system_recommendations(all_conflicts, all_scope_issues)
            
            analysis_time_ms = (time.time() - start_time) * 1000
            
            # Store result for health reporting
            result = BatchAnalysisResult(
                summary=summary,
                conflicts=all_conflicts,
                scope_issues=all_scope_issues,
                system_health=system_health,
                language_breakdown=language_breakdown,
                performance_metrics=performance_metrics,
                recommendations=recommendations,
                analysis_time_ms=analysis_time_ms
            )
            
            self.last_batch_analysis = result
            await self._update_system_health()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Batch analysis failed: {e}")
            raise
    
    async def get_system_health(self) -> SystemHealthReport:
        """Get current system health report"""
        if not self.system_health:
            await self._update_system_health()
        
        return self.system_health
    
    async def get_handler_conflicts(self, handler_name: str, language: Optional[str] = None) -> List[ConflictReport]:
        """Get existing conflicts for specific handler with optional language filtering"""
        try:
            # Get conflicts from last batch analysis or run new analysis
            if not self.last_batch_analysis:
                await self.run_batch_analysis(language)
            
            # Filter conflicts for the specific handler
            handler_conflicts = []
            for conflict in self.last_batch_analysis.conflicts:
                if (conflict.intent_a.startswith(handler_name + '.') or 
                    conflict.intent_b.startswith(handler_name + '.')):
                    if not language or conflict.language == language:
                        handler_conflicts.append(conflict)
            
            return handler_conflicts
            
        except Exception as e:
            self.logger.error(f"Failed to get conflicts for handler {handler_name}: {e}")
            return []
    
    # Helper methods
    
    def _donation_to_intent_unit(self, handler_name: str, language: str, donation_data: Dict[str, Any]) -> IntentUnit:
        """Convert donation data to IntentUnit for analysis"""
        # Extract method donations
        methods = donation_data.get('methods', {})
        
        # For simplified analysis, combine all methods into one unit
        # Real implementation might analyze each method separately
        all_phrases = []
        all_lemmas = []
        all_token_patterns = []
        all_slot_patterns = {}
        all_examples = []
        all_parameters = []
        
        for method_key, method_data in methods.items():
            if isinstance(method_data, dict):
                all_phrases.extend(method_data.get('phrases', []))
                all_lemmas.extend(method_data.get('lemmas', []))
                all_token_patterns.extend(method_data.get('token_patterns', []))
                
                # Merge slot patterns
                slot_patterns = method_data.get('slot_patterns', {})
                for slot_name, patterns in slot_patterns.items():
                    if slot_name not in all_slot_patterns:
                        all_slot_patterns[slot_name] = []
                    all_slot_patterns[slot_name].extend(patterns)
                
                all_examples.extend(method_data.get('examples', []))
                all_parameters.extend(method_data.get('parameters', []))
        
        return IntentUnit(
            intent_name=handler_name,
            handler_name=handler_name,
            language=language,
            phrases=all_phrases,
            lemmas=all_lemmas,
            token_patterns=all_token_patterns,
            slot_patterns=all_slot_patterns,
            examples=all_examples,
            parameters=all_parameters
        )
    
    async def _get_context_units(self, language: str, exclude_handler: Optional[str] = None) -> List[IntentUnit]:
        """Get context units for analysis (simplified implementation)"""
        # This is a simplified implementation
        # Real implementation would load from donation system
        return []
    
    async def _get_all_intent_units(self, language: Optional[str] = None) -> List[IntentUnit]:
        """Get all intent units for batch analysis (simplified implementation)"""
        # This is a simplified implementation
        # Real implementation would load all donations from the system
        return []
    
    async def _analyze_conflicts(self, unit: IntentUnit, context: List[IntentUnit], conflicts: List[ConflictReport]):
        """Analyze conflicts for a unit and add to conflicts list"""
        if not self.conflict_detector:
            return
        
        for context_unit in context:
            # Phrase overlap analysis
            overlap_score = self.conflict_detector.detect_phrase_overlap(unit, context_unit)
            if overlap_score.jaccard_similarity > 0.3 or overlap_score.token_f1 > 0.5:
                conflict_data = {
                    'type': 'phrase_overlap',
                    'overlap_score': overlap_score
                }
                if self.report_generator:
                    conflict = self.report_generator.generate_conflict_report(unit, context_unit, conflict_data)
                    conflicts.append(conflict)
        
        # Keyword collision analysis
        all_units = [unit] + context
        collisions = self.conflict_detector.detect_keyword_collisions(all_units)
        
        for collision in collisions:
            if unit.intent_name in collision.colliding_intents:
                for other_intent in collision.colliding_intents:
                    if other_intent != unit.intent_name:
                        # Find the other unit
                        other_unit = next((u for u in context if u.intent_name == other_intent), None)
                        if other_unit and self.report_generator:
                            conflict_data = {
                                'type': 'keyword_collision',
                                'collision': collision
                            }
                            conflict = self.report_generator.generate_conflict_report(unit, other_unit, conflict_data)
                            conflicts.append(conflict)
    
    async def _analyze_scope(self, unit: IntentUnit, context: List[IntentUnit], scope_issues: List):
        """Analyze scope issues for a unit and add to scope_issues list"""
        if not self.scope_analyzer:
            return
        
        # Cross-domain attraction analysis
        cross_domain_issues = self.scope_analyzer.detect_cross_domain_attraction(unit, context)
        scope_issues.extend(cross_domain_issues)
        
        # Pattern breadth analysis
        breadth_analysis = self.scope_analyzer.analyze_pattern_breadth(unit)
        if breadth_analysis.breadth_score > 0.8:
            # Convert breadth analysis to scope issue
            scope_issue = {
                'intent_name': unit.intent_name,
                'language': unit.language,
                'issue_type': 'overly_broad_patterns',
                'severity': 'warning' if breadth_analysis.breadth_score > 0.9 else 'info',
                'score': breadth_analysis.breadth_score,
                'evidence': {
                    'breadth_score': breadth_analysis.breadth_score,
                    'overly_broad_patterns': breadth_analysis.overly_broad_patterns
                },
                'suggestions': breadth_analysis.recommendations
            }
            scope_issues.append(scope_issue)
    
    def _calculate_impact_score(self, new_conflicts: List, resolved_conflicts: List) -> float:
        """Calculate impact score for change analysis"""
        new_score = sum(0.8 if c.severity == 'blocker' else 0.5 if c.severity == 'warning' else 0.2 for c in new_conflicts)
        resolved_score = sum(0.8 if c.severity == 'blocker' else 0.5 if c.severity == 'warning' else 0.2 for c in resolved_conflicts)
        
        # Net impact (new problems - resolved problems)
        net_impact = new_score - resolved_score
        
        # Normalize to 0-1 scale
        return min(1.0, max(0.0, net_impact / 10.0))
    
    def _generate_impact_recommendations(self, new_conflicts: List, resolved_conflicts: List) -> List[str]:
        """Generate recommendations based on change impact"""
        recommendations = []
        
        if new_conflicts:
            recommendations.append(f"Address {len(new_conflicts)} new conflicts introduced by changes")
        
        if resolved_conflicts:
            recommendations.append(f"Good: {len(resolved_conflicts)} conflicts resolved by changes")
        
        return recommendations
    
    def _calculate_system_health_metrics(self, summary: Dict[str, int], all_units: List[IntentUnit]) -> Dict[str, float]:
        """Calculate system health metrics"""
        total_intents = summary['total_intents']
        total_conflicts = summary['total_conflicts']
        blockers = summary['blockers']
        
        if total_intents == 0:
            return {'overall_score': 1.0, 'conflict_ratio': 0.0, 'coverage_ratio': 1.0}
        
        # Calculate health score
        conflict_ratio = total_conflicts / total_intents
        blocker_penalty = blockers * 0.2
        overall_score = max(0.0, 1.0 - conflict_ratio - blocker_penalty)
        
        return {
            'overall_score': overall_score,
            'conflict_ratio': conflict_ratio,
            'coverage_ratio': 0.9  # Simplified - would calculate actual coverage
        }
    
    def _generate_system_recommendations(self, conflicts: List, scope_issues: List) -> List[str]:
        """Generate system-wide recommendations"""
        recommendations = []
        
        blocker_conflicts = [c for c in conflicts if c.severity == 'blocker']
        if blocker_conflicts:
            recommendations.append(f"URGENT: Resolve {len(blocker_conflicts)} blocking conflicts")
        
        warning_conflicts = [c for c in conflicts if c.severity == 'warning']
        if warning_conflicts:
            recommendations.append(f"Address {len(warning_conflicts)} warning-level conflicts")
        
        if scope_issues:
            recommendations.append(f"Review {len(scope_issues)} scope issues for better intent organization")
        
        return recommendations
    
    async def _update_system_health(self):
        """Update system health report"""
        try:
            if self.last_batch_analysis:
                summary = self.last_batch_analysis.summary
                health_score = self.last_batch_analysis.system_health.get('overall_score', 0.5)
                
                if health_score >= 0.8:
                    status = 'healthy'
                elif health_score >= 0.6:
                    status = 'degraded'
                else:
                    status = 'critical'
                
                self.system_health = SystemHealthReport(
                    status=status,
                    health_score=health_score,
                    component_status={
                        'conflict_detector': 'operational' if self.conflict_detector else 'disabled',
                        'scope_analyzer': 'operational' if self.scope_analyzer else 'disabled',
                        'hybrid_analyzer': 'operational' if self.hybrid_analyzer else 'disabled',
                        'spacy_analyzer': 'operational' if self.spacy_analyzer else 'disabled'
                    },
                    conflict_summary={
                        'blockers': summary.get('blockers', 0),
                        'warnings': summary.get('warnings', 0),
                        'info': summary.get('info', 0)
                    },
                    performance_summary={
                        'avg_analysis_time': self.last_batch_analysis.analysis_time_ms,
                        'success_rate': self._calculate_success_rate()
                    },
                    recommendations=self.last_batch_analysis.recommendations,
                    last_analysis=self.last_batch_analysis.timestamp
                )
            else:
                # Default health report
                self.system_health = SystemHealthReport(
                    status='healthy',
                    health_score=1.0,
                    component_status={},
                    conflict_summary={'blockers': 0, 'warnings': 0, 'info': 0},
                    performance_summary={'avg_analysis_time': 0.0, 'success_rate': 1.0},
                    recommendations=[],
                    last_analysis=time.time()
                )
        except Exception as e:
            self.logger.error(f"Failed to update system health: {e}")
    
    def _update_analysis_stats(self, analysis_time_ms: float, success: bool):
        """Update analysis performance statistics"""
        self.analysis_stats['total_analyses'] += 1
        
        if success:
            self.analysis_stats['successful_analyses'] += 1
        else:
            self.analysis_stats['failed_analyses'] += 1
        
        # Update running average
        current_avg = self.analysis_stats['avg_analysis_time_ms']
        n = self.analysis_stats['total_analyses']
        self.analysis_stats['avg_analysis_time_ms'] = ((current_avg * (n - 1)) + analysis_time_ms) / n
    
    def _calculate_success_rate(self) -> float:
        """Calculate analysis success rate"""
        total = self.analysis_stats['total_analyses']
        if total == 0:
            return 1.0
        return self.analysis_stats['successful_analyses'] / total
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total_requests = self.analysis_stats['cache_hits'] + self.analysis_stats['cache_misses']
        if total_requests == 0:
            return 0.0
        return self.analysis_stats['cache_hits'] / total_requests
    
    # ============================================================
    # WebAPIPlugin Implementation
    # ============================================================
    
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with NLU analysis endpoints"""
        try:
            from fastapi import APIRouter, HTTPException, Depends, Query
            from ..api.schemas import (
                # Request schemas
                AnalyzeDonationRequest,
                AnalyzeChangesRequest,
                ValidateRequest,
                
                # Response schemas
                NLUAnalysisResult,
                ChangeImpactAnalysisResponse,
                NLUValidationResult,
                BatchAnalysisResponse,
                SystemHealthResponse,
                ConflictReport,
                ErrorResponse
            )
        except ImportError:
            self.logger.warning("FastAPI not available - web API endpoints disabled")
            return None
        
        # Create router
        router = APIRouter()
        
        # Reference to this component instance for endpoints
        component = self
        
        def validate_language_param(language: Optional[str] = None) -> Optional[str]:
            """Validate and normalize language parameter for API endpoints"""
            if language is None:
                return None
            if language not in ['ru', 'en']:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported language: {language}. Supported languages: ru, en"
                )
            return language
        
        # ============================================================
        # REAL-TIME ANALYSIS ENDPOINTS
        # ============================================================
        
        @router.post("/analyze/donation", response_model=NLUAnalysisResult)
        async def analyze_donation(request: AnalyzeDonationRequest) -> NLUAnalysisResult:
            """Real-time analysis endpoint for config-ui"""
            try:
                # Validate language
                validate_language_param(request.language)
                
                # Perform analysis
                analysis_result = await component.analyze_donation_realtime(
                    handler_name=request.handler_name,
                    language=request.language,
                    donation_data=request.donation_data
                )
                
                # Convert to API response format
                return NLUAnalysisResult(
                    success=True,
                    conflicts=[conflict.dict() for conflict in analysis_result.conflicts],
                    scope_issues=[issue.dict() for issue in analysis_result.scope_issues],
                    performance_metrics=analysis_result.performance_metrics,
                    language_coverage=analysis_result.language_coverage,
                    analysis_time_ms=analysis_result.analysis_time_ms
                )
                
            except Exception as e:
                component.logger.error(f"Donation analysis failed: {e}")
                raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
        
        @router.post("/analyze/changes", response_model=ChangeImpactAnalysisResponse)
        async def analyze_changes(
            request: AnalyzeChangesRequest,
            language: Optional[str] = Query(None, description="Optional language filter (ru, en)")
        ) -> ChangeImpactAnalysisResponse:
            """Impact analysis for multiple changes with optional language scoping"""
            try:
                # Validate language parameter
                validated_language = validate_language_param(language)
                
                # Filter changes by language if specified
                filtered_changes = request.changes
                if validated_language:
                    filtered_changes = {
                        key: change for key, change in request.changes.items()
                        if change.get('language') == validated_language
                    }
                
                # Perform impact analysis
                impact_analysis = await component.analyze_changes_impact(filtered_changes)
                
                # Convert to API response format
                return ChangeImpactAnalysisResponse(
                    success=True,
                    changes=impact_analysis.changes,
                    affected_intents=impact_analysis.affected_intents,
                    new_conflicts=[conflict.dict() for conflict in impact_analysis.new_conflicts],
                    resolved_conflicts=[conflict.dict() for conflict in impact_analysis.resolved_conflicts],
                    impact_score=impact_analysis.impact_score,
                    recommendations=impact_analysis.recommendations,
                    analysis_time_ms=impact_analysis.analysis_time_ms
                )
                
            except Exception as e:
                component.logger.error(f"Change impact analysis failed: {e}")
                raise HTTPException(status_code=500, detail=f"Impact analysis failed: {str(e)}")
        
        @router.post("/validate/save", response_model=NLUValidationResult)
        async def validate_before_save(request: ValidateRequest) -> NLUValidationResult:
            """Pre-save validation with severity classification"""
            try:
                # Validate language
                validate_language_param(request.language)
                
                # Perform validation
                validation_result = await component.validate_before_save(
                    handler_name=request.handler_name,
                    language=request.language,
                    donation_data=request.donation_data
                )
                
                # Convert to API response format
                return NLUValidationResult(
                    success=True,
                    is_valid=validation_result.is_valid,
                    has_blocking_conflicts=validation_result.has_blocking_conflicts,
                    has_warnings=validation_result.has_warnings,
                    conflicts=[conflict.dict() for conflict in validation_result.conflicts],
                    suggestions=validation_result.suggestions,
                    validation_time_ms=validation_result.validation_time_ms
                )
                
            except Exception as e:
                component.logger.error(f"Validation failed: {e}")
                raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
        
        # ============================================================
        # SYSTEM ANALYSIS ENDPOINTS
        # ============================================================
        
        @router.get("/conflicts/{handler_name}", response_model=List[ConflictReport])
        async def get_handler_conflicts(
            handler_name: str,
            language: Optional[str] = Query(None, description="Optional language filter (ru, en)")
        ) -> List[ConflictReport]:
            """Get existing conflicts for specific handler with optional language filtering"""
            try:
                # Validate language parameter
                validated_language = validate_language_param(language)
                
                # Get handler conflicts
                conflicts = await component.get_handler_conflicts(handler_name, validated_language)
                
                return conflicts
                
            except Exception as e:
                component.logger.error(f"Failed to get conflicts for handler {handler_name}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to retrieve conflicts: {str(e)}")
        
        @router.get("/analysis/batch", response_model=BatchAnalysisResponse)
        async def run_batch_analysis(
            language: Optional[str] = Query(None, description="Optional language filter (ru, en)")
        ) -> BatchAnalysisResponse:
            """Full system analysis for dashboard/CI with optional language scoping"""
            try:
                # Validate language parameter
                validated_language = validate_language_param(language)
                
                # Run batch analysis
                batch_result = await component.run_batch_analysis(validated_language)
                
                # Convert to API response format
                return BatchAnalysisResponse(
                    success=True,
                    summary=batch_result.summary,
                    conflicts=batch_result.conflicts,
                    scope_issues=[issue.dict() for issue in batch_result.scope_issues],
                    system_health=batch_result.system_health,
                    language_breakdown=batch_result.language_breakdown,
                    performance_metrics=batch_result.performance_metrics,
                    recommendations=batch_result.recommendations,
                    analysis_time_ms=batch_result.analysis_time_ms
                )
                
            except Exception as e:
                component.logger.error(f"Batch analysis failed: {e}")
                raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")
        
        @router.get("/health", response_model=SystemHealthResponse)
        async def get_system_health() -> SystemHealthResponse:
            """Overall NLU system health metrics"""
            try:
                # Get system health
                health_report = await component.get_system_health()
                
                # Convert to API response format
                return SystemHealthResponse(
                    success=True,
                    status=health_report.status,
                    health_score=health_report.health_score,
                    component_status=health_report.component_status,
                    conflict_summary=health_report.conflict_summary,
                    performance_summary=health_report.performance_summary,
                    recommendations=health_report.recommendations,
                    last_analysis=health_report.last_analysis
                )
                
            except Exception as e:
                component.logger.error(f"Health check failed: {e}")
                raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
        
        # ============================================================
        # UTILITY ENDPOINTS
        # ============================================================
        
        @router.get("/capabilities")
        async def get_analysis_capabilities() -> dict:
            """Get available analysis capabilities"""
            try:
                capabilities = {
                    "component_info": component.get_providers_info(),
                    "supported_languages": ["ru", "en"],
                    "analysis_types": [
                        "real_time_donation_analysis",
                        "change_impact_analysis", 
                        "pre_save_validation",
                        "batch_system_analysis",
                        "conflict_detection",
                        "scope_analysis"
                    ],
                    "conflict_types": [
                        "phrase_overlap",
                        "keyword_collision",
                        "pattern_crosshit",
                        "scope_creep"
                    ],
                    "severity_levels": ["blocker", "warning", "info"],
                    "analyzers": {
                        "hybrid_keyword_matcher": bool(component.hybrid_analyzer),
                        "spacy_provider": bool(component.spacy_analyzer),
                        "conflict_detector": bool(component.conflict_detector),
                        "scope_analyzer": bool(component.scope_analyzer)
                    }
                }
                
                return capabilities
                
            except Exception as e:
                component.logger.error(f"Failed to get capabilities: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to retrieve capabilities: {str(e)}")
        
        @router.get("/statistics")
        async def get_analysis_statistics() -> dict:
            """Get analysis performance statistics"""
            try:
                stats = {
                    "analysis_stats": component.analysis_stats,
                    "component_status": {
                        "initialized": component.initialized,
                        "last_batch_analysis": component.last_batch_analysis.timestamp if component.last_batch_analysis else None,
                        "cache_size": len(component.analysis_cache),
                        "system_health_status": component.system_health.status if component.system_health else "unknown"
                    },
                    "performance_metrics": {
                        "success_rate": component._calculate_success_rate(),
                        "cache_hit_rate": component._calculate_cache_hit_rate(),
                        "average_analysis_time_ms": component.analysis_stats['avg_analysis_time_ms']
                    }
                }
                
                return stats
                
            except Exception as e:
                component.logger.error(f"Failed to get statistics: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics: {str(e)}")
        
        return router
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for NLU analysis API endpoints"""
        return "/nlu_analysis"
    
    def get_api_tags(self) -> list[str]:
        """Get OpenAPI tags for NLU analysis endpoints"""
        return ["NLU Analysis"]
    
    def requires_authentication(self) -> bool:
        """NLU analysis endpoints don't require authentication"""
        return False
