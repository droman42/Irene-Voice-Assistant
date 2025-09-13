"""
Developer Tools and Debugging - Phase 3.4 Implementation

Provides debugging tools and action inspection for fire-and-forget actions.
"""

import asyncio
import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class InspectionLevel(Enum):
    """Levels of detail for action inspection"""
    BASIC = "basic"
    DETAILED = "detailed"
    FULL = "full"


@dataclass
class ActionInspectionResult:
    """Result of action inspection"""
    
    session_id: str
    domain: str
    action_name: str
    inspection_level: InspectionLevel
    timestamp: float = field(default_factory=time.time)
    
    # Basic info
    status: str = "unknown"
    handler: str = "unknown"
    started_at: Optional[float] = None
    duration: Optional[float] = None
    
    # Detailed info
    task_info: Optional[Dict[str, Any]] = None
    retry_info: Optional[Dict[str, Any]] = None
    timeout_info: Optional[Dict[str, Any]] = None
    
    # Full info
    context_snapshot: Optional[Dict[str, Any]] = None
    system_state: Optional[Dict[str, Any]] = None
    error_details: Optional[Dict[str, Any]] = None


@dataclass
class TestActionConfig:
    """Configuration for test actions"""
    
    action_name: str
    domain: str
    duration: float = 1.0
    success_probability: float = 1.0
    error_message: Optional[str] = None
    timeout: Optional[float] = None
    max_retries: int = 0


class ActionDebugger:
    """Debugging and inspection tool for fire-and-forget actions"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ActionDebugger")
        
        # Component references
        self.context_manager = None
        self.metrics_collector = None
        
        # Debug state tracking
        self._inspection_history: List[ActionInspectionResult] = []
        self._test_actions: Dict[str, TestActionConfig] = {}
        
        # Debug configuration
        self._debug_enabled = True
        self._max_history_size = 1000
        
    def initialize(self, components: Dict[str, Any]) -> None:
        """Initialize debugger with system components"""
        self.context_manager = components.get('context_manager')
        self.metrics_collector = components.get('metrics_collector')
        
        self.logger.info("Action debugger initialized")
    
    async def inspect_active_action(self, session_id: str, domain: str, 
                                  level: InspectionLevel = InspectionLevel.BASIC) -> ActionInspectionResult:
        """Inspect a currently active action"""
        try:
            if not self.context_manager:
                raise RuntimeError("Context manager not available")
            
            # Get conversation context
            context = await self.context_manager.get_or_create_context(session_id)
            
            if domain not in context.active_actions:
                raise ValueError(f"No active action found in domain: {domain}")
            
            action_info = context.active_actions[domain]
            
            # Create inspection result
            result = ActionInspectionResult(
                session_id=session_id,
                domain=domain,
                action_name=action_info.get('action', 'unknown'),
                inspection_level=level,
                status=action_info.get('status', 'unknown'),
                handler=action_info.get('handler', 'unknown'),
                started_at=action_info.get('started_at')
            )
            
            # Calculate duration if action is running
            if result.started_at:
                result.duration = time.time() - result.started_at
            
            # Add detailed information based on inspection level
            if level in [InspectionLevel.DETAILED, InspectionLevel.FULL]:
                result.task_info = {
                    'task_id': action_info.get('task_id'),
                    'timeout': action_info.get('timeout'),
                    'timeout_at': action_info.get('timeout_at'),
                    'timeout_remaining': max(0, action_info.get('timeout_at', time.time()) - time.time())
                }
                
                result.retry_info = {
                    'max_retries': action_info.get('max_retries', 0),
                    'retry_count': action_info.get('retry_count', 0),
                    'retry_delay': action_info.get('retry_delay', 0)
                }
            
            if level == InspectionLevel.FULL:
                # Get full context snapshot
                result.context_snapshot = {
                    'conversation_history_count': len(context.conversation_history),
                    'recent_actions_count': len(context.recent_actions),
                    'failed_actions_count': len(context.failed_actions),
                    'memory_usage': context.get_memory_usage_estimate(),
                    'last_updated': context.last_updated
                }
                
                # Get system state if metrics collector is available
                if self.metrics_collector:
                    result.system_state = {
                        'system_metrics': self.metrics_collector.get_system_metrics(),
                        'active_actions_summary': self.metrics_collector.get_active_actions_summary(),
                        'domain_metrics': self.metrics_collector.get_domain_metrics(domain)
                    }
            
            # Add to inspection history
            self._inspection_history.append(result)
            if len(self._inspection_history) > self._max_history_size:
                self._inspection_history = self._inspection_history[-self._max_history_size:]
            
            self.logger.debug(f"Inspected action {domain}/{result.action_name} in session {session_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to inspect action {domain} in session {session_id}: {e}")
            # Return error result
            return ActionInspectionResult(
                session_id=session_id,
                domain=domain,
                action_name="error",
                inspection_level=level,
                error_details={"error": str(e), "traceback": traceback.format_exc()}
            )
    
    def create_test_action(self, config: TestActionConfig) -> str:
        """Create a test action configuration"""
        test_id = f"test_{config.domain}_{config.action_name}_{int(time.time())}"
        self._test_actions[test_id] = config
        
        self.logger.info(f"Created test action: {test_id}")
        return test_id
    
    async def execute_test_action(self, test_id: str, session_id: str) -> Dict[str, Any]:
        """Execute a test action for debugging purposes"""
        if test_id not in self._test_actions:
            return {"error": f"Test action {test_id} not found"}
        
        config = self._test_actions[test_id]
        
        try:
            # Create a mock action function
            async def mock_action():
                # Simulate work
                await asyncio.sleep(config.duration)
                
                # Simulate failure based on probability
                import random
                if random.random() > config.success_probability:
                    raise RuntimeError(config.error_message or "Simulated test failure")
                
                return f"Test action {config.action_name} completed successfully"
            
            # Record test execution start
            start_time = time.time()
            
            # Execute with timeout if specified
            if config.timeout:
                result = await asyncio.wait_for(mock_action(), timeout=config.timeout)
            else:
                result = await mock_action()
            
            duration = time.time() - start_time
            
            return {
                "success": True,
                "result": result,
                "duration": duration,
                "test_config": config.__dict__
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Test action timed out",
                "duration": config.timeout,
                "test_config": config.__dict__
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "success": False,
                "error": str(e),
                "duration": duration,
                "test_config": config.__dict__
            }
    
    def get_debugging_status(self) -> Dict[str, Any]:
        """Get current debugging system status"""
        return {
            "debug_enabled": self._debug_enabled,
            "inspection_history_size": len(self._inspection_history),
            "max_history_size": self._max_history_size,
            "active_test_actions": len(self._test_actions),
            "component_availability": {
                "context_manager": self.context_manager is not None,
                "metrics_collector": self.metrics_collector is not None
            }
        }


# Global debugger instance
_action_debugger: Optional[ActionDebugger] = None


def get_action_debugger() -> ActionDebugger:
    """Get the global action debugger instance"""
    global _action_debugger
    if _action_debugger is None:
        _action_debugger = ActionDebugger()
    return _action_debugger


def initialize_action_debugger(components: Dict[str, Any]) -> ActionDebugger:
    """Initialize the global action debugger"""
    debugger = get_action_debugger()
    debugger.initialize(components)
    return debugger
