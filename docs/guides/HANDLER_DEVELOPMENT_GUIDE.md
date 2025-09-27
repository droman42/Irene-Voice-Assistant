# Handler Development Guide - Contextual Commands

## Overview

This guide covers best practices for developing intent handlers that support the contextual command disambiguation system. It includes patterns, performance considerations, and implementation guidelines for Phase 4 TODO16.

## Table of Contents

1. [Handler Architecture](#handler-architecture)
2. [Contextual Command Support](#contextual-command-support)
3. [Performance Best Practices](#performance-best-practices)
4. [Action Lifecycle Management](#action-lifecycle-management)
5. [Error Handling](#error-handling)
6. [Testing Strategies](#testing-strategies)
7. [Configuration Guidelines](#configuration-guidelines)

## Handler Architecture

### Base Handler Structure

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import asyncio
import logging
import time

from irene.intents.handlers.base import IntentHandler
from irene.intents.models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)

class MyDomainHandler(IntentHandler):
    """
    Example handler with contextual command support.
    
    Supports: stop, pause, resume, cancel commands
    Domain: my_domain
    Priority: 75 (configurable in donation file)
    """
    
    def __init__(self):
        super().__init__()
        self.domain = "my_domain"
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._paused_states: Dict[str, Dict[str, Any]] = {}
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process the intent"""
        return (
            intent.domain == self.domain and 
            intent.action in self._get_supported_actions()
        )
    
    def _get_supported_actions(self) -> List[str]:
        """Get list of supported actions including contextual commands"""
        return [
            # Domain-specific actions
            "start_task", "configure_task", "status_task",
            # Contextual commands (resolved from contextual.* intents)
            "stop", "pause", "resume", "cancel"
        ]
    
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Main execution method with contextual command routing"""
        try:
            # Route to appropriate method based on intent action
            if intent.action == "stop":
                return await self._handle_stop_action(intent, context)
            elif intent.action == "pause":
                return await self._handle_pause_action(intent, context)
            elif intent.action == "resume":
                return await self._handle_resume_action(intent, context)
            elif intent.action == "cancel":
                return await self._handle_cancel_action(intent, context)
            elif intent.action == "start_task":
                return await self._handle_start_task(intent, context)
            else:
                return await self._handle_unknown_action(intent, context)
                
        except Exception as e:
            logger.error(f"Error executing intent {intent.name}: {e}")
            return IntentResult(
                success=False,
                response="An error occurred while processing your request",
                intent_name=intent.name,
                handler_name=self.__class__.__name__,
                error=str(e)
            )
```

## Contextual Command Support

### Stop Command Implementation

```python
async def _handle_stop_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
    """
    Handle domain-specific stop command.
    
    This method receives a resolved intent (e.g., "my_domain.stop") after
    the orchestrator has performed contextual disambiguation.
    """
    try:
        stopped_actions = []
        
        # Find and stop all active actions for this domain
        for action_name, action_info in list(context.active_actions.items()):
            if action_info.get('domain') == self.domain:
                # Stop the specific action
                success = await self._stop_specific_action(action_name, action_info)
                if success:
                    stopped_actions.append(action_name)
                    # Remove from active actions
                    context.remove_completed_action(action_name)
        
        # Clean up handler-specific state
        await self._cleanup_stopped_actions(stopped_actions)
        
        if stopped_actions:
            response = f"Stopped {len(stopped_actions)} action(s): {', '.join(stopped_actions)}"
            return IntentResult(
                success=True,
                response=response,
                intent_name=intent.name,
                handler_name=self.__class__.__name__,
                metadata={"stopped_actions": stopped_actions}
            )
        else:
            return IntentResult(
                success=False,
                response="No active actions to stop",
                intent_name=intent.name,
                handler_name=self.__class__.__name__
            )
            
    except Exception as e:
        logger.error(f"Error stopping actions: {e}")
        return IntentResult(
            success=False,
            response="Failed to stop actions",
            intent_name=intent.name,
            handler_name=self.__class__.__name__,
            error=str(e)
        )

async def _stop_specific_action(self, action_name: str, action_info: Dict[str, Any]) -> bool:
    """Stop a specific action and clean up resources"""
    try:
        # Cancel async task if exists
        if action_name in self._active_tasks:
            task = self._active_tasks[action_name]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling
            del self._active_tasks[action_name]
        
        # Clean up action-specific resources
        await self._cleanup_action_resources(action_name, action_info)
        
        logger.info(f"Successfully stopped action: {action_name}")
        return True
        
    except Exception as e:
        logger.error(f"Error stopping action {action_name}: {e}")
        return False
```

### Pause/Resume Implementation

```python
async def _handle_pause_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
    """Handle domain-specific pause command"""
    try:
        paused_actions = []
        
        for action_name, action_info in context.active_actions.items():
            if action_info.get('domain') == self.domain:
                # Save current state before pausing
                current_state = await self._get_action_state(action_name)
                self._paused_states[action_name] = {
                    'state': current_state,
                    'action_info': action_info.copy(),
                    'paused_at': time.time()
                }
                
                # Pause the action (but don't remove from active_actions)
                success = await self._pause_specific_action(action_name, action_info)
                if success:
                    paused_actions.append(action_name)
        
        if paused_actions:
            response = f"Paused {len(paused_actions)} action(s)"
            return IntentResult(
                success=True,
                response=response,
                intent_name=intent.name,
                handler_name=self.__class__.__name__,
                metadata={"paused_actions": paused_actions}
            )
        else:
            return IntentResult(
                success=False,
                response="No active actions to pause",
                intent_name=intent.name,
                handler_name=self.__class__.__name__
            )
            
    except Exception as e:
        logger.error(f"Error pausing actions: {e}")
        return IntentResult(
            success=False,
            response="Failed to pause actions",
            intent_name=intent.name,
            handler_name=self.__class__.__name__,
            error=str(e)
        )

async def _handle_resume_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
    """Handle domain-specific resume command"""
    try:
        resumed_actions = []
        
        for action_name, paused_data in list(self._paused_states.items()):
            # Restore action from saved state
            success = await self._resume_specific_action(
                action_name, 
                paused_data['state'], 
                paused_data['action_info']
            )
            
            if success:
                resumed_actions.append(action_name)
                # Remove from paused states
                del self._paused_states[action_name]
        
        if resumed_actions:
            response = f"Resumed {len(resumed_actions)} action(s)"
            return IntentResult(
                success=True,
                response=response,
                intent_name=intent.name,
                handler_name=self.__class__.__name__,
                metadata={"resumed_actions": resumed_actions}
            )
        else:
            return IntentResult(
                success=False,
                response="No paused actions to resume",
                intent_name=intent.name,
                handler_name=self.__class__.__name__
            )
            
    except Exception as e:
        logger.error(f"Error resuming actions: {e}")
        return IntentResult(
            success=False,
            response="Failed to resume actions",
            intent_name=intent.name,
            handler_name=self.__class__.__name__,
            error=str(e)
        )
```

### Cancel Command Implementation

```python
async def _handle_cancel_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
    """
    Handle domain-specific cancel command.
    
    Cancel is more destructive than stop - it removes actions completely
    and cleans up all associated state.
    """
    try:
        cancelled_actions = []
        
        # Cancel active actions
        for action_name, action_info in list(context.active_actions.items()):
            if action_info.get('domain') == self.domain:
                success = await self._cancel_specific_action(action_name, action_info)
                if success:
                    cancelled_actions.append(action_name)
                    context.remove_completed_action(action_name)
        
        # Cancel paused actions
        for action_name in list(self._paused_states.keys()):
            await self._cancel_paused_action(action_name)
            cancelled_actions.append(action_name)
            del self._paused_states[action_name]
        
        # Full cleanup
        await self._cleanup_all_resources()
        
        if cancelled_actions:
            response = f"Cancelled {len(cancelled_actions)} action(s)"
            return IntentResult(
                success=True,
                response=response,
                intent_name=intent.name,
                handler_name=self.__class__.__name__,
                metadata={"cancelled_actions": cancelled_actions}
            )
        else:
            return IntentResult(
                success=False,
                response="No actions to cancel",
                intent_name=intent.name,
                handler_name=self.__class__.__name__
            )
            
    except Exception as e:
        logger.error(f"Error cancelling actions: {e}")
        return IntentResult(
            success=False,
            response="Failed to cancel actions",
            intent_name=intent.name,
            handler_name=self.__class__.__name__,
            error=str(e)
        )
```

## Performance Best Practices

### Async/Await Patterns

```python
# ✅ Good: Non-blocking operations
async def _stop_specific_action(self, action_name: str, action_info: Dict[str, Any]) -> bool:
    """Efficient async action stopping"""
    try:
        # Use asyncio.gather for parallel operations
        cleanup_tasks = [
            self._cleanup_task_resources(action_name),
            self._notify_action_stopped(action_name),
            self._update_action_metrics(action_name)
        ]
        
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        return True
        
    except Exception as e:
        logger.error(f"Error stopping action {action_name}: {e}")
        return False

# ❌ Bad: Blocking operations
def _stop_specific_action_blocking(self, action_name: str, action_info: Dict[str, Any]) -> bool:
    """Inefficient blocking action stopping"""
    # This blocks the event loop
    time.sleep(1)  # Don't do this!
    
    # Synchronous file I/O
    with open(f"/tmp/{action_name}.log", "w") as f:  # Don't do this!
        f.write("Action stopped")
    
    return True
```

### Memory Management

```python
class MemoryEfficientHandler(IntentHandler):
    """Handler with efficient memory management"""
    
    def __init__(self):
        super().__init__()
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._action_cache: Dict[str, Any] = {}
        self._cache_max_size = 100  # Limit cache size
        self._cache_ttl = 300  # 5 minute TTL
    
    async def _cleanup_stopped_actions(self, stopped_actions: List[str]) -> None:
        """Clean up memory for stopped actions"""
        for action_name in stopped_actions:
            # Remove from caches
            self._action_cache.pop(action_name, None)
            
            # Clean up task references
            if action_name in self._active_tasks:
                del self._active_tasks[action_name]
        
        # Periodic cache cleanup
        if len(self._action_cache) > self._cache_max_size:
            await self._cleanup_old_cache_entries()
    
    async def _cleanup_old_cache_entries(self) -> None:
        """Remove old cache entries to prevent memory leaks"""
        current_time = time.time()
        expired_keys = []
        
        for key, data in self._action_cache.items():
            if isinstance(data, dict) and 'created_at' in data:
                if current_time - data['created_at'] > self._cache_ttl:
                    expired_keys.append(key)
        
        for key in expired_keys:
            del self._action_cache[key]
        
        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
```

### Latency Optimization

```python
async def _handle_stop_action_optimized(self, intent: Intent, context: ConversationContext) -> IntentResult:
    """Optimized stop action with <2ms target latency"""
    start_time = time.perf_counter()
    
    try:
        # Fast path: Pre-filter actions by domain
        domain_actions = {
            name: info for name, info in context.active_actions.items()
            if info.get('domain') == self.domain
        }
        
        if not domain_actions:
            # Early return for no actions
            return IntentResult(
                success=False,
                response="No active actions to stop",
                intent_name=intent.name,
                handler_name=self.__class__.__name__
            )
        
        # Parallel stopping for multiple actions
        stop_tasks = [
            self._stop_specific_action(name, info)
            for name, info in domain_actions.items()
        ]
        
        results = await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        # Process results
        stopped_actions = []
        for i, (action_name, result) in enumerate(zip(domain_actions.keys(), results)):
            if result is True:  # Successful stop
                stopped_actions.append(action_name)
                context.remove_completed_action(action_name)
            elif isinstance(result, Exception):
                logger.warning(f"Failed to stop action {action_name}: {result}")
        
        # Measure performance
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        if latency_ms > 5.0:  # Log slow operations
            logger.warning(f"Stop action took {latency_ms:.2f}ms (threshold: 5ms)")
        
        response = f"Stopped {len(stopped_actions)} action(s)"
        return IntentResult(
            success=len(stopped_actions) > 0,
            response=response,
            intent_name=intent.name,
            handler_name=self.__class__.__name__,
            metadata={
                "stopped_actions": stopped_actions,
                "latency_ms": latency_ms
            }
        )
        
    except Exception as e:
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        logger.error(f"Error in stop action ({latency_ms:.2f}ms): {e}")
        return IntentResult(
            success=False,
            response="Failed to stop actions",
            intent_name=intent.name,
            handler_name=self.__class__.__name__,
            error=str(e)
        )
```

## Action Lifecycle Management

### Proper Action Registration

```python
async def _handle_start_task(self, intent: Intent, context: ConversationContext) -> IntentResult:
    """Start a new task and register it properly"""
    try:
        # Extract parameters
        task_name = intent.entities.get('task_name', f"task_{int(time.time())}")
        task_config = intent.entities.get('config', {})
        
        # Create and start the task
        task = asyncio.create_task(self._run_task(task_name, task_config))
        self._active_tasks[task_name] = task
        
        # Register with conversation context
        action_info = {
            'domain': self.domain,
            'action': 'run_task',
            'started_at': time.time(),
            'task_name': task_name,
            'config': task_config,
            'handler': self.__class__.__name__
        }
        
        context.add_active_action(task_name, action_info)
        
        # Set up task completion callback
        task.add_done_callback(
            lambda t: self._on_task_completed(task_name, t, context)
        )
        
        return IntentResult(
            success=True,
            response=f"Started task: {task_name}",
            intent_name=intent.name,
            handler_name=self.__class__.__name__,
            metadata={"task_name": task_name}
        )
        
    except Exception as e:
        logger.error(f"Error starting task: {e}")
        return IntentResult(
            success=False,
            response="Failed to start task",
            intent_name=intent.name,
            handler_name=self.__class__.__name__,
            error=str(e)
        )

def _on_task_completed(self, task_name: str, task: asyncio.Task, context: ConversationContext) -> None:
    """Handle task completion"""
    try:
        if task.cancelled():
            logger.info(f"Task {task_name} was cancelled")
        elif task.exception():
            logger.error(f"Task {task_name} failed: {task.exception()}")
        else:
            logger.info(f"Task {task_name} completed successfully")
        
        # Clean up
        self._active_tasks.pop(task_name, None)
        context.remove_completed_action(task_name)
        
    except Exception as e:
        logger.error(f"Error handling task completion for {task_name}: {e}")
```

### State Synchronization

```python
async def _synchronize_action_state(self, context: ConversationContext) -> None:
    """Synchronize handler state with conversation context"""
    try:
        # Remove completed tasks from active actions
        completed_tasks = []
        for task_name, task in self._active_tasks.items():
            if task.done():
                completed_tasks.append(task_name)
        
        for task_name in completed_tasks:
            del self._active_tasks[task_name]
            context.remove_completed_action(task_name)
        
        # Add missing active actions
        for task_name, task in self._active_tasks.items():
            if task_name not in context.active_actions:
                action_info = {
                    'domain': self.domain,
                    'action': 'run_task',
                    'started_at': time.time(),
                    'task_name': task_name,
                    'handler': self.__class__.__name__
                }
                context.add_active_action(task_name, action_info)
        
        logger.debug(f"Synchronized {len(self._active_tasks)} active tasks")
        
    except Exception as e:
        logger.error(f"Error synchronizing action state: {e}")
```

## Error Handling

### Graceful Degradation

```python
async def _handle_stop_action_with_fallback(self, intent: Intent, context: ConversationContext) -> IntentResult:
    """Stop action with graceful error handling"""
    stopped_actions = []
    failed_actions = []
    
    try:
        # Attempt to stop each action individually
        for action_name, action_info in list(context.active_actions.items()):
            if action_info.get('domain') == self.domain:
                try:
                    success = await asyncio.wait_for(
                        self._stop_specific_action(action_name, action_info),
                        timeout=2.0  # 2 second timeout per action
                    )
                    
                    if success:
                        stopped_actions.append(action_name)
                        context.remove_completed_action(action_name)
                    else:
                        failed_actions.append(action_name)
                        
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout stopping action {action_name}")
                    failed_actions.append(action_name)
                    # Force cleanup
                    await self._force_cleanup_action(action_name)
                    
                except Exception as e:
                    logger.error(f"Error stopping action {action_name}: {e}")
                    failed_actions.append(action_name)
        
        # Determine overall success
        total_actions = len(stopped_actions) + len(failed_actions)
        success_rate = len(stopped_actions) / total_actions if total_actions > 0 else 0
        
        if success_rate >= 0.8:  # 80% success threshold
            response = f"Stopped {len(stopped_actions)} action(s)"
            if failed_actions:
                response += f" ({len(failed_actions)} failed)"
            
            return IntentResult(
                success=True,
                response=response,
                intent_name=intent.name,
                handler_name=self.__class__.__name__,
                metadata={
                    "stopped_actions": stopped_actions,
                    "failed_actions": failed_actions
                }
            )
        else:
            return IntentResult(
                success=False,
                response=f"Failed to stop most actions ({len(failed_actions)}/{total_actions} failed)",
                intent_name=intent.name,
                handler_name=self.__class__.__name__,
                metadata={
                    "stopped_actions": stopped_actions,
                    "failed_actions": failed_actions
                }
            )
            
    except Exception as e:
        logger.error(f"Critical error in stop action: {e}")
        return IntentResult(
            success=False,
            response="Critical error occurred while stopping actions",
            intent_name=intent.name,
            handler_name=self.__class__.__name__,
            error=str(e)
        )

async def _force_cleanup_action(self, action_name: str) -> None:
    """Force cleanup of an action that failed to stop gracefully"""
    try:
        # Cancel task forcefully
        if action_name in self._active_tasks:
            task = self._active_tasks[action_name]
            task.cancel()
            del self._active_tasks[action_name]
        
        # Clean up resources
        await self._emergency_cleanup_resources(action_name)
        
        logger.warning(f"Force cleaned up action: {action_name}")
        
    except Exception as e:
        logger.error(f"Error in force cleanup for {action_name}: {e}")
```

## Testing Strategies

### Unit Testing

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncio

class TestMyDomainHandler:
    
    @pytest.fixture
    def handler(self):
        return MyDomainHandler()
    
    @pytest.fixture
    def context(self):
        context = ConversationContext(session_id="test", client_id="test", language="en")
        context.active_actions = {
            "test_task": {
                "domain": "my_domain",
                "action": "run_task",
                "started_at": time.time(),
                "task_name": "test_task"
            }
        }
        return context
    
    @pytest.mark.asyncio
    async def test_stop_action_success(self, handler, context):
        """Test successful stop action"""
        # Mock the stop method
        handler._stop_specific_action = AsyncMock(return_value=True)
        handler._cleanup_stopped_actions = AsyncMock()
        
        intent = Intent(
            name="my_domain.stop",
            domain="my_domain",
            action="stop",
            text="stop my task",
            confidence=0.9
        )
        
        result = await handler._handle_stop_action(intent, context)
        
        assert result.success is True
        assert "stopped" in result.response.lower()
        assert len(context.active_actions) == 0
        
        # Verify mocks were called
        handler._stop_specific_action.assert_called_once()
        handler._cleanup_stopped_actions.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_action_no_active_actions(self, handler):
        """Test stop action with no active actions"""
        context = ConversationContext(session_id="test", client_id="test", language="en")
        # No active actions
        
        intent = Intent(
            name="my_domain.stop",
            domain="my_domain",
            action="stop",
            text="stop",
            confidence=0.9
        )
        
        result = await handler._handle_stop_action(intent, context)
        
        assert result.success is False
        assert "no active actions" in result.response.lower()
    
    @pytest.mark.asyncio
    async def test_stop_action_performance(self, handler, context):
        """Test stop action performance"""
        # Add many active actions
        for i in range(10):
            context.active_actions[f"task_{i}"] = {
                "domain": "my_domain",
                "action": "run_task",
                "started_at": time.time(),
                "task_name": f"task_{i}"
            }
        
        handler._stop_specific_action = AsyncMock(return_value=True)
        handler._cleanup_stopped_actions = AsyncMock()
        
        intent = Intent(
            name="my_domain.stop",
            domain="my_domain",
            action="stop",
            text="stop all",
            confidence=0.9
        )
        
        start_time = time.perf_counter()
        result = await handler._handle_stop_action(intent, context)
        end_time = time.perf_counter()
        
        latency_ms = (end_time - start_time) * 1000
        
        assert result.success is True
        assert latency_ms < 10.0  # Should complete within 10ms
        assert len(context.active_actions) == 0
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_full_contextual_command_flow():
    """Test complete contextual command flow"""
    # Set up components
    handler = MyDomainHandler()
    registry = IntentRegistry()
    registry.register_handler("my_domain", handler)
    
    context_manager = ContextManager()
    orchestrator = IntentOrchestrator(
        registry=registry,
        context_manager=context_manager,
        domain_priorities={"my_domain": 75}
    )
    
    # Set up context with active action
    session_id = "integration_test"
    context = await context_manager.get_context(session_id)
    context.active_actions = {
        "test_task": {
            "domain": "my_domain",
            "action": "run_task",
            "started_at": time.time()
        }
    }
    
    # Create contextual intent (from NLU)
    contextual_intent = Intent(
        name="contextual.stop",
        domain="contextual",
        action="stop",
        text="stop",
        confidence=0.9
    )
    
    # Execute through orchestrator
    result = await orchestrator.execute_intent(contextual_intent, context)
    
    # Verify results
    assert result.success is True
    assert "stopped" in result.response.lower()
    assert len(context.active_actions) == 0
```

## Configuration Guidelines

### Donation File Structure

```json
{
  "handler_name": "my_domain_handler",
  "display_name": "My Domain Handler",
  "description": "Handles my domain specific tasks with contextual command support",
  "domain": "my_domain",
  "version": "1.0.0",
  
  "action_domain_priority": 75,
  
  "contextual_commands": {
    "stop": {
      "patterns": ["stop", "halt", "end", "terminate"],
      "description": "Stop all active domain tasks",
      "destructive": true
    },
    "pause": {
      "patterns": ["pause", "hold", "suspend", "freeze"],
      "description": "Pause active domain tasks",
      "destructive": false
    },
    "resume": {
      "patterns": ["resume", "continue", "restart", "unpause"],
      "description": "Resume paused domain tasks",
      "destructive": false
    },
    "cancel": {
      "patterns": ["cancel", "abort", "remove", "delete"],
      "description": "Cancel and remove domain tasks",
      "destructive": true
    }
  },
  
  "intents": {
    "my_domain.start_task": {
      "description": "Start a new domain task",
      "parameters": [
        {
          "name": "task_name",
          "type": "string",
          "required": false,
          "description": "Name of the task to start"
        },
        {
          "name": "config",
          "type": "object",
          "required": false,
          "description": "Task configuration parameters"
        }
      ]
    },
    "my_domain.stop": {
      "description": "Stop active domain tasks",
      "parameters": []
    },
    "my_domain.pause": {
      "description": "Pause active domain tasks",
      "parameters": []
    },
    "my_domain.resume": {
      "description": "Resume paused domain tasks",
      "parameters": []
    },
    "my_domain.cancel": {
      "description": "Cancel domain tasks",
      "parameters": []
    }
  },
  
  "performance": {
    "max_concurrent_actions": 10,
    "action_timeout_seconds": 300,
    "cleanup_interval_seconds": 60
  }
}
```

### Performance Configuration

```python
# In your handler's __init__ method
def __init__(self):
    super().__init__()
    
    # Performance settings
    self._max_concurrent_actions = 10
    self._action_timeout = 300  # 5 minutes
    self._cleanup_interval = 60  # 1 minute
    
    # Start periodic cleanup
    self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

async def _periodic_cleanup(self):
    """Periodic cleanup of expired actions"""
    while True:
        try:
            await asyncio.sleep(self._cleanup_interval)
            await self._cleanup_expired_actions()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}")

async def _cleanup_expired_actions(self):
    """Clean up actions that have exceeded timeout"""
    current_time = time.time()
    expired_actions = []
    
    for action_name, task in list(self._active_tasks.items()):
        # Check if task has been running too long
        if hasattr(task, '_start_time'):
            if current_time - task._start_time > self._action_timeout:
                expired_actions.append(action_name)
    
    for action_name in expired_actions:
        logger.warning(f"Cleaning up expired action: {action_name}")
        await self._force_cleanup_action(action_name)
```

This guide provides comprehensive patterns for developing handlers that support the contextual command system while maintaining high performance and reliability. Follow these patterns to ensure your handlers integrate seamlessly with the disambiguation system and provide a consistent user experience.
