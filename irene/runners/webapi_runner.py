"""
Web API Runner - FastAPI server for Irene

Replaces legacy runva_webapi.py with modern async FastAPI architecture.
Provides REST endpoints and WebSocket support for remote access.
Now using BaseRunner for unified patterns.
"""

import asyncio
import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import json

from ..config.models import CoreConfig, ComponentConfig, LogLevel
from ..config.manager import ConfigManager
from ..core.engine import AsyncVACore
from ..utils.loader import get_component_status
from ..utils.logging import setup_logging
from .base import BaseRunner, RunnerConfig, check_component_dependencies, print_dependency_status


logger = logging.getLogger(__name__)




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


class WebAPIRunner(BaseRunner):
    """
    Web API Server Runner
    
    This runner ALWAYS uses web input only, regardless of config file settings.
    It overrides any input configuration to ensure only web input is enabled.
    
    Replaces legacy runva_webapi.py with modern FastAPI architecture.
    Provides REST endpoints and WebSocket for remote assistant access.
    Now using BaseRunner for unified patterns.
    """
    
    def __init__(self):
        runner_config = RunnerConfig(
            name="WebAPI",
            description="Web API Server Mode (web input only)",
            requires_config_file=False,
            supports_interactive=False,
            required_dependencies=["fastapi", "uvicorn"]
        )
        super().__init__(runner_config)
        self.app = None
        self.web_input = None
        self._start_time = time.time()  # Track start time for uptime calculation
    
    def _add_runner_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add WebAPI-specific command line arguments"""
        # Server options
        parser.add_argument(
            "--host",
            default="127.0.0.1",
            help="Host to bind to (default: 127.0.0.1)"
        )
        parser.add_argument(
            "--port", "-p",
            type=int,
            default=None,  # Will be set from config if not provided
            help="Port to bind to (default: from config or 8000)"
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
        
        # CORS options
        parser.add_argument(
            "--cors-origins",
            nargs="*",
            default=["http://localhost:3000", "http://127.0.0.1:3000"],
            help="Allowed CORS origins"
        )
        
        # Web component options
        parser.add_argument(
            "--enable-tts",
            action="store_true",
            default=True,
            help="Enable TTS output (default: True)"
        )
    
    def _get_usage_examples(self) -> str:
        """Get usage examples for WebAPI runner"""
        return """
Examples:
  %(prog)s                           # Start on default host:port (from config or 8000)
  %(prog)s --host 0.0.0.0 --port 8080 # Custom host and port (overrides config)
  %(prog)s --ssl-cert cert.pem       # Enable HTTPS (web input only)
  %(prog)s --enable-tts              # Enable TTS for audio responses (default: enabled)
  %(prog)s --cors-origins "*"        # Allow all CORS origins

