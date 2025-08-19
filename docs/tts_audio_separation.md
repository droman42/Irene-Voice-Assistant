# TTS and Audio Component Separation

## Executive Summary

This document defines the architectural refactoring to properly separate Text-to-Speech (TTS) generation from audio playback in the Irene Voice Assistant. The new architecture mandates workflow-level coordination through temporary files, eliminates mixed responsibilities, and establishes clear component boundaries with no backward compatibility.

## Current Architecture Problems

### Problem 1: Mixed Responsibilities

TTS providers currently have **inconsistent responsibilities**:

- **Silero v3/v4**: Generates audio + handles playback coordination through core.output_manager
- **pyttsx**: Generates audio + plays directly via engine.say()/runAndWait()
- **ElevenLabs**: Generates audio only (relies on caller for playback)

This creates **tight coupling** and **inconsistent behavior** across providers.

### Problem 2: TTS Component Violating Single Responsibility

The TTS Component currently handles playback coordination:

```python
# Current problematic code in Silero provider
core = kwargs.get('core')
if core and hasattr(core, 'output_manager'):
    audio_plugins = getattr(core.output_manager, '_audio_plugins', [])
    for plugin in audio_plugins:
        await plugin.play_file(temp_path)
```

This violates **Single Responsibility Principle** - TTS should focus only on text-to-speech conversion.

### Problem 3: Lack of Workflow Control

Currently, workflows cannot:
- Choose between file output vs stream output
- Control audio playback timing
- Apply audio processing between TTS and playback
- Handle TTS/audio failures separately
- Implement custom audio routing logic
- Configure output format/quality per use case

### Problem 4: Build System Awareness

The build analyzer shows the system recognizes this dependency:

```python
if tts_providers and not audio_providers:
    result.errors.append("TTS providers enabled but no audio output providers configured")
```

This indicates the architecture expects separation but doesn't enforce it properly.

## New Architecture Requirements

### 1. Universal Temporary File Interface

**All TTS-Audio coordination must occur through temporary files:**

```
Workflow Level (Universal Pattern):
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Workflow      │    │ TTS Component   │    │ Audio Component │
│                 │    │                 │    │                 │
│ Orchestration   │───►│ Generate File   │───►│ Play File       │
│ + Temp File Mgmt│    │ (temp_path)     │    │ (temp_path)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2. Mandatory Component Pairing

**Configuration Validation Rule:**
- IF TTS component is configured → Audio component MUST be configured
- IF Audio component configured without TTS → Valid (audio-only use cases)
- Missing Audio when TTS present → **FATAL ERROR at bootstrap**

### 3. No Backward Compatibility

**Complete elimination of legacy functionality:**
- Remove all `speak()` methods from TTS providers
- Remove all audio playback logic from TTS components
- No compatibility layer or migration period
- Clean break from mixed-responsibility pattern

### 4. Workflow-Managed Lifecycle

**Temporary file lifecycle controlled by workflow:**
- Workflow creates unique temporary file path
- Workflow calls `tts.synthesize_to_file(text, temp_path)`
- Workflow calls `audio.play_file(temp_path)`
- **Workflow MUST delete temporary file after playback**
- No automatic cleanup - explicit workflow responsibility

### 5. Global Temporary Storage Configuration

**New configuration parameter for temporary file storage:**
```toml
[storage]
temp_audio_dir = "/path/to/temp/audio"  # Similar to IRENE_ASSETS_ROOT/cache
# Defaults to system temp with irene subdirectory
```

### 6. Parallel Session Safety

**Unique temporary file naming:**
- Random UUID-based filenames: `tts_{uuid4().hex}.wav`
- Prevents conflicts between parallel sessions
- Timestamp prefixes for debugging: `{timestamp}_{uuid}_tts.wav`

## Technical Specifications

### TTS Provider Interface (New)

**Simplified, file-only interface:**

```python
class TTSProvider(ProviderBase):
    @abstractmethod
    async def synthesize_to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """Generate audio file from text - ONLY method required"""
        pass
    
    # NO speak() method - REMOVED
    # NO stream methods - Simplified to file-only approach
