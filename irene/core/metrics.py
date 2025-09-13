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
        """Get system-wide metrics"""
        metrics = self._system_metrics.copy()
        metrics["uptime_seconds"] = time.time() - metrics["uptime_start"]
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


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


async def initialize_metrics_system() -> MetricsCollector:
    """Initialize the global metrics system"""
    collector = get_metrics_collector()
    await collector.start_monitoring()
    return collector


async def shutdown_metrics_system() -> None:
    """Shutdown the global metrics system"""
    global _metrics_collector
    if _metrics_collector:
        await _metrics_collector.stop_monitoring()
        _metrics_collector = None
