"""
Enhanced Conversation Context Management

Manages conversation context and history for sessions with advanced features
for the intent system including session persistence, context-aware processing,
and intelligent context management.
"""

import time
import logging
import asyncio
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from .models import UnifiedConversationContext, Intent, IntentResult
from ..core.metrics import get_metrics_collector

if TYPE_CHECKING:
    from ..workflows.base import RequestContext

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
        self.sessions: Dict[str, UnifiedConversationContext] = {}
        self.session_timeout = session_timeout
        self.max_history_turns = max_history_turns
        self.cleanup_interval = 300  # Cleanup every 5 minutes
        self.last_cleanup = time.time()
        self.metrics_collector = get_metrics_collector()  # Phase 2: Session analytics integration
    
    async def get_context(self, session_id: str) -> UnifiedConversationContext:
        """
        Retrieve or create conversation context for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            UnifiedConversationContext for the session
        """
        # Clean up expired sessions periodically
        await self._cleanup_expired_sessions()
        
        # Check if this is a new session
        is_new_session = session_id not in self.sessions
        
        if session_id in self.sessions:
            context = self.sessions[session_id]
            # Check if session has expired
            if time.time() - context.last_updated > self.session_timeout:
                logger.info(f"Session {session_id} expired, creating new context")
                
                # Phase 2: Record session end for expired session
                self.metrics_collector.record_session_end(session_id)
                
                del self.sessions[session_id]
                is_new_session = True  # Treat as new session
            else:
                return context
        
        # Create new context with Russian default
        context = UnifiedConversationContext(
            session_id=session_id,
            language="ru",  # Russian-first default
            max_history_turns=self.max_history_turns
        )
        self.sessions[session_id] = context
        logger.info(f"Created new conversation context for session: {session_id}")
        
        # Phase 2: Record session start for new sessions
        if is_new_session:
            self.metrics_collector.record_session_start(session_id)
        return context
    
    async def get_context_with_request_info(self, session_id: str, request_context: 'RequestContext' = None) -> UnifiedConversationContext:
        """
        Retrieve or create conversation context with client information from request context.
        
        Args:
            session_id: Unique session identifier
            request_context: Request context with client identification information
            
        Returns:
            UnifiedConversationContext for the session with client context applied
        """
        # Get or create base context
        context = await self.get_context(session_id)
        
        # Apply client information from request context if provided
        if request_context:
            # Update language preference
            if hasattr(request_context, 'language') and request_context.language:
                context.language = request_context.language
            
            # Set client identification and context
            if hasattr(request_context, 'client_id') and request_context.client_id:
                client_metadata = {
                    "room_name": getattr(request_context, 'room_name', None),
                    "source": request_context.source,
                    "last_request_time": time.time()
                }
                
                # Add device context if available
                if hasattr(request_context, 'device_context') and request_context.device_context:
                    client_metadata["available_devices"] = request_context.device_context.get("available_devices", [])
                    client_metadata["device_capabilities"] = request_context.device_context.get("device_capabilities", {})
                
                # Merge additional metadata
                if request_context.metadata:
                    client_metadata.update(request_context.metadata)
                
                # Set client context
                context.set_client_context(request_context.client_id, client_metadata)
                context.request_source = request_context.source
                
                logger.debug(f"Applied client context for session {session_id}: client_id={request_context.client_id}, room={request_context.room_name}")
        
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
    
    async def process_intent_with_context(self, intent: Intent, session_id: str) -> UnifiedConversationContext:
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
    
    async def get_context_for_intent_processing(self, session_id: str, intent_domain: str = None) -> UnifiedConversationContext:
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
        
        # Phase 2: Update session activity with intent execution result
        if hasattr(result, 'metadata') and result.metadata and 'original_intent' in result.metadata:
            intent_name = result.metadata['original_intent']
        else:
            intent_name = "unknown"
        
        self.metrics_collector.update_session_activity(session_id, intent_name, result.success)
        
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
    
    async def get_all_contexts(self) -> Dict[str, UnifiedConversationContext]:
        """Get all active conversation contexts for memory management."""
        await self._cleanup_expired_sessions()
        return self.sessions.copy()
    
    # Action ambiguity resolution methods for TODO16
    def resolve_contextual_command_ambiguity(
        self, 
        session_id: str,
        command_type: str,
        target_domains: List[str] = None,
        domain_priorities: Dict[str, int] = None,
        require_confirmation: bool = False
    ) -> Dict[str, Any]:
        """
        Generic contextual command disambiguation for any command type.
        
        Phase 1-3 TODO16: Implements sophisticated disambiguation logic using domain priorities,
        active action analysis, and recency fallback for contextual commands (stop, pause, resume, cancel, etc.).
        
        Phase 3 enhancements:
        - Enhanced multi-domain resolution with confidence scoring
        - User confirmation support for ambiguous cases
        - Improved priority resolution with tie-breaking
        
        Phase 4 enhancements:
        - Performance monitoring with configurable thresholds
        - Caching for domain priorities and patterns
        
        Args:
            session_id: Session identifier
            command_type: Type of contextual command ("stop", "pause", "resume", etc.)
            target_domains: Specific domains mentioned in command (if any)
            domain_priorities: Domain priority configuration
            require_confirmation: Whether to require user confirmation for ambiguous cases
            
        Returns:
            Dictionary with resolution information including target domain and confidence
        """
        # Phase 4 TODO16: Integrated performance monitoring with MetricsCollector
        start_time = time.perf_counter()
        
        # Perform disambiguation
        resolution = self._resolve_contextual_command_internal(
            session_id, command_type, target_domains, domain_priorities, require_confirmation
        )
        
        # Record metrics in unified system
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        metrics_collector = get_metrics_collector()
        metrics_collector.record_contextual_disambiguation(
            command_type=command_type,
            target_domain=resolution.get("target_domain"),
            latency_ms=latency_ms,
            confidence=resolution.get("confidence", 0.0),
            resolution_method=resolution.get("resolution", "unknown"),
            cache_hit=False  # TODO: Implement cache hit detection when caching is added
        )
        
        return resolution
    
    def _resolve_contextual_command_internal(
        self,
        session_id: str,
        command_type: str,
        target_domains: List[str] = None,
        domain_priorities: Dict[str, int] = None,
        require_confirmation: bool = False
    ) -> Dict[str, Any]:
        """Internal disambiguation logic"""
        
        if session_id not in self.sessions:
            return {"resolution": "no_session", "actions": [], "command_type": command_type}
        
        context = self.sessions[session_id]
        active_actions = getattr(context, 'active_actions', {})
        
        if not active_actions:
            return {"resolution": "no_active_actions", "actions": [], "command_type": command_type}
        
        # If specific domains mentioned in command, filter to those
        if target_domains:
            filtered_actions = {}
            for action_name, action_info in active_actions.items():
                action_domain = action_info.get('domain', 'unknown')
                if action_domain in target_domains:
                    filtered_actions[action_name] = action_info
            
            if filtered_actions:
                # Return the target domain for intent resolution
                target_domain = target_domains[0] if len(target_domains) == 1 else target_domains[0]  # Use first domain if multiple
                return {
                    "resolution": "domain_specific",
                    "target_domain": target_domain,
                    "actions": list(filtered_actions.keys()),
                    "target_domains": target_domains,
                    "action_details": filtered_actions,
                    "command_type": command_type
                }
            else:
                return {
                    "resolution": "no_matching_domain",
                    "target_domains": target_domains,
                    "actions": [],
                    "command_type": command_type
                }
        
        # Phase 3: Enhanced multi-domain resolution with confidence scoring
        if len(active_actions) > 1:
            # Group actions by domain and calculate resolution confidence
            domain_actions = {}
            domain_scores = {}
            
            for action_name, action_info in active_actions.items():
                domain = action_info.get('domain', 'unknown')
                if domain not in domain_actions:
                    domain_actions[domain] = []
                domain_actions[domain].append((action_name, action_info))
            
            # Calculate confidence scores for each domain
            for domain, actions in domain_actions.items():
                score = 0
                
                # Priority score (0-100 points)
                if domain_priorities:
                    priority = domain_priorities.get(domain, 0)
                    score += min(priority, 100)  # Cap at 100 points
                
                # Recency score (0-50 points based on most recent action in domain)
                most_recent_time = 0
                for action_name, action_info in actions:
                    started_at = action_info.get('started_at', 0)
                    most_recent_time = max(most_recent_time, started_at)
                
                if most_recent_time > 0:
                    # More recent actions get higher scores (up to 50 points)
                    current_time = time.time()
                    age_seconds = current_time - most_recent_time
                    recency_score = max(0, 50 - (age_seconds / 60))  # Decay over minutes
                    score += recency_score
                
                # Action count bonus (0-20 points for multiple actions in same domain)
                if len(actions) > 1:
                    score += min(len(actions) * 5, 20)
                
                domain_scores[domain] = score
            
            # Find highest scoring domain
            best_domain = max(domain_scores.keys(), key=lambda d: domain_scores[d])
            best_score = domain_scores[best_domain]
            
            # Check for ties (within 10 points)
            tied_domains = [d for d, s in domain_scores.items() if abs(s - best_score) <= 10]
            
            # Phase 3: Handle ambiguous cases requiring confirmation
            if len(tied_domains) > 1 and require_confirmation:
                return {
                    "resolution": "requires_confirmation",
                    "ambiguous_domains": tied_domains,
                    "domain_scores": domain_scores,
                    "actions": list(active_actions.keys()),
                    "action_details": active_actions,
                    "command_type": command_type,
                    "confidence": 0.5  # Low confidence due to ambiguity
                }
            
            # Return best domain with confidence score
            best_actions = domain_actions[best_domain]
            confidence = min(best_score / 150.0, 1.0)  # Normalize to 0-1 scale
            
            return {
                "resolution": "multi_domain_priority" if len(tied_domains) == 1 else "priority_with_tiebreak",
                "target_domain": best_domain,
                "priority_domain": best_domain,
                "priority_score": domain_priorities.get(best_domain, 0) if domain_priorities else 0,
                "confidence_score": best_score,
                "confidence": confidence,
                "actions": [action[0] for action in best_actions],
                "action_details": {action[0]: action[1] for action in best_actions},
                "domain_scores": domain_scores,
                "tied_domains": tied_domains if len(tied_domains) > 1 else [],
                "command_type": command_type
            }
        
        # Fallback: single action or most recent action (by started_at timestamp)
        if len(active_actions) == 1:
            # Single action - high confidence
            action_name, action_info = next(iter(active_actions.items()))
            target_domain = action_info.get('domain', 'unknown')
            return {
                "resolution": "single_action",
                "target_domain": target_domain,
                "actions": [action_name],
                "action_details": {action_name: action_info},
                "started_at": action_info.get('started_at', 0),
                "confidence": 0.95,  # High confidence for single action
                "command_type": command_type
            }
        
        # Multiple actions but no priorities - use most recent
        most_recent = None
        most_recent_time = 0
        
        for action_name, action_info in active_actions.items():
            started_at = action_info.get('started_at', 0)
            if started_at > most_recent_time:
                most_recent_time = started_at
                most_recent = (action_name, action_info)
        
        if most_recent:
            target_domain = most_recent[1].get('domain', 'unknown')
            # Calculate confidence based on how recent the action is
            current_time = time.time()
            age_seconds = current_time - most_recent_time
            confidence = max(0.3, 0.8 - (age_seconds / 300))  # Decay over 5 minutes, min 0.3
            
            return {
                "resolution": "most_recent",
                "target_domain": target_domain,
                "actions": [most_recent[0]],
                "action_details": {most_recent[0]: most_recent[1]},
                "started_at": most_recent_time,
                "confidence": confidence,
                "command_type": command_type
            }
        
        # Fallback: no actions to target
        return {
            "resolution": "no_actions", 
            "actions": [], 
            "command_type": command_type,
            "confidence": 0.0
        }
    
    def get_active_actions_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get summary of active actions for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Summary of active actions grouped by domain
        """
        if session_id not in self.sessions:
            return {"total_actions": 0, "domains": {}}
        
        context = self.sessions[session_id]
        active_actions = getattr(context, 'active_actions', {})
        
        if not active_actions:
            return {"total_actions": 0, "domains": {}}
        
        # Group by domain
        domains = {}
        for action_name, action_info in active_actions.items():
            domain = action_info.get('domain', 'unknown')
            if domain not in domains:
                domains[domain] = {
                    "actions": [],
                    "count": 0,
                    "latest_start": 0
                }
            
            domains[domain]["actions"].append({
                "name": action_name,
                "started_at": action_info.get('started_at', 0),
                "handler": action_info.get('handler', 'unknown')
            })
            domains[domain]["count"] += 1
            
            # Track latest start time for domain
            start_time = action_info.get('started_at', 0)
            if start_time > domains[domain]["latest_start"]:
                domains[domain]["latest_start"] = start_time
        
        return {
            "total_actions": len(active_actions),
            "domains": domains,
            "domain_count": len(domains)
        }
    
    def should_ask_for_clarification(
        self, 
        session_id: str, 
        domain_priorities: Dict[str, int] = None,
        clarification_threshold: int = 2
    ) -> Dict[str, Any]:
        """
        Determine if system should ask for clarification on stop commands.
        
        Args:
            session_id: Session identifier
            domain_priorities: Domain priority configuration
            clarification_threshold: Minimum number of actions to trigger clarification
            
        Returns:
            Information about whether clarification is needed
        """
        if session_id not in self.sessions:
            return {"needs_clarification": False, "reason": "no_session"}
        
        context = self.sessions[session_id]
        active_actions = getattr(context, 'active_actions', {})
        
        if len(active_actions) < clarification_threshold:
            return {"needs_clarification": False, "reason": "below_threshold"}
        
        # Check if there are multiple domains with similar priority
        if domain_priorities:
            domain_actions = {}
            for action_name, action_info in active_actions.items():
                domain = action_info.get('domain', 'unknown')
                if domain not in domain_actions:
                    domain_actions[domain] = []
                domain_actions[domain].append(action_name)
            
            # Get priorities for active domains
            domain_priorities_active = {}
            for domain in domain_actions:
                domain_priorities_active[domain] = domain_priorities.get(domain, 0)
            
            # Check if multiple domains have similar high priority (within 20 points)
            sorted_domains = sorted(domain_priorities_active.items(), key=lambda x: x[1], reverse=True)
            if len(sorted_domains) >= 2:
                highest_priority = sorted_domains[0][1]
                second_priority = sorted_domains[1][1]
                
                if highest_priority - second_priority <= 20:
                    return {
                        "needs_clarification": True,
                        "reason": "similar_priorities",
                        "conflicting_domains": [sorted_domains[0][0], sorted_domains[1][0]],
                        "domain_actions": domain_actions
                    }
        
        return {"needs_clarification": False, "reason": "clear_priority"}
    
    async def update_language_preference(self, session_id: str, language: str):
        """
        Update user's language preference for future sessions.
        
        Phase 3: Language preference persistence implementation.
        
        Args:
            session_id: Session identifier
            language: Target language code (e.g., 'ru', 'en')
        """
        context = await self.get_context(session_id)
        context.user_preferences['language'] = language
        context.language = language
        context.last_updated = time.time()
        logger.info(f"Updated language preference for session {session_id}: {language}")
    
    # Phase 3 TODO16: Disambiguation context storage for follow-up resolution
    
    def store_disambiguation_context(self, session_id: str, disambiguation_data: Dict[str, Any]) -> None:
        """
        Store disambiguation context for follow-up resolution.
        
        Args:
            session_id: Session identifier
            disambiguation_data: Disambiguation context data
        """
        if session_id not in self.sessions:
            return
        
        context = self.sessions[session_id]
        
        # Store disambiguation context with expiration
        if not hasattr(context, 'disambiguation_context'):
            context.disambiguation_context = {}
        
        context.disambiguation_context = disambiguation_data
        logger.debug(f"Stored disambiguation context for session {session_id}: {disambiguation_data['type']}")
    
    def get_disambiguation_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get stored disambiguation context for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Disambiguation context data or None if not found/expired
        """
        if session_id not in self.sessions:
            return None
        
        context = self.sessions[session_id]
        disambiguation_data = getattr(context, 'disambiguation_context', None)
        
        if not disambiguation_data:
            return None
        
        # Check if context has expired (5 minutes)
        timestamp = disambiguation_data.get('timestamp', 0)
        if time.time() - timestamp > 300:  # 5 minutes
            self.clear_disambiguation_context(session_id)
            return None
        
        return disambiguation_data
    
    def clear_disambiguation_context(self, session_id: str) -> None:
        """
        Clear disambiguation context for a session.
        
        Args:
            session_id: Session identifier
        """
        if session_id not in self.sessions:
            return
        
        context = self.sessions[session_id]
        if hasattr(context, 'disambiguation_context'):
            delattr(context, 'disambiguation_context')
            logger.debug(f"Cleared disambiguation context for session {session_id}") 