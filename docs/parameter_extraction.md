# Parameter Extraction Architecture Redesign

## Executive Summary

This document outlines the architectural redesign to move parameter extraction from a separate `JSONBasedParameterExtractor` component into NLU providers themselves, creating a unified donation consumption model and eliminating duplicate spaCy model loading.

## Current Architecture Problems

### Issue 1: Duplicate spaCy Model Loading
- **Parameter Extractor**: Tries to load `ru_core_news_sm` independently
- **SpaCy NLU Provider**: Loads the same model with asset management
- **Result**: Resource waste, architectural inconsistency, model loading failures

### Issue 2: Multiple Donation Consumers
```
JSON Donations → DonationLoader → {
    IntentHandlerManager → JSONBasedParameterExtractor (consumer 1)
    NLUComponent → NLUProviders (consumer 2)
}
```

### Issue 3: Architectural Inconsistency
- Parameter extraction is cross-cutting concern handled separately
- No shared NLP resources between intent recognition and parameter extraction
- Different error handling and asset management approaches

### Issue 4: CRITICAL - spaCy Validation Blocking System Startup
- **Donation Loading**: Validates ALL spaCy patterns at startup (182 patterns across 14 handlers)
- **System Failure**: Entire system fails if spaCy unavailable, even for basic functionality
- **Wrong Validation Scope**: Optional advanced features treated as mandatory dependencies
- **Deployment Problem**: Works in development (with spaCy) but fails in production (without spaCy)

## Proposed Solution: Unified NLU Provider Architecture

### Core Principles
1. **Single Consumer Model**: NLU providers become the only consumers of donations
2. **Provider-Specific Validation**: Each provider validates only patterns it actually uses
3. **Graceful Degradation**: System works with reduced functionality when dependencies unavailable
4. **Startup Resilience**: Only JSON schema and method existence validated at startup

## Architecture Overview

### New Donation Flow
```
JSON Donations → DonationLoader (JSON + Method validation ONLY) → ✓ Always succeeds
                     ↓
            KeywordDonation objects → NLU Component → NLU Providers
                     ↓
    SpaCy Provider: Validates spaCy patterns → Degrades gracefully if spaCy unavailable
    Hybrid Provider: Uses basic patterns → Always works (no spaCy dependency)
```

### New Processing Flow
```
Text Input → NLU Provider → {
    Step 1: recognize() → Intent (with basic entities)
    Step 2: extract_parameters() → Enhanced Intent (with extracted parameters)
} → Enhanced Intent
```

### Validation Separation Strategy
```
STARTUP (Universal - Always Required):
✓ JSON schema compliance
✓ Method existence in handlers
✓ Basic field validation

RUNTIME (Provider-Specific - Optional):
✓ SpaCy Provider: Validates spaCy patterns if spaCy available
✓ Hybrid Provider: No advanced validation needed
✓ Graceful degradation on validation failures
```

## Data Structure Analysis

### KeywordDonation Structure (Already Perfect!)
The existing `KeywordDonation` class already bundles both pieces of information:

```python
class KeywordDonation(BaseModel):
    intent: str                     # "timer.set", "conversation.general"
    phrases: List[str]              # Basic recognition patterns (no spaCy needed)
    parameters: List[ParameterSpec] # Parameter specifications
    token_patterns: List[...]       # Advanced spaCy patterns (optional)
    slot_patterns: Dict[...]        # Advanced spaCy patterns (optional)
    extraction_patterns: List[...]  # Advanced spaCy patterns (optional)
```

### Pattern Validation by Provider Type

#### Universal Patterns (Always Valid)
```json
{
  "phrases": ["привет", "hello"],           // ✓ Startup: JSON schema only
  "lemmas": ["привет", "здравствовать"],    // ✓ Startup: JSON schema only  
  "parameters": [...],                      // ✓ Startup: JSON schema only
  "method_name": "handle_greeting"          // ✓ Startup: Method existence check
}
```

