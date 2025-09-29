"""Core data models for the intent system."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Set

from rapidfuzz import fuzz, process


class ConversationState(Enum):
    """Represents the current state of a conversation session"""
    IDLE = "idle"                    # No active conversation
    CONVERSING = "conversing"        # Active LLM conversation  
    CLARIFYING = "clarifying"        # Resolving ambiguous intent
    CONTEXTUAL = "contextual"        # Processing contextual command (already working)


class ContextLayer(Enum):
    """Represents different layers of context resolution (Phase 3)"""
    SESSION = "session"      # Room, user preferences, device capabilities
    THREAD = "thread"        # Domain-specific conversations  
    ACTION = "action"        # Active fire-and-forget actions
    INTENT = "intent"        # Current intent and entities


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


# OLD ConversationContext class removed - replaced by UnifiedConversationContext


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
    
    # Conversation state management (Phase 2)
    conversation_state: ConversationState = ConversationState.IDLE
    state_context: Dict[str, Any] = field(default_factory=dict)  # State-specific context
    state_changed_at: float = field(default_factory=time.time)
    
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
            if handler_name == "conversation":
                # Initialize conversation handler with threading support (Phase 3)
                self.handler_contexts[handler_name] = {
                    "messages": [],
                    "conversation_type": "chat", 
                    "model_preference": "",
                    "created_at": time.time(),
                    "threads": {}  # Domain-specific conversation threads
                }
            else:
                # Standard handler context for non-conversation handlers
                self.handler_contexts[handler_name] = {
                    "messages": [],
                    "conversation_type": "chat", 
                    "model_preference": "",
                    "created_at": time.time()
                }
            
            # NEW: Restore conversation history for conversation handler
            if handler_name == "conversation" and self.conversation_history:
                self._restore_conversation_history_to_handler_context(handler_name)
        
        return self.handler_contexts[handler_name]
    
    def clear_handler_context(self, handler_name: str, keep_system: bool = True):
        """Clear handler-specific context (e.g., LLM history)"""
        context = self.get_handler_context(handler_name)
        if keep_system and context.get("messages") and context["messages"][0].get("role") == "system":
            system_msg = context["messages"][0]
            context["messages"] = [system_msg]
        else:
            context["messages"] = []
    
    def _restore_conversation_history_to_handler_context(self, handler_name: str):
        """Convert general conversation_history to LLM message format"""
        messages = []
        
        # Convert recent conversation history to LLM format
        recent_history = self.conversation_history[-10:]  # Last 10 interactions
        
        for interaction in recent_history:
            if interaction.get("user_text"):
                messages.append({
                    "role": "user", 
                    "content": interaction["user_text"]
                })
            if interaction.get("response"):
                messages.append({
                    "role": "assistant", 
                    "content": interaction["response"]
                })
        
        self.handler_contexts[handler_name]["messages"] = messages
    
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
    
    # Conversation state management methods (Phase 2)
    def transition_state(self, new_state: ConversationState, context: Optional[Dict[str, Any]] = None) -> bool:
        """Transition to a new conversation state with optional context"""
        old_state = self.conversation_state
        
        # Validate state transition
        if not self._is_valid_transition(old_state, new_state):
            return False
        
        # Update state
        self.conversation_state = new_state
        self.state_changed_at = time.time()
        self.last_activity = time.time()
        
        # Update state context
        if context:
            self.state_context.update(context)
        else:
            # Clear context for new state if no context provided
            self.state_context.clear()
        
        return True
    
    def _is_valid_transition(self, from_state: ConversationState, to_state: ConversationState) -> bool:
        """Check if a state transition is valid"""
        # Define valid state transitions
        valid_transitions = {
            ConversationState.IDLE: [ConversationState.CONVERSING, ConversationState.CLARIFYING, ConversationState.CONTEXTUAL],
            ConversationState.CONVERSING: [ConversationState.IDLE, ConversationState.CLARIFYING, ConversationState.CONTEXTUAL],
            ConversationState.CLARIFYING: [ConversationState.CONVERSING, ConversationState.IDLE],
            ConversationState.CONTEXTUAL: [ConversationState.IDLE, ConversationState.CONVERSING]
        }
        
        return to_state in valid_transitions.get(from_state, [])
    
    def get_conversation_state(self) -> ConversationState:
        """Get current conversation state"""
        return self.conversation_state
    
    def get_state_context(self) -> Dict[str, Any]:
        """Get current state context"""
        return self.state_context.copy()
    
    def get_state_duration(self) -> float:
        """Get duration in current state (seconds)"""
        return time.time() - self.state_changed_at
    
    def is_state(self, state: ConversationState) -> bool:
        """Check if currently in specific state"""
        return self.conversation_state == state
    
    def update_state_context(self, key: str, value: Any) -> None:
        """Update a specific key in state context"""
        self.state_context[key] = value
        self.last_activity = time.time()
    
    def clear_state_context(self) -> None:
        """Clear all state context data"""
        self.state_context.clear()
        self.last_activity = time.time()
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of current conversation state"""
        return {
            "current_state": self.conversation_state.value,
            "state_duration": self.get_state_duration(),
            "state_context": self.state_context.copy(),
            "last_state_change": self.state_changed_at
        }
    
    # Conversation threading methods (Phase 3)
    def get_conversation_thread(self, domain: str) -> Dict[str, Any]:
        """Get or create a domain-specific conversation thread"""
        handler_context = self.get_handler_context("conversation")
        
        if domain not in handler_context["threads"]:
            handler_context["threads"][domain] = {
                "messages": [],
                "last_activity": time.time(),
                "active_context": {},
                "created_at": time.time()
            }
        
        return handler_context["threads"][domain]
    
    def add_to_thread(self, domain: str, role: str, content: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Add a message to a domain-specific conversation thread"""
        thread = self.get_conversation_thread(domain)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time()
        }
        
        if context:
            message["context"] = context
        
        thread["messages"].append(message)
        thread["last_activity"] = time.time()
        self.last_activity = time.time()
    
    def get_thread_messages(self, domain: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get messages from a domain-specific thread"""
        thread = self.get_conversation_thread(domain)
        messages = thread["messages"]
        
        if limit:
            return messages[-limit:]
        return messages
    
    def update_thread_context(self, domain: str, context: Dict[str, Any]) -> None:
        """Update the active context for a domain thread"""
        thread = self.get_conversation_thread(domain)
        thread["active_context"].update(context)
        thread["last_activity"] = time.time()
        self.last_activity = time.time()
    
    def get_thread_context(self, domain: str) -> Dict[str, Any]:
        """Get the active context for a domain thread"""
        thread = self.get_conversation_thread(domain)
        return thread["active_context"].copy()
    
    def clear_thread(self, domain: str, keep_context: bool = True) -> None:
        """Clear a domain-specific conversation thread"""
        thread = self.get_conversation_thread(domain)
        thread["messages"] = []
        thread["last_activity"] = time.time()
        
        if not keep_context:
            thread["active_context"] = {}
    
    def get_active_threads(self, since_seconds: int = 300) -> List[str]:
        """Get list of domain threads that have been active recently"""
        handler_context = self.get_handler_context("conversation")
        current_time = time.time()
        
        active_domains = []
        for domain, thread in handler_context["threads"].items():
            if current_time - thread["last_activity"] < since_seconds:
                active_domains.append(domain)
        
        return active_domains
    
    def get_thread_summary(self, domain: str) -> Dict[str, Any]:
        """Get summary information about a domain thread"""
        thread = self.get_conversation_thread(domain)
        
        return {
            "domain": domain,
            "message_count": len(thread["messages"]),
            "last_activity": thread["last_activity"],
            "created_at": thread.get("created_at", 0),
            "active_context_keys": list(thread["active_context"].keys()),
            "age_seconds": time.time() - thread.get("created_at", time.time())
        }
    
    def get_all_threads_summary(self) -> Dict[str, Any]:
        """Get summary of all conversation threads"""
        handler_context = self.get_handler_context("conversation")
        
        summaries = {}
        for domain in handler_context["threads"]:
            summaries[domain] = self.get_thread_summary(domain)
        
        return {
            "total_threads": len(handler_context["threads"]),
            "active_threads": len(self.get_active_threads()),
            "threads": summaries
        }
    
    # Progressive context resolution methods (Phase 3)
    def resolve_context(self, layer: ContextLayer, domain: Optional[str] = None) -> Dict[str, Any]:
        """Resolve context at specified layer with optional domain filtering"""
        if layer == ContextLayer.SESSION:
            return self._resolve_session_context()
        elif layer == ContextLayer.THREAD and domain:
            return self._resolve_thread_context(domain)
        elif layer == ContextLayer.ACTION:
            return self._resolve_action_context(domain)
        elif layer == ContextLayer.INTENT:
            return self._resolve_intent_context()
        else:
            return {}
    
    def _resolve_session_context(self) -> Dict[str, Any]:
        """Resolve session-level context (room, user preferences, device capabilities)"""
        return {
            "session_id": self.session_id,
            "client_id": self.client_id,
            "room_name": self.room_name,
            "language": self.language,
            "available_devices": self.available_devices,
            "client_metadata": self.client_metadata,
            "conversation_state": self.conversation_state.value,
            "created_at": self.created_at,
            "last_activity": self.last_activity
        }
    
    def _resolve_thread_context(self, domain: str) -> Dict[str, Any]:
        """Resolve thread-level context for specific domain"""
        if not domain:
            return {}
        
        thread = self.get_conversation_thread(domain)
        thread_summary = self.get_thread_summary(domain)
        
        return {
            "domain": domain,
            "messages": thread["messages"][-5:],  # Last 5 messages
            "active_context": thread["active_context"],
            "last_activity": thread["last_activity"],
            "message_count": thread_summary["message_count"],
            "age_seconds": thread_summary["age_seconds"]
        }
    
    def _resolve_action_context(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """Resolve action-level context (active fire-and-forget actions)"""
        if domain and domain in self.active_actions:
            # Return specific domain action
            return {
                "domain": domain,
                "action": self.active_actions[domain],
                "recent_actions": [a for a in self.recent_actions if a.get("domain") == domain][-3:],
                "failed_actions": [a for a in self.failed_actions if a.get("domain") == domain][-2:]
            }
        else:
            # Return all actions
            return {
                "active_actions": self.active_actions,
                "recent_actions": self.recent_actions[-5:],  # Last 5 actions
                "failed_actions": self.failed_actions[-3:],  # Last 3 failures
                "action_error_count": self.action_error_count
            }
    
    def _resolve_intent_context(self) -> Dict[str, Any]:
        """Resolve intent-level context (current intent and entities)"""
        # This would typically be called with current intent passed in
        # For now, return recent conversation context
        return {
            "conversation_history": self.conversation_history[-3:],  # Last 3 interactions
            "current_intent_context": self.current_intent_context,
            "last_intent_timestamp": self.last_intent_timestamp,
            "state_context": self.state_context
        }
    
    def resolve_layered_context(self, layers: List[ContextLayer], domain: Optional[str] = None) -> Dict[str, Any]:
        """Resolve context across multiple layers with priority"""
        layered_context = {}
        
        # Resolve contexts in priority order
        for layer in layers:
            layer_context = self.resolve_context(layer, domain)
            if layer_context:
                layered_context[layer.value] = layer_context
        
        return layered_context
    
    def get_contextual_summary(self, domain: Optional[str] = None, max_layers: int = 3) -> Dict[str, Any]:
        """Get a comprehensive context summary across layers"""
        # Define default layer priority
        priority_layers = [ContextLayer.INTENT, ContextLayer.ACTION, ContextLayer.THREAD, ContextLayer.SESSION]
        
        # Limit to max layers for performance
        selected_layers = priority_layers[:max_layers]
        
        layered_context = self.resolve_layered_context(selected_layers, domain)
        
        # Add metadata
        return {
            "domain": domain,
            "layers_resolved": len(layered_context),
            "resolution_timestamp": time.time(),
            "context": layered_context
        }
