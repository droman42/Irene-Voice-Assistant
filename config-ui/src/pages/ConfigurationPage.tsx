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
import { type ComponentName, type ComponentConfigType, type ComponentConfigureResponse } from '@/components/ui/TestConfigButton';
import type { CoreConfig, ConfigSchemaResponse, ConfigStatusResponse, ValidationResult } from '@/types/api';

interface ConfigurationTestState {
  status: 'idle' | 'testing' | 'applied' | 'error';
  message: string;
  testResult?: ComponentConfigureResponse;
  timestamp?: Date;
}

// Enhanced configuration state for Phase 4.3 workflow
interface ComponentConfigurationState {
  // Current configuration (what user is editing)
  current: ComponentConfigType | null;
  // Configuration that was last successfully tested via /configure
  tested: ComponentConfigType | null;
  // Configuration that is currently persisted in TOML
  persisted: ComponentConfigType | null;
  // Test state for this component
  testState: ConfigurationTestState;
  // Whether current config differs from tested config
  hasPendingTests: boolean;
  // Whether tested config differs from persisted config
  hasPendingPersist: boolean;
  // Whether there are conflicts between runtime and TOML
  hasConflicts: boolean;
}

interface ConfigurationPageState {
  config: CoreConfig | null;
  originalConfig: CoreConfig | null;
  schema: ConfigSchemaResponse;
  configStatus: ConfigStatusResponse | null;
  sectionChanges: Record<string, boolean>;
  loading: boolean;
  error: string | null;
  connectionStatus: 'connected' | 'disconnected' | 'checking';
  testStates: Record<ComponentName, ConfigurationTestState>;
  // Phase 4.3: Enhanced component configuration states
  componentStates: Record<ComponentName, ComponentConfigurationState>;
}

