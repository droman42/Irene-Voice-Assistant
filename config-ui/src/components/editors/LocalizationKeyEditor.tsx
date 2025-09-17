/**
 * LocalizationKeyEditor Component - Type-aware editor for localization values
 * 
 * Handles editing of different value types (strings, arrays, objects) for localization data.
 * Provides appropriate UI controls based on the value type and domain context.
 */

import { useState } from 'react';
import { Trash2, Plus, Type, List, Hash, ChevronDown, ChevronRight } from 'lucide-react';
import Input from '@/components/ui/Input';
import TextArea from '@/components/ui/TextArea';
import Badge from '@/components/ui/Badge';

interface LocalizationKeyEditorProps {
  keyName: string;
  value: any;
  onChange: (newKey: string, newValue: any) => void;
  onDelete: () => void;
  domain?: string;
}

type ValueType = 'string' | 'array' | 'object';

const LocalizationKeyEditor: React.FC<LocalizationKeyEditorProps> = ({
  keyName,
  value,
  onChange,
  onDelete,
  domain
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [currentKey, setCurrentKey] = useState(keyName);

  const getValueType = (val: any): ValueType => {
    if (Array.isArray(val)) return 'array';
    if (typeof val === 'object' && val !== null) return 'object';
    return 'string';
  };

  const [valueType, setValueType] = useState<ValueType>(getValueType(value));

  const handleKeyChange = (newKey: string) => {
    setCurrentKey(newKey);
    onChange(newKey, value);
  };

  const handleValueChange = (newValue: any) => {
    onChange(currentKey, newValue);
  };

  const handleTypeChange = (newType: ValueType) => {
    setValueType(newType);
    let newValue: any;
    
    switch (newType) {
      case 'string':
        newValue = Array.isArray(value) ? value.join(', ') : 
                   typeof value === 'object' ? JSON.stringify(value) : 
                   String(value);
        break;
      case 'array':
        newValue = Array.isArray(value) ? value : 
                   typeof value === 'string' ? value.split(',').map(s => s.trim()) :
                   [String(value)];
        break;
      case 'object':
        newValue = typeof value === 'object' && !Array.isArray(value) ? value :
                   Array.isArray(value) ? value.reduce((obj, item, index) => ({ ...obj, [`item_${index}`]: item }), {}) :
                   { value: String(value) };
        break;
    }
    
    handleValueChange(newValue);
  };

  const renderStringEditor = () => {
    const stringValue = String(value);
    
    if (stringValue.length > 100 || stringValue.includes('\n')) {
      return (
        <TextArea
          value={stringValue}
          onChange={handleValueChange}
          rows={3}
          className="text-sm"
          placeholder="Enter localization text..."
        />
      );
    }
    
    return (
      <Input
        value={stringValue}
        onChange={handleValueChange}
        placeholder="Enter localization text..."
        className="text-sm"
      />
    );
  };

  const renderArrayEditor = () => {
    const arrayValue = Array.isArray(value) ? value : [String(value)];
    
    const handleArrayChange = (newArray: string[]) => {
      handleValueChange(newArray);
    };

    const addArrayItem = () => {
      handleArrayChange([...arrayValue, '']);
    };

    const updateArrayItem = (index: number, newValue: string) => {
      const newArray = [...arrayValue];
      newArray[index] = newValue;
      handleArrayChange(newArray);
    };

    const removeArrayItem = (index: number) => {
      const newArray = arrayValue.filter((_, i) => i !== index);
      handleArrayChange(newArray);
    };

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">{arrayValue.length} items</span>
          <button
            onClick={addArrayItem}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors"
          >
            <Plus className="w-3 h-3" />
            Add Item
          </button>
        </div>
        
        <div className="space-y-2 max-h-40 overflow-y-auto">
          {arrayValue.map((item, index) => (
            <div key={index} className="flex items-center gap-2">
              <span className="text-xs text-gray-400 w-6">{index}</span>
              <Input
                value={String(item)}
                onChange={(newValue) => updateArrayItem(index, newValue)}
                placeholder={`Item ${index + 1}`}
                className="text-sm flex-1"
              />
              <button
                onClick={() => removeArrayItem(index)}
                className="p-1 text-red-500 hover:text-red-700 transition-colors"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
        
        {arrayValue.length === 0 && (
          <div className="text-center py-4 text-gray-500 text-sm">
            No items yet. Click "Add Item" to get started.
          </div>
        )}
      </div>
    );
  };

  const renderObjectEditor = () => {
    const objectValue = typeof value === 'object' && !Array.isArray(value) && value !== null ? 
                       value : 
                       { value: String(value) };
    
    const handleObjectChange = (newObject: Record<string, any>) => {
      handleValueChange(newObject);
    };

    const addObjectKey = () => {
      const newKey = `new_key_${Date.now()}`;
      handleObjectChange({
        ...objectValue,
        [newKey]: ''
      });
    };

    const updateObjectEntry = (oldKey: string, newKey: string, newValue: string) => {
      const newObject = { ...objectValue };
      delete newObject[oldKey];
      newObject[newKey] = newValue;
      handleObjectChange(newObject);
    };

    const removeObjectKey = (key: string) => {
      const newObject = { ...objectValue };
      delete newObject[key];
      handleObjectChange(newObject);
    };

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">{Object.keys(objectValue).length} properties</span>
          <button
            onClick={addObjectKey}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors"
          >
            <Plus className="w-3 h-3" />
            Add Property
          </button>
        </div>
        
        <div className="space-y-2 max-h-40 overflow-y-auto">
          {Object.entries(objectValue).map(([key, val]) => (
            <div key={key} className="grid grid-cols-2 gap-2">
              <Input
                value={key}
                onChange={(newKey) => updateObjectEntry(key, newKey, String(val))}
                placeholder="Property name"
                className="text-sm"
              />
              <div className="flex items-center gap-2">
                <Input
                  value={String(val)}
                  onChange={(newValue) => updateObjectEntry(key, key, newValue)}
                  placeholder="Property value"
                  className="text-sm flex-1"
                />
                <button
                  onClick={() => removeObjectKey(key)}
                  className="p-1 text-red-500 hover:text-red-700 transition-colors"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
        
        {Object.keys(objectValue).length === 0 && (
          <div className="text-center py-4 text-gray-500 text-sm">
            No properties yet. Click "Add Property" to get started.
          </div>
        )}
      </div>
    );
  };

  const getTypeIcon = (type: ValueType) => {
    switch (type) {
      case 'string': return <Type className="w-3 h-3" />;
      case 'array': return <List className="w-3 h-3" />;
      case 'object': return <Hash className="w-3 h-3" />;
    }
  };


  const getDomainHint = () => {
    if (domain === 'datetime' && keyName === 'weekdays') {
      return 'List of weekday names in order (Monday, Tuesday, ...)';
    } else if (domain === 'datetime' && keyName === 'months') {
      return 'List of month names in order (January, February, ...)';
    } else if (domain === 'components' && keyName === 'component_mappings') {
      return 'Map component aliases to their canonical names';
    } else if (domain === 'commands' && keyName === 'stop_patterns') {
      return 'List of command patterns to stop execution';
    }
    return null;
  };

  const domainHint = getDomainHint();

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white">
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-gray-400 hover:text-gray-600 transition-colors"
        >
          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
        
        <div className="flex-1">
          <Input
            value={currentKey}
            onChange={handleKeyChange}
            className="text-sm font-medium"
            placeholder="Key name"
          />
        </div>
        
        <div className="flex items-center gap-2">
          {/* Type selector */}
          <select
            value={valueType}
            onChange={(e) => handleTypeChange(e.target.value as ValueType)}
            className="text-xs border border-gray-200 rounded px-2 py-1 bg-white"
          >
            <option value="string">String</option>
            <option value="array">Array</option>
            <option value="object">Object</option>
          </select>
          
          <Badge variant="default" className="text-xs">
            {getTypeIcon(valueType)}
            {valueType}
          </Badge>
          
          <button
            onClick={onDelete}
            className="p-1 text-red-500 hover:text-red-700 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Domain hint */}
      {domainHint && (
        <div className="mb-3 p-2 bg-blue-50 border border-blue-200 rounded text-blue-700 text-sm">
          💡 {domainHint}
        </div>
      )}

      {/* Value editor */}
      {isExpanded && (
        <div className="space-y-2">
          {valueType === 'string' && renderStringEditor()}
          {valueType === 'array' && renderArrayEditor()}
          {valueType === 'object' && renderObjectEditor()}
        </div>
      )}
    </div>
  );
};

export default LocalizationKeyEditor;
