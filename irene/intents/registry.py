"""Intent handler registry."""

import re
import logging
from typing import Dict, Any, Optional, List, Pattern

from .models import Intent

logger = logging.getLogger(__name__)


class IntentRegistry:
    """Registry of intent handlers with pattern matching support and capability tracking."""
    
    def __init__(self):
        """Initialize the intent registry."""
        self.handlers: Dict[str, Any] = {}  # pattern -> handler
        self.compiled_patterns: Dict[str, Pattern] = {}  # pattern -> compiled regex
        self.handler_metadata: Dict[str, Dict[str, Any]] = {}  # pattern -> metadata
        
        # Phase 3 TODO16: Capability tracking for contextual commands
        self.contextual_capabilities: Dict[str, List[str]] = {}  # domain -> [supported_commands]
        self.command_handlers: Dict[str, List[str]] = {}  # command -> [supporting_domains]
    
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
        
        # Phase 3 TODO16: Extract and track contextual command capabilities
        self._update_contextual_capabilities(pattern, handler, metadata or {})
        
        logger.info(f"Registered intent handler: {pattern} -> {handler.__class__.__name__}")
    
    def unregister_handler(self, pattern: str):
        """Remove a handler from the registry."""
        if pattern in self.handlers:
            # Phase 3 TODO16: Clean up capability tracking
            self._cleanup_contextual_capabilities(pattern)
            
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
    
    # Phase 3 TODO16: Contextual command capability tracking methods
    
    def _update_contextual_capabilities(self, pattern: str, handler: Any, metadata: Dict[str, Any]) -> None:
        """
        Extract and update contextual command capabilities from handler metadata.
        
        Args:
            pattern: Handler pattern
            handler: Handler instance
            metadata: Handler metadata containing capability information
        """
        # Extract domain from pattern or metadata
        domain = self._extract_domain_from_pattern(pattern)
        if not domain and 'handler_domain' in metadata:
            domain = metadata['handler_domain']
        
        if not domain:
            return  # Skip if no domain can be determined
        
        # Extract supported contextual commands from metadata
        supported_commands = set()
        
        # Check for action_patterns in metadata (from donation files)
        if 'supported_actions' in metadata:
            actions = metadata['supported_actions']
            if isinstance(actions, list):
                supported_commands.update(actions)
        
        # Check for contextual command patterns
        contextual_commands = ['stop', 'pause', 'resume', 'cancel', 'next', 'previous', 'volume']
        for command in contextual_commands:
            # Check if handler supports this command based on patterns or methods
            if self._handler_supports_command(handler, command, metadata):
                supported_commands.add(command)
        
        # Update capability tracking
        if supported_commands:
            self.contextual_capabilities[domain] = list(supported_commands)
            
            # Update reverse mapping (command -> domains)
            for command in supported_commands:
                if command not in self.command_handlers:
                    self.command_handlers[command] = []
                if domain not in self.command_handlers[command]:
                    self.command_handlers[command].append(domain)
            
            logger.debug(f"Registered contextual capabilities for {domain}: {list(supported_commands)}")
    
    def _cleanup_contextual_capabilities(self, pattern: str) -> None:
        """
        Clean up contextual command capabilities when a handler is unregistered.
        
        Args:
            pattern: Handler pattern being unregistered
        """
        domain = self._extract_domain_from_pattern(pattern)
        if not domain:
            return
        
        # Remove domain from capabilities
        if domain in self.contextual_capabilities:
            commands = self.contextual_capabilities[domain]
            del self.contextual_capabilities[domain]
            
            # Clean up reverse mapping
            for command in commands:
                if command in self.command_handlers:
                    if domain in self.command_handlers[command]:
                        self.command_handlers[command].remove(domain)
                    # Remove command entry if no domains support it
                    if not self.command_handlers[command]:
                        del self.command_handlers[command]
            
            logger.debug(f"Cleaned up contextual capabilities for {domain}")
    
    def _extract_domain_from_pattern(self, pattern: str) -> Optional[str]:
        """Extract domain from handler pattern."""
        if '.' in pattern:
            return pattern.split('.')[0]
        return pattern if not ('*' in pattern or '?' in pattern) else None
    
    def _handler_supports_command(self, handler: Any, command: str, metadata: Dict[str, Any]) -> bool:
        """
        Check if a handler supports a specific contextual command.
        
        Args:
            handler: Handler instance
            command: Contextual command to check
            metadata: Handler metadata
            
        Returns:
            True if handler supports the command
        """
        # Check method existence
        method_name = f"_handle_{command}_action"
        if hasattr(handler, method_name):
            return True
        
        # Check generic method patterns
        generic_methods = [f"_handle_{command}", f"handle_{command}", f"{command}_action"]
        for method in generic_methods:
            if hasattr(handler, method):
                return True
        
        # Check metadata patterns
        if 'supported_actions' in metadata:
            actions = metadata['supported_actions']
            if isinstance(actions, list) and command in actions:
                return True
        
        return False
    
    def get_handlers_for_contextual_command(self, command: str) -> List[str]:
        """
        Get list of domains that support a specific contextual command.
        
        Args:
            command: Contextual command (e.g., "stop", "pause", "resume")
            
        Returns:
            List of domain names that support the command
        """
        return self.command_handlers.get(command, [])
    
    def get_contextual_capabilities(self, domain: str) -> List[str]:
        """
        Get list of contextual commands supported by a domain.
        
        Args:
            domain: Domain name
            
        Returns:
            List of supported contextual commands
        """
        return self.contextual_capabilities.get(domain, [])
    
    def get_all_contextual_capabilities(self) -> Dict[str, List[str]]:
        """
        Get complete mapping of domains to their supported contextual commands.
        
        Returns:
            Dictionary mapping domain names to lists of supported commands
        """
        return self.contextual_capabilities.copy()
    
    def can_handle_contextual_command(self, command: str, domain: str = None) -> bool:
        """
        Check if a contextual command can be handled, optionally by a specific domain.
        
        Args:
            command: Contextual command to check
            domain: Optional specific domain to check
            
        Returns:
            True if the command can be handled
        """
        if domain:
            return command in self.contextual_capabilities.get(domain, [])
        else:
            return command in self.command_handlers
    
    def get_capability_summary(self) -> Dict[str, Any]:
        """
        Get summary of all contextual command capabilities.
        
        Returns:
            Summary dictionary with capability statistics
        """
        total_domains = len(self.contextual_capabilities)
        total_commands = len(self.command_handlers)
        
        # Calculate coverage statistics
        command_coverage = {}
        for command, domains in self.command_handlers.items():
            command_coverage[command] = len(domains)
        
        domain_coverage = {}
        for domain, commands in self.contextual_capabilities.items():
            domain_coverage[domain] = len(commands)
        
        return {
            "total_domains_with_capabilities": total_domains,
            "total_contextual_commands": total_commands,
            "command_coverage": command_coverage,  # command -> number of supporting domains
            "domain_coverage": domain_coverage,    # domain -> number of supported commands
            "domains": list(self.contextual_capabilities.keys()),
            "commands": list(self.command_handlers.keys())
        }