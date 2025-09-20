/**
 * useValidationWorkflow Hook - Enhanced validation workflow with blocking gates
 * 
 * Provides comprehensive pre-save validation with blocking conflict detection,
 * warning handling, and smart validation gates for the donation saving workflow.
 */

import { useState, useCallback } from 'react';
import apiClient from '@/utils/apiClient';
import type { NLUValidationResult, DonationData, ConflictReport } from '@/types';

interface UseValidationWorkflowOptions {
  onValidationComplete?: (result: NLUValidationResult) => void;
  onValidationError?: (error: string) => void;
}

interface UseValidationWorkflowReturn {
  validationResult: NLUValidationResult | null;
  isValidating: boolean;
  validationError: string | null;
  validateForSaving: (handlerName: string, language: string, donationData: DonationData) => Promise<NLUValidationResult>;
  canSave: boolean;
  hasBlockingConflicts: boolean;
  hasWarnings: boolean;
  blockingConflicts: ConflictReport[];
  warningConflicts: ConflictReport[];
  clearValidation: () => void;
}

const useValidationWorkflow = (
  options: UseValidationWorkflowOptions = {}
): UseValidationWorkflowReturn => {
  const { onValidationComplete, onValidationError } = options;

  // State
  const [validationResult, setValidationResult] = useState<NLUValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Perform validation
  const validateForSaving = useCallback(async (
    handlerName: string,
    language: string,
    donationData: DonationData
  ): Promise<NLUValidationResult> => {
    setIsValidating(true);
    setValidationError(null);

    try {
      const result = await apiClient.validateDonation(handlerName, language, donationData);
      
      setValidationResult(result);
      
      if (onValidationComplete) {
        onValidationComplete(result);
      }

      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Validation failed';
      setValidationError(errorMessage);
      
      if (onValidationError) {
        onValidationError(errorMessage);
      }

      // Return a failed validation result
      const failedResult: NLUValidationResult = {
        success: false,
        timestamp: Date.now(),
        is_valid: false,
        has_blocking_conflicts: true,
        has_warnings: false,
        conflicts: [],
        suggestions: ['Validation service unavailable - please try again'],
        validation_time_ms: 0
      };

      setValidationResult(failedResult);
      return failedResult;
    } finally {
      setIsValidating(false);
    }
  }, [onValidationComplete, onValidationError]);

  // Clear validation state
  const clearValidation = useCallback(() => {
    setValidationResult(null);
    setValidationError(null);
    setIsValidating(false);
  }, []);

  // Derived state
  const hasBlockingConflicts = validationResult?.has_blocking_conflicts || false;
  const hasWarnings = validationResult?.has_warnings || false;
  const canSave = validationResult?.is_valid && !hasBlockingConflicts;

  const blockingConflicts = validationResult?.conflicts.filter(c => c.severity === 'blocker') || [];
  const warningConflicts = validationResult?.conflicts.filter(c => c.severity === 'warning') || [];

  return {
    validationResult,
    isValidating,
    validationError,
    validateForSaving,
    canSave: canSave || false,
    hasBlockingConflicts,
    hasWarnings,
    blockingConflicts,
    warningConflicts,
    clearValidation
  };
};

export default useValidationWorkflow;
