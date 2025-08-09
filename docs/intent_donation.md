# Intent Keyword Donation Architecture

## Overview

This document describes the unified solution for TODO07 (Disconnected NLU and Intent Handler Systems) and TODO08 (NLU Architecture Revision), implementing a keyword-first NLU architecture with cascading spaCy semantic fallbacks, integrated parameter extraction, and JSON-based donation specifications.

## Architecture Principles

### 1. Intent-Driven Recognition
- Intent handlers **donate** their recognition patterns via JSON files
- Single source of truth: handlers own their identification logic through declarative specifications
- Dynamic pattern collection at startup eliminates manual synchronization

### 2. Cascading Performance Optimization
- **Fast path**: Hybrid keyword matching (patterns + fuzzy) handles 80-90% of common intents
- **Rule path**: spaCy sm model with enhanced morphological patterns 
- **Semantic path**: spaCy md model with vector-based understanding
- **Fallback**: Conversation handler for unmatched utterances

### 3. Resource-Adaptive Deployment
- Full pipeline for servers/desktops (~180MB total)
- Rule-only pipeline for edge devices (~80MB total)
- Keyword-only pipeline for ultra-constrained devices (~20MB total)

### 4. Integrated Parameter Extraction
- Declarative parameter specifications in JSON donations
- Automatic parameter extraction during NLU recognition
- Type-safe parameter validation and conversion

### 5. Context-Aware Processing
- ClientId and metadata used as NLU processing context, not text augmentation
- Entity resolution using client capabilities and room context
- Contextual intent disambiguation based on available devices

### 6. Declarative Configuration Management
- JSON-based donation files with pydantic validation
- Fatal error on validation failure ensures consistency
- Separation of intent logic (Python) from recognition patterns (JSON)

## Donation System Architecture

### A. JSON-Based Donation Format

#### A1. File Structure and Discovery

```
irene/intents/handlers/
├── timer.py                    # Python handler logic
├── timer.json                  # Intent donations for timer
├── greetings.py               # Python handler logic  
├── greetings.json             # Intent donations for greetings
└── weather/
    ├── weather_handler.py
    └── weather_handler.json
```

**Discovery Rules:**
- JSON donation file must have same name as Python handler file
- JSON file must be in same directory as Python handler
- Missing JSON file for existing handler = fatal error
- JSON file without corresponding handler = ignored with warning

#### A2. JSON Schema Structure

```json
{
  "$schema": "https://irene-voice-assistant.org/schemas/donation/v1.0.json",
  "schema_version": "1.0",
  "handler_domain": "timer",
  "description": "Timer functionality with duration and message support",
  
  "global_parameters": [
    {
      "name": "retain",
      "type": "boolean",
      "required": false,
      "default_value": false,
      "description": "Whether to retain state across sessions"
    }
  ],
  
  "method_donations": [
    {
      "method_name": "set_timer",
      "intent_suffix": "set",
      "description": "Set a timer with duration and optional message",
      
      "phrases": [
        "поставь таймер", "заведи будильник", "установи напоминание",
        "засеки время", "напомни через", "разбуди через"
      ],
      
      "lemmas": ["поставить", "завести", "установить", "засечь", "таймер", "будильник"],
      
      "parameters": [
        {
          "name": "duration",
          "type": "integer",
          "required": true,
          "description": "Timer duration number",
          "min_value": 1,
          "max_value": 86400,
          "extraction_patterns": [
            {"pattern": [{"LIKE_NUM": true}], "label": "DURATION_VALUE"},
            {"pattern": [{"TEXT": {"REGEX": "^\\d+$"}}], "label": "DURATION_VALUE"}
          ],
          "aliases": ["время", "длительность", "на"]
        },
        {
          "name": "unit",
          "type": "choice",
          "required": false,
          "default_value": "minutes",
          "description": "Time unit for duration",
          "choices": ["seconds", "minutes", "hours"],
          "extraction_patterns": [
            {"pattern": [{"LEMMA": {"IN": ["секунда", "минута", "час"]}}], "label": "TIME_UNIT"},
            {"pattern": [{"LOWER": {"IN": ["сек", "мин", "ч"]}}], "label": "TIME_UNIT"}
          ],
          "aliases": ["единица", "время"]
        },
        {
          "name": "message",
          "type": "string",
          "required": false,
          "default_value": "Таймер завершён!",
          "description": "Custom message when timer completes",
          "extraction_patterns": [
            {"pattern": [{"LOWER": {"IN": ["сообщение", "напомни", "скажи"]}}, {"IS_SENT_START": false}], "label": "TIMER_MESSAGE"}
          ],
          "aliases": ["текст", "напоминание"]
        }
      ],
      
      "token_patterns": [
        [{"POS": "VERB", "LEMMA": {"IN": ["поставить", "установить", "завести"]}}, 
         {"LEMMA": {"IN": ["таймер", "будильник", "напоминание"]}}],
        [{"LEMMA": "таймер"}, {"LOWER": "на"}, {"LIKE_NUM": true}]
      ],
      
      "slot_patterns": {
        "DURATION_VALUE": [
          [{"LIKE_NUM": true}, {"LEMMA": {"IN": ["минута", "секунда", "час"]}}],
          [{"TEXT": {"REGEX": "^\\d+$"}}, {"LOWER": {"IN": ["мин", "сек", "ч"]}}]
        ],
        "TIME_UNIT": [
          [{"LEMMA": {"IN": ["секунда", "минута", "час"]}}],
          [{"LOWER": {"IN": ["сек", "мин", "ч"]}}]
        ],
        "TIMER_MESSAGE": [
          [{"LOWER": "сообщение"}, {"IS_ALPHA": true, "OP": "+"}],
          [{"LOWER": "напомни"}, {"IS_ALPHA": true, "OP": "+"}]
        ]
      },
      
      "examples": [
        {
          "text": "поставь таймер на 5 минут",
          "parameters": {"duration": 5, "unit": "minutes"}
        },
        {
          "text": "заведи будильник на 2 часа с сообщением проснись",
          "parameters": {"duration": 2, "unit": "hours", "message": "проснись"}
        },
        {
          "text": "засеки 30 сек",
          "parameters": {"duration": 30, "unit": "seconds"}
        }
      ],
      
      "boost": 1.2
    }
  ],
  
  "negative_patterns": [
    [{"LEMMA": {"IN": ["отменить", "убрать", "стоп"]}}, {"LEMMA": "таймер"}]
  ]
}
```

