/**
 * TemplateKeyEditor Component - Specialized editor for template key-value pairs
 * 
 * Handles different template value types: strings, arrays, and objects
 * with appropriate UI components for each type.
 */

import { useState } from 'react';
import { Trash2, Plus, ChevronDown, ChevronRight } from 'lucide-react';
import Input from '@/components/ui/Input';
import TextArea from '@/components/ui/TextArea';
import ArrayOfStringsEditor from './ArrayOfStringsEditor';

interface TemplateKeyEditorProps {
  templateKey: string;
  value: string | string[] | Record<string, any>;
  onChange: (key: string, value: string | string[] | Record<string, any>) => void;
  onDelete: (key: string) => void;
  onKeyChange: (oldKey: string, newKey: string) => void;
}

const TemplateKeyEditor: React.FC<TemplateKeyEditorProps> = ({
  templateKey,
  value,
  onChange,
  onDelete,
  onKeyChange
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [keyName, setKeyName] = useState(templateKey);

  const handleKeyNameChange = (newKey: string) => {
    setKeyName(newKey);
    if (newKey !== templateKey) {
      onKeyChange(templateKey, newKey);
    }
  };

  const getValueType = (): 'string' | 'array' | 'object' => {
    if (Array.isArray(value)) return 'array';
    if (typeof value === 'object' && value !== null) return 'object';
    return 'string';
  };

  const handleValueChange = (newValue: string | string[] | Record<string, any>) => {
    onChange(templateKey, newValue);
  };

  const handleStringChange = (newValue: string) => {
    handleValueChange(newValue);
  };

  const handleArrayChange = (newArray: string[]) => {
    handleValueChange(newArray);
  };

  const handleObjectKeyChange = (oldKey: string, newKey: string, objValue: any) => {
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      const newObj = { ...value };
      delete newObj[oldKey];
      newObj[newKey] = objValue;
      handleValueChange(newObj);
    }
  };

  const handleObjectValueChange = (objKey: string, objValue: string) => {
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      const newObj = { ...value, [objKey]: objValue };
      handleValueChange(newObj);
    }
  };

  const handleObjectKeyDelete = (objKey: string) => {
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      const newObj = { ...value };
      delete newObj[objKey];
      handleValueChange(newObj);
    }
  };

  const addObjectKey = () => {
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      const newKey = `new_key_${Date.now()}`;
      const newObj = { ...value, [newKey]: '' };
      handleValueChange(newObj);
    }
  };

  const renderValueEditor = () => {
    const valueType = getValueType();

    switch (valueType) {
      case 'string':
        return (
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              Template Value (String)
            </label>
            {typeof value === 'string' && value.length > 100 ? (
              <TextArea
                value={value as string}
                onChange={handleStringChange}
                placeholder="Enter template content..."
                rows={4}
              />
            ) : (
              <Input
                value={value as string}
                onChange={handleStringChange}
                placeholder="Enter template content..."
              />
            )}
          </div>
        );

      case 'array':
        return (
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              Template Values (Array)
            </label>
            <ArrayOfStringsEditor
              value={value as string[]}
              onChange={handleArrayChange}
              placeholder="Enter template option..."
            />
          </div>
        );

      case 'object':
        return (
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <label className="block text-sm font-medium text-gray-700">
                Template Object
              </label>
              <button
                type="button"
                onClick={addObjectKey}
                className="flex items-center space-x-1 text-sm text-blue-600 hover:text-blue-500"
              >
                <Plus className="w-4 h-4" />
                <span>Add Key</span>
              </button>
            </div>
            <div className="space-y-3 bg-gray-50 p-3 rounded-md">
              {typeof value === 'object' && value !== null && !Array.isArray(value) && (
                Object.entries(value).map(([objKey, objValue]) => (
                  <div key={objKey} className="flex space-x-2">
                    <Input
                      value={objKey}
                      onChange={(newKey) => handleObjectKeyChange(objKey, newKey, objValue)}
                      placeholder="Key name..."
                      className="w-1/3"
                    />
                    <Input
                      value={String(objValue)}
                      onChange={(newValue) => handleObjectValueChange(objKey, newValue)}
                      placeholder="Value..."
                      className="flex-1"
                    />
                    <button
                      type="button"
                      onClick={() => handleObjectKeyDelete(objKey)}
                      className="p-2 text-red-600 hover:text-red-500"
                      title="Delete key"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="border border-gray-200 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center space-x-2 text-sm font-medium text-gray-700 hover:text-gray-900"
        >
          {isExpanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
          <span>Template Key</span>
        </button>
        
        <button
          type="button"
          onClick={() => onDelete(templateKey)}
          className="p-1 text-red-600 hover:text-red-500"
          title="Delete template key"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {isExpanded && (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Key Name
            </label>
            <Input
              value={keyName}
              onChange={handleKeyNameChange}
              placeholder="Enter key name..."
            />
          </div>

          {renderValueEditor()}

          <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded">
            <strong>Type:</strong> {getValueType()} | 
            <strong> Length:</strong> {
              getValueType() === 'string' 
                ? (value as string).length
                : getValueType() === 'array'
                ? (value as string[]).length
                : Object.keys(value as object).length
            }
          </div>
        </div>
      )}
    </div>
  );
};

export default TemplateKeyEditor;
