# Language Support Enhancement Implementation Plan

## Overview

This document outlines the comprehensive implementation plan for enhancing language support in the Irene Voice Assistant project. The plan addresses reorganization of asset structures, donation file separation by language, selective language loading, system-wide component adjustments, and updates to the donations editor system.

## Background

The current system has mixed language support with inconsistent patterns across different asset types:
- **Templates/Prompts**: Recently migrated to `handler_name/{lang}.yaml` structure ✅
- **Localization**: Already follows `component/{lang}.yaml` pattern ✅ 
- **Donations**: Currently store all languages mixed in single JSON files (works well for NLU) ✅
- **Language Loading**: Loads all languages regardless of configuration ❌
- **System Components**: Already process unified mixed-language data optimally ✅

## Research Findings

After analyzing the current implementation and researching best practices for multilingual NLU systems, we discovered that **the current system already implements the optimal processing architecture**:

✅ **Unified NLU Processing**: Mixed-language patterns in single providers for better cross-language understanding  
✅ **Runtime Language Detection**: Smart language detection with context awareness  
✅ **Single Provider Instances**: Optimal memory usage and performance  
✅ **Cross-Language Pattern Matching**: Better fuzzy matching across languages

**The only enhancement needed**: Language-separated donation files for **better editing experience** while maintaining the **optimal unified processing**.

## Implementation Plan

### Phase 1: Asset Structure Completion ✅ COMPLETED

**Status**: Successfully implemented and tested
- ✅ Migrated templates from `handler/language/file.yaml` to `handler_name/{lang}.yaml`
- ✅ Migrated prompts to same pattern
- ✅ Updated `IntentAssetLoader` with new loading logic
- ✅ Added handler name mapping (`conversation` → `conversation_handler`)
- ✅ Verified system startup and functionality

**Benefits Achieved**:
- Consistent structure across templates and prompts
- Easier language addition (just add new `.yaml` files)
- Self-documenting folder names with `_handler` suffix
- Reduced directory nesting complexity

### Phase 2: Hybrid Language Architecture - Better Editing with Unified Processing

**Objective**: Implement language-separated donation files that merge into the existing optimal unified processing system

#### Phase 2A: Enhanced Asset Loader Infrastructure

**Language-Aware AssetLoaderConfig Enhancement**:
```python
class AssetLoaderConfig:
    def __init__(
        self,
        supported_languages: List[str] = None,
        default_language: str = "ru",
        enable_language_filtering: bool = True,
        ...
    ):
        self.supported_languages = supported_languages or ["ru", "en"]
        self.default_language = default_language
        self.enable_language_filtering = enable_language_filtering
```

**New IntentAssetLoader for Language-Separated Files**:
```python
class IntentAssetLoader:
    async def _load_donations(self, handler_names: List[str]) -> None:
        """Load language-separated donation files and merge for unified processing"""
        donations_dir = self.assets_root / "donations"
        
        for handler_name in handler_names:
            asset_handler_name = self._get_asset_handler_name(handler_name)
            language_donation_dir = donations_dir / asset_handler_name
            
            if not language_donation_dir.exists():
                self._add_warning(f"Missing donation directory for handler '{handler_name}': {language_donation_dir}")
                continue
                
            await self._load_language_separated_donations(language_donation_dir, handler_name)
    
    async def _load_language_separated_donations(self, lang_dir: Path, handler_name: str) -> None:
        """Load and merge language-specific donation files into unified donation"""
        language_donations = {}
        
        # Load each language file
        for lang_file in lang_dir.glob("*.json"):
            language = lang_file.stem
            if language in self.config.supported_languages:
                lang_donation = await self._load_and_validate_donation(lang_file, handler_name)
                language_donations[language] = lang_donation
                logger.debug(f"Loaded {language} donation for handler '{handler_name}'")
        
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
        merged_methods = {}
        
        # Merge method donations by method_name + intent_suffix
        for language, donation in language_donations.items():
            for method_donation in donation.method_donations:
                method_key = f"{method_donation.method_name}#{method_donation.intent_suffix}"
                
                if method_key not in merged_methods:
                    # Create new merged method donation
                    merged_methods[method_key] = MethodDonation(
                        method_name=method_donation.method_name,
                        intent_suffix=method_donation.intent_suffix,
                        description=method_donation.description,
                        phrases=[],  # Will accumulate from all languages
                        parameters=method_donation.parameters,  # Same across languages
                        lemmas=method_donation.lemmas or [],
                        token_patterns=method_donation.token_patterns or [],
                        spacy_patterns=method_donation.spacy_patterns or []
                    )
                
                # Accumulate phrases from all languages
                merged_methods[method_key].phrases.extend(method_donation.phrases)
                
                # Merge other language-specific fields
                if method_donation.lemmas:
                    merged_methods[method_key].lemmas.extend(method_donation.lemmas)
        
        # Create unified donation with merged methods
        return HandlerDonation(
            schema_version=base_donation.schema_version,
            donation_version=base_donation.donation_version,
            handler_domain=base_donation.handler_domain,
            description=base_donation.description,
            method_donations=list(merged_methods.values()),
            intent_name_patterns=base_donation.intent_name_patterns,
            action_patterns=base_donation.action_patterns,
            domain_patterns=base_donation.domain_patterns,
            global_parameters=base_donation.global_parameters
        )
```

