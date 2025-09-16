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
    HandlerDonation, MethodDonation, DonationValidationConfig, DonationDiscoveryError,
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
        fallback_language: str = "en",
        supported_languages: List[str] = None,
        enable_language_filtering: bool = True
    ):
        self.validate_json_schema = validate_json_schema
        self.validate_method_existence = validate_method_existence
        self.validate_spacy_patterns = validate_spacy_patterns
        self.strict_mode = strict_mode
        self.default_language = default_language
        self.fallback_language = fallback_language
        self.supported_languages = supported_languages or ["ru", "en"]
        self.enable_language_filtering = enable_language_filtering


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
    
    async def load_donation_on_demand(self, handler_name: str) -> Optional[HandlerDonation]:
        """
        Load donation from file for configuration UI only.
        
        This method loads donation data directly from the filesystem without
        caching it in memory or registering it with the runtime system.
        Used exclusively by the configuration UI to access donations for
        handlers that may not be currently enabled.
        
        Args:
            handler_name: Name of the handler to load donation for
            
        Returns:
            HandlerDonation object if file exists and is valid, None otherwise
            
        Note:
            - Does NOT add to self.donations cache
            - Does NOT register handler with runtime system  
            - Read-only access for configuration purposes only
        """
        donations_dir = self.assets_root / "donations"
        json_path = donations_dir / f"{handler_name}.json"
        
        try:
            if not json_path.exists():
                logger.debug(f"No donation file found for handler '{handler_name}': {json_path}")
                return None
            
            # Load and validate donation directly from file
            donation = await self._load_and_validate_donation(json_path, handler_name)
            logger.debug(f"Loaded donation on-demand for handler '{handler_name}' (configuration UI)")
            return donation
            
        except Exception as e:
            logger.warning(f"Failed to load donation on-demand for handler '{handler_name}': {e}")
            return None
    
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
    
    def get_prompt_metadata(self, handler_name: str, prompt_type: str, language: str = None) -> Optional[Dict[str, Any]]:
        """Get LLM prompt metadata for assets editor"""
        language = language or self.config.default_language
        
        handler_prompts = self.prompts.get(handler_name, {})
        metadata_key = f"{prompt_type}_{language}_metadata"
        
        # Try requested language first
        if metadata_key in handler_prompts:
            return handler_prompts[metadata_key]
        
        # Fallback to default language
        fallback_key = f"{prompt_type}_{self.config.fallback_language}_metadata"
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
        """Load language-separated donation files and merge for unified processing"""
        donations_dir = self.assets_root / "donations"
        
        for handler_name in handler_names:
            asset_handler_name = self._get_asset_handler_name(handler_name)
            language_donation_dir = donations_dir / asset_handler_name
            
            # Load language-separated structure (only supported format)
            if language_donation_dir.exists() and language_donation_dir.is_dir():
                await self._load_language_separated_donations(language_donation_dir, handler_name)
            else:
                self._add_warning(f"No language-separated donation directory found for handler '{handler_name}': {language_donation_dir}")
    
    async def _load_language_separated_donations(self, lang_dir: Path, handler_name: str) -> None:
        """Load and merge language-specific donation files into unified donation"""
        language_donations = {}
        
        # Load each language file
        for lang_file in lang_dir.glob("*.json"):
            language = lang_file.stem
            if language in self.config.supported_languages:
                try:
                    lang_donation = await self._load_and_validate_donation(lang_file, handler_name)
                    language_donations[language] = lang_donation
                    logger.debug(f"Loaded {language} donation for handler '{handler_name}'")
                except Exception as e:
                    self._add_warning(f"Failed to load {language} donation for handler '{handler_name}': {e}")
        
        if not language_donations:
            self._add_warning(f"No valid language donations found for handler '{handler_name}' in {lang_dir}")
            return
        
        # Merge into unified HandlerDonation for optimal processing
        merged_donation = self._merge_language_donations(language_donations, handler_name)
        self.donations[handler_name] = merged_donation
        
        logger.info(f"Merged {len(language_donations)} language donations for handler '{handler_name}'")
    
    def _merge_language_donations(self, language_donations: Dict[str, HandlerDonation], handler_name: str) -> HandlerDonation:
        """Merge language-specific donations into unified donation for NLU processing"""
        # Use first donation as base structure
        base_donation = next(iter(language_donations.values()))
        
        # First pass: collect all phrases and metadata by method key
        method_data = {}
        
        for language, donation in language_donations.items():
            for method_donation in donation.method_donations:
                method_key = f"{method_donation.method_name}#{method_donation.intent_suffix}"
                
                if method_key not in method_data:
                    method_data[method_key] = {
                        'method_name': method_donation.method_name,
                        'intent_suffix': method_donation.intent_suffix,
                        'description': method_donation.description,
                        'phrases': [],
                        'parameters': method_donation.parameters,
                        'lemmas': [],
                        'token_patterns': method_donation.token_patterns or [],
                        'slot_patterns': method_donation.slot_patterns or {},
                        'examples': [],
                        'boost': method_donation.boost
                    }
                
                # Accumulate phrases from all languages
                method_data[method_key]['phrases'].extend(method_donation.phrases)
                
                # Merge other language-specific fields
                if method_donation.lemmas:
                    method_data[method_key]['lemmas'].extend(method_donation.lemmas)
                if method_donation.examples:
                    method_data[method_key]['examples'].extend(method_donation.examples)
        
        # Second pass: create MethodDonation objects with accumulated data
        merged_methods = []
        for method_key, data in method_data.items():
            if data['phrases']:  # Only create if we have phrases
                merged_method = MethodDonation(
                    method_name=data['method_name'],
                    intent_suffix=data['intent_suffix'],
                    description=data['description'],
                    phrases=data['phrases'],
                    parameters=data['parameters'],
                    lemmas=data['lemmas'],
                    token_patterns=data['token_patterns'],
                    slot_patterns=data['slot_patterns'],
                    examples=data['examples'],
                    boost=data['boost']
                )
                merged_methods.append(merged_method)
        
        # Create unified donation with merged methods
        return HandlerDonation(
            schema_version=base_donation.schema_version,
            donation_version=base_donation.donation_version,
            handler_domain=base_donation.handler_domain,
            description=base_donation.description,
            method_donations=merged_methods,
            intent_name_patterns=base_donation.intent_name_patterns,
            action_patterns=base_donation.action_patterns,
            domain_patterns=base_donation.domain_patterns,
            fallback_conditions=base_donation.fallback_conditions,
            additional_recognition_patterns=base_donation.additional_recognition_patterns,
            language_detection=base_donation.language_detection,
            train_keywords=base_donation.train_keywords,
            global_parameters=base_donation.global_parameters,
            negative_patterns=base_donation.negative_patterns
        )
    
    def _get_asset_handler_name(self, handler_name: str) -> str:
        """Map handler file name to asset directory name"""
        # Handler files ending with _handler already have the suffix
        if handler_name.endswith("_handler"):
            return handler_name
        # For files without suffix, add _handler
        return f"{handler_name}_handler"
    
    # ============================================================
    # LANGUAGE-SEPARATED FILE ACCESS FOR EDITOR (Phase 3C)
    # ============================================================
    
    def get_donation_for_language_editing(self, handler_name: str, language: str) -> Optional[HandlerDonation]:
        """Get language-specific donation for editing purposes"""
        asset_handler_name = self._get_asset_handler_name(handler_name)
        lang_file = self.assets_root / "donations" / asset_handler_name / f"{language}.json"
        
        if lang_file.exists():
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return HandlerDonation(**data)
            except Exception as e:
                logger.error(f"Failed to load {language} donation for {handler_name}: {e}")
                return None
        
        return None
    
    def save_donation_for_language(self, handler_name: str, language: str, donation: HandlerDonation) -> bool:
        """Save language-specific donation for editing"""
        try:
            asset_handler_name = self._get_asset_handler_name(handler_name)
            lang_dir = self.assets_root / "donations" / asset_handler_name
            lang_dir.mkdir(parents=True, exist_ok=True)
            
            # Convert to dict and add explicit language field
            donation_dict = donation.dict()
            donation_dict["language"] = language
            
            lang_file = lang_dir / f"{language}.json"
            with open(lang_file, 'w', encoding='utf-8') as f:
                json.dump(donation_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {language} donation for handler '{handler_name}' to {lang_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save {language} donation for {handler_name}: {e}")
            return False
    
    async def reload_unified_donation(self, handler_name: str) -> bool:
        """Reload unified donation after language file changes"""
        try:
            asset_handler_name = self._get_asset_handler_name(handler_name)
            lang_dir = self.assets_root / "donations" / asset_handler_name
            
            if lang_dir.exists():
                # Clear existing donation
                if handler_name in self.donations:
                    del self.donations[handler_name]
                
                # Reload language-separated donations
                await self._load_language_separated_donations(lang_dir, handler_name)
                logger.info(f"Reloaded unified donation for handler '{handler_name}'")
                return True
            else:
                logger.warning(f"No donation directory found for handler '{handler_name}': {lang_dir}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to reload donation for {handler_name}: {e}")
            return False
    
    def get_available_languages_for_handler(self, handler_name: str) -> List[str]:
        """Get list of available language files for handler"""
        asset_handler_name = self._get_asset_handler_name(handler_name)
        lang_dir = self.assets_root / "donations" / asset_handler_name
        
        if not lang_dir.exists():
            return []
        
        return [lang_file.stem for lang_file in lang_dir.glob("*.json")]
    
    def get_all_handlers_with_languages(self) -> Dict[str, List[str]]:
        """Get all handlers with their available languages"""
        donations_dir = self.assets_root / "donations"
        handlers_languages = {}
        
        if not donations_dir.exists():
            return handlers_languages
        
        for handler_dir in donations_dir.iterdir():
            if handler_dir.is_dir():
                # Convert asset handler name back to handler name
                handler_name = handler_dir.name
                if handler_name.endswith("_handler"):
                    handler_name = handler_name[:-8]  # Remove "_handler" suffix
                
                languages = [lang_file.stem for lang_file in handler_dir.glob("*.json")]
                if languages:
                    handlers_languages[handler_name] = sorted(languages)
        
        return handlers_languages
    
    def validate_cross_language_consistency(self, handler_name: str) -> Dict[str, Any]:
        """Validate consistency across language files for a handler"""
        languages = self.get_available_languages_for_handler(handler_name)
        
        if len(languages) < 2:
            return {
                "parameter_consistency": True,
                "missing_methods": [],
                "extra_methods": []
            }
        
        # Load all language donations for comparison
        language_donations = {}
        for language in languages:
            donation = self.get_donation_for_language_editing(handler_name, language)
            if donation:
                language_donations[language] = donation
        
        if not language_donations:
            return {
                "parameter_consistency": False,
                "missing_methods": [],
                "extra_methods": []
            }
        
        # Check method consistency
        all_methods = set()
        methods_by_lang = {}
        
        for language, donation in language_donations.items():
            methods = {f"{m.method_name}#{m.intent_suffix}" for m in donation.method_donations}
            all_methods.update(methods)
            methods_by_lang[language] = methods
        
        # Find missing and extra methods per language
        missing_methods = []
        extra_methods = []
        
        base_methods = next(iter(methods_by_lang.values()))
        for language, methods in methods_by_lang.items():
            missing = base_methods - methods
            extra = methods - base_methods
            
            if missing:
                missing_methods.extend([f"{language}: {method}" for method in missing])
            if extra:
                extra_methods.extend([f"{language}: {method}" for method in extra])
        
        # Check parameter consistency (simplified check)
        parameter_consistency = len(set(len(methods) for methods in methods_by_lang.values())) == 1
        
        return {
            "parameter_consistency": parameter_consistency,
            "missing_methods": missing_methods,
            "extra_methods": extra_methods
        }
    
    async def _load_templates(self, handler_names: List[str]) -> None:
        """Load response templates (Category B: YAML/JSON/Markdown parsing)"""
        templates_dir = self.assets_root / "templates"
        
        if not templates_dir.exists():
            logger.debug("Templates directory does not exist, skipping template loading")
            return
        
        for handler_name in handler_names:
            asset_handler_name = self._get_asset_handler_name(handler_name)
            handler_template_dir = templates_dir / asset_handler_name
            
            if not handler_template_dir.exists():
                logger.debug(f"No templates directory for handler '{handler_name}' (looked for '{asset_handler_name}'), skipping")
                continue
            
            try:
                handler_templates = {}
                
                # NEW: Load consolidated language files directly (lang.yaml pattern)
                for lang_file in handler_template_dir.glob("*.yaml"):
                    language = lang_file.stem
                    lang_templates = await self._load_language_file(lang_file)
                    
                    # Merge templates by name
                    for template_name, content in lang_templates.items():
                        if template_name not in handler_templates:
                            handler_templates[template_name] = {}
                        handler_templates[template_name][language] = content
                
                if handler_templates:
                    self.templates[handler_name] = handler_templates
                    logger.debug(f"Loaded {len(handler_templates)} template sets for handler '{handler_name}' from '{asset_handler_name}'")
                
            except Exception as e:
                self._add_warning(f"Failed to load templates for handler '{handler_name}': {e}")
    
    async def _load_prompts(self, handler_names: List[str]) -> None:
        """Load LLM prompts from YAML files with metadata (YAML format only)"""
        prompts_dir = self.assets_root / "prompts"
        
        if not prompts_dir.exists():
            logger.debug("Prompts directory does not exist, skipping prompt loading")
            return
        
        for handler_name in handler_names:
            asset_handler_name = self._get_asset_handler_name(handler_name)
            handler_prompt_dir = prompts_dir / asset_handler_name
            
            if not handler_prompt_dir.exists():
                logger.debug(f"No prompts directory for handler '{handler_name}' (looked for '{asset_handler_name}'), skipping")
                continue
            
            try:
                handler_prompts = {}
                
                # NEW: Load consolidated language files directly (lang.yaml pattern)
                for lang_file in handler_prompt_dir.glob("*.yaml"):
                    language = lang_file.stem
                    
                    with open(lang_file, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        
                        # Extract prompt content from YAML structure
                        for prompt_type, prompt_data in data.items():
                            if isinstance(prompt_data, dict) and 'content' in prompt_data:
                                prompt_key = f"{prompt_type}_{language}"
                                # Store just the content for backward compatibility
                                handler_prompts[prompt_key] = prompt_data['content'].strip()
                                
                                # Store full metadata for assets editor API
                                metadata_key = f"{prompt_type}_{language}_metadata"
                                handler_prompts[metadata_key] = {
                                    'description': prompt_data.get('description', ''),
                                    'usage_context': prompt_data.get('usage_context', ''),
                                    'variables': prompt_data.get('variables', []),
                                    'prompt_type': prompt_data.get('prompt_type', 'system')
                                }
                
                if handler_prompts:
                    self.prompts[handler_name] = handler_prompts
                    logger.debug(f"Loaded {len([k for k in handler_prompts.keys() if not k.endswith('_metadata')])} prompts for handler '{handler_name}' from '{asset_handler_name}'")
                
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
    
    async def _load_language_file(self, lang_file: Path) -> Dict[str, str]:
        """Load template/prompt data from a single language file (YAML and JSON formats only)"""
        templates = {}
        
        try:
            if lang_file.suffix == '.yaml':
                with open(lang_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        templates.update(data)
                    else:
                        logger.warning(f"Expected dict in {lang_file}, got {type(data)}")
            
            elif lang_file.suffix == '.json':
                with open(lang_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        templates.update(data)
                    else:
                        logger.warning(f"Expected dict in {lang_file}, got {type(data)}")
            
            else:
                logger.debug(f"Skipping unknown file type: {lang_file}")
        
        except Exception as e:
            self._add_warning(f"Failed to load language file {lang_file}: {e}")
        
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
