/**
 * TemplatesPage Component - Main templates management interface
 * 
 * Integrates handler list, template editor, and apply changes workflow
 * with full API integration for real-time template management.
 * Follows the exact same pattern as DonationsPage for consistency.
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { AlertCircle, FileText, Code } from 'lucide-react';

// Import reusable components from donations
import HandlerList from '@/components/donations/HandlerList';
import LanguageTabs, { LanguageInfo } from '@/components/donations/LanguageTabs';
import ApplyChangesBar from '@/components/common/ApplyChangesBar';

// Import template-specific components
import TemplateEditor from '@/components/editors/TemplateEditor';

// Import UI components
import Section from '@/components/ui/Section';
import Badge from '@/components/ui/Badge';

import apiClient from '@/utils/apiClient';
import type { 
  HandlerLanguageInfo
} from '@/types';

interface TemplateData {
  [key: string]: string | string[] | Record<string, any>;
}

interface TemplateValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
}

const TemplatesPage: React.FC = () => {
  // Core state management
  const [handlers, setHandlers] = useState<HandlerLanguageInfo[]>([]);
  const [selectedHandler, setSelectedHandler] = useState<string | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null);
  const [templateData, setTemplateData] = useState<TemplateData>({});
  const [originalTemplateData, setOriginalTemplateData] = useState<TemplateData>({});
  
  // UI state
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Template management state
  const [validationResult, setValidationResult] = useState<TemplateValidationResult>({
    isValid: true,
    errors: [],
    warnings: []
  });
  const [hasChanges, setHasChanges] = useState(false);
  
  // Language management state  
  const [languageInfos, setLanguageInfos] = useState<Record<string, LanguageInfo>>({});
  
  // Handler list UI state
  const [searchQuery, setSearchQuery] = useState('');
  const [filterLanguageCount, setFilterLanguageCount] = useState<'all' | 'single' | 'multiple'>('all');

  // Load handlers on component mount
  useEffect(() => {
    loadHandlers();
  }, []);

  // Check for changes when template data changes
  useEffect(() => {
    if (selectedHandler && selectedLanguage) {
      const changed = JSON.stringify(templateData) !== JSON.stringify(originalTemplateData);
      setHasChanges(changed);
    }
  }, [templateData, originalTemplateData, selectedHandler, selectedLanguage]);

  // Update language info when handlers change
  useEffect(() => {
    const newLanguageInfos: Record<string, LanguageInfo> = {};
    
    // Ensure handlers is an array and each handler has required properties
    (handlers || []).forEach(handler => {
      if (handler && handler.handler_name && Array.isArray(handler.languages)) {
        handler.languages.forEach(lang => {
          if (typeof lang === 'string') {
            const key = `${handler.handler_name}:${lang}`;
            newLanguageInfos[key] = {
              code: lang,
              label: lang.toUpperCase(),
              status: 'loaded',
              validationErrors: 0
            };
          }
        });
      }
    });
    
    setLanguageInfos(newLanguageInfos);
  }, [handlers]);

  const loadHandlers = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await apiClient.getTemplateHandlers();
      
      // Ensure we have a valid handlers array with proper structure
      const validHandlers = (response.handlers || []).filter(handler => 
        handler && 
        typeof handler.handler_name === 'string' && 
        Array.isArray(handler.languages)
      );
      
      setHandlers(validHandlers);
      
      // Auto-select first handler if available
      if (validHandlers.length > 0) {
        const firstHandler = validHandlers[0];
        setSelectedHandler(firstHandler.handler_name);
        
        if (firstHandler.languages && firstHandler.languages.length > 0) {
          setSelectedLanguage(firstHandler.languages[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load template handlers:', err);
      setError(err instanceof Error ? err.message : 'Failed to load template handlers');
      // Set empty array on error to prevent undefined access
      setHandlers([]);
    } finally {
      setLoading(false);
    }
  };

  const loadTemplateData = async (handlerName: string, language: string) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await apiClient.getLanguageTemplate(handlerName, language);
      const data = response.template_data || {};
      
      setTemplateData(data);
      setOriginalTemplateData(data);
      
      // Reset validation when loading new data
      setValidationResult({
        isValid: true,
        errors: [],
        warnings: []
      });
      
    } catch (err) {
      console.error('Failed to load template data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load template data');
      
      // Reset to empty state on error
      setTemplateData({});
      setOriginalTemplateData({});
    } finally {
      setLoading(false);
    }
  };

  // Load template data when handler or language selection changes
  useEffect(() => {
    if (selectedHandler && selectedLanguage) {
      loadTemplateData(selectedHandler, selectedLanguage);
    }
  }, [selectedHandler, selectedLanguage]);

  const handleHandlerSelect = useCallback((handlerName: string) => {
    if (handlerName === selectedHandler) return;
    
    setSelectedHandler(handlerName);
    
    // Auto-select first available language for the new handler
    const handler = handlers.find(h => h.handler_name === handlerName);
    if (handler && handler.languages.length > 0) {
      setSelectedLanguage(handler.languages[0]);
    } else {
      setSelectedLanguage(null);
    }
  }, [selectedHandler, handlers]);

  const handleLanguageChange = useCallback((language: string) => {
    if (language === selectedLanguage) return;
    setSelectedLanguage(language);
  }, [selectedLanguage]);

  const handleTemplateChange = useCallback((newData: TemplateData) => {
    setTemplateData(newData);
  }, []);

  const handleValidationChange = useCallback((isValid: boolean, errors: string[]) => {
    setValidationResult({
      isValid,
      errors,
      warnings: [] // Template validation currently only returns errors
    });
  }, []);

  const handleSave = async () => {
    if (!selectedHandler || !selectedLanguage) return;
    
    try {
      setSaving(true);
      setError(null);
      
      const response = await apiClient.updateLanguageTemplate(
        selectedHandler,
        selectedLanguage,
        templateData,
        {
          validateBeforeSave: true,
          triggerReload: true
        }
      );
      
      if (response.success) {
        setOriginalTemplateData(templateData);
        setHasChanges(false);
        
        // Update language info with validation results
        if (response.errors && response.errors.length > 0) {
          const key = `${selectedHandler}:${selectedLanguage}`;
          setLanguageInfos(prev => ({
            ...prev,
            [key]: {
              ...prev[key],
              validationErrors: response.errors.length
            }
          }));
        }
      } else {
        setError('Failed to save template: ' + (response.errors || []).map((e: any) => e.message).join(', '));
      }
    } catch (err) {
      console.error('Failed to save template:', err);
      setError(err instanceof Error ? err.message : 'Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  const handleValidate = async () => {
    if (!selectedHandler || !selectedLanguage) {
      return {
        valid: false,
        errors: ['No handler or language selected'],
        warnings: [],
        details: null
      };
    }
    
    try {
      setValidating(true);
      setError(null);
      
      const response = await apiClient.validateLanguageTemplate(
        selectedHandler,
        selectedLanguage,
        templateData
      );
      
      const result = {
        isValid: response.is_valid || false,
        errors: (response.errors || []).map((e: any) => e.message || String(e)),
        warnings: (response.warnings || []).map((w: any) => w.message || String(w))
      };
      
      setValidationResult(result);
      
      return {
        valid: result.isValid,
        errors: result.errors,
        warnings: result.warnings,
        details: null
      };
      
    } catch (err) {
      console.error('Failed to validate template:', err);
      setError(err instanceof Error ? err.message : 'Failed to validate template');
      
      return {
        valid: false,
        errors: [err instanceof Error ? err.message : 'Failed to validate template'],
        warnings: [],
        details: null
      };
    } finally {
      setValidating(false);
    }
  };

  const handleDiscard = () => {
    setTemplateData(originalTemplateData);
    setHasChanges(false);
    setValidationResult({
      isValid: true,
      errors: [],
      warnings: []
    });
  };

  const handleCreateLanguage = async (language: string, options: { copyFrom?: string; useTemplate?: boolean }) => {
    if (!selectedHandler) return;
    
    try {
      const response = await apiClient.createTemplateLanguage(selectedHandler, language, options);
      
      if (response.success) {
        // Reload handlers to get updated language list
        await loadHandlers();
        
        // Select the new language
        setSelectedLanguage(language);
      }
    } catch (err) {
      console.error('Failed to create template language:', err);
      setError(err instanceof Error ? err.message : 'Failed to create template language');
    }
  };

  const handleDeleteLanguage = async (language: string) => {
    if (!selectedHandler) return;
    
    try {
      const response = await apiClient.deleteTemplateLanguage(selectedHandler, language);
      
      if (response.success) {
        // Reload handlers to get updated language list
        await loadHandlers();
        
        // If we deleted the currently selected language, select another one
        if (language === selectedLanguage) {
          const handler = handlers.find(h => h.handler_name === selectedHandler);
          const remainingLanguages = handler?.languages.filter(l => l !== language) || [];
          setSelectedLanguage(remainingLanguages.length > 0 ? remainingLanguages[0] : null);
        }
      }
    } catch (err) {
      console.error('Failed to delete template language:', err);
      setError(err instanceof Error ? err.message : 'Failed to delete template language');
    }
  };

  // Compute language info for LanguageTabs
  const currentLanguageInfos: LanguageInfo[] = useMemo(() => {
    if (!selectedHandler) return [];
    
    const handler = handlers.find(h => h && h.handler_name === selectedHandler);
    if (!handler || !Array.isArray(handler.languages)) return [];
    
    return handler.languages
      .filter(lang => typeof lang === 'string')
      .map(lang => {
        const key = `${selectedHandler}:${lang}`;
        return languageInfos[key] || {
          code: lang,
          label: lang.toUpperCase(),
          status: 'loaded',
          validationErrors: 0
        };
      });
  }, [selectedHandler, handlers, languageInfos]);

  // Get supported languages from current handler
  const currentSupportedLanguages = useMemo(() => {
    if (!selectedHandler) return ["en", "ru"];
    
    const handler = handlers.find(h => h && h.handler_name === selectedHandler);
    if (!handler || !Array.isArray(handler.supported_languages)) {
      return ["en", "ru"];
    }
    
    return handler.supported_languages.filter(lang => typeof lang === 'string');
  }, [selectedHandler, handlers]);

  if (loading && !selectedHandler) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Template Management</h1>
          <p className="text-gray-600">Manage response templates for intent handlers</p>
        </div>
        <div className="flex items-center space-x-2 mt-1">
          <Badge variant="info">
            <Code className="w-3 h-3 mr-1" />
            YAML Editor
          </Badge>
          {hasChanges && (
            <Badge variant="warning">
              Unsaved Changes
            </Badge>
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <AlertCircle className="h-5 w-5 text-red-400" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error</h3>
              <p className="mt-1 text-sm text-red-700">{error}</p>
            </div>
          </div>
        </div>
      )}

      <div className="h-full flex">
        {/* Handler List */}
        <HandlerList
          handlers={handlers}
          selectedHandler={selectedHandler}
          selectedLanguage={selectedLanguage}
          onSelect={handleHandlerSelect}
          onLanguageSelect={() => {}} // Not used for templates (handled by LanguageTabs)
          onCreateLanguage={() => {}} // Not used (handled by LanguageTabs)
          onDeleteLanguage={() => {}} // Not used (handled by LanguageTabs)
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          filterLanguageCount={filterLanguageCount}
          onFilterLanguageCountChange={setFilterLanguageCount}
          loading={loading}
          error={error}
        />

        {/* Main Content */}
        <div className="flex-1 flex flex-col">
          {selectedHandler ? (
            <div className="space-y-6">
              {/* Language Tabs */}
              <LanguageTabs
                activeLanguage={selectedLanguage || ''}
                availableLanguages={currentLanguageInfos}
                supportedLanguages={currentSupportedLanguages}
                onLanguageChange={handleLanguageChange}
                onCreateLanguage={(lang: string, templateFrom?: string) => {
                  handleCreateLanguage(lang, { 
                    copyFrom: templateFrom, 
                    useTemplate: !templateFrom 
                  });
                }}
                onDeleteLanguage={handleDeleteLanguage}
                handlerName={selectedHandler}
              />

              {selectedLanguage ? (
                <>
                  {/* Template Editor */}
                  <TemplateEditor
                    value={templateData}
                    onChange={handleTemplateChange}
                    onValidationChange={handleValidationChange}
                  />

                  {/* Validation Results */}
                  {(!validationResult.isValid || validationResult.warnings.length > 0) && (
                    <Section title="Validation Results">
                      {validationResult.errors.length > 0 && (
                        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
                          <h4 className="text-sm font-medium text-red-800 mb-1">Errors:</h4>
                          <ul className="text-sm text-red-700 list-disc list-inside">
                            {validationResult.errors.map((error, index) => (
                              <li key={index}>{error}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      
                      {validationResult.warnings.length > 0 && (
                        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                          <h4 className="text-sm font-medium text-yellow-800 mb-1">Warnings:</h4>
                          <ul className="text-sm text-yellow-700 list-disc list-inside">
                            {validationResult.warnings.map((warning, index) => (
                              <li key={index}>{warning}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </Section>
                  )}

                  {/* Apply Changes Bar */}
                  <ApplyChangesBar
                    visible={hasChanges}
                    selectedHandler={selectedHandler}
                    hasUnsavedChanges={hasChanges}
                    onSave={handleSave}
                    onValidate={handleValidate}
                    onCancel={handleDiscard}
                    loading={saving || validating}
                  />
                </>
              ) : (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">No Language Selected</h3>
                  <p className="text-gray-600">Select a language to edit templates</p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <Code className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Handler Selected</h3>
              <p className="text-gray-600">Select a handler to manage its templates</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TemplatesPage;
