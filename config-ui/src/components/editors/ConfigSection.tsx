/**
 * ConfigSection Component - Collapsible configuration section editor
 * 
 * Implements three-level accordion structure:
 * Level 1: Major sections (collapsed by default)
 * Level 2: Subsections (provider groups, collapsed by default)  
 * Level 3: Key-value pairs (auto-generated from schema)
 */

import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Save, TestTube, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import { ConfigWidget } from './ConfigWidgets';
import MicrophoneConfigSection from './MicrophoneConfigSection';
import type { FieldSchema } from './ConfigWidgets';

interface ConfigSectionProps {
  name: string;
  title?: string;
  data: any;
  schema?: Record<string, FieldSchema>;
  hasChanges?: boolean;
  onChange: (data: any) => void;
  onValidate?: () => Promise<{ valid: boolean; errors?: any[] }>;
  onApply?: () => Promise<any>;
  disabled?: boolean;
  level?: 1 | 2; // Level 1 = major section, Level 2 = subsection
  componentName?: string; // Original component name for provider lookups
}

export const ConfigSection: React.FC<ConfigSectionProps> = ({
  name,
  title,
  data,
  schema,
  hasChanges = false,
  onChange,
  onValidate,
  onApply,
  disabled = false,
  level = 1,
  componentName
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [validationResult, setValidationResult] = useState<{ valid: boolean; errors?: any[] } | null>(null);
  
  const displayTitle = title || name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, ' ');
  
  // Auto-expand if there are validation errors
  useEffect(() => {
    if (validationResult && !validationResult.valid) {
      setIsExpanded(true);
    }
  }, [validationResult]);
  
  const handleValidate = async () => {
    if (!onValidate) return;
    
    setIsValidating(true);
    try {
      const result = await onValidate();
      setValidationResult(result);
    } catch (error) {
      setValidationResult({ 
        valid: false, 
        errors: [{ message: error instanceof Error ? error.message : 'Validation failed' }] 
      });
    } finally {
      setIsValidating(false);
    }
  };
  
  const handleApply = async () => {
    if (!onApply) return;
    
    setIsSaving(true);
    try {
      await onApply();
      setValidationResult(null); // Clear validation state after successful save
    } catch (error) {
      console.error('Apply failed:', error);
    } finally {
      setIsSaving(false);
    }
  };
  
  const updateField = (fieldName: string, value: any) => {
    const newData = { ...data, [fieldName]: value };
    onChange(newData);
  };
  
  const renderField = (fieldName: string, fieldSchema: FieldSchema) => {
    return (
      <div key={fieldName} className="p-4 border-l-2 border-gray-100">
        <ConfigWidget
          name={fieldName}
          value={data?.[fieldName]}
          schema={fieldSchema}
          onChange={(value) => updateField(fieldName, value)}
          disabled={disabled}
          path={[name, fieldName]}
          componentName={componentName || name}
        />
      </div>
    );
  };
  
  const renderSubsections = () => {
    if (!data || typeof data !== 'object') return null;
    
    // Detect microphone configuration section
    if (name.includes('microphone') && data.device_id !== undefined) {
      return (
        <MicrophoneConfigSection
          data={data}
          schema={schema}
          onChange={onChange}
          disabled={disabled}
        />
      );
    }
    
    // Detect provider subsections
    if (data.providers && typeof data.providers === 'object') {
      return (
        <div className="space-y-2">
          {/* General settings (non-provider fields) */}
          {schema && (
            <ConfigSection
              name={`${name}_general`}
              title="General Settings"
              data={Object.fromEntries(
                Object.entries(data).filter(([key]) => key !== 'providers')
              )}
              schema={Object.fromEntries(
                Object.entries(schema).filter(([key]) => key !== 'providers')
              )}
              onChange={(generalData) => {
                onChange({ ...data, ...generalData });
              }}
              level={2}
              disabled={disabled}
              componentName={componentName || name}
            />
          )}
          
          {/* Provider subsections */}
          {Object.entries(data.providers).map(([providerName, providerData]) => (
            <ConfigSection
              key={providerName}
              name={`${name}_${providerName}`}
              title={`${providerName.charAt(0).toUpperCase() + providerName.slice(1)} Provider`}
              data={providerData}
              onChange={(newProviderData) => {
                const newProviders = { ...data.providers, [providerName]: newProviderData };
                onChange({ ...data, providers: newProviders });
              }}
              level={2}
              disabled={disabled}
              componentName={componentName || name}
            />
          ))}
        </div>
      );
    }
    
    // For non-provider sections, check for nested objects and render appropriately
    if (schema) {
      // Separate nested objects from simple fields
      const nestedObjects: Array<[string, FieldSchema]> = [];
      const simpleFields: Array<[string, FieldSchema]> = [];
      
      Object.entries(schema).forEach(([fieldName, fieldSchema]) => {
        if (fieldSchema.type === 'object' && fieldSchema.properties) {
          nestedObjects.push([fieldName, fieldSchema]);
        } else {
          simpleFields.push([fieldName, fieldSchema]);
        }
      });
      
      return (
        <div className="space-y-4">
          {/* Render simple fields first */}
          {simpleFields.map(([fieldName, fieldSchema]) => 
            renderField(fieldName, fieldSchema)
          )}
          
          {/* Render nested objects as collapsible subsections */}
          {nestedObjects.map(([fieldName, fieldSchema]) => (
            <ConfigSection
              key={fieldName}
              name={`${name}_${fieldName}`}
              title={fieldSchema.description || fieldName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              data={data?.[fieldName]}
              schema={fieldSchema.properties}
              onChange={(nestedData) => {
                onChange({ ...data, [fieldName]: nestedData });
              }}
              level={2}
              disabled={disabled}
              componentName={componentName || name}
            />
          ))}
        </div>
      );
    }
    
    // Fallback: render generic object fields
    return (
      <div className="space-y-4">
        {Object.entries(data).map(([fieldName, value]) => {
          const genericSchema: FieldSchema = {
            type: typeof value === 'boolean' ? 'boolean' : 
                  typeof value === 'number' ? 'number' : 'string',
            description: '',
            required: false
          };
          return renderField(fieldName, genericSchema);
        })}
      </div>
    );
  };
  
  const getStatusIndicator = () => {
    if (isSaving || isValidating) {
      return <Loader className="h-4 w-4 text-blue-500 animate-spin" />;
    }
    
    if (validationResult) {
      return validationResult.valid ? (
        <CheckCircle className="h-4 w-4 text-green-500" />
      ) : (
        <AlertCircle className="h-4 w-4 text-red-500" />
      );
    }
    
    if (hasChanges) {
      return <div className="h-2 w-2 bg-orange-500 rounded-full" />;
    }
    
    return null;
  };
  
  const getCardClass = () => {
    const baseClass = "bg-white border rounded-lg transition-all duration-200";
    
    if (level === 1) {
      return `${baseClass} border-gray-200 shadow-sm hover:shadow-md`;
    } else {
      return `${baseClass} border-gray-100 shadow-sm`;
    }
  };
  
  const getHeaderClass = () => {
    const baseClass = "flex items-center justify-between p-4 cursor-pointer";
    
    if (level === 1) {
      return `${baseClass} hover:bg-gray-50`;
    } else {
      return `${baseClass} hover:bg-gray-25`;
    }
  };
  
  return (
    <div className={getCardClass()}>
      {/* Section Header */}
      <div className={getHeaderClass()} onClick={() => setIsExpanded(!isExpanded)}>
        <div className="flex items-center space-x-3">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-400" />
          )}
          <div>
            <h3 className={`font-medium ${level === 1 ? 'text-lg text-gray-900' : 'text-md text-gray-800'}`}>
              {displayTitle}
            </h3>
            {level === 1 && schema && (
              <p className="text-sm text-gray-500 mt-1">
                {Object.keys(schema).length} settings
              </p>
            )}
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          {getStatusIndicator()}
          
          {hasChanges && isExpanded && level === 1 && (
            <div className="flex items-center space-x-2">
              {onValidate && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleValidate();
                  }}
                  disabled={isValidating || disabled}
                  className="p-1 text-blue-600 hover:text-blue-800 disabled:opacity-50"
                  title="Validate section"
                >
                  <TestTube className="h-4 w-4" />
                </button>
              )}
              
              {onApply && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleApply();
                  }}
                  disabled={isSaving || disabled}
                  className="p-1 text-green-600 hover:text-green-800 disabled:opacity-50"
                  title="Apply changes"
                >
                  <Save className="h-4 w-4" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Validation Errors */}
      {isExpanded && validationResult && !validationResult.valid && (
        <div className="px-4 pb-2">
          <div className="bg-red-50 border border-red-200 rounded-md p-3">
            <div className="flex items-center">
              <AlertCircle className="h-4 w-4 text-red-500 mr-2" />
              <span className="text-sm font-medium text-red-800">Validation Errors</span>
            </div>
            <ul className="mt-2 text-sm text-red-700 space-y-1">
              {validationResult.errors?.map((error, index) => (
                <li key={index}>• {error.message || error}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      
      {/* Section Content */}
      {isExpanded && (
        <div className="border-t border-gray-100">
          <div className="p-4">
            {renderSubsections()}
          </div>
        </div>
      )}
    </div>
  );
};

export default ConfigSection;
