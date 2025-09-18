import { Plus, Trash2, Info, RefreshCw, AlertTriangle } from 'lucide-react';
import SpacyAttributeEditor from './SpacyAttributeEditor';
import type { TokenPatternsEditorProps } from '@/types';

interface EnhancedTokenPatternsEditorProps extends TokenPatternsEditorProps {
  currentLemmas?: string[];
  onLemmasSync?: (extractedLemmas: string[]) => void;
  showSyncIndicator?: boolean;
}

export default function TokenPatternsEditor({
  value, 
  onChange, 
  globalParams,
  disabled = false,
  currentLemmas = [],
  onLemmasSync,
  showSyncIndicator = false
}: EnhancedTokenPatternsEditorProps) {
  const patterns: Array<Array<Record<string, any>>> = value ?? [];
  
  const addPattern = (): void => {
    onChange([...(patterns ?? []), []]);
  };

  const removePattern = (i: number): void => {
    onChange(patterns.filter((_, idx) => idx !== i));
  };

  const addToken = (i: number): void => {
    const next = patterns.map((p, idx) => idx === i ? [...p, {}] : p);
    onChange(next);
  };

  const updateToken = (pi: number, ti: number, token: Record<string, any>): void => {
    const next = patterns.map((p, idx) => 
      idx === pi ? p.map((t, j) => j === ti ? token : t) : p
    );
    onChange(next);
  };

  const removeToken = (pi: number, ti: number): void => {
    const next = patterns.map((p, idx) => 
      idx === pi ? p.filter((_, j) => j !== ti) : p
    );
    onChange(next);
  };

  // Extract lemmas from token patterns
  const extractLemmasFromPatterns = (): string[] => {
    const extractedLemmas: Set<string> = new Set();
    
    patterns.forEach(pattern => {
      pattern.forEach(token => {
        if (token.LEMMA) {
          if (typeof token.LEMMA === 'string') {
            extractedLemmas.add(token.LEMMA);
          } else if (token.LEMMA.IN && Array.isArray(token.LEMMA.IN)) {
            token.LEMMA.IN.forEach((lemma: string) => extractedLemmas.add(lemma));
          }
        }
      });
    });

    return Array.from(extractedLemmas);
  };

  // Check if current lemmas are out of sync with token patterns
  const getUnsyncedLemmas = (): string[] => {
    const extractedLemmas = extractLemmasFromPatterns();
    return extractedLemmas.filter(lemma => !currentLemmas.includes(lemma));
  };


  const unsyncedLemmas = getUnsyncedLemmas();
  const hasUnsyncedLemmas = unsyncedLemmas.length > 0;

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="font-medium">Token Patterns</div>
          <button
            className="p-1 text-gray-400 hover:text-gray-600"
            title="Token patterns use spaCy's powerful pattern matching. Each pattern is a sequence of tokens with specific attributes."
          >
            <Info className="w-4 h-4" />
          </button>
        </div>
        
        {/* Sync controls */}
        <div className="flex items-center space-x-2">
          {showSyncIndicator && hasUnsyncedLemmas && (
            <div className="flex items-center text-amber-600 text-xs">
              <AlertTriangle className="w-3 h-3 mr-1" />
              {unsyncedLemmas.length} unsynced lemma{unsyncedLemmas.length !== 1 ? 's' : ''}
            </div>
          )}
          {onLemmasSync && hasUnsyncedLemmas && (
            <button
              type="button"
              onClick={() => {
                const extractedLemmas = extractLemmasFromPatterns();
                onLemmasSync(extractedLemmas);
              }}
              disabled={disabled}
              className="flex items-center text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 disabled:opacity-50"
              title={`Sync ${unsyncedLemmas.length} lemma(s) to method lemmas`}
            >
              <RefreshCw className="w-3 h-3 mr-1" />
              Sync Lemmas
            </button>
          )}
        </div>
      </div>
      {patterns.length === 0 ? (
        <div className="text-sm text-gray-500 mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="font-medium text-blue-800 mb-1">No token patterns defined</div>
          <div className="text-blue-700">
            Token patterns allow precise matching of text using spaCy's linguistic analysis. 
            Add a pattern to match specific sequences of words, parts of speech, or other token attributes.
          </div>
        </div>
      ) : null}
      <div className="flex flex-col gap-3">
        {patterns.map((pat, pi) => (
          <div key={pi} className="border rounded-xl p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-medium">Pattern {pi + 1}</div>
              <button
                className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => removePattern(pi)}
                title="Remove pattern"
                disabled={disabled}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {pat.map((tok, ti) => (
                <div key={ti} className="border rounded-lg p-2">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs text-gray-600">Token {ti + 1}</div>
                    <button
                      className="p-1 rounded-lg border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      onClick={() => removeToken(pi, ti)}
                      title="Remove token"
                      disabled={disabled}
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                  <SpacyAttributeEditor
                    value={tok ?? {}}
                    onChange={(o) => updateToken(pi, ti, o)}
                    disabled={disabled}
                  />
                </div>
              ))}
              <button
                className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => addToken(pi)}
                disabled={disabled}
              >
                <Plus className="w-4 h-4" /> Add token
              </button>
            </div>
            {globalParams && globalParams.length > 0 && (
              <div className="text-xs text-gray-500 mt-2">
                Available parameters: {globalParams.join(', ')}
              </div>
            )}
          </div>
        ))}
      </div>
      <button
        className="mt-2 inline-flex items-center gap-2 px-3 py-2 border rounded-xl hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        onClick={addPattern}
        disabled={disabled}
      >
        <Plus className="w-4 h-4" /> Add pattern
      </button>

    </div>
  );
}
