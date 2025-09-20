/**
 * SuggestionPanel Component - Smart fix suggestions for conflicts
 * 
 * Displays actionable suggestions for resolving detected conflicts
 * with the ability to apply suggestions directly to the donation data.
 */

import React, { useState } from 'react';
import { Lightbulb, CheckCircle, ArrowRight, X } from 'lucide-react';
import type { ConflictReport } from '@/types';

interface SuggestionPanelProps {
  conflicts: ConflictReport[];
  onApplySuggestion?: (conflictId: string, suggestion: string) => void;
  onDismissConflict?: (conflictId: string) => void;
  className?: string;
}

const SuggestionPanel: React.FC<SuggestionPanelProps> = ({
  conflicts,
  onApplySuggestion,
  onDismissConflict,
  className = ''
}) => {
  const [expandedConflicts, setExpandedConflicts] = useState<Set<string>>(new Set());
  const [appliedSuggestions, setAppliedSuggestions] = useState<Set<string>>(new Set());

  // Filter to only show conflicts with suggestions
  const conflictsWithSuggestions = conflicts.filter(c => c.suggestions.length > 0);

  if (conflictsWithSuggestions.length === 0) {
    return null;
  }

  const getConflictId = (conflict: ConflictReport): string => {
    return `${conflict.intent_a}-${conflict.intent_b}-${conflict.conflict_type}`;
  };

  const toggleExpanded = (conflictId: string) => {
    setExpandedConflicts(prev => {
      const newSet = new Set(prev);
      if (newSet.has(conflictId)) {
        newSet.delete(conflictId);
      } else {
        newSet.add(conflictId);
      }
      return newSet;
    });
  };

  const handleApplySuggestion = (conflict: ConflictReport, suggestion: string) => {
    const conflictId = getConflictId(conflict);
    const suggestionId = `${conflictId}-${suggestion}`;
    
    if (onApplySuggestion) {
      onApplySuggestion(conflictId, suggestion);
      setAppliedSuggestions(prev => new Set([...prev, suggestionId]));
    }
  };

  const handleDismissConflict = (conflict: ConflictReport) => {
    const conflictId = getConflictId(conflict);
    if (onDismissConflict) {
      onDismissConflict(conflictId);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'blocker':
        return 'border-red-200 bg-red-50';
      case 'warning':
        return 'border-yellow-200 bg-yellow-50';
      case 'info':
        return 'border-blue-200 bg-blue-50';
      default:
        return 'border-gray-200 bg-gray-50';
    }
  };

  return (
    <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>
      <div className="flex items-center space-x-2 p-3 border-b border-gray-200 bg-gray-50">
        <Lightbulb className="w-4 h-4 text-yellow-500" />
        <h3 className="text-sm font-medium text-gray-900">
          Smart Suggestions ({conflictsWithSuggestions.length})
        </h3>
      </div>

      <div className="divide-y divide-gray-200">
        {conflictsWithSuggestions.map((conflict) => {
          const conflictId = getConflictId(conflict);
          const isExpanded = expandedConflicts.has(conflictId);

          return (
            <div key={conflictId} className={`p-3 ${getSeverityColor(conflict.severity)}`}>
              {/* Conflict Header */}
              <div className="flex items-center justify-between">
                <button
                  onClick={() => toggleExpanded(conflictId)}
                  className="flex items-center space-x-2 text-left flex-1 hover:bg-white hover:bg-opacity-50 -m-1 p-1 rounded transition-colors"
                >
                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-900">
                      {conflict.intent_a} ↔ {conflict.intent_b}
                    </div>
                    <div className="text-xs text-gray-600">
                      {conflict.conflict_type.replace(/_/g, ' ')} • {conflict.suggestions.length} suggestion{conflict.suggestions.length !== 1 ? 's' : ''}
                    </div>
                  </div>
                  <ArrowRight className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                </button>
                
                <button
                  onClick={() => handleDismissConflict(conflict)}
                  className="p-1 text-gray-400 hover:text-gray-600 hover:bg-white hover:bg-opacity-50 rounded transition-colors"
                  title="Dismiss conflict"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Expanded Suggestions */}
              {isExpanded && (
                <div className="mt-3 space-y-2">
                  {conflict.suggestions.map((suggestion, index) => {
                    const suggestionId = `${conflictId}-${suggestion}`;
                    const isApplied = appliedSuggestions.has(suggestionId);

                    return (
                      <div key={index} className="bg-white bg-opacity-70 border border-gray-200 rounded p-3">
                        <div className="text-sm text-gray-700 mb-2">
                          {suggestion}
                        </div>
                        
                        <div className="flex items-center justify-between">
                          <div className="text-xs text-gray-500">
                            Suggestion {index + 1} of {conflict.suggestions.length}
                          </div>
                          
                          {isApplied ? (
                            <div className="flex items-center space-x-1 text-green-600 text-xs">
                              <CheckCircle className="w-3 h-3" />
                              <span>Applied</span>
                            </div>
                          ) : (
                            <button
                              onClick={() => handleApplySuggestion(conflict, suggestion)}
                              className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors"
                              disabled={!onApplySuggestion}
                            >
                              Apply
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SuggestionPanel;
