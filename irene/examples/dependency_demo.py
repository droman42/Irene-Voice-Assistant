"""
Dependency Management Demo

Demonstrates the graceful dependency loading and component fallback
features of Irene v13.
"""

import asyncio
import logging
from pathlib import Path

from ..config.models import CoreConfig, ComponentConfig
from ..core.engine import AsyncVACore
from ..core.session_manager import SessionManager
from ..core.components import ComponentLoader
from ..utils.loader import get_component_status, suggest_installation


async def main():
    """Demonstrate dependency management features"""
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    print("=" * 60)
    print("🎯 Irene v13 - Dependency Management Demo")
    print("=" * 60)
    
    # 1. Component Status Report
    print("\n📊 Component Availability Report:")
    print("-" * 40)
    
    status = get_component_status()
    for component, info in status.items():
        status_icon = "✅" if info["available"] else "❌"
        print(f"{status_icon} {component.capitalize()}: {'Available' if info['available'] else 'Missing'}")
        
        if not info["available"]:
            print(f"   Missing: {', '.join(info['missing'])}")
            suggestion = suggest_installation(component)
            if suggestion:
                print(f"   Install: {suggestion}")
        print()
    
    # 2. ComponentLoader Caching Demo
    print("\n🔄 ComponentLoader Caching Demo:")
    print("-" * 40)
    
    # Clear cache and test
    ComponentLoader.clear_cache()
    
    # Check microphone multiple times (should use cache after first check)
    for i in range(3):
        available = ComponentLoader.is_available("microphone", ["vosk", "sounddevice"])
        print(f"Check {i+1}: Microphone available = {available}")
    
    # Show cache contents
    print("\nComponentLoader Cache:")
    report = ComponentLoader.get_availability_report()
    for cache_type, data in report.items():
        print(f"  {cache_type}: {data}")
    
    # 3. Deployment Profile Testing
    print("\n🚀 Testing Different Deployment Profiles:")
    print("-" * 40)
    
    profiles = [
        ("Headless", ComponentConfig(microphone=False, tts=False, audio_output=False, web_api=False)),
        ("API-Only", ComponentConfig(microphone=False, tts=False, audio_output=False, web_api=True)),
        ("TTS-Only", ComponentConfig(microphone=False, tts=True, audio_output=True, web_api=False)),
        ("Full Voice", ComponentConfig(microphone=True, tts=True, audio_output=True, web_api=True)),
    ]
    
    for profile_name, component_config in profiles:
        print(f"\n🔧 Testing {profile_name} Profile:")
        
        config = CoreConfig(
            name=f"Irene-{profile_name}",
            components=component_config,
            debug=True
        )
        
        # Create and start core with this profile
        core = AsyncVACore(config)
        
        try:
            await core.start()
            
            # Get component info
            component_info = core.component_manager.get_component_info()
            active_components = [name for name, info in component_info.items() 
                               if info.initialized]
            
            detected_profile = core.component_manager.get_deployment_profile()
            
            print(f"   Active components: {active_components}")
            print(f"   Detected profile: {detected_profile}")
            
            # Test a simple command
            # Use unified workflow interface
            result = await core.workflow_manager.process_text_input(
                text="hello",
                session_id=SessionManager.generate_session_id("dependency_demo"),
                wants_audio=False,
                client_context={"source": "dependency_demo"}
            )
            print(f"Response: {result.text}")
            
        except Exception as e:
            print(f"   ❌ Failed to start: {e}")
        finally:
            await core.stop()
        
        print(f"   ✅ {profile_name} profile test completed")
    
    # 4. Graceful Fallback Demo
    print("\n🛡️ Graceful Fallback Demo:")
    print("-" * 40)
    
    # Test what happens when components are missing
    missing_component_config = ComponentConfig(
        microphone=True,  # Request microphone even if not available
        tts=True,        # Request TTS even if not available
        audio_output=True,
        web_api=True
    )
    
    config = CoreConfig(
        name="Irene-Fallback-Test",
        components=missing_component_config,
        debug=True
    )
    
    core = AsyncVACore(config)
    
    try:
        print("Starting core with potentially missing components...")
        await core.start()
        
        profile = core.component_manager.get_deployment_profile()
        print(f"Graceful fallback resulted in: {profile}")
        
        # Test commands in fallback mode
        test_commands = ["hello", "what time is it", "say goodbye"]
        
        for command in test_commands:
            print(f"Testing command: '{command}'")
            try:
                # Use unified workflow interface
                result = await core.workflow_manager.process_text_input(
                    text=command,
                    session_id=SessionManager.generate_session_id("dependency_demo_interactive"),
                    wants_audio=False,
                    client_context={"source": "dependency_demo"}
                )
                print(f"Response: {result.text}")
                print("  ✅ Command processed successfully")
            except Exception as e:
                print(f"  ⚠️  Command failed: {e}")
    
    except Exception as e:
        print(f"❌ Fallback test failed: {e}")
    finally:
        await core.stop()
    
    # 5. Component Loading Performance
    print("\n⚡ Component Loading Performance:")
    print("-" * 40)
    
    import time
    
    # Time component loading
    start_time = time.time()
    
    components = [
        ComponentLoader.load_microphone_component(),
        ComponentLoader.load_tts_component(),
        ComponentLoader.load_audio_output_component(),
        ComponentLoader.load_web_api_component(),
    ]
    
    end_time = time.time()
    
    available_count = sum(1 for c in components if c is not None)
    total_count = len(components)
    
    print(f"Loaded {available_count}/{total_count} components in {end_time - start_time:.3f}s")
    
    # Cleanup loaded components
    for component in components:
        if component:
            await component.stop()
    
    print("\n🎉 Dependency Management Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main()) 