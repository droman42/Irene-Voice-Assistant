# Universal TTS Plugin Documentation

## Overview

The UniversalTTSPlugin is a coordinator plugin that manages multiple Text-to-Speech (TTS) providers through a unified interface. It replaces the previous individual TTS plugins with a single, configurable plugin that can use different TTS backends based on configuration.

## Architecture

### Universal Plugin Pattern
- **Coordinator**: UniversalTTSPlugin manages provider lifecycle and API exposure
- **Providers**: Individual TTS implementations (SileroV3, SileroV4, Pyttsx, Console, ElevenLabs, etc.)
- **Configuration-Driven**: Provider selection and parameters via TOML configuration
- **Unified API**: Single web API endpoint (`/tts/*`) for all TTS functionality

### Key Features

- 🎯 **Multiple Provider Support**: Switch between different TTS engines
- 🔄 **Runtime Provider Switching**: Change TTS provider without restart
- 🔗 **Fallback Mechanism**: Automatic fallback to alternative providers
- 🚀 **Performance Optimized**: Lazy loading, caching, and concurrent initialization
- 🌐 **Web API**: Complete REST API for all TTS operations
- 🎙️ **Voice Commands**: Control TTS settings via voice commands

## Supported Providers

| Provider | Description | Quality | Languages | Real-time |
|----------|-------------|---------|-----------|-----------|
| `silero_v3` | Neural TTS using Silero v3 models | High | Russian | Yes |
| `silero_v4` | Neural TTS using Silero v4 models | Very High | Multilingual | Yes |
| `pyttsx` | Cross-platform TTS using pyttsx3 | Medium | System dependent | Yes |
| `console` | Text output for testing/debugging | N/A | All | Yes |
| `vosk_tts` | TTS functionality from Vosk | Medium | Russian | Yes |
| `elevenlabs` | Cloud-based neural TTS | Very High | Multilingual | Yes* |

*Requires internet connection

## Configuration

### Basic Configuration

```toml
[plugins.universal_tts]
enabled = true
default_provider = "silero_v3"
fallback_providers = ["pyttsx", "console"]
lazy_loading = true
concurrent_initialization = true
load_balancing = false
auto_retry = true
```

### Provider Configuration

#### Silero v3 TTS
```toml
[plugins.universal_tts.providers.silero_v3]
enabled = true
model_path = "~/.cache/irene/models/silero_v3"
model_url = "https://models.silero.ai/models/tts/ru/v3_1_ru.pt"
model_file = "silero_model_v3.pt"
default_speaker = "xenia"
sample_rate = 24000
torch_device = "cpu"
put_accent = true
put_yo = true
threads = 4
```

#### Pyttsx TTS
```toml
[plugins.universal_tts.providers.pyttsx]
enabled = true
voice_rate = 200
voice_volume = 0.9
voice_id = "russian"
```

#### Console TTS (for testing)
```toml
[plugins.universal_tts.providers.console]
enabled = true
color_output = true
timing_simulation = false
```

#### ElevenLabs TTS
```toml
[plugins.universal_tts.providers.elevenlabs]
enabled = false
api_key_env = "ELEVENLABS_API_KEY"
voice_id = "21m00Tcm4TlvDq8ikWAM"
model = "eleven_monolingual_v1"
stability = 0.5
similarity_boost = 0.5
```

### Performance Configuration

```toml
[plugins.universal_tts]
# Enable lazy loading for faster startup
lazy_loading = true

# Enable concurrent initialization for faster loading
concurrent_initialization = true

# Provider caching (automatic for Silero models)
# Shared models across provider instances
```

## API Reference

### Base URL
All TTS endpoints are available under `/tts/` when the web API is enabled.

### Endpoints

#### POST /tts/speak
Convert text to speech and play audio.

**Request Body:**
```json
{
  "text": "Привет, как дела?",
  "provider": "silero_v3",
  "speaker": "xenia",
  "sample_rate": 24000
}
```

**Response:**
```json
{
  "success": true,
  "provider": "silero_v3",
  "text": "Привет, как дела?"
}
```

#### GET /tts/providers
List all available TTS providers and their capabilities.

