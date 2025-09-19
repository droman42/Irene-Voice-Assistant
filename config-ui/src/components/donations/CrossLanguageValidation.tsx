/**
 * CrossLanguageValidation Component - Dedicated cross-language validation UI
 * 
 * Provides a prominent validation panel with parameter consistency checking,
 * method completeness validation, and automated synchronization tools.
 */

import { useState } from 'react';
import { 
  AlertTriangle, 
  CheckCircle, 
  RefreshCw, 
  RotateCw, 
  ChevronDown, 
  ChevronRight,
  AlertCircle,
  Info,
  ArrowRight,
  Settings
} from 'lucide-react';
import Badge from '@/components/ui/Badge';
import type { 
  ValidationReport, 
  CompletenessReport,
  HandlerLanguageInfo 
} from '@/types/api';

export interface CrossLanguageValidationProps {
  handlerName: string;
  handlerInfo: HandlerLanguageInfo;
  activeLanguage: string;
  validationReport: ValidationReport | null;
  completenessReport: CompletenessReport | null;
  onRefreshValidation: () => void;
  onSyncParameters: (sourceLanguage: string, targetLanguages: string[]) => void;
  isLoading?: boolean;
  disabled?: boolean;
}

const CrossLanguageValidation: React.FC<CrossLanguageValidationProps> = ({
  // handlerName not used in component logic
  handlerInfo,
  activeLanguage,
  validationReport,
  completenessReport,
  onRefreshValidation,
  onSyncParameters,
  isLoading = false,
  disabled = false
}) => {
  const [expanded, setExpanded] = useState(false);
  const [showParameterDetails, setShowParameterDetails] = useState(false);
  const [showMethodDetails, setShowMethodDetails] = useState(false);

  // Calculate validation summary
  const hasMultipleLanguages = handlerInfo.languages.length > 1;
  const hasValidationData = validationReport || completenessReport;
  
  const parameterIssues = validationReport ? 
    validationReport.missing_parameters.length + validationReport.type_mismatches.length : 0;
  const methodIssues = completenessReport ? 
    completenessReport.missing_methods.length + completenessReport.extra_methods.length : 0;
  
  const totalIssues = parameterIssues + methodIssues;
  const hasIssues = totalIssues > 0;

  const handleSyncFromActive = () => {
    if (disabled || isLoading) return;
    
    const targetLanguages = handlerInfo.languages.filter(lang => lang !== activeLanguage);
    if (targetLanguages.length > 0) {
      onSyncParameters(activeLanguage, targetLanguages);
    }
  };

  if (!hasMultipleLanguages) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <div className="flex items-center space-x-2 text-sm text-gray-600">
          <Info className="w-4 h-4" />
          <span>Single language handler - cross-language validation not applicable</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center space-x-2 text-left hover:bg-gray-50 -m-1 p-1 rounded"
              disabled={disabled}
            >
              {expanded ? (
                <ChevronDown className="w-4 h-4 text-gray-500" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-500" />
              )}
              <div className="flex items-center space-x-2">
                <Settings className="w-5 h-5 text-blue-600" />
                <h3 className="text-lg font-semibold text-gray-900">Cross-Language Validation</h3>
              </div>
            </button>
            
            {/* Status Badge */}
            {hasValidationData && (
              <div className="flex items-center space-x-2">
                {hasIssues ? (
                  <Badge variant="warning" className="flex items-center space-x-1">
                    <AlertTriangle className="w-3 h-3" />
                    <span>{totalIssues} issues</span>
                  </Badge>
                ) : (
                  <Badge variant="success" className="flex items-center space-x-1">
                    <CheckCircle className="w-3 h-3" />
                    <span>Synchronized</span>
                  </Badge>
                )}
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center space-x-2">
            <button
              onClick={onRefreshValidation}
              disabled={disabled || isLoading}
              className={`
                flex items-center space-x-1 px-3 py-1.5 text-sm rounded-md transition-colors
                ${disabled || isLoading 
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                  : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                }
              `}
              title="Refresh validation status"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>

            {hasIssues && (
              <button
                onClick={handleSyncFromActive}
                disabled={disabled || isLoading}
                className={`
                  flex items-center space-x-1 px-3 py-1.5 text-sm rounded-md transition-colors
                  ${disabled || isLoading 
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                    : 'bg-green-50 text-green-700 hover:bg-green-100'
                  }
                `}
                title={`Sync parameters from ${activeLanguage} to other languages`}
              >
                <RotateCw className="w-4 h-4" />
                <span>Sync from {activeLanguage.toUpperCase()}</span>
              </button>
            )}
          </div>
        </div>

        {/* Summary Info */}
        <div className="mt-3 text-sm text-gray-600">
          <span>
            Comparing {handlerInfo.languages.length} languages: {handlerInfo.languages.map(lang => lang.toUpperCase()).join(', ')}
          </span>
          {hasValidationData && (
            <span className="ml-2">
              • Last checked: {new Date(
                (validationReport?.timestamp || completenessReport?.timestamp || 0) * 1000
              ).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="p-4 space-y-4">
          {!hasValidationData ? (
            <div className="flex items-center justify-center py-8 text-gray-500">
              <div className="text-center">
                <RefreshCw className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                <p>Click "Refresh" to run cross-language validation</p>
                <p className="text-xs mt-2 text-gray-400">
                  Note: This feature requires backend API support
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Parameter Consistency Section */}
              {validationReport && (
                <div className="border border-gray-200 rounded-lg">
                  <button
                    onClick={() => setShowParameterDetails(!showParameterDetails)}
                    className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-50"
                  >
                    <div className="flex items-center space-x-3">
                      {validationReport.parameter_consistency ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-yellow-500" />
                      )}
                      <div>
                        <h4 className="font-medium text-gray-900">Parameter Consistency</h4>
                        <p className="text-sm text-gray-600">
                          {validationReport.parameter_consistency 
                            ? 'All parameters are consistent across languages'
                            : `${parameterIssues} parameter inconsistencies found`
                          }
                        </p>
                      </div>
                    </div>
                    {showParameterDetails ? (
                      <ChevronDown className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-500" />
                    )}
                  </button>

                  {showParameterDetails && !validationReport.parameter_consistency && (
                    <div className="px-3 pb-3 border-t border-gray-100">
                      {validationReport.missing_parameters.length > 0 && (
                        <div className="mt-3">
                          <h5 className="text-sm font-medium text-red-800 mb-2">Missing Parameters:</h5>
                          <ul className="space-y-1">
                            {validationReport.missing_parameters.map((issue, index) => (
                              <li key={`missing-${index}`} className="text-sm text-red-700 flex items-center space-x-1">
                                <AlertCircle className="w-3 h-3 flex-shrink-0" />
                                <span>{issue}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {validationReport.type_mismatches.length > 0 && (
                        <div className="mt-3">
                          <h5 className="text-sm font-medium text-yellow-800 mb-2">Type Mismatches:</h5>
                          <ul className="space-y-1">
                            {validationReport.type_mismatches.map((issue, index) => (
                              <li key={`mismatch-${index}`} className="text-sm text-yellow-700 flex items-center space-x-1">
                                <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                                <span>{issue}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Method Completeness Section */}
              {completenessReport && (
                <div className="border border-gray-200 rounded-lg">
                  <button
                    onClick={() => setShowMethodDetails(!showMethodDetails)}
                    className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-50"
                  >
                    <div className="flex items-center space-x-3">
                      {completenessReport.method_completeness ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-yellow-500" />
                      )}
                      <div>
                        <h4 className="font-medium text-gray-900">Method Completeness</h4>
                        <p className="text-sm text-gray-600">
                          {completenessReport.method_completeness 
                            ? 'All methods are present in all languages'
                            : `${methodIssues} method inconsistencies found`
                          }
                        </p>
                      </div>
                    </div>
                    {showMethodDetails ? (
                      <ChevronDown className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-500" />
                    )}
                  </button>

                  {showMethodDetails && (
                    <div className="px-3 pb-3 border-t border-gray-100">
                      {/* Method counts by language */}
                      <div className="mt-3">
                        <h5 className="text-sm font-medium text-gray-800 mb-2">Method Counts by Language:</h5>
                        <div className="grid grid-cols-2 gap-2">
                          {Object.entries(completenessReport.method_counts_by_language).map(([lang, count]) => (
                            <div key={lang} className="flex items-center justify-between text-sm">
                              <span className="text-gray-600">{lang.toUpperCase()}:</span>
                              <Badge variant="info">{count} methods</Badge>
                            </div>
                          ))}
                        </div>
                      </div>

                      {completenessReport.missing_methods.length > 0 && (
                        <div className="mt-3">
                          <h5 className="text-sm font-medium text-red-800 mb-2">Missing Methods:</h5>
                          <ul className="space-y-1">
                            {completenessReport.missing_methods.map((issue, index) => (
                              <li key={`missing-method-${index}`} className="text-sm text-red-700 flex items-center space-x-1">
                                <AlertCircle className="w-3 h-3 flex-shrink-0" />
                                <span>{issue}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {completenessReport.extra_methods.length > 0 && (
                        <div className="mt-3">
                          <h5 className="text-sm font-medium text-blue-800 mb-2">Extra Methods:</h5>
                          <ul className="space-y-1">
                            {completenessReport.extra_methods.map((issue, index) => (
                              <li key={`extra-method-${index}`} className="text-sm text-blue-700 flex items-center space-x-1">
                                <Info className="w-3 h-3 flex-shrink-0" />
                                <span>{issue}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Synchronization Actions */}
              {hasIssues && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start space-x-3">
                    <RotateCw className="w-5 h-5 text-blue-600 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="text-sm font-medium text-blue-900 mb-2">Recommended Actions</h4>
                      <p className="text-sm text-blue-800 mb-3">
                        Use the active language ({activeLanguage.toUpperCase()}) as the source to synchronize 
                        parameter structures across all languages. This will:
                      </p>
                      <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside mb-3">
                        <li>Copy parameter definitions to missing languages</li>
                        <li>Ensure consistent parameter types across languages</li>
                        <li>Preserve existing phrases and translations</li>
                      </ul>
                      <button
                        onClick={handleSyncFromActive}
                        disabled={disabled || isLoading}
                        className={`
                          flex items-center space-x-2 px-4 py-2 text-sm font-medium rounded-md transition-colors
                          ${disabled || isLoading 
                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                            : 'bg-blue-600 text-white hover:bg-blue-700'
                          }
                        `}
                      >
                        <ArrowRight className="w-4 h-4" />
                        <span>Sync from {activeLanguage.toUpperCase()} to all languages</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default CrossLanguageValidation;
