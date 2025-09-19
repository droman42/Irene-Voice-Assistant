/**
 * Irene API Client - Centralized API communication for donations management
 * 
 * Provides type-safe API calls to the Irene backend with proper error handling,
 * response validation, and consistent request formatting.
 */

import type {
  ApiError,
  SchemaResponse,
  IntentStatusResponse,
  IntentHandlersResponse,
  ReloadResponse,
  // Language-aware donation types
  DonationHandlerListResponse,
  LanguageDonationContentResponse,
  LanguageDonationUpdateRequest,
  LanguageDonationUpdateResponse,
  LanguageDonationValidationRequest,
  LanguageDonationValidationResponse,
  CreateLanguageRequest,
  CreateLanguageResponse,
  DeleteLanguageResponse,
  ReloadDonationResponse,
  // Phase 4: Cross-language validation types
  CrossLanguageValidationResponse,
  SyncParametersRequest,
  SyncParametersResponse,
  SuggestTranslationsRequest,
  SuggestTranslationsResponse,
  // Phase 6: Template management types
  TemplateHandlerListResponse,
  TemplateContentResponse,
  TemplateUpdateRequest,
  TemplateUpdateResponse,
  TemplateValidationRequest,
  TemplateValidationResponse,
  CreateTemplateLanguageRequest,
  CreateTemplateLanguageResponse,
  DeleteTemplateLanguageResponse,
  // Prompt management types (Phase 7)
  PromptHandlerListResponse,
  PromptContentResponse,
  PromptDefinition,
  PromptUpdateRequest,
  PromptUpdateResponse,
  PromptValidationRequest,
  PromptValidationResponse,
  CreatePromptLanguageRequest,
  CreatePromptLanguageResponse,
  DeletePromptLanguageResponse,
  // Localization types
  LocalizationDomainListResponse,
  LocalizationContentResponse,
  LocalizationUpdateRequest,
  LocalizationUpdateResponse,
  LocalizationValidationRequest,
  LocalizationValidationResponse,
  CreateLocalizationLanguageRequest,
  CreateLocalizationLanguageResponse,
  DeleteLocalizationLanguageResponse,
  // Configuration management types
  CoreConfig,
  ConfigSchemaResponse,
  ConfigUpdateResponse,
  ConfigValidationResponse,
  ConfigStatusResponse,
  ProvidersResponse,
  AudioDevicesResponse,
  // Raw TOML types (Phase 5)
  RawTomlRequest,
  RawTomlResponse,
  RawTomlSaveResponse,
  RawTomlValidationRequest,
  RawTomlValidationResponse,
  SectionToTomlRequest,
  SectionToTomlResponse
} from '@/types';

interface RequestOptions extends RequestInit {
  headers?: Record<string, string>;
}

class IreneApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  /**
   * Make a generic API request with error handling
   */
  async request<T = any>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const defaultOptions: RequestOptions = {
      headers: {
        'Content-Type': 'application/json',
      },
    };

    const finalOptions: RequestOptions = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, finalOptions);

      // Handle non-OK responses
      if (!response.ok) {
        let errorMessage = `API Error: ${response.status} ${response.statusText}`;
        
        try {
          const errorData: ApiError = await response.json();
          if (errorData.error) {
            errorMessage = errorData.error;
          }
        } catch (e) {
          // If we can't parse error JSON, use the status text
        }
        
        throw new Error(errorMessage);
      }

      // Parse and return JSON response
      const data: T = await response.json();
      return data;
    } catch (error) {
      // Re-throw with context if it's a fetch error
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error(`Failed to connect to Irene API at ${this.baseUrl}: ${error.message}`);
      }
      throw error;
    }
  }

  /**
   * Make a GET request
   */
  async get<T = any>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  /**
   * Make a POST request
   */
  async post<T = any>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * Make a PUT request
   */
  async put<T = any>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  /**
   * Make a DELETE request
   */
  async delete<T = any>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'DELETE',
    });
  }

  // ============================================================
  // SYSTEM METHODS
  // ============================================================

  /**
   * Get donation JSON schema for validation
   */
  async getDonationSchema(): Promise<SchemaResponse> {
    return this.get<SchemaResponse>('/intents/schema');
  }

  /**
   * Trigger intent system reload
   */
  async reloadIntentSystem(): Promise<ReloadResponse> {
    return this.post<ReloadResponse>('/intents/reload', {});
  }

  // ============================================================
  // LANGUAGE-AWARE DONATION METHODS
  // ============================================================

  /**
   * List all handlers with language information
   */
  async getDonationHandlers(): Promise<DonationHandlerListResponse> {
    return this.get<DonationHandlerListResponse>('/intents/donations');
  }

  /**
   * Get available languages for a handler
   */
  async getHandlerLanguages(handlerName: string): Promise<string[]> {
    return this.get<string[]>(`/intents/donations/${encodeURIComponent(handlerName)}/languages`);
  }

  /**
   * Get language-specific donation content for editing
   */
  async getLanguageDonation(handlerName: string, language: string): Promise<LanguageDonationContentResponse> {
    return this.get<LanguageDonationContentResponse>(
      `/intents/donations/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}`
    );
  }

  /**
   * Update language-specific donation
   */
  async updateLanguageDonation(
    handlerName: string, 
    language: string, 
    donationData: any,
    options: {
      validateBeforeSave?: boolean;
      triggerReload?: boolean;
    } = {}
  ): Promise<LanguageDonationUpdateResponse> {
    const requestData: LanguageDonationUpdateRequest = {
      donation_data: donationData,
      validate_before_save: options.validateBeforeSave ?? true,
      trigger_reload: options.triggerReload ?? true,
    };

    return this.put<LanguageDonationUpdateResponse>(
      `/intents/donations/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}`,
      requestData
    );
  }

  /**
   * Validate language-specific donation without saving
   */
  async validateLanguageDonation(
    handlerName: string, 
    language: string, 
    donationData: any
  ): Promise<LanguageDonationValidationResponse> {
    const requestData: LanguageDonationValidationRequest = {
      donation_data: donationData,
    };

    return this.post<LanguageDonationValidationResponse>(
      `/intents/donations/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}/validate`,
      requestData
    );
  }

  /**
   * Create a new language file for a handler
   */
  async createLanguage(
    handlerName: string, 
    language: string, 
    options: {
      copyFrom?: string;
      useTemplate?: boolean;
    } = {}
  ): Promise<CreateLanguageResponse> {
    const requestData: CreateLanguageRequest = {
      copy_from: options.copyFrom,
      use_template: options.useTemplate ?? false,
    };

    return this.post<CreateLanguageResponse>(
      `/intents/donations/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}/create`,
      requestData
    );
  }

  /**
   * Delete a language file for a handler
   */
  async deleteLanguage(handlerName: string, language: string): Promise<DeleteLanguageResponse> {
    return this.delete<DeleteLanguageResponse>(
      `/intents/donations/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}`
    );
  }

  /**
   * Trigger unified donation reload for a handler
   */
  async reloadHandlerDonation(handlerName: string): Promise<ReloadDonationResponse> {
    return this.post<ReloadDonationResponse>(
      `/intents/donations/${encodeURIComponent(handlerName)}/reload`,
      {}
    );
  }

  // ============================================================
  // PHASE 4: CROSS-LANGUAGE VALIDATION METHODS
  // ============================================================

  /**
   * Get cross-language validation report for a handler
   */
  async getCrossLanguageValidation(handlerName: string): Promise<CrossLanguageValidationResponse> {
    return this.get<CrossLanguageValidationResponse>(
      `/intents/donations/${encodeURIComponent(handlerName)}/cross-validation`
    );
  }

  /**
   * Sync parameter structures across languages
   */
  async syncParameters(
    handlerName: string,
    sourceLanguage: string,
    targetLanguages: string[]
  ): Promise<SyncParametersResponse> {
    const requestData: SyncParametersRequest = {
      source_language: sourceLanguage,
      target_languages: targetLanguages,
    };

    return this.post<SyncParametersResponse>(
      `/intents/donations/${encodeURIComponent(handlerName)}/sync-parameters`,
      requestData
    );
  }

  /**
   * Get translation suggestions for missing phrases
   */
  async suggestTranslations(
    handlerName: string,
    sourceLanguage: string,
    targetLanguage: string
  ): Promise<SuggestTranslationsResponse> {
    const requestData: SuggestTranslationsRequest = {
      source_language: sourceLanguage,
      target_language: targetLanguage,
    };

    return this.post<SuggestTranslationsResponse>(
      `/intents/donations/${encodeURIComponent(handlerName)}/suggest-translations`,
      requestData
    );
  }

  // ============================================================
  // SYSTEM STATUS METHODS
  // ============================================================

  /**
   * Get intent system status
   */
  async getIntentStatus(): Promise<IntentStatusResponse> {
    return this.get<IntentStatusResponse>('/intents/status');
  }

  /**
   * Get available intent handlers
   */
  async getIntentHandlers(): Promise<IntentHandlersResponse> {
    return this.get<IntentHandlersResponse>('/intents/handlers');
  }

  /**
   * Check if API is reachable and system is healthy
   */
  async checkConnection(): Promise<boolean> {
    try {
      await this.getIntentStatus();
      return true;
    } catch (error) {
      console.warn('API connection check failed:', error instanceof Error ? error.message : String(error));
      return false;
    }
  }

  // ============================================================
  // TEMPLATE MANAGEMENT API (Phase 6)
  // ============================================================

  /**
   * Get all handlers with template language info
   */
  async getTemplateHandlers(): Promise<TemplateHandlerListResponse> {
    return this.get<TemplateHandlerListResponse>('/intents/templates');
  }

  /**
   * Get available languages for a handler's templates
   */
  async getTemplateHandlerLanguages(handlerName: string): Promise<string[]> {
    return this.get<string[]>(`/intents/templates/${encodeURIComponent(handlerName)}/languages`);
  }

  /**
   * Get language-specific template content
   */
  async getLanguageTemplate(handlerName: string, language: string): Promise<TemplateContentResponse> {
    return this.get<TemplateContentResponse>(
      `/intents/templates/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}`
    );
  }

  /**
   * Update language-specific template
   */
  async updateLanguageTemplate(
    handlerName: string, 
    language: string, 
    templateData: Record<string, any>,
    options: {
      validateBeforeSave?: boolean;
      triggerReload?: boolean;
    } = {}
  ): Promise<TemplateUpdateResponse> {
    const requestData: TemplateUpdateRequest = {
      template_data: templateData,
      validate_before_save: options.validateBeforeSave ?? true,
      trigger_reload: options.triggerReload ?? true
    };

    return this.put<TemplateUpdateResponse>(
      `/intents/templates/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}`,
      requestData
    );
  }

  /**
   * Validate language-specific template without saving
   */
  async validateLanguageTemplate(
    handlerName: string, 
    language: string, 
    templateData: Record<string, any>
  ): Promise<TemplateValidationResponse> {
    const requestData: TemplateValidationRequest = {
      template_data: templateData
    };

    return this.post<TemplateValidationResponse>(
      `/intents/templates/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}/validate`,
      requestData
    );
  }

  /**
   * Delete language-specific template file
   */
  async deleteTemplateLanguage(handlerName: string, language: string): Promise<DeleteTemplateLanguageResponse> {
    return this.delete<DeleteTemplateLanguageResponse>(
      `/intents/templates/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}`
    );
  }

  /**
   * Create new language file for template
   */
  async createTemplateLanguage(
    handlerName: string, 
    language: string, 
    options: {
      copyFrom?: string;
      useTemplate?: boolean;
    } = {}
  ): Promise<CreateTemplateLanguageResponse> {
    const requestData: CreateTemplateLanguageRequest = {
      copy_from: options.copyFrom,
      use_template: options.useTemplate ?? false
    };

    return this.post<CreateTemplateLanguageResponse>(
      `/intents/templates/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}`,
      requestData
    );
  }

  // ============================================================
  // PROMPT MANAGEMENT API (Phase 7)
  // ============================================================

  /**
   * Get all handlers with prompt language info
   */
  async getPromptHandlers(): Promise<PromptHandlerListResponse> {
    return this.get<PromptHandlerListResponse>('/intents/prompts');
  }

  /**
   * Get available languages for a handler's prompts
   */
  async getPromptHandlerLanguages(handlerName: string): Promise<string[]> {
    return this.get<string[]>(`/intents/prompts/${encodeURIComponent(handlerName)}/languages`);
  }

  /**
   * Get language-specific prompt content
   */
  async getLanguagePrompt(handlerName: string, language: string): Promise<PromptContentResponse> {
    return this.get<PromptContentResponse>(
      `/intents/prompts/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}`
    );
  }

  /**
   * Update language-specific prompt
   */
  async updateLanguagePrompt(
    handlerName: string, 
    language: string, 
    promptData: Record<string, PromptDefinition>,
    options: {
      validateBeforeSave?: boolean;
      triggerReload?: boolean;
    } = {}
  ): Promise<PromptUpdateResponse> {
    const requestData: PromptUpdateRequest = {
      prompt_data: promptData,
      validate_before_save: options.validateBeforeSave ?? true,
      trigger_reload: options.triggerReload ?? true
    };

    return this.put<PromptUpdateResponse>(
      `/intents/prompts/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}`,
      requestData
    );
  }

  /**
   * Validate language-specific prompt without saving
   */
  async validateLanguagePrompt(
    handlerName: string, 
    language: string, 
    promptData: Record<string, PromptDefinition>
  ): Promise<PromptValidationResponse> {
    const requestData: PromptValidationRequest = {
      prompt_data: promptData
    };

    return this.post<PromptValidationResponse>(
      `/intents/prompts/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}/validate`,
      requestData
    );
  }

  /**
   * Delete language-specific prompt file
   */
  async deletePromptLanguage(handlerName: string, language: string): Promise<DeletePromptLanguageResponse> {
    return this.delete<DeletePromptLanguageResponse>(
      `/intents/prompts/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}`
    );
  }

  /**
   * Create new language file for prompt
   */
  async createPromptLanguage(
    handlerName: string, 
    language: string, 
    options: {
      copyFrom?: string;
      useTemplate?: boolean;
    } = {}
  ): Promise<CreatePromptLanguageResponse> {
    const requestData: CreatePromptLanguageRequest = {
      copy_from: options.copyFrom,
      use_template: options.useTemplate ?? false
    };

    return this.post<CreatePromptLanguageResponse>(
      `/intents/prompts/${encodeURIComponent(handlerName)}/${encodeURIComponent(language)}`,
      requestData
    );
  }

  // ============================================================
  // CONFIGURATION MANAGEMENT API 
  // ============================================================

  /**
   * Get complete TOML configuration
   */
  async getConfig(): Promise<CoreConfig> {
    return this.get<CoreConfig>('/configuration/config');
  }

  /**
   * Get configuration schema for all sections
   */
  async getConfigSchema(): Promise<ConfigSchemaResponse> {
    return this.get<ConfigSchemaResponse>('/configuration/config/schema');
  }

  /**
   * Get specific section schema
   */
  async getSectionSchema(sectionName: string): Promise<ConfigSchemaResponse> {
    return this.get<ConfigSchemaResponse>(`/configuration/config/schema/${encodeURIComponent(sectionName)}`);
  }

  /**
   * Update specific configuration section
   */
  async updateConfigSection(sectionName: string, data: any): Promise<ConfigUpdateResponse> {
    return this.put<ConfigUpdateResponse>(`/configuration/config/sections/${encodeURIComponent(sectionName)}`, data);
  }

  /**
   * Validate configuration section without saving
   */
  async validateConfigSection(sectionName: string, data: any): Promise<ConfigValidationResponse> {
    return this.post<ConfigValidationResponse>(`/configuration/config/sections/${encodeURIComponent(sectionName)}/validate`, data);
  }

  /**
   * Get available providers for a component
   */
  async getAvailableProviders(componentName: string): Promise<ProvidersResponse> {
    return this.get<ProvidersResponse>(`/configuration/config/providers/${encodeURIComponent(componentName)}`);
  }

  /**
   * Get available audio input devices for microphone configuration
   */
  async getAvailableAudioDevices(): Promise<AudioDevicesResponse> {
    return this.get<AudioDevicesResponse>('/configuration/config/audio/devices');
  }

  /**
   * Get configuration system status
   */
  async getConfigStatus(): Promise<ConfigStatusResponse> {
    return this.get<ConfigStatusResponse>('/configuration/config/status');
  }

  // ============================================================
  // RAW TOML CONFIGURATION METHODS (Phase 5)
  // ============================================================

  /**
   * Get raw TOML configuration content with comments preserved
   */
  async getRawToml(): Promise<RawTomlResponse> {
    try {
      return await this.get<RawTomlResponse>('/configuration/config/raw');
    } catch (error) {
      console.error('Failed to fetch raw TOML content:', error);
      throw new Error('Unable to load TOML configuration. Please check your connection and try again.');
    }
  }

  /**
   * Save raw TOML content with comment preservation
   */
  async saveRawToml(tomlContent: string, validateBeforeSave: boolean = true): Promise<RawTomlSaveResponse> {
    try {
      const requestData: RawTomlRequest = {
        toml_content: tomlContent,
        validate_before_save: validateBeforeSave
      };
      return await this.put<RawTomlSaveResponse>('/configuration/config/raw', requestData);
    } catch (error) {
      console.error('Failed to save TOML content:', error);
      // Try to extract validation errors from response
      if (error instanceof Error && error.message.includes('validation failed')) {
        throw new Error('Configuration validation failed. Please check your settings and try again.');
      }
      throw new Error('Unable to save TOML configuration. Please check your settings and try again.');
    }
  }

  /**
   * Validate raw TOML content without saving
   */
  async validateRawToml(tomlContent: string): Promise<RawTomlValidationResponse> {
    try {
      const requestData: RawTomlValidationRequest = {
        toml_content: tomlContent
      };
      return await this.post<RawTomlValidationResponse>('/configuration/config/raw/validate', requestData);
    } catch (error) {
      console.error('Failed to validate TOML content:', error);
      // Return a failed validation response instead of throwing
      return {
        success: false,
        timestamp: Date.now(),
        valid: false,
        errors: [{ 
          msg: error instanceof Error ? error.message : 'Validation service unavailable', 
          type: 'network_error' 
        }]
      };
    }
  }

  /**
   * Apply section changes to raw TOML while preserving comments
   */
  async applySectionToToml(sectionName: string, sectionData: any): Promise<SectionToTomlResponse> {
    try {
      const requestData: SectionToTomlRequest = {
        section_data: sectionData
      };
      return await this.post<SectionToTomlResponse>(
        `/configuration/config/sections/${encodeURIComponent(sectionName)}/toml`, 
        requestData
      );
    } catch (error) {
      console.error(`Failed to apply section '${sectionName}' to TOML:`, error);
      throw new Error(`Unable to update section '${sectionName}' with comment preservation. Falling back to standard update.`);
    }
  }

  // ========================================
  // LOCALIZATION MANAGEMENT METHODS (Phase 8)
  // ========================================

  /**
   * Get all domains with their available languages
   */
  async getLocalizationDomains(): Promise<LocalizationDomainListResponse> {
    return this.get<LocalizationDomainListResponse>('/intents/localizations');
  }

  /**
   * Get available languages for a domain
   */
  async getLocalizationDomainLanguages(domain: string): Promise<string[]> {
    return this.get<string[]>(`/intents/localizations/${encodeURIComponent(domain)}/languages`);
  }

  /**
   * Get language-specific localization content
   */
  async getLanguageLocalization(domain: string, language: string): Promise<LocalizationContentResponse> {
    return this.get<LocalizationContentResponse>(
      `/intents/localizations/${encodeURIComponent(domain)}/${encodeURIComponent(language)}`
    );
  }

  /**
   * Update language-specific localization
   */
  async updateLanguageLocalization(
    domain: string, 
    language: string, 
    localizationData: Record<string, any>,
    options: {
      validateBeforeSave?: boolean;
      triggerReload?: boolean;
    } = {}
  ): Promise<LocalizationUpdateResponse> {
    const requestData: LocalizationUpdateRequest = {
      localization_data: localizationData,
      validate_before_save: options.validateBeforeSave ?? true,
      trigger_reload: options.triggerReload ?? true
    };

    return this.put<LocalizationUpdateResponse>(
      `/intents/localizations/${encodeURIComponent(domain)}/${encodeURIComponent(language)}`,
      requestData
    );
  }

  /**
   * Validate language-specific localization without saving
   */
  async validateLanguageLocalization(
    domain: string, 
    language: string, 
    localizationData: Record<string, any>
  ): Promise<LocalizationValidationResponse> {
    const requestData: LocalizationValidationRequest = {
      localization_data: localizationData
    };

    return this.post<LocalizationValidationResponse>(
      `/intents/localizations/${encodeURIComponent(domain)}/${encodeURIComponent(language)}/validate`,
      requestData
    );
  }

  /**
   * Delete language-specific localization file
   */
  async deleteLocalizationLanguage(domain: string, language: string): Promise<DeleteLocalizationLanguageResponse> {
    return this.delete<DeleteLocalizationLanguageResponse>(
      `/intents/localizations/${encodeURIComponent(domain)}/${encodeURIComponent(language)}`
    );
  }

  /**
   * Create new language file for localization
   */
  async createLocalizationLanguage(
    domain: string, 
    language: string, 
    options: {
      copyFrom?: string;
      useTemplate?: boolean;
    } = {}
  ): Promise<CreateLocalizationLanguageResponse> {
    const requestData: CreateLocalizationLanguageRequest = {
      copy_from: options.copyFrom,
      use_template: options.useTemplate ?? false
    };

    return this.post<CreateLocalizationLanguageResponse>(
      `/intents/localizations/${encodeURIComponent(domain)}/${encodeURIComponent(language)}`,
      requestData
    );
  }
}

// Create and export a default instance
const apiClient = new IreneApiClient();
export default apiClient;

// Also export the class for custom instances
export { IreneApiClient };
