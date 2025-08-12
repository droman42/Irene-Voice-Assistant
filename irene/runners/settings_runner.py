"""
Settings Manager Runner - Web-based configuration interface

Replaces legacy runva_settings_manager.py with modern configuration management.
Provides web UI for managing Irene configuration and plugins.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from ..config.models import CoreConfig, ComponentConfig, LogLevel
from ..config.manager import ConfigManager
from ..core.engine import AsyncVACore
from ..utils.loader import get_component_status
from ..utils.logging import setup_logging


logger = logging.getLogger(__name__)


def setup_settings_argument_parser() -> argparse.ArgumentParser:
    """Setup Settings Manager specific argument parser"""
    parser = argparse.ArgumentParser(
        description="Irene Voice Assistant v13 - Settings Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Start settings manager
  %(prog)s --host 0.0.0.0 --port 7860 # Custom host and port
  %(prog)s --no-browser              # Don't open browser automatically
        """
    )
    
    # Configuration options
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=Path("config.toml"),
        help="Configuration file path (default: config.toml)"
    )
    
    # Server options
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=7860,
        help="Port to bind to (default: 7860)"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically"
    )
    
    # Interface options
    parser.add_argument(
        "--theme",
        choices=["default", "dark", "light"],
        default="default",
        help="UI theme (default: default)"
    )
    parser.add_argument(
        "--title",
        default="Irene Voice Assistant - Settings Manager",
        help="Web interface title"
    )
    
    # Development options
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Reduce output verbosity"
    )
    
    # Logging options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )
    
    return parser


def check_settings_dependencies() -> bool:
    """Check if Settings Manager dependencies are available"""
    try:
        import gradio as gr  # type: ignore
        print("✅ Settings Manager dependencies available")
        print(f"   Gradio version: {gr.__version__}")
        return True
    except ImportError as e:
        print(f"❌ Settings Manager dependencies missing: {e}")
        print("💡 Install with: pip install gradio")
        return False


