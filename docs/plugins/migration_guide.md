# Migration Guide: Legacy Plugins → Universal Plugin Architecture

## Overview

This guide helps you migrate from the old "many small plugins" approach to the new "Universal Plugin + Provider" architecture introduced in Irene Voice Assistant Phase 5.

## What Changed

### Before (Legacy System)
- 14+ individual plugin classes
- Separate plugin for each TTS/Audio backend
- No unified web APIs
- Complex inter-plugin dependencies

### After (Universal System)
- 8 Universal Plugin classes (coordinators)
- 12+ Provider classes (implementations)
- Unified web APIs for all functionality
- Configuration-driven provider instantiation

## Migration Process

### Automatic Migration

Use the automated migration tool for quick conversion:

```bash
# Migrate a single config file
python tools/migrate_to_universal_plugins.py config.toml

# Migrate all configs in a directory
python tools/migrate_to_universal_plugins.py --directory ~/.config/irene/

# Preview changes without modifying files
python tools/migrate_to_universal_plugins.py --dry-run config.toml
```

### Manual Migration

If you prefer manual migration or need custom adjustments:

## TTS Plugin Migration

### Legacy Configuration
```toml
[plugins.silero_v3_tts]
enabled = true
model_path = "~/.cache/irene/models/silero_v3"
default_speaker = "xenia"
sample_rate = 24000
torch_device = "cpu"

[plugins.pyttsx_tts]
enabled = true
voice_rate = 200
voice_volume = 0.9

[plugins.console_tts]
enabled = true
color_output = true
```

### New Universal Configuration
```toml
[plugins.universal_tts]
enabled = true
default_provider = "silero_v3"
fallback_providers = ["pyttsx", "console"]
lazy_loading = true
concurrent_initialization = true

[plugins.universal_tts.providers.silero_v3]
enabled = true
model_path = "~/.cache/irene/models/silero_v3"
default_speaker = "xenia"
sample_rate = 24000
torch_device = "cpu"

[plugins.universal_tts.providers.pyttsx]
enabled = true
voice_rate = 200
voice_volume = 0.9

[plugins.universal_tts.providers.console]
enabled = true
color_output = true
```

## Audio Plugin Migration

### Legacy Configuration
```toml
[plugins.sounddevice_audio]
enabled = true
device_id = -1
sample_rate = 44100
channels = 2

[plugins.audioplayer_audio]
enabled = true
volume = 0.8

[plugins.console_audio]
enabled = true
color_output = true
```

### New Universal Configuration
```toml
[plugins.universal_audio]
enabled = true
default_provider = "sounddevice"
concurrent_playback = false

[plugins.universal_audio.providers.sounddevice]
enabled = true
device_id = -1
sample_rate = 44100
channels = 2

[plugins.universal_audio.providers.audioplayer]
enabled = true
volume = 0.8

[plugins.universal_audio.providers.console]
enabled = true
color_output = true
```

## Plugin Mapping Reference

### TTS Plugins
| Legacy Plugin | Universal Provider | Notes |
|---------------|-------------------|-------|
| `silero_v3_tts` | `universal_tts.providers.silero_v3` | All config preserved |
| `silero_v4_tts` | `universal_tts.providers.silero_v4` | All config preserved |
| `pyttsx_tts` | `universal_tts.providers.pyttsx` | All config preserved |
| `console_tts` | `universal_tts.providers.console` | All config preserved |
| `vosk_tts` | `universal_tts.providers.vosk_tts` | All config preserved |

### Audio Plugins
| Legacy Plugin | Universal Provider | Notes |
|---------------|-------------------|-------|
| `sounddevice_audio` | `universal_audio.providers.sounddevice` | All config preserved |
| `audioplayer_audio` | `universal_audio.providers.audioplayer` | All config preserved |
| `aplay_audio` | `universal_audio.providers.aplay` | All config preserved |
| `simpleaudio_audio` | `universal_audio.providers.simpleaudio` | All config preserved |
| `console_audio` | `universal_audio.providers.console` | All config preserved |

## API Changes

### Legacy Plugin APIs
Each plugin had its own separate API (if any):
```
/silero_v3_tts/speak
/pyttsx_tts/speak
/sounddevice_audio/play
```

### New Universal APIs
Unified APIs for each functionality domain:
```
/tts/speak          (all TTS providers)
/tts/providers      (discovery)
/tts/configure      (runtime config)

/audio/play         (all audio providers)
/audio/providers    (discovery)
/audio/devices      (device discovery)
```

## Voice Command Changes

### Legacy Commands
Commands were provider-specific:
```
"используй силеро"     (Silero-specific)
"переключись на pyttsx" (Pyttsx-specific)
```

### New Universal Commands
Commands work across all providers:
```
"переключись на силеро"    (switches universal TTS)
"скажи привет голосом ксении"  (uses current provider)
"покажи голоса"           (shows all providers)
```

## Code Migration

### Python API Changes

