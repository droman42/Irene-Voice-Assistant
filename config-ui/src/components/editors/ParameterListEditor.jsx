import React from 'react'
import { Trash2 } from 'lucide-react'
import ParameterSpecEditor from './ParameterSpecEditor.jsx'

export default function ParameterListEditor({value, onChange}){
  const arr = value ?? []
  const add = ()=> onChange([...(arr ?? []), { name: '', type: 'string', required: true }])
  const del = (idx)=> onChange(arr.filter((_,i)=>i!==idx))
  const set = (idx, obj)=> onChange(arr.map((o,i)=> i===idx ? obj : o))
  const up = (idx)=>{ if(idx<=0) return; const next=[...arr]; [next[idx-1], next[idx]]=[next[idx], next[idx-1]]; onChange(next); }
  const down = (idx)=>{ if(idx>=arr.length-1) return; const next=[...arr]; [next[idx+1], next[idx]]=[next[idx], next[idx+1]]; onChange(next); }
  return (
    <div className="flex flex-col gap-2">
      {arr.length===0 ? <div className="text-sm text-gray-500 mb-2">No parameters</div> : null}
      {arr.map((p, idx)=>(
        <div key={idx} className="border rounded-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-medium">Parameter {idx+1}</div>
            <div className="flex items-center gap-2">
              <button className="p-2 rounded-lg border hover:bg-gray-50" onClick={()=>up(idx)} title="Move up">↑</button>
              <button className="p-2 rounded-lg border hover:bg-gray-50" onClick={()=>down(idx)} title="Move down">↓</button>
              <button className="p-2 rounded-lg border hover:bg-gray-50" onClick={()=>del(idx)} title="Remove"><Trash2 className="w-4 h-4"/></button>
            </div>
          </div>
          <ParameterSpecEditor value={p} onChange={(np)=>set(idx,np)} />
        </div>
      ))}
      <button onClick={add} className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl hover:bg-gray-50">＋ Add parameter</button>
    </div>
  )
}
