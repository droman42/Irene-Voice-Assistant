# Platform Dependency Harmonization Plan

## 📋 Overview

This document outlines the implementation plan for harmonizing platform naming inconsistencies between `get_platform_support()` and `get_platform_dependencies()` methods across the Irene Voice Assistant codebase.

## 🔍 Problem Analysis

### Current Inconsistency

**`get_platform_support()` returns:**
- `["linux", "windows", "macos"]` (generic OS names)
- Sometimes includes: `"armv7"` (architecture-specific)

**`get_platform_dependencies()` expects keys:**
- `"ubuntu"` (specific Linux distribution)
- `"alpine"` (specific Linux distribution) 
- `"centos"` (specific Linux distribution)
- `"macos"` (generic OS name)

### Root Cause

The inconsistency stems from mixing **logical platform support** (OS capability) with **physical platform implementation** (distribution-specific packages). The build system needs to know:

1. **What OSes can run this?** (platform support)
2. **What packages does each distribution need?** (platform dependencies)

### Current Usage Analysis

**Build System Usage:**
- Docker builds use `--platform linux.ubuntu` and `--platform linux.alpine`
- Build analyzer maps to specific distributions: Ubuntu for x86_64, Alpine for ARMv7
- Dependency validator validates against distribution-specific package repositories

**Platform Support Semantics:**
- `get_platform_support()` indicates **capability** (can this run on this OS?)
- `get_platform_dependencies()` provides **implementation** (what packages does this distribution need?)

**Docker Architecture:**
- x86_64 builds → Ubuntu base → `"ubuntu"` packages (apt)
- ARMv7 builds → Alpine base → `"alpine"` packages (apk)
- The system needs distribution-specific package managers

## 🎯 Chosen Solution: Option 2 - Standardized Keys with Dot Notation

### New Platform Keys

**Current:** `["ubuntu", "alpine", "centos", "macos"]`  
**New:** `["linux.ubuntu", "linux.alpine", "macos", "windows"]`

### Rationale for Changes

- ✅ **Remove CentOS** - Project doesn't support it today  
- ✅ **Add Windows** - Many providers support it but it's missing from dependency keys
- ✅ **Standardize Linux distributions** - Use `linux.ubuntu` and `linux.alpine` dot notation
- ✅ **Keep macOS** - Maintain as `macos` (already platform-specific)

### Benefits

1. **Clear separation of concerns** - platform support vs implementation details
2. **Backward compatible** - existing logic can map `linux` → `linux.ubuntu`
3. **Future-proof** - easily add new distributions like `linux.fedora`
4. **Docker-friendly** - matches actual build target naming
5. **Validation-ready** - dependency validator can ensure consistency

## 📊 Scope Analysis

**Total Entry Points to Update:** **49 files** identified

### Provider Categories

- **6 TTS Providers** (console, pyttsx, silero_v3, silero_v4, elevenlabs, vosk)
- **3 ASR Providers** (vosk, google_cloud, whisper)  
- **4 Audio Providers** (aplay, audioplayer, simpleaudio, sounddevice, console)
- **3 NLU Providers** (spacy, hybrid_keyword_matcher, rule_based)
- **4 Text Processing Providers** (number, general, tts, asr)
- **2 Voice Trigger Providers** (microwakeword, openwakeword)
- **3 LLM Providers** (vsegpt, anthropic, openai)
- **12 Intent Handlers** (various handlers)
- **5 Components** (base, intent, text_processor, nlu, voice_trigger)
- **Core Classes** (workflows, plugins, inputs, metadata interface)

### Platform Support Patterns

**Linux-Only Providers** (return empty for `macos`, `windows`):
- `aplay` (line 107: only supports `["linux"]`)

**Cross-Platform Providers** (support all platforms):
- All TTS providers
- All ASR providers  
- Most audio providers
- All NLU providers
- All text processing providers
- All voice trigger providers  
- All LLM providers

