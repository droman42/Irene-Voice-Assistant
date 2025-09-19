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

// ============================================================
// TEMPLATE MANAGEMENT TYPES (Phase 6)
// ============================================================

export interface TemplateMetadata {
  file_path: string;
  language: string;
  file_size: number;
  last_modified: number;
  template_count: number;
}

export interface TemplateContentResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  template_data: Record<string, any>;
  metadata: TemplateMetadata;
  available_languages: string[];
  schema_info: {
    expected_keys: string[];
    key_types: Record<string, string>;
  };
}

export interface TemplateUpdateRequest {
  template_data: Record<string, any>;
  validate_before_save?: boolean;
  trigger_reload?: boolean;
}

export interface TemplateUpdateResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  validation_passed: boolean;
  reload_triggered: boolean;
  backup_created: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

export interface TemplateValidationRequest {
  template_data: Record<string, any>;
}

export interface TemplateValidationResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  is_valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  validation_types: string[];
}

export interface CreateTemplateLanguageRequest {
  copy_from?: string;
  use_template?: boolean;
}

export interface CreateTemplateLanguageResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  created: boolean;
  copied_from?: string;
}

export interface DeleteTemplateLanguageResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  deleted: boolean;
  backup_created: boolean;
}

export interface TemplateHandlerListResponse extends BaseApiResponse {
  handlers: HandlerLanguageInfo[];
  total_handlers: number;
}

// ============================================================
// PROMPT MANAGEMENT TYPES (Phase 7)
// ============================================================

export interface PromptDefinition {
  description: string;
  usage_context: string;
  variables: Array<{ name: string; description: string }>;
  prompt_type: 'system' | 'template' | 'user';
  content: string;
}

export interface PromptMetadata {
  file_path: string;
  language: string;
  file_size: number;
  last_modified: number;
  prompt_count: number;
}

export interface PromptContentResponse extends BaseApiResponse {
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

export interface PromptUpdateRequest {
  prompt_data: Record<string, PromptDefinition>;
  validate_before_save?: boolean;
  trigger_reload?: boolean;
}

export interface PromptUpdateResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  validation_passed: boolean;
  reload_triggered: boolean;
  backup_created: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

export interface PromptValidationRequest {
  prompt_data: Record<string, PromptDefinition>;
}

export interface PromptValidationResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  is_valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  validation_types: string[];
}

export interface CreatePromptLanguageRequest {
  copy_from?: string;
  use_template?: boolean;
}

export interface CreatePromptLanguageResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  created: boolean;
  copied_from?: string;
}

export interface DeletePromptLanguageResponse extends BaseApiResponse {
  handler_name: string;
  language: string;
  deleted: boolean;
  backup_created: boolean;
}

export interface PromptHandlerListResponse extends BaseApiResponse {
  handlers: HandlerLanguageInfo[];
  total_handlers: number;
}

// ============================================================
// LOCALIZATION MANAGEMENT TYPES (Phase 8)
// ============================================================

export interface LocalizationMetadata {
  file_path: string;
  language: string;
  file_size: number;
  last_modified: number;
  entry_count: number;
}

export interface LocalizationContentResponse extends BaseApiResponse {
  domain: string;
  language: string;
  localization_data: Record<string, any>;
  metadata: LocalizationMetadata;
  available_languages: string[];
  schema_info: {
    expected_keys: string[];
    key_types: Record<string, string>;
    domain_description: string;
  };
}

export interface LocalizationUpdateRequest {
  localization_data: Record<string, any>;
  validate_before_save?: boolean;
  trigger_reload?: boolean;
}

export interface LocalizationUpdateResponse extends BaseApiResponse {
  domain: string;
  language: string;
  validation_passed: boolean;
  reload_triggered: boolean;
  backup_created: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

export interface LocalizationValidationRequest {
  localization_data: Record<string, any>;
}

export interface LocalizationValidationResponse extends BaseApiResponse {
  domain: string;
  language: string;
  is_valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  validation_types: string[];
}

export interface CreateLocalizationLanguageRequest {
  copy_from?: string;
  use_template?: boolean;
}

export interface CreateLocalizationLanguageResponse extends BaseApiResponse {
  domain: string;
  language: string;
  created: boolean;
  copied_from?: string;
}

export interface DeleteLocalizationLanguageResponse extends BaseApiResponse {
  domain: string;
  language: string;
  deleted: boolean;
  backup_created: boolean;
}

export interface DomainLanguageInfo {
  domain: string;
  languages: string[];
  total_languages: number;
  supported_languages: string[];
  default_language: string;
}

export interface LocalizationDomainListResponse extends BaseApiResponse {
  domains: DomainLanguageInfo[];
  total_domains: number;
}

// ============================================================
// CONFIGURATION MANAGEMENT TYPES
// ============================================================

// Core configuration interface (matches CoreConfig from backend)
export interface CoreConfig {
  // Core settings
  name: string;
  version: string;
  debug: boolean;
  log_level: string;
  
