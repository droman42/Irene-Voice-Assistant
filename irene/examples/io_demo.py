#!/usr/bin/env python3
"""
Input/Output System Demo

Demonstrates the modern I/O architecture with:
- Modern CLIInput (AsyncIterator interface)
- Modern TextOutput (Response-based interface)
- TTSOutput integration with pyttsx3
- InputManager and OutputManager coordination
"""

import asyncio
import logging
from typing import Dict, Any

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_text_output():
    """Test the modern TextOutput implementation"""
    print("\n=== Testing TextOutput ===")
    
    from irene.outputs.text import TextOutput
    from irene.outputs.base import Response
    
    text_output = TextOutput(prefix="DEMO: ", use_colors=True)
    
    # Test basic response
    await text_output.send(Response("Hello, this is a basic text response!", response_type="text"))
    
    # Test different response types
    await text_output.send(Response("This is an error message", response_type="error"))
    await text_output.send(Response("This is a warning", response_type="warning"))
    await text_output.send(Response("This is success feedback", response_type="success"))
    await text_output.send(Response("This is info", response_type="info"))
    await text_output.send(Response("This is debug info", response_type="debug", metadata={"key": "value"}))
    
    # Test configuration
    print(f"Text output settings: {text_output.get_settings()}")
    print(f"Color status: {text_output.get_color_status()}")


async def test_tts_output():
    """Test the TTSOutput implementation"""
    print("\n=== Testing TTSOutput ===")
    
    try:
        from irene.outputs.tts import TTSOutput
        from irene.outputs.base import Response
        
        tts_output = TTSOutput(engine="pyttsx3")
        
        if tts_output.is_available():
            print("TTS is available - testing speech...")
            await tts_output.send(Response("Hello! This is a TTS test.", response_type="tts"))
            
            # Test voice listing
            voices = tts_output.get_supported_voices()
            print(f"Available voices: {len(voices)} found")
            for i, voice in enumerate(voices[:3]):  # Show first 3
                print(f"  {i+1}. {voice}")
                
        else:
            print("TTS is not available - pyttsx3 may not be installed")
            
    except Exception as e:
        print(f"TTS test failed: {e}")


async def test_cli_input():
    """Test the modern CLIInput implementation"""
    print("\n=== Testing CLIInput ===")
    
    from irene.inputs.cli import CLIInput
    
    cli_input = CLIInput(prompt="demo> ")
    
    print("Starting CLI input (type 'quit' to stop)...")
    await cli_input.start_listening()
    
    # Listen for commands for a short time
    async for command in cli_input.listen():
        print(f"Received command: '{command}'")
        
        if command.lower() == 'quit':
            break
            
        # Echo the command back
        print(f"Echo: {command}")
        
    await cli_input.stop_listening()
    print("CLI input test completed")


async def test_input_manager():
    """Test the InputManager with modern sources"""
    print("\n=== Testing InputManager ===")
    
    from irene.inputs.base import InputManager
    
    # Mock component manager for testing
    class MockComponentManager:
        def has_component(self, name: str) -> bool:
            return True
    
    input_manager = InputManager(MockComponentManager())
    await input_manager.initialize()
    
    # Show discovered sources
    available_sources = input_manager.get_available_sources()
    print(f"Available input sources: {available_sources}")
    
    for source_name in available_sources:
        source_info = input_manager.get_source_info(source_name)
        print(f"  {source_name}: {source_info}")


async def test_output_manager():
    """Test the OutputManager with modern targets"""
    print("\n=== Testing OutputManager ===")
    
    from irene.outputs.base import OutputManager
    
    # Mock component manager for testing
    class MockComponentManager:
        def has_component(self, name: str) -> bool:
            return True
    
    output_manager = OutputManager(MockComponentManager())
    await output_manager.initialize()
    
    # Show discovered targets
    available_targets = output_manager.get_available_targets()
    print(f"Available output targets: {available_targets}")
    
    for target_name in available_targets:
        target_info = output_manager.get_target_info(target_name)
        print(f"  {target_name}: {target_info}")
    
    # Test sending responses
    await output_manager.send_response("Testing text output", response_type="text")
    await output_manager.send_response("Testing error output", response_type="error")
    
    # Test TTS if available
    if output_manager.has_tts():
        print("TTS is available - testing speech output...")
        await output_manager.speak("Testing TTS output")
    else:
        print("TTS is not available")


async def test_integrated_io():
    """Test integrated I/O workflow"""
    print("\n=== Testing Integrated I/O Workflow ===")
    
    from irene.inputs.base import InputManager
    from irene.outputs.base import OutputManager
    
    # Mock component manager
    class MockComponentManager:
        def has_component(self, name: str) -> bool:
            return True
    
    # Initialize managers
    input_manager = InputManager(MockComponentManager())
    output_manager = OutputManager(MockComponentManager())
    
    await input_manager.initialize()
    await output_manager.initialize()
    
    # Start CLI input
    await input_manager.start_source("cli")
    
    await output_manager.send_response(
        "Integrated I/O test ready. Type commands (or 'quit' to exit):",
        response_type="info"
    )
    
    # Process commands for a short demo
    command_count = 0
    while command_count < 5:  # Limit for demo
        try:
            # Get next command from any active source
            source_name, command = await asyncio.wait_for(
                input_manager.get_next_input(), timeout=10.0
            )
            command_count += 1
            
            if command.lower() == 'quit':
                break
                
            # Echo command back through output manager
            await output_manager.send_response(
                f"Command {command_count} from {source_name}: {command}",
                response_type="text"
            )
            
            # Test TTS for certain commands
            if "hello" in command.lower() and output_manager.has_tts():
                await output_manager.speak(f"Hello! You said: {command}")
                
        except asyncio.TimeoutError:
            await output_manager.send_response(
                "No input received. Demo ending...",
                response_type="warning"
            )
            break
        except Exception as e:
            logger.error(f"Error in integrated test: {e}")
            break
    
    await input_manager.stop_source("cli")
    print("Integrated I/O test completed")


async def main():
    """Run all I/O tests"""
    print("🔧 Modern I/O System Demonstration")
    print("=" * 50)
    
    try:
        # Test individual components
        await test_text_output()
        await test_tts_output()
        
        # Test managers
        await test_input_manager()
        await test_output_manager()
        
        # Test CLI input (interactive)
        print("\n⚠️  The CLI input test requires user interaction.")
        response = input("Run interactive CLI test? (y/n): ")
        if response.lower().startswith('y'):
            await test_cli_input()
        
        # Test integrated workflow
        print("\n⚠️  The integrated test requires user interaction.")
        response = input("Run integrated I/O test? (y/n): ")
        if response.lower().startswith('y'):
            await test_integrated_io()
        
        print("\n✅ I/O System Demo completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        logger.exception("Demo error details")


if __name__ == "__main__":
    asyncio.run(main()) 