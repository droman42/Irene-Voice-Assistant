"""
Base Runner Class - Common patterns for all Irene runners

Provides unified initialization, configuration management, and core lifecycle
patterns shared across CLI, WebAPI, and VOSK runners.
"""

import asyncio
import argparse
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from ..config.models import CoreConfig, ComponentConfig, LogLevel
from ..config.manager import ConfigManager
from ..core.engine import AsyncVACore
from ..utils.logging import setup_logging


logger = logging.getLogger(__name__)


@dataclass
class RunnerConfig:
    """Configuration specific to runner behavior"""
    name: str
    description: str
    requires_config_file: bool = False
    supports_interactive: bool = False
    default_components: Optional[ComponentConfig] = None
    required_dependencies: List[str] = None
    
    def __post_init__(self):
        if self.required_dependencies is None:
            self.required_dependencies = []


class BaseRunner(ABC):
    """
    Abstract base class for all Irene runners.
    
    Provides common patterns for:
    - Argument parsing with runner-specific extensions
    - Environment and logging setup
    - Configuration loading and validation
    - Core lifecycle management
    - Error handling and cleanup
    """
    
    def __init__(self, runner_config: RunnerConfig):
        self.runner_config = runner_config
        self.core: Optional[AsyncVACore] = None
        self._logger = logging.getLogger(f"{__name__}.{self.runner_config.name}")
        
    async def run(self, args: Optional[List[str]] = None) -> int:
        """Main runner entry point with unified pattern"""
        try:
            # 1. Load environment variables from .env file first
            from dotenv import load_dotenv
            load_dotenv()
            
            # 2. Parse arguments (base + runner-specific)
            parser = self._create_argument_parser()
            parsed_args = parser.parse_args(args)
            
            # 3. Setup centralized logging
            self._setup_logging(parsed_args)
            
            # 4. Handle utility options (exit early if needed)
            early_exit_code = await self._handle_utility_options(parsed_args)
            if early_exit_code is not None:
                return early_exit_code
            
            # 5. Check dependencies
            if not await self._check_dependencies(parsed_args):
                return 1
            
            # 6. Create and validate configuration
            config = await self._create_and_validate_config(parsed_args)
            
            # 7. Create and start assistant core
            self.core = AsyncVACore(config, config_path=parsed_args.config)
            
            if not getattr(parsed_args, 'quiet', False):
                self._logger.info(f"Initializing Irene in {self.runner_config.name} mode...")
                print(f"🔧 Initializing Irene in {self.runner_config.name} mode...")
            
            await self.core.start()
            
            # 8. Runner-specific initialization
            await self._post_core_setup(parsed_args)
            
            # 9. Execute runner-specific logic
            return await self._execute_runner_logic(parsed_args)
            
        except Exception as e:
            self._logger.error(f"{self.runner_config.name} Runner error: {e}")
            if not getattr(parsed_args, 'quiet', False):
                print(f"❌ {self.runner_config.name} Runner error: {e}")
            return 1
        finally:
            if self.core:
                await self.core.stop()
    
    def _create_argument_parser(self) -> argparse.ArgumentParser:
        """Create argument parser with base options + runner-specific extensions"""
        parser = argparse.ArgumentParser(
            description=f"Irene Voice Assistant v14 - {self.runner_config.description}",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self._get_usage_examples()
        )
        
        # Add base arguments
        self._add_base_arguments(parser)
        
        # Add runner-specific arguments
        self._add_runner_arguments(parser)
        
        return parser
    
    def _add_base_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add common arguments shared by all runners"""
        # Configuration options
        parser.add_argument(
            "--config", "-c",
            type=Path,
            default=Path("config.toml"),
            help="Configuration file path (default: config.toml)"
        )
        
        # Logging options
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
            help="Set logging level"
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
        
        # Utility options
        parser.add_argument(
            "--check-deps",
            action="store_true",
            help="Check dependencies and exit"
        )
    
    def _setup_logging(self, args: argparse.Namespace) -> None:
        """Setup centralized logging"""
        log_level = LogLevel(args.log_level)
        if args.debug:
            log_level = LogLevel.DEBUG
            
        setup_logging(
            level=log_level,
            log_file=Path("logs/irene.log"),
            enable_console=True
        )
    
    async def _handle_utility_options(self, args: argparse.Namespace) -> Optional[int]:
        """Handle utility options that should exit early"""
        if args.check_deps:
            success = await self._check_dependencies(args)
            return 0 if success else 1
        
        # Allow runners to handle additional utility options
        return await self._handle_runner_utility_options(args)
    
    async def _create_and_validate_config(self, args: argparse.Namespace) -> CoreConfig:
        """Create configuration with unified pattern"""
        config_manager = ConfigManager()
        
        # Load base configuration
        if args.config.exists():
            config = await config_manager.load_config(args.config)
            if not args.quiet:
                print(f"✅ Loaded configuration from: {args.config}")
        elif self.runner_config.requires_config_file:
            print(f"❌ Configuration file not found: {args.config}")
            print(f"💡 {self.runner_config.name} runner requires a configuration file")
            raise ValueError(f"Configuration file not found: {args.config}")
        else:
            config = config_manager.get_default_config()
            if not args.quiet:
                print("📋 Using default configuration")
        
        # Apply runner-specific configuration modifications
        config = await self._modify_config_for_runner(config, args)
        
        # Apply command line overrides
        if args.debug:
            config.debug = True
            config.log_level = LogLevel.DEBUG
        elif args.log_level:
            config.log_level = LogLevel(args.log_level)
        
        # Validate configuration
        await self._validate_runner_config(config, args)
        
        return config
    
    async def _validate_runner_config(self, config: CoreConfig, args: argparse.Namespace) -> None:
        """Validate configuration for runner requirements"""
        errors = []
        
        # Check runner-specific requirements
        runner_errors = await self._validate_runner_specific_config(config, args)
        errors.extend(runner_errors)
        
        if errors:
            error_message = f"{self.runner_config.name} Runner configuration validation failed:\n\n"
            for i, error in enumerate(errors, 1):
                error_message += f"  {i}. {error}\n"
            error_message += f"\nPlease update your configuration file for {self.runner_config.name} mode.\n"
            
            # Add runner-specific configuration examples
            example_config = self._get_configuration_example()
            if example_config:
                error_message += f"\nExample configuration:\n{example_config}"
            
            raise ValueError(error_message)
    
    # Abstract methods that runners must implement
    @abstractmethod
    def _add_runner_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add runner-specific command line arguments"""
        pass
    
    @abstractmethod
    def _get_usage_examples(self) -> str:
        """Get usage examples for help text"""
        pass
    
    @abstractmethod
    async def _check_dependencies(self, args: argparse.Namespace) -> bool:
        """Check runner-specific dependencies"""
        pass
    
    @abstractmethod
    async def _modify_config_for_runner(self, config: CoreConfig, args: argparse.Namespace) -> CoreConfig:
        """Modify configuration for runner-specific needs"""
        pass
    
    @abstractmethod
    async def _validate_runner_specific_config(self, config: CoreConfig, args: argparse.Namespace) -> List[str]:
        """Validate runner-specific configuration requirements. Return list of error messages."""
        pass
    
    @abstractmethod
    async def _execute_runner_logic(self, args: argparse.Namespace) -> int:
        """Execute the main runner logic"""
        pass
    
    # Optional methods that runners can override
    async def _handle_runner_utility_options(self, args: argparse.Namespace) -> Optional[int]:
        """Handle runner-specific utility options. Return exit code if should exit early."""
        return None
    
    async def _post_core_setup(self, args: argparse.Namespace) -> None:
        """Perform runner-specific setup after core is started"""
        pass
    
    def _get_configuration_example(self) -> Optional[str]:
        """Get example configuration for error messages"""
        return None


