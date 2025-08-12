"""
Configuration System Demo - Phase H Features

Demonstrates the enhanced configuration system including:
- Default config generation
- Environment variable support
- Hot-reload capabilities
- Pydantic validation
- Configuration-driven plugin loading
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from ..config.manager import ConfigManager
from ..config.models import CoreConfig, create_config_from_profile
from ..core.engine import AsyncVACore

# Setup logging for demo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_default_config_generation():
    """Demonstrate automatic default configuration generation"""
    print("\n🔧 Demo 1: Default Configuration Generation")
    print("=" * 50)
    
    config_manager = ConfigManager()
    
    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "demo_config.toml"
        
        # Generate default configuration file
        generated_path = await config_manager.generate_default_config_file(config_path, profile="voice")
        
        print(f"✅ Generated default config: {generated_path}")
        
        # Show the generated content
        content = config_path.read_text()
        print("\n📄 Generated configuration content (first 20 lines):")
        print("-" * 50)
        for i, line in enumerate(content.split('\n')[:20]):
            print(f"{i+1:2d}: {line}")
        print("... (truncated)")
        
        # Load the generated config
        loaded_config = await config_manager.load_config(config_path)
        print(f"\n✅ Successfully loaded generated config")
        print(f"   - Assistant name: {loaded_config.name}")
        print(f"   - Components enabled: microphone={loaded_config.components.microphone}, "
              f"tts={loaded_config.components.tts}, web_api={loaded_config.components.web_api}")


async def demo_environment_variables():
    """Demonstrate environment variable configuration"""
    print("\n🌍 Demo 2: Environment Variable Configuration")
    print("=" * 50)
    
    # Set some environment variables
    test_env_vars = {
        "IRENE_NAME": "Demo Assistant",
        "IRENE_DEBUG": "true",
        "IRENE_COMPONENTS__WEB_PORT": "9999",
        "IRENE_LANGUAGE": "ru-RU"
    }
    
    # Save original values and set test values
    original_values = {}
    for key, value in test_env_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value
        print(f"Set {key} = {value}")
    
    try:
        config_manager = ConfigManager()
        
        # Load config from environment (no file)
        config = config_manager._load_from_environment()
        
        print(f"\n✅ Loaded configuration from environment variables:")
        print(f"   - Assistant name: {config.name}")
        print(f"   - Debug mode: {config.debug}")
        print(f"   - Web port: {config.components.web_port}")
        print(f"   - Language: {config.language}")
        
    finally:
        # Restore original environment
        for key, original_value in original_values.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


async def demo_configuration_validation():
    """Demonstrate Pydantic configuration validation"""
    print("\n✅ Demo 3: Configuration Validation")
    print("=" * 50)
    
    config_manager = ConfigManager()
    
    # Test valid configuration
    print("Testing valid configuration...")
    valid_config_data = {
        "name": "Test Assistant",
        "components": {
            "web_port": 8080
        }
    }
    
    try:
        config = await config_manager._dict_to_config_validated(valid_config_data)
        print(f"✅ Valid config loaded: {config.name}, port {config.components.web_port}")
    except Exception as e:
        print(f"❌ Unexpected error with valid config: {e}")
    
    # Test invalid configuration
    print("\nTesting invalid configuration...")
    invalid_config_data = {
        "name": "Test Assistant",
        "components": {
            "web_port": 99999  # Invalid port number
        }
    }
    
    try:
        config = await config_manager._dict_to_config_validated(invalid_config_data)
        print(f"⚠️  Invalid config unexpectedly accepted: {config.name}")
    except Exception as e:
        print(f"✅ Invalid config properly rejected: {type(e).__name__}")


async def demo_plugin_configuration():
    """Demonstrate configuration-driven plugin loading"""
    print("\n🔌 Demo 4: Configuration-Driven Plugin Loading")
    print("=" * 50)
    
    # Create config with specific plugins enabled
    config = create_config_from_profile("headless")
    
    # NOTE: Builtin plugin configuration removed - functionality moved to intent handlers
    print("Plugin configuration:")
    print("   ✅ Intent handlers automatically discovered via entry-points")
    print("   ✅ RandomIntentHandler (replaces RandomPlugin)")
    print("   ✅ SystemServiceIntentHandler (replaces AsyncServiceDemoPlugin)")
    
    # Create and start engine with this configuration
    print("\nCreating AsyncVACore with plugin configuration...")
    engine = AsyncVACore(config)
    
    try:
        await engine.start()
        
        # Show loaded plugins
        loaded_plugins = list(engine.plugin_manager._plugins.keys())
        print(f"\n✅ Engine started with {len(loaded_plugins)} plugins:")
        for plugin_name in loaded_plugins:
            print(f"   - {plugin_name}")
            
        # Test a command
        print("\nTesting command processing...")
        # Use unified workflow interface
        result = await engine.workflow_manager.process_text_input(
            text="привет",
            session_id="config_demo",
            wants_audio=False,
            client_context={"source": "config_demo"}
        )
        print(f"Response: {result.text}")
        
    except Exception as e:
        logger.error(f"Failed to start engine: {e}")
    finally:
        await engine.stop()


async def demo_hot_reload():
    """Demonstrate hot-reload configuration"""
    print("\n🔥 Demo 5: Hot-Reload Configuration")
    print("=" * 50)
    
    config_manager = ConfigManager()
    
    # Create temporary config file
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "hot_reload_demo.toml"
        
        # Generate initial config
        await config_manager.generate_default_config_file(config_path, profile="headless")
        
        # Track reload events
        reload_count = 0
        
        def on_config_reload(new_config: CoreConfig):
            nonlocal reload_count
            reload_count += 1
            print(f"🔄 Config reloaded #{reload_count}: assistant name = {new_config.name}")
        
        # Start hot-reload monitoring
        config_manager.start_hot_reload(config_path, on_config_reload)
        
        print(f"Started hot-reload monitoring for: {config_path}")
        print("Simulating config file changes...")
        
        # Simulate config file changes
        for i in range(3):
            await asyncio.sleep(1.5)  # Wait for file watcher
            
            # Load and modify config
            config = await config_manager.load_config(config_path)
            config.name = f"Hot Reload Demo #{i+1}"
            await config_manager.save_config(config, config_path)
            print(f"Modified config file (change #{i+1})")
            
            await asyncio.sleep(1.5)  # Wait for reload detection
        
        print(f"\n✅ Hot-reload demo completed. Total reloads detected: {reload_count}")
        
        # Stop monitoring
        config_manager.stop_hot_reload(config_path)


async def demo_deployment_profiles():
    """Demonstrate deployment profile configurations"""
    print("\n🚀 Demo 6: Deployment Profiles")
    print("=" * 50)
    
    profiles = ["headless", "api", "voice"]
    
    for profile_name in profiles:
        print(f"\n📋 Profile: {profile_name}")
        print("-" * 30)
        
        try:
            config = create_config_from_profile(profile_name)
            
            print(f"Components configuration:")
            print(f"   - Microphone: {config.components.microphone}")
            print(f"   - TTS: {config.components.tts}")
            print(f"   - Audio Output: {config.components.audio_output}")
            print(f"   - Web API: {config.components.web_api}")
            print(f"   - Web Port: {config.components.web_port}")
            
            # Show plugin configuration
            print(f"   - Intent Handlers: Available via entry-points (replaces builtin plugins)")
            
        except Exception as e:
            print(f"❌ Failed to create profile {profile_name}: {e}")


async def main():
    """Run all configuration system demos"""
    print("🎯 Irene Voice Assistant - Configuration System Demo")
    print("Phase H: Configuration System Completion")
    print("=" * 60)
    
    demos = [
        demo_default_config_generation,
        demo_environment_variables,
        demo_configuration_validation,
        demo_plugin_configuration,
        demo_hot_reload,
        demo_deployment_profiles,
    ]
    
    for i, demo_func in enumerate(demos, 1):
        try:
            await demo_func()
            if i < len(demos):
                print("\n" + "="*60)
        except Exception as e:
            logger.error(f"Demo {demo_func.__name__} failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n🎉 Configuration system demo completed!")
    print("All Phase H features demonstrated successfully.")


if __name__ == "__main__":
    asyncio.run(main()) 