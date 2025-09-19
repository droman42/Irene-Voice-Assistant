/**
 * TomlPreview Component - Live TOML configuration preview with comment preservation
 * 
 * Phase 6 Enhanced Features:
 * - Syntax highlighting with react-syntax-highlighter
 * - Real-time TOML validation with error display
 * - Diff viewer for configuration changes
 * - Comment preservation using Phase 4/5 backend APIs
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Copy, CheckCircle, Eye, EyeOff, RefreshCw, AlertCircle, GitCompare, Code, Settings } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { DiffEditor } from '@monaco-editor/react';
import DiffViewer from './DiffViewer';
import ValidationErrorDisplay from './ValidationErrorDisplay';
import apiClient from '@/utils/apiClient';

interface TomlPreviewProps {
  config: any;
  className?: string;
  showDiff?: boolean;
  originalConfig?: any; // For diff comparison
}

interface TomlError {
  msg: string;
  type: string;
  line?: number;
  column?: number;
}

type ViewMode = 'preview' | 'diff' | 'editor';
type ThemeMode = 'light' | 'dark';

export const TomlPreview: React.FC<TomlPreviewProps> = ({ 
  config, 
  className = ""
  // showDiff and originalConfig reserved for future enhancement
}) => {
  // Existing state
  const [copied, setCopied] = useState(false);
  const [showSensitive, setShowSensitive] = useState(false);
  const [rawToml, setRawToml] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  
  // Phase 6: New state for advanced features
  const [viewMode, setViewMode] = useState<ViewMode>('preview');
  const [themeMode, setThemeMode] = useState<ThemeMode>('light');
  const [syntaxHighlighting, setSyntaxHighlighting] = useState(true);
  const [tomlErrors, setTomlErrors] = useState<TomlError[]>([]);
  const [validating, setValidating] = useState(false);
  const [originalToml, setOriginalToml] = useState(''); // For diff comparison
  const [validationDebounceTimer, setValidationDebounceTimer] = useState<NodeJS.Timeout | null>(null);
  
  // Phase 6: Real-time TOML validation with debouncing
  const validateTomlLive = useCallback(async (content: string) => {
    if (!content.trim()) {
      setTomlErrors([]);
      return;
    }
    
    setValidating(true);
    try {
      const result = await apiClient.validateRawToml(content);
      if (result.valid) {
        setTomlErrors([]);
      } else {
        // Convert validation errors to TomlError format
        const errors: TomlError[] = (result.errors || []).map(error => ({
          msg: error.msg || 'Unknown validation error',
          type: error.type || 'validation_error',
          // Extract line/column from loc array if available
          line: error.loc && error.loc.length > 0 ? Number(error.loc[0]) : undefined,
          column: error.loc && error.loc.length > 1 ? Number(error.loc[1]) : undefined
        }));
        setTomlErrors(errors);
      }
    } catch (error) {
      console.error('TOML validation failed:', error);
      setTomlErrors([{ 
        msg: 'Validation service temporarily unavailable', 
        type: 'network_error' 
      }]);
    } finally {
      setValidating(false);
    }
  }, []);
  
  // Debounced validation function
  const scheduleValidation = useCallback((content: string) => {
    // Clear existing timer
    if (validationDebounceTimer) {
      clearTimeout(validationDebounceTimer);
    }
    
    // Schedule new validation after 500ms delay
    const timer = setTimeout(() => {
      validateTomlLive(content);
    }, 500);
    
    setValidationDebounceTimer(timer);
  }, [validateTomlLive, validationDebounceTimer]);
  
  // Load raw TOML content from backend with comments preserved
  const loadRawToml = async (skipValidation = false) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await apiClient.getRawToml();
      const content = response.toml_content;
      
      // Store original content for diff comparison
      if (!originalToml) {
        setOriginalToml(content);
      }
      
      // Apply sensitive value masking if needed
      const processedContent = showSensitive ? content : maskSensitiveValues(content);
      setRawToml(processedContent);
      setLastUpdated(new Date());
      
      // Phase 6: Trigger validation if not skipped
      if (!skipValidation) {
        scheduleValidation(content);
      }
    } catch (err) {
      console.error('Failed to load raw TOML:', err);
      setError('Failed to load TOML preview. Using fallback rendering.');
      // Fallback to generating from config object
      const fallbackContent = generateFallbackToml(config, showSensitive);
      setRawToml(fallbackContent);
      // Don't validate fallback content
    } finally {
      setLoading(false);
    }
  };
  
  // Phase 6: Theme selection for syntax highlighting
  const syntaxTheme = useMemo(() => {
    return themeMode === 'dark' ? oneDark : oneLight;
  }, [themeMode]);
  
  // Load TOML when component mounts or config changes
  useEffect(() => {
    loadRawToml();
  }, [config]); // Re-load when config changes
  
  // Update display when showSensitive changes (without re-fetching)
  useEffect(() => {
    if (rawToml) {
      // Re-process the existing content for sensitive value masking
      loadRawToml();
    }
  }, [showSensitive]);
  
  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (validationDebounceTimer) {
        clearTimeout(validationDebounceTimer);
      }
    };
  }, [validationDebounceTimer]);
  
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(rawToml);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
    }
  };
  
  const toggleSensitive = () => {
    setShowSensitive(!showSensitive);
  };
  
  const handleRefresh = () => {
    loadRawToml();
  };
  
  // Phase 6: New event handlers
  const handleViewModeChange = (newMode: ViewMode) => {
    setViewMode(newMode);
  };
  
  const toggleTheme = () => {
    setThemeMode(prev => prev === 'light' ? 'dark' : 'light');
  };
  
  const toggleSyntaxHighlighting = () => {
    setSyntaxHighlighting(prev => !prev);
  };
  
  // Removed handleValidateNow - validation is automatic via debouncing
  
  return (
    <div className={`bg-white border border-gray-200 rounded-lg ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <h3 className="text-lg font-medium text-gray-900">TOML Preview</h3>
          {lastUpdated && (
            <span className="text-xs text-gray-500">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          {/* Phase 6: Validation status indicator */}
          {validating && (
            <div className="flex items-center space-x-1 text-blue-600">
              <RefreshCw className="h-3 w-3 animate-spin" />
              <span className="text-xs">Validating...</span>
            </div>
          )}
          {tomlErrors.length > 0 && (
            <div className="flex items-center space-x-1 text-red-600" title={`${tomlErrors.length} validation error(s)`}>
              <AlertCircle className="h-4 w-4" />
              <span className="text-xs">{tomlErrors.length} error(s)</span>
            </div>
          )}
          {!validating && tomlErrors.length === 0 && rawToml && (
            <div className="flex items-center space-x-1 text-green-600" title="TOML is valid">
              <CheckCircle className="h-3 w-3" />
              <span className="text-xs">Valid</span>
            </div>
          )}
        </div>
        
        {/* Phase 6: Enhanced toolbar with view mode controls */}
        <div className="flex items-center space-x-1">
          {/* View mode toggle */}
          <div className="flex border border-gray-300 rounded-md">
            <button
              onClick={() => handleViewModeChange('preview')}
              className={`px-2 py-1 text-xs rounded-l-md ${
                viewMode === 'preview' 
                  ? 'bg-blue-500 text-white' 
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
              title="Preview mode"
            >
              <Code className="h-3 w-3" />
            </button>
            {originalToml && (
              <button
                onClick={() => handleViewModeChange('diff')}
                className={`px-2 py-1 text-xs border-l border-gray-300 ${
                  viewMode === 'diff' 
                    ? 'bg-blue-500 text-white' 
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
                title="Diff view"
              >
                <GitCompare className="h-3 w-3" />
              </button>
            )}
            <button
              onClick={() => handleViewModeChange('editor')}
              className={`px-2 py-1 text-xs rounded-r-md border-l border-gray-300 ${
                viewMode === 'editor' 
                  ? 'bg-blue-500 text-white' 
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
              title="Advanced editor"
            >
              <Settings className="h-3 w-3" />
            </button>
          </div>
          
          {error && (
            <div className="flex items-center space-x-1 text-amber-600" title={error}>
              <AlertCircle className="h-4 w-4" />
              <span className="text-xs">Fallback</span>
            </div>
          )}
          
          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 text-gray-500 hover:text-gray-700 rounded-md hover:bg-gray-100"
            title={`Switch to ${themeMode === 'light' ? 'dark' : 'light'} theme`}
          >
            {themeMode === 'light' ? '🌙' : '☀️'}
          </button>
          
          {/* Syntax highlighting toggle */}
          <button
            onClick={toggleSyntaxHighlighting}
            className={`p-2 rounded-md hover:bg-gray-100 ${
              syntaxHighlighting 
                ? 'text-blue-600 hover:text-blue-700' 
                : 'text-gray-500 hover:text-gray-700'
            }`}
            title={syntaxHighlighting ? 'Disable syntax highlighting' : 'Enable syntax highlighting'}
          >
            <Code className="h-4 w-4" />
          </button>
          
          <button
            onClick={handleRefresh}
            className="p-2 text-gray-500 hover:text-gray-700 rounded-md hover:bg-gray-100"
            title="Refresh TOML content"
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
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
            disabled={copied || loading}
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
        {loading ? (
          <div className="flex items-center justify-center p-8 text-gray-500">
            <RefreshCw className="h-6 w-6 animate-spin mr-2" />
            <span>Loading TOML content...</span>
          </div>
        ) : (
          <>
            {/* Phase 6: View mode content rendering */}
            {viewMode === 'preview' && (
              <div className="space-y-4">
                {syntaxHighlighting ? (
                  <SyntaxHighlighter 
                    language="toml" 
                    style={syntaxTheme}
                    showLineNumbers={true}
                    wrapLongLines={true}
                    className="rounded-md"
                    customStyle={{
                      fontSize: '14px',
                      lineHeight: '1.4',
                      margin: 0,
                      minHeight: '500px' // Ensure minimum height to match config sections
                    }}
                  >
                    {rawToml}
                  </SyntaxHighlighter>
                ) : (
                  <pre className="bg-gray-50 rounded-md p-4 text-sm font-mono border" style={{ minHeight: '500px' }}>
                    <code className="text-gray-800">{rawToml}</code>
                  </pre>
                )}
              </div>
            )}
            
            {viewMode === 'diff' && originalToml && (
              <DiffViewer
                original={originalToml}
                modified={rawToml}
                title="Configuration Changes"
                language="toml"
                theme={themeMode}
                height="500px"
              />
            )}
            
            {viewMode === 'editor' && (
              <div className="space-y-4">
                <div className="text-sm text-gray-600 mb-2">
                  Advanced TOML editor (read-only preview)
                </div>
                {/* Monaco Editor for enhanced editing experience */}
                <div 
                  className={`border rounded-md ${themeMode === 'dark' ? 'border-gray-600' : 'border-gray-300'}`}
                  style={{ height: '500px' }}
                >
                  <DiffEditor
                    original=""
                    modified={rawToml}
                    language="toml"
                    height="100%"
                    theme={themeMode === 'dark' ? 'vs-dark' : 'vs'}
                    options={{
                      readOnly: true,
                      renderSideBySide: false,
                      automaticLayout: true,
                      minimap: { enabled: true },
                      scrollBeyondLastLine: false,
                      fontSize: 14,
                      lineHeight: 20,
                      wordWrap: 'on',
                      folding: true,
                      lineNumbers: 'on'
                    }}
                  />
                </div>
              </div>
            )}
          </>
        )}
        
        {/* Phase 6: Validation errors display */}
        <ValidationErrorDisplay errors={tomlErrors} />
        
        {error && (
          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-md text-sm text-amber-700">
            <div className="flex items-start space-x-2">
              <AlertCircle className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
              <div>
                <div className="font-medium">Fallback Mode</div>
                <div className="mt-1">{error}</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================
// SENSITIVE VALUE MASKING AND FALLBACK UTILITIES
// ============================================================

/**
 * Mask sensitive values in TOML content for display
 */
function maskSensitiveValues(tomlContent: string): string {
  if (!tomlContent) return '';
  
  const lines = tomlContent.split('\n');
  const maskedLines = lines.map(line => {
    // Skip comment lines
    if (line.trim().startsWith('#')) {
      return line;
    }
    
    // Look for key = value pairs
    const keyValueMatch = line.match(/^(\s*)([^=]+)\s*=\s*"([^"]*)"(.*)$/);
    if (keyValueMatch) {
      const [, indent, key, value, rest] = keyValueMatch;
      
      // Check if this looks like a sensitive value
      if (isSensitiveValue(key.trim(), value)) {
        return `${indent}${key.trim()} = "***HIDDEN***"${rest}`;
      }
    }
    
    return line;
  });
  
  return maskedLines.join('\n');
}

/**
 * Check if a key-value pair represents sensitive data
 */
function isSensitiveValue(key: string, value: string): boolean {
  if (!value || typeof value !== 'string') {
    return false;
  }
  
  // Environment variables are not considered sensitive for display purposes
  if (value.startsWith('${') && value.endsWith('}')) {
    return false;
  }
  
  // Check key patterns for sensitive data
  const sensitiveKeyPatterns = [
    /key/i,
    /token/i,
    /secret/i,
    /password/i,
    /auth/i,
    /credential/i,
    /api_key/i
  ];
  
  const keyIsSensitive = sensitiveKeyPatterns.some(pattern => pattern.test(key));
  
  // Check if the value looks like an API key, token, etc.
  const looksLikeKey = value.length > 15 && /^[a-zA-Z0-9+/=_-]+$/.test(value);
  
  return keyIsSensitive || looksLikeKey;
}

/**
 * Generate fallback TOML content from configuration object
 * Used when backend API is unavailable
 */
function generateFallbackToml(obj: any, showSensitive: boolean = false): string {
  if (!obj || typeof obj !== 'object') {
    return '# Configuration data unavailable';
  }
  
  const lines: string[] = [];
  lines.push('# ============================================================');
  lines.push('# FALLBACK TOML PREVIEW (Backend API unavailable)');
  lines.push('# This preview may not include comments or exact formatting');
  lines.push('# ============================================================');
  lines.push('');
  
  const convertObject = (obj: any, depth: number = 0): string[] => {
    const result: string[] = [];
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
          result.push(`[${key}]`);
          result.push(...convertObject(value, depth + 1));
          result.push(''); // Add spacing between sections
        } else {
          result.push(`${indent}[${key}]`);
          result.push(...convertObject(value, depth + 1));
        }
      } else {
        // Simple value
        const formattedValue = formatFallbackValue(value, key, showSensitive);
        result.push(`${indent}${key} = ${formattedValue}`);
      }
    }
    
    return result;
  };
  
  lines.push(...convertObject(obj));
  return lines.join('\n');
}

/**
 * Format a value for fallback TOML generation
 */
function formatFallbackValue(value: any, key: string, showSensitive: boolean): string {
  if (typeof value === 'string') {
    // Check if it's an environment variable
    if (value.startsWith('${') && value.endsWith('}')) {
      return `"${value}"`; // Keep env vars as-is
    }
    
    // Check if it looks like a sensitive value
    if (!showSensitive && isSensitiveValue(key, value)) {
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
    const items = value.map(item => 
      typeof item === 'string' ? `"${item.replace(/"/g, '\\"')}"` : String(item)
    );
    return `[${items.join(', ')}]`;
  }
  
  return `"${String(value)}"`;
}

export default TomlPreview;
