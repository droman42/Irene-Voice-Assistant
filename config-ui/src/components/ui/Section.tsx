import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { SectionProps } from '@/types';

export default function Section({
  title,
  children,
  collapsible = true,
  defaultCollapsed = false,
  className = '',
  badge,
  actions
}: SectionProps) {
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  if (!collapsible) {
    return (
      <div className={`border rounded-2xl shadow-sm bg-white ${className}`}>
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <div className="flex items-center gap-2">
            <div className="text-lg font-semibold">{title}</div>
            {badge}
          </div>
          {actions}
        </div>
        <div className="px-4 py-4">{children}</div>
      </div>
    );
  }

  return (
    <div className={`border rounded-2xl shadow-sm bg-white ${className}`}>
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
        aria-expanded={!isCollapsed}
        aria-controls={`section-content-${title.replace(/\s+/g, '-').toLowerCase()}`}
      >
        <div className="flex items-center gap-2">
          <div className="text-lg font-semibold text-left">{title}</div>
          {badge}
        </div>
        <div className="flex items-center gap-2">
          {actions}
          {isCollapsed ? (
            <ChevronRight className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          )}
        </div>
      </button>
      {!isCollapsed && (
        <div
          id={`section-content-${title.replace(/\s+/g, '-').toLowerCase()}`}
          className="px-4 pb-4"
        >
          {children}
        </div>
      )}
    </div>
  );
}
