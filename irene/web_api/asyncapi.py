"""
AsyncAPI infrastructure for WebSocket endpoint documentation

Provides schema-based decorators and auto-generation for AsyncAPI specifications
from WebSocket endpoints in Irene components.
"""

import json
import logging
from typing import Dict, Any, Optional, Type, Union, get_type_hints, get_origin, get_args
from functools import wraps
from dataclasses import dataclass
from pydantic import BaseModel
from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class WebSocketEndpointMeta:
    """Metadata for a WebSocket endpoint"""
    path: str
    description: str
    receives_schema: Optional[Type[BaseModel]]
    sends_schema: Optional[Type[BaseModel]]
    tags: list[str]


class WebSocketRegistry:
    """Registry for WebSocket endpoints and their schemas"""
    
    def __init__(self):
        self._endpoints: Dict[str, WebSocketEndpointMeta] = {}
    
    def register_endpoint(self, endpoint_meta: WebSocketEndpointMeta) -> None:
        """Register a WebSocket endpoint"""
        self._endpoints[endpoint_meta.path] = endpoint_meta
        logger.debug(f"Registered WebSocket endpoint: {endpoint_meta.path}")
    
    def get_endpoints(self) -> Dict[str, WebSocketEndpointMeta]:
        """Get all registered endpoints"""
        return self._endpoints.copy()
    
    def clear(self) -> None:
        """Clear all registered endpoints"""
        self._endpoints.clear()


# Global registry instance
_websocket_registry = WebSocketRegistry()


def websocket_api(
    description: str,
    receives: Optional[Type[BaseModel]] = None,
    sends: Optional[Type[BaseModel]] = None,
    tags: Optional[list[str]] = None
):
    """
    Decorator to mark WebSocket endpoints with schema information for AsyncAPI generation
    
    Args:
        description: Human-readable description of the WebSocket endpoint
        receives: Pydantic model for messages the endpoint receives
        sends: Pydantic model for messages the endpoint sends
        tags: List of tags for grouping in documentation
    
    Example:
        @websocket_api(
            description="Real-time speech recognition streaming",
            receives=AudioChunkMessage,
            sends=TranscriptionResultMessage,
            tags=["Speech Recognition"]
        )
        @router.websocket("/stream")
        async def stream_transcription(websocket: WebSocket):
            ...
    """
    def decorator(func):
        # Store metadata on the function
        func._websocket_meta = WebSocketEndpointMeta(
            path="",  # Will be set when we know the full path
            description=description,
            receives_schema=receives,
            sends_schema=sends,
            tags=tags or []
        )
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def pydantic_to_asyncapi_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """Convert a Pydantic model to AsyncAPI schema format"""
    try:
        # Get the JSON schema from Pydantic
        json_schema = model.model_json_schema()
        
        # Convert to AsyncAPI message schema format
        asyncapi_schema = {
            "name": model.__name__,
            "title": json_schema.get("title", model.__name__),
            "contentType": "application/json",
            "payload": {
                "type": "object",
                "properties": json_schema.get("properties", {}),
                "required": json_schema.get("required", [])
            }
        }
        
        # Add description if available
        if "description" in json_schema:
            asyncapi_schema["description"] = json_schema["description"]
        
        # Handle definitions/references
        if "$defs" in json_schema:
            asyncapi_schema["payload"]["$defs"] = json_schema["$defs"]
        
        return asyncapi_schema
        
    except Exception as e:
        logger.error(f"Error converting Pydantic model {model.__name__} to AsyncAPI schema: {e}")
        return {
            "name": model.__name__,
            "contentType": "application/json",
            "payload": {"type": "object"}
        }


