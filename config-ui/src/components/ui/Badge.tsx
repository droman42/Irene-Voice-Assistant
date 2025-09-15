import type { BadgeProps } from '@/types';

export default function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  const variantClasses = {
    default: 'bg-gray-50 text-gray-700 border-gray-200',
    success: 'bg-green-50 text-green-700 border-green-200',
    warning: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    error: 'bg-red-50 text-red-700 border-red-200',
    info: 'bg-blue-50 text-blue-700 border-blue-200',
  };

  const variantClass = variantClasses[variant] || variantClasses.default;

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${variantClass} ${className}`}>
      {children}
    </span>
  );
}