#### SpaCy-Specific Patterns (Runtime Validation)
```json
{
  "token_patterns": [...],                  // ✓ Runtime: SpaCy provider validates
  "slot_patterns": {...},                   // ✓ Runtime: SpaCy provider validates
  "extraction_patterns": [...]              // ✓ Runtime: SpaCy provider validates
}
```

### Association Mechanism (Already Built-In!)
The `convert_to_keyword_donations()` method creates perfect association:

1. **Intent Name**: `f"{donation.handler_domain}.{method_donation.intent_suffix}"`
2. **Parameters**: `method_donation.parameters + donation.global_parameters`
3. **Bundling**: Both stored in the same `KeywordDonation` object

**No additional mapping logic needed!** The intent name serves as the natural key for both recognition patterns and parameter specifications.

## Implementation Plan

### Phase 0: Fix Donation Validation (CRITICAL - System Blocking Issue)

#### Remove spaCy Validation from Startup
```python
# In irene/core/donation_loader.py
async def _load_and_validate_donation(self, json_path: Path, handler_path: Path):
    # Validate JSON schema ✓ 
    await self._validate_json_schema(json_data, json_path)
    
    # Validate method existence ✓
    await self._validate_method_existence(donation, handler_path)
    
    # REMOVE: await self._validate_spacy_patterns(donation) ❌
    # SpaCy validation moved to providers at runtime
```

#### Update Validation Configuration
```python
# In irene/intents/manager.py - Fix default config
"donation_validation": {
    "strict_mode": True,                    # Keep strict for JSON/method validation
    "validate_method_existence": True,      # ✓ Required at startup
    "validate_spacy_patterns": False,       # ❌ Never at startup
    "validate_json_schema": True           # ✓ Required at startup
}
```

#### Immediate Benefit
- **System starts successfully** even without spaCy
- **Basic NLU functionality** always available via Hybrid provider
- **Advanced features** degrade gracefully

### Phase 1: NLU Provider Base Class Enhancement

#### Add Parameter Extraction Interface
```python
# In irene/providers/nlu/base.py
@abstractmethod
async def extract_parameters(self, text: str, intent_name: str, parameter_specs: List[ParameterSpec]) -> Dict[str, Any]:
    """Extract parameters using provider's NLP capabilities"""
    pass

async def recognize_with_parameters(self, text: str, context: ConversationContext) -> Intent:
    """Recognize intent and extract parameters in one operation"""
    # Default implementation - providers can override for optimization
    intent = await self.recognize(text, context)
    
    if intent.name in self.parameter_specs:
        parameters = await self.extract_parameters(text, intent.name, self.parameter_specs[intent.name])
        intent.entities.update(parameters)
    
    return intent
```

#### Add Parameter Storage
```python
class NLUProvider(ProviderBase):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Existing fields...
        
        # NEW: Parameter specifications storage
        self.parameter_specs: Dict[str, List[ParameterSpec]] = {}  # intent_name -> parameter specs
```

### Phase 2: SpaCy Provider Implementation

#### Enhance Initialization with spaCy Pattern Validation
```python
async def _initialize_from_donations(self, keyword_donations: List[KeywordDonation]) -> None:
    """Initialize provider with both intent patterns AND parameter specs + spaCy validation"""
    
    # Clear existing data
    self.intent_patterns = {}
    self.parameter_specs = {}
    self.advanced_patterns = {}
    
    for donation in keyword_donations:
        intent_name = donation.intent
        
        # Store basic patterns (always works)
        self.intent_patterns[intent_name] = donation.phrases
        self.parameter_specs[intent_name] = donation.parameters
        
        # Validate and store spaCy patterns (runtime validation)
        if self.nlp:  # spaCy available
            try:
                self._validate_and_store_spacy_patterns(donation)
                logger.debug(f"SpaCy patterns validated for '{intent_name}'")
            except Exception as e:
                logger.warning(f"Invalid spaCy patterns for '{intent_name}': {e} - using basic functionality")
                # Continue without advanced patterns - graceful degradation
        else:
            logger.info(f"SpaCy unavailable - using basic patterns only for '{intent_name}'")
        
        logger.debug(f"Registered intent '{intent_name}' with {len(donation.phrases)} phrases and {len(donation.parameters)} parameters")

def _validate_and_store_spacy_patterns(self, donation: KeywordDonation) -> None:
    """Validate spaCy patterns at runtime (moved from donation loading)"""
    try:
        # Validate token patterns
        for i, pattern in enumerate(donation.token_patterns):
            self.matcher.add(f"test_token_{donation.intent}_{i}", [pattern])
        
        # Validate slot patterns
        for slot_name, patterns in donation.slot_patterns.items():
            for i, pattern in enumerate(patterns):
                self.entity_ruler.add_patterns([{"label": slot_name, "pattern": pattern}])
        
        # Store validated advanced patterns
        self.advanced_patterns[donation.intent] = {
            "token_patterns": donation.token_patterns,
            "slot_patterns": donation.slot_patterns,
            "extraction_patterns": donation.extraction_patterns
        }
        
    except Exception as e:
        # Pattern validation failed - log warning but continue
        logger.warning(f"SpaCy pattern validation failed for {donation.intent}: {e}")
        # Provider falls back to basic phrase matching
```

