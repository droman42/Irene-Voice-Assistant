/**
 * SpacyAttributeEditor - Enhanced editor for spaCy token attributes
 * 
 * Provides structured editing for spaCy token patterns with:
 * - Categorized attribute selection
 * - Type-aware value editors
 * - Support for complex patterns (IN, regex, etc.)
 * - Helpful tooltips and examples
 */

import { useState } from 'react';
import { Plus, Trash2, HelpCircle, ChevronDown, ChevronRight } from 'lucide-react';
import { 
  SPACY_ATTRIBUTES, 
  ATTRIBUTE_CATEGORIES, 
  getAttributeByKey,
  getCategoryColor,
  type SpacyAttribute 
} from '@/utils/spacyAttributes';

interface SpacyAttributeEditorProps {
  value: Record<string, any>;
  onChange: (value: Record<string, any>) => void;
  disabled?: boolean;
}

interface AttributeValueEditorProps {
  attribute: SpacyAttribute;
  value: any;
  onChange: (value: any) => void;
  disabled?: boolean;
}

// Individual value editor based on attribute type
function AttributeValueEditor({ attribute, value, onChange, disabled }: AttributeValueEditorProps) {
  const [useINSyntax, setUseINSyntax] = useState(
    value && typeof value === 'object' && 'IN' in value
  );

  if (useINSyntax && attribute.supportsIN) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Match any of:</label>
          <button
            onClick={() => {
              setUseINSyntax(false);
              onChange(attribute.valueType === 'boolean' ? true : '');
            }}
            className="text-xs text-blue-600 hover:text-blue-800"
            disabled={disabled}
          >
            Switch to single value
          </button>
        </div>
        <ArrayValueEditor
          items={value?.IN || []}
          onChange={(items) => onChange({ IN: items })}
          disabled={disabled}
          attribute={attribute}
        />
      </div>
    );
  }

  switch (attribute.valueType) {
    case 'boolean':
      return (
        <div className="flex items-center gap-2">
          <select
            value={String(value)}
            onChange={(e) => onChange(e.target.value === 'true')}
            className="border rounded-lg px-2 py-1 text-sm"
            disabled={disabled}
          >
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
          {attribute.supportsIN && (
            <button
              onClick={() => {
                setUseINSyntax(true);
                onChange({ IN: [true, false] });
              }}
              className="text-xs text-blue-600 hover:text-blue-800"
              disabled={disabled}
            >
              Use list
            </button>
          )}
        </div>
      );

    case 'enum':
      return (
        <div className="space-y-2">
          <select
            value={String(value || '')}
            onChange={(e) => onChange(e.target.value)}
            className="w-full border rounded-lg px-2 py-1 text-sm"
            disabled={disabled}
          >
            <option value="">Select {attribute.label}</option>
            {attribute.enumValues?.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          {attribute.supportsIN && (
            <button
              onClick={() => {
                setUseINSyntax(true);
                onChange({ IN: [] });
              }}
              className="text-xs text-blue-600 hover:text-blue-800"
              disabled={disabled}
            >
              Select multiple
            </button>
          )}
        </div>
      );

    case 'number':
      return (
        <input
          type="number"
          value={value || ''}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full border rounded-lg px-2 py-1 text-sm"
          placeholder={`Enter ${attribute.label.toLowerCase()}`}
          disabled={disabled}
        />
      );

    case 'text':
    default:
      return (
        <div className="space-y-2">
          <input
            type="text"
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            className="w-full border rounded-lg px-2 py-1 text-sm"
            placeholder={`Enter ${attribute.label.toLowerCase()}`}
            disabled={disabled}
          />
          {attribute.supportsIN && (
            <button
              onClick={() => {
                setUseINSyntax(true);
                onChange({ IN: [] });
              }}
              className="text-xs text-blue-600 hover:text-blue-800"
              disabled={disabled}
            >
              Use list
            </button>
          )}
          {attribute.examples && (
            <div className="text-xs text-gray-500">
              Examples: {attribute.examples.join(', ')}
            </div>
          )}
        </div>
      );
  }
}

