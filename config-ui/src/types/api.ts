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

// Updated to match backend DonationContentResponse schema exactly
export interface DonationResponse extends BaseApiResponse {
  handler_name: string;
  donation_data: Record<string, any>; // Backend uses "additionalProperties": true
  metadata: DonationListItem; // Backend refs DonationMetadata
}

// Updated to match backend DonationListResponse schema exactly  
export interface DonationsListResponse extends BaseApiResponse {
  donations: DonationListItem[];
  total_count: number;
}

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
  schema: Record<string, any>; // Backend uses "additionalProperties": true
  schema_version: string;
  supported_versions: string[];
}

// Update request types - match backend schemas exactly
export interface UpdateDonationRequest {
  donation_data: Record<string, any>; // Backend uses "additionalProperties": true
  validate_before_save?: boolean; // default: true
  trigger_reload?: boolean; // default: true
}

export interface ValidateDonationRequest {
  donation_data: Record<string, any>; // Backend uses "additionalProperties": true
  handler_name: string;
}

// Update response types - match backend schemas exactly
export interface UpdateDonationResponse extends BaseApiResponse {
  handler_name: string;
  validation_passed: boolean;
  reload_triggered: boolean;
  backup_created: boolean;
  errors: ValidationError[]; // default: []
  warnings: ValidationWarning[]; // default: []
}

export interface ValidateDonationResponse extends BaseApiResponse {
  handler_name: string;
  is_valid: boolean;
  errors: ValidationError[]; // default: []
  warnings: ValidationWarning[]; // default: []
  validation_types: string[];
}

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
