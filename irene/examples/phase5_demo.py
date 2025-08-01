#!/usr/bin/env python3
"""
Phase 5 Input/Output Abstraction Demo - Optional Components Architecture

Demonstrates the new input/output abstraction system with:
- InputSource interface with AsyncIterator pattern
- OutputTarget interface with Response objects
- Optional component handling (microphone, TTS, web)
- Graceful fallbacks when components unavailable
- Component discovery and management
"""

import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from ..config.models import CoreConfig, ComponentConfig
from ..core.engine import AsyncVACore
from ..core.context import Context
from ..outputs.base import Response


async def main():
    """Demonstrate the new Phase 5 input/output abstraction system"""
    print("🚀 Irene v13 - Phase 5 Input/Output Abstraction Demo")
    print("=" * 60)
    
    # Create configuration with minimal components to test graceful fallbacks
    config = CoreConfig(
        components=ComponentConfig(
            microphone=False,  # Will test optional component handling
            tts=False,         # Will test TTS fallback
            audio_output=False,
            web_api=False
        )
    )
    
    # Initialize the async VA core
    core = AsyncVACore(config)
    
    try:
        # Start the core (this initializes input/output managers)
        print("\n📦 Starting AsyncVACore with new I/O abstraction...")
        await core.start()
        
        print(f"✅ Core started successfully!")
        
        # Test Input Abstraction
        print("\n🎤 Input System Status:")
        input_manager = core.input_manager
        
        print(f"  Available sources: {input_manager.get_available_sources()}")
        print(f"  Active sources: {input_manager.get_active_sources()}")
        print(f"  Total available: {input_manager.available_source_count}")
        print(f"  Total active: {input_manager.active_source_count}")
        
        # Show detailed info for each source
        for source_name in input_manager.get_available_sources():
            info = input_manager.get_source_info(source_name)
            if info:
                print(f"\n  📋 {source_name.upper()} Input:")
                for key, value in info.items():
                    print(f"    {key}: {value}")
                    
        # Test Output Abstraction
        print(f"\n🔊 Output System Status:")
        output_manager = core.output_manager
        
        print(f"  Available targets: {output_manager.get_available_targets()}")
        print(f"  Active targets: {output_manager.get_active_targets()}")
        print(f"  Total available: {output_manager.available_target_count}")
        print(f"  Total active: {output_manager.active_target_count}")
        print(f"  TTS available: {output_manager.has_tts()}")
        
        # Show detailed info for each target
        for target_name in output_manager.get_available_targets():
            info = output_manager.get_target_info(target_name)
            if info:
                print(f"\n  📋 {target_name.upper()} Output:")
                for key, value in info.items():
                    print(f"    {key}: {value}")
                    
        # Test Response Objects and Routing
        print(f"\n💬 Testing Response System:")
        
        # Test different response types
        test_responses = [
            Response("Hello! This is a text response.", response_type="text"),
            Response("This would be spoken by TTS.", response_type="tts"),
            Response("This is an error message.", response_type="error"),
            Response("This is a notification.", response_type="notification"),
        ]
        
        for response in test_responses:
            print(f"\n  → Sending {response.response_type} response: '{response.text}'")
            try:
                await output_manager.send_response_object(response)
                print(f"    ✅ Sent successfully")
            except Exception as e:
                print(f"    ❌ Error: {e}")
                
        # Test legacy compatibility
        print(f"\n🔄 Testing Legacy Compatibility:")
        await output_manager.text_output("Legacy text output test")
        await output_manager.speak("Legacy TTS output test (will fallback to text)")
        
        # Test Command Processing with New I/O
        print(f"\n🎯 Testing Command Processing with New I/O:")
        context = core.context_manager.create_context()
        
        test_commands = ["help", "status", "version"]
        
        for cmd in test_commands:
            print(f"\n  → Processing: '{cmd}'")
            try:
                await core.process_command(cmd, context)
                print(f"    ✅ Command processed successfully")
            except Exception as e:
                print(f"    ❌ Error: {e}")
                
        # Test Optional Component Graceful Fallbacks
        print(f"\n🔧 Testing Optional Component Handling:")
        
        # Test microphone fallback
        print(f"  📱 Microphone component:")
        if hasattr(core.input_manager, '_sources'):
            mic_sources = [name for name, source in core.input_manager._sources.items() 
                          if hasattr(source, 'get_input_type') and source.get_input_type() == 'microphone']
            if mic_sources:
                print(f"    ✅ Microphone input available: {mic_sources}")
            else:
                print(f"    ⚠️  Microphone input not available (graceful fallback)")
        
        # Test TTS fallback
        print(f"  🔊 TTS component:")
        if hasattr(core.output_manager, '_targets'):
            tts_targets = [name for name, target in core.output_manager._targets.items() 
                          if hasattr(target, 'get_output_type') and target.get_output_type() == 'tts']
            if tts_targets:
                print(f"    ✅ TTS output available: {tts_targets}")
            else:
                print(f"    ⚠️  TTS output not available (graceful fallback to text)")
                
        # Test web component fallback
        print(f"  🌐 Web component:")
        if hasattr(core.output_manager, '_targets'):
            web_targets = [name for name, target in core.output_manager._targets.items() 
                          if hasattr(target, 'get_output_type') and target.get_output_type() == 'web']
            if web_targets:
                print(f"    ✅ Web output available: {web_targets}")
            else:
                print(f"    ⚠️  Web output not available (graceful fallback)")
                
        # Test Component Manager Integration
        print(f"\n⚙️  Component Manager Integration:")
        component_manager = core.component_manager
        print(f"  Deployment profile: {component_manager.get_deployment_profile()}")
        
        # Test input source discovery and startup
        print(f"\n🚀 Testing Dynamic Input Management:")
        
        # Start CLI input source
        if 'cli' in input_manager.get_available_sources():
            print(f"  → Starting CLI input source...")
            success = await input_manager.start_source('cli')
            print(f"    {'✅' if success else '❌'} CLI input start: {success}")
            
            # Wait a moment for any setup
            await asyncio.sleep(0.5)
            
            # Stop CLI input source
            print(f"  → Stopping CLI input source...")
            success = await input_manager.stop_source('cli')
            print(f"    {'✅' if success else '❌'} CLI input stop: {success}")
            
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Clean shutdown
        print("\n🛑 Shutting down...")
        if core._running:
            await core.stop()
        print("✅ Shutdown complete")

    print("\n🎉 Phase 5 Input/Output Abstraction Demo completed successfully!")
    print("\nKey improvements implemented:")
    print("  ✅ InputSource interface with AsyncIterator pattern")
    print("  ✅ OutputTarget interface with Response objects")
    print("  ✅ Optional component handling (microphone, TTS, web)")
    print("  ✅ Graceful fallbacks when components unavailable")
    print("  ✅ Component discovery and automatic initialization")
    print("  ✅ Legacy compatibility via adapter pattern")
    print("  ✅ Response type routing and filtering")
    print("  ✅ Unified input/output management")
    print("  ✅ Non-blocking I/O operations throughout")


if __name__ == "__main__":
    asyncio.run(main()) 