#### Phase 2B: Donation File Structure Migration

**Current Mixed Structure**:
```
assets/donations/
├── conversation.json          # Contains mixed EN/RU phrases
├── system.json               # Contains mixed EN/RU phrases
└── [other handlers...]       # All mixing languages
```

**New Language-Separated Structure**:
```
assets/donations/
├── conversation_handler/
│   ├── en.json
│   └── ru.json
├── system_handler/
│   ├── en.json  
│   └── ru.json
└── [other handlers...]
```

**JSON Schema Updates**:
```json
{
  "$schema": "../v1.0.json",
  "schema_version": "1.0", 
  "donation_version": "1.0",
  "handler_domain": "conversation",
  "language": "en",                    // NEW: Explicit language field
  "description": "General conversation...",
  "method_donations": [
    {
      "phrases": ["let's talk", "let's chat"],  // Only English
      "examples": [
        {"text": "let's talk", "parameters": {}}  // Only English
      ]
    }
  ]
}
```

**Migration Implementation**:
1. Update `assets/v1.0.json` with new language field
2. Create `tools/migrate_donations_by_language.py` script
3. Implement language detection and phrase separation
4. Generate language-specific files with validation

#### Phase 2C: One-Time Migration Script

**Temporary Migration Script** (`tools/migrate_donations.py`):
```python
#!/usr/bin/env python3
"""One-time script to migrate existing donation files to language-separated structure"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

class DonationMigrationTool:
    def __init__(self):
        self.russian_indicators = {'а', 'е', 'и', 'о', 'у', 'ы', 'э', 'ю', 'я', 'ё'}
        self.english_indicators = {'a', 'e', 'i', 'o', 'u'}
    
    def migrate_all_donations(self, source_dir: Path, target_dir: Path) -> None:
        """Migrate all donation files from unified to language-separated structure"""
        donations_dir = source_dir / "donations"
        
        for donation_file in donations_dir.glob("*.json"):
            handler_name = donation_file.stem
            print(f"Migrating {handler_name}...")
            
            self.split_donation_by_language(donation_file, target_dir, handler_name)
        
        print("Migration completed. You can now delete this script.")
    
    def split_donation_by_language(self, source_file: Path, target_dir: Path, handler_name: str) -> None:
        """Split single donation file into language-separated files"""
        with open(source_file, 'r', encoding='utf-8') as f:
            donation = json.load(f)
        
        # Create handler directory
        asset_handler_name = f"{handler_name}_handler" if not handler_name.endswith("_handler") else handler_name
        handler_dir = target_dir / "donations" / asset_handler_name
        handler_dir.mkdir(parents=True, exist_ok=True)
        
        # Separate phrases by language
        languages_data = defaultdict(lambda: {
            **donation,
            "method_donations": []
        })
        
        for method_donation in donation["method_donations"]:
            phrases_by_lang = self._separate_phrases_by_language(method_donation["phrases"])
            
            for language, phrases in phrases_by_lang.items():
                if phrases:  # Only add if has phrases in this language
                    method_copy = method_donation.copy()
                    method_copy["phrases"] = phrases
                    
                    # Filter language-specific patterns if present
                    if "lemmas" in method_copy:
                        method_copy["lemmas"] = self._filter_lemmas_by_language(method_copy["lemmas"], language)
                    
                    languages_data[language]["method_donations"].append(method_copy)
        
        # Write language-specific files
        for language, lang_data in languages_data.items():
            if lang_data["method_donations"]:  # Only write if has content
                lang_data["language"] = language  # Add explicit language field
                
                lang_file = handler_dir / f"{language}.json"
                with open(lang_file, 'w', encoding='utf-8') as f:
                    json.dump(lang_data, f, indent=2, ensure_ascii=False)
                
                print(f"  Created {lang_file} with {len(lang_data['method_donations'])} methods")
    
    def _separate_phrases_by_language(self, phrases: List[str]) -> Dict[str, List[str]]:
        """Separate phrases by detected language"""
        phrases_by_lang = defaultdict(list)
        
        for phrase in phrases:
            detected_lang = self._detect_phrase_language(phrase)
            phrases_by_lang[detected_lang].append(phrase)
        
        return dict(phrases_by_lang)
    
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
    
    def _filter_lemmas_by_language(self, lemmas: List[str], language: str) -> List[str]:
        """Filter lemmas to match the target language"""
        return [lemma for lemma in lemmas if self._detect_phrase_language(lemma) == language]

if __name__ == "__main__":
    migrator = DonationMigrationTool()
    source_dir = Path("assets")
    target_dir = Path("assets")
    
    migrator.migrate_all_donations(source_dir, target_dir)
    
    print("\nMigration complete!")
    print("1. Verify the new language-separated files in assets/donations/")
    print("2. Test the system startup")
    print("3. Delete the old *.json files from assets/donations/")
    print("4. Delete this migration script")
```

