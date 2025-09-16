/**
 * LanguageTabs Component - Language selection and management interface
 * 
 * Provides tab-based language switching with creation, deletion, and validation status
 * indicators as outlined in Phase 3 of the language support plan.
 */

import { useState } from 'react';
import { Plus, X, AlertTriangle, CheckCircle, Clock, Shield, RotateCw } from 'lucide-react';
import Badge from '@/components/ui/Badge';
import type { ValidationReport, CompletenessReport } from '@/types/api';

export interface LanguageInfo {
  code: string;
  label: string;
  status: 'loaded' | 'loading' | 'error' | 'missing';
  validationErrors?: number;
  methodCount?: number;
  lastModified?: string;
}

export interface LanguageTabsProps {
  activeLanguage: string;
  availableLanguages: LanguageInfo[];
  supportedLanguages: string[];
  onLanguageChange: (lang: string) => void;
  onCreateLanguage: (lang: string, templateFrom?: string) => void;
  onDeleteLanguage: (lang: string) => void;
  onCompareLanguages?: (lang1: string, lang2: string) => void;
  disabled?: boolean;
  // Phase 4: Cross-language validation props
  handlerName?: string;
  validationReport?: ValidationReport | null;
  completenessReport?: CompletenessReport | null;
  onRefreshValidation?: () => void;
  onSyncParameters?: (sourceLanguage: string, targetLanguages: string[]) => void;
}

