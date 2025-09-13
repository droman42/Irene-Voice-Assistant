"""
Monitoring Component - Phase 3 Integration

Integrates all Phase 3 services (notifications, metrics, memory management, 
debug tools, analytics dashboard) into the system component architecture.
"""

import logging
from typing import Dict, Any, List, Optional

from ..core.components import Component
from ..core.interfaces.webapi import WebAPIPlugin
from ..core.notifications import initialize_notification_service, get_notification_service
from ..core.metrics import initialize_metrics_system, get_metrics_collector
from ..core.memory_manager import initialize_memory_manager, get_memory_manager
from ..core.debug_tools import initialize_action_debugger, get_action_debugger
from ..core.analytics_dashboard import initialize_analytics_dashboard, get_analytics_dashboard

logger = logging.getLogger(__name__)


class MonitoringComponent(Component, WebAPIPlugin):
    """
    Monitoring Component - Phase 3 Services Integration
    
    Provides comprehensive monitoring, analytics, and management capabilities
    for fire-and-forget actions and system performance.
    
    Integrates:
    - User Notification Service (Phase 3.1)
    - Metrics and Monitoring (Phase 3.2) 
    - Memory Management (Phase 3.3)
    - Debug Tools (Phase 3.4)
    - Action Management (Phase 3.5)
    - Analytics Dashboard
    """
    
    def __init__(self):
        super().__init__()
        self.notification_service = None
        self.metrics_collector = None
        self.memory_manager = None
        self.action_debugger = None
        self.analytics_dashboard = None
        
        # Component references for integration
        self.context_manager = None
        self.intent_component = None
        
    async def initialize(self, core) -> None:
        """Initialize monitoring component with all Phase 3 services"""
        try:
            self.logger.info("Initializing Phase 3 Monitoring Component...")
            
            # Get configuration
            config = getattr(core.config, 'monitoring', None)
            if not config:
                # Create default config if missing
                self.logger.warning("No monitoring configuration found, using defaults")
                config = type('MonitoringConfig', (), {
                    'enabled': True,
                    'notifications_enabled': True,
                    'notifications_default_channel': 'log',
                    'notifications_tts_enabled': True,
                    'metrics_enabled': True,
                    'metrics_monitoring_interval': 300,
                    'metrics_retention_hours': 24,
                    'memory_management_enabled': True,
                    'memory_cleanup_interval': 1800,
                    'memory_aggressive_cleanup': False,
                    'debug_tools_enabled': True,
                    'debug_auto_inspect_failures': True,
                    'debug_max_history': 1000,
                    'analytics_dashboard_enabled': True,
                    'analytics_web_port': 8081,
                    'analytics_refresh_interval': 30
                })()
            
            # Convert Pydantic model to dict for easier access
            if hasattr(config, 'model_dump'):
                config_dict = config.model_dump()
            elif hasattr(config, 'dict'):
                config_dict = config.dict()
            else:
                config_dict = {attr: getattr(config, attr) for attr in dir(config) if not attr.startswith('_')}
            
            # Get required components
            self.context_manager = getattr(core, 'context_manager', None)
            self.intent_component = core.component_manager.get_component('intent_system')
            
            if not self.context_manager:
                raise RuntimeError("Context manager not available - required for monitoring")
            
            # Initialize Phase 3 services based on configuration
            components_dict = {
                'context_manager': self.context_manager,
                'tts': core.component_manager.get_component('tts'),
                'audio': core.component_manager.get_component('audio')
            }
            
            # Phase 3.1: Initialize Notification Service
            if config_dict.get('notifications_enabled', True):
                self.notification_service = await initialize_notification_service(components_dict)
                self.logger.info("✅ Notification service initialized")
            else:
                self.logger.info("⏭️ Notification service disabled in configuration")
            
            # Phase 3.2: Initialize Metrics System
            if config_dict.get('metrics_enabled', True):
                self.metrics_collector = await initialize_metrics_system()
                self.logger.info("✅ Metrics system initialized")
            else:
                self.logger.info("⏭️ Metrics system disabled in configuration")
            
            # Phase 3.3: Initialize Memory Manager
            if config_dict.get('memory_management_enabled', True):
                self.memory_manager = await initialize_memory_manager(self.context_manager)
                self.logger.info("✅ Memory manager initialized")
            else:
                self.logger.info("⏭️ Memory manager disabled in configuration")
            
            # Phase 3.4: Initialize Debug Tools
            if config_dict.get('debug_tools_enabled', True):
                debug_components = {
                    'context_manager': self.context_manager,
                    'metrics_collector': self.metrics_collector,
                    'notification_service': self.notification_service
                }
                self.action_debugger = initialize_action_debugger(debug_components)
                self.logger.info("✅ Debug tools initialized")
            else:
                self.logger.info("⏭️ Debug tools disabled in configuration")
            
            # Phase 3.5: Initialize Analytics Dashboard
            if config_dict.get('analytics_dashboard_enabled', True):
                self.analytics_dashboard = initialize_analytics_dashboard(self.metrics_collector)
                self.logger.info("✅ Analytics dashboard initialized")
            else:
                self.logger.info("⏭️ Analytics dashboard disabled in configuration")
            
            # Integrate with intent handlers
            await self._integrate_with_intent_handlers()
            
            self.initialized = True
            self.logger.info("🎉 Phase 3 Monitoring Component fully initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize monitoring component: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown monitoring component and all services"""
        try:
            if self.memory_manager:
                await self.memory_manager.shutdown()
            
            if self.notification_service:
                await self.notification_service.stop()
            
            if self.metrics_collector:
                await self.metrics_collector.stop_monitoring()
            
            self.logger.info("Monitoring component shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during monitoring component shutdown: {e}")
    
    async def _integrate_with_intent_handlers(self) -> None:
        """Integrate Phase 3 services with intent handlers"""
        try:
            if not self.intent_component:
                self.logger.warning("Intent component not available - skipping handler integration")
                return
            
            # Get intent handler manager
            handler_manager = getattr(self.intent_component, 'handler_manager', None)
            if not handler_manager:
                self.logger.warning("Intent handler manager not available")
                return
            
            # Get all handler instances
            handlers = getattr(handler_manager, '_handler_instances', {})
            
            # Inject Phase 3 services into each handler
            for handler_name, handler in handlers.items():
                try:
                    # Inject notification service
                    if hasattr(handler, 'set_notification_service'):
                        await handler.set_notification_service(self.notification_service)
                    
                    # Inject metrics collector
                    if hasattr(handler, 'set_metrics_collector'):
                        handler.set_metrics_collector(self.metrics_collector)
                    
                    # Inject action debugger
                    if hasattr(handler, 'set_action_debugger'):
                        handler.set_action_debugger(self.action_debugger)
                    
                    self.logger.debug(f"Integrated Phase 3 services with handler: {handler_name}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to integrate with handler {handler_name}: {e}")
            
            self.logger.info(f"Integrated Phase 3 services with {len(handlers)} intent handlers")
            
        except Exception as e:
            self.logger.error(f"Failed to integrate with intent handlers: {e}")
    
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with monitoring endpoints"""
        try:
            from fastapi import APIRouter, HTTPException
            from pydantic import BaseModel
            from typing import Dict, Any, List
            
            router = APIRouter()
            
            # Response models
            class MonitoringStatusResponse(BaseModel):
                status: str
                services: Dict[str, bool]
                uptime: float
                
            class MetricsResponse(BaseModel):
                system_metrics: Dict[str, Any]
                domain_metrics: Dict[str, Any]
                performance_summary: Dict[str, Any]
                
            class MemoryStatusResponse(BaseModel):
                memory_usage: Dict[str, Any]
                cleanup_needed: Dict[str, bool]
                recommendations: List[Dict[str, Any]]
                
            class NotificationResponse(BaseModel):
                success: bool
                message: str
                
            class DebugResponse(BaseModel):
                debug_status: Dict[str, Any]
                inspection_history: List[Dict[str, Any]]
                
            class DashboardResponse(BaseModel):
                dashboard_data: Dict[str, Any]
                health_summary: Dict[str, Any]
            
            # Monitoring status endpoint
            @router.get("/status", response_model=MonitoringStatusResponse)
            async def get_monitoring_status():
                """Get overall monitoring system status"""
                import time
                
                services = {
                    "notification_service": self.notification_service is not None,
                    "metrics_collector": self.metrics_collector is not None,
                    "memory_manager": self.memory_manager is not None,
                    "action_debugger": self.action_debugger is not None,
                    "analytics_dashboard": self.analytics_dashboard is not None
                }
                
                return MonitoringStatusResponse(
                    status="active" if all(services.values()) else "partial",
                    services=services,
                    uptime=time.time() - getattr(self, '_start_time', time.time())
                )
            
            # Metrics endpoints
            @router.get("/metrics", response_model=MetricsResponse)
            async def get_metrics():
                """Get comprehensive system metrics"""
                if not self.metrics_collector:
                    raise HTTPException(status_code=503, detail="Metrics collector not available")
                
                return MetricsResponse(
                    system_metrics=self.metrics_collector.get_system_metrics(),
                    domain_metrics=self.metrics_collector.get_all_domain_metrics(),
                    performance_summary=self.metrics_collector.get_performance_summary(3600)  # Last hour
                )
            
            # Memory management endpoints
            @router.get("/memory", response_model=MemoryStatusResponse)
            async def get_memory_status():
                """Get memory usage and management status"""
                if not self.memory_manager:
                    raise HTTPException(status_code=503, detail="Memory manager not available")
                
                analysis = await self.memory_manager.analyze_system_memory_usage()
                recommendations = await self.memory_manager.get_memory_recommendations()
                
                return MemoryStatusResponse(
                    memory_usage=analysis,
                    cleanup_needed={"system_cleanup": len(recommendations) > 0},
                    recommendations=recommendations
                )
            
            @router.post("/memory/cleanup")
            async def trigger_memory_cleanup(aggressive: bool = False):
                """Trigger system memory cleanup"""
                if not self.memory_manager:
                    raise HTTPException(status_code=503, detail="Memory manager not available")
                
                result = await self.memory_manager.perform_system_cleanup(aggressive=aggressive)
                return result
            
            # Notification endpoints
            @router.post("/notifications/test", response_model=NotificationResponse)
            async def send_test_notification():
                """Send a test notification"""
                if not self.notification_service:
                    raise HTTPException(status_code=503, detail="Notification service not available")
                
                success = await self.notification_service.send_system_status_notification(
                    title="Test Notification",
                    message="This is a test notification from the monitoring system"
                )
                
                return NotificationResponse(
                    success=success,
                    message="Test notification sent" if success else "Failed to send notification"
                )
            
            # Debug endpoints
            @router.get("/debug", response_model=DebugResponse)
            async def get_debug_status():
                """Get debugging system status"""
                if not self.action_debugger:
                    raise HTTPException(status_code=503, detail="Action debugger not available")
                
                return DebugResponse(
                    debug_status=self.action_debugger.get_debugging_status(),
                    inspection_history=[]  # Could add recent inspections here
                )
            
            # Analytics dashboard endpoints
            @router.get("/dashboard", response_model=DashboardResponse)
            async def get_dashboard_data():
                """Get analytics dashboard data"""
                if not self.analytics_dashboard:
                    raise HTTPException(status_code=503, detail="Analytics dashboard not available")
                
                return DashboardResponse(
                    dashboard_data=self.analytics_dashboard.get_dashboard_data(),
                    health_summary=self.analytics_dashboard.get_system_health_summary()
                )
            
            @router.get("/dashboard/html")
            async def get_dashboard_html():
                """Get HTML analytics dashboard"""
                if not self.analytics_dashboard:
                    raise HTTPException(status_code=503, detail="Analytics dashboard not available")
                
                from fastapi.responses import HTMLResponse
                html_content = self.analytics_dashboard.generate_html_dashboard()
                return HTMLResponse(content=html_content)
            
            return router
            
        except ImportError:
            self.logger.warning("FastAPI not available for monitoring web API")
            return None
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for monitoring API endpoints"""
        return "/monitoring"
    
    def get_api_tags(self) -> List[str]:
        """Get OpenAPI tags for monitoring endpoints"""
        return ["Monitoring", "Phase 3", "Analytics", "Metrics", "Memory", "Debug"]
    
    def is_api_available(self) -> bool:
        """Check if FastAPI dependencies are available for web API"""
        try:
            import fastapi
            import pydantic
            return True
        except ImportError:
            return False
    
    # Component interface methods
    def get_python_dependencies(self) -> List[str]:
        """Python dependencies for monitoring component"""
        return [
            "fastapi>=0.100.0",
            "uvicorn[standard]>=0.20.0",
            "pydantic>=2.0.0"
        ]
    
    def get_component_dependencies(self) -> List[str]:
        """Component dependencies"""
        return ["intent_system"]  # Requires intent system for handler integration
    
    # Service access methods for other components
    def get_notification_service(self):
        """Get notification service instance"""
        return self.notification_service
    
    def get_metrics_collector(self):
        """Get metrics collector instance"""
        return self.metrics_collector
    
    def get_memory_manager(self):
        """Get memory manager instance"""
        return self.memory_manager
    
    def get_action_debugger(self):
        """Get action debugger instance"""
        return self.action_debugger
    
    def get_analytics_dashboard(self):
        """Get analytics dashboard instance"""
        return self.analytics_dashboard
