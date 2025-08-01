"""
Audio Demo - Demonstrate v13 audio playback capabilities

Showcases all 5 audio plugins with different backends:
- SoundDevice (primary backend)
- AudioPlayer (cross-platform)
- Aplay (Linux)
- SimpleAudio (simple WAV playback)
- Console (debug output)
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from ..plugins.builtin.sounddevice_audio_plugin import SoundDeviceAudioPlugin
from ..plugins.builtin.audioplayer_audio_plugin import AudioPlayerAudioPlugin
from ..plugins.builtin.aplay_audio_plugin import AplayAudioPlugin
from ..plugins.builtin.simpleaudio_audio_plugin import SimpleAudioPlugin
from ..plugins.builtin.console_audio_plugin import ConsoleAudioPlugin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_audio_plugin(plugin, test_file: Optional[Path] = None):
    """Test a single audio plugin"""
    print(f"\n{'='*60}")
    print(f"🎵 Testing: {plugin.name}")
    print(f"   Description: {plugin.description}")
    print(f"   Version: {plugin.version}")
    print(f"   Available: {plugin.is_available()}")
    print(f"   Supported formats: {plugin.get_supported_formats()}")
    print(f"   Playback devices: {len(plugin.get_playback_devices())}")
    
    if not plugin.is_available():
        print(f"   ⚠️  Plugin not available - dependencies missing")
        if plugin.optional_dependencies:
            print(f"   💡 Install dependencies: {', '.join(plugin.optional_dependencies)}")
        return
    
    try:
        # Initialize plugin
        await plugin.initialize(None)
        
        # Test device enumeration
        devices = plugin.get_playback_devices()
        print(f"   📻 Available devices:")
        for device in devices:
            print(f"      - {device['name']} (ID: {device['id']})")
        
        # Test volume setting
        await plugin.set_volume(0.8)
        
        # Test file playback if test file provided
        if test_file and test_file.exists():
            print(f"   🎶 Playing test file: {test_file.name}")
            await plugin.play_file(test_file, volume=0.5)
        else:
            print(f"   ⚠️  No test file provided for actual playback")
            
        # Test playback controls
        print(f"   🎛️  Testing playback controls...")
        await plugin.pause_playback()
        await plugin.resume_playback()
        await plugin.stop_playback()
        
        print(f"   ✅ Plugin test completed successfully")
        
    except Exception as e:
        print(f"   ❌ Plugin test failed: {e}")
        
    finally:
        try:
            await plugin.shutdown()
        except:
            pass
            

async def audio_plugin_demo():
    """Demonstrate all audio plugins"""
    print("🎵 Irene Voice Assistant v13 - Audio Plugin Demo")
    print("=" * 60)
    print()
    print("This demo showcases all 5 audio playback backends:")
    print("1. SoundDevice - Primary high-quality backend")
    print("2. AudioPlayer - Cross-platform compatibility")
    print("3. Aplay - Linux ALSA command-line")
    print("4. SimpleAudio - Simple WAV playback")
    print("5. Console - Debug output (always available)")
    print()
    
    # Create test audio plugins
    plugins = [
        SoundDeviceAudioPlugin(),
        AudioPlayerAudioPlugin(),
        AplayAudioPlugin(),
        SimpleAudioPlugin(),
        ConsoleAudioPlugin()
    ]
    
    # Look for test audio file
    test_file = None
    possible_test_files = [
        Path("media/test.wav"),
        Path("test.wav"),
        Path("audio_test.wav"),
        Path("/usr/share/sounds/alsa/Front_Left.wav"),  # Common Linux test file
        Path("/System/Library/Sounds/Ping.aiff"),       # macOS test file
        Path("C:/Windows/Media/chimes.wav")              # Windows test file
    ]
    
    for file_path in possible_test_files:
        if file_path.exists():
            test_file = file_path
            break
    
    if test_file:
        print(f"📁 Using test audio file: {test_file}")
    else:
        print("📁 No test audio file found - will demonstrate capabilities without actual playback")
    print()
    
    # Test each plugin
    for plugin in plugins:
        await test_audio_plugin(plugin, test_file)
    
    print(f"\n{'='*60}")
    print("🎵 Audio Plugin Demo Completed")
    print()
    print("Summary:")
    print("- SoundDevice: High-quality audio with device selection")
    print("- AudioPlayer: Simple cross-platform playback")
    print("- Aplay: Linux command-line audio (no Python deps)")
    print("- SimpleAudio: Lightweight WAV-only playback")
    print("- Console: Debug output for testing")
    print()
    print("✨ All plugins implement the same AudioPlugin interface")
    print("✨ Graceful fallback when dependencies missing")
    print("✨ Async operation - no blocking calls")
    print("✨ Volume control and device selection (where supported)")
    

async def audio_compatibility_test():
    """Test audio plugin compatibility and availability"""
    print("\n🔍 Audio Plugin Compatibility Report")
    print("=" * 50)
    
    plugins = [
        ("SoundDevice", SoundDeviceAudioPlugin()),
        ("AudioPlayer", AudioPlayerAudioPlugin()),
        ("Aplay", AplayAudioPlugin()),
        ("SimpleAudio", SimpleAudioPlugin()),
        ("Console", ConsoleAudioPlugin())
    ]
    
    available_plugins = []
    
    for name, plugin in plugins:
        status = "✅ Available" if plugin.is_available() else "❌ Missing"
        deps = plugin.optional_dependencies
        deps_str = f" (deps: {', '.join(deps)})" if deps else " (no deps)"
        
        print(f"{name:12} {status}{deps_str}")
        
        if plugin.is_available():
            available_plugins.append(name)
    
    print(f"\n📊 {len(available_plugins)}/{len(plugins)} plugins available")
    print(f"Available: {', '.join(available_plugins)}")
    
    if len(available_plugins) == 0:
        print("⚠️  No audio plugins available!")
        print("💡 Install audio dependencies:")
        print("   uv add 'sounddevice>=0.4.0' 'soundfile>=0.12.0' 'numpy>=1.20.0'")
        print("   uv add 'audioplayer>=0.6.0'")
        print("   uv add 'simpleaudio>=1.0.4'")
    else:
        print("✅ Audio playback capabilities available")


async def main():
    """Main demo function"""
    try:
        await audio_compatibility_test()
        await audio_plugin_demo()
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        logging.exception("Demo error")


if __name__ == "__main__":
    asyncio.run(main()) 