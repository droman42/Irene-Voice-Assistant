/**
 * TypeScript type definitions for React component props and state
 */

import { ReactNode } from 'react';
import { DonationData, DonationListItem, ValidationResult, JsonSchema } from './api';

// UI Component Props
export interface BadgeProps {
  children: ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info';
  className?: string;
}

export interface InputProps {
  label?: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
  required?: boolean;
  type?: 'text' | 'password' | 'email' | 'number';
  className?: string;
}

export interface TextAreaProps {
  label?: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
  required?: boolean;
  rows?: number;
  className?: string;
}

export interface ToggleProps {
  label?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
}

export interface SectionProps {
  title: string;
  children: ReactNode;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
  className?: string;
  badge?: ReactNode;
  actions?: ReactNode;
}

// Layout Component Props
export interface LayoutProps {
  children: ReactNode;
}

export interface SidebarProps {
  collapsed: boolean;
  onToggle: (collapsed: boolean) => void;
}

export interface HeaderProps {
  connectionStatus?: 'connected' | 'disconnected' | 'connecting';
  systemInfo?: {
    version?: string;
    uptime?: string;
    handlersCount?: number;
    donationsCount?: number;
  };
}

// Editor Component Props
export interface ArrayOfStringsEditorProps {
  label: string;
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
}

interface Parameter {
  name: string;
  type: 'string' | 'integer' | 'float' | 'duration' | 'datetime' | 'boolean' | 'choice' | 'entity';
  required: boolean;
  default_value?: string;
  description?: string;
  choices?: string[];
  pattern?: string;
  min_value?: number;
  max_value?: number;
  aliases?: string[];
  extraction_patterns?: Array<Record<string, any>>;
}

export interface ParameterListEditorProps {
  value: Parameter[];
  onChange: (value: Parameter[]) => void;
  availableParams?: string[];
  disabled?: boolean;
}

export interface TokenPatternsEditorProps {
  value: Array<Array<Record<string, any>>>;
  onChange: (value: Array<Array<Record<string, any>>>) => void;
  globalParams?: string[];
  disabled?: boolean;
}

export interface SlotPatternsEditorProps {
  value: Record<string, Array<Array<Record<string, any>>>>;
  onChange: (value: Record<string, Array<Array<Record<string, any>>>>) => void;
  globalParams?: string[];
  disabled?: boolean;
}

export interface ExamplesEditorProps {
  value: Array<string | { text: string; parameters: Record<string, any> }>;
  onChange: (value: Array<string | { text: string; parameters: Record<string, any> }>) => void;
  globalParams?: string[];
  disabled?: boolean;
}

// Donations Component Props
export interface HandlerListProps {
  handlers: DonationListItem[];
  selectedHandler?: string;
  onSelect: (handlerName: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  filterDomain: string;
  onFilterDomainChange: (domain: string) => void;
  filterMethodCount: string;
  onFilterMethodCountChange: (filter: string) => void;
  filterModified: boolean;
  onFilterModifiedChange: (modified: boolean) => void;
  bulkSelection: string[];
  onBulkSelectionChange: (selection: string[]) => void;
  hasChanges: Record<string, boolean>;
  loading?: boolean;
  error?: string;
}

export interface ApplyChangesBarProps {
  visible: boolean;
  selectedHandler?: string;
  hasUnsavedChanges: boolean;
  onSave: () => Promise<void>;
  onValidate: () => Promise<ValidationResult>;
  onCancel: () => void;
  loading?: boolean;
  lastSaved?: Date;
}

export interface MethodDonationEditorProps {
  value: DonationData;
  onChange: (value: DonationData) => void;
  globalParamNames: string[];
  schema?: JsonSchema;
  validationResult?: ValidationResult;
  disabled?: boolean;
  showRawJson?: boolean;
  onToggleRawJson?: () => void;
}

// Page Component Props and State
export interface DonationsPageState {
  donations: Record<string, DonationData>;
  originalDonations: Record<string, DonationData>;
  donationsList: DonationListItem[];
  schema: JsonSchema | null;
  selectedHandler: string | null;
  hasChanges: Record<string, boolean>;
  searchQuery: string;
  filterDomain: string;
  filterMethodCount: string;
  filterModified: boolean;
  bulkSelection: string[];
  showRawJson: boolean;
  loading: boolean;
  error: string | null;
  validationResults: Record<string, ValidationResult>;
  lastSaved: Date | null;
}

// Search and Filter Types
export interface SearchFilters {
  query: string;
  domain: string;
  methodCount: string;
  modified: boolean;
}

export interface BulkOperationResult {
  success: boolean;
  message: string;
  results: Array<{
    handler: string;
    success: boolean;
    error?: string;
  }>;
}

// Configuration Types (for future use)
export interface ConfigSection {
  name: string;
  title: string;
  description?: string;
  fields: ConfigField[];
}

export interface ConfigField {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'select' | 'array' | 'object';
  label: string;
  description?: string;
  required?: boolean;
  default?: any;
  options?: Array<{ value: any; label: string }>;
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
  };
}

// Monitoring Types (for future use)
export interface MonitoringData {
  system: {
    status: 'healthy' | 'warning' | 'error';
    uptime: string;
    memory_usage: number;
    cpu_usage: number;
  };
  components: Array<{
    name: string;
    status: 'healthy' | 'warning' | 'error';
    last_update: string;
    details?: any;
  }>;
  metrics: {
    requests_per_minute: number;
    error_rate: number;
    response_time_avg: number;
  };
  activity: Array<{
    timestamp: string;
    type: 'info' | 'warning' | 'error';
    message: string;
    component?: string;
  }>;
}
