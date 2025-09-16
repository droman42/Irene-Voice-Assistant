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
from ..core.intent_asset_loader import IntentAssetLoader, AssetLoaderConfig

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
        self._asset_loader: Optional[IntentAssetLoader] = None
        self._donations: Dict[str, Any] = {}
        self._intent_system_config: Optional[Any] = None  # Phase 5: Store full intent system config
        self._initialized = False
        
    async def initialize(self, config: Optional[Dict[str, Any]] = None, intent_system_config: Optional[Any] = None) -> None:
        """
        Discover and register intent handlers from entry-points with donation support.
        
        Args:
            config: Configuration dictionary for intent handler settings
            intent_system_config: Full intent system configuration (Pydantic IntentSystemConfig or dict)
        """
        if self._initialized:
            return
            
        logger.info("Initializing IntentHandlerManager with donation support...")
        
        # Phase 5: Store full intent system config for handler-specific configurations
        self._intent_system_config = intent_system_config
        
        # Configuration is now purely driven by IntentSystemConfig - no defaults here
        if not config:
            raise ValueError("IntentHandlerManager requires configuration from IntentSystemConfig")
        
        # Get enabled handlers list from configuration (disabled takes precedence)
        if "enabled" in config and "disabled" in config:
            # New structured configuration
            enabled_handlers = [h for h in config["enabled"] if h not in config.get("disabled", [])]
        else:
            # Legacy dict configuration support
            enabled_handlers = config.get("enabled", [])
            disabled_handlers = config.get("disabled", [])
            enabled_handlers = [h for h in enabled_handlers if h not in disabled_handlers]
        logger.info(f"Enabled intent handlers: {enabled_handlers}")
        
        # Phase 6: Initialize unified asset loader
        from pathlib import Path
        asset_config = AssetLoaderConfig(**config.get("asset_validation", {}))
        assets_root = Path("assets")
        self._asset_loader = IntentAssetLoader(assets_root, asset_config)
        
        # Validate enabled handlers before discovery
        if not enabled_handlers:
            raise ValueError("No intent handlers enabled - at least one handler must be enabled")
        
        # Discover handlers from entry-points (configuration-driven filtering)
        try:
            self._handler_classes = dynamic_loader.discover_providers(
                "irene.intents.handlers", 
                enabled_handlers
            )
        except Exception as e:
            raise RuntimeError(f"Failed to discover intent handlers: {e}")
        
        # Validate discovery results
        discovered_handlers = set(self._handler_classes.keys())
        requested_handlers = set(enabled_handlers)
        missing_handlers = requested_handlers - discovered_handlers
        
        if missing_handlers:
            logger.error(f"Requested handlers not found via entry-points: {missing_handlers}")
            logger.error(f"Available handlers found: {discovered_handlers}")
            raise ValueError(f"Intent handlers not found: {missing_handlers}. "
                           f"Check that these handlers exist and are properly registered as entry-points.")
        
        logger.info(f"Successfully discovered {len(self._handler_classes)} enabled intent handlers: {list(self._handler_classes.keys())}")
        
        # Phase 6: Load JSON donations (CRITICAL - must happen before handler instantiation)
        await self._load_donations()
        
        # Instantiate and register discovered handlers with donations
        await self._instantiate_handlers()
        await self._initialize_handlers_with_donations()
        await self._register_handlers()
        
        
        # Create orchestrator with registry only (no parameter extractor needed)
        self._orchestrator = IntentOrchestrator(self._registry)
        
        self._initialized = True
        logger.info(f"IntentHandlerManager initialized with {len(self._handler_instances)} handlers and donation support")
    
    def set_context_manager(self, context_manager: Any) -> None:
        """Set the context manager on all registered handlers for fire-and-forget action tracking."""
        for handler_name, handler in self._handler_instances.items():
            if hasattr(handler, 'set_context_manager'):
                handler.set_context_manager(context_manager)
                logger.debug(f"Set context manager on handler: {handler_name}")
            else:
                logger.warning(f"Handler {handler_name} does not support context manager injection")
    
    def _get_handler_config(self, handler_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific handler using metadata-driven discovery.
        
        Args:
            handler_name: Name of the handler
            
        Returns:
            Handler configuration dict or None if not available
        """
        if not self._intent_system_config:
            return None
        
        # Check if handler actually requires configuration
        handler_class = self._handler_classes.get(handler_name)
        if not handler_class or not hasattr(handler_class, 'requires_configuration'):
            return None
        
        if not handler_class.requires_configuration():
            return None  # Handler doesn't need configuration
        
        # Dynamic configuration discovery using multiple naming patterns
        config_patterns = [
            handler_name,  # Direct mapping: "conversation" -> self.conversation
            handler_name.replace('_handler', ''),  # "text_enhancement_handler" -> self.text_enhancement
            handler_name.replace('_intent_handler', ''),  # Future compatibility
        ]
        
        # Try each pattern to find configuration
        for pattern in config_patterns:
            if hasattr(self._intent_system_config, pattern):
                handler_config = getattr(self._intent_system_config, pattern)
                
                # Convert Pydantic model to dict if needed
                if hasattr(handler_config, 'model_dump'):
                    return handler_config.model_dump()
                elif hasattr(handler_config, 'dict'):
                    return handler_config.dict()
                else:
                    return handler_config
            elif isinstance(self._intent_system_config, dict):
                config_value = self._intent_system_config.get(pattern)
                if config_value is not None:
                    return config_value
        
        # If no configuration found but handler requires it, log warning
        logger.warning(f"Handler '{handler_name}' requires configuration but none found. Tried patterns: {config_patterns}")
        return None
    

    async def _load_donations(self) -> None:
        """Load JSON donations and other assets for enabled handlers only."""
        try:
            # Get handler names from discovered classes (already filtered to enabled only)
            handler_names = list(self._handler_classes.keys())
            
            if not handler_names:
                raise ValueError("No handler names available for donation loading")
            
            logger.info(f"Loading donations for enabled handlers: {handler_names}")
            
            # Load all assets using unified asset loader
            await self._asset_loader.load_all_assets(handler_names)
            
            # Get donations from the asset loader
            self._donations = self._asset_loader.donations
            
            # Validate donation loading results
            loaded_donations = set(self._donations.keys())
            expected_handlers = set(handler_names)
            missing_donations = expected_handlers - loaded_donations
            
            if missing_donations:
                logger.warning(f"Missing donations for handlers: {missing_donations}")
                logger.warning("These handlers may not function properly without donations")
            
            extra_donations = loaded_donations - expected_handlers
            if extra_donations:
                logger.info(f"Extra donations found (will be ignored): {extra_donations}")
            
            if not self._donations:
                raise RuntimeError("No donations were loaded - intent system cannot function")
            
            logger.info(f"Successfully loaded {len(self._donations)} JSON donations for handlers: {list(self._donations.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to load assets: {e}")
            raise RuntimeError(f"Asset loading failed: {e}")
    
    async def _instantiate_handlers(self) -> None:
        """Instantiate discovered handler classes with proper configuration injection."""
        for name, handler_class in self._handler_classes.items():
            try:
                # Phase 5: Check if handler needs configuration injection
                handler_config = self._get_handler_config(name)
                
                # Configuration validation is handled by Pydantic models in CoreConfig.intent_system
                
                # Check if handler constructor accepts config parameter
                import inspect
                sig = inspect.signature(handler_class.__init__)
                
                if 'config' in sig.parameters and handler_config is not None:
                    # Instantiate with configuration
                    handler_instance = handler_class(config=handler_config)
                    logger.debug(f"Instantiated intent handler '{name}' with configuration: {list(handler_config.keys()) if isinstance(handler_config, dict) else type(handler_config).__name__}")
                else:
                    # Instantiate without configuration
                    handler_instance = handler_class()
                    logger.debug(f"Instantiated intent handler: {name}")
                
                self._handler_instances[name] = handler_instance
                
            except Exception as e:
                logger.error(f"Failed to instantiate intent handler {name}: {e}")
                continue
    
    async def _initialize_handlers_with_donations(self) -> None:
        """Initialize handlers with their corresponding JSON donations and asset loader."""
        failed_handlers = []
        
        for name, handler in self._handler_instances.items():
            try:
                # Set asset loader on handler (all handlers get access to assets)
                if hasattr(handler, 'set_asset_loader'):
                    handler.set_asset_loader(self._asset_loader)
                    logger.debug(f"Initialized handler {name} with asset loader")
                else:
                    logger.warning(f"Handler {name} does not support asset loader (no set_asset_loader method)")
                
                # Check if donation exists for this handler
                if name in self._donations:
                    donation = self._donations[name]
                    
                    # Validate donation structure
                    if not hasattr(donation, 'method_donations'):
                        logger.error(f"Invalid donation structure for handler {name}: missing method_donations")
                        failed_handlers.append(name)
                        continue
                    
                    # Set donation on handler
                    if hasattr(handler, 'set_donation'):
                        handler.set_donation(donation)
                        logger.debug(f"Initialized handler {name} with donation containing {len(donation.method_donations)} methods")
                    else:
                        logger.error(f"Handler {name} does not support donations (no set_donation method)")
                        failed_handlers.append(name)
                        continue
                else:
                    logger.error(f"No donation found for handler {name}")
                    failed_handlers.append(name)
                    continue
                
                # Validate handler is properly initialized
                if hasattr(handler, 'has_donation') and not handler.has_donation():
                    logger.error(f"Handler {name} failed donation initialization")
                    failed_handlers.append(name)
                    continue
                    
            except Exception as e:
                logger.error(f"Failed to initialize handler {name} with assets: {e}")
                failed_handlers.append(name)
                continue
        
        # Remove failed handlers from instances
        for failed_name in failed_handlers:
            if failed_name in self._handler_instances:
                del self._handler_instances[failed_name]
                logger.warning(f"Removed failed handler: {failed_name}")
        
        # Check if we have any working handlers left
        if not self._handler_instances:
            raise RuntimeError("All intent handlers failed initialization - intent system cannot function")
        
        if failed_handlers:
            logger.warning(f"Intent handlers failed initialization: {failed_handlers}")
            logger.info(f"Continuing with {len(self._handler_instances)} working handlers: {list(self._handler_instances.keys())}")
        
        logger.info(f"Successfully initialized {len(self._handler_instances)} handlers with donations")
    
    
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