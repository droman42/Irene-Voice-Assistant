/**
 * DonationsPage Component - Main donations management interface
 * 
 * Integrates handler list, donation editor, and apply changes workflow
 * with full API integration for real-time donation management.
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { AlertCircle, Trash2, FileText, ChevronDown, ChevronRight, AlertTriangle, RefreshCw } from 'lucide-react';

// Import components
import HandlerList from '@/components/donations/HandlerList';
import LanguageTabs, { LanguageInfo } from '@/components/donations/LanguageTabs';
import CrossLanguageValidation from '@/components/donations/CrossLanguageValidation';
import ApplyChangesBar from '@/components/common/ApplyChangesBar';

// Import analysis components
import { 
  ConflictStatusBar, 
  SuggestionPanel 
} from '@/components/analysis';

// Import analysis hooks
import { useRealtimeAnalysis } from '@/hooks';

// Import existing form components
import Section from '@/components/ui/Section';
import Input from '@/components/ui/Input';
import Badge from '@/components/ui/Badge';
import ArrayOfStringsEditor from '@/components/editors/ArrayOfStringsEditor';
// import ParameterListEditor from '@/components/editors/ParameterListEditor';
import TokenPatternsEditor from '@/components/editors/TokenPatternsEditor';
import SlotPatternsEditor from '@/components/editors/SlotPatternsEditor';
import ExamplesEditor from '@/components/editors/ExamplesEditor';
import LemmasEditor from '@/components/editors/LemmasEditor';

import apiClient from '@/utils/apiClient';
import type { 
  DonationData, 
  ValidationResult,
  JsonSchema,
  HandlerLanguageInfo,
  DonationHandlerListResponse,
  LanguageDonationContentResponse,
  // Phase 4: Cross-language validation types
  ValidationReport,
  CompletenessReport,
  CrossLanguageValidationResponse
} from '@/types';

// Note: Utility functions available for future use
// function download(filename: string, text: string): void { ... }
// function fileToText(file: File): Promise<string> { ... }

// Method Donation Editor
interface MethodDonationEditorProps {
  value: DonationData;
  onChange: (value: DonationData) => void;
  globalParamNames: string[];
  schema?: JsonSchema;
  validationResult?: ValidationResult;
  disabled?: boolean;
  showRawJson?: boolean;
  onToggleRawJson?: () => void;
  selectedHandler?: string;
  expandedMethods?: Record<string, Set<number>>;
  onToggleMethodExpansion?: (handlerName: string, methodIndex: number) => void;
  extractLemmasFromTokenPatterns?: (tokenPatterns: Array<Array<Record<string, any>>>) => string[];
}

function MethodDonationEditor({ 
  value, 
  onChange, 
  globalParamNames,
  disabled = false,
  selectedHandler,
  expandedMethods,
  onToggleMethodExpansion,
  currentLanguage,
  extractLemmasFromTokenPatterns
}: MethodDonationEditorProps & { currentLanguage?: string }) {
  
  // Real-time analysis for conflict detection
  const { 
    conflicts, 
    analysisStatus
  } = useRealtimeAnalysis(selectedHandler || null, currentLanguage || null, value, {
    debounceMs: 800, // Slightly longer debounce for editing
    autoAnalyze: true,
    enableCaching: true
  });
  
  const v = value ?? { description: '', handler_domain: '', method_donations: [] };
  const set = (k: keyof DonationData, val: any): void => {
    onChange({ ...(value ?? {}), [k]: val });
  };

  // Helper function for checking sync issues
  const hasLemmaSyncIssues = (method: any): boolean => {
    if (!extractLemmasFromTokenPatterns) return false;
    const extractedLemmas = extractLemmasFromTokenPatterns(method.token_patterns || []);
    const currentLemmas = method.lemmas || [];
    return extractedLemmas.some(lemma => !currentLemmas.includes(lemma));
  };

  // Helper functions for method expansion state
  const isMethodExpanded = (methodIndex: number): boolean => {
    return selectedHandler ? (expandedMethods?.[selectedHandler]?.has(methodIndex) || false) : false;
  };

  const toggleMethodExpansion = (methodIndex: number): void => {
    if (selectedHandler && onToggleMethodExpansion) {
      onToggleMethodExpansion(selectedHandler, methodIndex);
    }
  };

  return (
    <div className="space-y-6">
      {/* Real-time Analysis Status */}
      <ConflictStatusBar 
        conflicts={conflicts} 
        status={analysisStatus}
        className="mb-4"
      />
      
      <Section title="Basic Information" defaultCollapsed={false}>
        <div className="space-y-4">
          {/* Structural/Metadata fields - Read only */}
          <div className="p-4 bg-gray-50 rounded-lg border">
            <h4 className="text-sm font-medium text-gray-700 mb-3">Structure & Metadata (Read-only)</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <Input
                  label="Handler Domain"
                  value={v.handler_domain || ''}
                  onChange={() => {}} // No-op since it's readonly
                  disabled={true}
                  required
                />
                <p className="text-xs text-gray-500 mt-1">Defines which handler this donation belongs to</p>
              </div>
              <div>
                <Input
                  label="Language"
                  value={currentLanguage || 'Unknown'}
                  onChange={() => {}} // No-op since it's readonly
                  disabled={true}
                />
                <p className="text-xs text-gray-500 mt-1">Language code for this donation file</p>
              </div>
              <div>
                <Input
                  label="Schema Version"
                  value={v.schema_version || '1.0'}
                  onChange={() => {}} // No-op since it's readonly
                  disabled={true}
                />
                <p className="text-xs text-gray-500 mt-1">JSON schema version used</p>
              </div>
              <div>
                <Input
                  label="Donation Version"
                  value={v.donation_version || '1.0'}
                  onChange={() => {}} // No-op since it's readonly
                  disabled={true}
                />
                <p className="text-xs text-gray-500 mt-1">Content version for caching</p>
              </div>
            </div>
          </div>
          
          {/* Content fields - Editable */}
          <div>
            <Input
              label="Description"
              value={v.description || ''}
              onChange={(val) => set('description', val)}
              disabled={disabled}
              required
            />
            <p className="text-xs text-gray-500 mt-1">Human-readable description of this handler's functionality</p>
          </div>
        </div>
      </Section>

      <Section title="Methods" badge={<Badge variant="info">{v.method_donations?.length || 0} methods</Badge>}>
        {/* Validation summary */}
        {(() => {
          const methodsWithSyncIssues = (v.method_donations || []).filter(hasLemmaSyncIssues);
          if (methodsWithSyncIssues.length > 0) {
            const handleSyncAll = () => {
              const newMethods = [...(v.method_donations || [])];
              let hasChanges = false;
              
              methodsWithSyncIssues.forEach((method, _) => {
                const methodIndex = newMethods.findIndex(m => m === method);
                if (methodIndex !== -1 && extractLemmasFromTokenPatterns) {
                  const extractedLemmas = extractLemmasFromTokenPatterns(method.token_patterns || []);
                  const currentLemmas = method.lemmas || [];
                  const mergedLemmas = [...new Set([...currentLemmas, ...extractedLemmas])];
                  
                  // Only update if there are actually new lemmas to add
                  if (mergedLemmas.length > currentLemmas.length) {
                    newMethods[methodIndex] = { ...method, lemmas: mergedLemmas };
                    hasChanges = true;
                  }
                }
              });
              
              if (hasChanges) {
                set('method_donations', newMethods);
              }
            };
            
            return (
              <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center text-amber-800 text-sm font-medium">
                    <AlertTriangle className="w-4 h-4 mr-2" />
                    Sync Issues Detected
                  </div>
                  <button
                    onClick={handleSyncAll}
                    disabled={disabled}
                    className="flex items-center text-xs px-3 py-1 bg-amber-600 text-white rounded hover:bg-amber-700 disabled:opacity-50 transition-colors"
                    title="Automatically sync lemmas for all methods with issues"
                  >
                    <RefreshCw className="w-3 h-3 mr-1" />
                    Sync All ({methodsWithSyncIssues.length})
                  </button>
                </div>
                <div className="text-amber-700 text-xs">
                  {methodsWithSyncIssues.length} method{methodsWithSyncIssues.length !== 1 ? 's' : ''} ha{methodsWithSyncIssues.length === 1 ? 's' : 've'} lemmas that need to be synced with token patterns. 
                  Use the sync buttons or click "Sync All" to automatically add missing lemmas.
                </div>
              </div>
            );
          }
          return null;
        })()}
        
        <div className="space-y-4">
          {(v.method_donations?.map((method, idx) => {
            const isExpanded = isMethodExpanded(idx);
            const methodName = method.method_name || `Method ${idx + 1}`;
            
            return (
              <div key={idx} className="border rounded-xl bg-white">
                {/* Collapsible Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-100">
                  <button
                    onClick={() => toggleMethodExpansion(idx)}
                    className="flex items-center space-x-2 text-left flex-1 hover:bg-gray-50 -m-2 p-2 rounded-lg transition-colors"
                    disabled={disabled}
                  >
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronRight className="w-4 h-4 text-gray-500" />
                    )}
                    <div>
                      <h4 className="text-sm font-medium text-gray-900">{methodName}</h4>
                      {method.description && (
                        <p className="text-xs text-gray-500 mt-0.5">{method.description}</p>
                      )}
                    </div>
                  </button>
                  <button
                    onClick={() => {
                      const newMethods = v.method_donations.filter((_, i) => i !== idx);
                      set('method_donations', newMethods);
                    }}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                    disabled={disabled}
                    title="Remove method"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                {/* Collapsible Content */}
                {isExpanded && (
                  <div className="p-4">
                    {/* Method Structure - Read only */}
                    <div className="p-3 bg-gray-50 rounded-lg border mb-4">
                      <h5 className="text-xs font-medium text-gray-600 mb-2">Method Structure (Read-only)</h5>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <Input
                            label="Method name"
                            value={method.method_name || ''}
                            onChange={() => {}} // No-op since it's readonly
                            disabled={true}
                            required
                          />
                          <p className="text-xs text-gray-500 mt-1">Python method name - must match handler code</p>
                        </div>
                        <div>
                          <Input
                            label="Intent suffix"
                            value={method.intent_suffix || ''}
                            onChange={() => {}} // No-op since it's readonly
                            disabled={true}
                          />
                          <p className="text-xs text-gray-500 mt-1">Defines intent routing structure</p>
                        </div>
                      </div>
                    </div>
                    
                    {/* Method Content - Editable */}
                    <div className="mb-4">
                      <Input
                        label="Description"
                        value={method.description || ''}
                        onChange={(val) => {
                          const newMethods = [...(v.method_donations || [])];
                          newMethods[idx] = { ...method, description: val };
                          set('method_donations', newMethods);
                        }}
                        disabled={disabled}
                        placeholder="Describe what this method does"
                      />
                      <p className="text-xs text-gray-500 mt-1">Human-readable description of method functionality</p>
                    </div>

                    {/* Method-specific editors */}
                    <div className="space-y-4">
                      <ArrayOfStringsEditor
                        label="Global Parameters"
                        value={method.global_params || []}
                        onChange={(val) => {
                          const newMethods = [...(v.method_donations || [])];
                          newMethods[idx] = { ...method, global_params: val };
                          set('method_donations', newMethods);
                        }}
                        disabled={disabled}
                      />
                      
                      <LemmasEditor
                        value={method.lemmas || []}
                        onChange={(val) => {
                          const newMethods = [...(v.method_donations || [])];
                          newMethods[idx] = { ...method, lemmas: val };
                          set('method_donations', newMethods);
                        }}
                        disabled={disabled}
                        tokenPatterns={method.token_patterns || []}
                        slotPatterns={method.slot_patterns || {}}
                        onAutoSync={() => {
                          if (!extractLemmasFromTokenPatterns) return;
                          const extractedLemmas = extractLemmasFromTokenPatterns(method.token_patterns || []);
                          const currentLemmas = method.lemmas || [];
                          const mergedLemmas = [...new Set([...currentLemmas, ...extractedLemmas])];
                          
                          const newMethods = [...(v.method_donations || [])];
                          newMethods[idx] = { ...method, lemmas: mergedLemmas };
                          set('method_donations', newMethods);
                        }}
                        showSyncWarning={hasLemmaSyncIssues(method)}
                        conflicts={conflicts}
                      />

                      <TokenPatternsEditor
                        value={method.token_patterns || []}
                        onChange={(val) => {
                          const newMethods = [...(v.method_donations || [])];
                          newMethods[idx] = { ...method, token_patterns: val };
                          set('method_donations', newMethods);
                        }}
                        globalParams={globalParamNames}
                        disabled={disabled}
                        currentLemmas={method.lemmas || []}
                        onLemmasSync={(extractedLemmas) => {
                          const currentLemmas = method.lemmas || [];
                          const allExtractedLemmas = extractLemmasFromTokenPatterns?.(method.token_patterns || []) || [];
                          const mergedLemmas = [...new Set([...currentLemmas, ...allExtractedLemmas, ...extractedLemmas])];
                          
                          const newMethods = [...(v.method_donations || [])];
                          newMethods[idx] = { ...method, lemmas: mergedLemmas };
                          set('method_donations', newMethods);
                        }}
                        showSyncIndicator={true}
                      />

                      <SlotPatternsEditor
                        value={method.slot_patterns || {}}
                        onChange={(val) => {
                          const newMethods = [...(v.method_donations || [])];
                          newMethods[idx] = { ...method, slot_patterns: val };
                          set('method_donations', newMethods);
                        }}
                        globalParams={globalParamNames}
                        disabled={disabled}
                      />

                      <ExamplesEditor
                        value={method.examples || []}
                        onChange={(val) => {
                          const newMethods = [...(v.method_donations || [])];
                          newMethods[idx] = { ...method, examples: val };
                          set('method_donations', newMethods);
                        }}
                        globalParams={globalParamNames}
                        disabled={disabled}
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          }) || [])}
          
          <button
            onClick={() => {
              const newMethods = [...(v.method_donations || []), { method_name: '', intent_suffix: '', description: '', phrases: [], parameters: [], token_patterns: [], slot_patterns: {}, examples: [] }];
              set('method_donations', newMethods);
            }}
            className="w-full p-4 border-2 border-dashed border-gray-300 rounded-xl text-gray-600 hover:border-gray-400 hover:text-gray-700 transition-colors"
            disabled={disabled}
          >
            + Add Method
          </button>
        </div>
      </Section>

      {/* Smart Suggestions Panel */}
      {conflicts.length > 0 && (
        <SuggestionPanel 
          conflicts={conflicts}
          onApplySuggestion={(conflictId, suggestion) => {
            console.log('Apply suggestion:', conflictId, suggestion);
            // TODO: Implement suggestion application logic
          }}
          onDismissConflict={(conflictId) => {
            console.log('Dismiss conflict:', conflictId);
            // TODO: Implement conflict dismissal logic
          }}
        />
      )}
    </div>
  );
}

const DonationsPage: React.FC = () => {
  // Helper function to extract lemmas from token patterns and slot patterns
  const extractLemmasFromTokenPatterns = (tokenPatterns: Array<Array<Record<string, any>>>, slotPatterns?: Record<string, Array<Array<Record<string, any>>>>): string[] => {
    const extractedLemmas: Set<string> = new Set();
    
    // Extract from token patterns
    tokenPatterns.forEach(pattern => {
      pattern.forEach(token => {
        if (token.LEMMA) {
          if (typeof token.LEMMA === 'string') {
            extractedLemmas.add(token.LEMMA);
          } else if (token.LEMMA.IN && Array.isArray(token.LEMMA.IN)) {
            token.LEMMA.IN.forEach((lemma: string) => extractedLemmas.add(lemma));
          }
        }
      });
    });
    
    // Extract from slot patterns
    if (slotPatterns) {
      Object.values(slotPatterns).forEach(slotPatternArray => {
        slotPatternArray.forEach(pattern => {
          pattern.forEach(token => {
            if (token.LEMMA) {
              if (typeof token.LEMMA === 'string') {
                extractedLemmas.add(token.LEMMA);
              } else if (token.LEMMA.IN && Array.isArray(token.LEMMA.IN)) {
                token.LEMMA.IN.forEach((lemma: string) => extractedLemmas.add(lemma));
              }
            }
          });
        });
      });
    }
    
    return Array.from(extractedLemmas);
  };

  // Core state - Updated for language-aware architecture
  const [handlersList, setHandlersList] = useState<HandlerLanguageInfo[]>([]);
  const [donations, setDonations] = useState<Record<string, DonationData>>({});
  const [originalDonations, setOriginalDonations] = useState<Record<string, DonationData>>({});
  const [schema, setSchema] = useState<JsonSchema | null>(null);
  const [selectedHandler, setSelectedHandler] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState<Record<string, boolean>>({});

  // Loading and error states
  const [loadingHandlers, setLoadingHandlers] = useState(true);
  const [, setLoadingSchema] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

  // UI state
  const [searchQuery, setSearchQuery] = useState('');
  const [showRawJson, setShowRawJson] = useState(false);
  
  // Method collapsible state - track expanded methods by handler:methodIndex
  const [expandedMethods, setExpandedMethods] = useState<Record<string, Set<number>>>({});

  // Validation state
  const [validationResults, setValidationResults] = useState<Record<string, ValidationResult>>({});

  // Language support state  
  const [selectedLanguage, setSelectedLanguage] = useState<string>('en');
  const [languageCountFilter, setLanguageCountFilter] = useState<'all' | 'single' | 'multiple'>('all');
  
  // Phase 4: Cross-language validation state
  const [validationReport, setValidationReport] = useState<ValidationReport | null>(null);
  const [completenessReport, setCompletenessReport] = useState<CompletenessReport | null>(null);

  // Helper functions for language management
  const getAvailableLanguagesForHandler = (handlerName: string): LanguageInfo[] => {
    const handler = handlersList.find(h => h.handler_name === handlerName);
    if (!handler) return [];
    
    return handler.languages.map(lang => {
      const donationKey = `${handlerName}:${lang}`;
      const donation = donations[donationKey];
      const methodCount = donation?.method_donations?.length || 0;
      const hasValidationErrors = validationResults[donationKey] && !validationResults[donationKey].valid;
      
      return {
        code: lang,
        label: lang.toUpperCase(),
        status: hasValidationErrors ? 'error' as const : 'loaded' as const,
        methodCount,
        lastModified: new Date().toISOString(),
        validationErrors: hasValidationErrors ? validationResults[donationKey].errors.length : 0
      };
    });
  };

  const getSupportedLanguages = (): string[] => {
    const handler = handlersList.find(h => h.handler_name === selectedHandler);
    return handler?.supported_languages || ['en', 'ru'];
  };

  const convertToNestedHasChanges = (flatChanges: Record<string, boolean>): Record<string, Record<string, boolean>> => {
    const nested: Record<string, Record<string, boolean>> = {};
    
    for (const [key, hasChanged] of Object.entries(flatChanges)) {
      if (key.includes(':')) {
        const [handlerName, language] = key.split(':');
        if (!nested[handlerName]) {
          nested[handlerName] = {};
        }
        nested[handlerName][language] = hasChanged;
      }
    }
    
    return nested;
  };

  const handleCreateLanguage = async (language: string, templateFrom?: string) => {
    if (!selectedHandler) return;
    
    try {
      await apiClient.createLanguage(selectedHandler, language, { 
        copyFrom: templateFrom,
        useTemplate: !templateFrom 
      });
      
      // Reload handlers to get updated language list
      await loadHandlers();
      
      // Switch to the new language
      setSelectedLanguage(language);
    } catch (err) {
      console.error('Failed to create language:', err);
      setError(err instanceof Error ? err.message : 'Failed to create language');
    }
  };

  const handleDeleteLanguage = async (language: string) => {
    if (!selectedHandler) return;
    
    try {
      await apiClient.deleteLanguage(selectedHandler, language);
      
      // Reload handlers to get updated language list
      await loadHandlers();
      
      // Switch to default language if current language was deleted
      if (selectedLanguage === language) {
        const handler = handlersList.find(h => h.handler_name === selectedHandler);
        if (handler && handler.languages.length > 0) {
          setSelectedLanguage(handler.default_language || handler.languages[0]);
        }
      }
    } catch (err) {
      console.error('Failed to delete language:', err);
      setError(err instanceof Error ? err.message : 'Failed to delete language');
    }
  };

  // Helper function for method expansion state
  const toggleMethodExpansion = (handlerName: string, methodIndex: number): void => {
    setExpandedMethods(prev => {
      const handlerExpanded = prev[handlerName] || new Set();
      const newExpanded = new Set(handlerExpanded);
      
      if (newExpanded.has(methodIndex)) {
        newExpanded.delete(methodIndex);
      } else {
        newExpanded.add(methodIndex);
      }
      
      return {
        ...prev,
        [handlerName]: newExpanded
      };
    });
  };

  // Phase 4: Cross-language validation functions
  const loadCrossLanguageValidation = async (handlerName: string) => {
    if (!handlerName) return;
    
    try {
      const response: CrossLanguageValidationResponse = await apiClient.getCrossLanguageValidation(handlerName);
      
      setValidationReport(response.parameter_report || null);
      setCompletenessReport(response.completeness_report || null);
    } catch (err) {
      // Gracefully handle 404 - the cross-language validation API might not be implemented yet
      if (err instanceof Error && err.message.includes('404')) {
        console.warn('Cross-language validation API not implemented yet - feature will be hidden');
        setValidationReport(null);
        setCompletenessReport(null);
        return;
      }
      
      console.error('Failed to load cross-language validation:', err);
      setValidationReport(null);
      setCompletenessReport(null);
    }
  };

  const handleRefreshValidation = useCallback(() => {
    if (selectedHandler) {
      loadCrossLanguageValidation(selectedHandler);
    }
  }, [selectedHandler]);

  const handleSyncParameters = useCallback(async (sourceLanguage: string, targetLanguages: string[]) => {
    if (!selectedHandler) return;
    
    try {
      await apiClient.syncParameters(selectedHandler, sourceLanguage, targetLanguages);
      
      // Refresh validation after sync
      await loadCrossLanguageValidation(selectedHandler);
      
      // Reload donations for affected languages
      for (const targetLang of targetLanguages) {
        await loadDonation(selectedHandler, targetLang);
      }
      
      console.log(`Successfully synced parameters from ${sourceLanguage} to ${targetLanguages.join(', ')}`);
    } catch (err) {
      // Handle 404 gracefully - the sync API might not be implemented yet
      if (err instanceof Error && err.message.includes('404')) {
        console.warn('Parameter sync API not implemented yet');
        setError('Parameter synchronization feature is not available yet. Please sync parameters manually.');
        return;
      }
      
      console.error('Failed to sync parameters:', err);
      setError(err instanceof Error ? err.message : 'Failed to sync parameters');
    }
  }, [selectedHandler]);

  // Load initial data
  useEffect(() => {
    Promise.all([
      loadHandlers(),
      loadSchema()
    ]);
  }, []);

  // Load selected donation when handler or language changes
  useEffect(() => {
    if (selectedHandler && selectedLanguage) {
      const donationKey = `${selectedHandler}:${selectedLanguage}`;
      if (!donations[donationKey]) {
        loadDonation(selectedHandler, selectedLanguage);
      }
    }
  }, [selectedHandler, selectedLanguage, donations]);

  // Load cross-language validation when handler changes and has multiple languages
  useEffect(() => {
    if (selectedHandler) {
      const handler = handlersList.find(h => h.handler_name === selectedHandler);
      if (handler && handler.languages.length > 1) {
        loadCrossLanguageValidation(selectedHandler);
      } else {
        // Clear validation for single-language handlers
        setValidationReport(null);
        setCompletenessReport(null);
      }
    }
  }, [selectedHandler, handlersList]);

  const loadHandlers = async (): Promise<void> => {
    try {
      setLoadingHandlers(true);
      setError(null);

      const response: DonationHandlerListResponse = await apiClient.getDonationHandlers();
      setHandlersList(response.handlers || []);

      // Auto-select first handler if none selected
      if (response.handlers && response.handlers.length > 0 && !selectedHandler) {
        setSelectedHandler(response.handlers[0].handler_name);
        // Also set default language for the first handler
        const firstHandler = response.handlers[0];
        if (firstHandler.languages.length > 0) {
          setSelectedLanguage(firstHandler.default_language || firstHandler.languages[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load handlers:', err);
      setError(err instanceof Error ? err.message : 'Failed to load handlers');
    } finally {
      setLoadingHandlers(false);
    }
  };

  const loadSchema = async (): Promise<void> => {
    try {
      setLoadingSchema(true);
      const response = await apiClient.getDonationSchema();
      setSchema(response.json_schema as JsonSchema);
    } catch (err) {
      console.error('Failed to load schema:', err);
      // Schema loading failure is not critical, continue without it
    } finally {
      setLoadingSchema(false);
    }
  };

  const loadDonation = async (handlerName: string, language?: string): Promise<void> => {
    const targetLanguage = language || selectedLanguage;
    if (!targetLanguage) {
      console.warn('No language selected for loading donation');
      return;
    }
    
    try {
      const response: LanguageDonationContentResponse = await apiClient.getLanguageDonation(handlerName, targetLanguage);
      const donationKey = `${handlerName}:${targetLanguage}`;
      
      setDonations(prev => ({
        ...prev,
        [donationKey]: response.donation_data as DonationData
      }));
      setOriginalDonations(prev => ({
        ...prev,
        [donationKey]: JSON.parse(JSON.stringify(response.donation_data as DonationData))
      }));
    } catch (err) {
      // Handle 404 errors gracefully - some handlers might not have donation files yet
      if (err instanceof Error && err.message.includes('404')) {
        console.warn(`No donation file found for handler ${handlerName} - this is normal for handlers without donations`);
        // Create empty donation structure for handlers without donation files
        const emptyDonation: DonationData = {
          description: `Donation configuration for ${handlerName}`,
          handler_domain: handlerName.split('_')[0] || 'general', // Try to infer domain from handler name
          method_donations: []
        };
        setDonations(prev => ({
          ...prev,
          [handlerName]: emptyDonation
        }));
        setOriginalDonations(prev => ({
          ...prev,
          [handlerName]: JSON.parse(JSON.stringify(emptyDonation))
        }));
      } else {
        console.error(`Failed to load donation ${handlerName}:`, err);
        setError(err instanceof Error ? err.message : `Failed to load donation ${handlerName}`);
      }
    }
  };

  const handleDonationChange = useCallback((handlerName: string, newDonation: DonationData): void => {
    setDonations(prev => ({
      ...prev,
      [handlerName]: newDonation
    }));

    // Check if changed
    const original = originalDonations[handlerName];
    const isChanged = JSON.stringify(newDonation) !== JSON.stringify(original);
    
    setHasChanges(prev => ({
      ...prev,
      [handlerName]: isChanged
    }));
  }, [originalDonations]);


  // Get global parameter names for the current donation
  const globalParamNames = useMemo(() => {
    if (!selectedHandler || !selectedLanguage) return [];
    const donationKey = `${selectedHandler}:${selectedLanguage}`;
    if (!donations[donationKey]) return [];
    const donation = donations[donationKey];
    const allParams = new Set<string>();
    
    donation.method_donations?.forEach(method => {
      method.global_params?.forEach(param => allParams.add(param));
    });
    
    return Array.from(allParams).sort();
  }, [donations, selectedHandler]);

  const handleSave = async (): Promise<void> => {
    if (!selectedHandler || !selectedLanguage) return;

    try {
      setSaveStatus('saving');
      setError(null);

      const donationKey = `${selectedHandler}:${selectedLanguage}`;
      const donationData = donations[donationKey];
      
      if (!donationData) {
        throw new Error('No donation data to save');
      }

      await apiClient.updateLanguageDonation(selectedHandler, selectedLanguage, donationData);

      // Update original to mark as saved
      setOriginalDonations(prev => ({
        ...prev,
        [donationKey]: JSON.parse(JSON.stringify(donationData))
      }));

      setHasChanges(prev => ({
        ...prev,
        [donationKey]: false
      }));

      setSaveStatus('saved');
      
      // Reset save status after 2 seconds
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (err) {
      console.error('Failed to save donation:', err);
      setError(err instanceof Error ? err.message : 'Failed to save donation');
      setSaveStatus('error');
    }
  };

  const handleValidate = async (): Promise<ValidationResult> => {
    if (!selectedHandler || !selectedLanguage) {
      return { valid: false, errors: ['No handler or language selected'], warnings: [] };
    }

    try {
      const donationKey = `${selectedHandler}:${selectedLanguage}`;
      const donationData = donations[donationKey];
      
      if (!donationData) {
        return { valid: false, errors: ['No donation data to validate'], warnings: [] };
      }
      
      const response = await apiClient.validateLanguageDonation(selectedHandler, selectedLanguage, donationData);
      
      // Convert new API response structure to legacy ValidationResult format
      const validationResult: ValidationResult = {
        valid: response.is_valid,
        errors: response.errors?.map((err: any) => err.msg) || [],
        warnings: response.warnings?.map((warn: any) => warn.message) || [],
        details: response
      };

      setValidationResults(prev => ({
        ...prev,
        [donationKey]: validationResult
      }));

      return validationResult;
    } catch (err: any) {
      console.error('Validation failed:', err);
      const errorResult: ValidationResult = {
        valid: false,
        errors: [err instanceof Error ? err.message : 'Validation failed'],
        warnings: []
      };
      
      setValidationResults(prev => ({
        ...prev,
        [selectedHandler]: errorResult
      }));

      return errorResult;
    }
  };

  const handleCancel = (): void => {
    if (!selectedHandler || !selectedLanguage) return;

    const donationKey = `${selectedHandler}:${selectedLanguage}`;
    const original = originalDonations[donationKey];
    if (original) {
      setDonations(prev => ({
        ...prev,
        [donationKey]: JSON.parse(JSON.stringify(original))
      }));
      
      setHasChanges(prev => ({
        ...prev,
        [donationKey]: false
      }));
    }
  };

  // No need for filtering logic here - it's handled by HandlerList component

  if (loadingHandlers) {
    return (
      <div className="p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded mb-4"></div>
          <div className="grid grid-cols-4 gap-4">
            <div className="h-96 bg-gray-200 rounded"></div>
            <div className="col-span-3 h-96 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 mr-3 flex-shrink-0" />
            <div>
              <h3 className="text-red-800 font-medium">Failed to load donations</h3>
              <p className="text-red-700 text-sm mt-1">{error}</p>
              <button
                onClick={() => {
                  setError(null);
                  loadHandlers();
                }}
                className="mt-3 px-3 py-1 bg-red-100 text-red-800 rounded text-sm hover:bg-red-200 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Main Content Area with Sidebar */}
      <div className="flex-1 flex">
        {/* Handler List */}
        <HandlerList
          handlers={handlersList}
          selectedHandler={selectedHandler}
          selectedLanguage={selectedLanguage}
          onSelect={setSelectedHandler}
          onLanguageSelect={(handlerName, language) => {
            setSelectedHandler(handlerName);
            setSelectedLanguage(language);
          }}
          onCreateLanguage={handleCreateLanguage}
          onDeleteLanguage={handleDeleteLanguage}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          filterLanguageCount={languageCountFilter}
          onFilterLanguageCountChange={setLanguageCountFilter}
          hasChanges={convertToNestedHasChanges(hasChanges)}
          loading={loadingHandlers}
          error={error}
        />

      {/* Main Editor Area */}
      <div className="flex-1 flex flex-col pb-20">
        {selectedHandler ? (
          <>
            {/* Language Tabs */}
            <LanguageTabs
              activeLanguage={selectedLanguage}
              availableLanguages={getAvailableLanguagesForHandler(selectedHandler)}
              supportedLanguages={getSupportedLanguages()}
              onLanguageChange={setSelectedLanguage}
              onCreateLanguage={handleCreateLanguage}
              onDeleteLanguage={handleDeleteLanguage}
              disabled={saveStatus === 'saving'}
              // Phase 4: Cross-language validation props
              handlerName={selectedHandler}
              validationReport={validationReport}
              completenessReport={completenessReport}
              onRefreshValidation={handleRefreshValidation}
              onSyncParameters={handleSyncParameters}
            />

            {/* Cross-Language Validation Panel */}
            {selectedHandler && (
              <div className="border-b border-gray-200 p-4 bg-gray-50">
                <CrossLanguageValidation
                  handlerName={selectedHandler}
                  handlerInfo={handlersList.find(h => h.handler_name === selectedHandler)!}
                  activeLanguage={selectedLanguage}
                  validationReport={validationReport}
                  completenessReport={completenessReport}
                  onRefreshValidation={handleRefreshValidation}
                  onSyncParameters={handleSyncParameters}
                  isLoading={saveStatus === 'saving'}
                  disabled={saveStatus === 'saving'}
                />
              </div>
            )}

            {/* Header */}
            <div className="border-b border-gray-200 p-6 bg-white">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">{selectedHandler}</h1>
                  {selectedLanguage && donations[`${selectedHandler}:${selectedLanguage}`] && (
                    <p className="text-gray-600 mt-1">
                      {donations[`${selectedHandler}:${selectedLanguage}`].description || 'No description'}
                    </p>
                  )}
                </div>
                {selectedHandler && selectedLanguage && hasChanges[`${selectedHandler}:${selectedLanguage}`] && (
                  <Badge variant="warning">Unsaved Changes</Badge>
                )}
              </div>
            </div>

            {/* Editor Content */}
            <div className="flex-1 overflow-auto p-6">
              {selectedLanguage && donations[`${selectedHandler}:${selectedLanguage}`] ? (
                <div>
                  {/* Show notice for empty donations */}
                  {donations[`${selectedHandler}:${selectedLanguage}`].method_donations?.length === 0 && (
                    <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                      <div className="flex items-start">
                        <AlertCircle className="w-5 h-5 text-blue-500 mt-0.5 mr-3 flex-shrink-0" />
                        <div>
                          <h3 className="text-blue-800 font-medium">New Donation Configuration</h3>
                          <p className="text-blue-700 text-sm mt-1">
                            This handler doesn't have a donation file yet. You can create one by adding methods below.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  <MethodDonationEditor
                    value={donations[`${selectedHandler}:${selectedLanguage}`]}
                    onChange={(newDonation) => handleDonationChange(`${selectedHandler}:${selectedLanguage}`, newDonation)}
                    globalParamNames={globalParamNames}
                    schema={schema || undefined}
                    validationResult={selectedLanguage ? validationResults[`${selectedHandler}:${selectedLanguage}`] : undefined}
                    disabled={saveStatus === 'saving'}
                    showRawJson={showRawJson}
                    onToggleRawJson={() => setShowRawJson(!showRawJson)}
                    selectedHandler={selectedHandler}
                    expandedMethods={expandedMethods}
                    onToggleMethodExpansion={toggleMethodExpansion}
                    currentLanguage={selectedLanguage}
                    extractLemmasFromTokenPatterns={extractLemmasFromTokenPatterns}
                  />
                </div>
              ) : (
                <div className="flex items-center justify-center h-64">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <span className="ml-2 text-gray-600">Loading donation...</span>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full bg-gray-50">
            <div className="text-center">
              <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-xl font-medium text-gray-900 mb-2">Select a handler</h3>
              <p className="text-gray-500">
                Choose a handler from the list to edit its donation configuration
              </p>
            </div>
          </div>
        )}
      </div>
      </div>

      {/* Apply Changes Bar - Positioned at bottom of entire page */}
      <ApplyChangesBar
        visible={!!(selectedHandler && selectedLanguage && hasChanges[`${selectedHandler}:${selectedLanguage}`])}
        selectedHandler={selectedHandler || undefined}
        hasUnsavedChanges={selectedHandler && selectedLanguage ? hasChanges[`${selectedHandler}:${selectedLanguage}`] || false : false}
        onSave={handleSave}
        onValidate={handleValidate}
        onCancel={handleCancel}
        loading={saveStatus === 'saving'}
        lastSaved={saveStatus === 'saved' ? new Date() : undefined}
        nluContext={{
          language: selectedLanguage || undefined,
          donationData: selectedHandler && selectedLanguage ? donations[`${selectedHandler}:${selectedLanguage}`] : undefined,
          enableEnhancedValidation: true
        }}
      />
    </div>
  );
};

export default DonationsPage;
