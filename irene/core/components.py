"""
Component Management - Optional component loading and lifecycle

Handles optional components with graceful dependency checking,
automatic fallbacks, and component lifecycle management.
Enhanced with existing utilities from loader.py.
"""

import asyncio
import logging
from typing import Optional, Any, Type, TypeVar, Dict, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ..config.models import CoreConfig, ComponentConfig
from ..utils.loader import DependencyChecker, get_component_status
from ..components.base import Component

logger = logging.getLogger(__name__)

T = TypeVar('T', bound='Component')


class ComponentNotAvailable(Exception):
    """Raised when optional component dependencies are missing"""
    pass



@dataclass
class ComponentInfo:
    """Information about a component's status and capabilities"""
    name: str
    available: bool
    initialized: bool = False
    error_message: Optional[str] = None
    dependencies: Optional[list[str]] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class DependencyResolver:
    """Resolves component dependencies using topological sorting"""
    
    def __init__(self, components_config: Dict[str, Type]):
        self.components_config = components_config
        
    def resolve_initialization_order(self, enabled_components: List[str]) -> List[str]:
        """Resolve component initialization order based on dependencies"""
        # Build dependency graph (reversed for correct topological sort)
        dependency_graph = {component: [] for component in enabled_components}
        
        for component_name in enabled_components:
            if component_name in self.components_config:
                try:
                    component_class = self.components_config[component_name]
                    # Create temporary instance to get dependencies
                    temp_instance = component_class()
                    dependencies = temp_instance.get_component_dependencies()
                    
                    # For each dependency, add an edge FROM dependency TO component
                    for dep in dependencies:
                        if dep in enabled_components:
                            dependency_graph[dep].append(component_name)
                except Exception:
                    # If we can't determine dependencies, assume no dependencies
                    pass
        
        # Topological sort
        return self._topological_sort(dependency_graph)
    
    def _topological_sort(self, graph: Dict[str, List[str]]) -> List[str]:
        """Perform topological sort on dependency graph"""
        in_degree = {node: 0 for node in graph}
        for node in graph:
            for neighbor in graph[node]:
                if neighbor in in_degree:
                    in_degree[neighbor] += 1
        
        queue = [node for node in in_degree if in_degree[node] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in graph.get(node, []):
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
        
        return result


class ComponentManager:
    """
    V14 Component Manager - Advanced component management with dependency injection
    
    Features:
    - V14 CoreConfig integration with direct component mapping
    - Entry-point discovery for all components
    - Sophisticated dependency injection system
    - Topological dependency resolution
    - Advanced graceful degradation with fallbacks
    - Component-specific configuration access
    """
    
    def __init__(self, config: CoreConfig):
        self.config = config
        self._components: Dict[str, Component] = {}
        self._failed_components: Dict[str, Exception] = {}
        self._dependency_resolver: Optional[DependencyResolver] = None
        self._initialized = False
        self.dependency_checker = DependencyChecker()  # From loader.py
    
    def get_available_components(self) -> Dict[str, Type]:
        """Get available components through existing entry-point discovery"""
        # Use EXISTING dynamic_loader instead of hardcoded dictionary
        from ..utils.loader import dynamic_loader
        return dynamic_loader.discover_providers("irene.components")
        
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status using loader.py utilities"""
        return get_component_status()  # From loader.py
        
    async def initialize_components(self, core) -> None:
        """Initialize all configured components using V14 architecture with dependency injection"""
        if self._initialized:
            return
            
        logger.info("Initializing V14 component system with dependency injection...")
        
        # Get available components and create dependency resolver
        available_components = self.get_available_components()
        self._dependency_resolver = DependencyResolver(available_components)
        
        # Get enabled components
        enabled_components = [name for name in available_components.keys() 
                            if self._is_component_enabled(name)]
        
        # Resolve initialization order based on dependencies
        initialization_order = self._dependency_resolver.resolve_initialization_order(enabled_components)
        logger.info(f"Component initialization order: {initialization_order}")
        
        # Initialize components in dependency order
        await self._initialize_components_with_dependency_injection(core, initialization_order, available_components)
        
        # Post-initialization coordination (Phase 2: Donation coordination)
        await self._post_initialize_coordination()
        
        self._initialized = True
        
        # Log deployment profile and status
        profile = self.get_deployment_profile()
        success_count = len(self._components)
        failed_count = len(self._failed_components)
        logger.info(f"V14 Components initialized. Profile: {profile}, Success: {success_count}, Failed: {failed_count}")
        
        if self._failed_components:
            logger.warning(f"Failed components with graceful degradation: {list(self._failed_components.keys())}")
    
    async def _initialize_components_with_dependency_injection(self, core, initialization_order: List[str], available_components: Dict[str, Type]) -> None:
        """Initialize components with sophisticated dependency injection and graceful degradation"""
        
        for component_name in initialization_order:
            if component_name not in available_components:
                continue
                
            component_class = available_components[component_name]
            
            try:
                # Create component instance
                component_instance = component_class()
                
                # Inject configuration
                component_config = self._get_component_config(component_name)
                if component_config:
                    component_instance.config = component_config
                
                # Inject component dependencies
                await self._inject_component_dependencies(component_instance)
                
                # Inject service dependencies
                await self._inject_service_dependencies(component_instance, core)
                
                # Initialize component
                await component_instance.initialize(core)
                
                # Store successfully initialized component
                self._components[component_name] = component_instance
                logger.info(f"✅ Component '{component_name}' initialized successfully with dependency injection")
                
            except Exception as e:
                # Advanced graceful degradation
                await self._handle_component_failure(component_name, e, initialization_order)
    
    async def _post_initialize_coordination(self) -> None:
        """
        Handle post-initialization coordination between components.
        
        This method is called after all components are initialized to handle
        cross-component coordination that requires all components to be available.
        """
        logger.info("Starting post-initialization coordination...")
        
        # Coordinate NLU and Intent components for donation loading (Phase 2)
        nlu_component = self._components.get('nlu')
        if nlu_component and hasattr(nlu_component, 'post_initialize_coordination'):
            try:
                await nlu_component.post_initialize_coordination()
                logger.info("✅ NLU post-initialization coordination completed")
            except Exception as e:
                logger.error(f"❌ NLU post-initialization coordination failed: {e}")
                # Don't fail the entire system for coordination issues
                logger.warning("Continuing with NLU fallback patterns")
        
        # Inject component dependencies into intent handlers (Phase 3)
        intent_component = self._components.get('intent_system')
        if intent_component and hasattr(intent_component, 'post_initialize_handler_dependencies'):
            try:
                await intent_component.post_initialize_handler_dependencies(self)
                logger.info("✅ Intent handler dependency injection completed")
            except Exception as e:
                logger.error(f"❌ Intent handler dependency injection failed: {e}")
                # Don't fail the entire system for injection issues
                logger.warning("Continuing with intent handlers in limited dependency mode")
        
        # Inject context manager into intent handlers for fire-and-forget action tracking
        if intent_component and hasattr(intent_component, 'set_context_manager') and hasattr(self, 'context_manager'):
            try:
                intent_component.set_context_manager(self.context_manager)
                logger.info("✅ Context manager injected into intent handlers for fire-and-forget tracking")
            except Exception as e:
                logger.error(f"❌ Context manager injection failed: {e}")
                logger.warning("Continuing without fire-and-forget context tracking")
        
        logger.info("Post-initialization coordination completed")
    
    async def _inject_component_dependencies(self, component: Component) -> None:
        """Inject component dependencies"""
        required_components = component.get_component_dependencies()
        
        for dep_name in required_components:
            if dep_name in self._components:
                component.inject_dependency(dep_name, self._components[dep_name])
                logger.debug(f"Injected component dependency '{dep_name}' into '{component.name}'")
            else:
                logger.warning(f"Component dependency '{dep_name}' not available for '{component.name}'")
    
    async def _inject_service_dependencies(self, component: Component, core) -> None:
        """Inject service dependencies (core services like context manager, etc.)"""
        required_services = component.get_service_dependencies()
        
        for service_name, expected_type in required_services.items():
            service = None
            
            # Map service names to core services
            service_mapping = {
                'context_manager': getattr(core, 'context_manager', None),  # Use unified context manager
                'timer_manager': getattr(core, 'timer_manager', None),
                'workflow_manager': getattr(core, 'workflow_manager', None),
                'plugin_manager': getattr(core, 'plugin_manager', None),
                'input_manager': getattr(core, 'input_manager', None),
                'config': self.config
            }
            
            service = service_mapping.get(service_name)
            
            if service and isinstance(service, expected_type):
                component.inject_dependency(service_name, service)
                logger.debug(f"Injected service dependency '{service_name}' into '{component.name}'")
            elif service:
                logger.warning(f"Service '{service_name}' type mismatch for '{component.name}': expected {expected_type}, got {type(service)}")
            else:
                logger.warning(f"Service dependency '{service_name}' not available for '{component.name}'")
    
    async def _handle_component_failure(self, component_name: str, error: Exception, initialization_order: List[str]) -> None:
        """Handle component failure with advanced graceful degradation"""
        self._failed_components[component_name] = error
        
        # Check if we can use fallback components
        fallback_found = await self._attempt_fallback_initialization(component_name, error)
        
        if not fallback_found:
            logger.error(f"❌ Component '{component_name}' failed to initialize: {error}")
            
            # Check if this failure affects dependent components
            dependent_components = [comp for comp in initialization_order 
                                 if comp not in self._components and comp not in self._failed_components]
            
            affected_dependents = []
            for dep_comp_name in dependent_components:
                if component_name in self._get_component_dependencies_for(dep_comp_name):
                    affected_dependents.append(dep_comp_name)
            
            if affected_dependents:
                logger.warning(f"Component '{component_name}' failure may affect: {affected_dependents}")
    
    async def _attempt_fallback_initialization(self, component_name: str, original_error: Exception) -> bool:
        """Attempt to initialize fallback or alternative components"""
        # Define fallback mappings for critical components
        fallback_mapping = {
            'tts': ['console_tts', 'fallback_tts'],
            'audio': ['console_audio', 'fallback_audio'],
            'asr': ['fallback_asr'],
            'llm': ['console_llm', 'fallback_llm']
        }
        
        fallbacks = fallback_mapping.get(component_name, [])
        
        for fallback_name in fallbacks:
            try:
                # Try to initialize fallback component
                available_components = self.get_available_components()
                if fallback_name in available_components:
                    logger.info(f"Attempting fallback '{fallback_name}' for failed component '{component_name}'")
                    # This would need to be implemented based on available fallback components
                    # For now, just log the attempt
                    logger.info(f"Fallback component '{fallback_name}' would be initialized here")
                    return False  # Return True when actually implemented
            except Exception as e:
                logger.debug(f"Fallback '{fallback_name}' also failed: {e}")
        
        return False
    
    def _get_component_dependencies_for(self, component_name: str) -> List[str]:
        """Get component dependencies for a given component name"""
        try:
            available_components = self.get_available_components()
            if component_name in available_components:
                temp_instance = available_components[component_name]()
                return temp_instance.get_component_dependencies()
        except Exception:
            pass
        return []

    def _is_component_enabled(self, component_name: str) -> bool:
        """V14: Check if component is enabled using direct components mapping"""
        return getattr(self.config.components, component_name, False)
        
    def _get_component_config(self, component_name: str) -> Optional[Any]:
        """V14: Get component-specific configuration"""
        return getattr(self.config, component_name, None)
        
    def has_component(self, name: str) -> bool:
        """Check if a component is available and initialized"""
        return name in self._components and self._components[name].initialized
        
    def get_component(self, name: str) -> Optional[Component]:
        """Get a component by name"""
        return self._components.get(name)
        
    def get_active_components(self) -> list[str]:
        """Get list of active (initialized) component names"""
        return list(self._components.keys())
    
    def get_components(self) -> Dict[str, Component]:
        """Get all component instances (for WorkflowManager)"""
        return self._components.copy()
        
    def get_deployment_profile(self) -> str:
        """Detect deployment profile based on enabled components"""
        components = self.config.components
        system = self.config.system
        inputs = self.config.inputs
        
        # Voice profile: microphone input + TTS + Audio + ASR
        if (inputs.microphone and components.tts and 
            components.audio and components.asr):
            return "voice"
        
        # API profile: web input only + minimal components
        elif (inputs.web and not inputs.microphone and 
              system.web_api_enabled and not components.tts):
            return "api"
        
        # Headless profile: CLI only, no audio/TTS
        elif (inputs.cli and not inputs.microphone and 
              not system.web_api_enabled and not components.tts):
            return "headless"
        
        # Custom profile
        else:
            enabled_components = [name for name in 
                               ['tts', 'audio', 'asr', 'llm', 'voice_trigger', 'nlu', 'text_processor'] 
                               if getattr(components, name, False)]
            return f"custom({len(enabled_components)} components)"
    
    async def shutdown_all(self) -> None:
        """Shutdown all components with proper dependency order"""
        if not self._initialized:
            return
            
        logger.info("Shutting down V14 component system...")
        
        # Shutdown in reverse order of initialization
        shutdown_order = list(reversed(list(self._components.keys())))
        
        for component_name in shutdown_order:
            component = self._components.get(component_name)
            if component:
                try:
                    await component.shutdown()
                    logger.info(f"✅ Component '{component_name}' shutdown successfully")
                except Exception as e:
                    logger.error(f"❌ Error shutting down component '{component_name}': {e}")
        
        self._components.clear()
        self._failed_components.clear()
        self._initialized = False
        
        logger.info("V14 component system shutdown completed")
            
    def get_component_info(self) -> dict[str, ComponentInfo]:
        """Get information about all components (successful and failed)"""
        info = {}
        
        # Report on successfully initialized components
        for name, component in self._components.items():
            info[name] = ComponentInfo(
                name=name,
                available=True,
                initialized=component.initialized,
                dependencies=component.get_python_dependencies()
            )
        
        # Report on failed components
        for name, error in self._failed_components.items():
            info[name] = ComponentInfo(
                name=name,
                available=False,
                initialized=False,
                error_message=str(error),
                dependencies=[]
            )
                
        return info
    
    def get_failed_components(self) -> Dict[str, Exception]:
        """Get dictionary of failed components and their errors"""
        return self._failed_components.copy()
    
    def is_component_failed(self, component_name: str) -> bool:
        """Check if a component failed to initialize"""
        return component_name in self._failed_components 