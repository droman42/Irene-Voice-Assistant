/**
 * TestConfigButton Component - Button for testing configuration via /configure endpoints
 * 
 * Handles live configuration testing for all 8 voice assistant components
 */

import React from 'react';
import { TestTube, Loader } from 'lucide-react';
import type { 
  TTSConfig, ASRConfig, AudioConfig, LLMConfig, NLUConfig, 
  VoiceTriggerConfig, TextProcessorConfig, IntentSystemConfig,
  TTSConfigureResponse, ASRConfigureResponse, AudioConfigureResponse, 
  LLMConfigureResponse, NLUConfigureResponse, VoiceTriggerConfigureResponse,
  TextProcessorConfigureResponse, IntentSystemConfigureResponse
} from '@/types/api';

// Union types for all config types and responses
export type ComponentConfigType = 
  | TTSConfig 
  | ASRConfig 
  | AudioConfig 
  | LLMConfig 
  | NLUConfig 
  | VoiceTriggerConfig 
  | TextProcessorConfig 
  | IntentSystemConfig;

export type ComponentConfigureResponse = 
  | TTSConfigureResponse 
  | ASRConfigureResponse 
  | AudioConfigureResponse 
  | LLMConfigureResponse 
  | NLUConfigureResponse 
  | VoiceTriggerConfigureResponse
  | TextProcessorConfigureResponse 
  | IntentSystemConfigureResponse;

export type ComponentName = 
  | 'tts' 
  | 'asr' 
  | 'audio' 
  | 'llm' 
  | 'nlu' 
  | 'voice_trigger' 
  | 'text_processing' 
  | 'intent_system';

interface TestConfigButtonProps {
  component: ComponentName;
  config: ComponentConfigType;
  onTest: (component: ComponentName, config: ComponentConfigType) => Promise<ComponentConfigureResponse>;
  loading?: boolean;
  disabled?: boolean;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'primary' | 'secondary' | 'outline';
  showPreview?: boolean; // Show preview of what will be applied
  hasChanges?: boolean; // Whether there are changes to test
}

export const TestConfigButton: React.FC<TestConfigButtonProps> = ({
  component,
  config,
  onTest,
  loading = false,
  disabled = false,
  className = '',
  size = 'md',
  variant = 'outline',
  showPreview = false,
  hasChanges = true
}) => {
  const handleClick = async () => {
    if (disabled || loading) return;
    
    try {
      await onTest(component, config);
    } catch (error) {
      console.error(`Failed to test ${component} configuration:`, error);
    }
  };

  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return 'px-2 py-1 text-xs';
      case 'md':
        return 'px-3 py-2 text-sm';
      case 'lg':
        return 'px-4 py-3 text-base';
    }
  };

  const getVariantClasses = () => {
    const isDisabled = disabled || loading;
    const noChanges = disabled && !hasChanges;
    
    switch (variant) {
      case 'primary':
        return isDisabled 
          ? 'bg-blue-300 text-white cursor-not-allowed'
          : 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800';
      case 'secondary':
        return isDisabled
          ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
          : 'bg-gray-600 text-white hover:bg-gray-700 active:bg-gray-800';
      case 'outline':
        if (noChanges) {
          return 'border border-gray-200 text-gray-400 cursor-not-allowed bg-gray-50';
        }
        return isDisabled
          ? 'border border-gray-300 text-gray-400 cursor-not-allowed'
          : 'border border-blue-600 text-blue-600 hover:bg-blue-50 active:bg-blue-100';
    }
  };

  const getComponentDisplayName = () => {
    const names: Record<ComponentName, string> = {
      tts: 'TTS',
      asr: 'ASR',
      audio: 'Audio',
      llm: 'LLM',
      nlu: 'NLU',
      voice_trigger: 'Voice Trigger',
      text_processing: 'Text Processing',
      intent_system: 'Intent System'
    };
    return names[component];
  };

  const getPreviewText = () => {
    if (!showPreview || !config) return '';
    
    const preview: string[] = [];
    
    // Add key configuration details based on component type
    if ('enabled' in config) {
      preview.push(`Enabled: ${config.enabled}`);
    }
    if ('default_provider' in config && config.default_provider) {
      preview.push(`Provider: ${config.default_provider}`);
    }
    if ('fallback_providers' in config && config.fallback_providers && config.fallback_providers.length > 0) {
      preview.push(`Fallbacks: ${config.fallback_providers.join(', ')}`);
    }
    
    return preview.length > 0 ? `\n\nWill apply:\n${preview.join('\n')}` : '';
  };

  return (
    <button
      onClick={handleClick}
      disabled={disabled || loading}
      className={`
        inline-flex items-center justify-center
        font-medium rounded-md transition-colors duration-200
        ${getSizeClasses()}
        ${getVariantClasses()}
        ${className}
      `}
      title={
        disabled && !hasChanges 
          ? `No changes to test for ${getComponentDisplayName()}`
          : `Test ${getComponentDisplayName()} configuration${getPreviewText()}`
      }
    >
      {loading ? (
        <Loader className={`${size === 'sm' ? 'h-3 w-3' : size === 'lg' ? 'h-5 w-5' : 'h-4 w-4'} animate-spin mr-2`} />
      ) : (
        <TestTube className={`${size === 'sm' ? 'h-3 w-3' : size === 'lg' ? 'h-5 w-5' : 'h-4 w-4'} mr-2`} />
      )}
      {loading ? 'Testing...' : disabled && !hasChanges ? 'No Changes' : 'Test Config'}
    </button>
  );
};

export default TestConfigButton;