**Platform-Specific Package Requirements:**
- **Audio providers:** `libportaudio2` (Ubuntu) → `portaudio-dev` (Alpine)
- **ML providers:** `libsndfile1` (Ubuntu) → `libsndfile-dev` (Alpine)
- **Build tools:** `build-essential` (Ubuntu) → `build-base` (Alpine)

## 📋 Implementation Phases

### Phase 1: Core Infrastructure Update ✅ COMPLETED

#### 1.1 Update Core Metadata Interface ✅ COMPLETED

**File:** `irene/core/metadata.py`

**Changes Required:**
- Update `get_platform_dependencies()` default return from:
  ```python
  return {
      "ubuntu": [],
      "alpine": [],
      "centos": [],
      "macos": []
  }
  ```
  
  To:
  ```python
  return {
      "linux.ubuntu": [],
      "linux.alpine": [],
      "macos": [],
      "windows": []
  }
  ```

- Update docstring examples to use new platform keys
- Update comment explanations for platform mapping

#### 1.2 Update Base Classes ✅ COMPLETED

**Files to Update:**
- `irene/components/base.py` ✅ COMPLETED
- `irene/workflows/base.py` ✅ COMPLETED
- `irene/plugins/base.py` ✅ COMPLETED
- `irene/intents/handlers/base.py` ✅ COMPLETED
- `irene/inputs/base.py` ✅ COMPLETED

**Pattern:** Replace platform dependency dictionary in each base class implementation.

### Phase 2: Build System Infrastructure ✅ COMPLETED

#### 2.1 Update Build Analyzer ✅ COMPLETED

**File:** `irene/tools/build_analyzer.py`

**Changes Required:**
- Line 676: Update platforms list from `["ubuntu", "alpine", "centos", "macos"]` to `["linux.ubuntu", "linux.alpine", "macos", "windows"]`
- Update platform mapping logic to handle dot notation
- Update validation for new platform keys
- Add backward compatibility mapping: `ubuntu` → `linux.ubuntu`, `alpine` → `linux.alpine`

#### 2.2 Update Dependency Validator ✅ COMPLETED

**File:** `irene/tools/dependency_validator.py`

**Changes Required:**
- Lines 91-107: Update `_known_packages` dictionary keys:
  ```python
  self._known_packages = {
      "linux.ubuntu": {
          "libportaudio2", "libsndfile1", "libffi-dev", "ffmpeg", "espeak", "espeak-data",
          "alsa-utils", "libavformat58", "libavcodec58", "libasound2-dev", "libatomic1"
      },
      "linux.alpine": {
          "portaudio-dev", "libsndfile-dev", "libffi-dev", "ffmpeg", "espeak", "espeak-data",
          "alsa-utils", "ffmpeg-dev", "alsa-lib-dev", "libatomic", "ffmpeg-libs"
      },
      "macos": {
          "portaudio", "libsndfile", "libffi", "ffmpeg", "espeak"
      },
      "windows": {
          # Windows package validation typically not needed
      }
  }
  ```
- Remove CentOS package validation
- Update platform consistency validation logic

### Phase 3: Provider Implementation Updates ✅ COMPLETED

#### 3.1 Implementation Patterns

**Pattern A: No System Dependencies (most common)**
```python
@classmethod  
def get_platform_dependencies(cls) -> Dict[str, List[str]]:
    """[Provider] has no system dependencies"""
    return {
        "linux.ubuntu": [],
        "linux.alpine": [],
        "macos": [],
        "windows": []
    }
```

**Pattern B: Audio/ML Dependencies**
```python
@classmethod  
def get_platform_dependencies(cls) -> Dict[str, List[str]]:
    """Platform-specific system packages for [Provider]"""
    return {
        "linux.ubuntu": ["libportaudio2", "libsndfile1"],
        "linux.alpine": ["portaudio-dev", "libsndfile-dev"],
        "macos": [],  # Homebrew handles dependencies
        "windows": []  # Windows package management differs
    }
```

**Pattern C: Linux-Only Providers**
```python
@classmethod  
def get_platform_dependencies(cls) -> Dict[str, List[str]]:
    """Platform-specific system packages for [Provider]"""
    return {
        "linux.ubuntu": ["alsa-utils"],
        "linux.alpine": ["alsa-utils"],  
        "macos": [],  # Not supported
        "windows": []  # Not supported
    }
```

