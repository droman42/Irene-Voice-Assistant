"""Core data models for the intent system."""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set

from rapidfuzz import fuzz, process


@dataclass
class Intent:
    """Represents a recognized user intent with extracted entities."""
    
    name: str                          # "weather.get_current"
    entities: Dict[str, Any]           # {"location": "Moscow", "time": "now"}
    confidence: float                  # 0.95
    raw_text: str                      # Original user text
    timestamp: float = field(default_factory=time.time)
    domain: Optional[str] = None       # "weather", "timer", "conversation"
    action: Optional[str] = None       # "get_current", "set", "cancel"
    session_id: str = "default"       # Session identifier
    
    def __post_init__(self):
        """Extract domain and action from intent name if not provided."""
        if self.domain is None or self.action is None:
            parts = self.name.split(".", 1)
            if len(parts) == 2:
                self.domain = self.domain or parts[0]
                self.action = self.action or parts[1]
            else:
                self.domain = self.domain or "general"
                self.action = self.action or parts[0]


@dataclass  
class IntentResult:
    """Result of intent execution with response and metadata."""
    
    text: str                          # Response text
    should_speak: bool = True          # Whether to use TTS
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional data
    actions: List[str] = field(default_factory=list)        # Additional actions to perform (deprecated - kept for compatibility)
    action_metadata: Dict[str, Any] = field(default_factory=dict)  # NEW: Action context updates for fire-and-forget execution
    success: bool = True               # Whether execution was successful
    error: Optional[str] = None        # Error message if failed
    confidence: float = 1.0            # Confidence in the response
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConversationContext:
    """Comprehensive conversation context with client identification and metadata"""
    
    # Core identification
    session_id: str
    user_id: Optional[str] = None
    client_id: Optional[str] = None  # Room/client identifier
    
    # Client metadata for context-aware processing
    client_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Conversation state
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    current_intent_context: Optional[str] = None
    last_intent_timestamp: Optional[float] = None
    
    # NEW: Action tracking for fire-and-forget execution
    active_actions: Dict[str, Any] = field(default_factory=dict)      # Currently running actions by domain/type
    recent_actions: List[Dict[str, Any]] = field(default_factory=list) # Recently completed/failed actions with metadata
    failed_actions: List[Dict[str, Any]] = field(default_factory=list) # Failed actions with detailed error information
    action_error_count: Dict[str, int] = field(default_factory=dict)   # Error count by domain for failure tracking
    
    # Device and capability context
    available_devices: List[Dict[str, Any]] = field(default_factory=list)
    preferred_output_device: Optional[str] = None
    client_capabilities: Dict[str, bool] = field(default_factory=dict)
    
    # User preferences
    language: str = "ru"
    timezone: Optional[str] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    # Phase 3.1: User notification preferences
    notification_preferences: Dict[str, Any] = field(default_factory=lambda: {
        "action_completion": {
            "enabled": True,
            "long_running_threshold": 30.0,  # seconds
            "delivery_methods": ["tts", "log"],  # tts, log, ui, push
            "priority_filter": "important"  # all, important, critical
        },
        "action_failure": {
            "enabled": True,
            "critical_only": True,
            "delivery_methods": ["tts", "log"],
            "retry_notifications": False
        },
        "system_status": {
            "enabled": True,
            "delivery_methods": ["log"],
            "include_metrics": False
        }
    })
    
    # Phase 3.3: Memory management configuration
    memory_management: Dict[str, Any] = field(default_factory=lambda: {
        "retention_policies": {
            "conversation_history": {
                "max_entries": 50,
                "max_age_hours": 24,
                "cleanup_threshold": 60  # cleanup when exceeding max_entries by this amount
            },
            "recent_actions": {
                "max_entries": 20,
                "max_age_hours": 6,
                "cleanup_threshold": 25
            },
            "failed_actions": {
                "max_entries": 50,
                "max_age_hours": 48,  # Keep failures longer for analysis
                "cleanup_threshold": 60
            }
        },
        "auto_cleanup": {
            "enabled": True,
            "interval_minutes": 30,
            "aggressive_cleanup_threshold": 0.8  # Trigger aggressive cleanup at 80% memory usage
        },
        "memory_monitoring": {
            "enabled": True,
            "alert_threshold_mb": 100,
            "critical_threshold_mb": 200
        }
    })
    
    # System context
    timestamp: float = field(default_factory=time.time)
    request_source: str = "unknown"  # "microphone", "web", "api", etc.
    
    # Legacy compatibility fields
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    max_history_turns: int = 10
    
    def __post_init__(self):
        """Initialize conversation history from legacy history field"""
        if self.history and not self.conversation_history:
            self.conversation_history = self.history.copy()
        
        # Sync metadata with client_metadata
        if self.metadata and not self.client_metadata:
            self.client_metadata.update(self.metadata)
    
    def get_room_name(self) -> Optional[str]:
        """Get human-readable room name from client context"""
        if self.client_id:
            return self.client_metadata.get('room_name', self.client_id)
        return None
    
    def get_device_capabilities(self) -> List[Dict[str, Any]]:
        """Get list of devices available in this client context"""
        return self.client_metadata.get('available_devices', self.available_devices)
    
    def set_client_context(self, client_id: str, metadata: Dict[str, Any]):
        """Set client identification and metadata"""
        self.client_id = client_id
        self.client_metadata = metadata
        # Update available devices from metadata
        if 'available_devices' in metadata:
            self.available_devices = metadata['available_devices']
    
    def get_device_by_name(self, device_name: str) -> Optional[Dict[str, Any]]:
        """Find device by name using fuzzy matching"""
        devices = self.get_device_capabilities()
        
        # Exact match first
        for device in devices:
            if device.get('name', '').lower() == device_name.lower():
                return device
        
        # Fuzzy match fallback using rapidfuzz
        device_names = [device.get('name', '') for device in devices]
        best_match = process.extractOne(device_name, device_names, scorer=fuzz.ratio)
        
        if best_match and best_match[1] >= 70:  # 70% similarity threshold
            for device in devices:
                if device.get('name', '') == best_match[0]:
                    return device
        
        return None
    
    def add_to_history(self, user_text: str, response: str, intent: Optional[str] = None):
        """Add interaction to conversation history"""
        self.conversation_history.append({
            "timestamp": time.time(),
            "user_text": user_text,
            "response": response,
            "intent": intent,
            "client_id": self.client_id
        })
        
        # Keep only last 10 interactions to prevent memory bloat
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
        
        self.last_updated = time.time()
    
    def get_recent_intents(self, limit: int = 3) -> List[str]:
        """Get recent intent names for context"""
        recent = []
        for interaction in reversed(self.conversation_history[-limit:]):
            if interaction.get('intent'):
                recent.append(interaction['intent'])
        return recent
    
    def has_capability(self, capability: str) -> bool:
        """Check if client has specific capability"""
        return self.client_capabilities.get(capability, False)
    
    def get_device_types(self) -> Set[str]:
        """Get set of device types available in this context"""
        devices = self.get_device_capabilities()
        return {device.get('type', 'unknown') for device in devices}
    
    # NEW: Action tracking methods for fire-and-forget execution
    def add_active_action(self, domain: str, action_info: Dict[str, Any]):
        """Add an active action to the context"""
        self.active_actions[domain] = {
            **action_info,
            'started_at': time.time(),
            'client_id': self.client_id
        }
        self.last_updated = time.time()
    
    def complete_action(self, domain: str, success: bool = True, error: Optional[str] = None):
        """Move an active action to recent actions as completed"""
        if domain in self.active_actions:
            action_info = self.active_actions.pop(domain)
            action_info.update({
                'completed_at': time.time(),
                'success': success,
                'error': error
            })
            self.recent_actions.append(action_info)
            
            # Keep only last 10 recent actions to prevent memory bloat
            if len(self.recent_actions) > 10:
                self.recent_actions = self.recent_actions[-10:]
            
            self.last_updated = time.time()
    
    def get_active_action_domains(self) -> List[str]:
        """Get list of domains with currently active actions"""
        return list(self.active_actions.keys())
    
    def has_active_action(self, domain: str) -> bool:
        """Check if there's an active action in the specified domain"""
        return domain in self.active_actions
    
    def get_recent_action_domains(self, limit: int = 3) -> List[str]:
        """Get recent action domains for disambiguation"""
        recent_domains = []
        for action in reversed(self.recent_actions[-limit:]):
            domain = action.get('domain')
            if domain and domain not in recent_domains:
                recent_domains.append(domain)
        return recent_domains
    
    def remove_completed_action(self, domain: str, success: bool = True, error: Optional[str] = None):
        """Remove a completed action from active tracking and add to recent actions"""
        if domain in self.active_actions:
            action_info = self.active_actions.pop(domain)
            action_info.update({
                'completed_at': time.time(),
                'status': 'completed' if success else 'failed',
                'success': success,
                'error': error
            })
            
            # Add to recent actions
            self.recent_actions.append(action_info)
            
            # If action failed, also add to failed actions with detailed error tracking
            if not success:
                failed_action = action_info.copy()
                failed_action.update({
                    'failure_type': self._classify_error(error) if error else 'unknown',
                    'retry_count': action_info.get('retry_count', 0),
                    'is_critical': self._is_critical_failure(domain, error)
                })
                self.failed_actions.append(failed_action)
                
                # Update error count for this domain
                self.action_error_count[domain] = self.action_error_count.get(domain, 0) + 1
                
                # Keep only last 20 failed actions to prevent memory bloat
                if len(self.failed_actions) > 20:
                    self.failed_actions = self.failed_actions[-20:]
            
            # Keep only last 10 recent actions to prevent memory bloat
            if len(self.recent_actions) > 10:
                self.recent_actions = self.recent_actions[-10:]
            
            self.last_updated = time.time()
            return True
        return False
    
    def update_action_status(self, domain: str, status: str, error: Optional[str] = None):
        """Update the status of an active action"""
        if domain in self.active_actions:
            self.active_actions[domain]['status'] = status
            if error:
                self.active_actions[domain]['error'] = error
            self.active_actions[domain]['last_updated'] = time.time()
            self.last_updated = time.time()
            return True
        return False
    
    def _classify_error(self, error: str) -> str:
        """Classify error type for better error handling"""
        if not error:
            return 'unknown'
        
        error_lower = error.lower()
        
        if 'timeout' in error_lower or 'timed out' in error_lower:
            return 'timeout'
        elif 'connection' in error_lower or 'network' in error_lower:
            return 'network'
        elif 'permission' in error_lower or 'access' in error_lower:
            return 'permission'
        elif 'not found' in error_lower or '404' in error_lower:
            return 'not_found'
        elif 'unavailable' in error_lower or 'service' in error_lower:
            return 'service_unavailable'
        elif 'cancelled' in error_lower or 'canceled' in error_lower:
            return 'cancelled'
        else:
            return 'runtime'
    
    def _is_critical_failure(self, domain: str, error: Optional[str]) -> bool:
        """Determine if a failure is critical and should be reported to users"""
        if not error:
            return False
        
        error_lower = error.lower()
        
        # Critical failures that should be reported
        critical_indicators = [
            'permission denied',
            'access denied',
            'authentication failed',
            'service unavailable',
            'critical error',
            'fatal error'
        ]
        
        # Check if this domain has had too many failures recently
        error_count = self.action_error_count.get(domain, 0)
        if error_count >= 3:  # 3 or more failures in this domain
            return True
        
        return any(indicator in error_lower for indicator in critical_indicators)
    
    def get_failed_actions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent failed actions for error reporting"""
        return self.failed_actions[-limit:] if self.failed_actions else []
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of action errors for monitoring"""
        return {
            'total_failed_actions': len(self.failed_actions),
            'error_count_by_domain': self.action_error_count.copy(),
            'recent_critical_failures': [
                action for action in self.failed_actions[-10:] 
                if action.get('is_critical', False)
            ]
        }
    
    def has_critical_failures(self) -> bool:
        """Check if there are any recent critical failures"""
        return any(
            action.get('is_critical', False) 
            for action in self.failed_actions[-5:]  # Check last 5 failures
        )
    
    # Phase 3.1: User Notification System Methods
    def should_notify_completion(self, domain: str, duration: float) -> bool:
        """Check if action completion should trigger user notification"""
        prefs = self.notification_preferences.get("action_completion", {})
        if not prefs.get("enabled", True):
            return False
        
        threshold = prefs.get("long_running_threshold", 30.0)
        return duration >= threshold
    
    def should_notify_failure(self, domain: str, error: Optional[str], is_critical: bool) -> bool:
        """Check if action failure should trigger user notification"""
        prefs = self.notification_preferences.get("action_failure", {})
        if not prefs.get("enabled", True):
            return False
        
        if prefs.get("critical_only", True):
            return is_critical
        
        return True
    
    def get_notification_methods(self, notification_type: str) -> List[str]:
        """Get delivery methods for a notification type"""
        prefs = self.notification_preferences.get(notification_type, {})
        return prefs.get("delivery_methods", ["log"])
    
    def update_notification_preferences(self, notification_type: str, preferences: Dict[str, Any]) -> None:
        """Update notification preferences for a specific type"""
        if notification_type not in self.notification_preferences:
            self.notification_preferences[notification_type] = {}
        
        self.notification_preferences[notification_type].update(preferences)
        self.last_updated = time.time()
    
    def get_notification_summary(self) -> Dict[str, Any]:
        """Get summary of notification settings and recent notifications"""
        return {
            "preferences": self.notification_preferences.copy(),
            "recent_notifications": getattr(self, '_recent_notifications', []),
            "notification_count": getattr(self, '_notification_count', 0)
        }
    
    # Phase 3.3: Advanced Memory Management Methods
    def get_memory_usage_estimate(self) -> Dict[str, Any]:
        """Estimate memory usage of conversation context data"""
        import sys
        
        try:
            # Calculate approximate memory usage
            conversation_size = sum(sys.getsizeof(str(item)) for item in self.conversation_history)
            recent_actions_size = sum(sys.getsizeof(str(item)) for item in self.recent_actions)
            failed_actions_size = sum(sys.getsizeof(str(item)) for item in self.failed_actions)
            active_actions_size = sum(sys.getsizeof(str(item)) for item in self.active_actions.values())
            metadata_size = sys.getsizeof(str(self.client_metadata))
            preferences_size = sys.getsizeof(str(self.user_preferences))
            
            total_bytes = (
                conversation_size + recent_actions_size + failed_actions_size +
                active_actions_size + metadata_size + preferences_size
            )
            
            return {
                "total_bytes": total_bytes,
                "total_mb": total_bytes / (1024 * 1024),
                "breakdown": {
                    "conversation_history": {
                        "entries": len(self.conversation_history),
                        "bytes": conversation_size
                    },
                    "recent_actions": {
                        "entries": len(self.recent_actions),
                        "bytes": recent_actions_size
                    },
                    "failed_actions": {
                        "entries": len(self.failed_actions),
                        "bytes": failed_actions_size
                    },
                    "active_actions": {
                        "entries": len(self.active_actions),
                        "bytes": active_actions_size
                    },
                    "metadata": {
                        "bytes": metadata_size + preferences_size
                    }
                }
            }
        except Exception as e:
            return {
                "error": str(e),
                "total_bytes": 0,
                "total_mb": 0.0,
                "breakdown": {}
            }
    
    def should_trigger_cleanup(self) -> Dict[str, bool]:
        """Check if cleanup should be triggered based on retention policies"""
        policies = self.memory_management.get("retention_policies", {})
        current_time = time.time()
        
        cleanup_needed = {
            "conversation_history": False,
            "recent_actions": False,
            "failed_actions": False,
            "memory_pressure": False
        }
        
        # Check conversation history
        conv_policy = policies.get("conversation_history", {})
        max_entries = conv_policy.get("max_entries", 50)
        cleanup_threshold = conv_policy.get("cleanup_threshold", 60)
        if len(self.conversation_history) > max_entries + cleanup_threshold:
            cleanup_needed["conversation_history"] = True
        
        # Check recent actions
        recent_policy = policies.get("recent_actions", {})
        max_entries = recent_policy.get("max_entries", 20)
        cleanup_threshold = recent_policy.get("cleanup_threshold", 25)
        if len(self.recent_actions) > max_entries + cleanup_threshold:
            cleanup_needed["recent_actions"] = True
        
        # Check failed actions
        failed_policy = policies.get("failed_actions", {})
        max_entries = failed_policy.get("max_entries", 50)
        cleanup_threshold = failed_policy.get("cleanup_threshold", 60)
        if len(self.failed_actions) > max_entries + cleanup_threshold:
            cleanup_needed["failed_actions"] = True
        
        # Check memory pressure
        memory_usage = self.get_memory_usage_estimate()
        memory_config = self.memory_management.get("memory_monitoring", {})
        alert_threshold = memory_config.get("alert_threshold_mb", 100)
        if memory_usage.get("total_mb", 0) > alert_threshold:
            cleanup_needed["memory_pressure"] = True
        
        return cleanup_needed
    
    def perform_cleanup(self, aggressive: bool = False) -> Dict[str, int]:
        """Perform memory cleanup based on retention policies"""
        policies = self.memory_management.get("retention_policies", {})
        current_time = time.time()
        
        cleanup_stats = {
            "conversation_history_removed": 0,
            "recent_actions_removed": 0,
            "failed_actions_removed": 0
        }
        
        # Cleanup conversation history
        conv_policy = policies.get("conversation_history", {})
        max_entries = conv_policy.get("max_entries", 50)
        max_age_seconds = conv_policy.get("max_age_hours", 24) * 3600
        
        if aggressive:
            # Aggressive cleanup: keep only half the max entries
            target_size = max_entries // 2
        else:
            target_size = max_entries
        
        # Remove old entries by age
        cutoff_time = current_time - max_age_seconds
        original_count = len(self.conversation_history)
        self.conversation_history = [
            entry for entry in self.conversation_history
            if entry.get("timestamp", current_time) > cutoff_time
        ]
        
        # Remove excess entries by count
        if len(self.conversation_history) > target_size:
            excess = len(self.conversation_history) - target_size
            self.conversation_history = self.conversation_history[excess:]
        
        cleanup_stats["conversation_history_removed"] = original_count - len(self.conversation_history)
        
        # Cleanup recent actions
        recent_policy = policies.get("recent_actions", {})
        max_entries = recent_policy.get("max_entries", 20)
        max_age_seconds = recent_policy.get("max_age_hours", 6) * 3600
        
        if aggressive:
            target_size = max_entries // 2
        else:
            target_size = max_entries
        
        # Remove old entries by age
        cutoff_time = current_time - max_age_seconds
        original_count = len(self.recent_actions)
        self.recent_actions = [
            action for action in self.recent_actions
            if action.get("completed_at", current_time) > cutoff_time
        ]
        
        # Remove excess entries by count (keep most recent)
        if len(self.recent_actions) > target_size:
            self.recent_actions = self.recent_actions[-target_size:]
        
        cleanup_stats["recent_actions_removed"] = original_count - len(self.recent_actions)
        
        # Cleanup failed actions
        failed_policy = policies.get("failed_actions", {})
        max_entries = failed_policy.get("max_entries", 50)
        max_age_seconds = failed_policy.get("max_age_hours", 48) * 3600
        
        if aggressive:
            target_size = max_entries // 2
        else:
            target_size = max_entries
        
        # Remove old entries by age
        cutoff_time = current_time - max_age_seconds
        original_count = len(self.failed_actions)
        self.failed_actions = [
            action for action in self.failed_actions
            if action.get("completed_at", current_time) > cutoff_time
        ]
        
        # Remove excess entries by count (keep most recent)
        if len(self.failed_actions) > target_size:
            self.failed_actions = self.failed_actions[-target_size:]
        
        cleanup_stats["failed_actions_removed"] = original_count - len(self.failed_actions)
        
        # Update last updated timestamp
        self.last_updated = time.time()
        
        return cleanup_stats
    
    def update_memory_management_config(self, config: Dict[str, Any]) -> None:
        """Update memory management configuration"""
        self.memory_management.update(config)
        self.last_updated = time.time()
    
    def get_memory_management_status(self) -> Dict[str, Any]:
        """Get comprehensive memory management status"""
        memory_usage = self.get_memory_usage_estimate()
        cleanup_needed = self.should_trigger_cleanup()
        
        return {
            "memory_usage": memory_usage,
            "cleanup_needed": cleanup_needed,
            "retention_policies": self.memory_management.get("retention_policies", {}),
            "auto_cleanup_enabled": self.memory_management.get("auto_cleanup", {}).get("enabled", True),
            "data_counts": {
                "conversation_history": len(self.conversation_history),
                "recent_actions": len(self.recent_actions),
                "failed_actions": len(self.failed_actions),
                "active_actions": len(self.active_actions)
            },
            "last_updated": self.last_updated
        }
    
    def cancel_action(self, domain: str, reason: str = "User requested cancellation") -> bool:
        """
        Cancel an active action in the specified domain.
        
        Args:
            domain: Domain of the action to cancel
            reason: Reason for cancellation
            
        Returns:
            True if action was found and marked for cancellation, False otherwise
        """
        if domain in self.active_actions:
            self.active_actions[domain].update({
                'status': 'cancelled',
                'cancelled_at': time.time(),
                'cancellation_reason': reason
            })
            self.last_updated = time.time()
            return True
        return False
    
    def get_cancellable_actions(self) -> List[str]:
        """Get list of domains with actions that can be cancelled"""
        return [
            domain for domain, action_info in self.active_actions.items()
            if action_info.get('status') == 'running'
        ]
    
    # Legacy compatibility methods
    def add_user_turn(self, intent: Intent):
        """Add a user turn to conversation history (legacy compatibility)"""
        self.history.append({
            "type": "user",
            "intent": intent.name,
            "text": intent.raw_text,
            "entities": intent.entities,
            "timestamp": intent.timestamp
        })
        
        # Also add to new conversation_history format
        self.add_to_history(intent.raw_text, "", intent.name)
        
        self._trim_history()
        self.last_updated = time.time()
    
    def add_assistant_turn(self, result: IntentResult):
        """Add an assistant turn to conversation history (legacy compatibility)"""
        self.history.append({
            "type": "assistant", 
            "text": result.text,
            "metadata": result.metadata,
            "timestamp": result.timestamp
        })
        
        # Update last conversation entry with response
        if self.conversation_history:
            self.conversation_history[-1]["response"] = result.text
        
        self._trim_history()
        self.last_updated = time.time()
    
    def _trim_history(self):
        """Keep history within max_history_turns limit"""
        if len(self.history) > self.max_history_turns * 2:  # User + assistant pairs
            self.history = self.history[-(self.max_history_turns * 2):]
    
    def get_recent_context(self, turns: int = 3) -> List[Dict[str, Any]]:
        """Get recent conversation turns for context (legacy compatibility)"""
        return self.history[-turns*2:] if self.history else []


