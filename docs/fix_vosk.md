# Sampling Rate Compatibility Fix Plan

## **Overview**

This document outlines the comprehensive plan to fix sampling rate compatibility issues between microphone input and both ASR and Voice Trigger components in the Irene Voice Assistant system.

## **Identified Issues**

### **Critical Runtime Errors**
1. **ASR Component**: Missing `process_audio(AudioData)` method - workflow calls non-existent method
2. **Voice Trigger Component**: Workflow calls `process_audio()` but component only has `detect()` method
3. **Sample Rate Mismatches**: Microphone (16kHz) vs providers with different requirements

### **Current Problems**
- AudioData objects contain sample rate metadata but it's ignored
- No validation of microphone vs provider sample rate compatibility  
- No automatic resampling when rates don't match
- Hard failures or degraded performance on rate mismatches

## **Implementation Plan**

## **Phase 1: Critical Runtime Fixes (Immediate)**

### **1.1 Fix Missing/Incorrect Methods**
- **ASR Component**: Add missing `process_audio(AudioData) -> str` method
- **Voice Trigger Component**: Fix workflow calling wrong method name  
- **Priority**: CRITICAL - These cause runtime AttributeError exceptions

### **1.2 Method Signature Standardization**
```
ASRComponent:
  - process_audio(AudioData) -> str  [NEW - bridge method]
  - transcribe_audio(bytes) -> str   [EXISTING]

VoiceTriggerComponent:  
  - process_audio(AudioData) -> WakeWordResult  [NEW - for workflow compatibility]
  - detect(AudioData) -> WakeWordResult         [EXISTING - keep for direct usage]
```

## **Phase 2: Audio Infrastructure Enhancement**

### **2.1 AudioData Resampling Infrastructure**
Create centralized resampling utilities that preserve AudioData metadata:

```
AudioProcessor class:
  - resample_audio_data(AudioData, target_rate) -> AudioData
  - validate_sample_rate_compatibility(source_rate, target_rates) -> bool
  - get_optimal_conversion_path(source_rate, target_rate) -> ConversionMethod
```

### **2.2 Enhanced Audio Format Converter**
Extend existing `AudioFormatConverter` in `irene/utils/audio_helpers.py`:
- Add AudioData-aware conversion methods
- Support for real-time streaming conversion
- Quality vs performance trade-offs
- Memory-efficient chunk-based processing

### **2.3 Sample Rate Detection and Validation**
- Automatic sample rate detection from audio streams
- Cross-component rate compatibility validation
- Configuration validation at startup

## **Phase 3: Provider-Specific Enhancements**

### **3.1 ASR Provider Updates**

**All ASR Providers:**
- Add `get_preferred_sample_rates() -> List[int]` method
- Add `supports_sample_rate(rate: int) -> bool` method
- Enhanced parameter schemas with sample rate preferences

**Provider-Specific:**
- **VOSK**: Support multiple rates, validate against model requirements
- **Whisper**: Leverage existing flexibility, add rate metadata forwarding
- **Google Cloud**: Validate rate matches `sample_rate_hertz` parameter

### **3.2 Voice Trigger Provider Updates**

**Base VoiceTriggerProvider:**
- Add `get_supported_sample_rates() -> List[int]` method
- Add `get_default_sample_rate() -> int` method  
- Add `supports_resampling() -> bool` method
- Add `get_default_channels() -> int` method

**Provider-Specific:**
- **OpenWakeWord**: Specify supported rates and optimal defaults
- **MicroWakeWord**: Specify required rates and validate chunk compatibility
- **Future providers**: Support multiple rates with clear capability declarations

## **Phase 4: Component Architecture Updates**

### **4.1 ASR Component Enhancement**
```python
class ASRComponent:
    async def process_audio(self, audio_data: AudioData, **kwargs) -> str:
        # 1. Extract provider requirements
        # 2. Check sample rate compatibility  
        # 3. Auto-resample if needed and supported
        # 4. Call transcribe_audio with converted data
        # 5. Handle fallback providers on rate mismatch
    
    async def _handle_sample_rate_mismatch(self, audio_data, provider, **kwargs):
        # Attempt resampling or fallback provider selection
```

