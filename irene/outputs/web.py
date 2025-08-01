"""
Web Output Target - Web interface output

Provides web-based output via WebSockets or HTTP for remote clients
and web application integration.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
import json

from .base import OutputTarget, Response, ComponentNotAvailable

logger = logging.getLogger(__name__)


class WebOutput(OutputTarget):
    """
    Web-based output target using WebSockets.
    
    Features:
    - Real-time WebSocket communication
    - Multiple client support
    - JSON message formatting
    - Connection management
    """
    
    def __init__(self, host: str = "localhost", port: int = 8000):
        self.host = host
        self.port = port
        self._clients: list[Any] = []  # WebSocket clients
        self._server = None
        self._running = False
        
        # Check for required dependencies
        try:
            import fastapi
            import uvicorn
            self._fastapi_available = True
        except ImportError as e:
            logger.warning(f"Web output dependencies not available: {e}")
            self._fastapi_available = False
        
    def is_available(self) -> bool:
        """Check if web output is available"""
        return self._fastapi_available
        
    def get_output_type(self) -> str:
        """Get output type identifier"""
        return "web"
        
    def supports_response_type(self, response_type: str) -> bool:
        """Check if this target supports the response type"""
        # Web output handles all response types
        return True
        
    def get_settings(self) -> Dict[str, Any]:
        """Get current web settings"""
        return {
            "host": self.host,
            "port": self.port,
            "fastapi_available": self._fastapi_available,
            "connected_clients": len(self._clients)
        }
        
    async def configure_output(self, **settings) -> None:
        """Configure web settings"""
        if "host" in settings:
            self.host = settings["host"]
        if "port" in settings:
            self.port = settings["port"]
            
    async def test_output(self) -> bool:
        """Test web functionality"""
        if not self.is_available():
            return False
            
        try:
            # Test basic web output functionality
            test_response = Response("Web test", response_type="test")
            await self.send(test_response)
            return True
        except Exception as e:
            logger.error(f"Web output test failed: {e}")
            return False
        
    async def send(self, response: Response) -> None:
        """Send response via web interface"""
        if not self.is_available():
            raise ComponentNotAvailable("Web output dependencies not available")
            
        try:
            # Create web response format
            web_response = {
                "text": response.text,
                "type": response.response_type,
                "metadata": response.metadata or {},
                "priority": response.priority,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Send to all connected WebSocket clients
            if self._clients:
                await self._broadcast_to_clients(web_response)
            else:
                logger.debug(f"No web clients connected, queuing response: {response.text}")
                
            # If no clients, could store in database or file for later retrieval
            
        except Exception as e:
            logger.error(f"Web output error: {e}")
            raise
            
    async def send_error(self, error: str) -> None:
        """Send error message via web interface"""
        error_response = Response(f"Error: {error}", response_type="error")
        await self.send(error_response)
        
    async def _broadcast_to_clients(self, message: dict[str, Any]) -> None:
        """Broadcast message to all connected clients"""
        if not self._clients:
            return
            
        # Create JSON message
        json_message = json.dumps(message)
        
        # Send to all clients (remove disconnected ones)
        disconnected_clients = []
        for client in self._clients[:]:
            try:
                await client.send(json_message)
            except Exception:
                disconnected_clients.append(client)
                
        # Clean up disconnected clients
        for client in disconnected_clients:
            self._clients.remove(client)
            
    def add_client(self, client: Any) -> None:
        """Add a WebSocket client"""
        self._clients.append(client)
        logger.info(f"Web client connected. Total clients: {len(self._clients)}")
        
    def remove_client(self, client: Any) -> None:
        """Remove a WebSocket client"""
        if client in self._clients:
            self._clients.remove(client)
            logger.info(f"Web client disconnected. Total clients: {len(self._clients)}")
            
    async def get_response_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent response history for new clients"""
        # In a real implementation, this would query a database or cache
        # For now, return empty list
        return []
        
    def get_client_count(self) -> int:
        """Get number of connected clients"""
        return len(self._clients)
        
    async def send_to_client(self, client: Any, response: Response) -> None:
        """Send response to a specific client"""
        web_response = {
            "text": response.text,
            "type": response.response_type,
            "metadata": response.metadata or {},
            "priority": response.priority,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        try:
            json_message = json.dumps(web_response)
            logger.debug(f"Sending to specific web client: {json_message}")
            # await client.send_text(json_message)
        except Exception as e:
            logger.error(f"Failed to send to specific client: {e}")
            # Remove client if send fails
            self.remove_client(client) 