class InteractiveRunnerMixin:
    """
    Mixin for runners that support interactive mode.
    
    Provides common interactive loop patterns.
    """
    
    async def _run_interactive_loop(self, args: argparse.Namespace, prompt_text: str = "irene> ") -> int:
        """Run interactive command loop with unified pattern"""
        if not self.core:
            return 1
        
        try:
            from prompt_toolkit import prompt
        except ImportError:
            print("❌ Interactive mode requires prompt_toolkit")
            print("💡 Install with: uv add prompt_toolkit")
            return 1
        
        if not args.quiet:
            print("\n💬 Type 'help' for available commands, or 'quit' to exit")
            print("-" * 50)
        
        try:
            while self.core.is_running:
                try:
                    display_prompt = prompt_text if not args.quiet else "> "
                    command = await asyncio.to_thread(
                        prompt,
                        display_prompt,
                        mouse_support=True,
                        enable_history_search=True
                    )
                    
                    if command:
                        command = command.strip()
                    
                    if command.lower() in ["quit", "exit", "q"]:
                        break
                    elif command.lower() == "help":
                        self._print_interactive_help()
                        continue
                    elif command.lower() == "status":
                        self._print_interactive_status()
                        continue
                    elif not command:
                        continue
                    
                    # Process command through unified workflow
                    await self._process_interactive_command(command, args)
                    
                except KeyboardInterrupt:
                    if not args.quiet:
                        print("\n\n🛑 Interrupt received, shutting down...")
                    break
                except EOFError:
                    if not args.quiet:
                        print("\n\n👋 EOF received, goodbye!")
                    break
                except Exception as e:
                    self._logger.error(f"Error processing command: {e}")
                    if not args.quiet:
                        print(f"❌ Error: {e}")
            
            return 0
            
        except Exception as e:
            self._logger.error(f"Interactive loop error: {e}")
            return 1
    
    async def _process_interactive_command(self, command: str, args: argparse.Namespace) -> None:
        """Process a single interactive command"""
        result = await self.core.workflow_manager.process_text_input(
            text=command,
            session_id=f"{self.runner_config.name}_interactive",
            wants_audio=getattr(args, 'enable_tts', False),
            client_context={"source": f"{self.runner_config.name}_interactive"}
        )
        
        if result.text and not args.quiet:
            print(f"📝 {result.text}")
    
    def _print_interactive_help(self) -> None:
        """Print help for interactive mode"""
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
        """Print system status in interactive mode"""
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


