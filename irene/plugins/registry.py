"""
Plugin Registry - Plugin discovery and registration

Handles plugin discovery from directories, validation,
and registration for loading.
"""

import asyncio
import importlib.util
import inspect
from typing import List, Dict, Type, Set, Optional
from pathlib import Path
import logging

from ..core.interfaces.plugin import PluginInterface

logger = logging.getLogger(__name__)


class PluginDiscoveryError(Exception):
    """Exception raised during plugin discovery"""
    pass


class PluginValidationError(Exception):
    """Exception raised during plugin validation"""
    pass


class PluginRegistry:
    """
    Discovers and registers plugins from filesystem and configuration.
    
    Features:
    - Concurrent plugin discovery
    - Error tracking and reporting
    - Dependency validation
    - Plugin metadata extraction
    - Circular dependency detection
    """
    
    def __init__(self):
        self._discovered_plugins: dict[str, Type[PluginInterface]] = {}
        self._plugin_metadata: dict[str, dict] = {}
        self._scanned_paths: set[Path] = set()
        self._errors: list[dict] = []  # Track discovery errors
        
    async def scan_directory(self, directory: Path) -> None:
        """
        Scan a directory for plugins.
        
        Args:
            directory: Directory path to scan for plugins
            
        Raises:
            PluginDiscoveryError: If directory scanning fails
        """
        if directory in self._scanned_paths:
            logger.debug(f"Directory already scanned: {directory}")
            return
            
        self._scanned_paths.add(directory)
        
        if not directory.exists() or not directory.is_dir():
            error_msg = f"Plugin directory does not exist: {directory}"
            logger.warning(error_msg)
            self._errors.append({
                "type": "directory_not_found",
                "path": str(directory),
                "message": error_msg
            })
            return
            
        logger.info(f"Scanning for plugins in: {directory}")
        
        try:
            # Scan for Python files
            python_files = list(directory.glob("**/*.py"))
            
            scan_tasks = []
            for file_path in python_files:
                if file_path.name.startswith("__"):
                    continue
                scan_tasks.append(self._scan_file(file_path))
                
            # Process files concurrently
            if scan_tasks:
                await asyncio.gather(*scan_tasks, return_exceptions=True)
                
        except Exception as e:
            error_msg = f"Failed to scan directory {directory}: {e}"
            logger.error(error_msg)
            self._errors.append({
                "type": "directory_scan_error",
                "path": str(directory),
                "message": error_msg,
                "exception": str(e)
            })
            raise PluginDiscoveryError(error_msg) from e
            
    async def _scan_file(self, file_path: Path) -> None:
        """Scan a Python file for plugin classes"""
        try:
            # Load module
            spec = importlib.util.spec_from_file_location(
                f"plugin_{file_path.stem}", file_path
            )
            if not spec or not spec.loader:
                return
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find plugin classes
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if self._is_valid_plugin_class(obj):
                    await self._register_plugin_class(obj, file_path)
                    
        except Exception as e:
            error_msg = f"Error scanning plugin file {file_path}: {e}"
            logger.error(error_msg)
            self._errors.append({
                "type": "file_scan_error",
                "path": str(file_path),
                "message": error_msg,
                "exception": str(e)
            })
            
    def _is_valid_plugin_class(self, cls) -> bool:
        """Check if a class is a valid plugin"""
        try:
            # Must inherit from PluginInterface
            if not issubclass(cls, PluginInterface):
                return False
                
            # Must not be abstract base class or interface itself
            if cls is PluginInterface:
                return False
                
            # Must be instantiable
            if inspect.isabstract(cls):
                return False
                
            # Try to create temporary instance to validate
            try:
                temp_instance = cls()
                # Check required properties
                if not hasattr(temp_instance, 'name') or not temp_instance.name:
                    return False
                if not hasattr(temp_instance, 'version') or not temp_instance.version:
                    return False
            except Exception:
                return False
                
            return True
            
        except (TypeError, AttributeError):
            return False
            
    async def _register_plugin_class(self, plugin_class: Type[PluginInterface], file_path: Path) -> None:
        """Register a valid plugin class"""
        try:
            # Create temporary instance to get metadata
            temp_instance = plugin_class()
            plugin_name = temp_instance.name
            
            # Check for name conflicts
            if plugin_name in self._discovered_plugins:
                existing_plugin = self._discovered_plugins[plugin_name]
                if existing_plugin != plugin_class:
                    error_msg = f"Plugin name conflict: {plugin_name} (found in {file_path})"
                    logger.warning(error_msg)
                    self._errors.append({
                        "type": "name_conflict",
                        "plugin_name": plugin_name,
                        "path": str(file_path),
                        "message": error_msg
                    })
                return
                
            # Store plugin class
            self._discovered_plugins[plugin_name] = plugin_class
            
            # Store metadata
            self._plugin_metadata[plugin_name] = {
                "name": temp_instance.name,
                "version": temp_instance.version,
                "description": temp_instance.description,
                "dependencies": temp_instance.dependencies,
                "optional_dependencies": temp_instance.optional_dependencies,
                "class": plugin_class.__name__,
                "module": plugin_class.__module__,
                "file_path": str(file_path),
                "config_schema": temp_instance.get_config_schema()
            }
            
            logger.debug(f"Registered plugin: {plugin_name} v{temp_instance.version}")
            
        except Exception as e:
            error_msg = f"Error registering plugin {plugin_class.__name__}: {e}"
            logger.error(error_msg)
            self._errors.append({
                "type": "registration_error",
                "plugin_class": plugin_class.__name__,
                "path": str(file_path),
                "message": error_msg,
                "exception": str(e)
            })
            
    async def get_discovered_plugins(self) -> List[Type[PluginInterface]]:
        """Get all discovered plugin classes"""
        return list(self._discovered_plugins.values())
        
    def get_plugin_class(self, plugin_name: str) -> Optional[Type[PluginInterface]]:
        """Get a specific plugin class by name"""
        return self._discovered_plugins.get(plugin_name)
        
    def get_plugin_metadata(self, plugin_name: str) -> Optional[Dict]:
        """Get metadata for a specific plugin"""
        return self._plugin_metadata.get(plugin_name, {})
        
    def list_plugin_names(self) -> List[str]:
        """Get list of all discovered plugin names"""
        return list(self._discovered_plugins.keys())
        
    def get_plugins_by_dependency(self, dependency: str) -> List[str]:
        """Get plugins that depend on a specific dependency"""
        result = []
        for name, metadata in self._plugin_metadata.items():
            deps = metadata.get("dependencies", []) + metadata.get("optional_dependencies", [])
            if dependency in deps:
                result.append(name)
        return result
        
    def validate_dependencies(self) -> Dict[str, List[str]]:
        """
        Validate plugin dependencies.
        
        Returns:
            Dictionary mapping plugin names to missing dependencies
        """
        missing_deps = {}
        all_plugin_names = set(self._discovered_plugins.keys())
        
        for name, metadata in self._plugin_metadata.items():
            missing = []
            for dep in metadata.get("dependencies", []):
                if dep not in all_plugin_names:
                    missing.append(dep)
            if missing:
                missing_deps[name] = missing
                
        return missing_deps
        
    def validate_all_plugins(self) -> Dict[str, List[str]]:
        """
        Validate all discovered plugins and return issues.
        
        Returns:
            Dictionary mapping plugin names to list of validation issues
        """
        issues = {}
        
        # Check dependencies
        missing_deps = self.validate_dependencies()
        issues.update({name: [f"Missing dependency: {dep}" for dep in deps] 
                      for name, deps in missing_deps.items()})
        
        # Check for circular dependencies
        circular_deps = self._detect_circular_dependencies()
        for cycle in circular_deps:
            for plugin_name in cycle:
                if plugin_name not in issues:
                    issues[plugin_name] = []
                issues[plugin_name].append(f"Circular dependency detected: {' -> '.join(cycle)}")
        
        return issues
        
    def _detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies between plugins"""
        cycles = []
        
        def has_path(start: str, end: str, visited: set[str]) -> bool:
            if start == end:
                return True
            if start in visited:
                return False
            visited.add(start)
            
            for neighbor in graph.get(start, []):
                if has_path(neighbor, end, visited.copy()):
                    return True
            return False
        
        for plugin_name in self._plugin_metadata:
            metadata = self._plugin_metadata[plugin_name]
            for dep in metadata.get("dependencies", []):
                if has_path(dep, plugin_name, set()):
                    cycles.append([plugin_name, dep])
        
        return cycles
        
    def get_discovery_errors(self) -> List[Dict]:
        """Get list of errors encountered during discovery"""
        return self._errors.copy()
        
    def clear_errors(self) -> None:
        """Clear accumulated errors"""
        self._errors.clear()
        
    def get_statistics(self) -> Dict:
        """Get registry statistics"""
        return {
            "plugins_discovered": len(self._discovered_plugins),
            "paths_scanned": len(self._scanned_paths),
            "errors_encountered": len(self._errors),
            "dependency_issues": len(self.validate_dependencies()),
            "circular_dependencies": len(self._detect_circular_dependencies())
        }
        
    @property
    def plugin_count(self) -> int:
        """Get number of discovered plugins"""
        return len(self._discovered_plugins)
        
    def reset(self) -> None:
        """Reset the registry to initial state"""
        self._discovered_plugins.clear()
        self._plugin_metadata.clear()
        self._scanned_paths.clear()
        self._errors.clear()
        logger.info("Plugin registry reset") 