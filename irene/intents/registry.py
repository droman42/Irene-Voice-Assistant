"""Intent handler registry."""

import re
import logging
from typing import Dict, Any, Optional, List, Pattern

from .models import Intent

logger = logging.getLogger(__name__)


class IntentRegistry:
    """Registry of intent handlers with pattern matching support."""
    
    def __init__(self):
        """Initialize the intent registry."""
        self.handlers: Dict[str, Any] = {}  # pattern -> handler
        self.compiled_patterns: Dict[str, Pattern] = {}  # pattern -> compiled regex
        self.handler_metadata: Dict[str, Dict[str, Any]] = {}  # pattern -> metadata
    
    def register_handler(self, pattern: str, handler: Any, metadata: Optional[Dict[str, Any]] = None):
        """
        Register an intent handler with a pattern.
        
        Args:
            pattern: Intent pattern (e.g., "weather.*", "timer.set", "conversation")
            handler: Handler instance that can execute matching intents
            metadata: Optional metadata about the handler
        """
        # Validate handler interface
        if not hasattr(handler, 'execute'):
            raise ValueError(f"Handler for pattern '{pattern}' must have an 'execute' method")
        
        if not hasattr(handler, 'can_handle'):
            raise ValueError(f"Handler for pattern '{pattern}' must have a 'can_handle' method")
        
        # Convert pattern to regex if it contains wildcards
        if '*' in pattern or '?' in pattern:
            # Convert simple wildcards to regex
            regex_pattern = pattern.replace('.', r'\.').replace('*', '.*').replace('?', '.')
            regex_pattern = f"^{regex_pattern}$"
            self.compiled_patterns[pattern] = re.compile(regex_pattern)
        
        self.handlers[pattern] = handler
        self.handler_metadata[pattern] = metadata or {}
        
        logger.info(f"Registered intent handler: {pattern} -> {handler.__class__.__name__}")
    
    def unregister_handler(self, pattern: str):
        """Remove a handler from the registry."""
        if pattern in self.handlers:
            del self.handlers[pattern]
            if pattern in self.compiled_patterns:
                del self.compiled_patterns[pattern]
            if pattern in self.handler_metadata:
                del self.handler_metadata[pattern]
            logger.info(f"Unregistered intent handler: {pattern}")
    
    def get_handler(self, intent: Intent) -> Optional[Any]:
        """
        Find the best handler for an intent.
        
        Args:
            intent: Intent to find handler for
            
        Returns:
            Handler instance or None if no match found
        """
        intent_name = intent.name
        
        # First try exact matches
        if intent_name in self.handlers:
            return self.handlers[intent_name]
        
        # Then try pattern matches (most specific first)
        matching_patterns = []
        
        for pattern in self.handlers.keys():
            if pattern in self.compiled_patterns:
                # Regex pattern match
                if self.compiled_patterns[pattern].match(intent_name):
                    matching_patterns.append((pattern, len(pattern.replace('*', ''))))
            else:
                # Simple prefix match for backward compatibility
                if intent_name.startswith(pattern):
                    matching_patterns.append((pattern, len(pattern)))
        
        if matching_patterns:
            # Sort by specificity (longer patterns first)
            matching_patterns.sort(key=lambda x: x[1], reverse=True)
            best_pattern = matching_patterns[0][0]
            return self.handlers[best_pattern]
        
        # Try domain fallback (e.g., "weather" for "weather.unknown_action")
        if '.' in intent_name:
            domain = intent_name.split('.')[0]
            if domain in self.handlers:
                return self.handlers[domain]
            
            # Try domain wildcard
            domain_wildcard = f"{domain}.*"
            if domain_wildcard in self.handlers:
                return self.handlers[domain_wildcard]
        
        logger.debug(f"No handler found for intent: {intent_name}")
        return None
    
    def get_handlers_for_domain(self, domain: str) -> List[Any]:
        """Get all handlers that can handle a specific domain."""
        handlers = []
        
        for pattern, handler in self.handlers.items():
            # Check exact domain match
            if pattern == domain:
                handlers.append(handler)
                continue
            
            # Check pattern match
            if pattern in self.compiled_patterns:
                test_intent = f"{domain}.test"
                if self.compiled_patterns[pattern].match(test_intent):
                    handlers.append(handler)
            elif pattern.startswith(f"{domain}."):
                handlers.append(handler)
        
        return handlers
    
    async def get_all_handlers(self) -> Dict[str, Any]:
        """Get all registered handlers."""
        return self.handlers.copy()
    
    def get_handler_info(self, pattern: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific handler."""
        if pattern not in self.handlers:
            return None
        
        handler = self.handlers[pattern]
        info = {
            "pattern": pattern,
            "class": handler.__class__.__name__,
            "metadata": self.handler_metadata.get(pattern, {}),
            "is_regex": pattern in self.compiled_patterns
        }
        
        # Add handler-specific information if available
        if hasattr(handler, 'get_info'):
            try:
                handler_info = handler.get_info()
                info.update(handler_info)
            except Exception as e:
                logger.warning(f"Error getting handler info for {pattern}: {e}")
        
        return info
    
    def list_patterns(self) -> List[str]:
        """Get list of all registered patterns."""
        return list(self.handlers.keys())
    
    def get_supported_intents(self) -> List[str]:
        """Get list of all supported intent patterns."""
        intents = []
        
        for pattern in self.handlers.keys():
            if '*' not in pattern and '?' not in pattern:
                # Exact intent name
                intents.append(pattern)
            else:
                # Pattern - provide example
                example = pattern.replace('*', 'example').replace('?', 'x')
                intents.append(f"{pattern} (e.g., {example})")
        
        return sorted(intents)
    
    async def validate_handlers(self) -> Dict[str, Dict[str, Any]]:
        """Validate all registered handlers and return status."""
        results = {}
        
        for pattern, handler in self.handlers.items():
            try:
                # Check if handler is available
                is_available = True
                if hasattr(handler, 'is_available'):
                    is_available = await handler.is_available()
                
                # Check required methods
                has_execute = hasattr(handler, 'execute')
                has_can_handle = hasattr(handler, 'can_handle')
                
                results[pattern] = {
                    "valid": has_execute and has_can_handle and is_available,
                    "available": is_available,
                    "has_execute": has_execute,
                    "has_can_handle": has_can_handle,
                    "class": handler.__class__.__name__,
                    "error": None
                }
                
            except Exception as e:
                results[pattern] = {
                    "valid": False,
                    "available": False,
                    "has_execute": False,
                    "has_can_handle": False,
                    "class": handler.__class__.__name__,
                    "error": str(e)
                }
        
        return results 