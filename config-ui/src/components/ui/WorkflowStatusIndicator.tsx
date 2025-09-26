/**
 * WorkflowStatusIndicator Component - Shows the current state in the Test → Validate → Persist workflow
 * 
 * Provides visual indicators for configuration workflow states in Phase 4.3
 */

import React from 'react';
import { CheckCircle, TestTube, Save, AlertTriangle, Clock, FileText } from 'lucide-react';

export type WorkflowStateType = 'pristine' | 'edited' | 'tested' | 'persisted' | 'conflict';

interface WorkflowStatus {
  hasChanges: boolean;
  isTested: boolean;
  isPersisted: boolean;
  hasConflicts: boolean;
  canTest: boolean;
  canPersist: boolean;
  testStatus: 'idle' | 'testing' | 'applied' | 'error';
}

interface WorkflowStatusIndicatorProps {
  status: WorkflowStatus;
  stateType: WorkflowStateType;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  showDetails?: boolean;
}

export const WorkflowStatusIndicator: React.FC<WorkflowStatusIndicatorProps> = ({
  status,
  stateType,
  className = '',
  size = 'md',
  showDetails = false
}) => {
  const getStateConfig = () => {
    switch (stateType) {
      case 'pristine':
        return {
          icon: <FileText className={getIconSize()} />,
          bgColor: 'bg-gray-50',
          borderColor: 'border-gray-200',
          textColor: 'text-gray-600',
          iconColor: 'text-gray-400',
          label: 'Pristine',
          description: 'No changes made'
        };
      case 'edited':
        return {
          icon: <Clock className={getIconSize()} />,
          bgColor: 'bg-orange-50',
          borderColor: 'border-orange-200',
          textColor: 'text-orange-800',
          iconColor: 'text-orange-600',
          label: 'Edited',
          description: 'Changes pending test'
        };
      case 'tested':
        return {
          icon: <TestTube className={getIconSize()} />,
          bgColor: 'bg-blue-50',
          borderColor: 'border-blue-200',
          textColor: 'text-blue-800',
          iconColor: 'text-blue-600',
          label: 'Tested',
          description: 'Ready to persist'
        };
      case 'persisted':
        return {
          icon: <CheckCircle className={getIconSize()} />,
          bgColor: 'bg-green-50',
          borderColor: 'border-green-200',
          textColor: 'text-green-800',
          iconColor: 'text-green-600',
          label: 'Persisted',
          description: 'Saved to TOML'
        };
      case 'conflict':
        return {
          icon: <AlertTriangle className={getIconSize()} />,
          bgColor: 'bg-red-50',
          borderColor: 'border-red-200',
          textColor: 'text-red-800',
          iconColor: 'text-red-600',
          label: 'Conflict',
          description: 'Runtime/TOML mismatch'
        };
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

  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return 'px-2 py-1 text-xs';
      case 'md':
        return 'px-3 py-1.5 text-sm';
      case 'lg':
        return 'px-4 py-2 text-base';
    }
  };

  const config = getStateConfig();

  const getWorkflowSteps = () => {
    const steps = [
      {
        name: 'Edit',
        completed: status.hasChanges,
        active: status.hasChanges && !status.isTested,
        icon: <Clock className="h-3 w-3" />
      },
      {
        name: 'Test',
        completed: status.isTested,
        active: status.isTested && !status.isPersisted,
        icon: <TestTube className="h-3 w-3" />
      },
      {
        name: 'Persist',
        completed: status.isPersisted && status.isTested,
        active: false,
        icon: <Save className="h-3 w-3" />
      }
    ];

    return steps;
  };

  return (
    <div className={`inline-flex items-center ${getSizeClasses()} ${config.bgColor} border ${config.borderColor} rounded-md ${className}`}>
      <div className={`${config.iconColor} mr-2`}>
        {config.icon}
      </div>
      <div className="flex flex-col">
        <span className={`font-medium ${config.textColor}`}>
          {config.label}
        </span>
        {showDetails && (
          <div className="mt-1">
            <span className={`text-xs ${config.textColor} opacity-75`}>
              {config.description}
            </span>
            {/* Workflow progress steps */}
            <div className="flex items-center mt-1 space-x-1">
              {getWorkflowSteps().map((step, index) => (
                <div key={step.name} className="flex items-center">
                  <div
                    className={`
                      flex items-center justify-center w-4 h-4 rounded-full text-xs
                      ${step.completed 
                        ? 'bg-green-100 text-green-600 border border-green-200' 
                        : step.active
                        ? 'bg-blue-100 text-blue-600 border border-blue-200'
                        : 'bg-gray-100 text-gray-400 border border-gray-200'
                      }
                    `}
                    title={`${step.name} ${step.completed ? 'completed' : step.active ? 'active' : 'pending'}`}
                  >
                    {step.icon}
                  </div>
                  {index < getWorkflowSteps().length - 1 && (
                    <div 
                      className={`w-2 h-0.5 mx-0.5 ${
                        step.completed ? 'bg-green-300' : 'bg-gray-200'
                      }`} 
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default WorkflowStatusIndicator;
