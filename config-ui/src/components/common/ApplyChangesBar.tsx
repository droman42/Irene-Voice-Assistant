/**
 * ApplyChangesBar Component - Save workflow controls
 * 
 * Provides validation and save controls for unsaved changes across all pages,
 * with visual feedback and error handling.
 */

import { useState } from 'react';
import { 
  Save, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  Eye,
  X,
  AlertTriangle
} from 'lucide-react';
import type { ApplyChangesBarProps, ValidationResult } from '@/types';
import { useValidationWorkflow } from '@/hooks';
import { ValidationIndicator, BlockingConflictsDialog } from '@/components/analysis';

const ApplyChangesBar: React.FC<ApplyChangesBarProps> = ({
  visible,
  selectedHandler,
  hasUnsavedChanges,
  onSave,
  onValidate,
  onCancel,
  loading = false,
  lastSaved,
  nluContext
}) => {
  const [isApplying, setIsApplying] = useState(false);
  const [showBlockingDialog, setShowBlockingDialog] = useState(false);
  const [legacyValidationResult, setLegacyValidationResult] = useState<ValidationResult | null>(null);
  const [isValidatingLegacy, setIsValidatingLegacy] = useState(false);
  
  // Determine if we should use enhanced NLU validation
  const useEnhancedValidation = Boolean(
    nluContext?.enableEnhancedValidation && 
    selectedHandler && 
    nluContext?.language && 
    nluContext?.donationData
  );
  
  // Enhanced validation workflow (only for NLU context)
  const {
    validationResult: nluValidationResult,
    isValidating: isValidatingNLU,
    validateForSaving,
    canSave: canSaveNLU,
    hasBlockingConflicts,
    hasWarnings,
    blockingConflicts,
    warningConflicts,
    clearValidation: clearNLUValidation
  } = useValidationWorkflow({
    onValidationComplete: (result) => {
      console.log('NLU validation completed:', result);
    },
    onValidationError: (error) => {
      console.error('NLU validation error:', error);
    }
  });
  
  // Determine which validation state to use
  const validationResult = useEnhancedValidation ? nluValidationResult : legacyValidationResult;
  const isValidating = useEnhancedValidation ? isValidatingNLU : isValidatingLegacy;
  const canSave = useEnhancedValidation ? canSaveNLU : (legacyValidationResult?.valid !== false);

  // Handle validation (dual mode)
  const handleValidate = async (): Promise<void> => {
    if (!selectedHandler) return;

    if (useEnhancedValidation && nluContext?.language && nluContext?.donationData) {
      // Use enhanced NLU validation
      try {
        await validateForSaving(selectedHandler, nluContext.language, nluContext.donationData);
      } catch (error) {
        console.error('Enhanced validation failed:', error);
      }
    } else {
      // Use legacy validation
      if (!onValidate) return;
      
      setIsValidatingLegacy(true);
      try {
        const result = await onValidate();
        setLegacyValidationResult(result);
      } catch (error) {
        console.error('Legacy validation failed:', error);
        setLegacyValidationResult({
          valid: false,
          errors: [error instanceof Error ? error.message : 'Validation failed'],
          warnings: []
        });
      } finally {
        setIsValidatingLegacy(false);
      }
    }
  };

  // Handle apply/save (dual mode)
  const handleApply = async (): Promise<void> => {
    if (!onSave) return;

    if (useEnhancedValidation) {
      // Enhanced NLU validation workflow
      if (!validationResult) {
        await handleValidate();
        return; // Let user review validation results first
      }

      // Check for blocking conflicts
      if (hasBlockingConflicts) {
        setShowBlockingDialog(true);
        return; // Block save until conflicts are resolved
      }

      // Show warning dialog for warnings
      if (hasWarnings && warningConflicts.length > 0) {
        const proceed = window.confirm(
          `There are ${warningConflicts.length} warning${warningConflicts.length !== 1 ? 's' : ''} that should be reviewed. Do you want to proceed with saving anyway?`
        );
        if (!proceed) return;
      }
    } else {
      // Legacy validation workflow
      if (validationResult && !validationResult.valid) {
        const proceed = window.confirm(
          `There are validation errors. Do you want to proceed with saving anyway?`
        );
        if (!proceed) return;
      }
      
      if (validationResult && validationResult.warnings && validationResult.warnings.length > 0) {
        const proceed = window.confirm(
          `There are ${validationResult.warnings.length} warning${validationResult.warnings.length !== 1 ? 's' : ''}. Do you want to proceed with saving anyway?`
        );
        if (!proceed) return;
      }
    }

    setIsApplying(true);
    try {
      await onSave();
      
      // Clear validation state on successful save
      if (useEnhancedValidation) {
        clearNLUValidation();
      } else {
        setLegacyValidationResult(null);
      }
    } catch (error) {
      console.error('Failed to apply changes:', error);
    } finally {
      setIsApplying(false);
    }
  };

  // Handle discard (dual mode)
  const handleDiscard = (): void => {
    if (onCancel) {
      onCancel();
    }
    
    // Clear validation state
    if (useEnhancedValidation) {
      clearNLUValidation();
    } else {
      setLegacyValidationResult(null);
    }
  };

  if (!visible) return null;

  // Determine validation state based on mode
  const hasValidationErrors = useEnhancedValidation 
    ? hasBlockingConflicts 
    : (legacyValidationResult && !legacyValidationResult.valid);
  const hasValidationWarnings = useEnhancedValidation 
    ? hasWarnings 
    : (legacyValidationResult && legacyValidationResult.warnings && legacyValidationResult.warnings.length > 0);
  const canApply = !isApplying && !loading && canSave;

  return (
    <div className="fixed bottom-0 left-0 right-0 border-t border-gray-200 bg-white px-6 py-4 shadow-lg z-50">
      <div className="flex items-center justify-between">
        {/* Left side - Status */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 text-orange-500" />
            <span className="text-sm text-gray-700">
              {hasUnsavedChanges ? (
                selectedHandler ? (
                  <>Unsaved changes in <strong>{selectedHandler}</strong></>
                ) : (
                  <>Unsaved configuration changes</>
                )
              ) : (
                <>No pending changes</>
              )}
            </span>
          </div>
          
          {lastSaved && (
            <span className="text-xs text-gray-500">
              Last saved: {lastSaved.toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* Right side - Actions */}
        <div className="flex items-center space-x-3">
          {/* Validation Button */}
          <button
              onClick={handleValidate}
              disabled={isValidating || loading}
              className="inline-flex items-center px-3 py-2 border border-blue-300 text-sm font-medium rounded-md text-blue-700 bg-blue-50 hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isValidating ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Eye className="w-4 h-4 mr-2" />
              )}
              {isValidating ? 'Validating...' : 'Validate'}
            </button>

          {/* Discard Button */}
          <button
            onClick={handleDiscard}
            disabled={loading || isApplying}
            className="inline-flex items-center px-3 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <X className="w-4 h-4 mr-2" />
            Cancel
          </button>

          {/* Apply Button */}
          <button
            onClick={handleApply}
            disabled={!canApply}
            className={`inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${
              hasValidationErrors
                ? 'bg-red-600 hover:bg-red-700 focus:ring-red-500'
                : 'bg-green-600 hover:bg-green-700 focus:ring-green-500'
            }`}
          >
            {isApplying ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            {isApplying ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>

      {/* Conditional Validation Results */}
      {validationResult && (
        <div className="mt-4">
          {useEnhancedValidation ? (
            // Enhanced NLU validation display
            <ValidationIndicator 
              result={validationResult} 
              isValidating={isValidating}
            />
          ) : (
            // Legacy validation display
            <div className="space-y-2">
              {/* Errors */}
              {legacyValidationResult?.errors && legacyValidationResult.errors.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-md p-3">
                  <div className="flex">
                    <AlertCircle className="w-5 h-5 text-red-400 mr-2 mt-0.5 flex-shrink-0" />
                    <div className="text-sm">
                      <h4 className="text-red-800 font-medium mb-1">Validation Errors</h4>
                      <ul className="text-red-700 space-y-1">
                        {legacyValidationResult.errors.map((error, index) => (
                          <li key={index} className="list-disc list-inside">
                            {error}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {/* Warnings */}
              {hasValidationWarnings && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
                  <div className="flex">
                    <AlertTriangle className="w-5 h-5 text-yellow-400 mr-2 mt-0.5 flex-shrink-0" />
                    <div className="text-sm">
                      <h4 className="text-yellow-800 font-medium mb-1">Validation Warnings</h4>
                      <ul className="text-yellow-700 space-y-1">
                        {legacyValidationResult?.warnings?.map((warning, index) => (
                          <li key={index} className="list-disc list-inside">
                            {warning}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {/* Success */}
              {legacyValidationResult?.valid && (!legacyValidationResult.warnings || legacyValidationResult.warnings.length === 0) && (
                <div className="bg-green-50 border border-green-200 rounded-md p-3">
                  <div className="flex">
                    <CheckCircle2 className="w-5 h-5 text-green-400 mr-2 mt-0.5 flex-shrink-0" />
                    <div className="text-sm">
                      <p className="text-green-800 font-medium">Validation successful</p>
                      <p className="text-green-700">No errors found. Ready to save.</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Enhanced NLU Features - Only show when in NLU context */}
      {useEnhancedValidation && showBlockingDialog && (
        <BlockingConflictsDialog
          conflicts={blockingConflicts}
          onResolve={(conflictId) => {
            console.log('Resolve conflict:', conflictId);
            // TODO: Implement conflict resolution
            setShowBlockingDialog(false);
          }}
          onClose={() => setShowBlockingDialog(false)}
        />
      )}
    </div>
  );
};

export default ApplyChangesBar;
