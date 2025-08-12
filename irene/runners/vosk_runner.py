"""
VOSK Runner - Speech recognition using VOSK model

Replaces legacy runva_vosk.py with modern async architecture.
Provides offline speech recognition with microphone input.
"""

import asyncio
import argparse
import logging
import sys
import queue
from pathlib import Path
from typing import Optional

from ..config.models import CoreConfig, ComponentConfig, LogLevel
from ..config.manager import ConfigManager
from ..core.engine import AsyncVACore
from ..utils.loader import get_component_status
from ..utils.logging import setup_logging


logger = logging.getLogger(__name__)


def setup_vosk_argument_parser() -> argparse.ArgumentParser:
    """Setup VOSK-specific argument parser"""
    parser = argparse.ArgumentParser(
        description="Irene Voice Assistant v13 - VOSK Speech Recognition Mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Use default model and device
  %(prog)s --model models/vosk-small # Use specific VOSK model
  %(prog)s --device 2                # Use specific audio device
  %(prog)s --list-devices            # List available audio devices
        """
    )
    
    # Configuration options
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=Path("config.toml"),
        help="Configuration file path (default: config.toml)"
    )
    
    # VOSK-specific options
    parser.add_argument(
        "--model", "-m",
        type=Path,
        default=Path("model"),
        help="Path to VOSK model directory (default: model)"
    )
    
    # Audio device options
    parser.add_argument(
        "--device", "-d",
        help="Input device (numeric ID or substring)"
    )
    parser.add_argument(
        "--samplerate", "-r",
        type=int,
        help="Audio sampling rate (default: device default)"
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit"
    )
    
    # Recording options
    parser.add_argument(
        "--save-audio", "-s",
        type=Path,
        help="Save audio recording to file"
    )
    parser.add_argument(
        "--blocksize",
        type=int,
        default=8000,
        help="Audio buffer block size (default: 8000)"
    )
    
    # Assistant options
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Reduce output verbosity"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    
    return parser


def check_vosk_dependencies() -> bool:
    """Check if VOSK dependencies are available"""
    try:
        import vosk  # type: ignore
        import sounddevice as sd  # type: ignore
        print("✅ VOSK dependencies available")
        print(f"   VOSK version: {vosk.__version__ if hasattr(vosk, '__version__') else 'unknown'}")
        print(f"   Sounddevice available: yes")
        return True
    except ImportError as e:
        print(f"❌ VOSK dependencies missing: {e}")
        print("💡 Install with: uv add irene-voice-assistant[audio-input]")
        return False


def list_audio_devices():
    """List available audio input devices"""
    try:
        import sounddevice as sd  # type: ignore
        print("🎤 Available Audio Input Devices:")
        print("=" * 50)
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                default_marker = " (default)" if i == sd.default.device[0] else ""
                print(f"{i:2d}: {device['name']}{default_marker}")
                print(f"    Channels: {device['max_input_channels']}, "
                      f"Sample rate: {device['default_samplerate']:.0f} Hz")
    except ImportError:
        print("❌ Sounddevice not available - install audio-input dependencies")


class VoskRunner:
    """
    VOSK Speech Recognition Runner
    
    Replaces legacy runva_vosk.py with modern async architecture.
    Provides continuous speech recognition with VOSK offline models.
    """
    
    def __init__(self):
        self.core: Optional[AsyncVACore] = None
        self.audio_queue: Optional[queue.Queue] = None
        self.model = None
        self.recognizer = None
        self.audio_stream = None
        self.save_file = None
        self.mic_blocked = False
        
    async def run(self, args: Optional[list[str]] = None) -> int:
        """Run VOSK speech recognition mode"""
        # Parse arguments
        parser = setup_vosk_argument_parser()
        parsed_args = parser.parse_args(args)
        
        # Set up centralized logging to logs/irene.log
        log_level = LogLevel(parsed_args.log_level)
        setup_logging(
            level=log_level,
            log_file=Path("logs/irene.log"),
            enable_console=True
        )
        
        try:
            # Handle utility options first
            if parsed_args.list_devices:
                list_audio_devices()
                return 0
            
            # Check dependencies
            if not check_vosk_dependencies():
                return 1
            
            # Check model availability
            if not parsed_args.model.exists():
                print(f"❌ VOSK model not found at: {parsed_args.model}")
                print("💡 Download a model from https://alphacephei.com/vosk/models")
                print("   and extract to 'model' directory")
                return 1
            
            # Initialize VOSK components
            await self._initialize_vosk(parsed_args)
            
            # Create assistant configuration (enable microphone)
            config = await self._create_vosk_config(parsed_args)
            
            # Create and start assistant
            self.core = AsyncVACore(config)
            
            if not parsed_args.quiet:
                print("🔧 Initializing Irene with VOSK...")
            await self.core.start()
            
            if not parsed_args.quiet:
                print("🎤 Starting speech recognition...")
                print("Press Ctrl+C to stop")
                print("#" * 60)
            
            # Start speech recognition loop
            return await self._speech_recognition_loop(parsed_args)
            
        except Exception as e:
            logger.error(f"VOSK Runner error: {e}")
            return 1
        finally:
            await self._cleanup()
    
    async def _initialize_vosk(self, args):
        """Initialize VOSK model and audio components"""
        import vosk  # type: ignore
        import sounddevice as sd  # type: ignore
        
        # Create audio queue
        self.audio_queue = queue.Queue()
        
        # Load VOSK model
        if not args.quiet:
            print(f"📦 Loading VOSK model from: {args.model}")
        self.model = vosk.Model(str(args.model))
        
        # Set up audio device
        if args.device:
            device_id = int(args.device) if args.device.isdigit() else args.device
        else:
            device_id = None
        
        # Get sample rate
        if args.samplerate:
            samplerate = args.samplerate
        else:
            device_info = sd.query_devices(device_id, 'input')
            samplerate = int(device_info['default_samplerate'])
        
        # Create recognizer
        self.recognizer = vosk.KaldiRecognizer(self.model, samplerate)
        
        # Set up audio file saving if requested
        if args.save_audio:
            self.save_file = open(args.save_audio, "wb")
        
        # Start audio stream
        def audio_callback(indata, frames, time, status):
            """Audio callback for sounddevice"""
            if status:
                logger.warning(f"Audio status: {status}")
            if not self.mic_blocked and self.audio_queue:
                self.audio_queue.put(bytes(indata))
        
        self.audio_stream = sd.RawInputStream(
            samplerate=samplerate,
            blocksize=args.blocksize,
            device=device_id,
            dtype='int16',
            channels=1,
            callback=audio_callback
        )
        
        if not args.quiet:
            print(f"🎤 Audio device: {device_id or 'default'}")
            print(f"📊 Sample rate: {samplerate} Hz")
            print(f"📏 Block size: {args.blocksize}")
    
    async def _create_vosk_config(self, args) -> CoreConfig:
        """Create configuration for VOSK mode"""
        # Force enable microphone and audio components
        components = ComponentConfig(
            microphone=True,
            tts=True,  # Enable TTS for responses
            audio_output=True,
            web_api=False  # Disable web API in VOSK mode
        )
        
        config = CoreConfig(
            components=components,
            debug=args.debug
        )
        
        return config
    
    async def _speech_recognition_loop(self, args) -> int:
        """Main speech recognition loop"""
        import json
        
        if not self.audio_stream:
            logger.error("Audio stream not initialized")
            return 1
        if not self.audio_queue:
            logger.error("Audio queue not initialized")
            return 1
        if not self.recognizer:
            logger.error("VOSK recognizer not initialized")
            return 1
        
        try:
            # Start audio stream
            self.audio_stream.start()
            
            while self.core and self.core.is_running:
                try:
                    # Get audio data (with timeout)
                    try:
                        data = self.audio_queue.get(timeout=1.0)
                    except queue.Empty:
                        # Update timers and continue
                        await asyncio.sleep(0.1)
                        continue
                    
                    # Save audio if requested
                    if self.save_file:
                        self.save_file.write(data)
                    
                    # Process audio with VOSK
                    if self.recognizer.AcceptWaveform(data):
                        # Complete recognition result
                        result = self.recognizer.Result()
                        result_data = json.loads(result)
                        text = result_data.get("text", "").strip()
                        
                        if text:
                            if not args.quiet:
                                print(f"🗣️  Recognized: '{text}'")
                            
                            # Block microphone during processing
                            self.mic_blocked = True
                            
                            try:
                                # Process command with assistant
                                if self.core:
                                    # Use unified workflow interface
                                    result = await self.core.workflow_manager.process_text_input(
                                        text=text,
                                        session_id="vosk_session",
                                        wants_audio=True,  # Vosk typically wants audio output
                                        client_context={"source": "vosk_runner"}
                                    )
                                    if result.text:
                                        print(f"Response: {result.text}")
                            except Exception as e:
                                logger.error(f"Error processing command '{text}': {e}")
                            finally:
                                # Unblock microphone
                                self.mic_blocked = False
                    else:
                        # Partial result (optional debug output)
                        if args.debug:
                            partial = self.recognizer.PartialResult()
                            partial_data = json.loads(partial)
                            partial_text = partial_data.get("partial", "")
                            if partial_text:
                                print(f"🔄 Partial: '{partial_text}'", end='\r')
                
                except Exception as e:
                    logger.error(f"Speech recognition error: {e}")
                    await asyncio.sleep(0.1)
            
            return 0
            
        except KeyboardInterrupt:
            if not args.quiet:
                print("\n\n🛑 Speech recognition stopped")
            return 0
        except Exception as e:
            logger.error(f"Speech recognition loop error: {e}")
            return 1
    
    async def _cleanup(self):
        """Clean up resources"""
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
        
        if self.save_file:
            self.save_file.close()
        
        if self.core:
            await self.core.stop()


def run_vosk() -> int:
    """Entry point for VOSK runner"""
    runner = VoskRunner()
    try:
        return asyncio.run(runner.run())
    except KeyboardInterrupt:
        print("\n👋 VOSK runner stopped")
        return 0


if __name__ == "__main__":
    sys.exit(run_vosk()) 