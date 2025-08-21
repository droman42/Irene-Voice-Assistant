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
from typing import Optional, Any, Callable, Awaitable

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
    
    # Context continuation for multi-turn conversations
    continuation_handler: Optional[Callable[[str, 'Context'], Awaitable[Any]]] = None
    continuation_timeout: Optional[int] = None
    continuation_timer: Optional[asyncio.Task] = None
    
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
    
    async def set_continuation(self, handler: Callable[[str, 'Context'], Awaitable[Any]], timeout: int = 20) -> None:
        """
        Set a continuation handler for multi-turn conversations.
        
        Args:
            handler: Async function to handle subsequent commands
            timeout: Timeout in seconds for the continuation
        """
        # Clear any existing continuation
        await self.clear_continuation()
        
        self.continuation_handler = handler
        self.continuation_timeout = timeout
        
        # Set up timeout timer
        if timeout > 0:
            self.continuation_timer = asyncio.create_task(self._continuation_timeout())
        
        self.update_access_time()
        logger.debug(f"Context continuation set with {timeout}s timeout")
    
    async def clear_continuation(self) -> None:
        """Clear the continuation handler and cancel timeout"""
        if self.continuation_timer:
            self.continuation_timer.cancel()
            try:
                await self.continuation_timer
            except asyncio.CancelledError:
                pass
            self.continuation_timer = None
        
        self.continuation_handler = None
        self.continuation_timeout = None
        logger.debug("Context continuation cleared")
    
    async def _continuation_timeout(self) -> None:
        """Handle continuation timeout"""
        try:
            if self.continuation_timeout:
                await asyncio.sleep(self.continuation_timeout)
                logger.debug("Context continuation timed out")
                await self.clear_continuation()
        except asyncio.CancelledError:
            pass
    
    def has_continuation(self) -> bool:
        """Check if context has an active continuation handler"""
        return self.continuation_handler is not None
    
    async def handle_continuation(self, command: str) -> Any:
        """
        Handle a command using the continuation handler.
        
        Args:
            command: The command to handle
            
        Returns:
            Result from the continuation handler
        """
        if not self.continuation_handler:
            raise ValueError("No continuation handler set")
        
        self.update_access_time()
        return await self.continuation_handler(command, self)


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
        
    async def get_or_create_context(self, session_id: str, client_id: Optional[str] = None, 
                                   client_metadata: Optional[dict] = None):
        """Get existing context or create a new one - returns ConversationContext for workflow compatibility"""
        # Import ConversationContext here to avoid circular imports
        from ..intents.models import ConversationContext
        
        # Check if we already have a context (basic Context type)
        basic_context = self.get_context(session_id)
        
        # Always return a ConversationContext for workflow compatibility
        # Convert basic context data if it exists, otherwise create new
        conversation_context = ConversationContext(
            session_id=session_id,
            user_id=client_id,
            client_id=client_id,
            client_metadata=client_metadata or {},
            conversation_history=basic_context.conversation_history if basic_context else []
        )
        
        # Store the basic context for internal management
        if basic_context is None:
            basic_context = Context(user_id=client_id)
            basic_context.session_id = session_id
            if client_metadata:
                basic_context.variables.update(client_metadata)
            self._contexts[session_id] = basic_context
        
        return conversation_context
        
    async def remove_context(self, session_id: str) -> None:
        """Remove a context"""
        if session_id in self._contexts:
            context = self._contexts[session_id]
            # Clear any active continuation before removing
            await context.clear_continuation()
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
                    await self.remove_context(session_id)
                    
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