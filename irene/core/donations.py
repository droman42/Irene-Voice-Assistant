"""
JSON Donation System - Pydantic Models and Validation

Core models for the intent donation system implementing keyword-first NLU architecture
with cascading spaCy semantic fallbacks and integrated parameter extraction.
"""

import logging
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Union
from enum import Enum

logger = logging.getLogger(__name__)


class ParameterType(str, Enum):
    """Types of parameters that can be extracted from user input"""
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
    
    # NEW: Handler-level pattern matching fields for can_handle logic
    intent_name_patterns: Optional[List[str]] = Field(default_factory=list, description="Intent name patterns for can_handle")
    action_patterns: Optional[List[str]] = Field(default_factory=list, description="Action patterns for can_handle")
    domain_patterns: Optional[List[str]] = Field(default_factory=list, description="Domain patterns for can_handle")
    fallback_conditions: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Fallback conditions for can_handle")
    
    # Additional recognition patterns (for NLU providers)
    additional_recognition_patterns: Optional[List[str]] = Field(default_factory=list, description="Additional patterns for NLU recognition")
    language_detection: Optional[Dict[str, List[str]]] = Field(default_factory=dict, description="Language detection patterns")
    train_keywords: Optional[List[str]] = Field(default_factory=list, description="Train-specific keywords")
    
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


class KeywordDonation(BaseModel):
    """Converted donation format for keyword matching providers"""
    intent: str = Field(..., description="Full intent name (domain.suffix)")
    phrases: List[str] = Field(..., min_items=1, description="Trigger phrases")
    lemmas: List[str] = Field(default_factory=list, description="Key lemmas")
    parameters: List[ParameterSpec] = Field(default_factory=list, description="Parameter specifications")
    token_patterns: List[List[Dict[str, Any]]] = Field(default_factory=list, description="spaCy token patterns")
    slot_patterns: Dict[str, List[List[Dict[str, Any]]]] = Field(default_factory=dict, description="spaCy slot patterns")
    examples: List[Dict[str, Any]] = Field(default_factory=list, description="Training examples")
    boost: float = Field(1.0, ge=0.0, le=10.0, description="Pattern strength multiplier")


class DonationValidationConfig(BaseModel):
    """Configuration for donation validation"""
    strict_mode: bool = Field(True, description="Fail on any validation error")
    warn_unused_patterns: bool = Field(True, description="Warn about unused patterns")
    validate_method_existence: bool = Field(True, description="Validate method exists in Python handler")
    validate_spacy_patterns: bool = Field(True, description="Validate spaCy pattern syntax")
    validate_json_schema: bool = Field(True, description="Validate JSON files against JSON Schema")
    max_methods_per_handler: int = Field(1000, description="Maximum methods per handler")
    max_phrases_per_method: int = Field(100, description="Maximum phrases per method")


class DonationDiscoveryError(Exception):
    """Raised when donation discovery or validation fails"""
    pass


class ParameterExtractionError(Exception):
    """Raised when parameter extraction fails"""
    pass