  // Main configuration sections
  system: SystemConfig;
  inputs: InputConfig;
  components: ComponentConfig;
  assets: AssetConfig;
  workflows: WorkflowConfig;
  
  // Component-specific configurations
  tts: TTSConfig;
  audio: AudioConfig;
  asr: ASRConfig;
  llm: LLMConfig;
  voice_trigger: VoiceTriggerConfig;
  nlu: NLUConfig;
  text_processor: TextProcessorConfig;
  intent_system: IntentSystemConfig;
  vad: VADConfig;
  monitoring: MonitoringConfig;
  
  // Language and locale
  language: string;
  timezone?: string;
  
  // Runtime settings
  max_concurrent_commands: number;
  command_timeout_seconds: number;
  context_timeout_minutes: number;
}

// Configuration section interfaces (matching backend Pydantic models)
export interface SystemConfig {
  microphone_enabled: boolean;
  audio_playback_enabled: boolean;
  web_api_enabled: boolean;
  web_port: number;
}

export interface InputConfig {
  microphone: boolean;
  web: boolean;
  cli: boolean;
  default_input: string;
  microphone_config: MicrophoneInputConfig;
  web_config: WebInputConfig;
  cli_config: CLIInputConfig;
}

export interface MicrophoneInputConfig {
  enabled: boolean;
  device_id?: number;
  sample_rate: number;
  channels: number;
  chunk_size: number;
  buffer_queue_size: number;
  auto_resample: boolean;
  resample_quality: string;
}

export interface WebInputConfig {
  enabled: boolean;
  websocket_enabled: boolean;
  rest_api_enabled: boolean;
}

export interface CLIInputConfig {
  enabled: boolean;
  prompt_prefix: string;
  history_enabled: boolean;
}

export interface ComponentConfig {
  tts: boolean;
  asr: boolean;
  audio: boolean;
  llm: boolean;
  voice_trigger: boolean;
  nlu: boolean;
  text_processor: boolean;
  intent_system: boolean;
  vad: boolean;
  monitoring: boolean;
}

export interface TTSConfig {
  enabled: boolean;
  default_provider?: string;
  fallback_providers: string[];
  providers: Record<string, Record<string, any>>;
}

export interface AudioConfig {
  enabled: boolean;
  default_provider?: string;
  fallback_providers: string[];
  concurrent_playback: boolean;
  providers: Record<string, Record<string, any>>;
}

export interface ASRConfig {
  enabled: boolean;
  default_provider?: string;
  fallback_providers: string[];
  sample_rate?: number;
  channels: number;
  allow_resampling: boolean;
  resample_quality: string;
  providers: Record<string, Record<string, any>>;
}

export interface LLMConfig {
  enabled: boolean;
  default_provider?: string;
  fallback_providers: string[];
  providers: Record<string, Record<string, any>>;
}

export interface VoiceTriggerConfig {
  enabled: boolean;
  default_provider?: string;
  wake_words: string[];
  confidence_threshold: number;
  buffer_seconds: number;
  timeout_seconds: number;
  sample_rate?: number;
  channels: number;
  allow_resampling: boolean;
  resample_quality: string;
  strict_validation: boolean;
  providers: Record<string, Record<string, any>>;
}

export interface NLUConfig {
  enabled: boolean;
  default_provider?: string;
  confidence_threshold: number;
  fallback_intent: string;
  provider_cascade_order: string[];
  max_cascade_attempts: number;
  cascade_timeout_ms: number;
  cache_recognition_results: boolean;
  cache_ttl_seconds: number;
  auto_detect_language: boolean;
  language_detection_confidence_threshold: number;
  persist_language_preference: boolean;
  supported_languages: string[];
  default_language: string;
  providers: Record<string, Record<string, any>>;
}

export interface TextProcessorConfig {
  enabled: boolean;
  stages: string[];
  normalizers: Record<string, Record<string, any>>;
  providers: Record<string, Record<string, any>>;
}

export interface IntentSystemConfig {
  enabled: boolean;
  confidence_threshold: number;
  fallback_intent: string;
  handlers: IntentHandlerListConfig;
  // Handler-specific configurations would be included here
  [key: string]: any;
}

export interface IntentHandlerListConfig {
  enabled: string[];
  disabled: string[];
  auto_discover: boolean;
  discovery_paths: string[];
  asset_validation: Record<string, any>;
}

export interface VADConfig {
  enabled: boolean;
  energy_threshold: number;
  sensitivity: number;
  voice_duration_ms: number;
  silence_duration_ms: number;
  max_segment_duration_s: number;
  voice_frames_required: number;
  silence_frames_required: number;
  use_zero_crossing_rate: boolean;
  adaptive_threshold: boolean;
  noise_percentile: number;
  voice_multiplier: number;
  processing_timeout_ms: number;
  buffer_size_frames: number;
  normalize_for_asr: boolean;
  asr_target_rms: number;
  enable_fallback_to_original: boolean;
}

export interface MonitoringConfig {
  enabled: boolean;
  metrics_enabled: boolean;
  dashboard_enabled: boolean;
  notifications_enabled: boolean;
  debug_tools_enabled: boolean;
  memory_management_enabled: boolean;
  notifications_default_channel: string;
  notifications_tts_enabled: boolean;
  notifications_web_enabled: boolean;
  metrics_monitoring_interval: number;
  metrics_retention_hours: number;
  memory_cleanup_interval: number;
  memory_aggressive_cleanup: boolean;
  debug_auto_inspect_failures: boolean;
  debug_max_history: number;
  analytics_dashboard_enabled: boolean;
  analytics_refresh_interval: number;
}

export interface AssetConfig {
  assets_root: string;
  auto_create_dirs: boolean;
  cleanup_on_startup: boolean;
  auto_download: boolean;
  download_timeout_seconds: number;
  max_download_retries: number;
  verify_downloads: boolean;
  cache_enabled: boolean;
  max_cache_size_mb: number;
  cache_ttl_hours: number;
  preload_essential_models: boolean;
  model_compression: boolean;
  concurrent_downloads: number;
}

export interface WorkflowConfig {
  enabled: string[];
  default: string;
  unified_voice_assistant: UnifiedVoiceAssistantWorkflowConfig;
}

export interface UnifiedVoiceAssistantWorkflowConfig {
  voice_trigger_enabled: boolean;
  asr_enabled: boolean;
  text_processing_enabled: boolean;
  nlu_enabled: boolean;
  intent_execution_enabled: boolean;
  llm_enabled: boolean;
  tts_enabled: boolean;
  audio_enabled: boolean;
  monitoring_enabled: boolean;
  enable_vad_processing: boolean;
}

// Configuration schema metadata (from Pydantic introspection)
export interface ConfigFieldSchema {
  type: string;
  description: string;
  required: boolean;
  default?: any;
  constraints?: Record<string, any>;
  properties?: Record<string, ConfigFieldSchema>; // For nested objects
}

export interface ConfigSectionSchema {
  fields: Record<string, ConfigFieldSchema>;
  title: string;
  description: string;
}

export interface ConfigSchemaResponse {
  [sectionName: string]: ConfigSectionSchema;
}

// Configuration API responses (matching backend schemas)
export interface ConfigUpdateResponse extends BaseApiResponse {
  message: string;
  reload_triggered: boolean;
  backup_created?: string;
}

export interface ConfigValidationResponse extends BaseApiResponse {
  valid: boolean;
  data?: Record<string, any>;
  validation_errors?: ValidationError[];
}

export interface ConfigStatusResponse extends BaseApiResponse {
  config_path?: string;
  config_exists: boolean;
  hot_reload_active: boolean;
  component_initialized: boolean;
  last_modified?: number;
  file_size?: number;
}

export interface ProviderInfo {
  name: string;
  description: string;
  version: string;
  enabled_by_default: boolean;
}

export interface ProvidersResponse {
  [providerName: string]: ProviderInfo;
}
