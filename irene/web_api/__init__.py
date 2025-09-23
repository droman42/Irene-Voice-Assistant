"""
Web API utilities and infrastructure for Irene Voice Assistant

Provides AsyncAPI documentation generation, WebSocket schema decorators,
and other web API related functionality.
"""

from .asyncapi import (
    websocket_api,
    WebSocketEndpointMeta,
    WebSocketRegistry,
    get_websocket_registry,
    extract_websocket_specs_from_router,
    generate_base_asyncapi_spec,
    merge_asyncapi_specs,
    pydantic_to_asyncapi_schema,
    parse_endpoint_docstring
)

__all__ = [
    "websocket_api",
    "WebSocketEndpointMeta", 
    "WebSocketRegistry",
    "get_websocket_registry",
    "extract_websocket_specs_from_router",
    "generate_base_asyncapi_spec",
    "merge_asyncapi_specs",
    "pydantic_to_asyncapi_schema",
    "parse_endpoint_docstring"
]
