"""
WebAPI Router - FastAPI routes for Irene Voice Assistant

Extracted from webapi_runner.py to separate routing concerns from server setup.
Contains all endpoint definitions and request handlers.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, List, Optional

# Type imports - actual imports deferred to function scope to avoid circular dependencies
try:
    from ..core.engine import AsyncVACore
    from ..core.intent_asset_loader import IntentAssetLoader  
    from ..inputs.web import WebInput
    from fastapi import APIRouter  # type: ignore
except ImportError:
    # Handle import errors gracefully for type checking
    AsyncVACore = object
    IntentAssetLoader = object
    WebInput = object
    APIRouter = object

logger = logging.getLogger(__name__)


async def _generate_asyncapi_spec(core: AsyncVACore) -> Dict[str, Any]:
    """Generate combined AsyncAPI specification from all components"""
    from ..web_api.asyncapi import generate_base_asyncapi_spec, merge_asyncapi_specs
    
    try:
        # Start with base AsyncAPI spec
        base_spec = generate_base_asyncapi_spec()
        component_specs = []
        
        # Get WebAPI components (same logic as _mount_component_routers)
        if core:
            from ..core.interfaces.webapi import WebAPIPlugin
            web_components = []
            
            # Check component manager first
            if hasattr(core, 'component_manager'):
                try:
                    available_components = core.component_manager.get_components()
                    logger.debug(f"Found {len(available_components)} available components: {list(available_components.keys())}")
                    
                    for name, component in available_components.items():
                        if isinstance(component, WebAPIPlugin):
                            web_components.append((name, component))
                            logger.debug(f"Component {name} implements WebAPIPlugin")
                        else:
                            logger.debug(f"Component {name} does not implement WebAPIPlugin (type: {type(component).__name__})")
                            
                except Exception as e:
                    logger.warning(f"Could not get components from component manager: {e}")
            else:
                logger.warning("Core does not have component_manager")
            
            # Also check plugin manager
            if hasattr(core, 'plugin_manager'):
                try:
                    for name, plugin in core.plugin_manager._plugins.items():
                        if isinstance(plugin, WebAPIPlugin):
                            web_components.append((name, plugin))
                            logger.debug(f"Plugin {name} implements WebAPIPlugin")
                        else:
                            logger.debug(f"Plugin {name} does not implement WebAPIPlugin (type: {type(plugin).__name__})")
                except Exception as e:
                    logger.warning(f"Could not get plugins from plugin manager: {e}")
            else:
                logger.warning("Core does not have plugin_manager")
            
            logger.debug(f"Found {len(web_components)} WebAPIPlugin components for AsyncAPI generation")
            
            # Collect AsyncAPI specs from each component
            for name, component in web_components:
                try:
                    if hasattr(component, 'get_websocket_spec'):
                        spec = component.get_websocket_spec()
                        if spec:
                            component_specs.append(spec)
                            logger.debug(f"✅ Generated AsyncAPI spec for {name}")
                        else:
                            logger.debug(f"⚪ Component {name} has no WebSocket endpoints")
                    else:
                        logger.debug(f"⚪ Component {name} doesn't implement get_websocket_spec")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to generate AsyncAPI spec for {name}: {e}")
            
            # Merge all specs
            merged_spec = merge_asyncapi_specs(base_spec, component_specs)
            
            logger.info(f"✅ Generated AsyncAPI spec with {len(merged_spec.get('channels', {}))} channels "
                       f"and {len(merged_spec.get('components', {}).get('messages', {}))} message types")
            
            return merged_spec
        
        else:
            logger.warning("Core or plugin manager not available for AsyncAPI generation")
            return base_spec
            
    except Exception as e:
        logger.error(f"Error generating AsyncAPI specification: {e}")
        return generate_base_asyncapi_spec()  # Return empty spec on error


def create_webapi_router(
    core: AsyncVACore, 
    asset_loader: Optional[IntentAssetLoader], 
    web_input: Optional[WebInput], 
    start_time: float
) -> APIRouter:
    """
    Create FastAPI router with all WebAPI endpoints
    
    Args:
        core: AsyncVACore instance for processing commands and component access
        asset_loader: IntentAssetLoader instance for serving HTML templates (can be None)
        web_input: WebInput instance for connection info (can be None)
        start_time: Server start time for uptime calculation
    
    Returns:
        FastAPI router with all endpoints configured
    """
    from fastapi import APIRouter, HTTPException, UploadFile, File  # type: ignore
    from fastapi.responses import HTMLResponse, Response  # type: ignore
    from pydantic import BaseModel  # type: ignore
    
    # Import centralized API schemas
    from ..api.schemas import CommandRequest, CommandResponse, TraceCommandResponse
    from ..core.trace_context import TraceContext
    from ..utils.loader import get_component_status
    from ..__version__ import __version__
    
    router = APIRouter()
    
    # Local response models for specific endpoints
    class StatusResponse(BaseModel):
        status: str
        components: Dict[str, Any]
        web_clients: int
        
    class HistoryResponse(BaseModel):
        messages: list[Dict[str, Any]]
        total_count: int
    
    class SystemCapabilitiesResponse(BaseModel):
        version: str
        components: Dict[str, Any]
        intent_handlers: List[str]
        nlu_providers: List[str]
        voice_trigger_providers: List[str]
        text_processing_providers: List[str]
        workflows: List[str]
    
    # Root endpoint
    @router.get("/", response_class=HTMLResponse, tags=["General"])
    async def root():
        """Serve a simple web interface"""
        if asset_loader:
            html_content = asset_loader.get_web_template_with_variables(
                "index",
                version=__version__
            )
            if html_content:
                return HTMLResponse(content=html_content)
            else:
                logger.error("Web template 'index' not found")
                raise HTTPException(status_code=500, detail="Web interface template not available")
        else:
            logger.error("Web asset loader not initialized")
            raise HTTPException(status_code=500, detail="Web asset system not available")
    
    # Status endpoint
    @router.get("/status", response_model=StatusResponse, tags=["General"])
    async def get_status():
        """Get assistant status and component information"""
        components = get_component_status()
        web_clients = 0  # WebSocket clients now handled by individual components
        
        return StatusResponse(
            status="running",
            components=components,
            web_clients=web_clients
        )
    
    # Command execution endpoint
    @router.post("/execute/command", response_model=CommandResponse, tags=["General"])
    async def execute_command(request: CommandRequest):
        """Execute a voice assistant command via REST API"""
        try:
            if not core:
                raise HTTPException(status_code=503, detail="Assistant not initialized")
            
            # Process command through unified workflow interface
            result = await core.workflow_manager.process_text_input(
                text=request.command,
                session_id="webapi_session",
                wants_audio=False,
                client_context={"source": "rest_api"}
            )
            
            return CommandResponse(
                success=result.success,
                response=result.text or f"Command '{request.command}' processed successfully",
                metadata={"processed_via": "rest_api", "intent_result": result.metadata}
            )
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return CommandResponse(
                success=False,
                response="Command execution failed",
                error=str(e)
            )
    
    # Audio execution endpoint
    @router.post("/execute/audio", response_model=CommandResponse, tags=["General"])
    async def execute_audio(audio_file: UploadFile = File(...)):
        """Execute audio processing via REST API"""
        try:
            if not core:
                raise HTTPException(status_code=503, detail="Assistant not initialized")
            
            # Validate file size (limit to 10MB for safety)
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
            file_size = 0
            audio_data = b""
            
            # Read audio data with size check
            while True:
                chunk = await audio_file.read(8192)  # Read in 8KB chunks
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413, 
                        detail=f"Audio file too large (max {MAX_FILE_SIZE / 1024 / 1024:.1f}MB)"
                    )
                audio_data += chunk
            
            logger.info(f"Audio processing: {audio_file.filename}, size: {file_size} bytes")
            
            # Process audio through workflow manager without tracing
            result = await core.workflow_manager.process_audio_input(
                audio_data=audio_data,
                session_id="audio_session",
                wants_audio=False,  # Don't generate TTS for API endpoint
                client_context={
                    "source": "audio_api",
                    "filename": audio_file.filename,
                    "skip_wake_word": True,  # Skip wake word for uploaded files
                    "file_size_bytes": file_size
                }
            )
            
            return CommandResponse(
                success=result.success,
                response=result.text or f"Audio file '{audio_file.filename}' processed successfully",
                metadata={"processed_via": "audio_api", "filename": audio_file.filename, "file_size_bytes": file_size}
            )
            
        except HTTPException:
            # Re-raise HTTP exceptions (like file too large)
            raise
            
        except Exception as e:
            logger.error(f"Audio execution error: {e}")
            return CommandResponse(
                success=False,
                response="Audio processing failed",
                error=str(e)
            )
    
    # Health check endpoint
    @router.get("/health", tags=["General"])
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "version": __version__,
            "timestamp": asyncio.get_event_loop().time()
        }
    
    # PHASE 7 - TODO16: Trace endpoints for detailed pipeline execution visibility
    @router.post("/trace/command", response_model=TraceCommandResponse, tags=["Tracing"])
    async def trace_command_execution(request: CommandRequest):
        """Execute command with full execution trace"""
        try:
            if not core:
                raise HTTPException(status_code=503, detail="Assistant not initialized")
            
            # Create trace context for detailed execution tracking with production limits
            trace_context = TraceContext(
                enabled=True, 
                request_id=str(uuid.uuid4()),
                max_stages=50,  # Limit stages for command traces
                max_data_size_mb=5  # 5MB limit for command traces
            )
            
            # Execute same workflow as normal command but with tracing
            result = await core.workflow_manager.process_text_input(
                text=request.command,
                session_id=request.metadata.get("session_id", "trace_session") if request.metadata else "trace_session",
                wants_audio=False,
                client_context={"source": "trace_api", "trace_enabled": True},
                trace_context=trace_context  # Pass trace context to workflow
            )
            
            return TraceCommandResponse(
                success=result.success,
                final_result={
                    "text": result.text,
                    "success": result.success,
                    "metadata": result.metadata,
                    "confidence": result.confidence,
                    "timestamp": result.timestamp
                },
                execution_trace={
                    "request_id": trace_context.request_id,
                    "pipeline_stages": [
                        {
                            "stage": stage.get("stage", "unknown"),
                            "input_data": stage.get("input"),
                            "output_data": stage.get("output"),
                            "metadata": stage.get("metadata", {}),
                            "processing_time_ms": stage.get("processing_time_ms", 0.0),
                            "timestamp": stage.get("timestamp", time.time())
                        }
                        for stage in trace_context.stages
                    ],
                    "context_evolution": {
                        "before": trace_context.context_snapshots.get("before"),
                        "after": trace_context.context_snapshots.get("after"),
                        "changes": trace_context._calculate_context_changes()
                    },
                    "performance_metrics": {
                        "total_processing_time_ms": sum(
                            stage.get("processing_time_ms", 0) for stage in trace_context.stages
                        ),
                        "stage_breakdown": {
                            stage.get("stage", "unknown"): stage.get("processing_time_ms", 0) 
                            for stage in trace_context.stages
                        },
                        "total_stages": len(trace_context.stages)
                    }
                },
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"Trace command execution error: {e}")
            trace_request_id = trace_context.request_id if 'trace_context' in locals() else "unknown"
            return TraceCommandResponse(
                success=False,
                final_result={},
                execution_trace={
                    "request_id": trace_request_id,
                    "pipeline_stages": [],
                    "context_evolution": {
                        "before": None,
                        "after": None,
                        "changes": {}
                    },
                    "performance_metrics": {
                        "total_processing_time_ms": 0.0,
                        "stage_breakdown": {},
                        "total_stages": 0
                    },
                    "error": str(e)
                },
                timestamp=time.time(),
                error=str(e)
            )
    
    @router.post("/trace/audio", response_model=TraceCommandResponse, tags=["Tracing"])
    async def trace_audio_execution(audio_file: UploadFile = File(...)):
        """Execute audio processing with full execution trace"""
        try:
            if not core:
                raise HTTPException(status_code=503, detail="Assistant not initialized")
            
            # Validate file size (limit to 10MB for safety)
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
            file_size = 0
            audio_data = b""
            
            # Read audio data with size check
            while True:
                chunk = await audio_file.read(8192)  # Read in 8KB chunks
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413, 
                        detail=f"Audio file too large (max {MAX_FILE_SIZE / 1024 / 1024:.1f}MB)"
                    )
                audio_data += chunk
            
            # Create trace context with production limits for audio
            trace_context = TraceContext(
                enabled=True, 
                request_id=str(uuid.uuid4()),
                max_stages=75,  # More stages for audio processing
                max_data_size_mb=15  # Higher limit for audio traces (includes audio data)
            )
            
            logger.info(f"Trace audio processing: {audio_file.filename}, size: {file_size} bytes")
            
            # Process audio through workflow manager with tracing
            result = await core.workflow_manager.process_audio_input(
                audio_data=audio_data,
                session_id="trace_audio_session",
                wants_audio=False,  # Don't generate TTS for trace endpoint
                client_context={
                    "source": "trace_audio_api",
                    "filename": audio_file.filename,
                    "skip_wake_word": True,  # Skip wake word for uploaded files
                    "file_size_bytes": file_size
                },
                trace_context=trace_context
            )
            
            return TraceCommandResponse(
                success=result.success,
                final_result={
                    "text": result.text,
                    "success": result.success,
                    "metadata": result.metadata,
                    "confidence": result.confidence,
                    "timestamp": result.timestamp
                },
                execution_trace={
                    "request_id": trace_context.request_id,
                    "pipeline_stages": [
                        {
                            "stage": stage.get("stage", "unknown"),
                            "input_data": stage.get("input"),
                            "output_data": stage.get("output"),
                            "metadata": stage.get("metadata", {}),
                            "processing_time_ms": stage.get("processing_time_ms", 0.0),
                            "timestamp": stage.get("timestamp", time.time())
                        }
                        for stage in trace_context.stages
                    ],
                    "context_evolution": {
                        "before": trace_context.context_snapshots.get("before"),
                        "after": trace_context.context_snapshots.get("after"),
                        "changes": trace_context._calculate_context_changes()
                    },
                    "performance_metrics": {
                        "total_processing_time_ms": sum(
                            stage.get("processing_time_ms", 0) for stage in trace_context.stages
                        ),
                        "stage_breakdown": {
                            stage.get("stage", "unknown"): stage.get("processing_time_ms", 0) 
                            for stage in trace_context.stages
                        },
                        "total_stages": len(trace_context.stages)
                    }
                },
                timestamp=time.time()
            )
            
        except HTTPException:
            # Re-raise HTTP exceptions (like file too large)
            raise
            
        except Exception as e:
            logger.error(f"Trace audio execution error: {e}")
            trace_request_id = trace_context.request_id if 'trace_context' in locals() else "unknown"
            return TraceCommandResponse(
                success=False,
                final_result={},
                execution_trace={
                    "request_id": trace_request_id,
                    "pipeline_stages": trace_context.stages if 'trace_context' in locals() else [],
                    "context_evolution": {
                        "before": trace_context.context_snapshots.get("before") if 'trace_context' in locals() else None,
                        "after": trace_context.context_snapshots.get("after") if 'trace_context' in locals() else None,
                        "changes": trace_context._calculate_context_changes() if 'trace_context' in locals() else {}
                    },
                    "performance_metrics": {
                        "total_processing_time_ms": sum(
                            stage.get("processing_time_ms", 0) for stage in trace_context.stages
                        ) if 'trace_context' in locals() else 0.0,
                        "stage_breakdown": {
                            stage.get("stage", "unknown"): stage.get("processing_time_ms", 0) 
                            for stage in trace_context.stages
                        } if 'trace_context' in locals() else {},
                        "total_stages": len(trace_context.stages) if 'trace_context' in locals() else 0
                    },
                    "error": str(e)
                },
                timestamp=time.time(),
                error=str(e)
            )
    
    # Component info endpoint
    @router.get("/components", tags=["General"])
    async def get_component_info():
        """Get detailed component information"""
        info = {}
        
        if web_input:
            info["web_input"] = web_input.get_connection_info()
        
        # Web output handled via HTTP responses (unified workflow)
        
        if core:
            info["core"] = {
                "input_sources": list(core.input_manager._sources.keys()),
                "workflows": list(core.workflow_manager.workflows.keys()),
                "plugins": core.plugin_manager.plugin_count
            }
        
        return info
    
    # System capabilities endpoint
    @router.get("/system/capabilities", response_model=SystemCapabilitiesResponse, tags=["General"])
    async def get_system_capabilities():
        """Get comprehensive system capabilities"""
        try:
            capabilities = {
                "version": __version__,
                "components": {},
                "intent_handlers": [],
                "nlu_providers": ["hybrid_keyword_matcher", "spacy_nlu"],
                "voice_trigger_providers": ["openwakeword"],
                "text_processing_providers": ["unified", "number"],
                "workflows": ["voice_assistant", "continuous_listening"]
            }
            
            # Get component status if available
            if core and hasattr(core, 'component_manager'):
                try:
                    component_status = await core.component_manager.get_available_components()
                    capabilities["components"] = {
                        name: {"available": True, "type": type(comp).__name__}
                        for name, comp in component_status.items()
                    }
                except Exception as e:
                    logger.warning(f"Could not get component status: {e}")
            
            return SystemCapabilitiesResponse(**capabilities)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Enhanced system status endpoint
    @router.get("/system/status", tags=["General"])
    async def get_enhanced_system_status():
        """Enhanced system status with intent system information"""
        try:
            status = {
                "system": "healthy",
                "version": __version__,
                "mode": "intent_system" if hasattr(core, 'workflow_manager') else "legacy",
                "timestamp": time.time(),
                "uptime": time.time() - start_time
            }
            
            # Add component information
            if core:
                status["core"] = {
                    "running": core.is_running,
                    "input_sources": len(getattr(core.input_manager, '_sources', {})),
                    "plugins": getattr(core.plugin_manager, 'plugin_count', 0)
                }
            
            # Web client information now handled by individual components
            status["web_clients"] = 0  # Component-specific WebSockets handle client tracking
            
            return status
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # AsyncAPI documentation endpoints
    @router.get("/asyncapi", response_class=HTMLResponse, include_in_schema=False)
    async def asyncapi_docs():
        """Serve AsyncAPI documentation page"""
        if asset_loader:
            html_content = asset_loader.get_web_template("asyncapi")
            if html_content:
                return HTMLResponse(content=html_content)
            else:
                logger.error("Web template 'asyncapi' not found")
                raise HTTPException(status_code=500, detail="AsyncAPI documentation template not available")
        else:
            logger.error("Web asset loader not initialized")
            raise HTTPException(status_code=500, detail="Web asset system not available")
    
    @router.get("/asyncapi.yaml", include_in_schema=False)
    async def asyncapi_spec():
        """Get AsyncAPI specification in YAML format"""
        try:
            spec = await _generate_asyncapi_spec(core)
            
            # Convert to YAML
            import yaml
            yaml_content = yaml.dump(spec, default_flow_style=False, sort_keys=False)
            
            return Response(
                content=yaml_content,
                media_type="application/x-yaml",
                headers={"Content-Disposition": "inline; filename=asyncapi.yaml"}
            )
        except Exception as e:
            logger.error(f"Error generating AsyncAPI spec: {e}")
            raise HTTPException(500, f"Failed to generate AsyncAPI specification: {e}")
    
    @router.get("/asyncapi.json", include_in_schema=False)
    async def asyncapi_spec_json():
        """Get AsyncAPI specification in JSON format"""
        try:
            spec = await _generate_asyncapi_spec(core)
            return spec
        except Exception as e:
            logger.error(f"Error generating AsyncAPI spec: {e}")
            raise HTTPException(500, f"Failed to generate AsyncAPI specification: {e}")
    
    @router.get("/debug/asyncapi", include_in_schema=False)
    async def debug_asyncapi():
        """Debug AsyncAPI generation process"""
        debug_info = {}
        
        try:
            # Check component manager first
            if core and hasattr(core, 'component_manager'):
                debug_info["component_manager_available"] = True
                available_components = core.component_manager.get_components()
                debug_info["total_components"] = len(available_components)
                debug_info["component_names"] = list(available_components.keys())
            else:
                debug_info["component_manager_available"] = False
            
            # Check plugin manager
            if core and hasattr(core, 'plugin_manager'):
                debug_info["plugin_manager_available"] = True
                debug_info["total_plugins"] = len(core.plugin_manager._plugins)
                
                # Find WebAPIPlugin components
                from ..core.interfaces.webapi import WebAPIPlugin
                web_components = []
                
                for name, plugin in core.plugin_manager._plugins.items():
                    plugin_info = {
                        "name": name,
                        "type": type(plugin).__name__,
                        "is_webapi_plugin": isinstance(plugin, WebAPIPlugin),
                        "has_get_websocket_spec": hasattr(plugin, 'get_websocket_spec'),
                        "has_get_router": hasattr(plugin, 'get_router')
                    }
                    
                    if isinstance(plugin, WebAPIPlugin):
                        web_components.append((name, plugin))
                        try:
                            router = plugin.get_router()
                            plugin_info["router_available"] = router is not None
                            if router:
                                plugin_info["router_routes_count"] = len(router.routes)
                                plugin_info["websocket_routes"] = []
                                
                                for route in router.routes:
                                    if hasattr(route, 'endpoint') and hasattr(route.endpoint, '_websocket_meta'):
                                        plugin_info["websocket_routes"].append({
                                            "path": route.path,
                                            "endpoint": route.endpoint.__name__,
                                            "has_meta": True
                                        })
                                
                                # Test get_websocket_spec method
                                if hasattr(plugin, 'get_websocket_spec'):
                                    spec = plugin.get_websocket_spec()
                                    plugin_info["websocket_spec"] = spec
                                
                        except Exception as e:
                            plugin_info["error"] = str(e)
                    
                    debug_info[f"plugin_{name}"] = plugin_info
                
                debug_info["webapi_components_count"] = len(web_components)
            else:
                debug_info["plugin_manager_available"] = False
            
            return debug_info
            
        except Exception as e:
            return {"error": str(e), "traceback": str(e)}
    
    return router
