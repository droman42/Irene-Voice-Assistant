import { Plus, Trash2 } from 'lucide-react';
import KeyValueEditor from './KeyValueEditor';

interface ObjectArrayEditorProps {
  label: string;
  value: Array<Record<string, any>>;
  onChange: (value: Array<Record<string, any>>) => void;
  disabled?: boolean;
}

export default function ObjectArrayEditor({
  label, 
  value, 
  onChange, 
  disabled = false
}: ObjectArrayEditorProps) {
  const arr = value ?? [];
  
  const add = (): void => {
    onChange([...(arr ?? []), {}]);
  };

  const del = (idx: number): void => {
    onChange(arr.filter((_, i) => i !== idx));
  };

  const set = (idx: number, obj: Record<string, any>): void => {
    onChange(arr.map((o, i) => i === idx ? obj : o));
  };

  return (
    <div>
      <div className="font-medium mb-2">{label}</div>
      {arr.length === 0 ? (
        <div className="text-sm text-gray-500 mb-2">No items</div>
      ) : null}
      <div className="flex flex-col gap-2">
        {arr.map((o, idx) => (
          <div key={idx} className="border rounded-xl p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-medium">Item {idx + 1}</div>
              <button
                className="p-2 rounded-lg border hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => del(idx)}
                disabled={disabled}
                title="Remove item"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
            <KeyValueEditor
              label="Fields"
              object={o}
              onChange={(no) => set(idx, no)}
              disabled={disabled}
            />
          </div>
        ))}
      </div>
      <button
        onClick={add}
        className="mt-2 inline-flex items-center gap-2 px-3 py-2 border rounded-xl hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        disabled={disabled}
      >
        <Plus className="w-4 h-4" /> Add item
      </button>
    </div>
  );
}