### B. Pydantic Validation Schema

#### B1. Python Schema Models

```python
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Union
from enum import Enum

class ParameterType(str, Enum):
    """Types of parameters that can be extracted"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DURATION = "duration"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    ENTITY = "entity"

class ParameterSpec(BaseModel):
    """Specification for a parameter that can be extracted from user input"""
    name: str = Field(..., description="Parameter name")
    type: ParameterType = Field(..., description="Parameter type")
    required: bool = Field(True, description="Is this parameter mandatory?")
    default_value: Any = Field(None, description="Default if not provided")
    description: str = Field("", description="Human-readable description")
    
    # Type-specific configurations
    choices: Optional[List[str]] = Field(None, description="Valid choices for CHOICE type")
    min_value: Optional[Union[int, float]] = Field(None, description="Minimum value for numeric types")
    max_value: Optional[Union[int, float]] = Field(None, description="Maximum value for numeric types")
    pattern: Optional[str] = Field(None, description="Regex pattern for STRING type")
    
    # Extraction configuration
    extraction_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="spaCy extraction patterns")
    aliases: List[str] = Field(default_factory=list, description="Alternative parameter names")
    
    @validator('choices')
    def choices_required_for_choice_type(cls, v, values):
        if values.get('type') == ParameterType.CHOICE and not v:
            raise ValueError('choices required for CHOICE parameter type')
        return v
    
    @validator('min_value', 'max_value')
    def numeric_validators_for_numeric_types(cls, v, values):
        param_type = values.get('type')
        if v is not None and param_type not in [ParameterType.INTEGER, ParameterType.FLOAT]:
            raise ValueError(f'min_value/max_value only valid for numeric types, got {param_type}')
        return v

class TrainingExample(BaseModel):
    """Training example with expected parameters"""
    text: str = Field(..., description="Example user input text")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Expected extracted parameters")

class MethodDonation(BaseModel):
    """Donation for a specific handler method"""
    method_name: str = Field(..., description="Python method name in handler")
    intent_suffix: str = Field(..., description="Intent suffix after domain")
    description: Optional[str] = Field("", description="Method description")
    
    # Recognition patterns
    phrases: List[str] = Field(..., min_items=1, description="Trigger phrases")
    lemmas: List[str] = Field(default_factory=list, description="Key lemmas")
    
    # Parameter specifications
    parameters: List[ParameterSpec] = Field(default_factory=list, description="Method parameters")
    
    # spaCy patterns
    token_patterns: List[List[Dict[str, Any]]] = Field(default_factory=list, description="spaCy token patterns")
    slot_patterns: Dict[str, List[List[Dict[str, Any]]]] = Field(default_factory=dict, description="spaCy slot patterns")
    
    # Training data
    examples: List[TrainingExample] = Field(default_factory=list, description="Training examples")
    
    # Configuration
    boost: float = Field(1.0, ge=0.0, le=10.0, description="Pattern strength multiplier")
    
    @validator('method_name')
    def method_name_valid_identifier(cls, v):
        if not v.isidentifier():
            raise ValueError(f'method_name must be valid Python identifier, got: {v}')
        return v

class HandlerDonation(BaseModel):
    """Complete donation from a handler with metadata and validation"""
    schema_version: str = Field(..., description="JSON schema version")
    handler_domain: str = Field(..., description="Handler domain name")
    description: Optional[str] = Field("", description="Handler description")
    
    # Method donations
    method_donations: List[MethodDonation] = Field(..., min_items=1, description="Method-specific donations")
    
    # Global configuration
    global_parameters: List[ParameterSpec] = Field(default_factory=list, description="Shared parameters")
    negative_patterns: List[List[Dict[str, Any]]] = Field(default_factory=list, description="Negative patterns")
    
    @validator('schema_version')
    def supported_schema_version(cls, v):
        supported_versions = ['1.0']
        if v not in supported_versions:
            raise ValueError(f'Unsupported schema version: {v}. Supported: {supported_versions}')
        return v
    
    @validator('handler_domain')
    def domain_valid_identifier(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f'handler_domain must be alphanumeric with hyphens/underscores, got: {v}')
        return v
    
    @validator('method_donations')
    def unique_method_names(cls, v):
        method_names = [method.method_name for method in v]
        if len(method_names) != len(set(method_names)):
            raise ValueError('method_name must be unique within handler')
        return v
    
    @validator('method_donations')
    def unique_intent_suffixes(cls, v):
        intent_suffixes = [method.intent_suffix for method in v]
        if len(intent_suffixes) != len(set(intent_suffixes)):
            raise ValueError('intent_suffix must be unique within handler')
        return v
```

#### B2. Validation Configuration

```python
class DonationValidationConfig(BaseModel):
    """Configuration for donation validation"""
    strict_mode: bool = Field(True, description="Fail on any validation error")
    warn_unused_patterns: bool = Field(True, description="Warn about unused patterns")
    validate_method_existence: bool = Field(True, description="Validate method exists in Python handler")
    validate_spacy_patterns: bool = Field(True, description="Validate spaCy pattern syntax")
    max_methods_per_handler: int = Field(1000, description="Maximum methods per handler")
    max_phrases_per_method: int = Field(100, description="Maximum phrases per method")
```

### C. Donation Discovery and Loading System

#### C1. Enhanced Discovery Process

