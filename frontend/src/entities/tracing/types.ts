/** 追踪系统 TypeScript 类型定义 */

export interface Trace {
  trace_id: string;
  name: string;
  user_id: string | null;
  session_id: string | null;
  metadata: Record<string, any> | null;
  start_time: string;
  end_time: string | null;
  total_duration_ms: number;
  total_tokens: number;
  total_cost: string | null;
  status: 'success' | 'failed' | 'partial';
  created_at: string;
}

export interface Span {
  span_id: string | null;
  parent_span_id: string | null;
  name: string;
  duration_ms: number | null;
  tokens: number | null;
  status: 'success' | 'error';
  prompt_messages: any[] | null;
  completion_message: string | null;
  call_parameters: Record<string, any> | null;
  error: string | null;
}

export interface TraceDetail extends Trace {
  spans: Span[];
}

export interface LLMCallLog {
  id: number;
  trace_id: string | null;
  span_id: string | null;
  model_name: string;
  tokens: number | null;
  cost: string | null;
  level: 'INFO' | 'WARNING' | 'ERROR';
  created_at: string;
}

export interface LLMCallLogDetail extends LLMCallLog {
  parent_span_id: string | null;
  prompt_messages: any[] | null;
  completion_message: string | null;
  call_parameters: Record<string, any> | null;
  model_parameters: Record<string, any> | null;
  tags: any[] | null;
  completion_start_time_ms: number | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface CostAnalysis {
  total_cost: string;
  total_tokens: number;
  total_calls: number;
  avg_cost_per_call: string;
  model_stats: Array<{
    model: string;
    calls: number;
    tokens: number;
    cost: number;
  }>;
}

export interface LatencyDistribution {
  p50: number;
  p95: number;
  p99: number;
  avg: number;
  min: number;
  max: number;
}

export interface ErrorAnalysis {
  total_errors: number;
  error_types: Array<{
    type: string;
    count: number;
    examples: Array<{
      trace_id: string | null;
      span_id: string | null;
      message: string;
    }>;
  }>;
}

export interface TraceFilters {
  start_time?: string;
  end_time?: string;
  status?: string;
  user_id?: string;
  trace_id?: string;
  models?: string[];
  scenes?: string[];
  tags?: string[];
}
