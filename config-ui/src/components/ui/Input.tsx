import React from 'react';
import type { InputProps } from '@/types';

export default function Input({
  label,
  value,
  onChange,
  placeholder,
  required = false,
  type = 'text',
  error,
  disabled = false,
  className = ''
}: InputProps) {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (type === 'number') {
      const numValue = e.target.value === '' ? '' : Number(e.target.value);
      onChange(String(numValue));
    } else {
      onChange(e.target.value);
    }
  };

  return (
    <label className={`block mb-3 ${className}`}>
      {label && (
        <div className="text-sm font-medium mb-1">
          {label}
          {required && <span className="text-red-500">*</span>}
        </div>
      )}
      <input
        className={`w-full border rounded-xl px-3 py-2 focus:outline-none focus:ring ${
          error ? 'border-red-500 focus:ring-red-200' : 'border-gray-300 focus:ring-blue-200'
        } ${disabled ? 'bg-gray-100 cursor-not-allowed' : ''}`}
        value={value ?? ''}
        onChange={handleChange}
        placeholder={placeholder}
        type={type}
        disabled={disabled}
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
