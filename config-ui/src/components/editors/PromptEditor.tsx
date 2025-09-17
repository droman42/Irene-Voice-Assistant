/**
 * PromptEditor Component - Multi-section editor for prompt definitions
 * 
 * Provides structured editing for prompt YAML files with metadata support.
 * Handles prompt definitions with description, usage context, variables, and content.
 */

import { useState, useEffect } from 'react';
import { Plus, Eye, Code, Layout, MessageSquare } from 'lucide-react';
import PromptDefinitionEditor from './PromptDefinitionEditor';
import Section from '@/components/ui/Section';
import TextArea from '@/components/ui/TextArea';
import Badge from '@/components/ui/Badge';
import type { PromptDefinition } from '@/types/api';

interface PromptEditorProps {
  value: Record<string, PromptDefinition>;
  onChange: (value: Record<string, PromptDefinition>) => void;
  onValidationChange?: (isValid: boolean, errors: string[]) => void;
}

type ViewMode = 'structured' | 'yaml' | 'preview';

const PromptEditor: React.FC<PromptEditorProps> = ({
  value,
  onChange,
  onValidationChange
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('structured');
  const [yamlContent, setYamlContent] = useState('');
  const [yamlError, setYamlError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Convert prompt definitions to YAML string
  const promptsToYaml = (prompts: Record<string, PromptDefinition>): string => {
    const yamlLines: string[] = [];
    
    Object.entries(prompts).forEach(([promptName, prompt]) => {
      yamlLines.push(`${promptName}:`);
      yamlLines.push(`  description: "${prompt.description}"`);
      yamlLines.push(`  usage_context: "${prompt.usage_context}"`);
      yamlLines.push(`  prompt_type: "${prompt.prompt_type}"`);
      
      if (prompt.variables && prompt.variables.length > 0) {
        yamlLines.push(`  variables:`);
        prompt.variables.forEach(variable => {
          yamlLines.push(`    - name: "${variable.name}"`);
          yamlLines.push(`      description: "${variable.description}"`);
        });
      } else {
        yamlLines.push(`  variables: []`);
      }
      
      // Handle multiline content
      if (prompt.content.includes('\n')) {
        yamlLines.push(`  content: |`);
        prompt.content.split('\n').forEach(line => {
          yamlLines.push(`    ${line}`);
        });
      } else {
        yamlLines.push(`  content: "${prompt.content.replace(/"/g, '\\"')}"`);
      }
      yamlLines.push('');
    });

    return yamlLines.join('\n');
  };

  // Parse YAML string to prompt definitions (simple implementation)
  const yamlToPrompts = (yamlStr: string): Record<string, PromptDefinition> => {
    try {
      // This is a simplified YAML parser for prompt structure
      // In a real implementation, you'd use a proper YAML library
      const lines = yamlStr.split('\n');
      const prompts: Record<string, PromptDefinition> = {};
      let currentPrompt: string | null = null;
      let currentSection: string | null = null;
      let content: string[] = [];
      let variables: Array<{ name: string; description: string }> = [];
      let currentVariable: { name?: string; description?: string } = {};

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;

        // Main prompt name
        if (line.match(/^[a-zA-Z_][a-zA-Z0-9_]*:$/)) {
          if (currentPrompt) {
            // Save previous prompt
            prompts[currentPrompt] = {
              description: prompts[currentPrompt]?.description || '',
              usage_context: prompts[currentPrompt]?.usage_context || '',
              variables: variables,
              prompt_type: prompts[currentPrompt]?.prompt_type || 'system',
              content: content.join('\n')
            };
          }
          currentPrompt = line.replace(':', '');
          currentSection = null;
          content = [];
          variables = [];
          prompts[currentPrompt] = {
            description: '',
            usage_context: '',
            variables: [],
            prompt_type: 'system',
            content: ''
          };
          continue;
        }

        if (!currentPrompt) continue;

        // Handle sections
        if (line.match(/^\s+description:/)) {
          currentSection = 'description';
          const value = line.split('description:')[1]?.trim().replace(/^"|"$/g, '') || '';
          prompts[currentPrompt].description = value;
        } else if (line.match(/^\s+usage_context:/)) {
          currentSection = 'usage_context';
          const value = line.split('usage_context:')[1]?.trim().replace(/^"|"$/g, '') || '';
          prompts[currentPrompt].usage_context = value;
        } else if (line.match(/^\s+prompt_type:/)) {
          currentSection = 'prompt_type';
          const value = line.split('prompt_type:')[1]?.trim().replace(/^"|"$/g, '') || 'system';
          prompts[currentPrompt].prompt_type = value as 'system' | 'template' | 'user';
        } else if (line.match(/^\s+variables:/)) {
          currentSection = 'variables';
        } else if (line.match(/^\s+content:/)) {
          currentSection = 'content';
          const value = line.split('content:')[1]?.trim();
          if (value && !value.startsWith('|')) {
            content = [value.replace(/^"|"$/g, '')];
          }
        } else if (currentSection === 'content' && line.match(/^\s{4,}/)) {
          content.push(line.substring(4));
        } else if (currentSection === 'variables' && line.match(/^\s+- name:/)) {
          if (currentVariable.name) {
            variables.push(currentVariable as { name: string; description: string });
          }
          currentVariable = { name: line.split('name:')[1]?.trim().replace(/^"|"$/g, '') };
        } else if (currentSection === 'variables' && line.match(/^\s+description:/)) {
          currentVariable.description = line.split('description:')[1]?.trim().replace(/^"|"$/g, '') || '';
        }
      }

      // Save the last prompt
      if (currentPrompt) {
        if (currentVariable.name) {
          variables.push(currentVariable as { name: string; description: string });
        }
        prompts[currentPrompt] = {
          ...prompts[currentPrompt],
          variables: variables,
          content: content.join('\n')
        };
      }

      return prompts;
    } catch (error) {
      throw new Error(`YAML parsing error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Update YAML content when value changes (structured -> YAML)
  useEffect(() => {
    if (viewMode !== 'yaml') {
      setYamlContent(promptsToYaml(value));
    }
  }, [value, viewMode]);

  // Validate prompts
  useEffect(() => {
    const errors: string[] = [];
    
    Object.entries(value).forEach(([promptName, prompt]) => {
      if (!prompt.description) {
        errors.push(`${promptName}: Description is required`);
      }
      if (!prompt.usage_context) {
        errors.push(`${promptName}: Usage context is required`);
      }
      if (!prompt.content) {
        errors.push(`${promptName}: Content is required`);
      }
      if (prompt.variables) {
        prompt.variables.forEach((variable, index) => {
          if (!variable.name) {
            errors.push(`${promptName}: Variable ${index + 1} missing name`);
          }
        });
      }
    });
    
    setValidationErrors(errors);
    onValidationChange?.(errors.length === 0, errors);
  }, [value, onValidationChange]);

  const handleYamlChange = (newYaml: string) => {
    setYamlContent(newYaml);
    setYamlError(null);
    
    try {
      const parsed = yamlToPrompts(newYaml);
      onChange(parsed);
    } catch (error) {
      setYamlError(error instanceof Error ? error.message : 'Invalid YAML');
    }
  };

  const handlePromptChange = (promptName: string, promptData: PromptDefinition) => {
    onChange({
      ...value,
      [promptName]: promptData
    });
  };

  const handlePromptDelete = (promptName: string) => {
    const newValue = { ...value };
    delete newValue[promptName];
    onChange(newValue);
  };

  const addNewPrompt = () => {
    const newPromptName = prompt('Enter new prompt name:');
    if (newPromptName && !value[newPromptName]) {
      const newPrompt: PromptDefinition = {
        description: 'New prompt description',
        usage_context: 'Context where this prompt is used',
        variables: [],
        prompt_type: 'system',
        content: 'Prompt content goes here'
      };
      onChange({
        ...value,
        [newPromptName]: newPrompt
      });
    }
  };

  const renderStructuredView = () => (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-gray-900">Prompt Definitions</h3>
        <button
          type="button"
          onClick={addNewPrompt}
          className="flex items-center space-x-2 px-3 py-1 bg-yellow-600 text-white rounded-md hover:bg-yellow-700"
          title="Add a new prompt definition"
        >
          <Plus className="w-4 h-4" />
          <span>Add Prompt</span>
        </button>
      </div>
      
      {Object.keys(value).length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <MessageSquare className="w-8 h-8 mx-auto mb-2" />
          <p>No prompts defined. Click "Add Prompt" to create one.</p>
        </div>
      ) : (
        Object.entries(value).map(([promptName, promptData]) => (
          <PromptDefinitionEditor
            key={promptName}
            promptName={promptName}
            value={promptData}
            onChange={handlePromptChange}
            onDelete={handlePromptDelete}
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
      <h3 className="text-lg font-medium text-gray-900">Prompt Preview</h3>
      {Object.entries(value).map(([promptName, promptData]) => (
        <div key={promptName} className="bg-gray-50 rounded-lg p-4 border">
          <div className="flex items-center space-x-2 mb-2">
            <h4 className="font-medium text-gray-900">{promptName}</h4>
            <Badge variant={promptData.prompt_type === 'system' ? 'info' : promptData.prompt_type === 'template' ? 'warning' : 'default'}>
              {promptData.prompt_type}
            </Badge>
          </div>
          <p className="text-sm text-gray-600 mb-2">{promptData.description}</p>
          <p className="text-xs text-gray-500 mb-3">Context: {promptData.usage_context}</p>
          
          {promptData.variables.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-medium text-gray-700 mb-1">Variables:</p>
              <div className="flex flex-wrap gap-1">
                {promptData.variables.map((variable, idx) => (
                  <Badge key={idx} variant="default" className="text-xs">
                    {variable.name}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          
          <div className="bg-white rounded border p-3">
            <pre className="text-sm text-gray-800 whitespace-pre-wrap">{promptData.content}</pre>
          </div>
        </div>
      ))}
    </div>
  );

  return (
    <Section title="Prompt Editor">
      {/* View Mode Toggle */}
      <div className="flex space-x-2 mb-4">
        <button
          type="button"
          onClick={() => setViewMode('structured')}
          className={`flex items-center space-x-2 px-3 py-1 rounded-md ${
            viewMode === 'structured' 
              ? 'bg-blue-100 text-blue-700' 
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <Layout className="w-4 h-4" />
          <span>Structured</span>
        </button>
        <button
          type="button"
          onClick={() => setViewMode('yaml')}
          className={`flex items-center space-x-2 px-3 py-1 rounded-md ${
            viewMode === 'yaml' 
              ? 'bg-blue-100 text-blue-700' 
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <Code className="w-4 h-4" />
          <span>YAML</span>
        </button>
        <button
          type="button"
          onClick={() => setViewMode('preview')}
          className={`flex items-center space-x-2 px-3 py-1 rounded-md ${
            viewMode === 'preview' 
              ? 'bg-blue-100 text-blue-700' 
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <Eye className="w-4 h-4" />
          <span>Preview</span>
        </button>
      </div>

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 mb-4">
          <h4 className="text-sm font-medium text-red-800 mb-2">Validation Errors</h4>
          <ul className="text-sm text-red-700 space-y-1">
            {validationErrors.map((error, index) => (
              <li key={index}>• {error}</li>
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

export default PromptEditor;