#### 3.2 Provider-Specific Updates

**TTS Providers (6 files):**
- `irene/providers/tts/console.py` - Pattern A
- `irene/providers/tts/elevenlabs.py` - Pattern A  
- `irene/providers/tts/pyttsx.py` - Pattern B (espeak dependencies)
- `irene/providers/tts/silero_v3.py` - Pattern B (libsndfile dependencies)
- `irene/providers/tts/silero_v4.py` - Pattern B (libsndfile dependencies)
- `irene/providers/tts/vosk.py` - Pattern B (libffi dependencies)

**ASR Providers (3 files):**
- `irene/providers/asr/google_cloud.py` - Pattern A
- `irene/providers/asr/whisper.py` - Pattern B (ffmpeg dependencies)
- `irene/providers/asr/vosk.py` - Pattern B (libffi dependencies)

**Audio Providers (4 files):**
- `irene/providers/audio/aplay.py` - Pattern C (Linux-only, alsa-utils)
- `irene/providers/audio/audioplayer.py` - Pattern A
- `irene/providers/audio/simpleaudio.py` - Pattern A
- `irene/providers/audio/sounddevice.py` - Pattern B (portaudio dependencies)
- `irene/providers/audio/console.py` - Pattern A

**NLU Providers (3 files):**
- `irene/providers/nlu/spacy_provider.py` - Pattern B (build-essential dependencies)
- `irene/providers/nlu/hybrid_keyword_matcher.py` - Pattern B (build-essential dependencies)
- `irene/providers/nlu/rule_based.py` - Pattern A

**Text Processing Providers (4 files):**
- All use Pattern A (no system dependencies)

**Voice Trigger Providers (2 files):**
- Both use Pattern A (pure Python/TensorFlow)

**LLM Providers (3 files):**
- All use Pattern A (cloud-based, no system dependencies)

**Intent Handlers (12 files):**
- All use Pattern A (pure logic, no system dependencies)

**Components and Core Classes (5+ files):**
- All use Pattern A (coordination only, no direct dependencies)

### Phase 4: Docker and Configuration Updates ✅ COMPLETED

#### 4.1 Docker Build Scripts ✅ COMPLETED

**Files:** `Dockerfile.x86_64`, `Dockerfile.armv7`

**Changes Required:**
- ✅ `Dockerfile.x86_64` Line 46: Update `--platform ubuntu` to `--platform linux.ubuntu`
- ✅ `Dockerfile.armv7` Line 45: Update `--platform alpine` to `--platform linux.alpine`

#### 4.2 Build Analyzer Platform Mapping ✅ COMPLETED

**Changes Required:**
- ✅ Update platform argument parsing to accept both old and new formats
- ✅ Maintain backward compatibility during transition:
  - ✅ `ubuntu` → `linux.ubuntu` (with deprecation warning)
  - ✅ `alpine` → `linux.alpine` (with deprecation warning)
  - ✅ `centos` → removed (error message)
  - ✅ `macos` → `macos` (unchanged)
  - ✅ `windows` → `windows` (new)

### Phase 5: Documentation and Examples ✅ COMPLETED

#### 5.1 Update Documentation ✅ COMPLETED

**Files to Update:**
- ✅ `docs/TODO/TODO05.md` - Update platform examples
- ✅ `README-BUILD.md` - Update platform examples  
- ✅ `README-DOCKER.md` - Update platform flags (already used correct Docker platform syntax)
- ✅ External package integration examples

**Changes Required:**
- ✅ Replace all instances of old platform keys with new standardized keys
- ✅ Update command examples to use new platform flags
- ✅ Document migration path for external packages

#### 5.2 Update External Package Documentation ✅ COMPLETED

**Changes Required:**
- ✅ Update examples showing proper platform keys
- ✅ Update validation examples
- ✅ Provide migration guide for third-party packages

## 🔄 Migration Strategy

