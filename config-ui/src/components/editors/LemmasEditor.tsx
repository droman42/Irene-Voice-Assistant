import { Plus, Trash2, AlertTriangle, RefreshCw } from 'lucide-react';
import { useState } from 'react';

interface LemmasEditorProps {
  value: string[];
  onChange: (lemmas: string[]) => void;
  disabled?: boolean;
  tokenPatterns?: Array<Array<Record<string, any>>>;
  onAutoSync?: () => void;
  showSyncWarning?: boolean;
}

export default function LemmasEditor({
  value = [],
  onChange,
  disabled = false,
  tokenPatterns = [],
  onAutoSync,
  showSyncWarning = false
}: LemmasEditorProps) {
  const [newLemma, setNewLemma] = useState('');
  
  const addLemma = (): void => {
    if (newLemma.trim() && !value.includes(newLemma.trim())) {
      onChange([...value, newLemma.trim()]);
      setNewLemma('');
    }
  };

  const removeLemma = (index: number): void => {
    onChange(value.filter((_, i) => i !== index));
  };

  const updateLemma = (index: number, newValue: string): void => {
    const updated = [...value];
    updated[index] = newValue;
    onChange(updated);
  };

  const handleKeyPress = (e: React.KeyboardEvent): void => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addLemma();
    }
  };

  // Extract suggested lemmas from token patterns
  const getSuggestedLemmas = (): string[] => {
    const suggested: Set<string> = new Set();
    
    tokenPatterns.forEach(pattern => {
      pattern.forEach(token => {
        if (token.LEMMA) {
          if (typeof token.LEMMA === 'string') {
            suggested.add(token.LEMMA);
          } else if (token.LEMMA.IN && Array.isArray(token.LEMMA.IN)) {
            token.LEMMA.IN.forEach((lemma: string) => suggested.add(lemma));
          }
        }
      });
    });

    // Filter out lemmas that are already added
    return Array.from(suggested).filter(lemma => !value.includes(lemma));
  };

  const suggestedLemmas = getSuggestedLemmas();

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <label className="block text-sm font-medium text-gray-700">
          Method Lemmas
        </label>
        <div className="flex items-center space-x-2">
          {showSyncWarning && (
            <div className="flex items-center text-amber-600 text-xs">
              <AlertTriangle className="w-3 h-3 mr-1" />
              {suggestedLemmas.length} unsynced
            </div>
          )}
          {onAutoSync && suggestedLemmas.length > 0 && (
            <button
              type="button"
              onClick={onAutoSync}
              disabled={disabled}
              className="flex items-center text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 disabled:opacity-50"
              title={`Auto-sync ${suggestedLemmas.length} lemma(s) from token patterns`}
            >
              <RefreshCw className="w-3 h-3 mr-1" />
              Sync ({suggestedLemmas.length})
            </button>
          )}
        </div>
      </div>
      
      <p className="text-xs text-gray-500 mb-3">
        Key lemmatized forms used for fuzzy keyword matching. Should align with token patterns.
      </p>

      {/* Current lemmas */}
      <div className="space-y-2 mb-3">
        {value.map((lemma, index) => (
          <div key={index} className="flex items-center space-x-2">
            <input
              type="text"
              value={lemma}
              onChange={(e) => updateLemma(index, e.target.value)}
              disabled={disabled}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50"
              placeholder="Enter lemma..."
            />
            <button
              type="button"
              onClick={() => removeLemma(index)}
              disabled={disabled}
              className="p-2 text-red-600 hover:bg-red-50 rounded-md disabled:opacity-50"
              title="Remove lemma"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* Add new lemma */}
      <div className="flex items-center space-x-2 mb-3">
        <input
          type="text"
          value={newLemma}
          onChange={(e) => setNewLemma(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={disabled}
          className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50"
          placeholder="Add new lemma..."
        />
        <button
          type="button"
          onClick={addLemma}
          disabled={disabled || !newLemma.trim()}
          className="flex items-center px-3 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Plus className="w-4 h-4 mr-1" />
          Add
        </button>
      </div>

      {/* Suggested lemmas from token patterns */}
      {suggestedLemmas.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-gray-600 mb-2">
            Suggested from token patterns:
          </p>
          <div className="flex flex-wrap gap-1">
            {suggestedLemmas.map((lemma, index) => (
              <button
                key={index}
                type="button"
                onClick={() => onChange([...value, lemma])}
                disabled={disabled}
                className="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50"
                title={`Add "${lemma}" to lemmas`}
              >
                + {lemma}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Info about lemmas */}
      <div className="mt-2 text-xs text-gray-500">
        <p>Lemmas are used for fuzzy keyword matching and should represent the base forms of words in your token patterns.</p>
      </div>
    </div>
  );
}
