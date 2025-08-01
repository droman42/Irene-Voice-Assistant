"""
Component Loading Utilities

Helper functions for graceful component loading and dependency management.
"""

import logging
from typing import Optional, Any, Callable, TypeVar
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