**Usage**:
```bash
# Run once to migrate
python tools/migrate_donations.py

# Verify migration worked
uv run python -m irene.runners.webapi_runner --config configs/config-master.toml

# Clean up old files
rm assets/donations/*.json
rm tools/migrate_donations.py
```

#### Phase 2 Testing Strategy

**Unit Tests**:
- Language-specific donation loading
- Schema validation for new language field
- AssetLoaderConfig language filtering
- Migration script validation

**Integration Tests**:
- Template/prompt loading with language filtering
- Donation file structure migration
- Cross-language consistency validation

**Test Cases**:
```python
def test_language_specific_donation_loading():
    # Test loading only configured languages
    
def test_donation_migration_script():
    # Test phrase separation and file generation
    
def test_asset_loader_language_filtering():
    # Test selective language loading
```

### Phase 3: Donations Editor Language Interface

**Objective**: Update donations editor to support language-separated donation editing while maintaining unified processing

#### Phase 3A: Current Architecture Analysis

**Current Optimal Processing** ✅:
```python
# Current system already implements optimal architecture:
for donation in keyword_donations:
    semantic_examples.extend(donation.phrases)  # MIXED LANGUAGES - OPTIMAL!
    self.intent_patterns[intent_name] = semantic_examples  # UNIFIED PATTERNS - OPTIMAL!
```

**Benefits of Current Unified Processing**:
- **Cross-language understanding**: Better fuzzy matching across languages
- **Single provider instances**: Optimal memory usage
- **Runtime language detection**: Smart context-aware language handling
- **Code-switching support**: Handles mixed-language queries naturally

**What We Keep** ✅:
```python
class NLUComponent:
    def __init__(self, config):
        # Keep current optimal architecture:
        self.providers = {"spacy": SpacyProvider(), "hybrid": HybridProvider()}
        
        # Enhanced with optional language filtering for deployment:
        if config.enable_language_filtering:
            filtered_donations = asset_loader.filter_donations_by_language(config.supported_languages)
        else:
            filtered_donations = asset_loader.convert_to_keyword_donations()  # All languages
```

**SpaCy Provider Language-Specific Initialization**:
```python
class SpacyProvider:
    def __init__(self, language: str = "ru"):
        self.language = language
        self.model_name = self._get_model_for_language(language)
        
    async def _initialize_from_donations(self, keyword_donations: List[KeywordDonation]):
        """Initialize with language-consistent patterns only"""
        for donation in keyword_donations:
            # Only process phrases in this provider's language
            if self._validate_language_consistency(donation.phrases):
                self.intent_patterns[donation.intent] = donation.phrases
            else:
                logger.warning(f"Language inconsistency in {donation.intent} for {self.language}")
```

#### Phase 3B: Optional Language Filtering Enhancement

**Current Pattern Registration** ✅ **KEEP AS-IS**:
```python
# Current optimal approach - no changes needed:
for method_donation in donation.method_donations:
    intent_pattern = f"{domain}.{method_donation.intent_suffix}"
    patterns.append(intent_pattern)  # UNIFIED PATTERNS - OPTIMAL!
```

**Optional Enhancement for Deployment Filtering**:
```python
class IntentAssetLoader:
    def convert_to_keyword_donations(self, filter_languages: List[str] = None) -> List[KeywordDonation]:
        """Convert with optional language filtering for resource-constrained deployments"""
        keyword_donations = []
        
        for handler_name, donation in self.donations.items():
            for method_donation in donation.method_donations:
                # Optional phrase filtering for deployment
                phrases = method_donation.phrases
                if filter_languages and self.config.enable_language_filtering:
                    phrases = self._filter_phrases_by_language(phrases, filter_languages)
                
                keyword_donation = KeywordDonation(
                    intent=f"{donation.handler_domain}.{method_donation.intent_suffix}",
                    phrases=phrases,  # Filtered if requested, unified if not
                    parameters=converted_params
                )
                keyword_donations.append(keyword_donation)
        
        return keyword_donations
    
    def _filter_phrases_by_language(self, phrases: List[str], supported_languages: List[str]) -> List[str]:
        """Optional filtering for deployment scenarios"""
        if not self.config.enable_language_filtering:
            return phrases  # No filtering, return all for optimal performance
        
        # Filter only if explicitly requested for resource-constrained deployments
        filtered = []
        for phrase in phrases:
            detected_lang = self._quick_language_detect(phrase)
            if detected_lang in supported_languages:
                filtered.append(phrase)
        return filtered
```

#### Phase 3C: Editor API Support Methods

