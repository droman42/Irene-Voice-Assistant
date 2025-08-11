import React from 'react'

export default function TextArea({label, value, onChange, placeholder}){
  return (
    <label className="block mb-3">
      <div className="text-sm font-medium mb-1">{label}</div>
      <textarea className="w-full border rounded-xl px-3 py-2 h-28 focus:outline-none focus:ring" value={value ?? ''} onChange={e=>onChange(e.target.value)} placeholder={placeholder} />
    </label>
  )
}
