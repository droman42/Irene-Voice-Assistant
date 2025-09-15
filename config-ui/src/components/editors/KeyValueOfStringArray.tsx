import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import ArrayOfStringsEditor from './ArrayOfStringsEditor';

interface KeyValueOfStringArrayProps {
  label: string;
  value: Record<string, string[]>;
  onChange: (value: Record<string, string[]>) => void;
  disabled?: boolean;
}

export default function KeyValueOfStringArray({
  label, 
  value, 
  onChange, 
  disabled = false
}: KeyValueOfStringArrayProps) {
  const obj = value ?? {};
  const [k, setK] = useState('');
  const [v, setV] = useState('');
  
  const add = (): void => {
    if (!k.trim()) return;
    const arr = (obj[k] ?? []).slice();
    if (v.trim()) arr.push(v);
    const next = { ...obj, [k]: arr };
    onChange(next);
    setK('');
    setV('');
  };

  const deleteKey = (key: string): void => {
    const next = { ...obj };
    delete next[key];
    onChange(next);
  };

  const updateArray = (key: string, newArray: string[]): void => {
    onChange({ ...obj, [key]: newArray ?? [] });
  };

  return (
    <div>
      <div className="font-medium mb-2">{label}</div>
      {Object.entries(obj).map(([key, list]) => (
        <div key={key} className="border rounded-xl p-3 mb-2">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-medium">
              Language: <span className="font-mono bg-gray-50 px-2 py-0.5 rounded">{key}</span>
            </div>
            <button
              className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={() => deleteKey(key)}
              disabled={disabled}
              title="Remove language"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
          <ArrayOfStringsEditor
            label="Patterns"
            value={list ?? []}
            onChange={(val) => updateArray(key, val)}
            disabled={disabled}
          />
        </div>
      ))}
      <div className="flex items-center gap-2">
        <input
          className={`border rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            disabled ? 'bg-gray-100 cursor-not-allowed' : ''
          }`}
          placeholder="lang (e.g., en, de)"
          value={k}
          onChange={(e) => setK(e.target.value)}
          disabled={disabled}
        />
        <input
          className={`border rounded-xl px-3 py-2 flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            disabled ? 'bg-gray-100 cursor-not-allowed' : ''
          }`}
          placeholder="first pattern (optional)"
          value={v}
          onChange={(e) => setV(e.target.value)}
          disabled={disabled}
        />
        <button
          className="px-3 py-2 border rounded-xl hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={add}
          disabled={disabled || !k.trim()}
        >
          Add language
        </button>
      </div>
    </div>
  );
}
