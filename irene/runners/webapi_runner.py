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
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, Any, List
import json

from ..config.models import CoreConfig, ComponentConfig, LogLevel
from ..config.manager import ConfigManager
from ..core.engine import AsyncVACore
from ..utils.loader import get_component_status
from ..utils.logging import setup_logging
from .base import BaseRunner, RunnerConfig, check_component_dependencies, print_dependency_status
from ..web_api.asyncapi import generate_base_asyncapi_spec, merge_asyncapi_specs
from ..__version__ import __version__


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
        self._asset_loader = None  # NEW: Asset loader for web templates
    
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
        # Initialize web asset loader
        await self._setup_web_asset_loader()
        
        # Initialize web components
        await self._setup_web_components(args)
        
        # Create FastAPI app
        self.app = await self._create_fastapi_app(args)
    
    async def _execute_runner_logic(self, args: argparse.Namespace) -> int:
        """Execute WebAPI runner logic"""
        # Start server
        return await self._start_server(args)
    
    async def _setup_web_asset_loader(self) -> None:
        """Setup web asset loader for HTML templates"""
        try:
            from ..core.intent_asset_loader import IntentAssetLoader, AssetLoaderConfig
            from pathlib import Path
            
            # Use current working directory assets folder or fallback
            assets_root = Path("assets")
            if not assets_root.exists():
                # Try relative to script location
                assets_root = Path(__file__).parent.parent.parent / "assets"
            
            # Create asset loader for web templates only
            asset_config = AssetLoaderConfig()
            self._asset_loader = IntentAssetLoader(assets_root, asset_config)
            
            # Load only web templates (no handler names needed)
            await self._asset_loader._load_web_templates()
            
            logger.info(f"✅ Web asset loader initialized with {len(self._asset_loader.web_templates)} templates")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize web asset loader: {e}")
            logger.warning("Web templates will fallback to inline HTML")
            self._asset_loader = None
    
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
        
        # Define lifespan context manager
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Handle application startup and shutdown"""
            # Startup: nothing specific needed here for this application
            yield
            # Shutdown: cleanup web components
            logger.info("Shutting down Web API server")
            if self.web_input:
                await self.web_input.stop_listening()
        
        # Create FastAPI app with lifespan
        app = FastAPI(
            title="Irene Voice Assistant API",
            description="Modern async voice assistant API with WebSocket support",
            version=__version__,
            debug=args.debug,
            lifespan=lifespan
        )
        
        # Add CORS middleware - Allow all origins for development
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,  # Must be False when allow_origins=["*"]
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Mount static files for CSS/JS assets
        await self._mount_static_files(app)
        
        # Import centralized API schemas
        from ..api.schemas import CommandRequest, CommandResponse
        
        class StatusResponse(BaseModel):
            status: str
            components: Dict[str, Any]
            web_clients: int
            
        class HistoryResponse(BaseModel):
            messages: list[Dict[str, Any]]
            total_count: int
        
        # Root endpoint
        @app.get("/", response_class=HTMLResponse, tags=["General"])
        async def root():
            """Serve a simple web interface"""
            if self._asset_loader:
                html_content = self._asset_loader.get_web_template_with_variables(
                    "index",
                    version=__version__
                )
                if html_content:
                    return HTMLResponse(content=html_content)
                else:
                    logger.error("Web template 'index' not found")
                    raise HTTPException(status_code=500, detail="Web interface template not available")
            else:
                logger.error("Web asset loader not initialized")
                raise HTTPException(status_code=500, detail="Web asset system not available")
        
        # Status endpoint
        @app.get("/status", response_model=StatusResponse, tags=["General"])
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
        @app.post("/command", response_model=CommandResponse, tags=["General"])
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
                    response="Command execution failed",
                    error=str(e)
                )
        
        # Health check endpoint
        @app.get("/health", tags=["General"])
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "version": __version__,
                "timestamp": asyncio.get_event_loop().time()
            }
        
        # Mount component routers - NEW PHASE 4 FUNCTIONALITY
        await self._mount_component_routers(app)
        
        # Intent management endpoints - NEW PHASE 4 FUNCTIONALITY  
        await self._add_intent_management_endpoints(app)
        
        # AsyncAPI documentation endpoints
        await self._add_asyncapi_endpoints(app)
        
        # Component info endpoint
        @app.get("/components", tags=["General"])
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
        
        return app
    
    async def _mount_static_files(self, app) -> None:
        """Mount static files for CSS/JS assets"""
        try:
            from fastapi.staticfiles import StaticFiles  # type: ignore
            from pathlib import Path
            
            # Determine static files path
            static_path = Path("assets/web/static")
            if not static_path.exists():
                # Try relative to script location
                static_path = Path(__file__).parent.parent.parent / "assets" / "web" / "static"
            
            if static_path.exists():
                app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
                logger.info(f"✅ Static files mounted from {static_path}")
            else:
                logger.warning(f"⚠️ Static files directory not found: {static_path}")
                
        except ImportError:
            logger.warning("FastAPI StaticFiles not available, skipping static file mounting")
        except Exception as e:
            logger.error(f"❌ Failed to mount static files: {e}")
    
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
    
    async def _generate_asyncapi_spec(self) -> Dict[str, Any]:
        """Generate combined AsyncAPI specification from all components"""
        try:
            # Start with base AsyncAPI spec
            base_spec = generate_base_asyncapi_spec()
            component_specs = []
            
            # Get WebAPI components (same logic as _mount_component_routers)
            if self.core:
                from ..core.interfaces.webapi import WebAPIPlugin
                web_components = []
                
                # Check component manager first
                if hasattr(self.core, 'component_manager'):
                    try:
                        available_components = self.core.component_manager.get_components()
                        logger.debug(f"Found {len(available_components)} available components: {list(available_components.keys())}")
                        
                        for name, component in available_components.items():
                            if isinstance(component, WebAPIPlugin):
                                web_components.append((name, component))
                                logger.debug(f"Component {name} implements WebAPIPlugin")
                            else:
                                logger.debug(f"Component {name} does not implement WebAPIPlugin (type: {type(component).__name__})")
                                
                    except Exception as e:
                        logger.warning(f"Could not get components from component manager: {e}")
                else:
                    logger.warning("Core does not have component_manager")
                
                # Also check plugin manager
                if hasattr(self.core, 'plugin_manager'):
                    try:
                        for name, plugin in self.core.plugin_manager._plugins.items():
                            if isinstance(plugin, WebAPIPlugin):
                                web_components.append((name, plugin))
                                logger.debug(f"Plugin {name} implements WebAPIPlugin")
                            else:
                                logger.debug(f"Plugin {name} does not implement WebAPIPlugin (type: {type(plugin).__name__})")
                    except Exception as e:
                        logger.warning(f"Could not get plugins from plugin manager: {e}")
                else:
                    logger.warning("Core does not have plugin_manager")
                
                logger.debug(f"Found {len(web_components)} WebAPIPlugin components for AsyncAPI generation")
                
                # Collect AsyncAPI specs from each component
                for name, component in web_components:
                    try:
                        if hasattr(component, 'get_websocket_spec'):
                            spec = component.get_websocket_spec()
                            if spec:
                                component_specs.append(spec)
                                logger.debug(f"✅ Generated AsyncAPI spec for {name}")
                            else:
                                logger.debug(f"⚪ Component {name} has no WebSocket endpoints")
                        else:
                            logger.debug(f"⚪ Component {name} doesn't implement get_websocket_spec")
                            
                    except Exception as e:
                        logger.error(f"❌ Failed to generate AsyncAPI spec for {name}: {e}")
                
                # Merge all specs
                merged_spec = merge_asyncapi_specs(base_spec, component_specs)
                
                logger.info(f"✅ Generated AsyncAPI spec with {len(merged_spec.get('channels', {}))} channels "
                           f"and {len(merged_spec.get('components', {}).get('messages', {}))} message types")
                
                return merged_spec
            
            else:
                logger.warning("Core or plugin manager not available for AsyncAPI generation")
                return base_spec
                
        except Exception as e:
            logger.error(f"Error generating AsyncAPI specification: {e}")
            return generate_base_asyncapi_spec()  # Return empty spec on error
    
    async def _add_intent_management_endpoints(self, app):
        """Add high-level intent management endpoints"""
        try:
            from fastapi import HTTPException  # type: ignore
            from pydantic import BaseModel  # type: ignore
            from typing import Dict, Any, Optional, List
            
            # Request/Response models for system capabilities
            class SystemCapabilitiesResponse(BaseModel):
                version: str
                components: Dict[str, Any]
                intent_handlers: List[str]
                nlu_providers: List[str]
                voice_trigger_providers: List[str]
                text_processing_providers: List[str]
                workflows: List[str]
                
            @app.get("/system/capabilities", response_model=SystemCapabilitiesResponse, tags=["General"])
            async def get_system_capabilities():
                """Get comprehensive system capabilities"""
                try:
                    capabilities = {
                        "version": __version__,
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
            
            @app.get("/system/status", tags=["General"])
            async def get_enhanced_system_status():
                """Enhanced system status with intent system information"""
                try:
                    status = {
                        "system": "healthy",
                        "version": __version__,
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
    
    async def _add_asyncapi_endpoints(self, app):
        """Add AsyncAPI documentation endpoints"""
        try:
            from fastapi.responses import HTMLResponse  # type: ignore
            
            @app.get("/asyncapi", response_class=HTMLResponse, include_in_schema=False)
            async def asyncapi_docs():
                """Serve AsyncAPI documentation page"""
                if self._asset_loader:
                    html_content = self._asset_loader.get_web_template("asyncapi")
                    if html_content:
                        return HTMLResponse(content=html_content)
                    else:
                        logger.error("Web template 'asyncapi' not found")
                        raise HTTPException(status_code=500, detail="AsyncAPI documentation template not available")
                else:
                    logger.error("Web asset loader not initialized")
                    raise HTTPException(status_code=500, detail="Web asset system not available")
            
            @app.get("/asyncapi.yaml", include_in_schema=False)
            async def asyncapi_spec():
                """Get AsyncAPI specification in YAML format"""
                try:
                    spec = await self._generate_asyncapi_spec()
                    
                    # Convert to YAML
                    import yaml
                    yaml_content = yaml.dump(spec, default_flow_style=False, sort_keys=False)
                    
                    from fastapi.responses import Response  # type: ignore
                    return Response(
                        content=yaml_content,
                        media_type="application/x-yaml",
                        headers={"Content-Disposition": "inline; filename=asyncapi.yaml"}
                    )
                except Exception as e:
                    logger.error(f"Error generating AsyncAPI spec: {e}")
                    from fastapi import HTTPException  # type: ignore
                    raise HTTPException(500, f"Failed to generate AsyncAPI specification: {e}")
            
            @app.get("/asyncapi.json", include_in_schema=False)
            async def asyncapi_spec_json():
                """Get AsyncAPI specification in JSON format"""
                try:
                    spec = await self._generate_asyncapi_spec()
                    return spec
                except Exception as e:
                    logger.error(f"Error generating AsyncAPI spec: {e}")
                    from fastapi import HTTPException  # type: ignore
                    raise HTTPException(500, f"Failed to generate AsyncAPI specification: {e}")
            
            @app.get("/debug/asyncapi", include_in_schema=False)
            async def debug_asyncapi():
                """Debug AsyncAPI generation process"""
                debug_info = {}
                
                try:
                    # Check component manager first
                    if self.core and hasattr(self.core, 'component_manager'):
                        debug_info["component_manager_available"] = True
                        available_components = self.core.component_manager.get_components()
                        debug_info["total_components"] = len(available_components)
                        debug_info["component_names"] = list(available_components.keys())
                    else:
                        debug_info["component_manager_available"] = False
                    
                    # Check plugin manager
                    if self.core and hasattr(self.core, 'plugin_manager'):
                        debug_info["plugin_manager_available"] = True
                        debug_info["total_plugins"] = len(self.core.plugin_manager._plugins)
                        
                        # Find WebAPIPlugin components
                        from ..core.interfaces.webapi import WebAPIPlugin
                        web_components = []
                        
                        for name, plugin in self.core.plugin_manager._plugins.items():
                            plugin_info = {
                                "name": name,
                                "type": type(plugin).__name__,
                                "is_webapi_plugin": isinstance(plugin, WebAPIPlugin),
                                "has_get_websocket_spec": hasattr(plugin, 'get_websocket_spec'),
                                "has_get_router": hasattr(plugin, 'get_router')
                            }
                            
                            if isinstance(plugin, WebAPIPlugin):
                                web_components.append((name, plugin))
                                try:
                                    router = plugin.get_router()
                                    plugin_info["router_available"] = router is not None
                                    if router:
                                        plugin_info["router_routes_count"] = len(router.routes)
                                        plugin_info["websocket_routes"] = []
                                        
                                        for route in router.routes:
                                            if hasattr(route, 'endpoint') and hasattr(route.endpoint, '_websocket_meta'):
                                                plugin_info["websocket_routes"].append({
                                                    "path": route.path,
                                                    "endpoint": route.endpoint.__name__,
                                                    "has_meta": True
                                                })
                                        
                                        # Test get_websocket_spec method
                                        if hasattr(plugin, 'get_websocket_spec'):
                                            spec = plugin.get_websocket_spec()
                                            plugin_info["websocket_spec"] = spec
                                        
                                except Exception as e:
                                    plugin_info["error"] = str(e)
                            
                            debug_info[f"plugin_{name}"] = plugin_info
                        
                        debug_info["webapi_components_count"] = len(web_components)
                    else:
                        debug_info["plugin_manager_available"] = False
                    
                    return debug_info
                    
                except Exception as e:
                    return {"error": str(e), "traceback": str(e)}
            
            logger.info("✅ Added AsyncAPI documentation endpoints: /asyncapi, /asyncapi.yaml, /asyncapi.json")
            
        except ImportError as e:
            logger.warning(f"AsyncAPI dependencies not available: {e}")
        except Exception as e:
            logger.error(f"Error adding AsyncAPI endpoints: {e}")
    
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
            print(f"📚 REST API docs available at {protocol}://{args.host}:{args.port}/docs")
            print(f"🚀 WebSocket API docs available at {protocol}://{args.host}:{args.port}/asyncapi")
            print(f"🌍 Web interface at {protocol}://{args.host}:{args.port}")
            print(f"🔌 Component WebSockets: /asr/stream (speech recognition), /asr/binary (ESP32-optimized)")
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