```python
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class DonationDiscoveryError(Exception):
    """Raised when donation discovery or validation fails"""
    pass

class DonationLoader:
    """Loads and validates JSON donations with fatal error handling"""
    
    def __init__(self, config: DonationValidationConfig):
        self.config = config
        self.validation_errors: List[str] = []
        self.warnings: List[str] = []
    
    async def discover_and_load_donations(self, handler_paths: List[Path]) -> Dict[str, HandlerDonation]:
        """Discover JSON files and load validated donations"""
        donations = {}
        
        for handler_path in handler_paths:
            handler_name = handler_path.stem
            json_path = handler_path.parent / f"{handler_name}.json"
            
            try:
                if not json_path.exists():
                    error_msg = f"Missing JSON donation file for handler '{handler_name}': {json_path}"
                    self._add_error(error_msg)
                    continue
                
                # Load and validate JSON donation
                donation = await self._load_and_validate_donation(json_path, handler_path)
                donations[handler_name] = donation
                
                logger.info(f"Loaded donation for handler '{handler_name}': {len(donation.method_donations)} methods")
                
            except Exception as e:
                error_msg = f"Failed to load donation for handler '{handler_name}': {e}"
                self._add_error(error_msg)
        
        # Check for fatal errors
        if self.validation_errors:
            self._handle_validation_errors()
        
        # Log warnings
        for warning in self.warnings:
            logger.warning(warning)
        
        return donations
    
    async def _load_and_validate_donation(self, json_path: Path, handler_path: Path) -> HandlerDonation:
        """Load and validate a single JSON donation file"""
        
        # Load JSON
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            raise DonationDiscoveryError(f"Invalid JSON syntax in {json_path}: {e}")
        except Exception as e:
            raise DonationDiscoveryError(f"Failed to read {json_path}: {e}")
        
        # Validate with pydantic
        try:
            donation = HandlerDonation(**json_data)
        except Exception as e:
            raise DonationDiscoveryError(f"Schema validation failed for {json_path}: {e}")
        
        # Additional validations
        if self.config.validate_method_existence:
            await self._validate_method_existence(donation, handler_path)
        
        if self.config.validate_spacy_patterns:
            await self._validate_spacy_patterns(donation)
        
        return donation
    
    async def _validate_method_existence(self, donation: HandlerDonation, handler_path: Path):
        """Validate that donated methods exist in Python handler"""
        # Load Python module and check methods exist
        import importlib.util
        
        spec = importlib.util.spec_from_file_location("handler_module", handler_path)
        if not spec or not spec.loader:
            raise DonationDiscoveryError(f"Cannot load Python handler: {handler_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find handler class
        handler_class = None
        for item_name in dir(module):
            item = getattr(module, item_name)
            if (isinstance(item, type) and 
                hasattr(item, '__bases__') and 
                'IntentHandler' in [base.__name__ for base in item.__bases__]):
                handler_class = item
                break
        
        if not handler_class:
            raise DonationDiscoveryError(f"No IntentHandler class found in {handler_path}")
        
        # Check methods exist
        for method_donation in donation.method_donations:
            if not hasattr(handler_class, method_donation.method_name):
                error_msg = f"Method '{method_donation.method_name}' not found in handler class {handler_class.__name__}"
                raise DonationDiscoveryError(error_msg)
    
    async def _validate_spacy_patterns(self, donation: HandlerDonation):
        """Validate spaCy pattern syntax"""
        try:
            import spacy
            from spacy.matcher import Matcher
            from spacy.pipeline import EntityRuler
            
            nlp = spacy.blank("ru")  # Minimal model for validation
            matcher = Matcher(nlp.vocab)
            ruler = EntityRuler(nlp)
            
            for method_donation in donation.method_donations:
                # Validate token patterns
                for i, pattern in enumerate(method_donation.token_patterns):
                    try:
                        matcher.add(f"test_pattern_{i}", [pattern])
                    except Exception as e:
                        raise DonationDiscoveryError(f"Invalid token pattern in method '{method_donation.method_name}': {e}")
                
                # Validate slot patterns
                for slot_name, patterns in method_donation.slot_patterns.items():
                    for i, pattern in enumerate(patterns):
                        try:
                            ruler.add_patterns([{"label": slot_name, "pattern": pattern}])
                        except Exception as e:
                            raise DonationDiscoveryError(f"Invalid slot pattern '{slot_name}' in method '{method_donation.method_name}': {e}")
        
        except ImportError:
            if self.config.strict_mode:
                raise DonationDiscoveryError("spaCy not available for pattern validation")
            else:
                self.warnings.append("spaCy not available, skipping pattern validation")
    
    def _add_error(self, error_msg: str):
        """Add validation error"""
        self.validation_errors.append(error_msg)
        logger.error(error_msg)
    
    def _add_warning(self, warning_msg: str):
        """Add validation warning"""
        self.warnings.append(warning_msg)
        logger.warning(warning_msg)
    
    def _handle_validation_errors(self):
        """Handle validation errors based on configuration"""
        if self.config.strict_mode:
            error_summary = f"Donation validation failed with {len(self.validation_errors)} errors:\n"
            error_summary += "\n".join(f"  - {error}" for error in self.validation_errors)
            raise DonationDiscoveryError(error_summary)
        else:
            # Non-strict mode: log errors but continue
            for error in self.validation_errors:
                logger.error(f"Donation validation error (non-fatal): {error}")
```

#### C2. Integration with Handler Discovery

```python
class EnhancedHandlerManager:
    """Intent handler manager with JSON donation support"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.donation_loader = DonationLoader(
            DonationValidationConfig(**config.get('donation_validation', {}))
        )
        self.handlers: Dict[str, IntentHandler] = {}
        self.donations: Dict[str, HandlerDonation] = {}
    
    async def initialize(self) -> None:
        """Initialize handlers with JSON donation validation"""
        
        # Discover Python handler files
        handler_paths = self._discover_handler_files()
        
        # Load and validate JSON donations (FATAL on error)
        self.donations = await self.donation_loader.discover_and_load_donations(handler_paths)
        
        # Instantiate Python handlers
        self.handlers = await self._instantiate_handlers(handler_paths)
        
        # Validate handler-donation consistency
        await self._validate_handler_donation_consistency()
        
        logger.info(f"Initialized {len(self.handlers)} handlers with {sum(len(d.method_donations) for d in self.donations.values())} total methods")
    
    def _discover_handler_files(self) -> List[Path]:
        """Discover Python handler files"""
        handler_dir = Path("irene/intents/handlers")
        return list(handler_dir.glob("**/*.py"))
    
    async def _validate_handler_donation_consistency(self):
        """Validate that all handlers have donations and vice versa"""
        handler_names = set(self.handlers.keys())
        donation_names = set(self.donations.keys())
        
        # Check for handlers without donations
        missing_donations = handler_names - donation_names
        if missing_donations:
            raise DonationDiscoveryError(f"Handlers without donations: {missing_donations}")
        
        # Check for donations without handlers
        orphaned_donations = donation_names - handler_names
        if orphaned_donations:
            logger.warning(f"Donations without handlers (will be ignored): {orphaned_donations}")
    
    def get_donations_as_keyword_donations(self) -> List[KeywordDonation]:
        """Convert JSON donations to KeywordDonation objects for NLU"""
        keyword_donations = []
        
        for handler_name, donation in self.donations.items():
            for method_donation in donation.method_donations:
                # Build full intent name
                full_intent_name = f"{donation.handler_domain}.{method_donation.intent_suffix}"
                
                # Convert to KeywordDonation format
                # Convert parameter specs
                converted_params = []
                for param in method_donation.parameters + donation.global_parameters:
                    converted_params.append(ParameterSpec(
                        name=param.name,
                        type=ParameterType(param.type),
                        required=param.required,
                        default_value=param.default_value,
                        description=param.description,
                        choices=param.choices,
                        min_value=param.min_value,
                        max_value=param.max_value,
                        pattern=param.pattern,
                        extraction_patterns=param.extraction_patterns,
                        aliases=param.aliases
                    ))
                
                keyword_donation = KeywordDonation(
                    intent=full_intent_name,
                    phrases=method_donation.phrases,
                    lemmas=method_donation.lemmas,
                    parameters=converted_params,
                    token_patterns=method_donation.token_patterns,
                    slot_patterns=method_donation.slot_patterns,
                    examples=[{"text": ex.text, "parameters": ex.parameters} for ex in method_donation.examples],
                    boost=method_donation.boost
                )
                keyword_donations.append(keyword_donation)
        
        return keyword_donations
```

