# Configuration Architecture Cleanup Plan

**Status**: 🔄 **PLANNED**  
**Priority**: High  
**Goal**: Establish entry-point names as single source of truth for component configuration

## 🎯 Problem Analysis

### Current Configuration Mess

The component configuration system has evolved through multiple phases and now exhibits significant architectural inconsistencies:

| **Component (Entry-Point)** | **Current Config Pattern** | **Config Location** | **Issues** |
|-------------------------------|---------------------------|-------------------|------------|
| `tts` | ✅ Universal Plugin | `[plugins.universal_tts]` | Works |
| `audio` | ✅ Universal Plugin | `[plugins.universal_audio]` | Works |
| `asr` | ✅ Universal Plugin | `[plugins.universal_asr]` | Works |
| `llm` | ✅ Universal Plugin | `[plugins.universal_llm]` | Works |
| `voice_trigger` | ❌ **Non-Universal Plugin** | `[plugins.voice_trigger]` | **No "universal_" prefix!** |
| `text_processor` | ✅ Universal Plugin | `[plugins.universal_text_processor]` | Works |
| `nlu` | ❌ **Component Config** | `[components.nlu]` | **Different section!** |
| `intent_system` | ❌ **System Config** | `[intents]` | **System-level!** |

### Failed Current Implementation

```python
# Current broken logic in ComponentManager._is_component_enabled():
plugin_name = f"universal_{component_name}"  # ❌ FAILS for 3/8 components!

# Failures:
# "voice_trigger" → "universal_voice_trigger" (doesn't exist)
# "nlu" → "universal_nlu" (wrong section - should be components.nlu)  
# "intent_system" → "universal_intent_system" (should be intents.enabled)
```

### Root Causes

1. **No Single Source of Truth**: Configuration mapping scattered across hardcoded dictionaries
2. **Architectural Inconsistency**: Mixed configuration patterns (universal plugins, direct components, system configs)
3. **Tight Coupling**: ComponentManager hardcodes configuration paths
4. **Poor Encapsulation**: TOML structure exposed throughout the system

## 🏗️ Proposed Solution: Entry-Point Driven Configuration

### Core Principles

1. **Entry-Point Name** = **Component Identity** = **Source of Truth**
2. **Config Model Discovery** = **Component.get_config_class()** method
3. **TOML Structure** = **Implementation Detail** (encapsulated by config model)
4. **Generic Resolution**: Same logic works for all components regardless of config complexity

### Architecture Overview

```mermaid
graph TD
    A[Entry-Point: 'tts'] --> B[TTSComponent]
    B --> C[get_config_class() → UniversalTTSConfig]
    B --> D[get_config_path() → 'plugins.universal_tts']
    C --> E[Config Model Validation]
    D --> F[TOML Path Resolution]
    E --> G[Component.is_enabled()]
    F --> G
    G --> H[ComponentManager Decision]
```

## 📋 Implementation Plan

### Phase 1: Component Base Class Enhancement ✅ **COMPLETED**

**File**: `irene/components/base.py`

**Add Abstract Methods**:
```python
class Component(EntryPointMetadata, ABC):
    # ... existing methods ...
    
    @classmethod
    @abstractmethod
    def get_config_class(cls) -> Type[BaseModel]:
        """Return the Pydantic config model for this component"""
        pass
    
    @classmethod  
    @abstractmethod
    def get_config_path(cls) -> str:
        """Return the TOML path to this component's config"""
        pass
    
    def get_config(self, core_config: CoreConfig) -> Optional[BaseModel]:
        """Get this component's configuration instance"""
        config_class = self.get_config_class()
        config_path = self.get_config_path()
        return extract_config_by_path(core_config, config_path, config_class)
    
    def is_enabled(self, core_config: CoreConfig) -> bool:
        """Check if this component is enabled via its config"""
        config = self.get_config(core_config)
        if config is None:
            return False
        return getattr(config, 'enabled', True)
    
    @classmethod
    def is_enabled_in_config(cls, core_config: CoreConfig) -> bool:
        """Class method to check if component is enabled without instantiation"""
        try:
            config_class = cls.get_config_class()
            config_path = cls.get_config_path()
            config = extract_config_by_path(core_config, config_path, config_class)
            if config is None:
                return False
            return getattr(config, 'enabled', True)
        except Exception:
            return False
```

### Phase 2: Config Path Resolution System ✅ **COMPLETED**

**File**: `irene/config/resolver.py` (new file)

