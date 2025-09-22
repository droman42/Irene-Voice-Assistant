/**
 * SpacyAttributeEditor - Enhanced editor for spaCy token attributes
 * 
 * Provides structured editing for spaCy token patterns with:
 * - Intelligent parsing of SpaCy attribute structures  
 * - Type-aware value editors that preserve attribute semantics
 * - Support for complex patterns (REGEX, IN, NOT_IN, etc.)
 * - User-friendly display of attribute names and types
 */

import { useState } from 'react';
import { Plus, Trash2, ChevronDown, ChevronRight } from 'lucide-react';
import { 
  parseSpacyAttribute, 
  reconstructSpacyAttribute, 
  getSpacyAttributeSuggestions,
  type SpacyAttributeStructure 
} from '@/utils/spacyAttributeHelpers';
import SpacyValueEditor from './SpacyValueEditor';

interface SpacyAttributeEditorProps {
  value: Record<string, any>;
  onChange: (value: Record<string, any>) => void;
  disabled?: boolean;
}

interface StructuredAttributeEditorProps {
  attributeName: string;
  structure: SpacyAttributeStructure;
  onChange: (newValue: any) => void;
  onRemove: () => void;
  disabled?: boolean;
}

// Structured attribute editor that handles complex SpaCy patterns
function StructuredAttributeEditor({ 
  attributeName, 
  structure, 
  onChange, 
  onRemove, 
  disabled 
}: StructuredAttributeEditorProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const handleValueChange = (newValue: any) => {
    const reconstructedValue = reconstructSpacyAttribute(structure, newValue);
    onChange(reconstructedValue);
  };

  const getTypeIndicator = () => {
    const typeColors: Record<string, string> = {
      'string': 'bg-blue-100 text-blue-800',
      'regex': 'bg-purple-100 text-purple-800',
      'list': 'bg-green-100 text-green-800',
      'boolean': 'bg-yellow-100 text-yellow-800',
      'number': 'bg-orange-100 text-orange-800',
      'operator': 'bg-red-100 text-red-800',
      'unknown': 'bg-gray-100 text-gray-800'
    };

    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${typeColors[structure.valueType] || typeColors.unknown}`}>
        {structure.valueType}
      </span>
    );
  };

  return (
    <div className="border border-gray-200 rounded-lg bg-white">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-100">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 text-left flex-1 hover:bg-gray-50 -m-1 p-1 rounded"
          disabled={disabled}
        >
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-500" />
          )}
          <span className="font-medium text-gray-900">{structure.displayLabel}</span>
          {getTypeIndicator()}
        </button>
        
        <button
          onClick={onRemove}
          className="p-1 text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
          disabled={disabled}
          title="Remove attribute"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Expandable Content */}
      {isExpanded && (
        <div className="p-3 space-y-3">
          {/* Description/Help */}
          {structure.isComplex && (
            <div className="text-sm text-gray-600 bg-blue-50 border border-blue-200 rounded p-2">
              <strong>{structure.attributeName}</strong> with <strong>{structure.valueType}</strong> matching
            </div>
          )}
          
          {/* Value Editor */}
          <SpacyValueEditor
            structure={structure}
            onChange={handleValueChange}
            disabled={disabled}
          />
        </div>
      )}
    </div>
  );
}

// Main SpaCy Attribute Editor component
export default function SpacyAttributeEditor({ 
  value, 
  onChange, 
  disabled = false 
}: SpacyAttributeEditorProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newAttributeName, setNewAttributeName] = useState('');

  // Parse all current attributes into structured format
  const structuredAttributes = Object.entries(value || {}).map(([key, val]) => ({
    key,
    structure: parseSpacyAttribute(key, val)
  }));

  const handleAttributeChange = (attributeKey: string, newValue: any) => {
    const newAttributes = { ...value };
    newAttributes[attributeKey] = newValue;
    onChange(newAttributes);
  };

  const handleAttributeRemove = (attributeKey: string) => {
    const newAttributes = { ...value };
    delete newAttributes[attributeKey];
    onChange(newAttributes);
  };

  const handleAddAttribute = () => {
    if (!newAttributeName.trim()) return;
    
    const attributeName = newAttributeName.trim();
    const newAttributes = { ...value };
    
    // Set default value based on common attribute patterns
    if (attributeName === 'OP') {
      newAttributes[attributeName] = '?';
    } else if (attributeName.includes('IS_') || attributeName.includes('LIKE_')) {
      newAttributes[attributeName] = true;
    } else {
      newAttributes[attributeName] = '';
    }
    
    onChange(newAttributes);
    setNewAttributeName('');
    setShowAddForm(false);
  };

  const getAttributeSuggestions = () => {
    const suggestions = getSpacyAttributeSuggestions();
    const currentKeys = Object.keys(value || {});
    return Object.keys(suggestions).filter(key => !currentKeys.includes(key));
  };

  return (
    <div className="space-y-3">
      {/* Current Attributes */}
      {structuredAttributes.length > 0 ? (
        <div className="space-y-2">
          {structuredAttributes.map(({ key, structure }) => (
            <StructuredAttributeEditor
              key={key}
              attributeName={key}
              structure={structure}
              onChange={(newValue) => handleAttributeChange(key, newValue)}
              onRemove={() => handleAttributeRemove(key)}
              disabled={disabled}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-lg border border-gray-200">
          <div className="text-sm font-medium mb-1">No attributes defined</div>
          <div className="text-xs">Add SpaCy attributes to define token matching patterns</div>
        </div>
      )}

      {/* Add New Attribute */}
      {!showAddForm ? (
        <button
          onClick={() => setShowAddForm(true)}
          className="w-full flex items-center justify-center gap-2 p-3 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-gray-400 hover:text-gray-700 transition-colors"
          disabled={disabled}
        >
          <Plus className="w-4 h-4" />
          Add attribute
        </button>
      ) : (
        <div className="border border-gray-200 rounded-lg p-3 bg-gray-50">
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Attribute Name
              </label>
              <select
                value={newAttributeName}
                onChange={(e) => setNewAttributeName(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Select attribute...</option>
                {getAttributeSuggestions().map(attr => (
                  <option key={attr} value={attr}>{attr}</option>
                ))}
                <option value="custom">Custom attribute...</option>
              </select>
            </div>
            
            {newAttributeName === 'custom' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Custom Attribute Name
                </label>
                <input
                  type="text"
                  value=""
                  onChange={(e) => setNewAttributeName(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Enter custom attribute name..."
                />
              </div>
            )}
            
            <div className="flex gap-2">
              <button
                onClick={handleAddAttribute}
                disabled={!newAttributeName || disabled}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm"
              >
                Add
              </button>
              <button
                onClick={() => {
                  setShowAddForm(false);
                  setNewAttributeName('');
                }}
                className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition-colors text-sm"
                disabled={disabled}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}