### D. Configuration Integration

Configuration for the donation system is integrated into the main system configuration schema (see Complete Configuration Schema section below).

## Parameter Extraction System

### A. Parameter Extractor Architecture

#### A1. JSON-Integrated Parameter Extractor

```python
class JSONBasedParameterExtractor:
    """Parameter extractor that uses JSON donation specifications"""
    
    def __init__(self):
        self.nlp = None
        self.parameter_specs: Dict[str, List[ParameterSpec]] = {}
        self.extraction_rules = {}
    
    async def initialize_from_json_donations(self, donations: Dict[str, HandlerDonation]):
        """Initialize parameter extraction from JSON donations"""
        import spacy
        from spacy.pipeline import EntityRuler
        
        self.nlp = spacy.load("ru_core_news_sm")
        
        # Build parameter specs from JSON donations
        for handler_name, donation in donations.items():
            for method_donation in donation.method_donations:
                full_intent_name = f"{donation.handler_domain}.{method_donation.intent_suffix}"
                
                # Combine method parameters with global parameters
                all_parameters = method_donation.parameters + donation.global_parameters
                self.parameter_specs[full_intent_name] = all_parameters
                
                # Add extraction patterns to spaCy
                for param in all_parameters:
                    for pattern in param.extraction_patterns:
                        if 'pattern' in pattern and 'label' in pattern:
                            self.nlp.get_pipe("entity_ruler").add_patterns([pattern])
    
    async def extract_parameters(self, intent: Intent, intent_name: str) -> Dict[str, Any]:
        """Extract parameters using JSON-defined specifications"""
        parameter_specs = self.parameter_specs.get(intent_name, [])
        if not parameter_specs:
            return {}
        
        doc = self.nlp(intent.raw_text)
        extracted_params = {}
        
        for param_spec in parameter_specs:
            value = await self._extract_single_parameter(doc, param_spec, intent)
            
            if value is not None:
                extracted_params[param_spec.name] = value
            elif param_spec.required and param_spec.default_value is None:
                raise ParameterExtractionError(f"Required parameter '{param_spec.name}' not found")
            elif param_spec.default_value is not None:
                extracted_params[param_spec.name] = param_spec.default_value
        
        return extracted_params
```

### B. Handler Execution Integration

#### B1. Simplified Handler Interface

```python
class IntentHandler(EntryPointMetadata, ABC):
    """Enhanced intent handler base class for JSON donation system"""
    
    def __init__(self):
        super().__init__()
        self.donation: Optional[HandlerDonation] = None
    
    def set_donation(self, donation: HandlerDonation):
        """Set the JSON donation for this handler"""
        self.donation = donation
    
    async def can_handle(self, intent: Intent) -> bool:
        """Check if handler can process intent using JSON donation"""
        if not self.donation:
            return False
        
        # Check if intent matches any method donation
        expected_domain = self.donation.handler_domain
        return intent.domain == expected_domain
    
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Route to appropriate method based on intent and JSON donation"""
        if not self.donation:
            return IntentResult(text="Handler not properly initialized", success=False)
        
        # Find matching method donation
        method_name = self._find_method_for_intent(intent)
        if not method_name:
            return IntentResult(text=f"No method found for intent {intent.name}", success=False)
        
        # Call the method
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            return await method(intent, context)
        else:
            return IntentResult(text=f"Method {method_name} not implemented", success=False)
    
    def _find_method_for_intent(self, intent: Intent) -> Optional[str]:
        """Find method name for intent using JSON donation"""
        expected_suffix = intent.name.split('.', 1)[1] if '.' in intent.name else intent.name
        
        for method_donation in self.donation.method_donations:
            if method_donation.intent_suffix == expected_suffix:
                return method_donation.method_name
        
        return None
```

#### B2. Example Handler Implementation

```python
class TimerIntentHandler(IntentHandler):
    """Timer handler using JSON donations - no hardcoded patterns!"""
    
    def __init__(self):
        super().__init__()
        self.active_timers: Dict[str, Dict[str, Any]] = {}
        self.timer_counter = 0
    
    # Method referenced in timer.json
    async def set_timer(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Set timer - parameters already extracted from JSON donation specs"""
        
        # Parameters extracted automatically from JSON donation
        duration = intent.entities.get('duration')  # Already validated as int
        unit = intent.entities.get('unit', 'minutes')  # Already validated as choice
        message = intent.entities.get('message', 'Таймер завершён!')  # Already validated as string
        
        if duration is None:
            return IntentResult(text="Duration not specified", success=False)
        
        # Convert to seconds and create timer
        duration_seconds = self._convert_to_seconds(duration, unit)
        timer_id = await self._create_timer(duration_seconds, message, context.session_id)
        
        return IntentResult(
            text=f"Таймер установлен на {duration} {unit}. Сообщение: {message}",
            metadata={"timer_id": timer_id}
        )
    
    # Method referenced in timer.json  
    async def cancel_timer(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Cancel timer - parameters extracted from JSON"""
        timer_id = intent.entities.get('timer_id')
        
        # Implementation details...
        return IntentResult(text="Таймер отменён")
```

## Cascading NLU Architecture

