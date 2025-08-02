"""
Web Input Source - Web interface input with audio processing

ENHANCED: Provides web-based input via WebSockets or HTTP for remote control
and web application integration. Now supports audio chunk processing via ASR.
"""

import asyncio
import logging
from typing import AsyncIterator, Dict, Any, Optional, cast
import json
import base64

from .base import InputSource, ComponentNotAvailable
from ..core.interfaces.asr import ASRPlugin
from ..core.interfaces.llm import LLMPlugin

logger = logging.getLogger(__name__)


class WebInput(InputSource):
    """
    ENHANCED: Web input source for receiving commands via web interface.
    
    Supports WebSocket and HTTP-based command input with audio processing.
    Requires FastAPI/uvicorn for operation.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self._listening = False
        self._command_queue: Optional[asyncio.Queue] = None
        self._web_server = None
        self._websocket_connections: list = []
        self.core = None  # Core reference for ASR plugin access
        
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
        
    async def listen(self) -> AsyncIterator[str]:
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
        ENHANCED: Handle both text and audio messages
        Expected formats:
        - Text: {"type": "command", "command": "text"}
        - Audio: {"type": "audio_chunk", "data": "base64_audio", "language": "ru", "enhance": false}
        """
        try:
            message = json.loads(message_data)
            
            # Existing text command handling
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
                    
            # NEW: Audio chunk handling via ASR plugin
            elif message.get("type") == "audio_chunk":
                await self._handle_audio_chunk(websocket, message)
                
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
    
    async def _handle_audio_chunk(self, websocket, message: dict) -> None:
        """NEW: Process audio chunk using ASR plugin"""
        try:
            # Get ASR plugin from core
            if not self.core:
                raise ComponentNotAvailable("Core reference not available")
                
            asr_plugin = self.core.plugin_manager.get_asr_plugin("universal_asr")
            if not asr_plugin:
                raise ComponentNotAvailable("ASR plugin not available")
            
            # Decode base64 audio
            audio_data = base64.b64decode(message["data"])
            language = message.get("language", "ru")
            enhance = message.get("enhance", False)
            
            # Transcribe audio using ASR plugin
            # Cast to ASRPlugin since we've already checked it's not None
            asr_plugin_typed = cast(ASRPlugin, asr_plugin)
            text = await asr_plugin_typed.transcribe_audio(
                audio_data, language=language
            )
            
            if text.strip():
                # Optional LLM enhancement
                enhanced_text = None
                if enhance:
                    llm_plugin = self.core.plugin_manager.get_llm_plugin("universal_llm")
                    if llm_plugin:
                        try:
                            # Cast to LLMPlugin since we've already checked it's not None
                            llm_plugin_typed = cast(LLMPlugin, llm_plugin)
                            enhanced_text = await llm_plugin_typed.enhance_text(text, task="improve_speech_recognition")
                        except Exception as e:
                            logger.warning(f"LLM enhancement failed: {e}")
                
                # Use enhanced text if available, otherwise use original
                final_text = enhanced_text if enhanced_text else text
                
                # Send transcribed text as command
                await self.send_command(final_text.strip())
                
                # Send result back to client
                response = {
                    "type": "transcription_result",
                    "original_audio_size": len(audio_data),
                    "transcribed_text": text,
                    "enhanced_text": enhanced_text,
                    "final_text": final_text,
                    "enhanced": enhance and enhanced_text is not None,
                    "language": language,
                    "success": True
                }
                await websocket.send_text(json.dumps(response))
            else:
                # No text recognized
                response = {
                    "type": "transcription_result",
                    "transcribed_text": "",
                    "enhanced": False,
                    "language": language,
                    "success": True,
                    "message": "No speech detected"
                }
                await websocket.send_text(json.dumps(response))
                
        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            error_response = {
                "type": "error",
                "success": False,
                "error": str(e),
                "error_type": "audio_processing"
            }
            await websocket.send_text(json.dumps(error_response))
            
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