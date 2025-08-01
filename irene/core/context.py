"""
Context Management - Session and conversation state

Handles user sessions, conversation context, and plugin data
with automatic cleanup and timeout management.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class Context:
    """
    Represents conversation context and session state.
    
    Contains user information, conversation history, plugin data,
    and session variables with automatic cleanup.
    """
    
    # Session identification
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    
    # User preferences and history
    user_preferences: dict[str, Any] = field(default_factory=dict)
    
    # Conversation state
    previous_commands: list[str] = field(default_factory=list)
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    
    # Plugin-specific data storage
    plugin_data: dict[str, Any] = field(default_factory=dict)
    
    # Session variables
    variables: dict[str, Any] = field(default_factory=dict)
    
    def update_access_time(self) -> None:
        """Update last accessed timestamp"""
        self.last_accessed = datetime.now()
        
    def add_command(self, command: str) -> None:
        """Add command to history"""
        self.previous_commands.append(command)
        if len(self.previous_commands) > 50:  # Keep last 50 commands
            self.previous_commands.pop(0)
        self.update_access_time()
        
    def add_conversation_entry(self, entry: dict[str, Any]) -> None:
        """Add entry to conversation history"""
        entry['timestamp'] = datetime.now().isoformat()
        self.conversation_history.append(entry)
        if len(self.conversation_history) > 100:  # Keep last 100 entries
            self.conversation_history.pop(0)
        self.update_access_time()
        
    def get_plugin_data(self, plugin_name: str) -> dict[str, Any]:
        """Get plugin-specific data"""
        return self.plugin_data.get(plugin_name, {})
        
    def set_plugin_data(self, plugin_name: str, data: dict[str, Any]) -> None:
        """Set plugin-specific data"""
        self.plugin_data[plugin_name] = data
        self.update_access_time()
        
    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get session variable"""
        return self.variables.get(name, default)
        
    def set_variable(self, name: str, value: Any) -> None:
        """Set session variable"""
        self.variables[name] = value
        self.update_access_time()
        
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if context has expired"""
        expiry_time = self.last_accessed + timedelta(minutes=timeout_minutes)
        return datetime.now() > expiry_time


class ContextManager:
    """
    Manages conversation contexts and session cleanup.
    
    Features:
    - Context lifecycle management
    - Automatic timeout cleanup
    - Session isolation
    - Memory management
    """
    
    def __init__(self, timeout_minutes: int = 30):
        self._contexts: dict[str, Context] = {}
        self._timeout_minutes = timeout_minutes
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self) -> None:
        """Start the context manager"""
        self._running = True
        # Start periodic cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_contexts())
        
    async def stop(self) -> None:
        """Stop the context manager"""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
                
    def create_context(self, user_id: Optional[str] = None) -> Context:
        """Create a new conversation context"""
        context = Context(user_id=user_id)
        self._contexts[context.session_id] = context
        return context
        
    def get_context(self, session_id: str) -> Optional[Context]:
        """Get existing context by session ID"""
        context = self._contexts.get(session_id)
        if context:
            context.update_access_time()
        return context
        
    def remove_context(self, session_id: str) -> None:
        """Remove a context"""
        if session_id in self._contexts:
            del self._contexts[session_id]
            
    def get_user_contexts(self, user_id: str) -> list[Context]:
        """Get all contexts for a specific user"""
        return [ctx for ctx in self._contexts.values() if ctx.user_id == user_id]
        
    async def _cleanup_expired_contexts(self) -> None:
        """Periodically clean up expired contexts"""
        while self._running:
            try:
                expired_sessions = [
                    session_id for session_id, context in self._contexts.items()
                    if context.is_expired(self._timeout_minutes)
                ]
                
                for session_id in expired_sessions:
                    self.remove_context(session_id)
                    
                if expired_sessions:
                    print(f"Cleaned up {len(expired_sessions)} expired contexts")
                    
                # Run cleanup every 5 minutes
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in context cleanup: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
                
    @property
    def active_contexts_count(self) -> int:
        """Get the number of active contexts"""
        return len(self._contexts) 