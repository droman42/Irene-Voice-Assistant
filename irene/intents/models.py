"""Core data models for the intent system."""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


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
    actions: List[str] = field(default_factory=list)        # Additional actions to perform
    success: bool = True               # Whether execution was successful
    error: Optional[str] = None        # Error message if failed
    confidence: float = 1.0            # Confidence in the response
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConversationContext:
    """Context for conversation management and history."""
    
    session_id: str
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    max_history_turns: int = 10
    
    def add_user_turn(self, intent: Intent):
        """Add a user turn to conversation history."""
        self.history.append({
            "type": "user",
            "intent": intent.name,
            "text": intent.raw_text,
            "entities": intent.entities,
            "timestamp": intent.timestamp
        })
        self._trim_history()
        self.last_updated = time.time()
    
    def add_assistant_turn(self, result: IntentResult):
        """Add an assistant turn to conversation history."""
        self.history.append({
            "type": "assistant", 
            "text": result.text,
            "metadata": result.metadata,
            "timestamp": result.timestamp
        })
        self._trim_history()
        self.last_updated = time.time()
    
    def _trim_history(self):
        """Keep history within max_history_turns limit."""
        if len(self.history) > self.max_history_turns * 2:  # User + assistant pairs
            self.history = self.history[-(self.max_history_turns * 2):]
    
    def get_recent_context(self, turns: int = 3) -> List[Dict[str, Any]]:
        """Get recent conversation turns for context."""
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