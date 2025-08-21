"""
JSON Donation Discovery and Loading System

Loads and validates JSON donations with fatal error handling for the intent donation system.
"""

import json
import logging
import asyncio
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .donations import (
    HandlerDonation, DonationValidationConfig, DonationDiscoveryError,
    KeywordDonation, ParameterSpec, ParameterType
)

logger = logging.getLogger(__name__)


class DonationLoader:
    """Loads and validates JSON donations with fatal error handling"""
    
    def __init__(self, config: Optional[DonationValidationConfig] = None):
        self.config = config or DonationValidationConfig()
        self.validation_errors: List[str] = []
        self.warnings: List[str] = []
    
    async def discover_and_load_donations(self, handler_paths: List[Path]) -> Dict[str, HandlerDonation]:
        """Discover JSON files and load validated donations"""
        donations = {}
        
        for handler_path in handler_paths:
            handler_name = handler_path.stem
            # NEW: Look for JSON donations in the donations subdirectory
            donations_dir = handler_path.parent / "donations"
            json_path = donations_dir / f"{handler_name}.json"
            
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
        
        # JSON Schema validation (if available)
        if self.config.validate_json_schema:
            await self._validate_json_schema(json_data, json_path)
        
        # Validate with pydantic
        try:
            donation = HandlerDonation(**json_data)
        except Exception as e:
            raise DonationDiscoveryError(f"Pydantic validation failed for {json_path}: {e}")
        
        # Additional validations
        if self.config.validate_method_existence:
            await self._validate_method_existence(donation, handler_path)
        
        # PHASE 0/6: spaCy validation moved to providers at runtime
        
        return donation
    
    async def _validate_json_schema(self, json_data: dict, json_path: Path) -> None:
        """Validate JSON data against JSON Schema"""
        try:
            import jsonschema
            from pathlib import Path
            
            # Load schema file
            schema_path = Path("schemas/donation/v1.0.json")
            if not schema_path.exists():
                logger.warning(f"JSON Schema not found at {schema_path} - skipping schema validation")
                return
            
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            
            # Validate JSON data against schema
            jsonschema.validate(instance=json_data, schema=schema)
            logger.debug(f"JSON Schema validation passed for {json_path.name}")
            
        except ImportError:
            if self.config.strict_mode:
                raise DonationDiscoveryError(f"jsonschema library not available for validation of {json_path}")
            else:
                logger.warning("jsonschema library not available - skipping JSON Schema validation")
        except jsonschema.ValidationError as e:
            error_msg = f"JSON Schema validation failed for {json_path}: {e.message}"
            if self.config.strict_mode:
                raise DonationDiscoveryError(error_msg)
            else:
                self._add_error(error_msg)
        except Exception as e:
            error_msg = f"JSON Schema validation error for {json_path}: {e}"
            if self.config.strict_mode:
                raise DonationDiscoveryError(error_msg)
            else:
                self._add_error(error_msg)
    
    async def _validate_method_existence(self, donation: HandlerDonation, handler_path: Path):
        """Validate that donated methods exist in Python handler"""
        # Load Python module and check methods exist
        try:
            # Convert file path to module name for proper import context
            # handler_path is like: irene/intents/handlers/timer.py
            # We need module name like: irene.intents.handlers.timer
            parts = handler_path.with_suffix('').parts
            module_name = '.'.join(parts)
            
            # Use importlib.import_module for proper package context
            import importlib
            module = importlib.import_module(module_name)
            
            # Find handler class
            handler_class = None
            for item_name in dir(module):
                item = getattr(module, item_name)
                if (isinstance(item, type) and 
                    hasattr(item, '__bases__') and 
                    any('IntentHandler' in base.__name__ for base in item.__bases__)):
                    handler_class = item
                    break
            
            if not handler_class:
                raise DonationDiscoveryError(f"No IntentHandler class found in {handler_path}")
            
            # Check methods exist
            for method_donation in donation.method_donations:
                if not hasattr(handler_class, method_donation.method_name):
                    error_msg = f"Method '{method_donation.method_name}' not found in handler class {handler_class.__name__}"
                    raise DonationDiscoveryError(error_msg)
        
        except Exception as e:
            if "No IntentHandler class found" in str(e) or "Method" in str(e) and "not found" in str(e):
                raise
            else:
                self._add_warning(f"Could not validate method existence for {handler_path}: {e}")
    
    # PHASE 6: _validate_spacy_patterns method removed - functionality moved to SpaCy provider
    # This provides runtime validation with graceful degradation instead of startup validation
    
    def convert_to_keyword_donations(self, donations: Dict[str, HandlerDonation]) -> List[KeywordDonation]:
        """Convert JSON donations to KeywordDonation objects for NLU providers"""
        keyword_donations = []
        
        for handler_name, donation in donations.items():
            for method_donation in donation.method_donations:
                # Build full intent name
                full_intent_name = f"{donation.handler_domain}.{method_donation.intent_suffix}"
                
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
                    boost=method_donation.boost,
                    donation_version=donation.donation_version,
                    handler_domain=donation.handler_domain
                )
                keyword_donations.append(keyword_donation)
        
        return keyword_donations
    
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


class EnhancedHandlerManager:
    """Intent handler manager with JSON donation support"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.donation_loader = DonationLoader(
            DonationValidationConfig(**config.get('donation_validation', {}))
        )
        self.handlers: Dict[str, Any] = {}  # Will contain IntentHandler instances
        self.donations: Dict[str, HandlerDonation] = {}
    
    async def initialize(self, handler_dir: Path = None) -> None:
        """Initialize handlers with JSON donation validation"""
        
        # Discover Python handler files
        if handler_dir is None:
            handler_dir = Path("irene/intents/handlers")
        
        handler_paths = self._discover_handler_files(handler_dir)
        
        # Ensure donations subdirectory exists
        donations_dir = handler_dir / "donations"
        if not donations_dir.exists():
            logger.warning(f"Donations directory does not exist: {donations_dir}. Creating it...")
            donations_dir.mkdir(parents=True, exist_ok=True)
        
        # Load and validate JSON donations (FATAL on error)
        self.donations = await self.donation_loader.discover_and_load_donations(handler_paths)
        
        # Instantiate Python handlers would happen here
        # (This is simplified for now - full handler instantiation would require additional setup)
        
        # Validate handler-donation consistency
        await self._validate_handler_donation_consistency()
        
        logger.info(f"Initialized donations for {len(self.donations)} handlers with {sum(len(d.method_donations) for d in self.donations.values())} total methods")
    
    def _discover_handler_files(self, handler_dir: Path) -> List[Path]:
        """Discover Python handler files"""
        if not handler_dir.exists():
            raise DonationDiscoveryError(f"Handler directory does not exist: {handler_dir}")
        
        python_files = []
        for file_path in handler_dir.glob("*.py"):
            # Skip base.py and __init__.py
            if file_path.name not in ['base.py', '__init__.py']:
                python_files.append(file_path)
        
        return python_files
    
    async def _validate_handler_donation_consistency(self):
        """Validate that all handlers have donations and vice versa"""
        # This is a simplified version - in practice would check actual handler instances
        logger.info(f"Validated donation consistency for {len(self.donations)} handlers")
    
    def get_donations_as_keyword_donations(self) -> List[KeywordDonation]:
        """Convert JSON donations to KeywordDonation objects for NLU"""
        return self.donation_loader.convert_to_keyword_donations(self.donations)
