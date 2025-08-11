import React, { useState } from 'react'

function coerceValue(v){
  if(v === '') return ''
  if(v === 'true') return true
  if(v === 'false') return false
  if(!isNaN(Number(v))) return Number(v)
  return v
}

export default function KeyValueEditor({label, object, onChange}){
  const entries = Object.entries(object ?? {})
  const setKV = (k, v)=>{
    const next = { ...(object ?? {}) }
    next[k] = v
    onChange(next)
  }
  const del = (k)=>{
    const next = { ...(object ?? {}) }
    delete next[k]
    onChange(next)
  }
  const [newKey, setNewKey] = useState('')
  const [newVal, setNewVal] = useState('')
  return (
    <div className="mb-4">
      <div className="font-medium mb-2">{label}</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-3">
        {entries.map(([k,v])=> (
          <div key={k} className="flex items-center gap-2">
            <input className="border rounded-xl px-3 py-2 flex-1" value={k} onChange={(e)=>{ const nk=e.target.value; const val=v; const next={...(object??{})}; delete next[k]; next[nk]=val; onChange(next); }} />
            <input className="border rounded-xl px-3 py-2 flex-1" value={String(v)} onChange={(e)=>setKV(k, coerceValue(e.target.value))} />
            <button onClick={()=>del(k)} className="p-2 rounded-lg border hover:bg-gray-50">✕</button>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <input className="border rounded-xl px-3 py-2 flex-1" placeholder="key" value={newKey} onChange={(e)=>setNewKey(e.target.value)} />
        <input className="border rounded-xl px-3 py-2 flex-1" placeholder="value" value={newVal} onChange={(e)=>setNewVal(e.target.value)} />
        <button className="px-3 py-2 border rounded-xl hover:bg-gray-50" onClick={()=>{ if(!newKey) return; const next={...(object??{})}; next[newKey]=coerceValue(newVal); onChange(next); setNewKey(''); setNewVal(''); }}>Add</button>
      </div>
    </div>
  )
}
