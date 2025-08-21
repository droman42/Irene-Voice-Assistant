"""
NLU Provider Base Classes

Abstract base class for all NLU (Natural Language Understanding) implementations.
Following ABC inheritance pattern for type safety and runtime validation.
"""

from abc import abstractmethod
from typing import Dict, Any, List, Optional

from ..base import ProviderBase
from ...intents.models import Intent, ConversationContext
from ...core.donations import ParameterSpec


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
        
        # PHASE 1: Parameter specifications storage
        self.parameter_specs: Dict[str, List[ParameterSpec]] = {}  # intent_name -> parameter specs
    
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
    async def extract_parameters(self, text: str, intent_name: str, parameter_specs: List[ParameterSpec]) -> Dict[str, Any]:
        """Extract parameters using provider's NLP capabilities
        
        Args:
            text: Input text to extract parameters from
            intent_name: Name of the recognized intent
            parameter_specs: List of parameter specifications to extract
            
        Returns:
            Dictionary of extracted parameters
        """
        pass
    
    @abstractmethod
    def get_supported_intents(self) -> List[str]:
        """Return list of intents this provider can recognize
        
        Returns:
            List of intent names this provider supports
        """
        pass
    
    async def recognize_with_parameters(self, text: str, context: ConversationContext) -> Intent:
        """Recognize intent and extract parameters in one operation
        
        Args:
            text: Input text to analyze
            context: Conversation context for better understanding
            
        Returns:
            Intent object with recognized intent, entities, and extracted parameters
        """
        # Default implementation - providers can override for optimization
        intent = await self.recognize(text, context)
        
        # Handle case where recognition returns None (low confidence)
        if intent is None:
            return None
            
        if intent.name in self.parameter_specs:
            parameters = await self.extract_parameters(text, intent.name, self.parameter_specs[intent.name])
            intent.entities.update(parameters)
        
        return intent
    
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
    
    async def _initialize_from_donations(self, keyword_donations: List[Any]) -> None:
        """
        Initialize provider with JSON donation patterns (Phase 2 integration).
        
        This method should be implemented by providers that support donation-driven
        pattern loading. Providers that don't implement this method will use
        fallback patterns.
        
        Args:
            keyword_donations: List of KeywordDonation objects from JSON donations
        """
        # Default implementation - providers can override
        pass