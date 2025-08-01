"""
CLI Runner - Command line interface for Irene

Enhanced with dependency checking and graceful fallback handling.
"""

import asyncio
import logging
import argparse
import sys
from pathlib import Path
from typing import Optional

from ..config.models import CoreConfig, ComponentConfig
from ..config.manager import ConfigManager
from ..core.engine import AsyncVACore
from ..utils.loader import get_component_status, suggest_installation


def setup_argument_parser() -> argparse.ArgumentParser:
    """Setup command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Irene Voice Assistant v13 - Modern async voice assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Start with default config
  %(prog)s --config config.toml      # Use specific config file
  %(prog)s --headless                # Run in headless mode
  %(prog)s --api-only                # Run as API server only
  %(prog)s --check-deps              # Check component dependencies
  %(prog)s --voice                   # Full voice assistant mode
        """
    )
    
    # Configuration options
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=Path("config.toml"),
        help="Configuration file path (default: config.toml)"
    )
    
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
        "--check-deps",
        action="store_true",
        help="Check component dependencies and exit"
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available deployment profiles and exit"
    )
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
    
    # Logging options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Override data directory path"
    )
    
    return parser


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


async def create_config_from_args(args: argparse.Namespace) -> CoreConfig:
    """Create configuration from command line arguments"""
    
    # Start with default config or load from file
    config_manager = ConfigManager()
    
    if args.config.exists():
        config = await config_manager.load_config(args.config)
    else:
        config = config_manager.get_default_config()
    
    # Apply deployment profile overrides
    if args.headless:
        config.components = ComponentConfig(
            microphone=False, tts=False, audio_output=False, web_api=False
        )
    elif args.api_only:
        config.components = ComponentConfig(
            microphone=False, tts=False, audio_output=False, web_api=True
        )
    elif args.voice:
        config.components = ComponentConfig(
            microphone=True, tts=True, audio_output=True, web_api=True
        )
    
    # Apply command line overrides
    if args.debug:
        config.debug = True
        from ..config.models import LogLevel
        config.log_level = LogLevel.DEBUG
    elif args.log_level:
        from ..config.models import LogLevel
        config.log_level = LogLevel(args.log_level)
    
    if args.data_dir:
        config.data_directory = args.data_dir
    
    return config


async def main():
    """Main CLI entry point"""
    # Setup argument parser and parse args
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Setup logging based on args
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Handle utility options first (exit early)
    if args.check_deps:
        success = check_dependencies()
        return 0 if success else 1
    
    if args.list_profiles:
        list_deployment_profiles()
        return 0
    
    # Handle test greeting (legacy compatibility)
    if args.test_greeting:
        args.command = "привет"
        if not args.quiet:
            print("🧪 Testing greeting command (legacy compatibility mode)")
    
    # Create configuration from args
    try:
        config = await create_config_from_args(args)
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        print(f"❌ Configuration error: {e}")
        return 1

    
    # Create and start the assistant
    core = AsyncVACore(config)
    
    try:
        if not args.quiet:
            logger.info("Initializing Irene...")
            print("🔧 Initializing Irene...")
        await core.start()
        
        profile = core.component_manager.get_deployment_profile()
        if not args.quiet:
            print(f"🚀 Irene started successfully in {profile} mode")
            
            # Show available components
            component_info = core.component_manager.get_component_info()
            active_components = [name for name, info in component_info.items() 
                               if info.initialized]
            
            if active_components:
                print(f"📦 Active components: {', '.join(active_components)}")
            else:
                print("📦 Running in minimal mode (no optional components)")
        
        # Handle single command execution
        if args.command:
            try:
                if not args.quiet:
                    print(f"🔤 Executing command: '{args.command}'")
                await core.process_command(args.command)
                
                # Exit unless interactive mode is forced
                if not args.interactive:
                    if not args.quiet:
                        print("✅ Command executed successfully")
                    await core.stop()
                    return 0
            except Exception as e:
                logger.error(f"Error executing command '{args.command}': {e}")
                print(f"❌ Error executing command: {e}")
                await core.stop()
                return 1
        
        # Interactive mode
        if not args.quiet:
            print("\n💬 Type 'help' for available commands, or 'quit' to exit")
            print("-" * 50)
        
        # Main interaction loop
        while core.is_running:
            try:
                prompt = "irene> " if not args.quiet else "> "
                command = input(prompt).strip()
                
                if command.lower() in ["quit", "exit", "q"]:
                    break
                elif command.lower() == "help":
                    print_help()
                    continue
                elif command.lower() == "status":
                    print_status(core)
                    continue
                elif not command:
                    continue
                
                # Process the command
                await core.process_command(command)
                
            except KeyboardInterrupt:
                if not args.quiet:
                    print("\n\n🛑 Interrupt received, shutting down...")
                break
            except EOFError:
                if not args.quiet:
                    print("\n\n👋 EOF received, goodbye!")
                break
            except Exception as e:
                logger.error(f"Error processing command: {e}")
                if not args.quiet:
                    print(f"❌ Error: {e}")
    
    except Exception as e:
        logger.error(f"Failed to start Irene: {e}")
        print(f"❌ Failed to start Irene: {e}")
        return 1
    finally:
        if not args.quiet:
            print("\n🔄 Shutting down...")
        await core.stop()
        if not args.quiet:
            print("👋 Goodbye!")
    
    return 0


