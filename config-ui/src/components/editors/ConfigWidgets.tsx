/**
 * Configuration Widgets - Generic and specialized input widgets for TOML configuration
 * 
 * Provides auto-generated widgets based on Pydantic field metadata with specialized
 * widgets for complex configuration types like environment variables and provider selection.
 */

import React, { useState, useEffect } from 'react';
import { ChevronDown, Eye, EyeOff, Info } from 'lucide-react';
import apiClient from '@/utils/apiClient';
import type { ConfigFieldSchema } from '@/types/api';

// ============================================================
// WIDGET INTERFACES
// ============================================================

// Use the imported type instead of defining locally
export type FieldSchema = ConfigFieldSchema;

export interface ConfigWidgetProps {
  name: string;
  value: any;
  schema: FieldSchema;
  onChange: (value: any) => void;
  disabled?: boolean;
  path?: string[]; // For nested configuration paths
}

// ============================================================
// BASIC WIDGETS
// ============================================================

export const BooleanWidget: React.FC<ConfigWidgetProps> = ({ 
  name, value, schema, onChange, disabled 
}) => {
  return (
    <div className="flex items-center space-x-3">
      <input
        type="checkbox"
        id={name}
        checked={value ?? schema.default ?? false}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded disabled:opacity-50"
      />
      <label htmlFor={name} className="flex-1">
        <span className="text-sm font-medium text-gray-700">{name}</span>
        {schema.description && (
          <div className="flex items-center mt-1">
            <Info className="h-3 w-3 text-gray-400 mr-1" />
            <span className="text-xs text-gray-500">{schema.description}</span>
          </div>
        )}
      </label>
    </div>
  );
};

