/**
 * PromptDefinitionEditor Component - Editor for individual prompt definitions
 * 
 * Handles prompt metadata, variables, and content editing with collapsible sections.
 */

import { useState } from 'react';
import { Trash2, Plus, ChevronDown, ChevronRight, MessageSquare } from 'lucide-react';
import Input from '@/components/ui/Input';
import TextArea from '@/components/ui/TextArea';
import Badge from '@/components/ui/Badge';
import type { PromptDefinition } from '@/types/api';

interface PromptDefinitionEditorProps {
  promptName: string;
  value: PromptDefinition;
  onChange: (promptName: string, value: PromptDefinition) => void;
  onDelete: (promptName: string) => void;
}

interface PromptVariable {
  name: string;
  description: string;
}

const PromptDefinitionEditor: React.FC<PromptDefinitionEditorProps> = ({
  promptName,
  value,
  onChange,
  onDelete
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const handleFieldChange = (field: keyof PromptDefinition, newValue: any) => {
    onChange(promptName, {
      ...value,
      [field]: newValue
    });
  };

  const handleVariableChange = (index: number, field: keyof PromptVariable, newValue: string) => {
    const newVariables = [...value.variables];
    newVariables[index] = {
      ...newVariables[index],
      [field]: newValue
    };
    handleFieldChange('variables', newVariables);
  };

  const addVariable = () => {
    const newVariable: PromptVariable = {
      name: '',
      description: ''
    };
    handleFieldChange('variables', [...value.variables, newVariable]);
  };

  const removeVariable = (index: number) => {
    const newVariables = value.variables.filter((_, i) => i !== index);
    handleFieldChange('variables', newVariables);
  };

  const handleDelete = () => {
    if (confirm(`Are you sure you want to delete the prompt "${promptName}"?`)) {
      onDelete(promptName);
    }
  };

  const getPromptTypeColor = (type: string) => {
    switch (type) {
      case 'system': return 'info';
      case 'template': return 'warning';
      case 'user': return 'default';
      default: return 'default';
    }
  };

  return (
    <div className="border border-gray-200 rounded-lg bg-white">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center space-x-3">
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-gray-400 hover:text-gray-600"
          >
            {isExpanded ? (
              <ChevronDown className="w-5 h-5" />
            ) : (
              <ChevronRight className="w-5 h-5" />
            )}
          </button>
          <MessageSquare className="w-5 h-5 text-blue-500" />
          <div className="flex items-center space-x-2">
            <h3 className="text-lg font-medium text-gray-900">{promptName}</h3>
            <Badge variant={getPromptTypeColor(value.prompt_type)}>
              {value.prompt_type}
            </Badge>
          </div>
        </div>
        <button
          type="button"
          onClick={handleDelete}
          className="text-red-600 hover:text-red-800"
          title={`Delete prompt "${promptName}"`}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="p-4 space-y-4">
          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description *
            </label>
            <Input
              value={value.description}
              onChange={(newValue) => handleFieldChange('description', newValue)}
              placeholder="Brief description of this prompt"
            />
          </div>

          {/* Usage Context */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Usage Context *
            </label>
            <Input
              value={value.usage_context}
              onChange={(newValue) => handleFieldChange('usage_context', newValue)}
              placeholder="When and how this prompt is used"
            />
          </div>

          {/* Prompt Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Prompt Type *
            </label>
            <select
              value={value.prompt_type}
              onChange={(e) => handleFieldChange('prompt_type', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="system">System</option>
              <option value="template">Template</option>
              <option value="user">User</option>
            </select>
            <p className="mt-1 text-xs text-gray-500">
              {value.prompt_type === 'system' && 'System prompts set the AI\'s role and behavior'}
              {value.prompt_type === 'template' && 'Template prompts are filled with variables'}
              {value.prompt_type === 'user' && 'User prompts simulate user input'}
            </p>
          </div>

          {/* Variables */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Variables
              </label>
              <button
                type="button"
                onClick={addVariable}
                className="flex items-center space-x-1 px-2 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                <Plus className="w-3 h-3" />
                <span>Add Variable</span>
              </button>
            </div>
            
            {value.variables.length === 0 ? (
              <div className="text-center py-4 text-gray-500 border-2 border-dashed border-gray-200 rounded-md">
                <p className="text-sm">No variables defined</p>
                <p className="text-xs">Variables can be referenced in the prompt content using {'{variable_name}'}</p>
              </div>
            ) : (
              <div className="space-y-2">
                {value.variables.map((variable, index) => (
                  <div key={index} className="flex items-start space-x-2 p-3 bg-gray-50 rounded-md">
                    <div className="flex-1 space-y-2">
                      <Input
                        value={variable.name}
                        onChange={(newValue) => handleVariableChange(index, 'name', newValue)}
                        placeholder="Variable name (e.g., user_input)"
                      />
                      <Input
                        value={variable.description}
                        onChange={(newValue) => handleVariableChange(index, 'description', newValue)}
                        placeholder="Description of this variable"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => removeVariable(index)}
                      className="text-red-600 hover:text-red-800 mt-1"
                      title="Remove variable"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Content */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Content *
            </label>
            <TextArea
              value={value.content}
              onChange={(newValue) => handleFieldChange('content', newValue)}
              placeholder="Enter the prompt content here..."
              rows={6}
            />
            <div className="mt-1 text-xs text-gray-500">
              <p>You can reference variables using curly braces: {'{variable_name}'}</p>
              {value.variables.length > 0 && (
                <p>Available variables: {value.variables.map(v => `{${v.name}}`).join(', ')}</p>
              )}
            </div>
          </div>

          {/* Preview */}
          {value.content && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Preview
              </label>
              <div className="bg-gray-50 border rounded-md p-3">
                <pre className="text-sm text-gray-800 whitespace-pre-wrap">{value.content}</pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PromptDefinitionEditor;