### A. Plugin Pipeline Architecture

#### A1. JSON-Aware NLU Orchestrator

```python
class NLUOrchestrator:
    """Cascading NLU with JSON donation integration"""
    
    def __init__(self, config: Dict[str, Any]):
        enabled_plugins = config.get('enabled_plugins', ['keyword_matcher'])
        
        self.plugins = []
        if 'keyword_matcher' in enabled_plugins:
            self.plugins.append(KeywordMatcherPlugin())
        if 'spacy_rules_sm' in enabled_plugins:
            self.plugins.append(SpaCyRuleBasedPlugin("sm"))
        if 'llm_nlu' in enabled_plugins:
            self.plugins.append(LLMNLUPlugin(config.get('llm_nlu', {})))
        if 'spacy_semantic_md' in enabled_plugins:
            self.plugins.append(SpaCySemanticPlugin("md"))
        
        self.plugins.append(ConversationFallbackPlugin())
    
    async def initialize_from_json_donations(self, donations: Dict[str, HandlerDonation]):
        """Initialize plugins from JSON donations"""
        # Convert JSON donations to KeywordDonation format
        keyword_donations = self._convert_json_to_keyword_donations(donations)
        
        # Initialize each plugin
        for plugin in self.plugins:
            if hasattr(plugin, '_initialize_from_donations'):
                await plugin._initialize_from_donations(keyword_donations)
    
    def _convert_json_to_keyword_donations(self, donations: Dict[str, HandlerDonation]) -> List[KeywordDonation]:
        """Convert JSON donations to KeywordDonation objects"""
        keyword_donations = []
        
        for handler_name, donation in donations.items():
            keyword_donations.extend(
                self._create_keyword_donations_for_handler(donation)
            )
        
        return keyword_donations
    
    def _create_keyword_donations_for_handler(self, donation: HandlerDonation) -> List[KeywordDonation]:
        """Create KeywordDonation objects for a single handler - reuses existing conversion logic"""
        # This method delegates to the same conversion logic used in EnhancedHandlerManager
        # to avoid duplication while maintaining the NLU orchestrator interface
        handler_manager = EnhancedHandlerManager({})
        handler_manager.donations = {donation.handler_domain: donation}
        return handler_manager.get_donations_as_keyword_donations()
```

### B. Stage-Specific Plugin Implementations

The existing plugin implementations (KeywordMatcherPlugin, SpaCyRuleBasedPlugin, SpaCySemanticPlugin) remain unchanged - they work with KeywordDonation objects regardless of whether those objects came from Python code or JSON files.

## Text Processing Integration

### A. JSON-Aware Text Processing Pipeline

```python
async def _process_text_pipeline_with_json(self, text: str, context: ConversationContext) -> Intent:
    """Enhanced text processing pipeline with JSON-based donations"""
    
    # Stage 1: Text preprocessing (unchanged)
    if self.text_processor and await self.text_processor.is_available():
        preprocessed_text = await self.text_processor.improve(text, context, stage="asr_output")
    else:
        preprocessed_text = text
    
    # Stage 2: NLU with JSON donations and parameter extraction
    intent = await self.enhanced_intent_recognizer.recognize_with_parameters(preprocessed_text, context)
    
    # Stage 3: Intent execution with JSON-aware routing
    result = await self.intent_orchestrator.execute_intent(intent, context)
    
    return result
```

## Context-Aware NLU Processing

### A. ClientId Integration Architecture

#### A1. Comprehensive Conversation Context

```python
@dataclass
class ConversationContext:
    """Comprehensive conversation context with client identification and metadata"""
    
    # Core identification
    session_id: str
    user_id: Optional[str] = None
    client_id: Optional[str] = None  # Room/client identifier
    
    # Client metadata for context-aware processing
    client_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Conversation state
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    current_intent_context: Optional[str] = None
    last_intent_timestamp: Optional[float] = None
    
    # Device and capability context
    available_devices: List[Dict[str, Any]] = field(default_factory=list)
    preferred_output_device: Optional[str] = None
    client_capabilities: Dict[str, bool] = field(default_factory=dict)
    
    # User preferences
    language: str = "ru"
    timezone: Optional[str] = None
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    # System context
    timestamp: float = field(default_factory=time.time)
    request_source: str = "unknown"  # "microphone", "web", "api", etc.
    
    def get_room_name(self) -> Optional[str]:
        """Get human-readable room name from client context"""
        if self.client_id:
            return self.client_metadata.get('room_name', self.client_id)
        return None
    
    def get_device_capabilities(self) -> List[Dict[str, Any]]:
        """Get list of devices available in this client context"""
        return self.client_metadata.get('available_devices', self.available_devices)
    
    def set_client_context(self, client_id: str, metadata: Dict[str, Any]):
        """Set client identification and metadata"""
        self.client_id = client_id
        self.client_metadata = metadata
        # Update available devices from metadata
        if 'available_devices' in metadata:
            self.available_devices = metadata['available_devices']
    
    def get_device_by_name(self, device_name: str) -> Optional[Dict[str, Any]]:
        """Find device by name using fuzzy matching"""
        devices = self.get_device_capabilities()
        
        # Exact match first
        for device in devices:
            if device.get('name', '').lower() == device_name.lower():
                return device
        
        # Fuzzy match fallback
        try:
            from rapidfuzz import fuzz, process
            device_names = [device.get('name', '') for device in devices]
            best_match = process.extractOne(device_name, device_names, scorer=fuzz.ratio)
            
            if best_match and best_match[1] > 70:  # 70% similarity threshold
                for device in devices:
                    if device.get('name', '') == best_match[0]:
                        return device
        except ImportError:
            pass  # Fallback to exact match only if rapidfuzz not available
        
        return None
    
    def add_to_history(self, user_text: str, response: str, intent: Optional[str] = None):
        """Add interaction to conversation history"""
        self.conversation_history.append({
            "timestamp": time.time(),
            "user_text": user_text,
            "response": response,
            "intent": intent,
            "client_id": self.client_id
        })
        
        # Keep only last 10 interactions to prevent memory bloat
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
    
    def get_recent_intents(self, limit: int = 3) -> List[str]:
        """Get recent intent names for context"""
        recent = []
        for interaction in reversed(self.conversation_history[-limit:]):
            if interaction.get('intent'):
                recent.append(interaction['intent'])
        return recent
    
    def has_capability(self, capability: str) -> bool:
        """Check if client has specific capability"""
        return self.client_capabilities.get(capability, False)
    
    def get_device_types(self) -> Set[str]:
        """Get set of device types available in this context"""
        devices = self.get_device_capabilities()
        return {device.get('type', 'unknown') for device in devices}
```

