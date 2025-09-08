"""
CLI Runner - Command line interface for Irene

Enhanced with dependency checking and graceful fallback handling.
Now using BaseRunner for unified patterns.
"""

import asyncio
import logging
import argparse
import sys
from pathlib import Path
from typing import Optional, List

from prompt_toolkit import prompt

from ..config.models import CoreConfig, ComponentConfig, LogLevel
from ..config.manager import ConfigManager
from ..core.engine import AsyncVACore
from ..utils.loader import get_component_status, suggest_installation
from ..utils.logging import setup_logging
from .base import BaseRunner, RunnerConfig, InteractiveRunnerMixin, check_component_dependencies, print_dependency_status




def check_dependencies() -> bool:
    """
    Check and report component dependencies.
    
    Returns:
        True if all requested components are available
    """
    print("🔍 Checking Component Dependencies")
    print("=" * 50)
    
    status = get_component_status()
    all_available = True
    
    for component, info in status.items():
        status_icon = "✅" if info["available"] else "❌"
        print(f"{status_icon} {component.capitalize()}: {'Available' if info['available'] else 'Not Available'}")
        
        if info["available"]:
            print(f"   Dependencies: {', '.join(info['dependencies'])}")
        else:
            all_available = False
            print(f"   Missing: {', '.join(info['missing'])}")
            suggestion = suggest_installation(component)
            if suggestion:
                print(f"   💡 Install with: {suggestion}")
        print()
    
    if all_available:
        print("🎉 All components are available!")
    else:
        print("⚠️  Some components are missing. Irene will run with available components only.")
    
    return all_available


def list_deployment_profiles():
    """List available deployment profiles"""
    print("🚀 Available Deployment Profiles")
    print("=" * 40)
    
    profiles = [
        ("headless", "Text processing only (no dependencies)"),
        ("api-only", "Web API server (requires fastapi, uvicorn)"),
        ("tts-only", "Text-to-speech output (requires pyttsx3)"),
        ("voice", "Full voice assistant (all components)"),
        ("custom", "Custom configuration via config file")
    ]
    
    for name, description in profiles:
        print(f"📋 {name}")
        print(f"   {description}")
        
        # Check availability
        if name == "headless":
            print("   ✅ Always available")
        elif name == "custom":
            print("   ⚙️  Depends on configuration")
        else:
            # Check specific requirements
            status = get_component_status()
            required_components = {
                "api-only": ["web_api"],
                "tts-only": ["tts"],
                "voice": ["microphone", "tts", "web_api"]
            }
            
            if name in required_components:
                missing = []
                for comp in required_components[name]:
                    if not status.get(comp, {}).get("available", False):
                        missing.append(comp)
                
                if missing:
                    print(f"   ❌ Missing: {', '.join(missing)}")
                    for comp in missing:
                        suggestion = suggest_installation(comp)
                        if suggestion:
                            print(f"      Install: {suggestion}")
                else:
                    print("   ✅ Available")
        print()






class CLIRunner(BaseRunner, InteractiveRunnerMixin):
    """
    CLI Runner class - Provides command line interface for Irene.
    
    Now using BaseRunner for unified patterns and InteractiveRunnerMixin
    for interactive mode support.
    """
    
    def __init__(self):
        runner_config = RunnerConfig(
            name="CLI",
            description="Command line interface for Irene",
            requires_config_file=False,
            supports_interactive=True,
            required_dependencies=["core"]
        )
        super().__init__(runner_config)
    
    def _add_runner_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add CLI-specific command line arguments"""
        # Deployment profile shortcuts
        profile_group = parser.add_mutually_exclusive_group()
        profile_group.add_argument(
            "--headless",
            action="store_true",
            help="Run in headless mode (no audio, no web API)"
        )
        profile_group.add_argument(
            "--api-only",
            action="store_true", 
            help="Run as API server only (no audio components)"
        )
        profile_group.add_argument(
            "--voice",
            action="store_true",
            help="Full voice assistant mode (all components if available)"
        )
        
        # Utility options
        parser.add_argument(
            "--list-profiles",
            action="store_true",
            help="List available deployment profiles and exit"
        )
        
        # Command execution options
        parser.add_argument(
            "--command", "-e",
            type=str,
            help="Execute a single command and exit (like legacy runva_cmdline.py)"
        )
        parser.add_argument(
            "--interactive", "-i",
            action="store_true",
            help="Force interactive mode even when --command is specified"
        )
        parser.add_argument(
            "--test-greeting",
            action="store_true",
            help="Test greeting command and exit (legacy compatibility)"
        )
        parser.add_argument(
            "--enable-tts", 
            action="store_true",
            help="Enable TTS audio output for CLI responses (Phase 5 support)"
        )
        
        # Data directory override
        parser.add_argument(
            "--data-dir",
            type=Path,
            help="Override data directory path"
        )
    
    def _get_usage_examples(self) -> str:
        """Get usage examples for CLI runner"""
        return """
