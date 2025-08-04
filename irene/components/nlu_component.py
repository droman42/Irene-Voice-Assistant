"""
NLU Component - Natural Language Understanding component

This component provides intent recognition and entity extraction capabilities
through multiple NLU providers with web API support.
"""

import logging
from typing import Dict, Any, List, Optional

from .base import Component
from ..core.interfaces.webapi import WebAPIPlugin
from ..intents.models import Intent, ConversationContext

logger = logging.getLogger(__name__)


class NLUComponent(Component, WebAPIPlugin):
    """Natural Language Understanding component"""
    
    def __init__(self):
        super().__init__()
        self.confidence_threshold = 0.7
        self.fallback_intent = "conversation.general"
    
    @property
    def name(self) -> str:
        return "nlu"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Natural Language Understanding component for intent recognition and entity extraction"
        
    @property
    def dependencies(self) -> List[str]:
        return []  # No hard dependencies
        
    @property
    def optional_dependencies(self) -> List[str]:
        return ["spacy", "spacy-transformers", "openai"]
        
    @property
    def enabled_by_default(self) -> bool:
        return True
        
    @property  
    def category(self) -> str:
        return "nlu"
        
    @property
    def platforms(self) -> List[str]:
        return []  # All platforms
    
    def get_dependencies(self) -> List[str]:
        """Get list of dependencies for this component."""
        return self.dependencies  # Use @property for consistency
    
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        """
        Recognize intent from text using configured NLU providers.
        
        Args:
            text: Input text to analyze
            context: Conversation context for better understanding
            
        Returns:
            Intent object with recognized intent and entities
        """
        # Coordinate multiple NLU providers
        provider = self.get_current_provider()
        if not provider:
            logger.warning("No NLU provider available, creating fallback intent")
            return self._create_fallback_intent(text, context.session_id)
        
        try:
            intent = await provider.recognize(text, context)
            
            # Check confidence threshold
            if intent.confidence < self.confidence_threshold:
                logger.info(f"Low confidence ({intent.confidence:.2f}) for intent '{intent.name}', "
                           f"falling back to conversation")
                return self._create_fallback_intent(text, context.session_id)
            
            return intent
            
        except Exception as e:
            logger.error(f"Error in NLU provider: {e}")
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
    
    def configure(self, config: Dict[str, Any]):
        """Configure the NLU component."""
        if "confidence_threshold" in config:
            self.confidence_threshold = config["confidence_threshold"]
        
        if "fallback_intent" in config:
            self.fallback_intent = config["fallback_intent"]
        
        logger.info(f"Configured NLU component: threshold={self.confidence_threshold}, "
                   f"fallback={self.fallback_intent}")
    
    # WebAPIPlugin interface - following universal plugin pattern
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with NLU endpoints"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter, HTTPException  # type: ignore
            from pydantic import BaseModel  # type: ignore
            
            router = APIRouter()
            
            # Request/Response models
            class NLURequest(BaseModel):
                text: str
                context: Optional[Dict[str, Any]] = None
                provider: Optional[str] = None
                
            class IntentResponse(BaseModel):
                name: str
                entities: Dict[str, Any]
                confidence: float
                provider: str
                domain: Optional[str] = None
                action: Optional[str] = None
                
            @router.post("/recognize", response_model=IntentResponse)
            async def recognize_intent(request: NLURequest):
                """Recognize intent from text input"""
                # Create context from request
                context = ConversationContext(
                    session_id=request.context.get("session_id", "default") if request.context else "default",
                    history=request.context.get("history", []) if request.context else []
                )
                
                # Use specific provider if requested
                if request.provider and request.provider in self.providers:
                    intent = await self.providers[request.provider].recognize(request.text, context)
                    provider_name = request.provider
                else:
                    intent = await self.recognize(request.text, context)
                    provider_name = self.default_provider or "fallback"
                
                return IntentResponse(
                    name=intent.name,
                    entities=intent.entities,
                    confidence=intent.confidence,
                    provider=provider_name,
                    domain=intent.domain,
                    action=intent.action
                )
            
            @router.get("/providers")
            async def list_nlu_providers():
                """Discovery endpoint for NLU provider capabilities"""
                result = {}
                for name, provider in self.providers.items():
                    result[name] = {
                        "available": await provider.is_available() if hasattr(provider, 'is_available') else True,
                        "languages": getattr(provider, 'get_supported_languages', lambda: [])(),
                        "domains": getattr(provider, 'get_supported_domains', lambda: [])(),
                        "parameters": getattr(provider, 'get_parameter_schema', lambda: {})(),
                        "capabilities": getattr(provider, 'get_capabilities', lambda: {})()
                    }
                return {"providers": result, "default": self.default_provider}
            
            @router.post("/configure")
            async def configure_nlu(provider: str, set_as_default: bool = False):
                """Configure NLU settings"""
                if provider in self.providers:
                    if set_as_default:
                        self.default_provider = provider
                    return {"success": True, "default_provider": self.default_provider}
                else:
                    raise HTTPException(404, f"Provider '{provider}' not available")
            
            @router.get("/config")
            async def get_nlu_config():
                """Get current NLU configuration"""
                return {
                    "confidence_threshold": self.confidence_threshold,
                    "fallback_intent": self.fallback_intent,
                    "default_provider": self.default_provider,
                    "available_providers": list(self.providers.keys())
                }
            
            return router
            
        except ImportError:
            logger.warning("FastAPI not available for NLU web API")
            return None
    
    def is_api_available(self) -> bool:
        """Check if web API is available."""
        try:
            import fastapi
            import pydantic
            return True
        except ImportError:
            return False
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for NLU API endpoints"""
        return "/nlu"
    
    def get_api_tags(self) -> List[str]:
        """Get OpenAPI tags for NLU endpoints"""
        return ["nlu", "intent_recognition"] 