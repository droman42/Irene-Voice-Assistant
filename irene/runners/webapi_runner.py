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

from ..config.models import CoreConfig, ComponentConfig, LogLevel
from ..config.manager import ConfigManager
from ..core.engine import AsyncVACore
from ..utils.loader import get_component_status
from ..utils.logging import setup_logging
from .base import BaseRunner, RunnerConfig, check_component_dependencies, print_dependency_status
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
        from fastapi import FastAPI  # type: ignore
        from fastapi.middleware.cors import CORSMiddleware  # type: ignore
        from .webapi_router import create_webapi_router
        
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
        
        # Include main router with all endpoints
        main_router = create_webapi_router(
            core=self.core,
            asset_loader=self._asset_loader,
            web_input=self.web_input,
            start_time=self._start_time
        )
        app.include_router(main_router)
        
        # Mount component routers - NEW PHASE 4 FUNCTIONALITY
        await self._mount_component_routers(app)
        
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
    
    
    async def _add_intent_management_endpoints(self, app):
        """Intent management endpoints now handled by main router"""
        # Analytics and monitoring endpoints - NEW PHASE 4 FUNCTIONALITY
        await self._add_analytics_endpoints(app)
        
        logger.info("Intent management endpoints included via main router")
    
    async def _add_asyncapi_endpoints(self, app):
        """AsyncAPI documentation endpoints now handled by main router"""
        logger.info("AsyncAPI documentation endpoints included via main router")
    
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