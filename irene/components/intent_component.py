"""
Intent Component - Intent system integration with component architecture

This component wraps the IntentHandlerManager and provides the intent system
(registry, orchestrator, handlers) as a unified component that can be
integrated into workflows and the component lifecycle.
"""

import logging
from typing import Dict, Any, List, Optional, Type

from pydantic import BaseModel
from .base import Component
from ..core.interfaces.webapi import WebAPIPlugin
from ..intents.manager import IntentHandlerManager
from ..intents.registry import IntentRegistry
from ..intents.orchestrator import IntentOrchestrator

logger = logging.getLogger(__name__)


class IntentComponent(Component, WebAPIPlugin):
    """
    Intent system component providing intent recognition and handling.
    
    Features:
    - Dynamic intent handler discovery and registration
    - Configuration-driven handler filtering
    - Intent orchestration and execution
    - Web API endpoints for intent management
    - Integration with workflow system
    """
    
    def __init__(self):
        super().__init__()
        self.handler_manager: Optional[IntentHandlerManager] = None
        self.intent_orchestrator: Optional[IntentOrchestrator] = None
        self.intent_registry: Optional[IntentRegistry] = None
        self._config: Optional[Dict[str, Any]] = None
        
    async def initialize(self, core) -> None:
        """Initialize the intent system with configuration-driven handler discovery"""
        await super().initialize(core)
        
        # Get intent system configuration (Phase 5: Use proper Pydantic IntentSystemConfig)
        intent_config = getattr(core.config, 'intent_system', None)
        
        # Configuration must be provided - no fallback defaults
        if not intent_config:
            raise ValueError("IntentComponent requires configuration from CoreConfig.intent_system")
        
        self._config = intent_config
        
        # Initialize intent handler manager (Phase 5: Pass full intent system config)
        self.handler_manager = IntentHandlerManager()
        # Extract handler configuration from IntentSystemConfig
        if isinstance(intent_config, dict):
            handler_config = intent_config.get("handlers", {})
        else:
            # For Pydantic IntentSystemConfig, convert IntentHandlerListConfig to dict
            handlers_obj = getattr(intent_config, "handlers", None)
            if handlers_obj:
                handler_config = {
                    "enabled": handlers_obj.enabled,
                    "disabled": handlers_obj.disabled,
                    "auto_discover": handlers_obj.auto_discover,
                    "discovery_paths": handlers_obj.discovery_paths,
                    "asset_validation": handlers_obj.asset_validation
                }
            else:
                handler_config = {}
        
        # Phase 5: Pass full intent system config for handler-specific configurations
        await self.handler_manager.initialize(handler_config, intent_system_config=intent_config)
        
        # Get registry and orchestrator from manager
        self.intent_registry = self.handler_manager.get_registry()
        self.intent_orchestrator = self.handler_manager.get_orchestrator()
        
        # Inject component dependencies into handlers
        await self._inject_handler_dependencies(core)
        
        # Validate initialization results
        await self._validate_initialization_results()
        
        # Log initialization status  
        handlers = self.handler_manager.get_handlers()
        donations = self.handler_manager.get_donations()
        logger.info(f"Intent component initialized with {len(handlers)} handlers: {list(handlers.keys())}")
        logger.info(f"Loaded {len(donations)} JSON donations for donation-driven execution")
        
    def get_enabled_handler_names(self) -> List[str]:
        """
        Get list of enabled intent handler names.
        
        Returns:
            List of enabled handler names
        """
        if self.handler_manager:
            return list(self.handler_manager.get_handlers().keys())
        return []
    
    def get_enabled_handler_donations(self) -> Dict[str, Any]:
        """
        Get donations for enabled intent handlers.
        
        Returns:
            Dictionary of handler donations
        """
        if self.handler_manager:
            return self.handler_manager.get_donations()
        return {}
    
    async def _validate_initialization_results(self) -> None:
        """
        Validate that initialization completed successfully with comprehensive checks.
        """
        try:
            # Check that handler manager was created
            if not self.handler_manager:
                raise RuntimeError("IntentHandlerManager was not initialized")
            
            # Check that registry and orchestrator were created
            if not self.intent_registry:
                raise RuntimeError("Intent registry was not initialized")
            
            if not self.intent_orchestrator:
                raise RuntimeError("Intent orchestrator was not initialized")
            
            # Get enabled handlers from configuration
            if isinstance(self._config, dict):
                enabled_config = self._config.get("handlers", {}).get("enabled", [])
                disabled_config = self._config.get("handlers", {}).get("disabled", [])
            else:
                enabled_config = self._config.handlers.enabled
                disabled_config = self._config.handlers.disabled
            
            expected_handlers = [h for h in enabled_config if h not in disabled_config]
            
            # Check that expected handlers were loaded
            actual_handlers = self.get_enabled_handler_names()
            
            if not actual_handlers:
                raise RuntimeError("No intent handlers were successfully loaded")
            
            missing_handlers = set(expected_handlers) - set(actual_handlers)
            if missing_handlers:
                logger.error(f"Expected handlers not loaded: {missing_handlers}")
                logger.error(f"Configuration enabled: {enabled_config}")
                logger.error(f"Configuration disabled: {disabled_config}")
                logger.error(f"Actually loaded: {actual_handlers}")
                raise RuntimeError(f"Critical intent handlers failed to load: {missing_handlers}")
            
            # Check that donations were loaded
            donations = self.get_enabled_handler_donations()
            if not donations:
                raise RuntimeError("No intent handler donations were loaded")
            
            missing_donations = set(actual_handlers) - set(donations.keys())
            if missing_donations:
                logger.warning(f"Handlers missing donations: {missing_donations}")
                # This is a warning, not a fatal error
            
            # Validate registry has patterns
            if hasattr(self.intent_registry, 'handlers') and not self.intent_registry.handlers:
                logger.warning("Intent registry has no registered handlers")
            
            logger.info("✅ Intent component initialization validation passed")
            
        except Exception as e:
            logger.error(f"❌ Intent component initialization validation failed: {e}")
            raise RuntimeError(f"Intent component failed validation: {e}")
        
    async def shutdown(self) -> None:
        """Shutdown the intent system"""
        if self.handler_manager:
            # Clear handlers and reset system
            self.handler_manager._handler_instances.clear()
            self.handler_manager._handler_classes.clear()
            
        self.intent_orchestrator = None
        self.intent_registry = None
        self.handler_manager = None
        
        logger.info("Intent component shutdown completed")
        
    async def _inject_handler_dependencies(self, core) -> None:
        """Inject component dependencies into intent handlers"""
        try:
            # Get the component manager to access other components
            component_manager = getattr(core, 'component_manager', None)
            if not component_manager:
                logger.warning("Component manager not available for handler dependency injection")
                return
                
            # Get available components
            components = component_manager.get_components()
            
            # Get all handler instances
            handlers = self.handler_manager.get_handlers()
            
            for handler_name, handler in handlers.items():
                # Inject LLM component if handler needs it (specifically ConversationIntentHandler)
                if handler_name == 'conversation' and 'llm' in components:
                    handler.llm_component = components['llm']
                    logger.debug(f"Injected LLM component into {handler_name} handler")
                
                # Add other component injections as needed
                # if handler_name == 'some_other_handler' and 'other_component' in components:
                #     handler.other_component = components['other_component']
                    
        except Exception as e:
            logger.error(f"Failed to inject handler dependencies: {e}")

    def get_component_dependencies(self) -> List[str]:
        """Get list of required component dependencies."""
        return ["nlu", "llm"]  # Intent system needs NLU for recognition and LLM for processing
    
    def get_service_dependencies(self) -> Dict[str, type]:
        """Get list of required service dependencies."""
        return {}  # No service dependencies
    
    def get_providers_info(self) -> str:
        """Implementation of abstract method - Intent system doesn't use traditional providers"""
        if not self.handler_manager:
            return "Система интентов не инициализирована"
        
        handlers = self.handler_manager.get_handlers()
        donations = self.handler_manager.get_donations()
        
        info_lines = [f"Система обработки интентов ({len(handlers)} обработчиков):"]
        for name, handler in handlers.items():
            status = "✓"
            domains = getattr(handler, 'get_supported_domains', lambda: ["general"])()
            info_lines.append(f"  {status} {name}: {', '.join(domains[:2])}")
        
        info_lines.append(f"Загружено JSON-пожертвований: {len(donations)}")
        info_lines.append("Используется система обработчиков, а не провайдеров")
        
        return "\n".join(info_lines)
    
    # PluginInterface implementation (required by WebAPIPlugin)
    @property
    def name(self) -> str:
        """Get plugin name"""
        return "intent_system"
    
    @property
    def version(self) -> str:
        """Get plugin version"""
        return "1.0.0"
    
    @property
    def description(self) -> str:
        """Get plugin description"""
        return "Intent recognition and handling system with dynamic handler discovery"
    
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router for Web API integration"""
        try:
            from fastapi import APIRouter
            
            router = APIRouter()
            
            @router.get("/status")
            async def get_intent_status():
                """Get intent system status"""
                return await self.get_status()
            
            @router.get("/handlers")
            async def get_intent_handlers():
                """Get available intent handlers"""
                if not self.handler_manager:
                    return {"error": "Intent system not initialized"}
                
                handlers_info = {}
                donations = self.handler_manager.get_donations()
                
                for name, handler in self.handler_manager.get_handlers().items():
                    handler_info = {
                        "class": handler.__class__.__name__,
                        "domains": getattr(handler, 'get_supported_domains', lambda: [])(),
                        "actions": getattr(handler, 'get_supported_actions', lambda: [])(),
                        "available": await handler.is_available() if hasattr(handler, 'is_available') else True,
                        "capabilities": getattr(handler, 'get_capabilities', lambda: {})(),
                        "has_donation": hasattr(handler, 'has_donation') and handler.has_donation(),
                        "supports_donation_routing": hasattr(handler, 'execute_with_donation_routing')
                    }
                    
                    # Add donation information if available
                    if name in donations:
                        donation = donations[name]
                        handler_info["donation"] = {
                            "domain": donation.handler_domain,
                            "methods_count": len(donation.method_donations),
                            "methods": [
                                {
                                    "name": method.method_name,
                                    "intent_suffix": method.intent_suffix,
                                    "full_intent": f"{donation.handler_domain}.{method.intent_suffix}",
                                    "parameters_count": len(method.parameters),
                                    "phrases_count": len(method.phrases)
                                }
                                for method in donation.method_donations
                            ],
                            "global_parameters_count": len(donation.global_parameters)
                        }
                    
                    handlers_info[name] = handler_info
                
                return {"handlers": handlers_info}
            
            @router.get("/registry")
            async def get_intent_registry():
                """Get intent registry patterns"""
                if not self.intent_registry:
                    return {"error": "Intent registry not initialized"}
                
                handlers = await self.intent_registry.get_all_handlers()
                patterns_info = {}
                
                for pattern, handler in handlers.items():
                    patterns_info[pattern] = {
                        "handler_class": handler.__class__.__name__,
                        "metadata": self.intent_registry.get_handler_info(pattern)
                    }
                
                return {"patterns": patterns_info}
            
            @router.post("/reload")
            async def reload_intent_handlers():
                """Reload intent handlers with current configuration"""
                if not self.handler_manager:
                    return {"error": "Intent system not initialized"}
                
                try:
                    # Handle both dict and Pydantic config objects
                    if isinstance(self._config, dict):
                        handlers_config = self._config.get("handlers", {})
                    else:
                        handlers_config = getattr(self._config, "handlers", {})
                    await self.handler_manager.reload_handlers(handlers_config)
                    
                    # Update references
                    self.intent_registry = self.handler_manager.get_registry()
                    self.intent_orchestrator = self.handler_manager.get_orchestrator()
                    
                    handlers = self.handler_manager.get_handlers()
                    return {
                        "status": "reloaded",
                        "handlers_count": len(handlers),
                        "handlers": list(handlers.keys())
                    }
                except Exception as e:
                    logger.error(f"Failed to reload intent handlers: {e}")
                    return {"error": f"Reload failed: {str(e)}"}
            
            return router
            
        except ImportError:
            logger.warning("FastAPI not available, Web API routes disabled")
            return None
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get configuration schema for Web API"""
        return {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "handlers": {
                    "type": "object",
                    "properties": {
                        "enabled": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": []
                        },
                        "disabled": {
                            "type": "array", 
                            "items": {"type": "string"},
                            "default": []
                        },
                        "auto_discover": {"type": "boolean", "default": True}
                    }
                }
            }
        }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get intent system status for Web API"""
        if not self.handler_manager:
            return {"status": "not_initialized"}
        
        handlers = self.handler_manager.get_handlers()
        donations = self.handler_manager.get_donations()
        registry_handlers = await self.intent_registry.get_all_handlers() if self.intent_registry else {}
        
        # Get orchestrator capabilities for donation information
        orchestrator_capabilities = {}
        if self.intent_orchestrator:
            orchestrator_capabilities = await self.intent_orchestrator.get_capabilities()
        
        return {
            "status": "active",
            "handlers_count": len(handlers),
            "handlers": list(handlers.keys()),
            "donations_count": len(donations),
            "donations": list(donations.keys()),
            "registry_patterns": list(registry_handlers.keys()),
            "donation_routing_enabled": orchestrator_capabilities.get("donation_routing_enabled", False),
            "parameter_extraction_integrated": orchestrator_capabilities.get("parameter_extraction_integrated", True),  # PHASE 6: Updated to reflect new architecture
            "configuration": self._config
        }
    

    
    # Helper methods for workflow integration
    def get_orchestrator(self) -> Optional[IntentOrchestrator]:
        """Get the intent orchestrator for workflow integration"""
        return self.intent_orchestrator
    
    def get_registry(self) -> Optional[IntentRegistry]:
        """Get the intent registry for direct access"""
        return self.intent_registry
    
    def get_handler_manager(self) -> Optional[IntentHandlerManager]:
        """Get the handler manager for advanced operations"""
        return self.handler_manager

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Intent component needs web API functionality"""
        return ["fastapi>=0.100.0", "uvicorn[standard]>=0.20.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Intent component has no system dependencies - coordinates providers only"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Intent component supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    # Config interface methods (Phase 3 - Configuration Architecture Cleanup)
    @classmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the Pydantic config model for this component"""
        from ..config.models import IntentSystemConfig
        return IntentSystemConfig
    
    @classmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to this component's config (V14 Architecture)"""
        return "intent_system" 