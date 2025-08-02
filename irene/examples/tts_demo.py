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

from ..providers.tts import (
    ConsoleTTSProvider,
    PyttsTTSProvider,
    SileroV3TTSProvider,
    SileroV4TTSProvider,
    VoskTTSProvider
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_tts_provider(provider, test_text: str = "Привет! Это тест синтеза речи."):
    """Test a single TTS provider"""
    print(f"\n{'='*70}")
    print(f"🎙️  Testing: {provider.get_provider_name()}")
    print(f"   Available: {await provider.is_available()}")
    
    if not await provider.is_available():
        print(f"   ⚠️  Provider not available - dependencies missing")
        return False
    
    try:
        # Test file generation 
        test_file = Path(f"test_{provider.get_provider_name()}.wav")
        try:
            print(f"   📁 Generating speech file: {test_file}")
            await provider.to_file(test_text, str(test_file))
            
            if test_file.exists():
                size = test_file.stat().st_size
                print(f"   📄 File generated: {size:,} bytes")
                # Clean up test file
                test_file.unlink()
                print(f"   ✅ Provider test completed successfully")
                return True
            else:
                print(f"   ⚠️  File not generated")
                return False
                
        except Exception as e:
            print(f"   ❌ File generation failed: {e}")
            return False
        
    except Exception as e:
        print(f"   ❌ Provider test failed: {e}")
        logger.exception(f"Error testing {provider.get_provider_name()}")
        return False


async def tts_provider_demo():
    """Demonstrate all TTS providers"""
    print("🎙️  Irene Voice Assistant v13 - TTS Provider Demo")
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
    
    # Create test TTS providers with minimal config
    providers = [
        ConsoleTTSProvider({}),
        PyttsTTSProvider({}), 
        SileroV3TTSProvider({}),
        SileroV4TTSProvider({}),
        VoskTTSProvider({})
    ]
    
    # Test each provider
    results = {}
    for provider in providers:
        success = await test_tts_provider(provider, test_text)
        results[provider.get_provider_name()] = success
    
    # Summary
    print(f"\n{'='*70}")
    print("🎙️  TTS Provider Demo Summary")
    print("=" * 70)
    
    available_count = sum(results.values())
    total_count = len(results)
    
    print(f"📊 {available_count}/{total_count} TTS providers available and working")
    print()
    
    for provider_name, success in results.items():
        status = "✅ Working" if success else "❌ Failed"
        print(f"  {provider_name:20} {status}")
    
    print()
    print("🎭 TTS Engine Comparison:")
    print("  Console TTS    - Debug output (no audio)")
    print("  Pyttsx3 TTS    - System TTS (cross-platform)")
    print("  Silero v3 TTS  - Neural TTS (high quality, torch 1.10+)")
    print("  Silero v4 TTS  - Neural TTS (latest, torch 2.0+)")
    print("  VOSK TTS       - Russian TTS (GPU optional)")
    print()
    print("✨ All providers implement the same TTSProvider interface")
    print("✨ Graceful fallback when dependencies missing")
    print("✨ Async operation - no blocking calls")
    print("✨ Voice selection and settings configuration")


async def tts_compatibility_test():
    """Test TTS provider compatibility and availability"""
    print("\n🔍 TTS Provider Compatibility Report")
    print("=" * 50)
    
    providers = [
        ("Console", ConsoleTTSProvider({})),
        ("Pyttsx3", PyttsTTSProvider({})),
        ("Silero v3", SileroV3TTSProvider({})),
        ("Silero v4", SileroV4TTSProvider({})),
        ("VOSK TTS", VoskTTSProvider({}))
    ]
    
    available_providers = []
    neural_providers = []
    
    for name, provider in providers:
        try:
            is_available = await provider.is_available()
            status = "✅ Available" if is_available else "❌ Missing"
            
            print(f"{name:12} {status}")
            
            if is_available:
                available_providers.append(name)
                if 'silero' in name.lower() or 'vosk' in name.lower():
                    neural_providers.append(name)
        except Exception as e:
            print(f"{name:12} ❌ Error: {e}")
    
    print(f"\n📊 {len(available_providers)}/{len(providers)} TTS providers available")
    print(f"Available: {', '.join(available_providers)}")
    
    if neural_providers:
        print(f"🧠 Neural TTS: {', '.join(neural_providers)}")
    
    if len(available_providers) == 0:
        print("⚠️  No TTS providers available!")
        print("💡 Install TTS dependencies:")
        print("   uv add 'pyttsx3>=2.90'")
        print("   uv add 'torch>=1.10.0'  # For Silero v3")
        print("   uv add 'torch>=2.0.0'   # For Silero v4") 
        print("   uv add vosk-tts         # For VOSK TTS")
    elif len(available_providers) == 1 and available_providers[0] == "Console":
        print("⚠️  Only debug TTS available!")
        print("💡 Install real TTS engines for speech output")
    else:
        print("✅ TTS capabilities available")
        if neural_providers:
            print("🎯 High-quality neural TTS ready!")


async def tts_performance_test():
    """Test TTS performance and quality"""
    print("\n⚡ TTS Performance Test")
    print("=" * 40)
    
    # Test text for performance
    performance_text = "Быстрый тест производительности синтеза речи."
    
    providers = [
        ("Pyttsx3", PyttsTTSProvider({})),
        ("Silero v3", SileroV3TTSProvider({})),
        ("Silero v4", SileroV4TTSProvider({})),
        ("VOSK TTS", VoskTTSProvider({}))
    ]
    
    for name, provider in providers:
        try:
            if not await provider.is_available():
                continue
            
            # Measure performance
            import time
            start_time = time.time()
            
            temp_path = Path(f"perf_{provider.get_provider_name()}.wav")
                
            try:
                await provider.to_file(performance_text, str(temp_path))
                end_time = time.time()
                
                duration = end_time - start_time
                file_size = temp_path.stat().st_size if temp_path.exists() else 0
                
                print(f"{name:12} {duration:.2f}s ({file_size:,} bytes)")
                
                # Clean up
                if temp_path.exists():
                    temp_path.unlink()
                    
            except Exception as e:
                print(f"{name:12} Failed: {e}")
            
        except Exception as e:
            print(f"{name:12} Error: {e}")


async def main():
    """Main demo function"""
    try:
        await tts_compatibility_test()
        await tts_provider_demo()
        await tts_performance_test()
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        logging.exception("Demo error")


if __name__ == "__main__":
    asyncio.run(main()) 