```

### Audio Provider Interface (Unchanged)

**File playback interface (already exists):**

```python
class AudioProvider(ProviderBase):
    @abstractmethod
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """Play audio file - Universal approach"""
        pass
    
    # Stream methods remain for future use but not required for TTS integration
```

### Workflow Implementation Pattern

**Mandatory pattern for all TTS-enabled workflows:**

```python
import uuid
from pathlib import Path

async def speak_response(self, text: str):
    # 1. Generate unique temporary file path
    temp_filename = f"tts_{uuid.uuid4().hex}.wav"
    temp_path = self.config.temp_audio_dir / temp_filename
    
    try:
        # 2. TTS generates audio to file
        await self.tts.synthesize_to_file(text, temp_path)
        
        # 3. Audio plays the file
        await self.audio.play_file(temp_path)
        
    finally:
        # 4. MANDATORY cleanup - workflow responsibility
        if temp_path.exists():
            temp_path.unlink()
```

### Configuration Schema

**Required configuration structure:**

```toml
[storage]
temp_audio_dir = "/var/tmp/irene/audio"  # NEW: Global temp audio storage
# Defaults to: {system_temp}/irene/audio/

[components.tts]
enabled = true
default_provider = "silero_v3"

[components.audio]  # MANDATORY if TTS enabled
enabled = true
default_provider = "sounddevice"

# This configuration is INVALID and causes FATAL ERROR:
# [components.tts]
# enabled = true
# [components.audio]
# enabled = false  # ← FATAL: TTS requires Audio component
```

### Bootstrap Validation Rules

**Configuration validation at startup:**

```python
def validate_tts_audio_config(config):
    tts_enabled = config.components.get('tts', {}).get('enabled', False)
    audio_enabled = config.components.get('audio', {}).get('enabled', False)
    
    if tts_enabled and not audio_enabled:
        raise FatalConfigError(
            "TTS component requires Audio component. "
            "Either disable TTS or enable Audio component."
        )
    
    # Audio without TTS is valid (audio-only use cases)
    return True
```



## Benefits Summary

### Architectural Benefits

1. **Clean Separation**: TTS generates files, Audio plays files, Workflow orchestrates
2. **Universal Interface**: All TTS providers use same file-based approach
3. **Explicit Dependencies**: Configuration enforces TTS-Audio pairing
4. **Workflow Control**: Business logic centralized in workflows
5. **Better Testability**: Components can be tested independently

### Operational Benefits

6. **Consistent Behavior**: No provider-specific playback differences
7. **Parallel Safety**: UUID-based filenames prevent conflicts
8. **Error Isolation**: Separate TTS generation and audio playback failures
9. **Resource Management**: Explicit temp file lifecycle control
10. **Configuration Validation**: Invalid configs caught at startup

### Developer Benefits

11. **Simplified Interfaces**: Single method per provider type
12. **No Legacy Complexity**: Clean break from mixed responsibilities
13. **Clear Error Attribution**: Know whether TTS or Audio failed
14. **Predictable Behavior**: Same pattern across all providers
15. **Easier Debugging**: File-based coordination is visible and traceable

## Provider Readiness Analysis

### TTS Providers (File Generation Capability)

| Provider | Library | Current `to_file()` Support | Implementation Required | Migration Effort |
|----------|---------|----------------------------|------------------------|------------------|
| **Silero v3** | PyTorch + torchaudio | ✅ Complete - `model.save_wav()` | Remove `speak()` method only | **Minimal** |
| **Silero v4** | PyTorch + soundfile | ✅ Complete - `sf.write()` | Remove `speak()` method only | **Minimal** |
| **ElevenLabs** | httpx (HTTP API) | ✅ Complete - Downloads to file | Remove `speak()` method only | **Minimal** |
| **pyttsx3** | System TTS engines | ✅ Complete - `engine.save_to_file()` | Remove `speak()` method only | **Minimal** |
| **Vosk TTS** | pyttsx3 wrapper | ✅ Complete - Via pyttsx3 | Remove `speak()` method only | **Minimal** |
| **Console** | Text output only | ✅ Complete - Text to file | Remove `speak()` method only | **Minimal** |

### Audio Providers (File Playback Capability)

| Provider | Library | Current `play_file()` Support | Additional Work Needed | Migration Effort |
|----------|---------|------------------------------|------------------------|------------------|
| **SoundDevice** | sounddevice + soundfile | ✅ Complete and optimized | None | **None** |
| **SimpleAudio** | simpleaudio | ✅ Complete - WAV files only | None | **None** |
| **AudioPlayer** | audioplayer | ✅ Complete - Multi-format | None | **None** |
| **aplay** | System command | ✅ Complete - Via subprocess | None | **None** |
| **Console** | Text output only | ✅ Complete - Debug simulation | None | **None** |

### Implementation Summary

**Excellent News: All providers already support the required functionality!**

#### TTS Providers:
- **All providers** already have working `synthesize_to_file()` methods
- **Only change needed**: Remove `speak()` methods (breaking change)
- **No new functionality** needs to be implemented

#### Audio Providers:
- **All providers** already have working `play_file()` methods
- **No changes needed** - existing interfaces are perfect
- **Universal compatibility** across all audio backends

#### Key Insight:
The universal temp file approach is **already supported** by every provider. The refactoring is primarily about **removing mixed responsibilities** rather than adding new capabilities.

## Final Implementation Architecture

### Universal Pattern (All Providers)

**Single approach for all TTS-Audio coordination:**

```
Workflow → TTS.synthesize_to_file() → Audio.play_file() → Cleanup
          ↓                          ↓                    ↓
     All TTS Providers         All Audio Providers   Delete temp file
