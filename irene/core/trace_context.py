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

from ..intents.models import ConversationContext

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
    
    def record_context_snapshot(self, when: str, context: ConversationContext) -> None:
        """
        Record conversation context state snapshots with production error handling
        
        Args:
            when: When the snapshot was taken ("before" or "after")
            context: ConversationContext to snapshot
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
        Calculate changes between before/after context snapshots
        
        Returns:
            Dictionary describing context changes during execution
        """
        before = self.context_snapshots.get("before", {})
        after = self.context_snapshots.get("after", {})
        
        if not before or not after:
            return {"summary": "Incomplete context tracking"}
        
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
        
        return {
            "active_actions_added": actions_added,
            "active_actions_removed": actions_removed,
            "conversation_history_entries_added": history_entries_added,
            "total_active_actions_before": len(before_actions),
            "total_active_actions_after": len(after_actions),
            "summary": f"Added {len(actions_added)} actions, removed {len(actions_removed)} actions, {history_entries_added} history entries"
        }
