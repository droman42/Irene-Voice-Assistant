/**
 * TypeScript type definitions for Irene API responses and data structures
 */

// Base API response structure - matches backend standard
export interface BaseApiResponse {
  success: boolean;
  timestamp: number;
}

// Error response structure
export interface ApiError {
  error: string;
  details?: any;
  status_code?: number;
}

// Validation error/warning types - matches backend schemas
export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ValidationWarning {
  type: string;
  message: string;
  path?: string;
}

// Legacy validation result structure for compatibility
export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  details?: any;
}

// Donation-related types
export interface DonationMethod {
  method_name: string;
  intent_suffix: string;
  description: string;
  phrases?: string[];
  lemmas?: string[];
  parameters?: any[];
  token_patterns?: Array<Array<Record<string, any>>>;
  slot_patterns?: Record<string, Array<Array<Record<string, any>>>>;
  examples?: Array<string | { text: string; parameters: Record<string, any> }>;
  boost?: number;
  
  // Legacy field mappings for backward compatibility
  name?: string; // Maps to method_name
  global_params?: string[]; // Legacy field
}

export interface DonationData {
  schema_version?: string;
  donation_version?: string;
  handler_domain: string;
  description: string;
  intent_name_patterns?: string[];
  action_patterns?: string[];
  domain_patterns?: string[];
  fallback_conditions?: any[];
  additional_recognition_patterns?: any[];
  language_detection?: any;
  train_keywords?: string[];
  method_donations: DonationMethod[];
  global_parameters?: any[];
  negative_patterns?: any[];
  
  // Legacy field mappings for backward compatibility
  domain?: string; // Maps to handler_domain
  methods?: DonationMethod[]; // Maps to method_donations
}

// Donation metadata - matches backend DonationMetadata schema exactly
export interface DonationListItem {
  handler_name: string;
  domain: string;
  description: string;
  methods_count: number;
  global_parameters_count: number;
  file_size: number;
  last_modified: number; // Unix timestamp
}

// Legacy donation types removed - replaced by language-aware types below

// Schema-related types
export interface JsonSchema {
  $schema?: string;
  type: string;
  properties?: Record<string, any>;
  required?: string[];
  definitions?: Record<string, any>;
  [key: string]: any;
}

// Updated to match backend DonationSchemaResponse schema exactly
export interface SchemaResponse extends BaseApiResponse {
  json_schema: Record<string, any>; // Backend uses "additionalProperties": true
  schema_version: string;
  supported_versions: string[];
}

// Legacy request/response types removed - replaced by language-aware types below

// System status types
export interface SystemStatus {
  status: 'healthy' | 'warning' | 'error';
  component: string;
  message?: string;
  last_updated: string;
  details?: any;
}

// Updated to match backend IntentSystemStatusResponse schema exactly
export interface IntentStatusResponse extends BaseApiResponse {
  status: string;
  handlers_count: number;
  handlers: string[];
  donations_count: number;
  donations: string[];
  registry_patterns: string[];
  donation_routing_enabled: boolean;
  parameter_extraction_integrated: boolean;
  configuration: Record<string, any> | null;
}

// Simplified handlers response (backend /intents/handlers returns basic JSON)
export interface IntentHandlersResponse {
  handlers: Array<{
    name: string;
    type: string;
    enabled: boolean;
    description?: string;
  }>;
  total_count: number;
}

// Updated to match backend IntentReloadResponse schema exactly
export interface ReloadResponse extends BaseApiResponse {
  status: string;
  handlers_count: number;
  handlers: string[];
  error?: string | null;
}

// ============================================================
// LANGUAGE-AWARE DONATION TYPES (Phase 3)
// ============================================================

export interface HandlerLanguageInfo {
  handler_name: string;
  languages: string[];
  total_languages: number;
  supported_languages: string[];
  default_language: string;
}

export interface DonationHandlerListResponse extends BaseApiResponse {
  handlers: HandlerLanguageInfo[];
  total_handlers: number;
}

export interface LanguageDonationMetadata {
  file_path: string;
  language: string;
  file_size: number;
  last_modified: number;
}

export interface CrossLanguageValidation {
  is_consistent: boolean;
  missing_methods: string[];
  extra_methods: string[];
  inconsistent_parameters: string[];
  total_methods: number;
  languages_compared: string[];
}

export interface LanguageDonationContentResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  donation_data: DonationData;
  metadata: LanguageDonationMetadata;
  available_languages: string[];
  cross_language_validation: CrossLanguageValidation;
}

export interface LanguageDonationUpdateRequest {
  donation_data: any;
  validate_before_save: boolean;
  trigger_reload: boolean;
}

export interface LanguageDonationUpdateResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  validation_passed: boolean;
  reload_triggered: boolean;
  backup_created: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

export interface LanguageDonationValidationRequest {
  donation_data: any;
}

export interface LanguageDonationValidationResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  is_valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  validation_types: string[];
}

export interface CreateLanguageRequest {
  copy_from?: string;
  use_template: boolean;
}

export interface CreateLanguageResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  created: boolean;
  copied_from?: string;
}

export interface DeleteLanguageResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  deleted: boolean;
}

export interface ReloadDonationResponse extends BaseApiResponse {
  handler_name: string;
  reloaded: boolean;
  merged_languages: string[];
}

// ============================================================
// Phase 4: Cross-Language Validation Types
// ============================================================

export interface ValidationReport {
  handler_name: string;
  languages_checked: string[];
  parameter_consistency: boolean;
  missing_parameters: string[];
  extra_parameters: string[];
  type_mismatches: string[];
  warnings: string[];
  timestamp: number;
}

export interface CompletenessReport {
  handler_name: string;
  languages_checked: string[];
  method_completeness: boolean;
  missing_methods: string[];
  extra_methods: string[];
  all_methods: string[];
  method_counts_by_language: Record<string, number>;
  warnings: string[];
  timestamp: number;
}

export interface MissingPhraseInfo {
  method_key: string;
  source_phrases: string[];
  target_phrases: string[];
  missing_count: number;
  coverage_ratio: number;
}

export interface TranslationSuggestions {
  handler_name: string;
  source_language: string;
  target_language: string;
  missing_phrases: MissingPhraseInfo[];
  missing_methods: string[];
  confidence_scores: Record<string, number>;
  timestamp: number;
}

export interface CrossLanguageValidationResponse extends BaseApiResponse {
  validation_type: string;
  parameter_report?: ValidationReport;
  completeness_report?: CompletenessReport;
}

export interface SyncParametersRequest {
  source_language: string;
  target_languages: string[];
}

export interface SyncParametersResponse extends BaseApiResponse {
  handler_name: string;
  source_language: string;
  sync_results: Record<string, boolean>;
  updated_languages: string[];
  skipped_languages: string[];
}

export interface SuggestTranslationsRequest {
  source_language: string;
  target_language: string;
}

export interface SuggestTranslationsResponse extends BaseApiResponse {
  suggestions: TranslationSuggestions;
}
