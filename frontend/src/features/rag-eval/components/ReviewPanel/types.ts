/**
 * 审查面板类型定义
 */

/** 已采纳建议项 */
export interface AdoptedSuggestion {
  id: string;
  param_name: string;
  current_value: unknown;
  suggested_value: unknown;
  custom_value?: unknown;
  reason?: string;
  expected_effect?: Record<string, unknown>;
  risk?: string;
  source_version?: string;
}

/** 审查项（用于展示） */
export interface ReviewItem {
  adopted: AdoptedSuggestion;
  index: number;
}

/** 影响预览聚合数据 */
export interface ImpactPreview {
  metrics: Record<string, {
    current: number;
    predicted_min: number;
    predicted_max: number;
    delta_min: number;
    delta_max: number;
  }>;
  total_changes: number;
}

/** 保存版本请求 */
export interface SaveVersionRequest {
  adopted_suggestions: Array<{
    id: string;
    param_name: string;
    value: unknown;
  }>;
  description?: string;
}

/** 保存版本响应 */
export interface SaveVersionResponse {
  version_id: string;
  message: string;
}
