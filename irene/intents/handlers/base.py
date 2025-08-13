"""Base intent handler class."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Coroutine

from ..models import Intent, IntentResult, ConversationContext
from ...core.metadata import EntryPointMetadata

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
        *args, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute an action using fire-and-forget pattern with context tracking.
        
        Args:
            action_func: Async function to execute
            action_name: Human-readable action name
            domain: Action domain for ambiguity resolution
            *args: Arguments to pass to action function
            **kwargs: Keyword arguments to pass to action function
            
        Returns:
            Action metadata for context tracking
        """
        try:
            # Create background task for fire-and-forget execution
            task = asyncio.create_task(action_func(*args, **kwargs))
            
            # Generate action metadata for context tracking
            action_metadata = {
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
            
            # Set up completion callback for context updates
            task.add_done_callback(
                lambda t: self._handle_action_completion(action_name, domain, t)
            )
            
            self.logger.info(f"Started fire-and-forget action: {action_name} (domain: {domain})")
            return action_metadata
            
        except Exception as e:
            self.logger.error(f"Failed to start action {action_name}: {e}")
            return {
                "recent_actions": [{
                    "handler": self.__class__.__name__,
                    "action": action_name,
                    "domain": domain,
                    "started_at": time.time(),
                    "completed_at": time.time(),
                    "status": "failed",
                    "error": str(e)
                }]
            }
    
    def _handle_action_completion(self, action_name: str, domain: str, task: asyncio.Task) -> None:
        """
        Handle action completion for context updates.
        
        Args:
            action_name: Name of the completed action
            domain: Action domain
            task: Completed asyncio task
        """
        try:
            if task.exception():
                self.logger.error(f"Action {action_name} failed: {task.exception()}")
                status = "failed"
                error = str(task.exception())
            else:
                self.logger.info(f"Action {action_name} completed successfully")
                status = "completed"
                error = None
                
            # TODO: Update conversation context with completion status
            # This would require context manager access or callback mechanism
            
        except Exception as e:
            self.logger.error(f"Error handling action completion for {action_name}: {e}")
    
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
    
    def parse_stop_command(self, intent: Intent) -> Optional[Dict[str, Any]]:
        """
        Parse stop command to extract target action/domain information.
        
        Args:
            intent: Stop command intent
            
        Returns:
            Dictionary with target information or None if not a stop command
        """
        text = intent.text.lower()
        
        # Basic stop command patterns
        stop_patterns = [
            "стоп", "останови", "прекрати", "выключи",
            "stop", "halt", "cancel", "turn off"
        ]
        
        if not any(pattern in text for pattern in stop_patterns):
            return None
        
        # Extract target domain/action hints
        domain_hints = {
            "music": ["музыка", "музыку", "песню", "трек", "music", "song", "track"],
            "lights": ["свет", "лампы", "освещение", "lights", "lamp", "lighting"],
            "smart_home": ["устройство", "девайс", "device", "smart"],
            "media": ["видео", "фильм", "медиа", "video", "movie", "media"],
            "timer": ["таймер", "будильник", "timer", "alarm"]
        }
        
        target_domains = []
        for domain, keywords in domain_hints.items():
            if any(keyword in text for keyword in keywords):
                target_domains.append(domain)
        
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