#### Implement Parameter Extraction
```python
async def extract_parameters(self, text: str, intent_name: str, parameter_specs: List[ParameterSpec]) -> Dict[str, Any]:
    """Extract parameters using spaCy NLP capabilities"""
    if not self.nlp or not parameter_specs:
        return {}
    
    # Process text with existing spaCy model
    doc = self.nlp(text)
    
    extracted_params = {}
    
    for param_spec in parameter_specs:
        try:
            # Reuse existing spaCy logic from JSONBasedParameterExtractor
            value = await self._extract_single_parameter_spacy(doc, param_spec, text)
            
            if value is not None:
                converted_value = self._convert_and_validate_parameter(value, param_spec)
                extracted_params[param_spec.name] = converted_value
            elif param_spec.required and param_spec.default_value is None:
                raise ParameterExtractionError(f"Required parameter '{param_spec.name}' not found")
            elif param_spec.default_value is not None:
                extracted_params[param_spec.name] = param_spec.default_value
                
        except Exception as e:
            if param_spec.required:
                raise ParameterExtractionError(f"Failed to extract required parameter '{param_spec.name}': {e}")
            else:
                logger.warning(f"Failed to extract optional parameter '{param_spec.name}': {e}")
    
    return extracted_params
```

### Phase 3: Hybrid Provider Implementation

#### Store Parameters (No Advanced Validation Needed)
```python
async def _initialize_from_donations(self, keyword_donations: List[KeywordDonation]) -> None:
    """Initialize hybrid provider - ignores spaCy patterns, no validation needed"""
    
    # Clear existing data
    self.intent_patterns = {}
    self.parameter_specs = {}
    
    for donation in keyword_donations:
        intent_name = donation.intent
        
        # Store basic patterns (what hybrid provider uses)
        self.intent_patterns[intent_name] = donation.phrases
        self.parameter_specs[intent_name] = donation.parameters
        
        # IGNORE advanced spaCy patterns - hybrid provider doesn't use them
        # No validation needed, no errors possible
        
        logger.debug(f"Registered hybrid intent '{intent_name}' with {len(donation.phrases)} phrases and {len(donation.parameters)} parameters")
```

#### Simple Parameter Extraction
```python
async def extract_parameters(self, text: str, intent_name: str, parameter_specs: List[ParameterSpec]) -> Dict[str, Any]:
    """Extract parameters using regex and fuzzy matching"""
    if not parameter_specs:
        return {}
    
    extracted_params = {}
    text_lower = text.lower()
    
    for param_spec in parameter_specs:
        try:
            # Use regex pattern matching
            if param_spec.pattern:
                value = self._extract_with_regex(text, param_spec)
            else:
                # Use type-specific extraction
                value = self._extract_by_type(text_lower, param_spec)
            
            if value is not None:
                converted_value = self._convert_and_validate_parameter(value, param_spec)
                extracted_params[param_spec.name] = converted_value
            elif param_spec.default_value is not None:
                extracted_params[param_spec.name] = param_spec.default_value
                
        except Exception as e:
            logger.warning(f"Failed to extract parameter '{param_spec.name}': {e}")
    
    return extracted_params
```

