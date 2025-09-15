import { Trash2, ChevronUp, ChevronDown, Plus } from 'lucide-react';
import ParameterSpecEditor from './ParameterSpecEditor';
import type { ParameterListEditorProps } from '@/types';

interface Parameter {
  name: string;
  type: 'string' | 'integer' | 'float' | 'duration' | 'datetime' | 'boolean' | 'choice' | 'entity';
  required: boolean;
  default_value?: string;
  description?: string;
  choices?: string[];
  pattern?: string;
  min_value?: number;
  max_value?: number;
  aliases?: string[];
  extraction_patterns?: Array<Record<string, any>>;
}

export default function ParameterListEditor({
  value, 
  onChange,
  availableParams,
  disabled = false
}: ParameterListEditorProps) {
  const arr: Parameter[] = value ?? [];
  
  const add = (): void => {
    onChange([...(arr ?? []), { name: '', type: 'string', required: true }]);
  };

  const del = (idx: number): void => {
    onChange(arr.filter((_, i) => i !== idx));
  };

  const set = (idx: number, obj: Parameter): void => {
    onChange(arr.map((o, i) => i === idx ? obj : o));
  };

  const moveUp = (idx: number): void => {
    if (idx <= 0) return;
    const next = [...arr];
    [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
    onChange(next);
  };

  const moveDown = (idx: number): void => {
    if (idx >= arr.length - 1) return;
    const next = [...arr];
    [next[idx + 1], next[idx]] = [next[idx], next[idx + 1]];
    onChange(next);
  };

  return (
    <div className="flex flex-col gap-2">
      {arr.length === 0 ? (
        <div className="text-sm text-gray-500 mb-2">No parameters</div>
      ) : null}
      {arr.map((p, idx) => (
        <div key={idx} className="border rounded-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-medium">Parameter {idx + 1}</div>
            <div className="flex items-center gap-2">
              <button
                className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => moveUp(idx)}
                title="Move up"
                disabled={disabled || idx === 0}
              >
                <ChevronUp className="w-4 h-4" />
              </button>
              <button
                className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => moveDown(idx)}
                title="Move down"
                disabled={disabled || idx === arr.length - 1}
              >
                <ChevronDown className="w-4 h-4" />
              </button>
              <button
                className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => del(idx)}
                title="Remove"
                disabled={disabled}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
          <ParameterSpecEditor
            value={p}
            onChange={(np) => set(idx, np)}
            disabled={disabled}
          />
          {availableParams && (
            <div className="text-xs text-gray-500 mt-2">
              Available parameters: {availableParams.join(', ')}
            </div>
          )}
        </div>
      ))}
      <button
        onClick={add}
        className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        disabled={disabled}
      >
        <Plus className="w-4 h-4" /> Add parameter
      </button>
    </div>
  );
}
