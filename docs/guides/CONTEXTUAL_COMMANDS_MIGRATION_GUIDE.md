# Contextual Commands Migration Guide

## Overview

This guide helps developers migrate custom intent handlers to support the new contextual command disambiguation system introduced in Phase 4 of TODO16. The system provides intelligent resolution of ambiguous commands like "stop", "pause", "resume" across multiple active actions and domains.

## Table of Contents

1. [Migration Overview](#migration-overview)
2. [Breaking Changes](#breaking-changes)
3. [Step-by-Step Migration](#step-by-step-migration)
4. [Handler Implementation Patterns](#handler-implementation-patterns)
5. [Donation File Updates](#donation-file-updates)
6. [Performance Considerations](#performance-considerations)
7. [Testing Your Migration](#testing-your-migration)
8. [Troubleshooting](#troubleshooting)

## Migration Overview

### What Changed

**Before (Deprecated)**:
- Handlers implemented `parse_stop_command()` and `_handle_stop_command()`
- Each handler duplicated disambiguation logic
- Ambiguous commands were processed by individual handlers
- Stop-specific patterns hardcoded in handler code

**After (New System)**:
- Central disambiguation in `IntentOrchestrator`
- Handlers receive resolved domain-specific intents
- Contextual commands externalized to localization files
- Performance monitoring and caching support
- Cross-handler coordination for complex scenarios

### Benefits

- **Consistent Behavior**: Same disambiguation logic across all handlers
- **Performance**: Caching and monitoring with <5ms latency targets
- **Maintainability**: No duplicated disambiguation code
- **Extensibility**: Easy to add new contextual commands
- **Internationalization**: Localized command patterns

## Breaking Changes

### Removed Methods

The following methods are **deprecated and removed**:

```python
# ❌ REMOVED - Do not implement these methods
class MyHandler(IntentHandler):
    def parse_stop_command(self, intent: Intent) -> Optional[Dict[str, Any]]:
        # This method is no longer called
        pass
    
    async def _handle_stop_command(self, stop_info: dict, context: ConversationContext):
        # This method is no longer called
        pass
```

### Changed Intent Flow

**Before**:
```
User: "stop" → Handler.parse_stop_command() → Handler._handle_stop_command()
```

**After**:
```
User: "stop" → NLU: contextual.stop → Orchestrator: disambiguation → Handler: domain.stop
```

### Required Changes

1. **Remove deprecated methods** from your handlers
2. **Implement domain-specific methods** for contextual commands
3. **Update donation files** with contextual command patterns
4. **Configure domain priorities** in your handler's donation file

## Step-by-Step Migration

### Step 1: Remove Deprecated Methods

Remove these methods from your handler class:

```python
class MyCustomHandler(IntentHandler):
    # ❌ Remove these methods
    # def parse_stop_command(self, intent: Intent) -> Optional[Dict[str, Any]]:
    # async def _handle_stop_command(self, stop_info: dict, context: ConversationContext):
    pass
```

### Step 2: Implement Domain-Specific Methods

Add methods for each contextual command your handler supports:

```python
class MyCustomHandler(IntentHandler):
    
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Main execution method with domain-specific routing"""
        
        # Route to appropriate method based on intent action
        if intent.action == "stop":
            return await self._handle_stop_action(intent, context)
        elif intent.action == "pause":
            return await self._handle_pause_action(intent, context)
        elif intent.action == "resume":
            return await self._handle_resume_action(intent, context)
        elif intent.action == "cancel":
            return await self._handle_cancel_action(intent, context)
        else:
            # Handle other domain-specific intents
            return await self._handle_other_actions(intent, context)
    
    async def _handle_stop_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle domain-specific stop command"""
        try:
            # Your handler receives a resolved intent like "my_domain.stop"
            # No need to parse or disambiguate - just execute the stop action
            
            # Example: Stop all active actions for this domain
            active_actions = context.active_actions
            stopped_actions = []
            
            for action_name, action_info in active_actions.items():
                if action_info.get('domain') == 'my_domain':
                    # Stop the specific action
                    await self._stop_specific_action(action_name, action_info)
                    stopped_actions.append(action_name)
                    
                    # Remove from active actions
                    context.remove_completed_action(action_name)
            
            if stopped_actions:
                response = f"Stopped {len(stopped_actions)} action(s): {', '.join(stopped_actions)}"
                return IntentResult(
                    success=True,
                    response=response,
                    intent_name=intent.name,
                    handler_name=self.__class__.__name__
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
    
    async def _handle_pause_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle domain-specific pause command"""
        # Similar pattern for pause functionality
        pass
    
    async def _handle_resume_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle domain-specific resume command"""
        # Similar pattern for resume functionality
        pass
    
    async def _stop_specific_action(self, action_name: str, action_info: Dict[str, Any]) -> None:
        """Stop a specific action (implement your domain logic here)"""
        # Example implementation
        if hasattr(self, '_active_tasks') and action_name in self._active_tasks:
            task = self._active_tasks[action_name]
            if not task.done():
                task.cancel()
            del self._active_tasks[action_name]
```

### Step 3: Update Donation Files

Update your handler's donation files to include contextual command patterns:

```json
{
  "handler_name": "my_custom_handler",
  "display_name": "My Custom Handler",
  "description": "Handles custom domain actions",
  "domain": "my_domain",
  
  "action_domain_priority": 80,
  
  "contextual_commands": {
    "stop": {
      "patterns": ["stop", "halt", "end"],
      "description": "Stop all active custom actions"
    },
    "pause": {
      "patterns": ["pause", "hold", "suspend"],
      "description": "Pause active custom actions"
    },
    "resume": {
      "patterns": ["resume", "continue", "restart"],
      "description": "Resume paused custom actions"
    },
    "cancel": {
      "patterns": ["cancel", "abort", "terminate"],
      "description": "Cancel and remove custom actions"
    }
  },
  
  "intents": {
    "my_domain.stop": {
      "description": "Stop custom domain actions",
      "parameters": []
    },
    "my_domain.pause": {
      "description": "Pause custom domain actions", 
      "parameters": []
    },
    "my_domain.resume": {
      "description": "Resume custom domain actions",
      "parameters": []
    }
  }
}
```

### Step 4: Configure Domain Priority

Set your handler's priority in the donation file:

```json
{
  "action_domain_priority": 75,
}
```

**Priority Guidelines**:
- **90-100**: Critical system functions (audio playback, emergency stops)
- **70-89**: Important user actions (timers, alarms, primary tasks)
- **50-69**: Secondary functions (voice synthesis, notifications)
- **30-49**: Background tasks (system monitoring, logging)
- **10-29**: Low priority tasks (cleanup, maintenance)

### Step 5: Update Localization Files

Add your contextual commands to localization files:

```yaml
# assets/localization/commands/en.yaml
contextual_commands:
  my_domain:
    stop: ["stop my task", "end custom action", "halt my process"]
    pause: ["pause my task", "hold custom action"]
    resume: ["resume my task", "continue custom action"]
    cancel: ["cancel my task", "abort custom action"]

# assets/localization/commands/ru.yaml  
contextual_commands:
  my_domain:
    stop: ["останови мою задачу", "завершить действие", "прекрати процесс"]
    pause: ["приостанови задачу", "задержи действие"]
    resume: ["продолжи задачу", "возобнови действие"]
    cancel: ["отмени задачу", "прерви действие"]
```

## Handler Implementation Patterns

### Pattern 1: Simple Action Management

For handlers with simple fire-and-forget actions:

```python
class SimpleHandler(IntentHandler):
    
    def __init__(self):
        super().__init__()
        self._active_tasks: Dict[str, asyncio.Task] = {}
    
    async def _handle_stop_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Stop all active tasks"""
        stopped_count = 0
        
        for task_name, task in list(self._active_tasks.items()):
            if not task.done():
                task.cancel()
                stopped_count += 1
            del self._active_tasks[task_name]
            context.remove_completed_action(task_name)
        
        return IntentResult(
            success=True,
            response=f"Stopped {stopped_count} task(s)",
            intent_name=intent.name
        )
```

### Pattern 2: Stateful Action Management

For handlers with complex state management:

```python
class StatefulHandler(IntentHandler):
    
    def __init__(self):
        super().__init__()
        self._action_states: Dict[str, Dict[str, Any]] = {}
    
    async def _handle_pause_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Pause active actions while preserving state"""
        paused_actions = []
        
        for action_name, action_info in context.active_actions.items():
            if action_info.get('domain') == self.domain:
                # Save current state
                current_state = await self._get_action_state(action_name)
                self._action_states[action_name] = current_state
                
                # Pause the action
                await self._pause_action(action_name)
                paused_actions.append(action_name)
        
        return IntentResult(
            success=len(paused_actions) > 0,
            response=f"Paused {len(paused_actions)} action(s)",
            intent_name=intent.name
        )
    
    async def _handle_resume_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Resume paused actions from saved state"""
        resumed_actions = []
        
        for action_name, saved_state in self._action_states.items():
            await self._resume_action(action_name, saved_state)
            resumed_actions.append(action_name)
        
        self._action_states.clear()
        
        return IntentResult(
            success=len(resumed_actions) > 0,
            response=f"Resumed {len(resumed_actions)} action(s)",
            intent_name=intent.name
        )
```

### Pattern 3: Resource Management

For handlers managing external resources:

```python
class ResourceHandler(IntentHandler):
    
    async def _handle_stop_action(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Stop actions and clean up resources"""
        try:
            # Stop active processes
            stopped_actions = []
            for action_name, action_info in context.active_actions.items():
                if action_info.get('domain') == self.domain:
                    # Clean up resources
                    await self._cleanup_action_resources(action_name, action_info)
                    stopped_actions.append(action_name)
                    context.remove_completed_action(action_name)
            
            # Additional cleanup
            await self._cleanup_shared_resources()
            
            return IntentResult(
                success=True,
                response=f"Stopped and cleaned up {len(stopped_actions)} action(s)",
                intent_name=intent.name
            )
            
        except Exception as e:
            logger.error(f"Error during resource cleanup: {e}")
            return IntentResult(
                success=False,
                response="Failed to stop actions cleanly",
                intent_name=intent.name,
                error=str(e)
            )
    
    async def _cleanup_action_resources(self, action_name: str, action_info: Dict[str, Any]) -> None:
        """Clean up resources for a specific action"""
        # Close files, network connections, etc.
        pass
    
    async def _cleanup_shared_resources(self) -> None:
        """Clean up shared resources"""
        # Clean up shared state, connections, etc.
        pass
```

## Performance Considerations

### Caching

The system automatically caches domain priorities and command patterns. No handler changes needed, but be aware:

- Domain priorities are cached for 5 minutes by default
- Command patterns are cached per language
- Cache size limits prevent memory issues

### Latency Targets

- **Single action**: <2ms average
- **Multi-domain**: <4ms average  
- **Complex scenarios**: <5ms average
- **Concurrent load**: <15ms average

### Best Practices

1. **Keep action state minimal** - Store only essential information in `context.active_actions`
2. **Use async/await properly** - Don't block the event loop
3. **Handle cancellation gracefully** - Check for cancellation in long-running operations
4. **Clean up resources** - Always clean up in stop/cancel handlers
5. **Log performance issues** - Use structured logging for debugging

## Testing Your Migration

### Unit Tests

Test your handler's contextual command methods:

```python
import pytest
from irene.intents.models import Intent, ConversationContext

class TestMyHandlerMigration:
    
    @pytest.mark.asyncio
    async def test_stop_action(self):
        """Test stop action handling"""
        handler = MyCustomHandler()
        
        # Create resolved intent (what handler receives)
        intent = Intent(
            name="my_domain.stop",
            domain="my_domain",
            action="stop",
            text="stop my task",
            confidence=0.9
        )
        
        context = ConversationContext(session_id="test", client_id="test", language="en")
        context.active_actions = {
            "test_action": {
                "domain": "my_domain",
                "action": "test_task",
                "started_at": time.time()
            }
        }
        
        result = await handler._handle_stop_action(intent, context)
        
        assert result.success is True
        assert "stopped" in result.response.lower()
        assert len(context.active_actions) == 0  # Should be removed
```

### Integration Tests

Test with the full orchestrator:

```python
@pytest.mark.asyncio
async def test_contextual_command_integration(self):
    """Test full contextual command flow"""
    # Set up orchestrator with your handler
    registry = IntentRegistry()
    registry.register_handler("my_domain", MyCustomHandler())
    
    orchestrator = IntentOrchestrator(
        registry=registry,
        context_manager=ContextManager(),
        domain_priorities={"my_domain": 75}
    )
    
    # Create contextual intent (what NLU produces)
    contextual_intent = Intent(
        name="contextual.stop",
        domain="contextual", 
        action="stop",
        text="stop",
        confidence=0.9
    )
    
    context = ConversationContext(session_id="test", client_id="test", language="en")
    context.active_actions = {
        "my_action": {
            "domain": "my_domain",
            "action": "my_task",
            "started_at": time.time()
        }
    }
    
    # Execute through orchestrator
    result = await orchestrator.execute_intent(contextual_intent, context)
    
    assert result.success is True
```

### Performance Tests

Verify your handler meets performance requirements:

```python
@pytest.mark.asyncio
async def test_handler_performance(self):
    """Test handler performance under load"""
    handler = MyCustomHandler()
    
    # Create many active actions
    context = ConversationContext(session_id="perf_test", client_id="test", language="en")
    for i in range(10):
        context.active_actions[f"action_{i}"] = {
            "domain": "my_domain",
            "action": f"task_{i}",
            "started_at": time.time()
        }
    
    intent = Intent(
        name="my_domain.stop",
        domain="my_domain",
        action="stop",
        text="stop all",
        confidence=0.9
    )
    
    # Measure performance
    start_time = time.perf_counter()
    result = await handler._handle_stop_action(intent, context)
    end_time = time.perf_counter()
    
    latency_ms = (end_time - start_time) * 1000
    
    assert result.success is True
    assert latency_ms < 10.0  # Should complete within 10ms
```

## Troubleshooting

### Common Issues

#### 1. Handler Not Receiving Contextual Commands

**Problem**: Your handler's contextual methods are never called.

**Solution**: 
- Verify your handler is registered with the correct domain
- Check that `contextual_commands` are defined in your donation file
- Ensure domain priorities are configured

#### 2. Disambiguation Always Targets Other Handlers

**Problem**: Contextual commands always resolve to other domains.

**Solution**:
- Increase your handler's `action_domain_priority` 
- Verify your handler supports the contextual command type
- Check that you have active actions in `context.active_actions`

#### 3. Performance Issues

**Problem**: Contextual commands are slow or timeout.

**Solution**:
- Optimize your stop/pause/resume methods
- Use async/await properly
- Avoid blocking operations
- Check for resource leaks

#### 4. Active Actions Not Updated

**Problem**: Stopped actions remain in `context.active_actions`.

**Solution**:
- Call `context.remove_completed_action(action_name)` after stopping
- Update action state properly in pause/resume handlers
- Verify action names match exactly

### Debug Logging

Enable debug logging to troubleshoot issues:

```python
import logging

# Enable contextual command debugging
logging.getLogger("irene.intents.orchestrator").setLevel(logging.DEBUG)
logging.getLogger("irene.intents.context").setLevel(logging.DEBUG)
logging.getLogger("irene.intents.performance").setLevel(logging.DEBUG)
```

### Configuration Validation

Validate your configuration:

```python
from irene.config.models import ContextualCommandsConfig

# Test your configuration
config = ContextualCommandsConfig(
    enable_pattern_caching=True,
    cache_ttl_seconds=300,
    max_cache_size_patterns=1000,
    performance_monitoring=True,
    latency_threshold_ms=5.0
)

print(f"Configuration valid: {config}")
```

## Migration Checklist

- [ ] Remove `parse_stop_command()` method
- [ ] Remove `_handle_stop_command()` method  
- [ ] Implement `_handle_stop_action()` method
- [ ] Implement `_handle_pause_action()` method (if supported)
- [ ] Implement `_handle_resume_action()` method (if supported)
- [ ] Implement `_handle_cancel_action()` method (if supported)
- [ ] Update donation file with `contextual_commands` section
- [ ] Set `action_domain_priority` in donation file
- [ ] Add localization patterns for your commands
- [ ] Update handler's `execute()` method to route contextual commands
- [ ] Ensure proper cleanup in stop/cancel handlers
- [ ] Update `context.active_actions` when actions complete
- [ ] Write unit tests for contextual command methods
- [ ] Write integration tests with orchestrator
- [ ] Verify performance meets <5ms requirement
- [ ] Test with multiple active actions
- [ ] Test priority resolution with other handlers
- [ ] Update handler documentation

## Support

For additional help with migration:

1. Check the [Handler Development Guide](HANDLER_DEVELOPMENT_GUIDE.md)
2. Review existing handler implementations in `irene/intents/handlers/`
3. Run the Phase 4 test suite: `python -m pytest irene/tests/test_phase4_*.py`
4. Enable debug logging for detailed troubleshooting

The contextual command system is designed to be backward compatible during the migration period, but deprecated methods will be removed in future versions. Complete your migration as soon as possible to take advantage of the improved performance and consistency.
