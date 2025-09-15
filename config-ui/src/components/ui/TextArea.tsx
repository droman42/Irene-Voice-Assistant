import type { TextAreaProps } from '@/types';

export default function TextArea({
  label,
  value,
  onChange,
  placeholder,
  error,
  disabled = false,
  required = false,
  rows = 4,
  className = ''
}: TextAreaProps) {
  return (
    <label className={`block mb-3 ${className}`}>
      {label && (
        <div className="text-sm font-medium mb-1">
          {label}
          {required && <span className="text-red-500">*</span>}
        </div>
      )}
      <textarea
        className={`w-full border rounded-xl px-3 py-2 focus:outline-none focus:ring resize-vertical ${
          error ? 'border-red-500 focus:ring-red-200' : 'border-gray-300 focus:ring-blue-200'
        } ${disabled ? 'bg-gray-100 cursor-not-allowed' : ''}`}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        rows={rows}
        aria-invalid={!!error}
        aria-describedby={error ? `${label}-error` : undefined}
      />
      {error && (
        <div id={`${label}-error`} className="text-sm text-red-600 mt-1">
          {error}
        </div>
      )}
    </label>
  );
}
