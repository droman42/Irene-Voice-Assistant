"""Base component class for fundamental voice assistant components."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type

from pydantic import BaseModel
from ..core.metadata import EntryPointMetadata
from ..config.models import CoreConfig

logger = logging.getLogger(__name__)


class Component(EntryPointMetadata, ABC):
    """Base class for all fundamental components."""
    
    def __init__(self):
        """Initialize the component."""
        # Use property-compatible name access for logging
        component_name = getattr(self, 'name', self.__class__.__name__)
        self.logger = logging.getLogger(f"{__name__}.{component_name}")
        self.providers: Dict[str, Any] = {}
        self.default_provider: Optional[str] = None
        self.initialized = False
    
    @abstractmethod
    def get_dependencies(self) -> List[str]:
        """
        Get list of dependencies for this component.
        
        Returns:
            List of required package names
        """
        pass
    
    @abstractmethod
    def get_providers_info(self) -> str:
        """
        Get human-readable information about available providers.
        
        Returns:
            Formatted string with provider information for user display
        """
        pass
    
    @classmethod
    @abstractmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the Pydantic config model for this component"""
        pass
    
    @classmethod  
    @abstractmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to this component's config"""
        pass
    
    def get_config(self, core_config: CoreConfig) -> Optional[BaseModel]:
        """Get this component's configuration instance"""
        config_class = self.get_config_class()
        config_path = self.get_config_path()
        # TODO: This will be implemented in Phase 2 - Config Path Resolution System
        from ..config.resolver import extract_config_by_path
        return extract_config_by_path(core_config, config_path, config_class)
    
    def is_enabled(self, core_config: CoreConfig) -> bool:
        """Check if this component is enabled via its config"""
        config = self.get_config(core_config)
        if config is None:
            return False
        return getattr(config, 'enabled', True)
    
    @classmethod
    def is_enabled_in_config(cls, core_config: CoreConfig) -> bool:
        """Class method to check if component is enabled without instantiation"""
        try:
            config_class = cls.get_config_class()
            config_path = cls.get_config_path()
            # TODO: This will be implemented in Phase 2 - Config Path Resolution System
            from ..config.resolver import extract_config_by_path
            config = extract_config_by_path(core_config, config_path, config_class)
            if config is None:
                return False
            return getattr(config, 'enabled', True)
        except Exception:
            return False
    
    def parse_provider_name_from_text(self, text: str) -> Optional[str]:
        """
        Extract provider name from user text/voice command.
        
        Args:
            text: User input text (voice command, API request, etc.)
            
        Returns:
            Provider name if found, None otherwise
            
        Note: Default implementation provides basic keyword matching.
              Components can override for component-specific aliases.
        """
        text_lower = text.lower()
        
        # Try direct provider name match
        for provider_name in self.providers.keys():
            if provider_name.lower() in text_lower:
                return provider_name
        
        return None
    
    def switch_provider(self, provider_name: str) -> bool:
        """
        Switch to a different provider (alias for set_default_provider).
        
        Args:
            provider_name: Name of provider to switch to
            
        Returns:
            True if switch successful, False otherwise
        """
        return self.set_default_provider(provider_name)
    
    def get_provider_capabilities(self) -> Dict[str, Any]:
        """
        Get capabilities of all providers.
        
        Returns:
            Dictionary mapping provider names to their capabilities
        """
        capabilities = {}
        for name, provider in self.providers.items():
            if hasattr(provider, 'get_capabilities'):
                try:
                    capabilities[name] = provider.get_capabilities()
                except Exception as e:
                    capabilities[name] = {"error": str(e)}
            else:
                capabilities[name] = {"available": True}
        
        return capabilities
    
    def list_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return list(self.providers.keys())
    
    def is_provider_available(self, provider_name: str) -> bool:
        """Check if a specific provider is available."""
        return provider_name in self.providers
    
    async def initialize(self, core=None):
        """Initialize the component and its providers."""
        self.logger.info(f"Initializing component: {self.name}")
        self.initialized = True
    
    async def shutdown(self):
        """Shutdown the component and clean up resources."""
        for name, provider in self.providers.items():
            if hasattr(provider, 'shutdown'):
                try:
                    await provider.shutdown()
                    self.logger.info(f"Shutdown provider: {name}")
                except Exception as e:
                    self.logger.error(f"Error shutting down provider {name}: {e}")
        
        self.initialized = False
        self.logger.info(f"Component {self.name} shutdown complete")
    
    def add_provider(self, name: str, provider: Any):
        """
        Add a provider to this component.
        
        Args:
            name: Provider name
            provider: Provider instance
        """
        self.providers[name] = provider
        if self.default_provider is None:
            self.default_provider = name
        self.logger.info(f"Added provider '{name}' to component {self.name}")
    
    def set_default_provider(self, name: str) -> bool:
        """
        Set the default provider for this component.
        
        Args:
            name: Provider name to set as default
            
        Returns:
            True if provider was set successfully, False otherwise
        """
        if name in self.providers:
            self.default_provider = name
            self.logger.info(f"Set default provider for {self.name}: {name}")
            return True
        else:
            self.logger.warning(f"Provider '{name}' not found in component {self.name}")
            return False
    
    def get_current_provider(self) -> Optional[Any]:
        """
        Get the current default provider.
        
        Returns:
            Current provider instance or None
        """
        if self.default_provider and self.default_provider in self.providers:
            return self.providers[self.default_provider]
        elif self.providers:
            # Return first available provider
            return next(iter(self.providers.values()))
        return None
    
    async def is_available(self) -> bool:
        """
        Check if the component is available and functioning.
        
        Returns:
            True if component is available
        """
        if not self.initialized:
            return False
        
        provider = self.get_current_provider()
        if provider and hasattr(provider, 'is_available'):
            try:
                return await provider.is_available()
            except Exception:
                return False
        
        return provider is not None
    
    async def is_healthy(self) -> bool:
        """
        Check if the component is healthy and ready for use.
        
        Returns:
            True if component is healthy
        """
        return await self.is_available()
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get component capabilities and provider information.
        
        Returns:
            Dictionary describing component capabilities
        """
        capabilities = {
            "name": self.name,
            "initialized": self.initialized,
            "providers": list(self.providers.keys()),
            "default_provider": self.default_provider,
            "dependencies": self.get_dependencies()
        }
        
        # Add provider capabilities
        provider_caps = {}
        for name, provider in self.providers.items():
            if hasattr(provider, 'get_capabilities'):
                try:
                    provider_caps[name] = provider.get_capabilities()
                except Exception as e:
                    provider_caps[name] = {"error": str(e)}
            else:
                provider_caps[name] = {"available": True}
        
        capabilities["provider_capabilities"] = provider_caps
        return capabilities
    
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about available providers.
        
        Returns:
            Dictionary with provider information
        """
        info = {}
        for name, provider in self.providers.items():
            provider_info = {
                "name": name,
                "class": provider.__class__.__name__,
                "is_default": name == self.default_provider
            }
            
            if hasattr(provider, 'get_info'):
                try:
                    provider_info.update(provider.get_info())
                except Exception as e:
                    provider_info["error"] = str(e)
            
            info[name] = provider_info
        
        return info
    
    def configure_provider(self, provider_name: str, config: Dict[str, Any]):
        """
        Configure a specific provider.
        
        Args:
            provider_name: Name of provider to configure
            config: Configuration dictionary
        """
        if provider_name not in self.providers:
            raise ValueError(f"Provider '{provider_name}' not found")
        
        provider = self.providers[provider_name]
        if hasattr(provider, 'configure'):
            provider.configure(config)
            self.logger.info(f"Configured provider {provider_name}")
        else:
            self.logger.warning(f"Provider {provider_name} does not support configuration")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current component status.
        
        Returns:
            Dictionary with component status information
        """
        return {
            "name": self.name,
            "initialized": self.initialized,
            "provider_count": len(self.providers),
            "default_provider": self.default_provider,
            "providers": list(self.providers.keys())
        }
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Components coordinate providers - minimal direct dependencies"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Components have no system dependencies - coordinate providers only"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Components support all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"] 