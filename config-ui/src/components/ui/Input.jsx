import React from 'react'

export default function Input({label, value, onChange, placeholder, required, type='text'}){
  return (
    <label className="block mb-3">
      <div className="text-sm font-medium mb-1">{label}{required ? <span className="text-red-500">*</span> : null}</div>
      <input className="w-full border rounded-xl px-3 py-2 focus:outline-none focus:ring" value={value ?? ''} onChange={e=>onChange(type==='number'? (e.target.value===''? '' : Number(e.target.value)) : e.target.value)} placeholder={placeholder} type={type} />
    </label>
  )
}
