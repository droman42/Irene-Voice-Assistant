"""
TTS Demo - Demonstrate v13 text-to-speech capabilities

Showcases all 5 TTS engines with different backends:
- Console (debug output)
- Pyttsx3 (cross-platform TTS)
- Silero v3 (neural TTS with torch 1.10+)
- Silero v4 (neural TTS with torch 2.0+)
- VOSK TTS (Russian TTS with optional GPU)
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from ..plugins.builtin.console_tts_plugin import ConsoleTTSPlugin
from ..plugins.builtin.pyttsx_tts_plugin import PyttsTTSPlugin
from ..plugins.builtin.silero_v3_tts_plugin import SileroV3TTSPlugin
from ..plugins.builtin.silero_v4_tts_plugin import SileroV4TTSPlugin
from ..plugins.builtin.vosk_tts_plugin import VoskTTSPlugin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_tts_plugin(plugin, test_text: str = "Привет! Это тест синтеза речи."):
    """Test a single TTS plugin"""
    print(f"\n{'='*70}")
    print(f"🎙️  Testing: {plugin.name}")
    print(f"   Description: {plugin.description}")
    print(f"   Version: {plugin.version}")
    print(f"   Available: {plugin.is_available()}")
    print(f"   Supported languages: {plugin.get_supported_languages()}")
    print(f"   Supported voices: {len(plugin.get_supported_voices())}")
    
    if not plugin.is_available():
        print(f"   ⚠️  Plugin not available - dependencies missing")
        if plugin.optional_dependencies:
            print(f"   💡 Install dependencies: {', '.join(plugin.optional_dependencies)}")
        return False
    
    try:
        # Initialize plugin
        await plugin.initialize(None)
        
        # Show voice settings
        settings = plugin.get_voice_settings()
        print(f"   🎛️  Voice settings:")
        for key, value in settings.items():
            print(f"      - {key}: {value}")
        
        # Test voice listing
        voices = plugin.get_supported_voices()
        if voices:
            print(f"   🎭 Available voices:")
            for voice in voices[:5]:  # Limit to first 5
                print(f"      - {voice}")
            if len(voices) > 5:
                print(f"      ... and {len(voices) - 5} more")
        
        # Test speech generation
        print(f"   🎤 Testing speech generation...")
        test_result = await plugin.test_speech()
        
        if test_result:
            print(f"   ✅ Speech test successful")
            
            # Test file generation if requested
            test_file = Path(f"test_{plugin.name}.wav")
            try:
                print(f"   📁 Generating speech file: {test_file}")
                await plugin.to_file(test_text, test_file)
                
                if test_file.exists():
                    size = test_file.stat().st_size
                    print(f"   📄 File generated: {size:,} bytes")
                    # Clean up test file
                    test_file.unlink()
                else:
                    print(f"   ⚠️  File not generated")
                    
            except Exception as e:
                print(f"   ❌ File generation failed: {e}")
        else:
            print(f"   ❌ Speech test failed")
            
        print(f"   ✅ Plugin test completed successfully")
        return True
        
    except Exception as e:
        print(f"   ❌ Plugin test failed: {e}")
        return False
        
    finally:
        try:
            await plugin.shutdown()
        except:
            pass


async def tts_plugin_demo():
    """Demonstrate all TTS plugins"""
    print("🎙️  Irene Voice Assistant v13 - TTS Plugin Demo")
    print("=" * 70)
    print()
    print("This demo showcases all 5 TTS engines:")
    print("1. Console - Debug output (always available)")
    print("2. Pyttsx3 - Cross-platform system TTS")
    print("3. Silero v3 - Neural TTS (torch 1.10+)")
    print("4. Silero v4 - Neural TTS (torch 2.0+)")
    print("5. VOSK TTS - Russian TTS with GPU support")
    print()
    
    # Test text
    test_text = "Привет! Я Ирина, ваш голосовой ассистент. Это демонстрация синтеза речи."
    print(f"📝 Test text: \"{test_text}\"")
    print()
    
    # Create test TTS plugins
    plugins = [
        ConsoleTTSPlugin(),
        PyttsTTSPlugin(), 
        SileroV3TTSPlugin(),
        SileroV4TTSPlugin(),
        VoskTTSPlugin()
    ]
    
    # Test each plugin
    results = {}
    for plugin in plugins:
        success = await test_tts_plugin(plugin, test_text)
        results[plugin.name] = success
    
    # Summary
    print(f"\n{'='*70}")
    print("🎙️  TTS Plugin Demo Summary")
    print("=" * 70)
    
    available_count = sum(results.values())
    total_count = len(results)
    
    print(f"📊 {available_count}/{total_count} TTS plugins available and working")
    print()
    
    for plugin_name, success in results.items():
        status = "✅ Working" if success else "❌ Failed"
        print(f"  {plugin_name:20} {status}")
    
    print()
    print("🎭 TTS Engine Comparison:")
    print("  Console TTS    - Debug output (no audio)")
    print("  Pyttsx3 TTS    - System TTS (cross-platform)")
    print("  Silero v3 TTS  - Neural TTS (high quality, torch 1.10+)")
    print("  Silero v4 TTS  - Neural TTS (latest, torch 2.0+)")
    print("  VOSK TTS       - Russian TTS (GPU optional)")
    print()
    print("✨ All plugins implement the same TTSPlugin interface")
    print("✨ Graceful fallback when dependencies missing")
    print("✨ Async operation - no blocking calls")
    print("✨ Voice selection and settings configuration")


async def tts_compatibility_test():
    """Test TTS plugin compatibility and availability"""
    print("\n🔍 TTS Plugin Compatibility Report")
    print("=" * 50)
    
    plugins = [
        ("Console", ConsoleTTSPlugin()),
        ("Pyttsx3", PyttsTTSPlugin()),
        ("Silero v3", SileroV3TTSPlugin()),
        ("Silero v4", SileroV4TTSPlugin()),
        ("VOSK TTS", VoskTTSPlugin())
    ]
    
    available_plugins = []
    neural_plugins = []
    
    for name, plugin in plugins:
        status = "✅ Available" if plugin.is_available() else "❌ Missing"
        deps = plugin.optional_dependencies
        deps_str = f" (deps: {', '.join(deps)})" if deps else " (no deps)"
        
        print(f"{name:12} {status}{deps_str}")
        
        if plugin.is_available():
            available_plugins.append(name)
            if 'silero' in name.lower() or 'vosk' in name.lower():
                neural_plugins.append(name)
    
    print(f"\n📊 {len(available_plugins)}/{len(plugins)} TTS plugins available")
    print(f"Available: {', '.join(available_plugins)}")
    
    if neural_plugins:
        print(f"🧠 Neural TTS: {', '.join(neural_plugins)}")
    
    if len(available_plugins) == 0:
        print("⚠️  No TTS plugins available!")
        print("💡 Install TTS dependencies:")
        print("   uv add 'pyttsx3>=2.90'")
        print("   uv add 'torch>=1.10.0'  # For Silero v3")
        print("   uv add 'torch>=2.0.0'   # For Silero v4") 
        print("   uv add vosk-tts         # For VOSK TTS")
    elif len(available_plugins) == 1 and available_plugins[0] == "Console":
        print("⚠️  Only debug TTS available!")
        print("💡 Install real TTS engines for speech output")
    else:
        print("✅ TTS capabilities available")
        if neural_plugins:
            print("🎯 High-quality neural TTS ready!")


async def tts_performance_test():
    """Test TTS performance and quality"""
    print("\n⚡ TTS Performance Test")
    print("=" * 40)
    
    # Test text for performance
    performance_text = "Быстрый тест производительности синтеза речи."
    
    plugins = [
        ("Pyttsx3", PyttsTTSPlugin()),
        ("Silero v3", SileroV3TTSPlugin()),
        ("Silero v4", SileroV4TTSPlugin()),
        ("VOSK TTS", VoskTTSPlugin())
    ]
    
    for name, plugin in plugins:
        if not plugin.is_available():
            continue
            
        try:
            await plugin.initialize(None)
            
            # Measure performance
            import time
            start_time = time.time()
            
            with Path(f"perf_{plugin.name}.wav").open('wb') as temp_file:
                temp_path = Path(temp_file.name)
                
            try:
                await plugin.to_file(performance_text, temp_path)
                end_time = time.time()
                
                duration = end_time - start_time
                file_size = temp_path.stat().st_size if temp_path.exists() else 0
                
                print(f"{name:12} {duration:.2f}s ({file_size:,} bytes)")
                
                # Clean up
                if temp_path.exists():
                    temp_path.unlink()
                    
            except Exception as e:
                print(f"{name:12} Failed: {e}")
                
            await plugin.shutdown()
            
        except Exception as e:
            print(f"{name:12} Error: {e}")


async def main():
    """Main demo function"""
    try:
        await tts_compatibility_test()
        await tts_plugin_demo()
        await tts_performance_test()
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        logging.exception("Demo error")


if __name__ == "__main__":
    asyncio.run(main()) 