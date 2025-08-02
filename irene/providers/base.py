"""
Provider Base Classes and Utilities

Common functionality and base classes for all provider implementations.
Providers are pure implementation classes managed by Universal Plugins.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ProviderStatus(Enum):
    """Provider availability status"""
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    INITIALIZING = "initializing"


class ProviderBase(ABC):
    """
    Base class for all provider implementations.
    
    Provides common functionality like configuration management,
    logging, and status tracking.
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