**Response:**
```json
{
  "providers": {
    "silero_v3": {
      "available": true,
      "parameters": {
        "speaker": {
          "type": "string",
          "options": ["xenia", "aidar", "baya", "kseniya", "eugene"],
          "default": "xenia"
        },
        "sample_rate": {
          "type": "integer",
          "options": [8000, 24000, 48000],
          "default": 24000
        }
      },
      "capabilities": {
        "languages": ["ru"],
        "formats": ["wav"],
        "quality": "high",
        "real_time": true
      }
    }
  },
  "default": "silero_v3"
}
```

#### POST /tts/configure
Configure TTS settings at runtime.

**Request Body:**
```json
{
  "provider": "pyttsx",
  "set_as_default": true
}
```

**Response:**
```json
{
  "success": true,
  "default_provider": "pyttsx"
}
```

## Voice Commands

### Provider Control
- `"переключись на силеро"` - Switch to Silero provider
- `"переключись на pyttsx"` - Switch to Pyttsx provider
- `"покажи голоса"` - Show available providers and voices

### Speech Commands
- `"скажи привет голосом ксении"` - Speak text with specific voice
- `"скажи [текст] голосом [имя]"` - General pattern for voice selection

### Information Commands
- `"покажи провайдеры тts"` - List available TTS providers
- `"какой голос используется"` - Show current default provider

## Usage Examples

### Python API

```python
# Get TTS plugin
tts_plugin = core.plugin_manager.get_plugin("universal_tts")

# Basic speech
await tts_plugin.speak("Привет, мир!")

# With provider selection
await tts_plugin.speak("Hello, world!", provider="elevenlabs", voice_id="custom_voice")

# Generate file
from pathlib import Path
await tts_plugin.to_file("Test speech", Path("output.wav"), provider="silero_v3")
```

### HTTP API

```bash
# Speak text
curl -X POST http://localhost:8000/tts/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Привет, как дела?", "provider": "silero_v3"}'

# List providers
curl http://localhost:8000/tts/providers

# Switch default provider
curl -X POST http://localhost:8000/tts/configure \
  -H "Content-Type: application/json" \
  -d '{"provider": "pyttsx", "set_as_default": true}'
```

## Migration from Legacy Plugins

### Old Configuration (Before Phase 5)
```toml
[plugins.silero_v3_tts]
enabled = true
model_path = "~/.cache/irene/models/silero_v3"
default_speaker = "xenia"

[plugins.pyttsx_tts]
enabled = true
voice_rate = 200
```

### New Configuration (After Phase 5)
```toml
[plugins.universal_tts]
enabled = true
default_provider = "silero_v3"
fallback_providers = ["pyttsx", "console"]

[plugins.universal_tts.providers.silero_v3]
enabled = true
model_path = "~/.cache/irene/models/silero_v3"
default_speaker = "xenia"

[plugins.universal_tts.providers.pyttsx]
enabled = true
voice_rate = 200
```

### Migration Tool
Use the automated migration tool:
```bash
python tools/migrate_to_universal_plugins.py config.toml
```

## Troubleshooting

### Common Issues

#### Provider Not Available
```
ERROR: TTS provider 'silero_v3' not available (dependencies missing)
```
**Solution**: Install required dependencies:
```bash
pip install torch soundfile
```

#### Model Download Failed
```
ERROR: Failed to download Silero v3 model
```
**Solution**: Check internet connection and model URL, or download manually.

#### No Audio Output
```
WARNING: No audio plugins available for playback
```
**Solution**: Ensure UniversalAudioPlugin is enabled and configured.

### Debug Mode
Enable verbose logging:
```toml
[logging]
level = "DEBUG"
```

### Performance Issues
- Enable lazy loading: `lazy_loading = true`
- Use concurrent initialization: `concurrent_initialization = true`
- Check model caching in logs for Silero providers

## Advanced Configuration

### Custom Provider Development
See `docs/examples/tts_provider_example.py` for creating custom TTS providers.

### Load Balancing
```toml
[plugins.universal_tts]
load_balancing = true
provider_weights = {silero_v3 = 0.7, pyttsx = 0.3}
```

### Provider-Specific Settings
Each provider supports unique parameters. Check the provider's `get_parameter_schema()` for available options.

## Related Documentation
- [Universal Audio Plugin](universal_audio.md)
- [Provider Development Guide](../examples/tts_provider_example.py)
- [Migration Guide](migration_guide.md) 