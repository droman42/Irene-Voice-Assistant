"""
NLU Provider Base Classes

Abstract base class for all NLU (Natural Language Understanding) implementations.
Following ABC inheritance pattern for type safety and runtime validation.
"""

from abc import abstractmethod
from typing import Dict, Any, List, Optional

from ..base import ProviderBase
from ...intents.models import Intent, ConversationContext


class NLUProvider(ProviderBase):
    """
    Abstract base class for NLU implementations.
    
    All NLU providers must implement intent recognition functionality
    following the Component-Provider pattern.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with provider-specific configuration
        
        Args:
            config: Provider-specific configuration dictionary
        """
        # Call ProviderBase.__init__ to get status tracking, logging, etc.
        super().__init__(config)
    
    @abstractmethod
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        """Recognize intent from text
        
        Args:
            text: Input text to analyze for intent recognition
            context: Conversation context for better understanding
            
        Returns:
            Intent object with recognized intent, entities, and confidence
        """
        pass
    
    @abstractmethod
    async def extract_entities(self, text: str, intent_name: str) -> Dict[str, Any]:
        """Extract entities for a given intent (optional but recommended)
        
        Args:
            text: Input text to extract entities from
            intent_name: Name of the recognized intent
            
        Returns:
            Dictionary of extracted entities
        """
        pass
    
    @abstractmethod
    def get_supported_intents(self) -> List[str]:
        """Return list of intents this provider can recognize
        
        Returns:
            List of intent names this provider supports
        """
        pass
    
    def get_confidence_threshold(self) -> float:
        """Get minimum confidence threshold for this provider (optional override)
        
        Returns:
            Minimum confidence threshold (default: 0.7)
        """
        return self.config.get('confidence_threshold', 0.7)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities (optional override)
        
        Returns:
            Dictionary with capability information
        """
        return {
            "supported_intents": self.get_supported_intents(),
            "confidence_threshold": self.get_confidence_threshold(),
            "entity_extraction": True,  # Override if no entity extraction
            "context_aware": True,  # Override if context not used
            "real_time": True,  # Override if not real-time capable
        } 