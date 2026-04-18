/**
 * 提示词对比类型定义
 */

/** 提示词对比数据 */
export interface PromptComparison {
  prompt_key: string;
  prompt_name_zh?: string;
  current_version: PromptVersion;
  suggested_version: PromptVersion;
  diff_summary: DiffSummary;
  impact_analysis: ImpactAnalysis;
}

/** 提示词版本信息 */
export interface PromptVersion {
  version: string;
  version_number?: number;
  content: string;
  created_at?: string;
  created_by?: string;
  change_summary?: string;
}

/** 差异摘要 */
export interface DiffSummary {
  lines_added: number;
  lines_removed: number;
  lines_modified: number;
  lines_unchanged: number;
  summary: string;
}

/** 影响分析 */
export interface ImpactAnalysis {
  expected_effects: string[];
  risk_warnings: string[];
  affected_features: string[];
}

/** 提示词对比模态框属性 */
export interface PromptComparisonModalProps {
  visible: boolean;
  promptKey: string;
  currentVersion?: string;
  targetVersion?: string;
  onClose: () => void;
}