#### A2. Context-Aware NLU Processing

The comprehensive ConversationContext above integrates with NLU processing to provide context-aware entity resolution and intent disambiguation using client identification and device capabilities.

## Asset Management Integration

### A. spaCy Integration with Asset Management

spaCy providers use the standard asset management system instead of custom asset managers:

```python
class SpaCyRuleBasedPlugin:
    """spaCy plugin using standard asset management"""
    
    def __init__(self, model_name: str = "ru_core_news_sm"):
        self.model_name = model_name
        self.nlp = None
    
    def get_asset_config(self) -> Dict[str, Any]:
        """Standard asset configuration method"""
        return {
            "file_extension": ".whl",  # spaCy models are wheels
            "directory_name": "spacy",
            "cache_types": ["models", "runtime"],
            "model_urls": {
                "ru_core_news_sm": "https://github.com/explosion/spacy-models/releases/download/ru_core_news_sm-3.7.0/ru_core_news_sm-3.7.0-py3-none-any.whl",
                "ru_core_news_md": "https://github.com/explosion/spacy-models/releases/download/ru_core_news_md-3.7.0/ru_core_news_md-3.7.0-py3-none-any.whl",
                "ru_core_news_lg": "https://github.com/explosion/spacy-models/releases/download/ru_core_news_lg-3.7.0/ru_core_news_lg-3.7.0-py3-none-any.whl"
            },
            "credential_patterns": [],  # No API credentials needed
        }
    
    async def initialize(self, asset_manager):
        """Initialize using standard asset manager"""
        # Use existing asset management system
        model_path = await asset_manager.ensure_model_available(
            provider_name="spacy",
            model_name=self.model_name,
            asset_config=self.get_asset_config()
        )
        
        # Install and load model
        await self._install_spacy_model(model_path)
        
        import spacy
        self.nlp = spacy.load(self.model_name)
        
        logger.info(f"Initialized spaCy plugin with model {self.model_name}")
    
    async def _install_spacy_model(self, model_path: str):
        """Install spaCy model using pip"""
        import subprocess
        import sys
        
        cmd = [sys.executable, "-m", "pip", "install", model_path, "--no-deps", "--force-reinstall"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to install spaCy model: {result.stderr}")
    
    async def is_available(self) -> bool:
        """Check if plugin is available (model downloaded and loaded)"""
        return self.nlp is not None
```

## Hybrid Keyword Matching Architecture

### A. Enhanced Keyword Matcher with Fuzzy Matching

#### A1. Hybrid Matching Strategy

