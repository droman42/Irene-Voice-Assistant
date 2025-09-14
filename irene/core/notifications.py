"""
User Notification System - Phase 3.1 Implementation

Handles delivery of user notifications for fire-and-forget actions,
system status updates, and critical failures through multiple channels.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications that can be sent to users"""
    ACTION_COMPLETION = "action_completion"
    ACTION_FAILURE = "action_failure"
    SYSTEM_STATUS = "system_status"
    CRITICAL_ALERT = "critical_alert"


class NotificationPriority(Enum):
    """Priority levels for notifications"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DeliveryMethod(Enum):
    """Available notification delivery methods"""
    TTS = "tts"           # Text-to-speech audio notification
    LOG = "log"           # Log entry (always available)
    UI = "ui"             # User interface notification
    PUSH = "push"         # Push notification (future)
    EMAIL = "email"       # Email notification (future)


@dataclass
class NotificationMessage:
    """Represents a notification message to be delivered"""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: NotificationType = NotificationType.SYSTEM_STATUS
    priority: NotificationPriority = NotificationPriority.NORMAL
    title: str = ""
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    delivery_methods: List[DeliveryMethod] = field(default_factory=lambda: [DeliveryMethod.LOG])
    session_id: Optional[str] = None
    domain: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    delivered_at: Optional[float] = None
    delivery_status: Dict[DeliveryMethod, bool] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3


class NotificationService:
    """
    Service for delivering user notifications through multiple channels.
    
    Integrates with TTS, audio, and logging systems to provide comprehensive
    user feedback for fire-and-forget actions and system events.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.NotificationService")
        self._delivery_handlers: Dict[DeliveryMethod, Callable] = {}
        self._notification_queue: asyncio.Queue = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None
        self._running = False
        self._metrics = {
            "total_sent": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "deliveries_by_method": {},
            "deliveries_by_type": {}
        }
        
        # Configuration settings (configurable)
        self._default_channel = "log"
        self._tts_enabled = True
        self._web_enabled = True
        
        # Component references (injected during initialization)
        self.tts_component = None
        self.audio_component = None
        self.context_manager = None
        
    async def initialize(self, components: Dict[str, Any]) -> None:
        """Initialize notification service with system components"""
        self.tts_component = components.get('tts')
        self.audio_component = components.get('audio')
        self.context_manager = components.get('context_manager')
        
        # Register default delivery handlers
        self._delivery_handlers[DeliveryMethod.LOG] = self._deliver_via_log
        
        if self.tts_component and self.audio_component:
            self._delivery_handlers[DeliveryMethod.TTS] = self._deliver_via_tts
            self.logger.info("TTS notification delivery enabled")
        else:
            self.logger.info("TTS notification delivery disabled (TTS or Audio component not available)")
        
        # Start notification processing
        await self.start()
        
        self.logger.info("Notification service initialized")
    
    async def start(self) -> None:
        """Start the notification processing task"""
        if self._running:
            return
        
        self._running = True
        self._processing_task = asyncio.create_task(self._process_notifications())
        self.logger.info("Notification processing started")
    
    async def stop(self) -> None:
        """Stop the notification processing task"""
        if not self._running:
            return
        
        self._running = False
        
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Notification processing stopped")
    
    async def send_notification(self, notification: NotificationMessage) -> bool:
        """
        Queue a notification for delivery.
        
        Args:
            notification: Notification message to send
            
        Returns:
            True if queued successfully, False otherwise
        """
        try:
            await self._notification_queue.put(notification)
            self.logger.debug(f"Queued notification: {notification.type.value} - {notification.title}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to queue notification: {e}")
            return False
    
    async def send_action_completion_notification(
        self, 
        session_id: str, 
        domain: str, 
        action_name: str, 
        duration: float,
        success: bool = True,
        error: Optional[str] = None
    ) -> bool:
        """Send notification for completed fire-and-forget action"""
        
        # Get user preferences from context
        if self.context_manager:
            try:
                context = await self.context_manager.get_or_create_context(session_id)
                if not context.should_notify_completion(domain, duration):
                    return True  # User doesn't want this notification
                
                delivery_methods = [DeliveryMethod(method) for method in context.get_notification_methods("action_completion")]
            except Exception as e:
                self.logger.warning(f"Failed to get notification preferences: {e}")
                delivery_methods = [DeliveryMethod.LOG]
        else:
            delivery_methods = [DeliveryMethod.LOG]
        
        # Create notification message
        if success:
            title = f"Action Completed: {action_name}"
            message = f"The {action_name} action in {domain} has completed successfully after {duration:.1f} seconds."
            priority = NotificationPriority.NORMAL
        else:
            title = f"Action Failed: {action_name}"
            message = f"The {action_name} action in {domain} failed after {duration:.1f} seconds."
            if error:
                message += f" Error: {error}"
            priority = NotificationPriority.HIGH
        
        notification = NotificationMessage(
            type=NotificationType.ACTION_COMPLETION,
            priority=priority,
            title=title,
            message=message,
            details={
                "domain": domain,
                "action_name": action_name,
                "duration": duration,
                "success": success,
                "error": error
            },
            delivery_methods=delivery_methods,
            session_id=session_id,
            domain=domain
        )
        
        return await self.send_notification(notification)
    
    async def send_action_failure_notification(
        self,
        session_id: str,
        domain: str,
        action_name: str,
        error: str,
        is_critical: bool = False
    ) -> bool:
        """Send notification for failed fire-and-forget action"""
        
        # Get user preferences from context
        if self.context_manager:
            try:
                context = await self.context_manager.get_or_create_context(session_id)
                if not context.should_notify_failure(domain, error, is_critical):
                    return True  # User doesn't want this notification
                
                delivery_methods = [DeliveryMethod(method) for method in context.get_notification_methods("action_failure")]
            except Exception as e:
                self.logger.warning(f"Failed to get notification preferences: {e}")
                delivery_methods = [DeliveryMethod.LOG, DeliveryMethod.TTS] if is_critical else [DeliveryMethod.LOG]
        else:
            delivery_methods = [DeliveryMethod.LOG, DeliveryMethod.TTS] if is_critical else [DeliveryMethod.LOG]
        
        # Create notification message
        title = f"{'Critical ' if is_critical else ''}Action Failure: {action_name}"
        message = f"The {action_name} action in {domain} has failed. Error: {error}"
        
        if is_critical:
            message += " This is a critical failure that may require attention."
        
        notification = NotificationMessage(
            type=NotificationType.ACTION_FAILURE if not is_critical else NotificationType.CRITICAL_ALERT,
            priority=NotificationPriority.CRITICAL if is_critical else NotificationPriority.HIGH,
            title=title,
            message=message,
            details={
                "domain": domain,
                "action_name": action_name,
                "error": error,
                "is_critical": is_critical
            },
            delivery_methods=delivery_methods,
            session_id=session_id,
            domain=domain
        )
        
        return await self.send_notification(notification)
    
    async def send_system_status_notification(
        self,
        title: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> bool:
        """Send system status notification"""
        
        notification = NotificationMessage(
            type=NotificationType.SYSTEM_STATUS,
            priority=priority,
            title=title,
            message=message,
            details=details or {},
            delivery_methods=[DeliveryMethod.LOG]  # System notifications go to log by default
        )
        
        return await self.send_notification(notification)
    
    async def _process_notifications(self) -> None:
        """Main notification processing loop"""
        self.logger.info("Notification processing loop started")
        
        while self._running:
            try:
                # Get next notification from queue
                notification = await asyncio.wait_for(
                    self._notification_queue.get(), 
                    timeout=1.0
                )
                
                # Process the notification
                await self._deliver_notification(notification)
                
            except asyncio.TimeoutError:
                # No notifications to process, continue
                continue
            except Exception as e:
                self.logger.error(f"Error processing notification: {e}")
        
        self.logger.info("Notification processing loop stopped")
    
    async def _deliver_notification(self, notification: NotificationMessage) -> None:
        """Deliver a notification through all specified methods"""
        self.logger.info(f"Delivering notification: {notification.type.value} - {notification.title}")
        
        self._metrics["total_sent"] += 1
        self._metrics["deliveries_by_type"][notification.type.value] = \
            self._metrics["deliveries_by_type"].get(notification.type.value, 0) + 1
        
        successful_deliveries = 0
        
        for method in notification.delivery_methods:
            try:
                handler = self._delivery_handlers.get(method)
                if handler:
                    await handler(notification)
                    notification.delivery_status[method] = True
                    successful_deliveries += 1
                    
                    # Update metrics
                    self._metrics["deliveries_by_method"][method.value] = \
                        self._metrics["deliveries_by_method"].get(method.value, 0) + 1
                else:
                    self.logger.warning(f"No handler available for delivery method: {method.value}")
                    notification.delivery_status[method] = False
                    
            except Exception as e:
                self.logger.error(f"Failed to deliver notification via {method.value}: {e}")
                notification.delivery_status[method] = False
        
        # Update notification status
        notification.delivered_at = time.time()
        
        if successful_deliveries > 0:
            self._metrics["successful_deliveries"] += 1
            self.logger.debug(f"Notification delivered via {successful_deliveries}/{len(notification.delivery_methods)} methods")
        else:
            self._metrics["failed_deliveries"] += 1
            self.logger.error(f"Failed to deliver notification via any method")
    
    async def _deliver_via_log(self, notification: NotificationMessage) -> None:
        """Deliver notification via logging system"""
        log_level = {
            NotificationPriority.LOW: logging.DEBUG,
            NotificationPriority.NORMAL: logging.INFO,
            NotificationPriority.HIGH: logging.WARNING,
            NotificationPriority.CRITICAL: logging.ERROR
        }.get(notification.priority, logging.INFO)
        
        log_message = f"🔔 {notification.title}: {notification.message}"
        if notification.details:
            log_message += f" | Details: {notification.details}"
        
        self.logger.log(log_level, log_message)
    
    async def _deliver_via_tts(self, notification: NotificationMessage) -> None:
        """Deliver notification via TTS audio"""
        if not (self.tts_component and self.audio_component):
            raise RuntimeError("TTS or Audio component not available")
        
        try:
            # Create TTS-friendly message
            tts_message = self._create_tts_message(notification)
            
            # Generate temporary audio file
            temp_filename = f"notification_{notification.id}.wav"
            temp_path = Path("/tmp") / temp_filename  # TODO: Use proper temp directory from config
            
            # Generate TTS audio
            await self.tts_component.synthesize_to_file(tts_message, temp_path)
            
            # Play audio
            await self.audio_component.play_file(temp_path)
            
            self.logger.debug(f"TTS notification delivered: {notification.title}")
            
        except Exception as e:
            self.logger.error(f"TTS notification delivery failed: {e}")
            raise
        finally:
            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()
    
    def _create_tts_message(self, notification: NotificationMessage) -> str:
        """Create TTS-friendly version of notification message"""
        # Simplify message for speech
        if notification.type == NotificationType.ACTION_COMPLETION:
            if notification.details.get("success", True):
                return f"Action {notification.details.get('action_name', 'unknown')} completed successfully."
            else:
                return f"Action {notification.details.get('action_name', 'unknown')} failed."
        
        elif notification.type == NotificationType.ACTION_FAILURE:
            return f"Action {notification.details.get('action_name', 'unknown')} has failed."
        
        elif notification.type == NotificationType.CRITICAL_ALERT:
            return f"Critical alert: {notification.title}"
        
        else:
            return notification.message
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get notification delivery metrics"""
        return self._metrics.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get notification service status"""
        return {
            "running": self._running,
            "queue_size": self._notification_queue.qsize(),
            "available_methods": list(self._delivery_handlers.keys()),
            "metrics": self.get_metrics()
        }


# Global notification service instance
_notification_service: Optional[NotificationService] = None


async def initialize_notification_service(components: Dict[str, Any], config: dict = None) -> NotificationService:
    """Initialize the global notification service with configuration"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
        
        # Apply configuration if provided
        if config:
            if 'default_channel' in config:
                _notification_service._default_channel = config['default_channel']
            if 'tts_enabled' in config:
                _notification_service._tts_enabled = config['tts_enabled']
            if 'web_enabled' in config:
                _notification_service._web_enabled = config['web_enabled']
        
        await _notification_service.initialize(components)
    return _notification_service


async def get_notification_service() -> NotificationService:
    """Get the global notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service




async def shutdown_notification_service() -> None:
    """Shutdown the global notification service"""
    global _notification_service
    if _notification_service:
        await _notification_service.stop()
        _notification_service = None
