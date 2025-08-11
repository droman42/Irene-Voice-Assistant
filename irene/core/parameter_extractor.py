"""
JSON-Based Parameter Extraction System

Parameter extractor that uses JSON donation specifications for type-safe parameter 
validation and conversion in the intent donation system.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta

from .donations import ParameterSpec, ParameterType, ParameterExtractionError, HandlerDonation
from ..intents.models import Intent

logger = logging.getLogger(__name__)


class JSONBasedParameterExtractor:
    """Parameter extractor that uses JSON donation specifications"""
    
    def __init__(self):
        self.nlp = None
        self.parameter_specs: Dict[str, List[ParameterSpec]] = {}
        self.extraction_rules = {}
    
    async def initialize_from_json_donations(self, donations: Dict[str, HandlerDonation]):
        """Initialize parameter extraction from JSON donations"""
        try:
            # Try to load spaCy for advanced extraction
            import spacy  # type: ignore
            self.nlp = spacy.load("ru_core_news_sm")
            logger.info("Initialized parameter extractor with spaCy support")
        except ImportError:
            logger.warning("spaCy not available, using basic extraction only")
        except OSError:
            logger.warning("spaCy model not available, using basic extraction only")
        
        # Build parameter specs from JSON donations
        for handler_name, donation in donations.items():
            for method_donation in donation.method_donations:
                full_intent_name = f"{donation.handler_domain}.{method_donation.intent_suffix}"
                
                # Combine method parameters with global parameters
                all_parameters = method_donation.parameters + donation.global_parameters
                self.parameter_specs[full_intent_name] = all_parameters
                
                logger.debug(f"Registered {len(all_parameters)} parameters for intent {full_intent_name}")
    
    async def extract_parameters(self, intent: Intent, intent_name: str) -> Dict[str, Any]:
        """Extract parameters using JSON-defined specifications"""
        parameter_specs = self.parameter_specs.get(intent_name, [])
        if not parameter_specs:
            return {}
        
        # Process text with spaCy if available
        doc = None
        if self.nlp:
            try:
                doc = self.nlp(intent.raw_text)
            except Exception as e:
                logger.warning(f"spaCy processing failed: {e}")
        
        extracted_params = {}
        
        for param_spec in parameter_specs:
            try:
                value = await self._extract_single_parameter(intent.raw_text, doc, param_spec, intent)
                
                if value is not None:
                    # Type conversion and validation
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
    
    async def _extract_single_parameter(self, text: str, doc: Any, param_spec: ParameterSpec, intent: Intent) -> Any:
        """Extract a single parameter using various extraction strategies"""
        
        # Strategy 1: spaCy pattern matching
        if doc and param_spec.extraction_patterns:
            spacy_result = await self._extract_with_spacy_patterns(doc, param_spec)
            if spacy_result is not None:
                return spacy_result
        
        # Strategy 2: Regex pattern matching
        if param_spec.pattern:
            regex_result = await self._extract_with_regex(text, param_spec)
            if regex_result is not None:
                return regex_result
        
        # Strategy 3: Type-specific extraction
        type_result = await self._extract_by_type(text, param_spec)
        if type_result is not None:
            return type_result
        
        # Strategy 4: Alias matching
        alias_result = await self._extract_by_aliases(text, param_spec)
        if alias_result is not None:
            return alias_result
        
        return None
    
    async def _extract_with_spacy_patterns(self, doc: Any, param_spec: ParameterSpec) -> Any:
        """Extract parameter using spaCy extraction patterns"""
        try:
            for pattern_config in param_spec.extraction_patterns:
                if 'pattern' in pattern_config:
                    # Simple entity matching for now
                    label = pattern_config.get('label', param_spec.name.upper())
                    
                    # Check for entities with matching label
                    for ent in doc.ents:
                        if ent.label_ == label:
                            return ent.text
                    
                    # Check for pattern matching in text
                    pattern = pattern_config['pattern']
                    if isinstance(pattern, list) and len(pattern) > 0:
                        # Simple pattern matching - look for specific tokens
                        for token in doc:
                            if self._token_matches_pattern(token, pattern[0]):
                                return token.text
        except Exception as e:
            logger.debug(f"spaCy pattern extraction failed for {param_spec.name}: {e}")
        
        return None
    
    def _token_matches_pattern(self, token: Any, pattern: Dict[str, Any]) -> bool:
        """Check if a token matches a spaCy pattern"""
        try:
            for key, value in pattern.items():
                if key == "LIKE_NUM" and value:
                    return token.like_num
                elif key == "IS_ALPHA" and value:
                    return token.is_alpha
                elif key == "LEMMA":
                    if isinstance(value, dict) and "IN" in value:
                        return token.lemma_ in value["IN"]
                    else:
                        return token.lemma_ == value
                elif key == "TEXT":
                    if isinstance(value, dict) and "REGEX" in value:
                        return bool(re.search(value["REGEX"], token.text, re.IGNORECASE))
                    else:
                        return token.text == value
                elif key == "LOWER":
                    if isinstance(value, dict) and "IN" in value:
                        return token.lower_ in value["IN"]
                    else:
                        return token.lower_ == value
        except Exception:
            pass
        return False
    
    async def _extract_with_regex(self, text: str, param_spec: ParameterSpec) -> Any:
        """Extract parameter using regex pattern"""
        try:
            pattern = param_spec.pattern
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Return first group if exists, otherwise full match
                return match.group(1) if match.groups() else match.group(0)
        except Exception as e:
            logger.debug(f"Regex extraction failed for {param_spec.name}: {e}")
        
        return None
    
    async def _extract_by_type(self, text: str, param_spec: ParameterSpec) -> Any:
        """Extract parameter using type-specific patterns"""
        text_lower = text.lower()
        
        if param_spec.type == ParameterType.INTEGER:
            # Look for numbers
            numbers = re.findall(r'\d+', text)
            if numbers:
                return int(numbers[0])
        
        elif param_spec.type == ParameterType.FLOAT:
            # Look for decimal numbers
            numbers = re.findall(r'\d+\.?\d*', text)
            if numbers:
                return float(numbers[0])
        
        elif param_spec.type == ParameterType.BOOLEAN:
            # Look for boolean indicators
            true_values = ['да', 'yes', 'true', '1', 'включи', 'enable']
            false_values = ['нет', 'no', 'false', '0', 'выключи', 'disable']
            
            for true_val in true_values:
                if true_val in text_lower:
                    return True
            for false_val in false_values:
                if false_val in text_lower:
                    return False
        
        elif param_spec.type == ParameterType.CHOICE:
            # Look for valid choices
            if param_spec.choices:
                for choice in param_spec.choices:
                    if choice.lower() in text_lower:
                        return choice
        
        elif param_spec.type == ParameterType.DURATION:
            # Extract duration (minutes, seconds, hours)
            duration_patterns = [
                (r'(\d+)\s*(секунд|сек)', 'seconds'),
                (r'(\d+)\s*(минут|мин)', 'minutes'),
                (r'(\d+)\s*(час|часа|часов)', 'hours'),
                (r'(\d+)\s*(day|days|дней|день)', 'days')
            ]
            
            for pattern, unit in duration_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    value = int(match.group(1))
                    # Convert to seconds
                    if unit == 'minutes':
                        return value * 60
                    elif unit == 'hours':
                        return value * 3600
                    elif unit == 'days':
                        return value * 86400
                    else:  # seconds
                        return value
        
        elif param_spec.type == ParameterType.STRING:
            # For string, look for quoted text or after keywords
            quoted_match = re.search(r'["\']([^"\']+)["\']', text)
            if quoted_match:
                return quoted_match.group(1)
            
            # Look for text after common keywords
            keywords = ['сообщение', 'message', 'text', 'название', 'name']
            for keyword in keywords:
                pattern = rf'{keyword}[:\s]+([^\s]+(?:\s+[^\s]+)*?)(?:\s|$)'
                match = re.search(pattern, text_lower)
                if match:
                    return match.group(1).strip()
        
        return None
    
    async def _extract_by_aliases(self, text: str, param_spec: ParameterSpec) -> Any:
        """Extract parameter by looking for aliases"""
        if not param_spec.aliases:
            return None
        
        text_lower = text.lower()
        for alias in param_spec.aliases:
            if alias.lower() in text_lower:
                # Found alias, try to extract value after it
                pattern = rf'{re.escape(alias.lower())}\s*[:=]?\s*([^\s]+)'
                match = re.search(pattern, text_lower)
                if match:
                    return match.group(1)
        
        return None
    
    def _convert_and_validate_parameter(self, value: Any, param_spec: ParameterSpec) -> Any:
        """Convert and validate parameter according to its specification"""
        try:
            # Type conversion
            if param_spec.type == ParameterType.INTEGER:
                converted = int(value)
            elif param_spec.type == ParameterType.FLOAT:
                converted = float(value)
            elif param_spec.type == ParameterType.BOOLEAN:
                if isinstance(value, bool):
                    converted = value
                else:
                    converted = str(value).lower() in ['true', '1', 'да', 'yes']
            elif param_spec.type == ParameterType.STRING:
                converted = str(value)
            else:
                converted = value
            
            # Validation
            if param_spec.type in [ParameterType.INTEGER, ParameterType.FLOAT]:
                if param_spec.min_value is not None and converted < param_spec.min_value:
                    raise ValueError(f"Value {converted} below minimum {param_spec.min_value}")
                if param_spec.max_value is not None and converted > param_spec.max_value:
                    raise ValueError(f"Value {converted} above maximum {param_spec.max_value}")
            
            if param_spec.type == ParameterType.CHOICE:
                if param_spec.choices and converted not in param_spec.choices:
                    raise ValueError(f"Value {converted} not in valid choices {param_spec.choices}")
            
            return converted
            
        except Exception as e:
            raise ParameterExtractionError(f"Parameter conversion/validation failed for {param_spec.name}: {e}")
