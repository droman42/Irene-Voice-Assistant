import React from 'react'
import Input from '../ui/Input.jsx'
import TextArea from '../ui/TextArea.jsx'
import Toggle from '../ui/Toggle.jsx'
import ArrayOfStringsEditor from './ArrayOfStringsEditor.jsx'
import ExtractionPatternsEditor from './ExtractionPatternsEditor.jsx'

export default function ParameterSpecEditor({value, onChange}){
  const v = value ?? { name: '', type: 'string', required: true }
  const set = (k, val)=> onChange({ ...(v ?? {}), [k]: val })
  return (
    <div className="border rounded-xl p-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Input label="Name" value={v.name} onChange={(val)=>set('name', val)} />
        <label className="block">
          <div className="text-sm font-medium mb-1">Type</div>
          <select className="w-full border rounded-xl px-3 py-2" value={v.type} onChange={(e)=>set('type', e.target.value)}>
            { ['string','integer','float','duration','datetime','boolean','choice','entity'].map(t=> <option key={t} value={t}>{t}</option>) }
          </select>
        </label>
        <Toggle label="Required" checked={!!v.required} onChange={(val)=>set('required', val)} />
        <Input label="Default value" value={v.default_value ?? ''} onChange={(val)=>set('default_value', val)} />
        <TextArea label="Description" value={v.description ?? ''} onChange={(val)=>set('description', val)} />
        {v.type === 'choice' ? (
          <ArrayOfStringsEditor label="Choices" value={v.choices ?? []} onChange={(val)=>set('choices', val)} addLabel="Add choice" />
        ) : null}
        {v.type === 'string' ? (
          <Input label="Regex pattern (optional)" value={v.pattern ?? ''} onChange={(val)=>set('pattern', val)} placeholder="e.g. ^[a-z]+$" />
        ) : null}
        {(v.type === 'integer' || v.type === 'float') ? (
          <div className="grid grid-cols-2 gap-2">
            <Input label="Min value" value={v.min_value ?? ''} onChange={(val)=>set('min_value', val)} type="number" />
            <Input label="Max value" value={v.max_value ?? ''} onChange={(val)=>set('max_value', val)} type="number" />
          </div>
        ) : null}
        <ArrayOfStringsEditor label="Aliases" value={v.aliases ?? []} onChange={(val)=>set('aliases', val)} addLabel="Add alias" />
        <div>
          <div className="text-sm font-medium mb-2">Extraction patterns</div>
          <ExtractionPatternsEditor value={v.extraction_patterns ?? []} onChange={(val)=>set('extraction_patterns', val)} />
        </div>
      </div>
    </div>
  )
}
