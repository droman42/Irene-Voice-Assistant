"""Intent orchestration and execution."""

import logging
import time
from typing import Dict, Any, Optional, List

from .models import Intent, IntentResult, ConversationContext
from .registry import IntentRegistry
from ..core.metrics import get_metrics_collector, MetricsCollector
from ..core.trace_context import TraceContext

logger = logging.getLogger(__name__)


class IntentOrchestrator:
    """Central intent coordinator that routes intents to appropriate handlers with donation-driven execution."""
    
    def __init__(self, registry: IntentRegistry, context_manager=None, domain_priorities: Dict[str, int] = None):
        """
        Initialize the intent orchestrator.
        
        Args:
            registry: Intent registry containing available handlers
            context_manager: Context manager for contextual command disambiguation (Phase 1 TODO16)
            domain_priorities: Domain priorities for contextual command resolution (Phase 1 TODO16)
        """
        self.registry = registry
        self.middleware: list = []
        self.error_handlers: Dict[str, callable] = {}
        self._use_donation_routing = True  # Phase 6: Enable donation-driven routing
        self.metrics_collector = get_metrics_collector()  # Phase 2: Intent analytics integration
        
        # Phase 1 TODO16: Contextual command disambiguation support
        self.context_manager = context_manager
        self.domain_priorities = domain_priorities or {}
        
        # Cache for capabilities to prevent excessive provider availability checks
        self._capabilities_cache = None
        self._capabilities_cache_time = 0
        self._capabilities_cache_duration = 30  # 30 seconds cache for capabilities
    
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
    
    async def execute(self, intent: Intent, context: ConversationContext, 
                     trace_context: Optional[TraceContext] = None) -> IntentResult:
        """
        Execute intent with optional handler resolution and disambiguation tracing.
        
        This is a wrapper for execute_intent() to maintain compatibility with the workflow
        interface that expects an 'execute' method.
        
        Args:
            intent: The recognized intent to execute
            context: Conversation context for execution
            trace_context: Optional trace context for detailed execution tracking
            
        Returns:
            IntentResult containing the response and metadata
        """
        # Fast path - existing logic when no tracing
        if not trace_context or not trace_context.enabled:
            # Original implementation unchanged
            return await self.execute_intent(intent, context)
        
        # Trace path - detailed handler resolution tracking
        stage_start = time.time()
        execution_metadata = {
            "input_intent": {
                "name": intent.name,
                "domain": intent.domain,
                "action": intent.action,
                "confidence": intent.confidence,
                "entities": intent.entities
            },
            "disambiguation_process": None,
            "handler_resolution": {},
            "handler_execution": {},
            "component_name": self.__class__.__name__
        }
        
        # Execute with detailed tracking
        try:
            # Store trace_context for handler access
            self._current_trace_context = trace_context
            
            result = await self.execute_intent(intent, context)
            execution_metadata["handler_execution"]["success"] = result.success
            execution_metadata["handler_execution"]["text"] = result.text
            execution_metadata["handler_execution"]["confidence"] = result.confidence
            
        except Exception as e:
            execution_metadata["handler_execution"]["success"] = False
            execution_metadata["handler_execution"]["error"] = str(e)
            raise
        finally:
            # Clear the stored trace_context
            self._current_trace_context = None
        
        trace_context.record_stage(
            stage_name="intent_execution",
            input_data=execution_metadata["input_intent"],
            output_data={
                "success": result.success,
                "text": result.text,
                "confidence": result.confidence,
                "should_speak": result.should_speak,
                "action_metadata": result.action_metadata
            } if 'result' in locals() else None,
            metadata=execution_metadata,
            processing_time_ms=(time.time() - stage_start) * 1000
        )
        
        return result
    
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
            
            # Phase 2 TODO16: Central disambiguation - handlers never see ambiguous commands
            if processed_intent.domain == "contextual":
                # STEP 1: Check if this is a contextual intent from NLU cascade
                # STEP 2: Analyze active fire-and-forget actions for disambiguation
                active_actions = context.active_actions
                if not active_actions:
                    return self._create_error_result(
                        "No active actions to target with that command.",
                        "no_active_actions",
                        intent
                    )
                
                # STEP 3: Central disambiguation using existing sophisticated logic
                # Phase 3 TODO16: Enhanced disambiguation with capability checking
                available_domains = self.registry.get_handlers_for_contextual_command(processed_intent.action)
                
                # Filter active actions to only those with handlers that support this command
                filtered_active_actions = {}
                for action_name, action_info in active_actions.items():
                    action_domain = action_info.get('domain', 'unknown')
                    if action_domain in available_domains:
                        filtered_active_actions[action_name] = action_info
                
                if not filtered_active_actions:
                    return self._create_error_result(
                        f"No active actions support the '{processed_intent.action}' command.",
                        "no_capable_handlers",
                        intent,
                        f"Available handlers for '{processed_intent.action}': {', '.join(available_domains) if available_domains else 'none'}"
                    )
                
                # Determine if confirmation is needed based on ambiguity
                require_confirmation = len(filtered_active_actions) > 1 and self._should_require_confirmation(
                    filtered_active_actions, processed_intent.action
                )
                
                resolution = self.context_manager.resolve_contextual_command_ambiguity(
                    session_id=context.session_id,
                    command_type=processed_intent.action,  # "stop", "pause", "resume", etc.
                    target_domains=None,  # No explicit domain targeting for pure contextual commands
                    domain_priorities=self.domain_priorities,
                    require_confirmation=require_confirmation
                )
                
                # Phase 3 TODO16: Handle confirmation requests
                if resolution.get("resolution") == "requires_confirmation":
                    return await self._handle_disambiguation_confirmation(resolution, intent, context)
                
                # Check if resolution was successful
                if resolution["resolution"] in ["no_session", "no_active_actions", "no_actions"]:
                    logger.debug(f"Contextual intent resolution failed: {resolution['resolution']}")
                    return self._create_error_result(
                        "No active actions to target with that command.",
                        "contextual_resolution_failed",
                        intent
                    )
                
                # Extract target domain from resolution
                target_domain = resolution.get("target_domain")
                if not target_domain:
                    logger.warning(f"No target domain in contextual resolution: {resolution}")
                    return self._create_error_result(
                        "Could not determine which action to target.",
                        "ambiguous_target",
                        intent
                    )
                
                # STEP 4: Transform to resolved domain-specific intent
                resolved_intent = Intent(
                    name=f"{target_domain}.{processed_intent.action}",
                    action=processed_intent.action,
                    domain=target_domain,
                    text=processed_intent.text,
                    entities=processed_intent.entities.copy(),
                    confidence=processed_intent.confidence,
                    raw_text=processed_intent.raw_text
                )
                
                # Add resolution metadata to entities
                resolved_intent.entities["_contextual_resolution"] = {
                    "original_intent": processed_intent.name,
                    "resolution_method": resolution["resolution"],
                    "target_domain": target_domain,
                    "command_type": processed_intent.action
                }
                
                logger.info(f"Resolved contextual intent '{processed_intent.name}' to '{resolved_intent.name}' "
                           f"using {resolution['resolution']} method")
                
                processed_intent = resolved_intent
            
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
                # Set trace_context on handler for LLM component calls
                handler._trace_context = getattr(self, '_current_trace_context', None)
                
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
                
                # Clear trace_context from handler after execution
                handler._trace_context = None
                
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
        """Get orchestrator capabilities and handler information (with caching)."""
        # Check cache first
        current_time = time.time()
        if (self._capabilities_cache is not None and 
            current_time - self._capabilities_cache_time < self._capabilities_cache_duration):
            logger.debug("Intent orchestrator capabilities cached")
            return self._capabilities_cache
        
        logger.debug("Intent orchestrator: Building capabilities (cache miss)")
        handlers = await self.registry.get_all_handlers()
        
        capabilities = {
            "handlers": {},
            "middleware_count": len(self.middleware),
            "error_handlers": list(self.error_handlers.keys()),
            "supported_domains": set(),
            "supported_actions": set(),
            "donation_routing_enabled": self._use_donation_routing,
            "parameter_extraction_integrated": True,  # PHASE 5: Parameter extraction now integrated into NLU providers
            # Phase 3 TODO16: Contextual command capabilities
            "contextual_capabilities": self.registry.get_all_contextual_capabilities(),
            "contextual_command_summary": self.registry.get_capability_summary()
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
        
        # Cache the result
        self._capabilities_cache = capabilities
        self._capabilities_cache_time = current_time
        
        return capabilities
    
    # Phase 3 TODO16: Enhanced user experience methods
    
    def _should_require_confirmation(self, active_actions: Dict[str, Any], command_type: str) -> bool:
        """
        Determine if user confirmation should be required for ambiguous contextual commands.
        
        Args:
            active_actions: Dictionary of active actions
            command_type: Type of contextual command
            
        Returns:
            True if confirmation should be required
        """
        # Require confirmation if multiple domains have similar priority scores
        if len(active_actions) <= 1:
            return False
        
        # Check if domains have very different priorities (clear winner)
        domains = set(action_info.get('domain', 'unknown') for action_info in active_actions.values())
        if len(domains) <= 1:
            return False  # All actions in same domain
        
        # Check priority differences
        if self.domain_priorities:
            priorities = [self.domain_priorities.get(domain, 0) for domain in domains]
            max_priority = max(priorities)
            min_priority = min(priorities)
            
            # If priority difference is significant (>20 points), don't require confirmation
            if max_priority - min_priority > 20:
                return False
        
        # For destructive commands, always require confirmation when ambiguous
        destructive_commands = ['stop', 'cancel', 'delete', 'remove']
        if command_type in destructive_commands:
            return True
        
        # For non-destructive commands, require confirmation if more than 2 domains
        return len(domains) > 2
    
    async def _handle_disambiguation_confirmation(
        self, 
        resolution: Dict[str, Any], 
        original_intent: Intent, 
        context: ConversationContext
    ) -> IntentResult:
        """
        Handle disambiguation confirmation for ambiguous contextual commands.
        
        Args:
            resolution: Disambiguation resolution requiring confirmation
            original_intent: Original contextual intent
            context: Conversation context
            
        Returns:
            IntentResult with confirmation request or error
        """
        ambiguous_domains = resolution.get("ambiguous_domains", [])
        command_type = resolution.get("command_type", "unknown")
        
        if not ambiguous_domains:
            return self._create_error_result(
                "Unable to determine which action to target.",
                "disambiguation_failed",
                original_intent
            )
        
        # Create user-friendly confirmation message
        domain_descriptions = self._get_domain_descriptions(ambiguous_domains, context)
        
        if len(ambiguous_domains) == 2:
            confirmation_message = (
                f"I found multiple active actions for '{command_type}'. "
                f"Did you mean to {command_type} {domain_descriptions[0]} or {domain_descriptions[1]}? "
                f"Please specify which one."
            )
        else:
            domain_list = ", ".join(domain_descriptions[:-1]) + f", or {domain_descriptions[-1]}"
            confirmation_message = (
                f"I found multiple active actions for '{command_type}': {domain_list}. "
                f"Please specify which one you'd like to {command_type}."
            )
        
        # Store disambiguation context for follow-up
        self._store_disambiguation_context(context.session_id, resolution, original_intent)
        
        return IntentResult(
            text=confirmation_message,
            should_speak=True,
            success=True,
            metadata={
                "requires_disambiguation": True,
                "disambiguation_type": "contextual_command",
                "command_type": command_type,
                "ambiguous_domains": ambiguous_domains,
                "domain_descriptions": domain_descriptions,
                "original_intent": original_intent.name,
                "confidence_scores": resolution.get("domain_scores", {}),
                "session_id": context.session_id
            },
            confidence=0.5  # Medium confidence due to ambiguity
        )
    
    def _get_domain_descriptions(self, domains: List[str], context: ConversationContext) -> List[str]:
        """
        Get user-friendly descriptions for domains based on active actions.
        
        Args:
            domains: List of domain names
            context: Conversation context
            
        Returns:
            List of user-friendly domain descriptions
        """
        descriptions = []
        active_actions = getattr(context, 'active_actions', {})
        
        for domain in domains:
            # Find actions in this domain
            domain_actions = [
                action_name for action_name, action_info in active_actions.items()
                if action_info.get('domain') == domain
            ]
            
            if domain_actions:
                # Use the most descriptive action name or domain name
                if domain == 'audio':
                    descriptions.append("audio playback")
                elif domain == 'timer':
                    descriptions.append("timer")
                elif domain == 'voice_synthesis':
                    descriptions.append("voice synthesis")
                else:
                    descriptions.append(domain)
            else:
                descriptions.append(domain)
        
        return descriptions
    
    def _store_disambiguation_context(
        self, 
        session_id: str, 
        resolution: Dict[str, Any], 
        original_intent: Intent
    ) -> None:
        """
        Store disambiguation context for follow-up resolution.
        
        Args:
            session_id: Session identifier
            resolution: Disambiguation resolution
            original_intent: Original contextual intent
        """
        # Store in context manager for follow-up processing
        if hasattr(self.context_manager, 'store_disambiguation_context'):
            self.context_manager.store_disambiguation_context(
                session_id, 
                {
                    "type": "contextual_command",
                    "resolution": resolution,
                    "original_intent": original_intent,
                    "timestamp": time.time()
                }
            )
    
    def invalidate_capabilities_cache(self):
        """Invalidate the capabilities cache to force a fresh check"""
        self._capabilities_cache = None
        self._capabilities_cache_time = 0
        logger.debug("Intent orchestrator capabilities cache invalidated")
    
    async def validate_intent(self, intent: Intent) -> bool:
        """Validate if an intent can be executed."""
        handler = self.registry.get_handler(intent)
        if not handler:
            return False
        
        try:
            return await handler.can_handle(intent)
        except Exception:
            return False
    