### Backward Compatibility Approach

1. **Build Analyzer**: Accept both old (`ubuntu`) and new (`linux.ubuntu`) formats initially
2. **Dependency Validator**: Map old keys to new keys during validation  
3. **Docker Builds**: Update to use new format but document old format deprecation
4. **Gradual Migration**: Providers can be updated incrementally

### Rollout Order

1. **Core Infrastructure** (Phase 1) - Foundation changes
2. **Build System** (Phase 2) - Critical tooling updates  
3. **Provider Updates** (Phase 3) - Bulk implementation updates
4. **Docker & Config** (Phase 4) - Deployment updates
5. **Documentation** (Phase 5) - User-facing updates

### External Package Migration Guide

**For Third-Party Package Developers:**

1. **Update Platform Keys**: Replace old platform keys in both `get_platform_dependencies()` and `get_platform_support()` implementations:
   ```python
   # OLD format (deprecated) - Both methods inconsistent
   def get_platform_support(cls) -> List[str]:
       return ["linux", "windows", "macos"]
   
   def get_platform_dependencies(cls) -> Dict[str, List[str]]:
       return {
           "ubuntu": ["libmylib-dev"],
           "alpine": ["mylib-dev"], 
           "centos": ["mylib-devel"],
           "macos": []
       }
   
   # NEW format (required) - Both methods harmonized
   def get_platform_support(cls) -> List[str]:
       return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
   
   def get_platform_dependencies(cls) -> Dict[str, List[str]]:
       return {
           "linux.ubuntu": ["libmylib-dev"],
           "linux.alpine": ["mylib-dev"], 
           "macos": [],
           "windows": []  # Add Windows support
       }
   ```

2. **Update Command Examples**: Replace platform flags in documentation:
   ```bash
   # OLD command (deprecated)
   python -m irene.tools.dependency_validator --platform ubuntu
   
   # NEW command (required)
   python -m irene.tools.dependency_validator --platform linux.ubuntu
   ```

3. **Test Migration**: Validate your package works with new platform keys:
   ```bash
   # Test your external package
   python -m irene.tools.dependency_validator \
       --file your_package/providers/my_provider.py \
       --class MyProvider \
       --platform linux.ubuntu
   ```

4. **Backward Compatibility**: The build analyzer provides automatic mapping during transition period, but update your implementations to avoid deprecation warnings.

5. **Verify Consistency**: Ensure your `get_platform_support()` and `get_platform_dependencies()` methods use identical platform keys to avoid validation warnings.

### Validation Strategy

1. **Unit Tests**: Update all platform dependency tests
2. **Integration Tests**: Validate build analyzer works with new keys
3. **Docker Tests**: Ensure builds work with new platform flags
4. **Cross-Platform Tests**: Validate dependency resolution for all platforms

## 🧪 Testing Plan

### Test Categories

1. **Metadata Validation**: All 49 entry points return correct new platform keys
2. **Build Analyzer**: Generates correct dependencies for `linux.ubuntu` and `linux.alpine`
3. **Dependency Validator**: Validates packages exist in respective repositories
4. **Docker Builds**: Successfully build images with new platform flags
5. **Backward Compatibility**: Old platform flags still work during transition

### Test Commands

```bash
# Validate all providers use new platform keys
python -m irene.tools.dependency_validator --validate-all --platforms linux.ubuntu,linux.alpine,macos,windows

# Test build analyzer with new platforms  
python -m irene.tools.build_analyzer --config configs/voice.toml --platform linux.ubuntu
python -m irene.tools.build_analyzer --config configs/voice.toml --platform linux.alpine

# Test Docker builds
docker build -f Dockerfile.x86_64 --build-arg CONFIG_PROFILE=voice .
docker build -f Dockerfile.armv7 --build-arg CONFIG_PROFILE=embedded-armv7 .

# Test backward compatibility (should issue deprecation warnings)
python -m irene.tools.build_analyzer --config configs/voice.toml --platform ubuntu
python -m irene.tools.build_analyzer --config configs/voice.toml --platform alpine
```

