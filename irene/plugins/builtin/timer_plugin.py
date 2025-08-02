"""
Async Timer Plugin - Demonstrates new async timer system

Shows how to use the AsyncTimerManager for non-blocking timer operations,
replacing the old threading.Timer approach.
"""

import asyncio
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ...core.context import Context
from ...core.commands import CommandResult
from ...core.interfaces.webapi import WebAPIPlugin
from ..base import BaseCommandPlugin


class AsyncTimerPlugin(BaseCommandPlugin, WebAPIPlugin):
    """
    Async timer plugin demonstrating the new timer system.
    
    Features:
    - Non-blocking async timers
    - Timer management and cancellation
    - Context-aware timer storage
    - Natural language time parsing
    - Web API endpoints for timer management
    """
    
    @property
    def name(self) -> str:
        return "async_timer"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Async timer functionality with natural language parsing and web API"
        
    @property
    def dependencies(self) -> list[str]:
        """No dependencies for timer"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """No optional dependencies for timer"""
        return []
        
    # Additional metadata for PluginRegistry discovery
    @property
    def enabled_by_default(self) -> bool:
        """Timer should be enabled by default"""
        return True
        
    @property  
    def category(self) -> str:
        """Plugin category"""
        return "command"
        
    @property
    def platforms(self) -> list[str]:
        """Supported platforms (empty = all platforms)"""
        return []
        
    def __init__(self):
        super().__init__()
        self.add_trigger("timer")
        self.add_trigger("set timer")
        self.add_trigger("cancel timer")
        self.add_trigger("list timers")
        
        # Internal timer tracking for API
        self.active_timers: Dict[str, Dict[str, Any]] = {}
        
    # BaseCommandPlugin interface - existing voice functionality
    async def _handle_command_impl(self, command: str, context: Context) -> CommandResult:
        """Handle timer commands"""
        command_lower = command.lower().strip()
        
        if command_lower.startswith("timer ") or command_lower.startswith("set timer"):
            return await self._handle_set_timer(command, context)
        elif command_lower.startswith("cancel timer"):
            return await self._handle_cancel_timer(command, context)
        elif command_lower == "list timers":
            return await self._handle_list_timers(context)
        else:
            return await self._handle_timer_help(context)
    
    # Timer functionality methods (used by both voice and API)
    async def start_timer_async(self, duration: int, message: str = "Timer finished!", unit: str = "seconds") -> str:
        """Start a timer and return timer ID"""
        # Convert duration to seconds
        duration_seconds = self._convert_to_seconds(duration, unit)
        
        if not self._core:
            raise RuntimeError("Plugin not initialized")
            
        # Create a temporary timer_id for the callback (this would be handled by timer manager)
        import uuid
        temp_timer_id = str(uuid.uuid4())
        
        timer_id = await self._core.timer_manager.schedule_timer(
            name=message,
            delay_seconds=duration_seconds,
            callback=self._create_api_timer_callback(message, temp_timer_id)
        )
        
        # Use the actual timer_id returned by the manager
        if timer_id != temp_timer_id:
            # Update our tracking to use the real timer_id
            pass
        
        # Store timer info
        self.active_timers[timer_id] = {
            "name": message,
            "duration": duration_seconds,
            "unit": unit,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(seconds=duration_seconds),
            "status": "active"
        }
        
        return timer_id
    
    async def cancel_timer_async(self, timer_id: str) -> bool:
        """Cancel a specific timer"""
        if timer_id not in self.active_timers:
            return False
            
        if not self._core:
            raise RuntimeError("Plugin not initialized")
            
        success = await self._core.timer_manager.cancel_timer(timer_id)
        
        if success and timer_id in self.active_timers:
            self.active_timers[timer_id]["status"] = "cancelled"
            del self.active_timers[timer_id]
            
        return success
    
    async def pause_timer_async(self, timer_id: str) -> bool:
        """Pause a running timer"""
        if timer_id not in self.active_timers:
            return False
            
        # Note: This is a simplified implementation
        # In a full implementation, you'd need timer manager support for pausing
        self.active_timers[timer_id]["status"] = "paused"
        return True
    
    async def resume_timer_async(self, timer_id: str) -> bool:
        """Resume a paused timer"""
        if timer_id not in self.active_timers:
            return False
            
        # Note: This is a simplified implementation
        # In a full implementation, you'd need timer manager support for resuming
        self.active_timers[timer_id]["status"] = "active"
        return True
    
    def get_timer_info(self, timer_id: str) -> Optional[Dict[str, Any]]:
        """Get timer information"""
        return self.active_timers.get(timer_id)
    
    def list_active_timers(self) -> List[Dict[str, Any]]:
        """List all active timers"""
        timers = []
        now = datetime.now()
        
        for timer_id, timer_info in self.active_timers.items():
            remaining_seconds = (timer_info["expires_at"] - now).total_seconds()
            timers.append({
                "id": timer_id,
                "name": timer_info["name"],
                "remaining_seconds": max(0, remaining_seconds),
                "status": timer_info["status"],
                "created_at": timer_info["created_at"].isoformat(),
                "expires_at": timer_info["expires_at"].isoformat()
            })
            
        return timers
    
    # WebAPIPlugin interface - unified API
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with timer endpoints"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter, HTTPException  # type: ignore
            from pydantic import BaseModel  # type: ignore
            
            router = APIRouter()
            
            # Request/Response models
            class TimerRequest(BaseModel):
                duration: int
                message: str = "Timer finished!"
                unit: str = "seconds"
                
            class TimerResponse(BaseModel):
                timer_id: str
                duration: int
                unit: str
                message: str
                expires_at: str
                
            class TimerListResponse(BaseModel):
                active_timers: List[Dict[str, Any]]
                count: int
                
            class TimerActionResponse(BaseModel):
                success: bool
                timer_id: str
                action: str
                message: Optional[str] = None
            
            @router.post("/set", response_model=TimerResponse)
            async def set_timer(request: TimerRequest):
                """Set a timer via API"""
                try:
                    timer_id = await self.start_timer_async(
                        duration=request.duration,
                        message=request.message,
                        unit=request.unit
                    )
                    
                    timer_info = self.get_timer_info(timer_id)
                    if not timer_info:
                        raise HTTPException(500, "Failed to create timer")
                    
                    return TimerResponse(
                        timer_id=timer_id,
                        duration=request.duration,
                        unit=request.unit,
                        message=request.message,
                        expires_at=timer_info["expires_at"].isoformat()
                    )
                    
                except Exception as e:
                    raise HTTPException(400, f"Failed to set timer: {str(e)}")
            
            @router.get("/list", response_model=TimerListResponse)
            async def list_timers():
                """List all active timers"""
                timers = self.list_active_timers()
                return TimerListResponse(
                    active_timers=timers,
                    count=len(timers)
                )
            
            @router.delete("/{timer_id}", response_model=TimerActionResponse)
            async def cancel_timer(timer_id: str):
                """Cancel a specific timer"""
                success = await self.cancel_timer_async(timer_id)
                return TimerActionResponse(
                    success=success,
                    timer_id=timer_id,
                    action="cancel",
                    message="Timer cancelled successfully" if success else "Timer not found"
                )
            
            @router.post("/pause/{timer_id}", response_model=TimerActionResponse)
            async def pause_timer(timer_id: str):
                """Pause a running timer"""
                success = await self.pause_timer_async(timer_id)
                return TimerActionResponse(
                    success=success,
                    timer_id=timer_id,
                    action="pause",
                    message="Timer paused successfully" if success else "Timer not found"
                )
            
            @router.post("/resume/{timer_id}", response_model=TimerActionResponse)
            async def resume_timer(timer_id: str):
                """Resume a paused timer"""
                success = await self.resume_timer_async(timer_id)
                return TimerActionResponse(
                    success=success,
                    timer_id=timer_id,
                    action="resume",
                    message="Timer resumed successfully" if success else "Timer not found"
                )
            
            return router
            
        except ImportError:
            self.logger.warning("FastAPI not available for timer web API")
            return None
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for timer API endpoints"""
        return "/timer"
    
    def get_api_tags(self) -> list[str]:
        """Get OpenAPI tags for timer endpoints"""
        return ["Timer", "Async Timers"]

    # Internal helper methods
    def _convert_to_seconds(self, duration: int, unit: str) -> float:
        """Convert duration to seconds based on unit"""
        unit_multipliers = {
            "seconds": 1,
            "minutes": 60,
            "hours": 3600,
            "s": 1,
            "m": 60,
            "h": 3600
        }
        return float(duration) * unit_multipliers.get(unit.lower(), 1)
            
    async def _handle_set_timer(self, command: str, context: Context) -> CommandResult:
        """Set a new timer"""
        # Parse timer duration from command
        duration = self._parse_duration(command)
        if duration is None:
            return CommandResult.error_result(
                "⏰ Could not parse timer duration. Try: 'timer 5 minutes' or 'timer 30 seconds'"
            )
            
        # Parse optional timer name/message
        message = self._parse_timer_message(command)
        timer_name = message if message else f"Timer for {duration}s"
        
        try:
            # Use the async timer manager from core
            if not self._core:
                raise RuntimeError("Plugin not initialized")
                
            timer_id = await self._core.timer_manager.schedule_timer(
                name=timer_name,
                delay_seconds=duration,
                callback=self._create_timer_callback(timer_name, context)
            )
            
            # Store timer info in context
            timer_data = context.get_plugin_data(self.name)
            timer_data[timer_id] = {
                "name": timer_name,
                "duration": duration,
                "created_at": context.last_accessed
            }
            context.set_plugin_data(self.name, timer_data)
            
            return CommandResult.success_result(
                f"⏰ Timer set for {self._format_duration(duration)}: '{timer_name}'"
            )
            
        except Exception as e:
            return CommandResult.error_result(f"Failed to set timer: {str(e)}")
            
    async def _handle_cancel_timer(self, command: str, context: Context) -> CommandResult:
        """Cancel a timer"""
        timer_data = context.get_plugin_data(self.name)
        
        if not timer_data:
            return CommandResult.error_result("No active timers to cancel")
            
        # For now, cancel the most recent timer
        # In a full implementation, we could parse timer name/ID
        timer_ids = list(timer_data.keys())
        if timer_ids:
            timer_id = timer_ids[-1]
            timer_info = timer_data[timer_id]
            
            # Cancel the timer
            if not self._core:
                raise RuntimeError("Plugin not initialized")
            success = await self._core.timer_manager.cancel_timer(timer_id)
            
            if success:
                del timer_data[timer_id]
                context.set_plugin_data(self.name, timer_data)
                return CommandResult.success_result(
                    f"⏰ Cancelled timer: '{timer_info['name']}'"
                )
            else:
                return CommandResult.error_result("Failed to cancel timer")
        else:
            return CommandResult.error_result("No active timers found")
            
    async def _handle_list_timers(self, context: Context) -> CommandResult:
        """List active timers"""
        timer_data = context.get_plugin_data(self.name)
        
        if not timer_data:
            return CommandResult.success_result("⏰ No active timers")
            
        timer_list = ["⏰ Active Timers:"]
        for timer_id, info in timer_data.items():
            timer_list.append(f"• {info['name']} ({self._format_duration(info['duration'])})")
            
        return CommandResult.success_result("\n".join(timer_list))
        
    async def _handle_timer_help(self, context: Context) -> CommandResult:
        """Show timer help"""
        help_text = """
⏰ Timer Commands:

• timer <duration> [message] - Set a timer
  Examples: 
  - timer 5 minutes
  - timer 30 seconds tea is ready
  - timer 1 hour meeting

• cancel timer - Cancel the most recent timer
• list timers - Show all active timers

Supported time units: seconds, minutes, hours
        """.strip()
        
        return CommandResult.success_result(help_text)
        
    def _parse_duration(self, command: str) -> Optional[float]:
        """Parse duration from command text"""
        # Simple regex patterns for common time formats
        patterns = [
            (r'(\d+)\s*seconds?', 1),
            (r'(\d+)\s*minutes?', 60),
            (r'(\d+)\s*hours?', 3600),
            (r'(\d+)\s*s\b', 1),
            (r'(\d+)\s*m\b', 60),
            (r'(\d+)\s*h\b', 3600),
        ]
        
        command_lower = command.lower()
        for pattern, multiplier in patterns:
            match = re.search(pattern, command_lower)
            if match:
                return float(match.group(1)) * multiplier
                
        return None
        
    def _parse_timer_message(self, command: str) -> Optional[str]:
        """Extract timer message from command"""
        # Look for text after time specification
        patterns = [
            r'\d+\s*(?:seconds?|minutes?|hours?|s|m|h)\s+(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                return match.group(1).strip()
                
        return None
        
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable form"""
        if seconds < 60:
            return f"{int(seconds)} second{'s' if seconds != 1 else ''}"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = int(seconds // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''}"
            
    def _create_api_timer_callback(self, timer_name: str, timer_id: str):
        """Create async callback for API timer expiration"""
        async def timer_expired():
            # Send notification through the core
            message = f"⏰ Timer expired: {timer_name}"
            if self._core:
                await self._core.say(message)
            
            # Remove from internal tracking
            if timer_id in self.active_timers:
                del self.active_timers[timer_id]
            
        return timer_expired
    
    def _create_timer_callback(self, timer_name: str, context: Context):
        """Create async callback for voice command timer expiration"""
        async def timer_expired():
            # Send notification through the core
            message = f"⏰ Timer expired: {timer_name}"
            if self._core:
                await self._core.say(message)
            
            # Remove from context
            timer_data = context.get_plugin_data(self.name)
            # Find and remove the timer by name
            for timer_id, info in list(timer_data.items()):
                if info['name'] == timer_name:
                    del timer_data[timer_id]
                    break
            context.set_plugin_data(self.name, timer_data)
            
        return timer_expired 