class SettingsManagerRunner:
    """
    Settings Manager Runner
    
    Replaces legacy runva_settings_manager.py with modern configuration management.
    Provides web-based interface for managing Irene settings and plugins.
    """
    
    def __init__(self):
        self.core: Optional[AsyncVACore] = None
        self.config_manager: Optional[ConfigManager] = None
        self.interface = None
        
    async def run(self, args: Optional[list[str]] = None) -> int:
        """Run Settings Manager"""
        # Parse arguments
        parser = setup_settings_argument_parser()
        parsed_args = parser.parse_args(args)
        
        # Set up centralized logging to logs/irene.log
        log_level = LogLevel(parsed_args.log_level)
        setup_logging(
            level=log_level,
            log_file=Path("logs/irene.log"),
            enable_console=True
        )
        
        try:
            # Check dependencies
            if not check_settings_dependencies():
                return 1
            
            # Initialize configuration manager
            self.config_manager = ConfigManager()
            
            # Try to load existing config or create default
            try:
                config = await self.config_manager.load_config(parsed_args.config)
            except Exception as e:
                logger.warning(f"Could not load config: {e}")
                # Create default config
                config = CoreConfig()
                if not parsed_args.quiet:
                    print("📝 Using default configuration")
            
            # Create assistant (but don't start it automatically)
            self.core = AsyncVACore(config)
            
            if not parsed_args.quiet:
                print("🔧 Initializing Settings Manager...")
            
            # Create Gradio interface
            self.interface = await self._create_gradio_interface(parsed_args)
            
            # Launch interface
            return await self._launch_interface(parsed_args)
            
        except Exception as e:
            logger.error(f"Settings Manager error: {e}")
            return 1
    
    async def _create_gradio_interface(self, args):
        """Create Gradio web interface for settings management"""
        import gradio as gr  # type: ignore
        
        # Disable Gradio analytics
        import os
        if 'GRADIO_ANALYTICS_ENABLED' not in os.environ:
            os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'
        
        with gr.Blocks(title=args.title, theme=args.theme if args.theme != "default" else None) as interface:
            gr.Markdown("# 🤖 Irene Voice Assistant - Settings Manager v13")
            gr.Markdown("Configure your voice assistant settings and manage plugins")
            
            with gr.Tabs():
                # System Status Tab
                with gr.Tab("📊 System Status"):
                    gr.Markdown("## System Information")
                    
                    status_text = gr.Textbox(
                        label="Status",
                        value="Not started",
                        interactive=False
                    )
                    
                    components_text = gr.Textbox(
                        label="Components",
                        value="Loading...",
                        interactive=False,
                        lines=5
                    )
                    
                    refresh_btn = gr.Button("🔄 Refresh Status")
                    start_btn = gr.Button("▶️ Start Assistant")
                    stop_btn = gr.Button("⏹️ Stop Assistant")
                    
                    def get_status_info():
                        if self.core and self.core.is_running:
                            profile = self.core.component_manager.get_deployment_profile()
                            component_info = self.core.component_manager.get_component_info()
                            plugin_count = len(self.core.plugin_manager._plugins)
                            
                            status = f"Running ({profile} mode)"
                            components = f"Plugins loaded: {plugin_count}\n\nComponents:\n"
                            for name, info in component_info.items():
                                status_icon = "✅" if info.initialized else "❌"
                                components += f"{status_icon} {name.capitalize()}: {'Active' if info.initialized else 'Inactive'}\n"
                        else:
                            status = "Stopped"
                            components = "Assistant not running"
                        
                        return status, components
                    
                    async def start_assistant():
                        if not self.core:
                            return "Error: Core not initialized", "Core not available"
                        try:
                            await self.core.start()
                            return get_status_info()
                        except Exception as e:
                            return f"Error: {e}", str(e)
                    
                    async def stop_assistant():
                        if not self.core:
                            return "Error: Core not initialized", "Core not available"
                        try:
                            await self.core.stop()
                            return get_status_info()
                        except Exception as e:
                            return f"Error: {e}", str(e)
                    
                    refresh_btn.click(
                        fn=get_status_info,
                        outputs=[status_text, components_text]
                    )
                    
                    start_btn.click(
                        fn=lambda: asyncio.create_task(start_assistant()),
                        outputs=[status_text, components_text]
                    )
                    
                    stop_btn.click(
                        fn=lambda: asyncio.create_task(stop_assistant()),
                        outputs=[status_text, components_text]
                    )
                
                # Component Configuration Tab
                with gr.Tab("🔧 Components"):
                    gr.Markdown("## Component Configuration")
                    
                    microphone_enabled = gr.Checkbox(
                        label="Enable Microphone Input",
                        value=self.core.config.components.microphone if self.core else False
                    )
                    
                    tts_enabled = gr.Checkbox(
                        label="Enable Text-to-Speech",
                        value=self.core.config.components.tts if self.core else True
                    )
                    
                    audio_output_enabled = gr.Checkbox(
                        label="Enable Audio Output",
                        value=self.core.config.components.audio_output if self.core else False
                    )
                    
                    web_api_enabled = gr.Checkbox(
                        label="Enable Web API",
                        value=self.core.config.components.web_api if self.core else False
                    )
                    
                    save_config_btn = gr.Button("💾 Save Configuration")
                    config_status = gr.Textbox(
                        label="Status",
                        value="",
                        interactive=False
                    )
                    
                    async def save_configuration(mic, tts, audio, web):
                        if not self.config_manager:
                            return "❌ Error: Config manager not initialized"
                        if not self.core:
                            return "❌ Error: Core not initialized"
                            
                        try:
                            # Update component configuration
                            new_components = ComponentConfig(
                                microphone=mic,
                                tts=tts,
                                audio_output=audio,
                                web_api=web
                            )
                            
                            # Create new config
                            new_config = CoreConfig(components=new_components)
                            
                            # Save to file
                            await self.config_manager.save_config(new_config, args.config)
                            
                            # Update core config
                            self.core.config = new_config
                            
                            return "✅ Configuration saved successfully!"
                        
                        except Exception as e:
                            return f"❌ Error saving configuration: {e}"
                    
                    save_config_btn.click(
                        fn=lambda mic, tts, audio, web: asyncio.create_task(
                            save_configuration(mic, tts, audio, web)
                        ),
                        inputs=[microphone_enabled, tts_enabled, audio_output_enabled, web_api_enabled],
                        outputs=[config_status]
                    )
                
                # Plugin Management Tab
                with gr.Tab("🔌 Plugins"):
                    gr.Markdown("## Plugin Management")
                    
                    plugin_list = gr.Textbox(
                        label="Loaded Plugins",
                        value="Loading...",
                        interactive=False,
                        lines=10
                    )
                    
                    refresh_plugins_btn = gr.Button("🔄 Refresh Plugin List")
                    
                    def get_plugin_info():
                        if self.core:
                            plugins = self.core.plugin_manager._plugins
                            if plugins:
                                info = f"Total plugins loaded: {len(plugins)}\n\n"
                                for name, plugin in plugins.items():
                                    info += f"📦 {name}\n"
                                    info += f"   Version: {plugin.version}\n"
                                    # Check if plugin has get_triggers method (CommandPlugin specific)
                                    if hasattr(plugin, 'get_triggers') and callable(getattr(plugin, 'get_triggers')):
                                        try:
                                            triggers = plugin.get_triggers()  # type: ignore
                                            info += f"   Triggers: {', '.join(triggers[:3])}{'...' if len(triggers) > 3 else ''}\n"
                                        except:
                                            pass
                                    info += "\n"
                                return info
                            else:
                                return "No plugins loaded"
                        else:
                            return "Assistant not initialized"
                    
                    refresh_plugins_btn.click(
                        fn=get_plugin_info,
                        outputs=[plugin_list]
                    )
                
                # Dependency Check Tab
                with gr.Tab("📋 Dependencies"):
                    gr.Markdown("## Dependency Status")
                    
                    deps_text = gr.Textbox(
                        label="Component Dependencies",
                        value="Loading...",
                        interactive=False,
                        lines=15
                    )
                    
                    check_deps_btn = gr.Button("🔍 Check Dependencies")
                    
                    def check_dependencies():
                        status = get_component_status()
                        result = "Component Dependency Status:\n\n"
                        
                        for component, info in status.items():
                            status_icon = "✅" if info["available"] else "❌"
                            result += f"{status_icon} {component.capitalize()}\n"
                            result += f"   Dependencies: {', '.join(info['dependencies'])}\n"
                            if not info["available"]:
                                result += f"   Status: Missing dependencies\n"
                            else:
                                result += f"   Status: Available\n"
                            result += "\n"
                        
                        return result
                    
                    check_deps_btn.click(
                        fn=check_dependencies,
                        outputs=[deps_text]
                    )
            
            # Load initial data
            interface.load(
                fn=get_status_info,
                outputs=[status_text, components_text]
            )
            interface.load(
                fn=get_plugin_info,
                outputs=[plugin_list]
            )
            interface.load(
                fn=check_dependencies,
                outputs=[deps_text]
            )
        
        return interface
    
    async def _launch_interface(self, args) -> int:
        """Launch the Gradio interface"""
        if not self.interface:
            logger.error("Interface not initialized")
            return 1
            
        try:
            if not args.quiet:
                print(f"🌐 Starting Settings Manager at http://{args.host}:{args.port}")
                print("Press Ctrl+C to stop")
            
            # Launch interface (blocking call)
            self.interface.launch(
                server_name=args.host,
                server_port=args.port,
                inbrowser=not args.no_browser,
                debug=args.debug,
                quiet=args.quiet
            )
            
            return 0
            
        except KeyboardInterrupt:
            if not args.quiet:
                print("\n🛑 Settings Manager stopped")
            return 0
        except Exception as e:
            logger.error(f"Interface error: {e}")
            return 1


def run_settings() -> int:
    """Entry point for Settings Manager runner"""
    runner = SettingsManagerRunner()
    try:
        return asyncio.run(runner.run())
    except KeyboardInterrupt:
        print("\n👋 Settings Manager stopped")
        return 0


if __name__ == "__main__":
    sys.exit(run_settings()) 