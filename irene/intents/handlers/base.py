"""Base intent handler class."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Coroutine

from ..models import Intent, IntentResult, ConversationContext
from ...core.metadata import EntryPointMetadata
from ...core.notifications import get_notification_service, NotificationService
from ...core.metrics import get_metrics_collector, MetricsCollector
from ...core.debug_tools import get_action_debugger, ActionDebugger, InspectionLevel

logger = logging.getLogger(__name__)


class IntentHandler(EntryPointMetadata, ABC):
    """
    Enhanced base class for intent handlers with JSON donation support.
    
    Features:
    - JSON donation integration for pattern-free operation
    - Donation-driven method routing
    - Parameter extraction from donation specifications
    """
    
    def __init__(self):
        """Initialize the intent handler."""
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
        self.donation: Optional[Any] = None  # Will be HandlerDonation
        self._donation_initialized = False
        self.asset_loader: Optional[Any] = None  # Will be IntentAssetLoader
        self._asset_loader_initialized = False
        self.context_manager: Optional[Any] = None  # Context manager for fire-and-forget actions
        self._timeout_tasks: Dict[str, asyncio.Task] = {}  # Track timeout monitoring tasks
        self._notification_service: Optional[NotificationService] = None  # Phase 3.1: Notification service
        self._metrics_collector: Optional[MetricsCollector] = None  # Phase 3.2: Metrics collector
        self._action_debugger: Optional[ActionDebugger] = None  # Phase 3.4: Action debugger
    
    def set_context_manager(self, context_manager: Any) -> None:
        """Set the context manager for fire-and-forget action tracking."""
        self.context_manager = context_manager
    
    async def set_notification_service(self, notification_service: Optional[NotificationService] = None) -> None:
        """Set the notification service for user notifications (Phase 3.1)"""
        if notification_service is None:
            self._notification_service = await get_notification_service()
        else:
            self._notification_service = notification_service
    
    def set_metrics_collector(self, metrics_collector: Optional[MetricsCollector] = None) -> None:
        """Set the metrics collector for performance tracking (Phase 3.2)"""
        if metrics_collector is None:
            self._metrics_collector = get_metrics_collector()
        else:
            self._metrics_collector = metrics_collector
    
    # Phase 2: Intent analytics helper methods
    def record_intent_recognition(self, intent_name: str, confidence: float, processing_time: float, session_id: Optional[str] = None) -> None:
        """Record intent recognition metrics through unified metrics collector"""
        if self._metrics_collector:
            self._metrics_collector.record_intent_recognition(intent_name, confidence, processing_time, session_id)
    
    def record_intent_execution(self, intent_name: str, success: bool, execution_time: float, 
                               error: Optional[str] = None, session_id: Optional[str] = None) -> None:
        """Record intent execution metrics through unified metrics collector"""
        if self._metrics_collector:
            self._metrics_collector.record_intent_execution(intent_name, success, execution_time, error, session_id)
    
    def record_session_start(self, session_id: str) -> None:
        """Record conversation session start through unified metrics collector"""
        if self._metrics_collector:
            self._metrics_collector.record_session_start(session_id)
    
    def record_session_end(self, session_id: str, user_satisfaction: Optional[float] = None) -> None:
        """Record conversation session end through unified metrics collector"""
        if self._metrics_collector:
            self._metrics_collector.record_session_end(session_id, user_satisfaction)
    
    def set_action_debugger(self, action_debugger: Optional[ActionDebugger] = None) -> None:
        """Set the action debugger for development tools (Phase 3.4)"""
        if action_debugger is None:
            self._action_debugger = get_action_debugger()
        else:
            self._action_debugger = action_debugger
    
    async def execute_fire_and_forget_with_context(
        self, 
        action_func: Callable[..., Coroutine[Any, Any, Any]], 
        action_name: str,
        domain: str,
        context: ConversationContext,
        timeout: Optional[float] = None,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        *args, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a fire-and-forget action with automatic context manager and session_id injection.
        
        Args:
            action_func: Async function to execute
            action_name: Human-readable action name
            domain: Action domain for ambiguity resolution
            context: Conversation context (provides session_id)
            timeout: Optional timeout in seconds (default: 300 seconds)
            max_retries: Maximum number of retry attempts for transient failures (default: 0)
            retry_delay: Delay between retry attempts in seconds (default: 1.0)
            *args: Arguments to pass to action function
            **kwargs: Keyword arguments to pass to action function
            
        Returns:
            Action metadata for context tracking
        """
        return await self.execute_fire_and_forget_action(
            action_func=action_func,
            action_name=action_name,
            domain=domain,
            context_manager=self.context_manager,
            session_id=context.session_id,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            *args,
            **kwargs
        )
    
    @abstractmethod
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """
        Execute the intent and return a result.
        
        Args:
            intent: The intent to execute
            context: Current conversation context
            
        Returns:
            IntentResult with response and metadata
        """
        pass
    
    @abstractmethod
    async def can_handle(self, intent: Intent) -> bool:
        """
        Check if this handler can process the given intent.
        
        Args:
            intent: Intent to check
            
        Returns:
            True if this handler can process the intent
        """
        pass
    
    async def is_available(self) -> bool:
        """
        Check if this handler is currently available.
        
        Returns:
            True if the handler is available and functioning
        """
        return True
    
    def set_donation(self, donation: Any) -> None:
        """
        Set the JSON donation for this handler.
        
        Args:
            donation: HandlerDonation object with method specifications
        """
        self.donation = donation
        self._donation_initialized = True
        self.logger.info(f"Handler {self.name} initialized with donation containing {len(donation.method_donations)} methods")
    
    def get_donation(self) -> Optional[Any]:
        """
        Get the JSON donation for this handler.
        
        Returns:
            HandlerDonation object or None if not set
        """
        return self.donation
    
    def has_donation(self) -> bool:
        """
        Check if this handler has a JSON donation set.
        
        Returns:
            True if donation is set and initialized
        """
        return self._donation_initialized and self.donation is not None
    
    def set_asset_loader(self, asset_loader: Any) -> None:
        """
        Set the IntentAssetLoader for this handler.
        
        Args:
            asset_loader: IntentAssetLoader object for accessing external assets
        """
        self.asset_loader = asset_loader
        self._asset_loader_initialized = True
        self.logger.info(f"Handler {self.name} initialized with asset loader")
    
    def get_asset_loader(self) -> Optional[Any]:
        """
        Get the IntentAssetLoader for this handler.
        
        Returns:
            IntentAssetLoader object or None if not set
        """
        return self.asset_loader
    
    def has_asset_loader(self) -> bool:
        """
        Check if this handler has an asset loader set.
        
        Returns:
            True if asset loader is set and initialized
        """
        return self._asset_loader_initialized and self.asset_loader is not None
    
    def find_method_for_intent(self, intent: Intent) -> Optional[str]:
        """
        Find method name for intent using JSON donation.
        
        Args:
            intent: Intent to find method for
            
        Returns:
            Method name or None if not found
        """
        if not self.has_donation():
            return None
        
        expected_suffix = intent.name.split('.', 1)[1] if '.' in intent.name else intent.name
        
        for method_donation in self.donation.method_donations:
            if method_donation.intent_suffix == expected_suffix:
                return method_donation.method_name
        
        return None
    
    async def execute_with_donation_routing(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """
        Execute intent using donation-driven method routing.
        
        Args:
            intent: The intent to execute
            context: Current conversation context
            
        Returns:
            IntentResult with response and metadata
        """
        if not self.has_donation():
            return self._create_error_result(
                "Handler not properly initialized with donation",
                "donation_missing"
            )
        
        # Find matching method donation
        method_name = self.find_method_for_intent(intent)
        if not method_name:
            return self._create_error_result(
                f"No method found for intent {intent.name}",
                "method_not_found"
            )
        
        # Call the method
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            try:
                return await method(intent, context)
            except Exception as e:
                self.logger.error(f"Method {method_name} execution failed: {e}")
                return self._create_error_result(
                    f"Method execution failed: {str(e)}",
                    "method_execution_error"
                )
        else:
            return self._create_error_result(
                f"Method {method_name} not implemented in handler",
                "method_not_implemented"
            )
    
    def get_supported_domains(self) -> List[str]:
        """
        Get list of domains this handler supports.
        
        Returns:
            List of supported domain names
        """
        return []
    
    def get_supported_actions(self) -> List[str]:
        """
        Get list of actions this handler supports.
        
        Returns:
            List of supported action names
        """
        return []
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get handler capabilities and metadata.
        
        Returns:
            Dictionary describing handler capabilities
        """
        return {
            "name": self.name,
            "domains": self.get_supported_domains(),
            "actions": self.get_supported_actions(),
            "available": True
        }
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get general information about this handler.
        
        Returns:
            Dictionary with handler information
        """
        return {
            "class": self.__class__.__name__,
            "module": self.__class__.__module__,
            "description": self.__doc__ or "No description available"
        }
    
    def _create_success_result(self, 
                             text: str, 
                             should_speak: bool = True,
                             metadata: Optional[Dict[str, Any]] = None,
                             actions: Optional[List[str]] = None) -> IntentResult:
        """
        Helper method to create a successful intent result.
        
        Args:
            text: Response text
            should_speak: Whether response should be spoken
            metadata: Additional metadata
            actions: Additional actions to perform
            
        Returns:
            IntentResult indicating success
        """
        return IntentResult(
            text=text,
            should_speak=should_speak,
            metadata=metadata or {},
            actions=actions or [],
            success=True,
            confidence=1.0
        )
    
    def _create_error_result(self, 
                           text: str, 
                           error: str,
                           metadata: Optional[Dict[str, Any]] = None) -> IntentResult:
        """
        Helper method to create an error intent result.
        
        Args:
            text: Error message to display
            error: Error type or description
            metadata: Additional metadata
            
        Returns:
            IntentResult indicating failure
        """
        return IntentResult(
            text=text,
            should_speak=True,
            metadata=metadata or {},
            success=False,
            error=error,
            confidence=0.0
        )
    
    async def validate_entities(self, intent: Intent, required_entities: List[str]) -> bool:
        """
        Validate that required entities are present in the intent.
        
        Args:
            intent: Intent to validate
            required_entities: List of required entity names
            
        Returns:
            True if all required entities are present
        """
        for entity in required_entities:
            if entity not in intent.entities or intent.entities[entity] is None:
                self.logger.warning(f"Missing required entity '{entity}' in intent {intent.name}")
                return False
        return True
    
    def extract_entity(self, intent: Intent, entity_name: str, default: Any = None) -> Any:
        """
        Extract an entity value from the intent.
        
        Args:
            intent: Intent to extract from
            entity_name: Name of the entity to extract
            default: Default value if entity is not found
            
        Returns:
            Entity value or default
        """
        return intent.entities.get(entity_name, default)
    
    async def preprocess_intent(self, intent: Intent, context: ConversationContext) -> Intent:
        """
        Preprocess the intent before execution (can be overridden).
        
        Args:
            intent: Original intent
            context: Conversation context
            
        Returns:
            Processed intent (may be modified)
        """
        return intent
    
    async def postprocess_result(self, result: IntentResult, intent: Intent, context: ConversationContext) -> IntentResult:
        """
        Postprocess the result after execution (can be overridden).
        
        Args:
            result: Original result
            intent: The intent that was executed
            context: Conversation context
            
        Returns:
            Processed result (may be modified)
        """
        return result
    
    # Action execution helper methods for Phase 5
    async def execute_fire_and_forget_action(
        self, 
        action_func: Callable[..., Coroutine[Any, Any, Any]], 
        action_name: str,
        domain: str,
        context_manager: Optional[Any] = None,
        session_id: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        *args, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute an action using fire-and-forget pattern with context tracking.
        
        Args:
            action_func: Async function to execute
            action_name: Human-readable action name
            domain: Action domain for ambiguity resolution
            context_manager: Context manager for completion callbacks
            session_id: Session ID for context updates
            timeout: Optional timeout in seconds (default: 300 seconds)
            max_retries: Maximum number of retry attempts for transient failures (default: 0)
            retry_delay: Delay between retry attempts in seconds (default: 1.0)
            *args: Arguments to pass to action function
            **kwargs: Keyword arguments to pass to action function
            
        Returns:
            Action metadata for context tracking
        """
        try:
            # Set default timeout if not provided
            if timeout is None:
                timeout = 300.0  # 5 minutes default
            
            # Create background task for fire-and-forget execution with retry logic
            if max_retries > 0:
                task = asyncio.create_task(self._execute_with_retry(
                    action_func, action_name, domain, max_retries, retry_delay, *args, **kwargs
                ))
            else:
                task = asyncio.create_task(action_func(*args, **kwargs))
            
            # Phase 3.2: Record action start in metrics
            if self._metrics_collector:
                self._metrics_collector.record_action_start(
                    domain=domain,
                    action_name=action_name,
                    handler=self.__class__.__name__,
                    session_id=session_id
                )
            
            # Generate action metadata for context tracking
            action_metadata = {
                "active_actions": {
                    action_name: {
                        "handler": self.__class__.__name__,
                        "action": action_name,
                        "domain": domain,
                        "started_at": time.time(),
                        "task_id": id(task),
                        "status": "running",
                        "timeout": timeout,
                        "timeout_at": time.time() + timeout,
                        "max_retries": max_retries,
                        "retry_delay": retry_delay,
                        "retry_count": 0
                    }
                }
            }
            
            # Use provided context manager or fall back to instance context manager
            effective_context_manager = context_manager or self.context_manager
            
            # Set up completion callback for context updates
            task.add_done_callback(
                lambda t: self._handle_action_completion(action_name, domain, t, effective_context_manager, session_id)
            )
            
            # Set up timeout monitoring
            if timeout > 0:
                timeout_task = asyncio.create_task(self._monitor_action_timeout(
                    task, action_name, domain, timeout, effective_context_manager, session_id
                ))
                # Track timeout task for cleanup
                timeout_key = f"{domain}:{action_name}"
                self._timeout_tasks[timeout_key] = timeout_task
                # Store timeout task reference in metadata for potential cancellation
                action_metadata["active_actions"][action_name]["timeout_task_id"] = id(timeout_task)
                action_metadata["active_actions"][action_name]["timeout_key"] = timeout_key
            
            # Validate metadata structure before returning
            if not self._validate_action_metadata(action_metadata):
                self.logger.error(f"Generated invalid action metadata for {action_name}")
                # Return a minimal valid structure as fallback
                return {
                    "active_actions": {
                        action_name: {
                            "handler": self.__class__.__name__,
                            "action": action_name,
                            "domain": domain,
                            "started_at": time.time(),
                            "task_id": id(task),
                            "status": "running"
                        }
                    }
                }
            
            self.logger.info(f"Started fire-and-forget action: {action_name} (domain: {domain})")
            return action_metadata
            
        except Exception as e:
            self.logger.error(f"Failed to start action {action_name}: {e}")
            # Use consistent metadata structure - failed actions still go in active_actions
            # but with failed status and immediate completion time
            error_metadata = {
                "active_actions": {
                    action_name: {
                        "handler": self.__class__.__name__,
                        "action": action_name,
                        "domain": domain,
                        "started_at": time.time(),
                        "completed_at": time.time(),
                        "task_id": None,  # No task created due to failure
                        "status": "failed",
                        "error": str(e),
                        "failed_at_startup": True  # Flag to indicate startup failure
                    }
                }
            }
            
            # Validate error metadata structure
            if not self._validate_action_metadata(error_metadata):
                self.logger.error(f"Generated invalid error metadata for {action_name}")
            
            return error_metadata
    
    def _handle_action_completion(self, action_name: str, domain: str, task: asyncio.Task, 
                                 context_manager: Optional[Any] = None, session_id: Optional[str] = None) -> None:
        """
        Handle action completion for context updates.
        
        Args:
            action_name: Name of the completed action
            domain: Action domain
            task: Completed asyncio task
            context_manager: Context manager for updating conversation context
            session_id: Session ID for context lookup
        """
        try:
            if task.exception():
                self.logger.error(f"Action {action_name} failed: {task.exception()}")
                success = False
                error = str(task.exception())
            else:
                self.logger.info(f"Action {action_name} completed successfully")
                success = True
                error = None
            
            # Update conversation context with completion status if context manager is available
            if context_manager and session_id:
                try:
                    # Create a task to handle the async context update
                    asyncio.create_task(self._update_context_on_completion(
                        context_manager, session_id, domain, success, error, action_name
                    ))
                except Exception as ctx_error:
                    self.logger.error(f"Failed to update context for completed action {action_name}: {ctx_error}")
            else:
                self.logger.debug(f"No context manager or session_id provided for action {action_name} completion")
                
        except Exception as e:
            self.logger.error(f"Error handling action completion for {action_name}: {e}")
    
    async def _update_context_on_completion(self, context_manager: Any, session_id: str, 
                                          domain: str, success: bool, error: Optional[str], action_name: str) -> None:
        """
        Update conversation context when an action completes.
        
        Args:
            context_manager: Context manager instance
            session_id: Session ID for context lookup
            domain: Action domain
            success: Whether action completed successfully
            error: Error message if action failed
        """
        try:
            # Get the conversation context
            conversation_context = await context_manager.get_or_create_context(session_id)
            
            # Remove the completed action and add to recent actions
            if conversation_context.remove_completed_action(domain, success, error):
                self.logger.debug(f"Updated context for completed action in domain: {domain}")
                
                # Cancel and clean up associated timeout task
                timeout_key = f"{domain}:{action_name}"
                if timeout_key in self._timeout_tasks:
                    timeout_task = self._timeout_tasks[timeout_key]
                    if not timeout_task.done():
                        timeout_task.cancel()
                    del self._timeout_tasks[timeout_key]
                
                # Phase 3.2: Record action completion in metrics
                if self._metrics_collector:
                    try:
                        # Get additional metrics data
                        action_info = conversation_context.active_actions.get(domain, {})
                        retry_count = action_info.get('retry_count', 0)
                        timeout_occurred = action_info.get('status') == 'timeout'
                        error_type = conversation_context._classify_error(error) if error else None
                        
                        self._metrics_collector.record_action_completion(
                            domain=domain,
                            success=success,
                            error=error,
                            error_type=error_type,
                            retry_count=retry_count,
                            timeout_occurred=timeout_occurred
                        )
                    except Exception as metrics_error:
                        self.logger.error(f"Failed to record action metrics: {metrics_error}")
                
                # Phase 3.1: Send user notifications for action completion/failure
                if self._notification_service:
                    try:
                        # Calculate action duration
                        action_info = conversation_context.active_actions.get(domain, {})
                        started_at = action_info.get('started_at', time.time())
                        duration = time.time() - started_at
                        
                        if success:
                            # Send completion notification for long-running actions
                            await self._notification_service.send_action_completion_notification(
                                session_id=session_id,
                                domain=domain,
                                action_name=action_name,
                                duration=duration,
                                success=True
                            )
                        else:
                            # Send failure notification
                            is_critical = conversation_context._is_critical_failure(domain, error)
                            await self._notification_service.send_action_failure_notification(
                                session_id=session_id,
                                domain=domain,
                                action_name=action_name,
                                error=error or "Unknown error",
                                is_critical=is_critical
                            )
                    except Exception as notif_error:
                        self.logger.error(f"Failed to send user notification: {notif_error}")
                
                # Notify about critical failures (legacy method)
                if not success and error:
                    await self._notify_critical_failure(action_name, domain, error, conversation_context)
            else:
                self.logger.warning(f"No active action found in domain {domain} to complete")
                
        except Exception as e:
            self.logger.error(f"Failed to update conversation context on action completion: {e}")
    
    async def _notify_critical_failure(self, action_name: str, domain: str, error: str, 
                                     context: ConversationContext) -> None:
        """
        Notify about critical action failures that may require user attention.
        
        Args:
            action_name: Name of the failed action
            domain: Action domain
            error: Error message
            context: Conversation context for failure tracking
        """
        try:
            # Check if this is a critical failure
            if context._is_critical_failure(domain, error):
                self.logger.error(f"CRITICAL FAILURE in {domain}: {action_name} - {error}")
                
                # Log detailed error information for monitoring
                error_summary = context.get_error_summary()
                self.logger.warning(f"Error summary for session {context.session_id}: {error_summary}")
                
                # TODO: In Phase 3, this could trigger user notifications
                # For now, we ensure critical failures are prominently logged
                
        except Exception as e:
            self.logger.error(f"Error in critical failure notification: {e}")
    
    async def _monitor_action_timeout(self, task: asyncio.Task, action_name: str, domain: str, 
                                    timeout: float, context_manager: Optional[Any] = None, 
                                    session_id: Optional[str] = None) -> None:
        """
        Monitor action timeout and handle timeout scenarios.
        
        Args:
            task: The action task to monitor
            action_name: Name of the action
            domain: Action domain
            timeout: Timeout duration in seconds
            context_manager: Context manager for updates
            session_id: Session ID for context lookup
        """
        try:
            # Wait for either task completion or timeout
            await asyncio.sleep(timeout)
            
            # If we reach here, the task has timed out
            if not task.done():
                self.logger.warning(f"Action {action_name} in domain {domain} timed out after {timeout} seconds")
                
                # Cancel the timed-out task
                task.cancel()
                
                # Update context with timeout status
                if context_manager and session_id:
                    try:
                        conversation_context = await context_manager.get_or_create_context(session_id)
                        
                        # Update action status to timeout
                        conversation_context.update_action_status(domain, "timeout", f"Action timed out after {timeout} seconds")
                        
                        # Remove the timed-out action and mark as failed
                        conversation_context.remove_completed_action(
                            domain, 
                            success=False, 
                            error=f"Action timed out after {timeout} seconds"
                        )
                        
                        # Notify about timeout (considered a critical failure)
                        await self._notify_critical_failure(
                            action_name, domain, f"Action timed out after {timeout} seconds", conversation_context
                        )
                        
                    except Exception as ctx_error:
                        self.logger.error(f"Failed to update context for timed-out action {action_name}: {ctx_error}")
                
        except asyncio.CancelledError:
            # Timeout monitoring was cancelled (task completed normally)
            pass
        except Exception as e:
            self.logger.error(f"Error in timeout monitoring for action {action_name}: {e}")
        finally:
            # Clean up timeout task tracking
            timeout_key = f"{domain}:{action_name}"
            if timeout_key in self._timeout_tasks:
                del self._timeout_tasks[timeout_key]
    
    async def _execute_with_retry(self, action_func: Callable[..., Coroutine[Any, Any, Any]], 
                                action_name: str, domain: str, max_retries: int, retry_delay: float,
                                *args, **kwargs) -> Any:
        """
        Execute an action with retry logic for transient failures.
        
        Args:
            action_func: The async function to execute
            action_name: Name of the action for logging
            domain: Action domain
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            *args: Arguments to pass to action function
            **kwargs: Keyword arguments to pass to action function
            
        Returns:
            Result of the action function
            
        Raises:
            Exception: The last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                if attempt > 0:
                    self.logger.info(f"Retrying action {action_name} (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(retry_delay)
                
                result = await action_func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"Action {action_name} succeeded on retry attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if this is a transient failure that should be retried
                if attempt < max_retries and self._is_transient_failure(e):
                    self.logger.warning(f"Transient failure in action {action_name} (attempt {attempt + 1}): {e}")
                    continue
                else:
                    # Either max retries reached or non-transient failure
                    if attempt >= max_retries:
                        self.logger.error(f"Action {action_name} failed after {max_retries + 1} attempts: {e}")
                    else:
                        self.logger.error(f"Non-transient failure in action {action_name}: {e}")
                    break
        
        # All retries exhausted, raise the last exception
        raise last_exception
    
    def _is_transient_failure(self, error: Exception) -> bool:
        """
        Determine if an error represents a transient failure that should be retried.
        
        Args:
            error: The exception to analyze
            
        Returns:
            True if the error is likely transient and should be retried
        """
        error_str = str(error).lower()
        
        # Common transient failure patterns
        transient_patterns = [
            'timeout',
            'connection reset',
            'connection refused',
            'temporary failure',
            'service unavailable',
            'too many requests',
            'rate limit',
            'network is unreachable',
            'connection timed out'
        ]
        
        # Check for transient error patterns
        for pattern in transient_patterns:
            if pattern in error_str:
                return True
        
        # Check for specific exception types that are typically transient
        transient_exceptions = [
            'TimeoutError',
            'ConnectionError',
            'ConnectionResetError',
            'ConnectionRefusedError'
        ]
        
        exception_name = error.__class__.__name__
        return exception_name in transient_exceptions
    
    async def cancel_action(self, domain: str, context: ConversationContext, 
                          reason: str = "User requested cancellation") -> bool:
        """
        Cancel an active fire-and-forget action.
        
        Args:
            domain: Domain of the action to cancel
            context: Conversation context
            reason: Reason for cancellation
            
        Returns:
            True if action was cancelled, False if no active action found
        """
        try:
            # Mark action as cancelled in context
            if context.cancel_action(domain, reason):
                self.logger.info(f"Action in domain {domain} marked for cancellation: {reason}")
                
                # Remove the cancelled action and add to recent actions
                context.remove_completed_action(domain, success=False, error=f"Cancelled: {reason}")
                
                return True
            else:
                self.logger.warning(f"No active action found in domain {domain} to cancel")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cancelling action in domain {domain}: {e}")
            return False
    
    def get_active_actions(self, context: ConversationContext) -> List[Dict[str, Any]]:
        """
        Get list of active fire-and-forget actions.
        
        Args:
            context: Conversation context
            
        Returns:
            List of active action information
        """
        try:
            return [
                {
                    'domain': domain,
                    'action': action_info.get('action', 'unknown'),
                    'handler': action_info.get('handler', 'unknown'),
                    'started_at': action_info.get('started_at', 0),
                    'status': action_info.get('status', 'unknown'),
                    'timeout_at': action_info.get('timeout_at'),
                    'max_retries': action_info.get('max_retries', 0),
                    'retry_count': action_info.get('retry_count', 0)
                }
                for domain, action_info in context.active_actions.items()
            ]
        except Exception as e:
            self.logger.error(f"Error getting active actions: {e}")
            return []
    
    async def cleanup_timeout_tasks(self) -> None:
        """Clean up all timeout monitoring tasks during shutdown"""
        if self._timeout_tasks:
            self.logger.info(f"Cleaning up {len(self._timeout_tasks)} timeout monitoring tasks")
            
            # Cancel all timeout tasks
            for timeout_key, task in self._timeout_tasks.items():
                if not task.done():
                    task.cancel()
            
            # Wait for all tasks to complete cancellation
            if self._timeout_tasks:
                await asyncio.gather(*self._timeout_tasks.values(), return_exceptions=True)
            
            # Clear the tracking dictionary
            self._timeout_tasks.clear()
            self.logger.debug("All timeout monitoring tasks cleaned up")
    
    def _validate_action_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Validate action metadata structure for consistency.
        
        Args:
            metadata: Action metadata to validate
            
        Returns:
            True if metadata is valid, False otherwise
        """
        try:
            if not isinstance(metadata, dict):
                self.logger.error("Action metadata must be a dictionary")
                return False
            
            if "active_actions" not in metadata:
                self.logger.error("Action metadata must contain 'active_actions' key")
                return False
            
            active_actions = metadata["active_actions"]
            if not isinstance(active_actions, dict):
                self.logger.error("'active_actions' must be a dictionary")
                return False
            
            # Validate each action entry
            for action_name, action_info in active_actions.items():
                if not isinstance(action_info, dict):
                    self.logger.error(f"Action info for '{action_name}' must be a dictionary")
                    return False
                
                required_fields = ["handler", "action", "domain", "started_at", "status"]
                for field in required_fields:
                    if field not in action_info:
                        self.logger.error(f"Action '{action_name}' missing required field: {field}")
                        return False
                
                # Validate status values
                valid_statuses = ["running", "completed", "failed", "timeout", "cancelled"]
                if action_info["status"] not in valid_statuses:
                    self.logger.error(f"Action '{action_name}' has invalid status: {action_info['status']}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating action metadata: {e}")
            return False
    
    def create_action_result(
        self, 
        response_text: str, 
        action_name: str,
        domain: str,
        should_speak: bool = True,
        action_metadata: Optional[Dict[str, Any]] = None
    ) -> IntentResult:
        """
        Create an IntentResult with action metadata for fire-and-forget actions.
        
        Args:
            response_text: Immediate response text
            action_name: Human-readable action name
            domain: Action domain for ambiguity resolution
            should_speak: Whether response should be spoken
            action_metadata: Pre-generated action metadata (from execute_fire_and_forget_action)
            
        Returns:
            IntentResult with action tracking metadata
        """
        return IntentResult(
            text=response_text,
            should_speak=should_speak,
            metadata={},
            action_metadata=action_metadata or {},
            success=True,
            confidence=1.0
        )
    
    def _get_stop_patterns(self, language: str = "ru") -> List[str]:
        """Get stop command patterns from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"BaseIntentHandler: Asset loader not initialized. "
                f"Cannot access stop patterns for language '{language}'. "
                f"This is a fatal configuration error - command patterns must be externalized."
            )
        
        # Get patterns from asset loader
        commands_data = self.asset_loader.get_localization("commands", language)
        if commands_data is None:
            raise RuntimeError(
                f"BaseIntentHandler: Required command patterns for language '{language}' "
                f"not found in assets/localization/commands/{language}.yaml. "
                f"This is a fatal error - all command patterns must be externalized."
            )
        
        stop_patterns = commands_data.get("stop_patterns", [])
        if not stop_patterns:
            raise RuntimeError(
                f"BaseIntentHandler: Empty stop_patterns in assets/localization/commands/{language}.yaml. "
                f"At least one stop pattern must be defined for language '{language}'."
            )
        
        return stop_patterns
    
    def _get_domain_hints(self, language: str = "ru") -> Dict[str, List[str]]:
        """Get domain hints from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"BaseIntentHandler: Asset loader not initialized. "
                f"Cannot access domain hints for language '{language}'. "
                f"This is a fatal configuration error - domain patterns must be externalized."
            )
        
        # Get domain hints from asset loader
        domains_data = self.asset_loader.get_localization("domains", language)
        if domains_data is None:
            raise RuntimeError(
                f"BaseIntentHandler: Required domain hints for language '{language}' "
                f"not found in assets/localization/domains/{language}.yaml. "
                f"This is a fatal error - all domain patterns must be externalized."
            )
        
        domain_hints = domains_data.get("domain_hints", {})
        if not domain_hints:
            raise RuntimeError(
                f"BaseIntentHandler: Empty domain_hints in assets/localization/domains/{language}.yaml. "
                f"At least one domain hint must be defined for language '{language}'."
            )
        
        return domain_hints
    
    def parse_stop_command(self, intent: Intent) -> Optional[Dict[str, Any]]:
        """
        Parse stop command to extract target action/domain information.
        
        Args:
            intent: Stop command intent
            
        Returns:
            Dictionary with target information or None if not a stop command
        """
        text = intent.text.lower()
        
        # Get stop patterns from localization data (both languages)
        ru_stop_patterns = self._get_stop_patterns("ru")
        en_stop_patterns = self._get_stop_patterns("en")
        all_stop_patterns = ru_stop_patterns + en_stop_patterns
        
        if not any(pattern in text for pattern in all_stop_patterns):
            return None
        
        # Get domain hints from localization data (both languages)
        ru_domain_hints = self._get_domain_hints("ru")
        en_domain_hints = self._get_domain_hints("en")
        
        target_domains = []
        
        # Check Russian domain hints
        for domain, keywords in ru_domain_hints.items():
            if any(keyword in text for keyword in keywords):
                target_domains.append(domain)
        
        # Check English domain hints
        for domain, keywords in en_domain_hints.items():
            if any(keyword in text for keyword in keywords):
                target_domains.append(domain)
        
        # Remove duplicates
        target_domains = list(set(target_domains))
        
        return {
            "is_stop_command": True,
            "target_domains": target_domains,
            "original_text": intent.text
        }
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Intent handlers process intents - minimal dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Intent handlers have no system dependencies - pure logic"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Intent handlers support all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    # Phase 3.5: Enhanced Action Management Interface
    async def get_action_status(self, domain: str, context: ConversationContext) -> Dict[str, Any]:
        """Get detailed status of an action in a specific domain"""
        try:
            if domain in context.active_actions:
                action_info = context.active_actions[domain]
                current_time = time.time()
                
                status = {
                    "domain": domain,
                    "action_name": action_info.get('action', 'unknown'),
                    "handler": action_info.get('handler', 'unknown'),
                    "status": action_info.get('status', 'unknown'),
                    "started_at": action_info.get('started_at'),
                    "running_time": current_time - action_info.get('started_at', current_time),
                    "timeout_at": action_info.get('timeout_at'),
                    "timeout_remaining": max(0, action_info.get('timeout_at', current_time) - current_time) if action_info.get('timeout_at') else None,
                    "max_retries": action_info.get('max_retries', 0),
                    "retry_count": action_info.get('retry_count', 0),
                    "task_id": action_info.get('task_id'),
                    "cancellable": action_info.get('status') in ['running', 'pending'],
                    "is_active": True
                }
                
                return status
            
            # Check recent actions
            for action in reversed(context.recent_actions):
                if action.get('domain') == domain:
                    return {
                        "domain": domain,
                        "action_name": action.get('action', 'unknown'),
                        "handler": action.get('handler', 'unknown'),
                        "status": "completed" if action.get('success', True) else "failed",
                        "started_at": action.get('started_at'),
                        "completed_at": action.get('completed_at'),
                        "duration": action.get('completed_at', 0) - action.get('started_at', 0),
                        "success": action.get('success', True),
                        "error": action.get('error'),
                        "is_active": False
                    }
            
            return {
                "domain": domain,
                "error": "No action found in domain",
                "is_active": False
            }
            
        except Exception as e:
            self.logger.error(f"Error getting action status for domain {domain}: {e}")
            return {
                "domain": domain,
                "error": str(e),
                "is_active": False
            }
    
    async def list_all_actions(self, context: ConversationContext, 
                             include_history: bool = True,
                             history_limit: int = 10) -> Dict[str, Any]:
        """List all actions (active and recent history)"""
        try:
            result = {
                "active_actions": self.get_active_actions(context),
                "summary": {
                    "active_count": len(context.active_actions),
                    "recent_count": len(context.recent_actions),
                    "failed_count": len(context.failed_actions)
                }
            }
            
            if include_history:
                # Recent completed actions
                recent_actions = []
                for action in reversed(context.recent_actions[-history_limit:]):
                    recent_actions.append({
                        "domain": action.get('domain'),
                        "action_name": action.get('action', 'unknown'),
                        "handler": action.get('handler', 'unknown'),
                        "started_at": action.get('started_at'),
                        "completed_at": action.get('completed_at'),
                        "duration": action.get('completed_at', 0) - action.get('started_at', 0),
                        "success": action.get('success', True),
                        "error": action.get('error')
                    })
                
                # Recent failed actions
                failed_actions = []
                for action in reversed(context.failed_actions[-history_limit:]):
                    failed_actions.append({
                        "domain": action.get('domain'),
                        "action_name": action.get('action', 'unknown'),
                        "handler": action.get('handler', 'unknown'),
                        "started_at": action.get('started_at'),
                        "completed_at": action.get('completed_at'),
                        "duration": action.get('completed_at', 0) - action.get('started_at', 0),
                        "error": action.get('error'),
                        "error_type": action.get('failure_type'),
                        "is_critical": action.get('is_critical', False),
                        "retry_count": action.get('retry_count', 0)
                    })
                
                result["recent_actions"] = recent_actions
                result["failed_actions"] = failed_actions
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error listing all actions: {e}")
            return {
                "error": str(e),
                "active_actions": [],
                "summary": {"active_count": 0, "recent_count": 0, "failed_count": 0}
            }
    
    async def cancel_all_actions(self, context: ConversationContext, 
                               reason: str = "Bulk cancellation requested") -> Dict[str, Any]:
        """Cancel all active actions in the context"""
        try:
            active_domains = list(context.active_actions.keys())
            
            if not active_domains:
                return {
                    "success": True,
                    "message": "No active actions to cancel",
                    "cancelled_count": 0,
                    "cancelled_actions": []
                }
            
            cancelled_actions = []
            failed_cancellations = []
            
            for domain in active_domains:
                try:
                    # Mark action as cancelled in context
                    if context.cancel_action(domain, reason):
                        action_info = context.active_actions.get(domain, {})
                        action_name = action_info.get('action', 'unknown')
                        
                        self.logger.info(f"Action {action_name} in domain {domain} marked for cancellation: {reason}")
                        
                        # Record metrics if available
                        if self._metrics_collector:
                            self._metrics_collector.record_action_completion(
                                domain=domain,
                                success=False,
                                error=f"Cancelled: {reason}",
                                error_type="cancelled"
                            )
                        
                        # Remove the cancelled action and add to recent actions
                        context.remove_completed_action(domain, success=False, error=f"Cancelled: {reason}")
                        
                        cancelled_actions.append({
                            "domain": domain,
                            "action_name": action_name,
                            "reason": reason,
                            "cancelled_at": time.time()
                        })
                    else:
                        failed_cancellations.append({
                            "domain": domain,
                            "error": "Failed to mark action for cancellation"
                        })
                        
                except Exception as e:
                    failed_cancellations.append({
                        "domain": domain,
                        "error": str(e)
                    })
            
            return {
                "success": len(failed_cancellations) == 0,
                "cancelled_count": len(cancelled_actions),
                "failed_count": len(failed_cancellations),
                "cancelled_actions": cancelled_actions,
                "failed_cancellations": failed_cancellations,
                "reason": reason
            }
            
        except Exception as e:
            self.logger.error(f"Error cancelling all actions: {e}")
            return {
                "success": False,
                "error": str(e),
                "cancelled_count": 0
            }
    
    async def inspect_action(self, domain: str, context: ConversationContext,
                           level: InspectionLevel = InspectionLevel.BASIC) -> Dict[str, Any]:
        """Inspect an action using the debugger (Phase 3.4 integration)"""
        try:
            if not self._action_debugger:
                return {
                    "error": "Action debugger not available",
                    "domain": domain
                }
            
            inspection_result = await self._action_debugger.inspect_active_action(
                session_id=context.session_id,
                domain=domain,
                level=level
            )
            
            # Convert inspection result to dictionary
            return {
                "session_id": inspection_result.session_id,
                "domain": inspection_result.domain,
                "action_name": inspection_result.action_name,
                "inspection_level": inspection_result.inspection_level.value,
                "timestamp": inspection_result.timestamp,
                "status": inspection_result.status,
                "handler": inspection_result.handler,
                "started_at": inspection_result.started_at,
                "duration": inspection_result.duration,
                "task_info": inspection_result.task_info,
                "retry_info": inspection_result.retry_info,
                "timeout_info": inspection_result.timeout_info,
                "context_snapshot": inspection_result.context_snapshot,
                "system_state": inspection_result.system_state,
                "error_details": inspection_result.error_details
            }
            
        except Exception as e:
            self.logger.error(f"Error inspecting action {domain}: {e}")
            return {
                "error": str(e),
                "domain": domain
            }
    
    def get_action_management_capabilities(self) -> Dict[str, Any]:
        """Get available action management capabilities"""
        return {
            "list_actions": True,
            "cancel_actions": True,
            "inspect_actions": self._action_debugger is not None,
            "action_status": True,
            "bulk_operations": True,
            "metrics_integration": self._metrics_collector is not None,
            "notifications_integration": self._notification_service is not None,
            "debugging_tools": self._action_debugger is not None
        } 