**Language-Separated File Access for Editor**:
```python
class IntentAssetLoader:
    def get_donation_for_language_editing(self, handler_name: str, language: str) -> Optional[HandlerDonation]:
        """Get language-specific donation for editing purposes"""
        asset_handler_name = self._get_asset_handler_name(handler_name)
        lang_file = self.assets_root / "donations" / asset_handler_name / f"{language}.json"
        
        if lang_file.exists():
            with open(lang_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return HandlerDonation.from_dict(data)
        
        return None
    
    def save_donation_for_language(self, handler_name: str, language: str, donation: HandlerDonation) -> None:
        """Save language-specific donation for editing"""
        asset_handler_name = self._get_asset_handler_name(handler_name)
        lang_dir = self.assets_root / "donations" / asset_handler_name
        lang_dir.mkdir(parents=True, exist_ok=True)
        
        # Add explicit language field
        donation_dict = donation.to_dict()
        donation_dict["language"] = language
        
        lang_file = lang_dir / f"{language}.json"
        with open(lang_file, 'w', encoding='utf-8') as f:
            json.dump(donation_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {language} donation for handler '{handler_name}' to {lang_file}")
    
    async def reload_unified_donation(self, handler_name: str) -> None:
        """Reload unified donation after language file changes"""
        asset_handler_name = self._get_asset_handler_name(handler_name)
        lang_dir = self.assets_root / "donations" / asset_handler_name
        
        if lang_dir.exists():
            await self._load_language_separated_donations(lang_dir, handler_name)
            logger.info(f"Reloaded unified donation for handler '{handler_name}'")
    
    def get_available_languages_for_handler(self, handler_name: str) -> List[str]:
        """Get list of available language files for handler"""
        asset_handler_name = self._get_asset_handler_name(handler_name)
        lang_dir = self.assets_root / "donations" / asset_handler_name
        
        if not lang_dir.exists():
            return []
        
        return [lang_file.stem for lang_file in lang_dir.glob("*.json")]
```

#### Phase 3D: Enhanced Runtime Language Handling ✅ **ALREADY OPTIMAL**

**Current System Already Implements Optimal Pattern**:
```python
# From irene/components/nlu_component.py - already optimal:
class ContextAwareNLUProcessor:
    async def _detect_language(self, text: str, context: ConversationContext) -> str:
        """Detect language with context awareness - ALREADY IMPLEMENTED ✅"""
        # Priority order:
        # 1. User preference from context
        # 2. Previous conversation language  
        # 3. Text-based detection
        # 4. System default
```

**Current Optimal Processing** ✅:
```python
# Current system already handles language context optimally:
class IntentOrchestrator:
    async def process_intent(self, intent: Intent, context: ConversationContext):
        """Process intent with automatic language detection - ALREADY OPTIMAL ✅"""
        # Language detection already implemented and working
        # Templates/prompts already use language context
        # No changes needed - system already works optimally
```

#### Phase 3 Testing Strategy

**Unit Tests**:
- Language-specific provider initialization
- Intent registration by language
- Asset conversion with language filtering
- Handler language context switching

**Integration Tests**:
- End-to-end intent processing with language context
- Cross-language handler routing
- Language detection and fallback logic

**Test Cases**:
```python
def test_language_specific_nlu_providers():
    # Test provider isolation by language
    
def test_intent_registration_by_language():
    # Test pattern registration with language context
    
def test_handler_language_context():
    # Test handler processing with language switching
    
def test_cross_language_intent_routing():
    # Test language-aware intent orchestration
```

### Phase 4: Enhanced Donations Editor for Language-Separated Files

**Objective**: Update donations editor to support editing language-separated donation files while maintaining unified processing

#### Phase 4A: Backend API Language-Aware Endpoints

**New Language-Aware Endpoints**:
```
GET    /intents/donations                              # List all handlers with language info
GET    /intents/donations/{handler_name}               # List languages for handler  
GET    /intents/donations/{handler_name}/{language}    # Get language-specific donation for editing
PUT    /intents/donations/{handler_name}/{language}    # Update language-specific donation
POST   /intents/donations/{handler_name}/{language}/validate  # Validate specific language
DELETE /intents/donations/{handler_name}/{language}    # Delete language file
POST   /intents/donations/{handler_name}/{language}    # Create new language file
POST   /intents/donations/{handler_name}/reload        # Trigger unified donation reload
```

**API Response Schema Updates**:
```typescript
interface DonationHandlerListResponse {
  handlers: Array<{
    handler_name: string;
    languages: string[];              // Available languages
    total_languages: number;          // Language count
    supported_languages: string[];    // From system config
    default_language: string;         // System default
  }>;
}

interface DonationContentResponse {
  handler_name: string;
  language: string;                   // Current language
  donation_data: Record<string, any>;
  metadata: {
    file_path: string;               // e.g., "conversation_handler/en.json"
    language: string;                // Language code
    file_size: number;
    last_modified: number;
  };
  available_languages: string[];     // Other available languages
  cross_language_validation: {       // NEW: Cross-language checks
    parameter_consistency: boolean;
    missing_methods: string[];
    extra_methods: string[];
  };
}
```

#### Phase 4B: Frontend Language Management Interface

