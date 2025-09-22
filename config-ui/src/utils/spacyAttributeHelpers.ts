/**
 * SpaCy Attribute Helpers - Utilities for parsing and handling SpaCy attribute structures
 * 
 * Provides intelligent parsing of SpaCy token attributes to enable proper UI display
 * and editing while preserving the underlying SpaCy structure integrity.
 */

export type SpacyValueType = 'string' | 'regex' | 'list' | 'boolean' | 'operator' | 'number' | 'unknown';

export interface SpacyAttributeStructure {
  attributeName: string;        // "TEXT", "LOWER", "LEMMA", etc.
  valueType: SpacyValueType;    // Type of the value for appropriate input
  displayLabel: string;         // User-friendly display label
  editableValue: any;          // The actual value that should be editable
  isComplex: boolean;          // Whether it has nested structure
  originalValue: any;          // Original value for reconstruction
}

/**
 * Parse a SpaCy attribute key-value pair into a structured format
 */
export function parseSpacyAttribute(key: string, value: any): SpacyAttributeStructure {
  // Handle simple string values
  if (typeof value === 'string') {
    return {
      attributeName: key,
      valueType: 'string',
      displayLabel: key,
      editableValue: value,
      isComplex: false,
      originalValue: value
    };
  }

  // Handle boolean values
  if (typeof value === 'boolean') {
    return {
      attributeName: key,
      valueType: 'boolean',
      displayLabel: key,
      editableValue: value,
      isComplex: false,
      originalValue: value
    };
  }

  // Handle number values
  if (typeof value === 'number') {
    return {
      attributeName: key,
      valueType: 'number',
      displayLabel: key,
      editableValue: value,
      isComplex: false,
      originalValue: value
    };
  }

  // Handle object values with special SpaCy structures
  if (typeof value === 'object' && value !== null) {
    
    // REGEX pattern: { "REGEX": "pattern" }
    if (value.REGEX && typeof value.REGEX === 'string') {
      return {
        attributeName: key,
        valueType: 'regex',
        displayLabel: `${key} (REGEX)`,
        editableValue: value.REGEX,
        isComplex: true,
        originalValue: value
      };
    }

    // IN array: { "IN": ["item1", "item2"] }
    if (value.IN && Array.isArray(value.IN)) {
      return {
        attributeName: key,
        valueType: 'list',
        displayLabel: `${key} (IN)`,
        editableValue: value.IN,
        isComplex: true,
        originalValue: value
      };
    }

    // FUZZY matching: { "FUZZY": "pattern" }
    if (value.FUZZY && typeof value.FUZZY === 'string') {
      return {
        attributeName: key,
        valueType: 'string',
        displayLabel: `${key} (FUZZY)`,
        editableValue: value.FUZZY,
        isComplex: true,
        originalValue: value
      };
    }

    // NOT_IN array: { "NOT_IN": ["item1", "item2"] }
    if (value.NOT_IN && Array.isArray(value.NOT_IN)) {
      return {
        attributeName: key,
        valueType: 'list',
        displayLabel: `${key} (NOT_IN)`,
        editableValue: value.NOT_IN,
        isComplex: true,
        originalValue: value
      };
    }

    // Comparison operators: { ">=": 5 }, { "<": 10 }, etc.
    const comparisonOps = ['>=', '<=', '>', '<', '==', '!='];
    for (const op of comparisonOps) {
      if (value[op] !== undefined) {
        return {
          attributeName: key,
          valueType: 'number',
          displayLabel: `${key} (${op})`,
          editableValue: value[op],
          isComplex: true,
          originalValue: value
        };
      }
    }

    // If it's an object but doesn't match known patterns, treat as JSON
    return {
      attributeName: key,
      valueType: 'unknown',
      displayLabel: `${key} (Custom)`,
      editableValue: JSON.stringify(value),
      isComplex: true,
      originalValue: value
    };
  }

  // Handle special operator values for OP attribute
  if (key === 'OP' && typeof value === 'string') {
    return {
      attributeName: key,
      valueType: 'operator',
      displayLabel: 'OP',
      editableValue: value,
      isComplex: false,
      originalValue: value
    };
  }

  // Fallback for unknown types
  return {
    attributeName: key,
    valueType: 'unknown',
    displayLabel: key,
    editableValue: String(value),
    isComplex: false,
    originalValue: value
  };
}

