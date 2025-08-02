"""
Web API Plugin Interface - For plugins that provide web endpoints

Defines the interface for plugins that expose functionality via REST APIs
using FastAPI routers.
"""

from typing import Optional, Any, TYPE_CHECKING
from abc import abstractmethod

from .plugin import PluginInterface

if TYPE_CHECKING:
    from fastapi import APIRouter  # type: ignore


class WebAPIPlugin(PluginInterface):
    """
    Interface for plugins that provide web API endpoints.
    
    WebAPI plugins extend functionality by exposing REST endpoints
    that can be integrated into the main FastAPI application.
    """
    
    @abstractmethod
    def get_router(self) -> Optional[Any]:
        """
        Get FastAPI router with plugin endpoints.
        
        Returns:
            APIRouter instance with endpoints, or None if not available
        """
        pass
        
    def get_api_prefix(self) -> str:
        """
        Get URL prefix for this plugin's API endpoints.
        
        Returns:
            URL prefix (e.g., '/tts', '/audio', '/timer')
        """
        return f"/{self.name}"
        
    def get_api_tags(self) -> list[str]:
        """
        Get OpenAPI tags for this plugin's endpoints.
        
        Returns:
            List of tags for API documentation grouping
        """
        return [self.name]
        
    def requires_authentication(self) -> bool:
        """
        Whether this plugin's endpoints require authentication.
        
        Returns:
            True if authentication is required
        """
        return False
        
    def is_api_available(self) -> bool:
        """
        Check if web API functionality is available.
        
        Returns:
            True if FastAPI dependencies are available
        """
        try:
            import fastapi  # type: ignore
            return True
        except ImportError:
            return False
        
    def get_openapi_schema(self) -> Optional[dict]:
        """
        Get custom OpenAPI schema additions for this plugin.
        
        Returns:
            OpenAPI schema dict or None for auto-generation
        """
        return None 