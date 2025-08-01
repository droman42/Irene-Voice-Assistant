"""
Async Timer Plugin - Demonstrates new async timer system

Shows how to use the AsyncTimerManager for non-blocking timer operations,
replacing the old threading.Timer approach.
"""

import asyncio
import re
from typing import List, Optional

from ...core.context import Context
from ...core.commands import CommandResult
from ..base import BaseCommandPlugin


class AsyncTimerPlugin(BaseCommandPlugin):
    """
    Async timer plugin demonstrating the new timer system.
    
    Features:
    - Non-blocking async timers
    - Timer management and cancellation
    - Context-aware timer storage
    - Natural language time parsing
    """
    
    @property
    def name(self) -> str:
        return "async_timer"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Async timer functionality with natural language support"
        
    def __init__(self):
        super().__init__()
        self.add_trigger("timer")
        self.add_trigger("set timer")
        self.add_trigger("cancel timer")
        self.add_trigger("list timers")
        
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
            
    def _create_timer_callback(self, timer_name: str, context: Context):
        """Create async callback for timer expiration"""
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