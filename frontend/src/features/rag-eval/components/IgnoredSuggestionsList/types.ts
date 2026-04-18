/**
 * 已忽略建议列表类型定义
 */

/** 建议类型 */
export type IgnoredSuggestionType = 'config' | 'prompt';

/** 忽略范围 */
export type IgnoredSuggestionScope = 'report' | 'test_set';

/** 已忽略建议项 */
export interface IgnoredSuggestion {
  id: string;
  param_name: string;
  name_zh?: string;
  suggestion_type: IgnoredSuggestionType;
  ignore_scope: IgnoredSuggestionScope;
  ignored_at?: string;
  ignored_by?: string;
  ignore_reason?: string | null;
  restored: boolean;
  restored_at?: string | null;
}

/** 已忽略建议列表响应 */
export interface IgnoredSuggestionResponse {
  items: IgnoredSuggestion[];
  total: number;
}

/** 恢复忽略建议响应 */
export interface RestoreIgnoredSuggestionResponse {
  id: string;
  restored: boolean;
  restored_at?: string | null;
  message: string;
}
