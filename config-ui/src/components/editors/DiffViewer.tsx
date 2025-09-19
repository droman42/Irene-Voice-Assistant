/**
 * DiffViewer Component - Dedicated component for viewing configuration changes
 * 
 * Phase 6 Feature: Provides side-by-side diff view for TOML configuration changes
 * with Monaco editor integration for professional diff experience.
 */

import React from 'react';
import { DiffEditor } from '@monaco-editor/react';

interface DiffViewerProps {
  original: string;
  modified: string;
  title?: string;
  language?: string;
  theme?: 'light' | 'dark';
  height?: string;
  className?: string;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  original,
  modified,
  title = "Configuration Changes",
  language = "toml",
  theme = 'light',
  height = "400px",
  className = ""
}) => {
  return (
    <div className={`border border-gray-200 rounded-lg ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200 bg-gray-50">
        <h4 className="text-sm font-medium text-gray-900">{title}</h4>
        <div className="flex items-center space-x-2 text-xs text-gray-500">
          <span className="px-2 py-1 bg-red-100 text-red-700 rounded">- Original</span>
          <span className="px-2 py-1 bg-green-100 text-green-700 rounded">+ Modified</span>
        </div>
      </div>
      
      {/* Diff Editor */}
      <div className="p-0">
        <DiffEditor
          original={original}
          modified={modified}
          language={language}
          height={height}
          theme={theme === 'dark' ? 'vs-dark' : 'vs'}
          options={{
            readOnly: true,
            renderSideBySide: true,
            diffWordWrap: 'on',
            automaticLayout: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 14,
            lineHeight: 20,
            folding: true,
            lineNumbers: 'on',
            originalEditable: false,
            enableSplitViewResizing: true,
            renderOverviewRuler: true,
            ignoreTrimWhitespace: false
          }}
          loading={
            <div className="flex items-center justify-center p-8 text-gray-500">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mr-2"></div>
              <span>Loading diff viewer...</span>
            </div>
          }
        />
      </div>
    </div>
  );
};

export default DiffViewer;
