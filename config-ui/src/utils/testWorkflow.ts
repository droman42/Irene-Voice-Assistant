/**
 * Test Workflow Utilities
 * 
 * Helper functions to validate the donation editing workflow
 * and ensure all components work together properly.
 */

import apiClient from '@/utils/apiClient';
import type { DonationData, ValidationResult } from '@/types';

interface TestResult {
  name: string;
  status: 'running' | 'passed' | 'failed';
  error?: string;
  duration?: number;
}

interface WorkflowTestResults {
  success: boolean;
  tests: TestResult[];
  errors: string[];
  totalDuration?: number;
}

/**
 * Test the complete donation editing workflow
 */
export async function testDonationWorkflow(): Promise<WorkflowTestResults> {
  const startTime = Date.now();
  const results: WorkflowTestResults = {
    success: true,
    tests: [],
    errors: []
  };

  try {
    // Test 1: API Connection
    results.tests.push({ name: 'API Connection', status: 'running' });
    const testStart = Date.now();
    const connected = await apiClient.checkConnection();
    if (connected) {
      results.tests[0].status = 'passed';
      results.tests[0].duration = Date.now() - testStart;
    } else {
      results.tests[0].status = 'failed';
      results.tests[0].error = 'Cannot connect to API';
      results.success = false;
    }

    // Test 2: Schema Loading
    results.tests.push({ name: 'Schema Loading', status: 'running' });
    const schemaStart = Date.now();
    try {
      const schemaResponse = await apiClient.getDonationSchema();
      if (schemaResponse.json_schema && typeof schemaResponse.json_schema === 'object') {
        results.tests[1].status = 'passed';
        results.tests[1].duration = Date.now() - schemaStart;
      } else {
        results.tests[1].status = 'failed';
        results.tests[1].error = 'Invalid schema format';
        results.success = false;
      }
    } catch (error) {
      results.tests[1].status = 'failed';
      results.tests[1].error = error instanceof Error ? error.message : 'Schema loading failed';
      results.success = false;
    }

    // Test 3: Handlers List Loading (Language-Aware)
    results.tests.push({ name: 'Handlers List Loading', status: 'running' });
    const listStart = Date.now();
    try {
      const handlersResponse = await apiClient.getDonationHandlers();
      if (handlersResponse.handlers && Array.isArray(handlersResponse.handlers)) {
        results.tests[2].status = 'passed';
        results.tests[2].duration = Date.now() - listStart;
      } else {
        results.tests[2].status = 'failed';
        results.tests[2].error = 'Invalid handlers list format';
        results.success = false;
      }
    } catch (error) {
      results.tests[2].status = 'failed';
      results.tests[2].error = error instanceof Error ? error.message : 'Handlers list loading failed';
      results.success = false;
    }

    // Test 4: Language-Specific Donation Loading (if handlers exist)
    const handlersResponse = await apiClient.getDonationHandlers();
    if (handlersResponse.handlers.length > 0) {
      const firstHandler = handlersResponse.handlers[0];
      const testLanguage = firstHandler.languages[0] || 'en'; // Use first available language
      
      results.tests.push({ name: 'Language-Specific Donation Loading', status: 'running' });
      const donationStart = Date.now();
      
      try {
        const donationResponse = await apiClient.getLanguageDonation(firstHandler.handler_name, testLanguage);
        if (donationResponse.donation_data && donationResponse.handler_name && donationResponse.language) {
          results.tests[3].status = 'passed';
          results.tests[3].duration = Date.now() - donationStart;
        } else {
          results.tests[3].status = 'failed';
          results.tests[3].error = 'Invalid language donation data format';
          results.success = false;
        }
      } catch (error) {
        results.tests[3].status = 'failed';
        results.tests[3].error = error instanceof Error ? error.message : 'Language donation loading failed';
        results.success = false;
      }

      // Test 5: Language-Specific Validation (dry-run)
      results.tests.push({ name: 'Language Validation Test', status: 'running' });
      const validationStart = Date.now();
      
      try {
        const donationResponse = await apiClient.getLanguageDonation(firstHandler.handler_name, testLanguage);
        const validationResponse = await apiClient.validateLanguageDonation(
          firstHandler.handler_name,
          testLanguage,
          donationResponse.donation_data
        );
        
        if (validationResponse.is_valid !== undefined && typeof validationResponse.is_valid === 'boolean') {
          results.tests[4].status = 'passed';
          results.tests[4].duration = Date.now() - validationStart;
        } else {
          results.tests[4].status = 'failed';
          results.tests[4].error = 'Invalid validation response format';
          results.success = false;
        }
      } catch (error) {
        results.tests[4].status = 'failed';
        results.tests[4].error = error instanceof Error ? error.message : 'Validation test failed';
        results.success = false;
      }
    }

  } catch (error) {
    results.success = false;
    results.errors.push(error instanceof Error ? error.message : 'Unknown workflow error');
  }

  results.totalDuration = Date.now() - startTime;
  return results;
}