# Utility functions for dependency checking
async def check_component_dependencies(component_names: List[str]) -> Dict[str, Dict[str, Any]]:
    """Check dependencies for specific components"""
    from ..utils.loader import get_component_status
    
    status = get_component_status()
    results = {}
    
    for component in component_names:
        if component in status:
            results[component] = status[component]
        else:
            results[component] = {
                "available": False,
                "dependencies": [],
                "missing": [f"Unknown component: {component}"]
            }
    
    return results


def print_dependency_status(component_status: Dict[str, Dict[str, Any]], quiet: bool = False) -> bool:
    """Print dependency status and return True if all available"""
    if not quiet:
        print("🔍 Checking Dependencies")
        print("=" * 50)
    
    all_available = True
    
    for component, info in component_status.items():
        status_icon = "✅" if info["available"] else "❌"
        if not quiet:
            print(f"{status_icon} {component.capitalize()}: {'Available' if info['available'] else 'Not Available'}")
            
            if info["available"]:
                print(f"   Dependencies: {', '.join(info['dependencies'])}")
            else:
                all_available = False
                print(f"   Missing: {', '.join(info['missing'])}")
                from ..utils.loader import suggest_installation
                suggestion = suggest_installation(component)
                if suggestion:
                    print(f"   💡 Install with: {suggestion}")
            print()
    
    if not quiet:
        if all_available:
            print("🎉 All required dependencies are available!")
        else:
            print("⚠️  Some dependencies are missing. Runner will attempt to continue with available components.")
    
    return all_available
