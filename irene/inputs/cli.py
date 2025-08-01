"""
CLI Input Source - Command line input

Provides command line interface for text-based interaction
with the voice assistant.
"""

import asyncio
import sys
from typing import Optional

from .base import LegacyInputSource


class CLIInput(LegacyInputSource):
    """
    Command line input source.
    
    Provides a simple text-based interface for testing
    and headless operation.
    """
    
    def __init__(self, prompt: str = "irene> "):
        self.prompt = prompt
        self._running = False
        self._command_queue = asyncio.Queue()
        self._input_task: Optional[asyncio.Task] = None
        self.input_type = "cli"
        
    async def get_command(self) -> Optional[str]:
        """Get the next command (non-blocking)"""
        try:
            return await asyncio.wait_for(self._command_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None
            
    async def _input_loop(self) -> None:
        """Background task to read input"""
        while self._running:
            try:
                # Use asyncio to avoid blocking
                command = await asyncio.to_thread(input, self.prompt)
                if command.strip():
                    await self._command_queue.put(command.strip())
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                print(f"CLI input error: {e}")
                await asyncio.sleep(0.1)
                
    async def start(self) -> None:
        """Start CLI input"""
        self._running = True
        self._input_task = asyncio.create_task(self._input_loop())
        print("CLI input started. Type commands or 'quit' to exit.")
        
    async def stop(self) -> None:
        """Stop CLI input"""
        self._running = False
        if self._input_task:
            self._input_task.cancel()
            try:
                await self._input_task
            except asyncio.CancelledError:
                pass
        print("CLI input stopped.")
        
    def is_available(self) -> bool:
        """CLI is always available"""
        return True 