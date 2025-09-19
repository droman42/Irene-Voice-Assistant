/**
 * TomlPreview Component - Live TOML configuration preview
 * 
 * Displays a formatted preview of the current configuration in TOML format
 * with syntax highlighting and the ability to copy to clipboard.
 */

import React, { useState, useMemo } from 'react';
import { Copy, CheckCircle, Eye, EyeOff } from 'lucide-react';

interface TomlPreviewProps {
  config: any;
  className?: string;
}

export const TomlPreview: React.FC<TomlPreviewProps> = ({ 
  config, 
  className = "" 
}) => {
  const [copied, setCopied] = useState(false);
  const [showSensitive, setShowSensitive] = useState(false);
  
  // Convert configuration to TOML format
  const tomlContent = useMemo(() => {
    return convertToToml(config, showSensitive);
  }, [config, showSensitive]);
  
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(tomlContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
    }
  };
  
  const toggleSensitive = () => {
    setShowSensitive(!showSensitive);
  };
  
  return (
    <div className={`bg-white border border-gray-200 rounded-lg ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">TOML Preview</h3>
        <div className="flex items-center space-x-2">
          <button
            onClick={toggleSensitive}
            className="p-2 text-gray-500 hover:text-gray-700 rounded-md hover:bg-gray-100"
            title={showSensitive ? "Hide sensitive values" : "Show sensitive values"}
          >
            {showSensitive ? (
              <EyeOff className="h-4 w-4" />
            ) : (
              <Eye className="h-4 w-4" />
            )}
          </button>
          <button
            onClick={handleCopy}
            className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:text-gray-900 rounded-md hover:bg-gray-100"
            disabled={copied}
          >
            {copied ? (
              <>
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span>Copied!</span>
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>
      
      {/* Content */}
      <div className="p-4">
        <pre className="bg-gray-50 rounded-md p-4 overflow-auto text-sm font-mono max-h-96">
          <code className="text-gray-800">{tomlContent}</code>
        </pre>
      </div>
    </div>
  );
};

// ============================================================
// TOML CONVERSION UTILITIES
// ============================================================

function convertToToml(obj: any, showSensitive: boolean = false, depth: number = 0): string {
  if (!obj || typeof obj !== 'object') {
    return '';
  }
  
  const lines: string[] = [];
  const indent = '  '.repeat(depth);
  
  // Sort keys to ensure consistent output
  const sortedKeys = Object.keys(obj).sort();
  
  for (const key of sortedKeys) {
    const value = obj[key];
    
    if (value === null || value === undefined) {
      continue; // Skip null/undefined values
    }
    
    if (typeof value === 'object' && !Array.isArray(value)) {
      // Nested object - create section
      if (depth === 0) {
        lines.push(`\n[${key}]`);
        lines.push(convertToToml(value, showSensitive, depth + 1));
      } else {
        lines.push(`\n${indent}[${key}]`);
        lines.push(convertToToml(value, showSensitive, depth + 1));
      }
    } else {
      // Simple value
      const formattedValue = formatTomlValue(value, showSensitive);
      lines.push(`${indent}${key} = ${formattedValue}`);
    }
  }
  
  return lines.filter(line => line.trim()).join('\n');
}

function formatTomlValue(value: any, showSensitive: boolean): string {
  if (typeof value === 'string') {
    // Check if it's an environment variable
    if (value.startsWith('${') && value.endsWith('}')) {
      return `"${value}"`; // Keep env vars as-is
    }
    
    // Check if it looks like a sensitive value
    if (!showSensitive && isSensitiveValue(value)) {
      return '"***HIDDEN***"';
    }
    
    // Regular string
    return `"${value.replace(/"/g, '\\"')}"`;
  }
  
  if (typeof value === 'number') {
    return value.toString();
  }
  
  if (typeof value === 'boolean') {
    return value.toString();
  }
  
  if (Array.isArray(value)) {
    const items = value.map(item => formatTomlValue(item, showSensitive));
    return `[${items.join(', ')}]`;
  }
  
  return `"${String(value)}"`;
}

function isSensitiveValue(value: string): boolean {
  if (!value || typeof value !== 'string') {
    return false;
  }
  
  // Environment variables are not considered sensitive for display purposes
  if (value.startsWith('${') && value.endsWith('}')) {
    return false;
  }
  
  // Patterns for detecting sensitive values
  // const sensitivePatterns = [
  //   /key/i,
  //   /token/i,
  //   /secret/i,
  //   /password/i,
  //   /auth/i
  // ];
  
  // Check if the value looks like an API key, token, etc.
  const looksLikeKey = value.length > 20 && /^[a-zA-Z0-9+/=_-]+$/.test(value);
  
  return looksLikeKey;
}

export default TomlPreview;