export const StringWidget: React.FC<ConfigWidgetProps> = ({ 
  name, value, schema, onChange, disabled 
}) => {
  return (
    <div className="space-y-1">
      <label htmlFor={name} className="block text-sm font-medium text-gray-700">
        {name}
        {schema.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <input
        type="text"
        id={name}
        value={value ?? schema.default ?? ''}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder={schema.default ? `Default: ${schema.default}` : undefined}
        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm"
      />
      {schema.description && (
        <div className="flex items-center">
          <Info className="h-3 w-3 text-gray-400 mr-1" />
          <span className="text-xs text-gray-500">{schema.description}</span>
        </div>
      )}
    </div>
  );
};

export const NumberWidget: React.FC<ConfigWidgetProps> = ({ 
  name, value, schema, onChange, disabled 
}) => {
  const isInteger = schema.type === 'integer';
  const step = isInteger ? 1 : 0.1;
  
  return (
    <div className="space-y-1">
      <label htmlFor={name} className="block text-sm font-medium text-gray-700">
        {name}
        {schema.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <input
        type="number"
        id={name}
        value={value ?? schema.default ?? ''}
        onChange={(e) => {
          const val = e.target.value;
          if (val === '') {
            onChange(null);
          } else {
            onChange(isInteger ? parseInt(val, 10) : parseFloat(val));
          }
        }}
        step={step}
        disabled={disabled}
        placeholder={schema.default ? `Default: ${schema.default}` : undefined}
        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm"
      />
      {schema.description && (
        <div className="flex items-center">
          <Info className="h-3 w-3 text-gray-400 mr-1" />
          <span className="text-xs text-gray-500">{schema.description}</span>
        </div>
      )}
    </div>
  );
};

export const ArrayWidget: React.FC<ConfigWidgetProps> = ({ 
  name, value, schema, onChange, disabled 
}) => {
  const arrayValue = Array.isArray(value) ? value : (schema.default || []);
  
  const addItem = () => {
    onChange([...arrayValue, '']);
  };
  
  const removeItem = (index: number) => {
    const newArray = arrayValue.filter((_: any, i: number) => i !== index);
    onChange(newArray);
  };
  
  const updateItem = (index: number, newValue: string) => {
    const newArray = [...arrayValue];
    newArray[index] = newValue;
    onChange(newArray);
  };
  
  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        {name}
        {schema.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      
      <div className="space-y-2">
        {arrayValue.map((item: any, index: number) => (
          <div key={index} className="flex items-center space-x-2">
            <input
              type="text"
              value={item}
              onChange={(e) => updateItem(index, e.target.value)}
              disabled={disabled}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm"
              placeholder={`Item ${index + 1}`}
            />
            <button
              type="button"
              onClick={() => removeItem(index)}
              disabled={disabled}
              className="px-2 py-2 text-red-600 hover:text-red-800 disabled:opacity-50"
            >
              ×
            </button>
          </div>
        ))}
        
        <button
          type="button"
          onClick={addItem}
          disabled={disabled}
          className="px-3 py-1 text-sm text-blue-600 hover:text-blue-800 disabled:opacity-50"
        >
          + Add Item
        </button>
      </div>
      
      {schema.description && (
        <div className="flex items-center">
          <Info className="h-3 w-3 text-gray-400 mr-1" />
          <span className="text-xs text-gray-500">{schema.description}</span>
        </div>
      )}
    </div>
  );
};

// ============================================================
// SPECIALIZED WIDGETS
// ============================================================

export const EnvironmentVariableWidget: React.FC<ConfigWidgetProps> = ({ 
  name, value, schema, onChange, disabled 
}) => {
  const [showValue, setShowValue] = useState(false);
  const isEnvVar = typeof value === 'string' && value.startsWith('${') && value.endsWith('}');
  
  return (
    <div className="space-y-1">
      <label htmlFor={name} className="block text-sm font-medium text-gray-700">
        {name}
        {schema.required && <span className="text-red-500 ml-1">*</span>}
        {isEnvVar && (
          <span className="ml-2 px-2 py-0.5 text-xs bg-green-100 text-green-800 rounded">
            ENV VAR
          </span>
        )}
      </label>
      <div className="relative">
        <input
          type={showValue ? "text" : "password"}
          id={name}
          value={value ?? schema.default ?? ''}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder="${ENV_VAR_NAME} or direct value"
          className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm"
        />
        <button
          type="button"
          onClick={() => setShowValue(!showValue)}
          className="absolute inset-y-0 right-0 pr-3 flex items-center"
        >
          {showValue ? (
            <EyeOff className="h-4 w-4 text-gray-400" />
          ) : (
            <Eye className="h-4 w-4 text-gray-400" />
          )}
        </button>
      </div>
      <div className="text-xs text-gray-500">
        Use ${`{VARIABLE_NAME}`} syntax for environment variables
      </div>
      {schema.description && (
        <div className="flex items-center">
          <Info className="h-3 w-3 text-gray-400 mr-1" />
          <span className="text-xs text-gray-500">{schema.description}</span>
        </div>
      )}
    </div>
  );
};

export const ProviderSelectWidget: React.FC<ConfigWidgetProps & { 
  componentName?: string 
}> = ({ 
  name, value, schema, onChange, disabled, componentName, path 
}) => {
  const [providers, setProviders] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);
  
  // Determine component name from path if not provided
  const inferredComponent = componentName || (path && path[0]);
  
  useEffect(() => {
    if (inferredComponent) {
      loadProviders();
    }
  }, [inferredComponent]);
  
  const loadProviders = async () => {
    if (!inferredComponent) return;
    
    setLoading(true);
    try {
      const providerData = await apiClient.getAvailableProviders(inferredComponent);
      setProviders(providerData);
    } catch (error) {
      console.warn(`Failed to load providers for ${inferredComponent}:`, error);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="space-y-1">
      <label htmlFor={name} className="block text-sm font-medium text-gray-700">
        {name}
        {schema.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <div className="relative">
        <select
          id={name}
          value={value ?? schema.default ?? ''}
          onChange={(e) => onChange(e.target.value || null)}
          disabled={disabled || loading}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm appearance-none"
        >
          <option value="">Select provider...</option>
          {Object.entries(providers).map(([key, provider]) => (
            <option key={key} value={key}>
              {provider.name || key} {provider.version && `(${provider.version})`}
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
      </div>
      {loading && (
        <div className="text-xs text-gray-500">Loading providers...</div>
      )}
      {schema.description && (
        <div className="flex items-center">
          <Info className="h-3 w-3 text-gray-400 mr-1" />
          <span className="text-xs text-gray-500">{schema.description}</span>
        </div>
      )}
    </div>
  );
};

export const InputSelectWidget: React.FC<ConfigWidgetProps> = ({ 
  name, value, schema, onChange, disabled 
}) => {
  // Define available input sources
  const inputSources = [
    { value: 'microphone', label: 'Microphone', description: 'Voice input from microphone' },
    { value: 'web', label: 'Web Interface', description: 'Input from web UI' },
    { value: 'cli', label: 'Command Line', description: 'Text input from terminal' }
  ];
  
  return (
    <div className="space-y-1">
      <label htmlFor={name} className="block text-sm font-medium text-gray-700">
        {name}
        {schema.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <div className="relative">
        <select
          id={name}
          value={value ?? schema.default ?? ''}
          onChange={(e) => onChange(e.target.value || null)}
          disabled={disabled}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm appearance-none"
        >
          <option value="">Select input source...</option>
          {inputSources.map((source) => (
            <option key={source.value} value={source.value}>
              {source.label}
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
      </div>
      {schema.description && (
        <div className="flex items-center">
          <Info className="h-3 w-3 text-gray-400 mr-1" />
          <span className="text-xs text-gray-500">{schema.description}</span>
        </div>
      )}
    </div>
  );
};

export const MicrophoneSelectWidget: React.FC<ConfigWidgetProps & { 
  onDeviceChange?: (deviceInfo: any) => void 
}> = ({ 
  name, value, schema, onChange, disabled, onDeviceChange 
}) => {
  const [devices, setDevices] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    loadAudioDevices();
  }, []);
  
  const loadAudioDevices = async () => {
    setLoading(true);
    try {
      const response = await apiClient.getAvailableAudioDevices();
      if (response.success) {
        setDevices(response.devices);
      } else {
        console.warn('Failed to load audio devices:', response.message);
        setDevices([]);
      }
    } catch (error) {
      console.warn('Failed to load audio devices:', error);
      setDevices([]);
    } finally {
      setLoading(false);
    }
  };
  
  const handleDeviceChange = (deviceId: string) => {
    const numericId = deviceId === '' ? null : parseInt(deviceId, 10);
    onChange(numericId);
    
    // Notify parent about device info for auto-populating other fields
    if (onDeviceChange && deviceId !== '') {
      const selectedDevice = devices.find(d => d.id === numericId);
      if (selectedDevice) {
        onDeviceChange(selectedDevice);
      }
    }
  };
  
  return (
    <div className="space-y-1">
      <label htmlFor={name} className="block text-sm font-medium text-gray-700">
        {name}
        {schema.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <div className="relative">
        <select
          id={name}
          value={value === null ? '' : value?.toString() || ''}
          onChange={(e) => handleDeviceChange(e.target.value)}
          disabled={disabled || loading}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm appearance-none"
        >
          <option value="">Default device</option>
          {devices.map((device) => (
            <option key={device.id} value={device.id}>
              {device.name} {device.is_default ? '(system default)' : ''} - {device.channels}ch, {device.sample_rate}Hz
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
      </div>
      {loading && (
        <div className="text-xs text-gray-500">Loading audio devices...</div>
      )}
      {!loading && devices.length === 0 && (
        <div className="text-xs text-red-500">No audio devices found. Check audio dependencies.</div>
      )}
      {schema.description && (
        <div className="flex items-center">
          <Info className="h-3 w-3 text-gray-400 mr-1" />
          <span className="text-xs text-gray-500">{schema.description}</span>
        </div>
      )}
    </div>
  );
};

export const AudioOutputSelectWidget: React.FC<ConfigWidgetProps & { 
  onDeviceChange?: (deviceInfo: any) => void 
}> = ({ 
  name, value, schema, onChange, disabled, onDeviceChange 
}) => {
  const [devices, setDevices] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    loadAudioOutputDevices();
  }, []);
  
  const loadAudioOutputDevices = async () => {
    setLoading(true);
    try {
      const response = await apiClient.getAvailableAudioOutputDevices();
      if (response.success) {
        setDevices(response.devices);
      } else {
        console.warn('Failed to load audio output devices:', response.message);
        setDevices([]);
      }
    } catch (error) {
      console.warn('Failed to load audio output devices:', error);
      setDevices([]);
    } finally {
      setLoading(false);
    }
  };
  
  const handleDeviceChange = (deviceId: string) => {
    const numericId = deviceId === '' ? null : parseInt(deviceId, 10);
    onChange(numericId);
    
    // Notify parent about device info for auto-populating other fields
    if (onDeviceChange && deviceId !== '') {
      const selectedDevice = devices.find(d => d.id === numericId);
      if (selectedDevice) {
        onDeviceChange(selectedDevice);
      }
    }
  };
  
  return (
    <div className="space-y-1">
      <label htmlFor={name} className="block text-sm font-medium text-gray-700">
        {name}
        {schema.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <div className="relative">
        <select
          id={name}
          value={value === null ? '' : value?.toString() || ''}
          onChange={(e) => handleDeviceChange(e.target.value)}
          disabled={disabled || loading}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm appearance-none"
        >
          <option value="">Default audio output device</option>
          {devices.map((device) => (
            <option key={device.id} value={device.id}>
              {device.name} {device.is_default ? '(system default)' : ''} - {device.channels}ch, {device.sample_rate}Hz
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
      </div>
      {loading && (
        <div className="text-xs text-gray-500">Loading audio output devices...</div>
      )}
      {!loading && devices.length === 0 && (
        <div className="text-xs text-red-500">No audio output devices found. Check audio dependencies.</div>
      )}
      {schema.description && (
        <div className="flex items-center">
          <Info className="h-3 w-3 text-gray-400 mr-1" />
          <span className="text-xs text-gray-500">{schema.description}</span>
        </div>
      )}
    </div>
  );
};

export const ReadOnlyWidget: React.FC<ConfigWidgetProps> = ({ 
  name, value, schema 
}) => {
  const displayValue = value ?? schema.default ?? 'Not set';
  
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">
        {name}
      </label>
      <div className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-600 text-sm">
        {displayValue}
      </div>
      {schema.description && (
        <div className="flex items-center">
          <Info className="h-3 w-3 text-gray-400 mr-1" />
          <span className="text-xs text-gray-500">{schema.description}</span>
        </div>
      )}
    </div>
  );
};

export const RangeSliderWidget: React.FC<ConfigWidgetProps> = ({ 
  name, value, schema, onChange, disabled 
}) => {
  const min = schema.constraints?.ge ?? schema.constraints?.gt ?? 0;
  const max = schema.constraints?.le ?? schema.constraints?.lt ?? 1;
  const step = schema.type === 'integer' ? 1 : 0.01;
  const currentValue = value ?? schema.default ?? min;
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label htmlFor={name} className="block text-sm font-medium text-gray-700">
          {name}
          {schema.required && <span className="text-red-500 ml-1">*</span>}
        </label>
        <span className="text-sm text-gray-600">{currentValue}</span>
      </div>
      <input
        type="range"
        id={name}
        min={min}
        max={max}
        step={step}
        value={currentValue}
        onChange={(e) => {
          const val = parseFloat(e.target.value);
          onChange(schema.type === 'integer' ? Math.round(val) : val);
        }}
        disabled={disabled}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
      />
      <div className="flex justify-between text-xs text-gray-500">
        <span>{min}</span>
        <span>{max}</span>
      </div>
      {schema.description && (
        <div className="flex items-center">
          <Info className="h-3 w-3 text-gray-400 mr-1" />
          <span className="text-xs text-gray-500">{schema.description}</span>
        </div>
      )}
    </div>
  );
};

// ============================================================
// WIDGET FACTORY
// ============================================================

export const ConfigWidget: React.FC<ConfigWidgetProps & { 
  componentName?: string 
}> = (props) => {
  const { name, value, schema, componentName, path } = props;
  
  // Detect specialized widget types
  if (typeof value === 'string' && (value.startsWith('${') || name.toLowerCase().includes('key') || name.toLowerCase().includes('token'))) {
    return <EnvironmentVariableWidget {...props} />;
  }
  
  // Enhanced provider field detection
  if (name === 'default_provider' || name.endsWith('_provider') || name.includes('provider')) {
    return <ProviderSelectWidget {...props} componentName={componentName} />;
  }
  
  // Input source field detection
  if (name === 'default_input' || name.endsWith('_input') || (name.includes('input') && name.includes('default'))) {
    return <InputSelectWidget {...props} />;
  }
  
  // Microphone device field detection
  if (name === 'device_id' && path && path.some((p: string) => p.includes('microphone'))) {
    return <MicrophoneSelectWidget {...props} />;
  }
  
  // Audio output device field detection
  if (name === 'device_id' && path && path.some((p: string) => 
    p.includes('audio') || p.includes('tts') || p.includes('sounddevice') || 
    p.includes('aplay') || p.includes('console') || p.includes('audioplayer') || 
    p.includes('simpleaudio')
  )) {
    return <AudioOutputSelectWidget {...props} />;
  }
  
  // Legacy device field detection for backward compatibility
  if (name === 'device' && path && path.some((p: string) => 
    p.includes('audio') || p.includes('aplay') || p.includes('console')
  )) {
    return <AudioOutputSelectWidget {...props} />;
  }
  
  // Read-only fields for microphone configuration (auto-populated from device)
  if ((name === 'sample_rate' || name === 'channels') && path && path.some((p: string) => p.includes('microphone'))) {
    return <ReadOnlyWidget {...props} />;
  }
  
  // Read-only fields marked in schema (removed as readonly property doesn't exist in ConfigFieldSchema)
  
  if (schema.constraints && (schema.constraints.ge !== undefined || schema.constraints.le !== undefined) && schema.type === 'number') {
    return <RangeSliderWidget {...props} />;
  }
  
  // Default widget based on type
  switch (schema.type) {
    case 'boolean':
      return <BooleanWidget {...props} />;
    case 'integer':
    case 'number':
      return <NumberWidget {...props} />;
    case 'array':
      return <ArrayWidget {...props} />;
    case 'object':
      // Object fields should be handled by ConfigSection's nested object logic
      // If we get here, render as a read-only display indicating this should be a collapsible section
      return (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">
            {name}
            {schema.required && <span className="text-red-500 ml-1">*</span>}
          </label>
          <div className="px-3 py-2 bg-yellow-50 border border-yellow-200 rounded-md text-sm text-yellow-800">
            ⚠️ Object field should be rendered as collapsible section (ConfigSection issue)
          </div>
          {schema.description && (
            <div className="flex items-center">
              <span className="text-xs text-gray-500">{schema.description}</span>
            </div>
          )}
        </div>
      );
    case 'string':
    default:
      return <StringWidget {...props} />;
  }
};

export default ConfigWidget;
