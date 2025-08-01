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
        model_path="model",
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
    """Test basic speech recognition functionality"""
    print("\n=== Testing Basic Speech Recognition ===")
    
    from irene.inputs.microphone import MicrophoneInput
    
    mic_input = MicrophoneInput()
    
    if not mic_input.is_available():
        print("❌ Microphone not available - skipping speech recognition test")
        return
    
    # Check if model exists
    model_path = Path("model")
    if not model_path.exists():
        print(f"❌ VOSK model not found at '{model_path}' - skipping speech recognition test")
        print("💡 Download a model from https://alphacephei.com/vosk/models")
        return
    
    try:
        print("🎤 Starting speech recognition...")
        print("💬 Speak something (test will run for 10 seconds)")
        
        await mic_input.start_listening()
        
        # Listen for speech for 10 seconds
        recognition_count = 0
        start_time = asyncio.get_event_loop().time()
        
        async for command in mic_input.listen():
            recognition_count += 1
            print(f"🗣️  #{recognition_count}: '{command}'")
            
            # Stop after 10 seconds or 3 recognitions
            current_time = asyncio.get_event_loop().time()
            if current_time - start_time > 10.0 or recognition_count >= 3:
                break
        
        await mic_input.stop_listening()
        print(f"✅ Speech recognition completed - {recognition_count} commands recognized")
        
    except Exception as e:
        print(f"❌ Speech recognition test failed: {e}")
        logger.exception("Speech recognition error details")


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
        
        # Test if VOSK model exists
        model_path = Path("model")
        if model_path.exists():
            print("\n🎙️  Starting integrated microphone test (5 seconds)...")
            
            try:
                # Start microphone source
                await input_manager.start_source("microphone")
                
                await output_manager.send_response(
                    "🎤 Microphone integration test started. Speak a command!",
                    response_type="info"
                )
                
                # Listen for commands
                command_count = 0
                start_time = asyncio.get_event_loop().time()
                
                while command_count < 2:  # Limit for demo
                    try:
                        source_name, command = await asyncio.wait_for(
                            input_manager.get_next_input(), timeout=5.0
                        )
                        command_count += 1
                        
                        await output_manager.send_response(
                            f"🗣️  Heard from {source_name}: '{command}'",
                            response_type="success"
                        )
                        
                        # Test TTS if available
                        if output_manager.has_tts():
                            await output_manager.speak(f"I heard: {command}")
                        
                    except asyncio.TimeoutError:
                        await output_manager.send_response(
                            "⏰ No speech detected in 5 seconds",
                            response_type="warning"
                        )
                        break
                
                await input_manager.stop_source("microphone")
                print("✅ Integrated microphone test completed")
                
            except Exception as e:
                print(f"❌ Integrated test failed: {e}")
                logger.exception("Integration test error")
        else:
            print(f"ℹ️  VOSK model not found at '{model_path}' - skipping integrated test")
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
    
    model_path = Path("model")
    if model_path.exists():
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
    else:
        print(f"ℹ️  VOSK model not found at '{model_path}' - status shows model not loaded")


async def test_error_handling():
    """Test error handling scenarios"""
    print("\n=== Testing Error Handling ===")
    
    from irene.inputs.microphone import MicrophoneInput
    
    # Test with invalid model path
    print("🧪 Testing invalid model path...")
    mic_input = MicrophoneInput(model_path="nonexistent_model")
    
    if mic_input.is_available():
        try:
            await mic_input.start_listening()
            print("❌ Expected error for invalid model path")
        except Exception as e:
            print(f"✅ Correctly handled invalid model path: {e}")
    
    # Test with invalid device ID
    print("\n🧪 Testing invalid device ID...")
    mic_input2 = MicrophoneInput(device_id=9999)  # Likely invalid device ID
    
    if mic_input2.is_available():
        try:
            await mic_input2.start_listening()
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
        
        # Interactive speech recognition test
        from irene.inputs.microphone import MicrophoneInput
        mic_input = MicrophoneInput()
        model_path = Path("model")
        
        if mic_input.is_available() and model_path.exists():
            print("\n⚠️  Interactive speech recognition test available.")
            response = input("Run speech recognition test? (y/n): ")
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