import { useState } from 'react';

function coerceValue(v: string): string | number | boolean {
  if (v === '') return '';
  if (v === 'true') return true;
  if (v === 'false') return false;
  if (!isNaN(Number(v))) return Number(v);
  return v;
}

interface KeyValueEditorProps {
  label: string;
  object: Record<string, any>;
  onChange: (object: Record<string, any>) => void;
  disabled?: boolean;
}

export default function KeyValueEditor({
  label, 
  object, 
  onChange, 
  disabled = false
}: KeyValueEditorProps) {
  const entries = Object.entries(object ?? {});
  
  const setKV = (k: string, v: any): void => {
    const next = { ...(object ?? {}) };
    next[k] = v;
    onChange(next);
  };

  const del = (k: string): void => {
    const next = { ...(object ?? {}) };
    delete next[k];
    onChange(next);
  };

  const updateKey = (oldKey: string, newKey: string): void => {
    if (oldKey === newKey) return;
    const val = object[oldKey];
    const next = { ...(object ?? {}) };
    delete next[oldKey];
    next[newKey] = val;
    onChange(next);
  };

  const [newKey, setNewKey] = useState('');
  const [newVal, setNewVal] = useState('');

  const addEntry = (): void => {
    if (!newKey.trim()) return;
    const next = { ...(object ?? {}) };
    next[newKey] = coerceValue(newVal);
    onChange(next);
    setNewKey('');
    setNewVal('');
  };

  return (
    <div className="mb-4">
      <div className="font-medium mb-2">{label}</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-3">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-center gap-2">
            <input
              className={`border rounded-xl px-3 py-2 flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                disabled ? 'bg-gray-100 cursor-not-allowed' : ''
              }`}
              value={k}
              onChange={(e) => updateKey(k, e.target.value)}
              disabled={disabled}
              placeholder="Key"
            />
            <input
              className={`border rounded-xl px-3 py-2 flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                disabled ? 'bg-gray-100 cursor-not-allowed' : ''
              }`}
              value={String(v)}
              onChange={(e) => setKV(k, coerceValue(e.target.value))}
              disabled={disabled}
              placeholder="Value"
            />
            <button
              onClick={() => del(k)}
              className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={disabled}
              title="Remove entry"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <input
          className={`border rounded-xl px-3 py-2 flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            disabled ? 'bg-gray-100 cursor-not-allowed' : ''
          }`}
          placeholder="Key"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          disabled={disabled}
        />
        <input
          className={`border rounded-xl px-3 py-2 flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            disabled ? 'bg-gray-100 cursor-not-allowed' : ''
          }`}
          placeholder="Value"
          value={newVal}
          onChange={(e) => setNewVal(e.target.value)}
          disabled={disabled}
        />
        <button
          className="px-3 py-2 border rounded-xl hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={addEntry}
          disabled={disabled || !newKey.trim()}
        >
          Add
        </button>
      </div>
    </div>
  );
}
