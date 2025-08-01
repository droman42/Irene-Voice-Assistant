"""
Async Service Demo Plugin - Background service demonstration

Shows how to create plugins that run background async services,
demonstrating the AsyncServicePlugin base class.
"""

import asyncio
from datetime import datetime
from typing import List

from ...core.context import Context
from ...core.commands import CommandResult
from ..base import AsyncServicePlugin, BaseCommandPlugin


class AsyncServiceDemoPlugin(AsyncServicePlugin, BaseCommandPlugin):
    """
    Demonstrates async background service functionality.
    
    Features:
    - Background async task execution
    - Periodic operations without blocking
    - Service lifecycle management
    - Resource cleanup
    """
    
    @property
    def name(self) -> str:
        return "async_service_demo"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Service demonstration with background tasks and lifecycle management"
        
    @property
    def dependencies(self) -> list[str]:
        """No dependencies for service demo"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """No optional dependencies for service demo"""
        return []
        
    # Additional metadata for PluginRegistry discovery
    @property
    def enabled_by_default(self) -> bool:
        """Service demo not enabled by default (demonstration only)"""
        return False
        
    @property  
    def category(self) -> str:
        """Plugin category"""
        return "service"
        
    @property
    def platforms(self) -> list[str]:
        """Supported platforms (empty = all platforms)"""
        return []
        
    def __init__(self):
        super().__init__()
        self._status_count = 0
        self._last_heartbeat = None
        self.add_trigger("service status")
        self.add_trigger("service stats")
        
    async def _service_loop(self) -> None:
        """Background service that runs periodic operations"""
        self.logger.info("Async service started")
        
        while self._running:
            try:
                # Simulate periodic background work
                await self._perform_background_task()
                
                # Wait before next iteration
                await asyncio.sleep(10)  # Run every 10 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in service loop: {e}")
                await asyncio.sleep(5)  # Wait before retry
                
        self.logger.info("Async service stopped")
        
    async def _perform_background_task(self) -> None:
        """Perform periodic background work"""
        self._status_count += 1
        self._last_heartbeat = datetime.now()
        
        # Log periodic heartbeat
        if self._status_count % 6 == 0:  # Every minute (6 * 10 seconds)
            self.logger.info(f"Service heartbeat #{self._status_count}")
            
    async def _handle_command_impl(self, command: str, context: Context) -> CommandResult:
        """Handle service-related commands"""
        command_lower = command.lower().strip()
        
        if command_lower == "service status":
            return await self._handle_service_status(context)
        elif command_lower == "service stats":
            return await self._handle_service_stats(context)
        else:
            return CommandResult.error_result("Unknown service command")
            
    async def _handle_service_status(self, context: Context) -> CommandResult:
        """Show service status"""
        status = "🟢 Running" if self.is_service_running else "🔴 Stopped"
        
        status_text = f"""
🔧 Async Service Status:
• Service: {status}
• Heartbeats: {self._status_count}
• Last heartbeat: {self._last_heartbeat.strftime('%H:%M:%S') if self._last_heartbeat else 'Never'}
• Uptime: {self._get_uptime()}
        """.strip()
        
        return CommandResult.success_result(status_text)
        
    async def _handle_service_stats(self, context: Context) -> CommandResult:
        """Show detailed service statistics"""
        # Simulate async data collection
        await asyncio.sleep(0.1)
        
        stats_text = f"""
📊 Service Statistics:
• Total heartbeats: {self._status_count}
• Service running: {self.is_service_running}
• Background tasks: {1 if self.is_service_running else 0}
• Memory efficient: ✅ (async implementation)
• Non-blocking: ✅ (doesn't block main thread)
• Resource usage: Minimal
        """.strip()
        
        return CommandResult.success_result(stats_text)
        
    def _get_uptime(self) -> str:
        """Get service uptime"""
        if not self._last_heartbeat:
            return "No heartbeats yet"
            
        # Calculate uptime based on heartbeat frequency
        uptime_seconds = self._status_count * 10  # 10 seconds per heartbeat
        
        if uptime_seconds < 60:
            return f"{uptime_seconds} seconds"
        elif uptime_seconds < 3600:
            minutes = uptime_seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = uptime_seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
            
    async def shutdown(self) -> None:
        """Enhanced shutdown with service-specific cleanup"""
        self.logger.info(f"Shutting down service (processed {self._status_count} heartbeats)")
        await super().shutdown() 