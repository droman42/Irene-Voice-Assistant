/**
 * SpacyValueEditor - Specialized input components for different SpaCy attribute value types
 * 
 * Provides appropriate input controls based on the SpaCy attribute structure,
 * ensuring proper editing while maintaining the underlying data integrity.
 */

import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { SpacyAttributeStructure, getOperatorOptions } from '@/utils/spacyAttributeHelpers';

interface SpacyValueEditorProps {
  structure: SpacyAttributeStructure;
  onChange: (newValue: any) => void;
  disabled?: boolean;
}

const SpacyValueEditor: React.FC<SpacyValueEditorProps> = ({
  structure,
  onChange,
  disabled = false
}) => {
  const { valueType, editableValue } = structure;

  // String input for simple text values and regex patterns
  const renderStringInput = (placeholder?: string) => (
    <input
      type="text"
      value={editableValue || ''}
      onChange={(e) => onChange(e.target.value)}
      className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      placeholder={placeholder}
      disabled={disabled}
    />
  );

  // Boolean toggle for true/false values
  const renderBooleanInput = () => (
    <select
      value={String(editableValue)}
      onChange={(e) => onChange(e.target.value === 'true')}
      className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      disabled={disabled}
    >
      <option value="true">True</option>
      <option value="false">False</option>
    </select>
  );

  // Number input for numeric values
  const renderNumberInput = () => (
    <input
      type="number"
      value={editableValue || ''}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      disabled={disabled}
    />
  );

  // Operator dropdown for OP attribute
  const renderOperatorInput = () => {
    const operators = getOperatorOptions();
    
    return (
      <select
        value={editableValue || ''}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        disabled={disabled}
      >
        <option value="">Select operator...</option>
        {operators.map(op => (
          <option key={op} value={op}>
            {op} - {getOperatorDescription(op)}
          </option>
        ))}
      </select>
    );
  };

  // Array editor for IN/NOT_IN lists
  const renderListInput = () => {
    const listValue: string[] = Array.isArray(editableValue) ? editableValue : [];
    
    const addItem = () => {
      onChange([...listValue, '']);
    };

    const updateItem = (index: number, newValue: string) => {
      const newList = [...listValue];
      newList[index] = newValue;
      onChange(newList);
    };

    const removeItem = (index: number) => {
      const newList = listValue.filter((_, i) => i !== index);
      onChange(newList);
    };

    return (
      <div className="space-y-2">
        <div className="space-y-2">
          {listValue.map((item, index) => (
            <div key={index} className="flex items-center gap-2">
              <span className="text-xs text-gray-500 w-6">{index + 1}.</span>
              <input
                type="text"
                value={item}
                onChange={(e) => updateItem(index, e.target.value)}
                className="flex-1 border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder={`Item ${index + 1}`}
                disabled={disabled}
              />
              <button
                type="button"
                onClick={() => removeItem(index)}
                className="p-2 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
                disabled={disabled}
                title="Remove item"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
        
        <button
          type="button"
          onClick={addItem}
          className="flex items-center gap-2 px-3 py-2 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-lg transition-colors"
          disabled={disabled}
        >
          <Plus className="w-4 h-4" />
          Add item
        </button>
        
        {listValue.length === 0 && (
          <div className="text-sm text-gray-500 italic">
            No items yet. Click "Add item" to get started.
          </div>
        )}
      </div>
    );
  };

  // JSON editor for unknown/custom structures
  const renderJsonInput = () => (
    <div className="space-y-2">
      <div className="text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded p-2">
        ⚠️ Custom JSON structure - edit carefully to maintain validity
      </div>
      <textarea
        value={editableValue || ''}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        rows={3}
        placeholder="Enter valid JSON..."
        disabled={disabled}
      />
    </div>
  );

  // Main render logic based on value type
  switch (valueType) {
    case 'string':
      return renderStringInput();
    
    case 'regex':
      return renderStringInput('Enter regex pattern (e.g., word1|word2)');
    
    case 'boolean':
      return renderBooleanInput();
    
    case 'number':
      return renderNumberInput();
    
    case 'operator':
      return renderOperatorInput();
    
    case 'list':
      return renderListInput();
    
    case 'unknown':
      return renderJsonInput();
    
    default:
      return renderStringInput();
  }
};

// Helper function to get operator descriptions
function getOperatorDescription(op: string): string {
  const descriptions: Record<string, string> = {
    '?': 'Zero or one',
    '*': 'Zero or more',
    '+': 'One or more',
    '!': 'Negation',
    '{2}': 'Exactly 2',
    '{2,4}': 'Between 2 and 4',
    '{2,}': '2 or more',
    '{,4}': 'Up to 4'
  };
  
  return descriptions[op] || 'Custom quantifier';
}

export default SpacyValueEditor;
