import Input from '@/components/ui/Input';
import TextArea from '@/components/ui/TextArea';
import Toggle from '@/components/ui/Toggle';
import ArrayOfStringsEditor from './ArrayOfStringsEditor';
import ExtractionPatternsEditor from './ExtractionPatternsEditor';

interface ParameterSpec {
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

interface ParameterSpecEditorProps {
  value: ParameterSpec;
  onChange: (value: ParameterSpec) => void;
  disabled?: boolean;
}

export default function ParameterSpecEditor({
  value, 
  onChange, 
  disabled = false
}: ParameterSpecEditorProps) {
  const v = value ?? { name: '', type: 'string' as const, required: true };
  
  const set = (k: keyof ParameterSpec, val: any): void => {
    onChange({ ...(v ?? {}), [k]: val });
  };

  const parameterTypes = [
    'string', 'integer', 'float', 'duration', 
    'datetime', 'boolean', 'choice', 'entity'
  ] as const;

  return (
    <div className="border rounded-xl p-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Input
          label="Name"
          value={v.name}
          onChange={(val) => set('name', val)}
          disabled={disabled}
          required
        />
        <label className="block">
          <div className="text-sm font-medium mb-1">Type</div>
          <select
            className={`w-full border rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
              disabled ? 'bg-gray-100 cursor-not-allowed' : ''
            }`}
            value={v.type}
            onChange={(e) => set('type', e.target.value as ParameterSpec['type'])}
            disabled={disabled}
          >
            {parameterTypes.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
        <Toggle
          label="Required"
          checked={!!v.required}
          onChange={(val) => set('required', val)}
          disabled={disabled}
        />
        <Input
          label="Default value"
          value={v.default_value ?? ''}
          onChange={(val) => set('default_value', val)}
          disabled={disabled}
        />
        <TextArea
          label="Description"
          value={v.description ?? ''}
          onChange={(val) => set('description', val)}
          disabled={disabled}
        />
        {v.type === 'choice' ? (
          <ArrayOfStringsEditor
            label="Choices"
            value={v.choices ?? []}
            onChange={(val) => set('choices', val)}
            disabled={disabled}
          />
        ) : null}
        {v.type === 'string' ? (
          <Input
            label="Regex pattern (optional)"
            value={v.pattern ?? ''}
            onChange={(val) => set('pattern', val)}
            placeholder="e.g. ^[a-z]+$"
            disabled={disabled}
          />
        ) : null}
        {(v.type === 'integer' || v.type === 'float') ? (
          <div className="grid grid-cols-2 gap-2">
            <Input
              label="Min value"
              value={String(v.min_value ?? '')}
              onChange={(val) => set('min_value', val ? Number(val) : undefined)}
              type="number"
              disabled={disabled}
            />
            <Input
              label="Max value"
              value={String(v.max_value ?? '')}
              onChange={(val) => set('max_value', val ? Number(val) : undefined)}
              type="number"
              disabled={disabled}
            />
          </div>
        ) : null}
        <ArrayOfStringsEditor
          label="Aliases"
          value={v.aliases ?? []}
          onChange={(val) => set('aliases', val)}
          disabled={disabled}
        />
        <div>
          <div className="text-sm font-medium mb-2">Extraction patterns</div>
          <ExtractionPatternsEditor
            value={v.extraction_patterns ?? []}
            onChange={(val) => set('extraction_patterns', val)}
            disabled={disabled}
          />
        </div>
      </div>
    </div>
  );
}
