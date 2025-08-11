import React, { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

export default function Section({ title, subtitle, children, defaultOpen = true }){
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border rounded-2xl shadow-sm bg-white">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-4 py-3">
        <div>
          <div className="text-lg font-semibold">{title}</div>
          {subtitle ? <div className="text-sm text-gray-500">{subtitle}</div> : null}
        </div>
        {open ? <ChevronDown /> : <ChevronRight />}
      </button>
      {open ? <div className="px-4 pb-4">{children}</div> : null}
    </div>
  )
}
