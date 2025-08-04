"""
Analytics and Monitoring System

Tracks intent recognition accuracy, execution success rates, context session duration,
and user satisfaction scoring for the intent system.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
import asyncio

from ..intents.models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


@dataclass
class IntentMetrics:
    """Metrics for intent processing"""
    intent_name: str
    recognition_count: int = 0
    execution_success_count: int = 0
    execution_failure_count: int = 0
    total_confidence: float = 0.0
    response_times: List[float] = field(default_factory=list)
    last_used: float = field(default_factory=time.time)
    
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence for this intent"""
        return self.total_confidence / self.recognition_count if self.recognition_count > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate for this intent"""
        total_executions = self.execution_success_count + self.execution_failure_count
        return self.execution_success_count / total_executions if total_executions > 0 else 0.0
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time"""
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0


@dataclass
class SessionMetrics:
    """Metrics for conversation sessions"""
    session_id: str
    start_time: float
    last_activity: float
    intent_count: int = 0
    successful_intents: int = 0
    failed_intents: int = 0
    user_satisfaction_score: float = 0.8  # Default assumption
    conversation_coherence: float = 0.8   # Default assumption
    language_switches: int = 0
    domains_used: List[str] = field(default_factory=list)
    
    @property
    def session_duration(self) -> float:
        """Get session duration in seconds"""
        return self.last_activity - self.start_time
    
    @property
    def intent_success_rate(self) -> float:
        """Calculate intent success rate for this session"""
        total = self.successful_intents + self.failed_intents
        return self.successful_intents / total if total > 0 else 0.0


