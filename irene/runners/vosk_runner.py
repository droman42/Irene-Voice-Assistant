"""
VOSK Runner - Thin wrapper for VOSK speech recognition

Modern async architecture thin wrapper that validates TOML configuration
and delegates to the existing ASR component + VOSK provider system.
Uses asset management for model downloads and component system for processing.
Now using BaseRunner for unified patterns.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, List

from ..config.models import CoreConfig, LogLevel
from ..config.manager import ConfigManager
from ..core.engine import AsyncVACore
from ..utils.loader import get_component_status
from ..utils.logging import setup_logging
from .base import BaseRunner, RunnerConfig, check_component_dependencies, print_dependency_status


logger = logging.getLogger(__name__)




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


class VoskRunner(BaseRunner):
    """
    VOSK Speech Recognition Runner - Thin Wrapper
    
    Validates TOML configuration for VOSK setup and delegates to the
    existing ASR component + VOSK provider system. Uses asset management
    for model downloads and component system for speech processing.
    Now using BaseRunner for unified patterns.
    """
    
    def __init__(self):
        runner_config = RunnerConfig(
            name="VOSK",
            description="VOSK Speech Recognition Mode",
            requires_config_file=True,
            supports_interactive=False,
            required_dependencies=["vosk", "sounddevice"]
        )
        super().__init__(runner_config)
    
    def _add_runner_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add VOSK-specific command line arguments"""
        # Utility options
        parser.add_argument(
            "--list-devices",
            action="store_true",
            help="List available audio devices and exit"
        )
    
    def _get_usage_examples(self) -> str:
        """Get usage examples for VOSK runner"""
        return """
Examples:
  %(prog)s                           # Use configuration from config.toml
  %(prog)s --config my-config.toml   # Use specific configuration file
  %(prog)s --list-devices            # List available audio devices
  %(prog)s --check-deps              # Check VOSK dependencies
        """
    
    async def _check_dependencies(self, args: argparse.Namespace) -> bool:
        """Check VOSK runner dependencies"""
        if args.check_deps:
            return check_vosk_dependencies()
        
        # For normal operation, check that VOSK is available
        try:
            import vosk  # type: ignore
            import sounddevice as sd  # type: ignore
            return True
        except ImportError:
            if not args.quiet:
                print("❌ VOSK dependencies missing")
                print("💡 Install with: uv add irene-voice-assistant[audio-input]")
            return False
    
    async def _handle_runner_utility_options(self, args: argparse.Namespace) -> Optional[int]:
        """Handle VOSK-specific utility options"""
        if args.list_devices:
            list_audio_devices()
            return 0
        return None
    
    async def _modify_config_for_runner(self, config: CoreConfig, args: argparse.Namespace) -> CoreConfig:
        """Modify configuration for VOSK-specific needs"""
        # Force-enable microphone input and required components for VOSK operation
        config.inputs.microphone = True
        config.system.microphone_enabled = True
        
        # Ensure ASR component is enabled
        config.components.asr = True
        
        # Enable required components for voice processing
        config.components.audio = True  # For potential TTS responses
        config.components.intent_system = True  # For processing recognized speech
        config.components.text_processor = True  # For text processing pipeline
        config.components.nlu = True  # For natural language understanding
        
        # Set microphone as the default input for VOSK mode
        config.inputs.default_input = "microphone"
        
        return config
    
    async def _validate_runner_specific_config(self, config: CoreConfig, args: argparse.Namespace) -> List[str]:
        """Validate VOSK-specific configuration requirements"""
        errors = []
        
        # Check ASR component enabled
        if not config.components.asr:
            errors.append("ASR component must be enabled (components.asr = true)")
        
        # Check ASR configuration
        if not config.asr.enabled:
            errors.append("ASR component must be enabled (asr.enabled = true)")
        
        if config.asr.default_provider != "vosk":
            errors.append(f"ASR default provider must be 'vosk', got '{config.asr.default_provider}' (asr.default_provider = \"vosk\")")
        
        # Check VOSK provider enabled
        vosk_config = config.asr.providers.get("vosk", {})
        if not vosk_config.get("enabled", False):
            errors.append("VOSK ASR provider must be enabled (asr.providers.vosk.enabled = true)")
        
        # Check microphone input enabled
        if not config.inputs.microphone:
            errors.append("Microphone input must be enabled (inputs.microphone = true)")
        
        if not config.inputs.microphone_config.enabled:
            errors.append("Microphone input config must be enabled (inputs.microphone_config.enabled = true)")
        
        # Check system capabilities
        if not config.system.microphone_enabled:
            errors.append("System microphone capability must be enabled (system.microphone_enabled = true)")
        
        return errors
    
    def _get_configuration_example(self) -> Optional[str]:
        """Get example configuration for VOSK runner"""
        return """
[components]
asr = true

[system]
microphone_enabled = true

[inputs]
microphone = true

[asr]
enabled = true
default_provider = "vosk"

[asr.providers.vosk]
enabled = true
default_language = "ru"
preload_models = true"""
    
    async def _post_core_setup(self, args: argparse.Namespace) -> None:
        """VOSK-specific setup after core is started"""
        # Ensure microphone input is started (guaranteed activation)
        if self.core and self.core.input_manager:
            # Check if microphone source exists and start it if not already active
            if "microphone" in self.core.input_manager._sources:
                if "microphone" not in self.core.input_manager._active_sources:
                    success = await self.core.input_manager.start_source("microphone")
                    if success:
                        logger.info("✅ Explicitly started microphone input for VOSK")
                    else:
                        logger.warning("⚠️ Failed to start microphone input - check hardware/permissions")
                else:
                    logger.info("✅ Microphone input already active")
            else:
                logger.error("❌ Microphone input source not available - check configuration and hardware")
        
        if not args.quiet:
            print("🎤 VOSK speech recognition active")
            print("   Microphone input → VOSK ASR → Intent processing")
            print("   Press Ctrl+C to stop")
            print("=" * 60)
    
    async def _execute_runner_logic(self, args: argparse.Namespace) -> int:
        """Execute VOSK runner logic"""
        try:
            # Keep the system running - microphone input handles audio capture
            # and the ASR component + VOSK provider handle speech recognition
            while self.core and self.core.is_running:
                await asyncio.sleep(1.0)
            return 0
            
        except KeyboardInterrupt:
            if not args.quiet:
                print("\n\n🛑 VOSK speech recognition stopped")
            return 0


def run_vosk() -> int:
    """Entry point for VOSK runner"""
    try:
        runner = VoskRunner()
        return asyncio.run(runner.run())
    except KeyboardInterrupt:
        print("\n👋 VOSK runner stopped")
        return 0


if __name__ == "__main__":
    sys.exit(run_vosk()) 