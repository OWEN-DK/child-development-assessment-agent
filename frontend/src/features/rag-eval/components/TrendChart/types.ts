/**
 * 趋势图表类型定义
 */

export interface TrendRun {
  run_id: string;
  value: number;
  started_at: string | null;
}

export interface ConfigChange {
  change_set_id: string;
  change_set_label: string;
  status: string;
  rollback_reason: string | null;
  created_at: string | null;
}

export interface TrendDataPoint {
  version_id: string;
  version_label: string;
  created_at: string | null;
  run_count: number;
  mean: number;
  min: number;
  max: number;
  runs: TrendRun[];
  config_changes: ConfigChange[];
}

export interface TrendChartProps {
  testSetId: string;
  metric?: string;
  days?: number;
  height?: number;
}