/**
 * Reconstruct a SpaCy attribute value from edited components
 */
export function reconstructSpacyAttribute(structure: SpacyAttributeStructure, newValue: any): any {
  if (!structure.isComplex) {
    // Simple values - return as-is with appropriate type conversion
    switch (structure.valueType) {
      case 'boolean':
        return typeof newValue === 'boolean' ? newValue : newValue === 'true';
      case 'number':
        return typeof newValue === 'number' ? newValue : Number(newValue);
      default:
        return newValue;
    }
  }

  // Complex values - reconstruct the original structure
  const original = structure.originalValue;
  
  if (original && typeof original === 'object') {
    if (original.REGEX !== undefined) {
      return { REGEX: newValue };
    }
    if (original.IN !== undefined) {
      return { IN: Array.isArray(newValue) ? newValue : [newValue] };
    }
    if (original.FUZZY !== undefined) {
      return { FUZZY: newValue };
    }
    if (original.NOT_IN !== undefined) {
      return { NOT_IN: Array.isArray(newValue) ? newValue : [newValue] };
    }
    
    // Handle comparison operators
    const comparisonOps = ['>=', '<=', '>', '<', '==', '!='];
    for (const op of comparisonOps) {
      if (original[op] !== undefined) {
        return { [op]: Number(newValue) };
      }
    }
  }

  // For unknown complex types, try to parse as JSON
  if (structure.valueType === 'unknown') {
    try {
      return JSON.parse(newValue);
    } catch {
      return newValue;
    }
  }

  return newValue;
}

/**
 * Get available operator options for OP attribute
 */
export function getOperatorOptions(): string[] {
  return [
    '?',     // Zero or one
    '*',     // Zero or more
    '+',     // One or more
    '!',     // Negation
    '{2}',   // Exactly 2
    '{2,4}', // Between 2 and 4
    '{2,}',  // 2 or more
    '{,4}'   // Up to 4
  ];
}

/**
 * Get common SpaCy attribute suggestions
 */
export function getSpacyAttributeSuggestions(): Record<string, string[]> {
  return {
    'TEXT': ['Basic text matching'],
    'LOWER': ['Lowercase text matching'],
    'LEMMA': ['Lemmatized form matching'],
    'POS': ['Part-of-speech tags'],
    'TAG': ['Fine-grained POS tags'],
    'DEP': ['Dependency relation'],
    'ENT_TYPE': ['Named entity type'],
    'LIKE_NUM': ['Looks like a number'],
    'LIKE_EMAIL': ['Looks like an email'],
    'LIKE_URL': ['Looks like a URL'],
    'IS_ALPHA': ['Only alphabetic characters'],
    'IS_DIGIT': ['Only digits'],
    'IS_LOWER': ['All lowercase'],
    'IS_UPPER': ['All uppercase'],
    'IS_TITLE': ['Title case'],
    'IS_PUNCT': ['Punctuation'],
    'IS_SPACE': ['Whitespace'],
    'IS_STOP': ['Stop word'],
    'SHAPE': ['Word shape (capitalization pattern)'],
    'LENGTH': ['Token length'],
    'OP': ['Operator (quantifier)']
  };
}

/**
 * Validate SpaCy attribute structure
 */
export function validateSpacyAttribute(key: string, value: any): { isValid: boolean; error?: string } {
  if (!key || key.trim() === '') {
    return { isValid: false, error: 'Attribute name cannot be empty' };
  }

  if (key === 'OP') {
    const validOps = getOperatorOptions();
    if (typeof value === 'string' && !validOps.some(op => value.includes(op.replace(/[{}]/g, '')))) {
      return { isValid: false, error: `Invalid operator. Use one of: ${validOps.join(', ')}` };
    }
  }

  if (typeof value === 'object' && value !== null) {
    if (value.IN && !Array.isArray(value.IN)) {
      return { isValid: false, error: 'IN value must be an array' };
    }
    if (value.NOT_IN && !Array.isArray(value.NOT_IN)) {
      return { isValid: false, error: 'NOT_IN value must be an array' };
    }
  }

  return { isValid: true };
}
