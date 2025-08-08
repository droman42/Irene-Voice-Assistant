"""
Intent Handler Manager - Dynamic discovery and registration of intent handlers

This module provides the IntentHandlerManager that discovers intent handlers 
from entry-points and registers them with the IntentRegistry, implementing
configuration-driven filtering for enabled/disabled handlers.
"""

import logging
from typing import Dict, Any, List, Optional

from .registry import IntentRegistry
from .orchestrator import IntentOrchestrator
from ..utils.loader import dynamic_loader

logger = logging.getLogger(__name__)


class IntentHandlerManager:
    """
    Manages intent handler discovery, instantiation, and registration.
    
    Features:
    - Dynamic discovery using entry-points
    - Configuration-driven filtering (enabled/disabled handlers)
    - Automatic registration with IntentRegistry
    - Pattern-based handler setup
    - Integration with IntentOrchestrator
    """
    
    def __init__(self):
        """Initialize the intent handler manager."""
        self._handler_classes: Dict[str, type] = {}
        self._handler_instances: Dict[str, Any] = {}
        self._registry = IntentRegistry()
        self._orchestrator: Optional[IntentOrchestrator] = None
        self._initialized = False
        
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Discover and register intent handlers from entry-points.
        
        Args:
            config: Configuration dictionary for intent handler settings
        """
        if self._initialized:
            return
            
        logger.info("Initializing IntentHandlerManager...")
        
        # Default configuration
        default_config = {
            "enabled": ["conversation", "greetings", "timer", "datetime", "system"],
            "disabled": ["train_schedule"],  # Example: disable specific handlers
            "auto_discover": True,
            "discovery_paths": ["irene.intents.handlers"]
        }
        
        # Merge with provided config
        handler_config = {**default_config, **(config or {})}
        
        # Get enabled handlers list
        enabled_handlers = handler_config.get("enabled", [])
        logger.info(f"Enabled intent handlers: {enabled_handlers}")
        
        # Discover handlers from entry-points (configuration-driven filtering)
        self._handler_classes = dynamic_loader.discover_providers(
            "irene.intents.handlers", 
            enabled_handlers
        )
        logger.info(f"Discovered {len(self._handler_classes)} enabled intent handlers: {list(self._handler_classes.keys())}")
        
        # Instantiate and register discovered handlers
        await self._instantiate_handlers()
        await self._register_handlers()
        
        # Create orchestrator with registry
        self._orchestrator = IntentOrchestrator(self._registry)
        
        self._initialized = True
        logger.info(f"IntentHandlerManager initialized with {len(self._handler_instances)} handlers")
    
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
    
    async def _register_handlers(self) -> None:
        """Register handler instances with the IntentRegistry."""
        for name, handler in self._handler_instances.items():
            try:
                # Get supported patterns from handler
                patterns = await self._get_handler_patterns(handler)
                
                # Register each pattern with the registry
                for pattern in patterns:
                    metadata = {
                        "handler_name": name,
                        "handler_class": handler.__class__.__name__,
                        "supported_domains": getattr(handler, 'get_supported_domains', lambda: [])(),
                        "supported_actions": getattr(handler, 'get_supported_actions', lambda: [])()
                    }
                    
                    self._registry.register_handler(pattern, handler, metadata)
                    logger.debug(f"Registered pattern '{pattern}' for handler {name}")
                    
            except Exception as e:
                logger.error(f"Failed to register intent handler {name}: {e}")
                continue
    
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