"""
Async Timer Management - Non-blocking timer system

Replaces threading.Timer with asyncio.Task for proper async integration.
Provides timer scheduling, cancellation, and management capabilities.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass
import uuid

logger = logging.getLogger(__name__)


@dataclass
class TimerInfo:
    """Information about a scheduled timer"""
    timer_id: str
    name: str
    created_at: datetime
    scheduled_for: datetime
    callback: Callable[[], Awaitable[Any]]
    task: asyncio.Task
    is_recurring: bool = False
    interval_seconds: Optional[float] = None


class AsyncTimerManager:
    """
    Async timer management system replacing threading.Timer.
    
    Features:
    - Non-blocking timer operations
    - Timer lifecycle management
    - Graceful shutdown
    - Timer state tracking
    """
    
    def __init__(self):
        self._timers: dict[str, TimerInfo] = {}
        self._running = False
        
    async def start(self) -> None:
        """Start the timer manager"""
        self._running = True
        logger.info("AsyncTimerManager started")
        
    async def stop(self) -> None:
        """Stop the timer manager and cancel all timers"""
        self._running = False
        await self.cancel_all()
        logger.info("AsyncTimerManager stopped")
        
    async def schedule_timer(
        self,
        name: str,
        delay_seconds: float,
        callback: Callable[[], Awaitable[Any]],
        timer_id: Optional[str] = None
    ) -> str:
        """
        Schedule a one-time timer.
        
        Args:
            name: Human-readable timer name
            delay_seconds: Delay in seconds before callback execution
            callback: Async function to call when timer expires
            timer_id: Optional custom timer ID
            
        Returns:
            Timer ID for cancellation
        """
        if not self._running:
            raise RuntimeError("Timer manager not started")
            
        timer_id = timer_id or str(uuid.uuid4())
        
        if timer_id in self._timers:
            raise ValueError(f"Timer with ID '{timer_id}' already exists")
            
        scheduled_for = datetime.now() + timedelta(seconds=delay_seconds)
        
        # Create the timer task
        task = asyncio.create_task(self._timer_wrapper(timer_id, delay_seconds, callback))
        
        timer_info = TimerInfo(
            timer_id=timer_id,
            name=name,
            created_at=datetime.now(),
            scheduled_for=scheduled_for,
            callback=callback,
            task=task,
            is_recurring=False
        )
        
        self._timers[timer_id] = timer_info
        
        logger.info(f"Scheduled timer '{name}' (ID: {timer_id}) for {delay_seconds}s")
        return timer_id
        
    async def schedule_recurring_timer(
        self,
        name: str,
        interval_seconds: float,
        callback: Callable[[], Awaitable[Any]],
        timer_id: Optional[str] = None
    ) -> str:
        """
        Schedule a recurring timer.
        
        Args:
            name: Human-readable timer name
            interval_seconds: Interval between executions
            callback: Async function to call on each interval
            timer_id: Optional custom timer ID
            
        Returns:
            Timer ID for cancellation
        """
        if not self._running:
            raise RuntimeError("Timer manager not started")
            
        timer_id = timer_id or str(uuid.uuid4())
        
        if timer_id in self._timers:
            raise ValueError(f"Timer with ID '{timer_id}' already exists")
            
        scheduled_for = datetime.now() + timedelta(seconds=interval_seconds)
        
        # Create the recurring timer task
        task = asyncio.create_task(
            self._recurring_timer_wrapper(timer_id, interval_seconds, callback)
        )
        
        timer_info = TimerInfo(
            timer_id=timer_id,
            name=name,
            created_at=datetime.now(),
            scheduled_for=scheduled_for,
            callback=callback,
            task=task,
            is_recurring=True,
            interval_seconds=interval_seconds
        )
        
        self._timers[timer_id] = timer_info
        
        logger.info(f"Scheduled recurring timer '{name}' (ID: {timer_id}) every {interval_seconds}s")
        return timer_id
        
    async def cancel_timer(self, timer_id: str) -> bool:
        """
        Cancel a specific timer.
        
        Args:
            timer_id: Timer ID to cancel
            
        Returns:
            True if timer was cancelled, False if not found
        """
        timer_info = self._timers.get(timer_id)
        if not timer_info:
            return False
            
        timer_info.task.cancel()
        
        try:
            await timer_info.task
        except asyncio.CancelledError:
            pass
            
        del self._timers[timer_id]
        logger.info(f"Cancelled timer '{timer_info.name}' (ID: {timer_id})")
        return True
        
    async def cancel_all(self) -> int:
        """
        Cancel all active timers.
        
        Returns:
            Number of timers cancelled
        """
        timer_ids = list(self._timers.keys())
        cancelled_count = 0
        
        for timer_id in timer_ids:
            if await self.cancel_timer(timer_id):
                cancelled_count += 1
                
        logger.info(f"Cancelled {cancelled_count} timers")
        return cancelled_count
        
    async def _timer_wrapper(
        self, 
        timer_id: str, 
        delay_seconds: float, 
        callback: Callable[[], Awaitable[Any]]
    ) -> None:
        """Wrapper for one-time timer execution"""
        try:
            await asyncio.sleep(delay_seconds)
            
            if timer_id in self._timers:
                timer_info = self._timers[timer_id]
                logger.debug(f"Executing timer '{timer_info.name}' (ID: {timer_id})")
                
                try:
                    await callback()
                except Exception as e:
                    logger.error(f"Error in timer callback '{timer_info.name}': {e}")
                    
                # Remove timer after execution
                if timer_id in self._timers:
                    del self._timers[timer_id]
                    
        except asyncio.CancelledError:
            # Timer was cancelled
            pass
        except Exception as e:
            logger.error(f"Error in timer wrapper: {e}")
            
    async def _recurring_timer_wrapper(
        self,
        timer_id: str,
        interval_seconds: float,
        callback: Callable[[], Awaitable[Any]]
    ) -> None:
        """Wrapper for recurring timer execution"""
        try:
            while timer_id in self._timers and self._running:
                await asyncio.sleep(interval_seconds)
                
                if timer_id in self._timers:
                    timer_info = self._timers[timer_id]
                    logger.debug(f"Executing recurring timer '{timer_info.name}' (ID: {timer_id})")
                    
                    try:
                        await callback()
                    except Exception as e:
                        logger.error(f"Error in recurring timer callback '{timer_info.name}': {e}")
                        
        except asyncio.CancelledError:
            # Timer was cancelled
            pass
        except Exception as e:
            logger.error(f"Error in recurring timer wrapper: {e}")
            
    def get_timer_info(self, timer_id: str) -> Optional[TimerInfo]:
        """Get information about a specific timer"""
        return self._timers.get(timer_id)
        
    def list_timers(self) -> Dict[str, TimerInfo]:
        """Get all active timers"""
        return self._timers.copy()
        
    @property
    def active_timer_count(self) -> int:
        """Get the number of active timers"""
        return len(self._timers) 