@dataclass
class WakeWordResult:
    """Result of wake word detection."""
    
    detected: bool
    confidence: float
    word: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    audio_data: Optional[bytes] = None


@dataclass
class AudioData:
    """Audio data container for processing pipeline."""
    
    data: bytes
    timestamp: float
    sample_rate: int = 16000
    channels: int = 1
    format: str = "pcm16"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedConversationContext:
    """Unified conversation context replacing both ConversationContext and ConversationSession
    
    CRITICAL: Maintains room/client-scoped session boundaries for fire-and-forget action tracking
    and contextual command resolution (TODO16 compatibility).
    
    DESIGN: Single-user, multi-room system where sessions represent physical locations.
    """
    
    # Core identification (room-scoped sessions preserved)
    session_id: str                   # Room-based: "kitchen_session", "living_room_session"
    client_id: Optional[str] = None   # Room ID: "kitchen", "living_room"
    room_name: Optional[str] = None   # Human-readable: "Кухня", "Гостиная"
    
    # System-level context (from old ConversationContext)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    client_metadata: Dict[str, Any] = field(default_factory=dict)
    available_devices: List[Dict[str, Any]] = field(default_factory=list)
    language: str = "ru"
    
    # CRITICAL: Fire-and-forget action tracking (room-scoped)
    active_actions: Dict[str, Any] = field(default_factory=dict)      # Domain -> action info
    recent_actions: List[Dict[str, Any]] = field(default_factory=list) # Completed actions
    failed_actions: List[Dict[str, Any]] = field(default_factory=list) # Failed actions
    action_error_count: Dict[str, int] = field(default_factory=dict)   # Error tracking
    
    # Handler-specific contexts (replaces ConversationSession approach)
    handler_contexts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Unified timestamps
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    # Legacy compatibility fields (from ConversationContext)
    user_id: Optional[str] = None
    current_intent_context: Optional[str] = None
    last_intent_timestamp: Optional[float] = None
    preferred_output_device: Optional[str] = None
    client_capabilities: Dict[str, bool] = field(default_factory=dict)
    timezone: Optional[str] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    notification_preferences: Dict[str, Any] = field(default_factory=lambda: {
        "action_completion": {
            "enabled": True,
            "long_running_threshold": 30.0,  # seconds
            "delivery_methods": ["tts", "log"],  # tts, log, ui, push
            "priority_filter": "important"  # all, important, critical
        },
        "action_failure": {
            "enabled": True,
            "critical_only": True,
            "delivery_methods": ["tts", "log"],
            "retry_notifications": False
        },
        "system_status": {
            "enabled": True,
            "delivery_methods": ["log"],
            "include_metrics": False
        }
    })
    memory_management: Dict[str, Any] = field(default_factory=lambda: {
        "retention_policies": {
            "conversation_history": {
                "max_entries": 50,
                "max_age_hours": 24,
                "cleanup_threshold": 60  # cleanup when exceeding max_entries by this amount
            },
            "recent_actions": {
                "max_entries": 20,
                "max_age_hours": 6,
                "cleanup_threshold": 25
            },
            "failed_actions": {
                "max_entries": 50,
                "max_age_hours": 48,  # Keep failures longer for analysis
                "cleanup_threshold": 60
            }
        },
        "auto_cleanup": {
            "enabled": True,
            "interval_minutes": 30,
            "aggressive_cleanup_threshold": 0.8  # Trigger aggressive cleanup at 80% memory usage
        },
        "memory_monitoring": {
            "enabled": True,
            "alert_threshold_mb": 100,
            "critical_threshold_mb": 200
        }
    })
    timestamp: float = field(default_factory=time.time)
    request_source: str = "unknown"  # "microphone", "web", "api", etc.
    
    # Legacy compatibility fields
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)
    max_history_turns: int = 10
    
    def __post_init__(self):
        """Initialize conversation history from legacy history field"""
        if self.history and not self.conversation_history:
            self.conversation_history = self.history.copy()
        
        # Sync metadata with client_metadata
        if self.metadata and not self.client_metadata:
            self.client_metadata.update(self.metadata)
    
    # Combined methods from both old classes
    def get_room_name(self) -> Optional[str]:
        """Get human-readable room name from client context"""
        if self.room_name:
            return self.room_name
        if self.client_id:
            return self.client_metadata.get('room_name', self.client_id)
        return None
    
    def get_device_capabilities(self) -> List[Dict[str, Any]]:
        """Get list of devices available in this client context"""
        return self.client_metadata.get('available_devices', self.available_devices)
    
    def get_device_by_name(self, device_name: str) -> Optional[Dict[str, Any]]:
        """Find device by name using fuzzy matching"""
        devices = self.get_device_capabilities()
        
        # Exact match first
        for device in devices:
            if device.get('name', '').lower() == device_name.lower():
                return device
        
        # Fuzzy match fallback using rapidfuzz
        device_names = [device.get('name', '') for device in devices]
        best_match = process.extractOne(device_name, device_names, scorer=fuzz.ratio)
        
        if best_match and best_match[1] >= 70:  # 70% similarity threshold
            for device in devices:
                if device.get('name', '') == best_match[0]:
                    return device
        
        return None
    
    # Handler-specific context management
    def get_handler_context(self, handler_name: str) -> Dict[str, Any]:
        """Get handler-specific context (e.g., LLM conversation history)"""
        if handler_name not in self.handler_contexts:
            self.handler_contexts[handler_name] = {
                "messages": [],
                "conversation_type": "chat", 
                "model_preference": "",
                "created_at": time.time()
            }
        return self.handler_contexts[handler_name]
    
    def clear_handler_context(self, handler_name: str, keep_system: bool = True):
        """Clear handler-specific context (e.g., LLM history)"""
        context = self.get_handler_context(handler_name)
        if keep_system and context.get("messages") and context["messages"][0].get("role") == "system":
            system_msg = context["messages"][0]
            context["messages"] = [system_msg]
        else:
            context["messages"] = []
    
    # CRITICAL: Fire-and-forget action management (preserved from ConversationContext)
    def add_active_action(self, domain: str, action_info: Dict[str, Any]):
        """Add active action with automatic room context injection"""
        self.active_actions[domain] = {
            **action_info,
            'room_id': self.client_id,
            'room_name': self.room_name,
            'session_id': self.session_id,
            'started_at': time.time()
        }
        self.last_updated = time.time()
    
    def complete_action(self, domain: str, success: bool = True, error: Optional[str] = None):
        """Move an active action to recent actions as completed"""
        if domain in self.active_actions:
            action_info = self.active_actions.pop(domain)
            action_info.update({
                'completed_at': time.time(),
                'success': success,
                'error': error
            })
            self.recent_actions.append(action_info)
            
            # Keep only last 10 recent actions to prevent memory bloat
            if len(self.recent_actions) > 10:
                self.recent_actions = self.recent_actions[-10:]
            
            self.last_updated = time.time()
    
    def has_active_action(self, domain: str) -> bool:
        """Check if there's an active action in the specified domain"""
        return domain in self.active_actions
    
    def get_active_action_domains(self) -> List[str]:
        """Get list of domains with currently active actions"""
        return list(self.active_actions.keys())
    
    def remove_completed_action(self, domain: str, success: bool = True, error: Optional[str] = None):
        """Remove a completed action from active tracking and add to recent actions"""
        if domain in self.active_actions:
            action_info = self.active_actions.pop(domain)
            action_info.update({
                'completed_at': time.time(),
                'status': 'completed' if success else 'failed',
                'success': success,
                'error': error
            })
            
            # Add to recent actions
            self.recent_actions.append(action_info)
            
            # If action failed, also add to failed actions with detailed error tracking
            if not success:
                failed_action = action_info.copy()
                failed_action.update({
                    'failure_type': self._classify_error(error) if error else 'unknown',
                    'retry_count': action_info.get('retry_count', 0),
                    'is_critical': self._is_critical_failure(domain, error)
                })
                self.failed_actions.append(failed_action)
                
                # Update error count for this domain
                self.action_error_count[domain] = self.action_error_count.get(domain, 0) + 1
                
                # Keep only last 20 failed actions to prevent memory bloat
                if len(self.failed_actions) > 20:
                    self.failed_actions = self.failed_actions[-20:]
            
            # Keep only last 10 recent actions to prevent memory bloat
            if len(self.recent_actions) > 10:
                self.recent_actions = self.recent_actions[-10:]
            
            self.last_updated = time.time()
            return True
        return False
    
    # Additional fire-and-forget management methods
    def cancel_action(self, domain: str, reason: str = "User requested cancellation") -> bool:
        """Cancel an active action and mark it as cancelled"""
        if domain in self.active_actions:
            self.active_actions[domain].update({
                'status': 'cancelled',
                'cancelled_at': time.time(),
                'cancellation_reason': reason
            })
            self.last_updated = time.time()
            return True
        return False
    
    def update_action_status(self, domain: str, status: str, error: Optional[str] = None) -> bool:
        """Update the status of a running action"""
        if domain in self.active_actions:
            self.active_actions[domain]['status'] = status
            if error:
                self.active_actions[domain]['error'] = error
            self.active_actions[domain]['last_updated'] = time.time()
            self.last_updated = time.time()
            return True
        return False
    
    def get_cancellable_actions(self) -> List[str]:
        """Get list of domains with actions that can be cancelled"""
        return [domain for domain, action_info in self.active_actions.items()
                if action_info.get('status') == 'running']
    
    # Legacy compatibility methods from ConversationContext
    def set_client_context(self, client_id: str, metadata: Dict[str, Any]):
        """Set client identification and metadata"""
        self.client_id = client_id
        self.client_metadata = metadata
        # Update available devices from metadata
        if 'available_devices' in metadata:
            self.available_devices = metadata['available_devices']
        # Update room name if provided
        if 'room_name' in metadata:
            self.room_name = metadata['room_name']
        self.last_updated = time.time()
    
    def add_to_history(self, user_text: str, response: str, intent: Optional[str] = None):
        """Add interaction to conversation history"""
        self.conversation_history.append({
            "timestamp": time.time(),
            "user_text": user_text,
            "response": response,
            "intent": intent,
            "client_id": self.client_id
        })
        
        # Keep only last 10 interactions to prevent memory bloat
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
        
        self.last_updated = time.time()
    
    def get_recent_intents(self, limit: int = 3) -> List[str]:
        """Get recent intent names for context"""
        recent = []
        for interaction in reversed(self.conversation_history[-limit:]):
            if interaction.get('intent'):
                recent.append(interaction['intent'])
        return recent
    
    def has_capability(self, capability: str) -> bool:
        """Check if client has specific capability"""
        return self.client_capabilities.get(capability, False)
    
    def get_device_types(self) -> Set[str]:
        """Get set of device types available in this context"""
        devices = self.get_device_capabilities()
        return {device.get('type', 'unknown') for device in devices}
    
    def get_recent_action_domains(self, limit: int = 3) -> List[str]:
        """Get recent action domains for disambiguation"""
        recent_domains = []
        for action in reversed(self.recent_actions[-limit:]):
            domain = action.get('domain')
            if domain and domain not in recent_domains:
                recent_domains.append(domain)
        return recent_domains
    
    def _classify_error(self, error: str) -> str:
        """Classify error type for better error handling"""
        if not error:
            return 'unknown'
        
        error_lower = error.lower()
        
        if 'timeout' in error_lower or 'timed out' in error_lower:
            return 'timeout'
        elif 'connection' in error_lower or 'network' in error_lower:
            return 'network'
        elif 'permission' in error_lower or 'access' in error_lower:
            return 'permission'
        elif 'not found' in error_lower or '404' in error_lower:
            return 'not_found'
        elif 'unavailable' in error_lower or 'service' in error_lower:
            return 'service_unavailable'
        elif 'cancelled' in error_lower or 'canceled' in error_lower:
            return 'cancelled'
        else:
            return 'runtime'
    
    def _is_critical_failure(self, domain: str, error: Optional[str]) -> bool:
        """Determine if a failure is critical and should be reported to users"""
        if not error:
            return False
        
        error_lower = error.lower()
        
        # Critical failures that should be reported
        critical_indicators = [
            'permission denied',
            'access denied',
            'authentication failed',
            'service unavailable',
            'critical error',
            'fatal error'
        ]
        
        # Check if this domain has had too many failures recently
        error_count = self.action_error_count.get(domain, 0)
        if error_count >= 3:  # 3 or more failures in this domain
            return True
        
        return any(indicator in error_lower for indicator in critical_indicators)
    
    # User notification system methods
    def should_notify_completion(self, domain: str, duration: float) -> bool:
        """Check if action completion should trigger user notification"""
        prefs = self.notification_preferences.get("action_completion", {})
        if not prefs.get("enabled", True):
            return False
        
        threshold = prefs.get("long_running_threshold", 30.0)
        return duration >= threshold
    
    def should_notify_failure(self, domain: str, error: Optional[str], is_critical: bool) -> bool:
        """Check if action failure should trigger user notification"""
        prefs = self.notification_preferences.get("action_failure", {})
        if not prefs.get("enabled", True):
            return False
        
        if prefs.get("critical_only", True):
            return is_critical
        
        return True
    
    def get_notification_methods(self, notification_type: str) -> List[str]:
        """Get delivery methods for a notification type"""
        prefs = self.notification_preferences.get(notification_type, {})
        return prefs.get("delivery_methods", ["log"])
    
    def update_notification_preferences(self, notification_type: str, preferences: Dict[str, Any]) -> None:
        """Update notification preferences for a specific type"""
        if notification_type not in self.notification_preferences:
            self.notification_preferences[notification_type] = {}
        
        self.notification_preferences[notification_type].update(preferences)
        self.last_updated = time.time()
    
    def get_notification_summary(self) -> Dict[str, Any]:
        """Get summary of notification settings and recent notifications"""
        return {
            "preferences": self.notification_preferences.copy(),
            "recent_notifications": getattr(self, '_recent_notifications', []),
            "notification_count": getattr(self, '_notification_count', 0)
        }
    
    def get_failed_actions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent failed actions for error reporting"""
        return self.failed_actions[-limit:] if self.failed_actions else []
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of action errors for monitoring"""
        return {
            'total_failed_actions': len(self.failed_actions),
            'error_count_by_domain': self.action_error_count.copy(),
            'recent_critical_failures': [
                action for action in self.failed_actions[-10:] 
                if action.get('is_critical', False)
            ]
        }
    
    def has_critical_failures(self) -> bool:
        """Check if there are any recent critical failures"""
        return any(
            action.get('is_critical', False) 
            for action in self.failed_actions[-5:]  # Check last 5 failures
        )
    
    # Legacy compatibility methods
    def add_user_turn(self, intent: Intent):
        """Add a user turn to conversation history (legacy compatibility)"""
        self.history.append({
            "type": "user",
            "intent": intent.name,
            "text": intent.raw_text,
            "entities": intent.entities,
            "timestamp": intent.timestamp
        })
        
        # Also add to new conversation_history format
        self.add_to_history(intent.raw_text, "", intent.name)
        
        self._trim_history()
        self.last_updated = time.time()
    
    def add_assistant_turn(self, result: IntentResult):
        """Add an assistant turn to conversation history (legacy compatibility)"""
        self.history.append({
            "type": "assistant", 
            "text": result.text,
            "metadata": result.metadata,
            "timestamp": result.timestamp
        })
        
        # Update last conversation entry with response
        if self.conversation_history:
            self.conversation_history[-1]["response"] = result.text
        
        self._trim_history()
        self.last_updated = time.time()
    
    def _trim_history(self):
        """Keep history within max_history_turns limit"""
        if len(self.history) > self.max_history_turns * 2:  # User + assistant pairs
            self.history = self.history[-(self.max_history_turns * 2):]
    
    def get_recent_context(self, turns: int = 3) -> List[Dict[str, Any]]:
        """Get recent conversation turns for context (legacy compatibility)"""
        return self.history[-turns*2:] if self.history else []     
    # Memory management methods (Phase 1.3 MemoryManager compatibility)
    def get_memory_usage_estimate(self) -> Dict[str, Any]:
        """Estimate memory usage of unified context data"""
        import sys
        
        try:
            # Calculate approximate memory usage for all context data
            conversation_size = sum(sys.getsizeof(str(item)) for item in self.conversation_history)
            handler_contexts_size = sum(sys.getsizeof(str(ctx)) for ctx in self.handler_contexts.values())
            active_actions_size = sum(sys.getsizeof(str(action)) for action in self.active_actions.values())
            recent_actions_size = sum(sys.getsizeof(str(action)) for action in self.recent_actions)
            failed_actions_size = sum(sys.getsizeof(str(action)) for action in self.failed_actions)
            metadata_size = sys.getsizeof(str(self.client_metadata))
            devices_size = sum(sys.getsizeof(str(device)) for device in self.available_devices)
            
            total_bytes = (
                conversation_size + handler_contexts_size + active_actions_size +
                recent_actions_size + failed_actions_size + metadata_size + devices_size
            )
            
            return {
                "total_bytes": total_bytes,
                "total_mb": total_bytes / (1024 * 1024),
                "breakdown": {
                    "conversation_history": {
                        "entries": len(self.conversation_history),
                        "bytes": conversation_size
                    },
                    "handler_contexts": {
                        "handlers": len(self.handler_contexts),
                        "bytes": handler_contexts_size
                    },
                    "active_actions": {
                        "entries": len(self.active_actions),
                        "bytes": active_actions_size
                    },
                    "recent_actions": {
                        "entries": len(self.recent_actions),
                        "bytes": recent_actions_size
                    },
                    "failed_actions": {
                        "entries": len(self.failed_actions),
                        "bytes": failed_actions_size
                    },
                    "client_metadata": {
                        "bytes": metadata_size
                    },
                    "available_devices": {
                        "entries": len(self.available_devices),
                        "bytes": devices_size
                    }
                }
            }
        except Exception as e:
            return {
                "total_bytes": 0,
                "total_mb": 0.0,
                "error": str(e),
                "breakdown": {}
            }
