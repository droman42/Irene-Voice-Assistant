/**
 * spaCy Token Attributes for Pattern Matching
 * 
 * Comprehensive list of spaCy token attributes that can be used in token patterns,
 * organized by category with type information and descriptions.
 */

export type AttributeValueType = 'text' | 'boolean' | 'enum' | 'list' | 'regex' | 'number';

export interface SpacyAttribute {
  key: string;
  label: string;
  description: string;
  valueType: AttributeValueType;
  category: string;
  examples?: string[];
  enumValues?: string[];
  supportsIN?: boolean; // Whether it can use {"IN": [...]} syntax
  supportsRegex?: boolean;
}

export interface AttributeCategory {
  name: string;
  label: string;
  description: string;
  color: string;
}

export const ATTRIBUTE_CATEGORIES: Record<string, AttributeCategory> = {
  text: {
    name: 'text',
    label: 'Text Matching',
    description: 'Attributes for matching text content',
    color: 'blue'
  },
  character: {
    name: 'character',
    label: 'Character Types',
    description: 'Boolean attributes for character classification',
    color: 'green'
  },
  linguistic: {
    name: 'linguistic',
    label: 'Linguistic Analysis',
    description: 'Part-of-speech, dependencies, and linguistic features',
    color: 'purple'
  },
  entity: {
    name: 'entity',
    label: 'Named Entities',
    description: 'Named entity recognition attributes',
    color: 'orange'
  },
  position: {
    name: 'position',
    label: 'Position & Structure',
    description: 'Sentence and document position attributes',
    color: 'gray'
  },
  operator: {
    name: 'operator',
    label: 'Pattern Operators',
    description: 'Quantifiers and matching operators',
    color: 'red'
  },
  custom: {
    name: 'custom',
    label: 'Custom/Advanced',
    description: 'Custom attributes and advanced matching',
    color: 'indigo'
  }
};

