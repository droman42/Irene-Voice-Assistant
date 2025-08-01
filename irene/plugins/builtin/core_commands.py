"""
Core Commands Plugin - Essential system commands

Demonstrates the new async plugin architecture with basic system commands
like help, status, version, etc.
"""

import asyncio
import time
from datetime import datetime
from typing import List

from ...core.context import Context
from ...core.commands import CommandResult
from ..base import BaseCommandPlugin


class CoreCommandsPlugin(BaseCommandPlugin):
    """
    Core system commands for Irene.
    
    Provides essential commands for system control and information.
    """
    
    # Plugin metadata for PluginRegistry discovery
    _enabled_by_default = True
    _category = "command"
    _platforms = []  # All platforms
    
    @property
    def name(self) -> str:
        return "core_commands"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Essential system commands (help, status, version, etc.)"
        
    @property
    def dependencies(self) -> list[str]:
        """No dependencies for core commands"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """No optional dependencies for core commands"""
        return []
        
    # Additional metadata for PluginRegistry discovery
    @property
    def enabled_by_default(self) -> bool:
        """Core commands should always be enabled by default"""
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
        # Register our command triggers
        self.add_trigger("help")
        self.add_trigger("status")
        self.add_trigger("version")
        self.add_trigger("info")
        self.add_trigger("ping")
        self.add_trigger("uptime")
        
    async def _handle_command_impl(self, command: str, context: Context) -> CommandResult:
        """Handle core commands"""
        command_lower = command.lower().strip()
        
        if command_lower == "help":
            return await self._handle_help(context)
        elif command_lower == "status":
            return await self._handle_status(context)
        elif command_lower == "version":
            return await self._handle_version(context)
        elif command_lower == "info":
            return await self._handle_info(context)
        elif command_lower == "ping":
            return await self._handle_ping(context)
        elif command_lower == "uptime":
            return await self._handle_uptime(context)
        else:
            return CommandResult.error_result("Unknown core command")
            
    async def _handle_help(self, context: Context) -> CommandResult:
        """Show available commands"""
        # Simulate async operation
        await asyncio.sleep(0.1)
        
        help_text = """
🤖 Irene Voice Assistant v13 - Available Commands:

Core Commands:
• help - Show this help message
• status - Show system status
• version - Show version information
• info - Show session information
• ping - Test system responsiveness
• uptime - Show system uptime

Basic Commands:
• привет - Greeting responses
• время - Current time
• дата - Current date
• подбрось монетку - Coin flip
• брось кубик - Dice roll
• таймер 30 секунд - Set timer

Type any command to get started!
        """.strip()
        
        return CommandResult.success_result(help_text)
        
    async def _handle_status(self, context: Context) -> CommandResult:
        """Show system status"""
        # Simulate async status check
        await asyncio.sleep(0.05)
        
        status_text = f"""
📊 System Status:
• Session ID: {context.session_id[:8]}...
• Session created: {context.created_at.strftime('%Y-%m-%d %H:%M:%S')}
• Last accessed: {context.last_accessed.strftime('%H:%M:%S')}
• Commands processed: {len(context.previous_commands)}
• Context active: ✅
• System status: 🟢 Operational
        """.strip()
        
        return CommandResult.success_result(status_text)
        
    async def _handle_version(self, context: Context) -> CommandResult:
        """Show version information"""
        version_text = """
🔧 Irene Voice Assistant v13.0.0-dev
• Architecture: Async/Await
• Python: 3.11+
• Mode: Development
• Features: Modern async architecture, optional components
        """.strip()
        
        return CommandResult.success_result(version_text)
        
    async def _handle_info(self, context: Context) -> CommandResult:
        """Show session information"""
        info_text = f"""
ℹ️  Session Information:
• Session ID: {context.session_id}
• User ID: {context.user_id or 'Anonymous'}
• Created: {context.created_at.strftime('%Y-%m-%d %H:%M:%S')}
• Commands in history: {len(context.previous_commands)}
• Conversation interactions: {len(context.conversation_history)}
• Plugin data keys: {len(context.plugin_data)}
        """.strip()
        
        return CommandResult.success_result(info_text)
        
    async def _handle_ping(self, context: Context) -> CommandResult:
        """Test system responsiveness"""
        # Measure async response time
        start_time = time.time()
        await asyncio.sleep(0.01)  # Simulate minimal processing
        response_time = (time.time() - start_time) * 1000
        
        ping_text = f"🏓 Pong! Response time: {response_time:.2f}ms"
        return CommandResult.success_result(ping_text)
        
    async def _handle_uptime(self, context: Context) -> CommandResult:
        """Show system uptime"""
        uptime = datetime.now() - context.created_at
        
        uptime_text = f"⏰ Session uptime: {str(uptime).split('.')[0]}"
        return CommandResult.success_result(uptime_text) 