const LanguageTabs: React.FC<LanguageTabsProps> = ({
  activeLanguage,
  availableLanguages,
  supportedLanguages,
  onLanguageChange,
  onCreateLanguage,
  onDeleteLanguage,
  onCompareLanguages,
  disabled = false,
  // Phase 4: Cross-language validation props
  validationReport,
  completenessReport,
  onRefreshValidation,
  onSyncParameters
}) => {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newLanguageCode, setNewLanguageCode] = useState('');
  const [templateLanguage, setTemplateLanguage] = useState('');

  const getLanguageLabel = (code: string): string => {
    const labels: Record<string, string> = {
      'en': 'English',
      'ru': 'Русский',
      'de': 'Deutsch',
      'fr': 'Français',
      'es': 'Español',
      'it': 'Italiano',
      'pt': 'Português',
      'zh': '中文',
      'ja': '日本語',
      'ko': '한국어'
    };
    return labels[code] || code.toUpperCase();
  };

  const getStatusIcon = (status: string, validationErrors?: number) => {
    switch (status) {
      case 'loaded':
        return validationErrors && validationErrors > 0 
          ? <AlertTriangle className="w-3 h-3 text-yellow-500" />
          : <CheckCircle className="w-3 h-3 text-green-500" />;
      case 'loading':
        return <Clock className="w-3 h-3 text-blue-500 animate-spin" />;
      case 'error':
        return <AlertTriangle className="w-3 h-3 text-red-500" />;
      case 'missing':
        return <AlertTriangle className="w-3 h-3 text-gray-400" />;
      default:
        return null;
    }
  };

  const getStatusBadge = (language: LanguageInfo) => {
    if (language.validationErrors && language.validationErrors > 0) {
      return <Badge variant="warning">{language.validationErrors}</Badge>;
    }
    if (language.status === 'error') {
      return <Badge variant="error">Error</Badge>;
    }
    if (language.status === 'missing') {
      return <Badge variant="default">Missing</Badge>;
    }
    return null;
  };

  const handleCreateLanguage = () => {
    if (newLanguageCode.trim()) {
      onCreateLanguage(newLanguageCode.trim(), templateLanguage || undefined);
      setNewLanguageCode('');
      setTemplateLanguage('');
      setShowCreateForm(false);
    }
  };

  const missingLanguages = supportedLanguages.filter(
    lang => !availableLanguages.some(available => available.code === lang)
  );

  // Cross-language validation helpers
  const hasValidationIssues = () => {
    return (validationReport && !validationReport.parameter_consistency) ||
           (completenessReport && !completenessReport.method_completeness);
  };

  const getValidationSummary = () => {
    const issues = [];
    if (validationReport && !validationReport.parameter_consistency) {
      issues.push(`${validationReport.missing_parameters.length + validationReport.type_mismatches.length} parameter issues`);
    }
    if (completenessReport && !completenessReport.method_completeness) {
      issues.push(`${completenessReport.missing_methods.length + completenessReport.extra_methods.length} method issues`);
    }
    return issues.join(', ');
  };

  const handleSyncParameters = () => {
    if (!onSyncParameters || availableLanguages.length < 2) return;
    
    // Use the active language as source, sync to all other languages
    const targetLanguages = availableLanguages
      .map(lang => lang.code)
      .filter(code => code !== activeLanguage);
    
    onSyncParameters(activeLanguage, targetLanguages);
  };

  return (
    <div className="border-b border-gray-200 bg-white">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center space-x-1">
          {/* Available Language Tabs */}
          {availableLanguages.map((language) => (
            <div
              key={language.code}
              className={`
                relative flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors
                ${activeLanguage === language.code
                  ? 'bg-blue-100 text-blue-700 border border-blue-300'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }
                ${disabled ? 'opacity-50' : 'cursor-pointer'}
                ${language.status === 'error' ? 'bg-red-50 text-red-700' : ''}
              `}
            >
              <button
                onClick={() => !disabled && onLanguageChange(language.code)}
                disabled={disabled || language.status === 'loading'}
                className="flex items-center space-x-2 flex-1 text-left"
              >
                <span>{getLanguageLabel(language.code)}</span>
                {getStatusIcon(language.status, language.validationErrors)}
                {getStatusBadge(language)}
              </button>
              
              {/* Delete button for non-active languages */}
              {language.code !== activeLanguage && !disabled && language.status !== 'loading' && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteLanguage(language.code);
                  }}
                  className="ml-1 p-0.5 text-gray-400 hover:text-red-600 transition-colors"
                  title={`Delete ${getLanguageLabel(language.code)}`}
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          ))}

          {/* Add Language Button */}
          {!disabled && (
            <div className="relative">
              {!showCreateForm ? (
                <button
                  onClick={() => setShowCreateForm(true)}
                  className="flex items-center space-x-1 px-3 py-2 text-sm text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                  title="Add new language"
                >
                  <Plus className="w-4 h-4" />
                  <span>Add Language</span>
                </button>
              ) : (
                <div className="flex items-center space-x-2 p-2 bg-gray-50 rounded-md border">
                  <select
                    value={newLanguageCode}
                    onChange={(e) => setNewLanguageCode(e.target.value)}
                    className="text-sm border border-gray-300 rounded px-2 py-1"
                  >
                    <option value="">Select language...</option>
                    {missingLanguages.map(lang => (
                      <option key={lang} value={lang}>
                        {getLanguageLabel(lang)}
                      </option>
                    ))}
                  </select>
                  
                  {availableLanguages.length > 0 && (
                    <select
                      value={templateLanguage}
                      onChange={(e) => setTemplateLanguage(e.target.value)}
                      className="text-sm border border-gray-300 rounded px-2 py-1"
                    >
                      <option value="">From scratch</option>
                      {availableLanguages.map(lang => (
                        <option key={lang.code} value={lang.code}>
                          Copy from {getLanguageLabel(lang.code)}
                        </option>
                      ))}
                    </select>
                  )}
                  
                  <button
                    onClick={handleCreateLanguage}
                    disabled={!newLanguageCode}
                    className="px-2 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  >
                    Create
                  </button>
                  
                  <button
                    onClick={() => {
                      setShowCreateForm(false);
                      setNewLanguageCode('');
                      setTemplateLanguage('');
                    }}
                    className="px-2 py-1 text-sm text-gray-600 hover:text-gray-800"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Language Info and Cross-Language Validation */}
        <div className="flex items-center space-x-4 text-sm">
          <span className="text-gray-500">
            {availableLanguages.length} of {supportedLanguages.length} languages
          </span>
          
          {/* Phase 4: Cross-language validation status */}
          {availableLanguages.length > 1 && (validationReport || completenessReport) && (
            <div className="flex items-center space-x-2">
              {hasValidationIssues() ? (
                <Badge variant="warning" className="flex items-center space-x-1">
                  <AlertTriangle className="w-3 h-3" />
                  <span>{getValidationSummary()}</span>
                </Badge>
              ) : (
                <Badge variant="success" className="flex items-center space-x-1">
                  <CheckCircle className="w-3 h-3" />
                  <span>Synchronized</span>
                </Badge>
              )}
              
              {onRefreshValidation && (
                <button
                  onClick={onRefreshValidation}
                  className="text-blue-600 hover:text-blue-800 p-1 rounded"
                  title="Refresh validation"
                >
                  <Shield className="w-4 h-4" />
                </button>
              )}
              
              {onSyncParameters && availableLanguages.length > 1 && hasValidationIssues() && (
                <button
                  onClick={handleSyncParameters}
                  className="text-green-600 hover:text-green-800 p-1 rounded"
                  title="Sync parameters from active language"
                >
                  <RotateCw className="w-4 h-4" />
                </button>
              )}
            </div>
          )}
          
          {onCompareLanguages && availableLanguages.length > 1 && (
            <button
              onClick={() => {
                const otherLang = availableLanguages.find(l => l.code !== activeLanguage);
                if (otherLang) {
                  onCompareLanguages(activeLanguage, otherLang.code);
                }
              }}
              className="text-blue-600 hover:text-blue-800"
            >
              Compare Languages
            </button>
          )}
        </div>
      </div>

      {/* Missing Languages Warning */}
      {missingLanguages.length > 0 && (
        <div className="px-4 py-2 bg-yellow-50 border-t border-yellow-200">
          <div className="flex items-center space-x-2 text-sm text-yellow-800">
            <AlertTriangle className="w-4 h-4" />
            <span>
              Missing languages: {missingLanguages.map(getLanguageLabel).join(', ')}
            </span>
          </div>
        </div>
      )}

      {/* Phase 4: Cross-Language Validation Details */}
      {availableLanguages.length > 1 && hasValidationIssues() && (validationReport || completenessReport) && (
        <div className="px-4 py-3 bg-red-50 border-t border-red-200">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-red-800">Cross-Language Validation Issues</h4>
              {onRefreshValidation && (
                <button
                  onClick={onRefreshValidation}
                  className="text-xs text-red-600 hover:text-red-800"
                >
                  Refresh validation
                </button>
              )}
            </div>
            
            {/* Parameter Consistency Issues */}
            {validationReport && !validationReport.parameter_consistency && (
              <div className="text-sm text-red-700">
                <div className="font-medium mb-1">Parameter Issues:</div>
                <ul className="list-disc list-inside text-xs space-y-1">
                  {validationReport.missing_parameters.map((issue, index) => (
                    <li key={`missing-${index}`}>Missing parameter: {issue}</li>
                  ))}
                  {validationReport.type_mismatches.map((issue, index) => (
                    <li key={`mismatch-${index}`}>Type mismatch: {issue}</li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Method Completeness Issues */}
            {completenessReport && !completenessReport.method_completeness && (
              <div className="text-sm text-red-700">
                <div className="font-medium mb-1">Method Issues:</div>
                <ul className="list-disc list-inside text-xs space-y-1">
                  {completenessReport.missing_methods.map((issue, index) => (
                    <li key={`missing-method-${index}`}>Missing method: {issue}</li>
                  ))}
                  {completenessReport.extra_methods.map((issue, index) => (
                    <li key={`extra-method-${index}`}>Extra method: {issue}</li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Action Buttons */}
            <div className="flex items-center space-x-2 pt-2">
              {onSyncParameters && availableLanguages.length > 1 && (
                <button
                  onClick={handleSyncParameters}
                  className="inline-flex items-center space-x-1 px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  <RotateCw className="w-3 h-3" />
                  <span>Sync from {getLanguageLabel(activeLanguage)}</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LanguageTabs;
