/**
 * ValidationErrorDisplay Component - Displays TOML validation errors
 * 
 * Phase 6 Feature: Professional error display for real-time TOML validation
 * with proper formatting and error categorization.
 */

import React from 'react';
import { AlertCircle, AlertTriangle, Info } from 'lucide-react';

interface ValidationError {
  msg: string;
  type: string;
  line?: number;
  column?: number;
}

interface ValidationErrorDisplayProps {
  errors: ValidationError[];
  className?: string;
}

export const ValidationErrorDisplay: React.FC<ValidationErrorDisplayProps> = ({
  errors,
  className = ""
}) => {
  if (errors.length === 0) {
    return null;
  }

  const getErrorIcon = (errorType: string) => {
    switch (errorType) {
      case 'syntax_error':
      case 'parse_error':
        return <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />;
      case 'validation_error':
        return <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />;
      case 'network_error':
        return <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />;
      default:
        return <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />;
    }
  };

  const getErrorStyle = (errorType: string) => {
    switch (errorType) {
      case 'syntax_error':
      case 'parse_error':
        return "bg-red-50 border-red-200";
      case 'validation_error':
        return "bg-amber-50 border-amber-200";
      case 'network_error':
        return "bg-blue-50 border-blue-200";
      default:
        return "bg-red-50 border-red-200";
    }
  };

  const getErrorTitle = (errorType: string) => {
    switch (errorType) {
      case 'syntax_error':
        return 'Syntax Error';
      case 'parse_error':
        return 'Parse Error';
      case 'validation_error':
        return 'Validation Error';
      case 'network_error':
        return 'Network Error';
      default:
        return 'Error';
    }
  };

  return (
    <div className={`mt-4 space-y-2 ${className}`}>
      <div className="flex items-center space-x-2">
        <h4 className="text-sm font-medium text-red-800">
          Validation Errors ({errors.length})
        </h4>
        <div className="text-xs text-gray-500">
          Fix these issues before saving
        </div>
      </div>
      
      {errors.map((error, index) => (
        <div 
          key={index}
          className={`p-3 border rounded-md text-sm ${getErrorStyle(error.type)}`}
        >
          <div className="flex items-start space-x-2">
            {getErrorIcon(error.type)}
            <div className="flex-1">
              <div className="font-medium text-gray-800">
                {getErrorTitle(error.type)}
                {error.line && error.column && (
                  <span className="ml-2 text-xs font-normal text-gray-600">
                    Line {error.line}, Column {error.column}
                  </span>
                )}
              </div>
              <div className="text-gray-700 mt-1">
                {error.msg}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default ValidationErrorDisplay;
