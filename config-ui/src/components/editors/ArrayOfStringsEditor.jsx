import React from 'react'
import { Plus, Trash2 } from 'lucide-react'

export default function ArrayOfStringsEditor({label, value, onChange, addLabel='Add'}){
  const arr = (value ?? [])
  const update = (idx, v)=>{
    const next = [...arr]
    next[idx] = v
    onChange(next)
  }
  const remove = (idx)=>{
    const next = arr.filter((_,i)=>i!==idx)
    onChange(next)
  }
  return (
    <div className="mb-4">
      <div className="font-medium mb-2">{label}</div>
      {arr.length === 0 ? <div className="text-sm text-gray-500 mb-2">No items</div> : null}
      {arr.map((it, idx)=>(
        <div key={idx} className="flex items-center gap-2 mb-2">
          <input className="flex-1 border rounded-xl px-3 py-2" value={it} onChange={e=>update(idx, e.target.value)} />
          <button className="p-2 rounded-lg border hover:bg-gray-50" onClick={()=>remove(idx)} title="Remove"><Trash2 className="w-4 h-4"/></button>
        </div>
      ))}
      <button className="inline-flex items-center gap-2 px-3 py-2 border rounded-xl hover:bg-gray-50" onClick={()=>onChange([...(value ?? []), '']) }>
        <Plus className="w-4 h-4"/> {addLabel}
      </button>
    </div>
  )
}
