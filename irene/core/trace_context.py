"""
Trace Context System for Pipeline Execution Tracing

This module provides the TraceContext class for collecting detailed pipeline
execution traces with conditional collection to ensure zero overhead when
tracing is disabled.

Features:
- Binary audio data handling with base64 conversion
- Sensitive data sanitization
- Context snapshot recording
- Performance timing collection
"""

import base64
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..intents.models import UnifiedConversationContext

logger = logging.getLogger(__name__)


class TraceContext:
    """
    Context object for collecting detailed pipeline execution traces
    
    This class provides conditional trace collection with zero overhead
    when tracing is disabled, and comprehensive data collection when enabled.
    
    Features:
    - Stage-by-stage execution recording
    - Binary audio data conversion to base64
    - Conversation context snapshots
    - Performance timing collection
    - Sensitive data sanitization
    """
    
    def __init__(self, enabled: bool = False, request_id: Optional[str] = None, 
                 max_stages: int = 100, max_data_size_mb: int = 10):
        """
        Initialize trace context with production safety limits
        
        Args:
            enabled: Whether trace collection is enabled
            request_id: Unique identifier for this trace request
            max_stages: Maximum number of stages to record (prevents memory issues)
            max_data_size_mb: Maximum total data size in MB (prevents memory exhaustion)
        """
        self.enabled = enabled
        self.request_id = request_id or str(uuid.uuid4())
        self.stages: List[Dict[str, Any]] = []
        self.start_time = time.time()
        self.context_snapshots: Dict[str, Any] = {"before": None, "after": None}
        
        # Phase 8: Production safety limits
        self.max_stages = max_stages
        self.max_data_size_bytes = max_data_size_mb * 1024 * 1024
        self._current_data_size = 0
        self._stages_dropped = 0
        self._data_size_exceeded = False
    
    def record_stage(self, stage_name: str, input_data: Any, output_data: Any, 
                    metadata: Dict[str, Any], processing_time_ms: float) -> None:
        """
        Record detailed stage execution information with production safety checks
        
        Args:
            stage_name: Name of the pipeline stage
            input_data: Input data for the stage
            output_data: Output data from the stage
            metadata: Additional metadata about stage execution
            processing_time_ms: Processing time in milliseconds
        """
        # Phase 8: Fast path - zero overhead when disabled
        if not self.enabled:
            return
        
        # Phase 8: Production safety - check stage limits
        if len(self.stages) >= self.max_stages:
            self._stages_dropped += 1
            if self._stages_dropped == 1:  # Only log once
                logger.warning(f"Trace stage limit ({self.max_stages}) exceeded, dropping subsequent stages")
            return
        
        # Phase 8: Production safety - check data size limits
        if self._data_size_exceeded:
            return
            
        # Sanitize data before size check (only when enabled)
        sanitized_input = self._sanitize_for_trace(input_data)
        sanitized_output = self._sanitize_for_trace(output_data)
        
        # Estimate stage data size
        stage_data = {
            "stage": stage_name,
            "input": sanitized_input,
            "output": sanitized_output,
            "metadata": metadata,
            "processing_time_ms": processing_time_ms,
            "timestamp": time.time()
        }
        
        # Phase 8: Production safety - rough data size estimation
        stage_size = self._estimate_data_size(stage_data)
        if self._current_data_size + stage_size > self.max_data_size_bytes:
            self._data_size_exceeded = True
            logger.warning(f"Trace data size limit ({self.max_data_size_bytes / 1024 / 1024:.1f}MB) exceeded, stopping trace collection")
            return
        
        self._current_data_size += stage_size
        self.stages.append(stage_data)
    
    def record_context_snapshot(self, when: str, context: UnifiedConversationContext) -> None:
        """
        Record conversation context state snapshots with production error handling
        
        Args:
            when: When the snapshot was taken ("before" or "after")
            context: UnifiedConversationContext to snapshot
        """
        # Phase 8: Ultra-fast path - immediate return when disabled
        if not self.enabled:
            return
        
        try:
            # Phase 8: Production reliability - safe context snapshot
            snapshot = {}
            
            # Safely extract active actions
            try:
                snapshot["active_actions"] = context.active_actions.copy() if context.active_actions else {}
            except Exception as e:
                snapshot["active_actions"] = {"error": f"Failed to copy active_actions: {str(e)}"}
            
            # Safely extract conversation history info
            try:
                history_length = len(context.conversation_history) if hasattr(context, 'conversation_history') and context.conversation_history else 0
                snapshot["conversation_history_length"] = history_length
                snapshot["recent_intents"] = context.conversation_history[-3:] if history_length > 0 else []
            except Exception as e:
                snapshot["conversation_history_length"] = 0
                snapshot["recent_intents"] = []
                snapshot["history_error"] = str(e)
            
            # Safely extract session information
            try:
                snapshot["session_id"] = getattr(context, 'session_id', 'unknown')
                snapshot["user_id"] = getattr(context, 'user_id', None)
            except Exception as e:
                snapshot["session_id"] = "unknown"
                snapshot["user_id"] = None
                snapshot["session_error"] = str(e)
            
            # NEW: Room context from session unification
            try:
                snapshot["client_id"] = getattr(context, 'client_id', None)
                snapshot["room_name"] = getattr(context, 'room_name', None)
            except Exception as e:
                snapshot["client_id"] = None
                snapshot["room_name"] = None
                snapshot["room_context_error"] = str(e)
            
            # NEW: Handler contexts (replaces ConversationSession)
            try:
                handler_contexts = getattr(context, 'handler_contexts', {})
                snapshot["handler_contexts"] = {
                    handler: {
                        "message_count": len(ctx.get("messages", [])),
                        "conversation_type": ctx.get("conversation_type", "unknown"),
                        "created_at": ctx.get("created_at", 0)
                    }
                    for handler, ctx in handler_contexts.items()
                } if handler_contexts else {}
            except Exception as e:
                snapshot["handler_contexts"] = {"error": f"Failed to extract handler contexts: {str(e)}"}
            
            # NEW: Enhanced fire-and-forget tracking
            try:
                snapshot["recent_actions_count"] = len(getattr(context, 'recent_actions', []))
                snapshot["failed_actions_count"] = len(getattr(context, 'failed_actions', []))
                snapshot["action_error_count"] = getattr(context, 'action_error_count', {}).copy()
            except Exception as e:
                snapshot["recent_actions_count"] = 0
                snapshot["failed_actions_count"] = 0
                snapshot["action_error_count"] = {}
                snapshot["action_tracking_error"] = str(e)
            
            # NEW: Room-scoped device context
            try:
                available_devices = getattr(context, 'available_devices', [])
                snapshot["available_devices_count"] = len(available_devices)
                snapshot["device_types"] = list(set(
                    device.get("type", "unknown") for device in available_devices
                )) if available_devices else []
                snapshot["language"] = getattr(context, 'language', 'unknown')
            except Exception as e:
                snapshot["available_devices_count"] = 0
                snapshot["device_types"] = []
                snapshot["language"] = "unknown"
                snapshot["device_context_error"] = str(e)
            
            # NEW: Memory usage from unification
            try:
                if hasattr(context, 'get_memory_usage_estimate'):
                    memory_usage = context.get_memory_usage_estimate()
                    snapshot["memory_usage"] = {
                        "total_mb": memory_usage.get("total_mb", 0.0),
                        "total_bytes": memory_usage.get("total_bytes", 0),
                        "breakdown_summary": {
                            key: data.get("bytes", 0) if isinstance(data, dict) else 0
                            for key, data in memory_usage.get("breakdown", {}).items()
                        }
                    }
                else:
                    snapshot["memory_usage"] = {"total_mb": 0.0, "total_bytes": 0, "breakdown_summary": {}}
            except Exception as e:
                snapshot["memory_usage"] = {
                    "total_mb": 0.0, 
                    "total_bytes": 0, 
                    "error": f"Memory estimation failed: {str(e)}"
                }
            
            # NEW: Timestamps for change analysis
            try:
                snapshot["created_at"] = getattr(context, 'created_at', 0)
                snapshot["last_activity"] = getattr(context, 'last_activity', 0)
                snapshot["snapshot_timestamp"] = time.time()
            except Exception as e:
                snapshot["created_at"] = 0
                snapshot["last_activity"] = 0
                snapshot["snapshot_timestamp"] = time.time()
                snapshot["timestamp_error"] = str(e)
            
            self.context_snapshots[when] = snapshot
            
        except Exception as e:
            # Phase 8: Production reliability - never fail trace recording
            logger.warning(f"Failed to record context snapshot for '{when}': {e}")
            self.context_snapshots[when] = {
                "error": f"Snapshot recording failed: {str(e)}",
                "timestamp": time.time()
            }
    
    def _sanitize_for_trace(self, data: Any) -> Any:
        """
        Sanitize sensitive data and handle binary audio data in trace output with production error handling
        
        This method handles:
        - Sensitive data removal (passwords, tokens, API keys)
        - Binary audio data conversion to base64
        - AudioData objects with metadata preservation
        - File path handling for audio files
        - Large string truncation
        - Production-safe error handling
        
        Args:
            data: Data to sanitize for trace output
            
        Returns:
            Sanitized data safe for trace storage
        """
        try:
            return self._do_sanitize(data)
        except Exception as e:
            # Phase 8: Production reliability - never fail sanitization
            logger.warning(f"Data sanitization failed: {e}")
            return {
                "type": "sanitization_error",
                "error": str(e),
                "data_type": type(data).__name__,
                "fallback_repr": str(data)[:100] + "..." if len(str(data)) > 100 else str(data)
            }
    
    def _do_sanitize(self, data: Any) -> Any:
        """
        Internal sanitization implementation (separated for error handling)
        """
        if isinstance(data, dict):
            # Phase 8: Enhanced security - remove sensitive keys and recursively sanitize
            sensitive_keys = {
                'password', 'token', 'api_key', 'secret', 'auth', 'credential', 
                'authorization', 'bearer', 'key', 'private', 'cert', 'certificate',
                'session', 'cookie', 'jwt', 'oauth', 'access_token', 'refresh_token'
            }
            
            sanitized = {}
            for k, v in data.items():
                key_lower = k.lower()
                # Skip sensitive keys or keys containing sensitive patterns
                if not any(sensitive in key_lower for sensitive in sensitive_keys):
                    sanitized[k] = self._do_sanitize(v)
                else:
                    sanitized[k] = "[REDACTED]"
            return sanitized
            
        elif isinstance(data, list):
            # Recursively sanitize list items
            return [self._do_sanitize(item) for item in data]
            
        elif isinstance(data, str):
            # Phase 8: Enhanced truncation with size information
            max_length = 2000  # Increased for better debugging but still safe
            if len(data) > max_length:
                return {
                    "type": "truncated_string",
                    "original_length": len(data),
                    "truncated_content": data[:max_length],
                    "note": f"String truncated from {len(data)} to {max_length} characters"
                }
            return data
            
        elif isinstance(data, bytes):
            # Phase 8: Enhanced binary handling with size limits
            max_binary_size = 1024 * 1024  # 1MB limit for binary data in traces
            if len(data) > max_binary_size:
                return {
                    "type": "large_binary_data",
                    "size_bytes": len(data),
                    "note": f"Binary data too large ({len(data)} bytes) for trace inclusion",
                    "sample_data": base64.b64encode(data[:1024]).decode('utf-8') + "...[truncated]"
                }
            return {
                "type": "binary_audio_data",
                "size_bytes": len(data),
                "base64_data": base64.b64encode(data).decode('utf-8')
            }
            
        elif hasattr(data, 'data') and isinstance(data.data, bytes):
            # Phase 8: Enhanced AudioData handling with size limits
            max_audio_size = 1024 * 1024  # 1MB limit for audio data in traces
            audio_size = len(data.data)
            
            result = {
                "type": "audio_data_object",
                "size_bytes": audio_size,
                "sample_rate": getattr(data, 'sample_rate', None),
                "channels": getattr(data, 'channels', None),
                "format": getattr(data, 'format', None),
                "duration_ms": getattr(data, 'duration_ms', None)
            }
            
            if audio_size > max_audio_size:
                result.update({
                    "note": f"Audio data too large ({audio_size} bytes) for trace inclusion",
                    "sample_data": base64.b64encode(data.data[:1024]).decode('utf-8') + "...[truncated]"
                })
            else:
                result["base64_data"] = base64.b64encode(data.data).decode('utf-8')
            
            return result
            
        elif isinstance(data, Path):
            # Phase 8: Enhanced file path handling with size limits
            try:
                if data.exists() and data.suffix.lower() in ['.wav', '.mp3', '.ogg', '.flac', '.aac', '.m4a']:
                    file_size = data.stat().st_size
                    max_file_size = 1024 * 1024  # 1MB limit for files in traces
                    
                    result = {
                        "type": "audio_file_path",
                        "file_path": str(data),
                        "size_bytes": file_size,
                        "file_extension": data.suffix.lower()
                    }
                    
                    if file_size > max_file_size:
                        result.update({
                            "note": f"Audio file too large ({file_size} bytes) for trace inclusion",
                            "sample_data": "[File content not included due to size limit]"
                        })
                    else:
                        with open(data, 'rb') as f:
                            file_content = f.read()
                        result["base64_data"] = base64.b64encode(file_content).decode('utf-8')
                    
                    return result
                else:
                    return {"type": "file_path", "path": str(data), "exists": data.exists()}
            except Exception as e:
                return {"type": "file_path_error", "path": str(data), "error": str(e)}
                
        elif hasattr(data, '__dict__'):
            # Handle objects with attributes by converting to dict
            try:
                return self._do_sanitize(data.__dict__)
            except Exception:
                return {"type": "object", "class": data.__class__.__name__, "repr": str(data)[:500]}
                
        return data
    
    def _estimate_data_size(self, data: Any) -> int:
        """
        Estimate the memory size of data structure for production safety
        
        Args:
            data: Data structure to estimate size for
            
        Returns:
            Estimated size in bytes
        """
        try:
            # Simple estimation based on string representation
            # This is approximate but sufficient for production safety
            import sys
            if hasattr(sys, 'getsizeof'):
                return sys.getsizeof(str(data))
            else:
                # Fallback: rough estimation based on string length
                return len(str(data)) * 2
        except Exception:
            # Safe fallback if size estimation fails
            return 1024  # Assume 1KB for unknown objects
    
    def get_trace_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the trace execution
        
        Returns:
            Dictionary with trace summary information
        """
        if not self.enabled or not self.stages:
            return {"enabled": self.enabled, "stages": 0}
            
        total_time = sum(stage.get("processing_time_ms", 0) for stage in self.stages)
        stage_breakdown = {stage["stage"]: stage.get("processing_time_ms", 0) for stage in self.stages}
        
        return {
            "request_id": self.request_id,
            "total_stages": len(self.stages),
            "total_processing_time_ms": total_time,
            "stage_breakdown": stage_breakdown,
            "context_snapshots_recorded": len([k for k, v in self.context_snapshots.items() if v is not None]),
            "execution_start_time": self.start_time,
            # Phase 8: Production safety information
            "production_safety": {
                "stages_dropped": self._stages_dropped,
                "data_size_exceeded": self._data_size_exceeded,
                "current_data_size_mb": round(self._current_data_size / 1024 / 1024, 2),
                "max_data_size_mb": round(self.max_data_size_bytes / 1024 / 1024, 2),
                "max_stages": self.max_stages
            }
        }
    
    def export_trace(self) -> Dict[str, Any]:
        """
        Export complete trace data for API responses
        
        Returns:
            Complete trace data structure for external consumption
        """
        if not self.enabled:
            return {"enabled": False, "message": "Tracing was disabled for this request"}
            
        return {
            "request_id": self.request_id,
            "pipeline_stages": self.stages,
            "context_evolution": {
                "before": self.context_snapshots.get("before"),
                "after": self.context_snapshots.get("after"),
                "changes": self._calculate_context_changes()
            },
            "performance_metrics": {
                "total_processing_time_ms": sum(
                    stage.get("processing_time_ms", 0) for stage in self.stages
                ),
                "stage_breakdown": {
                    stage["stage"]: stage.get("processing_time_ms", 0) 
                    for stage in self.stages
                },
                "total_stages": len(self.stages),
                "execution_start_time": self.start_time,
                "trace_overhead_estimate_ms": len(self.stages) * 0.1  # Estimated overhead per stage
            }
        }
    
    def _calculate_context_changes(self) -> Dict[str, Any]:
        """
        Enhanced context change analysis for UnifiedConversationContext
        
        Analyzes changes between before/after context snapshots including
        room context, handler contexts, fire-and-forget tracking, and memory usage.
        
        Returns:
            Dictionary describing comprehensive context changes during execution
        """
        before = self.context_snapshots.get("before", {})
        after = self.context_snapshots.get("after", {})
        
        if not before or not after:
            return {"summary": "Incomplete context tracking", "error": "Missing before or after snapshot"}
        
        # Existing active actions analysis
        before_actions = before.get("active_actions", {})
        after_actions = after.get("active_actions", {})
        
        actions_added = []
        actions_removed = []
        
        # Find added actions
        for domain, action_info in after_actions.items():
            if domain not in before_actions:
                actions_added.append({"domain": domain, "action": action_info})
        
        # Find removed actions
        for domain, action_info in before_actions.items():
            if domain not in after_actions:
                actions_removed.append({"domain": domain, "action": action_info})
        
        history_entries_added = after.get("conversation_history_length", 0) - before.get("conversation_history_length", 0)
        
        # NEW: Room context changes
        room_context_changed = (
            before.get("client_id") != after.get("client_id") or
            before.get("room_name") != after.get("room_name")
        )
        
        # NEW: Language changes
        language_changed = before.get("language") != after.get("language")
        
        # NEW: Handler context changes
        before_handlers = set(before.get("handler_contexts", {}).keys())
        after_handlers = set(after.get("handler_contexts", {}).keys())
        handler_contexts_modified = []
        
        for handler in before_handlers.union(after_handlers):
            before_ctx = before.get("handler_contexts", {}).get(handler, {})
            after_ctx = after.get("handler_contexts", {}).get(handler, {})
            
            if before_ctx != after_ctx:
                handler_contexts_modified.append({
                    "handler": handler,
                    "message_count_before": before_ctx.get("message_count", 0),
                    "message_count_after": after_ctx.get("message_count", 0),
                    "messages_added": after_ctx.get("message_count", 0) - before_ctx.get("message_count", 0)
                })
        
        # NEW: Fire-and-forget tracking changes
        recent_actions_added = after.get("recent_actions_count", 0) - before.get("recent_actions_count", 0)
        failed_actions_added = after.get("failed_actions_count", 0) - before.get("failed_actions_count", 0)
        
        # NEW: Device context changes
        devices_changed = before.get("available_devices_count") != after.get("available_devices_count")
        device_types_before = set(before.get("device_types", []))
        device_types_after = set(after.get("device_types", []))
        device_types_added = list(device_types_after - device_types_before)
        device_types_removed = list(device_types_before - device_types_after)
        
        # NEW: Memory usage changes
        before_memory = before.get("memory_usage", {})
        after_memory = after.get("memory_usage", {})
        try:
            memory_usage_delta_mb = after_memory.get("total_mb", 0) - before_memory.get("total_mb", 0)
        except (TypeError, ValueError):
            # Handle cases where memory usage values are not numeric (e.g., MagicMock in tests)
            memory_usage_delta_mb = 0.0
        
        # NEW: Activity tracking
        try:
            activity_time_delta = after.get("last_activity", 0) - before.get("last_activity", 0)
        except (TypeError, ValueError):
            # Handle cases where activity values are not numeric (e.g., MagicMock in tests)
            activity_time_delta = 0.0
        
        # Generate comprehensive summary
        changes_summary = []
        if actions_added:
            changes_summary.append(f"Added {len(actions_added)} active actions")
        if actions_removed:
            changes_summary.append(f"Removed {len(actions_removed)} active actions")
        if history_entries_added > 0:
            changes_summary.append(f"Added {history_entries_added} conversation entries")
        if handler_contexts_modified:
            changes_summary.append(f"Modified {len(handler_contexts_modified)} handler contexts")
        if room_context_changed:
            changes_summary.append("Room context changed")
        if language_changed:
            changes_summary.append("Language changed")
        if devices_changed:
            changes_summary.append("Device context changed")
        try:
            if abs(memory_usage_delta_mb) > 0.1:
                changes_summary.append(f"Memory usage changed by {memory_usage_delta_mb:.2f}MB")
        except (TypeError, ValueError):
            # Handle cases where memory_usage_delta_mb is not numeric
            pass
        
        return {
            # Existing analysis
            "active_actions_added": actions_added,
            "active_actions_removed": actions_removed,
            "conversation_history_entries_added": history_entries_added,
            "total_active_actions_before": len(before_actions),
            "total_active_actions_after": len(after_actions),
            
            # NEW: Room context changes
            "room_context_changed": room_context_changed,
            "room_id_before": before.get("client_id"),
            "room_id_after": after.get("client_id"),
            "room_name_before": before.get("room_name"),
            "room_name_after": after.get("room_name"),
            
            # NEW: Language changes
            "language_changed": language_changed,
            "language_before": before.get("language"),
            "language_after": after.get("language"),
            
            # NEW: Handler context changes
            "handler_contexts_modified": handler_contexts_modified,
            "handler_contexts_count_before": len(before_handlers),
            "handler_contexts_count_after": len(after_handlers),
            
            # NEW: Fire-and-forget changes
            "recent_actions_added": recent_actions_added,
            "failed_actions_added": failed_actions_added,
            "action_error_count_before": len(before.get("action_error_count", {})),
            "action_error_count_after": len(after.get("action_error_count", {})),
            
            # NEW: Device context changes
            "devices_changed": devices_changed,
            "device_count_before": before.get("available_devices_count", 0),
            "device_count_after": after.get("available_devices_count", 0),
            "device_types_added": device_types_added,
            "device_types_removed": device_types_removed,
            
            # NEW: Memory usage changes
            "memory_usage_delta_mb": round(memory_usage_delta_mb, 3),
            "memory_usage_before_mb": before_memory.get("total_mb", 0),
            "memory_usage_after_mb": after_memory.get("total_mb", 0),
            
            # NEW: Activity tracking
            "activity_time_delta_seconds": round(activity_time_delta, 3) if isinstance(activity_time_delta, (int, float)) else 0.0,
            "execution_duration_seconds": round(
                (after.get("snapshot_timestamp", 0) - before.get("snapshot_timestamp", 0)), 3
            ) if all(isinstance(x, (int, float)) for x in [after.get("snapshot_timestamp", 0), before.get("snapshot_timestamp", 0)]) else 0.0,
            
            # Enhanced summary
            "summary": "; ".join(changes_summary) if changes_summary else "No significant changes detected"
        }