### Phase 4: NLU Component Integration

#### Remove Parameter Extractor References
```python
# In irene/components/nlu_component.py
async def recognize(self, text: str, context: ConversationContext) -> Intent:
    """Recognize intent using cascading NLU providers with integrated parameter extraction"""
    
    for provider_name in provider_order:
        provider = self.providers[provider_name]
        
        try:
            # Use new integrated method
            intent = await provider.recognize_with_parameters(text, context)
            
            if intent.confidence >= self.confidence_threshold:
                logger.debug(f"Intent recognized by {provider_name}: {intent.name} (confidence: {intent.confidence:.3f})")
                return intent
                
        except Exception as e:
            logger.warning(f"Provider {provider_name} failed: {e}")
            continue
    
    # Return fallback intent
    return self._create_fallback_intent(text, context)
```

### Phase 5: Intent Management Cleanup

#### Remove Parameter Extractor Initialization
```python
# In irene/intents/manager.py
async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
    """Initialize intent handlers with NLU-integrated parameter extraction"""
    
    # Load donations
    await self._load_donations()
    
    # Initialize handlers (existing logic)
    await self._initialize_handlers_with_donations()
    
    # Remove: await self._initialize_parameter_extractor()
    
    # Initialize orchestrator WITHOUT parameter extractor
    self._orchestrator = IntentOrchestrator(self._registry)
    # Remove: self._orchestrator.set_parameter_extractor(self._parameter_extractor)
```

#### Remove Parameter Extraction from Orchestrator
```python
# In irene/intents/orchestrator.py
async def execute_intent(self, intent: Intent, context: ConversationContext) -> IntentResult:
    """Execute intent (parameter extraction now happens in NLU providers)"""
    
    # Remove parameter extraction logic - it's already done in NLU providers
    # Intent already contains extracted parameters
    
    # Execute intent directly
    logger.info(f"Executing intent '{intent.name}' with handler {handler.__class__.__name__}")
    result = await handler.execute(intent, context)
    
    return result
```

### Phase 6: Cleanup

#### Remove JSONBasedParameterExtractor
- Delete `irene/core/parameter_extractor.py`
- Remove imports and references throughout codebase
- Update tests to verify parameter extraction through NLU providers

## Migration Strategy

### Step-by-Step Migration (MECE Implementation)

**Phase 0: Critical Fix** - Resolve system startup blocking ✅ COMPLETED
- ✅ Remove spaCy validation from donation loading
- ✅ Update validation configuration
- ✅ Test system starts successfully without spaCy

**Phase 1: Foundation** - Establish provider interfaces ✅ COMPLETED
- ✅ Add parameter extraction interface to base NLU provider
- ✅ Add parameter storage to provider base class

**Phase 2: SpaCy Integration** - Advanced pattern handling ✅ COMPLETED
- ✅ Move spaCy validation from donation loader to SpaCy provider
- ✅ Implement parameter extraction in SpaCy provider
- ✅ Add graceful degradation for spaCy unavailability

**Phase 3: Hybrid Enhancement** - Basic pattern handling ✅ COMPLETED
- ✅ Implement parameter extraction in Hybrid provider
- ✅ Ensure no spaCy dependencies in hybrid provider

**Phase 4: System Integration** - Update core components ✅ COMPLETED
- ✅ Update NLU component to use integrated parameter extraction
- ✅ Remove parameter extractor references from orchestrator

**Phase 5: Cleanup** - Remove obsolete components ✅ COMPLETED
- ✅ Remove parameter extractor from intent management
- ✅ Delete JSONBasedParameterExtractor class
- ✅ Update all references and imports

**Phase 6: Validation** - Ensure system integrity ✅ COMPLETED
- ✅ Run comprehensive tests
- ✅ Verify both spaCy and non-spaCy deployments work
- ✅ Validate graceful degradation scenarios
- ✅ Remove obsolete JSONBasedParameterExtractor class and references
- ✅ Update tests to reflect new architecture