```

### Universal Workflow Analysis

**Current Implementation (irene/workflows/voice_assistant.py):**

The `UnifiedVoiceAssistantWorkflow` class is the universal workflow that handles all entry points. Currently it uses the legacy TTS pattern:

```python
# CURRENT (Legacy) - Line 632-639
async def _handle_tts_output(self, result: IntentResult, context: RequestContext):
    """Handle TTS output if TTS component is available"""
    if self.tts and result.text:
        try:
            self.logger.debug(f"Generating TTS for: {result.text[:50]}...")
            await self.tts.speak(result.text)  # ← LEGACY METHOD
        except Exception as e:
            self.logger.warning(f"TTS output failed: {e}")
```

**Required Changes:**

```python
# NEW (Required Implementation)
import uuid
from pathlib import Path

async def _handle_tts_output(self, result: IntentResult, context: RequestContext):
    """Handle TTS output using temp file coordination"""
    if not (self.tts and self.audio and result.text):
        return
        
    # Generate unique temporary file path
    temp_filename = f"tts_{uuid.uuid4().hex}.wav"
    temp_path = self.temp_audio_dir / temp_filename
    
    try:
        # Step 1: TTS generates audio file
        self.logger.debug(f"Generating TTS audio: {temp_path}")
        await self.tts.synthesize_to_file(result.text, temp_path)
        
        # Step 2: Audio plays the file
        self.logger.debug(f"Playing audio file: {temp_path}")
        await self.audio.play_file(temp_path)
        
        self.logger.info(f"Successfully played TTS audio for: {result.text[:50]}...")
        
    except Exception as e:
        self.logger.warning(f"TTS-Audio coordination failed: {e}")
        
    finally:
        # Step 3: MANDATORY cleanup
        if temp_path.exists():
            temp_path.unlink()
            self.logger.debug(f"Cleaned up temp file: {temp_path}")
```

**Additional Changes Required:**

1. **Add temp_audio_dir property** to UnifiedVoiceAssistantWorkflow:
```python
@property
def temp_audio_dir(self) -> Path:
    """Get temp audio directory from injected configuration"""
    config = self.get_component('config')
    if not config:
        raise ConfigValidationError("Configuration not available in workflow")
    return Path(config.storage.temp_audio_dir)
```

2. **Update initialize() method** (lines 387-425) to validate TTS-Audio pairing:
```python
# Add to component validation section (around line 408)
if self.components.get('tts') and not self.components.get('audio'):
    raise ConfigValidationError(
        "TTS component requires Audio component. "
        "Either disable TTS or enable Audio component."
    )
