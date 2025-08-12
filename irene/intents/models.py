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
    
    # Device and capability context
    available_devices: List[Dict[str, Any]] = field(default_factory=list)
    preferred_output_device: Optional[str] = None
    client_capabilities: Dict[str, bool] = field(default_factory=dict)
    
    # User preferences
    language: str = "ru"
    timezone: Optional[str] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
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