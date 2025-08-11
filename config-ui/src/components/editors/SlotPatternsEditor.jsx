import React, { useState } from 'react'
import { Trash2 } from 'lucide-react'
import TokenPatternsEditor from './TokenPatternsEditor.jsx'

export default function SlotPatternsEditor({label, value, onChange}){
  const slots = value ?? {}
  const [newSlot, setNewSlot] = useState('')
  const setSlot = (name, patterns)=>{
    const next = { ...(slots ?? {}) }
    next[name] = patterns
    onChange(next)
  }
  const delSlot = (name)=>{
    const next = { ...(slots ?? {}) }
    delete next[name]
    onChange(next)
  }
  return (
    <div className="mb-4">
      <div className="font-medium mb-2">{label}</div>
      {Object.keys(slots).length===0 ? <div className="text-sm text-gray-500 mb-2">No slots</div> : null}
      <div className="flex flex-col gap-3">
        {Object.entries(slots).map(([name, patterns])=> (
          <div key={name} className="border rounded-xl p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-medium">Slot: <span className="font-mono bg-gray-50 px-2 py-0.5 rounded">{name}</span></div>
              <button className="p-2 rounded-lg border hover:bg-gray-50" onClick={()=>delSlot(name)} title="Remove slot"><Trash2 className="w-4 h-4"/></button>
            </div>
            <TokenPatternsEditor label="Patterns" value={patterns ?? []} onChange={(v)=>setSlot(name, v)} />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 mt-2">
        <input className="border rounded-xl px-3 py-2" placeholder="slot name (e.g., amount, recipient)" value={newSlot} onChange={(e)=>setNewSlot(e.target.value)} />
        <button className="px-3 py-2 border rounded-xl hover:bg-gray-50" onClick={()=>{ if(!newSlot) return; const next={...(slots ?? {})}; next[newSlot]=[]; onChange(next); setNewSlot(''); }}>Add slot</button>
      </div>
    </div>
  )
}
