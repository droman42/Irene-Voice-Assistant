"""
Web API Runner - FastAPI server for Irene

Replaces legacy runva_webapi.py with modern async FastAPI architecture.
Provides REST endpoints and WebSocket support for remote access.
"""

import asyncio
import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any
import json

from ..config.models import CoreConfig, ComponentConfig, LogLevel
from ..config.manager import ConfigManager
from ..core.engine import AsyncVACore
from ..utils.loader import get_component_status
from ..utils.logging import setup_logging


logger = logging.getLogger(__name__)


def setup_webapi_argument_parser() -> argparse.ArgumentParser:
    """Setup Web API specific argument parser"""
    parser = argparse.ArgumentParser(
        description="Irene Voice Assistant v13 - Web API Server Mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Start on default host:port
  %(prog)s --host 0.0.0.0 --port 8080 # Custom host and port
  %(prog)s --ssl-cert cert.pem       # Enable HTTPS
        """
    )
    
    # Configuration options
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=Path("config.toml"),
        help="Configuration file path (default: config.toml)"
    )
    
    # Server options
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=5003,
        help="Port to bind to (default: 5003)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )
    
    # SSL options
    parser.add_argument(
        "--ssl-cert",
        type=Path,
        help="SSL certificate file path"
    )
    parser.add_argument(
        "--ssl-key",
        type=Path,
        help="SSL private key file path"
    )
    
    # Development options
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    # CORS options
    parser.add_argument(
        "--cors-origins",
        nargs="*",
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        help="Allowed CORS origins"
    )
    
    # Logging options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress startup messages"
    )
    
    # Web component options
    parser.add_argument(
        "--enable-microphone",
        action="store_true",
        help="Enable microphone input for web API"
    )
    parser.add_argument(
        "--enable-tts",
        action="store_true",
        default=True,
        help="Enable TTS output (default: True)"
    )
    
    return parser


def check_webapi_dependencies() -> bool:
    """Check if Web API dependencies are available"""
    try:
        import fastapi  # type: ignore
        import uvicorn  # type: ignore
        logger.info("✅ Web API dependencies available")
        return True
    except ImportError as e:
        logger.error(f"❌ Web API dependencies missing: {e}")
        print("💡 Install with: uv add irene-voice-assistant[web-api]")
        return False


class WebAPIRunner:
    """
    Web API Server Runner
    
    Replaces legacy runva_webapi.py with modern FastAPI architecture.
    Provides REST endpoints and WebSocket for remote assistant access.
    """
    
    def __init__(self):
        self.core: Optional[AsyncVACore] = None
        self.app = None
        self.web_input = None
        self.web_output = None
        self._start_time = time.time()  # Track start time for uptime calculation
        
    async def run(self, args: Optional[list[str]] = None) -> int:
        """Run Web API server mode"""
        # Load environment variables from .env file first
        from dotenv import load_dotenv
        load_dotenv()
        
        # Parse arguments
        parser = setup_webapi_argument_parser()
        parsed_args = parser.parse_args(args)
        
        # Set up centralized logging to logs/irene.log
        log_level = LogLevel(parsed_args.log_level)
        setup_logging(
            level=log_level,
            log_file=Path("logs/irene.log"),
            enable_console=True
        )
        
        try:
            # Check dependencies
            if not check_webapi_dependencies():
                return 1
            
            # Create assistant configuration (enable web API)
            config = await self._create_webapi_config(parsed_args)
            
            # Create and start assistant
            self.core = AsyncVACore(config)
            
            if not parsed_args.quiet:
                print("🔧 Initializing Irene Web API...")
            await self.core.start()
            
            # Initialize web components
            await self._setup_web_components(parsed_args)
            
            # Create FastAPI app
            self.app = await self._create_fastapi_app(parsed_args)
            
            # Start server
            return await self._start_server(parsed_args)
            
        except Exception as e:
            logger.error(f"Web API Runner error: {e}")
            return 1
        finally:
            if self.core:
                await self.core.stop()
    
    async def _create_webapi_config(self, args) -> CoreConfig:
        """Create configuration for Web API mode"""
        # Enable web API, optionally enable other components
        components = ComponentConfig(
            microphone=args.enable_microphone,  # Optional microphone in API mode
            tts=args.enable_tts,               # Enable TTS for audio responses
            audio_output=False,                # No direct audio output in API mode
            web_api=True                       # Enable web API
        )
        
        config = CoreConfig(
            components=components,
            debug=args.debug
        )
        
        return config
    
    async def _setup_web_components(self, args) -> None:
        """Setup WebInput component (output handled via unified workflow)"""
        from ..inputs.web import WebInput
        
        # Create web input (output handled by workflow via HTTP responses)
        self.web_input = WebInput(host=args.host, port=args.port)
        self.web_output = None  # Web output handled via HTTP responses, not separate component
        
        # Add to core managers
        if self.core:
            # Add web input source
            await self.core.input_manager.add_source("web", self.web_input)
            await self.core.input_manager.start_source("web")
            
            logger.info("✅ Web components initialized")
    
    async def _create_fastapi_app(self, args):
        """Create and configure FastAPI application"""
        from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect  # type: ignore
        from fastapi.middleware.cors import CORSMiddleware  # type: ignore
        from fastapi.responses import HTMLResponse  # type: ignore
        from pydantic import BaseModel  # type: ignore
        
        # Create FastAPI app
        app = FastAPI(
            title="Irene Voice Assistant API",
            description="Modern async voice assistant API with WebSocket support",
            version="13.0.0",
            debug=args.debug
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=args.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Pydantic models
        class CommandRequest(BaseModel):
            command: str
            context: Optional[Dict[str, Any]] = None
        
        class CommandResponse(BaseModel):
            success: bool
            response: Optional[str] = None
            error: Optional[str] = None
            metadata: Optional[Dict[str, Any]] = None
        
        class StatusResponse(BaseModel):
            status: str
            components: Dict[str, Any]
            web_clients: int
            
        class HistoryResponse(BaseModel):
            messages: list[Dict[str, Any]]
            total_count: int
        
        # Root endpoint
        @app.get("/", response_class=HTMLResponse)
        async def root():
            """Serve a simple web interface"""
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Irene Voice Assistant API</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .container { max-width: 800px; }
                    .command-form { margin: 20px 0; }
                    .command-input { width: 60%; padding: 10px; }
                    .send-btn { padding: 10px 20px; background: #007cba; color: white; border: none; cursor: pointer; }
                    .messages { border: 1px solid #ccc; height: 300px; overflow-y: scroll; padding: 10px; margin: 20px 0; }
                    .message { margin: 5px 0; padding: 5px; border-left: 3px solid #007cba; }
                    .error { border-left-color: #dc3545; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🤖 Irene Voice Assistant</h1>
                    <p>Modern async voice assistant API - v13.0.0</p>
                    
                    <div class="command-form">
                        <input type="text" id="commandInput" class="command-input" placeholder="Enter command..." />
                        <button onclick="sendCommand()" class="send-btn">Send Command</button>
                    </div>
                    
                    <div id="messages" class="messages">
                        <div class="message">Connected to Irene API. Type a command above!</div>
                    </div>
                    
                    <p><strong>API Documentation:</strong> <a href="/docs">/docs</a></p>
                    <p><strong>WebSocket:</strong> /ws</p>
                    <p><strong>REST API:</strong> POST /command</p>
                </div>
                
                <script>
                    const ws = new WebSocket(`ws://${window.location.host}/ws`);
                    const messages = document.getElementById('messages');
                    
                    ws.onmessage = function(event) {
                        const data = JSON.parse(event.data);
                        addMessage(data.text || JSON.stringify(data), data.type || 'info');
                    };
                    
                    function addMessage(text, type) {
                        const div = document.createElement('div');
                        div.className = 'message' + (type === 'error' ? ' error' : '');
                        div.textContent = new Date().toLocaleTimeString() + ': ' + text;
                        messages.appendChild(div);
                        messages.scrollTop = messages.scrollHeight;
                    }
                    
                    function sendCommand() {
                        const input = document.getElementById('commandInput');
                        const command = input.value.trim();
                        if (command) {
                            ws.send(JSON.stringify({type: 'command', command: command}));
                            input.value = '';
                        }
                    }
                    
                    document.getElementById('commandInput').addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') sendCommand();
                    });
                </script>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content)
        
        # Status endpoint
        @app.get("/status", response_model=StatusResponse)
        async def get_status():
            """Get assistant status and component information"""
            components = get_component_status()
            web_clients = len(self.web_output._clients) if self.web_output else 0
            
            return StatusResponse(
                status="running",
                components=components,
                web_clients=web_clients
            )
        
        # Command execution endpoint
        @app.post("/command", response_model=CommandResponse)
        async def execute_command(request: CommandRequest):
            """Execute a voice assistant command via REST API"""
            try:
                if not self.core:
                    raise HTTPException(status_code=503, detail="Assistant not initialized")
                
                # Process command through unified workflow interface
                result = await self.core.workflow_manager.process_text_input(
                    text=request.command,
                    session_id="webapi_session",
                    wants_audio=False,
                    client_context={"source": "rest_api"}
                )
                
                return CommandResponse(
                    success=result.success,
                    response=result.text or f"Command '{request.command}' processed successfully",
                    metadata={"processed_via": "rest_api", "intent_result": result.metadata}
                )
                
            except Exception as e:
                logger.error(f"Command execution error: {e}")
                return CommandResponse(
                    success=False,
                    error=str(e)
                )
        
        # Message history endpoint
        @app.get("/history", response_model=HistoryResponse)
        async def get_message_history(limit: int = 50):
            """Get recent message history"""
            if not self.web_output:
                raise HTTPException(status_code=503, detail="Web output not available")
                
            messages = self.web_output.get_message_history(limit)
            return HistoryResponse(
                messages=messages,
                total_count=len(messages)
            )
        
        # Clear history endpoint
        @app.post("/history/clear")
        async def clear_message_history():
            """Clear message history"""
            if not self.web_output:
                raise HTTPException(status_code=503, detail="Web output not available")
                
            await self.web_output.clear_history()
            return {"message": "History cleared successfully"}
        
        # WebSocket endpoint
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time communication"""
            await websocket.accept()
            
            # Add client to web output
            if self.web_output:
                await self.web_output.add_client(websocket)
            
            # Add connection to web input
            if self.web_input:
                await self.web_input.add_websocket_connection(websocket)
            
            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_text()
                    
                    # Handle message through web input
                    if self.web_input:
                        await self.web_input.handle_websocket_message(websocket, data)
                    
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                # Remove client from components
                if self.web_output:
                    await self.web_output.remove_client(websocket)
                if self.web_input:
                    await self.web_input.remove_websocket_connection(websocket)
        
        # Health check endpoint
        @app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "version": "13.0.0",
                "timestamp": asyncio.get_event_loop().time()
            }
        
        # Mount component routers - NEW PHASE 4 FUNCTIONALITY
        await self._mount_component_routers(app)
        
        # Intent management endpoints - NEW PHASE 4 FUNCTIONALITY  
        await self._add_intent_management_endpoints(app)
        
        # Component info endpoint
        @app.get("/components")
        async def get_component_info():
            """Get detailed component information"""
            info = {}
            
            if self.web_input:
                info["web_input"] = self.web_input.get_connection_info()
            
            # Web output handled via HTTP responses (unified workflow)
            
            if self.core:
                info["core"] = {
                    "input_sources": list(self.core.input_manager._sources.keys()),
                    "workflows": list(self.core.workflow_manager.workflows.keys()),
                    "plugins": self.core.plugin_manager.plugin_count
                }
            
            return info
        
        # Shutdown event
        @app.on_event("shutdown")
        async def shutdown_event():
            """Handle app shutdown"""
            logger.info("Shutting down Web API server")
            
            # Clean up web components
            if self.web_input:
                await self.web_input.stop_listening()
            
            if self.web_output:
                # Notify clients of shutdown
                await self.web_output.send_system_message("Server shutting down", "shutdown")
                # Disconnect all clients
                for client in self.web_output._clients[:]:
                    try:
                        await client.close()
                    except:
                        pass
        
        return app
    
    async def _mount_component_routers(self, app):
        """Mount component routers following the universal plugin pattern"""
        if not self.core:
            return
        
        try:
            from ..core.interfaces.webapi import WebAPIPlugin
            
            # Get all components that implement WebAPIPlugin
            web_components = []
            
            # Check if component manager has components that implement WebAPIPlugin
            if hasattr(self.core, 'component_manager'):
                try:
                    available_components = await self.core.component_manager.get_available_components()
                    for name, component in available_components.items():
                        if isinstance(component, WebAPIPlugin):
                            web_components.append((name, component))
                except Exception as e:
                    logger.warning(f"Could not get components from component manager: {e}")
            
            # Also check plugins that implement WebAPIPlugin
            if hasattr(self.core, 'plugin_manager'):
                for name, plugin in self.core.plugin_manager._plugins.items():
                    if isinstance(plugin, WebAPIPlugin):
                        web_components.append((name, plugin))
            
            # Mount each component's router
            mounted_count = 0
            for name, component in web_components:
                try:
                    router = component.get_router()
                    if router:
                        prefix = component.get_api_prefix()
                        tags = component.get_api_tags()
                        
                        app.include_router(
                            router,
                            prefix=prefix,
                            tags=tags
                        )
                        
                        mounted_count += 1
                        logger.info(f"Mounted {name} router at {prefix}")
                        
                except Exception as e:
                    logger.error(f"Failed to mount router for {name}: {e}")
            
            logger.info(f"Successfully mounted {mounted_count} component routers")
            
        except ImportError:
            logger.warning("FastAPI not available, skipping router mounting")
        except Exception as e:
            logger.error(f"Error mounting component routers: {e}")
    
    async def _add_intent_management_endpoints(self, app):
        """Add high-level intent management endpoints"""
        try:
            from fastapi import HTTPException  # type: ignore
            from pydantic import BaseModel  # type: ignore
            from typing import Dict, Any, Optional, List
            
            # Request/Response models for intent management
            class IntentExecutionRequest(BaseModel):
                text: str
                session_id: str = "default"
                context: Optional[Dict[str, Any]] = None
                wants_audio: bool = False  # Support TTS output for all entry points
                skip_wake_word: bool = True
                
            class IntentExecutionResponse(BaseModel):
                success: bool
                intent_name: str
                confidence: float
                response_text: str
                metadata: Dict[str, Any]
                error: Optional[str] = None
                
            class SystemCapabilitiesResponse(BaseModel):
                version: str
                components: Dict[str, Any]
                intent_handlers: List[str]
                nlu_providers: List[str]
                voice_trigger_providers: List[str]
                text_processing_providers: List[str]
                workflows: List[str]
                
            @app.post("/intents/execute", response_model=IntentExecutionResponse)
            async def execute_intent_directly(request: IntentExecutionRequest):
                """Direct intent execution endpoint"""
                try:
                    if not self.core:
                        raise HTTPException(status_code=503, detail="Assistant not initialized")
                    
                    # Use unified workflow interface (no more dual-path)
                    result = await self.core.workflow_manager.process_text_input(
                        text=request.text,
                        session_id=request.session_id,
                        wants_audio=request.wants_audio,
                        client_context={"source": "webapi_intent"}
                    )
                    
                    return IntentExecutionResponse(
                        success=result.success,
                        intent_name=request.text,  # Would need actual intent name from result
                        confidence=result.confidence,
                        response_text=result.text,
                        metadata=result.metadata,
                        error=result.error
                    )
                    
                except Exception as e:
                    logger.error(f"Intent execution error: {e}")
                    return IntentExecutionResponse(
                        success=False,
                        intent_name="error",
                        confidence=0.0,
                        response_text="Sorry, there was an error processing your request.",
                        metadata={},
                        error=str(e)
                    )
            
            @app.get("/intents/handlers")
            async def get_intent_handlers():
                """Get available intent handlers"""
                try:
                    # This would integrate with the intent registry
                    # For now, return basic information
                    handlers = [
                        "conversation", "greetings", "timer", "datetime", "system"
                    ]
                    
                    return {
                        "handlers": handlers,
                        "total": len(handlers),
                        "description": "Available intent handlers in the system"
                    }
                    
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            @app.get("/system/capabilities", response_model=SystemCapabilitiesResponse)
            async def get_system_capabilities():
                """Get comprehensive system capabilities"""
                try:
                    capabilities = {
                        "version": "13.0.0",
                        "components": {},
                        "intent_handlers": ["conversation", "greetings", "timer"],
                        "nlu_providers": ["hybrid_keyword_matcher", "spacy_nlu"],
                        "voice_trigger_providers": ["openwakeword"],
                        "text_processing_providers": ["unified", "number"],
                        "workflows": ["voice_assistant", "continuous_listening"]
                    }
                    
                    # Get component status if available
                    if self.core and hasattr(self.core, 'component_manager'):
                        try:
                            component_status = await self.core.component_manager.get_available_components()
                            capabilities["components"] = {
                                name: {"available": True, "type": type(comp).__name__}
                                for name, comp in component_status.items()
                            }
                        except Exception as e:
                            logger.warning(f"Could not get component status: {e}")
                    
                    return SystemCapabilitiesResponse(**capabilities)
                    
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            @app.get("/system/status")
            async def get_enhanced_system_status():
                """Enhanced system status with intent system information"""
                try:
                    status = {
                        "system": "healthy",
                        "version": "13.0.0",
                        "mode": "intent_system" if hasattr(self.core, 'workflow_manager') else "legacy",
                        "timestamp": time.time(),
                        "uptime": time.time() - getattr(self, '_start_time', time.time())
                    }
                    
                    # Add component information
                    if self.core:
                        status["core"] = {
                            "running": self.core.is_running,
                            "input_sources": len(getattr(self.core.input_manager, '_sources', {})),
                            "plugins": getattr(self.core.plugin_manager, 'plugin_count', 0)
                        }
                    
                    # Add web client information  
                    if self.web_output:
                        status["web_clients"] = len(self.web_output._clients)
                    
                    return status
                    
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            # Analytics and monitoring endpoints - NEW PHASE 4 FUNCTIONALITY
            await self._add_analytics_endpoints(app)
            
            logger.info("Added intent management endpoints")
            
        except ImportError:
            logger.warning("FastAPI not available for intent management endpoints")
        except Exception as e:
            logger.error(f"Error adding intent management endpoints: {e}")
    
    async def _add_analytics_endpoints(self, app):
        """Add analytics and monitoring endpoints"""
        try:
            from fastapi import HTTPException  # type: ignore
            from pydantic import BaseModel  # type: ignore
            from typing import Dict, Any
            
            # Response models for analytics
            class AnalyticsReportResponse(BaseModel):
                timestamp: float
                report_type: str
                intents: Dict[str, Any]
                sessions: Dict[str, Any]
                system: Dict[str, Any]
            
            @app.get("/analytics/intents")
            async def get_intent_analytics():
                """Get intent recognition and execution analytics"""
                try:
                    # Check if we have analytics manager
                    analytics_manager = getattr(self.core, 'analytics_manager', None)
                    if not analytics_manager:
                        return {
                            "error": "Analytics not available",
                            "message": "Analytics manager not initialized",
                            "mock_data": {
                                "total_intents_processed": 0,
                                "unique_intent_types": 0,
                                "average_confidence": 0.0,
                                "overall_success_rate": 0.0
                            }
                        }
                    
                    return await analytics_manager.get_intent_analytics()
                    
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            @app.get("/analytics/sessions")
            async def get_session_analytics():
                """Get conversation session analytics"""
                try:
                    analytics_manager = getattr(self.core, 'analytics_manager', None)
                    if not analytics_manager:
                        return {
                            "error": "Analytics not available",
                            "message": "Analytics manager not initialized",
                            "mock_data": {
                                "active_sessions": 0,
                                "total_sessions": 0,
                                "average_session_duration": 0.0,
                                "average_user_satisfaction": 0.8
                            }
                        }
                    
                    return await analytics_manager.get_session_analytics()
                    
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            @app.get("/analytics/performance")
            async def get_system_performance():
                """Get system performance metrics"""
                try:
                    analytics_manager = getattr(self.core, 'analytics_manager', None)
                    if not analytics_manager:
                        uptime = time.time() - self._start_time
                        return {
                            "error": "Analytics not available",
                            "message": "Analytics manager not initialized",
                            "basic_metrics": {
                                "uptime_seconds": uptime,
                                "web_clients": len(self.web_output._clients) if self.web_output else 0,
                                "system_status": "running"
                            }
                        }
                    
                    return await analytics_manager.get_system_performance()
                    
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            @app.get("/analytics/report", response_model=AnalyticsReportResponse)
            async def get_comprehensive_analytics_report():
                """Get comprehensive analytics report"""
                try:
                    analytics_manager = getattr(self.core, 'analytics_manager', None)
                    if not analytics_manager:
                        # Return mock comprehensive report
                        uptime = time.time() - self._start_time
                        return AnalyticsReportResponse(
                            timestamp=time.time(),
                            report_type="mock_comprehensive_analytics",
                            intents={
                                "overview": {
                                    "total_intents_processed": 0,
                                    "unique_intent_types": 0,
                                    "average_confidence": 0.0,
                                    "overall_success_rate": 0.0
                                }
                            },
                            sessions={
                                "overview": {
                                    "active_sessions": 0,
                                    "total_sessions": 0,
                                    "average_session_duration": 0.0,
                                    "average_user_satisfaction": 0.8
                                }
                            },
                            system={
                                "system": {
                                    "uptime_seconds": uptime,
                                    "total_requests": 0,
                                    "error_rate": 0.0
                                }
                            }
                        )
                    
                    report = await analytics_manager.generate_analytics_report()
                    return AnalyticsReportResponse(**report)
                    
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            @app.post("/analytics/session/{session_id}/satisfaction")
            async def rate_session_satisfaction(session_id: str, satisfaction_score: float):
                """Rate user satisfaction for a session (0.0-1.0)"""
                try:
                    if not 0.0 <= satisfaction_score <= 1.0:
                        raise HTTPException(status_code=400, detail="Satisfaction score must be between 0.0 and 1.0")
                    
                    analytics_manager = getattr(self.core, 'analytics_manager', None)
                    if analytics_manager:
                        # Update session satisfaction if it exists
                        if session_id in analytics_manager.session_metrics:
                            analytics_manager.session_metrics[session_id].user_satisfaction_score = satisfaction_score
                            return {
                                "success": True,
                                "session_id": session_id,
                                "satisfaction_score": satisfaction_score
                            }
                        else:
                            return {
                                "success": False,
                                "error": "Session not found",
                                "session_id": session_id
                            }
                    else:
                        return {
                            "success": False,
                            "error": "Analytics not available"
                        }
                    
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            @app.get("/metrics/prometheus")
            async def get_prometheus_metrics():
                """Get metrics in Prometheus format for monitoring systems"""
                try:
                    analytics_manager = getattr(self.core, 'analytics_manager', None)
                    
                    # Generate Prometheus-style metrics
                    metrics_lines = [
                        "# HELP irene_uptime_seconds Total uptime in seconds",
                        "# TYPE irene_uptime_seconds counter",
                        f"irene_uptime_seconds {time.time() - self._start_time}",
                        "",
                        "# HELP irene_web_clients Current number of web clients",
                        "# TYPE irene_web_clients gauge",
                        f"irene_web_clients {len(self.web_output._clients) if self.web_output else 0}",
                        ""
                    ]
                    
                    if analytics_manager:
                        intent_analytics = await analytics_manager.get_intent_analytics()
                        session_analytics = await analytics_manager.get_session_analytics()
                        
                        metrics_lines.extend([
                            "# HELP irene_intents_total Total number of intents processed",
                            "# TYPE irene_intents_total counter",
                            f"irene_intents_total {intent_analytics['overview']['total_intents_processed']}",
                            "",
                            "# HELP irene_intent_confidence_avg Average intent confidence",
                            "# TYPE irene_intent_confidence_avg gauge", 
                            f"irene_intent_confidence_avg {intent_analytics['overview']['average_confidence']}",
                            "",
                            "# HELP irene_sessions_active Current active sessions",
                            "# TYPE irene_sessions_active gauge",
                            f"irene_sessions_active {session_analytics['overview']['active_sessions']}",
                            "",
                            "# HELP irene_sessions_total Total number of sessions",
                            "# TYPE irene_sessions_total counter",
                            f"irene_sessions_total {session_analytics['overview']['total_sessions']}",
                            ""
                        ])
                    
                    return {"content_type": "text/plain", "metrics": "\n".join(metrics_lines)}
                    
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            logger.info("Added analytics and monitoring endpoints")
            
        except ImportError:
            logger.warning("FastAPI not available for analytics endpoints")
        except Exception as e:
            logger.error(f"Error adding analytics endpoints: {e}")
    
    async def _start_server(self, args) -> int:
        """Start the FastAPI server with uvicorn"""
        import uvicorn  # type: ignore
        
        if not self.app:
            logger.error("FastAPI app not initialized")
            return 1
        
        # Configure SSL if provided
        ssl_config = {}
        if args.ssl_cert and args.ssl_key:
            ssl_config = {
                "ssl_certfile": str(args.ssl_cert),
                "ssl_keyfile": str(args.ssl_key)
            }
        
        # Server configuration
        config_kwargs = {
            "app": self.app,
            "host": args.host,
            "port": args.port,
            "log_level": args.log_level.lower(),
            "reload": args.reload,
            "workers": args.workers if not args.reload else 1,
        }
        config_kwargs.update(ssl_config)
        
        config = uvicorn.Config(**config_kwargs)  # type: ignore
        
        server = uvicorn.Server(config)
        
        if not args.quiet:
            protocol = "https" if ssl_config else "http"
            print(f"🌐 Starting Web API server at {protocol}://{args.host}:{args.port}")
            print(f"📚 API docs available at {protocol}://{args.host}:{args.port}/docs")
            print(f"🌍 Web interface at {protocol}://{args.host}:{args.port}")
            print(f"🔌 WebSocket at ws://{args.host}:{args.port}/ws")
            print("Press Ctrl+C to stop")
        
        try:
            await server.serve()
            return 0
        except KeyboardInterrupt:
            if not args.quiet:
                print("\n🛑 Web API server stopped")
            return 0
        except Exception as e:
            logger.error(f"Server error: {e}")
            return 1


def run_webapi() -> int:
    """Entry point for Web API runner"""
    try:
        runner = WebAPIRunner()
        return asyncio.run(runner.run())
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        logger.error(f"Failed to start Web API runner: {e}")
        return 1 