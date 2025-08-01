"""
Web API Runner - FastAPI server for Irene

Replaces legacy runva_webapi.py with modern async FastAPI architecture.
Provides REST endpoints and WebSocket support for remote access.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json

from ..config.models import CoreConfig, ComponentConfig
from ..config.manager import ConfigManager
from ..core.engine import AsyncVACore
from ..utils.loader import ComponentLoader, get_component_status


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
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Reduce output verbosity"
    )
    
    # CORS options
    parser.add_argument(
        "--cors-origins",
        nargs="*",
        default=["*"],
        help="Allowed CORS origins (default: *)"
    )
    
    # Logging options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    
    return parser


def check_webapi_dependencies() -> bool:
    """Check if Web API dependencies are available"""
    try:
        import fastapi
        import uvicorn
        print("✅ Web API dependencies available")
        print(f"   FastAPI version: {fastapi.__version__}")
        print(f"   Uvicorn available: yes")
        return True
    except ImportError as e:
        print(f"❌ Web API dependencies missing: {e}")
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
        self.websocket_connections: list = []
        
    async def run(self, args: Optional[list[str]] = None) -> int:
        """Run Web API server mode"""
        # Parse arguments
        parser = setup_webapi_argument_parser()
        parsed_args = parser.parse_args(args)
        
        # Set up logging
        log_level = getattr(logging, parsed_args.log_level)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
            microphone=False,  # Typically no microphone in API mode
            tts=True,         # Enable TTS for audio responses
            audio_output=False, # No direct audio output in API mode
            web_api=True      # Enable web API
        )
        
        config = CoreConfig(
            components=components,
            debug=args.debug
        )
        
        return config
    
    async def _create_fastapi_app(self, args):
        """Create and configure FastAPI application"""
        from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import HTMLResponse
        from pydantic import BaseModel
        
        # Create FastAPI app
        app = FastAPI(
            title="Irene Voice Assistant API",
            description="Modern async voice assistant API",
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
            deployment_profile: str
            components: Dict[str, Any]
            plugins_loaded: int
        
        # Routes
        @app.get("/", response_class=HTMLResponse)
        async def root():
            """Root endpoint with API information"""
            return """
            <html>
                <head><title>Irene Voice Assistant API</title></head>
                <body>
                    <h1>🤖 Irene Voice Assistant API v13</h1>
                    <p>Modern async voice assistant API</p>
                    <ul>
                        <li><a href="/docs">📚 API Documentation</a></li>
                        <li><a href="/status">📊 System Status</a></li>
                        <li><a href="/health">❤️ Health Check</a></li>
                    </ul>
                </body>
            </html>
            """
        
        @app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}
        
        @app.get("/status", response_model=StatusResponse)
        async def get_status():
            """Get system status"""
            if not self.core:
                raise HTTPException(status_code=503, detail="Assistant not initialized")
            
            component_info = self.core.component_manager.get_component_info()
            profile = self.core.component_manager.get_deployment_profile()
            plugin_count = len(self.core.plugin_manager._plugins)
            
            return StatusResponse(
                status="running" if self.core.is_running else "stopped",
                deployment_profile=profile,
                components=component_info,
                plugins_loaded=plugin_count
            )
        
        @app.post("/command", response_model=CommandResponse)
        async def execute_command(request: CommandRequest):
            """Execute voice assistant command"""
            if not self.core:
                raise HTTPException(status_code=503, detail="Assistant not initialized")
            
            try:
                # Create context if provided
                context = None
                if request.context:
                    # Convert context dict to Context object
                    pass  # TODO: Implement context conversion
                
                # Process command
                await self.core.process_command(request.command, context)
                
                return CommandResponse(
                    success=True,
                    response=f"Command '{request.command}' processed successfully"
                )
            
            except Exception as e:
                logger.error(f"Error processing command: {e}")
                return CommandResponse(
                    success=False,
                    error=str(e)
                )
        
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time communication"""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            
            try:
                while True:
                    # Receive command from client
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    if message.get("type") == "command":
                        command = message.get("command", "")
                        
                        try:
                            # Process command
                            await self.core.process_command(command)
                            
                            # Send success response
                            await websocket.send_text(json.dumps({
                                "type": "response",
                                "success": True,
                                "command": command,
                                "response": f"Command '{command}' processed"
                            }))
                        
                        except Exception as e:
                            # Send error response
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "success": False,
                                "command": command,
                                "error": str(e)
                            }))
                    
                    elif message.get("type") == "ping":
                        # Respond to ping
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": asyncio.get_event_loop().time()
                        }))
            
            except WebSocketDisconnect:
                pass
            finally:
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)
        
        # Add startup and shutdown events
        @app.on_event("startup")
        async def startup_event():
            if not args.quiet:
                print("🚀 Web API server started")
        
        @app.on_event("shutdown")
        async def shutdown_event():
            if not args.quiet:
                print("🛑 Web API server stopped")
            
            # Close all WebSocket connections
            for websocket in self.websocket_connections:
                try:
                    await websocket.close()
                except:
                    pass
        
        return app
    
    async def _start_server(self, args) -> int:
        """Start the FastAPI server with uvicorn"""
        import uvicorn
        
        # Configure SSL if provided
        ssl_config = {}
        if args.ssl_cert and args.ssl_key:
            ssl_config = {
                "ssl_certfile": str(args.ssl_cert),
                "ssl_keyfile": str(args.ssl_key)
            }
        
        # Server configuration
        config = uvicorn.Config(
            app=self.app,
            host=args.host,
            port=args.port,
            log_level=args.log_level.lower(),
            reload=args.reload,
            workers=args.workers if not args.reload else 1,
            **ssl_config
        )
        
        server = uvicorn.Server(config)
        
        if not args.quiet:
            protocol = "https" if ssl_config else "http"
            print(f"🌐 Starting Web API server at {protocol}://{args.host}:{args.port}")
            print(f"📚 API docs available at {protocol}://{args.host}:{args.port}/docs")
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
    runner = WebAPIRunner()
    try:
        return asyncio.run(runner.run())
    except KeyboardInterrupt:
        print("\n👋 Web API server stopped")
        return 0


if __name__ == "__main__":
    sys.exit(run_webapi()) 