### **4.2 Voice Trigger Component Enhancement**
```python
class VoiceTriggerComponent:
    async def process_audio(self, audio_data: AudioData) -> WakeWordResult:
        # Bridge method for workflow compatibility
        return await self.detect(audio_data)
    
    async def detect(self, audio_data: AudioData) -> WakeWordResult:
        # 1. Check if resampling is needed based on configuration
        # 2. Apply efficient resampling if sample rates don't match
        # 3. Call provider detect_wake_word with correct format
        # 4. Handle provider fallbacks on configuration conflicts
```

## **Phase 5: Configuration and Validation**

### **5.1 Startup Validation**
- **FATAL ERROR VALIDATION**: Configuration contradictions cause immediate startup failure
- **Provider Requirement Conflicts**: Hard stop if provider requirements contradict config
- **Missing Provider Defaults**: Auto-resolve using provider defaults when config is unspecified
- **Cross-component Compatibility**: Ensure microphone, ASR, and voice trigger configurations are consistent

### **5.2 Configuration Enhancements**
```toml
[inputs.microphone_config]
sample_rate = 16000
channels = 1                  # NEW: explicit channel configuration
auto_resample = true          # NEW: enable/disable resampling globally
resample_quality = "medium"   # NEW: low/medium/high/best

[asr]
sample_rate = 16000          # AUTHORITATIVE: overrides provider preferences
channels = 1                 # AUTHORITATIVE: explicit channel requirement
allow_resampling = true      # Enable resampling for this component
resample_quality = "high"    # Component-specific quality setting

[voice_trigger] 
sample_rate = 16000          # AUTHORITATIVE: configuration takes precedence
channels = 1                 # AUTHORITATIVE: explicit channel requirement
allow_resampling = true      # NEW: enable resampling for voice triggers
resample_quality = "fast"    # Optimized for low-latency real-time processing
strict_validation = true     # Fatal error on provider conflicts
```

### **5.3 Configuration Validation Logic**

**Validation Priority Order:**
1. **Explicit Configuration**: User-defined values are AUTHORITATIVE
2. **Provider Defaults**: Used only when configuration is missing/unspecified
3. **System Defaults**: Fallback when both config and provider defaults are unavailable

**Fatal Error Conditions:**
```python
# Configuration contradicts hard provider requirements
if config.sample_rate not in provider.get_supported_rates():
    raise ConfigurationError(f"Provider {provider.name} doesn't support {config.sample_rate}Hz")

# Provider has conflicting defaults with explicit config
if config.explicit and provider.requires_exact_rate and config.sample_rate != provider.required_rate:
    raise ConfigurationError(f"Provider {provider.name} requires exactly {provider.required_rate}Hz")

# No configuration and provider has no defaults
if not config.sample_rate and not provider.get_default_sample_rate():
    raise ConfigurationError(f"No sample rate specified for {component} and provider has no defaults")
```

**Resolution Logic:**
```python
def resolve_audio_config(component_config, provider):
    if component_config.sample_rate:
        # Configuration is explicit and authoritative
        if provider.supports_sample_rate(component_config.sample_rate):
            return component_config
        elif component_config.allow_resampling:
            return component_config  # Will resample from provider's default
        else:
            raise FatalConfigurationError("Rate mismatch with resampling disabled")
    else:
        # Use provider defaults
        return AudioConfig(
            sample_rate=provider.get_default_sample_rate(),
            channels=provider.get_default_channels(),
            allow_resampling=component_config.allow_resampling
        )
```

### **5.4 Runtime Monitoring**
- Configuration validation success/failure logging
- Resampling performance metrics with latency tracking
- Provider compatibility status and fallback usage
- Audio format conversion overhead monitoring

## **Phase 6: Advanced Features**

### **6.1 Performance Optimization**
- **Voice Trigger**: Optimized resampling with minimal latency overhead
- **ASR**: Cached resampling for repeated rates
- **Streaming**: Chunk-based real-time conversion
- **Memory**: Buffer management for conversion operations

### **6.2 Quality-Performance Trade-offs**
```
Resampling Quality Levels:
- fast: Linear interpolation (lowest latency)
- medium: Polyphase filtering (balanced)
- high: Kaiser windowed sinc (best quality)
- adaptive: Dynamic based on rate ratio
```

## **Phase 7: Testing and Documentation**

### **7.1 Test Coverage**
- Unit tests for all sample rate combinations
- Integration tests with real audio hardware
- Performance benchmarks for resampling overhead
- Fallback provider chain testing