```

3. **Add imports** at top of file:
```python
import uuid
from pathlib import Path
```

4. **Update component assignment** (lines 415-422) to make audio mandatory when TTS present:
```python
self.tts = self.components.get('tts')  # Optional - for audio output
self.audio = self.components.get('audio')  # Required if TTS enabled
```

**Workflow Access to Configuration:**

The workflow needs access to `config.storage.temp_audio_dir`. Current injection pattern in `WorkflowManager._inject_components()` only injects components, not global configuration.

**Two potential solutions:**

**Option A: Inject config through ComponentManager**
```python
# In WorkflowManager._inject_components()
workflow.add_component('config', self.component_manager.config)
```

**Option B: Add config property to Workflow base class**
```python
# In Workflow base class
def set_config(self, config):
    self.config = config

# In WorkflowManager._inject_components()  
workflow.set_config(self.component_manager.config)
```

**Recommended: Option A** - Consistent with existing component injection pattern.

### Configuration Template

**Complete configuration example:**

```toml
# Global storage configuration
[storage]
temp_audio_dir = "/var/tmp/irene/audio"  # Required for TTS-Audio coordination

# TTS component (file generation only)
[components.tts]
enabled = true
default_provider = "silero_v3"

[components.tts.providers.silero_v3]
enabled = true
default_speaker = "xenia"
sample_rate = 24000

# Audio component (MANDATORY when TTS enabled) 
[components.audio]
enabled = true  # Must be true if TTS enabled
default_provider = "sounddevice"

[components.audio.providers.sounddevice]
enabled = true
buffer_size = 4096
default_device = "default"
```

## Implementation Checklist

### Phase 1: Breaking Changes (No Backward Compatibility)

- [x] **Remove `speak()` methods** from all TTS providers
- [x] **Remove audio playback logic** from TTS components  
- [x] **Add bootstrap validation** for TTS-Audio dependency
- [x] **Add temp_audio_dir configuration** parameter
- [x] **Update TTS Component** to only coordinate file generation

### Phase 2: UnifiedVoiceAssistantWorkflow Updates

**Critical Changes to `irene/workflows/voice_assistant.py`:**

- [x] **Update `_handle_tts_output()` method** (lines 632-639) to use temp file pattern
- [x] **Add temp_audio_dir property** to access configuration
- [x] **Add imports**: `import uuid` and `from pathlib import Path`
- [x] **Update initialize() method** to validate TTS-Audio pairing
- [x] **Add TTS-Audio validation** to component checks (line 408-412)
- [x] **Test both entry points** that call `_handle_tts_output()`:
  - `process_text_input()` (line 460)
  - `process_audio_stream()` (line 606)

**Required Changes to `irene/core/workflow_manager.py`:**

- [x] **Update `_inject_components()` method** (lines 76-102) to inject config:
```python
# Add after line 96
workflow.add_component('config', self.component_manager.config)
```

### Phase 3: Configuration & Directory Management

- [x] **Add temp_audio_dir to config schema**
- [x] **Create temp directory structure** on startup
- [x] **Add file permissions validation**
- [x] **Implement UUID-based temp file naming**

### Phase 4: Validation & Testing

- [x] **Configuration validation tests**
- [x] **TTS-Audio integration tests**
- [x] **Parallel session conflict tests**
- [x] **Error condition handling tests**
- [x] **Temp file cleanup verification**

### Phase 5: Documentation

- [ ] **Update provider documentation**
- [ ] **Create workflow migration examples**
- [ ] **Update configuration templates**
- [ ] **Add troubleshooting guide**

## Architecture Principles

This refactoring enforces **strict separation of concerns** where:

1. **TTS Components**: Generate audio files only (single responsibility)
2. **Audio Components**: Play audio files only (single responsibility)  
3. **Workflows**: Orchestrate TTS→Audio coordination (business logic)
4. **Configuration**: Validates component dependencies (fail-fast)
5. **Temp Files**: Universal handover mechanism (simple, traceable)

The result is a **clean, predictable, and maintainable** architecture with no legacy complexity.
