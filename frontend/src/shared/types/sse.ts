/**
 * SSE事件类型定义
 * 
 * 定义RAG评估工作流中全部10种SSE事件的TypeScript类型。
 * 所有事件通过SSEPublisher.publish()发布，消息格式统一为JSON对象，必须包含type字段标识事件类型。
 * 
 * 注意：spec定义10种事件（9种业务事件 + 1种系统事件heartbeat）。
 * export_failed不是独立事件类型，而是导出失败时的错误处理场景。
 */

// 集合指标
export interface OverallMetrics {
  precision: number;
  recall: number;
  f1: number;
  mrr: number;
  ndcg: number;
}

// 单层校验摘要
export interface ValidationSummaryItem {
  status: string;
  suggestion_count?: number;
}

// 10种SSE事件联合类型
export type SseEvent =
  | { type: 'run_started'; run_id: string; test_set_id: string; total_cases: number; config_version?: string; timestamp: string }
  | { type: 'progress'; run_id: string; current_case: number; total_cases: number; current_query?: string; elapsed_seconds?: number; timestamp: string }
  | { type: 'case_result'; run_id: string; case_id: string; query: string; hit_at_1: boolean; hit_at_3: boolean; hit_at_5: boolean; matched_doc_ids: string[]; matched_doc_scores: number[]; status: 'passed' | 'failed'; timestamp: string }
  | { type: 'test_completed'; run_id: string; total_cases: number; passed_cases: number; overall_metrics: OverallMetrics; timestamp: string }
  | { type: 'validation_started'; run_id: string; layer: number; timestamp: string }
  | { type: 'validation_completed'; run_id: string; layer: number; duration_ms: number; suggestion_count: number; timestamp: string }
  | { type: 'report_ready'; run_id: string; report_id: string; overall_metrics: OverallMetrics; total_duration_seconds: number; validation_summary: Record<string, ValidationSummaryItem>; timestamp: string }
  | { type: 'run_failed'; run_id: string; error_code: string; error_message: string; failed_at_case_id?: string; timestamp: string }
  | { type: 'heartbeat'; run_id: string; timestamp: string }
  | { type: 'export_ready'; task_id: string; report_id: string; download_url: string; file_size_bytes: number; timestamp: string }
  | { type: 'export_failed'; task_id: string; report_id: string; error: string; timestamp: string }
  | { type: 'reconnect_failed' };  // 客户端内部事件

// 事件处理器类型
export type SseEventHandler = (event: SseEvent) => void;

// 恢复状态接口
export interface RecoveryState {
  run_id: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  current: number;
  total: number;
  percentage?: number;
  last_case_result?: {
    case_id: string;
    query?: string;
    hit_at_1: boolean;
    hit_at_3: boolean;
    hit_at_5: boolean;
  };
  metrics?: OverallMetrics;
  validation_results?: unknown[];
  report_id?: string;
  error?: string;
  error_code?: string;
  started_at?: string;
  completed_at?: string;
  elapsed_seconds?: number;
}
