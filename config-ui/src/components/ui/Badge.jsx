import React from 'react'

export default function Badge({children, tone='default'}){
  const toneClass = tone === 'green' ? 'bg-green-50 text-green-700 border-green-200' : tone === 'red' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-gray-50 text-gray-700 border-gray-200'
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${toneClass}`}>{children}</span>
}
