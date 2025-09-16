/**
 * TemplateEditor Component - YAML-aware editor for response templates
 * 
 * Provides structured editing for template YAML files with support for
 * strings, arrays, and objects. Includes real-time validation and preview.
 */

import { useState, useEffect } from 'react';
import { Plus, FileText, Eye, EyeOff, Code, Layout } from 'lucide-react';
import TemplateKeyEditor from './TemplateKeyEditor';
import Section from '@/components/ui/Section';
import TextArea from '@/components/ui/TextArea';
import Badge from '@/components/ui/Badge';

interface TemplateEditorProps {
  value: Record<string, any>;
  onChange: (value: Record<string, any>) => void;
  schema?: Record<string, any>;
  onValidationChange?: (isValid: boolean, errors: string[]) => void;
}

type ViewMode = 'structured' | 'yaml' | 'preview';

const TemplateEditor: React.FC<TemplateEditorProps> = ({
  value,
  onChange,
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
        const entries = Object.entries(val);
        if (entries.length === 0) return '{}';
        return '\n' + entries.map(([k, v]) => 
          `${indent}${k}: ${processValue(v, indent + '  ')}`
        ).join('\n');
      }
      
      return String(val);
    };

    Object.entries(obj).forEach(([key, value]) => {
      yamlLines.push(`${key}: ${processValue(value)}`);
    });

    return yamlLines.join('\n');
  };

  // Parse YAML string to object (simple implementation)
  const yamlToObject = (yamlStr: string): Record<string, any> => {
    try {
      // This is a simplified YAML parser - in production you'd use a proper YAML library
      const lines = yamlStr.split('\n').filter(line => line.trim() && !line.trim().startsWith('#'));
      const result: Record<string, any> = {};
      
      for (const line of lines) {
        const match = line.match(/^([^:]+):\s*(.*)$/);
        if (match) {
          const key = match[1].trim();
          const value = match[2].trim();
          
          if (value.startsWith('"') && value.endsWith('"')) {
            result[key] = value.slice(1, -1).replace(/\\"/g, '"');
          } else if (value === '[]') {
            result[key] = [];
          } else if (value === '{}') {
            result[key] = {};
          } else if (value.startsWith('[') && value.endsWith(']')) {
            try {
              result[key] = JSON.parse(value);
            } catch {
              result[key] = value;
            }
          } else {
            result[key] = value;
          }
        }
      }
      
      return result;
    } catch (error) {
      throw new Error(`YAML parsing error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Update YAML content when value changes
  useEffect(() => {
    if (viewMode !== 'yaml') {
      setYamlContent(objectToYaml(value));
    }
  }, [value, viewMode]);

  // Validate template data
  useEffect(() => {
    const errors: string[] = [];
    
    // Basic validation
    if (typeof value !== 'object' || value === null) {
      errors.push('Template must be an object');
    } else {
      // Check for empty keys
      Object.keys(value).forEach(key => {
        if (!key.trim()) {
          errors.push('Template keys cannot be empty');
        }
      });
      
      // Check schema if provided
      if (schema && schema.expected_keys) {
        const missingKeys = schema.expected_keys.filter((key: string) => !(key in value));
        if (missingKeys.length > 0) {
          errors.push(`Missing expected keys: ${missingKeys.join(', ')}`);
        }
      }
    }
    
    setValidationErrors(errors);
    if (onValidationChange) {
      onValidationChange(errors.length === 0, errors);
    }
  }, [value, schema, onValidationChange]);

  const handleYamlChange = (newYaml: string) => {
    setYamlContent(newYaml);
    setYamlError(null);
    
    try {
      const parsed = yamlToObject(newYaml);
      onChange(parsed);
    } catch (error) {
      setYamlError(error instanceof Error ? error.message : 'YAML parsing error');
    }
  };

  const handleKeyChange = (key: string, newValue: string | string[] | Record<string, any>) => {
    const newData = { ...value, [key]: newValue };
    onChange(newData);
  };

  const handleKeyDelete = (key: string) => {
    const newData = { ...value };
    delete newData[key];
    onChange(newData);
  };

  // Key renaming removed - template keys are read-only

  const addNewKey = () => {
    const newKey = `new_template_${Date.now()}`;
    const newData = { ...value, [newKey]: '' };
    onChange(newData);
  };

  const renderStructuredView = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-gray-900">Template Keys</h3>
        <button
          type="button"
          onClick={addNewKey}
          className="flex items-center space-x-2 px-3 py-1 bg-yellow-600 text-white rounded-md hover:bg-yellow-700"
          title="Only add new keys if you're updating the code to use them"
        >
          <Plus className="w-4 h-4" />
          <span>Add Template Key</span>
        </button>
      </div>
      
      {Object.keys(value).length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <FileText className="w-8 h-8 mx-auto mb-2" />
          <p>No templates defined. Click "Add Template" to create one.</p>
        </div>
      ) : (
        Object.entries(value).map(([key, val]) => (
          <TemplateKeyEditor
            key={key}
            templateKey={key}
            value={val}
            onChange={handleKeyChange}
            onDelete={handleKeyDelete}
          />
        ))
      )}
    </div>
  );

  const renderYamlView = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          YAML Content
        </label>
        <TextArea
          value={yamlContent}
          onChange={handleYamlChange}
          placeholder="Enter YAML content..."
          rows={20}
          className={yamlError ? 'border-red-300' : ''}
        />
        {yamlError && (
          <p className="mt-1 text-sm text-red-600">{yamlError}</p>
        )}
      </div>
    </div>
  );

  const renderPreviewView = () => (
    <div className="space-y-4">
      <h3 className="text-lg font-medium text-gray-900">Template Preview</h3>
      <div className="bg-gray-50 p-4 rounded-lg">
        <pre className="text-sm text-gray-800 whitespace-pre-wrap">
          {objectToYaml(value)}
        </pre>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Template Statistics</h4>
          <div className="space-y-1 text-sm text-gray-600">
            <div>Total Keys: {Object.keys(value).length}</div>
            <div>String Values: {Object.values(value).filter(v => typeof v === 'string').length}</div>
            <div>Array Values: {Object.values(value).filter(v => Array.isArray(v)).length}</div>
            <div>Object Values: {Object.values(value).filter(v => typeof v === 'object' && v !== null && !Array.isArray(v)).length}</div>
          </div>
        </div>
        
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Template Keys</h4>
          <div className="flex flex-wrap gap-1">
            {Object.keys(value).map(key => (
              <Badge key={key} variant="secondary" className="text-xs">
                {key}
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <Section title="Template Editor">
      {/* View Mode Selector */}
      <div className="flex space-x-1 mb-6 bg-gray-100 p-1 rounded-lg">
        <button
          type="button"
          onClick={() => setViewMode('structured')}
          className={`flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
            viewMode === 'structured'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-700 hover:text-gray-900'
          }`}
        >
          <Layout className="w-4 h-4" />
          <span>Structured</span>
        </button>
        
        <button
          type="button"
          onClick={() => setViewMode('yaml')}
          className={`flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
            viewMode === 'yaml'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-700 hover:text-gray-900'
          }`}
        >
          <Code className="w-4 h-4" />
          <span>YAML</span>
        </button>
        
        <button
          type="button"
          onClick={() => setViewMode('preview')}
          className={`flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
            viewMode === 'preview'
              ? 'bg-white text-blue-600 shadow-sm'
              : 'text-gray-700 hover:text-gray-900'
          }`}
        >
          <Eye className="w-4 h-4" />
          <span>Preview</span>
        </button>
      </div>

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <h4 className="text-sm font-medium text-red-800 mb-1">Validation Errors:</h4>
          <ul className="text-sm text-red-700 list-disc list-inside">
            {validationErrors.map((error, index) => (
              <li key={index}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Content based on view mode */}
      {viewMode === 'structured' && renderStructuredView()}
      {viewMode === 'yaml' && renderYamlView()}
      {viewMode === 'preview' && renderPreviewView()}
    </Section>
  );
};

export default TemplateEditor;
