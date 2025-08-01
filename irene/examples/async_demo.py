"""
Async Demo - Complete working example of Irene v13

Demonstrates the new async architecture with:
- AsyncVACore engine
- Async plugin system
- Non-blocking operations
- Modern Python patterns
"""

import asyncio
import logging
from pathlib import Path

from ..core.engine import AsyncVACore
from ..config.models import CoreConfig, API_PROFILE
from ..inputs.cli import CLIInput
from ..outputs.text import TextOutput
from ..utils.logging import setup_logging


async def async_demo():
    """
    Complete demonstration of Irene v13 async architecture.
    
    Shows:
    - Async core initialization
    - Plugin loading and management
    - Command processing
    - Timer functionality
    - Background services
    - Context management
    """
    
    print("🚀 Irene Voice Assistant v13 - Async Architecture Demo")
    print("=" * 60)
    
    # Setup logging
    setup_logging(enable_console=True)
    logger = logging.getLogger("demo")
    
    # Create configuration
    config = CoreConfig(
        name="Irene Demo",
        debug=True,
        components=API_PROFILE  # Text-only mode for demo
    )
    
    # Initialize core engine
    core = AsyncVACore(config)
    
    try:
        print("📡 Starting Irene async core...")
        await core.start()
        
        # Set up input and output
        cli_input = CLIInput(prompt="irene-demo> ")
        text_output = TextOutput(prefix="🤖 ")
        
        await core.input_manager.add_source("cli", cli_input)
        await core.output_manager.add_target("text", text_output)
        await core.input_manager.start_source("cli")
        
        print("✅ Irene started successfully!")
        print()
        print("🎯 Try these commands to see async features:")
        print("• help - Show available commands")
        print("• status - Check system status")
        print("• timer 10 seconds demo timer - Set an async timer")
        print("• service status - Check background service")
        print("• ping - Test async responsiveness")
        print("• quit - Exit the demo")
        print()
        
        # Demo some async operations
        await demo_async_features(core)
        
        # Main command processing loop
        running = True
        while running:
            try:
                source_name, command = await core.input_manager.get_next_input()
                
                if command.lower() in ["quit", "exit"]:
                    print("👋 Shutting down demo...")
                    break
                    
                # Process command asynchronously
                await core.process_command(command)
                
            except KeyboardInterrupt:
                print("\n👋 Demo interrupted. Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in demo loop: {e}")
                
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Demo failed: {e}")
    finally:
        print("🔄 Cleaning up...")
        await core.stop()
        print("✅ Demo completed!")


async def demo_async_features(core: AsyncVACore):
    """Demonstrate key async features"""
    print("🔍 Demonstrating async features...")
    
    # Create a demo context
    context = core.context_manager.create_context(user_id="demo_user")
    
    # Demo 1: Concurrent command processing
    print("1️⃣  Testing concurrent command processing...")
    commands = ["version", "status", "ping"]
    
    # Process multiple commands concurrently
    results = await asyncio.gather(*[
        core.process_command(cmd, context) for cmd in commands
    ], return_exceptions=True)
    
    print("✅ Processed 3 commands concurrently!")
    
    # Demo 2: Async timer
    print("2️⃣  Setting up async timer...")
    await core.process_command("timer 5 seconds demo completed", context)
    
    # Demo 3: Check service status
    print("3️⃣  Checking background service...")
    await core.process_command("service status", context)
    
    print("🎉 Async features demo completed!")
    print()


async def run_performance_test():
    """Run a simple performance test to show async benefits"""
    print("⚡ Performance Test: Async vs Blocking Operations")
    print("-" * 50)
    
    # Simulate multiple async operations
    async def async_operation(delay: float, task_id: int):
        await asyncio.sleep(delay)
        return f"Task {task_id} completed in {delay}s"
    
    # Test concurrent execution
    start_time = asyncio.get_event_loop().time()
    
    tasks = [
        async_operation(0.1, 1),
        async_operation(0.2, 2), 
        async_operation(0.15, 3),
        async_operation(0.1, 4),
        async_operation(0.05, 5)
    ]
    
    results = await asyncio.gather(*tasks)
    
    total_time = asyncio.get_event_loop().time() - start_time
    
    print(f"✅ Completed 5 concurrent operations in {total_time:.3f}s")
    print("   (Sequential execution would take ~0.6s)")
    print("   🚀 Async speedup: ~3x faster!")
    print()


def main():
    """Main entry point for the demo"""
    try:
        # Run performance test first
        asyncio.run(run_performance_test())
        
        # Run main demo
        asyncio.run(async_demo())
        
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"❌ Demo error: {e}")


if __name__ == "__main__":
    main() 