```python
from rapidfuzz import fuzz, process
from typing import List, Tuple, Optional, Dict
import re
import logging

logger = logging.getLogger(__name__)

class HybridKeywordMatcher:
    """Keyword matcher with patterns + Levenshtein fuzzy matching"""
    
    def __init__(self, config: Dict[str, Any]):
        # Pattern matching configuration
        self.exact_patterns: Dict[str, List[re.Pattern]] = {}
        self.pattern_confidence = config.get('pattern_confidence', 0.9)
        
        # Fuzzy matching configuration
        self.fuzzy_keywords: Dict[str, List[str]] = {}
        self.fuzzy_threshold = config.get('fuzzy_threshold', 0.8)
        self.fuzzy_confidence_base = config.get('fuzzy_confidence_base', 0.7)
        self.max_fuzzy_keywords_per_intent = config.get('max_fuzzy_keywords_per_intent', 50)
        
        # Performance configuration
        self.max_text_length_for_fuzzy = config.get('max_text_length_for_fuzzy', 100)
        self.cache_fuzzy_results = config.get('cache_fuzzy_results', True)
        self.fuzzy_cache: Dict[str, Dict[str, float]] = {}
        
        # Text normalization
        self.case_sensitive = config.get('case_sensitive', False)
    
    async def _initialize_from_donations(self, donations: List[KeywordDonation]):
        """Build both patterns and fuzzy keyword lists from JSON donations"""
        
        for donation in donations:
            # Build regex patterns (for exact matching)
            patterns = []
            for phrase in donation.phrases:
                # Create pattern variants
                exact_pattern = self._build_exact_pattern(phrase)
                flexible_pattern = self._build_flexible_pattern(phrase)
                partial_pattern = self._build_partial_pattern(phrase)
                
                patterns.extend([exact_pattern, flexible_pattern, partial_pattern])
            
            self.exact_patterns[donation.intent] = patterns
            
            # Build fuzzy keyword lists (for similarity matching)
            keywords = []
            
            # Add phrases as keywords
            keywords.extend(donation.phrases)
            
            # Add individual lemmas as keywords  
            keywords.extend(donation.lemmas)
            
            # Add word combinations from phrases
            for phrase in donation.phrases:
                words = phrase.split()
                if len(words) > 1:
                    # Add 2-word combinations
                    for i in range(len(words) - 1):
                        keywords.append(f"{words[i]} {words[i+1]}")
                    
                    # Add 3-word combinations for longer phrases
                    if len(words) > 2:
                        for i in range(len(words) - 2):
                            keywords.append(f"{words[i]} {words[i+1]} {words[i+2]}")
            
            # Limit keywords for performance
            if len(keywords) > self.max_fuzzy_keywords_per_intent:
                # Sort by length and keep most relevant
                keywords = sorted(keywords, key=len, reverse=True)[:self.max_fuzzy_keywords_per_intent]
            
            self.fuzzy_keywords[donation.intent] = keywords
            
            logger.debug(f"Initialized {donation.intent}: {len(patterns)} patterns, {len(keywords)} fuzzy keywords")
    
    async def recognize(self, text: str, context: ConversationContext) -> Optional[Intent]:
        """Hybrid recognition: patterns first, then fuzzy matching"""
        
        # Skip fuzzy matching for very long texts (performance)
        use_fuzzy = len(text) <= self.max_text_length_for_fuzzy
        
        # Strategy 1: Exact pattern matching (fastest, highest confidence)
        pattern_result = await self._pattern_matching(text, context)
        if pattern_result:
            return pattern_result
        
        # Strategy 2: Fuzzy keyword matching (slower, lower confidence)
        if use_fuzzy:
            fuzzy_result = await self._fuzzy_matching(text, context)
            if fuzzy_result:
                return fuzzy_result
        
        return None
    
    async def _pattern_matching(self, text: str, context: ConversationContext) -> Optional[Intent]:
        """Fast regex pattern matching with multiple variants"""
        normalized_text = self._normalize_text(text)
        
        best_match = None
        best_confidence = 0.0
        
        for intent_name, patterns in self.exact_patterns.items():
            for i, pattern in enumerate(patterns):
                if pattern.search(normalized_text):
                    # Different confidence based on pattern type
                    pattern_type_confidence = self._get_pattern_type_confidence(i)
                    confidence = self.pattern_confidence * pattern_type_confidence
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = (intent_name, pattern, pattern_type_confidence)
        
        if best_match:
            intent_name, matched_pattern, pattern_confidence = best_match
            return Intent(
                name=intent_name,
                confidence=best_confidence,
                raw_text=text,
                session_id=context.session_id,
                metadata={
                    "method": "pattern_match", 
                    "matched_pattern": matched_pattern.pattern,
                    "pattern_confidence": pattern_confidence
                }
            )
        
        return None
    
    def _get_pattern_type_confidence(self, pattern_index: int) -> float:
        """Get confidence multiplier based on pattern type"""
        # Assuming 3 patterns per phrase: exact, flexible, partial
        pattern_type = pattern_index % 3
        if pattern_type == 0:  # Exact match
            return 1.0
        elif pattern_type == 1:  # Flexible order
            return 0.9
        else:  # Partial match
            return 0.8
    
    async def _fuzzy_matching(self, text: str, context: ConversationContext) -> Optional[Intent]:
        """Fuzzy Levenshtein-based matching with caching"""
        normalized_text = self._normalize_text(text)
        text_words = normalized_text.split()
        
        # Check cache first
        cache_key = normalized_text
        if self.cache_fuzzy_results and cache_key in self.fuzzy_cache:
            cached_results = self.fuzzy_cache[cache_key]
            best_intent = max(cached_results.items(), key=lambda x: x[1])
            if best_intent[1] >= self.fuzzy_threshold:
                return self._create_fuzzy_intent(best_intent[0], best_intent[1], text, context, cached=True)
        
        best_match = None
        best_score = 0.0
        intent_scores = {}
        
        for intent_name, keywords in self.fuzzy_keywords.items():
            intent_score = self._calculate_intent_fuzzy_score(text_words, keywords, normalized_text)
            intent_scores[intent_name] = intent_score
            
            if intent_score > best_score and intent_score >= self.fuzzy_threshold:
                best_score = intent_score
                best_match = intent_name
        
        # Cache results
        if self.cache_fuzzy_results:
            self.fuzzy_cache[cache_key] = intent_scores
            # Limit cache size
            if len(self.fuzzy_cache) > 1000:
                # Remove oldest entries
                cache_keys = list(self.fuzzy_cache.keys())
                for key in cache_keys[:100]:
                    del self.fuzzy_cache[key]
        
        if best_match:
            return self._create_fuzzy_intent(best_match, best_score, text, context, cached=False)
        
        return None
    
    def _create_fuzzy_intent(self, intent_name: str, score: float, text: str, 
                           context: ConversationContext, cached: bool) -> Intent:
        """Create Intent object for fuzzy match"""
        confidence = self.fuzzy_confidence_base * score
        return Intent(
            name=intent_name,
            confidence=confidence,
            raw_text=text,
            session_id=context.session_id,
            metadata={
                "method": "fuzzy_match", 
                "fuzzy_score": score,
                "matched_keywords": self._get_matched_keywords(text.split(), self.fuzzy_keywords[intent_name]),
                "cached": cached
            }
        )
    
    def _calculate_intent_fuzzy_score(self, text_words: List[str], keywords: List[str], full_text: str) -> float:
        """Calculate fuzzy matching score for an intent using multiple strategies"""
        
        # Strategy 1: Full text similarity to each keyword
        keyword_scores = []
        for keyword in keywords:
            # Use rapidfuzz for fast Levenshtein calculation
            similarity = fuzz.ratio(full_text.lower(), keyword.lower()) / 100.0
            keyword_scores.append(similarity)
        
        # Strategy 2: Word-level matching with partial ratio
        word_match_scores = []
        for word in text_words:
            if len(word) > 2:  # Skip very short words
                # Find best matching keyword for this word
                best_match = process.extractOne(
                    word.lower(), 
                    [k.lower() for k in keywords],
                    scorer=fuzz.partial_ratio
                )
                if best_match and best_match[1] > 70:  # 70% similarity threshold
                    word_match_scores.append(best_match[1] / 100.0)
        
        # Strategy 3: Token set ratio for better word order handling
        token_set_scores = []
        for keyword in keywords:
            token_similarity = fuzz.token_set_ratio(full_text.lower(), keyword.lower()) / 100.0
            token_set_scores.append(token_similarity)
        
        # Combine scores with weights
        max_keyword_score = max(keyword_scores) if keyword_scores else 0.0
        avg_word_score = sum(word_match_scores) / len(word_match_scores) if word_match_scores else 0.0
        max_token_score = max(token_set_scores) if token_set_scores else 0.0
        
        # Weighted combination: emphasize keyword matches, boost with word and token matches
        final_score = (max_keyword_score * 0.5) + (avg_word_score * 0.3) + (max_token_score * 0.2)
        
        return final_score
    
    def _get_matched_keywords(self, text_words: List[str], keywords: List[str]) -> List[str]:
        """Get keywords that contributed to the match for debugging"""
        matched = []
        full_text = " ".join(text_words)
        
        for keyword in keywords:
            # Check different similarity measures
            ratio_similarity = fuzz.ratio(full_text.lower(), keyword.lower())
            partial_similarity = fuzz.partial_ratio(full_text.lower(), keyword.lower())
            token_similarity = fuzz.token_set_ratio(full_text.lower(), keyword.lower())
            
            best_similarity = max(ratio_similarity, partial_similarity, token_similarity)
            
            if best_similarity > 70:  # 70% threshold for "contributing to match"
                matched.append(f"{keyword} ({best_similarity}%)")
        
        return matched[:3]  # Return top 3 matches
    
    def _build_exact_pattern(self, phrase: str) -> re.Pattern:
        """Build exact regex pattern for phrase"""
        escaped_phrase = re.escape(phrase)
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile(rf"\b{escaped_phrase}\b", flags)
    
    def _build_flexible_pattern(self, phrase: str) -> re.Pattern:
        """Build flexible pattern allowing any word order"""
        words = phrase.split()
        if len(words) <= 1:
            return self._build_exact_pattern(phrase)
        
        # Create pattern that matches all words in any order
        escaped_words = [re.escape(word) for word in words]
        pattern_parts = []
        for word in escaped_words:
            pattern_parts.append(f"(?=.*\\b{word}\\b)")
        
        pattern = "".join(pattern_parts) + ".*"
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile(pattern, flags)
    
    def _build_partial_pattern(self, phrase: str) -> re.Pattern:
        """Build partial pattern matching subset of words"""
        words = phrase.split()
        if len(words) <= 2:
            return self._build_flexible_pattern(phrase)
        
        # Require at least 70% of words to match
        min_words = max(1, int(len(words) * 0.7))
        escaped_words = [re.escape(word) for word in words]
        
        # Create pattern with word alternation
        word_patterns = [f"\\b{word}\\b" for word in escaped_words]
        pattern = f"(?:{'|'.join(word_patterns)})" + f"{{{min_words},}}"
        
        flags = 0 if self.case_sensitive else re.IGNORECASE
        return re.compile(pattern, flags)
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching"""
        if not self.case_sensitive:
            text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        return text
```

