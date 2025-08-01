"""
Web API Demo - Comprehensive demonstration of Irene's Web API capabilities

This demo showcases:
- FastAPI server setup and operation
- WebSocket real-time communication
- REST API endpoints
- Web interface integration
- Multi-client support
"""

import asyncio
import logging
import json
import time
from pathlib import Path
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_web_api_availability() -> bool:
    """Check if Web API components are available"""
    print("🔍 Checking Web API availability...")
    
    try:
        from ..inputs.web import WebInput
        from ..outputs.web import WebOutput
        from ..runners.webapi_runner import WebAPIRunner
        
        # Test component creation
        web_input = WebInput()
        web_output = WebOutput()
        
        print(f"✅ WebInput available: {web_input.is_available()}")
        print(f"✅ WebOutput available: {web_output.is_available()}")
        
        if not web_input.is_available() or not web_output.is_available():
            print("💡 Install web dependencies: uv add irene-voice-assistant[web-api]")
            return False
            
        return True
        
    except ImportError as e:
        print(f"❌ Web API components not available: {e}")
        print("💡 Install with: uv add irene-voice-assistant[web-api]")
        return False


async def test_web_input_functionality():
    """Test WebInput component functionality"""
    print("\n🔌 Testing WebInput functionality...")
    
    from ..inputs.web import WebInput
    
    # Create web input
    web_input = WebInput(host="localhost", port=8081)
    
    print(f"📊 Settings: {web_input.get_settings()}")
    
    # Test basic functionality
    test_result = await web_input.test_input()
    print(f"🧪 Test result: {'✅ PASS' if test_result else '❌ FAIL'}")
    
    # Start listening
    await web_input.start_listening()
    print(f"👂 Listening: {web_input.is_listening()}")
    
    # Simulate sending commands
    print("📤 Simulating command input...")
    await web_input.send_command("Hello from WebInput test")
    await web_input.send_command("Time")
    await web_input.send_command("Random number")
    
    # Listen for a short time to demonstrate AsyncIterator
    print("📥 Listening for commands...")
    command_count = 0
    async for command in web_input.listen():
        print(f"📨 Received command: {command}")
        command_count += 1
        if command_count >= 3:  # Stop after receiving test commands
            break
    
    # Stop listening
    await web_input.stop_listening()
    print(f"🛑 Stopped listening: {not web_input.is_listening()}")
    
    # Check connection info
    info = web_input.get_connection_info()
    print(f"📋 Connection info: {info}")


async def test_web_output_functionality():
    """Test WebOutput component functionality"""
    print("\n📤 Testing WebOutput functionality...")
    
    from ..inputs.web import WebInput
    from ..outputs.web import WebOutput
    from ..outputs.base import Response
    
    # Create web output
    web_output = WebOutput(host="localhost", port=8082)
    
    print(f"📊 Settings: {web_output.get_settings()}")
    
    # Test basic functionality
    test_result = await web_output.test_output()
    print(f"🧪 Test result: {'✅ PASS' if test_result else '❌ FAIL'}")
    
    # Test response formatting
    test_response = Response("Test message", response_type="test", metadata={"demo": True})
    formatted = web_output._format_web_response(test_response)
    print(f"📝 Formatted response: {formatted}")
    
    # Test message history
    await web_output.send(Response("First message", response_type="text"))
    await web_output.send(Response("Second message", response_type="tts"))
    await web_output.send(Response("Error message", response_type="error"))
    
    history = web_output.get_message_history(limit=5)
    print(f"📚 Message history ({len(history)} messages):")
    for i, msg in enumerate(history):
        print(f"   {i+1}. [{msg['response_type']}] {msg['text']}")
    
    # Test system messages
    await web_output.send_system_message("System notification", "notification")
    
    # Get client info (will be empty since no real WebSocket clients)
    client_info = web_output.get_client_info()
    print(f"👥 Client info: {client_info}")


async def test_web_api_integration():
    """Test WebInput and WebOutput integration"""
    print("\n🔗 Testing Web API integration...")
    
    from ..inputs.web import WebInput
    from ..outputs.web import WebOutput
    from ..outputs.base import Response
    from ..core.engine import AsyncVACore
    from ..config.models import CoreConfig, ComponentConfig
    
    # Create configuration for web API mode
    config = CoreConfig(
        components=ComponentConfig(
            microphone=False,
            tts=False, 
            audio_output=False,
            web_api=True
        )
    )
    
    # Create core with web components
    core = AsyncVACore(config)
    await core.start()
    
    # Create web components
    web_input = WebInput(host="localhost", port=8083)
    web_output = WebOutput(host="localhost", port=8083)
    
    # Add to core managers
    await core.input_manager.add_source("web", web_input)
    await core.input_manager.start_source("web")
    
    await core.output_manager.add_target("web", web_output)
    
    print("✅ Web components integrated with AsyncVACore")
    
    # Test command flow: WebInput → Core → WebOutput
    print("🔄 Testing command processing flow...")
    
    # Start listening
    async def command_listener():
        """Listen for commands and process them"""
        async for command in web_input.listen():
            print(f"📨 Processing command: {command}")
            await core.process_command(command)
            
            # Stop after processing one command
            break
    
    # Start listener task
    listener_task = asyncio.create_task(command_listener())
    
    # Send a test command
    await asyncio.sleep(0.1)  # Small delay
    await web_input.send_command("привет")
    
    # Wait for processing
    try:
        await asyncio.wait_for(listener_task, timeout=2.0)
        print("✅ Command processed successfully")
    except asyncio.TimeoutError:
        print("⏰ Command processing timed out")
    
    # Check message history for responses
    history = web_output.get_message_history()
    if history:
        print("📥 Responses generated:")
        for msg in history[-3:]:  # Last 3 messages
            print(f"   [{msg['response_type']}] {msg['text']}")
    
    # Cleanup
    await core.stop()
    print("🧹 Cleanup completed")