**Navigation Structure Evolution**:
```
Current: Handler Selection → Single Editor
New:     Handler Selection → Language Selection → Editor

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Handler List    │    │ Language Tabs    │    │ Donation Editor │
│                 │    │                  │    │                 │
│ □ conversation  │────│ [EN] [RU] [+]    │────│ Method Details  │
│   ├─ EN ✓      │    │ Active: EN       │    │ Phrases & Forms │
│   └─ RU ⚠      │    │ Config: EN,RU    │    │ Cross-validation│
│ □ system        │    │ Missing: DE      │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

**Enhanced Components**:

1. **Language-Aware Handler List**:
```typescript
interface HandlerListItem {
  handler_name: string;
  languages: Array<{
    code: string;
    status: 'complete' | 'partial' | 'missing';  // Validation status
    method_count: number;
    last_modified: string;
  }>;
  supported_languages: string[];     // From config
  total_methods: number;             // Max across languages
}
```

2. **Language Management Tabs**:
```typescript
interface LanguageTabs {
  activeLanguage: string;
  availableLanguages: Array<{
    code: string;
    label: string;
    status: 'loaded' | 'loading' | 'error';
    validationErrors: number;
  }>;
  supportedLanguages: string[];      // From config
  onLanguageChange: (lang: string) => void;
  onCreateLanguage: (lang: string, templateFrom?: string) => void;
  onDeleteLanguage: (lang: string) => void;
  onCompareLanguages: (lang1: string, lang2: string) => void;
}
```

#### Phase 4C: Enhanced API Client

**Language-Aware API Methods**:
```typescript
class ApiClient {
  // Handler and language discovery
  async getDonationHandlers(): Promise<DonationHandlerListResponse>;
  async getHandlerLanguages(handlerName: string): Promise<string[]>;
  
  // Language-specific CRUD operations
  async getDonation(handlerName: string, language: string): Promise<DonationContentResponse>;
  async updateDonation(handlerName: string, language: string, data: DonationData): Promise<UpdateDonationResponse>;
  async validateDonation(handlerName: string, language: string, data: DonationData): Promise<ValidateDonationResponse>;
  
  // Language management operations
  async createLanguage(handlerName: string, language: string, options: {
    copyFrom?: string;
    useTemplate?: boolean;
  }): Promise<CreateLanguageResponse>;
  async deleteLanguage(handlerName: string, language: string): Promise<DeleteLanguageResponse>;
  