```python
"""
Configuration resolution utilities for component-driven config discovery.
"""

from typing import Type, Optional, Any
from pydantic import BaseModel
from .models import CoreConfig

def extract_config_by_path(config: CoreConfig, path: str, config_class: Type[BaseModel]) -> Optional[BaseModel]:
    """
    Extract config from nested TOML structure using dot notation.
    
    Args:
        config: Root configuration object
        path: Dot-separated path (e.g., "plugins.universal_tts", "components.nlu", "intents")
        config_class: Expected Pydantic model class
        
    Returns:
        Config instance if found and valid, None otherwise
        
    Examples:
        - path="plugins.universal_tts" → config.plugins.universal_tts
        - path="components.nlu" → config.components.nlu  
        - path="intents" → config.intents
    """
    try:
        current = config
        for part in path.split('.'):
            current = getattr(current, part, None)
            if current is None:
                return None
        
        # Validate against expected config model
        if isinstance(current, config_class):
            return current
        elif isinstance(current, dict):
            # Try to construct from dict (for dynamic configs)
            return config_class(**current)
        else:
            # Invalid config type
            return None
            
    except (AttributeError, TypeError, ValueError) as e:
        # Config path not found or invalid
        return None

def is_component_enabled_by_name(component_name: str, config: CoreConfig) -> bool:
    """
    Check if a component is enabled using entry-point name.
    
    Args:
        component_name: Entry-point name (e.g., "tts", "voice_trigger", "nlu")
        config: Core configuration object
        
    Returns:
        True if component is enabled, False otherwise
    """
    # Essential components always enabled (required for core functionality)
    essential_components = ["intent_system", "nlu", "text_processor"]
    if component_name in essential_components:
        return True
    
    try:
        # Get component class from entry-points
        from ..utils.loader import dynamic_loader
        component_class = dynamic_loader.get_provider_class("irene.components", component_name)
        
        # Use component's own config resolution
        return component_class.is_enabled_in_config(config)
        
    except Exception:
        # Component not found or config resolution failed
        return False

def get_component_config_by_name(component_name: str, config: CoreConfig) -> Optional[BaseModel]:
    """
    Get component configuration using entry-point name.
    
    Args:
        component_name: Entry-point name
        config: Core configuration object
        
    Returns:
        Component config instance if found, None otherwise
    """
    try:
        from ..utils.loader import dynamic_loader
        component_class = dynamic_loader.get_provider_class("irene.components", component_name)
        
        config_class = component_class.get_config_class()
        config_path = component_class.get_config_path()
        
        return extract_config_by_path(config, config_path, config_class)
        
    except Exception:
        return None
```

### Phase 3: Component Implementation Matrix ✅ **COMPLETED**

**All 8 components must implement the config mapping interface:**

#### TTSComponent (`irene/components/tts_component.py`)
```python
@classmethod
def get_config_class(cls) -> Type[BaseModel]:
    from ..config.models import UniversalTTSConfig
    return UniversalTTSConfig

@classmethod
def get_config_path(cls) -> str:
    return "plugins.universal_tts"
```

#### AudioComponent (`irene/components/audio_component.py`)
```python
@classmethod
def get_config_class(cls) -> Type[BaseModel]:
    from ..config.models import UniversalAudioConfig
    return UniversalAudioConfig

@classmethod
def get_config_path(cls) -> str:
    return "plugins.universal_audio"
```

#### ASRComponent (`irene/components/asr_component.py`)
```python
@classmethod
def get_config_class(cls) -> Type[BaseModel]:
    from ..config.models import UniversalASRConfig
    return UniversalASRConfig

@classmethod
def get_config_path(cls) -> str:
    return "plugins.universal_asr"
```

#### LLMComponent (`irene/components/llm_component.py`)
```python
@classmethod
def get_config_class(cls) -> Type[BaseModel]:
    from ..config.models import UniversalLLMConfig
    return UniversalLLMConfig

@classmethod
def get_config_path(cls) -> str:
    return "plugins.universal_llm"
```

#### VoiceTriggerComponent (`irene/components/voice_trigger_component.py`)
```python
@classmethod
def get_config_class(cls) -> Type[BaseModel]:
    from ..config.models import VoiceTriggerConfig  # Note: NOT Universal*
    return VoiceTriggerConfig

@classmethod
def get_config_path(cls) -> str:
    return "plugins.voice_trigger"  # Note: NO "universal_" prefix
```

#### TextProcessorComponent (`irene/components/text_processor_component.py`)
```python
@classmethod
def get_config_class(cls) -> Type[BaseModel]:
    from ..config.models import TextProcessingConfig  # Note: "Processing" not "Processor"
    return TextProcessingConfig

@classmethod
def get_config_path(cls) -> str:
    return "plugins.universal_text_processor"
```

#### NLUComponent (`irene/components/nlu_component.py`)
```python
@classmethod
def get_config_class(cls) -> Type[BaseModel]:
    from ..config.models import UniversalNLUConfig
    return UniversalNLUConfig

@classmethod
def get_config_path(cls) -> str:
    return "components.nlu"  # Different section!
```

#### IntentComponent (`irene/components/intent_component.py`)
```python
@classmethod
def get_config_class(cls) -> Type[BaseModel]:
    from ..config.models import IntentSystemConfig
    return IntentSystemConfig

@classmethod
def get_config_path(cls) -> str:
    return "intents"  # System-level config!
```

### Phase 4: ComponentManager Cleanup ✅ **COMPLETED**

