"""
NLU Component - Natural Language Understanding component

This component provides intent recognition and entity extraction capabilities
through multiple NLU providers with web API support.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Type

from pydantic import BaseModel
from .base import Component
from ..core.interfaces.webapi import WebAPIPlugin
from ..intents.models import Intent, ConversationContext
from ..utils.loader import dynamic_loader
from ..providers.nlu.base import NLUProvider
from ..core.entity_resolver import ContextualEntityResolver

logger = logging.getLogger(__name__)


class ContextAwareNLUProcessor:
    """
    Context-aware NLU processor that enhances intent recognition with client 
    identification, device context, and entity resolution capabilities.
    """
    
    def __init__(self, nlu_component: 'NLUComponent'):
        self.nlu_component = nlu_component
        self.logger = logging.getLogger(f"{__name__}.ContextAwareNLUProcessor")
        
        # Entity resolver for context-based entity resolution
        self.entity_resolver = ContextualEntityResolver()
    
    async def process_with_context(self, text: str, context: ConversationContext) -> Intent:
        """
        Enhanced NLU processing with context-aware entity resolution and 
        intent disambiguation using client identification and device capabilities.
        
        Args:
            text: Input text to analyze
            context: Enhanced ConversationContext with client and device info
            
        Returns:
            Intent with context-enhanced entities and disambiguation
        """
        # Phase 1: Standard NLU recognition
        intent = await self.nlu_component.recognize(text, context)
        
        # Phase 2: Context-based entity resolution
        resolved_entities = await self.entity_resolver.resolve_entities(intent, context)
        
        # Phase 3: Context-aware entity enhancement
        enhanced_intent = await self._enhance_with_context(intent, context, resolved_entities)
        
        return enhanced_intent
    
    async def _enhance_with_context(self, intent: Intent, context: ConversationContext, 
                                   resolved_entities: Dict[str, Any]) -> Intent:
        """
        Enhance intent with context-aware entity resolution and disambiguation.
        
        This method implements the context-aware processing described in the 
        architecture document, using client identification and device capabilities.
        """
        # Start with resolved entities (includes original entities plus resolved ones)
        enhanced_entities = resolved_entities.copy()
        
        # 1. Client Context Enhancement
        if context.client_id:
            enhanced_entities["client_id"] = context.client_id
            
            room_name = context.get_room_name()
            if room_name:
                enhanced_entities["room_name"] = room_name
                self.logger.debug(f"Added room context: {room_name}")
        
        # 2. Device Entity Resolution
        enhanced_entities = await self._resolve_device_entities(enhanced_entities, context)
        
        # 3. Intent Disambiguation Based on Available Devices
        disambiguated_intent = await self._disambiguate_with_device_context(intent, context)
        
        # 4. User Preference Context
        if context.language and context.language != "ru":
            enhanced_entities["language_preference"] = context.language
        
        if context.timezone:
            enhanced_entities["timezone"] = context.timezone
        
        # 5. Conversation History Context
        recent_intents = context.get_recent_intents(limit=2)
        if recent_intents:
            enhanced_entities["recent_intents"] = recent_intents
            self.logger.debug(f"Added conversation context: {recent_intents}")
        
        # Create enhanced intent
        enhanced_intent = Intent(
            name=disambiguated_intent.name,
            entities=enhanced_entities,
            confidence=intent.confidence,
            raw_text=intent.raw_text,
            timestamp=intent.timestamp,
            domain=disambiguated_intent.domain,
            action=disambiguated_intent.action,
            session_id=intent.session_id
        )
        
        self.logger.info(f"Context-enhanced intent: {enhanced_intent.name} with {len(enhanced_entities)} entities")
        return enhanced_intent
    
    async def _resolve_device_entities(self, entities: Dict[str, Any], context: ConversationContext) -> Dict[str, Any]:
        """
        Resolve device references in entities using client context and fuzzy matching.
        
        This implements the device resolution described in the architecture document.
        """
        enhanced_entities = entities.copy()
        
        # Look for device-related entities that need resolution
        device_keywords = ["device", "light", "speaker", "tv", "television", "lamp", "switch"]
        
        for entity_key, entity_value in entities.items():
            if isinstance(entity_value, str):
                # Check if this entity might be a device reference
                entity_lower = entity_value.lower()
                
                # Check if it contains device keywords or looks like a device name
                is_device_reference = any(keyword in entity_lower for keyword in device_keywords)
                
                if is_device_reference:
                    # Try to resolve to actual device
                    resolved_device = context.get_device_by_name(entity_value)
                    if resolved_device:
                        enhanced_entities[f"{entity_key}_resolved"] = resolved_device
                        enhanced_entities[f"{entity_key}_device_id"] = resolved_device.get("id")
                        enhanced_entities[f"{entity_key}_device_type"] = resolved_device.get("type")
                        
                        self.logger.debug(f"Resolved device '{entity_value}' to {resolved_device.get('name')}")
                    else:
                        # Add available devices for potential suggestions
                        available_devices = context.get_device_capabilities()
                        if available_devices:
                            device_names = [d.get("name", "") for d in available_devices]
                            enhanced_entities["available_devices"] = device_names
                            self.logger.debug(f"Device '{entity_value}' not found, available: {device_names}")
        
        return enhanced_entities
    
    async def _disambiguate_with_device_context(self, intent: Intent, context: ConversationContext) -> Intent:
        """
        Disambiguate intent based on available device capabilities and context.
        
        This implements contextual intent disambiguation using client capabilities.
        """
        # If no client context available, return original intent
        if not context.client_id:
            return intent
        
        # Get available device types in this context
        available_device_types = context.get_device_types()
        
        # Intent disambiguation based on device availability
        if intent.domain == "system" and intent.action == "status":
            # If there are smart devices, this might be a device status query
            if "smart_device" in available_device_types or "sensor" in available_device_types:
                # Could disambiguate to device.status instead
                self.logger.debug("Disambiguating system.status to device context")
                enhanced_entities = intent.entities.copy()
                enhanced_entities["context_suggestion"] = "device_status"
        
        elif intent.domain == "conversation" and "display" in available_device_types:
            # If there's a display available, conversation might benefit from visual output
            enhanced_entities = intent.entities.copy()
            enhanced_entities["output_capabilities"] = ["text", "visual"]
            enhanced_entities["preferred_output_device"] = context.preferred_output_device
        
        # Return potentially enhanced intent (for now, return original)
        # In the future, this could return a different intent based on context
        return intent


class NLUComponent(Component, WebAPIPlugin):
    """
    Natural Language Understanding component.
    
    Coordinates multiple NLU providers (not plugins) following the Component-Provider pattern:
    - Component: Coordinates lifecycle and exposes unified interface
    - Providers: Implement specific NLU algorithms (rule-based, spaCy, etc.)
    """
    
    def __init__(self):
        super().__init__()
        self.providers: Dict[str, NLUProvider] = {}  # Proper ABC type hint
        self.confidence_threshold = 0.7
        self.fallback_intent = "conversation.general"
        self._provider_classes: Dict[str, type] = {}
        
        # Cascading provider coordination configuration
        self.provider_cascade_order: List[str] = []
        self.max_cascade_attempts = 4
        self.cascade_timeout_ms = 200
        self.cache_recognition_results = False
        self.cache_ttl_seconds = 300
        self._recognition_cache: Dict[str, Any] = {}
        
        # Context-aware processor
        self.context_processor = ContextAwareNLUProcessor(self)
    
    async def initialize(self, core) -> None:
        """Initialize NLU providers with configuration-driven filtering"""
        await super().initialize(core)
        
        # Get configuration first to determine enabled providers (V14 Architecture)
        config = getattr(core.config, 'nlu', None)
        if not config:
            # Create default config if missing
            from ..config.models import NLUConfig
            config = NLUConfig()
        
        # Convert Pydantic model to dict for backward compatibility with existing logic
        if hasattr(config, 'model_dump'):
            config = config.model_dump()
        elif hasattr(config, 'dict'):
            config = config.dict()
        else:
            # FATAL: Invalid configuration - cannot proceed with hardcoded defaults
            raise ValueError(
                "NLUComponent: Invalid configuration object received. "
                "Expected a valid NLUConfig instance, but got an invalid config. "
                "Please check your configuration file for proper v14 nlu section formatting."
            )
        
        # Configuration validation - should not be empty
        if not config:
            raise ValueError(
                "NLUComponent: Empty configuration received. "
                "A valid NLUConfig with providers must be provided in the v14 nlu section."
            )
        
        # Update component settings from config
        self.confidence_threshold = config.get("confidence_threshold", 0.7)
        self.fallback_intent = config.get("fallback_intent", "conversation.general")
        
        # Cascading provider coordination configuration
        self.provider_cascade_order = config.get("provider_cascade_order", [
            "keyword_matcher", "spacy_rules_sm", "spacy_semantic_md"
        ])
        self.max_cascade_attempts = config.get("max_cascade_attempts", 4)
        self.cascade_timeout_ms = config.get("cascade_timeout_ms", 200)
        self.cache_recognition_results = config.get("cache_recognition_results", False)
        self.cache_ttl_seconds = config.get("cache_ttl_seconds", 300)
        
        # Get provider configurations
        providers_config = config.get("providers", {})
        
        # Discover only enabled providers from entry-points (configuration-driven filtering)
        enabled_providers = [name for name, provider_config in providers_config.items() 
                            if provider_config.get("enabled", False)]
        
        # Always include keyword_matcher as fallback if not already included
        if "keyword_matcher" not in enabled_providers and providers_config.get("keyword_matcher", {}).get("enabled", True):
            enabled_providers.append("keyword_matcher")
            
        self._provider_classes = dynamic_loader.discover_providers("irene.providers.nlu", enabled_providers)
        logger.info(f"Discovered {len(self._provider_classes)} enabled NLU providers: {list(self._provider_classes.keys())}")
        
        # Initialize enabled providers
        enabled_count = 0
        for provider_name, provider_class in self._provider_classes.items():
            provider_config = providers_config.get(provider_name, {})
            if provider_config.get("enabled", False):
                try:
                    provider = provider_class(provider_config)
                    if hasattr(provider, 'is_available'):
                        if await provider.is_available():
                            self.providers[provider_name] = provider
                            enabled_count += 1
                            logger.info(f"Loaded NLU provider: {provider_name}")
                        else:
                            logger.warning(f"NLU provider {provider_name} not available (dependencies missing)")
                    else:
                        self.providers[provider_name] = provider
                        enabled_count += 1
                        logger.info(f"Loaded NLU provider: {provider_name}")
                except Exception as e:
                    logger.error(f"Failed to load NLU provider {provider_name}: {e}")
        
        # Set default provider if not set
        if not self.default_provider and self.providers:
            self.default_provider = next(iter(self.providers.keys()))
            logger.info(f"Set default NLU provider to: {self.default_provider}")
        
        logger.info(f"NLU component initialized with {enabled_count} providers")
        
        # Log cascading configuration
        logger.info(f"Cascading provider order: {self.provider_cascade_order}")
        logger.info(f"Max cascade attempts: {self.max_cascade_attempts}")
        
        # Initialize context processor
        logger.info("Context-aware NLU processor initialized")
        
        # Initialize providers with JSON donations (Phase 2 integration)
        await self.initialize_providers_from_json_donations()
    
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
    

    def get_component_dependencies(self) -> List[str]:
        """Get list of required component dependencies."""
        return ["text_processor"]  # NLU needs processed text
    
    def get_service_dependencies(self) -> Dict[str, type]:
        """Get list of required service dependencies."""
        return {}  # No service dependencies
    
    async def initialize_providers_from_json_donations(self) -> None:
        """
        Initialize NLU providers with JSON donation patterns.
        
        This is the critical bridge between the JSON donation system (Phase 0)
        and the NLU provider coordination (Phase 2).
        """
        try:
            # Import donation loader
            from ..core.donation_loader import DonationLoader
            from ..core.donations import DonationValidationConfig
            from pathlib import Path
            
            logger.info("Loading JSON donations for NLU provider initialization...")
            
            # Initialize donation loader with strict validation
            donation_config = DonationValidationConfig(strict_mode=True)
            donation_loader = DonationLoader(donation_config)
            
            # Discover handler files and load donations
            handler_dir = Path("irene/intents/handlers")
            handler_paths = self._discover_handler_files(handler_dir)
            
            # Load and validate JSON donations
            donations = await donation_loader.discover_and_load_donations(handler_paths)
            
            if not donations:
                logger.warning("No JSON donations found - providers will use fallback patterns")
                return
            
            logger.info(f"Loaded {len(donations)} JSON donations for NLU providers")
            
            # Convert donations to keyword format for providers
            keyword_donations = self._convert_json_to_keyword_donations(donations)
            
            # Initialize each provider with donations
            failed_providers = []
            for provider_name, provider in self.providers.items():
                if hasattr(provider, '_initialize_from_donations'):
                    try:
                        await provider._initialize_from_donations(keyword_donations)
                        logger.info(f"Initialized provider '{provider_name}' with {len(keyword_donations)} donations")
                    except Exception as e:
                        logger.error(f"Failed to initialize provider '{provider_name}' with donations: {e}")
                        failed_providers.append(provider_name)
                        # Phase 4: Remove failed provider from active providers
                        if provider_name in self.providers:
                            del self.providers[provider_name]
                else:
                    logger.warning(f"Provider '{provider_name}' does not support donation initialization")
            
            # Phase 4: Warn if critical providers failed
            if failed_providers:
                logger.warning(f"Phase 4: Providers failed donation initialization and were removed: {failed_providers}")
                logger.warning("System will operate with remaining donation-compatible providers only.")
            
            logger.info("JSON donation initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize providers from JSON donations: {e}")
            # Phase 4: No fallback patterns - this is a critical failure
            raise RuntimeError(f"NLU Component: JSON donation system failed to initialize: {e}. "
                             "Cannot operate without valid donations.")
    
    def _convert_json_to_keyword_donations(self, donations: Dict[str, Any]) -> List[Any]:
        """
        Convert JSON donations to KeywordDonation objects for NLU providers.
        
        Args:
            donations: Dictionary of handler donations
            
        Returns:
            List of KeywordDonation objects ready for provider consumption
        """
        try:
            from ..core.donation_loader import DonationLoader
            
            # Use the donation loader's conversion method
            donation_loader = DonationLoader()
            keyword_donations = donation_loader.convert_to_keyword_donations(donations)
            
            logger.debug(f"Converted {len(donations)} JSON donations to {len(keyword_donations)} keyword donations")
            
            return keyword_donations
            
        except Exception as e:
            logger.error(f"Failed to convert JSON donations to keyword format: {e}")
            return []
    
    def _discover_handler_files(self, handler_dir) -> List:
        """Discover Python handler files for donation loading"""
        from pathlib import Path
        handler_dir = Path(handler_dir)
        
        if not handler_dir.exists():
            logger.warning(f"Handler directory does not exist: {handler_dir}")
            return []
        
        python_files = []
        for file_path in handler_dir.glob("*.py"):
            # Skip base.py and __init__.py
            if file_path.name not in ['base.py', '__init__.py']:
                python_files.append(file_path)
        
        logger.debug(f"Discovered {len(python_files)} handler files in {handler_dir}")
        return python_files
    
    def _get_provider_cascade_order(self) -> List[str]:
        """
        Get provider order for cascading (fast -> slow, configuration-driven).
        
        Returns:
            List of provider names in cascade order
        """
        return self.provider_cascade_order
    
    def _get_cache_key(self, text: str, context: ConversationContext) -> str:
        """Generate cache key for recognition results"""
        # Include client context for cache differentiation
        context_key = f"{context.session_id}:{context.client_id}:{context.language}"
        return f"{context_key}:{hash(text.lower().strip())}"
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid"""
        import time
        if not cache_entry:
            return False
        
        cache_time = cache_entry.get("timestamp", 0)
        current_time = time.time()
        return (current_time - cache_time) < self.cache_ttl_seconds
    
    def _get_provider_confidence_threshold(self, provider_name: str) -> float:
        """
        Get confidence threshold for a specific provider.
        
        First checks provider-specific threshold, then falls back to global threshold.
        """
        # Get provider-specific configuration
        providers_config = getattr(self.core.config.components, 'nlu', {}).get("providers", {})
        provider_config = providers_config.get(provider_name, {})
        
        # Return provider-specific threshold or global threshold
        return provider_config.get("confidence_threshold", self.confidence_threshold)
    
    async def _try_provider_recognition(self, provider_name: str, text: str, 
                                      context: ConversationContext) -> Optional[Intent]:
        """
        Try recognition with a single provider with timeout and error handling.
        
        Args:
            provider_name: Name of the provider to try
            text: Input text to analyze
            context: Conversation context
            
        Returns:
            Intent if successful, None if failed or low confidence
        """
        if provider_name not in self.providers:
            logger.debug(f"Provider '{provider_name}' not available, skipping")
            return None
        
        provider = self.providers[provider_name]
        
        try:
            # PHASE 4: Use new integrated method for recognition with parameter extraction
            intent = await provider.recognize_with_parameters(text, context)
            
            # Get provider-specific confidence threshold
            provider_threshold = self._get_provider_confidence_threshold(provider_name)
            
            # Check if confidence meets provider-specific threshold
            if intent.confidence >= provider_threshold:
                logger.info(f"Intent recognized by {provider_name}: {intent.name} "
                           f"(confidence: {intent.confidence:.2f}, threshold: {provider_threshold:.2f})")
                return intent
            else:
                logger.debug(f"Provider {provider_name} low confidence "
                           f"({intent.confidence:.2f} < {provider_threshold:.2f}), trying next")
                return None
                
        except Exception as e:
            logger.warning(f"Provider {provider_name} failed: {e}")
            return None
    
    async def recognize(self, text: str, context: ConversationContext) -> Intent:
        """
        Recognize intent from text using cascading NLU providers.
        
        This implements the cascading provider coordination described in the 
        architecture document, trying providers in order of speed/accuracy until
        a confident intent is recognized.
        
        Args:
            text: Input text to analyze
            context: Conversation context for better understanding
            
        Returns:
            Intent object with recognized intent and entities
        """
        # Check cache if enabled
        if self.cache_recognition_results:
            cache_key = self._get_cache_key(text, context)
            cached_entry = self._recognition_cache.get(cache_key)
            
            if cached_entry and self._is_cache_valid(cached_entry):
                logger.debug(f"Cache hit for text: {text[:50]}...")
                cached_intent = cached_entry["intent"]
                import time as time_module
                cached_intent.timestamp = time_module.time()  # Update timestamp
                return cached_intent
        
        # Phase 4: Ensure we have available providers
        if not self.providers:
            raise RuntimeError("NLU Component: No providers available for intent recognition. "
                             "JSON donation initialization may have failed.")
        
        # Try providers in cascade order (fast -> slow)
        provider_order = self._get_provider_cascade_order()
        attempts = 0
        
        for provider_name in provider_order:
            if attempts >= self.max_cascade_attempts:
                logger.debug(f"Max cascade attempts ({self.max_cascade_attempts}) reached")
                break
            
            attempts += 1
            intent = await self._try_provider_recognition(provider_name, text, context)
            
            if intent:
                # Cache successful recognition if enabled
                if self.cache_recognition_results:
                    import time
                    self._recognition_cache[cache_key] = {
                        "intent": intent,
                        "timestamp": time.time(),
                        "provider": provider_name
                    }
                    
                    # Limit cache size
                    if len(self._recognition_cache) > 1000:
                        # Remove oldest entries
                        sorted_entries = sorted(
                            self._recognition_cache.items(),
                            key=lambda x: x[1]["timestamp"]
                        )
                        for old_key, _ in sorted_entries[:100]:
                            del self._recognition_cache[old_key]
                
                # Add provider metadata to intent
                intent.entities["_recognition_provider"] = provider_name
                intent.entities["_cascade_attempts"] = attempts
                
                return intent
        
        # All providers failed or low confidence - use conversation fallback
        logger.info(f"All NLU providers failed or low confidence after {attempts} attempts, "
                   f"using conversation fallback")
        
        fallback_intent = self._create_fallback_intent(text, context.session_id)
        fallback_intent.entities["_recognition_provider"] = "fallback"
        fallback_intent.entities["_cascade_attempts"] = attempts
        
        return fallback_intent
    
    def get_providers_info(self) -> str:
        """Implementation of abstract method - Get NLU providers information"""
        if not self.providers:
            return "Нет доступных провайдеров NLU"
        
        info_lines = [f"Доступные провайдеры NLU ({len(self.providers)}):"]
        for name, provider in self.providers.items():
            status = "✓ (по умолчанию)" if name == self.default_provider else "✓"
            capabilities = getattr(provider, 'get_capabilities', lambda: {})()
            languages = capabilities.get("languages", ["unknown"])
            domains = capabilities.get("domains", ["general"])
            info_lines.append(f"  {status} {name}: {', '.join(languages[:2])}, {', '.join(domains[:2])}")
        
        info_lines.append(f"Порог уверенности: {self.confidence_threshold}")
        info_lines.append(f"Резервный интент: {self.fallback_intent}")
        
        return "\n".join(info_lines)
    
    async def recognize_with_context(self, text: str, context: ConversationContext) -> Intent:
        """
        Context-aware intent recognition with enhanced entity resolution and disambiguation.
        
        This method provides the enhanced context-aware NLU processing capabilities
        described in the architecture document, using client identification and 
        device context for better understanding.
        
        Args:
            text: Input text to analyze
            context: Enhanced ConversationContext with client and device info
            
        Returns:
            Intent with context-enhanced entities and disambiguation
        """
        return await self.context_processor.process_with_context(text, context)
    
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
                    # PHASE 4: Use integrated parameter extraction for direct provider calls
                    intent = await self.providers[request.provider].recognize_with_parameters(request.text, context)
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

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """NLU component needs web API functionality"""
        return ["fastapi>=0.100.0", "uvicorn[standard]>=0.20.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """NLU component has no system dependencies - coordinates providers only"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """NLU component supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    # Config interface methods (Phase 3 - Configuration Architecture Cleanup)
    @classmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the Pydantic config model for this component"""
        from ..config.models import NLUConfig
        return NLUConfig
    
    @classmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to this component's config (V14 Architecture)"""
        return "nlu" 