  // Cross-language operations
  async validateCrossLanguageConsistency(handlerName: string): Promise<CrossLanguageValidationResponse>;
  async synchronizeParameters(handlerName: string, sourceLanguage: string, targetLanguages: string[]): Promise<SyncResponse>;
}
```

#### Phase 4 Testing Strategy

**Frontend Tests**:
- Language tab switching and state management
- Cross-language validation display
- Language creation and deletion workflows
- Bulk editing operations

**API Tests**:
- Language-specific CRUD operations
- Cross-language validation logic
- Error handling for missing languages
- Permission validation for language operations

### Phase 5: Simple Cleanup & Documentation (TBD)

**Objective**: Basic cleanup and documentation updates

**Simple Tasks (when ready)**:
- Delete migration script once confident in new system
- Update README with new language-separated structure  
- Clean up any unused legacy code
- Basic documentation updates

**Note**: Phase 5 scope will be determined later - avoiding overkill optimization tasks for now.

## Implementation Timeline

### Phase 1 ✅ COMPLETED (2024-09-16)
- Asset structure reorganization (templates/prompts)
- Handler name mapping implementation
- System testing and validation

### Phase 2: Language-Separated Files Implementation (Week 1-2) ✅ COMPLETED (2025-09-16)
- [x] **Week 1**: Enhanced AssetLoaderConfig with language filtering
- [x] **Week 1**: Language-separated donation file loading with unified merging
- [x] **Week 2**: One-time migration script and data conversion
- [x] **Week 2**: Testing and validation of new structure

**Implementation Results**:
- Successfully migrated all 14 donation files to language-separated structure
- Backward compatibility maintained with automatic fallback to legacy format
- Optimal unified processing preserved with cross-language phrase merging
- System startup verified with all components functioning correctly
- NLU providers receiving merged multi-language patterns as designed

### Phase 3: Editor Interface Replacement (Week 3-4) ✅ COMPLETED (2025-09-16)
- [x] **Week 3**: New backend API language-aware endpoints
- [x] **Week 3**: Language-separated file management API  
- [x] **Week 4**: New frontend language management interface
- [x] **Week 4**: Language-tab editor with cross-language validation

**Implementation Results (Completed)**:
- ✅ **7 new language-aware API endpoints**: Clean `/donations` endpoints (removed v2 suffixes)
- ✅ **Complete backend language-separated file access**: 14 handlers with en/ru language support
- ✅ **Cross-language validation system**: Parameter consistency, missing/extra method detection
- ✅ **Updated API client and TypeScript types**: Full language-aware frontend integration ready
- ✅ **Backend functionality fully tested**: Save/load cycles, validation, language management verified
- ✅ **Old single-file donation API endpoints removed**: Clean backend API transition completed
- ✅ **Complete frontend HandlerList replacement**: Language-aware with nested change tracking
- ✅ **Language tab interface for editor**: LanguageTabs component with create/delete/switch functionality
- ✅ **Handler → Language → Editor navigation flow**: Complete 3-tier interface implemented
- ✅ **Language-specific data handling**: Proper key structure (`${handler}:${language}`)
- ✅ **Real-time language status indicators**: Method counts, validation status, error counts
- ✅ **Language count filtering**: Filter handlers by single/multiple language support
- ✅ **Data quality fixes**: Corrected mixed Russian/English content in language-separated files
- ✅ **Full Phase 3 testing**: End-to-end functionality verified and working

### Phase 4: Essential Language Features (Week 5) ✅ COMPLETED (2025-09-16)
- [x] **Week 5**: Cross-language validation and synchronization tools
- [x] **Week 5**: Translation workflow integration

**Implementation Results (Completed)**:
- ✅ **CrossLanguageValidator backend class**: Complete parameter and method validation system
- ✅ **3 new API endpoints**: `cross-validation`, `sync-parameters`, `suggest-translations`
- ✅ **Enhanced API schemas**: Full type support for validation reports and sync operations
- ✅ **LanguageTabs component enhancement**: Real-time validation display with sync controls
- ✅ **DonationsPage integration**: Complete cross-language validation workflow
- ✅ **API client updates**: Full support for Phase 4 validation endpoints
- ✅ **Real-time feedback**: Automatic validation on handler selection and language switching
- ✅ **Parameter synchronization**: One-click sync from source to target languages

### Phase 5: Simple Cleanup & Documentation ✅ COMPLETED (2025-09-16)
- [x] **Cleanup and documentation finalization**

**Cleanup Implementation Results**:
- ✅ **Legacy code removal**: Removed unused functions and outdated comments
- ✅ **Legacy donation loading**: Removed backward compatibility code for single-file donations
- ✅ **Migration completion**: All old single-file donations successfully migrated
- ✅ **Code quality improvements**: All linting checks pass, codebase clean
- ✅ **Documentation finalization**: Complete documentation of all phases


## Testing Strategy

### Essential Tests
- Cross-language validation functionality  
- Parameter synchronization tools
- Language tab switching and management
- API endpoints for language operations

### Integration Tests  
- Editor workflows with language switching
- Language creation and deletion workflows
- Basic system functionality validation

## Rollback Plan

### Current System Rollback
- Migration script artifacts are preserved for potential rollback if needed
- Language-separated files can be merged back to unified format if required
- All core functionality remains backward compatible during transition

## Success Metrics

### Usability Metrics
- Language switching works smoothly in editor
- Cross-language validation catches inconsistencies
- Parameter sync reduces manual work

### Maintainability Metrics  
- Easy addition of new languages
- Improved donation editing workflow
- Better cross-language consistency

## Risk Assessment

### Remaining Risks
- **Cross-language validation complexity**: New UI components may introduce bugs
  - **Mitigation**: Incremental implementation and testing
- **Parameter sync edge cases**: Complex parameter structures may cause sync issues  
  - **Mitigation**: Start with simple cases, expand gradually

## Conclusion

This implementation plan provides a **hybrid approach** that delivers the best of both worlds: **better editing experience** through language-separated files while **maintaining optimal processing performance** through unified NLU architecture.

### Key Insights from Analysis

**Current System Strengths** ✅:
- **Optimal NLU Architecture**: Mixed-language processing for better cross-language understanding
- **Runtime Language Detection**: Smart, context-aware language handling
- **Single Provider Instances**: Optimal memory usage and performance
- **Code-switching Support**: Handles mixed-language queries naturally

**Targeted Improvements**:
- **Better Editing Experience**: Language-separated donation files for easier translation workflows
- **Enhanced Editor Interface**: Modern, tab-based editing with cross-language validation
- **Optional Deployment Filtering**: Resource optimization for constrained environments
- **Backwards Compatibility**: Smooth migration path with dual structure support

### Key Benefits of Hybrid Implementation

1. **Performance**: Maintains optimal unified NLU processing (no performance regression)
2. **Editing Experience**: Language-separated files make translation workflows much easier
3. **Flexibility**: Supports both unified and separated file structures
4. **Scalability**: Easy addition of new languages through simple file creation
5. **Maintainability**: Clear separation for translators while preserving system efficiency
6. **Backwards Compatibility**: Gradual migration without breaking existing functionality

### Technical Innovation

**Language-Separated Files → Unified Processing Pipeline**:
```
Edit: handler_name/en.json + handler_name/ru.json
  ↓ (merge during load)
Process: unified patterns for optimal NLU performance
  ↓ (language detection at runtime)
Respond: language-specific templates/prompts
```

This approach represents a **best-practices implementation** that optimizes for both developer experience and system performance, validated through research and current system analysis.

### Phase 6: Templates Editor Implementation ✅ COMPLETED (2025-09-16)

**Objective**: Implement language-aware editor for response templates following the donations editor pattern

#### Phase 6A: Backend API Implementation ✅ COMPLETED

**New Templates API Endpoints**:
```
GET    /intents/templates                              # List all handlers with language info
GET    /intents/templates/{handler_name}/languages     # List languages for handler  
GET    /intents/templates/{handler_name}/{language}    # Get language-specific templates
PUT    /intents/templates/{handler_name}/{language}    # Update language-specific templates
POST   /intents/templates/{handler_name}/{language}/validate  # Validate templates
DELETE /intents/templates/{handler_name}/{language}    # Delete language file
POST   /intents/templates/{handler_name}/{language}    # Create new language file
```

**Backend Schema Implementation**:
```typescript
interface TemplateContentResponse {
  handler_name: string;
  language: string;
  template_data: Record<string, string | string[] | Record<string, string>>;
  metadata: TemplateMetadata;
  available_languages: string[];
  schema_info: {
    expected_keys: string[];
    key_types: Record<string, 'string' | 'array' | 'object'>;
  };
}