class AnalyticsManager:
    """
    Analytics and monitoring manager for the intent system.
    
    Tracks:
    - Intent recognition accuracy
    - Intent execution success rates
    - Context session duration and quality
    - System performance metrics
    """
    
    def __init__(self, max_metrics_history: int = 1000):
        """
        Initialize analytics manager.
        
        Args:
            max_metrics_history: Maximum number of recent metrics to keep in memory
        """
        self.intent_metrics: Dict[str, IntentMetrics] = {}
        self.session_metrics: Dict[str, SessionMetrics] = {}
        self.system_metrics = {
            "start_time": time.time(),
            "total_requests": 0,
            "total_intents_processed": 0,
            "total_execution_errors": 0,
            "avg_processing_time": 0.0,
            "peak_concurrent_sessions": 0
        }
        
        # Recent metrics for trend analysis
        self.max_history = max_metrics_history
        self.recent_processing_times = deque(maxlen=max_metrics_history)
        self.recent_confidence_scores = deque(maxlen=max_metrics_history)
        self.hourly_stats = defaultdict(int)
        
        # Performance tracking
        self.active_sessions = set()
        self.peak_sessions = 0
        
        logger.info("Analytics manager initialized")
    
    async def track_intent_recognition(self, intent: Intent, processing_time: float):
        """
        Track intent recognition metrics.
        
        Args:
            intent: Recognized intent
            processing_time: Time taken to recognize intent in seconds
        """
        # Update intent-specific metrics
        if intent.name not in self.intent_metrics:
            self.intent_metrics[intent.name] = IntentMetrics(intent.name)
        
        metrics = self.intent_metrics[intent.name]
        metrics.recognition_count += 1
        metrics.total_confidence += intent.confidence
        metrics.response_times.append(processing_time)
        metrics.last_used = time.time()
        
        # Keep response times list reasonable
        if len(metrics.response_times) > 100:
            metrics.response_times = metrics.response_times[-50:]
        
        # Update system metrics
        self.system_metrics["total_intents_processed"] += 1
        self.recent_processing_times.append(processing_time)
        self.recent_confidence_scores.append(intent.confidence)
        
        # Update hourly stats
        hour_key = int(time.time() // 3600)
        self.hourly_stats[hour_key] += 1
        
        # Update average processing time
        if self.recent_processing_times:
            self.system_metrics["avg_processing_time"] = sum(self.recent_processing_times) / len(self.recent_processing_times)
        
        logger.debug(f"Tracked intent recognition: {intent.name} (confidence: {intent.confidence:.2f}, time: {processing_time:.3f}s)")
    
    async def track_intent_execution(self, intent: Intent, result: IntentResult, execution_time: float):
        """
        Track intent execution metrics.
        
        Args:
            intent: Executed intent
            result: Execution result
            execution_time: Time taken to execute intent in seconds
        """
        # Update intent-specific metrics
        if intent.name not in self.intent_metrics:
            self.intent_metrics[intent.name] = IntentMetrics(intent.name)
        
        metrics = self.intent_metrics[intent.name]
        if result.success:
            metrics.execution_success_count += 1
        else:
            metrics.execution_failure_count += 1
            self.system_metrics["total_execution_errors"] += 1
        
        # Update session metrics if available
        if intent.session_id in self.session_metrics:
            session = self.session_metrics[intent.session_id]
            session.intent_count += 1
            session.last_activity = time.time()
            
            if result.success:
                session.successful_intents += 1
            else:
                session.failed_intents += 1
            
            # Track domain usage
            if intent.domain and intent.domain not in session.domains_used:
                session.domains_used.append(intent.domain)
        
        logger.debug(f"Tracked intent execution: {intent.name} (success: {result.success}, time: {execution_time:.3f}s)")
    
    async def track_session_start(self, session_id: str):
        """
        Track the start of a conversation session.
        
        Args:
            session_id: Session identifier
        """
        current_time = time.time()
        
        self.session_metrics[session_id] = SessionMetrics(
            session_id=session_id,
            start_time=current_time,
            last_activity=current_time
        )
        
        self.active_sessions.add(session_id)
        
        # Update peak concurrent sessions
        if len(self.active_sessions) > self.peak_sessions:
            self.peak_sessions = len(self.active_sessions)
            self.system_metrics["peak_concurrent_sessions"] = self.peak_sessions
        
        logger.debug(f"Started tracking session: {session_id}")
    
    async def track_session_end(self, session_id: str, user_satisfaction: float = None):
        """
        Track the end of a conversation session.
        
        Args:
            session_id: Session identifier
            user_satisfaction: Optional user satisfaction score (0.0-1.0)
        """
        if session_id in self.session_metrics:
            session = self.session_metrics[session_id]
            session.last_activity = time.time()
            
            if user_satisfaction is not None:
                session.user_satisfaction_score = user_satisfaction
            
            logger.debug(f"Ended tracking session: {session_id} (duration: {session.session_duration:.1f}s)")
        
        self.active_sessions.discard(session_id)
    
    async def get_intent_analytics(self) -> Dict[str, Any]:
        """Get comprehensive intent analytics"""
        total_intents = sum(metrics.recognition_count for metrics in self.intent_metrics.values())
        
        # Calculate overall metrics
        if self.intent_metrics:
            avg_confidence = sum(metrics.average_confidence * metrics.recognition_count 
                               for metrics in self.intent_metrics.values()) / total_intents if total_intents > 0 else 0.0
            
            overall_success_rate = sum(metrics.execution_success_count 
                                     for metrics in self.intent_metrics.values()) / total_intents if total_intents > 0 else 0.0
        else:
            avg_confidence = 0.0
            overall_success_rate = 0.0
        
        # Top intents by usage
        top_intents = sorted(
            [(name, metrics.recognition_count, metrics.average_confidence, metrics.success_rate)
             for name, metrics in self.intent_metrics.items()],
            key=lambda x: x[1], reverse=True
        )[:10]
        
        # Recent performance trends
        recent_avg_confidence = sum(self.recent_confidence_scores) / len(self.recent_confidence_scores) if self.recent_confidence_scores else 0.0
        
        return {
            "overview": {
                "total_intents_processed": total_intents,
                "unique_intent_types": len(self.intent_metrics),
                "average_confidence": avg_confidence,
                "overall_success_rate": overall_success_rate,
                "recent_average_confidence": recent_avg_confidence
            },
            "top_intents": [
                {
                    "name": name,
                    "usage_count": count,
                    "avg_confidence": conf,
                    "success_rate": success
                }
                for name, count, conf, success in top_intents
            ],
            "detailed_metrics": {
                name: {
                    "recognition_count": metrics.recognition_count,
                    "average_confidence": metrics.average_confidence,
                    "success_rate": metrics.success_rate,
                    "average_response_time": metrics.average_response_time,
                    "last_used": metrics.last_used
                }
                for name, metrics in self.intent_metrics.items()
            }
        }
    
    async def get_session_analytics(self) -> Dict[str, Any]:
        """Get comprehensive session analytics"""
        active_session_count = len(self.active_sessions)
        total_sessions = len(self.session_metrics)
        
        if self.session_metrics:
            avg_session_duration = sum(session.session_duration for session in self.session_metrics.values()) / total_sessions
            avg_intents_per_session = sum(session.intent_count for session in self.session_metrics.values()) / total_sessions
            avg_user_satisfaction = sum(session.user_satisfaction_score for session in self.session_metrics.values()) / total_sessions
        else:
            avg_session_duration = 0.0
            avg_intents_per_session = 0.0
            avg_user_satisfaction = 0.0
        
        # Active sessions info
        active_sessions_info = []
        for session_id in self.active_sessions:
            if session_id in self.session_metrics:
                session = self.session_metrics[session_id]
                active_sessions_info.append({
                    "session_id": session_id,
                    "duration": session.session_duration,
                    "intent_count": session.intent_count,
                    "success_rate": session.intent_success_rate
                })
        
        return {
            "overview": {
                "active_sessions": active_session_count,
                "total_sessions": total_sessions,
                "peak_concurrent_sessions": self.peak_sessions,
                "average_session_duration": avg_session_duration,
                "average_intents_per_session": avg_intents_per_session,
                "average_user_satisfaction": avg_user_satisfaction
            },
            "active_sessions": active_sessions_info,
            "session_details": {
                session_id: {
                    "start_time": session.start_time,
                    "duration": session.session_duration,
                    "intent_count": session.intent_count,
                    "success_rate": session.intent_success_rate,
                    "domains_used": session.domains_used,
                    "satisfaction_score": session.user_satisfaction_score
                }
                for session_id, session in self.session_metrics.items()
            }
        }
    
    async def get_system_performance(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        uptime = time.time() - self.system_metrics["start_time"]
        
        # Calculate requests per minute
        requests_per_minute = (self.system_metrics["total_requests"] / uptime) * 60 if uptime > 0 else 0.0
        
        # Recent hourly activity
        current_hour = int(time.time() // 3600)
        recent_hours = [self.hourly_stats.get(current_hour - i, 0) for i in range(24)]
        
        return {
            "system": {
                "uptime_seconds": uptime,
                "total_requests": self.system_metrics["total_requests"],
                "total_intents_processed": self.system_metrics["total_intents_processed"],
                "total_execution_errors": self.system_metrics["total_execution_errors"],
                "average_processing_time": self.system_metrics["avg_processing_time"],
                "requests_per_minute": requests_per_minute,
                "error_rate": self.system_metrics["total_execution_errors"] / max(1, self.system_metrics["total_intents_processed"])
            },
            "performance": {
                "peak_concurrent_sessions": self.peak_sessions,
                "current_active_sessions": len(self.active_sessions),
                "recent_24h_activity": recent_hours
            }
        }
    
    async def cleanup_old_metrics(self, max_age_hours: int = 24):
        """
        Clean up old metrics to prevent memory buildup.
        
        Args:
            max_age_hours: Maximum age of metrics to keep in hours
        """
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        # Clean up old session metrics
        old_sessions = [
            session_id for session_id, session in self.session_metrics.items()
            if session.last_activity < cutoff_time
        ]
        
        for session_id in old_sessions:
            del self.session_metrics[session_id]
            self.active_sessions.discard(session_id)
        
        # Clean up old hourly stats
        cutoff_hour = int(cutoff_time // 3600)
        old_hours = [hour for hour in self.hourly_stats.keys() if hour < cutoff_hour]
        
        for hour in old_hours:
            del self.hourly_stats[hour]
        
        if old_sessions or old_hours:
            logger.info(f"Cleaned up {len(old_sessions)} old sessions and {len(old_hours)} old hourly stats")
    
    async def generate_analytics_report(self) -> Dict[str, Any]:
        """Generate comprehensive analytics report"""
        intent_analytics = await self.get_intent_analytics()
        session_analytics = await self.get_session_analytics()
        system_performance = await self.get_system_performance()
        
        return {
            "timestamp": time.time(),
            "report_type": "comprehensive_analytics",
            "intents": intent_analytics,
            "sessions": session_analytics,
            "system": system_performance
        } 