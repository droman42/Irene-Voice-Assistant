/**
 * ConflictBadge Component - Inline conflict markers for donation editing
 * 
 * Displays individual conflict indicators with severity-based styling
 * and tooltip information for detailed conflict information.
 */

import React from 'react';
import { AlertCircle, AlertTriangle, Info } from 'lucide-react';
import Badge from '@/components/ui/Badge';
import type { ConflictReport } from '@/types';

interface ConflictBadgeProps {
  conflict: ConflictReport;
  className?: string;
  onClick?: () => void;
}

const ConflictBadge: React.FC<ConflictBadgeProps> = ({
  conflict,
  className = '',
  onClick
}) => {
  const getSeverityConfig = () => {
    switch (conflict.severity) {
      case 'blocker':
        return {
          icon: AlertCircle,
          className: 'bg-red-100 text-red-800 border-red-300 hover:bg-red-200',
          label: 'Blocker'
        };
      case 'warning':
        return {
          icon: AlertTriangle,
          className: 'bg-yellow-100 text-yellow-800 border-yellow-300 hover:bg-yellow-200',
          label: 'Warning'
        };
      case 'info':
        return {
          icon: Info,
          className: 'bg-blue-100 text-blue-800 border-blue-300 hover:bg-blue-200',
          label: 'Info'
        };
      default:
        return {
          icon: Info,
          className: 'bg-gray-100 text-gray-800 border-gray-300 hover:bg-gray-200',
          label: 'Unknown'
        };
    }
  };

  const config = getSeverityConfig();
  const Icon = config.icon;

  const formatConflictType = (type: string): string => {
    return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const getTooltipContent = (): string => {
    const lines = [
      `Conflict: ${conflict.intent_a} ↔ ${conflict.intent_b}`,
      `Type: ${formatConflictType(conflict.conflict_type)}`,
      `Score: ${(conflict.score * 100).toFixed(1)}%`,
      `Language: ${conflict.language.toUpperCase()}`
    ];

    if (conflict.suggestions.length > 0) {
      lines.push('', 'Suggestions:');
      conflict.suggestions.slice(0, 2).forEach(suggestion => {
        lines.push(`• ${suggestion}`);
      });
      if (conflict.suggestions.length > 2) {
        lines.push(`• ... and ${conflict.suggestions.length - 2} more`);
      }
    }

    return lines.join('\n');
  };

  return (
    <div 
      className={`inline-flex items-center cursor-help ${className}`}
      title={getTooltipContent()}
      onClick={onClick}
    >
      <Badge 
        variant="custom" 
        className={`${config.className} cursor-pointer transition-colors duration-150 text-xs`}
      >
        <Icon className="w-3 h-3 mr-1" />
        {formatConflictType(conflict.conflict_type)}
      </Badge>
    </div>
  );
};

export default ConflictBadge;
