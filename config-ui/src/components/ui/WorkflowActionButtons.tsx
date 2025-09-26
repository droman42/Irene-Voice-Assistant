/**
 * WorkflowActionButtons Component - Action buttons for the Test → Validate → Persist workflow
 * 
 * Provides persist and rollback functionality for Phase 4.3 workflow integration
 */

import React from 'react';
import { Save, RotateCcw, AlertTriangle, Loader } from 'lucide-react';
import { ComponentName } from './TestConfigButton';

interface WorkflowStatus {
  hasChanges: boolean;
  isTested: boolean;
  isPersisted: boolean;
  hasConflicts: boolean;
  canTest: boolean;
  canPersist: boolean;
  testStatus: 'idle' | 'testing' | 'applied' | 'error';
}

interface WorkflowActionButtonsProps {
  component: ComponentName;
  status: WorkflowStatus;
  onPersistTested: (component: ComponentName) => Promise<void>;
  onRollbackToPersisted: (component: ComponentName) => void;
  onRollbackToTested: (component: ComponentName) => void;
  loading?: boolean;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const WorkflowActionButtons: React.FC<WorkflowActionButtonsProps> = ({
  component,
  status,
  onPersistTested,
  onRollbackToPersisted,
  onRollbackToTested,
  loading = false,
  className = '',
  size = 'sm'
}) => {
  const [persisting, setPersisting] = React.useState(false);

  const handlePersist = async () => {
    if (persisting || loading) return;
    
    setPersisting(true);
    try {
      await onPersistTested(component);
    } catch (error) {
      console.error(`Failed to persist ${component} configuration:`, error);
    } finally {
      setPersisting(false);
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

  const getIconSize = () => {
    switch (size) {
      case 'sm':
        return 'h-3 w-3';
      case 'md':
        return 'h-4 w-4';
      case 'lg':
        return 'h-5 w-5';
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

  return (
    <div className={`flex items-center space-x-1 ${className}`}>
      {/* Persist to TOML Button */}
      {status.canPersist && (
        <button
          onClick={handlePersist}
          disabled={persisting || loading || !status.canPersist}
          className={`
            inline-flex items-center justify-center
            font-medium rounded-md transition-colors duration-200
            ${getSizeClasses()}
            ${persisting || loading
              ? 'bg-green-300 text-white cursor-not-allowed'
              : 'bg-green-600 text-white hover:bg-green-700 active:bg-green-800'
            }
          `}
          title={`Persist tested ${getComponentDisplayName()} configuration to TOML`}
        >
          {persisting ? (
            <Loader className={`${getIconSize()} animate-spin mr-1`} />
          ) : (
            <Save className={`${getIconSize()} mr-1`} />
          )}
          {persisting ? 'Persisting...' : 'Persist to TOML'}
        </button>
      )}

      {/* Rollback Buttons */}
      <div className="flex items-center space-x-1">
        {/* Rollback to Tested */}
        {status.hasChanges && status.isTested && (
          <button
            onClick={() => onRollbackToTested(component)}
            disabled={loading}
            className={`
              inline-flex items-center justify-center
              font-medium rounded-md transition-colors duration-200
              border border-blue-600 text-blue-600 hover:bg-blue-50 active:bg-blue-100
              ${getSizeClasses()}
              ${loading ? 'opacity-50 cursor-not-allowed' : ''}
            `}
            title={`Rollback ${getComponentDisplayName()} to last tested configuration`}
          >
            <RotateCcw className={`${getIconSize()} mr-1`} />
            Rollback to Tested
          </button>
        )}

        {/* Rollback to Persisted */}
        {(status.hasChanges || status.isTested) && !status.isPersisted && (
          <button
            onClick={() => onRollbackToPersisted(component)}
            disabled={loading}
            className={`
              inline-flex items-center justify-center
              font-medium rounded-md transition-colors duration-200
              border border-gray-600 text-gray-600 hover:bg-gray-50 active:bg-gray-100
              ${getSizeClasses()}
              ${loading ? 'opacity-50 cursor-not-allowed' : ''}
            `}
            title={`Rollback ${getComponentDisplayName()} to last persisted (TOML) configuration`}
          >
            <RotateCcw className={`${getIconSize()} mr-1`} />
            Rollback to TOML
          </button>
        )}
      </div>

      {/* Conflict Indicator */}
      {status.hasConflicts && (
        <div 
          className={`
            inline-flex items-center justify-center
            font-medium rounded-md
            bg-red-50 border border-red-200 text-red-600
            ${getSizeClasses()}
          `}
          title={`${getComponentDisplayName()} has conflicts between runtime and TOML configuration`}
        >
          <AlertTriangle className={`${getIconSize()} mr-1`} />
          Conflict
        </div>
      )}
    </div>
  );
};

export default WorkflowActionButtons;
