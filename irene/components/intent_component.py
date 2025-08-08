"""
Intent Component - Intent system integration with component architecture

This component wraps the IntentHandlerManager and provides the intent system
(registry, orchestrator, handlers) as a unified component that can be
integrated into workflows and the component lifecycle.
"""

import logging
from typing import Dict, Any, List, Optional

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
        
        # Get intent handler configuration
        intent_config = getattr(core.config, 'intents', {})
        
        # Default configuration if not provided
        if not intent_config:
            intent_config = {
                "enabled": True,
                "handlers": {
                    "enabled": ["conversation", "greetings", "timer", "datetime", "system"],
                    "disabled": ["train_schedule"],
                    "auto_discover": True
                }
            }
        
        self._config = intent_config
        
        # Initialize intent handler manager
        self.handler_manager = IntentHandlerManager()
        handler_config = intent_config.get("handlers", {})
        
        await self.handler_manager.initialize(handler_config)
        
        # Get registry and orchestrator from manager
        self.intent_registry = self.handler_manager.get_registry()
        self.intent_orchestrator = self.handler_manager.get_orchestrator()
        
        # Log initialization status
        handlers = self.handler_manager.get_handlers()
        logger.info(f"Intent component initialized with {len(handlers)} handlers: {list(handlers.keys())}")
        
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
        
    def get_dependencies(self) -> List[str]:
        """Intent system has no external dependencies"""
        return []  # No external dependencies required
    
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
                for name, handler in self.handler_manager.get_handlers().items():
                    handlers_info[name] = {
                        "class": handler.__class__.__name__,
                        "domains": getattr(handler, 'get_supported_domains', lambda: [])(),
                        "actions": getattr(handler, 'get_supported_actions', lambda: [])(),
                        "available": await handler.is_available() if hasattr(handler, 'is_available') else True,
                        "capabilities": getattr(handler, 'get_capabilities', lambda: {})()
                    }
                
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
                    await self.handler_manager.reload_handlers(self._config.get("handlers", {}))
                    
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
                            "default": ["conversation", "greetings", "timer", "datetime", "system"]
                        },
                        "disabled": {
                            "type": "array", 
                            "items": {"type": "string"},
                            "default": ["train_schedule"]
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
        registry_handlers = await self.intent_registry.get_all_handlers() if self.intent_registry else {}
        
        return {
            "status": "active",
            "handlers_count": len(handlers),
            "handlers": list(handlers.keys()),
            "registry_patterns": list(registry_handlers.keys()),
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