### Backwards Compatibility
- Existing intent handlers continue to work unchanged
- Existing JSON donations work without modification
- No configuration changes required

### Testing Strategy
- Unit tests for each provider's parameter extraction
- Integration tests for complete flow
- Regression tests to ensure no functionality loss

## Benefits

### 1. **System Resilience** 
- **Startup Success**: System always starts, even without optional dependencies
- **Graceful Degradation**: Advanced features fail gracefully, basic functionality preserved
- **Deployment Flexibility**: Works in minimal environments (no spaCy) and full environments

### 2. **Architectural Consistency**
- **Single Consumer**: NLU providers are only donation consumers
- **Provider Ownership**: Each provider validates only what it uses
- **Separation of Concerns**: Startup validation vs runtime capabilities clearly separated

### 3. **Performance Improvements**
- **Single Pass Processing**: Intent recognition and parameter extraction in one operation
- **No Duplicate Loading**: Shared spaCy models between recognition and extraction
- **Reduced Latency**: Eliminated separate parameter extraction step

### 4. **Maintainability**
- **Cleaner Codebase**: Removed entire `JSONBasedParameterExtractor` class
- **Logical Organization**: spaCy logic consolidated in spaCy provider
- **Clear Responsibilities**: Each component has well-defined ownership

### 5. **Provider-Specific Optimization**
- **SpaCy Provider**: Advanced NLP-based pattern matching and parameter extraction
- **Hybrid Provider**: Fast regex/fuzzy matching without external dependencies
- **Extensibility**: Easy to add new providers with their own validation strategies

## Implementation Files

### Files to Modify (Organized by Phase)

#### Phase 0: Critical Donation Validation Fix
- `irene/core/donation_loader.py` - Remove spaCy validation from startup
- `irene/intents/manager.py` - Update validation configuration defaults

#### Phase 1-2: NLU Provider Enhancement  
- `irene/providers/nlu/base.py` - Add parameter extraction interface
- `irene/providers/nlu/spacy_provider.py` - Add spaCy validation + parameter extraction
- `irene/providers/nlu/hybrid_keyword_matcher.py` - Add parameter extraction

#### Phase 4-5: System Integration & Cleanup
- `irene/components/nlu_component.py` - Use integrated parameter extraction
- `irene/intents/manager.py` - Remove parameter extractor initialization  
- `irene/intents/orchestrator.py` - Remove parameter extraction step

### Files to Remove
- `irene/core/parameter_extractor.py` - Entire file becomes obsolete

### Tests to Update
- `irene/tests/test_spacy_asset_integration.py` - Update for provider-based extraction
- `irene/tests/test_phase1_integration.py` - Update integration tests
- Add new tests for:
  - Provider parameter extraction
  - Graceful degradation scenarios
  - Startup without spaCy dependencies

## Conclusion

This unified architecture redesign solves both the immediate system startup issue and the long-term architectural problems through a comprehensive provider-centric approach.

### Immediate Resolution (Phase 0)
- **System Startup**: Fixes critical blocking issue where system fails without spaCy
- **Deployment Reliability**: Ensures system works in any environment

### Long-term Architecture (Phases 1-6)
- **Single Consumer Model**: NLU providers become sole donation consumers
- **Provider Ownership**: Each provider validates only what it uses
- **Graceful Degradation**: Advanced features fail gracefully, preserving core functionality
- **Performance Optimization**: Eliminated duplicate processing and resource loading

### Final Architecture Benefits
- **Resilient**: System starts successfully regardless of optional dependencies
- **Efficient**: Single-pass processing with shared resources
- **Maintainable**: Clear separation of concerns and logical component organization
- **Extensible**: Easy to add new providers with their own capabilities
- **Robust**: Graceful handling of missing dependencies and validation failures

The existing donation system already provides perfect data structures for this approach, requiring no changes to donation formats or configurations. This makes the migration low-risk while delivering significant architectural improvements.
