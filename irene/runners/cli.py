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
    
    # Runtime options
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
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
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Handle utility commands
    if args.check_deps:
        check_dependencies()
        return
    
    if args.list_profiles:
        list_deployment_profiles()
        return
    
    # Create configuration
    try:
        config = await create_config_from_args(args)
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.value),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    print("🎯 Starting Irene Voice Assistant v13")
    print("=" * 50)
    
    # Show component status if in debug mode
    if config.debug:
        check_dependencies()
        print()
    
    # Create and start the assistant
    core = AsyncVACore(config)
    
    try:
        logger.info("Initializing Irene...")
        await core.start()
        
        profile = core.component_manager.get_deployment_profile()
        print(f"🚀 Irene started successfully in {profile} mode")
        
        # Show available components
        component_info = core.component_manager.get_component_info()
        active_components = [name for name, info in component_info.items() 
                           if info.initialized]
        
        if active_components:
            print(f"📦 Active components: {', '.join(active_components)}")
        else:
            print("📦 Running in minimal mode (no optional components)")
        
        print("\n💬 Type 'help' for available commands, or 'quit' to exit")
        print("-" * 50)
        
        # Main interaction loop
        while core.is_running:
            try:
                command = input("irene> ").strip()
                
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
                print("\n\n🛑 Interrupt received, shutting down...")
                break
            except EOFError:
                print("\n\n👋 EOF received, goodbye!")
                break
            except Exception as e:
                logger.error(f"Error processing command: {e}")
                print(f"❌ Error: {e}")
    
    except Exception as e:
        logger.error(f"Failed to start Irene: {e}")
        print(f"❌ Failed to start: {e}")
        
        # Suggest dependency installation if likely the issue
        if "import" in str(e).lower():
            print("\n💡 This might be a missing dependency issue.")
            print("Run with --check-deps to see what's missing.")
        
        sys.exit(1)
    
    finally:
        print("\n🛑 Shutting down Irene...")
        await core.stop()
        print("👋 Goodbye!")


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
    
    profile = core.component_manager.get_deployment_profile()
    print(f"Profile: {profile}")
    
    component_info = core.component_manager.get_component_info()
    
    for name, info in component_info.items():
        status_icon = "✅" if info.initialized else "❌"
        print(f"{status_icon} {name.capitalize()}: {'Active' if info.initialized else 'Inactive'}")
    
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0) 