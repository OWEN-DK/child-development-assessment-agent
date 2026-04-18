/**
 * 推荐面板类型定义
 */

/** 调优建议来源 */
export type SuggestionSource = 'rule_engine' | 'history' | 'llm';

/** 调优建议 */
export interface TuningSuggestion {
  id: string;
  param_name: string;
  current_value?: Record<string, unknown>;
  suggested_value?: Record<string, unknown>;
  action?: string;
  reason?: string;
  expected_effect?: Record<string, unknown>;
  priority?: 'high' | 'medium' | 'low';
  source?: SuggestionSource;
  applied: boolean;
}

/** 建议状态 */
export interface SuggestionState {
  adopted: Set<string>;
  ignored: Set<string>;
}

/** 推荐面板模式 */
export type RecommendationMode = 'recommendation' | 'wizard' | 'expert';

/** 忽略建议请求 */
export interface IgnoreSuggestionRequest {
  scope: 'report' | 'test_set';
  reason?: string;
  test_set_id: string;
  report_id?: string;
  param_name: string;
}

/** 忽略建议响应 */
export interface IgnoreSuggestionResponse {
  message: string;
  suggestion_id: string;
}
