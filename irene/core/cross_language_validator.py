"""
Cross-Language Validation System for Intent Donations

Phase 4 Implementation: Cross-language validation and synchronization tools
for language-separated donation files while maintaining optimal unified processing.

This module provides:
- Parameter consistency validation across language files
- Method completeness checking across languages
- Translation suggestion tools
- Cross-language synchronization utilities
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

from .donations import HandlerDonation, MethodDonation

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    """Report for parameter consistency validation"""
    handler_name: str
    languages_checked: List[str] 
    parameter_consistency: bool
    missing_parameters: List[str]  # Format: "language: method_name.parameter_name"
    extra_parameters: List[str]    # Format: "language: method_name.parameter_name"
    type_mismatches: List[str]     # Format: "method_name.parameter_name: lang1(type1) vs lang2(type2)"
    warnings: List[str]
    timestamp: float


@dataclass
class CompletenessReport:
    """Report for method completeness validation"""
    handler_name: str
    languages_checked: List[str]
    method_completeness: bool
    missing_methods: List[str]     # Format: "language: method_name#intent_suffix"
    extra_methods: List[str]       # Format: "language: method_name#intent_suffix"
    all_methods: Set[str]          # All unique method keys across languages
    method_counts_by_language: Dict[str, int]
    warnings: List[str]
    timestamp: float


@dataclass
class TranslationSuggestions:
    """Suggestions for missing translations"""
    handler_name: str
    source_language: str
    target_language: str
    missing_phrases: List[Dict[str, Any]]  # {method_key, phrases, examples}
    missing_methods: List[str]             # Method keys missing in target language
    confidence_scores: Dict[str, float]    # Confidence in suggestions
    timestamp: float


class CrossLanguageValidator:
    """Cross-language validation and synchronization for donation files"""
    
    def __init__(self, assets_root: Path, asset_loader=None):
        self.assets_root = Path(assets_root)
        self.asset_loader = asset_loader
        
        # Language detection helpers
        self.russian_indicators = {'а', 'е', 'и', 'о', 'у', 'ы', 'э', 'ю', 'я', 'ё'}
        self.english_indicators = {'a', 'e', 'i', 'o', 'u'}
    
    def validate_parameter_consistency(self, handler_name: str) -> ValidationReport:
        """Validate parameters are consistent across all language files"""
        import time
        
        # Load all language donations for this handler
        language_donations = self._load_all_language_donations(handler_name)
        
        if len(language_donations) < 2:
            # Single language or no languages - always consistent
            return ValidationReport(
                handler_name=handler_name,
                languages_checked=list(language_donations.keys()),
                parameter_consistency=True,
                missing_parameters=[],
                extra_parameters=[],
                type_mismatches=[],
                warnings=[] if language_donations else [f"No language files found for handler '{handler_name}'"],
                timestamp=time.time()
            )
        
        # Collect parameter info by method
        method_parameters = defaultdict(lambda: defaultdict(dict))  # method_key -> language -> parameters
        
        for language, donation in language_donations.items():
            for method_donation in donation.method_donations:
                method_key = f"{method_donation.method_name}#{method_donation.intent_suffix}"
                
                # Collect method-specific parameters
                method_params = {}
                for param in method_donation.parameters:
                    method_params[param.name] = {
                        'type': param.type,
                        'required': param.required,
                        'default_value': param.default_value
                    }
                
                method_parameters[method_key][language] = method_params
        
        # Validate consistency
        missing_parameters = []
        extra_parameters = []
        type_mismatches = []
        
        for method_key, lang_params in method_parameters.items():
            # Get all parameter names across all languages for this method
            all_param_names = set()
            for params in lang_params.values():
                all_param_names.update(params.keys())
            
            # Check each parameter across languages
            for param_name in all_param_names:
                param_types = {}
                languages_with_param = []
                
                for language, params in lang_params.items():
                    if param_name in params:
                        languages_with_param.append(language)
                        param_types[language] = params[param_name]['type']
                
                # Find missing parameters
                missing_languages = set(lang_params.keys()) - set(languages_with_param)
                for missing_lang in missing_languages:
                    missing_parameters.append(f"{missing_lang}: {method_key}.{param_name}")
                
                # Check type consistency
                if len(set(param_types.values())) > 1:
                    type_pairs = [f"{lang}({ptype})" for lang, ptype in param_types.items()]
                    type_mismatches.append(f"{method_key}.{param_name}: {' vs '.join(type_pairs)}")
        
        parameter_consistency = not (missing_parameters or type_mismatches)
        
        return ValidationReport(
            handler_name=handler_name,
            languages_checked=list(language_donations.keys()),
            parameter_consistency=parameter_consistency,
            missing_parameters=missing_parameters,
            extra_parameters=extra_parameters,
            type_mismatches=type_mismatches,
            warnings=[],
            timestamp=time.time()
        )
    
    def validate_method_completeness(self, handler_name: str) -> CompletenessReport:
        """Check all methods exist in all language files"""
        import time
        
        # Load all language donations for this handler
        language_donations = self._load_all_language_donations(handler_name)
        
        if len(language_donations) < 2:
            # Single language or no languages - always complete
            all_methods = set()
            method_counts = {}
            
            for language, donation in language_donations.items():
                methods = {f"{m.method_name}#{m.intent_suffix}" for m in donation.method_donations}
                all_methods.update(methods)
                method_counts[language] = len(methods)
            
            return CompletenessReport(
                handler_name=handler_name,
                languages_checked=list(language_donations.keys()),
                method_completeness=True,
                missing_methods=[],
                extra_methods=[],
                all_methods=all_methods,
                method_counts_by_language=method_counts,
                warnings=[] if language_donations else [f"No language files found for handler '{handler_name}'"],
                timestamp=time.time()
            )
        
        # Collect methods by language
        methods_by_language = {}
        all_methods = set()
        
        for language, donation in language_donations.items():
            methods = {f"{m.method_name}#{m.intent_suffix}" for m in donation.method_donations}
            methods_by_language[language] = methods
            all_methods.update(methods)
        
        # Find missing and extra methods
        missing_methods = []
        extra_methods = []
        
        # Use the language with the most methods as the baseline
        baseline_language = max(methods_by_language.keys(), key=lambda lang: len(methods_by_language[lang]))
        baseline_methods = methods_by_language[baseline_language]
        
        for language, methods in methods_by_language.items():
            if language != baseline_language:
                # Find methods missing in this language
                missing = baseline_methods - methods
                for method_key in missing:
                    missing_methods.append(f"{language}: {method_key}")
                
                # Find extra methods in this language
                extra = methods - baseline_methods
                for method_key in extra:
                    extra_methods.append(f"{language}: {method_key}")
        
        # Check if all languages have the same methods
        method_completeness = all(methods == baseline_methods for methods in methods_by_language.values())
        
        method_counts = {lang: len(methods) for lang, methods in methods_by_language.items()}
        
        return CompletenessReport(
            handler_name=handler_name,
            languages_checked=list(language_donations.keys()),
            method_completeness=method_completeness,
            missing_methods=missing_methods,
            extra_methods=extra_methods,
            all_methods=all_methods,
            method_counts_by_language=method_counts,
            warnings=[],
            timestamp=time.time()
        )
    
    def suggest_translations(self, handler_name: str, source_lang: str, target_lang: str) -> TranslationSuggestions:
        """Suggest missing phrases based on other language files"""
        import time
        
        # Load source and target language donations
        language_donations = self._load_all_language_donations(handler_name)
        
        if source_lang not in language_donations:
            return TranslationSuggestions(
                handler_name=handler_name,
                source_language=source_lang,
                target_language=target_lang,
                missing_phrases=[],
                missing_methods=[],
                confidence_scores={},
                timestamp=time.time()
            )
        
        source_donation = language_donations[source_lang]
        target_donation = language_donations.get(target_lang)
        
        missing_phrases = []
        missing_methods = []
        confidence_scores = {}
        
        # Collect source methods and phrases
        source_methods = {f"{m.method_name}#{m.intent_suffix}": m for m in source_donation.method_donations}
        
        if target_donation:
            target_methods = {f"{m.method_name}#{m.intent_suffix}": m for m in target_donation.method_donations}
            
            # Find methods with missing phrases
            for method_key, source_method in source_methods.items():
                if method_key in target_methods:
                    target_method = target_methods[method_key]
                    
                    # Calculate phrase coverage
                    source_phrase_count = len(source_method.phrases)
                    target_phrase_count = len(target_method.phrases)
                    
                    if target_phrase_count < source_phrase_count:
                        missing_phrases.append({
                            'method_key': method_key,
                            'source_phrases': source_method.phrases,
                            'target_phrases': target_method.phrases,
                            'missing_count': source_phrase_count - target_phrase_count,
                            'coverage_ratio': target_phrase_count / source_phrase_count if source_phrase_count > 0 else 1.0
                        })
                        
                        # Calculate confidence based on phrase overlap and language detection
                        confidence = self._calculate_translation_confidence(source_method.phrases, target_method.phrases)
                        confidence_scores[method_key] = confidence
                else:
                    # Completely missing method
                    missing_methods.append(method_key)
                    missing_phrases.append({
                        'method_key': method_key,
                        'source_phrases': source_method.phrases,
                        'target_phrases': [],
                        'missing_count': len(source_method.phrases),
                        'coverage_ratio': 0.0
                    })
                    confidence_scores[method_key] = 0.8  # High confidence for completely missing methods
        else:
            # Target language file doesn't exist - all methods are missing
            for method_key, source_method in source_methods.items():
                missing_methods.append(method_key)
                missing_phrases.append({
                    'method_key': method_key,
                    'source_phrases': source_method.phrases,
                    'target_phrases': [],
                    'missing_count': len(source_method.phrases),
                    'coverage_ratio': 0.0
                })
                confidence_scores[method_key] = 0.9  # Very high confidence for missing file
        
        return TranslationSuggestions(
            handler_name=handler_name,
            source_language=source_lang,
            target_language=target_lang,
            missing_phrases=missing_phrases,
            missing_methods=missing_methods,
            confidence_scores=confidence_scores,
            timestamp=time.time()
        )
    
    def sync_parameters_across_languages(self, handler_name: str, source_lang: str, target_languages: List[str]) -> Dict[str, bool]:
        """Synchronize parameter structures from source language to target languages"""
        result = {}
        
        try:
            # Load source language donation
            language_donations = self._load_all_language_donations(handler_name)
            
            if source_lang not in language_donations:
                logger.error(f"Source language '{source_lang}' not found for handler '{handler_name}'")
                return {lang: False for lang in target_languages}
            
            source_donation = language_donations[source_lang]
            
            for target_lang in target_languages:
                try:
                    if target_lang not in language_donations:
                        logger.warning(f"Target language '{target_lang}' not found for handler '{handler_name}' - skipping")
                        result[target_lang] = False
                        continue
                    
                    target_donation = language_donations[target_lang]
                    
                    # Sync parameters for each method
                    updated = False
                    for source_method in source_donation.method_donations:
                        source_method_key = f"{source_method.method_name}#{source_method.intent_suffix}"
                        
                        # Find corresponding method in target
                        target_method = None
                        for tm in target_donation.method_donations:
                            if f"{tm.method_name}#{tm.intent_suffix}" == source_method_key:
                                target_method = tm
                                break
                        
                        if target_method:
                            # Sync parameters (preserve target phrases but update parameters)
                            if target_method.parameters != source_method.parameters:
                                target_method.parameters = source_method.parameters[:]  # Copy parameters
                                updated = True
                                logger.info(f"Synced parameters for method '{source_method_key}' from {source_lang} to {target_lang}")
                    
                    # Save updated target donation if changes were made
                    if updated and self.asset_loader:
                        success = self.asset_loader.save_donation_for_language(handler_name, target_lang, target_donation)
                        result[target_lang] = success
                        
                        if success:
                            logger.info(f"Successfully synced parameters for handler '{handler_name}' from {source_lang} to {target_lang}")
                    else:
                        result[target_lang] = True  # No changes needed
                
                except Exception as e:
                    logger.error(f"Failed to sync parameters for {target_lang}: {e}")
                    result[target_lang] = False
        
        except Exception as e:
            logger.error(f"Failed to sync parameters for handler '{handler_name}': {e}")
            result = {lang: False for lang in target_languages}
        
        return result
    
    def _load_all_language_donations(self, handler_name: str) -> Dict[str, HandlerDonation]:
        """Load all language donations for a handler"""
        language_donations = {}
        
        if self.asset_loader:
            # Use asset loader if available
            languages = self.asset_loader.get_available_languages_for_handler(handler_name)
            for language in languages:
                donation = self.asset_loader.get_donation_for_language_editing(handler_name, language)
                if donation:
                    language_donations[language] = donation
        else:
            # Direct file system access
            asset_handler_name = self._get_asset_handler_name(handler_name)
            lang_dir = self.assets_root / "donations" / asset_handler_name
            
            if lang_dir.exists():
                for lang_file in lang_dir.glob("*.json"):
                    language = lang_file.stem
                    try:
                        with open(lang_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            donation = HandlerDonation(**data)
                            language_donations[language] = donation
                    except Exception as e:
                        logger.warning(f"Failed to load {language} donation for {handler_name}: {e}")
        
        return language_donations
    
    def _get_asset_handler_name(self, handler_name: str) -> str:
        """Map handler file name to asset directory name"""
        if handler_name.endswith("_handler"):
            return handler_name
        return f"{handler_name}_handler"
    
    def _calculate_translation_confidence(self, source_phrases: List[str], target_phrases: List[str]) -> float:
        """Calculate confidence score for translation suggestions"""
        if not source_phrases:
            return 1.0
        
        if not target_phrases:
            return 0.8  # High confidence for completely missing translations
        
        # Simple heuristic based on phrase count ratio and language detection
        coverage_ratio = len(target_phrases) / len(source_phrases)
        
        # Check if target phrases are actually in the target language
        target_lang_consistency = self._check_language_consistency(target_phrases)
        
        # Combine factors
        base_confidence = min(coverage_ratio, 1.0)
        language_penalty = 0.1 if not target_lang_consistency else 0.0
        
        return max(0.0, base_confidence - language_penalty)
    
    def _check_language_consistency(self, phrases: List[str]) -> bool:
        """Check if phrases are in a consistent language"""
        if not phrases:
            return True
        
        # Sample a few phrases for language detection
        sample_size = min(5, len(phrases))
        sample_phrases = phrases[:sample_size]
        
        language_scores = {'ru': 0, 'en': 0}
        
        for phrase in sample_phrases:
            detected_lang = self._detect_phrase_language(phrase)
            language_scores[detected_lang] += 1
        
        # Consider consistent if 80% of phrases are in the same language
        max_score = max(language_scores.values())
        consistency_ratio = max_score / sample_size
        
        return consistency_ratio >= 0.8
    
    def _detect_phrase_language(self, phrase: str) -> str:
        """Simple language detection based on character sets"""
        phrase_lower = phrase.lower()
        
        russian_chars = sum(1 for char in phrase_lower if char in self.russian_indicators)
        english_chars = sum(1 for char in phrase_lower if char in self.english_indicators)
        
        # Simple heuristic: more characteristic vowels = likely language
        if russian_chars > english_chars:
            return "ru"
        else:
            return "en"