def extract_websocket_specs_from_router(router, component_name: str, api_prefix: str) -> Dict[str, Any]:
    """
    Extract WebSocket specifications from a FastAPI router
    
    Args:
        router: FastAPI APIRouter instance
        component_name: Name of the component for namespacing
        api_prefix: API prefix for the component (e.g., "/asr")
    
    Returns:
        AsyncAPI specification fragment
    """
    channels = {}
    messages = {}
    operations = {}
    
    # Iterate through router routes to find WebSocket endpoints
    for route in router.routes:
        if hasattr(route, 'endpoint') and hasattr(route.endpoint, '_websocket_meta'):
            meta = route.endpoint._websocket_meta
            
            # Build full path with prefix
            full_path = f"{api_prefix}{route.path}"
            meta.path = full_path
            
            # Register in global registry
            _websocket_registry.register_endpoint(meta)
            
            # Build channel specification for AsyncAPI v3.0.0
            channel_spec = {
                "address": full_path,
                "description": meta.description,
                "bindings": {
                    "ws": {
                        "method": "GET"
                    }
                }
            }
            
            # Build operations for AsyncAPI v3.0.0
            channel_messages = {}
            
            # Add receive operation (messages we receive)
            if meta.receives_schema:
                receives_schema = pydantic_to_asyncapi_schema(meta.receives_schema)
                message_name = f"{component_name}_{meta.receives_schema.__name__}"
                messages[message_name] = receives_schema
                
                # Create stable channel message ID
                channel_msg_id = f"{meta.receives_schema.__name__.lower()}"
                channel_messages[channel_msg_id] = {"$ref": f"#/components/messages/{message_name}"}
                
                receive_op_id = f"{component_name}_receive_{route.path.replace('/', '_')}"
                operations[receive_op_id] = {
                    "action": "receive",
                    "channel": {
                        "$ref": f"#/channels/{full_path.replace('/', '~1')}"
                    },
                    "summary": f"Receive messages on {full_path}",
                    "messages": [
                        {
                            "$ref": f"#/channels/{full_path.replace('/', '~1')}/messages/{channel_msg_id}"
                        }
                    ]
                }
            
            # Add send operation (messages we send)
            if meta.sends_schema:
                sends_schema = pydantic_to_asyncapi_schema(meta.sends_schema)
                message_name = f"{component_name}_{meta.sends_schema.__name__}"
                messages[message_name] = sends_schema
                
                # Create stable channel message ID
                channel_msg_id = f"{meta.sends_schema.__name__.lower()}"
                channel_messages[channel_msg_id] = {"$ref": f"#/components/messages/{message_name}"}
                
                send_op_id = f"{component_name}_send_{route.path.replace('/', '_')}"
                operations[send_op_id] = {
                    "action": "send",
                    "channel": {
                        "$ref": f"#/channels/{full_path.replace('/', '~1')}"
                    },
                    "summary": f"Send messages on {full_path}",
                    "messages": [
                        {
                            "$ref": f"#/channels/{full_path.replace('/', '~1')}/messages/{channel_msg_id}"
                        }
                    ]
                }
            
            # Add messages to channel
            if channel_messages:
                channel_spec["messages"] = channel_messages
            
            channels[full_path] = channel_spec
    
    return {
        "channels": channels,
        "operations": operations,
        "messages": messages
    }


def generate_base_asyncapi_spec() -> Dict[str, Any]:
    """Generate base AsyncAPI specification structure"""
    return {
        "asyncapi": "3.0.0",
        "info": {
            "title": "Irene Voice Assistant WebSocket API",
            "version": "13.0.0",
            "description": "Real-time WebSocket endpoints for Irene Voice Assistant components",
            "contact": {
                "name": "Irene Voice Assistant",
                "url": "https://github.com/irene-voice-assistant"
            },
            "x-logo": "https://raw.githubusercontent.com/asyncapi/spec/master/assets/logo.png"
        },
        "defaultContentType": "application/json",
        "channels": {},
        "operations": {},
        "components": {
            "messages": {}
        }
    }


def merge_asyncapi_specs(base_spec: Dict[str, Any], component_specs: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge multiple component AsyncAPI specifications into a single spec
    
    Args:
        base_spec: Base AsyncAPI specification structure
        component_specs: List of component specifications to merge
    
    Returns:
        Combined AsyncAPI specification
    """
    merged = base_spec.copy()
    
    for spec in component_specs:
        # Merge channels
        merged["channels"].update(spec.get("channels", {}))
        
        # Merge operations
        merged["operations"].update(spec.get("operations", {}))
        
        # Merge messages
        merged["components"]["messages"].update(spec.get("messages", {}))
    
    return merged


def get_websocket_registry() -> WebSocketRegistry:
    """Get the global WebSocket registry"""
    return _websocket_registry
