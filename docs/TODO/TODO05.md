## 5. Universal Entry-Points Metadata System: Eliminate Build Analyzer Hardcoding

**Status:** Open  
**Priority:** High (Required before TODO #3 Phase 4-5)  
**Components:** Build dependency metadata for ALL entry-points across 14 namespaces (77 total entry-points)

### Problem

The current build analyzer (`irene/tools/build_analyzer.py`) contains extensive hardcoded mappings that violate the project's "no hardcoded patterns" philosophy:

1. **Provider Dependencies** (Lines 70-147): Hardcoded system and Python dependencies for 25+ providers
2. **Namespace List** (Lines 364-379): Hardcoded list of 14 entry-points namespaces  
3. **Platform Mappings**: Additional hardcoding in `Dockerfile.armv7` (lines 51-63) for Ubuntu→Alpine package conversion
4. **Missing Build Metadata**: No standardized way for ANY entry-points to declare their build requirements

This creates maintenance overhead, prevents external packages from integrating with the build system, and requires manual updates across multiple files for dependency changes.

### Proposed Solution: Extend Universal Metadata Interface

**Leverage and extend the existing `EntryPointMetadata` interface** created in TODO #4 with build dependency methods. **Relocate the interface** to a proper central location first.

### Implementation Scope Analysis

**Assets vs Build Dependencies:**

| **Namespace** | **Count** | **Asset Config (TODO #4)** | **Build Dependencies (TODO #5)** |
|---------------|-----------|----------------------------|----------------------------------|
| `irene.providers.audio` | 5 | ✅ **DONE** (Phase 1) | 🆕 Add build methods |
| `irene.providers.tts` | 6 | ✅ **DONE** (Phase 1) | 🆕 Add build methods |
| `irene.providers.asr` | 3 | ✅ **DONE** (Phase 1) | 🆕 Add build methods |
| `irene.providers.llm` | 3 | ✅ **DONE** (Phase 1) | 🆕 Add build methods |
| `irene.providers.voice_trigger` | 2 | ✅ **DONE** (Phase 1) | 🆕 Add build methods |
| `irene.providers.nlu` | 2 | ✅ **DONE** (Phase 1) | 🆕 Add build methods |
| `irene.providers.text_processing` | 4 | ✅ **DONE** (Phase 1) | 🆕 Add build methods |
| `irene.components` | 7 | ❌ Not applicable | 🆕 Implement full interface |
| `irene.workflows` | 2 | ❌ Not applicable | 🆕 Implement full interface |
| `irene.intents.handlers` | 6 | ❌ Not applicable | 🆕 Implement full interface |
| `irene.inputs` | 3 | ❌ Not applicable | 🆕 Implement full interface |
| `irene.outputs` | 3 | ❌ Not applicable | 🆕 Implement full interface |
| `irene.plugins.builtin` | 2 | ❌ Not applicable | 🆕 Implement full interface |
| `irene.runners` | 4 | ❌ Not applicable | 🆕 Implement full interface |

**Total: 25 providers need build methods added, 27 non-providers need full interface implementation**

### Implementation Strategy

#### **Phase 0: Interface Relocation** ✅ **COMPLETED** (Priority: Critical)
Relocate `EntryPointMetadata` from `irene/providers/base.py` to `irene/core/metadata.py`:

```python
# irene/core/metadata.py - NEW central location
from abc import ABC
from typing import Dict, Any, List

class EntryPointMetadata(ABC):
    """
    Universal metadata interface for all entry-points.
    
    Supports both asset configuration (TODO #4) and build dependencies (TODO #5).
    Enables configuration-driven systems and external package integration.
    """
    
    # ✅ Asset configuration methods (implemented in TODO #4)
    @classmethod
    def get_asset_config(cls) -> Dict[str, Any]:
        """Get asset configuration with intelligent defaults."""
        return {
            "file_extension": cls._get_default_extension(),
            "directory_name": cls._get_default_directory(),
            "credential_patterns": cls._get_default_credentials(),
            "cache_types": cls._get_default_cache_types(),
            "model_urls": cls._get_default_model_urls()
        }
    
    # 🆕 Build dependency methods (TODO #5)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Python dependency groups from pyproject.toml optional-dependencies."""
        return []
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Supported platforms: linux, windows, macos, armv7, etc."""
        return ["linux", "windows", "macos"]
        
    @classmethod  
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Platform-specific system package mappings."""
        return {
            "ubuntu": [],  # Ubuntu/Debian system packages
            "alpine": [],  # Alpine Linux (ARMv7) packages
            "centos": [],  # CentOS/RHEL packages
            "macos": []    # macOS Homebrew packages
        }
        
    # Asset configuration helper methods (moved from providers/base.py)
    @classmethod
    def _get_default_extension(cls) -> str:
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        name = cls.__name__.lower()
        if name.endswith('provider'):
            name = name[:-8]
        return name
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        return {}
```

#### **Updated Import Pattern**
```python
# All entry-point base classes now import from central location
from irene.core.metadata import EntryPointMetadata

class ProviderBase(EntryPointMetadata, ABC):  # Providers
class Component(EntryPointMetadata, ABC):     # Components  
class Workflow(EntryPointMetadata, ABC):      # Workflows
class IntentHandler(EntryPointMetadata, ABC): # Intent handlers
# ... etc
```

#### **Phase 1: Build Methods for Providers** (Priority: High)
Extend existing 25 provider implementations with build dependency methods:

```python
# irene/providers/audio/sounddevice.py - ADD build methods to existing class
class SoundDeviceAudioProvider(AudioProvider):  # Already inherits EntryPointMetadata via ProviderBase
    # ✅ Asset methods already implemented (TODO #4)
    @classmethod
    def _get_default_extension(cls) -> str:
        return ".wav"  # DONE
    
    # 🆕 Build methods (TODO #5)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        return ["audio-input", "audio-output"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        return {
            "ubuntu": ["libportaudio2", "libsndfile1"],
            "alpine": ["portaudio-dev", "libsndfile-dev"],  # ARMv7 Alpine
            "centos": ["portaudio-devel", "libsndfile-devel"],
            "macos": []  # Homebrew handles dependencies
        }
```

#### **Phase 2: Full Interface for Non-Providers** (Priority: High)
Implement complete `EntryPointMetadata` interface for non-provider classes:

```python
# irene/components/tts_component.py - ADD full interface inheritance
from irene.core.metadata import EntryPointMetadata

class TTSComponent(Component, EntryPointMetadata):  # NEW inheritance
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        return ["tts"]  # Needs TTS functionality group
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        return {
            "ubuntu": [],  # Components coordinate providers, no direct system deps
            "alpine": [], 
            "centos": [],
            "macos": []
        }
        
    # Asset methods (new for components)
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        return ["runtime"]  # Components use runtime cache only

# irene/workflows/voice_assistant.py  
class VoiceAssistantWorkflow(Workflow, EntryPointMetadata):  # NEW inheritance
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        return ["audio-input", "audio-output", "tts", "asr"]  # Voice workflow requirements

# irene/intents/handlers/train_schedule.py
class TrainScheduleIntentHandler(IntentHandler, EntryPointMetadata):  # NEW inheritance
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        return ["web-requests"]  # Needs HTTP client for train APIs

# irene/runners/webapi_runner.py
class WebAPIRunner(EntryPointMetadata):  # NEW inheritance (no common Runner base class)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        return ["web-api"]  # Needs FastAPI/uvicorn
```

### Comprehensive Hardcoding Elimination

**Three systems need complete replacement:**

1. **Build Analyzer Hardcoding** (`irene/tools/build_analyzer.py`):
   - Lines 70-147: `PROVIDER_SYSTEM_DEPENDENCIES` + `PROVIDER_PYTHON_DEPENDENCIES` 
   - Lines 364-379: Hardcoded namespace list
   - Replace with dynamic entry-point metadata queries

2. **Docker Platform Mapping** (`Dockerfile.armv7`):
   - Lines 51-63: Hardcoded `ubuntu_to_alpine` package conversion
   - Replace with `get_platform_dependencies()` queries

3. **Dynamic Discovery**: 
   - Query metadata from actual entry-point classes instead of static mappings
   - Support external packages automatically via their metadata implementations

### Benefits

- **Eliminates ALL Hardcoding**: Build analyzer, Docker builds, and discovery become fully dynamic
- **External Package Support**: Third-party packages integrate seamlessly via metadata methods
- **Platform Optimization**: Native support for Ubuntu, Alpine, CentOS, macOS builds  
- **Maintainability**: Dependencies live with the code that needs them
- **Architectural Consistency**: Universal pattern across ALL 77 entry-points
- **Build Efficiency**: Precise dependency analysis for minimal deployments

### Impact

- **Major Architectural Change**: Affects all base classes and 52+ implementations
- **Breaking Change**: Entry-point interface additions (backward compatible via default implementations)
- **Build System**: Complete overhaul of build analyzer and Docker infrastructure
- **External Packages**: Third-party entry-points must implement metadata methods
- **Maintenance**: Eliminates need for manual dependency mapping updates

#### **Phase 3: Build System Integration** (Priority: Critical)
Update build analyzer to query entry-point metadata instead of hardcoded mappings:

```python
# irene/tools/build_analyzer.py - REMOVE hardcoded mappings
class IreneBuildAnalyzer:
    def _get_provider_dependencies(self, provider_name: str) -> Dict[str, Any]:
        """Get provider dependencies via entry-point metadata queries"""
        from irene.utils.loader import dynamic_loader
        
        # Discover provider class via entry-points
        provider_class = self._find_provider_class(provider_name)
        if not provider_class:
            logger.warning(f"Provider '{provider_name}' not found")
            return {"python_deps": [], "system_deps": {}}
        
        # Query metadata instead of hardcoded mapping
        python_deps = provider_class.get_python_dependencies()
        platform_deps = provider_class.get_platform_dependencies()
        
        return {
            "python_deps": python_deps,
            "system_deps": platform_deps
        }
        
    def _discover_all_namespaces(self) -> List[str]:
        """Dynamically discover entry-point namespaces instead of hardcoded list"""
        # Replace hardcoded namespace list with dynamic discovery
        # Query pyproject.toml or entry-points directly
        pass
```

## ✅ **TODO #5 PHASE 0 COMPLETE - SUMMARY**

**MISSION ACCOMPLISHED**: Interface Relocation has been **successfully completed**.

### **What Was Achieved**
- ✅ **Interface Relocated**: `EntryPointMetadata` moved from `irene/providers/base.py` to `irene/core/metadata.py`
- ✅ **Extended Interface**: Added new build dependency methods (`get_python_dependencies`, `get_platform_support`, `get_platform_dependencies`)
- ✅ **Import Updates**: All provider base classes and modules updated to use new import location
- ✅ **Backward Compatibility**: Zero breaking changes to existing asset configuration functionality
- ✅ **Comprehensive Testing**: All imports verified working correctly with uv

### **Technical Implementation Complete**
```python
# NEW central location: irene/core/metadata.py
from irene.core.metadata import EntryPointMetadata

# All provider classes now inherit build dependency methods
class SomeProvider(ProviderBase):  # ProviderBase inherits from EntryPointMetadata
    # Asset methods (existing - TODO #4)
    @classmethod
    def _get_default_extension(cls) -> str: ...
    
    # Build methods (new - TODO #5) 
    @classmethod
    def get_python_dependencies(cls) -> List[str]: ...
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]: ...
    @classmethod
    def get_platform_support(cls) -> List[str]: ...
```

### **Universal Availability Verified**
- ✅ **Core Module**: `from irene.core.metadata import EntryPointMetadata` ✓
- ✅ **Provider Module**: `from irene.providers import EntryPointMetadata` ✓ 
- ✅ **Provider Base**: `from irene.providers.base import ProviderBase` ✓
- ✅ **Inheritance Chain**: All 25 provider implementations inherit new build methods automatically ✓

### **Ready for Phase 1**
**Phase 0 provides the complete foundation for Phase 1 (Provider Build Methods).** All provider implementations now have access to the new build dependency methods and can be extended with intelligent defaults.

### Implementation Requirements

#### **Phase 0: Interface Relocation** ✅ **COMPLETED** (Priority: Critical)
- ✅ Move `EntryPointMetadata` from `irene/providers/base.py` to `irene/core/metadata.py`
- ✅ Update all imports across provider base classes and implementations
- ✅ Ensure no breaking changes to existing asset configuration functionality

#### **Phase 1: Provider Build Methods** (Priority: High)
- Add build dependency methods to existing 25 provider implementations
- Providers already inherit `EntryPointMetadata` - just add the 3 new methods
- Migrate hardcoded dependency data from build analyzer to provider classes

#### **Phase 2: Non-Provider Interface Implementation** (Priority: High)  
- Add `EntryPointMetadata` inheritance to 27 non-provider base classes
- Implement metadata methods in components, workflows, inputs, outputs, intent handlers, runners, plugins
- Focus on build dependencies (asset methods not applicable for most)

#### **Phase 3: Build System Integration** (Priority: Critical)
- Remove ALL hardcoded mappings from build analyzer (PROVIDER_SYSTEM_DEPENDENCIES, PROVIDER_PYTHON_DEPENDENCIES)
- Replace hardcoded namespace list with dynamic discovery
- Update Docker builds to use platform-specific metadata queries

#### **Phase 4: Dependency Validation Tool** (Priority: Medium)
Create `irene/tools/dependency_validator.py` - intelligent validation tool that:

**Core Functionality:**
```bash
# Validate single entry-point class for target platform
python -m irene.tools.dependency_validator \
    --file irene/providers/audio/sounddevice.py \
    --class SoundDeviceAudioProvider \
    --platform ubuntu

# Validate all entry-points for specific platform
python -m irene.tools.dependency_validator \
    --validate-all --platform alpine

# Cross-platform validation for CI/CD
python -m irene.tools.dependency_validator \
    --validate-all --platforms ubuntu,alpine,centos,macos
```

**Smart Validation Features:**
- **Import Analysis**: Dynamically import and instantiate entry-point classes
- **Package Verification**: Check if declared Python dependencies actually exist in pyproject.toml
- **System Package Validation**: Verify system packages exist in target platform repositories
- **Cross-Platform Consistency**: Ensure platform-specific mappings are logically equivalent
- **Dependency Graph**: Detect circular dependencies and conflicts between entry-points
- **Performance Testing**: Validate that metadata methods execute quickly (< 100ms per class)
- **External Package Support**: Validate third-party entry-point metadata compliance

**Validation Logic:**
```python
class DependencyValidator:
    """Smart dependency validation for entry-point metadata"""
    
    def validate_entry_point(self, file_path: str, class_name: str, platform: str) -> ValidationResult:
        """Validate single entry-point's metadata for target platform"""
        # 1. Dynamic import and instantiation
        # 2. Call metadata methods and validate return types
        # 3. Verify Python deps exist in pyproject.toml optional-dependencies
        # 4. Check system packages exist in platform package repos
        # 5. Performance testing of metadata methods
        # 6. Cross-reference with build analyzer expectations
        
    def validate_platform_consistency(self, class_obj: type) -> ValidationResult:
        """Ensure platform-specific dependencies are logically equivalent"""
        # 1. Compare Ubuntu vs Alpine vs CentOS package mappings
        # 2. Detect missing platform support
        # 3. Validate package name conventions per platform
        
    def validate_all_entry_points(self, platforms: List[str]) -> Dict[str, ValidationResult]:
        """Validate all 77 entry-points across specified platforms"""
        # 1. Discovery via entry-points catalog
        # 2. Batch validation with progress reporting
        # 3. Generate comprehensive validation report
```

**Integration with CI/CD:**
- Pre-commit hook validation for modified entry-points
- GitHub Actions integration for cross-platform validation
- Build-time validation before Docker image creation
- External package validation for third-party entry-points

### Benefits Enhanced by TODO #4 Completion

- **Leverages Existing Infrastructure**: Builds on completed `EntryPointMetadata` interface from TODO #4
- **Reduced Implementation Scope**: Only need to add build methods to providers, full interface to non-providers
- **Proven Architecture**: Asset configuration already working, just extend for build dependencies
- **External Package Ready**: Interface relocation enables seamless third-party integration

### Related Files

#### **Phase 0: Interface Relocation** ✅ **COMPLETED**
- ✅ `irene/providers/base.py` (moved EntryPointMetadata OUT of this file)
- ✅ `irene/core/metadata.py` (new central location for EntryPointMetadata created)
- ✅ All provider base classes (imports updated successfully)

#### **Phase 1: Provider Build Methods**  
- 🔄 25 provider implementations (add 3 build methods to existing asset methods)
- 🔄 `irene/tools/build_analyzer.py` (query provider metadata instead of hardcoded PROVIDER_SYSTEM_DEPENDENCIES)

#### **Phase 2: Non-Provider Interface**
- 🆕 7 component base classes (inherit EntryPointMetadata)
- 🆕 2 workflow base classes (inherit EntryPointMetadata)
- 🆕 6 intent handler base classes (inherit EntryPointMetadata)
- 🆕 3 input base classes (inherit EntryPointMetadata)
- 🆕 3 output base classes (inherit EntryPointMetadata)
- 🆕 2 plugin base classes (inherit EntryPointMetadata)
- 🆕 4 runner classes (inherit EntryPointMetadata)

#### **Phase 3: Build System Integration**
- 🔄 `irene/tools/build_analyzer.py` (remove ALL hardcoded mappings, replace with metadata queries)
- 🔄 `Dockerfile.armv7` (remove hardcoded Ubuntu→Alpine conversion)
- 🔄 `Dockerfile.x86_64` (integrate dynamic metadata queries)

#### **Phase 4: Validation Tool**  
- 🆕 `irene/tools/dependency_validator.py` (new validation tool)

---