Examples:
  %(prog)s                           # Start with default config
  %(prog)s --config config.toml      # Use specific config file
  %(prog)s --headless                # Run in headless mode
  %(prog)s --api-only                # Run as API server only
  %(prog)s --check-deps              # Check component dependencies
  %(prog)s --voice                   # Full voice assistant mode
        """
    
    async def _check_dependencies(self, args: argparse.Namespace) -> bool:
        """Check CLI runner dependencies"""
        if args.check_deps:
            # Full dependency check for utility option
            success = check_dependencies()
            return success
        
        # Basic core dependencies always available for CLI
        return True
    
    async def _handle_runner_utility_options(self, args: argparse.Namespace) -> Optional[int]:
        """Handle CLI-specific utility options"""
        if args.list_profiles:
            list_deployment_profiles()
            return 0
        return None
    
    async def _modify_config_for_runner(self, config: CoreConfig, args: argparse.Namespace) -> CoreConfig:
        """Modify configuration for CLI-specific needs"""
        # Handle deployment profile overrides (V14 Architecture)
        if args.headless:
            # Headless: minimal components, no audio/voice
            config.components = ComponentConfig(
                tts=False, audio=False, asr=False, voice_trigger=False,
                llm=False, nlu=False, text_processor=False, intent_system=True
            )
            # Also update system capabilities
            config.system.microphone_enabled = False
            config.system.audio_playback_enabled = False
            config.system.web_api_enabled = False
            # Update input sources
            config.inputs.microphone = False
            config.inputs.web = False
            config.inputs.cli = True
            config.inputs.default_input = "cli"
        elif args.api_only:
            # API-only: text processing only, no voice components
            config.components = ComponentConfig(
                tts=False, audio=False, asr=False, voice_trigger=False,
                llm=True, nlu=True, text_processor=True, intent_system=True
            )
            # Update system capabilities  
            config.system.microphone_enabled = False
            config.system.audio_playback_enabled = False
            config.system.web_api_enabled = True
            # Update input sources
            config.inputs.microphone = False
            config.inputs.web = True
            config.inputs.cli = True
            config.inputs.default_input = "web"
        elif args.voice:
            # Voice: full voice assistant with all components
            config.components = ComponentConfig(
                tts=True, audio=True, asr=True, voice_trigger=True,
                llm=True, nlu=True, text_processor=True, intent_system=True
            )
            # Update system capabilities
            config.system.microphone_enabled = True
            config.system.audio_playback_enabled = True
            config.system.web_api_enabled = True
            # Update input sources
            config.inputs.microphone = True
            config.inputs.web = True
            config.inputs.cli = True
            config.inputs.default_input = "microphone"
        
        # Apply other command line overrides
        if args.data_dir:
            # V14: Update assets root instead of data_directory
            config.assets.assets_root = Path(args.data_dir)
        
        return config
    
    async def _validate_runner_specific_config(self, config: CoreConfig, args: argparse.Namespace) -> List[str]:
        """Validate CLI-specific configuration requirements"""
        errors = []
        
        # CLI runner is very flexible - only requires intent system for command processing
        if not config.components.intent_system:
            errors.append("Intent system must be enabled for CLI command processing (components.intent_system = true)")
        
        return errors
    
    async def _post_core_setup(self, args: argparse.Namespace) -> None:
        """CLI-specific setup after core is started"""
        # Handle test greeting (legacy compatibility)
        if args.test_greeting:
            args.command = "привет"
            if not args.quiet:
                print("🧪 Testing greeting command (legacy compatibility mode)")
        
        if not args.quiet:
            profile = self.core.component_manager.get_deployment_profile()
            print(f"🚀 Irene started successfully in {profile} mode")
            
            # Show available components
            component_info = self.core.component_manager.get_component_info()
            active_components = [name for name, info in component_info.items() 
                               if info.initialized]
            
            if active_components:
                print(f"📦 Active components: {', '.join(active_components)}")
            else:
                print("📦 Running in minimal mode (no optional components)")
    
    async def _execute_runner_logic(self, args: argparse.Namespace) -> int:
        """Execute CLI runner logic"""
        # Handle single command execution
        if args.command:
            try:
                if not args.quiet:
                    print(f"🔤 Executing command: '{args.command}'")
                # Use unified workflow interface
                result = await self.core.workflow_manager.process_text_input(
                    text=args.command,
                    session_id="cli_session",
                    wants_audio=getattr(args, 'enable_tts', False),  # Phase 5: TTS support
                    client_context={"source": "cli", "quiet": args.quiet}
                )
                if result.text and not args.quiet:
                    print(f"📝 Response: {result.text}")
                
                # Exit unless interactive mode is forced
                if not args.interactive:
                    if not args.quiet:
                        print("✅ Command executed successfully")
                    return 0
            except Exception as e:
                self._logger.error(f"Error executing command '{args.command}': {e}")
                if not args.quiet:
                    print(f"❌ Error executing command: {e}")
                return 1
        
        # Interactive mode
        return await self._run_interactive_loop(args, "irene> ")
    
    def _print_interactive_help(self) -> None:
        """Print help for CLI interactive mode"""
        print("\n📖 Available Commands:")
        print("-" * 30)
        print("help, h          - Show this help message")
        print("status           - Show component status")
        print("quit, exit, q    - Exit the application")
        print("hello            - Test greeting command")
        print("time             - Show current time")
        print("timer <seconds>  - Set a timer")
        print()
    
    def _print_interactive_status(self) -> None:
        """Print system status in CLI interactive mode"""
        print("\n📊 System Status:")
        print("-" * 20)
        
        # Core status
        print(f"🔧 Core: {'Running' if self.core._running else 'Stopped'}")
        
        # Component status
        component_info = self.core.component_manager.get_component_info()
        for name, info in component_info.items():
            status_icon = "✅" if info.initialized else "❌"
            print(f"{status_icon} {name.capitalize()}: {'Active' if info.initialized else 'Inactive'}")
        
        # Plugin status
        plugin_count = len(self.core.plugin_manager._plugins)
        print(f"🔌 Plugins loaded: {plugin_count}")
        
        # Deployment profile
        profile = self.core.component_manager.get_deployment_profile()
        print(f"🚀 Deployment profile: {profile}")
        print()


def run_cli() -> int:
    """Entry point for CLI runner"""
    try:
        runner = CLIRunner()
        return asyncio.run(runner.run())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        return 0


if __name__ == "__main__":
    sys.exit(run_cli()) 