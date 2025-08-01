#!/usr/bin/env python3
"""
Voice Assistant Integration Demo

Demonstrates the complete voice assistant pipeline with:
- MicrophoneInput for speech recognition
- AsyncVACore for command processing  
- TTSOutput for speech synthesis
- Complete voice interaction loop
"""

import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def check_voice_assistant_readiness():
    """Check if voice assistant components are ready"""
    print("🔍 Checking Voice Assistant Readiness")
    print("=" * 40)
    
    # Check microphone
    from irene.inputs.microphone import MicrophoneInput
    mic_input = MicrophoneInput()
    
    print(f"🎤 Microphone input: {'✅ Available' if mic_input.is_available() else '❌ Not available'}")
    
    if mic_input.is_available():
        devices = mic_input.list_audio_devices()
        print(f"   📱 Audio devices found: {len(devices)}")
    else:
        print("   💡 Install with: uv add vosk sounddevice")
    
    # Check TTS
    from irene.outputs.tts import TTSOutput
    tts_output = TTSOutput()
    
    print(f"🗣️  TTS output: {'✅ Available' if tts_output.is_available() else '❌ Not available'}")
    
    if tts_output.is_available():
        voices = tts_output.get_supported_voices()
        print(f"   🎭 Voices available: {len(voices)}")
    else:
        print("   💡 Install with: uv add pyttsx3")
    
    # Check VOSK model
    model_path = Path("model")
    print(f"🧠 VOSK model: {'✅ Found' if model_path.exists() else '❌ Not found'}")
    
    if not model_path.exists():
        print("   💡 Download from: https://alphacephei.com/vosk/models")
    
    # Check AsyncVACore
    try:
        from irene.core.engine import AsyncVACore
        print("🤖 AsyncVACore: ✅ Available")
    except ImportError as e:
        print(f"🤖 AsyncVACore: ❌ Error - {e}")
    
    # Overall readiness
    ready = (mic_input.is_available() and tts_output.is_available() and 
             model_path.exists())
    
    print(f"\n🎯 Voice Assistant Ready: {'✅ Yes' if ready else '❌ No'}")
    return ready


async def demo_voice_interaction_simple():
    """Demo simple voice interaction without full core"""
    print("\n🎙️  Simple Voice Interaction Demo")
    print("=" * 40)
    
    from irene.inputs.microphone import MicrophoneInput
    from irene.outputs.tts import TTSOutput
    from irene.outputs.text import TextOutput
    
    # Initialize components
    mic_input = MicrophoneInput()
    tts_output = TTSOutput()
    text_output = TextOutput(prefix="🤖 ASSISTANT: ")
    
    if not mic_input.is_available():
        print("❌ Microphone not available - skipping voice demo")
        return
    
    model_path = Path("model")
    if not model_path.exists():
        print("❌ VOSK model not found - skipping voice demo")
        return
    
    try:
        print("🎤 Starting voice interaction...")
        print("💬 Say something! (demo runs for 15 seconds)")
        
        # Start microphone
        await mic_input.start_listening()
        
        # Simple interaction loop
        start_time = asyncio.get_event_loop().time()
        interaction_count = 0
        
        async for command in mic_input.listen():
            interaction_count += 1
            
            # Show what was heard
            await text_output.send(Response(f"Heard: '{command}'", response_type="info"))
            
            # Generate simple response
            if "привет" in command.lower() or "hello" in command.lower():
                response_text = "Привет! Как дела?"
            elif "время" in command.lower() or "time" in command.lower():
                import datetime
                now = datetime.datetime.now()
                response_text = f"Сейчас {now.strftime('%H:%M')}"
            elif "как" in command.lower() and "дела" in command.lower():
                response_text = "У меня всё отлично! Спасибо за вопрос."
            else:
                response_text = f"Я услышал: {command}"
            
            # Output response
            await text_output.send(Response(response_text, response_type="success"))
            
            # Try TTS
            if tts_output.is_available():
                try:
                    await tts_output.send(Response(response_text, response_type="tts"))
                except Exception as e:
                    logger.warning(f"TTS failed: {e}")
            
            # Stop after time limit or interactions
            current_time = asyncio.get_event_loop().time()
            if current_time - start_time > 15.0 or interaction_count >= 3:
                break
        
        await mic_input.stop_listening()
        print(f"✅ Voice interaction completed - {interaction_count} interactions")
        
    except Exception as e:
        print(f"❌ Voice demo failed: {e}")
        logger.exception("Voice demo error")


