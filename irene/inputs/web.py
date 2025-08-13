"""
Web Input Source - Pure web interface input capture

Provides web-based input via WebSockets or HTTP for remote control
and web application integration. Pure capture without processing (separation of concerns).
"""

import asyncio
import logging
from typing import AsyncIterator, Dict, Any, Optional, List
import json

from .base import InputSource, ComponentNotAvailable, InputData

logger = logging.getLogger(__name__)


class WebInput(InputSource):
    """
    Web input source for receiving commands via web interface.
    
    Pure input capture - supports WebSocket and HTTP-based command input.
    Raw audio data is passed through without processing (separation of concerns).
    Requires FastAPI/uvicorn for operation.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self._listening = False
        self._command_queue: Optional[asyncio.Queue] = None
        self._web_server = None
        self._websocket_connections: list = []
        
        # Check for required dependencies
        try:
            import fastapi  # type: ignore
            import uvicorn  # type: ignore
            self._fastapi_available = True
        except ImportError as e:
            logger.warning(f"Web input dependencies not available: {e}")
            self._fastapi_available = False
        
    def is_available(self) -> bool:
        """Check if web input is available"""
        return self._fastapi_available
        
    def get_input_type(self) -> str:
        """Get input type identifier"""
        return "web"
        
    def get_settings(self) -> Dict[str, Any]:
        """Get current web settings"""
        return {
            "host": self.host,
            "port": self.port,
            "fastapi_available": self._fastapi_available,
            "websocket_connections": len(self._websocket_connections),
            "listening": self._listening
        }
        
    async def configure_input(self, **settings) -> None:
        """Configure web settings"""
        if "host" in settings:
            self.host = settings["host"]
        if "port" in settings:
            self.port = settings["port"]
            
    async def test_input(self) -> bool:
        """Test web functionality"""
        if not self.is_available():
            return False
            
        try:
            # Test that we can create a command queue
            test_queue = asyncio.Queue()
            await test_queue.put("test")
            result = await test_queue.get()
            return result == "test"
        except Exception as e:
            logger.error(f"Web input test failed: {e}")
            return False

    async def start_listening(self) -> None:
        """Start web input listening"""
        if not self.is_available():
            raise ComponentNotAvailable("Web input dependencies not available")
            
        if self._listening:
            return
            
        logger.info(f"Starting web input on {self.host}:{self.port}")
        self._command_queue = asyncio.Queue()
        self._listening = True
        
    async def stop_listening(self) -> None:
        """Stop web input listening"""
        if not self._listening:
            return
            
        logger.info("Stopping web input")
        self._listening = False
        
        # Close WebSocket connections
        for websocket in self._websocket_connections[:]:
            try:
                await websocket.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket connection: {e}")
        self._websocket_connections.clear()
        
        # Clear command queue
        if self._command_queue:
            while not self._command_queue.empty():
                try:
                    self._command_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
        
    def is_listening(self) -> bool:
        """Check if currently listening"""
        return self._listening
        
    async def listen(self) -> AsyncIterator[InputData]:
        """
        Listen for web commands and yield them.
        
        This method yields commands received from web clients via
        HTTP POST requests or WebSocket messages.
        """
        if not self._listening or not self._command_queue:
            return
            
        logger.info("Web input listening for commands...")
        
        while self._listening:
            try:
                # Wait for commands from web interface
                command = await asyncio.wait_for(
                    self._command_queue.get(), timeout=1.0
                )
                if command and command.strip():
                    logger.debug(f"Web input received command: {command}")
                    yield command.strip()
                    
            except asyncio.TimeoutError:
                # Normal timeout, continue listening
                continue
            except Exception as e:
                logger.error(f"Error in web input: {e}")
                break
                
    async def send_command(self, command: str) -> None:
        """
        Method for external code to send commands to this input source.
        Called by FastAPI route handlers and WebSocket handlers.
        """
        if self._listening and self._command_queue:
            await self._command_queue.put(command)
            logger.debug(f"Queued web command: {command}")
        else:
            logger.warning("Cannot send command: web input not listening")
            
    async def add_websocket_connection(self, websocket) -> None:
        """Add a WebSocket connection for command input"""
        self._websocket_connections.append(websocket)
        logger.info(f"Added WebSocket connection. Total: {len(self._websocket_connections)}")
        
    async def remove_websocket_connection(self, websocket) -> None:
        """Remove a WebSocket connection"""
        if websocket in self._websocket_connections:
            self._websocket_connections.remove(websocket)
            logger.info(f"Removed WebSocket connection. Total: {len(self._websocket_connections)}")
            
    async def handle_websocket_message(self, websocket, message_data: str) -> None:
        """
        Handle WebSocket messages - simplified to pure input capture
        Expected formats:
        - Text: {"type": "command", "command": "text"}
        - Raw Audio: {"type": "audio_data", "data": "base64_audio"} (no processing)
        """
        try:
            message = json.loads(message_data)
            
            # Handle text command messages
            if message.get("type") == "command":
                command = message.get("command", "").strip()
                if command:
                    await self.send_command(command)
                    
                    # Send acknowledgment back to client
                    response = {
                        "type": "ack",
                        "success": True,
                        "original_command": command,
                        "message": "Command received"
                    }
                    await websocket.send_text(json.dumps(response))
                else:
                    # Send error for empty command
                    response = {
                        "type": "error", 
                        "success": False,
                        "error": "Empty command received"
                    }
                    await websocket.send_text(json.dumps(response))
                    
            # Handle raw audio data (no processing - pure capture)
            elif message.get("type") == "audio_data":
                audio_data = message.get("data", "")
                if audio_data:
                    # Queue raw audio data for workflow processing
                    await self.send_command(f"AUDIO_DATA:{audio_data}")
                    
                    response = {
                        "type": "ack",
                        "success": True,
                        "message": "Audio data received"
                    }
                    await websocket.send_text(json.dumps(response))
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in WebSocket message: {e}")
            response = {
                "type": "error",
                "success": False, 
                "error": "Invalid JSON format"
            }
            await websocket.send_text(json.dumps(response))
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            response = {
                "type": "error",
                "success": False,
                "error": str(e)
            }
            await websocket.send_text(json.dumps(response))
    

    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get detailed connection information"""
        return {
            "listening": self._listening,
            "host": self.host,
            "port": self.port,
            "websocket_connections": len(self._websocket_connections),
            "queue_size": self._command_queue.qsize() if self._command_queue else 0,
            "fastapi_available": self._fastapi_available
        } 
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Web input needs web framework and WebSocket support"""
        return ["fastapi>=0.100.0", "uvicorn[standard]>=0.20.0", "websockets>=11.0.0"] 