def print_help():
    """Print available commands"""
    print("\n📖 Available Commands:")
    print("-" * 30)
    print("help, h          - Show this help message")
    print("status           - Show component status")
    print("quit, exit, q    - Exit the application")
    print("hello            - Test greeting command")
    print("time             - Show current time")
    print("timer <seconds>  - Set a timer")
    print()


def print_status(core: AsyncVACore):
    """Print current system status"""
    print("\n📊 System Status:")
    print("-" * 20)
    
    # Core status
    print(f"🔧 Core: {'Running' if core._running else 'Stopped'}")
    
    # Component status
    component_info = core.component_manager.get_component_info()
    for name, info in component_info.items():
        status_icon = "✅" if info.initialized else "❌"
        print(f"{status_icon} {name.capitalize()}: {'Active' if info.initialized else 'Inactive'}")
    
    # Plugin status
    plugin_count = len(core.plugin_manager._plugins)
    print(f"🔌 Plugins loaded: {plugin_count}")
    
    # Deployment profile
    profile = core.component_manager.get_deployment_profile()
    print(f"🚀 Deployment profile: {profile}")
    print()


class CLIRunner:
    """
    CLI Runner class - Provides command line interface for Irene.
    
    Replaces legacy runva_cmdline.py with modern async architecture.
    """
    
    def __init__(self):
        self.core: Optional[AsyncVACore] = None
        
    async def run(self, args: Optional[list[str]] = None) -> int:
        """Run the CLI with optional argument list"""
        # Parse arguments
        parser = setup_argument_parser()
        parsed_args = parser.parse_args(args)
        
        # Set up logging
        log_level = getattr(logging, parsed_args.log_level)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(__name__)
        
        try:
            # Handle utility options
            if parsed_args.check_deps:
                success = check_dependencies()
                return 0 if success else 1
            
            if parsed_args.list_profiles:
                list_deployment_profiles()
                return 0
            
            # Handle test greeting (legacy compatibility)
            if parsed_args.test_greeting:
                parsed_args.command = "привет"
                if not parsed_args.quiet:
                    print("🧪 Testing greeting command (legacy compatibility mode)")
            
            # Create configuration
            config = await create_config_from_args(parsed_args)
            
            # Create and start assistant
            self.core = AsyncVACore(config)
            
            if not parsed_args.quiet:
                print("🔧 Initializing Irene...")
            await self.core.start()
            
            # Handle single command execution
            if parsed_args.command:
                if not parsed_args.quiet:
                    print(f"🔤 Executing command: '{parsed_args.command}'")
                await self.core.process_command(parsed_args.command)
                
                if not parsed_args.interactive:
                    if not parsed_args.quiet:
                        print("✅ Command executed successfully")
                    return 0
            
            # Interactive mode
            return await self._interactive_loop(parsed_args)
            
        except Exception as e:
            logger.error(f"CLI Runner error: {e}")
            return 1
        finally:
            if self.core:
                await self.core.stop()
    
    async def _interactive_loop(self, args) -> int:
        """Run the interactive command loop"""
        if not self.core:
            return 1
            
        if not args.quiet:
            profile = self.core.component_manager.get_deployment_profile()
            print(f"🚀 Irene started successfully in {profile} mode")
            print("\n💬 Type 'help' for available commands, or 'quit' to exit")
            print("-" * 50)
        
        try:
            while self.core.is_running:
                try:
                    prompt = "irene> " if not args.quiet else "> "
                    command = input(prompt).strip()
                    
                    if command.lower() in ["quit", "exit", "q"]:
                        break
                    elif command.lower() == "help":
                        print_help()
                        continue
                    elif command.lower() == "status":
                        print_status(self.core)
                        continue
                    elif not command:
                        continue
                    
                    await self.core.process_command(command)
                    
                except KeyboardInterrupt:
                    if not args.quiet:
                        print("\n\n🛑 Interrupt received, shutting down...")
                    break
                except EOFError:
                    if not args.quiet:
                        print("\n\n👋 EOF received, goodbye!")
                    break
                except Exception as e:
                    logging.getLogger(__name__).error(f"Error processing command: {e}")
                    if not args.quiet:
                        print(f"❌ Error: {e}")
            
            return 0
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Interactive loop error: {e}")
            return 1


def run_cli() -> int:
    """Entry point for CLI runner (legacy compatibility)"""
    try:
        return asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        return 0


if __name__ == "__main__":
    sys.exit(run_cli()) 