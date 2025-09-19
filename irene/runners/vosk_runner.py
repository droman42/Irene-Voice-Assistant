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
    """List available audio input devices (legacy function for CLI)"""
    from ..utils.audio_devices import print_audio_devices, is_audio_available
    
    if not is_audio_available():
        print("❌ Sounddevice not available - install audio-input dependencies")
        return
    
    print_audio_devices()


class VoskRunner(BaseRunner):
    """
    VOSK Speech Recognition Runner - Thin Wrapper
    
    This runner ALWAYS uses microphone input only, regardless of config file settings.
    It overrides any input configuration to ensure only microphone input is enabled.
    
    Validates TOML configuration for VOSK setup and delegates to the
    existing ASR component + VOSK provider system. Uses asset management
    for model downloads and component system for speech processing.
    Now using BaseRunner for unified patterns.
    """
    
    def __init__(self):
        runner_config = RunnerConfig(
            name="VOSK",
            description="VOSK Speech Recognition Mode (microphone input only)",
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
  %(prog)s                           # Use configuration from config.toml (microphone input only)
  %(prog)s --config my-config.toml   # Use specific configuration file (microphone input only)
  %(prog)s --list-devices            # List available audio devices
  %(prog)s --check-deps              # Check VOSK dependencies

Note: VOSK runner always uses microphone input only, regardless of config file settings.
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
        # VOSK Runner ALWAYS forces microphone-only input configuration
        # This overrides any input configuration from the config file
        config.inputs.microphone = True
        config.inputs.web = False
        config.inputs.cli = False
        config.inputs.default_input = "microphone"
        
        # Enable microphone system capability
        config.system.microphone_enabled = True
        
        # Ensure ASR component is enabled for VOSK operation
        config.components.asr = True
        
        # Enable required components for voice processing
        config.components.audio = True  # For potential TTS responses
        config.components.intent_system = True  # For processing recognized speech
        config.components.text_processor = True  # For text processing pipeline
        config.components.nlu = True  # For natural language understanding
        
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
preload_models = true

# Note: VOSK runner always uses microphone input only.
# Other input configurations will be overridden."""
    
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
        
        # CRITICAL FIX: Start audio workflow for VOSK processing
        await self._start_vosk_audio_workflow()
        
        if not args.quiet:
            print("🎤 VOSK speech recognition active (microphone input only)")
            print("   Microphone input → VOSK ASR → Intent processing")
            print("💻 Input mode: Microphone only (other inputs disabled)")
            print("   Press Ctrl+C to stop")
            print("=" * 60)
    
    async def _start_vosk_audio_workflow(self) -> None:
        """
        Start audio workflow for VOSK processing with intelligent wake word handling.
        
        This method fixes the core issue where audio gets stuck in wake word detection
        when voice_trigger component is disabled. It automatically sets skip_wake_word=True
        when voice_trigger is not available, ensuring audio flows directly to ASR.
        """
        if not self.core or not self.core.workflow_manager:
            logger.error("❌ Core or workflow manager not available for VOSK audio processing")
            return
            
        # Check if voice_trigger component is available and enabled
        voice_trigger_available = False
        if self.core.component_manager:
            voice_trigger_component = self.core.component_manager.get_component('voice_trigger')
            voice_trigger_available = voice_trigger_component is not None
            
        # CRITICAL FIX: Automatically skip wake word detection if voice_trigger is disabled
        # This prevents the audio processing from getting stuck in the wake word waiting loop
        skip_wake_word = not voice_trigger_available
        
        logger.info(f"🔧 VOSK audio workflow configuration:")
        logger.info(f"   Voice trigger available: {voice_trigger_available}")
        logger.info(f"   Skip wake word detection: {skip_wake_word}")
        logger.info(f"   Audio flow: Microphone → {'Direct ASR' if skip_wake_word else 'Voice Trigger → ASR'}")
        
        try:
            # Get microphone input source
            mic_input = self.core.input_manager._sources.get("microphone")
            if not mic_input:
                logger.error("❌ Microphone input source not found for VOSK workflow")
                return
            
            # Get audio stream from microphone input
            audio_stream = self.core.workflow_manager._get_audio_stream(mic_input)
            
            # Start audio processing through workflow manager with intelligent skip_wake_word setting
            async for result in self.core.workflow_manager.process_audio_stream(
                audio_stream=audio_stream,
                session_id="vosk_session",
                skip_wake_word=skip_wake_word,  # Key fix: bypass wake word when voice_trigger disabled
                wants_audio=True,
                client_context={"source": "vosk_runner", "runner": "vosk"}
            ):
                # Process results as they come in
                if result.text and result.text.strip():
                    logger.info(f"✅ VOSK processed: '{result.text}'")
                    if result.action_metadata:
                        logger.debug(f"📋 Action metadata: {result.action_metadata}")
                
        except Exception as e:
            logger.error(f"❌ Failed to start VOSK audio workflow: {e}")
            raise
    
    async def _execute_runner_logic(self, args: argparse.Namespace) -> int:
        """Execute VOSK runner logic"""
        try:
            # The audio workflow is already running in _start_vosk_audio_workflow()
            # Just keep the system running while processing audio
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