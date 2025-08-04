"""
Enhanced Conversation Context Management

Manages conversation context and history for sessions with advanced features
for the intent system including session persistence, context-aware processing,
and intelligent context management.
"""

import time
import logging
import asyncio
from typing import Dict, Any, Optional, List
from .models import ConversationContext, Intent, IntentResult

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages conversation context and history for sessions."""
    
    def __init__(self, session_timeout: int = 1800, max_history_turns: int = 10):
        """
        Initialize the context manager.
        
        Args:
            session_timeout: Session timeout in seconds (default: 30 minutes)
            max_history_turns: Maximum conversation turns to keep in history
        """
        self.sessions: Dict[str, ConversationContext] = {}
        self.session_timeout = session_timeout
        self.max_history_turns = max_history_turns
        self.cleanup_interval = 300  # Cleanup every 5 minutes
        self.last_cleanup = time.time()
    
    async def get_context(self, session_id: str) -> ConversationContext:
        """
        Retrieve or create conversation context for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            ConversationContext for the session
        """
        # Clean up expired sessions periodically
        await self._cleanup_expired_sessions()
        
        if session_id in self.sessions:
            context = self.sessions[session_id]
            # Check if session has expired
            if time.time() - context.last_updated > self.session_timeout:
                logger.info(f"Session {session_id} expired, creating new context")
                del self.sessions[session_id]
            else:
                return context
        
        # Create new context
        context = ConversationContext(
            session_id=session_id,
            max_history_turns=self.max_history_turns
        )
        self.sessions[session_id] = context
        logger.info(f"Created new conversation context for session: {session_id}")
        return context
    
    async def update_context(self, session_id: str, metadata: Dict[str, Any]):
        """
        Update context metadata for a session.
        
        Args:
            session_id: Session identifier
            metadata: Metadata to update
        """
        context = await self.get_context(session_id)
        context.metadata.update(metadata)
        context.last_updated = time.time()
        logger.debug(f"Updated context metadata for session {session_id}")
    
    async def add_user_turn(self, session_id: str, intent: Intent):
        """
        Add a user turn to conversation history.
        
        Args:
            session_id: Session identifier
            intent: User intent to add
        """
        context = await self.get_context(session_id)
        context.add_user_turn(intent)
        logger.debug(f"Added user turn to session {session_id}: {intent.name}")
    
    async def add_assistant_turn(self, session_id: str, result: IntentResult):
        """
        Add an assistant turn to conversation history.
        
        Args:
            session_id: Session identifier
            result: Assistant response to add
        """
        context = await self.get_context(session_id)
        context.add_assistant_turn(result)
        logger.debug(f"Added assistant turn to session {session_id}")
    
    async def get_conversation_history(self, session_id: str, turns: int = 5) -> list:
        """
        Get recent conversation history for a session.
        
        Args:
            session_id: Session identifier
            turns: Number of conversation turns to retrieve
            
        Returns:
            List of recent conversation turns
        """
        context = await self.get_context(session_id)
        return context.get_recent_context(turns)
    
    async def clear_session(self, session_id: str):
        """
        Clear a specific session's context.
        
        Args:
            session_id: Session identifier to clear
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleared session context: {session_id}")
    
    async def clear_all_sessions(self):
        """Clear all session contexts."""
        self.sessions.clear()
        logger.info("Cleared all session contexts")
    
    async def get_active_sessions(self) -> list:
        """
        Get list of active session IDs.
        
        Returns:
            List of active session identifiers
        """
        await self._cleanup_expired_sessions()
        return list(self.sessions.keys())
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """
        Get statistics about active sessions.
        
        Returns:
            Dictionary with session statistics
        """
        await self._cleanup_expired_sessions()
        
        total_sessions = len(self.sessions)
        total_turns = sum(len(ctx.history) for ctx in self.sessions.values())
        
        # Calculate average session age
        current_time = time.time()
        session_ages = [current_time - ctx.created_at for ctx in self.sessions.values()]
        avg_age = sum(session_ages) / len(session_ages) if session_ages else 0
        
        return {
            "active_sessions": total_sessions,
            "total_conversation_turns": total_turns,
            "average_session_age_seconds": avg_age,
            "session_timeout_seconds": self.session_timeout,
            "max_history_turns": self.max_history_turns
        }
    
    async def _cleanup_expired_sessions(self):
        """Remove expired sessions from memory."""
        current_time = time.time()
        
        # Only cleanup if enough time has passed
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        expired_sessions = []
        for session_id, context in self.sessions.items():
            if current_time - context.last_updated > self.session_timeout:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up expired session: {session_id}")
        
        self.last_cleanup = current_time
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    def configure(self, config: Dict[str, Any]):
        """
        Configure the context manager.
        
        Args:
            config: Configuration dictionary
        """
        if "session_timeout" in config:
            self.session_timeout = config["session_timeout"]
            
        if "max_history_turns" in config:
            self.max_history_turns = config["max_history_turns"]
            # Update existing sessions
            for context in self.sessions.values():
                context.max_history_turns = self.max_history_turns
                context._trim_history()
        
        if "cleanup_interval" in config:
            self.cleanup_interval = config["cleanup_interval"]
        
        logger.info(f"Configured context manager: timeout={self.session_timeout}s, "
                   f"max_turns={self.max_history_turns}, cleanup_interval={self.cleanup_interval}s")
    
    async def process_intent_with_context(self, intent: Intent, session_id: str) -> ConversationContext:
        """
        Process an intent and update conversation context.
        
        Args:
            intent: Intent to process
            session_id: Session identifier
            
        Returns:
            Updated conversation context
        """
        context = await self.get_context(session_id)
        context.add_user_turn(intent)
        
        # Update context metadata based on intent
        if intent.domain and intent.domain != context.metadata.get('current_domain'):
            context.metadata['current_domain'] = intent.domain
            context.metadata['domain_switch_count'] = context.metadata.get('domain_switch_count', 0) + 1
        
        # Track intent patterns for context-aware processing
        if 'recent_intents' not in context.metadata:
            context.metadata['recent_intents'] = []
        
        context.metadata['recent_intents'].append({
            'name': intent.name,
            'domain': intent.domain,
            'confidence': intent.confidence,
            'timestamp': intent.timestamp
        })
        
        # Keep only recent intents (last 5)
        context.metadata['recent_intents'] = context.metadata['recent_intents'][-5:]
        
        return context
    
    async def get_context_for_intent_processing(self, session_id: str, intent_domain: str = None) -> ConversationContext:
        """
        Get context optimized for intent processing with domain awareness.
        
        Args:
            session_id: Session identifier
            intent_domain: Expected intent domain for context optimization
            
        Returns:
            Conversation context with enhanced metadata
        """
        context = await self.get_context(session_id)
        
        # Add intent processing metadata
        if 'intent_processing' not in context.metadata:
            context.metadata['intent_processing'] = {
                'total_intents': 0,
                'successful_intents': 0,
                'failed_intents': 0,
                'domain_frequency': {},
                'avg_confidence': 0.0
            }
        
        # Update domain frequency if specified
        if intent_domain:
            domain_freq = context.metadata['intent_processing']['domain_frequency']
            domain_freq[intent_domain] = domain_freq.get(intent_domain, 0) + 1
        
        return context
    
    async def update_context_with_result(self, result: IntentResult, session_id: str):
        """
        Update conversation context with intent execution result.
        
        Args:
            result: Intent execution result
            session_id: Session identifier
        """
        context = await self.get_context(session_id)
        context.add_assistant_turn(result)
        
        # Update intent processing statistics
        if 'intent_processing' in context.metadata:
            stats = context.metadata['intent_processing']
            stats['total_intents'] += 1
            
            if result.success:
                stats['successful_intents'] += 1
            else:
                stats['failed_intents'] += 1
            
            # Update average confidence
            if 'recent_intents' in context.metadata and context.metadata['recent_intents']:
                recent_confidences = [i['confidence'] for i in context.metadata['recent_intents']]
                stats['avg_confidence'] = sum(recent_confidences) / len(recent_confidences)
        
        # Track conversation quality
        if 'conversation_quality' not in context.metadata:
            context.metadata['conversation_quality'] = {
                'response_relevance': 0.8,  # Default assumption
                'user_satisfaction': 0.8,
                'coherence_score': 0.8
            }
    
    def get_recent_intent_patterns(self, session_id: str, count: int = 3) -> List[Dict[str, Any]]:
        """
        Get recent intent patterns for context-aware processing.
        
        Args:
            session_id: Session identifier
            count: Number of recent intents to return
            
        Returns:
            List of recent intent information
        """
        if session_id not in self.sessions:
            return []
        
        context = self.sessions[session_id]
        recent_intents = context.metadata.get('recent_intents', [])
        return recent_intents[-count:] if recent_intents else []
    
    def get_dominant_domain(self, session_id: str) -> Optional[str]:
        """
        Get the dominant intent domain for this session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Most frequent domain name or None
        """
        if session_id not in self.sessions:
            return None
        
        context = self.sessions[session_id]
        if 'intent_processing' not in context.metadata:
            return None
        
        domain_freq = context.metadata['intent_processing'].get('domain_frequency', {})
        if not domain_freq:
            return None
        
        return max(domain_freq.items(), key=lambda x: x[1])[0]
    
    def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """
        Get comprehensive session statistics.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with session statistics
        """
        if session_id not in self.sessions:
            return {}
        
        context = self.sessions[session_id]
        stats = {
            'session_id': session_id,
            'created_at': context.created_at,
            'last_updated': context.last_updated,
            'duration': time.time() - context.created_at,
            'history_length': len(context.history),
            'max_history_turns': context.max_history_turns
        }
        
        # Add intent processing stats if available
        if 'intent_processing' in context.metadata:
            stats.update(context.metadata['intent_processing'])
        
        # Add current domain
        stats['current_domain'] = context.metadata.get('current_domain')
        stats['domain_switches'] = context.metadata.get('domain_switch_count', 0)
        
        return stats
    
    async def cleanup_session(self, session_id: str) -> bool:
        """
        Manually cleanup a specific session.
        
        Args:
            session_id: Session to cleanup
            
        Returns:
            True if session was found and cleaned up
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Manually cleaned up session: {session_id}")
            return True
        return False
    
    def get_active_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self.sessions)
    
    def get_all_session_ids(self) -> List[str]:
        """Get list of all active session IDs."""
        return list(self.sessions.keys()) 