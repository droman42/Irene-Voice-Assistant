"""
Memory Management Service - Phase 3.3 Implementation

Provides automatic memory cleanup, monitoring, and optimization for
conversation contexts and system-wide memory usage.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MemoryAlert:
    """Represents a memory usage alert"""
    
    alert_type: str  # "warning", "critical", "cleanup_performed"
    message: str
    memory_usage_mb: float
    threshold_mb: float
    session_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)


class MemoryManager:
    """
    Service for managing memory usage across conversation contexts.
    
    Provides automatic cleanup, monitoring, and optimization to prevent
    memory leaks and ensure efficient resource utilization.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.MemoryManager")
        self.context_manager = None  # Injected during initialization
        
        # Memory monitoring configuration
        self._monitoring_enabled = True
        self._monitoring_interval = 300.0  # 5 minutes
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Cleanup configuration
        self._auto_cleanup_enabled = True
        self._cleanup_interval = 1800.0  # 30 minutes
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Memory tracking
        self._memory_alerts: List[MemoryAlert] = []
        self._cleanup_history: List[Dict[str, Any]] = []
        self._system_memory_stats = {
            "total_cleanups_performed": 0,
            "total_memory_freed_mb": 0.0,
            "last_cleanup_time": 0,
            "average_cleanup_interval": 0.0,
            "peak_memory_usage_mb": 0.0,
            "current_contexts_count": 0
        }
        
        # Alert callbacks
        self._alert_callbacks: List[Callable[[MemoryAlert], None]] = []
    
    async def initialize(self, context_manager) -> None:
        """Initialize memory manager with context manager"""
        self.context_manager = context_manager
        
        # Start monitoring and cleanup tasks
        await self.start_monitoring()
        await self.start_auto_cleanup()
        
        self.logger.info("Memory manager initialized")
    
    async def shutdown(self) -> None:
        """Shutdown memory manager"""
        await self.stop_monitoring()
        await self.stop_auto_cleanup()
        self.logger.info("Memory manager shutdown")
    
    async def start_monitoring(self) -> None:
        """Start memory monitoring task"""
        if self._monitoring_task is None and self._monitoring_enabled:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self.logger.info("Memory monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop memory monitoring task"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            self.logger.info("Memory monitoring stopped")
    
    async def start_auto_cleanup(self) -> None:
        """Start automatic cleanup task"""
        if self._cleanup_task is None and self._auto_cleanup_enabled:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self.logger.info("Automatic cleanup started")
    
    async def stop_auto_cleanup(self) -> None:
        """Stop automatic cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            self.logger.info("Automatic cleanup stopped")
    
    def add_alert_callback(self, callback: Callable[[MemoryAlert], None]) -> None:
        """Add callback for memory alerts"""
        self._alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: Callable[[MemoryAlert], None]) -> None:
        """Remove alert callback"""
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)
    
    async def analyze_system_memory_usage(self) -> Dict[str, Any]:
        """Analyze memory usage across all conversation contexts"""
        if not self.context_manager:
            return {"error": "No context manager available"}
        
        try:
            # Get all active contexts
            contexts = await self._get_all_contexts()
            
            total_memory_mb = 0.0
            context_stats = []
            
            for session_id, context in contexts.items():
                memory_usage = context.get_memory_usage_estimate()
                memory_mb = memory_usage.get("total_mb", 0.0)
                total_memory_mb += memory_mb
                
                context_stats.append({
                    "session_id": session_id,
                    "memory_mb": memory_mb,
                    "conversation_entries": len(context.conversation_history),
                    "recent_actions": len(context.recent_actions),
                    "failed_actions": len(context.failed_actions),
                    "active_actions": len(context.active_actions),
                    "last_updated": context.last_updated
                })
            
            # Sort by memory usage
            context_stats.sort(key=lambda x: x["memory_mb"], reverse=True)
            
            # Update system stats
            self._system_memory_stats["current_contexts_count"] = len(contexts)
            if total_memory_mb > self._system_memory_stats["peak_memory_usage_mb"]:
                self._system_memory_stats["peak_memory_usage_mb"] = total_memory_mb
            
            return {
                "total_contexts": len(contexts),
                "total_memory_mb": total_memory_mb,
                "average_memory_per_context_mb": total_memory_mb / len(contexts) if contexts else 0.0,
                "largest_contexts": context_stats[:10],  # Top 10 largest contexts
                "system_stats": self._system_memory_stats.copy(),
                "analysis_timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to analyze system memory usage: {e}")
            return {"error": str(e)}
    
    async def perform_system_cleanup(self, aggressive: bool = False) -> Dict[str, Any]:
        """Perform cleanup across all conversation contexts"""
        if not self.context_manager:
            return {"error": "No context manager available"}
        
        cleanup_start_time = time.time()
        
        try:
            contexts = await self._get_all_contexts()
            
            total_stats = {
                "contexts_cleaned": 0,
                "conversation_history_removed": 0,
                "recent_actions_removed": 0,
                "failed_actions_removed": 0,
                "memory_freed_mb": 0.0
            }
            
            for session_id, context in contexts.items():
                try:
                    # Get memory usage before cleanup
                    before_memory = context.get_memory_usage_estimate()
                    
                    # Check if cleanup is needed
                    cleanup_needed = context.should_trigger_cleanup()
                    
                    if aggressive or any(cleanup_needed.values()):
                        # Perform cleanup
                        cleanup_stats = context.perform_cleanup(aggressive=aggressive)
                        
                        # Get memory usage after cleanup
                        after_memory = context.get_memory_usage_estimate()
                        
                        # Update totals
                        total_stats["contexts_cleaned"] += 1
                        total_stats["conversation_history_removed"] += cleanup_stats["conversation_history_removed"]
                        total_stats["recent_actions_removed"] += cleanup_stats["recent_actions_removed"]
                        total_stats["failed_actions_removed"] += cleanup_stats["failed_actions_removed"]
                        
                        memory_freed = before_memory.get("total_mb", 0) - after_memory.get("total_mb", 0)
                        total_stats["memory_freed_mb"] += memory_freed
                        
                        self.logger.debug(f"Cleaned context {session_id}: freed {memory_freed:.2f}MB")
                        
                except Exception as e:
                    self.logger.error(f"Failed to cleanup context {session_id}: {e}")
            
            cleanup_duration = time.time() - cleanup_start_time
            
            # Update system stats
            self._system_memory_stats["total_cleanups_performed"] += 1
            self._system_memory_stats["total_memory_freed_mb"] += total_stats["memory_freed_mb"]
            self._system_memory_stats["last_cleanup_time"] = cleanup_start_time
            
            # Calculate average cleanup interval
            if len(self._cleanup_history) > 0:
                last_cleanup_time = self._cleanup_history[-1]["timestamp"]
                interval = cleanup_start_time - last_cleanup_time
                
                # Update running average
                current_avg = self._system_memory_stats["average_cleanup_interval"]
                cleanup_count = self._system_memory_stats["total_cleanups_performed"]
                self._system_memory_stats["average_cleanup_interval"] = (
                    (current_avg * (cleanup_count - 1) + interval) / cleanup_count
                )
            
            # Record cleanup in history
            cleanup_record = {
                "timestamp": cleanup_start_time,
                "duration": cleanup_duration,
                "aggressive": aggressive,
                "stats": total_stats.copy()
            }
            self._cleanup_history.append(cleanup_record)
            
            # Keep only last 50 cleanup records
            if len(self._cleanup_history) > 50:
                self._cleanup_history = self._cleanup_history[-50:]
            
            # Create cleanup alert
            if total_stats["memory_freed_mb"] > 0:
                alert = MemoryAlert(
                    alert_type="cleanup_performed",
                    message=f"System cleanup freed {total_stats['memory_freed_mb']:.2f}MB across {total_stats['contexts_cleaned']} contexts",
                    memory_usage_mb=total_stats["memory_freed_mb"],
                    threshold_mb=0.0,
                    details=total_stats
                )
                await self._trigger_alert(alert)
            
            self.logger.info(
                f"System cleanup completed: {total_stats['contexts_cleaned']} contexts, "
                f"{total_stats['memory_freed_mb']:.2f}MB freed in {cleanup_duration:.2f}s"
            )
            
            return {
                "success": True,
                "duration": cleanup_duration,
                "stats": total_stats
            }
            
        except Exception as e:
            self.logger.error(f"System cleanup failed: {e}")
            return {"error": str(e)}
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get comprehensive memory management statistics"""
        return {
            "system_stats": self._system_memory_stats.copy(),
            "recent_alerts": self._memory_alerts[-10:],  # Last 10 alerts
            "recent_cleanups": self._cleanup_history[-5:],  # Last 5 cleanups
            "monitoring_enabled": self._monitoring_enabled,
            "auto_cleanup_enabled": self._auto_cleanup_enabled,
            "monitoring_interval": self._monitoring_interval,
            "cleanup_interval": self._cleanup_interval
        }
    
    async def _monitoring_loop(self) -> None:
        """Background memory monitoring loop"""
        self.logger.info("Memory monitoring loop started")
        
        while self._monitoring_enabled:
            try:
                # Analyze current memory usage
                analysis = await self.analyze_system_memory_usage()
                
                if "error" not in analysis:
                    total_memory = analysis.get("total_memory_mb", 0)
                    context_count = analysis.get("total_contexts", 0)
                    
                    # Check for memory alerts
                    if total_memory > 200:  # Critical threshold
                        alert = MemoryAlert(
                            alert_type="critical",
                            message=f"Critical memory usage: {total_memory:.1f}MB across {context_count} contexts",
                            memory_usage_mb=total_memory,
                            threshold_mb=200.0,
                            details=analysis
                        )
                        await self._trigger_alert(alert)
                        
                    elif total_memory > 100:  # Warning threshold
                        alert = MemoryAlert(
                            alert_type="warning",
                            message=f"High memory usage: {total_memory:.1f}MB across {context_count} contexts",
                            memory_usage_mb=total_memory,
                            threshold_mb=100.0,
                            details=analysis
                        )
                        await self._trigger_alert(alert)
                    
                    # Log periodic summary
                    self.logger.info(
                        f"📊 Memory Monitor: {total_memory:.1f}MB across {context_count} contexts"
                    )
                
                await asyncio.sleep(self._monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in memory monitoring loop: {e}")
                await asyncio.sleep(60)  # Brief pause before retrying
        
        self.logger.info("Memory monitoring loop stopped")
    
    async def _cleanup_loop(self) -> None:
        """Background automatic cleanup loop"""
        self.logger.info("Automatic cleanup loop started")
        
        while self._auto_cleanup_enabled:
            try:
                # Perform system cleanup
                result = await self.perform_system_cleanup(aggressive=False)
                
                if "error" not in result:
                    stats = result.get("stats", {})
                    if stats.get("memory_freed_mb", 0) > 0:
                        self.logger.info(
                            f"🧹 Auto-cleanup: freed {stats['memory_freed_mb']:.2f}MB "
                            f"from {stats['contexts_cleaned']} contexts"
                        )
                
                await asyncio.sleep(self._cleanup_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in automatic cleanup loop: {e}")
                await asyncio.sleep(300)  # 5 minute pause before retrying
        
        self.logger.info("Automatic cleanup loop stopped")
    
    async def _trigger_alert(self, alert: MemoryAlert) -> None:
        """Trigger a memory alert"""
        # Add to alert history
        self._memory_alerts.append(alert)
        
        # Keep only last 100 alerts
        if len(self._memory_alerts) > 100:
            self._memory_alerts = self._memory_alerts[-100:]
        
        # Log the alert
        log_level = {
            "warning": logging.WARNING,
            "critical": logging.ERROR,
            "cleanup_performed": logging.INFO
        }.get(alert.alert_type, logging.INFO)
        
        self.logger.log(log_level, f"🚨 Memory Alert: {alert.message}")
        
        # Call registered callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"Error in memory alert callback: {e}")
    
    async def _get_all_contexts(self) -> Dict[str, Any]:
        """Get all active conversation contexts"""
        # This is a placeholder - actual implementation depends on context manager structure
        if hasattr(self.context_manager, 'get_all_contexts'):
            return await self.context_manager.get_all_contexts()
        elif hasattr(self.context_manager, '_contexts'):
            return self.context_manager._contexts.copy()
        else:
            self.logger.warning("Unable to access contexts from context manager")
            return {}


# Global memory manager instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


async def initialize_memory_manager(context_manager) -> MemoryManager:
    """Initialize the global memory manager"""
    manager = get_memory_manager()
    await manager.initialize(context_manager)
    return manager


async def shutdown_memory_manager() -> None:
    """Shutdown the global memory manager"""
    global _memory_manager
    if _memory_manager:
        await _memory_manager.shutdown()
        _memory_manager = None
