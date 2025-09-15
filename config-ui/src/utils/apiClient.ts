/**
 * Irene API Client - Centralized API communication for donations management
 * 
 * Provides type-safe API calls to the Irene backend with proper error handling,
 * response validation, and consistent request formatting.
 */

import type {
  ApiError,
  DonationsListResponse,
  DonationResponse,
  SchemaResponse,
  UpdateDonationRequest,
  UpdateDonationResponse,
  ValidateDonationRequest,
  ValidateDonationResponse,
  IntentStatusResponse,
  IntentHandlersResponse,
  ReloadResponse,
  DonationData
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

  // ============================================================
  // DONATIONS API METHODS
  // ============================================================

  /**
   * Get list of all donations with metadata
   */
  async getDonations(): Promise<DonationsListResponse> {
    return this.get<DonationsListResponse>('/intents/donations');
  }

  /**
   * Get specific donation content
   */
  async getDonation(handlerName: string): Promise<DonationResponse> {
    return this.get<DonationResponse>(`/intents/donations/${encodeURIComponent(handlerName)}`);
  }

  /**
   * Update donation content with optional validation and reload
   */
  async updateDonation(
    handlerName: string, 
    donationData: DonationData, 
    options: {
      validateBeforeSave?: boolean;
      triggerReload?: boolean;
    } = {}
  ): Promise<UpdateDonationResponse> {
    const requestData: UpdateDonationRequest = {
      donation_data: donationData,
      validate_before_save: options.validateBeforeSave !== false, // Default to true
      trigger_reload: options.triggerReload !== false, // Default to true
    };

    return this.put<UpdateDonationResponse>(
      `/intents/donations/${encodeURIComponent(handlerName)}`, 
      requestData
    );
  }

  /**
   * Validate donation data without saving (dry-run)
   */
  async validateDonation(handlerName: string, donationData: DonationData): Promise<ValidateDonationResponse> {
    const requestData: ValidateDonationRequest = {
      donation_data: donationData,
      handler_name: handlerName,
    };

    return this.post<ValidateDonationResponse>(
      `/intents/donations/${encodeURIComponent(handlerName)}/validate`, 
      requestData
    );
  }

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
}

// Create and export a default instance
const apiClient = new IreneApiClient();
export default apiClient;

// Also export the class for custom instances
export { IreneApiClient };