// Array editor for IN syntax
function ArrayValueEditor({ 
  items, 
  onChange, 
  disabled, 
  attribute 
}: { 
  items: any[]; 
  onChange: (items: any[]) => void; 
  disabled?: boolean;
  attribute: SpacyAttribute;
}) {
  const addItem = () => {
    const defaultValue = attribute.valueType === 'boolean' ? true : '';
    onChange([...items, defaultValue]);
  };

  const removeItem = (index: number) => {
    onChange(items.filter((_, i) => i !== index));
  };

  const updateItem = (index: number, value: any) => {
    const newItems = [...items];
    newItems[index] = value;
    onChange(newItems);
  };

  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={index} className="flex items-center gap-2">
          <div className="flex-1">
            {attribute.valueType === 'enum' ? (
              <select
                value={String(item || '')}
                onChange={(e) => updateItem(index, e.target.value)}
                className="w-full border rounded-lg px-2 py-1 text-sm"
                disabled={disabled}
              >
                <option value="">Select...</option>
                {attribute.enumValues?.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            ) : attribute.valueType === 'boolean' ? (
              <select
                value={String(item)}
                onChange={(e) => updateItem(index, e.target.value === 'true')}
                className="w-full border rounded-lg px-2 py-1 text-sm"
                disabled={disabled}
              >
                <option value="true">true</option>
                <option value="false">false</option>
              </select>
            ) : (
              <input
                type="text"
                value={item || ''}
                onChange={(e) => updateItem(index, e.target.value)}
                className="w-full border rounded-lg px-2 py-1 text-sm"
                disabled={disabled}
              />
            )}
          </div>
          <button
            onClick={() => removeItem(index)}
            className="p-1 text-red-600 hover:bg-red-50 rounded"
            disabled={disabled}
            title="Remove item"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      ))}
      <button
        onClick={addItem}
        className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
        disabled={disabled}
      >
        <Plus className="w-3 h-3" />
        Add value
      </button>
    </div>
  );
}

