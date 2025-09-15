import { Trash2, Plus } from 'lucide-react';
import TextArea from '@/components/ui/TextArea';
import KeyValueEditor from './KeyValueEditor';
import type { ExamplesEditorProps } from '@/types';

interface Example {
  text: string;
  parameters: Record<string, any>;
}

export default function ExamplesEditor({
  value, 
  onChange, 
  globalParams,
  disabled = false
}: ExamplesEditorProps) {
  const arr: Example[] = value?.map(item => {
    if (typeof item === 'string') {
      return { text: item, parameters: {} };
    }
    return item as Example;
  }) ?? [];

  const add = (): void => {
    onChange([...arr, { text: '', parameters: {} }]);
  };

  const del = (idx: number): void => {
    onChange(arr.filter((_, i) => i !== idx));
  };

  const set = (idx: number, obj: Example): void => {
    const newArr = arr.map((o, i) => i === idx ? obj : o);
    onChange(newArr);
  };

  return (
    <div className="flex flex-col gap-2">
      {arr.length === 0 ? (
        <div className="text-sm text-gray-500 mb-2">No examples</div>
      ) : null}
      {arr.map((ex, idx) => (
        <div key={idx} className="border rounded-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-medium">Example {idx + 1}</div>
            <button
              className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={() => del(idx)}
              disabled={disabled}
              title="Remove example"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
          <TextArea
            label="User text"
            value={ex.text ?? ''}
            onChange={(v) => set(idx, { ...ex, text: v })}
            disabled={disabled}
            placeholder="Enter example user input..."
          />
          <div className="text-sm font-medium mb-2">Expected parameters</div>
          <KeyValueEditor
            label="Parameters"
            object={ex.parameters ?? {}}
            onChange={(o) => set(idx, { ...ex, parameters: o })}
            disabled={disabled}
          />
          {globalParams?.length ? (
            <div className="text-xs text-gray-500 mt-2">
              Available parameters: {globalParams.join(', ')}
            </div>
          ) : null}
        </div>
      ))}
      <button
        onClick={add}
        className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        disabled={disabled}
      >
        <Plus className="w-4 h-4" /> Add example
      </button>
    </div>
  );
}
