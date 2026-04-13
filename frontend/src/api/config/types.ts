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
  config: Record<string, any>;
  description: string;
  created_by: string;
}

export interface ConfigUpdateResponse {
  status: string;
  version_id: string;
  previous_version: string | null;
  changed_keys: string[];
}

export interface ConfigPlaygroundState {
  baseVersion: ConfigVersion | null;
  draftChanges: Record<string, any>;
  isRunning: boolean;
  lastResult: any | null;
  comparisonBaseline: string | null;
}
