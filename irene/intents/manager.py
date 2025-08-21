"""
Intent Handler Manager - Dynamic discovery and registration of intent handlers

This module provides the IntentHandlerManager that discovers intent handlers 
from entry-points and registers them with the IntentRegistry, implementing
configuration-driven filtering for enabled/disabled handlers with donation support.
"""

import logging
from typing import Dict, Any, List, Optional

from .registry import IntentRegistry
from .orchestrator import IntentOrchestrator
from ..utils.loader import dynamic_loader
from ..core.donation_loader import DonationLoader
# PHASE 5: Remove parameter extractor import - now integrated into NLU providers

logger = logging.getLogger(__name__)


class IntentHandlerManager:
    """
    Manages intent handler discovery, instantiation, and registration with donation support.
    
    Features:
    - Dynamic discovery using entry-points
    - Configuration-driven filtering (enabled/disabled handlers)
    - Automatic registration with IntentRegistry
    - JSON donation loading and handler initialization
    - Parameter extraction integration
    - Integration with IntentOrchestrator
    """
    
    def __init__(self):
        """Initialize the intent handler manager."""
        self._handler_classes: Dict[str, type] = {}
        self._handler_instances: Dict[str, Any] = {}
        self._registry = IntentRegistry()
        self._orchestrator: Optional[IntentOrchestrator] = None
        self._donation_loader: Optional[DonationLoader] = None
        # PHASE 5: Remove parameter extractor field - now integrated into NLU providers
        self._donations: Dict[str, Any] = {}
        self._initialized = False
        
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Discover and register intent handlers from entry-points with donation support.
        
        Args:
            config: Configuration dictionary for intent handler settings
        """
        if self._initialized:
            return
            
        logger.info("Initializing IntentHandlerManager with donation support...")
        
        # Default configuration
        default_config = {
            "enabled": ["conversation", "greetings", "timer", "datetime", "system", "train_schedule"],
            "disabled": [],  # Phase 6: Enable all handlers by default
            "auto_discover": True,
            "discovery_paths": ["irene.intents.handlers"],
            "donation_validation": {
                "strict_mode": True,
                "validate_method_existence": True,
                "validate_spacy_patterns": False,  # PHASE 0: spaCy validation moved to providers at runtime
                "validate_json_schema": True
            }
        }
        
        # Merge with provided config
        handler_config = {**default_config, **(config or {})}
        
        # Get enabled handlers list
        enabled_handlers = handler_config.get("enabled", [])
        logger.info(f"Enabled intent handlers: {enabled_handlers}")
        
        # Phase 6: Initialize donation loader
        from ..core.donations import DonationValidationConfig
        validation_config = DonationValidationConfig(**handler_config.get("donation_validation", {}))
        self._donation_loader = DonationLoader(validation_config)
        
        # Discover handlers from entry-points (configuration-driven filtering)
        self._handler_classes = dynamic_loader.discover_providers(
            "irene.intents.handlers", 
            enabled_handlers
        )
        logger.info(f"Discovered {len(self._handler_classes)} enabled intent handlers: {list(self._handler_classes.keys())}")
        
        # Phase 6: Load JSON donations (CRITICAL - must happen before handler instantiation)
        await self._load_donations()
        
        # Instantiate and register discovered handlers with donations
        await self._instantiate_handlers()
        await self._initialize_handlers_with_donations()
        await self._register_handlers()
        
        # PHASE 5: Remove parameter extractor initialization - now integrated into NLU providers
        
        # Create orchestrator with registry only (no parameter extractor needed)
        self._orchestrator = IntentOrchestrator(self._registry)
        
        self._initialized = True
        logger.info(f"IntentHandlerManager initialized with {len(self._handler_instances)} handlers and donation support")
    
    async def _load_donations(self) -> None:
        """Load JSON donations for all handlers."""
        try:
            from pathlib import Path
            
            # Discover handler files in the standard location
            handler_dir = Path("irene/intents/handlers")
            handler_paths = []
            
            for handler_name in self._handler_classes.keys():
                handler_file = handler_dir / f"{handler_name}.py"
                if handler_file.exists():
                    handler_paths.append(handler_file)
                else:
                    logger.warning(f"Handler file not found for {handler_name}: {handler_file}")
            
            # Load donations using donation loader
            self._donations = await self._donation_loader.discover_and_load_donations(handler_paths)
            
            logger.info(f"Loaded {len(self._donations)} JSON donations for handlers: {list(self._donations.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to load JSON donations: {e}")
            raise RuntimeError(f"Donation loading failed: {e}")
    
    async def _instantiate_handlers(self) -> None:
        """Instantiate discovered handler classes."""
        for name, handler_class in self._handler_classes.items():
            try:
                # Instantiate handler
                handler_instance = handler_class()
                self._handler_instances[name] = handler_instance
                logger.debug(f"Instantiated intent handler: {name}")
                
            except Exception as e:
                logger.error(f"Failed to instantiate intent handler {name}: {e}")
                continue
    
    async def _initialize_handlers_with_donations(self) -> None:
        """Initialize handlers with their corresponding JSON donations."""
        for name, handler in self._handler_instances.items():
            try:
                if name in self._donations:
                    # Set donation on handler
                    donation = self._donations[name]
                    if hasattr(handler, 'set_donation'):
                        handler.set_donation(donation)
                        logger.debug(f"Initialized handler {name} with donation containing {len(donation.method_donations)} methods")
                    else:
                        logger.warning(f"Handler {name} does not support donations (no set_donation method)")
                else:
                    logger.error(f"No donation found for handler {name}")
                    raise RuntimeError(f"Missing donation for handler {name}")
                    
            except Exception as e:
                logger.error(f"Failed to initialize handler {name} with donation: {e}")
                raise
    
    # PHASE 5: Remove _initialize_parameter_extractor method - parameter extraction now integrated into NLU providers
    
    async def _register_handlers(self) -> None:
        """Register handler instances with the IntentRegistry using donation-based patterns."""
        for name, handler in self._handler_instances.items():
            try:
                # Phase 6: Get patterns from donations if available
                patterns = await self._get_handler_patterns_from_donations(name, handler)
                
                # Register each pattern with the registry
                for pattern in patterns:
                    metadata = {
                        "handler_name": name,
                        "handler_class": handler.__class__.__name__,
                        "has_donation": hasattr(handler, 'has_donation') and handler.has_donation(),
                        "donation_methods": len(self._donations[name].method_donations) if name in self._donations else 0,
                        "supported_domains": getattr(handler, 'get_supported_domains', lambda: [])(),
                        "supported_actions": getattr(handler, 'get_supported_actions', lambda: [])()
                    }
                    
                    self._registry.register_handler(pattern, handler, metadata)
                    logger.debug(f"Registered pattern '{pattern}' for handler {name}")
                    
            except Exception as e:
                logger.error(f"Failed to register intent handler {name}: {e}")
                continue
    
    async def _get_handler_patterns_from_donations(self, handler_name: str, handler: Any) -> List[str]:
        """
        Get registration patterns for a handler from donations or fallback to legacy patterns.
        
        Args:
            handler_name: Name of the handler
            handler: Handler instance
            
        Returns:
            List of patterns this handler should be registered for
        """
        patterns = []
        
        # Phase 6: Get patterns from JSON donations first
        if handler_name in self._donations:
            donation = self._donations[handler_name]
            domain = donation.handler_domain
            
            # Register for each method in the donation
            for method_donation in donation.method_donations:
                intent_pattern = f"{domain}.{method_donation.intent_suffix}"
                patterns.append(intent_pattern)
            
            # Also register domain wildcard for unspecified methods
            patterns.append(f"{domain}.*")
            
            logger.debug(f"Handler {handler_name} patterns from donation: {patterns}")
            return patterns
        
        # Fallback to legacy pattern detection
        return await self._get_handler_patterns(handler)
    
    async def _get_handler_patterns(self, handler: Any) -> List[str]:
        """
        Get registration patterns for a handler.
        
        Args:
            handler: Handler instance
            
        Returns:
            List of patterns this handler should be registered for
        """
        patterns = []
        
        # Check if handler provides its own patterns
        if hasattr(handler, 'get_supported_patterns'):
            try:
                handler_patterns = await handler.get_supported_patterns()
                if isinstance(handler_patterns, list):
                    patterns.extend(handler_patterns)
            except Exception as e:
                logger.warning(f"Handler {handler.__class__.__name__} get_supported_patterns failed: {e}")
        
        # Fallback: derive patterns from domains and actions
        if not patterns:
            domains = getattr(handler, 'get_supported_domains', lambda: [])()
            if domains:
                # Register for domain wildcards (e.g., "timer.*")
                patterns.extend([f"{domain}.*" for domain in domains])
            else:
                # Fallback: use handler class name
                handler_name = handler.__class__.__name__.lower()
                if handler_name.endswith('intenthandler'):
                    base_name = handler_name[:-13]  # Remove 'intenthandler'
                    patterns.append(f"{base_name}.*")
        
        # Ensure we have at least one pattern
        if not patterns:
            handler_name = handler.__class__.__name__.lower()
            if handler_name.endswith('intenthandler'):
                base_name = handler_name[:-13]
                patterns.append(base_name)
            else:
                patterns.append(handler_name)
        
        return patterns
    
    def get_registry(self) -> IntentRegistry:
        """Get the intent registry."""
        return self._registry
    
    def get_orchestrator(self) -> Optional[IntentOrchestrator]:
        """Get the intent orchestrator."""
        return self._orchestrator
    
    def get_handlers(self) -> Dict[str, Any]:
        """Get all registered handler instances."""
        return self._handler_instances.copy()
    
    def get_donations(self) -> Dict[str, Any]:
        """Get all loaded JSON donations."""
        return self._donations.copy()
    
    # PHASE 5: Remove get_parameter_extractor method - parameter extraction now integrated into NLU providers
    
    async def add_handler(self, name: str, handler: Any, patterns: Optional[List[str]] = None) -> None:
        """
        Dynamically add a handler instance.
        
        Args:
            name: Handler name
            handler: Handler instance
            patterns: Optional explicit patterns, otherwise derived from handler
        """
        self._handler_instances[name] = handler
        
        if patterns is None:
            patterns = await self._get_handler_patterns(handler)
        
        for pattern in patterns:
            self._registry.register_handler(pattern, handler)
            
        logger.info(f"Added intent handler: {name} with patterns {patterns}")
    
    async def remove_handler(self, name: str) -> bool:
        """
        Remove a handler by name.
        
        Args:
            name: Handler name to remove
            
        Returns:
            True if handler was removed, False if not found
        """
        if name not in self._handler_instances:
            return False
        
        # Remove from instances
        del self._handler_instances[name]
        
        # Note: IntentRegistry doesn't currently support removing by handler instance
        # This would need to be enhanced for full dynamic handler management
        logger.info(f"Removed intent handler: {name}")
        return True
    
    async def reload_handlers(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Reload all handlers with new configuration.
        
        Args:
            config: New configuration for handlers
        """
        logger.info("Reloading intent handlers...")
        
        # Clear current state
        self._handler_classes.clear()
        self._handler_instances.clear()
        self._registry = IntentRegistry()
        self._initialized = False
        
        # Reinitialize with new config
        await self.initialize(config)
        
        # Recreate orchestrator
        self._orchestrator = IntentOrchestrator(self._registry) 