### **7.2 Documentation Updates**
- Configuration guide for audio hardware compatibility
- Troubleshooting guide for sample rate issues
- Performance tuning recommendations
- Provider-specific audio requirements

## **Implementation Priority**

### **✅ Configuration Updates (COMPLETED):**
- **config-master.toml**: Updated with new audio configuration parameters
- Added component-level sample rate and resampling settings
- Added validation and resampling quality controls
- Aligned provider configurations with component requirements

### **✅ Phase 1: Critical Runtime Fixes (COMPLETED):**
- **ASRComponent**: Added missing `process_audio(AudioData) -> str` bridge method
- **VoiceTriggerComponent**: Added missing `process_audio(AudioData) -> WakeWordResult` bridge method
- **Method Signature Standardization**: Both components now support workflow-expected method calls
- **Runtime AttributeError Fixes**: Eliminated critical exceptions in workflow audio processing

### **✅ Phase 2: Audio Infrastructure Enhancement (COMPLETED):**
- **AudioProcessor Class**: Centralized resampling utilities preserving AudioData metadata
  - `resample_audio_data(AudioData, target_rate, method) -> AudioData`
  - `validate_sample_rate_compatibility(source_rate, target_rates) -> bool`
  - `get_optimal_conversion_path(source_rate, target_rate) -> ConversionMethod`
- **Enhanced AudioFormatConverter**: AudioData-aware conversion methods
  - `convert_audio_data()` with quality/performance trade-offs
  - `convert_audio_data_streaming()` for memory-efficient chunk processing
  - Real-time streaming conversion support
- **Sample Rate Detection and Validation**: Comprehensive validation framework
  - `detect_sample_rate_from_audio_data()` for AudioData objects
  - `validate_cross_component_compatibility()` for component rate matching
  - `validate_startup_audio_configuration()` for early error detection
- **ConversionMethod Enum**: Quality/performance trade-off options (linear, polyphase, sinc_kaiser, adaptive)
- **ResamplingResult DataClass**: Detailed resampling operation results with performance metrics

### **✅ Phase 3: Provider-Specific Enhancements (COMPLETED):**
- **ASR Provider Base Class Updates**: Added standardized sample rate capability methods
  - `get_preferred_sample_rates() -> List[int]` - ordered by preference
  - `supports_sample_rate(rate: int) -> bool` - compatibility validation
- **ASR Provider Implementations Enhanced**:
  - **VOSK**: Prefers 16kHz/8kHz, supports 8-48kHz with model validation
  - **Whisper**: Extremely flexible 8-96kHz range with internal resampling to 16kHz
  - **Google Cloud**: Strict rate requirements (8/16/22/44/48kHz) matching API specifications
- **Voice Trigger Provider Base Class Updates**: Added comprehensive audio capability methods
  - `get_supported_sample_rates() -> List[int]` - all supported rates
  - `get_default_sample_rate() -> int` - optimal rate for provider
  - `supports_resampling() -> bool` - internal resampling capability
  - `get_default_channels() -> int` - preferred channel count
- **Voice Trigger Provider Implementations Enhanced**:
  - **OpenWakeWord**: Flexible 8-44kHz support with 16kHz preference, resampling capable
  - **MicroWakeWord**: Strict 16kHz requirement for micro_speech compatibility, no resampling
- **Enhanced Parameter Schemas**: All providers now include sample rate preferences and constraints

### **✅ Phase 4: Component Architecture Updates (COMPLETED):**
- **ASR Component Enhancement**: Intelligent `process_audio()` method with complete workflow
  - **Step 1**: Extract provider requirements using Phase 3 capabilities
  - **Step 2**: Check sample rate compatibility with `supports_sample_rate()`
  - **Step 3**: Auto-resample using Phase 2 infrastructure when needed
  - **Step 4**: Call `transcribe_audio()` with converted/compatible data
  - **Step 5**: Handle fallback providers on rate mismatch via `_handle_sample_rate_mismatch()`
- **Voice Trigger Component Enhancement**: Real-time optimized `detect()` method
  - **Step 1**: Check resampling needs based on provider configuration 
  - **Step 2**: Apply efficient resampling with latency-optimized methods
  - **Step 3**: Call provider `detect_wake_word()` with correct format
  - **Step 4**: Handle provider fallbacks with sample rate intelligence
