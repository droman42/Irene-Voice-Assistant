import type { ToggleProps } from '@/types';

export default function Toggle({
  label,
  checked,
  onChange,
  disabled = false,
  className = ''
}: ToggleProps) {
  return (
    <label className={`flex items-center gap-3 mb-2 ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'} ${className}`}>
      <input
        type="checkbox"
        checked={!!checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
      />
      <span className="text-sm select-none">{label}</span>
    </label>
  );
}
