/**
 * 配置版本对比组件类型定义
 */

export interface ConfigVersionInfo {
  id: string;
  version_label: string;
  version_number: number;
  created_at: string | null;
}

export interface ConfigDiffItem {
  key: string;
  old_value: unknown;
  new_value: unknown;
}

export interface ConfigDiff {
  added: Record<string, unknown>;
  removed: Record<string, unknown>;
  changed: ConfigDiffItem[];
}

export interface ConfigComparisonData {
  from_version: ConfigVersionInfo;
  to_version: ConfigVersionInfo;
  diff: ConfigDiff;
}

export interface ConfigVersionComparisonProps {
  fromVersionId: string;
  toVersionId: string;
}
