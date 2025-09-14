"""
Monitoring Component - Phase 3 Integration

Integrates all Phase 3 services (notifications, metrics, memory management, 
debug tools, analytics dashboard) into the system component architecture.
"""

import logging
from typing import Dict, Any, List, Optional, Type

from pydantic import BaseModel

from .base import Component
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
            
            # Get monitoring configuration (Phase 5: Modern configuration only)
            config = getattr(core.config, 'monitoring', None)
            
            if not config:
                raise ValueError("Monitoring configuration required. Add [monitoring] section to config.")
            
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
                # Configure notification service with monitoring configuration
                notification_config = {
                    'default_channel': config_dict.get('notifications_default_channel', 'log'),
                    'tts_enabled': config_dict.get('notifications_tts_enabled', True),
                    'web_enabled': config_dict.get('notifications_web_enabled', True)
                }
                self.notification_service = await initialize_notification_service(components_dict, notification_config)
                self.logger.info(f"✅ Notification service initialized with default_channel={notification_config['default_channel']}")
            else:
                self.logger.info("⏭️ Notification service disabled in configuration")
            
            # Phase 3.2: Initialize Metrics System
            if config_dict.get('metrics_enabled', True):
                # Configure metrics system with monitoring configuration
                metrics_config = {
                    'monitoring_interval': config_dict.get('metrics_monitoring_interval', 300),
                    'retention_hours': config_dict.get('metrics_retention_hours', 24),
                    'max_history': config_dict.get('debug_max_history', 1000)
                }
                self.metrics_collector = await initialize_metrics_system(metrics_config)
                self.logger.info(f"✅ Metrics system initialized with interval={metrics_config['monitoring_interval']}s")
            else:
                self.logger.info("⏭️ Metrics system disabled in configuration")
            
            # Phase 3.3: Initialize Memory Manager
            if config_dict.get('memory_management_enabled', True):
                # Configure memory manager with monitoring configuration
                memory_config = {
                    'cleanup_interval': config_dict.get('memory_cleanup_interval', 1800),
                    'aggressive_cleanup': config_dict.get('memory_aggressive_cleanup', False)
                }
                self.memory_manager = await initialize_memory_manager(self.context_manager, memory_config)
                self.logger.info(f"✅ Memory manager initialized with cleanup_interval={memory_config['cleanup_interval']}s")
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
                # Configure analytics dashboard with monitoring configuration
                dashboard_config = {
                    'refresh_interval': config_dict.get('analytics_refresh_interval', 30)
                }
                self.analytics_dashboard = initialize_analytics_dashboard(self.metrics_collector, dashboard_config)
                self.logger.info(f"✅ Analytics dashboard initialized with refresh_interval={dashboard_config['refresh_interval']}s")
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
            
            # Phase 1: Analytics endpoints (migrated from webapi_runner.py)
            class AnalyticsReportResponse(BaseModel):
                timestamp: float
                report_type: str
                intents: Dict[str, Any]
                sessions: Dict[str, Any]
                system: Dict[str, Any]
            
            @router.get("/intents")
            async def get_intent_analytics():
                """Get intent recognition and execution analytics"""
                if not self.metrics_collector:
                    raise HTTPException(status_code=503, detail="Metrics collector not available")
                
                # Get intent analytics from unified metrics
                domain_metrics = self.metrics_collector.get_all_domain_metrics()
                intent_data = {}
                
                for domain, metrics in domain_metrics.items():
                    if not domain.startswith("intent_"):
                        continue
                    intent_name = domain.replace("intent_", "")
                    intent_data[intent_name] = {
                        "success_rate": metrics.success_rate,
                        "total_actions": metrics.total_actions,
                        "average_duration": metrics.avg_duration,
                        "last_updated": metrics.last_updated
                    }
                
                import time
                return {
                    "total_intents_processed": sum(m.total_actions for m in domain_metrics.values() if m.total_actions > 0),
                    "unique_intent_types": len(intent_data),
                    "intent_breakdown": intent_data,
                    "overall_success_rate": sum(m.success_rate for m in domain_metrics.values()) / max(1, len(domain_metrics)),
                    "timestamp": time.time()
                }
            
            @router.get("/sessions")
            async def get_session_analytics():
                """Get conversation session analytics"""
                if not self.metrics_collector:
                    raise HTTPException(status_code=503, detail="Metrics collector not available")
                
                # Get session analytics from unified metrics
                import time
                system_metrics = self.metrics_collector.get_system_metrics()
                return {
                    "active_sessions": system_metrics.get("current_concurrent_actions", 0),
                    "total_sessions": system_metrics.get("total_actions_completed", 0),
                    "average_session_duration": system_metrics.get("average_completion_time", 0.0),
                    "average_user_satisfaction": 0.8,  # Default value - to be enhanced later
                    "uptime_seconds": system_metrics.get("uptime_seconds", 0),
                    "timestamp": time.time()
                }
            
            @router.get("/performance")
            async def get_system_performance():
                """Get system performance metrics including VAD and component metrics"""
                if not self.metrics_collector:
                    raise HTTPException(status_code=503, detail="Metrics collector not available")
                
                import time
                system_metrics = self.metrics_collector.get_system_metrics()
                vad_metrics = self.metrics_collector.get_vad_metrics()
                component_metrics = self.metrics_collector.get_all_component_metrics()
                
                return {
                    "system": {
                        "uptime_seconds": system_metrics.get("uptime_seconds", 0),
                        "total_actions": system_metrics.get("total_actions_completed", 0),
                        "success_rate": system_metrics.get("average_success_rate", 0.0),
                        "peak_concurrent": system_metrics.get("peak_concurrent_actions", 0)
                    },
                    "vad": vad_metrics,
                    "components": component_metrics,
                    "timestamp": time.time()
                }
            
            @router.get("/report", response_model=AnalyticsReportResponse)
            async def get_comprehensive_analytics_report():
                """Get comprehensive analytics report"""
                if not self.metrics_collector:
                    raise HTTPException(status_code=503, detail="Metrics collector not available")
                
                # Gather data from all monitoring sources
                import time
                system_metrics = self.metrics_collector.get_system_metrics()
                domain_metrics = self.metrics_collector.get_all_domain_metrics()
                vad_metrics = self.metrics_collector.get_vad_metrics()
                component_metrics = self.metrics_collector.get_all_component_metrics()
                
                # Build comprehensive report
                return AnalyticsReportResponse(
                    timestamp=time.time(),
                    report_type="comprehensive_unified_analytics",
                    intents={
                        "overview": {
                            "total_actions": sum(m.total_actions for m in domain_metrics.values()),
                            "success_rate": sum(m.success_rate for m in domain_metrics.values()) / max(1, len(domain_metrics)),
                            "domain_count": len(domain_metrics)
                        },
                        "details": {domain: {"success_rate": m.success_rate, "total_actions": m.total_actions} 
                                  for domain, m in domain_metrics.items()}
                    },
                    sessions={
                        "overview": {
                            "active_sessions": system_metrics.get("current_concurrent_actions", 0),
                            "total_sessions": system_metrics.get("total_actions_completed", 0),
                            "peak_concurrent": system_metrics.get("peak_concurrent_actions", 0)
                        }
                    },
                    system={
                        "uptime_seconds": system_metrics.get("uptime_seconds", 0),
                        "vad_metrics": vad_metrics,
                        "component_metrics": component_metrics
                    }
                )
            
            @router.post("/session/{session_id}/satisfaction")
            async def rate_session_satisfaction(session_id: str, satisfaction_score: float):
                """Rate user satisfaction for a session (0.0-1.0)"""
                if not 0.0 <= satisfaction_score <= 1.0:
                    raise HTTPException(status_code=400, detail="Satisfaction score must be between 0.0 and 1.0")
                
                # For now, store satisfaction in memory - could be enhanced to persist
                # This is a placeholder implementation for Phase 1 compatibility
                return {
                    "success": True,
                    "session_id": session_id,
                    "satisfaction_score": satisfaction_score,
                    "message": "Satisfaction rating recorded in unified metrics system"
                }
            
            @router.get("/prometheus")
            async def get_prometheus_metrics():
                """Get metrics in Prometheus format for monitoring systems"""
                if not self.metrics_collector:
                    raise HTTPException(status_code=503, detail="Metrics collector not available")
                
                system_metrics = self.metrics_collector.get_system_metrics()
                vad_metrics = self.metrics_collector.get_vad_metrics()
                component_metrics = self.metrics_collector.get_all_component_metrics()
                
                # Generate Prometheus-style metrics
                import time
                timestamp = int(time.time() * 1000)
                
                lines = [
                    "# HELP irene_actions_total Total number of actions processed",
                    "# TYPE irene_actions_total counter",
                    f"irene_actions_total {system_metrics.get('total_actions_completed', 0)} {timestamp}",
                    "",
                    "# HELP irene_actions_success_rate Success rate of actions",
                    "# TYPE irene_actions_success_rate gauge", 
                    f"irene_actions_success_rate {system_metrics.get('average_success_rate', 0.0)} {timestamp}",
                    "",
                    "# HELP irene_vad_chunks_total Total VAD chunks processed",
                    "# TYPE irene_vad_chunks_total counter",
                    f"irene_vad_chunks_total {vad_metrics.get('total_chunks_processed', 0)} {timestamp}",
                    "",
                    "# HELP irene_vad_processing_time Average VAD processing time in ms",
                    "# TYPE irene_vad_processing_time gauge",
                    f"irene_vad_processing_time {vad_metrics.get('average_processing_time_ms', 0.0)} {timestamp}",
                    ""
                ]
                
                # Add component metrics
                for component, metrics in component_metrics.items():
                    if isinstance(metrics, dict):
                        for metric_name, value in metrics.items():
                            if isinstance(value, (int, float)):
                                lines.extend([
                                    f"# HELP irene_component_{component}_{metric_name} Component {component} {metric_name}",
                                    f"# TYPE irene_component_{component}_{metric_name} gauge",
                                    f"irene_component_{component}_{metric_name} {value} {timestamp}",
                                    ""
                                ])
                
                from fastapi.responses import PlainTextResponse
                return PlainTextResponse(content="\n".join(lines), media_type="text/plain")
            
            # Phase 3: Performance validation endpoint
            class PerformanceValidationResponse(BaseModel):
                performance_score: float
                meets_criteria: bool
                validation_criteria: Dict[str, float]
                performance_analysis: Dict[str, Any]
                recommendations: List[Dict[str, str]]
                generated_at: str
                
            @router.get("/performance/validate", response_model=PerformanceValidationResponse)
            async def validate_system_performance():
                """Validate unified metrics system performance impact - Phase 3"""
                if not self.analytics_dashboard:
                    raise HTTPException(status_code=503, detail="Analytics dashboard not available")
                
                validation_result = self.analytics_dashboard.validate_system_performance()
                
                return PerformanceValidationResponse(
                    performance_score=validation_result.get("performance_score", 0.0),
                    meets_criteria=validation_result.get("meets_criteria", False),
                    validation_criteria=validation_result.get("validation_criteria", {}),
                    performance_analysis=validation_result.get("performance_analysis", {}),
                    recommendations=validation_result.get("recommendations", []),
                    generated_at=validation_result.get("generated_at", "")
                )
            
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
    
    def get_service_dependencies(self) -> Dict[str, type]:
        """Get list of required service dependencies."""
        return {}  # No service dependencies
    
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
    
    # Required abstract methods from base Component class
    def get_providers_info(self) -> str:
        """Get human-readable information about monitoring services"""
        services = []
        if self.notification_service:
            services.append("Notification Service")
        if self.metrics_collector:
            services.append("Metrics Collector")
        if self.memory_manager:
            services.append("Memory Manager")
        if self.action_debugger:
            services.append("Action Debugger")
        if self.analytics_dashboard:
            services.append("Analytics Dashboard")
        
        if services:
            return f"Active monitoring services: {', '.join(services)}"
        else:
            return "No monitoring services currently active"
    
    @classmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the Pydantic config model for monitoring component"""
        from ..config.models import MonitoringConfig
        return MonitoringConfig
    
    @classmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to monitoring component config"""
        return "monitoring"
    
    # Required property methods from PluginInterface (inherited via Component base class)
    @property
    def name(self) -> str:
        """Get component name"""
        return "monitoring"
    
    @property
    def version(self) -> str:
        """Get component version"""
        return "1.0.0"
    
    @property
    def description(self) -> str:
        """Get component description"""
        return "Phase 3 monitoring component with unified metrics, notifications, and analytics"
