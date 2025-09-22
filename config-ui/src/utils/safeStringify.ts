/**
 * Safe Stringify Utilities - Prevent [object Object] display issues
 * 
 * Provides safe conversion of values to strings while preserving object content
 * in a human-readable format instead of the generic [object Object].
 */

/**
 * Safely convert any value to a string representation
 * Handles objects by stringifying them instead of showing [object Object]
 */
export function safeStringify(value: any): string {
  if (value === null || value === undefined) {
    return '';
  }
  
  if (typeof value === 'string') {
    return value;
  }
  
  if (typeof value === 'object') {
    try {
      // For arrays, show a clean representation
      if (Array.isArray(value)) {
        if (value.length === 0) return '[]';
        if (value.length <= 3) {
          return `[${value.map(item => typeof item === 'string' ? item : String(item)).join(', ')}]`;
        }
        return `[${value.slice(0, 2).map(item => typeof item === 'string' ? item : String(item)).join(', ')}, ...${value.length - 2} more]`;
      }
      
      // For objects, show JSON representation
      return JSON.stringify(value);
    } catch {
      return '[Invalid Object]';
    }
  }
  
  return String(value);
}

/**
 * Convert value to display format suitable for input fields
 * Similar to safeStringify but optimized for form inputs
 */
export function safeDisplayValue(value: any): string {
  if (value === null || value === undefined) {
    return '';
  }
  
  if (typeof value === 'string') {
    return value;
  }
  
  if (typeof value === 'boolean') {
    return String(value);
  }
  
  if (typeof value === 'number') {
    return String(value);
  }
  
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return '[Invalid Object]';
    }
  }
  
  return String(value);
}

/**
 * Check if a value would result in [object Object] when converted to string
 */
export function wouldShowObjectObject(value: any): boolean {
  return typeof value === 'object' && 
         value !== null && 
         !Array.isArray(value) && 
         String(value) === '[object Object]';
}

/**
 * Safe conversion for array items that might be objects
 */
export function safeArrayItemStringify(item: any): string {
  if (typeof item === 'object' && item !== null) {
    try {
      return JSON.stringify(item);
    } catch {
      return '[Invalid Item]';
    }
  }
  return String(item);
}
