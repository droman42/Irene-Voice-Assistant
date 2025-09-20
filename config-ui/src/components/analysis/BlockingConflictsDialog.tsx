/**
 * BlockingConflictsDialog Component - Dialog for blocking conflicts
 * 
 * Displays blocking conflicts that prevent saving with detailed information
 * and resolution options for each conflict.
 */

import React from 'react';
import { X, AlertCircle, ArrowRight } from 'lucide-react';
import ConflictBadge from './ConflictBadge';
import ConflictTooltip from './ConflictTooltip';
import type { ConflictReport } from '@/types';

interface BlockingConflictsDialogProps {
  conflicts: ConflictReport[];
  onResolve?: (conflictId: string) => void;
  onClose: () => void;
  className?: string;
}

const BlockingConflictsDialog: React.FC<BlockingConflictsDialogProps> = ({
  conflicts,
  onResolve,
  onClose,
  className = ''
}) => {
  const blockingConflicts = conflicts.filter(c => c.severity === 'blocker');

  if (blockingConflicts.length === 0) {
    return null;
  }

  const getConflictId = (conflict: ConflictReport): string => {
    return `${conflict.intent_a}-${conflict.intent_b}-${conflict.conflict_type}`;
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className={`bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden ${className}`}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-red-50">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 text-red-500" />
            <h2 className="text-lg font-semibold text-red-900">
              Blocking Conflicts Detected
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 hover:bg-red-100 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          <div className="mb-4">
            <p className="text-sm text-gray-700">
              The following {blockingConflicts.length} blocking conflict{blockingConflicts.length !== 1 ? 's' : ''} must be resolved before saving:
            </p>
          </div>

          <div className="space-y-4 max-h-96 overflow-y-auto">
            {blockingConflicts.map((conflict, index) => {
              const conflictId = getConflictId(conflict);

              return (
                <div key={conflictId} className="border border-red-200 rounded-lg bg-red-50 p-4">
                  {/* Conflict Header */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <span className="text-sm font-medium text-red-900">
                          Conflict #{index + 1}
                        </span>
                        <ConflictBadge conflict={conflict} />
                      </div>
                      
                      <div className="flex items-center space-x-2 text-sm">
                        <span className="bg-white px-2 py-1 rounded border text-gray-700">
                          {conflict.intent_a}
                        </span>
                        <ArrowRight className="w-4 h-4 text-gray-400" />
                        <span className="bg-white px-2 py-1 rounded border text-gray-700">
                          {conflict.intent_b}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Conflict Details */}
                  <div className="bg-white rounded border p-3 mb-3">
                    <ConflictTooltip conflict={conflict} className="border-0 shadow-none p-0 max-w-none" />
                  </div>

                  {/* Actions */}
                  {conflict.suggestions.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-medium text-red-800 mb-2">
                        Suggested Resolutions:
                      </div>
                      {conflict.suggestions.slice(0, 2).map((suggestion, suggestionIndex) => (
                        <div key={suggestionIndex} className="bg-white border rounded p-2 text-sm text-gray-700">
                          <div className="mb-2">{suggestion}</div>
                          {onResolve && (
                            <button
                              onClick={() => onResolve(conflictId)}
                              className="text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700 transition-colors"
                            >
                              Apply This Fix
                            </button>
                          )}
                        </div>
                      ))}
                      {conflict.suggestions.length > 2 && (
                        <div className="text-xs text-gray-600 italic">
                          ... and {conflict.suggestions.length - 2} more suggestions available
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-gray-200 bg-gray-50">
          <div className="text-sm text-gray-600">
            Resolve all blocking conflicts to enable saving
          </div>
          <div className="flex space-x-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm border border-gray-300 rounded hover:bg-gray-100 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BlockingConflictsDialog;