- **Sample Rate Mismatch Handlers**: Comprehensive fallback strategies
  - **ASR Handler**: Multi-level fallback (provider switching → force resampling → degraded processing)
  - **Voice Trigger Handler**: Provider-aware fallback with resampling support
  - **Intelligent Provider Selection**: Automatic compatible provider discovery
- **Configuration Integration**: Full integration with Phase 2 validation and Phase 5 configuration
  - **Resampling Control**: Honor `allow_resampling` and `resample_quality` settings
  - **Provider Preferences**: Respect provider capabilities and limitations
  - **Performance Optimization**: Voice trigger uses fast resampling, ASR uses quality resampling

### **✅ Phase 5: Configuration and Validation (COMPLETED):**
- **Configuration Model Enhancements**: Extended Pydantic models with Phase 5 audio parameters
  - **ASRConfig**: Added `sample_rate`, `channels`, `allow_resampling`, `resample_quality` with validation
  - **VoiceTriggerConfig**: Added audio parameters plus `strict_validation` for fatal error control
  - **MicrophoneInputConfig**: Added `auto_resample` and global `resample_quality` configuration
  - **Field Validation**: Comprehensive validation for sample rates (8-192kHz), channels (1-8), quality levels
- **Startup Validation**: Fatal error detection with immediate shutdown capability
  - **AudioConfigurationValidator**: Complete Phase 5 validation workflow implementation
  - **Fatal Error Conditions**: Configuration contradictions cause immediate startup failure
  - **Provider Requirement Conflicts**: Hard stop if provider requirements contradict configuration
  - **Cross-component Compatibility**: Validate microphone, ASR, and voice trigger consistency
- **Configuration Resolution Logic**: Three-tier priority system implementation
  - **Priority 1**: Explicit configuration is AUTHORITATIVE and overrides provider preferences
  - **Priority 2**: Provider defaults used only when configuration is missing/unspecified
  - **Priority 3**: System defaults fallback when both config and provider defaults unavailable
  - **`resolve_audio_config()`**: Complete resolution logic with fatal error handling
- **Runtime Monitoring**: Performance metrics and configuration tracking in both components
  - **ASR Component Metrics**: Total operations, timing, failure rates, success rates, provider fallbacks
  - **Voice Trigger Component Metrics**: Resampling metrics plus detection success/failure tracking
  - **Provider Fallback Tracking**: Automatic fallback usage statistics in both components
  - **Configuration Validation**: Success/failure logging with detailed error reporting
  - **Performance Analytics**: Average resampling time and overhead measurement
  - **Detection Analytics**: Wake word detection success rates and operation counts

### **✅ Phase 6: Advanced Features (COMPLETED):**

#### **✅ 6.1 Performance Optimization (COMPLETED):**
- **Voice Trigger**: Implemented optimized resampling with minimal latency overhead using latency-optimized conversion paths
  - `get_optimal_conversion_path()` with `use_case="voice_trigger"` prioritizes ConversionMethod.LINEAR for fastest processing
  - Real-time processing optimizations with fast quality settings override for voice trigger scenarios
  - Buffer management with pre-allocated conversion buffers in pool sizes (1KB-32KB) for memory efficiency
- **ASR**: Implemented cached resampling for repeated rates with intelligent cache management
  - Resampling cache with MD5-based cache keys using first 1KB of audio data for performance
  - FIFO eviction policy when cache reaches maximum size (100 entries by default)
  - Cache hit/miss tracking with performance statistics via `AudioProcessor.get_cache_stats()`
  - Quality-optimized conversion paths using `use_case="asr"` for highest quality resampling
- **Streaming**: Enhanced chunk-based real-time conversion with parallel processing capabilities
  - `convert_audio_data_streaming()` with optional parallel chunk processing for multi-core utilization
  - Order-preserving parallel conversion using asyncio.gather() with indexed chunk processing
  - Sequential fallback for single chunks or when parallel processing is disabled
- **Memory**: Buffer management for conversion operations with pooled buffer allocation
  - Pre-allocated buffer pools with optimal sizes (1KB, 2KB, 4KB, 8KB, 16KB, 32KB)
  - Efficient buffer reuse to minimize memory allocation overhead during conversion operations