### Validation Checklist

- [ ] All 49 entry points updated with new platform keys
- [ ] Build analyzer accepts new platform arguments
- [ ] Dependency validator validates against new platform repositories
- [ ] Docker builds succeed with new platform flags
- [ ] All tests pass with new platform naming
- [ ] Documentation updated with new examples
- [ ] Backward compatibility maintained during transition

### Phase 6: Platform Support Method Harmonization ✅ COMPLETED

#### 6.1 Critical Semantic Inconsistency

**Problem**: After completing Phases 1-5, a critical inconsistency remains between `get_platform_support()` and `get_platform_dependencies()` methods:

**Current State (Inconsistent):**
```python
# get_platform_support() returns generic OS names
def get_platform_support(cls) -> List[str]:
    return ["linux", "windows", "macos"]  # Generic capabilities

# get_platform_dependencies() expects specific distribution keys (Phase 3 ✅ COMPLETED)
def get_platform_dependencies(cls) -> Dict[str, List[str]]:
    return {
        "linux.ubuntu": [packages],      # Specific distributions
        "linux.alpine": [packages], 
        "macos": [packages],
        "windows": [packages]
    }
```

**Validation Issue:**
The dependency validator's platform consistency check fails:
```python
for platform in platform_support:  # ["linux", "windows", "macos"] 
    if platform not in platform_deps:  # Keys: ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        result.warnings.append(f"Platform '{platform}' in support list but no dependencies defined")
```

This creates false warnings because `"linux"` is supported but only `"linux.ubuntu"` and `"linux.alpine"` have dependency mappings.

#### 6.2 Required Harmonization

**Update all `get_platform_support()` implementations** to use the same platform keys as `get_platform_dependencies()`:

**Before (Current - Inconsistent):**
```python
def get_platform_support(cls) -> List[str]:
    return ["linux", "windows", "macos"]
```

**After (Required - Harmonized):**
```python
def get_platform_support(cls) -> List[str]:
    return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
```

#### 6.3 Implementation Scope

**Files to Update:** Same 49 files that were updated in Phase 3
- 6 TTS providers: console, elevenlabs, pyttsx, silero_v3, silero_v4, vosk
- 3 ASR providers: google_cloud, whisper, vosk  
- 5 Audio providers: aplay, audioplayer, simpleaudio, sounddevice, console
- 3 NLU providers: spacy_provider, hybrid_keyword_matcher, rule_based
- 4 Text processing providers: number, general, tts, asr
- 2 Voice trigger providers: microwakeword, openwakeword
- 3 LLM providers: vsegpt, anthropic, openai
- 12 Intent handlers: (all handlers in `irene/intents/handlers/`)
- Base classes: components, workflows, plugins, inputs, etc.

#### 6.4 Provider-Specific Patterns

**Pattern A: Cross-Platform Providers (Most Common)**
```python
def get_platform_support(cls) -> List[str]:
    return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
```

**Pattern B: Linux-Only Providers (e.g., aplay)**
```python
def get_platform_support(cls) -> List[str]:
    return ["linux.ubuntu", "linux.alpine"]  # No macOS/Windows support
```

**Pattern C: Specific Platform Limitation**
```python
def get_platform_support(cls) -> List[str]:
    return ["linux.ubuntu", "macos", "windows"]  # Skip Alpine if incompatible
```

#### 6.5 Build System Integration Update

**Update Build Analyzer:** 
- Extend `_normalize_platform_name()` method to handle harmonized platform support values
- Ensure proper mapping during transition period
- Update platform validation logic

**Update Dependency Validator:**
- Enhance platform consistency validation to work correctly with aligned platform keys
- Remove false positive warnings about missing dependency mappings

#### 6.6 Validation Benefits

After Phase 6 completion:
- ✅ Platform consistency validation works correctly
- ✅ No false warnings about missing dependency mappings  
- ✅ Clear 1:1 correspondence between supported platforms and dependency keys
- ✅ Simplified build analyzer logic
- ✅ More precise platform capability reporting
- ✅ Complete semantic consistency across the entire metadata interface

