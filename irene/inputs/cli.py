"""
CLI Input Source - Command line input

Provides command line interface for text-based interaction
with the voice assistant.
"""

import asyncio
import sys
from typing import AsyncIterator, Optional, List, Dict
import logging

from prompt_toolkit import prompt

from .base import InputSource, InputData

logger = logging.getLogger(__name__)


class CLIInput(InputSource):
    """
    Command-line input source for interactive text input.
    
    Provides a simple text-based interface for sending commands
    and receiving responses via the command line.
    """
    
    def __init__(self, prompt: str = "irene> "):
        super().__init__()
        self.prompt = prompt
        self._listening = False
        self._command_queue = asyncio.Queue()
        self._input_task: Optional[asyncio.Task] = None
        self._history = []  # Command history for enhanced input

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """CLI input needs prompt_toolkit for enhanced terminal features"""
        return ["prompt_toolkit>=3.0.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """CLI input has no system dependencies - pure Python"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """CLI input supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    async def listen(self) -> AsyncIterator[InputData]:
        """
        Listen for CLI commands and yield them as they arrive.
        
        Yields:
            Command strings as they are typed by the user
        """
        if not self._listening:
            return
            
        while self._listening:
            try:
                # Wait for commands from the input task
                command = await asyncio.wait_for(
                    self._command_queue.get(), timeout=1.0
                )
                if command and command.strip():
                    yield command.strip()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in CLI input: {e}")
                break
                
    async def start_listening(self) -> None:
        """Initialize and start CLI input"""
        self._listening = True
        self._input_task = asyncio.create_task(self._input_loop())
        print("CLI input started. Type commands or 'quit' to exit.")
        logger.info("CLI input listening started")
        
    async def stop_listening(self) -> None:
        """Stop CLI input and clean up"""
        self._listening = False
        if self._input_task:
            self._input_task.cancel()
            try:
                await self._input_task
            except asyncio.CancelledError:
                pass
        print("CLI input stopped.")
        logger.info("CLI input listening stopped")
        
    def is_listening(self) -> bool:
        """Check if currently listening for input"""
        return self._listening
        
    def is_available(self) -> bool:
        """CLI is always available"""
        return True
        
    def get_input_type(self) -> str:
        """Get input type identifier"""
        return "cli"
        
    async def _input_loop(self) -> None:
        """Background task to read CLI input with enhanced features"""
        while self._listening:
            try:
                # Use prompt_toolkit for enhanced input with cursor movement and history
                command = await asyncio.to_thread(
                    prompt,
                    self.prompt,
                    mouse_support=True,
                    enable_history_search=True
                )
                
                if command and command.strip():
                    # Add to history (avoid duplicates)
                    if not self._history or self._history[-1] != command.strip():
                        self._history.append(command.strip())
                        # Keep history size manageable
                        if len(self._history) > 100:
                            self._history.pop(0)
                    
                    # Handle quit command
                    if command.strip().lower() in ['quit', 'exit', 'q']:
                        await self._command_queue.put('quit')
                        break
                    await self._command_queue.put(command.strip())
            except (EOFError, KeyboardInterrupt):
                logger.info("CLI input interrupted by user")
                break
            except Exception as e:
                logger.error(f"CLI input error: {e}")
                await asyncio.sleep(0.1)
                
    async def test_input(self) -> bool:
        """Test CLI input functionality"""
        try:
            print("CLI input test - CLI is always available")
            return True
        except Exception as e:
            logger.error(f"CLI input test failed: {e}")
            return False


if __name__ == "__main__":
    print("⚠️  This module provides the CLIInput class for the Irene voice assistant.")
    print("To run the Irene CLI application, use:")
    print("  uv run python -m irene.runners.cli --help")
    print("  or check the project documentation for proper usage.") 