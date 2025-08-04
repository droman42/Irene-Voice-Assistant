"""Base intent handler class."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class IntentHandler(ABC):
    """Base class for all intent handlers."""
    
    def __init__(self):
        """Initialize the intent handler."""
        self.name = self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
    
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