// Category section with collapsible attributes
function CategorySection({ 
  category, 
  attributes, 
  selectedAttributes, 
  onAddAttribute, 
  disabled 
}: {
  category: string;
  attributes: SpacyAttribute[];
  selectedAttributes: Set<string>;
  onAddAttribute: (key: string) => void;
  disabled?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const categoryInfo = ATTRIBUTE_CATEGORIES[category];
  
  const availableAttributes = attributes.filter(attr => !selectedAttributes.has(attr.key));
  
  if (availableAttributes.length === 0) {
    return null;
  }

  return (
    <div className="border rounded-lg">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-50"
        disabled={disabled}
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-500" />
          )}
          <span className={`w-3 h-3 rounded-full bg-${categoryInfo.color}-200`}></span>
          <span className="font-medium">{categoryInfo.label}</span>
          <span className="text-sm text-gray-500">({availableAttributes.length})</span>
        </div>
      </button>
      
      {isExpanded && (
        <div className="border-t p-3 space-y-2">
          <p className="text-sm text-gray-600 mb-3">{categoryInfo.description}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {availableAttributes.map((attr) => (
              <button
                key={attr.key}
                onClick={() => onAddAttribute(attr.key)}
                className="flex items-center gap-2 p-2 text-left border rounded-lg hover:bg-gray-50 text-sm"
                disabled={disabled}
                title={attr.description}
              >
                <Plus className="w-3 h-3 text-gray-400" />
                <span className="font-mono text-xs">{attr.key}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SpacyAttributeEditor({ 
  value, 
  onChange, 
  disabled = false 
}: SpacyAttributeEditorProps) {
  const [showAttributeSelector, setShowAttributeSelector] = useState(false);
  
  const currentAttributes = Object.keys(value || {});
  const selectedAttributeSet = new Set(currentAttributes);

  const addAttribute = (key: string) => {
    const attribute = getAttributeByKey(key);
    if (!attribute) return;

    let defaultValue: any;
    switch (attribute.valueType) {
      case 'boolean':
        defaultValue = true;
        break;
      case 'number':
        defaultValue = 0;
        break;
      default:
        defaultValue = '';
    }

    onChange({
      ...value,
      [key]: defaultValue
    });
    setShowAttributeSelector(false);
  };

  const removeAttribute = (key: string) => {
    const newValue = { ...value };
    delete newValue[key];
    onChange(newValue);
  };

  const updateAttributeValue = (key: string, newValue: any) => {
    onChange({
      ...value,
      [key]: newValue
    });
  };

  // Group attributes by category
  const groupedAttributes = SPACY_ATTRIBUTES.reduce((groups: Record<string, SpacyAttribute[]>, attr) => {
    if (!groups[attr.category]) {
      groups[attr.category] = [];
    }
    groups[attr.category].push(attr);
    return groups;
  }, {});

  return (
    <div className="space-y-4">
      {/* Current Attributes */}
      {currentAttributes.length > 0 && (
        <div className="space-y-3">
          {currentAttributes.map((key) => {
            const attribute = getAttributeByKey(key);
            if (!attribute) {
              // Fallback for unknown attributes
              return (
                <div key={key} className="flex items-center gap-3 p-3 border rounded-lg bg-yellow-50">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {key} (Custom)
                    </label>
                    <input
                      type="text"
                      value={JSON.stringify(value[key])}
                      onChange={(e) => {
                        try {
                          const parsed = JSON.parse(e.target.value);
                          updateAttributeValue(key, parsed);
                        } catch {
                          updateAttributeValue(key, e.target.value);
                        }
                      }}
                      className="w-full border rounded-lg px-2 py-1 text-sm"
                      disabled={disabled}
                    />
                  </div>
                  <button
                    onClick={() => removeAttribute(key)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                    disabled={disabled}
                    title="Remove attribute"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              );
            }

            const categoryColor = getCategoryColor(attribute.category);
            
            return (
              <div key={key} className="flex items-start gap-3 p-3 border rounded-lg">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`w-2 h-2 rounded-full bg-${categoryColor}-400`}></span>
                    <label className="text-sm font-medium text-gray-700">
                      {attribute.label}
                    </label>
                    <span className="text-xs font-mono text-gray-500 bg-gray-100 px-1 rounded">
                      {attribute.key}
                    </span>
                    <button
                      className="p-1 text-gray-400 hover:text-gray-600"
                      title={attribute.description}
                    >
                      <HelpCircle className="w-3 h-3" />
                    </button>
                  </div>
                  <AttributeValueEditor
                    attribute={attribute}
                    value={value[key]}
                    onChange={(newValue) => updateAttributeValue(key, newValue)}
                    disabled={disabled}
                  />
                </div>
                <button
                  onClick={() => removeAttribute(key)}
                  className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                  disabled={disabled}
                  title="Remove attribute"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Attribute Button */}
      {!showAttributeSelector && (
        <button
          onClick={() => setShowAttributeSelector(true)}
          className="flex items-center gap-2 px-3 py-2 border border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-gray-400 hover:text-gray-700 transition-colors w-full"
          disabled={disabled}
        >
          <Plus className="w-4 h-4" />
          Add attribute
        </button>
      )}

      {/* Attribute Selector */}
      {showAttributeSelector && (
        <div className="border rounded-lg p-4 bg-gray-50">
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-medium">Add spaCy Attribute</h4>
            <button
              onClick={() => setShowAttributeSelector(false)}
              className="text-gray-500 hover:text-gray-700"
              disabled={disabled}
            >
              Cancel
            </button>
          </div>
          
          <div className="space-y-3">
            {Object.entries(groupedAttributes).map(([category, attributes]) => (
              <CategorySection
                key={category}
                category={category}
                attributes={attributes}
                selectedAttributes={selectedAttributeSet}
                onAddAttribute={addAttribute}
                disabled={disabled}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
