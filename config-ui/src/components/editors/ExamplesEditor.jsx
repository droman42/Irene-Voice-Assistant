import React from 'react'
import { Trash2, Plus } from 'lucide-react'
import TextArea from '../ui/TextArea.jsx'
import KeyValueEditor from './KeyValueEditor.jsx'

export default function ExamplesEditor({value, onChange, knownParams}){
  const arr = value ?? []
  const add = ()=> onChange([...(arr ?? []), { text: '', parameters: {} }])
  const del = (idx)=> onChange(arr.filter((_,i)=>i!==idx))
  const set = (idx, obj)=> onChange(arr.map((o,i)=> i===idx ? obj : o))
  return (
    <div className="flex flex-col gap-2">
      {arr.length===0 ? <div className="text-sm text-gray-500 mb-2">No examples</div> : null}
      {arr.map((ex, idx)=>(
        <div key={idx} className="border rounded-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-medium">Example {idx+1}</div>
            <button className="p-2 rounded-lg border hover:bg-gray-50" onClick={()=>del(idx)}><Trash2 className="w-4 h-4"/></button>
          </div>
          <TextArea label="User text" value={ex.text ?? ''} onChange={(v)=>set(idx,{...ex, text: v})} />
          <div className="text-sm font-medium mb-2">Expected parameters</div>
          <KeyValueEditor label="Parameters" object={ex.parameters ?? {}} onChange={(o)=>set(idx, { ...ex, parameters: o })} />
          {knownParams?.length ? (
            <div className="text-xs text-gray-500">Known parameters: {knownParams.join(', ')}</div>
          ) : null}
        </div>
      ))}
      <button onClick={add} className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl hover:bg-gray-50"><Plus className="w-4 h-4"/> Add example</button>
    </div>
  )
}
