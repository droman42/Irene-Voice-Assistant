"""
Provider Base Classes and Utilities

Common functionality and base classes for all provider implementations.
Providers are pure implementation classes managed by Universal Plugins.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ProviderStatus(Enum):
    """Provider availability status"""
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    INITIALIZING = "initializing"


class EntryPointMetadata:
    """
    Universal metadata interface for entry-points asset configuration.
    
    This interface enables configuration-driven asset management by allowing
    providers to declare their asset needs, credential patterns, and platform
    dependencies. Supports both intelligent defaults and TOML configuration
    overrides.
    
    Phase 1 of TODO #4: Configuration-Driven Asset Management
    """
    
    @classmethod
    def get_asset_config(cls) -> Dict[str, Any]:
        """
        Get asset configuration with intelligent defaults.
        
        Returns:
            Dictionary containing:
            - file_extension: Default file extension for models/assets
            - directory_name: Default directory name for asset storage
            - credential_patterns: List of environment variable patterns needed
            - cache_types: List of cache types used (models, runtime, temp, etc.)
            - model_urls: Dictionary of model URLs for downloads
        """
        return {
            "file_extension": cls._get_default_extension(),
            "directory_name": cls._get_default_directory(),
            "credential_patterns": cls._get_default_credentials(),
            "cache_types": cls._get_default_cache_types(),
            "model_urls": cls._get_default_model_urls()
        }
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """
        Override in provider classes for intelligent file extension defaults.
        
        Returns:
            Default file extension (e.g., ".pt", ".wav", ".json")
        """
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """
        Override in provider classes for intelligent directory name defaults.
        
        Returns:
            Default directory name for asset storage
        """
        # Default to lowercase class name without "Provider" suffix
        name = cls.__name__.lower()
        if name.endswith('provider'):
            name = name[:-8]  # Remove 'provider' suffix
        return name
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """
        Override in provider classes for intelligent credential defaults.
        
        Returns:
            List of environment variable patterns needed by provider
        """
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """
        Override in provider classes for intelligent cache type defaults.
        
        Returns:
            List of cache types used: ["models", "runtime", "temp", "downloads"]
        """
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """
        Override in provider classes for intelligent model URL defaults.
        
        Returns:
            Dictionary mapping model IDs to download URLs
        """
        return {}


class ProviderBase(EntryPointMetadata, ABC):
    """
    Base class for all provider implementations.
    
    Provides common functionality like configuration management,
    logging, status tracking, and asset configuration.
    
    Enhanced in TODO #4 Phase 1 with asset configuration support.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize provider with configuration.
        
        Args:
            config: Provider-specific configuration dictionary
        """
        self.config = config
        self._status = ProviderStatus.UNKNOWN
        self._last_error: Optional[str] = None
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    @property
    def status(self) -> ProviderStatus:
        """Current provider status"""
        return self._status
        
    @property 
    def last_error(self) -> Optional[str]:
        """Last error message, if any"""
        return self._last_error
        
    def _set_status(self, status: ProviderStatus, error: Optional[str] = None) -> None:
        """Update provider status and error message"""
        self._status = status
        self._last_error = error
        if error:
            self.logger.error(f"Provider status changed to {status.value}: {error}")
        else:
            self.logger.debug(f"Provider status changed to {status.value}")
    
    def get_asset_config(self) -> Dict[str, Any]:
        """
        Get asset configuration with TOML overrides and intelligent defaults.
        
        This method implements the configuration-driven asset management pattern
        by combining provider class defaults with TOML configuration overrides.
        
        Returns:
            Dictionary containing complete asset configuration
        """
        # Get intelligent defaults from class methods
        defaults = super().get_asset_config()
        
        # Get TOML configuration overrides if available
        asset_section = self.config.get("assets", {})
        
        # Merge defaults with TOML overrides
        result = {
            "file_extension": asset_section.get("file_extension", defaults["file_extension"]),
            "directory_name": asset_section.get("directory_name", defaults["directory_name"]),
            "credential_patterns": asset_section.get("credential_patterns", defaults["credential_patterns"]),
            "cache_types": asset_section.get("cache_types", defaults["cache_types"]),
            "model_urls": asset_section.get("model_urls", defaults["model_urls"])
        }
        
        return result
            
    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if provider is available and can be used.
        
        Returns:
            True if provider is ready for use
        """
        pass
        
    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get unique provider identifier.
        
        Returns:
            Unique provider name
        """
        pass
        
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with fallback.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)
        
    def validate_config(self) -> bool:
        """
        Validate provider configuration.
        
        Returns:
            True if configuration is valid
        """
        return True  # Override in subclasses for specific validation
        
    async def initialize(self) -> None:
        """
        Initialize provider resources.
        Called after construction and configuration validation.
        """
        self._set_status(ProviderStatus.INITIALIZING)
        try:
            await self._do_initialize()
            if await self.is_available():
                self._set_status(ProviderStatus.AVAILABLE)
            else:
                self._set_status(ProviderStatus.UNAVAILABLE, "Provider not available after initialization")
        except Exception as e:
            self._set_status(ProviderStatus.ERROR, str(e))
            raise
            
    async def _do_initialize(self) -> None:
        """Override in subclasses for provider-specific initialization"""
        pass
        
    async def cleanup(self) -> None:
        """Clean up provider resources"""
        pass 