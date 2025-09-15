import { Plus, Trash2 } from 'lucide-react';
import type { ArrayOfStringsEditorProps } from '@/types';

export default function ArrayOfStringsEditor({
  label, 
  value, 
  onChange, 
  placeholder,
  disabled = false
}: ArrayOfStringsEditorProps & { addLabel?: string }) {
  const arr = value ?? [];
  
  const update = (idx: number, v: string): void => {
    const next = [...arr];
    next[idx] = v;
    onChange(next);
  };

  const remove = (idx: number): void => {
    const next = arr.filter((_, i) => i !== idx);
    onChange(next);
  };

  const add = (): void => {
    onChange([...arr, '']);
  };

  return (
    <div className="mb-4">
      <div className="font-medium mb-2">{label}</div>
      {arr.length === 0 ? (
        <div className="text-sm text-gray-500 mb-2">No items</div>
      ) : null}
      {arr.map((item, idx) => (
        <div key={idx} className="flex items-center gap-2 mb-2">
          <input
            className={`flex-1 border rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              disabled ? 'bg-gray-100 cursor-not-allowed' : ''
            }`}
            value={item}
            onChange={(e) => update(idx, e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
          />
          <button
            className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => remove(idx)}
            title="Remove"
            disabled={disabled}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
      <button
        className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        onClick={add}
        disabled={disabled}
      >
        <Plus className="w-4 h-4" /> Add
      </button>
    </div>
  );
}
