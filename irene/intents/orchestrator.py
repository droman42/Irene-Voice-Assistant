"""Intent orchestration and execution."""

import logging
import time
from typing import Dict, Any, Optional

from .models import Intent, IntentResult, ConversationContext
from .registry import IntentRegistry
from ..core.metrics import get_metrics_collector, MetricsCollector

logger = logging.getLogger(__name__)


class IntentOrchestrator:
    """Central intent coordinator that routes intents to appropriate handlers with donation-driven execution."""
    
    def __init__(self, registry: IntentRegistry):
        """
        Initialize the intent orchestrator.
        
        Args:
            registry: Intent registry containing available handlers
        """
        self.registry = registry
        self.middleware: list = []
        self.error_handlers: Dict[str, callable] = {}
        self._use_donation_routing = True  # Phase 6: Enable donation-driven routing
        self.metrics_collector = get_metrics_collector()  # Phase 2: Intent analytics integration
    
    def add_middleware(self, middleware_func: callable):
        """Add middleware function to process intents before execution."""
        self.middleware.append(middleware_func)
        logger.info(f"Added middleware: {middleware_func.__name__}")
    
    def add_error_handler(self, error_type: str, handler: callable):
        """Add error handler for specific error types."""
        self.error_handlers[error_type] = handler
        logger.info(f"Added error handler for: {error_type}")
    
    
    def enable_donation_routing(self, enabled: bool = True):
        """Enable or disable donation-driven routing."""
        self._use_donation_routing = enabled
        logger.info(f"Donation-driven routing {'enabled' if enabled else 'disabled'}")
    
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """
        Execute an intent - workflow compatibility method.
        
        This is a wrapper for execute_intent() to maintain compatibility with the workflow
        interface that expects an 'execute' method.
        
        Args:
            intent: The recognized intent to execute
            context: Conversation context for execution
            
        Returns:
            IntentResult containing the response and metadata
        """
        return await self.execute_intent(intent, context)
    
    async def execute_intent(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """
        Execute an intent by routing it to the appropriate handler with donation-driven execution.
        
        Args:
            intent: The recognized intent to execute
            context: Conversation context for execution
            
        Returns:
            IntentResult containing the response and metadata
        """
        try:
            # Apply middleware processing
            processed_intent = await self._apply_middleware(intent, context)
            
            # Find handler for the intent
            handler = self.registry.get_handler(processed_intent)
            if not handler:
                logger.warning(f"No handler found for intent: {processed_intent.name}")
                return self._create_error_result(
                    f"I don't know how to handle that request.",
                    "no_handler",
                    processed_intent
                )
            
            # Check if handler can handle this specific intent
            if not await handler.can_handle(processed_intent):
                logger.warning(f"Handler {handler.__class__.__name__} cannot handle intent: {processed_intent.name}")
                return self._create_error_result(
                    "I can't process that request right now.",
                    "handler_unavailable", 
                    processed_intent
                )
            
            # Intent already contains extracted parameters from recognize_with_parameters
            
            # Execute the intent using donation-driven routing if available
            logger.info(f"Executing intent '{processed_intent.name}' with handler {handler.__class__.__name__}")
            
            # Phase 2: Track intent execution start time
            execution_start_time = time.time()
            
            try:
                if (self._use_donation_routing and 
                    hasattr(handler, 'execute_with_donation_routing') and 
                    hasattr(handler, 'has_donation') and 
                    handler.has_donation()):
                    # Phase 6: Use donation-driven method routing
                    logger.debug(f"Using donation-driven execution for {processed_intent.name}")
                    result = await handler.execute_with_donation_routing(processed_intent, context)
                else:
                    # Fallback to standard execution
                    logger.debug(f"Using standard execution for {processed_intent.name}")
                    result = await handler.execute(processed_intent, context)
                
                # Phase 2: Record successful intent execution
                execution_time = time.time() - execution_start_time
                self.metrics_collector.record_intent_execution(
                    intent_name=processed_intent.name,
                    success=result.success,
                    execution_time=execution_time,
                    session_id=getattr(processed_intent, 'session_id', None)
                )
                
                # Update conversation context
                context.add_user_turn(processed_intent)
                context.add_assistant_turn(result)
                
                logger.info(f"Intent executed successfully: {processed_intent.name}")
                return result
                
            except Exception as exec_error:
                # Phase 2: Record failed intent execution
                execution_time = time.time() - execution_start_time
                self.metrics_collector.record_intent_execution(
                    intent_name=processed_intent.name,
                    success=False,
                    execution_time=execution_time,
                    error=str(exec_error),
                    session_id=getattr(processed_intent, 'session_id', None)
                )
                raise  # Re-raise the exception to be handled by outer try-catch
            
        except Exception as e:
            logger.error(f"Error executing intent '{intent.name}': {e}", exc_info=True)
            
            # Try error handlers
            error_type = type(e).__name__
            if error_type in self.error_handlers:
                try:
                    return await self.error_handlers[error_type](intent, context, e)
                except Exception as handler_error:
                    logger.error(f"Error handler failed: {handler_error}")
            
            # Phase 2: Record failed intent execution for general errors
            self.metrics_collector.record_intent_execution(
                intent_name=intent.name,
                success=False,
                execution_time=0.0,
                error=str(e),
                session_id=intent.session_id
            )
            
            # Generic error response
            return self._create_error_result(
                "I encountered an error processing your request. Please try again.",
                "execution_error",
                intent,
                str(e)
            )
    
    async def _apply_middleware(self, intent: Intent, context: ConversationContext) -> Intent:
        """Apply middleware functions to process the intent."""
        processed_intent = intent
        
        for middleware in self.middleware:
            try:
                processed_intent = await middleware(processed_intent, context)
            except Exception as e:
                logger.error(f"Middleware error in {middleware.__name__}: {e}")
                # Continue with unprocessed intent if middleware fails
        
        return processed_intent
    
    def _create_error_result(self, 
                           message: str, 
                           error_type: str, 
                           intent: Intent,
                           error_details: Optional[str] = None) -> IntentResult:
        """Create a standardized error result."""
        return IntentResult(
            text=message,
            should_speak=True,
            success=False,
            error=error_type,
            metadata={
                "error_type": error_type,
                "original_intent": intent.name,
                "error_details": error_details
            },
            confidence=0.0
        )
    
    async def get_capabilities(self) -> Dict[str, Any]:
        """Get orchestrator capabilities and handler information."""
        handlers = await self.registry.get_all_handlers()
        
        capabilities = {
            "handlers": {},
            "middleware_count": len(self.middleware),
            "error_handlers": list(self.error_handlers.keys()),
            "supported_domains": set(),
            "supported_actions": set(),
            "donation_routing_enabled": self._use_donation_routing,
            "parameter_extraction_integrated": True  # PHASE 5: Parameter extraction now integrated into NLU providers
        }
        
        for pattern, handler in handlers.items():
            handler_info = {
                "class": handler.__class__.__name__,
                "pattern": pattern,
                "available": await handler.is_available() if hasattr(handler, 'is_available') else True,
                "has_donation": hasattr(handler, 'has_donation') and handler.has_donation(),
                "supports_donation_routing": hasattr(handler, 'execute_with_donation_routing')
            }
            
            # Extract domain information if available
            if hasattr(handler, 'supported_domains'):
                domains = handler.supported_domains()
                capabilities["supported_domains"].update(domains)
                handler_info["domains"] = list(domains)
            
            if hasattr(handler, 'supported_actions'):
                actions = handler.supported_actions()
                capabilities["supported_actions"].update(actions)
                handler_info["actions"] = list(actions)
            
            capabilities["handlers"][pattern] = handler_info
        
        # Convert sets to lists for JSON serialization
        capabilities["supported_domains"] = list(capabilities["supported_domains"])
        capabilities["supported_actions"] = list(capabilities["supported_actions"])
        
        return capabilities
    
    async def validate_intent(self, intent: Intent) -> bool:
        """Validate if an intent can be executed."""
        handler = self.registry.get_handler(intent)
        if not handler:
            return False
        
        try:
            return await handler.can_handle(intent)
        except Exception:
            return False 