async def demo_voice_with_core():
    """Demo voice interaction with full AsyncVACore integration"""
    print("\n🤖 Full Voice Assistant Demo")
    print("=" * 40)
    
    from irene.core.engine import AsyncVACore
    from irene.config.models import CoreConfig, ComponentConfig
    from irene.inputs.microphone import MicrophoneInput
    
    # Check readiness
    mic_input = MicrophoneInput()
    if not mic_input.is_available():
        print("❌ Microphone not available - skipping full demo")
        return
    
    model_path = Path("model")
    if not model_path.exists():
        print("❌ VOSK model not found - skipping full demo")
        return
    
    try:
        # Create voice-enabled configuration
        config = CoreConfig(
            components=ComponentConfig(
                microphone=True,
                tts=True,
                audio_output=True,
                web_api=False
            ),
            debug=True
        )
        
        # Initialize core
        core = AsyncVACore(config)
        await core.start()
        
        print("🎤 Full voice assistant ready!")
        print("💬 Try commands: 'привет', 'время', 'таймер 5 секунд', 'quit'")
        
        # Start microphone input
        await core.input_manager.start_source("microphone")
        
        # Voice interaction loop
        interaction_count = 0
        start_time = asyncio.get_event_loop().time()
        
        while interaction_count < 5:  # Limit for demo
            try:
                # Get command from any input source
                source_name, command = await asyncio.wait_for(
                    core.input_manager.get_next_input(), timeout=10.0
                )
                interaction_count += 1
                
                print(f"🗣️  Voice command from {source_name}: '{command}'")
                
                # Process with full core
                await core.process_command(command)
                
                # Check for quit
                if command.lower() in ['quit', 'выход', 'stop']:
                    break
                
            except asyncio.TimeoutError:
                print("⏰ No voice input in 10 seconds - ending demo")
                break
            except Exception as e:
                logger.error(f"Error in voice loop: {e}")
                break
        
        # Stop and cleanup
        await core.input_manager.stop_source("microphone")
        await core.stop()
        
        print(f"✅ Full voice assistant demo completed - {interaction_count} interactions")
        
    except Exception as e:
        print(f"❌ Full voice demo failed: {e}")
        logger.exception("Full voice demo error")


async def demo_microphone_audio_pipeline():
    """Demo the complete audio pipeline"""
    print("\n🔊 Audio Pipeline Demo")
    print("=" * 40)
    
    from irene.inputs.microphone import MicrophoneInput
    
    mic_input = MicrophoneInput()
    
    if not mic_input.is_available():
        print("❌ Audio pipeline demo requires microphone dependencies")
        return
    
    # Show detailed audio setup
    print("📊 Audio Configuration:")
    settings = mic_input.get_settings()
    for key, value in settings.items():
        print(f"  {key}: {value}")
    
    # List available devices
    devices = mic_input.list_audio_devices()
    print(f"\n📱 Available audio devices ({len(devices)}):")
    for device in devices:
        print(f"  {device['id']}: {device['name']} "
              f"({device['channels']}ch, {device['samplerate']}Hz)")
    
    # Test recognition status monitoring
    if Path("model").exists():
        print("\n📊 Recognition Status Monitoring:")
        
        # Before initialization
        status = await mic_input.get_recognition_info()
        print("Before start:", {k: v for k, v in status.items() 
                              if k != "audio_devices"})
        
        # After initialization
        await mic_input.start_listening()
        status = await mic_input.get_recognition_info()
        print("After start:", {k: v for k, v in status.items() 
                             if k != "audio_devices"})
        
        await mic_input.stop_listening()
        status = await mic_input.get_recognition_info()
        print("After stop:", {k: v for k, v in status.items() 
                            if k != "audio_devices"})


async def main():
    """Run comprehensive voice assistant demo"""
    print("🎤 Voice Assistant Integration Demo")
    print("=" * 50)
    
    try:
        # Check readiness
        ready = await check_voice_assistant_readiness()
        
        # Audio pipeline demo (works without model)
        await demo_microphone_audio_pipeline()
        
        if ready:
            # Interactive demos
            print("\n⚠️  Interactive voice demos available!")
            
            response = input("\nRun simple voice interaction demo? (y/n): ")
            if response.lower().startswith('y'):
                await demo_voice_interaction_simple()
            
            response = input("\nRun full voice assistant demo? (y/n): ")
            if response.lower().startswith('y'):
                await demo_voice_with_core()
        else:
            print("\n💡 To enable voice features:")
            print("   1. Install dependencies: uv add vosk sounddevice pyttsx3")
            print("   2. Download VOSK model to 'model/' directory")
            print("   3. Run this demo again")
        
        print("\n✅ Voice Assistant Demo completed!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        logger.exception("Demo error details")


if __name__ == "__main__":
    # Import Response here to avoid circular imports in demo functions
    from irene.outputs.base import Response
    asyncio.run(main()) 