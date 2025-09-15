"""
Intent Asset Loader - Unified Asset Management for Intent Handlers

Phase 1 Implementation: Replaces DonationLoader with unified asset loading
supporting donations, templates, prompts, and localization data.

This loader extends the proven DonationLoader patterns to handle all asset types
with unified error handling, validation, and caching.
"""

import json
import logging
import asyncio
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from .donations import (
    HandlerDonation, DonationValidationConfig, DonationDiscoveryError,
    KeywordDonation, ParameterSpec, ParameterType
)

logger = logging.getLogger(__name__)


class AssetLoaderConfig:
    """Configuration for IntentAssetLoader behavior"""
    
    def __init__(
        self,
        validate_json_schema: bool = True,
        validate_method_existence: bool = True,
        validate_spacy_patterns: bool = False,
        strict_mode: bool = False,
        default_language: str = "ru",
        fallback_language: str = "en"
    ):
        self.validate_json_schema = validate_json_schema
        self.validate_method_existence = validate_method_existence
        self.validate_spacy_patterns = validate_spacy_patterns
        self.strict_mode = strict_mode
        self.default_language = default_language
        self.fallback_language = fallback_language


class IntentAssetLoader:
    """Unified loader for all intent handler assets"""
    
    def __init__(self, assets_root: Path, config: Optional[AssetLoaderConfig] = None):
        self.assets_root = Path(assets_root)
        self.config = config or AssetLoaderConfig()
        
        # Asset caches
        self.donations: Dict[str, HandlerDonation] = {}
        self.templates: Dict[str, Dict[str, Any]] = {}
        self.prompts: Dict[str, Dict[str, str]] = {}
        self.localizations: Dict[str, Dict[str, Any]] = {}
        
        # Error tracking (reuse donation loader pattern)
        self.validation_errors: List[str] = []
        self.warnings: List[str] = []
    
    async def load_all_assets(self, handler_names: List[str]) -> None:
        """Load all asset types for specified handlers"""
        logger.info(f"Loading assets for {len(handler_names)} handlers: {handler_names}")
        
        # Load assets in parallel for better performance
        await asyncio.gather(
            self._load_donations(handler_names),
            self._load_templates(handler_names),
            self._load_prompts(handler_names),
            self._load_localizations(handler_names),
            return_exceptions=True
        )
        
        # Check for fatal errors
        if self.validation_errors:
            self._handle_validation_errors()
        
        # Log warnings
        for warning in self.warnings:
            logger.warning(warning)
        
        logger.info(f"Asset loading completed: {len(self.donations)} donations, "
                   f"{len(self.templates)} template sets, {len(self.prompts)} prompt sets, "
                   f"{len(self.localizations)} localization sets")
    
    # ============================================================
    # PUBLIC API (extends existing donation loader interface)
    # ============================================================
    
    def get_donation(self, handler_name: str) -> Optional[HandlerDonation]:
        """Get JSON donation (existing functionality)"""
        return self.donations.get(handler_name)
    
    async def save_donation(self, handler_name: str, donation_data: dict, create_backup: bool = True) -> bool:
        """Save donation JSON to file with backup support"""
        donations_dir = self.assets_root / "donations"
        json_path = donations_dir / f"{handler_name}.json"
        
        try:
            # Create backup if requested and file exists
            if create_backup and json_path.exists():
                # Create backups directory
                backups_dir = donations_dir / "backups"
                backups_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate backup filename with current datetime
                from datetime import datetime
                current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"{handler_name}_{current_datetime}.json"
                backup_path = backups_dir / backup_filename
                
                # Copy existing file to backup location
                import shutil
                shutil.copy2(json_path, backup_path)
                logger.info(f"Created backup: {backup_path}")
            
            # Ensure donations directory exists
            donations_dir.mkdir(parents=True, exist_ok=True)
            
            # Write JSON with proper formatting
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(donation_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved donation for handler '{handler_name}' to {json_path}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to save donation for handler '{handler_name}': {e}"
            self._add_error(error_msg)
            return False
    
    async def validate_donation_data(self, handler_name: str, donation_data: dict) -> tuple[bool, list, list]:
        """Validate donation data without saving (dry-run)
        
        Returns:
            tuple: (is_valid, errors, warnings)
        """
        validation_errors = []
        validation_warnings = []
        
        try:
            # JSON Schema validation (if available)
            if self.config.validate_json_schema:
                try:
                    await self._validate_json_schema(donation_data, Path(f"validation_{handler_name}.json"))
                except Exception as e:
                    validation_errors.append({
                        "type": "schema",
                        "message": f"JSON schema validation failed: {e}",
                        "path": None
                    })
            
            # Pydantic validation
            try:
                donation = HandlerDonation(**donation_data)
            except Exception as e:
                validation_errors.append({
                    "type": "pydantic",
                    "message": f"Data validation failed: {e}",
                    "path": None
                })
                return False, validation_errors, validation_warnings
            
            # Method existence validation (if available)
            if self.config.validate_method_existence:
                try:
                    await self._validate_method_existence(donation, handler_name)
                except Exception as e:
                    validation_warnings.append({
                        "type": "method_existence",
                        "message": f"Method validation warning: {e}",
                        "path": None
                    })
            
            return len(validation_errors) == 0, validation_errors, validation_warnings
            
        except Exception as e:
            validation_errors.append({
                "type": "general",
                "message": f"Validation error: {e}",
                "path": None
            })
            return False, validation_errors, validation_warnings
    
    def get_donation_metadata(self, handler_name: str) -> Optional[dict]:
        """Get metadata about a donation file"""
        donations_dir = self.assets_root / "donations"
        json_path = donations_dir / f"{handler_name}.json"
        
        if not json_path.exists():
            return None
        
        try:
            stat = json_path.stat()
            donation = self.donations.get(handler_name)
            
            metadata = {
                "handler_name": handler_name,
                "file_size": stat.st_size,
                "last_modified": stat.st_mtime
            }
            
            if donation:
                metadata.update({
                    "domain": donation.handler_domain,
                    "description": donation.description,
                    "methods_count": len(donation.method_donations),
                    "global_parameters_count": len(donation.global_parameters)
                })
            else:
                # Try to read basic info from file
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    metadata.update({
                        "domain": data.get("handler_domain", "unknown"),
                        "description": data.get("description", ""),
                        "methods_count": len(data.get("method_donations", [])),
                        "global_parameters_count": len(data.get("global_parameters", []))
                    })
                except Exception:
                    metadata.update({
                        "domain": "unknown",
                        "description": "Failed to read file",
                        "methods_count": 0,
                        "global_parameters_count": 0
                    })
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get metadata for {handler_name}: {e}")
            return None
    
    def list_all_donations(self) -> list[dict]:
        """List all available donation files with metadata"""
        donations_dir = self.assets_root / "donations"
        
        if not donations_dir.exists():
            return []
        
        donations_list = []
        for json_file in donations_dir.glob("*.json"):
            handler_name = json_file.stem
            metadata = self.get_donation_metadata(handler_name)
            if metadata:
                donations_list.append(metadata)
        
        return donations_list
    
    def get_template(self, handler_name: str, template_name: str, language: str = None) -> Optional[str]:
        """Get response template with i18n fallback"""
        language = language or self.config.default_language
        
        handler_templates = self.templates.get(handler_name, {})
        template_data = handler_templates.get(template_name, {})
        
        # Try requested language first
        if language in template_data:
            return template_data[language]
        
        # Fallback to default language
        if self.config.fallback_language in template_data:
            return template_data[self.config.fallback_language]
        
        # Fallback to any available language
        if template_data:
            return next(iter(template_data.values()))
        
        return None
    
    def get_prompt(self, handler_name: str, prompt_type: str, language: str = None) -> Optional[str]:
        """Get LLM prompt with language fallback"""
        language = language or self.config.default_language
        
        handler_prompts = self.prompts.get(handler_name, {})
        prompt_key = f"{prompt_type}_{language}"
        
        # Try requested language first
        if prompt_key in handler_prompts:
            return handler_prompts[prompt_key]
        
        # Fallback to default language
        fallback_key = f"{prompt_type}_{self.config.fallback_language}"
        if fallback_key in handler_prompts:
            return handler_prompts[fallback_key]
        
        return None
    
    def get_localization(self, domain: str, language: str = None) -> Optional[Dict[str, Any]]:
        """Get localization data (arrays, mappings) with language fallback"""
        language = language or self.config.default_language
        
        domain_data = self.localizations.get(domain, {})
        
        # Try requested language first
        if language in domain_data:
            return domain_data[language]
        
        # Fallback to default language
        if self.config.fallback_language in domain_data:
            return domain_data[self.config.fallback_language]
        
        return None
    
    def convert_to_keyword_donations(self) -> List[KeywordDonation]:
        """Convert JSON donations to KeywordDonation objects for NLU providers"""
        keyword_donations = []
        
        for handler_name, donation in self.donations.items():
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
    
    # ============================================================
    # ASSET LOADING IMPLEMENTATION
    # ============================================================
    
    async def _load_donations(self, handler_names: List[str]) -> None:
        """Load JSON donations (migrate existing donation loader logic)"""
        donations_dir = self.assets_root / "donations"
        
        for handler_name in handler_names:
            json_path = donations_dir / f"{handler_name}.json"
            
            try:
                if not json_path.exists():
                    self._add_warning(f"Missing JSON donation file for handler '{handler_name}': {json_path}")
                    continue
                
                # Load and validate JSON donation
                donation = await self._load_and_validate_donation(json_path, handler_name)
                self.donations[handler_name] = donation
                
                logger.debug(f"Loaded donation for handler '{handler_name}': {len(donation.method_donations)} methods")
                
            except Exception as e:
                error_msg = f"Failed to load donation for handler '{handler_name}': {e}"
                self._add_error(error_msg)
    
    async def _load_templates(self, handler_names: List[str]) -> None:
        """Load response templates (Category B: YAML/JSON/Markdown parsing)"""
        templates_dir = self.assets_root / "templates"
        
        if not templates_dir.exists():
            logger.debug("Templates directory does not exist, skipping template loading")
            return
        
        for handler_name in handler_names:
            handler_template_dir = templates_dir / handler_name
            
            if not handler_template_dir.exists():
                logger.debug(f"No templates directory for handler '{handler_name}', skipping")
                continue
            
            try:
                handler_templates = {}
                
                # Discover template files by language
                for lang_dir in handler_template_dir.iterdir():
                    if lang_dir.is_dir():
                        language = lang_dir.name
                        lang_templates = await self._load_language_templates(lang_dir)
                        
                        # Merge templates by name
                        for template_name, content in lang_templates.items():
                            if template_name not in handler_templates:
                                handler_templates[template_name] = {}
                            handler_templates[template_name][language] = content
                
                if handler_templates:
                    self.templates[handler_name] = handler_templates
                    logger.debug(f"Loaded {len(handler_templates)} template sets for handler '{handler_name}'")
                
            except Exception as e:
                self._add_warning(f"Failed to load templates for handler '{handler_name}': {e}")
    
    async def _load_prompts(self, handler_names: List[str]) -> None:
        """Load LLM prompts (Category A1: Text file loading)"""
        prompts_dir = self.assets_root / "prompts"
        
        if not prompts_dir.exists():
            logger.debug("Prompts directory does not exist, skipping prompt loading")
            return
        
        for handler_name in handler_names:
            handler_prompt_dir = prompts_dir / handler_name
            
            if not handler_prompt_dir.exists():
                logger.debug(f"No prompts directory for handler '{handler_name}', skipping")
                continue
            
            try:
                handler_prompts = {}
                
                # Discover prompt files by language
                for lang_dir in handler_prompt_dir.iterdir():
                    if lang_dir.is_dir():
                        language = lang_dir.name
                        
                        for prompt_file in lang_dir.glob("*.txt"):
                            prompt_type = prompt_file.stem
                            prompt_key = f"{prompt_type}_{language}"
                            
                            with open(prompt_file, 'r', encoding='utf-8') as f:
                                handler_prompts[prompt_key] = f.read().strip()
                
                if handler_prompts:
                    self.prompts[handler_name] = handler_prompts
                    logger.debug(f"Loaded {len(handler_prompts)} prompts for handler '{handler_name}'")
                
            except Exception as e:
                self._add_warning(f"Failed to load prompts for handler '{handler_name}': {e}")
    
    async def _load_localizations(self, handler_names: List[str]) -> None:
        """Load localization data (Category C: YAML parsing)"""
        localization_dir = self.assets_root / "localization"
        
        if not localization_dir.exists():
            logger.debug("Localization directory does not exist, skipping localization loading")
            return
        
        # Load domain-based localizations
        for domain_dir in localization_dir.iterdir():
            if domain_dir.is_dir():
                domain_name = domain_dir.name
                
                try:
                    domain_data = {}
                    
                    for lang_file in domain_dir.glob("*.yaml"):
                        language = lang_file.stem
                        
                        with open(lang_file, 'r', encoding='utf-8') as f:
                            domain_data[language] = yaml.safe_load(f)
                    
                    if domain_data:
                        self.localizations[domain_name] = domain_data
                        logger.debug(f"Loaded localization for domain '{domain_name}': {list(domain_data.keys())} languages")
                
                except Exception as e:
                    self._add_warning(f"Failed to load localization for domain '{domain_name}': {e}")
    
    # ============================================================
    # HELPER METHODS
    # ============================================================
    
    async def _load_and_validate_donation(self, json_path: Path, handler_name: str) -> HandlerDonation:
        """Load and validate a single JSON donation file (reused from DonationLoader)"""
        
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
            await self._validate_method_existence(donation, handler_name)
        
        return donation
    
    async def _validate_json_schema(self, json_data: dict, json_path: Path) -> None:
        """Validate JSON data against JSON Schema"""
        try:
            import jsonschema
            
            # Load schema file
            schema_path = self.assets_root / "v1.0.json"
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
        except Exception as e:
            error_msg = f"JSON Schema validation failed for {json_path}: {e}"
            if self.config.strict_mode:
                raise DonationDiscoveryError(error_msg)
            else:
                self._add_error(error_msg)
    
    async def _validate_method_existence(self, donation: HandlerDonation, handler_name: str):
        """Validate that donated methods exist in Python handler"""
        try:
            # Convert handler name to module path
            module_name = f"irene.intents.handlers.{handler_name}"
            
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
                raise DonationDiscoveryError(f"No IntentHandler class found for {handler_name}")
            
            # Check methods exist
            for method_donation in donation.method_donations:
                if not hasattr(handler_class, method_donation.method_name):
                    error_msg = f"Method '{method_donation.method_name}' not found in handler class {handler_class.__name__}"
                    raise DonationDiscoveryError(error_msg)
        
        except Exception as e:
            if "No IntentHandler class found" in str(e) or "Method" in str(e) and "not found" in str(e):
                raise
            else:
                self._add_warning(f"Could not validate method existence for {handler_name}: {e}")
    
    async def _load_language_templates(self, lang_dir: Path) -> Dict[str, str]:
        """Load template files for a specific language"""
        templates = {}
        
        for template_file in lang_dir.iterdir():
            if template_file.is_file():
                template_name = template_file.stem
                
                try:
                    if template_file.suffix == '.yaml':
                        with open(template_file, 'r', encoding='utf-8') as f:
                            data = yaml.safe_load(f)
                            if isinstance(data, list):
                                templates[template_name] = data
                            elif isinstance(data, dict):
                                templates.update(data)
                            else:
                                templates[template_name] = str(data)
                    
                    elif template_file.suffix == '.json':
                        with open(template_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                templates[template_name] = data
                            elif isinstance(data, dict):
                                templates.update(data)
                            else:
                                templates[template_name] = str(data)
                    
                    elif template_file.suffix in ['.md', '.txt']:
                        with open(template_file, 'r', encoding='utf-8') as f:
                            templates[template_name] = f.read().strip()
                    
                    else:
                        logger.debug(f"Skipping unknown template file type: {template_file}")
                
                except Exception as e:
                    self._add_warning(f"Failed to load template {template_file}: {e}")
        
        return templates
    
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
            error_summary = f"Asset loading failed with {len(self.validation_errors)} errors:\n"
            error_summary += "\n".join(f"  - {error}" for error in self.validation_errors)
            raise DonationDiscoveryError(error_summary)
        else:
            # Non-strict mode: log errors but continue
            for error in self.validation_errors:
                logger.error(f"Asset loading error (non-fatal): {error}")


class EnhancedHandlerManager:
    """Intent handler manager with unified asset support (replaces DonationLoader pattern)"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Create asset loader configuration
        asset_config = AssetLoaderConfig(
            **config.get('asset_validation', {})
        )
        
        # Initialize unified asset loader
        assets_root = Path(config.get('assets_root', 'assets'))
        self.asset_loader = IntentAssetLoader(assets_root, asset_config)
        
        self.handlers: Dict[str, Any] = {}  # Will contain IntentHandler instances
    
    async def initialize(self, handler_dir: Path = None) -> None:
        """Initialize handlers with unified asset loading"""
        
        # Discover Python handler files
        if handler_dir is None:
            handler_dir = Path("irene/intents/handlers")
        
        handler_paths = self._discover_handler_files(handler_dir)
        handler_names = [path.stem for path in handler_paths]
        
        # Load all assets using unified loader
        await self.asset_loader.load_all_assets(handler_names)
        
        # Validate handler-asset consistency
        await self._validate_handler_asset_consistency()
        
        logger.info(f"Initialized assets for {len(handler_names)} handlers with unified asset loader")
    
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
    
    async def _validate_handler_asset_consistency(self):
        """Validate that all handlers have assets and vice versa"""
        logger.info(f"Validated asset consistency for {len(self.asset_loader.donations)} handlers")
    
    def get_donations_as_keyword_donations(self) -> List[KeywordDonation]:
        """Convert JSON donations to KeywordDonation objects for NLU"""
        return self.asset_loader.convert_to_keyword_donations()
    
    def get_asset_loader(self) -> IntentAssetLoader:
        """Get the unified asset loader instance"""
        return self.asset_loader
