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
  DeletePromptLanguageResponse
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
}

// Create and export a default instance
const apiClient = new IreneApiClient();
export default apiClient;

// Also export the class for custom instances
export { IreneApiClient };