#### **✅ 6.2 Quality-Performance Trade-offs (COMPLETED):**
- **Enhanced Resampling Quality Levels**: Implemented sophisticated quality level system with dynamic method selection
  - **fast**: Linear interpolation (lowest latency) - optimized for voice trigger real-time processing
  - **medium**: Polyphase filtering (balanced) - default balanced approach for general use
  - **high**: Kaiser windowed sinc (best quality) - optimized for ASR transcription accuracy
  - **adaptive**: Dynamic method selection based on sample rate ratio for optimal results
    - Ratio ≤ 2.0: kaiser_fast for good quality with reasonable performance
    - Ratio ≤ 4.0: FFT-based resampling for medium quality large ratio changes
    - Ratio > 4.0: soxr_hq for highest quality extreme ratio conversions
- **Use Case Optimization**: Context-aware conversion method selection
  - **Voice Trigger**: Prioritizes low latency over quality (Linear for ratio ≤ 2.0, Polyphase for larger ratios)
  - **ASR**: Prioritizes quality over latency (Sinc Kaiser for ratio ≤ 1.5, Polyphase for medium, Adaptive for large)
  - **General**: Balanced approach using Polyphase for consistent results across ratio ranges
- **Runtime Method Selection**: Dynamic librosa resampling type selection based on ConversionMethod and ratio analysis

#### **✅ 6.3 Component Integration (COMPLETED):**
- **ASR Component**: Enhanced with Phase 6 optimizations for quality-focused audio processing
  - `use_case="asr"` in conversion path selection for highest quality resampling
  - Cache statistics integration in `get_runtime_metrics()` for performance monitoring
  - Quality-optimized resampling for both primary processing and fallback scenarios
- **Voice Trigger Component**: Enhanced with Phase 6 optimizations for latency-focused real-time processing
  - `use_case="voice_trigger"` in conversion path selection for minimal latency overhead
  - Fast quality override for real-time voice trigger scenarios to ensure responsive detection
  - Latency-optimized resampling in both main detection flow and fallback provider scenarios
- **Performance Monitoring**: Cache statistics and buffer utilization tracking integrated into existing metrics
  - Cache hit rates, cache size, and memory usage statistics available via component metrics
  - Buffer pool utilization and allocation efficiency tracking for conversion operations

### **✅ Phase 7: Testing and Documentation (COMPLETED):**

#### **✅ 7.1 Test Coverage (COMPLETED):**
- **Unit Tests for All Sample Rate Combinations**: Comprehensive test suite covering all common sample rate conversions
  - `test_phase7_audio_resampling.py`: Tests all sample rate combinations (8kHz-96kHz) with different conversion methods
  - Tests for cache performance, compatibility validation, and optimal conversion path selection
  - Error handling tests for invalid audio data, extreme sample rates, and cache overflow scenarios
  - Sample rate compatibility validation tests covering direct compatibility and efficient ratio validation
- **Integration Tests with Real Audio Hardware**: Complete integration testing with hardware simulation
  - `test_phase7_integration.py`: Hardware scenario testing with mock providers and realistic audio configurations
  - Tests for microphone input compatibility (16kHz, 44.1kHz, 48kHz) with ASR and voice trigger providers
  - Sample rate mismatch scenarios with automatic fallback behavior validation
  - Real-time streaming simulation with continuous processing and concurrent component operation
  - Provider fallback chain testing with multiple providers and different capabilities
- **Performance Benchmarks for Resampling Overhead**: Detailed performance analysis and benchmarking
  - `test_phase7_performance.py`: Comprehensive performance benchmark suite with real-time factor analysis
  - Latency benchmarks for voice trigger (target <0.1x real-time) and ASR scenarios
  - Throughput benchmarks with concurrent processing and streaming chunk analysis
  - Memory usage scaling tests, cache effectiveness measurement, and stress tests for extreme conditions
  - Performance regression testing to ensure optimization improvements maintain expected performance levels
- **Fallback Provider Chain Testing**: Complete fallback mechanism validation
  - `test_phase7_fallback_chains.py`: Comprehensive fallback chain testing with realistic failure scenarios
  - Primary provider failure testing with automatic fallback to backup providers
  - Sample rate compatibility fallback with provider switching based on supported rates
  - Multiple provider fallback chains with ordered preference and graceful degradation testing
  - Intermittent failure handling and configuration-driven fallback preference testing

#### **✅ 7.2 Documentation Updates (COMPLETED):**
- **Configuration Guide for Audio Hardware Compatibility**: Complete hardware configuration reference
  - `AUDIO_HARDWARE_COMPATIBILITY.md`: Comprehensive guide covering basic audio configuration, sample rate selection, and provider-specific settings
  - Hardware scenario guides for USB microphones (48kHz), embedded devices (16kHz), multi-channel interfaces, and low-power IoT devices
  - Performance optimization recommendations with resampling quality trade-offs and cache configuration
  - Validation commands, debug logging setup, and best practices summary for optimal configuration