export const SPACY_ATTRIBUTES: SpacyAttribute[] = [
  // Text Matching
  {
    key: 'TEXT',
    label: 'Exact Text',
    description: 'Match the exact text of the token',
    valueType: 'text',
    category: 'text',
    examples: ['"hello"', '"the"', '"."'],
    supportsIN: true
  },
  {
    key: 'LOWER',
    label: 'Lowercase Text',
    description: 'Match the lowercase version of the token text',
    valueType: 'text',
    category: 'text',
    examples: ['"hello"', '"world"'],
    supportsIN: true
  },
  {
    key: 'LEMMA',
    label: 'Lemma',
    description: 'Match the lemmatized form of the token',
    valueType: 'text',
    category: 'text',
    examples: ['"be"', '"go"', '"run"'],
    supportsIN: true
  },
  {
    key: 'NORM',
    label: 'Normalized Text',
    description: 'Match the normalized form of the token',
    valueType: 'text',
    category: 'text',
    supportsIN: true
  },

  // Character Types
  {
    key: 'IS_ALPHA',
    label: 'Is Alphabetic',
    description: 'Token consists of alphabetic characters',
    valueType: 'boolean',
    category: 'character',
    examples: ['true', 'false']
  },
  {
    key: 'IS_ASCII',
    label: 'Is ASCII',
    description: 'Token consists of ASCII characters',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_DIGIT',
    label: 'Is Digit',
    description: 'Token consists of digits',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_LOWER',
    label: 'Is Lowercase',
    description: 'Token is lowercase',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_UPPER',
    label: 'Is Uppercase',
    description: 'Token is uppercase',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_TITLE',
    label: 'Is Title Case',
    description: 'Token is title case',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_PUNCT',
    label: 'Is Punctuation',
    description: 'Token is punctuation',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_SPACE',
    label: 'Is Whitespace',
    description: 'Token is whitespace',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_STOP',
    label: 'Is Stop Word',
    description: 'Token is a stop word',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_BRACKET',
    label: 'Is Bracket',
    description: 'Token is a bracket',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_QUOTE',
    label: 'Is Quote',
    description: 'Token is a quotation mark',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_LEFT_PUNCT',
    label: 'Is Left Punctuation',
    description: 'Token is left punctuation',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_RIGHT_PUNCT',
    label: 'Is Right Punctuation',
    description: 'Token is right punctuation',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'IS_CURRENCY',
    label: 'Is Currency',
    description: 'Token is a currency symbol',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'LIKE_NUM',
    label: 'Like Number',
    description: 'Token resembles a number',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'LIKE_URL',
    label: 'Like URL',
    description: 'Token resembles a URL',
    valueType: 'boolean',
    category: 'character'
  },
  {
    key: 'LIKE_EMAIL',
    label: 'Like Email',
    description: 'Token resembles an email',
    valueType: 'boolean',
    category: 'character'
  },

  // Linguistic Analysis
  {
    key: 'POS',
    label: 'Part of Speech',
    description: 'Coarse-grained part-of-speech tag',
    valueType: 'enum',
    category: 'linguistic',
    enumValues: [
      'ADJ', 'ADP', 'ADV', 'AUX', 'CCONJ', 'DET', 'INTJ', 'NOUN', 
      'NUM', 'PART', 'PRON', 'PROPN', 'PUNCT', 'SCONJ', 'SYM', 
      'VERB', 'X', 'SPACE'
    ],
    supportsIN: true
  },
  {
    key: 'TAG',
    label: 'Fine-grained POS Tag',
    description: 'Fine-grained part-of-speech tag',
    valueType: 'text',
    category: 'linguistic',
    supportsIN: true
  },
  {
    key: 'DEP',
    label: 'Dependency Label',
    description: 'Syntactic dependency label',
    valueType: 'enum',
    category: 'linguistic',
    enumValues: [
      'ROOT', 'nsubj', 'dobj', 'iobj', 'csubj', 'ccomp', 'xcomp',
      'amod', 'nmod', 'nummod', 'appos', 'det', 'case', 'mark',
      'aux', 'auxpass', 'cop', 'advmod', 'neg', 'prep', 'prt',
      'agent', 'expl', 'attr', 'oprd', 'pobj', 'dative', 'meta',
      'parataxis', 'conj', 'cc', 'punct'
    ],
    supportsIN: true
  },
  {
    key: 'MORPH',
    label: 'Morphological Features',
    description: 'Morphological analysis',
    valueType: 'text',
    category: 'linguistic'
  },

  // Named Entities
  {
    key: 'ENT_TYPE',
    label: 'Entity Type',
    description: 'Named entity type',
    valueType: 'enum',
    category: 'entity',
    enumValues: [
      'PERSON', 'ORG', 'GPE', 'LOC', 'PRODUCT', 'EVENT', 'WORK_OF_ART',
      'LAW', 'LANGUAGE', 'DATE', 'TIME', 'PERCENT', 'MONEY', 'QUANTITY',
      'ORDINAL', 'CARDINAL', 'NORP', 'FAC'
    ],
    supportsIN: true
  },
  {
    key: 'ENT_IOB',
    label: 'Entity IOB',
    description: 'IOB code of named entity tag',
    valueType: 'enum',
    category: 'entity',
    enumValues: ['B', 'I', 'O']
  },
  {
    key: 'ENT_KB_ID',
    label: 'Entity KB ID',
    description: 'Knowledge base ID of the entity',
    valueType: 'text',
    category: 'entity'
  },

  // Position & Structure
  {
    key: 'SENT_START',
    label: 'Sentence Start',
    description: 'Token starts a sentence',
    valueType: 'boolean',
    category: 'position'
  },
  {
    key: 'IS_SENT_START',
    label: 'Is Sentence Start',
    description: 'Token is at sentence start',
    valueType: 'boolean',
    category: 'position'
  },
  {
    key: 'IS_SENT_END',
    label: 'Is Sentence End',
    description: 'Token is at sentence end',
    valueType: 'boolean',
    category: 'position'
  },

  // Pattern Operators
  {
    key: 'OP',
    label: 'Operator',
    description: 'Quantifier for pattern matching',
    valueType: 'enum',
    category: 'operator',
    enumValues: [
      '!',    // Match exactly 0 times (negation)
      '?',    // Match 0 or 1 times (optional)
      '+',    // Match 1 or more times
      '*'     // Match 0 or more times
    ]
  },

  // Length and Shape
  {
    key: 'LENGTH',
    label: 'Token Length',
    description: 'Character length of the token',
    valueType: 'number',
    category: 'character'
  },
  {
    key: 'SHAPE',
    label: 'Token Shape',
    description: 'Orthographic shape of token',
    valueType: 'text',
    category: 'character',
    examples: ['"Xxxxx"', '"dd/dd/dddd"', '"XX"']
  }
];

export const getAttributesByCategory = (category: string): SpacyAttribute[] => {
  return SPACY_ATTRIBUTES.filter(attr => attr.category === category);
};

export const getAttributeByKey = (key: string): SpacyAttribute | undefined => {
  return SPACY_ATTRIBUTES.find(attr => attr.key === key);
};

export const getCategoryColor = (category: string): string => {
  return ATTRIBUTE_CATEGORIES[category]?.color || 'gray';
};

export const isValidAttributeValue = (attribute: SpacyAttribute, value: any): boolean => {
  switch (attribute.valueType) {
    case 'boolean':
      return typeof value === 'boolean';
    case 'number':
      return typeof value === 'number';
    case 'text':
      return typeof value === 'string';
    case 'enum':
      return attribute.enumValues?.includes(String(value)) || false;
    case 'list':
      return Array.isArray(value);
    default:
      return true;
  }
};
