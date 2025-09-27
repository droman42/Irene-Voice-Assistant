"""
Metrics and Monitoring System - Phase 3.2 Implementation

Provides comprehensive tracking of fire-and-forget action performance,
success/failure rates, and system analytics with dashboard interface.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Deque, Tuple
import statistics

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics that can be tracked"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class ActionMetric:
    """Represents metrics for a single action execution"""
    
    action_name: str
    domain: str
    handler: str
    started_at: float
    completed_at: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    error_type: Optional[str] = None
    retry_count: int = 0
    timeout_occurred: bool = False
    memory_usage: Optional[float] = None  # MB
    session_id: Optional[str] = None


@dataclass
class DomainMetrics:
    """Aggregated metrics for a specific domain"""
    
    domain: str
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    total_duration: float = 0.0
    average_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    error_rate: float = 0.0
    timeout_count: int = 0
    retry_count: int = 0
    last_updated: float = field(default_factory=time.time)
    
    def update_from_action(self, action: ActionMetric) -> None:
        """Update domain metrics from a completed action"""
        self.total_actions += 1
        
        if action.success:
            self.successful_actions += 1
        else:
            self.failed_actions += 1
        
        if action.duration is not None:
            self.total_duration += action.duration
            self.average_duration = self.total_duration / self.total_actions
            self.min_duration = min(self.min_duration, action.duration)
            self.max_duration = max(self.max_duration, action.duration)
        
        if action.timeout_occurred:
            self.timeout_count += 1
        
        self.retry_count += action.retry_count
        self.error_rate = self.failed_actions / self.total_actions if self.total_actions > 0 else 0.0
        self.last_updated = time.time()


class MetricsCollector:
    """
    Collects and aggregates metrics for fire-and-forget actions.
    
    Provides real-time performance tracking, success/failure analysis,
    and historical trend data for system monitoring and optimization.
    """
    
    def __init__(self, max_history_size: int = 1000):
        self.logger = logging.getLogger(f"{__name__}.MetricsCollector")
        self.max_history_size = max_history_size
        
        # Action tracking
        self._active_actions: Dict[str, ActionMetric] = {}  # key: domain
        self._completed_actions: Deque[ActionMetric] = deque(maxlen=max_history_size)
        
        # Domain-specific metrics
        self._domain_metrics: Dict[str, DomainMetrics] = {}
        
        # System-wide metrics
        self._system_metrics = {
            "total_actions_started": 0,
            "total_actions_completed": 0,
            "total_actions_failed": 0,
            "average_success_rate": 0.0,
            "average_completion_time": 0.0,
            "peak_concurrent_actions": 0,
            "current_concurrent_actions": 0,
            "uptime_start": time.time(),
            "last_reset": time.time()
        }
        
        # Performance tracking
        self._performance_history: Deque[Tuple[float, Dict[str, Any]]] = deque(maxlen=100)  # (timestamp, metrics)
        self._error_patterns: Dict[str, int] = defaultdict(int)
        
        # Real-time monitoring
        self._monitoring_enabled = True
        self._monitoring_interval = 60.0  # seconds
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # VAD-specific metrics (Phase 1 integration)
        self._vad_metrics = {
            "total_chunks_processed": 0,
            "voice_segments_detected": 0,
            "silence_chunks_skipped": 0,
            "average_processing_time_ms": 0.0,
            "max_processing_time_ms": 0.0,
            "total_processing_time_ms": 0.0,
            "buffer_overflow_count": 0,
            "timeout_events": 0,
            "cache_hit_rate": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_voice_duration_ms": 0.0,
            "energy_cache_size": 0,
            "zcr_cache_size": 0,
            "array_cache_size": 0
        }
        
        # Phase 4 TODO16: Contextual command metrics integration
        self._contextual_command_metrics = {
            "total_disambiguations": 0,
            "successful_disambiguations": 0,
            "failed_disambiguations": 0,
            "average_latency_ms": 0.0,
            "max_latency_ms": 0.0,
            "min_latency_ms": float('inf'),
            "total_latency_ms": 0.0,
            "threshold_violations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "domain_resolutions": {},  # Per-domain resolution counts
            "command_type_stats": {},  # Per-command-type statistics
            "confidence_scores": [],   # Recent confidence scores for analysis
            "last_updated": time.time()
        }
        
        # Performance thresholds (configurable)
        self._contextual_command_config = None
    
    async def start_monitoring(self) -> None:
        """Start real-time metrics monitoring"""
        if self._monitoring_task is None:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self.logger.info("Metrics monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop real-time metrics monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            self.logger.info("Metrics monitoring stopped")
    
    def record_action_start(self, domain: str, action_name: str, handler: str, 
                           session_id: Optional[str] = None) -> None:
        """Record the start of a fire-and-forget action"""
        action = ActionMetric(
            action_name=action_name,
            domain=domain,
            handler=handler,
            started_at=time.time(),
            session_id=session_id
        )
        
        self._active_actions[domain] = action
        self._system_metrics["total_actions_started"] += 1
        self._system_metrics["current_concurrent_actions"] = len(self._active_actions)
        
        # Track peak concurrent actions
        if self._system_metrics["current_concurrent_actions"] > self._system_metrics["peak_concurrent_actions"]:
            self._system_metrics["peak_concurrent_actions"] = self._system_metrics["current_concurrent_actions"]
        
        self.logger.debug(f"Action started: {domain}/{action_name}")
    
    def record_action_completion(self, domain: str, success: bool = True, 
                               error: Optional[str] = None, error_type: Optional[str] = None,
                               retry_count: int = 0, timeout_occurred: bool = False,
                               memory_usage: Optional[float] = None) -> None:
        """Record the completion of a fire-and-forget action"""
        if domain not in self._active_actions:
            self.logger.warning(f"Attempted to complete unknown action in domain: {domain}")
            return
        
        action = self._active_actions.pop(domain)
        action.completed_at = time.time()
        action.duration = action.completed_at - action.started_at
        action.success = success
        action.error = error
        action.error_type = error_type
        action.retry_count = retry_count
        action.timeout_occurred = timeout_occurred
        action.memory_usage = memory_usage
        
        # Add to completed actions history
        self._completed_actions.append(action)
        
        # Update system metrics
        self._system_metrics["total_actions_completed"] += 1
        self._system_metrics["current_concurrent_actions"] = len(self._active_actions)
        
        if success:
            pass  # Success already tracked in total_actions_completed
        else:
            self._system_metrics["total_actions_failed"] += 1
            if error_type:
                self._error_patterns[error_type] += 1
        
        # Update domain metrics
        if domain not in self._domain_metrics:
            self._domain_metrics[domain] = DomainMetrics(domain=domain)
        
        self._domain_metrics[domain].update_from_action(action)
        
        # Update system-wide averages
        self._update_system_averages()
        
        self.logger.debug(f"Action completed: {domain}/{action.action_name} (success={success}, duration={action.duration:.2f}s)")
    
    def get_domain_metrics(self, domain: str) -> Optional[DomainMetrics]:
        """Get metrics for a specific domain"""
        return self._domain_metrics.get(domain)
    
    def get_all_domain_metrics(self) -> Dict[str, DomainMetrics]:
        """Get metrics for all domains"""
        return self._domain_metrics.copy()
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-wide metrics including VAD metrics"""
        metrics = self._system_metrics.copy()
        metrics["uptime_seconds"] = time.time() - metrics["uptime_start"]
        metrics["vad_metrics"] = self.get_vad_metrics()  # Include VAD metrics
        return metrics
    
    def get_performance_summary(self, time_window: Optional[float] = None) -> Dict[str, Any]:
        """
        Get performance summary for actions within a time window.
        
        Args:
            time_window: Time window in seconds (None for all history)
            
        Returns:
            Performance summary dictionary
        """
        cutoff_time = time.time() - time_window if time_window else 0
        
        # Filter actions within time window
        relevant_actions = [
            action for action in self._completed_actions
            if action.completed_at and action.completed_at >= cutoff_time
        ]
        
        if not relevant_actions:
            return {
                "total_actions": 0,
                "success_rate": 0.0,
                "average_duration": 0.0,
                "error_distribution": {},
                "domain_distribution": {}
            }
        
        # Calculate metrics
        total_actions = len(relevant_actions)
        successful_actions = sum(1 for action in relevant_actions if action.success)
        success_rate = successful_actions / total_actions
        
        durations = [action.duration for action in relevant_actions if action.duration is not None]
        average_duration = statistics.mean(durations) if durations else 0.0
        
        # Error distribution
        error_distribution = defaultdict(int)
        for action in relevant_actions:
            if not action.success and action.error_type:
                error_distribution[action.error_type] += 1
        
        # Domain distribution
        domain_distribution = defaultdict(int)
        for action in relevant_actions:
            domain_distribution[action.domain] += 1
        
        return {
            "total_actions": total_actions,
            "successful_actions": successful_actions,
            "failed_actions": total_actions - successful_actions,
            "success_rate": success_rate,
            "average_duration": average_duration,
            "median_duration": statistics.median(durations) if durations else 0.0,
            "min_duration": min(durations) if durations else 0.0,
            "max_duration": max(durations) if durations else 0.0,
            "error_distribution": dict(error_distribution),
            "domain_distribution": dict(domain_distribution),
            "time_window": time_window
        }
    
    def get_active_actions_summary(self) -> Dict[str, Any]:
        """Get summary of currently active actions"""
        current_time = time.time()
        
        active_summary = []
        for domain, action in self._active_actions.items():
            running_time = current_time - action.started_at
            active_summary.append({
                "domain": domain,
                "action_name": action.action_name,
                "handler": action.handler,
                "running_time": running_time,
                "session_id": action.session_id
            })
        
        return {
            "count": len(self._active_actions),
            "actions": active_summary,
            "longest_running": max(
                (current_time - action.started_at for action in self._active_actions.values()),
                default=0.0
            )
        }
    
    def get_error_analysis(self) -> Dict[str, Any]:
        """Get detailed error analysis"""
        recent_failures = [
            action for action in self._completed_actions
            if not action.success and action.completed_at and action.completed_at >= time.time() - 3600  # Last hour
        ]
        
        error_types = defaultdict(list)
        for action in recent_failures:
            error_types[action.error_type or "unknown"].append(action)
        
        analysis = {
            "total_recent_failures": len(recent_failures),
            "error_types": {},
            "most_common_errors": [],
            "domains_with_errors": set()
        }
        
        for error_type, actions in error_types.items():
            analysis["error_types"][error_type] = {
                "count": len(actions),
                "domains": list(set(action.domain for action in actions)),
                "recent_examples": [
                    {
                        "domain": action.domain,
                        "action_name": action.action_name,
                        "error": action.error,
                        "timestamp": action.completed_at
                    }
                    for action in actions[-3:]  # Last 3 examples
                ]
            }
            analysis["domains_with_errors"].update(action.domain for action in actions)
        
        # Sort by frequency
        analysis["most_common_errors"] = sorted(
            analysis["error_types"].items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:5]  # Top 5 most common errors
        
        analysis["domains_with_errors"] = list(analysis["domains_with_errors"])
        
        return analysis
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data for monitoring interface"""
        return {
            "system_metrics": self.get_system_metrics(),
            "domain_metrics": {
                domain: {
                    "domain": metrics.domain,
                    "total_actions": metrics.total_actions,
                    "success_rate": (metrics.successful_actions / metrics.total_actions) if metrics.total_actions > 0 else 0.0,
                    "average_duration": metrics.average_duration,
                    "error_rate": metrics.error_rate,
                    "last_updated": metrics.last_updated
                }
                for domain, metrics in self._domain_metrics.items()
            },
            "performance_summary": self.get_performance_summary(3600),  # Last hour
            "active_actions": self.get_active_actions_summary(),
            "error_analysis": self.get_error_analysis(),
            "recent_trends": self._get_recent_trends()
        }
    
    def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing or periodic cleanup)"""
        self._active_actions.clear()
        self._completed_actions.clear()
        self._domain_metrics.clear()
        self._performance_history.clear()
        self._error_patterns.clear()
        
        self._system_metrics = {
            "total_actions_started": 0,
            "total_actions_completed": 0,
            "total_actions_failed": 0,
            "average_success_rate": 0.0,
            "average_completion_time": 0.0,
            "peak_concurrent_actions": 0,
            "current_concurrent_actions": 0,
            "uptime_start": time.time(),
            "last_reset": time.time()
        }
        
        self.logger.info("Metrics reset completed")
    
    def _update_system_averages(self) -> None:
        """Update system-wide average metrics"""
        if self._system_metrics["total_actions_completed"] > 0:
            self._system_metrics["average_success_rate"] = (
                (self._system_metrics["total_actions_completed"] - self._system_metrics["total_actions_failed"]) /
                self._system_metrics["total_actions_completed"]
            )
        
        if self._completed_actions:
            durations = [action.duration for action in self._completed_actions if action.duration is not None]
            if durations:
                self._system_metrics["average_completion_time"] = statistics.mean(durations)
    
    def _get_recent_trends(self) -> Dict[str, Any]:
        """Get recent performance trends"""
        if len(self._performance_history) < 2:
            return {"trend_available": False}
        
        recent = self._performance_history[-1][1]
        previous = self._performance_history[-2][1]
        
        return {
            "trend_available": True,
            "success_rate_trend": recent.get("success_rate", 0) - previous.get("success_rate", 0),
            "average_duration_trend": recent.get("average_duration", 0) - previous.get("average_duration", 0),
            "action_volume_trend": recent.get("total_actions", 0) - previous.get("total_actions", 0)
        }
    
    async def _monitoring_loop(self) -> None:
        """Background monitoring loop for periodic metrics collection"""
        self.logger.info("Metrics monitoring loop started")
        
        while self._monitoring_enabled:
            try:
                # Collect current performance snapshot
                performance_snapshot = self.get_performance_summary(self._monitoring_interval)
                self._performance_history.append((time.time(), performance_snapshot))
                
                # Log periodic summary
                active_count = len(self._active_actions)
                total_completed = self._system_metrics["total_actions_completed"]
                success_rate = self._system_metrics["average_success_rate"]
                
                self.logger.info(
                    f"📊 Metrics Summary: {active_count} active, {total_completed} completed, "
                    f"{success_rate:.1%} success rate"
                )
                
                # Sleep until next monitoring cycle
                await asyncio.sleep(self._monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in metrics monitoring loop: {e}")
                await asyncio.sleep(10)  # Brief pause before retrying
        
        self.logger.info("Metrics monitoring loop stopped")
    
    # VAD-specific metrics methods (Phase 1 integration)
    def record_vad_chunk_processed(self, processing_time_ms: float, is_voice: bool = False) -> None:
        """Record processing of a VAD audio chunk"""
        self._vad_metrics["total_chunks_processed"] += 1
        self._vad_metrics["total_processing_time_ms"] += processing_time_ms
        
        if processing_time_ms > self._vad_metrics["max_processing_time_ms"]:
            self._vad_metrics["max_processing_time_ms"] = processing_time_ms
        
        # Update average processing time
        self._vad_metrics["average_processing_time_ms"] = (
            self._vad_metrics["total_processing_time_ms"] / self._vad_metrics["total_chunks_processed"]
        )
        
        if is_voice:
            self._vad_metrics["voice_segments_detected"] += 1
        else:
            self._vad_metrics["silence_chunks_skipped"] += 1
    
    def record_vad_voice_segment(self, duration_ms: float) -> None:
        """Record a detected voice segment duration"""
        self._vad_metrics["total_voice_duration_ms"] += duration_ms
    
    def record_vad_buffer_overflow(self) -> None:
        """Record a VAD buffer overflow event"""
        self._vad_metrics["buffer_overflow_count"] += 1
    
    def record_vad_timeout(self) -> None:
        """Record a VAD timeout event"""
        self._vad_metrics["timeout_events"] += 1
    
    def record_vad_cache_hit(self) -> None:
        """Record a VAD cache hit"""
        self._vad_metrics["cache_hits"] += 1
        total_cache_operations = self._vad_metrics["cache_hits"] + self._vad_metrics["cache_misses"]
        if total_cache_operations > 0:
            self._vad_metrics["cache_hit_rate"] = self._vad_metrics["cache_hits"] / total_cache_operations
    
    def record_vad_cache_miss(self) -> None:
        """Record a VAD cache miss"""
        self._vad_metrics["cache_misses"] += 1
        total_cache_operations = self._vad_metrics["cache_hits"] + self._vad_metrics["cache_misses"]
        if total_cache_operations > 0:
            self._vad_metrics["cache_hit_rate"] = self._vad_metrics["cache_hits"] / total_cache_operations
    
    def update_vad_cache_sizes(self, energy_cache_size: int, zcr_cache_size: int, array_cache_size: int) -> None:
        """Update VAD cache size metrics"""
        self._vad_metrics["energy_cache_size"] = energy_cache_size
        self._vad_metrics["zcr_cache_size"] = zcr_cache_size
        self._vad_metrics["array_cache_size"] = array_cache_size
    
    def get_vad_metrics(self) -> Dict[str, Any]:
        """Get comprehensive VAD metrics"""
        return self._vad_metrics.copy()
    
    # Advanced VAD metrics methods (Phase 1 complete integration)
    def record_vad_efficiency(self, real_time_factor: float, processing_efficiency: float, buffer_utilization: float) -> None:
        """Record VAD processing efficiency metrics"""
        if not hasattr(self, '_vad_advanced_metrics'):
            self._vad_advanced_metrics = {
                "real_time_factor": 0.0,
                "processing_efficiency": 0.0,
                "buffer_utilization": 0.0,
                "efficiency_samples": 0
            }
        
        # Update running averages
        samples = self._vad_advanced_metrics["efficiency_samples"]
        self._vad_advanced_metrics["real_time_factor"] = (
            (self._vad_advanced_metrics["real_time_factor"] * samples + real_time_factor) / (samples + 1)
        )
        self._vad_advanced_metrics["processing_efficiency"] = (
            (self._vad_advanced_metrics["processing_efficiency"] * samples + processing_efficiency) / (samples + 1)
        )
        self._vad_advanced_metrics["buffer_utilization"] = (
            (self._vad_advanced_metrics["buffer_utilization"] * samples + buffer_utilization) / (samples + 1)
        )
        self._vad_advanced_metrics["efficiency_samples"] += 1
    
    def record_vad_quality_metrics(self, energy_level: float, zcr_value: float, detection_confidence: float) -> None:
        """Record VAD detection quality metrics"""
        if not hasattr(self, '_vad_quality_metrics'):
            self._vad_quality_metrics = {
                "average_energy_level": 0.0,
                "average_zcr": 0.0,
                "average_confidence": 0.0,
                "quality_samples": 0
            }
        
        # Update running averages
        samples = self._vad_quality_metrics["quality_samples"]
        self._vad_quality_metrics["average_energy_level"] = (
            (self._vad_quality_metrics["average_energy_level"] * samples + energy_level) / (samples + 1)
        )
        self._vad_quality_metrics["average_zcr"] = (
            (self._vad_quality_metrics["average_zcr"] * samples + zcr_value) / (samples + 1)
        )
        self._vad_quality_metrics["average_confidence"] = (
            (self._vad_quality_metrics["average_confidence"] * samples + detection_confidence) / (samples + 1)
        )
        self._vad_quality_metrics["quality_samples"] += 1
    
    def get_vad_advanced_metrics(self) -> Dict[str, Any]:
        """Get advanced VAD metrics including efficiency and quality"""
        base_metrics = self.get_vad_metrics()
        base_metrics.update(getattr(self, '_vad_advanced_metrics', {}))
        base_metrics.update(getattr(self, '_vad_quality_metrics', {}))
        return base_metrics
    
    # Component runtime metrics methods (Phase 1 integration)
    def record_component_metrics(self, component_name: str, metrics: Dict[str, Any]) -> None:
        """Record component runtime metrics"""
        # Use action-based tracking for component metrics
        domain = f"component_{component_name}"
        
        # Store as domain-specific metrics
        if domain not in self._domain_metrics:
            self._domain_metrics[domain] = DomainMetrics(domain=domain)
        
        # Update the domain metrics with component data
        domain_metrics = self._domain_metrics[domain]
        domain_metrics.last_updated = time.time()
        
        # Store component-specific metrics in metadata
        if not hasattr(domain_metrics, 'component_metrics'):
            domain_metrics.component_metrics = {}
        domain_metrics.component_metrics = metrics
    
    def get_component_metrics(self, component_name: str) -> Dict[str, Any]:
        """Get metrics for a specific component"""
        domain = f"component_{component_name}"
        if domain in self._domain_metrics:
            domain_metrics = self._domain_metrics[domain]
            return getattr(domain_metrics, 'component_metrics', {})
        return {}
    
    def get_all_component_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all components"""
        component_metrics = {}
        for domain, metrics in self._domain_metrics.items():
            if domain.startswith("component_"):
                component_name = domain.replace("component_", "")
                component_metrics[component_name] = getattr(metrics, 'component_metrics', {})
        return component_metrics
    
    # Intent analytics methods (Phase 2 integration)
    def record_intent_recognition(self, intent_name: str, confidence: float, processing_time: float, session_id: Optional[str] = None) -> None:
        """Record intent recognition metrics"""
        domain = f"intent_{intent_name}"
        
        # Track as fire-and-forget action
        self.record_action_start(domain, "recognition", "intent_system", session_id)
        self.record_action_completion(domain, success=True)
        
        # Store intent-specific metrics
        if domain not in self._domain_metrics:
            self._domain_metrics[domain] = DomainMetrics(domain=domain)
        
        if not hasattr(self._domain_metrics[domain], 'intent_metrics'):
            self._domain_metrics[domain].intent_metrics = {
                'recognition_count': 0,
                'total_confidence': 0.0,
                'processing_times': deque(maxlen=100),
                'last_used': 0.0,
                'average_confidence': 0.0
            }
        
        intent_metrics = self._domain_metrics[domain].intent_metrics
        intent_metrics['recognition_count'] += 1
        intent_metrics['total_confidence'] += confidence
        intent_metrics['processing_times'].append(processing_time)
        intent_metrics['last_used'] = time.time()
        intent_metrics['average_confidence'] = intent_metrics['total_confidence'] / intent_metrics['recognition_count']
        
        self.logger.debug(f"Intent recognition recorded: {intent_name} (confidence: {confidence:.2f}, time: {processing_time:.3f}s)")
    
    def record_intent_execution(self, intent_name: str, success: bool, execution_time: float, 
                               error: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """Record intent execution metrics"""
        domain = f"intent_{intent_name}"
        
        # Track as fire-and-forget action
        self.record_action_start(domain, "execution", "intent_system", session_id)
        self.record_action_completion(domain, success=success, error=error, error_type="intent_execution_failure" if not success else None)
        
        # Store intent-specific execution metrics
        if domain not in self._domain_metrics:
            self._domain_metrics[domain] = DomainMetrics(domain=domain)
        
        if not hasattr(self._domain_metrics[domain], 'execution_metrics'):
            self._domain_metrics[domain].execution_metrics = {
                'execution_count': 0,
                'success_count': 0,
                'failure_count': 0,
                'execution_times': deque(maxlen=100),
                'success_rate': 0.0,
                'average_execution_time': 0.0
            }
        
        execution_metrics = self._domain_metrics[domain].execution_metrics
        execution_metrics['execution_count'] += 1
        execution_metrics['execution_times'].append(execution_time)
        
        if success:
            execution_metrics['success_count'] += 1
        else:
            execution_metrics['failure_count'] += 1
        
        execution_metrics['success_rate'] = execution_metrics['success_count'] / execution_metrics['execution_count']
        execution_metrics['average_execution_time'] = statistics.mean(execution_metrics['execution_times']) if execution_metrics['execution_times'] else 0.0
        
        self.logger.debug(f"Intent execution recorded: {intent_name} (success: {success}, time: {execution_time:.3f}s)")
    
    def record_session_start(self, session_id: str) -> None:
        """Record conversation session start"""
        domain = f"session_{session_id}"
        
        # Track as fire-and-forget action
        self.record_action_start(domain, "session", "intent_system", session_id)
        
        # Store session-specific metrics
        if domain not in self._domain_metrics:
            self._domain_metrics[domain] = DomainMetrics(domain=domain)
        
        if not hasattr(self._domain_metrics[domain], 'session_metrics'):
            self._domain_metrics[domain].session_metrics = {
                'session_id': session_id,
                'start_time': time.time(),
                'last_activity': time.time(),
                'intent_count': 0,
                'successful_intents': 0,
                'failed_intents': 0,
                'user_satisfaction_score': 0.8,  # Default
                'domains_used': set(),
                'language_switches': 0
            }
        
        self.logger.debug(f"Session started: {session_id}")
    
    def record_session_end(self, session_id: str, user_satisfaction: Optional[float] = None) -> None:
        """Record conversation session end"""
        domain = f"session_{session_id}"
        
        if domain in self._domain_metrics and hasattr(self._domain_metrics[domain], 'session_metrics'):
            session_metrics = self._domain_metrics[domain].session_metrics
            session_metrics['last_activity'] = time.time()
            
            if user_satisfaction is not None:
                session_metrics['user_satisfaction_score'] = user_satisfaction
            
            # Complete the session action
            if domain in self._active_actions:
                self.record_action_completion(domain, success=True)
            
            self.logger.debug(f"Session ended: {session_id}")
    
    def update_session_activity(self, session_id: str, intent_name: str, success: bool) -> None:
        """Update session activity with intent usage"""
        domain = f"session_{session_id}"
        
        if domain in self._domain_metrics and hasattr(self._domain_metrics[domain], 'session_metrics'):
            session_metrics = self._domain_metrics[domain].session_metrics
            session_metrics['last_activity'] = time.time()
            session_metrics['intent_count'] += 1
            
            if success:
                session_metrics['successful_intents'] += 1
            else:
                session_metrics['failed_intents'] += 1
            
            # Track domain usage (extract from intent name if follows pattern)
            if "_" in intent_name:
                domain_name = intent_name.split("_")[0]
                session_metrics['domains_used'].add(domain_name)
    
    def get_intent_analytics(self) -> Dict[str, Any]:
        """Get comprehensive intent analytics"""
        intent_domains = {domain: metrics for domain, metrics in self._domain_metrics.items() 
                         if domain.startswith("intent_")}
        
        if not intent_domains:
            return {
                "overview": {
                    "total_intents_processed": 0,
                    "unique_intent_types": 0,
                    "average_confidence": 0.0,
                    "overall_success_rate": 0.0,
                    "recent_average_confidence": 0.0
                },
                "top_intents": [],
                "detailed_metrics": {}
            }
        
        # Calculate overview metrics
        total_intents = sum(getattr(metrics, 'intent_metrics', {}).get('recognition_count', 0) 
                           for metrics in intent_domains.values())
        
        total_executions = sum(getattr(metrics, 'execution_metrics', {}).get('execution_count', 0) 
                              for metrics in intent_domains.values())
        
        total_successes = sum(getattr(metrics, 'execution_metrics', {}).get('success_count', 0) 
                             for metrics in intent_domains.values())
        
        avg_confidence = 0.0
        if total_intents > 0:
            total_confidence = sum(
                getattr(metrics, 'intent_metrics', {}).get('total_confidence', 0.0) 
                for metrics in intent_domains.values()
            )
            avg_confidence = total_confidence / total_intents
        
        overall_success_rate = total_successes / total_executions if total_executions > 0 else 0.0
        
        # Top intents by usage
        top_intents = []
        for domain, metrics in intent_domains.items():
            intent_name = domain.replace("intent_", "")
            intent_metrics = getattr(metrics, 'intent_metrics', {})
            execution_metrics = getattr(metrics, 'execution_metrics', {})
            
            if intent_metrics.get('recognition_count', 0) > 0:
                top_intents.append({
                    "name": intent_name,
                    "usage_count": intent_metrics.get('recognition_count', 0),
                    "avg_confidence": intent_metrics.get('average_confidence', 0.0),
                    "success_rate": execution_metrics.get('success_rate', 0.0)
                })
        
        top_intents.sort(key=lambda x: x['usage_count'], reverse=True)
        
        # Detailed metrics
        detailed_metrics = {}
        for domain, metrics in intent_domains.items():
            intent_name = domain.replace("intent_", "")
            intent_metrics = getattr(metrics, 'intent_metrics', {})
            execution_metrics = getattr(metrics, 'execution_metrics', {})
            
            detailed_metrics[intent_name] = {
                "recognition_count": intent_metrics.get('recognition_count', 0),
                "average_confidence": intent_metrics.get('average_confidence', 0.0),
                "success_rate": execution_metrics.get('success_rate', 0.0),
                "average_response_time": execution_metrics.get('average_execution_time', 0.0),
                "last_used": intent_metrics.get('last_used', 0.0)
            }
        
        return {
            "overview": {
                "total_intents_processed": total_intents,
                "unique_intent_types": len(intent_domains),
                "average_confidence": avg_confidence,
                "overall_success_rate": overall_success_rate,
                "recent_average_confidence": avg_confidence  # Simplified for now
            },
            "top_intents": top_intents[:10],
            "detailed_metrics": detailed_metrics
        }
    
    def get_session_analytics(self) -> Dict[str, Any]:
        """Get comprehensive session analytics"""
        session_domains = {domain: metrics for domain, metrics in self._domain_metrics.items() 
                          if domain.startswith("session_")}
        
        if not session_domains:
            return {
                "overview": {
                    "active_sessions": 0,
                    "total_sessions": 0,
                    "peak_concurrent_sessions": 0,
                    "average_session_duration": 0.0,
                    "average_intents_per_session": 0.0,
                    "average_user_satisfaction": 0.8
                },
                "active_sessions": [],
                "session_details": {}
            }
        
        # Active sessions (those with ongoing actions)
        active_sessions = []
        current_time = time.time()
        
        for domain, metrics in session_domains.items():
            if domain in self._active_actions:
                session_metrics = getattr(metrics, 'session_metrics', {})
                session_id = session_metrics.get('session_id', domain.replace('session_', ''))
                
                active_sessions.append({
                    "session_id": session_id,
                    "duration": current_time - session_metrics.get('start_time', current_time),
                    "intent_count": session_metrics.get('intent_count', 0),
                    "success_rate": self._calculate_session_success_rate(session_metrics)
                })
        
        # Calculate overall statistics
        total_sessions = len(session_domains)
        avg_duration = 0.0
        avg_intents = 0.0
        avg_satisfaction = 0.0
        
        if total_sessions > 0:
            durations = []
            intent_counts = []
            satisfactions = []
            
            for metrics in session_domains.values():
                session_metrics = getattr(metrics, 'session_metrics', {})
                start_time = session_metrics.get('start_time', current_time)
                last_activity = session_metrics.get('last_activity', start_time)
                durations.append(last_activity - start_time)
                intent_counts.append(session_metrics.get('intent_count', 0))
                satisfactions.append(session_metrics.get('user_satisfaction_score', 0.8))
            
            avg_duration = statistics.mean(durations) if durations else 0.0
            avg_intents = statistics.mean(intent_counts) if intent_counts else 0.0
            avg_satisfaction = statistics.mean(satisfactions) if satisfactions else 0.8
        
        # Session details
        session_details = {}
        for domain, metrics in session_domains.items():
            session_metrics = getattr(metrics, 'session_metrics', {})
            session_id = session_metrics.get('session_id', domain.replace('session_', ''))
            start_time = session_metrics.get('start_time', current_time)
            last_activity = session_metrics.get('last_activity', start_time)
            
            session_details[session_id] = {
                "start_time": start_time,
                "duration": last_activity - start_time,
                "intent_count": session_metrics.get('intent_count', 0),
                "success_rate": self._calculate_session_success_rate(session_metrics),
                "domains_used": list(session_metrics.get('domains_used', set())),
                "satisfaction_score": session_metrics.get('user_satisfaction_score', 0.8)
            }
        
        return {
            "overview": {
                "active_sessions": len(active_sessions),
                "total_sessions": total_sessions,
                "peak_concurrent_sessions": self._system_metrics.get("peak_concurrent_actions", 0),
                "average_session_duration": avg_duration,
                "average_intents_per_session": avg_intents,
                "average_user_satisfaction": avg_satisfaction
            },
            "active_sessions": active_sessions,
            "session_details": session_details
        }
    
    def _calculate_session_success_rate(self, session_metrics: Dict[str, Any]) -> float:
        """Calculate success rate for a session"""
        successful = session_metrics.get('successful_intents', 0)
        failed = session_metrics.get('failed_intents', 0)
        total = successful + failed
        return successful / total if total > 0 else 0.0
    
    def generate_analytics_report(self) -> Dict[str, Any]:
        """Generate comprehensive analytics report matching AnalyticsManager format"""
        intent_analytics = self.get_intent_analytics()
        session_analytics = self.get_session_analytics()
        system_metrics = self.get_system_metrics()
        
        return {
            "timestamp": time.time(),
            "report_type": "comprehensive_analytics",
            "intents": intent_analytics,
            "sessions": session_analytics,
            "system": {
                "uptime_seconds": system_metrics.get("uptime_seconds", 0),
                "total_requests": system_metrics.get("total_actions_started", 0),
                "total_intents_processed": intent_analytics["overview"]["total_intents_processed"],
                "total_execution_errors": system_metrics.get("total_actions_failed", 0),
                "average_processing_time": system_metrics.get("average_completion_time", 0.0),
                "requests_per_minute": 0.0,  # Calculated in original, simplified here
                "error_rate": system_metrics.get("total_actions_failed", 0) / max(1, system_metrics.get("total_actions_completed", 1))
            }
        }
    
    # Component-specific metrics methods (Phase 1 complete integration)
    def record_resampling_operation(self, component_name: str, duration_ms: float, success: bool = True) -> None:
        """Record a resampling operation for a component"""
        domain = f"component_{component_name}_resampling"
        
        if domain not in self._domain_metrics:
            self._domain_metrics[domain] = DomainMetrics(domain=domain)
        
        # Track as an action for consistency with fire-and-forget pattern
        if success:
            self.record_action_start(domain, "resampling", component_name)
            self.record_action_completion(domain, success=True)
        else:
            self.record_action_start(domain, "resampling", component_name)
            self.record_action_completion(domain, success=False, error="resampling_failed")
        
        # Store resampling-specific metrics
        if not hasattr(self._domain_metrics[domain], 'resampling_metrics'):
            self._domain_metrics[domain].resampling_metrics = {
                'total_operations': 0,
                'total_time_ms': 0.0,
                'failures': 0,
                'average_time_ms': 0.0
            }
        
        resampling = self._domain_metrics[domain].resampling_metrics
        resampling['total_operations'] += 1
        resampling['total_time_ms'] += duration_ms
        if not success:
            resampling['failures'] += 1
        resampling['average_time_ms'] = resampling['total_time_ms'] / resampling['total_operations']
    
    def record_detection_operation(self, component_name: str, success: bool, wake_word: str = None) -> None:
        """Record a detection operation for voice trigger components"""
        domain = f"component_{component_name}_detection"
        
        if domain not in self._domain_metrics:
            self._domain_metrics[domain] = DomainMetrics(domain=domain)
        
        # Track as an action
        self.record_action_start(domain, "detection", component_name)
        self.record_action_completion(domain, success=success)
        
        # Store detection-specific metrics
        if not hasattr(self._domain_metrics[domain], 'detection_metrics'):
            self._domain_metrics[domain].detection_metrics = {
                'total_operations': 0,
                'successes': 0,
                'wake_words': {}
            }
        
        detection = self._domain_metrics[domain].detection_metrics
        detection['total_operations'] += 1
        if success:
            detection['successes'] += 1
            if wake_word:
                detection['wake_words'][wake_word] = detection['wake_words'].get(wake_word, 0) + 1
    
    def get_component_resampling_metrics(self, component_name: str) -> Dict[str, Any]:
        """Get resampling metrics for a specific component"""
        domain = f"component_{component_name}_resampling"
        if domain in self._domain_metrics:
            return getattr(self._domain_metrics[domain], 'resampling_metrics', {})
        return {}
    
    def get_component_detection_metrics(self, component_name: str) -> Dict[str, Any]:
        """Get detection metrics for a specific component"""
        domain = f"component_{component_name}_detection"
        if domain in self._domain_metrics:
            return getattr(self._domain_metrics[domain], 'detection_metrics', {})
        return {}

    # Phase 4 TODO16: Contextual command performance tracking methods
    
    def set_contextual_command_config(self, config) -> None:
        """Set contextual command configuration for threshold monitoring"""
        self._contextual_command_config = config
        self.logger.info(f"Contextual command monitoring configured with {config.latency_threshold_ms}ms threshold")
    
    def record_contextual_disambiguation(
        self, 
        command_type: str,
        target_domain: Optional[str],
        latency_ms: float,
        confidence: float,
        resolution_method: str,
        cache_hit: bool = False
    ) -> None:
        """Record contextual command disambiguation metrics"""
        
        # Update counters
        self._contextual_command_metrics["total_disambiguations"] += 1
        if target_domain:
            self._contextual_command_metrics["successful_disambiguations"] += 1
        else:
            self._contextual_command_metrics["failed_disambiguations"] += 1
        
        # Update latency statistics
        self._update_contextual_latency_stats(latency_ms)
        
        # Check threshold violations
        if (self._contextual_command_config and 
            latency_ms > self._contextual_command_config.latency_threshold_ms):
            self._contextual_command_metrics["threshold_violations"] += 1
            self.logger.warning(f"Contextual disambiguation exceeded threshold: {latency_ms:.2f}ms > {self._contextual_command_config.latency_threshold_ms}ms")
        
        # Update cache statistics
        if cache_hit:
            self._contextual_command_metrics["cache_hits"] += 1
        else:
            self._contextual_command_metrics["cache_misses"] += 1
        
        # Track per-domain and per-command statistics
        self._update_contextual_resolution_stats(target_domain, command_type, confidence, resolution_method)
        
        # Store confidence score for analysis (keep last 100)
        self._contextual_command_metrics["confidence_scores"].append(confidence)
        if len(self._contextual_command_metrics["confidence_scores"]) > 100:
            self._contextual_command_metrics["confidence_scores"].pop(0)
        
        self._contextual_command_metrics["last_updated"] = time.time()
        
        # Log detailed metrics for debugging
        self.logger.debug(f"Contextual disambiguation recorded: {command_type} -> {target_domain} "
                         f"({latency_ms:.3f}ms, confidence={confidence:.2f}, method={resolution_method}, cache_hit={cache_hit})")
    
    def _update_contextual_latency_stats(self, latency_ms: float) -> None:
        """Update contextual command latency statistics"""
        metrics = self._contextual_command_metrics
        
        # Update total and average
        metrics["total_latency_ms"] += latency_ms
        total_count = metrics["total_disambiguations"]
        if total_count > 0:
            metrics["average_latency_ms"] = metrics["total_latency_ms"] / total_count
        
        # Update min/max
        if latency_ms > metrics["max_latency_ms"]:
            metrics["max_latency_ms"] = latency_ms
        if latency_ms < metrics["min_latency_ms"]:
            metrics["min_latency_ms"] = latency_ms
    
    def _update_contextual_resolution_stats(
        self, 
        target_domain: Optional[str], 
        command_type: str, 
        confidence: float, 
        resolution_method: str
    ) -> None:
        """Update per-domain and per-command resolution statistics"""
        
        # Track domain resolution counts
        if target_domain:
            domain_stats = self._contextual_command_metrics["domain_resolutions"]
            if target_domain not in domain_stats:
                domain_stats[target_domain] = {
                    "count": 0,
                    "total_confidence": 0.0,
                    "resolution_methods": {}
                }
            
            domain_stats[target_domain]["count"] += 1
            domain_stats[target_domain]["total_confidence"] += confidence
            
            # Track resolution methods per domain
            method_stats = domain_stats[target_domain]["resolution_methods"]
            method_stats[resolution_method] = method_stats.get(resolution_method, 0) + 1
        
        # Track command type statistics
        cmd_stats = self._contextual_command_metrics["command_type_stats"]
        if command_type not in cmd_stats:
            cmd_stats[command_type] = {
                "count": 0,
                "successful": 0,
                "total_confidence": 0.0,
                "total_latency": 0.0
            }
        
        cmd_stats[command_type]["count"] += 1
        if target_domain:
            cmd_stats[command_type]["successful"] += 1
        cmd_stats[command_type]["total_confidence"] += confidence
    
    def get_contextual_command_metrics(self) -> Dict[str, Any]:
        """Get contextual command performance metrics with derived calculations"""
        metrics = self._contextual_command_metrics.copy()
        
        # Calculate derived metrics
        total = metrics["total_disambiguations"]
        if total > 0:
            metrics["success_rate"] = metrics["successful_disambiguations"] / total
            metrics["failure_rate"] = metrics["failed_disambiguations"] / total
            metrics["threshold_violation_rate"] = metrics["threshold_violations"] / total
            
            # Cache performance
            total_cache_requests = metrics["cache_hits"] + metrics["cache_misses"]
            if total_cache_requests > 0:
                metrics["cache_hit_rate"] = metrics["cache_hits"] / total_cache_requests
            else:
                metrics["cache_hit_rate"] = 0.0
            
            # Confidence analysis
            if metrics["confidence_scores"]:
                confidence_scores = metrics["confidence_scores"]
                metrics["confidence_analysis"] = {
                    "average": sum(confidence_scores) / len(confidence_scores),
                    "min": min(confidence_scores),
                    "max": max(confidence_scores),
                    "count": len(confidence_scores)
                }
        else:
            metrics["success_rate"] = 0.0
            metrics["failure_rate"] = 0.0
            metrics["threshold_violation_rate"] = 0.0
            metrics["cache_hit_rate"] = 0.0
        
        # Add domain resolution analysis
        for domain, stats in metrics["domain_resolutions"].items():
            if stats["count"] > 0:
                stats["average_confidence"] = stats["total_confidence"] / stats["count"]
        
        # Add command type analysis  
        for cmd_type, stats in metrics["command_type_stats"].items():
            if stats["count"] > 0:
                stats["success_rate"] = stats["successful"] / stats["count"]
                stats["average_confidence"] = stats["total_confidence"] / stats["count"]
        
        return metrics


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


async def initialize_metrics_system(config: dict = None) -> MetricsCollector:
    """Initialize the global metrics system with configuration"""
    collector = get_metrics_collector()
    
    # Apply configuration if provided
    if config:
        if 'monitoring_interval' in config:
            collector._monitoring_interval = config['monitoring_interval']
        if 'max_history' in config:
            collector.max_history_size = config['max_history']
            # Update the deque with new max size
            collector._completed_actions = deque(collector._completed_actions, maxlen=config['max_history'])
    
    await collector.start_monitoring()
    return collector


async def shutdown_metrics_system() -> None:
    """Shutdown the global metrics system"""
    global _metrics_collector
    if _metrics_collector:
        await _metrics_collector.stop_monitoring()
        _metrics_collector = None