interface TemplateMetadata {
  file_path: string;
  language: string;
  file_size: number;
  last_modified: number;
  template_count: number;
}
```

#### Phase 6B: Frontend Implementation ✅ COMPLETED

**New Components**:
- **TemplateEditor**: YAML-aware editor with syntax highlighting
- **TemplateKeyEditor**: Specialized editor for string/array/object values  
- **TemplatesPage**: Main page following donations page pattern

**Reused Components**: `HandlerList`, `LanguageTabs`, `ApplyChangesBar`

**Asset Structure**: `assets/templates/{handler_name}/{language}.yaml`
**Complexity**: **Low** - Simple YAML key-value pairs and arrays

**Implementation Results**:
- ✅ **7 new template API endpoints**: Complete CRUD operations for template management
- ✅ **Enhanced asset loader**: Template loading, saving, validation, and language management methods
- ✅ **Template management schemas**: Full TypeScript integration with existing API patterns
- ✅ **TemplateEditor component**: Multi-view editor (Structured, YAML, Preview) with validation
- ✅ **TemplateKeyEditor component**: Type-aware editing for strings, arrays, and objects
- ✅ **TemplatesPage integration**: Complete templates management interface following donations pattern
- ✅ **API client extension**: Template endpoints added with proper typing
- ✅ **Navigation integration**: Templates page added to sidebar navigation (/templates route)
- ✅ **Existing template compatibility**: 12 handlers with en/ru template files ready for editing

### Phase 7: Prompts Editor Implementation ✅ COMPLETED (2025-09-17)

**Objective**: Implement language-aware editor for LLM prompts with metadata support

#### Phase 7A: Backend API Implementation ✅ COMPLETED

**New Prompts API Endpoints**:
```
GET    /intents/prompts                              # List all handlers with language info
GET    /intents/prompts/{handler_name}/languages     # List languages for handler  
GET    /intents/prompts/{handler_name}/{language}    # Get language-specific prompts
PUT    /intents/prompts/{handler_name}/{language}    # Update language-specific prompts
POST   /intents/prompts/{handler_name}/{language}/validate  # Validate prompts
DELETE /intents/prompts/{handler_name}/{language}    # Delete language file
POST   /intents/prompts/{handler_name}/{language}    # Create new language file
```

**Backend Schema Implementation**:
```typescript
interface PromptContentResponse {
  handler_name: string;
  language: string;
  prompt_data: Record<string, PromptDefinition>;
  metadata: PromptMetadata;
  available_languages: string[];
  schema_info: {
    required_fields: string[];
    prompt_types: string[];
  };
}

