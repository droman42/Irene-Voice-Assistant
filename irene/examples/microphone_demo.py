#!/usr/bin/env python3
"""
Microphone Input Demo

Demonstrates the VOSK speech recognition integration with:
- Device discovery and listing
- Real-time speech recognition
- Integration with InputManager and OutputManager
- Error handling for missing dependencies
- Recognition status monitoring
"""

import asyncio
import logging
from typing import Optional
from pathlib import Path

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_microphone_availability():
    """Test microphone component availability"""
    print("\n=== Testing Microphone Availability ===")
    
    from irene.inputs.microphone import MicrophoneInput
    
    mic_input = MicrophoneInput()
    
    print(f"Microphone available: {mic_input.is_available()}")
    
    if mic_input.is_available():
        print("✅ VOSK and sounddevice dependencies found")
        
        # List available devices
        devices = mic_input.list_audio_devices()
        print(f"\n📱 Available audio input devices ({len(devices)}):")
        for device in devices:
            print(f"  {device['id']}: {device['name']} "
                  f"({device['channels']} channels, {device['samplerate']} Hz)")
            
        # Test basic functionality
        test_result = await mic_input.test_input()
        print(f"🧪 Microphone test: {'✅ Passed' if test_result else '❌ Failed'}")
        
    else:
        print("❌ VOSK or sounddevice dependencies missing")
        print("💡 Install with: uv add vosk sounddevice")


async def test_microphone_configuration():
    """Test microphone configuration options"""
    print("\n=== Testing Microphone Configuration ===")
    
    from irene.inputs.microphone import MicrophoneInput
    
    mic_input = MicrophoneInput(
        asr_plugin=None,  # No ASR plugin for config demo
        device_id=None,  # Use default device
        samplerate=16000,
        blocksize=8000
    )
    
    # Display current settings
    settings = mic_input.get_settings()
    print("🔧 Current microphone settings:")
    for key, value in settings.items():
        print(f"  {key}: {value}")
    
    # Test configuration changes
    await mic_input.configure_input(
        samplerate=22050,
        blocksize=4000
    )
    
    updated_settings = mic_input.get_settings()
    print("\n🔄 Updated settings:")
    for key, value in updated_settings.items():
        print(f"  {key}: {value}")


async def test_speech_recognition_basic():
    """Test basic speech recognition functionality with ASR plugin integration"""
    print("\n=== Testing Basic Speech Recognition ===")
    
    from irene.inputs.microphone import MicrophoneInput
    
    mic_input = MicrophoneInput()
    
    if not mic_input.is_available():
        print("❌ Microphone not available - skipping speech recognition test")
        return
    
    # Note: ASR processing now handled by UniversalASRPlugin
    print("🔄 Note: In refactored architecture, speech recognition requires:")
    print("   1. MicrophoneInput for audio capture")
    print("   2. UniversalASRPlugin for speech-to-text processing")
    print("   3. Integration through InputManager/OutputManager")
    
    try:
        print("🎤 Testing audio capture (without ASR)...")
        
        await mic_input.start_listening()
        
        # Test audio capture for a short period
        info = await mic_input.get_recognition_info()
        print(f"📊 Audio capture status:")
        for key, value in info.items():
            if key != "audio_devices":  # Skip device list for brevity
                print(f"   {key}: {value}")
        
        # Note about ASR integration
        print("🔗 For speech recognition, use test_microphone_with_managers()")
        print("   which demonstrates full integration with InputManager/OutputManager")
        
        await mic_input.stop_listening()
        print("✅ Audio capture test completed")
        
    except Exception as e:
        print(f"❌ Audio capture test failed: {e}")
        logger.exception("Audio capture error details")


