#!/usr/bin/env python3
"""
Utilities Migration Demo

Demonstrates Phase I migrated utilities:
- Text processing and number-to-text conversion
- Audio processing helpers  
- Component integration
- Both sync and async versions

Usage:
    python -m irene.examples.utilities_demo
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from irene.utils import (
    # Text processing
    all_num_to_text, 
    all_num_to_text_async,
    num_to_text_ru,
    decimal_to_text_ru,
    
    # Audio helpers
    normalize_volume,
    format_audio_duration,
    get_audio_devices,
    get_default_audio_device,
    calculate_audio_buffer_size,
    test_audio_playback_capability,
    AudioFormatConverter,
    
    # Component loading
    get_component_status,
    suggest_installation
)


def demo_text_processing():
    """Demonstrate migrated text processing functionality."""
    print("📝 Text Processing Migration Demo")
    print("=" * 50)
    
    test_cases = [
        "У меня 123 рубля",
        "Температура -5.5 градусов", 
        "Скидка 25% на товары от 1000 до 5000 рублей",
        "Время: 14:30, дата: 2024-01-15"
    ]
    
    for text in test_cases:
        result = all_num_to_text(text)
        print(f"Original: {text}")
        print(f"Converted: {result}")
        print()


def demo_audio_helpers():
    """Demonstrate audio processing helpers."""
    print("🔊 Audio Processing Helpers Demo")
    print("=" * 50)
    
    # Volume normalization
    volumes = [None, 50, 100, 0.7, 1.2, -10]
    print("Volume normalization:")
    for vol in volumes:
        normalized = normalize_volume(vol)
        print(f"  {vol} → {normalized:.2f}")
    print()
    
    # Duration formatting
    durations = [30, 90, 3661, 7323.5]
    print("Duration formatting:")
    for dur in durations:
        formatted = format_audio_duration(dur)
        print(f"  {dur}s → {formatted}")
    print()
    
    # Buffer size calculation
    sample_rates = [8000, 16000, 44100, 48000]
    print("Buffer size calculation (100ms):")
    for sr in sample_rates:
        buffer = calculate_audio_buffer_size(sr, 100.0)
        print(f"  {sr}Hz → {buffer} samples")
    print()
    
    # Format support checking
    formats = ['wav', 'mp3', 'ogg', 'flac', 'xyz']
    print("Format support:")
    for fmt in formats:
        supported = AudioFormatConverter.supports_format(fmt)
        status = "✅" if supported else "❌"
        print(f"  {status} {fmt}")
    print()


async def demo_async_functions():
    """Demonstrate async versions of utilities."""
    print("⚡ Async Utilities Demo")
    print("=" * 50)
    
    # Async text processing
    test_text = "Заработал 50000 рублей за 30 дней"
    result = await all_num_to_text_async(test_text)
    print(f"Async text processing:")
    print(f"  Original: {test_text}")
    print(f"  Converted: {result}")
    print()
    
    # Async audio device detection
    print("Audio devices (async):")
    try:
        devices = await get_audio_devices()
        for device in devices[:3]:  # Show first 3 devices
            print(f"  • {device['name']} ({device['channels']} channels, {device['sample_rate']}Hz)")
        
        default_device = await get_default_audio_device()
        if default_device:
            print(f"  Default: {default_device['name']}")
    except Exception as e:
        print(f"  Device detection failed: {e}")
    print()
    
    # Audio capabilities test
    print("Audio playback capabilities:")
    capabilities = await test_audio_playback_capability()
    print(f"  Devices available: {capabilities['devices_available']}")
    print(f"  Supported formats: {', '.join(capabilities['supported_formats'])}")
    print("  Libraries available:")
    for lib, available in capabilities['libraries_available'].items():
        status = "✅" if available else "❌"
        print(f"    {status} {lib}")
    print()


def demo_component_status():
    """Demonstrate component dependency checking."""
    print("🔍 Component Dependencies Demo")  
    print("=" * 50)
    
    status = get_component_status()
    
    for component, info in status.items():
        status_icon = "✅" if info["available"] else "❌"
        print(f"{status_icon} {component.capitalize()}: {'Available' if info['available'] else 'Not Available'}")
        
        if not info["available"]:
            suggestion = suggest_installation(component)
            if suggestion:
                print(f"   💡 Install with: {suggestion}")
    print()


def demo_integration_examples():
    """Show how migrated utilities integrate with v13 plugins."""
    print("🔗 Integration Examples")
    print("=" * 50)
    
    print("Example 1: TTS Plugin Text Normalization")
    print("```python")
    print("# In TTS plugin:")
    print("from irene.utils import all_num_to_text_async")
    print("normalized = await all_num_to_text_async(text, language='ru')")
    print("```")
    print()
    
    print("Example 2: Audio Plugin Volume Control")
    print("```python") 
    print("# In audio plugin:")
    print("from irene.utils import normalize_volume")
    print("volume = normalize_volume(user_volume)  # 0.0-1.0 range")
    print("```")
    print()
    
    print("Example 3: Component Dependency Checking")
    print("```python")
    print("# In plugin initialization:")
    print("from irene.utils import get_component_status")
    print("if get_component_status()['audio_output']['available']:")
    print("    # Initialize audio functionality")
    print("```")
    print()


async def main():
    """Run all utility demonstrations."""
    print("🎯 Irene Voice Assistant - Utilities Migration Demo")
    print("=" * 70)
    print("Phase I: Essential Utilities Migration - COMPLETED ✅")
    print("=" * 70)
    print()
    
    # Synchronous demos
    demo_text_processing()
    demo_audio_helpers() 
    demo_component_status()
    demo_integration_examples()
    
    # Async demo
    await demo_async_functions()
    
    print("✅ All Phase I utilities migration demos completed successfully!")
    print()
    print("📋 Phase I Summary:")
    print("   ✅ Text processing utilities (Russian number-to-text)")
    print("   ✅ Audio processing helpers (volume, devices, formats)")
    print("   ✅ Component dependency management")
    print("   ✅ Async versions for v13 integration")
    print("   ✅ Legacy compatibility maintained")
    print()
    print("🎉 Phase I: Essential Utilities Migration - COMPLETE!")
    print("   Ready for next phase of v13 migration.")


if __name__ == "__main__":
    asyncio.run(main()) 