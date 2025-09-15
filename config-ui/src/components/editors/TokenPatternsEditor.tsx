import { Plus, Trash2 } from 'lucide-react';
import KeyValueEditor from './KeyValueEditor';
import type { TokenPatternsEditorProps } from '@/types';

export default function TokenPatternsEditor({
  value, 
  onChange, 
  globalParams,
  disabled = false
}: TokenPatternsEditorProps) {
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

  return (
    <div className="mb-4">
      <div className="font-medium mb-2">Token Patterns</div>
      {patterns.length === 0 ? (
        <div className="text-sm text-gray-500 mb-2">No patterns</div>
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
                  <KeyValueEditor
                    label="Attributes"
                    object={tok ?? {}}
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
