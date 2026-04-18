export interface ConfigFieldMetadata {
  key: string;
  type: string;
  default_value: any;
  current_value: any;
  description: string;
  category: string;
  hot_reloadable: boolean;
  requires_restart: boolean;
  affected_components: string[];
}

export interface ConfigVersion {
  id: string;
  version_id?: string; // For backward compatibility
  created_at: string;
  created_by: string;
  description: string;
  is_active?: boolean;
  parent_version_id: string | null;
  is_factory_reset: boolean;
}

export interface ConfigResponse {
  active_version: string | null;
  config: ConfigFieldMetadata[];
}

export interface ConfigUpdateRequest {
  config_snapshot: Record<string, any>;
  description: string;
  created_by: string;
}

export interface ConfigResetRequest {
  confirm: boolean;
  reason?: string;
}

export interface HealthDiagnosticRequest {
  config: Record<string, any>;
}

export interface DiagnosticSuggestion {
  priority: 'high' | 'medium' | 'low';
  issue: string;
  suggestion: string;
  config_path: string;
  current_value: string;
  recommended_value: string;
}

export interface HealthDiagnosticResponse {
  score: number;
  score_basis: string;
  suggestions: DiagnosticSuggestion[];
}

export interface ConfigUpdateResponse {
  status: string;
  version_id: string;
  previous_version: string | null;
  changed_keys: string[];
}
