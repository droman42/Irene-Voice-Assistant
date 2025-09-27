# Donation File Specification - Contextual Commands

## Overview

This document specifies the donation file format for intent handlers that support contextual command disambiguation (Phase 4 TODO16). Donation files define handler capabilities, domain priorities, and contextual command patterns.

## Table of Contents

1. [File Format](#file-format)
2. [Core Fields](#core-fields)
3. [Contextual Commands Section](#contextual-commands-section)
4. [Domain Priority Configuration](#domain-priority-configuration)
5. [Intent Definitions](#intent-definitions)
6. [Localization Support](#localization-support)
7. [Performance Configuration](#performance-configuration)
8. [Validation Rules](#validation-rules)
9. [Examples](#examples)

## File Format

Donation files are JSON documents located in `assets/donations/{handler_name}/{language}.json`.

### File Structure

```
assets/
└── donations/
    ├── audio_playback_handler/
    │   ├── en.json
    │   └── ru.json
    ├── timer_handler/
    │   ├── en.json
    │   └── ru.json
    └── my_custom_handler/
        ├── en.json
        └── ru.json
```

### Basic Template

```json
{
  "handler_name": "my_handler",
  "display_name": "My Handler",
  "description": "Handler description",
  "domain": "my_domain",
  "version": "1.0.0",
  "action_domain_priority": 75,
  "contextual_commands": {
    "stop": {
      "patterns": ["stop", "halt"],
      "description": "Stop actions",
      "destructive": true
    }
  },
  "intents": {
    "my_domain.action": {
      "description": "Action description",
      "parameters": []
    }
  }
}
```

## Core Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `handler_name` | string | Unique identifier for the handler |
| `display_name` | string | Human-readable handler name |
| `description` | string | Brief description of handler functionality |
| `domain` | string | Domain this handler manages |
| `version` | string | Handler version (semantic versioning) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `action_domain_priority` | integer | 50 | Priority for contextual command disambiguation (1-100) |
| `enabled` | boolean | true | Whether handler is enabled by default |
| `dependencies` | array | [] | List of required dependencies |
| `tags` | array | [] | Categorization tags |

### Example Core Section

```json
{
  "handler_name": "audio_playback_handler",
  "display_name": "Audio Playback Handler",
  "description": "Manages audio playback with support for contextual commands",
  "domain": "audio",
  "version": "2.1.0",
  "action_domain_priority": 90,
  "enabled": true,
  "dependencies": ["audio_component", "media_library"],
  "tags": ["media", "entertainment", "audio"]
}
```

## Contextual Commands Section

The `contextual_commands` section defines which contextual commands the handler supports and their patterns.

### Structure

```json
{
  "contextual_commands": {
    "command_type": {
      "patterns": ["pattern1", "pattern2"],
      "description": "Command description",
      "destructive": boolean,
      "confirmation_required": boolean,
      "aliases": ["alias1", "alias2"],
      "parameters": []
    }
  }
}
```

### Command Types

#### Standard Command Types

| Command | Description | Typical Use |
|---------|-------------|-------------|
| `stop` | Stop/halt active actions | Stop music, stop timer |
| `pause` | Temporarily pause actions | Pause music, pause timer |
| `resume` | Resume paused actions | Resume music, resume timer |
| `cancel` | Cancel and remove actions | Cancel timer, cancel download |
| `volume` | Adjust volume/intensity | Volume up, volume down |
| `next` | Move to next item | Next song, next item |
| `previous` | Move to previous item | Previous song, previous item |

#### Custom Command Types

Handlers can define custom contextual commands:

```json
{
  "contextual_commands": {
    "restart": {
      "patterns": ["restart", "reboot", "reset"],
      "description": "Restart the service",
      "destructive": true,
      "confirmation_required": true
    },
    "status": {
      "patterns": ["status", "info", "state"],
      "description": "Get current status",
      "destructive": false
    }
  }
}
```

### Command Properties

#### patterns (required)

Array of text patterns that trigger this command:

```json
{
  "stop": {
    "patterns": [
      "stop",
      "halt", 
      "end",
      "terminate",
      "cease"
    ]
  }
}
```

#### description (required)

Human-readable description of what the command does:

```json
{
  "pause": {
    "description": "Temporarily pause active audio playback"
  }
}
```

#### destructive (optional, default: false)

Whether the command is destructive (requires confirmation in ambiguous cases):

```json
{
  "cancel": {
    "destructive": true  // Requires confirmation if ambiguous
  },
  "pause": {
    "destructive": false  // No confirmation needed
  }
}
```

#### confirmation_required (optional, default: false)

Force confirmation even for unambiguous commands:

```json
{
  "stop": {
    "confirmation_required": true  // Always ask for confirmation
  }
}
```

#### aliases (optional)

Alternative names for the command:

```json
{
  "volume": {
    "patterns": ["volume up", "louder", "increase volume"],
    "aliases": ["vol", "sound", "audio_level"]
  }
}
```

#### parameters (optional)

Parameters the command accepts:

```json
{
  "volume": {
    "parameters": [
      {
        "name": "level",
        "type": "integer",
        "required": false,
        "min": 0,
        "max": 100,
        "description": "Volume level (0-100)"
      },
      {
        "name": "direction",
        "type": "string",
        "required": false,
        "enum": ["up", "down"],
        "description": "Volume direction"
      }
    ]
  }
}
```

### Complete Contextual Commands Example

```json
{
  "contextual_commands": {
    "stop": {
      "patterns": ["stop", "halt", "end", "cease"],
      "description": "Stop all active audio playback",
      "destructive": true,
      "confirmation_required": false,
      "aliases": ["terminate", "kill"]
    },
    "pause": {
      "patterns": ["pause", "hold", "suspend"],
      "description": "Pause active audio playback",
      "destructive": false,
      "aliases": ["freeze", "wait"]
    },
    "resume": {
      "patterns": ["resume", "continue", "unpause", "play"],
      "description": "Resume paused audio playback",
      "destructive": false,
      "aliases": ["restart", "proceed"]
    },
    "volume": {
      "patterns": ["volume", "louder", "quieter", "sound"],
      "description": "Adjust audio volume",
      "destructive": false,
      "parameters": [
        {
          "name": "level",
          "type": "integer",
          "required": false,
          "min": 0,
          "max": 100
        },
        {
          "name": "direction",
          "type": "string",
          "required": false,
          "enum": ["up", "down", "mute"]
        }
      ]
    },
    "next": {
      "patterns": ["next", "skip", "forward"],
      "description": "Skip to next audio track",
      "destructive": false
    },
    "previous": {
      "patterns": ["previous", "back", "last", "rewind"],
      "description": "Go to previous audio track", 
      "destructive": false
    }
  }
}
```

## Domain Priority Configuration

The `action_domain_priority` field determines handler priority during contextual command disambiguation.

### Priority Ranges

| Range | Category | Examples |
|-------|----------|----------|
| 90-100 | Critical/Emergency | Audio playback, emergency stops |
| 70-89 | High Priority | Timers, alarms, primary user tasks |
| 50-69 | Medium Priority | Voice synthesis, notifications |
| 30-49 | Low Priority | System monitoring, background tasks |
| 10-29 | Minimal Priority | Logging, cleanup, maintenance |

### Priority Guidelines

```json
{
  "action_domain_priority": 90,  // Audio playback (high user impact)
  
  "action_domain_priority": 70,  // Timer (important but not critical)
  
  "action_domain_priority": 60,  // Voice synthesis (can be interrupted)
  
  "action_domain_priority": 50,  // System info (default priority)
  
  "action_domain_priority": 30   // Background monitoring (low priority)
}
```

### Priority Considerations

1. **User Impact**: Higher priority for actions that directly affect user experience
2. **Interruption Cost**: Higher priority for actions that are expensive to restart
3. **Safety**: Higher priority for safety-critical operations
4. **Resource Usage**: Higher priority for resource-intensive operations

## Intent Definitions

The `intents` section defines the specific intents the handler can process.

### Intent Structure

```json
{
  "intents": {
    "intent_name": {
      "description": "Intent description",
      "parameters": [
        {
          "name": "parameter_name",
          "type": "parameter_type",
          "required": boolean,
          "description": "Parameter description",
          "default": "default_value",
          "enum": ["option1", "option2"],
          "min": minimum_value,
          "max": maximum_value
        }
      ],
      "examples": ["example utterance 1", "example utterance 2"],
      "confidence_threshold": 0.7
    }
  }
}
```

### Parameter Types

| Type | Description | Validation |
|------|-------------|------------|
| `string` | Text value | `min_length`, `max_length`, `pattern` |
| `integer` | Whole number | `min`, `max` |
| `float` | Decimal number | `min`, `max` |
| `boolean` | True/false | None |
| `array` | List of values | `min_items`, `max_items`, `item_type` |
| `object` | Complex object | `properties` schema |
| `enum` | Fixed set of values | `enum` array |

### Intent Examples

```json
{
  "intents": {
    "audio.play": {
      "description": "Play audio content",
      "parameters": [
        {
          "name": "source",
          "type": "string",
          "required": true,
          "description": "Audio source (file, URL, or search query)"
        },
        {
          "name": "volume",
          "type": "integer",
          "required": false,
          "min": 0,
          "max": 100,
          "default": 50,
          "description": "Playback volume (0-100)"
        },
        {
          "name": "repeat",
          "type": "boolean",
          "required": false,
          "default": false,
          "description": "Whether to repeat playback"
        }
      ],
      "examples": [
        "play music",
        "play beethoven symphony",
        "play podcast about technology"
      ],
      "confidence_threshold": 0.8
    },
    "audio.stop": {
      "description": "Stop audio playback",
      "parameters": [],
      "examples": ["stop music", "halt audio", "end playback"]
    },
    "audio.volume": {
      "description": "Adjust audio volume",
      "parameters": [
        {
          "name": "level",
          "type": "integer",
          "required": false,
          "min": 0,
          "max": 100,
          "description": "Target volume level"
        },
        {
          "name": "direction",
          "type": "enum",
          "enum": ["up", "down", "mute"],
          "required": false,
          "description": "Volume adjustment direction"
        }
      ],
      "examples": [
        "volume up",
        "set volume to 50",
        "mute audio",
        "louder"
      ]
    }
  }
}
```

## Localization Support

Donation files support multiple languages through separate files per language.

### Language Files

```
assets/donations/audio_playback_handler/
├── en.json     # English
├── ru.json     # Russian  
├── es.json     # Spanish
└── fr.json     # French
```

### Language-Specific Patterns

Each language file contains localized patterns:

```json
// en.json
{
  "contextual_commands": {
    "stop": {
      "patterns": ["stop", "halt", "end", "cease"],
      "description": "Stop audio playback"
    }
  }
}

// ru.json
{
  "contextual_commands": {
    "stop": {
      "patterns": ["стоп", "останови", "прекрати", "завершить"],
      "description": "Остановить воспроизведение аудио"
    }
  }
}
```

### Localization Guidelines

1. **Cultural Adaptation**: Adapt patterns to local speech patterns
2. **Formal/Informal**: Include both formal and informal variants
3. **Synonyms**: Include common synonyms and variations
4. **Abbreviations**: Include common abbreviations where appropriate

## Performance Configuration

Optional performance settings for the handler:

```json
{
  "performance": {
    "max_concurrent_actions": 10,
    "action_timeout_seconds": 300,
    "cleanup_interval_seconds": 60,
    "cache_size": 100,
    "cache_ttl_seconds": 300,
    "enable_metrics": true,
    "latency_threshold_ms": 5.0
  }
}
```

### Performance Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_concurrent_actions` | integer | 10 | Maximum concurrent actions |
| `action_timeout_seconds` | integer | 300 | Action timeout in seconds |
| `cleanup_interval_seconds` | integer | 60 | Cleanup interval in seconds |
| `cache_size` | integer | 100 | Cache size limit |
| `cache_ttl_seconds` | integer | 300 | Cache TTL in seconds |
| `enable_metrics` | boolean | true | Enable performance metrics |
| `latency_threshold_ms` | float | 5.0 | Latency threshold in milliseconds |

## Validation Rules

### Required Validations

1. **Handler Name**: Must be unique, alphanumeric with underscores
2. **Domain**: Must be unique across handlers
3. **Version**: Must follow semantic versioning (x.y.z)
4. **Priority**: Must be integer between 1-100
5. **Patterns**: Must be non-empty arrays of strings
6. **Intent Names**: Must follow domain.action format

### Schema Validation

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["handler_name", "display_name", "description", "domain", "version"],
  "properties": {
    "handler_name": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_]+$",
      "minLength": 1,
      "maxLength": 50
    },
    "display_name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 100
    },
    "domain": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_]+$",
      "minLength": 1,
      "maxLength": 30
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "action_domain_priority": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100
    },
    "contextual_commands": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z0-9_]+$": {
          "type": "object",
          "required": ["patterns", "description"],
          "properties": {
            "patterns": {
              "type": "array",
              "items": {"type": "string"},
              "minItems": 1
            },
            "description": {
              "type": "string",
              "minLength": 1
            },
            "destructive": {"type": "boolean"},
            "confirmation_required": {"type": "boolean"}
          }
        }
      }
    }
  }
}
```

## Examples

### Complete Audio Handler Example

```json
{
  "handler_name": "audio_playback_handler",
  "display_name": "Audio Playback Handler",
  "description": "Manages audio playback with full contextual command support",
  "domain": "audio",
  "version": "2.1.0",
  "action_domain_priority": 90,
  "enabled": true,
  "dependencies": ["audio_component", "media_library"],
  "tags": ["media", "entertainment", "audio"],
  
  "contextual_commands": {
    "stop": {
      "patterns": ["stop", "halt", "end", "cease", "terminate"],
      "description": "Stop all active audio playback",
      "destructive": true,
      "aliases": ["kill", "abort"]
    },
    "pause": {
      "patterns": ["pause", "hold", "suspend", "freeze"],
      "description": "Pause active audio playback",
      "destructive": false
    },
    "resume": {
      "patterns": ["resume", "continue", "unpause", "play"],
      "description": "Resume paused audio playback",
      "destructive": false
    },
    "volume": {
      "patterns": ["volume", "louder", "quieter", "sound level"],
      "description": "Adjust audio volume",
      "destructive": false,
      "parameters": [
        {
          "name": "level",
          "type": "integer",
          "required": false,
          "min": 0,
          "max": 100,
          "description": "Target volume level (0-100)"
        },
        {
          "name": "direction",
          "type": "enum",
          "enum": ["up", "down", "mute"],
          "required": false,
          "description": "Volume adjustment direction"
        }
      ]
    },
    "next": {
      "patterns": ["next", "skip", "forward", "next song"],
      "description": "Skip to next audio track",
      "destructive": false
    },
    "previous": {
      "patterns": ["previous", "back", "last", "previous song"],
      "description": "Go to previous audio track",
      "destructive": false
    }
  },
  
  "intents": {
    "audio.play": {
      "description": "Play audio content",
      "parameters": [
        {
          "name": "source",
          "type": "string",
          "required": true,
          "description": "Audio source (file, URL, or search query)"
        },
        {
          "name": "volume",
          "type": "integer",
          "required": false,
          "min": 0,
          "max": 100,
          "default": 50
        }
      ],
      "examples": ["play music", "play beethoven", "start audio"],
      "confidence_threshold": 0.8
    },
    "audio.stop": {
      "description": "Stop audio playback",
      "parameters": [],
      "examples": ["stop music", "halt audio"]
    },
    "audio.pause": {
      "description": "Pause audio playback",
      "parameters": [],
      "examples": ["pause music", "hold audio"]
    },
    "audio.resume": {
      "description": "Resume audio playback",
      "parameters": [],
      "examples": ["resume music", "continue audio"]
    },
    "audio.volume": {
      "description": "Adjust audio volume",
      "parameters": [
        {
          "name": "level",
          "type": "integer",
          "required": false,
          "min": 0,
          "max": 100
        }
      ],
      "examples": ["volume up", "set volume 50", "mute"]
    },
    "audio.next": {
      "description": "Next audio track",
      "parameters": [],
      "examples": ["next song", "skip track"]
    },
    "audio.previous": {
      "description": "Previous audio track", 
      "parameters": [],
      "examples": ["previous song", "last track"]
    }
  },
  
  "performance": {
    "max_concurrent_actions": 5,
    "action_timeout_seconds": 1800,
    "cleanup_interval_seconds": 30,
    "cache_size": 50,
    "enable_metrics": true,
    "latency_threshold_ms": 3.0
  }
}
```

### Simple Timer Handler Example

```json
{
  "handler_name": "timer_handler",
  "display_name": "Timer Handler",
  "description": "Manages timers and alarms with contextual commands",
  "domain": "timer",
  "version": "1.5.0",
  "action_domain_priority": 70,
  
  "contextual_commands": {
    "stop": {
      "patterns": ["stop", "cancel", "end"],
      "description": "Stop active timers",
      "destructive": true
    },
    "pause": {
      "patterns": ["pause", "hold"],
      "description": "Pause active timers",
      "destructive": false
    },
    "resume": {
      "patterns": ["resume", "continue"],
      "description": "Resume paused timers",
      "destructive": false
    }
  },
  
  "intents": {
    "timer.set": {
      "description": "Set a new timer",
      "parameters": [
        {
          "name": "duration",
          "type": "integer",
          "required": true,
          "min": 1,
          "description": "Timer duration in seconds"
        },
        {
          "name": "name",
          "type": "string",
          "required": false,
          "description": "Timer name"
        }
      ]
    },
    "timer.stop": {
      "description": "Stop timer",
      "parameters": []
    },
    "timer.pause": {
      "description": "Pause timer",
      "parameters": []
    },
    "timer.resume": {
      "description": "Resume timer",
      "parameters": []
    }
  }
}
```

This specification ensures consistent, comprehensive donation files that fully support the contextual command disambiguation system while maintaining backward compatibility and extensibility.