async def test_microphone_with_managers():
    """Test microphone integration with InputManager and OutputManager"""
    print("\n=== Testing Microphone with Managers ===")
    
    from irene.inputs.base import InputManager
    from irene.outputs.base import OutputManager
    from irene.inputs.microphone import MicrophoneInput
    
    # Mock component manager
    class MockComponentManager:
        def has_component(self, name: str) -> bool:
            return True
    
    # Initialize managers
    input_manager = InputManager(MockComponentManager())
    output_manager = OutputManager(MockComponentManager())
    
    await input_manager.initialize()
    await output_manager.initialize()
    
    # Show discovered sources
    available_sources = input_manager.get_available_sources()
    print(f"📥 Available input sources: {available_sources}")
    
    # Check if microphone was discovered
    if "microphone" in available_sources:
        print("✅ Microphone discovered by InputManager")
        
        # Get microphone info
        mic_info = input_manager.get_source_info("microphone")
        print(f"🎤 Microphone info: {mic_info}")
        
        # Note: Speech recognition requires UniversalASRPlugin
        print("\n🎙️  Note: Full speech recognition requires UniversalASRPlugin")
        print("ℹ️  This demo shows InputManager/OutputManager integration without ASR")
        
        try:
            # Start microphone source (audio capture only)
            await input_manager.start_source("microphone")
            
            await output_manager.send_response(
                "🎤 Microphone integration test started (audio capture only)",
                response_type="info"
            )
            
            # Test audio stream status
            mic_source = None
            for source in input_manager._sources.values():
                if hasattr(source, 'get_input_type') and source.get_input_type() == "microphone":
                    mic_source = source
                    break
                    
            if mic_source and hasattr(mic_source, 'get_recognition_info'):
                info = await mic_source.get_recognition_info()  # type: ignore
                await output_manager.send_response(
                    f"📊 Audio stream active: {info.get('audio_stream_active', False)}",
                    response_type="info"
                )
            
            # Wait briefly to show audio capture is working
            await asyncio.sleep(2)
            
            await input_manager.stop_source("microphone")
            print("✅ Integrated microphone test completed")
            
        except Exception as e:
            print(f"❌ Integrated test failed: {e}")
            logger.exception("Integration test error")
    else:
        print("❌ Microphone not discovered by InputManager")


async def test_recognition_status_monitoring():
    """Test recognition status monitoring"""
    print("\n=== Testing Recognition Status Monitoring ===")
    
    from irene.inputs.microphone import MicrophoneInput
    
    mic_input = MicrophoneInput()
    
    if not mic_input.is_available():
        print("❌ Microphone not available - skipping status monitoring test")
        return
    
    # Test status before initialization
    status_before = await mic_input.get_recognition_info()
    print("📊 Status before initialization:")
    for key, value in status_before.items():
        if key != "audio_devices":  # Skip device list for brevity
            print(f"  {key}: {value}")
    
    try:
        # Initialize and test status
        await mic_input.start_listening()
        
        status_after = await mic_input.get_recognition_info()
        print("\n📊 Status after initialization:")
        for key, value in status_after.items():
            if key != "audio_devices":
                print(f"  {key}: {value}")
        
        await mic_input.stop_listening()
        
        status_stopped = await mic_input.get_recognition_info()
        print("\n📊 Status after stopping:")
        for key, value in status_stopped.items():
            if key != "audio_devices":
                print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"❌ Status monitoring test failed: {e}")


async def test_error_handling():
    """Test error handling scenarios"""
    print("\n=== Testing Error Handling ===")
    
    from irene.inputs.microphone import MicrophoneInput
    
    # Test with invalid device ID
    print("🧪 Testing with no ASR plugin...")
    mic_input = MicrophoneInput(asr_plugin=None)
    
    if mic_input.is_available():
        try:
            await mic_input.start_listening()
            await mic_input.stop_listening()
            print("✅ Successfully handled microphone without ASR plugin")
        except Exception as e:
            print(f"✅ Correctly handled missing ASR plugin: {e}")
    
    # Test with invalid device ID
    print("\n🧪 Testing invalid device ID...")
    mic_input2 = MicrophoneInput(device_id=9999)  # Likely invalid device ID
    
    if mic_input2.is_available():
        try:
            await mic_input2.start_listening()
            await mic_input2.stop_listening()
            print("❌ Expected error for invalid device ID")
        except Exception as e:
            print(f"✅ Correctly handled invalid device ID: {e}")


async def main():
    """Run all microphone tests"""
    print("🎤 Microphone Input Demonstration")
    print("=" * 50)
    
    try:
        # Test basic availability
        await test_microphone_availability()
        
        # Test configuration
        await test_microphone_configuration()
        
        # Test managers integration
        await test_microphone_with_managers()
        
        # Test status monitoring
        await test_recognition_status_monitoring()
        
        # Test error handling
        await test_error_handling()
        
        # Interactive audio capture test
        from irene.inputs.microphone import MicrophoneInput
        mic_input = MicrophoneInput()
        
        if mic_input.is_available():
            print("\n⚠️  Interactive audio capture test available.")
            response = input("Run audio capture test? (y/n): ")
            if response.lower().startswith('y'):
                await test_speech_recognition_basic()
        
        print("\n✅ Microphone Demo completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        logger.exception("Demo error details")


if __name__ == "__main__":
    asyncio.run(main()) 