async def demonstrate_websocket_simulation():
    """Demonstrate WebSocket message handling"""
    print("\n🌐 Demonstrating WebSocket message handling...")
    
    from ..inputs.web import WebInput
    
    web_input = WebInput()
    await web_input.start_listening()
    
    # Simulate WebSocket connections and messages
    class MockWebSocket:
        def __init__(self, name: str):
            self.name = name
            self.messages_sent = []
        
        async def send_text(self, message: str):
            self.messages_sent.append(message)
            print(f"📨 [{self.name}] Sent: {message}")
        
        async def close(self):
            print(f"🔌 [{self.name}] Connection closed")
    
    # Create mock WebSocket clients
    client1 = MockWebSocket("Client1")
    client2 = MockWebSocket("Client2")
    
    # Add connections
    await web_input.add_websocket_connection(client1)
    await web_input.add_websocket_connection(client2)
    
    print(f"👥 Connected clients: {len(web_input._websocket_connections)}")
    
    # Test different message types
    test_messages = [
        '{"type": "command", "command": "время"}',
        '{"type": "command", "command": "привет"}',
        '{"type": "command", "command": ""}',  # Empty command
        '{"invalid": "json"}',  # Invalid message type
        'invalid json'  # Invalid JSON
    ]
    
    print("📨 Testing WebSocket message handling...")
    for i, message in enumerate(test_messages):
        print(f"\n🔄 Test {i+1}: {message}")
        await web_input.handle_websocket_message(client1, message)
    
    # Check client responses
    print(f"\n📤 Client1 received {len(client1.messages_sent)} responses:")
    for msg in client1.messages_sent:
        print(f"   {msg}")
    
    # Remove connections
    await web_input.remove_websocket_connection(client1)
    await web_input.remove_websocket_connection(client2)
    
    await web_input.stop_listening()


async def run_web_server_demo():
    """Demonstrate running the actual Web API server briefly"""
    print("\n🚀 Web API Server Demo...")
    print("This would normally start a full FastAPI server.")
    print("For security, we'll just demonstrate the runner setup.")
    
    from ..runners.webapi_runner import WebAPIRunner, check_webapi_dependencies
    
    # Check dependencies
    deps_ok = check_webapi_dependencies()
    if not deps_ok:
        print("❌ Cannot run server demo - dependencies missing")
        return
    
    print("✅ Web API dependencies available")
    
    # Create runner (but don't actually start server)
    runner = WebAPIRunner()
    
    print("📋 Server configuration:")
    print("   - Host: 127.0.0.1")
    print("   - Port: 5003")
    print("   - Endpoints: /, /status, /command, /history, /components, /health")
    print("   - WebSocket: /ws") 
    print("   - API Docs: /docs")
    
    print("\n💡 To start the actual server, run:")
    print("   uv run python -m irene.runners.webapi_runner")
    print("   # or")
    print("   uv run irene-webapi")


async def main():
    """Run comprehensive Web API demonstration"""
    print("🌐 Irene Web API Demo - Comprehensive Testing")
    print("=" * 60)
    
    # Check availability first
    if not await check_web_api_availability():
        print("❌ Cannot run demo - Web API components not available")
        return 1
    
    try:
        # Test individual components
        await test_web_input_functionality()
        await test_web_output_functionality()
        
        # Test integration
        await test_web_api_integration()
        
        # Test WebSocket simulation
        await demonstrate_websocket_simulation()
        
        # Server demo
        await run_web_server_demo()
        
        print("\n" + "=" * 60)
        print("✅ Web API Demo completed successfully!")
        print("\n🎯 Key Features Demonstrated:")
        print("   ✅ WebInput with AsyncIterator command yielding")
        print("   ✅ WebOutput with multi-client WebSocket support")
        print("   ✅ Integration with AsyncVACore")
        print("   ✅ WebSocket message handling and validation")
        print("   ✅ FastAPI server setup and configuration")
        print("   ✅ Message history and client management")
        
        return 0
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 