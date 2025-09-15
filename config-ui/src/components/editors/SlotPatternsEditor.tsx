import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import TokenPatternsEditor from './TokenPatternsEditor';
import type { SlotPatternsEditorProps } from '@/types';

export default function SlotPatternsEditor({
  value, 
  onChange, 
  globalParams,
  disabled = false
}: SlotPatternsEditorProps) {
  const slots = value ?? {};
  const [newSlot, setNewSlot] = useState('');
  
  const setSlot = (name: string, patterns: Array<Array<Record<string, any>>>): void => {
    const next = { ...(slots ?? {}) };
    next[name] = patterns;
    onChange(next);
  };

  const delSlot = (name: string): void => {
    const next = { ...(slots ?? {}) };
    delete next[name];
    onChange(next);
  };

  const addSlot = (): void => {
    if (!newSlot.trim()) return;
    const next = { ...(slots ?? {}) };
    next[newSlot] = [];
    onChange(next);
    setNewSlot('');
  };

  return (
    <div className="mb-4">
      <div className="font-medium mb-2">Slot Patterns</div>
      {Object.keys(slots).length === 0 ? (
        <div className="text-sm text-gray-500 mb-2">No slots</div>
      ) : null}
      <div className="flex flex-col gap-3">
        {Object.entries(slots).map(([name, patterns]) => (
          <div key={name} className="border rounded-xl p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-medium">
                Slot: <span className="font-mono bg-gray-50 px-2 py-0.5 rounded">{name}</span>
              </div>
              <button
                className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => delSlot(name)}
                title="Remove slot"
                disabled={disabled}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
            <TokenPatternsEditor
              value={patterns ?? []}
              onChange={(v) => setSlot(name, v)}
              globalParams={globalParams}
              disabled={disabled}
            />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 mt-2">
        <input
          className={`border rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            disabled ? 'bg-gray-100 cursor-not-allowed' : ''
          }`}
          placeholder="slot name (e.g., amount, recipient)"
          value={newSlot}
          onChange={(e) => setNewSlot(e.target.value)}
          disabled={disabled}
          onKeyPress={(e) => e.key === 'Enter' && addSlot()}
        />
        <button
          className="px-3 py-2 border rounded-xl hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={addSlot}
          disabled={disabled || !newSlot.trim()}
        >
          Add slot
        </button>
      </div>
    </div>
  );
}