const ConfigurationPage: React.FC = () => {
  // Helper function to create initial component state
  const createInitialComponentState = (): ComponentConfigurationState => ({
    current: null,
    tested: null,
    persisted: null,
    testState: { status: 'idle', message: '' },
    hasPendingTests: false,
    hasPendingPersist: false,
    hasConflicts: false
  });

  const [state, setState] = useState<ConfigurationPageState>({
    config: null,
    originalConfig: null,
    schema: {} as ConfigSchemaResponse,
    configStatus: null,
    sectionChanges: {},
    loading: true,
    error: null,
    connectionStatus: 'checking',
    testStates: {
      tts: { status: 'idle', message: '' },
      asr: { status: 'idle', message: '' },
      audio: { status: 'idle', message: '' },
      llm: { status: 'idle', message: '' },
      nlu: { status: 'idle', message: '' },
      voice_trigger: { status: 'idle', message: '' },
      text_processing: { status: 'idle', message: '' },
      intent_system: { status: 'idle', message: '' }
    },
    componentStates: {
      tts: createInitialComponentState(),
      asr: createInitialComponentState(),
      audio: createInitialComponentState(),
      llm: createInitialComponentState(),
      nlu: createInitialComponentState(),
      voice_trigger: createInitialComponentState(),
      text_processing: createInitialComponentState(),
      intent_system: createInitialComponentState()
    }
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

  // Helper function to map section names to component names
  const getComponentName = (sectionName: string): ComponentName | null => {
    const sectionToComponent: Record<string, ComponentName> = {
      'tts': 'tts',
      'asr': 'asr', 
      'audio': 'audio',
      'llm': 'llm',
      'nlu': 'nlu',
      'voice_trigger': 'voice_trigger',
      'text_processor': 'text_processing', // Section name is 'text_processor', component name is 'text_processing'
      'intent_system': 'intent_system'
    };
    return sectionToComponent[sectionName] || null;
  };

  // Helper function to get test state for a section
  const getTestStateForSection = (sectionName: string): ConfigurationTestState | undefined => {
    const componentName = getComponentName(sectionName);
    return componentName ? state.testStates[componentName] : undefined;
  };

  // Helper function to get overall test status summary
  const getTestStatusSummary = () => {
    const states = Object.values(state.testStates);
    const testing = states.filter(s => s.status === 'testing').length;
    const applied = states.filter(s => s.status === 'applied').length;
    const errors = states.filter(s => s.status === 'error').length;
    const total = states.filter(s => s.status !== 'idle').length;
    
    return { testing, applied, errors, total };
  };

  // Phase 4.3: Enhanced workflow helper functions
  
  // Helper function to update component configuration state
  const updateComponentState = (
    component: ComponentName, 
    updates: Partial<ComponentConfigurationState>
  ) => {
    setState(prev => ({
      ...prev,
      componentStates: {
        ...prev.componentStates,
        [component]: {
          ...prev.componentStates[component],
          ...updates
        }
      }
    }));
  };


  // Helper function to get workflow status for a component
  const getWorkflowStatus = (component: ComponentName) => {
    const componentState = state.componentStates[component];
    const testState = componentState.testState;
    
    return {
      hasChanges: componentState.hasPendingTests,
      isTested: testState.status === 'applied' && !componentState.hasPendingTests,
      isPersisted: !componentState.hasPendingPersist,
      hasConflicts: componentState.hasConflicts,
      canTest: componentState.hasPendingTests,
      canPersist: componentState.hasPendingPersist && testState.status === 'applied',
      testStatus: testState.status
    };
  };

  // Helper function to get configuration state type for visual indicators
  const getConfigurationStateType = (component: ComponentName): 'pristine' | 'edited' | 'tested' | 'persisted' | 'conflict' => {
    const status = getWorkflowStatus(component);
    
    if (status.hasConflicts) return 'conflict';
    if (status.isPersisted && status.isTested && !status.hasChanges) return 'persisted';
    if (status.isTested && !status.hasChanges) return 'tested';
    if (status.hasChanges) return 'edited';
    return 'pristine';
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

      // Initialize component states with current TOML configuration
      const initialComponentStates: Record<ComponentName, ComponentConfigurationState> = {
        tts: createInitialComponentState(),
        asr: createInitialComponentState(),
        audio: createInitialComponentState(),
        llm: createInitialComponentState(),
        nlu: createInitialComponentState(),
        voice_trigger: createInitialComponentState(),
        text_processing: createInitialComponentState(),
        intent_system: createInitialComponentState()
      };

      // Set current and persisted configs from TOML data
      Object.entries(initialComponentStates).forEach(([component, state]) => {
        const componentKey = component === 'text_processing' ? 'text_processor' : component;
        const componentConfig = (configData as any)?.[componentKey];
        if (componentConfig) {
          state.current = componentConfig;
          state.persisted = JSON.parse(JSON.stringify(componentConfig)); // Deep copy
        }
      });

      setState(prev => ({
        ...prev,
        config: configData,
        originalConfig: JSON.parse(JSON.stringify(configData)), // Deep copy
        schema: schemaData,
        configStatus: statusData,
        connectionStatus: 'connected',
        loading: false,
        componentStates: initialComponentStates
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
      
      // Phase 4.3: Update component state for configuration workflow
      const componentName = getComponentName(sectionName);
      const newComponentStates = { ...prev.componentStates };
      
      if (componentName) {
        const componentState = newComponentStates[componentName];
        const newComponentState = { ...componentState };
        
        // Update current configuration
        newComponentState.current = sectionData;
        
        // Check if current differs from tested configuration
        const hasPendingTests = newComponentState.tested 
          ? JSON.stringify(sectionData) !== JSON.stringify(newComponentState.tested)
          : true; // No tested config means we have pending tests
        
        // Check if tested differs from persisted configuration
        const hasPendingPersist = newComponentState.persisted && newComponentState.tested
          ? JSON.stringify(newComponentState.tested) !== JSON.stringify(newComponentState.persisted)
          : false;
        
        newComponentState.hasPendingTests = hasPendingTests;
        newComponentState.hasPendingPersist = hasPendingPersist;
        
        newComponentStates[componentName] = newComponentState;
      }
      
      return {
        ...prev,
        config: newConfig,
        sectionChanges: { ...prev.sectionChanges, [sectionName]: hasChanges },
        componentStates: newComponentStates
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
            
            // Phase 4.3: Update component state when TOML is persisted via comment-preserving workflow
            const componentName = getComponentName(sectionName);
            const newComponentStates = { ...prev.componentStates };
            
            if (componentName) {
              const sectionData = (prev.config as any)[sectionName];
              newComponentStates[componentName] = {
                ...newComponentStates[componentName],
                persisted: JSON.parse(JSON.stringify(sectionData)), // Deep copy
                hasPendingPersist: false,
                // If this config was also tested, mark it as no longer needing persistence
                hasPendingTests: newComponentStates[componentName].tested 
                  ? JSON.stringify(sectionData) !== JSON.stringify(newComponentStates[componentName].tested)
                  : false
              };
            }
            
            return {
              ...prev,
              originalConfig: { ...prev.originalConfig, [sectionName]: (prev.config as any)[sectionName] },
              sectionChanges: { ...prev.sectionChanges, [sectionName]: false },
              componentStates: newComponentStates
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
          
          // Phase 4.3: Update component state when TOML is persisted via traditional workflow
          const componentName = getComponentName(sectionName);
          const newComponentStates = { ...prev.componentStates };
          
          if (componentName) {
            const sectionData = (prev.config as any)[sectionName];
            newComponentStates[componentName] = {
              ...newComponentStates[componentName],
              persisted: JSON.parse(JSON.stringify(sectionData)), // Deep copy
              hasPendingPersist: false,
              // If this config was also tested, mark it as no longer needing persistence
              hasPendingTests: newComponentStates[componentName].tested 
                ? JSON.stringify(sectionData) !== JSON.stringify(newComponentStates[componentName].tested)
                : false
            };
          }
          
          return {
            ...prev,
            originalConfig: { ...prev.originalConfig, [sectionName]: (prev.config as any)[sectionName] },
            sectionChanges: { ...prev.sectionChanges, [sectionName]: false },
            componentStates: newComponentStates
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
      setState(prev => {
        // Phase 4.3: Reset component states when canceling changes
        const newComponentStates = { ...prev.componentStates };
        
        Object.entries(newComponentStates).forEach(([component, componentState]) => {
          const sectionName = component === 'text_processing' ? 'text_processor' : component;
          const originalSectionData = (prev.originalConfig as any)?.[sectionName];
          
          if (originalSectionData) {
            newComponentStates[component as ComponentName] = {
              ...componentState,
              current: JSON.parse(JSON.stringify(originalSectionData)), // Deep copy
              hasPendingTests: componentState.tested 
                ? JSON.stringify(originalSectionData) !== JSON.stringify(componentState.tested)
                : false
            };
          }
        });
        
        return {
          ...prev,
          config: JSON.parse(JSON.stringify(prev.originalConfig)), // Deep copy
          sectionChanges: {},
          componentStates: newComponentStates
        };
      });
    }
  };

  // Phase 4.3: Enhanced testing configuration via /configure endpoints with workflow integration
  const handleTestConfiguration = async (component: ComponentName, config: ComponentConfigType): Promise<ComponentConfigureResponse> => {
    // Update test state to show testing status
    const testState: ConfigurationTestState = {
      status: 'testing',
      message: `Testing ${component} configuration...`,
      timestamp: new Date()
    };

    setState(prev => ({
      ...prev,
      testStates: {
        ...prev.testStates,
        [component]: testState
      },
      componentStates: {
        ...prev.componentStates,
        [component]: {
          ...prev.componentStates[component],
          testState
        }
      }
    }));

    try {
      let result: ComponentConfigureResponse;
      
      // Call the appropriate configure API method based on component type
      switch (component) {
        case 'tts':
          result = await apiClient.configureTTS(config as any);
          break;
        case 'asr':
          result = await apiClient.configureASR(config as any);
          break;
        case 'audio':
          result = await apiClient.configureAudio(config as any);
          break;
        case 'llm':
          result = await apiClient.configureLLM(config as any);
          break;
        case 'nlu':
          result = await apiClient.configureNLU(config as any);
          break;
        case 'voice_trigger':
          result = await apiClient.configureVoiceTrigger(config as any);
          break;
        case 'text_processing':
          result = await apiClient.configureTextProcessor(config as any);
          break;
        case 'intent_system':
          result = await apiClient.configureIntentSystem(config as any);
          break;
        default:
          throw new Error(`Unknown component: ${component}`);
      }

      // Phase 4.3: Update enhanced component state with successful test
      const successTestState: ConfigurationTestState = {
        status: 'applied',
        message: result.message || `${component} configuration applied successfully`,
        testResult: result,
        timestamp: new Date()
      };

      setState(prev => {
        const componentState = prev.componentStates[component];
        const hasPendingPersist = componentState.persisted 
          ? JSON.stringify(config) !== JSON.stringify(componentState.persisted)
          : true; // No persisted config means we have pending persist

        return {
          ...prev,
          testStates: {
            ...prev.testStates,
            [component]: successTestState
          },
          componentStates: {
            ...prev.componentStates,
            [component]: {
              ...componentState,
              tested: JSON.parse(JSON.stringify(config)), // Deep copy of tested config
              testState: successTestState,
              hasPendingTests: false, // Config is now tested
              hasPendingPersist // Check if persist is needed
            }
          }
        };
      });

      console.log(`✅ ${component} configuration tested successfully:`, result);
      return result;

    } catch (error) {
      // Update test state to show error
      const errorMessage = error instanceof Error ? error.message : 'Configuration test failed';
      const errorTestState: ConfigurationTestState = {
        status: 'error',
        message: `${component} test failed: ${errorMessage}`,
        timestamp: new Date()
      };

      setState(prev => ({
        ...prev,
        testStates: {
          ...prev.testStates,
          [component]: errorTestState
        },
        componentStates: {
          ...prev.componentStates,
          [component]: {
            ...prev.componentStates[component],
            testState: errorTestState
          }
        }
      }));

      console.error(`❌ ${component} configuration test failed:`, error);
      throw error;
    }
  };

  // Phase 4.3: Workflow functions for Test → Validate → Persist

  // Handle persisting tested configuration to TOML
  const handlePersistTestedConfiguration = async (component: ComponentName): Promise<void> => {
    const componentState = state.componentStates[component];
    
    if (!componentState.tested) {
      throw new Error(`No tested configuration available for ${component}`);
    }

    if (componentState.testState.status !== 'applied') {
      throw new Error(`Configuration must be tested successfully before persisting for ${component}`);
    }

    try {
      const sectionName = component === 'text_processing' ? 'text_processor' : component;
      
      // Apply the tested configuration to TOML
      await applySection(sectionName);
      
      // Update component state to reflect persistence
      updateComponentState(component, {
        persisted: JSON.parse(JSON.stringify(componentState.tested)), // Deep copy
        hasPendingPersist: false
      });

      console.log(`✅ ${component} tested configuration persisted to TOML successfully`);
      
    } catch (error) {
      console.error(`❌ Failed to persist ${component} configuration:`, error);
      throw error;
    }
  };

  // Handle rollback to last persisted configuration
  const handleRollbackToPersistedConfiguration = (component: ComponentName): void => {
    const componentState = state.componentStates[component];
    
    if (!componentState.persisted) {
      console.warn(`No persisted configuration available for rollback for ${component}`);
      return;
    }

    try {
      const sectionName = component === 'text_processing' ? 'text_processor' : component;
      
      // Update the section with persisted configuration
      updateSection(sectionName, componentState.persisted);
      
      // Update component state
      updateComponentState(component, {
        current: JSON.parse(JSON.stringify(componentState.persisted)), // Deep copy
        tested: null, // Clear tested config since we rolled back
        testState: { status: 'idle', message: '' },
        hasPendingTests: false,
        hasPendingPersist: false
      });

      console.log(`✅ ${component} configuration rolled back to persisted state`);
      
    } catch (error) {
      console.error(`❌ Failed to rollback ${component} configuration:`, error);
    }
  };

  // Handle rollback to last tested configuration
  const handleRollbackToTestedConfiguration = (component: ComponentName): void => {
    const componentState = state.componentStates[component];
    
    if (!componentState.tested) {
      console.warn(`No tested configuration available for rollback for ${component}`);
      return;
    }

    try {
      const sectionName = component === 'text_processing' ? 'text_processor' : component;
      
      // Update the section with tested configuration
      updateSection(sectionName, componentState.tested);
      
      // Update component state
      updateComponentState(component, {
        current: JSON.parse(JSON.stringify(componentState.tested)), // Deep copy
        hasPendingTests: false
      });

      console.log(`✅ ${component} configuration rolled back to tested state`);
      
    } catch (error) {
      console.error(`❌ Failed to rollback ${component} configuration:`, error);
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

      {/* Configuration Test Status Summary */}
      {(() => {
        const summary = getTestStatusSummary();
        if (summary.total === 0) return null;
        
        return (
          <div className="mb-4 p-3 bg-gray-50 border border-gray-200 rounded-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <span className="text-sm font-medium text-gray-700">Configuration Testing Status:</span>
                {summary.testing > 0 && (
                  <div className="flex items-center text-blue-600">
                    <Loader className="h-4 w-4 animate-spin mr-1" />
                    <span className="text-sm">{summary.testing} testing</span>
                  </div>
                )}
                {summary.applied > 0 && (
                  <div className="flex items-center text-green-600">
                    <CheckCircle className="h-4 w-4 mr-1" />
                    <span className="text-sm">{summary.applied} applied</span>
                  </div>
                )}
                {summary.errors > 0 && (
                  <div className="flex items-center text-red-600">
                    <AlertCircle className="h-4 w-4 mr-1" />
                    <span className="text-sm">{summary.errors} errors</span>
                  </div>
                )}
              </div>
              <div className="text-xs text-gray-500">
                {summary.total} of 8 components tested
              </div>
            </div>
          </div>
        );
      })()}

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
              .map(sectionName => {
                const componentName = getComponentName(sectionName);
                const workflowStatus = componentName ? getWorkflowStatus(componentName) : undefined;
                const workflowStateType = componentName ? getConfigurationStateType(componentName) : 'pristine';
                
                return (
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
                    onTestConfig={handleTestConfiguration}
                    testState={getTestStateForSection(sectionName)}
                    level={1}
                    // Phase 4.3: Enhanced workflow props
                    workflowStatus={workflowStatus}
                    workflowStateType={workflowStateType}
                    onPersistTested={handlePersistTestedConfiguration}
                    onRollbackToPersisted={handleRollbackToPersistedConfiguration}
                    onRollbackToTested={handleRollbackToTestedConfiguration}
                  />
                );
              })}
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
