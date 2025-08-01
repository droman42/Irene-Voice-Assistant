#!/usr/bin/env python3
"""
Phase 4 Plugin System Demo - Interface-Based Plugin Architecture

Demonstrates the new interface-based plugin system with:
- CommandPluginAdapter bridging interfaces
- Proper AsyncPluginManager with PluginManager protocol compliance
- Enhanced registry with error handling and validation
- Clean separation between plugin interfaces and command processing
"""

import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from ..config.models import CoreConfig, ComponentConfig
from ..core.engine import AsyncVACore
from ..core.context import Context


async def main():
    """Demonstrate the new Phase 4 plugin system"""
    print("🚀 Irene v13 - Phase 4 Plugin System Demo")
    print("=" * 50)
    
    # Create configuration with minimal components
    config = CoreConfig(
        components=ComponentConfig(
            microphone=False,
            tts=False,
            audio_output=False,
            web_api=False
        )
    )
    
    # Initialize the async VA core
    core = AsyncVACore(config)
    
    try:
        # Start the core (this loads plugins using new system)
        print("\n📦 Starting AsyncVACore with new plugin system...")
        await core.start()
        
        print(f"✅ Core started successfully!")
        print(f"🔌 Loaded {core.plugin_manager.plugin_count} plugins")
        
        # Show plugin information
        print("\n📋 Loaded Plugins:")
        for plugin in core.plugin_manager.list_plugins_sync():
            info = core.plugin_manager.get_plugin_info(plugin.name)
            if info:
                print(f"  • {plugin.name} v{plugin.version}")
                print(f"    Description: {plugin.description}")
                print(f"    Interfaces: {', '.join(info['interfaces'])}")
            else:
                print(f"  • {plugin.name} v{plugin.version} (no info available)")
            
        # Show command handlers
        print("\n🎯 Command Handlers:")
        handlers = core.command_processor.list_handlers()
        for handler in handlers:
            print(f"  • {handler}")
            
        print(f"\n🔧 Available triggers: {core.command_processor.get_all_triggers()}")
        
        # Test commands using new system
        print("\n💬 Testing Command Processing:")
        context = core.context_manager.create_context()
        
        test_commands = ["help", "status", "version", "ping", "unknown command"]
        
        for cmd in test_commands:
            print(f"\n→ Testing: '{cmd}'")
            try:
                await core.process_command(cmd, context)
            except Exception as e:
                print(f"   ❌ Error: {e}")
                
        # Show registry statistics
        print("\n📊 Plugin Registry Statistics:")
        stats = core.plugin_manager.registry.get_statistics()
        for key, value in stats.items():
            print(f"  • {key.replace('_', ' ').title()}: {value}")
            
        # Show any discovery errors
        errors = core.plugin_manager.registry.get_discovery_errors()
        if errors:
            print(f"\n⚠️  Discovery Errors ({len(errors)}):")
            for error in errors:
                print(f"  • {error['type']}: {error['message']}")
        else:
            print("\n✅ No plugin discovery errors")
            
        # Test plugin management operations
        print("\n🔄 Testing Plugin Management:")
        
        # Test plugin info
        plugin_info = core.plugin_manager.get_plugin_info("core_commands")
        if plugin_info:
            print(f"  📄 Core Commands Plugin Info:")
            for key, value in plugin_info.items():
                print(f"     {key}: {value}")
                
        # Test dependency validation
        validation_results = core.plugin_manager.registry.validate_all_plugins()
        if validation_results:
            print(f"\n⚠️  Plugin Validation Issues:")
            for plugin_name, issues in validation_results.items():
                print(f"  • {plugin_name}: {', '.join(issues)}")
        else:
            print("\n✅ All plugins validated successfully")
            
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        raise
    finally:
        # Clean shutdown
        print("\n🛑 Shutting down...")
        if core._running:
            await core.stop()
        print("✅ Shutdown complete")

    print("\n🎉 Phase 4 Plugin System Demo completed successfully!")
    print("\nKey improvements implemented:")
    print("  ✅ Interface-based plugin architecture")
    print("  ✅ CommandPluginAdapter bridging system")
    print("  ✅ Enhanced AsyncPluginManager with PluginManager protocol")
    print("  ✅ Improved plugin registry with error handling")
    print("  ✅ Dependency validation and circular dependency detection")
    print("  ✅ Clean separation of concerns")


if __name__ == "__main__":
    asyncio.run(main()) 