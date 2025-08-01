"""
Component Demo - Showcasing Optional Components Architecture

Demonstrates how Irene v13 can run in different deployment modes
based on component availability and configuration.
"""

import asyncio
import logging
from dataclasses import dataclass

from ..core.engine import AsyncVACore
from ..config.models import CoreConfig, ComponentConfig, VOICE_PROFILE, API_PROFILE, HEADLESS_PROFILE

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def demo_deployment_profile(profile_name: str, component_config: ComponentConfig):
    """Demo a specific deployment profile"""
    print(f"\n{'='*60}")
    print(f"  DEMO: {profile_name}")
    print(f"{'='*60}")
    
    # Create configuration
    config = CoreConfig(
        name=f"Irene-{profile_name}",
        components=component_config,
        debug=True
    )
    
    # Show requested components
    print(f"Requested components:")
    print(f"  - Microphone: {component_config.microphone}")
    print(f"  - TTS: {component_config.tts}")
    print(f"  - Audio Output: {component_config.audio_output}")
    print(f"  - Web API: {component_config.web_api}")
    
    # Create and start core
    core = AsyncVACore(config)
    
    try:
        await core.start()
        
        # Show actual deployment profile
        profile = core.component_manager.get_deployment_profile()
        active = core.component_manager.get_active_components()
        print(f"\nActual deployment: {profile}")
        print(f"Active components: {active}")
        
        # Test basic functionality
        print(f"\nTesting command processing...")
        await core.process_command("hello")
        await core.process_command("what time is it")
        
        # Test say() method (component-aware)
        print(f"\nTesting say() method...")
        await core.say("Testing component-aware speech output")
        
        print(f"✅ {profile_name} demo completed successfully!")
        
    except Exception as e:
        print(f"❌ {profile_name} demo failed: {e}")
        
    finally:
        await core.stop()
        print(f"✅ {profile_name} cleanup completed")


async def main():
    """Run all deployment profile demos"""
    print("🚀 Irene v13 - Optional Components Architecture Demo")
    print("This demo shows how Irene adapts to different deployment scenarios")
    
    # Demo 1: Voice Assistant Profile (Full)
    await demo_deployment_profile("Voice Assistant (Full)", VOICE_PROFILE)
    
    # Demo 2: API Server Profile
    await demo_deployment_profile("API Server", API_PROFILE)
    
    # Demo 3: Headless Profile  
    await demo_deployment_profile("Headless Processor", HEADLESS_PROFILE)
    
    # Demo 4: Custom Profile
    custom_profile = ComponentConfig(
        microphone=False,
        tts=True,  # TTS only
        audio_output=False,
        web_api=False
    )
    await demo_deployment_profile("Custom (TTS Only)", custom_profile)
    
    print(f"\n{'='*60}")
    print("  🎉 ALL DEMOS COMPLETED!")
    print("  Phase 3: Optional Components Architecture ✅")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main()) 