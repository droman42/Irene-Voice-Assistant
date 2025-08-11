import React, { useState } from 'react'
import ArrayOfStringsEditor from './ArrayOfStringsEditor.jsx'
import { Trash2 } from 'lucide-react'

export default function KeyValueOfStringArray({label, value, onChange}){
  const obj = value ?? {}
  const [k, setK] = useState('')
  const [v, setV] = useState('')
  const add = ()=>{
    if(!k) return
    const arr = (obj[k] ?? []).slice()
    if(v) arr.push(v)
    const next = { ...obj, [k]: arr }
    onChange(next)
    setK(''); setV('')
  }
  return (
    <div>
      {Object.entries(obj).map(([key, list])=> (
        <div key={key} className="border rounded-xl p-3 mb-2">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-medium">Language: <span className="font-mono bg-gray-50 px-2 py-0.5 rounded">{key}</span></div>
            <button className="p-2 rounded-lg border hover:bg-gray-50" onClick={()=>{ const next={...obj}; delete next[key]; onChange(next); }}><Trash2 className="w-4 h-4"/></button>
          </div>
          <ArrayOfStringsEditor label="Patterns" value={list ?? []} onChange={(val)=> onChange({ ...obj, [key]: (val ?? []) })} addLabel="Add pattern" />
        </div>
      ))}
      <div className="flex items-center gap-2">
        <input className="border rounded-xl px-3 py-2" placeholder="lang (e.g., en, de)" value={k} onChange={(e)=>setK(e.target.value)} />
        <input className="border rounded-xl px-3 py-2 flex-1" placeholder="first pattern (optional)" value={v} onChange={(e)=>setV(e.target.value)} />
        <button className="px-3 py-2 border rounded-xl hover:bg-gray-50" onClick={add}>Add language</button>
      </div>
    </div>
  )
}