Note: WebAPI runner always uses web input only, regardless of config file settings.
Port priority: command line > config file > default (8000)
        """
    
    async def _check_dependencies(self, args: argparse.Namespace) -> bool:
        """Check WebAPI runner dependencies"""
        if args.check_deps:
            return check_webapi_dependencies()
        
        # For normal operation, check that FastAPI/uvicorn are available
        try:
            import fastapi  # type: ignore
            import uvicorn  # type: ignore
            return True
        except ImportError:
            if not args.quiet:
                print("❌ Web API dependencies missing")
                print("💡 Install with: uv add irene-voice-assistant[web-api]")
            return False
    
    async def _modify_config_for_runner(self, config: CoreConfig, args: argparse.Namespace) -> CoreConfig:
        """Modify configuration for WebAPI-specific needs"""
        # Enable web API service capability
        config.system.web_api_enabled = True
        
        # Set port from command line args or config, with fallback to 8000
        if args.port is not None:
            # Command line argument takes precedence
            args.port = args.port
        elif hasattr(config.system, 'web_port') and config.system.web_port:
            # Use configuration value
            args.port = config.system.web_port
        else:
            # Fallback to 8000 (same as config default)
            args.port = 8000
        
        # WebAPI Runner ALWAYS forces web-only input configuration
        # This overrides any input configuration from the config file
        config.inputs.microphone = False
        config.inputs.web = True
        config.inputs.cli = False
        config.inputs.default_input = "web"
        
        # Override microphone enablement regardless of --enable-microphone flag
        # WebAPI should only use web input, not direct microphone access
        config.system.microphone_enabled = False
        
        # Configure components (using correct v14 field names)
        config.components.tts = args.enable_tts     # Enable TTS for audio responses  
        config.components.audio = args.enable_tts   # Audio required when TTS is enabled
        config.components.intent_system = True      # Essential for processing requests
        config.components.asr = True                # Enable ASR for file upload transcription
        config.components.voice_trigger = False     # No wake word in web-only mode
        
        # Enable text processing for web requests
        config.components.text_processor = True
        config.components.nlu = True
        config.components.monitoring = True         # Enable monitoring for web API
        
        config.debug = args.debug
        
        return config
    
    async def _validate_runner_specific_config(self, config: CoreConfig, args: argparse.Namespace) -> List[str]:
        """Validate WebAPI-specific configuration requirements"""
        errors = []
        
        # WebAPI runner requires web API service to be enabled
        if not config.system.web_api_enabled:
            errors.append("Web API service must be enabled for WebAPI runner (system.web_api_enabled = true)")
        
        # Web input source should be enabled
        if not config.inputs.web:
            errors.append("Web input source must be enabled for WebAPI runner (inputs.web = true)")
        
        # Essential components must be enabled
        if not config.components.intent_system:
            errors.append("Intent system component must be enabled for WebAPI runner (components.intent_system = true)")
        
        return errors
    
    def _get_configuration_example(self) -> Optional[str]:
        """Get example configuration for WebAPI runner"""
        return """
[system]
web_api_enabled = true
web_port = 8000

[inputs]
web = true

[components]
intent_system = true
text_processor = true
nlu = true
tts = true
audio = true  # Required when TTS is enabled
asr = true    # Enables file upload transcription endpoints
monitoring = true