- **Troubleshooting Guide for Sample Rate Issues**: Detailed problem diagnosis and resolution
  - `AUDIO_TROUBLESHOOTING.md`: Complete troubleshooting guide with quick diagnosis checklist and common solutions
  - Sample rate issue resolution covering "sample rate mismatch," "resampling failed," and "no compatible providers" errors
  - Provider problem diagnosis including "provider not available" and initialization failure solutions
  - Performance issue troubleshooting for high latency, poor ASR performance, and memory leak detection
  - Hardware problem resolution for microphone detection and audio dropouts/distortion
  - Debug tools section with logging configuration, audio test commands, and advanced diagnostics
- **Performance Tuning Recommendations**: Comprehensive optimization guide
  - `AUDIO_PERFORMANCE_TUNING.md`: Detailed performance optimization covering latency, throughput, and memory efficiency
  - Quality vs performance trade-offs with resampling quality level analysis and use case recommendations
  - Cache optimization strategies, hardware-specific tuning, and monitoring/benchmarking frameworks
  - Advanced optimization techniques including custom conversion methods and profile-guided optimization
- **Provider-Specific Audio Requirements**: Complete provider reference documentation
  - `AUDIO_PROVIDER_REQUIREMENTS.md`: Detailed requirements for all ASR and voice trigger providers
  - ASR provider specifications for VOSK (model-dependent rates), Whisper (automatic resampling), and Google Cloud (strict requirements)
  - Voice trigger provider specifications for OpenWakeWord (flexible resampling) and MicroWakeWord (strict 16kHz requirement)
  - Provider comparison matrices, configuration examples, performance characteristics, and recommendation guidelines
  - Environment-specific configurations for high-performance workstations, embedded devices, and cloud-connected setups

### **✅ Sprint 1 (Critical) - COMPLETED:**
1. ✅ Fix runtime method errors
2. ✅ Add basic process_audio bridge methods
3. Basic sample rate validation

### **✅ Sprint 2 (Core Infrastructure) - COMPLETED:**
4. ✅ AudioData resampling infrastructure
5. ✅ Provider capability detection
6. ✅ Configuration validation

### **✅ Sprint 3 (Advanced Features) - COMPLETED:**
7. ✅ Performance optimization
8. ✅ Quality trade-off options
9. ✅ Runtime monitoring

### **✅ Sprint 4 (Polish) - COMPLETED:**
10. ✅ Comprehensive testing
11. ✅ Documentation updates
12. ✅ Performance monitoring

## **Risk Mitigation**

### **Voice Trigger Risks:**
- **Latency**: Efficient resampling algorithms for real-time performance
- **Accuracy**: Configuration validation ensures optimal model performance
- **Real-time**: Cached resampling and optimized pipelines

### **ASR Risks:**
- **Quality**: Configurable resampling quality levels
- **Performance**: Cached conversion and provider fallbacks
- **Compatibility**: Graceful degradation with warnings

### **System Risks:**
- **Startup**: Early validation prevents runtime surprises
- **Configuration**: Clear error messages for mismatches
- **Fallbacks**: Multiple provider options for robustness

## **Design Decisions**

### **Single Provider Philosophy**
- Real deployments typically use one ASR provider and one voice trigger provider
- No need for intelligent provider selection based on sample rates
- Focus on compatibility validation and resampling for the configured provider
- Fallback providers used only for failure recovery, not rate optimization

### **Component Separation**
- Voice Trigger: Configuration-driven with efficient resampling support
- ASR: Configuration-driven with flexible resampling options
- Both components respect configuration authority over provider preferences

### **Configuration-Driven**
- **Configuration Authority**: User configuration overrides provider preferences
- **Fatal Error Validation**: Contradictions cause immediate startup failure
- **Provider Defaults**: Used only when configuration is unspecified
- **Resampling Support**: All components support resampling when configured
- **Clear Error Messages**: Specific validation failures with resolution guidance

This plan addresses both the immediate runtime issues and establishes a robust foundation for audio compatibility across the entire system, with special consideration for the real-time requirements of voice trigger detection versus the more flexible requirements of ASR processing.