#### Legacy API
```python
# Get specific plugin
silero_plugin = core.plugin_manager.get_plugin("silero_v3_tts")
await silero_plugin.speak("Привет")

pyttsx_plugin = core.plugin_manager.get_plugin("pyttsx_tts")
await pyttsx_plugin.speak("Hello")
```

#### New Universal API
```python
# Get universal plugin
tts_plugin = core.plugin_manager.get_plugin("universal_tts")

# Use default provider
await tts_plugin.speak("Привет")

# Use specific provider
await tts_plugin.speak("Hello", provider="pyttsx")
await tts_plugin.speak("Hola", provider="elevenlabs", voice_id="spanish_voice")
```

### Custom Plugin Development

#### Legacy Provider Development
```python
class MyTTSPlugin(TTSPlugin):
    def __init__(self):
        # Plugin initialization
        pass
    
    async def speak(self, text: str) -> None:
        # TTS implementation
        pass
```

#### New Provider Development
```python
class MyTTSProvider(TTSProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Provider initialization
    
    async def is_available(self) -> bool:
        # Dependency check
        return True
    
    async def speak(self, text: str, **kwargs) -> None:
        # TTS implementation
        pass
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        # Return parameter schema
        return {}
    
    def get_capabilities(self) -> Dict[str, Any]:
        # Return provider capabilities
        return {}
```

## Performance Improvements

### New Features Available

#### Lazy Loading
Only load providers when first used:
```toml
[plugins.universal_tts]
lazy_loading = true
```

#### Concurrent Initialization
Load multiple providers simultaneously:
```toml
[plugins.universal_tts]
concurrent_initialization = true
```

#### Model Caching
Automatic caching for Silero models:
```
INFO: Cached Silero v3 model: silero_model_v3.pt:cpu
INFO: Using cached Silero v3 model: silero_model_v3.pt:cpu
```

## Troubleshooting Migration

### Common Issues

#### 1. Missing Providers After Migration
**Problem**: Some TTS/audio providers don't work after migration.
**Solution**: Check provider configuration and dependencies:
```bash
# Check provider status via API
curl http://localhost:8000/tts/providers
curl http://localhost:8000/audio/providers
```

#### 2. Configuration Not Found
**Problem**: `universal_tts` or `universal_audio` not found in config.
**Solution**: Re-run migration tool or manually add basic configuration:
```toml
[plugins.universal_tts]
enabled = true
default_provider = "console"

[plugins.universal_tts.providers.console]
enabled = true
```

#### 3. Voice Commands Not Working
**Problem**: Old voice commands still reference legacy plugins.
**Solution**: Update voice commands to use universal format:
- Old: `"используй pyttsx"`
- New: `"переключись на pyttsx"`

#### 4. Custom Plugins Broken
**Problem**: Custom plugins don't work with new system.
**Solution**: Convert custom plugins to provider format (see examples).

### Migration Validation

Verify successful migration:

```bash
# Check plugin status
python -c "
from irene.core.engine import AsyncVACore
from irene.config.models import CoreConfig
import asyncio

async def check():
    config = CoreConfig()
    core = AsyncVACore(config)
    await core.start()
    
    # Check universal plugins
    tts = core.plugin_manager.get_plugin('universal_tts')
    audio = core.plugin_manager.get_plugin('universal_audio')
    
    print(f'TTS providers: {len(tts.providers) if tts else 0}')
    print(f'Audio providers: {len(audio.providers) if audio else 0}')
    
    await core.stop()

asyncio.run(check())
"
```

## Rollback Plan

If you encounter issues and need to rollback:

### 1. Restore Configuration Backup
```bash
# Migration tool creates automatic backups
cp config.toml.backup config.toml
```

### 2. Git Rollback (if using git)
```bash
# Rollback to pre-migration state
git checkout pre-migration-backup
```

### 3. Manual Rollback
Remove universal plugin configuration and restore legacy format:
```toml
# Remove these sections
# [plugins.universal_tts]
# [plugins.universal_audio]

# Restore legacy format
[plugins.silero_v3_tts]
enabled = true
# ... restore old config
```

## Getting Help

### Resources
- [Universal TTS Documentation](universal_tts.md)
- [Universal Audio Documentation](universal_audio.md)
- [Example Configurations](../examples/)

### Support
- Check logs for detailed error messages
- Use `--dry-run` with migration tool to preview changes
- Enable debug logging to troubleshoot issues

### Reporting Issues
When reporting migration issues, include:
1. Original configuration file
2. Migration tool output
3. Error messages and logs
4. System information (OS, Python version, dependencies)

## Next Steps

After successful migration:

1. **Test All Functionality**: Verify TTS and audio work as expected
2. **Explore New Features**: Try lazy loading, concurrent initialization
3. **Update Documentation**: Update any custom documentation or scripts
4. **Performance Tuning**: Configure caching and optimization settings
5. **API Integration**: Explore new unified web APIs for integrations 