#### A2. Performance Configuration

Performance configuration is included in the Complete Configuration Schema section below.

## Configuration

### A. Complete Configuration Schema

```toml
[nlu]
enabled_plugins = ["keyword_matcher", "spacy_rules_sm", "spacy_semantic_md"]
confidence_threshold = 0.7
fallback_intent = "conversation.general"
donation_collection_enabled = true
parameter_extraction_enabled = true

[nlu.keyword_matcher]
enabled = true
confidence_threshold = 0.8
pattern_confidence = 0.9
fuzzy_threshold = 0.8
fuzzy_confidence_base = 0.7
max_fuzzy_keywords_per_intent = 50
max_text_length_for_fuzzy = 100
cache_fuzzy_results = true
case_sensitive = false

[nlu.spacy_rules_sm]
enabled = true
model_name = "ru_core_news_sm"
confidence_threshold = 0.7
morphology_expansion = true
auto_download = true

[nlu.spacy_semantic_md]
enabled = true
model_name = "ru_core_news_md"
confidence_threshold = 0.55
auto_download = true

[nlu.parameter_extraction]
enabled = true
strict_validation = true
type_conversion = true

[nlu.context_processing]
enabled = true
client_context_resolution = true
device_disambiguation = true
room_inference = true

[assets.spacy]
auto_download_missing = true
verify_installation = true
cleanup_on_startup = false
model_cache_expiry = 86400

[intents]
enabled_handlers = ["timer", "greetings", "weather"]

[intents.donations]
validation_mode = "strict"
schema_version = "1.0"
fail_on_missing_json = true
validate_method_existence = true
validate_spacy_patterns = true
reload_on_change = false

[intents.donations.error_handling]
fatal_on_missing_json = true
fatal_on_invalid_json = true
fatal_on_schema_validation = true
development_mode = false
```

## Performance Characteristics

### A. Resource Usage

#### A1. Memory Usage by Configuration

| Configuration | RAM Usage | Models Loaded | Use Case |
|---------------|-----------|---------------|----------|
| Keyword Only | ~20 MB | None | Ultra-constrained devices |
| Rules + Keywords | ~80 MB | ru_core_news_sm | Edge devices, IoT |
| Full Pipeline | ~180 MB | sm + md | Servers, desktops |
| Maximum | ~900 MB | sm + md + lg | Research, high-accuracy |

#### A2. Processing Speed by Stage

| Stage | Typical Latency | Success Rate | Memory |
|-------|-----------------|--------------|---------|
| JSON Loading (startup) | ~10-50ms | 100% | ~5 MB |
| Pattern Matching | ~0.5 ms | 70-75% | ~15 MB |
| Fuzzy Matching | ~2-5 ms | 15-20% | +5 MB |
| spaCy Rules (sm) | ~5-10 ms | 8-12% | +60 MB |
| spaCy Semantic (md) | ~15-25 ms | 2-3% | +120 MB |
| Parameter Extraction | ~2-5 ms | 95% | included |
| Context Processing | ~1-3 ms | 100% | ~1 MB |
| Conversation Fallback | ~1 ms | 100% | - |

### B. Fuzzy Matching Performance

- **Cache Hit Rate**: ~85% for common phrases
- **rapidfuzz Performance**: ~100K comparisons/second
- **Memory Overhead**: ~5MB for 1000 intents with 50 keywords each
- **Accuracy Improvement**: +15-20% recognition rate over pattern-only

## Implementation Strategy

### A. Implementation Phases

#### A1. Phase 1: Context-Aware Foundation
1. Enhance ConversationContext with client identification
2. Implement ContextAwareNLU processor
3. Add context-based entity resolution
4. Test with simple room/device scenarios

#### A2. Phase 2: Asset Management Integration  
1. Integrate spaCy providers with existing asset management system
2. Add standard asset configuration methods to spaCy plugins
3. Test model download and installation via standard asset manager
4. Verify spaCy model loading and caching

#### A3. Phase 3: Hybrid Keyword Matching
1. Implement HybridKeywordMatcher with patterns and fuzzy matching
2. Add rapidfuzz dependency and performance optimizations
3. Add caching and performance monitoring
4. Benchmark against pattern-only approach

#### A4. Phase 4: Integration and Optimization
1. Integrate all components with JSON donation system
2. Add comprehensive configuration options
3. Performance tuning and monitoring
4. Production testing and validation

This enhanced architecture provides context-aware NLU processing, integration with the existing asset management system for spaCy models, and robust hybrid keyword matching while maintaining the MECE structure and comprehensive JSON donation system. The design eliminates duplication by reusing existing asset management patterns and consolidating context processing into a single comprehensive class.

## Related Documentation

### MQTT Intent Handlers
For MQTT-based home automation and IoT device control, see:
- **[MQTT Intent Handler Architecture](intent_mqtt.md)** - Comprehensive guide for MQTT handlers with dynamic method generation, device discovery, and large-scale command management (deferred feature) 