/**
 * Validate donation data format
 */
export function validateDonationFormat(data: any): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!data || typeof data !== 'object') {
    errors.push('Donation data must be an object');
    return { valid: false, errors };
  }

  if (!data.description || typeof data.description !== 'string') {
    errors.push('Description is required and must be a string');
  }

  if (!data.domain || typeof data.domain !== 'string') {
    errors.push('Domain is required and must be a string');
  }

  if (!data.methods || !Array.isArray(data.methods)) {
    errors.push('Methods is required and must be an array');
  } else {
    data.methods.forEach((method: any, index: number) => {
      if (!method || typeof method !== 'object') {
        errors.push(`Method ${index} must be an object`);
        return;
      }
      
      if (!method.name || typeof method.name !== 'string') {
        errors.push(`Method ${index} must have a name`);
      }

      // Validate optional arrays
      const arrayFields = ['global_params', 'token_patterns', 'slot_patterns', 'examples'];
      arrayFields.forEach(field => {
        if (method[field] && !Array.isArray(method[field])) {
          errors.push(`Method ${index} ${field} must be an array if provided`);
        }
      });
    });
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Generate test donation data for validation
 */
export function generateTestDonation(): DonationData {
  return {
    handler_domain: "test",
    description: "Test donation for workflow validation",
    method_donations: [
      {
        method_name: "test_method",
        intent_suffix: "test_method",
        description: "Test method for validation workflow",
        global_params: ["param1", "param2"],
        token_patterns: [[{ "LOWER": "test" }, { "LOWER": "pattern" }]],
        slot_patterns: { "param1": [[{ "LOWER": "test" }]] },
        examples: ["test example with param1 and param2"]
      }
    ]
  };
}

/**
 * Check if validation result has errors
 */
export function hasValidationErrors(result: ValidationResult): boolean {
  return !result.valid || (result.errors && result.errors.length > 0);
}

/**
 * Format validation errors for display
 */
export function formatValidationErrors(result: ValidationResult): string[] {
  const messages: string[] = [];
  
  if (result.errors) {
    messages.push(...result.errors);
  }
  
  if (result.warnings) {
    messages.push(...result.warnings.map(w => `Warning: ${w}`));
  }
  
  return messages;
}

/**
 * Test API endpoint connectivity
 */
export async function testApiEndpoints(): Promise<Record<string, boolean>> {
  const endpoints = {
    status: '/intents/status',
    donations: '/intents/donations',
    schema: '/intents/schema',
    handlers: '/intents/handlers'
  };

  const results: Record<string, boolean> = {};

  for (const [name, endpoint] of Object.entries(endpoints)) {
    try {
      await apiClient.get(endpoint);
      results[name] = true;
    } catch (error) {
      results[name] = false;
      console.warn(`Endpoint ${endpoint} failed:`, error);
    }
  }

  return results;
}