interface PromptDefinition {
  description: string;
  usage_context: string;
  variables: Array<{name: string; description: string}>;
  prompt_type: 'system' | 'template' | 'user';
  content: string;
}
```

#### Phase 7B: Frontend Implementation ✅ COMPLETED

**New Components**:
- **PromptEditor**: Multi-section editor for prompt definitions
- **PromptMetadataEditor**: Editor for description, usage_context, variables
- **PromptContentEditor**: Large text area with variable highlighting
- **PromptVariableManager**: Dynamic variable definition interface
- **PromptsPage**: Main page following donations page pattern

**Asset Structure**: `assets/prompts/{handler_name}/{language}.yaml`
**Complexity**: **Medium** - Structured YAML with metadata, variables, and multi-line content

**Implementation Results**:
- ✅ **7 new prompt API endpoints**: Complete CRUD operations for prompt management with metadata support
- ✅ **Enhanced asset loader**: Prompt loading, saving, validation, and language management methods
- ✅ **Prompt management schemas**: Full TypeScript integration with PromptDefinition complex type
- ✅ **PromptEditor component**: Multi-view editor (Structured, YAML, Preview) with variable management
- ✅ **PromptDefinitionEditor component**: Metadata-aware editing for descriptions, contexts, variables, and content
- ✅ **PromptsPage integration**: Complete prompts management interface following donations pattern
- ✅ **API client extension**: Prompt endpoints added with proper typing for complex PromptDefinition objects
- ✅ **Navigation integration**: Prompts page added to sidebar navigation (/prompts route)
- ✅ **Existing prompt compatibility**: 1 handler (conversation) with en/ru prompt files ready for editing
- ✅ **Advanced validation**: Full prompt structure validation including metadata, variables, and content requirements

### Phase 8: Localizations Editor Implementation ✅ COMPLETED (2025-09-17)

**Objective**: Implement language-aware editor for system localization data (domain-based instead of handler-based)

#### Phase 8A: Backend API Implementation

**New Localizations API Endpoints**:
```
GET    /intents/localizations                           # List all domains with language info
GET    /intents/localizations/{domain}/languages        # List languages for domain  
GET    /intents/localizations/{domain}/{language}       # Get language-specific localizations
PUT    /intents/localizations/{domain}/{language}       # Update language-specific localizations
POST   /intents/localizations/{domain}/{language}/validate  # Validate localizations
DELETE /intents/localizations/{domain}/{language}       # Delete language file
POST   /intents/localizations/{domain}/{language}       # Create new language file
```

**Backend Schema Implementation**:
```typescript
interface LocalizationContentResponse {
  domain: string;  // Note: domain instead of handler_name
  language: string;
  localization_data: Record<string, any>;  // Various types: strings, arrays, objects
  metadata: LocalizationMetadata;
  available_languages: string[];
  schema_info: {
    expected_keys: string[];
    key_types: Record<string, string>;
    domain_description: string;
  };
}
```

#### Phase 8B: Frontend Implementation

**New Components**:
- **LocalizationEditor**: Multi-type value editor (strings, arrays, objects)
- **LocalizationKeyEditor**: Type-aware editor for different value types
- **LocalizationDomainList**: Domain selection component (adapted from HandlerList)
- **LocalizationsPage**: Main page following donations page pattern

**Reused Components**: `LanguageTabs`, `ApplyChangesBar` (adapted for domains)

**Asset Structure**: `assets/localization/{domain}/{language}.yaml`
**Complexity**: **Medium** - Domain-based with various data types

**Implementation Results**:
- ✅ **7 new localization API endpoints**: Complete CRUD operations for domain-based localization management
- ✅ **Enhanced asset loader**: Domain-based localization loading, saving, validation, and language management methods
- ✅ **Localization management schemas**: Full TypeScript integration with domain-specific validation
- ✅ **LocalizationEditor component**: Multi-view editor (Structured, YAML, Preview) with domain-aware validation
- ✅ **LocalizationKeyEditor component**: Type-aware editing for strings, arrays, and objects with domain hints
- ✅ **LocalizationsPage integration**: Complete localization management interface following donations pattern
- ✅ **API client extension**: Localization endpoints added with proper typing for domain-based data
- ✅ **Navigation integration**: Localizations page added to sidebar navigation (/localizations route)
- ✅ **Existing localization compatibility**: 5 domains (commands, components, datetime, domains, voice_synthesis) with en/ru files ready for editing
- ✅ **Domain-specific validation**: Targeted validation rules for each localization domain type
- ✅ **Multi-type value support**: Advanced editing for strings, arrays, and objects in localization data

## Implementation Timeline (Extended)

### Phase 6: Templates Editor (Week 6) ✅ COMPLETED (2025-09-16)
- ✅ **Week 6**: Backend API endpoints and schemas for templates
- ✅ **Week 6**: Frontend TemplateEditor components and TemplatesPage
- ✅ **Week 6**: Integration testing and validation

### Phase 7: Prompts Editor (Week 7) ✅ COMPLETED (2025-09-17)
- ✅ **Week 7**: Backend API endpoints and schemas for prompts
- ✅ **Week 7**: Frontend PromptEditor components with metadata support
- ✅ **Week 7**: Integration testing and variable management

### Phase 8: Localizations Editor (Week 8) ✅ COMPLETED (2025-09-17)
- ✅ **Week 8**: Backend API endpoints and schemas for localizations
- ✅ **Week 8**: Frontend LocalizationEditor components and domain management
- ✅ **Week 8**: Integration testing and multi-type value editing

## Extended Implementation Strategy

### Key Design Principles
1. **Consistency**: Follow the exact same patterns as the donations editor
2. **Reusability**: Maximize reuse of existing components (`LanguageTabs`, `ApplyChangesBar`, etc.)
3. **Type Safety**: Full TypeScript typing for all new schemas and components
4. **Validation**: Comprehensive validation for each asset type's unique requirements
5. **Language Support**: Full language-separation support like donations system

### Estimated Complexity
- **Templates Editor**: **Low** (1-2 days) - Simple YAML key-value editing
- **Prompts Editor**: **Medium** (2-3 days) - Structured YAML with metadata
- **Localizations Editor**: **Medium** (2-3 days) - Domain-based with various data types

**Total Additional Time**: 5-8 days for complete implementation of all three editors

## Final Status: Donations System Complete, Additional Editors Planned

### Completed Implementation ✅
- ✅ **Phase 1**: Asset structure reorganization
- ✅ **Phase 2**: Language-separated files with unified processing
- ✅ **Phase 3**: Enhanced editor interface
- ✅ **Phase 4**: Cross-language validation and synchronization tools
- ✅ **Phase 5**: Code cleanup and documentation finalization
- ✅ **Phase 6**: Templates Editor - Complete YAML response template editing system
- ✅ **Phase 7**: Prompts Editor - Complete LLM prompt editing system with metadata support

### Completed Implementation ✅
- ✅ **Phase 8**: Localizations Editor - Domain-based localization data editing system

The Irene Voice Assistant now has **complete, production-ready editing systems for donations, templates, prompts, and localizations** covering all major asset types:
- **Optimal performance** through unified NLU processing
- **Excellent developer experience** with language-separated editing
- **Automatic validation** to maintain consistency across languages
- **One-click synchronization** tools for efficient maintenance
- **Multi-format editing support** for JSON donations, YAML templates, structured prompts, and localization data
- **Domain-aware editing** for localization data with type-specific validation and hints
- **Clean, maintainable codebase** with comprehensive documentation
- **Complete asset management** for all major Irene Voice Assistant components
