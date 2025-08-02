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
from ..utils.loader import get_component_status


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
        """Setup WebInput and WebOutput components"""
        from ..inputs.web import WebInput
        from ..outputs.web import WebOutput
        
        # Create web input and output
        self.web_input = WebInput(host=args.host, port=args.port)
        self.web_output = WebOutput(host=args.host, port=args.port)
        
        # Add to core managers
        if self.core:
            # Add web input source
            await self.core.input_manager.add_source("web", self.web_input)
            await self.core.input_manager.start_source("web")
            
            # Add web output target
            await self.core.output_manager.add_target("web", self.web_output)
            
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
                
                # Process command through the assistant
                await self.core.process_command(request.command)
                
                return CommandResponse(
                    success=True,
                    response=f"Command '{request.command}' processed successfully",
                    metadata={"processed_via": "rest_api"}
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
        
        # Component info endpoint
        @app.get("/components")
        async def get_component_info():
            """Get detailed component information"""
            info = {}
            
            if self.web_input:
                info["web_input"] = self.web_input.get_connection_info()
            
            if self.web_output:
                info["web_output"] = {
                    **self.web_output.get_settings(),
                    "client_info": self.web_output.get_client_info()
                }
            
            if self.core:
                info["core"] = {
                    "input_sources": list(self.core.input_manager._sources.keys()),
                    "output_targets": list(self.core.output_manager._targets.keys()),
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