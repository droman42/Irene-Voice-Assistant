"""
Component Loading Utilities

Helper functions for graceful component loading and dependency management.
"""

import logging
from typing import Optional, Any, Callable, TypeVar, Dict, Type, List
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


def require_dependencies(*dependencies: str):
    """
    Decorator to check dependencies before executing a function.
    
    Args:
        dependencies: Module names that must be importable
        
    Raises:
        ImportError: If any dependency is missing
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            for dep in dependencies:
                try:
                    __import__(dep)
                except ImportError as e:
                    raise ImportError(f"Missing dependency '{dep}' for {func.__name__}: {e}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def safe_import(module_name: str, attribute: Optional[str] = None) -> Optional[Any]:
    """
    Safely import a module or attribute with graceful fallback.
    
    Args:
        module_name: Name of the module to import
        attribute: Optional attribute to get from the module
        
    Returns:
        The imported module/attribute or None if not available
    """
    try:
        module = __import__(module_name, fromlist=[attribute] if attribute else [])
        if attribute:
            return getattr(module, attribute)
        return module
    except (ImportError, AttributeError) as e:
        logger.debug(f"Safe import failed for {module_name}.{attribute or ''}: {e}")
        return None


def check_optional_dependency(component_name: str, module_name: str) -> bool:
    """
    Check if an optional dependency is available.
    
    Args:
        component_name: Name of the component for logging
        module_name: Module to check
        
    Returns:
        True if dependency is available
    """
    try:
        __import__(module_name)
        logger.debug(f"Optional dependency '{module_name}' available for {component_name}")
        return True
    except ImportError:
        logger.debug(f"Optional dependency '{module_name}' not available for {component_name}")
        return False


class DependencyChecker:
    """
    Utility class for checking multiple dependencies with caching.
    """
    
    def __init__(self):
        self._cache: dict[str, bool] = {}
        
    def check(self, name: str, dependencies: list[str]) -> bool:
        """Check if all dependencies are available (with caching)"""
        if name in self._cache:
            return self._cache[name]
            
        try:
            for dep in dependencies:
                __import__(dep)
            self._cache[name] = True
            return True
        except ImportError:
            self._cache[name] = False
            return False
    
    def clear_cache(self) -> None:
        """Clear the dependency cache"""
        self._cache.clear()


# Global dependency checker instance
dependency_checker = DependencyChecker()


# ============================================================
# ENTRY-POINTS DISCOVERY SYSTEM - Phase 2 Implementation
# ============================================================
# Entry-points based loader that replaces hardcoded _provider_classes
# Enables configuration-driven loading and external package extensibility

try:
    # Modern approach for Python 3.10+
    from importlib.metadata import entry_points
except ImportError:
    # Fallback for older Python versions  
    entry_points = None
    try:
        from importlib_metadata import entry_points  # type: ignore
    except ImportError:
        # Ultimate fallback using pkg_resources
        try:
            import pkg_resources  # type: ignore
        except ImportError:
            pkg_resources = None


class DynamicLoader:
    """
    Entry-points based loader with configuration filtering.
    
    Replaces hardcoded _provider_classes dictionaries in components with
    dynamic discovery from entry-points + configuration-driven filtering.
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Type]] = {}
        
    def discover_providers(self, namespace: str, enabled: List[str] = None) -> Dict[str, Type]:
        """
        Discover providers via entry-points with optional configuration filtering.
        
        Args:
            namespace: Entry-points namespace (e.g., 'irene.providers.tts')
            enabled: Optional list of enabled provider names for filtering
            
        Returns:
            Dictionary mapping provider names to their classes
        """
        # Use cache if available
        cache_key = f"{namespace}:{','.join(enabled or [])}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        discovered = {}
        
        try:
            # Use modern importlib.metadata if available
            if entry_points and hasattr(entry_points, 'select'):
                # Python 3.10+ style
                eps = entry_points(group=namespace)
            elif entry_points:
                # Python 3.8-3.9 style  
                eps = entry_points().get(namespace, [])
            elif 'pkg_resources' in globals() and pkg_resources:
                # Fallback to pkg_resources
                eps = pkg_resources.iter_entry_points(namespace)
            else:
                # No entry-points mechanism available
                logger.warning(f"No entry-points mechanism available for namespace '{namespace}'")
                return {}
                
            for entry_point in eps:
                # Filter by enabled list if provided
                if enabled and entry_point.name not in enabled:
                    continue
                    
                try:
                    provider_class = entry_point.load()
                    discovered[entry_point.name] = provider_class
                    logger.debug(f"Loaded provider '{entry_point.name}' from entry-point")
                    
                except ImportError as e:
                    logger.warning(f"Provider '{entry_point.name}' not available (import failed): {e}")
                    continue
                except Exception as e:
                    logger.error(f"Failed to load provider '{entry_point.name}': {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Entry-points discovery failed for namespace '{namespace}': {e}")
            # Graceful fallback - return empty dict to allow component initialization
            return {}
            
        # Cache the result
        self._cache[cache_key] = discovered
        
        logger.info(f"Discovered {len(discovered)} providers in namespace '{namespace}': {list(discovered.keys())}")
        return discovered
        
    def get_provider_class(self, namespace: str, provider_name: str) -> Optional[Type]:
        """
        Get a specific provider class by name from entry-points.
        
        Args:
            namespace: Entry-points namespace
            provider_name: Name of the provider to load
            
        Returns:
            Provider class or None if not found
        """
        providers = self.discover_providers(namespace)
        return providers.get(provider_name)
        
    def list_available_providers(self, namespace: str) -> List[str]:
        """
        List all available provider names in a namespace.
        
        Args:
            namespace: Entry-points namespace
            
        Returns:
            List of available provider names
        """
        providers = self.discover_providers(namespace)
        return list(providers.keys())
        
    def clear_cache(self):
        """Clear the discovery cache"""
        self._cache.clear()


# Global dynamic loader instance
dynamic_loader = DynamicLoader()


def get_component_status() -> dict[str, dict[str, Any]]:
    """
    Get status of all known optional components.
    
    Returns:
        Dictionary with component availability information
    """
    components = {
        "microphone": ["vosk", "sounddevice", "soundfile"],
        "tts": ["pyttsx3"],
        "audio_output": ["sounddevice", "soundfile"],
        "web_api": ["fastapi", "uvicorn"],
        "config_writing": ["tomli_w"],
    }
    
    status = {}
    for name, deps in components.items():
        available = dependency_checker.check(name, deps)
        status[name] = {
            "available": available,
            "dependencies": deps,
            "missing": []
        }
        
        # Find which specific dependencies are missing
        if not available:
            for dep in deps:
                if not check_optional_dependency(name, dep):
                    status[name]["missing"].append(dep)
    
    return status


def suggest_installation(component_name: str) -> Optional[str]:
    """
    Suggest pip installation command for a component.
    
    Args:
        component_name: Name of the component
        
    Returns:
        Suggested pip install command or None
    """
    suggestions = {
        "microphone": "uv add irene-voice-assistant[audio-input]",
        "tts": "uv add irene-voice-assistant[tts]", 
        "audio_output": "uv add irene-voice-assistant[audio-output]",
        "web_api": "uv add irene-voice-assistant[web-api]",
        "voice": "uv add irene-voice-assistant[voice]",
        "all": "uv add irene-voice-assistant[all]"
    }
    
    return suggestions.get(component_name) 