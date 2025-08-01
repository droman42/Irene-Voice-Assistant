"""
Web Output Target - Web interface output

Provides web-based output via WebSockets or HTTP for remote clients
and web application integration.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
import json
import time

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
        self._message_history: list[Dict[str, Any]] = []
        self._max_history = 100  # Keep last 100 messages
        
        # Check for required dependencies
        try:
            import fastapi  # type: ignore
            import uvicorn  # type: ignore
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
            "connected_clients": len(self._clients),
            "running": self._running,
            "message_history_size": len(self._message_history)
        }
        
    async def configure_output(self, **settings) -> None:
        """Configure web settings"""
        if "host" in settings:
            self.host = settings["host"]
        if "port" in settings:
            self.port = settings["port"]
        if "max_history" in settings:
            self._max_history = max(10, int(settings["max_history"]))
            
    async def test_output(self) -> bool:
        """Test web output functionality"""
        if not self.is_available():
            return False
            
        try:
            # Test that we can create and format a message
            test_response = Response("Test message", response_type="test")
            test_message = self._format_web_response(test_response)
            return "text" in test_message and "type" in test_message
        except Exception as e:
            logger.error(f"Web output test failed: {e}")
            return False

    async def send(self, response: Response) -> None:
        """Send response to all connected web clients"""
        if not self.is_available():
            logger.warning("Web output not available - skipping send")
            return
            
        try:
            # Format response for web transmission
            web_message = self._format_web_response(response)
            
            # Add to message history
            self._add_to_history(web_message)
            
            # Send to all connected clients
            if self._clients:
                await self._broadcast_to_clients(web_message)
                logger.debug(f"Sent web response to {len(self._clients)} clients: {response.text[:50]}...")
            else:
                logger.debug("No web clients connected - message not sent")
                
        except Exception as e:
            logger.error(f"Error sending web output: {e}")
            
    async def send_error(self, error: str) -> None:
        """Send error message to web clients"""
        error_response = Response(f"Error: {error}", response_type="error")
        await self.send(error_response)
        
    def _format_web_response(self, response: Response) -> Dict[str, Any]:
        """Format Response object for web transmission"""
        return {
            "type": "response",
            "response_type": response.response_type,
            "text": response.text,
            "metadata": response.metadata or {},
            "priority": response.priority,
            "timestamp": time.time()
        }
        
    def _add_to_history(self, message: Dict[str, Any]) -> None:
        """Add message to history with size limit"""
        self._message_history.append(message)
        
        # Trim history if it exceeds max size
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]
            
    async def _broadcast_to_clients(self, message: Dict[str, Any]) -> None:
        """Broadcast message to all connected WebSocket clients"""
        if not self._clients:
            return
            
        # Convert message to JSON
        message_json = json.dumps(message)
        
        # Send to all clients, removing disconnected ones
        disconnected_clients = []
        for client in self._clients[:]:
            try:
                await client.send_text(message_json)
            except Exception as e:
                logger.debug(f"Client disconnected during send: {e}")
                disconnected_clients.append(client)
                
        # Remove disconnected clients
        for client in disconnected_clients:
            await self.remove_client(client)
            
    async def add_client(self, websocket) -> None:
        """Add a WebSocket client"""
        self._clients.append(websocket)
        logger.info(f"Added web client. Total: {len(self._clients)}")
        
        # Send recent message history to new client
        await self._send_history_to_client(websocket)
        
    async def remove_client(self, websocket) -> None:
        """Remove a WebSocket client"""
        if websocket in self._clients:
            self._clients.remove(websocket)
            logger.info(f"Removed web client. Total: {len(self._clients)}")
            
    async def _send_history_to_client(self, websocket) -> None:
        """Send recent message history to a newly connected client"""
        if not self._message_history:
            return
            
        try:
            # Send a history message
            history_message = {
                "type": "history",
                "messages": self._message_history[-10:],  # Last 10 messages
                "total_messages": len(self._message_history)
            }
            await websocket.send_text(json.dumps(history_message))
            logger.debug(f"Sent message history to new client ({len(self._message_history[-10:])} messages)")
        except Exception as e:
            logger.error(f"Error sending history to client: {e}")
            
    async def clear_history(self) -> None:
        """Clear message history"""
        self._message_history.clear()
        logger.info("Cleared web output message history")
        
    def get_message_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get message history with optional limit"""
        if limit is None:
            return self._message_history.copy()
        else:
            return self._message_history[-limit:]
            
    def get_client_info(self) -> List[Dict[str, Any]]:
        """Get information about connected clients"""
        client_info = []
        for i, client in enumerate(self._clients):
            try:
                # Try to get client information
                client_info.append({
                    "id": i,
                    "connected": True,
                    "address": getattr(client, 'client', {}).get('host', 'unknown') if hasattr(client, 'client') else 'unknown'
                })
            except Exception:
                client_info.append({
                    "id": i,
                    "connected": False,
                    "address": "unknown"
                })
        return client_info
        
    async def send_system_message(self, message: str, message_type: str = "system") -> None:
        """Send a system message to all clients"""
        system_message = {
            "type": message_type,
            "text": message,
            "timestamp": time.time()
        }
        
        if self._clients:
            await self._broadcast_to_clients(system_message)
            logger.debug(f"Sent system message to {len(self._clients)} clients: {message}")
            
    async def ping_clients(self) -> Dict[str, int]:
        """Ping all clients to check connectivity"""
        active_clients = 0
        disconnected_clients = []
        
        for client in self._clients[:]:
            try:
                # Send ping message
                ping_message = {
                    "type": "ping",
                    "timestamp": time.time()
                }
                await client.send_text(json.dumps(ping_message))
                active_clients += 1
            except Exception:
                disconnected_clients.append(client)
                
        # Remove disconnected clients
        for client in disconnected_clients:
            await self.remove_client(client)
            
        return {
            "active_clients": active_clients,
            "disconnected_clients": len(disconnected_clients),
            "total_clients": len(self._clients)
        } 