# Note: WebAPI runner always uses web input only.
# Other input configurations will be overridden."""
    
    async def _post_core_setup(self, args: argparse.Namespace) -> None:
        """WebAPI-specific setup after core is started"""
        # Initialize web components
        await self._setup_web_components(args)
        
        # Create FastAPI app
        self.app = await self._create_fastapi_app(args)
    
    async def _execute_runner_logic(self, args: argparse.Namespace) -> int:
        """Execute WebAPI runner logic"""
        # Start server
        return await self._start_server(args)
    
    async def _setup_web_components(self, args) -> None:
        """Setup WebInput component (output handled via unified workflow)"""
        from ..inputs.web import WebInput
        
        # Create web input (output handled by workflow via HTTP responses)
        self.web_input = WebInput(host=args.host, port=args.port)
        
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
                    <p><strong>Component WebSockets:</strong> /asr/stream (speech recognition)</p>
                    <p><strong>REST API:</strong> POST /command</p>
                </div>
                
                <script>
                    const messages = document.getElementById('messages');
                    
                    function addMessage(text, type) {
                        const div = document.createElement('div');
                        div.className = 'message' + (type === 'error' ? ' error' : '');
                        div.textContent = new Date().toLocaleTimeString() + ': ' + text;
                        messages.appendChild(div);
                        messages.scrollTop = messages.scrollHeight;
                    }
                    
                    async function sendCommand() {
                        const input = document.getElementById('commandInput');
                        const command = input.value.trim();
                        if (command) {
                            try {
                                const response = await fetch('/command', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                    },
                                    body: JSON.stringify({command: command})
                                });
                                const result = await response.json();
                                addMessage(result.response || result.error || 'Command processed', result.success ? 'info' : 'error');
                            } catch (error) {
                                addMessage('Error sending command: ' + error.message, 'error');
                            }
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
            web_clients = 0  # WebSocket clients now handled by individual components
            
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
        
        return app
    
    async def _mount_component_routers(self, app):
        """Mount component routers following the universal plugin pattern"""
        if not self.core:
            logger.warning("Core not available for router mounting")
            return
        
        try:
            from ..core.interfaces.webapi import WebAPIPlugin
            
            # Get all components that implement WebAPIPlugin
            web_components = []
            
            logger.info("Searching for components with WebAPI support...")
            
            # Check if component manager has components that implement WebAPIPlugin
            if hasattr(self.core, 'component_manager'):
                try:
                    available_components = self.core.component_manager.get_components()
                    logger.info(f"Found {len(available_components)} available components: {list(available_components.keys())}")
                    
                    for name, component in available_components.items():
                        if isinstance(component, WebAPIPlugin):
                            web_components.append((name, component))
                            logger.info(f"Component {name} implements WebAPIPlugin")
                        else:
                            logger.debug(f"Component {name} does not implement WebAPIPlugin (type: {type(component).__name__})")
                            
                except Exception as e:
                    logger.warning(f"Could not get components from component manager: {e}")
            else:
                logger.warning("Core does not have component_manager")
            
            # Also check plugins that implement WebAPIPlugin
            if hasattr(self.core, 'plugin_manager'):
                try:
                    plugin_count = len(self.core.plugin_manager._plugins)
                    logger.info(f"Found {plugin_count} plugins in plugin manager")
                    
                    for name, plugin in self.core.plugin_manager._plugins.items():
                        if isinstance(plugin, WebAPIPlugin):
                            web_components.append((name, plugin))
                            logger.info(f"Plugin {name} implements WebAPIPlugin")
                        else:
                            logger.debug(f"Plugin {name} does not implement WebAPIPlugin (type: {type(plugin).__name__})")
                            
                except Exception as e:
                    logger.warning(f"Could not get plugins from plugin manager: {e}")
            else:
                logger.warning("Core does not have plugin_manager")
            
            logger.info(f"Found {len(web_components)} components/plugins with WebAPI support")
            
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
                        logger.info(f"✅ Mounted {name} router at {prefix} with tags {tags}")
                    else:
                        logger.warning(f"Component {name} returned no router")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to mount router for {name}: {e}")
            
            if mounted_count > 0:
                logger.info(f"✅ Successfully mounted {mounted_count} component routers")
            else:
                logger.warning("⚠️ No component routers were mounted - check component configuration and WebAPIPlugin implementation")
            
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
                    # Get actual enabled handlers from intent component
                    handlers = []
                    if self.core and hasattr(self.core, 'components') and 'intent_system' in self.core.components:
                        intent_component = self.core.components['intent_system']
                        if hasattr(intent_component, 'handler_manager') and intent_component.handler_manager:
                            handlers = list(intent_component.handler_manager.get_handlers().keys())
                    
                    # Fallback if intent system not available
                    if not handlers:
                        handlers = ["intent_system_not_initialized"]
                    
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
                        "intent_handlers": [],
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
                    
                    # Web client information now handled by individual components
                    status["web_clients"] = 0  # Component-specific WebSockets handle client tracking
                    
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
            
            # Phase 1: Analytics endpoints removed - migrated to /monitoring/* in MonitoringComponent
            
            logger.info("Analytics endpoints removed - migrated to /monitoring/* in MonitoringComponent")
            
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
            print(f"🌐 Starting Web API server at {protocol}://{args.host}:{args.port} (web input only)")
            print(f"📚 API docs available at {protocol}://{args.host}:{args.port}/docs")
            print(f"🌍 Web interface at {protocol}://{args.host}:{args.port}")
            print(f"🔌 Component WebSockets: /asr/stream (speech recognition)")
            print("💻 Input mode: Web only (other inputs disabled)")
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


if __name__ == "__main__":
    sys.exit(run_webapi()) 