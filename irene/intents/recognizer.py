"""Intent recognition (NLU) component."""

import logging
from typing import Dict, Any, Optional

from .models import Intent, ConversationContext
from ..providers.base import Provider

logger = logging.getLogger(__name__)


class IntentRecognizer:
    """Natural Language Understanding component that coordinates multiple NLU providers."""
    
    def __init__(self):
        """Initialize the intent recognizer."""
        self.providers: Dict[str, Provider] = {}
        self.default_provider: Optional[str] = None
        self.confidence_threshold: float = 0.7
        self.fallback_intent: str = "conversation.general"
    
    def add_provider(self, name: str, provider: Provider):
        """Add an NLU provider."""
        self.providers[name] = provider
        if self.default_provider is None:
            self.default_provider = name
        logger.info(f"Added NLU provider: {name}")
    
    def set_default_provider(self, name: str):
        """Set the default NLU provider."""
        if name in self.providers:
            self.default_provider = name
            logger.info(f"Set default NLU provider: {name}")
        else:
            raise ValueError(f"Provider '{name}' not found")
    
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        """
        Recognize intent from text using the configured NLU pipeline.
        
        Args:
            text: Input text to analyze
            context: Conversation context for better understanding
            
        Returns:
            Intent object with recognized intent and entities
        """
        if not self.providers:
            logger.warning("No NLU providers available, using fallback")
            return self._create_fallback_intent(text, context.session_id)
        
        provider_name = self.default_provider
        if not provider_name or provider_name not in self.providers:
            provider_name = next(iter(self.providers.keys()))
        
        provider = self.providers[provider_name]
        
        try:
            # Use primary NLU provider
            intent = await provider.recognize(text, context)
            
            # Check confidence threshold
            if intent.confidence < self.confidence_threshold:
                logger.info(f"Low confidence ({intent.confidence:.2f}) for intent '{intent.name}', "
                           f"falling back to conversation")
                return self._create_fallback_intent(text, context.session_id)
            
            logger.info(f"Recognized intent: {intent.name} (confidence: {intent.confidence:.2f})")
            return intent
            
        except Exception as e:
            logger.error(f"Error in NLU provider '{provider_name}': {e}")
            return self._create_fallback_intent(text, context.session_id)
    
    def _create_fallback_intent(self, text: str, session_id: str) -> Intent:
        """Create a fallback conversation intent when NLU fails or has low confidence."""
        return Intent(
            name=self.fallback_intent,
            entities={"original_text": text},
            confidence=1.0,  # High confidence for conversation fallback
            raw_text=text,
            session_id=session_id,
            domain="conversation",
            action="general"
        )
    
    async def get_available_providers(self) -> Dict[str, Dict[str, Any]]:
        """Get information about available NLU providers."""
        result = {}
        for name, provider in self.providers.items():
            try:
                result[name] = {
                    "available": await provider.is_available(),
                    "capabilities": getattr(provider, 'get_capabilities', lambda: {})(),
                    "is_default": name == self.default_provider
                }
            except Exception as e:
                result[name] = {
                    "available": False,
                    "error": str(e),
                    "is_default": name == self.default_provider
                }
        return result
    
    def configure(self, config: Dict[str, Any]):
        """Configure the intent recognizer."""
        if "confidence_threshold" in config:
            self.confidence_threshold = config["confidence_threshold"]
        
        if "fallback_intent" in config:
            self.fallback_intent = config["fallback_intent"]
        
        if "default_provider" in config and config["default_provider"] in self.providers:
            self.default_provider = config["default_provider"]
        
        logger.info(f"Configured intent recognizer: threshold={self.confidence_threshold}, "
                   f"fallback={self.fallback_intent}, default_provider={self.default_provider}") 