### Final Implementation Status

✅ **Phase 1: Core Infrastructure Update** - Foundation updated  
✅ **Phase 2: Build System Infrastructure** - Tools modernized  
✅ **Phase 3: Provider Implementation Updates** - `get_platform_dependencies()` harmonized (49 files)  
✅ **Phase 4: Docker and Configuration Updates** - Build infrastructure updated  
✅ **Phase 5: Documentation and Examples** - User-facing materials updated  
✅ **Phase 6: Platform Support Method Harmonization** - **SEMANTIC CONSISTENCY ACHIEVED** ✅

**Complete**: Phase 6 successfully addressed the critical semantic inconsistency between `get_platform_support()` and `get_platform_dependencies()` methods. All 49+ entry-points now use identical platform keys for both methods, ensuring complete validation consistency and eliminating false positive warnings.

## ⚠️ Risk Mitigation

### High-Risk Areas

1. **Docker Builds**: Platform flag changes could break CI/CD
2. **External Packages**: Third-party entry points may use old format
3. **Build Analyzer**: Platform mapping logic needs careful testing
4. **Dependency Validator**: Package repository validation could fail

### Mitigation Strategies

1. **Gradual Rollout**: Update infrastructure first, then providers
2. **Backward Compatibility**: Maintain mapping for transition period
3. **Comprehensive Testing**: Validate each phase before proceeding
4. **Documentation**: Clear migration guide for external packages
5. **Monitoring**: Track usage of old vs new platform keys
6. **Rollback Plan**: Ability to revert changes if critical issues arise

## 📈 Success Metrics

### Implementation Success

- All 49 entry points successfully updated
- Build analyzer generates correct dependencies for all platforms
- Docker builds complete successfully on both x86_64 and ARMv7
- Zero regressions in existing functionality
- All tests pass with new platform naming

### Long-term Success

- Consistent platform naming across the entire codebase
- Simplified external package integration
- Easier addition of new Linux distributions
- Improved build system maintainability
- Better cross-platform compatibility validation

## 🚀 Implementation Timeline

### Estimated Effort

- **Phase 1**: 2-3 hours (core infrastructure) ✅ **COMPLETED**
- **Phase 2**: 4-5 hours (build system updates) ✅ **COMPLETED**
- **Phase 3**: 6-8 hours (49 provider `get_platform_dependencies()` updates) ✅ **COMPLETED**
- **Phase 4**: 2-3 hours (Docker and configuration) ✅ **COMPLETED**
- **Phase 5**: 3-4 hours (documentation) ✅ **COMPLETED**
- **Phase 6**: 4-6 hours (49 provider `get_platform_support()` updates) ✅ **COMPLETED**

**Total Estimated Time**: 21-29 hours (original: 17-23 hours + Phase 6: 4-6 hours)

### Prerequisites

- Full test suite passing
- Clean git working directory
- Docker build environment available
- Access to all configuration profiles

### Deliverables

- Updated platform dependency interface ✅ **COMPLETED**
- All entry points using standardized platform dependency keys ✅ **COMPLETED** 
- All entry points using standardized platform support keys ✅ **COMPLETED**
- Updated build system supporting new platform naming ✅ **COMPLETED**
- Updated Docker configurations ✅ **COMPLETED**
- Comprehensive documentation ✅ **COMPLETED**
- Migration guide for external packages ✅ **COMPLETED**
- Validation that all builds work correctly ✅ **COMPLETED**
- Complete semantic consistency between platform support and dependencies ✅ **COMPLETED**

## 📚 References

- **Original Analysis**: Platform naming inconsistency identified in `irene/core/metadata.py`
- **Build System**: `irene/tools/build_analyzer.py` and `irene/tools/dependency_validator.py`
- **Docker Configurations**: `Dockerfile.x86_64` and `Dockerfile.armv7`
- **Provider Implementations**: 49 files across `irene/providers/`, `irene/components/`, etc.
- **Documentation**: `docs/TODO/TODO05.md`, `README-BUILD.md`, `README-DOCKER.md`
