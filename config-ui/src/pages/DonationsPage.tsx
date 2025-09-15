/**
 * DonationsPage Component - Main donations management interface
 * 
 * Integrates handler list, donation editor, and apply changes workflow
 * with full API integration for real-time donation management.
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { AlertCircle, Trash2, FileText, ChevronDown, ChevronRight } from 'lucide-react';

// Import components
import HandlerList from '@/components/donations/HandlerList';
import ApplyChangesBar from '@/components/donations/ApplyChangesBar';

// Import existing form components
import Section from '@/components/ui/Section';
import Input from '@/components/ui/Input';
import Badge from '@/components/ui/Badge';
import ArrayOfStringsEditor from '@/components/editors/ArrayOfStringsEditor';
// import ParameterListEditor from '@/components/editors/ParameterListEditor';
import TokenPatternsEditor from '@/components/editors/TokenPatternsEditor';
import SlotPatternsEditor from '@/components/editors/SlotPatternsEditor';
import ExamplesEditor from '@/components/editors/ExamplesEditor';

import apiClient from '@/utils/apiClient';
import type { 
  DonationData, 
  DonationListItem,
  ValidationResult,
  JsonSchema
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
}

function MethodDonationEditor({ 
  value, 
  onChange, 
  globalParamNames,
  disabled = false,
  selectedHandler,
  expandedMethods,
  onToggleMethodExpansion
}: MethodDonationEditorProps) {
  const v = value ?? { description: '', handler_domain: '', method_donations: [] };
  const set = (k: keyof DonationData, val: any): void => {
    onChange({ ...(v ?? {}), [k]: val });
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
      <Section title="Basic Information" defaultCollapsed={false}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="Description"
            value={v.description || ''}
            onChange={(val) => set('description', val)}
            disabled={disabled}
            required
          />
          <Input
            label="Domain"
            value={v.handler_domain || ''}
            onChange={(val) => set('handler_domain', val)}
            disabled={disabled}
            required
          />
        </div>
      </Section>

      <Section title="Methods" badge={<Badge variant="info">{v.method_donations?.length || 0} methods</Badge>}>
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
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                      <Input
                        label="Method name"
                        value={method.method_name || ''}
                        onChange={(val) => {
                          const newMethods = [...(v.method_donations || [])];
                          newMethods[idx] = { ...method, method_name: val };
                          set('method_donations', newMethods);
                        }}
                        disabled={disabled}
                        required
                      />
                      <Input
                        label="Intent suffix"
                        value={method.intent_suffix || ''}
                        onChange={(val) => {
                          const newMethods = [...(v.method_donations || [])];
                          newMethods[idx] = { ...method, intent_suffix: val };
                          set('method_donations', newMethods);
                        }}
                        disabled={disabled}
                        placeholder="e.g., hello, goodbye"
                      />
                    </div>
                    
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
                      
                      <TokenPatternsEditor
                        value={method.token_patterns || []}
                        onChange={(val) => {
                          const newMethods = [...(v.method_donations || [])];
                          newMethods[idx] = { ...method, token_patterns: val };
                          set('method_donations', newMethods);
                        }}
                        globalParams={globalParamNames}
                        disabled={disabled}
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
    </div>
  );
}

const DonationsPage: React.FC = () => {
  // Core state
  const [handlersList, setHandlersList] = useState<DonationListItem[]>([]);
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
  const [filterDomain, setFilterDomain] = useState('');
  const [filterMethodCount, setFilterMethodCount] = useState('');
  const [filterModified, setFilterModified] = useState(false);
  const [bulkSelection, setBulkSelection] = useState<string[]>([]);
  const [showRawJson, setShowRawJson] = useState(false);
  
  // Method collapsible state - track expanded methods by handler:methodIndex
  const [expandedMethods, setExpandedMethods] = useState<Record<string, Set<number>>>({});

  // Validation state
  const [validationResults, setValidationResults] = useState<Record<string, ValidationResult>>({});

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

  // Load initial data
  useEffect(() => {
    Promise.all([
      loadHandlers(),
      loadSchema()
    ]);
  }, []);

  // Load selected donation when handler changes
  useEffect(() => {
    if (selectedHandler && !donations[selectedHandler]) {
      loadDonation(selectedHandler);
    }
  }, [selectedHandler, donations]);

  const loadHandlers = async (): Promise<void> => {
    try {
      setLoadingHandlers(true);
      setError(null);

      const response = await apiClient.getDonations();
      setHandlersList(response.donations || []);

      // Auto-select first handler if none selected
      if (response.donations && response.donations.length > 0 && !selectedHandler) {
        setSelectedHandler(response.donations[0].handler_name);
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
      setSchema(response.schema as JsonSchema);
    } catch (err) {
      console.error('Failed to load schema:', err);
      // Schema loading failure is not critical, continue without it
    } finally {
      setLoadingSchema(false);
    }
  };

  const loadDonation = async (handlerName: string): Promise<void> => {
    try {
      const response = await apiClient.getDonation(handlerName);
      setDonations(prev => ({
        ...prev,
        [handlerName]: response.donation_data as DonationData
      }));
      setOriginalDonations(prev => ({
        ...prev,
        [handlerName]: JSON.parse(JSON.stringify(response.donation_data as DonationData))
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
    if (!selectedHandler || !donations[selectedHandler]) return [];
    const donation = donations[selectedHandler];
    const allParams = new Set<string>();
    
    donation.method_donations?.forEach(method => {
      method.global_params?.forEach(param => allParams.add(param));
    });
    
    return Array.from(allParams).sort();
  }, [donations, selectedHandler]);

  const handleSave = async (): Promise<void> => {
    if (!selectedHandler) return;

    try {
      setSaveStatus('saving');
      setError(null);

      const donationData = donations[selectedHandler];
      await apiClient.updateDonation(selectedHandler, donationData);

      // Update original to mark as saved
      setOriginalDonations(prev => ({
        ...prev,
        [selectedHandler]: JSON.parse(JSON.stringify(donationData))
      }));

      setHasChanges(prev => ({
        ...prev,
        [selectedHandler]: false
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
    if (!selectedHandler) {
      return { valid: false, errors: ['No handler selected'], warnings: [] };
    }

    try {
      const donationData = donations[selectedHandler];
      const response = await apiClient.validateDonation(selectedHandler, donationData);
      
      // Convert new API response structure to legacy ValidationResult format
      const validationResult: ValidationResult = {
        valid: response.is_valid,
        errors: response.errors?.map(err => err.msg) || [],
        warnings: response.warnings?.map(warn => warn.message) || [],
        details: response
      };

      setValidationResults(prev => ({
        ...prev,
        [selectedHandler]: validationResult
      }));

      return validationResult;
    } catch (err) {
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
    if (!selectedHandler) return;

    const original = originalDonations[selectedHandler];
    if (original) {
      setDonations(prev => ({
        ...prev,
        [selectedHandler]: JSON.parse(JSON.stringify(original))
      }));
      
      setHasChanges(prev => ({
        ...prev,
        [selectedHandler]: false
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
    <div className="h-full flex">
      {/* Handler List */}
      <HandlerList
        handlers={handlersList}
        selectedHandler={selectedHandler || undefined}
        onSelect={setSelectedHandler}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        filterDomain={filterDomain}
        onFilterDomainChange={setFilterDomain}
        filterMethodCount={filterMethodCount}
        onFilterMethodCountChange={setFilterMethodCount}
        filterModified={filterModified}
        onFilterModifiedChange={setFilterModified}
        bulkSelection={bulkSelection}
        onBulkSelectionChange={setBulkSelection}
        hasChanges={hasChanges}
        loading={loadingHandlers}
        error={error || undefined}
      />

      {/* Main Editor Area */}
      <div className="flex-1 flex flex-col">
        {selectedHandler ? (
          <>
            {/* Header */}
            <div className="border-b border-gray-200 p-6 bg-white">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">{selectedHandler}</h1>
                  {donations[selectedHandler] && (
                    <p className="text-gray-600 mt-1">
                      {donations[selectedHandler].description || 'No description'}
                    </p>
                  )}
                </div>
                {hasChanges[selectedHandler] && (
                  <Badge variant="warning">Unsaved Changes</Badge>
                )}
              </div>
            </div>

            {/* Editor Content */}
            <div className="flex-1 overflow-auto p-6">
              {donations[selectedHandler] ? (
                <div>
                  {/* Show notice for empty donations */}
                  {donations[selectedHandler].method_donations?.length === 0 && (
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
                    value={donations[selectedHandler]}
                    onChange={(newDonation) => handleDonationChange(selectedHandler, newDonation)}
                    globalParamNames={globalParamNames}
                    schema={schema || undefined}
                    validationResult={validationResults[selectedHandler]}
                    disabled={saveStatus === 'saving'}
                    showRawJson={showRawJson}
                    onToggleRawJson={() => setShowRawJson(!showRawJson)}
                    selectedHandler={selectedHandler}
                    expandedMethods={expandedMethods}
                    onToggleMethodExpansion={toggleMethodExpansion}
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

      {/* Apply Changes Bar */}
      <ApplyChangesBar
        visible={!!(selectedHandler && hasChanges[selectedHandler])}
        selectedHandler={selectedHandler || undefined}
        hasUnsavedChanges={selectedHandler ? hasChanges[selectedHandler] || false : false}
        onSave={handleSave}
        onValidate={handleValidate}
        onCancel={handleCancel}
        loading={saveStatus === 'saving'}
        lastSaved={saveStatus === 'saved' ? new Date() : undefined}
      />
    </div>
  );
};

export default DonationsPage;
