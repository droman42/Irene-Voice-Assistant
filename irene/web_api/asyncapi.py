"""
AsyncAPI infrastructure for WebSocket endpoint documentation

Provides schema-based decorators and auto-generation for AsyncAPI 2.6.0 specifications
from WebSocket endpoints in Irene components.

Uses AsyncAPI 2.6.0 for compatibility with @asyncapi/web-component@2.6.4 renderer.
"""

import json
import logging
from typing import Dict, Any, Optional, Type, Union, get_type_hints, get_origin, get_args
from ..__version__ import __version__
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
    """Convert a Pydantic model to AsyncAPI 2.6.0 schema format"""
    try:
        # Get the JSON schema from Pydantic
        json_schema = model.model_json_schema()
        
        # Clean up properties to be AsyncAPI 2.6.0 compatible
        cleaned_properties = {}
        if "properties" in json_schema:
            for prop_name, prop_def in json_schema["properties"].items():
                cleaned_properties[prop_name] = _clean_property_for_asyncapi(prop_def)
        
        # Convert to AsyncAPI message schema format
        asyncapi_schema = {
            "name": model.__name__,
            "title": json_schema.get("title", model.__name__),
            "contentType": "application/json",
            "payload": {
                "type": "object",
                "properties": cleaned_properties,
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


def _clean_property_for_asyncapi(prop_def: Dict[str, Any]) -> Dict[str, Any]:
    """Clean a property definition to be compatible with AsyncAPI 2.6.0"""
    if not isinstance(prop_def, dict):
        return prop_def
    
    # Handle $ref properties (schema references) - preserve them as-is
    if "$ref" in prop_def:
        return prop_def
    
    # Handle anyOf patterns (common for nullable fields in Pydantic)
    if "anyOf" in prop_def:
        any_of = prop_def["anyOf"]
        # Find the non-null type
        non_null_type = None
        for option in any_of:
            if option.get("type") != "null":
                non_null_type = option
                break
        
        if non_null_type:
            # Use the non-null type as the base, but preserve other properties
            cleaned = non_null_type.copy()
            # Add back description, title, example, default if they exist in the original
            for key in ["description", "title", "example", "default"]:
                if key in prop_def:
                    cleaned[key] = prop_def[key]
            return cleaned
        else:
            # Fallback to string type if we can't determine the type
            return {
                "type": "string",
                "description": prop_def.get("description", ""),
                "title": prop_def.get("title", "")
            }
    
    # Handle const values (like for literal types)
    if "const" in prop_def:
        return prop_def
    
    # If it already has a type, return as-is
    if "type" in prop_def:
        return prop_def
    
    # Fallback for unknown structures
    return {
        "type": "string",
        "description": prop_def.get("description", ""),
        "title": prop_def.get("title", "")
    }


def extract_websocket_specs_from_router(router, component_name: str, api_prefix: str) -> Dict[str, Any]:
    """
    Extract WebSocket specifications from a FastAPI router
    
    Args:
        router: FastAPI APIRouter instance
        component_name: Name of the component for namespacing
        api_prefix: API prefix for the component (e.g., "/asr")
    
    Returns:
        AsyncAPI 2.6.0 specification fragment
    """
    channels = {}
    messages = {}
    
    # Iterate through router routes to find WebSocket endpoints
    for route in router.routes:
        if hasattr(route, 'endpoint') and hasattr(route.endpoint, '_websocket_meta'):
            meta = route.endpoint._websocket_meta
            
            # Build full path with prefix
            full_path = f"{api_prefix}{route.path}"
            meta.path = full_path
            
            # Register in global registry
            _websocket_registry.register_endpoint(meta)
            
            # Build channel specification for AsyncAPI v2.6.0
            channel_spec = {
                "description": meta.description
            }
            
            # Convert tags to AsyncAPI 2.6.0 format (array of Tag Objects)
            tag_objs = [{"name": t} for t in (meta.tags or [])]
            
            # Add publish operation (client sends to server)
            if meta.receives_schema:
                receives_schema = pydantic_to_asyncapi_schema(meta.receives_schema)
                message_name = f"{component_name}_{meta.receives_schema.__name__}"
                messages[message_name] = receives_schema
                
                channel_spec["publish"] = {
                    "operationId": f"send{meta.receives_schema.__name__}",
                    "summary": f"Send {meta.receives_schema.__name__} to server",
                    "description": f"Client sends {meta.receives_schema.__name__} messages to the server for real-time processing",
                    "message": {"$ref": f"#/components/messages/{message_name}"},
                    **({"tags": tag_objs} if tag_objs else {})
                }
            
            # Add subscribe operation (server sends to client)
            if meta.sends_schema:
                sends_schema = pydantic_to_asyncapi_schema(meta.sends_schema)
                message_name = f"{component_name}_{meta.sends_schema.__name__}"
                messages[message_name] = sends_schema
                
                # For ASR, we also need to handle error messages
                # But let's use a simpler approach for better AsyncAPI 2.6.0 compatibility
                if component_name == "asr":
                    # Add error message schema
                    from ..api.schemas import TranscriptionErrorMessage
                    error_schema = pydantic_to_asyncapi_schema(TranscriptionErrorMessage)
                    error_message_name = f"{component_name}_TranscriptionErrorMessage"
                    messages[error_message_name] = error_schema
                
                # Use primary message reference (simpler for validation)
                channel_spec["subscribe"] = {
                    "operationId": f"receive{meta.sends_schema.__name__}",
                    "summary": f"Receive {meta.sends_schema.__name__} from server",
                    "description": f"Server sends {meta.sends_schema.__name__} messages back to the client with processing results",
                    "message": {"$ref": f"#/components/messages/{message_name}"},
                    **({"tags": tag_objs} if tag_objs else {})
                }
            
            channels[full_path] = channel_spec
    
    return {
        "channels": channels,
        "messages": messages
    }


def generate_base_asyncapi_spec() -> Dict[str, Any]:
    """Generate base AsyncAPI specification structure"""
    return {
        "asyncapi": "2.6.0",
        "info": {
            "title": "Irene Voice Assistant WebSocket API",
            "version": __version__,
            "description": "Real-time WebSocket endpoints for Irene Voice Assistant components",
            "contact": {
                "name": "Irene Voice Assistant",
                "url": "https://github.com/irene-voice-assistant"
            },
            "x-logo": {
                "url": "https://raw.githubusercontent.com/asyncapi/spec/master/assets/logo.png"
            }
        },
        "servers": {
            "default": {
                "url": "ws://{host}:{port}",
                "protocol": "ws",
                "variables": {
                    "host": {"default": "localhost"},
                    "port": {"default": "8000"}
                }
            }
        },
        "defaultContentType": "application/json",
        "channels": {},
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
        
        # Merge messages
        merged["components"]["messages"].update(spec.get("messages", {}))
    
    return merged


def get_websocket_registry() -> WebSocketRegistry:
    """Get the global WebSocket registry"""
    return _websocket_registry
