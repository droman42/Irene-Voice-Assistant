/**
 * LocalizationsPage - Main page for managing localization data
 * 
 * Provides domain-based localization editing following the same patterns
 * as DonationsPage but adapted for domain structure instead of handlers.
 */

import { useState, useEffect, useCallback } from 'react';
import { Globe, Loader, AlertCircle, Filter, RefreshCw } from 'lucide-react';
import { 
  DomainLanguageInfo, 
  LocalizationContentResponse
} from '@/types/api';

import HandlerList from '@/components/donations/HandlerList';
import LanguageTabs from '@/components/donations/LanguageTabs';
import LocalizationEditor from '@/components/editors/LocalizationEditor';
import Section from '@/components/ui/Section';
import Badge from '@/components/ui/Badge';
import apiClient from '@/utils/apiClient';

interface LocalizationChanges {
  [domainLanguageKey: string]: {
    domain: string;
    language: string;
    data: Record<string, any>;
    hasChanges: boolean;
  };
}

const LocalizationsPage: React.FC = () => {
  const [domains, setDomains] = useState<DomainLanguageInfo[]>([]);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<string>('en');
  const [localizationData, setLocalizationData] = useState<Record<string, any>>({});
  const [changes, setChanges] = useState<LocalizationChanges>({});
  const [metadata, setMetadata] = useState<LocalizationContentResponse['metadata'] | null>(null);
  
  // UI state
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [isValid, setIsValid] = useState(true);
  
  // Filters
  const [languageFilter, setLanguageFilter] = useState<'all' | 'single' | 'multiple'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const currentKey = selectedDomain ? `${selectedDomain}:${selectedLanguage}` : '';

  // Load domains on mount
  useEffect(() => {
    loadDomains();
  }, []);

  // Load localization data when domain/language changes
  useEffect(() => {
    if (selectedDomain && selectedLanguage) {
      loadLocalizationData(selectedDomain, selectedLanguage);
    }
  }, [selectedDomain, selectedLanguage]);

  const loadDomains = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await apiClient.getLocalizationDomains();
      setDomains(response.domains);
      
      // Auto-select first domain if none selected
      if (!selectedDomain && response.domains.length > 0) {
        setSelectedDomain(response.domains[0].domain);
      }
    } catch (err) {
      console.error('Failed to load domains:', err);
      setError('Failed to load localization domains');
    } finally {
      setLoading(false);
    }
  };

  const loadLocalizationData = async (domain: string, language: string) => {
    try {
      setError(null);
      
      const response = await apiClient.getLanguageLocalization(domain, language);
      setLocalizationData(response.localization_data);
      setMetadata(response.metadata);
      
      // Clear changes for this key since we're loading fresh data
      const newChanges = { ...changes };
      delete newChanges[`${domain}:${language}`];
      setChanges(newChanges);
      
    } catch (err) {
      console.error('Failed to load localization data:', err);
      setError(`Failed to load ${language} localization for domain ${domain}`);
    }
  };

  const handleLocalizationChange = useCallback((newData: Record<string, any>) => {
    setLocalizationData(newData);
    
    // Track changes
    if (selectedDomain) {
      setChanges(prev => ({
        ...prev,
        [currentKey]: {
          domain: selectedDomain,
          language: selectedLanguage,
          data: newData,
          hasChanges: true
        }
      }));
    }
  }, [selectedDomain, selectedLanguage, currentKey]);

  const handleValidationChange = useCallback((valid: boolean, errors: string[]) => {
    setIsValid(valid);
    setValidationErrors(errors);
  }, []);

  const handleSaveChanges = async () => {
    try {
      setSaving(true);
      setError(null);
      
      const changesToSave = Object.values(changes).filter(change => change.hasChanges);
      
      for (const change of changesToSave) {
        await apiClient.updateLanguageLocalization(
          change.domain,
          change.language,
          change.data,
          { validateBeforeSave: true, triggerReload: true }
        );
      }
      
      // Clear changes after successful save
      setChanges({});
      
      // Reload current data
      if (selectedDomain) {
        await loadLocalizationData(selectedDomain, selectedLanguage);
      }
      
      console.log('All localization changes saved successfully');
      
    } catch (err) {
      console.error('Failed to save changes:', err);
      setError('Failed to save localization changes');
    } finally {
      setSaving(false);
    }
  };

  const handleDiscardChanges = () => {
    setChanges({});
    
    // Reload current data
    if (selectedDomain) {
      loadLocalizationData(selectedDomain, selectedLanguage);
    }
  };

  const handleDomainSelect = (domain: string) => {
    setSelectedDomain(domain);
    
    // Auto-select first available language for new domain
    const domainInfo = domains.find(d => d.domain === domain);
    if (domainInfo && domainInfo.languages.length > 0) {
      const preferredLang = domainInfo.languages.includes('en') ? 'en' : domainInfo.languages[0];
      setSelectedLanguage(preferredLang);
    }
  };

  const filteredDomains = domains.filter(domain => {
    switch (languageFilter) {
      case 'single':
        return domain.total_languages === 1;
      case 'multiple':
        return domain.total_languages > 1;
      default:
        return true;
    }
  });

  const selectedDomainInfo = domains.find(d => d.domain === selectedDomain);
  const hasChanges = Object.values(changes).some(change => change.hasChanges);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader className="w-8 h-8 animate-spin text-blue-600" />
        <span className="ml-2 text-gray-600">Loading localization domains...</span>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Localizations</h1>
          <p className="text-gray-600">Manage domain-based localization data for different languages</p>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={loadDomains}
            className="flex items-center gap-2 px-3 py-2 text-gray-600 hover:text-gray-800 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-500" />
            <span className="text-red-800 font-medium">Error</span>
          </div>
          <p className="text-red-700 mt-1">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Domain List */}
        <div className="lg:col-span-1">
          <Section title="Domains" className="h-fit">
            {/* Filter Controls */}
            <div className="mb-4 flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-500" />
              <select
                value={languageFilter}
                onChange={(e) => setLanguageFilter(e.target.value as 'all' | 'single' | 'multiple')}
                className="text-sm border border-gray-200 rounded px-2 py-1 bg-white"
              >
                <option value="all">All Domains</option>
                <option value="single">Single Language</option>
                <option value="multiple">Multiple Languages</option>
              </select>
            </div>

            {/* Domain List */}
            <HandlerList
              handlers={filteredDomains.map(domain => ({
                handler_name: domain.domain,
                languages: domain.languages,
                supported_languages: domain.supported_languages,
                total_languages: domain.total_languages,
                default_language: domain.default_language,
                total_methods: 0
              }))}
              selectedHandler={selectedDomain}
              selectedLanguage={selectedLanguage}
              onSelect={handleDomainSelect}
              onLanguageSelect={() => {}} // Not used for domain-based navigation
              onCreateLanguage={() => {}} // Not used here
              onDeleteLanguage={() => {}} // Not used here
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              filterLanguageCount={languageFilter}
              onFilterLanguageCountChange={setLanguageFilter}
              hasChanges={{}}
              loading={loading}
              error={error}
            />
          </Section>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-3 space-y-6">
          {selectedDomain ? (
            <>
              {/* Language Tabs */}
              {selectedDomainInfo && (
                <LanguageTabs
                  activeLanguage={selectedLanguage}
                  availableLanguages={selectedDomainInfo.languages.map(lang => ({
                    code: lang,
                    label: lang.toUpperCase(),
                    status: 'loaded' as const,
                    validationErrors: lang === selectedLanguage ? validationErrors.length : 0
                  }))}
                  supportedLanguages={selectedDomainInfo.supported_languages}
                  onLanguageChange={setSelectedLanguage}
                  onCreateLanguage={(lang, templateFrom) => {
                    console.log('Create language:', lang, 'from:', templateFrom);
                    // TODO: Implement language creation
                  }}
                  onDeleteLanguage={(lang) => {
                    console.log('Delete language:', lang);
                    // TODO: Implement language deletion
                  }}
                />
              )}

              {/* Localization Editor */}
              <Section title={`${selectedDomain} - ${selectedLanguage.toUpperCase()}`}>
                <div className="space-y-4">
                  {/* Metadata */}
                  {metadata && (
                    <div className="flex items-center gap-4 text-sm text-gray-600 bg-gray-50 p-3 rounded">
                      <Badge variant="default">
                        {metadata.entry_count} entries
                      </Badge>
                      <span>
                        File: {metadata.file_path}
                      </span>
                      <span>
                        Size: {(metadata.file_size / 1024).toFixed(1)} KB
                      </span>
                    </div>
                  )}

                  {/* Validation Status */}
                  {!isValid && validationErrors.length > 0 && (
                    <div className="p-3 bg-yellow-50 border border-yellow-200 rounded">
                      <h4 className="font-medium text-yellow-800 mb-2">Validation Issues:</h4>
                      <ul className="text-sm text-yellow-700 space-y-1">
                        {validationErrors.map((error, index) => (
                          <li key={index}>• {error}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Editor */}
                  <LocalizationEditor
                    value={localizationData}
                    onChange={handleLocalizationChange}
                    domain={selectedDomain}
                    onValidationChange={handleValidationChange}
                  />
                </div>
              </Section>
            </>
          ) : (
            <Section title="Select a Domain">
              <div className="text-center py-12 text-gray-500">
                <Globe className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <h3 className="text-lg font-medium mb-2">No Domain Selected</h3>
                <p>Choose a domain from the list to start editing localizations</p>
              </div>
            </Section>
          )}
        </div>
      </div>

      {/* Simple Save Controls */}
      {hasChanges && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 z-50">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">
                {Object.values(changes).filter(c => c.hasChanges).length} unsaved changes
              </span>
              {!isValid && (
                <span className="text-sm text-red-600">
                  ⚠ Validation errors present
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleDiscardChanges}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
                disabled={saving}
              >
                Discard
              </button>
              <button
                onClick={handleSaveChanges}
                disabled={saving || !isValid}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 transition-colors flex items-center gap-2"
              >
                {saving ? (
                  <>
                    <Loader className="w-4 h-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save All Changes'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LocalizationsPage;