**File**: `irene/core/components.py`

**Replace Hardcoded Logic**:
```python
# BEFORE: Hardcoded nightmare
def _is_component_enabled(self, component_name: str, config) -> bool:
    # Essential components always enabled
    essential_components = ["intent_system", "nlu", "text_processor"]
    if component_name in essential_components:
        return True
    
    # Hardcoded mapping - WRONG!
    plugin_name = f"universal_{component_name}"
    # ... complex hardcoded logic

# AFTER: Clean, generic resolution
def _is_component_enabled(self, component_name: str, config: CoreConfig) -> bool:
    """Check if component is enabled using its own config declaration"""
    from ..config.resolver import is_component_enabled_by_name
    return is_component_enabled_by_name(component_name, config)
```

### Phase 5: Config Model Validation ✅ **COMPLETED**

**File**: `irene/config/models.py`

**Ensure Consistency**:
1. All component config models have consistent `enabled: bool` field
2. Create missing config models if needed:
   ```python
   class VoiceTriggerConfig(BaseModel):
       """Voice trigger / wake word configuration"""
       enabled: bool = Field(default=False, description="Enable voice trigger")
       default_provider: str = Field(default="openwakeword")
       # ... other fields
   ```

3. Verify config model naming consistency:
   - Check if `TextProcessingConfig` vs `UniversalTextProcessorConfig` naming
   - Ensure all models are properly imported and available

## 🧪 Testing Strategy

### Unit Tests

1. **Config Resolution Tests** (`tests/config/test_resolver.py`):
   ```python
   def test_extract_config_by_path():
       # Test all valid paths for each component
       
   def test_is_component_enabled_by_name():
       # Test enabled/disabled states for each component
       
   def test_component_config_mapping():
       # Test each component's config class and path
   ```

2. **Component Interface Tests** (`tests/components/test_config_interface.py`):
   ```python
   def test_all_components_implement_config_interface():
       # Verify all 8 components implement required methods
       
   def test_component_config_resolution():
       # Test actual config resolution for each component
   ```

### Integration Tests

1. **Real Config Tests** (`tests/integration/test_config_resolution.py`):
   - Test with actual config files from `configs/` directory
   - Verify all components resolve correctly
   - Test edge cases (missing configs, invalid configs)

2. **ComponentManager Tests** (`tests/core/test_component_manager.py`):
   - Test component enablement logic with real configs
   - Test essential vs optional component handling

## 📈 Migration Plan

### Week 1: Foundation
- **Day 1-2**: Implement config resolver system (`config/resolver.py`)
- **Day 3**: Add abstract methods to base `Component` class
- **Day 4-5**: Fix all component classes to implement interface (will initially break)

### Week 2: Component Implementation  
- **Day 1-3**: Implement config mapping for all 8 components
- **Day 4**: Validate all config models exist and are consistent
- **Day 5**: Test component config resolution

### Week 3: Integration
- **Day 1-2**: Replace `ComponentManager._is_component_enabled()` logic
- **Day 3**: Integration testing with real config files
- **Day 4**: Performance testing and optimization
- **Day 5**: Documentation and cleanup

## ✅ Expected Benefits

### Immediate Benefits
- **🎯 Single Source of Truth**: Entry-point names drive all configuration decisions
- **🔧 No More Hardcoding**: Generic config resolution works for all components
- **🛡️ Type Safety**: Pydantic models ensure config validation
- **🧪 Testability**: Easy to test config resolution per component

### Long-term Benefits
- **📈 Scalability**: Adding new components requires only implementing interface
- **🔄 Maintainability**: Config structure changes don't break core logic
- **🎨 Flexibility**: Can handle any TOML structure without changing ComponentManager
- **📚 Clarity**: Clear relationship between entry-points, components, and configs

### Developer Experience
- **✨ Consistency**: Same pattern for all components regardless of complexity
- **🔍 Debugging**: Easy to trace config resolution path
- **📝 Documentation**: Self-documenting through component interface
- **🚀 Extension**: Third-party components can use same pattern

## 🚨 Breaking Changes

### Component Interface Changes
- All component classes must implement `get_config_class()` and `get_config_path()`
- Components that don't implement interface will fail to load

### Configuration Validation
- Invalid config paths or models will cause component loading to fail
- More strict validation may expose previously hidden config errors

### Migration Required
- Any custom components must be updated to implement new interface
- Configuration tooling may need updates for new resolution system

## 🎯 Success Criteria

1. **✅ All 8 components load successfully** with new config resolution
2. **✅ No hardcoded config paths** remain in ComponentManager
3. **✅ Config resolution is generic** and works for all components
4. **✅ Entry-point names are sole source of truth** for component identity
5. **✅ TOML structure is fully encapsulated** by component config declarations
6. **✅ System is extensible** for future components without core changes

This implementation establishes a clean, maintainable foundation for component configuration that scales with the system's growth and eliminates the current architectural inconsistencies.
