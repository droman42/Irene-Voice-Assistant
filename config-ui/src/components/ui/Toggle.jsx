import React from 'react'

export default function Toggle({label, checked, onChange}){
  return (
    <label className="flex items-center gap-3 mb-2">
      <input type="checkbox" checked={!!checked} onChange={e=>onChange(e.target.checked)} />
      <span className="text-sm">{label}</span>
    </label>
  )
}
