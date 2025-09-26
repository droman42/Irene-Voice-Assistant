/**
 * ConfigurationStatus Component - Shows the status of configuration testing/application
 * 
 * Provides visual feedback for different configuration states during the live testing workflow
 */

import React from 'react';
import { CheckCircle, AlertCircle, Loader, Clock } from 'lucide-react';

export type ConfigurationStatusType = 'testing' | 'applied' | 'pending' | 'error';

interface ConfigurationStatusProps {
  status: ConfigurationStatusType;
  message: string;
  testResult?: any; // The configure response from the API
  className?: string;
}

export const ConfigurationStatus: React.FC<ConfigurationStatusProps> = ({
  status,
  message,
  testResult,
  className = ''
}) => {
  const getStatusConfig = () => {
    switch (status) {
      case 'testing':
        return {
          icon: <Loader className="h-4 w-4 animate-spin" />,
          bgColor: 'bg-blue-50',
          borderColor: 'border-blue-200',
          textColor: 'text-blue-800',
          iconColor: 'text-blue-600'
        };
      case 'applied':
        return {
          icon: <CheckCircle className="h-4 w-4" />,
          bgColor: 'bg-green-50',
          borderColor: 'border-green-200',
          textColor: 'text-green-800',
          iconColor: 'text-green-600'
        };
      case 'pending':
        return {
          icon: <Clock className="h-4 w-4" />,
          bgColor: 'bg-yellow-50',
          borderColor: 'border-yellow-200',
          textColor: 'text-yellow-800',
          iconColor: 'text-yellow-600'
        };
      case 'error':
        return {
          icon: <AlertCircle className="h-4 w-4" />,
          bgColor: 'bg-red-50',
          borderColor: 'border-red-200',
          textColor: 'text-red-800',
          iconColor: 'text-red-600'
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div className={`${config.bgColor} border ${config.borderColor} rounded-md p-3 ${className}`}>
      <div className="flex items-start">
        <div className={`${config.iconColor} mr-2 mt-0.5`}>
          {config.icon}
        </div>
        <div className="flex-1">
          <div className={`text-sm font-medium ${config.textColor}`}>
            {message}
          </div>
          {testResult && (
            <div className={`text-xs ${config.textColor} mt-1 opacity-75`}>
              {status === 'applied' && testResult.default_provider && (
                <div>Default provider: {testResult.default_provider}</div>
              )}
              {status === 'applied' && testResult.enabled_providers && (
                <div>Enabled providers: {testResult.enabled_providers.join(', ')}</div>
              )}
              {status === 'applied' && testResult.fallback_providers && testResult.fallback_providers.length > 0 && (
                <div>Fallback providers: {testResult.fallback_providers.join(', ')}</div>
              )}
              {status === 'applied' && testResult.language && (
                <div>Language: {testResult.language}</div>
              )}
              {status === 'applied' && testResult.confidence_threshold !== undefined && (
                <div>Confidence threshold: {testResult.confidence_threshold}</div>
              )}
              {status === 'applied' && testResult.wake_words && (
                <div>Wake words: {testResult.wake_words.join(', ')}</div>
              )}
              {status === 'applied' && testResult.enabled_handlers && (
                <div>Handlers: {testResult.enabled_handlers.length} enabled</div>
              )}
              {status === 'applied' && testResult.normalizers && (
                <div>Normalizers: {testResult.normalizers.join(', ')}</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ConfigurationStatus;
