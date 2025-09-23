/**
 * ConfigurationPage Component - Pydantic-driven TOML configuration management
 * 
 * Implements three-level accordion structure for managing system configuration:
 * Level 1: Major sections (Core, TTS, Audio, etc.) - collapsed by default
 * Level 2: Provider groups - collapsed by default
 * Level 3: Key-value pairs - auto-generated from Pydantic schema
 */

import React, { useState, useEffect } from 'react';
import { Settings, AlertCircle, CheckCircle, Loader, RefreshCw } from 'lucide-react';
import apiClient from '@/utils/apiClient';
import ConfigSection from '@/components/editors/ConfigSection';
import TomlPreview from '@/components/editors/TomlPreview';
import ApplyChangesBar from '@/components/common/ApplyChangesBar';
import type { CoreConfig, ConfigSchemaResponse, ConfigStatusResponse, ValidationResult } from '@/types/api';

interface ConfigurationPageState {
  config: CoreConfig | null;
  originalConfig: CoreConfig | null;
  schema: ConfigSchemaResponse;
  configStatus: ConfigStatusResponse | null;
  sectionChanges: Record<string, boolean>;
  loading: boolean;
  error: string | null;
  connectionStatus: 'connected' | 'disconnected' | 'checking';
}

const ConfigurationPage: React.FC = () => {
  const [state, setState] = useState<ConfigurationPageState>({
    config: null,
    originalConfig: null,
    schema: {} as ConfigSchemaResponse,
    configStatus: null,
    sectionChanges: {},
    loading: true,
    error: null,
    connectionStatus: 'checking'
  });

  const [showPreview, setShowPreview] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);

  // Helper function to get config filename from path
  const getConfigFileName = (): string => {
    if (!state.configStatus?.config_path) {
      return 'config.toml';
    }
    const path = state.configStatus.config_path;
    return path.split(/[/\\]/).pop() || 'config.toml';
  };

  // Auto-generated section order and titles from backend
  const [sectionOrder, setSectionOrder] = useState<string[]>([]);
  const [sectionTitles, setSectionTitles] = useState<Record<string, string>>({});

  useEffect(() => {
    loadConfiguration();
    loadSectionOrderAndTitles();
  }, []);

  const loadSectionOrderAndTitles = async () => {
    try {
      // Use proper API client method with TypeScript types
      const response = await apiClient.getConfigSectionOrder();
      setSectionOrder(response.section_order || []);
      setSectionTitles(response.section_titles || {});
    } catch (error) {
      console.error('Failed to load section order and titles:', error);
      // Fallback to basic section discovery if API fails
      if (state.config) {
        const availableSections = Object.keys(state.config);
        setSectionOrder(availableSections.sort());
        
        // Generate basic titles for fallback
        const fallbackTitles: Record<string, string> = {};
        availableSections.forEach(section => {
          fallbackTitles[section] = section.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
        });
        setSectionTitles(fallbackTitles);
      }
    }
  };

  // Update section order and titles when config changes
  useEffect(() => {
    if (state.config && sectionOrder.length === 0) {
      loadSectionOrderAndTitles();
    }
  }, [state.config, sectionOrder.length]);

  const loadConfiguration = async () => {
    setState(prev => ({ ...prev, loading: true, error: null, connectionStatus: 'checking' }));

    try {
      // Check connection first
      const connected = await apiClient.checkConnection();
      if (!connected) {
        setState(prev => ({ 
          ...prev, 
          connectionStatus: 'disconnected',
          error: 'Cannot connect to Irene API. Please ensure the server is running.',
          loading: false 
        }));
        return;
      }

      // Load configuration, schema, and status in parallel
      const [configData, schemaData, statusData] = await Promise.all([
        apiClient.getConfig(),
        apiClient.getConfigSchema(),
        apiClient.getConfigStatus()
      ]);

      setState(prev => ({
        ...prev,
        config: configData,
        originalConfig: JSON.parse(JSON.stringify(configData)), // Deep copy
        schema: schemaData,
        configStatus: statusData,
        connectionStatus: 'connected',
        loading: false
      }));

    } catch (error) {
      console.error('Failed to load configuration:', error);
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to load configuration',
        connectionStatus: 'disconnected',
        loading: false
      }));
    }
  };

  const updateSection = (sectionName: string, sectionData: any) => {
    setState(prev => {
      if (!prev.config || !prev.originalConfig) return prev;
      
      const newConfig = { ...prev.config, [sectionName]: sectionData };
      const hasChanges = JSON.stringify(sectionData) !== JSON.stringify((prev.originalConfig as any)?.[sectionName]);
      
      return {
        ...prev,
        config: newConfig,
        sectionChanges: { ...prev.sectionChanges, [sectionName]: hasChanges }
      };
    });
  };

  const validateSection = async (sectionName: string) => {
    if (!state.config) return { valid: false, errors: [{ message: 'No configuration loaded' }] };
    
    try {
      const result = await apiClient.validateConfigSection(sectionName, (state.config as any)[sectionName]);
      return {
        valid: result.valid,
        errors: result.validation_errors || []
      };
    } catch (error) {
      return {
        valid: false,
        errors: [{ message: error instanceof Error ? error.message : 'Validation failed' }]
      };
    }
  };

  const applySection = async (sectionName: string) => {
    if (!state.config) throw new Error('No configuration loaded');
    
    try {
      // Use comment-preserving TOML save method (Phase 5 enhancement)
      const sectionData = (state.config as any)[sectionName];
      const tomlResult = await apiClient.applySectionToToml(sectionName, sectionData);
      
      if (tomlResult.success && tomlResult.comments_preserved) {
        // Save the updated TOML content with comments preserved
        const saveResult = await apiClient.saveRawToml(tomlResult.toml_content, false); // Skip validation since it's already validated
        
        if (saveResult.success) {
          // Update original config to reflect saved state
          setState(prev => {
            if (!prev.config || !prev.originalConfig) return prev;
            return {
              ...prev,
              originalConfig: { ...prev.originalConfig, [sectionName]: (prev.config as any)[sectionName] },
              sectionChanges: { ...prev.sectionChanges, [sectionName]: false }
            };
          });
          
          // Show success notification
          console.log(`✅ Section '${sectionName}' saved with comments preserved`);
          if (saveResult.backup_created) {
            console.log(`📁 Backup created: ${saveResult.backup_created}`);
          }
          
          return saveResult;
        }
      }
      
      // Fallback to traditional section update if TOML method fails
      console.warn('TOML preservation failed, falling back to traditional section update');
      const result = await apiClient.updateConfigSection(sectionName, sectionData);
      
      if (result.success) {
        // Update original config to reflect saved state
        setState(prev => {
          if (!prev.config || !prev.originalConfig) return prev;
          return {
            ...prev,
            originalConfig: { ...prev.originalConfig, [sectionName]: (prev.config as any)[sectionName] },
            sectionChanges: { ...prev.sectionChanges, [sectionName]: false }
          };
        });
        
        // Show success notification
        if (result.reload_triggered) {
          console.log('Configuration updated and system reloaded');
        }
      }
      
      return result;
    } catch (error) {
      console.error('Failed to apply section:', error);
      throw error;
    }
  };

  const hasAnyChanges = Object.values(state.sectionChanges).some(Boolean);

  // Handle saving all changes
  const handleSaveAllChanges = async (): Promise<void> => {
    if (!state.config) return;

    try {
      // Apply all changed sections
      const changedSections = Object.entries(state.sectionChanges)
        .filter(([_, hasChanges]) => hasChanges)
        .map(([sectionName]) => sectionName);

      for (const sectionName of changedSections) {
        await applySection(sectionName);
      }

      setLastSaved(new Date());
    } catch (error) {
      console.error('Failed to save all changes:', error);
      throw error;
    }
  };

  // Handle validating all changes
  const handleValidateAllChanges = async (): Promise<ValidationResult> => {
    if (!state.config) {
      return { valid: false, errors: ['No configuration loaded'], warnings: [] };
    }

    try {
      const changedSections = Object.entries(state.sectionChanges)
        .filter(([_, hasChanges]) => hasChanges)
        .map(([sectionName]) => sectionName);

      const allErrors: string[] = [];
      const allWarnings: string[] = [];

      // Validate all changed sections
      for (const sectionName of changedSections) {
        try {
          const result = await validateSection(sectionName);
          if (!result.valid && result.errors) {
            allErrors.push(...result.errors.map(err => `${sectionName}: ${typeof err === 'string' ? err : (err as any).message || 'Validation error'}`));
          }
          // Note: warnings not currently supported by validateSection
          // if (result.warnings) {
          //   allWarnings.push(...result.warnings.map(warn => `${sectionName}: ${warn}`));
          // }
        } catch (error) {
          allErrors.push(`${sectionName}: Validation failed - ${error instanceof Error ? error.message : 'Unknown error'}`);
        }
      }

      return {
        valid: allErrors.length === 0,
        errors: allErrors,
        warnings: allWarnings
      };
    } catch (error) {
      return {
        valid: false,
        errors: [error instanceof Error ? error.message : 'Validation failed'],
        warnings: []
      };
    }
  };

  // Handle canceling changes
  const handleCancelChanges = (): void => {
    if (state.originalConfig) {
      setState(prev => ({
        ...prev,
        config: JSON.parse(JSON.stringify(prev.originalConfig)), // Deep copy
        sectionChanges: {}
      }));
    }
  };

  const renderConnectionStatus = () => {
    switch (state.connectionStatus) {
      case 'checking':
        return (
          <div className="flex items-center text-gray-500">
            <Loader className="h-4 w-4 animate-spin mr-2" />
            <span>Checking connection...</span>
          </div>
        );
      case 'connected':
        return (
          <div className="flex items-center text-green-600">
            <CheckCircle className="h-4 w-4 mr-2" />
            <span>Connected to Irene API</span>
          </div>
        );
      case 'disconnected':
        return (
          <div className="flex items-center text-red-600">
            <AlertCircle className="h-4 w-4 mr-2" />
            <span>Disconnected from API</span>
          </div>
        );
    }
  };

  if (state.loading) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center space-x-3">
            <Loader className="h-6 w-6 animate-spin text-blue-500" />
            <span className="text-lg text-gray-600">Loading configuration...</span>
          </div>
        </div>
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-center">
            <AlertCircle className="h-6 w-6 text-red-500 mr-3" />
            <div>
              <h2 className="text-lg font-semibold text-red-900">Configuration Error</h2>
              <p className="text-red-700 mt-1">{state.error}</p>
            </div>
          </div>
          <button
            onClick={loadConfiguration}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 flex items-center"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center space-x-3 mb-2">
              <h1 className="text-3xl font-bold text-gray-900">
                System Configuration
              </h1>
              <span 
                className="px-3 py-1 bg-blue-100 text-blue-800 text-sm font-medium rounded-full cursor-help"
                title={state.configStatus?.config_path || 'Configuration file'}
              >
                {getConfigFileName()}
              </span>
            </div>
            <p className="text-gray-600">
              Manage TOML configuration with automatic Pydantic validation and hot-reload.
            </p>
          </div>
          <div className="flex items-center space-x-4">
            {renderConnectionStatus()}
            <button
              onClick={() => setShowPreview(!showPreview)}
              className={`px-4 py-2 rounded-md flex items-center transition-colors ${
                showPreview 
                  ? 'bg-blue-100 text-blue-700 border border-blue-200 hover:bg-blue-200' 
                  : 'bg-gray-100 text-gray-700 border border-gray-200 hover:bg-gray-200'
              }`}
            >
              <Settings className="h-4 w-4 mr-2" />
              {showPreview ? 'Show Config Editor' : 'Show TOML Preview'}
            </button>
          </div>
        </div>

      </div>

      {/* Main content area with toggle between editor and preview */}
      <div className="flex-1 min-h-0">
        {showPreview ? (
          /* TOML Preview Mode - Full width with consistent height */
          <div className="space-y-4">
            <TomlPreview 
              config={state.config} 
              key={lastSaved?.getTime() || 0} // Force refresh when config is saved
              className="w-full"
            />
          </div>
        ) : (
          /* Configuration Editor Mode - Full width */
          <div className="space-y-4">
            {state.config && sectionOrder
              .filter(sectionName => (state.config as any)?.[sectionName] !== undefined)
              .map(sectionName => (
                <ConfigSection
                  key={sectionName}
                  name={sectionName}
                  title={sectionTitles[sectionName]}
                  data={(state.config as any)[sectionName]}
                  schema={state.schema[sectionName]?.fields}
                  hasChanges={state.sectionChanges[sectionName]}
                  onChange={(data) => updateSection(sectionName, data)}
                  onValidate={() => validateSection(sectionName)}
                  onApply={() => applySection(sectionName)}
                  level={1}
                />
              ))}
          </div>
        )}
      </div>

      {/* Apply Changes Bar - Visible in both modes */}
      <ApplyChangesBar
        visible={hasAnyChanges}
        selectedHandler={getConfigFileName()}
        hasUnsavedChanges={hasAnyChanges}
        onSave={handleSaveAllChanges}
        onValidate={handleValidateAllChanges}
        onCancel={handleCancelChanges}
        loading={state.loading}
        lastSaved={lastSaved || undefined}
      />
    </div>
  );
};

export default ConfigurationPage;
