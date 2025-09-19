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
import type { CoreConfig, ConfigSchemaResponse } from '@/types/api';

interface ConfigurationPageState {
  config: CoreConfig | null;
  originalConfig: CoreConfig | null;
  schema: ConfigSchemaResponse;
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
    sectionChanges: {},
    loading: true,
    error: null,
    connectionStatus: 'checking'
  });

  const [showPreview, setShowPreview] = useState(false);

  // Define section order and grouping
  const sectionOrder = [
    'system',
    'inputs', 
    'components',
    'tts',
    'audio',
    'asr',
    'llm',
    'voice_trigger',
    'nlu',
    'text_processor',
    'intent_system',
    'vad',
    'monitoring',
    'assets',
    'workflows'
  ];

  const sectionTitles: Record<string, string> = {
    system: '🔧 Core Settings',
    inputs: '📝 Input Sources',
    components: '🔌 Components',
    tts: '🗣️ Text-to-Speech',
    audio: '🔊 Audio Playback',
    asr: '🎤 Speech Recognition',
    llm: '🤖 Language Models',
    voice_trigger: '👂 Voice Trigger',
    nlu: '🧠 Natural Language Understanding',
    text_processor: '📝 Text Processing',
    intent_system: '🎯 Intent System',
    vad: '🔊 Voice Activity Detection',
    monitoring: '📊 Monitoring',
    assets: '📁 Asset Management',
    workflows: '⚡ Workflows'
  };

  useEffect(() => {
    loadConfiguration();
  }, []);

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

      // Load configuration and schema in parallel
      const [configData, schemaData] = await Promise.all([
        apiClient.getConfig(),
        apiClient.getConfigSchema()
      ]);

      setState(prev => ({
        ...prev,
        config: configData,
        originalConfig: JSON.parse(JSON.stringify(configData)), // Deep copy
        schema: schemaData,
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
      const result = await apiClient.updateConfigSection(sectionName, (state.config as any)[sectionName]);
      
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
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              System Configuration
            </h1>
            <p className="text-gray-600">
              Manage TOML configuration with automatic Pydantic validation and hot-reload.
            </p>
          </div>
          <div className="flex items-center space-x-4">
            {renderConnectionStatus()}
            <button
              onClick={() => setShowPreview(!showPreview)}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 flex items-center"
            >
              <Settings className="h-4 w-4 mr-2" />
              {showPreview ? 'Hide' : 'Show'} TOML Preview
            </button>
          </div>
        </div>

        {hasAnyChanges && (
          <div className="mt-4 bg-orange-50 border border-orange-200 rounded-lg p-4">
            <div className="flex items-center">
              <AlertCircle className="h-5 w-5 text-orange-500 mr-2" />
              <span className="text-orange-800 font-medium">
                You have unsaved changes. Remember to validate and apply sections individually.
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-8">
        {/* Configuration Sections */}
        <div className="flex-1 space-y-4">
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

        {/* TOML Preview Sidebar */}
        {showPreview && (
          <div className="w-96">
            <div className="sticky top-6">
              <TomlPreview config={state.config} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ConfigurationPage;
