/**
 * LocalizationEditor Component - Multi-type value editor for localization data
 * 
 * Provides structured editing for localization YAML files with support for
 * strings, arrays, and objects. Includes domain-specific validation and preview.
 */

import { useState, useEffect } from 'react';
import { Plus, Eye, Code, Layout, Globe } from 'lucide-react';
import LocalizationKeyEditor from './LocalizationKeyEditor';
import Section from '@/components/ui/Section';
import TextArea from '@/components/ui/TextArea';
import Badge from '@/components/ui/Badge';

interface LocalizationEditorProps {
  value: Record<string, any>;
  onChange: (value: Record<string, any>) => void;
  domain?: string;
  schema?: Record<string, any>;
  onValidationChange?: (isValid: boolean, errors: string[]) => void;
}

type ViewMode = 'structured' | 'yaml' | 'preview';

const LocalizationEditor: React.FC<LocalizationEditorProps> = ({
  value,
  onChange,
  domain,
  schema,
  onValidationChange
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('structured');
  const [yamlContent, setYamlContent] = useState('');
  const [yamlError, setYamlError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Convert object to YAML string (simple implementation)
  const objectToYaml = (obj: Record<string, any>): string => {
    const yamlLines: string[] = [];
    
    const processValue = (val: any, indent: string = ''): string => {
      if (typeof val === 'string') {
        // Handle multiline strings
        if (val.includes('\n')) {
          return `|\n${val.split('\n').map(line => `${indent}  ${line}`).join('\n')}`;
        }
        return `"${val.replace(/"/g, '\\"')}"`;
      }
      
      if (Array.isArray(val)) {
        if (val.length === 0) return '[]';
        return '\n' + val.map(item => `${indent}- ${processValue(item, indent + '  ')}`).join('\n');
      }
      
      if (typeof val === 'object' && val !== null) {
        if (Object.keys(val).length === 0) return '{}';
        return '\n' + Object.entries(val).map(([k, v]) => 
          `${indent}${k}: ${processValue(v, indent + '  ')}`
        ).join('\n');
      }
      
      return String(val);
    };

    Object.entries(obj).forEach(([key, val]) => {
      yamlLines.push(`${key}: ${processValue(val)}`);
    });

    return yamlLines.join('\n');
  };

  // Parse YAML string to object (simple implementation)
  const yamlToObject = (yamlStr: string): Record<string, any> => {
    try {
      // Simple YAML parser - in production, use a proper YAML library
      const lines = yamlStr.split('\n').filter(line => line.trim() && !line.trim().startsWith('#'));
      const result: Record<string, any> = {};
      let currentKey = '';
      let currentArray: string[] = [];
      let inArray = false;

      for (const line of lines) {
        const trimmed = line.trim();
        
        if (trimmed.startsWith('- ')) {
          // Array item
          if (inArray) {
            currentArray.push(trimmed.substring(2).trim().replace(/^"(.*)"$/, '$1'));
          }
        } else if (trimmed.includes(':')) {
          // Key-value pair
          if (inArray && currentKey) {
            result[currentKey] = currentArray;
            currentArray = [];
            inArray = false;
          }
          
          const [key, ...valueParts] = trimmed.split(':');
          const value = valueParts.join(':').trim();
          currentKey = key.trim();
          
          if (value) {
            if (value.startsWith('[') && value.endsWith(']')) {
              // Inline array
              result[currentKey] = value.slice(1, -1).split(',').map(item => item.trim().replace(/^"(.*)"$/, '$1'));
            } else if (value.startsWith('{') && value.endsWith('}')) {
              // Inline object (simplified)
              result[currentKey] = {};
            } else {
              // String value
              result[currentKey] = value.replace(/^"(.*)"$/, '$1');
            }
          } else {
            // Multi-line value starts
            inArray = true;
            currentArray = [];
          }
        }
      }
      
      // Handle final array
      if (inArray && currentKey) {
        result[currentKey] = currentArray;
      }

      return result;
    } catch (error) {
      throw new Error(`YAML parsing error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Update YAML content when value changes
  useEffect(() => {
    if (viewMode === 'yaml') {
      setYamlContent(objectToYaml(value));
    }
  }, [value, viewMode]);

  // Domain-specific validation
  const validateLocalizationData = (data: Record<string, any>): string[] => {
    const errors: string[] = [];
    
    // Basic validation
    if (!data || typeof data !== 'object') {
      errors.push('Localization data must be an object');
      return errors;
    }

    // Domain-specific validation
    if (domain === 'datetime') {
      const requiredFields = ['weekdays', 'months'];
      requiredFields.forEach(field => {
        if (!data[field]) {
          errors.push(`Missing required field for datetime domain: ${field}`);
        } else if (!Array.isArray(data[field])) {
          errors.push(`Field '${field}' must be an array`);
        }
      });
    } else if (domain === 'components') {
      if (!data.component_mappings || typeof data.component_mappings !== 'object') {
        errors.push('Missing or invalid component_mappings object');
      }
    } else if (domain === 'commands') {
      if (!data.stop_patterns || !Array.isArray(data.stop_patterns)) {
        errors.push('Missing or invalid stop_patterns array');
      }
    }

    // Check for empty values
    Object.entries(data).forEach(([key, value]) => {
      if (value === null || value === undefined || value === '') {
        errors.push(`Empty value for key: ${key}`);
      }
    });

    return errors;
  };

  // Validate current data
  useEffect(() => {
    const errors = validateLocalizationData(value);
    setValidationErrors(errors);
    onValidationChange?.(errors.length === 0, errors);
  }, [value, domain, onValidationChange]);

  const handleYamlChange = (newYaml: string) => {
    setYamlContent(newYaml);
    setYamlError(null);

    try {
      const parsed = yamlToObject(newYaml);
      onChange(parsed);
    } catch (error) {
      setYamlError(error instanceof Error ? error.message : 'Parse error');
    }
  };

  const handleAddKey = () => {
    const newKey = `new_key_${Date.now()}`;
    onChange({
      ...value,
      [newKey]: getDomainDefaultValue()
    });
  };

  const getDomainDefaultValue = (): any => {
    if (domain === 'datetime') {
      return ['Item 1', 'Item 2'];
    } else if (domain === 'components') {
      return { 'new_component': 'mapped_value' };
    } else if (domain === 'commands') {
      return ['command_pattern'];
    }
    return 'New value';
  };

  const handleKeyChange = (oldKey: string, newKey: string, newValue: any) => {
    const newData = { ...value };
    delete newData[oldKey];
    newData[newKey] = newValue;
    onChange(newData);
  };

  const handleDeleteKey = (key: string) => {
    const newData = { ...value };
    delete newData[key];
    onChange(newData);
  };

  const getViewModeIcon = (mode: ViewMode) => {
    switch (mode) {
      case 'structured': return <Layout className="w-4 h-4" />;
      case 'yaml': return <Code className="w-4 h-4" />;
      case 'preview': return <Eye className="w-4 h-4" />;
    }
  };

  const renderPreview = () => {
    return (
      <div className="space-y-4">
        <div className="p-4 bg-gray-50 rounded-lg">
          <h4 className="font-medium text-gray-700 mb-2 flex items-center gap-2">
            <Globe className="w-4 h-4" />
            Domain: {domain || 'Unknown'}
          </h4>
          <div className="text-sm text-gray-600">
            {schema?.domain_description || `Localization data for ${domain} domain`}
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h5 className="font-medium text-gray-700 mb-2">Keys ({Object.keys(value).length})</h5>
            <div className="space-y-1">
              {Object.keys(value).map(key => (
                <div key={key} className="flex items-center gap-2">
                  <Badge variant="default">{key}</Badge>
                  <span className="text-sm text-gray-500">
                    {Array.isArray(value[key]) ? `Array (${value[key].length})` :
                     typeof value[key] === 'object' ? `Object (${Object.keys(value[key]).length})` :
                     'String'}
                  </span>
                </div>
              ))}
            </div>
          </div>
          
          <div>
            <h5 className="font-medium text-gray-700 mb-2">Validation</h5>
            {validationErrors.length === 0 ? (
              <div className="text-green-600 text-sm">✓ No validation errors</div>
            ) : (
              <div className="space-y-1">
                {validationErrors.map((error, index) => (
                  <div key={index} className="text-red-600 text-sm">✗ {error}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* View Mode Selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-700">View:</span>
        {(['structured', 'yaml', 'preview'] as ViewMode[]).map((mode) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className={`flex items-center gap-2 px-3 py-1 rounded-md text-sm transition-colors ${
              viewMode === mode
                ? 'bg-blue-100 text-blue-700 border border-blue-200'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {getViewModeIcon(mode)}
            {mode.charAt(0).toUpperCase() + mode.slice(1)}
          </button>
        ))}
      </div>

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md">
          <h4 className="font-medium text-red-800 mb-2">Validation Errors:</h4>
          <ul className="text-sm text-red-700 space-y-1">
            {validationErrors.map((error, index) => (
              <li key={index}>• {error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Content based on view mode */}
      {viewMode === 'structured' && (
        <Section title="Localization Entries" className="space-y-4">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-600">
              {Object.keys(value).length} entries
            </div>
            <button
              onClick={handleAddKey}
              className="flex items-center gap-2 px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
            >
              <Plus className="w-4 h-4" />
              Add Entry
            </button>
          </div>
          
          <div className="space-y-3">
            {Object.entries(value).map(([key, val]) => (
              <LocalizationKeyEditor
                key={key}
                keyName={key}
                value={val}
                onChange={(newKey, newValue) => handleKeyChange(key, newKey, newValue)}
                onDelete={() => handleDeleteKey(key)}
                domain={domain}
              />
            ))}
          </div>
          
          {Object.keys(value).length === 0 && (
            <div className="text-center py-8 text-gray-500">
              <Globe className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No localization entries yet</p>
              <p className="text-sm mt-1">Click "Add Entry" to get started</p>
            </div>
          )}
        </Section>
      )}

      {viewMode === 'yaml' && (
        <Section title="YAML Editor">
          <div className="space-y-2">
            {yamlError && (
              <div className="p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                {yamlError}
              </div>
            )}
            <TextArea
              value={yamlContent}
              onChange={handleYamlChange}
              rows={20}
              className="font-mono text-sm"
              placeholder="# YAML content will appear here"
            />
          </div>
        </Section>
      )}

      {viewMode === 'preview' && (
        <Section title="Preview">
          {renderPreview()}
        </Section>
      )}
    </div>
  );
};

export default LocalizationEditor;
